"""materialize_dataflare_stage1.py — produces the mandatory Stage 1 governed
dataset artifacts for the exact analyzed Dataflare corpus revision
(docs/CLAUDE_EXECUTION_MASTER.md, "Stage 1 materialization gate").

Outputs:
    artifacts/datasets/dataflare_egypt_legal_corpus_v1/manifest.json
    artifacts/datasets/dataflare_egypt_legal_corpus_v1/split_manifest.json
    artifacts/datasets/dataflare_egypt_legal_corpus_v1/manual_review_manifest.json
    artifacts/reports/dataflare_corpus_report_v1.json

Run:
    python3 scripts/materialize_dataflare_stage1.py

Deliberately stdlib + pandas only — no LLM, no embedding model, no GPU,
per the "keep Stage 1 lightweight" instruction. Resource measurement uses
the stdlib `resource` module (POSIX), not an added dependency.
"""

from __future__ import annotations

import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = REPO_ROOT / "data/raw/dataflare/egypt-legal-corpus-train-00000-of-00001.parquet"
EXPECTED_SHA256 = "a55c349e9c95faffcdf49b66c726be7ae4ed738aafd43767d8ae99f5903d4458"

sys.path.insert(0, str(REPO_ROOT))

from src.legal_ai.domain.document_type import CLASSIFIER_VERSION, classify_document  # noqa: E402
from src.legal_ai.domain.duplicate_clustering import cluster_exact_duplicates  # noqa: E402
from src.legal_ai.evaluation.leakage import assign_groups, enrich_with_citation_key  # noqa: E402
from src.legal_ai.ingestion.article_segmentation import segment_articles  # noqa: E402
from src.legal_ai.ingestion.case_citation_extraction import extract_case_citation  # noqa: E402
from src.legal_ai.ingestion.text_quality_diagnostics import (  # noqa: E402
    scan_corpus_for_noise_prefix,
)

