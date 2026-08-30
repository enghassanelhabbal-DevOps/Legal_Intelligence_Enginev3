"""dataset_intake.py — Canonical dataset intake CLI (Stage 1).

Single entry point, as required ("do not create multiple competing CLIs"):

    python -m src.legal_ai.evaluation.dataset_intake profile <documents.json> [--manifest out.json]
    python -m src.legal_ai.evaluation.dataset_intake validate <manifest.json>
    python -m src.legal_ai.evaluation.dataset_intake leakage <protected.json> <candidate.json>
    python -m src.legal_ai.evaluation.dataset_intake split <documents.json> [--seed 42]
    python -m src.legal_ai.evaluation.dataset_intake report <documents.json> [--output report.json]

Every command prints a JSON report to stdout (and optionally --output) and
returns a process exit code: 0 = success, 1 = check failed, 2 = usage/IO error.
This makes it CI-usable without parsing prose (Stage 1 §21/§37).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.legal_ai.core.exceptions import (
    DatasetManifestError,
    DatasetSplitError,
    LegalAIError,
)
from src.legal_ai.evaluation.dataset_adapters import apply_adapter
from src.legal_ai.evaluation.dataset_manifest import DatasetManifest, TaskRole
from src.legal_ai.evaluation.dataset_profiler import profile_dataset
from src.legal_ai.evaluation.leakage import assign_groups, check_overlap

_SOFTWARE_VERSION = "dataset_intake_v1"


def _load_records(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "queries" in data:
        return data["queries"]  # eval-query-set shape (build_eval_set.py output)
    if isinstance(data, list):
        return data
    raise DatasetManifestError(
        f"Unrecognized dataset shape at {path}: expected a JSON list or a dict with 'queries'."
    )


def _write_report(report: dict[str, Any], output: str | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def cmd_profile(args: argparse.Namespace) -> int:
    records = _load_records(args.documents)
    records = apply_adapter(records, args.adapter)
    profile = profile_dataset(records)

    manifest = DatasetManifest(
        dataset_id=args.dataset_id or Path(args.documents).stem,
        dataset_version=args.dataset_version,
        name=args.dataset_id or Path(args.documents).stem,
        record_count=profile.record_count,
        content_hash=profile.content_hash,
        task_roles=[TaskRole.KNOWLEDGE_CORPUS.value] if not args.task_role else [args.task_role],
    )

    report = {
        "software_version": _SOFTWARE_VERSION,
        "input": str(args.documents),
        "input_hash": profile.content_hash,
        "manifest": manifest.to_dict(),
        "quality_profile": profile.to_dict(),
        "decision": "pass" if profile.malformed_records == 0 else "fail",
    }
    if args.manifest:
        manifest.to_json(args.manifest)
    _write_report(report, args.output)
    return 0 if report["decision"] == "pass" else 1


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        manifest = DatasetManifest.from_json(args.manifest)
        manifest.require_license_known_for_training()
    except (DatasetManifestError, json.JSONDecodeError, FileNotFoundError) as exc:
        _write_report(
            {
                "software_version": _SOFTWARE_VERSION,
                "input": str(args.manifest),
                "decision": "fail",
                "errors": [str(exc)],
            },
            args.output,
        )
        return 1

    report = {
        "software_version": _SOFTWARE_VERSION,
        "input": str(args.manifest),
        "manifest_hash": manifest.manifest_hash,
        "decision": "pass",
        "errors": [],
    }
    _write_report(report, args.output)
    return 0


def cmd_leakage(args: argparse.Namespace) -> int:
    protected = _load_records(args.protected)
    candidate = _load_records(args.candidate)
    overlap = check_overlap(
        protected,
        candidate,
        candidate_text_field=args.candidate_text_field,
        candidate_id_field=args.candidate_id_field,
    )

    decision = "pass" if (overlap.is_clean and overlap.is_meaningful) else "fail"
    report = {
        "software_version": _SOFTWARE_VERSION,
        "protected_input": str(args.protected),
        "candidate_input": str(args.candidate),
        "overlap": overlap.to_dict(),
        "decision": decision,
    }
    _write_report(report, args.output)
    return 0 if decision == "pass" else 1


def cmd_split(args: argparse.Namespace) -> int:
    records = _load_records(args.documents)
    try:
        split_result = assign_groups(records, seed=args.seed)
    except DatasetSplitError as exc:
        _write_report(
            {
                "software_version": _SOFTWARE_VERSION,
                "input": str(args.documents),
                "decision": "fail",
                "errors": [str(exc)],
            },
            args.output,
        )
        return 1

    report = {
        "software_version": _SOFTWARE_VERSION,
        "input": str(args.documents),
        "split": split_result.to_dict(),
        "decision": "pass",
    }
    if args.assignments_output:
        Path(args.assignments_output).write_text(
            json.dumps(split_result.assignments, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    _write_report(report, args.output)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Combined profile + split report — the full reproducible Stage 1 report."""
    records = _load_records(args.documents)
    records = apply_adapter(records, args.adapter)
    profile = profile_dataset(records)
    split_result = assign_groups(records, seed=args.seed)

    report = {
        "software_version": _SOFTWARE_VERSION,
        "input": str(args.documents),
        "input_hash": profile.content_hash,
        "quality_profile": profile.to_dict(),
        "split": split_result.to_dict(),
        "decision": "pass" if profile.malformed_records == 0 else "fail",
    }
    _write_report(report, args.output)
    return 0 if report["decision"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataset_intake", description="Canonical dataset intake CLI (Stage 1)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_profile = sub.add_parser("profile", help="Profile a dataset and emit a manifest + report.")
    p_profile.add_argument("documents")
    p_profile.add_argument("--dataset-id", default=None)
    p_profile.add_argument("--dataset-version", default="v1")
    p_profile.add_argument("--task-role", default=None)
    p_profile.add_argument("--manifest", default=None, help="Path to write the manifest JSON.")
    p_profile.add_argument(
        "--adapter", default="identity", help="Schema adapter name (see dataset_adapters.ADAPTERS)."
    )
    p_profile.add_argument("--output", default=None, help="Path to write the report JSON.")
    p_profile.set_defaults(func=cmd_profile)

    p_validate = sub.add_parser("validate", help="Validate a manifest.")
    p_validate.add_argument("manifest")
    p_validate.add_argument("--output", default=None)
    p_validate.set_defaults(func=cmd_validate)

    p_leakage = sub.add_parser(
        "leakage", help="Check candidate dataset for overlap with a protected dataset."
    )
    p_leakage.add_argument("protected")
    p_leakage.add_argument("candidate")
    p_leakage.add_argument(
        "--candidate-text-field",
        default=None,
        help="Text field name in the candidate dataset, if different from 'raw_text'.",
    )
    p_leakage.add_argument(
        "--candidate-id-field",
        default=None,
        help="ID field name in the candidate dataset, if different from 'document_id'.",
    )
    p_leakage.add_argument("--output", default=None)
    p_leakage.set_defaults(func=cmd_leakage)

    p_split = sub.add_parser("split", help="Produce a deterministic, group-safe split assignment.")
    p_split.add_argument("documents")
    p_split.add_argument("--seed", type=int, default=42)
    p_split.add_argument("--assignments-output", default=None)
    p_split.add_argument("--output", default=None)
    p_split.set_defaults(func=cmd_split)

    p_report = sub.add_parser("report", help="Combined profile + split reproducible report.")
    p_report.add_argument("documents")
    p_report.add_argument("--seed", type=int, default=42)
    p_report.add_argument(
        "--adapter", default="identity", help="Schema adapter name (see dataset_adapters.ADAPTERS)."
    )
    p_report.add_argument("--output", default=None)
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except LegalAIError as exc:
        payload = {"decision": "fail", "errors": [str(exc)]}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 1
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        payload = {"decision": "error", "errors": [str(exc)]}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
