from __future__ import annotations

import json

from src.legal_ai.evaluation.dataset_intake import main


def _write_json(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _corpus_fixture():
    return [
        {
            "document_id": "1",
            "jurisdiction": "EG",
            "law_id": "law_a",
            "law_name": "Law A",
            "article_id": "1",
            "raw_text": "نص المادة الأولى",
            "normalized_text": "نص الماده الاولي",
            "embedding_text": "المادة 1: نص المادة الأولى",
        },
        {
            "document_id": "2",
            "jurisdiction": "EG",
            "law_id": "law_b",
            "law_name": "Law B",
            "article_id": "2",
            "raw_text": "نص المادة الثانية",
            "normalized_text": "نص الماده الثانيه",
            "embedding_text": "المادة 2: نص المادة الثانية",
        },
    ]


def test_profile_command_exit_zero_and_writes_manifest(tmp_path, capsys):
    docs_path = _write_json(tmp_path, "docs.json", _corpus_fixture())
    manifest_path = tmp_path / "manifest.json"

    code = main(["profile", str(docs_path), "--manifest", str(manifest_path)])
    assert code == 0
    assert manifest_path.exists()

    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "pass"
    assert out["quality_profile"]["record_count"] == 2


def test_validate_command_round_trip(tmp_path, capsys):
    docs_path = _write_json(tmp_path, "docs.json", _corpus_fixture())
    manifest_path = tmp_path / "manifest.json"
    main(["profile", str(docs_path), "--manifest", str(manifest_path)])
    capsys.readouterr()

    code = main(["validate", str(manifest_path)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["decision"] == "pass"


def test_validate_command_fails_on_bad_manifest(tmp_path, capsys):
    bad_manifest = _write_json(
        tmp_path,
        "bad.json",
        {
            "dataset_id": "x",
            "dataset_version": "v1",
            "name": "x",
            "task_roles": ["nonexistent_role"],
        },
    )
    code = main(["validate", str(bad_manifest)])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["decision"] == "fail"


def test_split_command_deterministic_output(tmp_path, capsys):
    docs_path = _write_json(tmp_path, "docs.json", _corpus_fixture() * 5)
    code = main(["split", str(docs_path), "--seed", "42"])
    out1 = json.loads(capsys.readouterr().out)
    code2 = main(["split", str(docs_path), "--seed", "42"])
    out2 = json.loads(capsys.readouterr().out)
    assert code == 0 and code2 == 0
    assert out1["split"] == out2["split"]


def test_leakage_command_clean_exits_zero(tmp_path, capsys):
    protected = _write_json(tmp_path, "protected.json", _corpus_fixture())
    candidate = _write_json(
        tmp_path,
        "candidate.json",
        [{"document_id": "999", "raw_text": "نص لا علاقة له بأي شيء آخر"}],
    )
    code = main(["leakage", str(protected), str(candidate)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["decision"] == "pass"


def test_leakage_command_contaminated_exits_nonzero(tmp_path, capsys):
    fixture = _corpus_fixture()
    protected = _write_json(tmp_path, "protected.json", fixture)
    candidate = _write_json(tmp_path, "candidate.json", [fixture[0]])  # exact duplicate
    code = main(["leakage", str(protected), str(candidate)])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["decision"] == "fail"


def test_leakage_command_vacuous_schema_mismatch_exits_nonzero(tmp_path, capsys):
    protected = _write_json(tmp_path, "protected.json", _corpus_fixture())
    candidate = _write_json(
        tmp_path, "candidate.json", [{"query": "نص", "relevant_document_ids": ["1"]}]
    )
    code = main(["leakage", str(protected), str(candidate)])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["decision"] == "fail"
    assert out["overlap"]["is_meaningful"] is False


def test_report_command_combines_profile_and_split(tmp_path, capsys):
    docs_path = _write_json(tmp_path, "docs.json", _corpus_fixture() * 5)
    code = main(["report", str(docs_path)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "quality_profile" in out
    assert "split" in out


def test_missing_input_file_returns_error_exit_code(tmp_path, capsys):
    code = main(["profile", str(tmp_path / "does_not_exist.json")])
    assert code == 2
