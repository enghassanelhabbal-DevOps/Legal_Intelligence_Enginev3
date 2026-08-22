"""Qwen3 Transformers backend tuned for a 4 GB Quadro M2200.

Important design choice:
- The requested FP8 checkpoint is kept as an optional model id for capable GPUs.
- On a Quadro M2200 (Maxwell SM 5.2, 4 GB), this backend automatically uses
  the non-FP8 Qwen3-4B-Thinking-2507 checkpoint with Accelerate CPU offload.
- No bitsandbytes dependency is required for the M2200 path.

The code uses tokenizer.apply_chat_template(..., return_dict=True) exactly so
that the result can be passed to model.generate(**inputs).
"""

from __future__ import annotations

import gc
import logging
import re
from dataclasses import dataclass
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

LOGGER = logging.getLogger("qwen_backend")

FP8_MODEL_ID = "Qwen/Qwen3-4B-Thinking-2507-FP8"
M2200_SAFE_MODEL_ID = "Qwen/Qwen3-4B-Thinking-2507"


@dataclass(frozen=True)
class QwenConfig:
    # User-requested checkpoint. Used only when the GPU is known to support it.
    requested_model_id: str = FP8_MODEL_ID

    # Safe fallback for Quadro M2200 / Maxwell.
    fallback_model_id: str = M2200_SAFE_MODEL_ID

    # GPU memory budget is intentionally below the physical 4 GB VRAM.
    # This leaves headroom for CUDA context, tokenizer tensors, and runtime.
    m2200_gpu_memory: str = "3.2GiB"
    cpu_memory_budget: str = "12GiB"

    # Keep prompts compact because CPU-offloaded generation is expensive.
    max_input_tokens: int = 4096
    max_new_tokens: int = 320

    # Deterministic generation is preferable for grounded legal QA.
    do_sample: bool = False
    temperature: float = 0.6
    top_p: float = 0.95

    # Disk offload is a safety valve, not the first-choice path.
    offload_folder: str = "artifacts/qwen_offload"

    trust_remote_code: bool = False


