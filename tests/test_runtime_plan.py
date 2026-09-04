from __future__ import annotations

import json

from src.legal_ai.runtime.hardware import CUDAProbeResult, GPUDevice, HardwareSnapshot
from src.legal_ai.runtime.plan import ResolvedRuntimePlan, resolve_runtime_plan
from src.legal_ai.runtime.profiles import ExecutionProfile


def test_resolve_runtime_plan_never_touches_torch(monkeypatch):
    import sys

    plan = resolve_runtime_plan(probe_cuda_enabled=False)
    assert "torch" not in sys.modules
    assert isinstance(plan, ResolvedRuntimePlan)
    assert plan.device in {"cpu"}  # no CUDA probed -> never accelerated


def test_override_profile_is_respected_end_to_end():
    plan = resolve_runtime_plan(
        probe_cuda_enabled=False, override_profile=ExecutionProfile.BALANCED
    )
    assert plan.profile == ExecutionProfile.BALANCED
    # max_workers is scaled from the real host's effective core count (see
    # DR-029/budgets.budget_for_profile), so it is only guaranteed to sit
    # within BALANCED's clamp range [2, 8] here, not pinned to the old
    # static baseline of 4 — that baseline only applies when no
    # cpu_topology is supplied (see test_resource_budgets.py).
    assert 2 <= plan.budget.max_workers <= 8


def test_to_runtime_config_derives_from_budget_not_hardcoded_defaults():
    plan = resolve_runtime_plan(
        probe_cuda_enabled=False, override_profile=ExecutionProfile.CPU_MINIMAL
    )
    cfg = plan.to_runtime_config()
    assert cfg.dense_batch_size == plan.budget.dense_batch_size
    assert cfg.rerank_batch_size == plan.budget.rerank_batch_size
    assert cfg.max_seq_length == plan.budget.max_seq_length
    assert cfg.device == "cpu"


def test_to_pipeline_config_bounds_candidates_and_disables_rerank_when_budget_says_so():
    plan = resolve_runtime_plan(
        probe_cuda_enabled=False, override_profile=ExecutionProfile.CPU_MINIMAL
    )
    pcfg = plan.to_pipeline_config()
    assert pcfg.rerank_candidates == 0  # CPU_MINIMAL's rerank_batch_size is 0
    assert pcfg.dense_candidates <= plan.budget.max_candidates


def test_to_pipeline_config_preserves_caller_tuned_non_resource_fields():
    from src.legal_ai.core.models import PipelineConfig

    base = PipelineConfig(alpha=0.42, final_k=7, max_context_chars=9999)
    plan = resolve_runtime_plan(
        probe_cuda_enabled=False, override_profile=ExecutionProfile.BALANCED
    )
    pcfg = plan.to_pipeline_config(base)
    assert pcfg.alpha == 0.42
    assert pcfg.final_k == 7
    assert pcfg.max_context_chars == 9999


def test_to_generation_config_sets_timeout_from_budget():
    plan = resolve_runtime_plan(
        probe_cuda_enabled=False, override_profile=ExecutionProfile.REMOTE_LLM
    )
    gen_cfg = plan.to_generation_config()
    assert gen_cfg["timeout_s"] == int(plan.budget.request_timeout_seconds)
    assert gen_cfg["backend"] == "openai_compatible"


def test_to_generation_config_does_not_override_caller_choice():
    plan = resolve_runtime_plan(
        probe_cuda_enabled=False, override_profile=ExecutionProfile.REMOTE_LLM
    )
    gen_cfg = plan.to_generation_config({"backend": "qwen_transformers", "timeout_s": 999})
    assert gen_cfg["backend"] == "qwen_transformers"  # caller's explicit choice wins
    assert gen_cfg["timeout_s"] == 999


def test_accelerated_profile_resolves_cuda_device_without_a_second_probe():
    """Constructs a HardwareSnapshot directly (bypassing discover_hardware)
    to verify device resolution logic without needing a real GPU."""
    from src.legal_ai.runtime.budgets import budget_for_profile
    from src.legal_ai.runtime.cpu_topology import ContainerRuntime, CPUTopology
    from src.legal_ai.runtime.plan import _resolve_device, _resolve_precision
    from src.legal_ai.runtime.profiles import MIN_ACCELERATED_VRAM_BYTES, resolve_profile

    hardware = HardwareSnapshot(
        os_name="Linux", os_version="test", python_version="3.12.0",
        cpu_count_logical=8, cpu_count_physical=4,
        total_ram_bytes=16 * 1024**3, ram_probe_status="ok",
        storage_free_bytes=100 * 1024**3,
        cuda=CUDAProbeResult(
            available=True, device_count=1,
            devices=(GPUDevice(0, "Test GPU", MIN_ACCELERATED_VRAM_BYTES + 1, "8.0"),),
        ),
        cpu_topology=CPUTopology(
            logical_cores_host=8, physical_cores_host=4, affinity_cores=8,
            cgroup_quota_cores=None, container_runtime=ContainerRuntime.NONE,
            hyperthreading_likely=True, effective_cores=8, effective_cores_source="host_logical",
        ),
    )
    profile = resolve_profile(hardware)
    assert profile == ExecutionProfile.ACCELERATED
    device = _resolve_device(hardware, profile)
    assert device == "cuda:0"
    assert _resolve_precision(device) == "auto"
    budget = budget_for_profile(profile, cpu_topology=hardware.cpu_topology)
    plan = ResolvedRuntimePlan(
        hardware=hardware, profile=profile, budget=budget, device=device,
        precision=_resolve_precision(device),
    )
    cfg = plan.to_runtime_config()
    assert cfg.device == "cuda"
    assert cfg.gpu_id == 0
    assert cfg.enable_tf32 is True


def test_to_dict_is_json_serializable():
    plan = resolve_runtime_plan(probe_cuda_enabled=False)
    json.dumps(plan.to_dict())
