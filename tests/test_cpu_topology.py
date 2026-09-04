from __future__ import annotations

import json

import src.legal_ai.runtime.cpu_topology as cpu_topology_module
from src.legal_ai.runtime.cpu_topology import (
    ContainerRuntime,
    CPUTopology,
    discover_cpu_topology,
    recommended_thread_env,
)


def test_discover_cpu_topology_never_raises_and_effective_cores_at_least_one():
    topology = discover_cpu_topology()
    assert topology.effective_cores >= 1
    assert topology.effective_cores_source in {
        "cgroup_quota", "affinity_mask", "host_logical", "unknown_default",
    }


def test_to_dict_is_json_serializable():
    topology = discover_cpu_topology()
    json.dumps(topology.to_dict())  # must not raise; StrEnum must serialize as plain string


def test_cgroup_quota_wins_over_affinity_and_host_when_most_constrained(monkeypatch):
    """A 2-core cgroup quota on a host reporting 64 logical cores and an
    affinity mask of 32 must still resolve effective_cores to 2 — the
    quota is the actually-enforced limit (DR-029)."""
    monkeypatch.setattr(cpu_topology_module, "_logical_cores_host", lambda: 64)
    monkeypatch.setattr(cpu_topology_module, "_physical_cores_host", lambda: 32)
    monkeypatch.setattr(cpu_topology_module, "_affinity_cores", lambda: 32)
    monkeypatch.setattr(cpu_topology_module, "_cgroup_quota_cores", lambda: 2.0)
    monkeypatch.setattr(
        cpu_topology_module, "_detect_container_runtime", lambda: ContainerRuntime.KUBERNETES
    )

    topology = discover_cpu_topology()
    assert topology.effective_cores == 2
    assert topology.effective_cores_source == "cgroup_quota"
    assert topology.container_runtime == ContainerRuntime.KUBERNETES


def test_affinity_wins_over_host_logical_when_no_cgroup_quota(monkeypatch):
    """taskset/cpuset pinning without a cgroup quota — e.g. `taskset -c 0-3`
    on a 32-core host — must be respected over the raw host count."""
    monkeypatch.setattr(cpu_topology_module, "_logical_cores_host", lambda: 32)
    monkeypatch.setattr(cpu_topology_module, "_physical_cores_host", lambda: 16)
    monkeypatch.setattr(cpu_topology_module, "_affinity_cores", lambda: 4)
    monkeypatch.setattr(cpu_topology_module, "_cgroup_quota_cores", lambda: None)
    monkeypatch.setattr(
        cpu_topology_module, "_detect_container_runtime", lambda: ContainerRuntime.NONE
    )

    topology = discover_cpu_topology()
    assert topology.effective_cores == 4
    assert topology.effective_cores_source == "affinity_mask"


def test_fractional_cgroup_quota_floors_down_not_up(monkeypatch):
    """A 2.9-core quota must floor to 2 usable cores, not round up to 3 —
    rounding up would oversubscribe the real, enforced limit."""
    monkeypatch.setattr(cpu_topology_module, "_logical_cores_host", lambda: 16)
    monkeypatch.setattr(cpu_topology_module, "_physical_cores_host", lambda: 8)
    monkeypatch.setattr(cpu_topology_module, "_affinity_cores", lambda: None)
    monkeypatch.setattr(cpu_topology_module, "_cgroup_quota_cores", lambda: 2.9)
    monkeypatch.setattr(
        cpu_topology_module, "_detect_container_runtime", lambda: ContainerRuntime.DOCKER
    )

    topology = discover_cpu_topology()
    assert topology.effective_cores == 2


def test_no_signals_available_degrades_to_one_core_not_a_crash(monkeypatch):
    monkeypatch.setattr(cpu_topology_module, "_logical_cores_host", lambda: None)
    monkeypatch.setattr(cpu_topology_module, "_physical_cores_host", lambda: None)
    monkeypatch.setattr(cpu_topology_module, "_affinity_cores", lambda: None)
    monkeypatch.setattr(cpu_topology_module, "_cgroup_quota_cores", lambda: None)
    monkeypatch.setattr(
        cpu_topology_module, "_detect_container_runtime", lambda: ContainerRuntime.NONE
    )

    topology = discover_cpu_topology()
    assert topology.effective_cores == 1
    assert topology.effective_cores_source == "unknown_default"


def test_hyperthreading_detected_when_logical_exceeds_physical(monkeypatch):
    monkeypatch.setattr(cpu_topology_module, "_logical_cores_host", lambda: 16)
    monkeypatch.setattr(cpu_topology_module, "_physical_cores_host", lambda: 8)
    monkeypatch.setattr(cpu_topology_module, "_affinity_cores", lambda: 16)
    monkeypatch.setattr(cpu_topology_module, "_cgroup_quota_cores", lambda: None)
    monkeypatch.setattr(
        cpu_topology_module, "_detect_container_runtime", lambda: ContainerRuntime.NONE
    )

    topology = discover_cpu_topology()
    assert topology.hyperthreading_likely is True


def test_detect_container_runtime_reads_kubernetes_env_var(monkeypatch):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    assert cpu_topology_module._detect_container_runtime() == ContainerRuntime.KUBERNETES


def test_recommended_thread_env_uses_effective_cores_and_excludes_fabricated_torch_var():
    topology = CPUTopology(
        logical_cores_host=32, physical_cores_host=16, affinity_cores=None,
        cgroup_quota_cores=2.0, container_runtime=ContainerRuntime.DOCKER,
        hyperthreading_likely=True, effective_cores=2, effective_cores_source="cgroup_quota",
    )
    env = recommended_thread_env(topology)
    assert env["OMP_NUM_THREADS"] == "2"
    assert env["MKL_NUM_THREADS"] == "2"
    assert env["OPENBLAS_NUM_THREADS"] == "2"
    assert env["NUMEXPR_NUM_THREADS"] == "2"
    assert env["TOKENIZERS_PARALLELISM"] == "false"
    # PyTorch has no such env var — must not fabricate one callers would
    # wrongly rely on instead of calling torch.set_num_threads() explicitly.
    assert "TORCH_NUM_THREADS" not in env


def test_recommended_thread_env_does_not_mutate_os_environ(monkeypatch):
    monkeypatch.delenv("OMP_NUM_THREADS", raising=False)
    topology = discover_cpu_topology()
    recommended_thread_env(topology)
    import os

    assert "OMP_NUM_THREADS" not in os.environ
