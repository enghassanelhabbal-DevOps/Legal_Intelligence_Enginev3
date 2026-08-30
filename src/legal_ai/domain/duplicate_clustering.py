"""duplicate_clustering.py — exact-duplicate clustering that preserves
provenance instead of blindly dropping rows.

Per the master prompt: "Do NOT blindly drop_duplicates(text). Some
duplicate-text clusters contain different metadata/provenance/category
variants." This module groups records by exact content hash, but records
each member's own metadata (categories, index) rather than discarding all
but one — the canonical-record choice is deterministic and explicit, but
non-canonical members remain inspectable, not deleted.

Deliberately exact-hash only for this pass (near-duplicate detection is a
separate, more expensive concern the master prompt explicitly says to
defer: "cheap deterministic methods first... do NOT immediately add
expensive embedding-based deduplication").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.legal_ai.ingestion.validation import hash_document


class ClusterRelation(StrEnum):
    EXACT_DUPLICATE = "exact_duplicate"
    METADATA_VARIANT = "metadata_variant"  # same text, different categories/metadata
    UNIQUE = "unique"  # cluster of size 1


@dataclass
class DuplicateCluster:
    cluster_id: str  # content hash, stable and deterministic
    content_hash: str
    member_record_ids: list[str] = field(default_factory=list)
    canonical_record_id: str | None = None
    metadata_variants: list[dict[str, Any]] = field(default_factory=list)
    relation: str = ClusterRelation.UNIQUE.value

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "content_hash": self.content_hash,
            "member_record_ids": self.member_record_ids,
            "canonical_record_id": self.canonical_record_id,
            "member_count": len(self.member_record_ids),
            "metadata_variants": self.metadata_variants,
            "relation": self.relation,
        }


def cluster_exact_duplicates(
    records: list[dict[str, Any]],
    *,
    text_field: str = "text",
    id_field: str | None = None,
    metadata_fields: list[str] | None = None,
) -> list[DuplicateCluster]:
    """Group records sharing exact-identical text into clusters.

    If `id_field` is None or absent, the record's positional index (as a
    string) is used as its id — content-derived, never a fabricated
    original identifier (consistent with dataset_adapters.py's identifier
    honesty rule).

    The first record encountered in each cluster becomes canonical
    (deterministic — stable input order, not arbitrary); all members and
    their per-record metadata_fields values are preserved, not discarded.
    """
    metadata_fields = metadata_fields or []
    clusters: dict[str, DuplicateCluster] = {}

    for i, rec in enumerate(records):
        text = str(rec.get(text_field, "") or "")
        if not text:
            continue
        content_hash = hash_document({"raw_text": text})
        rec_id = str(rec.get(id_field)) if id_field and rec.get(id_field) is not None else str(i)

        if content_hash not in clusters:
            clusters[content_hash] = DuplicateCluster(
                cluster_id=content_hash, content_hash=content_hash
            )
        cluster = clusters[content_hash]
        cluster.member_record_ids.append(rec_id)
        if cluster.canonical_record_id is None:
            cluster.canonical_record_id = rec_id
        if metadata_fields:
            cluster.metadata_variants.append(
                {"record_id": rec_id, **{f: rec.get(f) for f in metadata_fields}}
            )

    for cluster in clusters.values():
        if len(cluster.member_record_ids) == 1:
            cluster.relation = ClusterRelation.UNIQUE.value
        else:
            # Compare metadata field VALUES only — record_id always differs
            # between distinct members and must not count as "variance".
            value_tuples = {
                tuple(v.get(f) for f in metadata_fields) for v in cluster.metadata_variants
            }
            if metadata_fields and len(value_tuples) > 1:
                cluster.relation = ClusterRelation.METADATA_VARIANT.value
            else:
                cluster.relation = ClusterRelation.EXACT_DUPLICATE.value

    return list(clusters.values())


__all__ = ["ClusterRelation", "DuplicateCluster", "cluster_exact_duplicates"]