ARTICLE_SEGMENTER_VERSION = "inline_reference_filtered_v2"
CITATION_PARSER_VERSION = "regex_v1"


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _flatten(cats: Any) -> list[str]:
    if cats is None:
        return []
    try:
        return list(cats)
    except TypeError:
        return [cats]


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _peak_rss_mb() -> float:
    # ru_maxrss is KB on Linux, bytes on macOS — this environment is Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def main() -> None:
    t_start = time.monotonic()

    actual_sha256 = _sha256_of(CORPUS_PATH)
    if actual_sha256 != EXPECTED_SHA256:
        raise SystemExit(
            f"SHA-256 mismatch: expected {EXPECTED_SHA256}, got {actual_sha256}. "
            f"Refusing to materialize artifacts against an unverified file."
        )

    df = pd.read_parquet(CORPUS_PATH)
    records = df.to_dict("records")
    record_count = len(records)
    total_tokens = int(df["tokens"].sum())

    # --- classification -------------------------------------------------
    doc_type_results = [
        classify_document(r["text"], _flatten(r.get("categories"))) for r in records
    ]
    doc_type_dist: dict[str, int] = {}
    for res in doc_type_results:
        doc_type_dist[res.document_type.value] = doc_type_dist.get(res.document_type.value, 0) + 1

    # --- category distribution ------------------------------------------
    cat_dist: dict[str, int] = {}
    for r in records:
        for c in _flatten(r.get("categories")):
            cat_dist[c] = cat_dist.get(c, 0) + 1

    # --- duplicate clustering --------------------------------------------
    clusters = cluster_exact_duplicates(records, text_field="text", metadata_fields=["law_name"])
    multi_member = [c for c in clusters if len(c.member_record_ids) > 1]
    metadata_variant = [c for c in multi_member if c.relation == "metadata_variant"]

    # --- citation extraction coverage ------------------------------------
    citations = [extract_case_citation(r["text"]) for r in records]
    case_like = [c for c in citations if c.is_case_ruling]
    clean_citations = [c for c in case_like if c.citation_key()]

    # --- article segmentation on non-case-like records --------------------
    statute_like_idx = [i for i, c in enumerate(citations) if not c.is_case_ruling]
    seg_results = [segment_articles(records[i]["text"]) for i in statute_like_idx]
    zero_marker = sum(1 for r in seg_results if r.marker_count == 0)

    # --- noise-prefix diagnostic (full corpus) -----------------------------
    noise_records = [{"document_id": str(i), "raw_text": r["text"]} for i, r in enumerate(records)]
    noise_report = scan_corpus_for_noise_prefix(noise_records)

    # --- unicode profile ----------------------------------------------------
    combining_hamza = ["\u0654", "\u0655"]
    law_names_with_combining = sum(
        1
        for r in records
        if isinstance(r.get("law_name"), str) and any(c in r["law_name"] for c in combining_hamza)
    )
    law_names_resolved_by_nfc = sum(
        1
        for r in records
        if isinstance(r.get("law_name"), str)
        and unicodedata.normalize("NFC", r["law_name"]) != r["law_name"]
    )

    # --- leakage-safe grouping / split roles --------------------------------
    enriched = [enrich_with_citation_key(r, text_field="text") for r in records]
    for i, rec in enumerate(enriched):
        rec["_row_index"] = i
    split_result = assign_groups(
        enriched,
        id_field="_row_index",
        seed=42,
        ratios={"knowledge": 0.6, "development": 0.2, "protected_evaluation_candidates": 0.2},
    )

    # quarantine: records in metadata-variant duplicate clusters (flagged for
    # manual review before being trusted in any role)
    quarantine_ids: set[str] = set()
    for c in metadata_variant:
        quarantine_ids.update(c.member_record_ids)

    role_assignments: dict[str, str] = {}
    for rec_id, split_name in split_result.assignments.items():
        role_assignments[rec_id] = "quarantine" if rec_id in quarantine_ids else split_name
    for rec_id in quarantine_ids:
        role_assignments[rec_id] = "quarantine"

    role_counts: dict[str, int] = {}
    for role in role_assignments.values():
        role_counts[role] = role_counts.get(role, 0) + 1

    # --- resource measurement -----------------------------------------------
    wall_time_s = time.monotonic() - t_start
    resource_meta = {
        "wall_time_seconds": round(wall_time_s, 3),
        "peak_rss_mb": round(_peak_rss_mb(), 1),
        "python_version": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "measurement_note": (
            "Single-process stdlib+pandas run; no LLM/embedding model/GPU "
            "loaded for this stage. peak_rss_mb via resource.getrusage "
            "(ru_maxrss, Linux=KB)."
        ),
    }

    git_commit = _git_commit()
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # ======================================================================
    # manifest.json
    # ======================================================================
    manifest = {
        "dataset_id": "dataflare_egypt_legal_corpus_v1",
        "dataset_version": "v1",
        "source": "dataflare/egypt-legal-corpus",
        "file_path": str(CORPUS_PATH.relative_to(REPO_ROOT)),
        "file_sha256": actual_sha256,
        "schema": {
            "columns": list(df.columns),
            "row_shape": "flattened_single_paragraph_per_record",
        },
        "record_count": record_count,
        "token_count": total_tokens,
        "license_state": "unknown",
        "provenance_state": "dataset_derived",
        "classifier_distribution": {
            "note": (
                "classifier PREDICTIONS, not verified corpus ground truth — "
                "see manual_review_manifest.json for the gold-labeling gate"
            ),
            "classifier_version": CLASSIFIER_VERSION,
            "distribution": doc_type_dist,
            "unknown_rate": round(doc_type_dist.get("unknown", 0) / record_count, 4),
        },
        "category_distribution": {
            "distinct_category_values": len(cat_dist),
            "total_category_tags": sum(cat_dist.values()),
            "top_20": dict(sorted(cat_dist.items(), key=lambda kv: -kv[1])[:20]),
        },
        "duplicate_cluster_statistics": {
            "total_clusters": len(clusters),
            "multi_member_clusters": len(multi_member),
            "records_in_multi_member_clusters": sum(len(c.member_record_ids) for c in multi_member),
            "note_on_696": (
                "696 records participate in duplicate clusters; this is NOT "
                "696 rows safe to delete — see metadata_variant_clusters below"
            ),
            "metadata_variant_clusters": len(metadata_variant),
            "exact_duplicate_clusters_no_metadata_variance": len(multi_member)
            - len(metadata_variant),
        },
        "citation_extraction": {
            "note": (
                "COVERAGE, not accuracy — no manually labeled gold sample "
                "has validated correctness yet"
            ),
            "case_like_records": len(case_like),
            "clean_citation_extractions": len(clean_citations),
            "coverage_ratio": round(len(clean_citations) / len(case_like), 4)
            if case_like
            else None,
            "parser_version": CITATION_PARSER_VERSION,
        },
        "structure_profile": {
            "note": "parser non-detection is NOT proof legal structure is absent",
            "statute_like_records_checked": len(statute_like_idx),
            "records_with_zero_markers_found": zero_marker,
            "zero_marker_ratio": round(zero_marker / len(statute_like_idx), 4)
            if statute_like_idx
            else None,
            "parser_version": ARTICLE_SEGMENTER_VERSION,
        },
        "unicode_profile": {
            "records_with_decomposed_combining_hamza_in_law_name": law_names_with_combining,
            "records_changed_by_nfc_normalization": law_names_resolved_by_nfc,
            "nfc_resolves_observed_decomposed_hamza": True,
        },
        "noise_prefix_diagnostic": noise_report.to_dict(),
        "parser_versions": {
            "document_type_classifier": CLASSIFIER_VERSION,
            "article_segmenter": ARTICLE_SEGMENTER_VERSION,
            "case_citation_parser": CITATION_PARSER_VERSION,
        },
        "software_commit": git_commit,
        "generated_at": generated_at,
        "resource_measurement": resource_meta,
    }

    # ======================================================================
    # split_manifest.json
    # ======================================================================
    split_manifest = {
        "dataset_id": "dataflare_egypt_legal_corpus_v1",
        "strategy": "citation_key_or_law_id_grouped_hash_split_v1",
        "seed": split_result.seed,
        "group_fields_preference": split_result.group_fields,
        "note": (
            "Roles reflect Stage 1 grouping design, not a scientifically "
            "validated ML train/test split. Dataflare's single 'train' "
            "split is NOT treated as a valid split here."
        ),
        "role_counts": role_counts,
        "role_assignments": role_assignments,
        "rationale": split_result.rationale
        + " Records in metadata-variant duplicate clusters are additionally "
        "quarantined regardless of their hash-based role, pending manual review.",
    }

    # ======================================================================
    # manual_review_manifest.json — stratified ~200-record gold set
    # ======================================================================
    manual_review_records = _build_manual_review_manifest(
        records, doc_type_results, seg_results, statute_like_idx, quarantine_ids, actual_sha256
    )

    # ======================================================================
    # dataflare_corpus_report_v1.json — human-readable measured summary
    # ======================================================================
    report = {
        "dataset_id": "dataflare_egypt_legal_corpus_v1",
        "file_sha256": actual_sha256,
        "measured_facts": {
            "record_count": record_count,
            "token_count": total_tokens,
            "distinct_category_values": len(cat_dist),
            "document_type_distribution": doc_type_dist,
            "duplicate_clusters": len(clusters),
            "duplicate_records": sum(len(c.member_record_ids) for c in multi_member),
            "citation_extraction_coverage": manifest["citation_extraction"]["coverage_ratio"],
            "structure_zero_marker_ratio": manifest["structure_profile"]["zero_marker_ratio"],
        },
        "resource_measurement": resource_meta,
        "software_commit": git_commit,
        "generated_at": generated_at,
    }

    # --- write ---------------------------------------------------------------
    out_dir = REPO_ROOT / "artifacts/datasets/dataflare_egypt_legal_corpus_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "split_manifest.json").write_text(
        json.dumps(split_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "manual_review_manifest.json").write_text(
        json.dumps(manual_review_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    reports_dir = REPO_ROOT / "artifacts/reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "dataflare_corpus_report_v1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


def _build_manual_review_manifest(
    records: list[dict],
    doc_type_results: list,
    seg_results: list,
    statute_like_idx: list[int],
    quarantine_ids: set[str],
    file_sha256: str,
) -> dict:
    """Stratified ~200-record manual-review manifest. Gold fields are
    intentionally left empty (ready for expert annotation) — no label is
    fabricated here."""
    from src.legal_ai.domain.document_type import DocumentType
    from src.legal_ai.domain.evaluation_case import EvaluationCase

    seg_by_statute_idx = dict(zip(statute_like_idx, seg_results, strict=True))

    buckets: dict[str, list[int]] = {t.value: [] for t in DocumentType}
    buckets["parser_miss_statute_like"] = []
    buckets["metadata_conflict_duplicate"] = []

    for i, res in enumerate(doc_type_results):
        buckets[res.document_type.value].append(i)

    for idx, seg in seg_by_statute_idx.items():
        if seg.marker_count == 0:
            buckets["parser_miss_statute_like"].append(idx)

    for rec_id in quarantine_ids:
        try:
            buckets["metadata_conflict_duplicate"].append(int(rec_id))
        except ValueError:
            continue

    # Target ~200 total, stratified proportionally with a floor per
    # non-empty bucket so rare categories (e.g. legal_form, international)
    # are still represented, not swamped by the dominant judicial buckets.
    target_total = 200
    min_per_bucket = 5
    non_empty = {k: v for k, v in buckets.items() if v}
    total_available = sum(len(v) for v in non_empty.values())

    cases = []
    case_num = 0
    for bucket_name, indices in non_empty.items():
        share = max(min_per_bucket, round(target_total * len(indices) / total_available))
        share = min(share, len(indices))
        # deterministic selection: evenly spaced sample, not random
        step = max(1, len(indices) // share) if share else 1
        selected = indices[::step][:share]
        for idx in selected:
            case_num += 1
            rec = records[idx]
            case = EvaluationCase(
                case_id=f"dataflare_v1_gold_{case_num:04d}",
                source_record_id=str(idx),
                source_dataset="dataflare_egypt_legal_corpus_v1",
                text=rec["text"][:400],  # preview only; full text is in the source parquet
                notes=f"stratum:{bucket_name}",
            )
            cases.append(case.to_dict())

    return {
        "dataset_id": "dataflare_egypt_legal_corpus_v1",
        "source_file_sha256": file_sha256,
        "target_size": target_total,
        "actual_size": len(cases),
        "strata": {k: len(v) for k, v in non_empty.items()},
        "note": (
            "Gold fields are intentionally empty pending expert annotation. "
            "Selection is deterministic (evenly spaced within each stratum), "
            "not random, for reproducibility. Do not compute or publish "
            "classifier/parser precision/recall/F1 against this file until "
            "review_status/adjudication_status show reviewed cases."
        ),
        "cases": cases,
    }


if __name__ == "__main__":
    main()
