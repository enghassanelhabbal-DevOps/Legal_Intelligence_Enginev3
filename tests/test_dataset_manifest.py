from __future__ import annotations

import json

import pytest

from src.legal_ai.core.exceptions import DatasetManifestError
from src.legal_ai.evaluation.dataset_manifest import (
    UNKNOWN,
    DatasetManifest,
    LicenseStatus,
    TaskRole,
)


def _minimal_manifest(**overrides) -> DatasetManifest:
    defaults = dict(dataset_id="ds1", dataset_version="v1", name="Test Dataset")
    defaults.update(overrides)
    return DatasetManifest(**defaults)


def test_defaults_are_explicit_unknown_not_guessed():
    m = _minimal_manifest()
    assert m.language == [UNKNOWN]
    assert m.jurisdictions == [UNKNOWN]
    assert m.license == LicenseStatus.UNKNOWN.value
    assert m.date_coverage == {"start": UNKNOWN, "end": UNKNOWN}


def test_manifest_hash_is_deterministic_for_same_content():
    m1 = _minimal_manifest(record_count=10)
    m2 = _minimal_manifest(record_count=10)
    assert m1.compute_manifest_hash() == m2.compute_manifest_hash()


def test_manifest_hash_changes_with_content():
    m1 = _minimal_manifest(record_count=10)
    m2 = _minimal_manifest(record_count=11)
    assert m1.manifest_hash != m2.manifest_hash


def test_manifest_hash_ignores_ingested_at_timestamp():
    m1 = _minimal_manifest(record_count=10, ingested_at="2020-01-01T00:00:00+00:00")
    m2 = _minimal_manifest(record_count=10, ingested_at="2025-01-01T00:00:00+00:00")
    assert m1.manifest_hash == m2.manifest_hash


def test_invalid_task_role_rejected():
    with pytest.raises(DatasetManifestError):
        _minimal_manifest(task_roles=["not_a_real_role"])


def test_valid_task_role_accepted():
    m = _minimal_manifest(task_roles=[TaskRole.KNOWLEDGE_CORPUS.value])
    assert m.task_roles == ["knowledge_corpus"]


def test_unknown_license_blocks_training_role():
    m = _minimal_manifest(task_roles=[TaskRole.RETRIEVAL_TRAINING.value])
    with pytest.raises(DatasetManifestError):
        m.require_license_known_for_training()


def test_known_license_allows_training_role():
    m = _minimal_manifest(
        task_roles=[TaskRole.RETRIEVAL_TRAINING.value],
        license=LicenseStatus.KNOWN_PERMISSIVE.value,
    )
    m.require_license_known_for_training()  # should not raise


def test_non_training_role_not_blocked_by_unknown_license():
    m = _minimal_manifest(task_roles=[TaskRole.KNOWLEDGE_CORPUS.value])
    m.require_license_known_for_training()  # should not raise


def test_round_trip_json(tmp_path):
    m = _minimal_manifest(record_count=42, jurisdictions=["EG"])
    path = tmp_path / "manifest.json"
    m.to_json(path)

    loaded = DatasetManifest.from_json(path)
    assert loaded.dataset_id == m.dataset_id
    assert loaded.record_count == 42
    assert loaded.jurisdictions == ["EG"]
    assert loaded.manifest_hash == m.manifest_hash


def test_from_json_ignores_unknown_extra_fields(tmp_path):
    payload = _minimal_manifest().to_dict()
    payload["some_future_field_not_yet_known"] = "x"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = DatasetManifest.from_json(path)
    assert loaded.dataset_id == "ds1"
