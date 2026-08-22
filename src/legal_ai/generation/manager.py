"""manager.py — LLM adapter manager.

Migrated from legal_ai/generation.py.
Selects the best available LLM backend (Qwen → fallback template).
Implements prompt scaffolding and basic injection detection.
"""

from __future__ import annotations

from typing import Any

from src.legal_ai.core.exceptions import GenerationError
from src.legal_ai.core.logging import get_logger

LOGGER = get_logger(__name__)

# Distinctive prompt-injection signal phrases. Deliberately NARROW: the
# previous list included "you are" and "do not", which appear constantly in
# ordinary legal/English text ("the court shall not...", "you are required
# to...") and produced false positives on legitimate legal questions. This
# is a defense-in-depth heuristic, not a security boundary — the real
# mitigation is (a) the system/user role separation below and (b) citation
# validation against retrieved evidence after generation.
_INJECTION_PATTERNS = [
    "ignore the above",
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard the system prompt",
    "system:",
    "assistant:",
]

_SYSTEM_PROMPT = (
    "أنت نظام للبحث القانوني. استخدم فقط النصوص القانونية المقدمة في 'السياق'. "
    "لا تختَرع مواداً أو أرقام مواد أو أحكامًا. لكل استنتاج، قدم إشارة مصدرية. "
    "إذا كان الدليل غير كافٍ، أبلغ بوضوح 'insufficient evidence'."
)


class LLMManager:
    """Selects and wraps an available LLM backend implementation.

    Backend selection is config-driven via `config["backend"]`:
      - "qwen_transformers" : local Qwen3 via Transformers (GPU/CPU)
      - "openai_compatible"  : any OpenAI-compatible remote endpoint
      - "auto" (default)     : try Qwen first, fall back to
                                openai_compatible if an api_key is configured

    This replaces the previous hardcoded "always try Qwen, fall back to a
    stub that raises NotImplementedError" behaviour, which meant any
    environment without a working local Qwen install (CI, Streamlit Cloud,
    CPU-only dev machines) had no working generation path at all.

    Implements:
      - Prompt-injection detection (conservative heuristic — see note above)
      - Structured prompt scaffolding with system instruction
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = config or {}
        self.backend: Any = None
        self.actual_backend: str | None = None

    # ------------------------------------------------------------------
    # Security helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_prompt_injection(text: str) -> bool:
        t = text.lower()
        return any(p in t for p in _INJECTION_PATTERNS)

    @staticmethod
    def _build_prompt(query: str, context: str) -> str:
        return (
            f"SYSTEM:\n{_SYSTEM_PROMPT}\n\n"
            f"LEGAL_CONTEXT:\n{context}\n\n"
            f"USER_QUERY:\n{query}\n\n"
            "INSTRUCTIONS:\nAnswer using ONLY the LEGAL_CONTEXT. "
            "Cite sources for every legal claim. "
            "If evidence is insufficient, say 'insufficient evidence'. "
            "Return JSON with keys: answer, citations, evidence, confidence, warnings."
        )

    # ------------------------------------------------------------------
    # Backend lifecycle
    # ------------------------------------------------------------------

    def _try_load_qwen(self) -> bool:
        try:
            from src.legal_ai.generation.backends.qwen_transformers_backend import (
                QwenConfig,
                QwenTransformersBackend,
            )

            qconf = QwenConfig()
            for k, v in self.config.items():
                if hasattr(qconf, k):
                    setattr(qconf, k, v)
            backend = QwenTransformersBackend(qconf)
            backend.load()
            self.backend = backend
            self.actual_backend = "qwen_transformers"
            LOGGER.info("Using QwenTransformersBackend")
            return True
        except Exception as exc:
            LOGGER.warning("Qwen backend unavailable: %s", exc)
            return False

    def _try_load_openai_compatible(self) -> bool:
        try:
            from src.legal_ai.generation.backends.openai_compatible_backend import (
                OpenAICompatibleBackend,
                OpenAICompatibleConfig,
            )

            oconf = OpenAICompatibleConfig()
            for k, v in self.config.items():
                if hasattr(oconf, k) and v:
                    setattr(oconf, k, v)
            if not oconf.api_key:
                LOGGER.info("openai_compatible backend skipped: no api_key configured")
                return False
            backend = OpenAICompatibleBackend(oconf)
            backend.load()
            self.backend = backend
            self.actual_backend = "openai_compatible"
            LOGGER.info("Using OpenAICompatibleBackend (model=%s)", oconf.model)
            return True
        except Exception as exc:
            LOGGER.warning("openai_compatible backend unavailable: %s", exc)
            return False

    def load(self) -> None:
        """Load the backend selected by config["backend"] (default: "auto")."""
        requested = self.config.get("backend", "auto")

        if requested == "qwen_transformers":
            if self._try_load_qwen():
                return
            raise GenerationError("Requested backend 'qwen_transformers' failed to load.")

        if requested == "openai_compatible":
            if self._try_load_openai_compatible():
                return
            raise GenerationError("Requested backend 'openai_compatible' failed to load (missing api_key?).")

        # "auto": prefer local Qwen, fall back to a remote endpoint if configured.
        if self._try_load_qwen():
            return
        if self._try_load_openai_compatible():
            return
        raise GenerationError(
            "No LLM backend available. Either install/enable local Qwen "
            "(torch/transformers + GPU or CPU offload) or set an api_key "
            "for an OpenAI-compatible endpoint in config."
        )

    def unload(self) -> None:
        if self.backend is None:
            return
        try:
            if hasattr(self.backend, "unload"):
                self.backend.unload()
        except Exception:
            pass
        finally:
            self.backend = None

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self, query: str, context: str) -> str:
        if self._detect_prompt_injection(query) or self._detect_prompt_injection(context):
            raise GenerationError("Prompt rejected: potential prompt injection detected.")

        if self.backend is None:
            self.load()

        prompt = self._build_prompt(query, context)

        if hasattr(self.backend, "generate"):
            try:
                return self.backend.generate(query, context)
            except TypeError:
                return self.backend.generate(prompt, "")

        raise GenerationError("Loaded backend does not implement generate()")

    def info(self) -> dict[str, Any]:
        if self.backend is None:
            return {"backend": None}
        if hasattr(self.backend, "info"):
            try:
                return self.backend.info()
            except Exception:
                pass
        return {"backend": self.actual_backend}


__all__ = ["LLMManager"]