class QwenTransformersBackend:
    def __init__(self, config: QwenConfig | None = None) -> None:
        self.config = config or QwenConfig()
        self.tokenizer = None
        self.model = None
        self.actual_model_id: str | None = None
        self.device_map: dict[str, Any] | None = None
        self._input_device: torch.device | None = None

    # ------------------------------------------------------------------
    # Hardware policy
    # ------------------------------------------------------------------
    @staticmethod
    def _gpu_info() -> tuple[bool, str | None, tuple[int, int] | None, int | None]:
        """Return (available, name, (major,minor), total_memory_bytes).

        Be defensive: handle cases where CUDA is not available or device ids are invalid
        (e.g., CUDA_VISIBLE_DEVICES is empty) and avoid raising AssertionError.
        """
        try:
            if not torch.cuda.is_available():
                return False, None, None, None
            # Ensure at least one device is visible
            if torch.cuda.device_count() == 0:
                return False, None, None, None
            dev = 0
            try:
                props = torch.cuda.get_device_properties(dev)
                name = props.name
                capability = torch.cuda.get_device_capability(dev)
                vram = int(props.total_memory)
                return True, name, capability, vram
            except Exception:
                # Best-effort fallback to other getters; if any call fails, treat GPU as unavailable
                try:
                    name = torch.cuda.get_device_name(dev)
                    capability = torch.cuda.get_device_capability(dev)
                    props = torch.cuda.get_device_properties(dev)
                    vram = int(props.total_memory)
                    return True, name, capability, vram
                except Exception:
                    return False, None, None, None
        except Exception:
            return False, None, None, None

    def _select_model(self) -> str:
        available, name, capability, vram = self._gpu_info()

        # The M2200 is Maxwell SM 5.2 and has 4 GB VRAM. Never attempt the
        # user-requested FP8 checkpoint on this device.
        if available and capability is not None:
            major, minor = capability
            if (major, minor) <= (5, 2) or (vram is not None and vram < 8 * 1024**3):
                LOGGER.warning(
                    "GPU policy: %s / SM %s.%s / %.2f GB. "
                    "Using non-FP8 Qwen3-4B-Thinking-2507 with CPU offload.",
                    name,
                    major,
                    minor,
                    (vram or 0) / 1024**3,
                )
                return self.config.fallback_model_id

        # Keep the requested FP8 checkpoint for genuinely capable hardware.
        return self.config.requested_model_id

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------
    def load(self) -> None:
        if self.model is not None:
            return

        self.actual_model_id = self._select_model()
        model_id = self.actual_model_id

        LOGGER.info("Loading Qwen model: %s", model_id)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            use_fast=True,
            trust_remote_code=self.config.trust_remote_code,
        )

        # The M2200 path intentionally uses standard Transformers + Accelerate
        # device_map instead of bitsandbytes quantization. This keeps the local
        # path portable and avoids depending on GPU kernels that are not aimed
        # at Maxwell.
        available, _, _, _ = self._gpu_info()
        if available and model_id == self.config.fallback_model_id:
            try:
                # Test if PyTorch can actually execute a math kernel on the GPU
                _ = (torch.ones(1).cuda() * 2).cpu()
                gpu_works = True
            except Exception:
                gpu_works = False

            if gpu_works:
                from accelerate import infer_auto_device_map, init_empty_weights

                with init_empty_weights():
                    empty_model = AutoModelForCausalLM.from_config(
                        self._load_config(model_id),
                        torch_dtype=torch.float16,
                    )

                max_memory = {
                    0: self.config.m2200_gpu_memory,
                    "cpu": self.config.cpu_memory_budget,
                }
                device_map = infer_auto_device_map(
                    empty_model,
                    max_memory=max_memory,
                    no_split_module_classes=[
                        "Qwen2DecoderLayer",
                        "Qwen2Block",
                    ],
                )
                del empty_model
                gc.collect()
                torch.cuda.empty_cache()
            else:
                LOGGER.warning("PyTorch cannot execute on this GPU. Forcing pure CPU device_map.")
                device_map = "cpu"
                max_memory = None

            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if gpu_works else torch.bfloat16,
                device_map=device_map,
                max_memory=max_memory,
                offload_folder=self.config.offload_folder if gpu_works else None,
                offload_state_dict=True if gpu_works else False,
                low_cpu_mem_usage=True,
                trust_remote_code=self.config.trust_remote_code,
            )
            self.device_map = dict(device_map) if isinstance(device_map, dict) else {"": "cpu"}
        else:
            # Capable GPU path: use the exact requested FP8 checkpoint and let
            # Transformers determine the device placement.
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                dtype="auto",
                device_map="auto",
                low_cpu_mem_usage=True,
                trust_remote_code=self.config.trust_remote_code,
            )

        self.model.eval()
        self._input_device = self._find_input_device()

        LOGGER.info("Qwen loaded. Input device: %s", self._input_device)
        if getattr(self.model, "hf_device_map", None):
            LOGGER.info("hf_device_map=%s", self.model.hf_device_map)

    def _load_config(self, model_id: str) -> Any:
        from transformers import AutoConfig

        return AutoConfig.from_pretrained(
            model_id,
            trust_remote_code=self.config.trust_remote_code,
        )

    def _find_input_device(self) -> torch.device:
        """Return the device holding the input embedding weights."""
        embedding = self.model.get_input_embeddings()
        return embedding.weight.device

    def unload(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        self.device_map = None
        self._input_device = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ------------------------------------------------------------------
    # Prompting / generation
    # ------------------------------------------------------------------
    @staticmethod
    def build_prompt(query: str, context: str) -> list[dict[str, str]]:
        system = """
أنت مساعد قانوني للبحث في النصوص القانونية المصرية.

قواعد إلزامية:
1. استخدم فقط المعلومات الموجودة في السياق القانوني المرفق.
2. لا تخترع مادة أو رقم مادة أو عقوبة أو استثناء غير موجود في السياق.
3. إذا لم يكن السياق كافيًا للإجابة، قل بوضوح: «لا يحتوي السياق المسترجع على معلومات كافية للإجابة بشكل موثوق».  # noqa: E501
4. عند ذكر قاعدة قانونية، اذكر اسم القانون ورقم المادة من المصدر متى كانا متاحين.
5. فرّق بين «النص القانوني» و«الشرح».
6. لا تقدم استنتاجًا قانونيًا غير مدعوم بالنص المسترجع.
7. اجعل الإجابة مباشرة ومركزة، ولا تكرر النصوص الطويلة دون حاجة.
8. لا تعرض سلسلة التفكير الداخلية أو خطوات التفكير الخاصة بالنموذج. أعرض النتيجة القانونية الموجزة فقط.  # noqa: E501
""".strip()

        user = f"""
السؤال:
{query}

السياق القانوني المسترجع:
{context}

أجب بالعربية، وابدأ بالإجابة المباشرة، ثم اذكر المواد القانونية التي استندت إليها.
""".strip()

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @staticmethod
    def _strip_thinking(text: str) -> str:
        # Do not expose hidden chain-of-thought in the application output.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<\|thinking\|>.*?<\|/thinking\|>", "", text, flags=re.DOTALL | re.IGNORECASE)  # noqa: E501
        return text.strip()

    def generate(self, query: str, context: str) -> str:
        self.load()
        assert self.model is not None
        assert self.tokenizer is not None
        assert self._input_device is not None

        messages = self.build_prompt(query, context)

        # `return_dict=True` is intentional: Qwen's official Transformers
        # example returns a dict-like BatchEncoding so it can be passed to
        # model.generate(**inputs).
        inputs = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )

        inputs = {k: v.to(self._input_device) for k, v in inputs.items()}
        prompt_len = int(inputs["input_ids"].shape[-1])

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                do_sample=self.config.do_sample,
                temperature=self.config.temperature if self.config.do_sample else None,
                top_p=self.config.top_p if self.config.do_sample else None,
                use_cache=True,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        generated = outputs[0, prompt_len:]
        text = self.tokenizer.decode(generated, skip_special_tokens=True)
        return self._strip_thinking(text)

    def info(self) -> dict[str, Any]:
        available, name, capability, vram = self._gpu_info()
        return {
            "requested_model": self.config.requested_model_id,
            "actual_model": self.actual_model_id,
            "cuda_available": available,
            "gpu_name": name,
            "compute_capability": capability,
            "vram_gb": None if vram is None else round(vram / 1024**3, 2),
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
        }
