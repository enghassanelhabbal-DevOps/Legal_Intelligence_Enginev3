"""plan.py — ResolvedRuntimePlan: the single canonical source of
device/batch/candidate/resource policy for dense retrieval, reranking, and
generation.

Before this module: `RuntimeConfig` (core/models.py) was constructed with
static, hand-set defaults (device="auto", dense_batch_size=32, ...)
independent of what hardware was actually discovered, and
`retrieval/pipeline.py`'s own `configure_runtime()` made its own in-process
`torch.cuda.is_available()` call — a second, unprotected hardware probe
duplicating (and bypassing the safety of) `runtime.hardware.probe_cuda()`'s
isolated-subprocess design (DR-028).

`ResolvedRuntimePlan` closes both gaps without touching retrieval
algorithms: hardware/profile/budget are resolved exactly ONCE, through the
existing safe `discover_hardware()` -> `resolve_profile()` ->
`budget_for_profile()` chain, and every downstream `RuntimeConfig`/
`PipelineConfig`/generation config is *derived* from that single resolution
via `to_runtime_config()`/`to_pipeline_config()`/`to_generation_config()`
rather than being independently guessed by each layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.legal_ai.core.models import PipelineConfig, RuntimeConfig
from src.legal_ai.runtime.budgets import ResourceBudget, budget_for_profile
from src.legal_ai.runtime.hardware import HardwareSnapshot, discover_hardware
from src.legal_ai.runtime.profiles import ExecutionProfile, resolve_profile


@dataclass(frozen=True)
class ResolvedRuntimePlan:
    """The canonical, centrally-owned runtime resolution for one process.

    Every device / precision / batch / candidate / worker / timeout
    decision that dense retrieval, reranking, and generation make should
    trace back to this object instead of being independently hand-set or
    independently re-probed.
    """

    hardware: HardwareSnapshot
    profile: ExecutionProfile
    budget: ResourceBudget
    device: str  # "cpu" | "cuda:N" — resolved once, from the safely-probed hardware snapshot
    precision: str  # "fp32" | "auto" — "auto" defers bf16-vs-fp16 choice to choose_dtype()

    # ------------------------------------------------------------------
    # Derivation into the config shapes existing code already consumes.
    # These are pure translations — none of them touch retrieval, ranking,
    # or generation *logic*.
    # ------------------------------------------------------------------

    def to_runtime_config(self) -> RuntimeConfig:
        """Derive the `RuntimeConfig` dense/reranking code already
        consumes, so `dense.py`/`cross_encoder.py`/`pipeline.py` need no
        change to their retrieval semantics — only to how their config is
        constructed.
        """
        gpu_id = 0
        if self.device.startswith("cuda:"):
            gpu_id = int(self.device.split(":", 1)[1])
        return RuntimeConfig(
            device="cuda" if self.device.startswith("cuda") else "cpu",
            gpu_id=gpu_id,
            precision=self.precision,
            dense_batch_size=self.budget.dense_batch_size,
            rerank_batch_size=self.budget.rerank_batch_size,
            num_threads=self.hardware.cpu_topology.effective_cores,
            enable_tf32=self.profile == ExecutionProfile.ACCELERATED,
            compile_reranker=False,  # never enabled by policy resolution alone (CC 5.2 dev target)
            max_seq_length=self.budget.max_seq_length,
        )

    def to_pipeline_config(self, base: PipelineConfig | None = None) -> PipelineConfig:
        """Derive candidate-count policy from the resolved budget,
        preserving every other `PipelineConfig` field (alpha, final_k,
        rerank_max_chars, max_context_chars) the caller already tuned —
        this only bounds the resource-sensitive candidate counts, it never
        changes fusion/ranking algorithm parameters.
        """
        base = base or PipelineConfig()
        cap = self.budget.max_candidates
        rerank_on = self.budget.rerank_batch_size > 0
        return PipelineConfig(
            dense_candidates=min(base.dense_candidates, cap),
            bm25_candidates=min(base.bm25_candidates, cap),
            rerank_candidates=min(base.rerank_candidates, cap) if rerank_on else 0,
            final_k=base.final_k,
            rerank_max_chars=base.rerank_max_chars,
            alpha=base.alpha,
            max_context_chars=base.max_context_chars,
        )

    def to_generation_config(self, base: dict[str, Any] | None = None) -> dict[str, Any]:
        """Derive `LLMManager` config overrides from resolved resource
        policy. Both backend config dataclasses (`QwenConfig`,
        `OpenAICompatibleConfig`) apply overrides via `hasattr()`, so a key
        one backend doesn't define is silently ignored by the other — this
        does not change backend-selection logic or prompt/generation
        semantics, only bounds/timeouts.
        """
        cfg: dict[str, Any] = dict(base or {})
        cfg.setdefault("timeout_s", int(self.budget.request_timeout_seconds))
        if self.profile == ExecutionProfile.REMOTE_LLM and "backend" not in cfg:
            cfg["backend"] = "openai_compatible"
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.value,
            "device": self.device,
            "precision": self.precision,
            "budget": {
                "max_workers": self.budget.max_workers,
                "max_queue_size": self.budget.max_queue_size,
                "dense_batch_size": self.budget.dense_batch_size,
                "rerank_batch_size": self.budget.rerank_batch_size,
                "max_seq_length": self.budget.max_seq_length,
                "max_candidates": self.budget.max_candidates,
                "max_retries": self.budget.max_retries,
                "request_timeout_seconds": self.budget.request_timeout_seconds,
                "memory_target_bytes": self.budget.memory_target_bytes,
            },
            "hardware": self.hardware.to_dict(),
        }


def _resolve_device(hardware: HardwareSnapshot, profile: ExecutionProfile) -> str:
    """cuda:0 only when the profile itself resolved to ACCELERATED — i.e.
    only when resolve_profile() already confirmed sufficient VRAM via the
    safely-probed hardware snapshot. Every other profile runs on CPU,
    including REMOTE_LLM (generation happens over the network, not on a
    local device)."""
    is_accelerated = profile == ExecutionProfile.ACCELERATED
    if is_accelerated and hardware.cuda.available and hardware.cuda.device_count > 0:
        return "cuda:0"
    return "cpu"


def _resolve_precision(device: str) -> str:
    if not device.startswith("cuda"):
        return "fp32"
    # Defer bf16-vs-fp16 capability selection to pipeline.choose_dtype(),
    # which already probes torch.cuda.is_bf16_supported() correctly once a
    # CUDA device is confirmed live — no need to duplicate that check here.
    return "auto"


def resolve_runtime_plan(
    *,
    override_profile: ExecutionProfile | None = None,
    remote_generation_configured: bool = False,
    probe_cuda_enabled: bool = True,
    cuda_timeout_seconds: float = 15.0,
) -> ResolvedRuntimePlan:
    """Resolve the ONE canonical runtime plan for this process.

    This is the single place device/batch/candidate/resource policy
    should be decided from scratch. Dense retrieval, reranking, and
    generation all derive their config from the returned plan rather than
    each independently guessing hardware, or worse, each making their own
    unprotected `torch.cuda.is_available()` call.
    """
    hardware = discover_hardware(
        probe_cuda_enabled=probe_cuda_enabled, cuda_timeout_seconds=cuda_timeout_seconds
    )
    profile = resolve_profile(
        hardware,
        override=override_profile,
        remote_generation_configured=remote_generation_configured,
    )
    budget = budget_for_profile(profile, cpu_topology=hardware.cpu_topology)
    device = _resolve_device(hardware, profile)
    precision = _resolve_precision(device)
    return ResolvedRuntimePlan(
        hardware=hardware, profile=profile, budget=budget, device=device, precision=precision
    )


__all__ = ["ResolvedRuntimePlan", "resolve_runtime_plan"]
