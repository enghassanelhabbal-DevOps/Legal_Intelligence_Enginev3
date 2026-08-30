from __future__ import annotations

from src.legal_ai.domain.duplicate_clustering import ClusterRelation, cluster_exact_duplicates


def test_unique_records_form_singleton_clusters():
    records = [{"text": "نص أ"}, {"text": "نص ب"}]
    clusters = cluster_exact_duplicates(records)
    assert len(clusters) == 2
    assert all(c.relation == ClusterRelation.UNIQUE.value for c in clusters)


def test_exact_duplicate_text_forms_one_cluster():
    records = [{"text": "نص مشترك"}, {"text": "نص مشترك"}]
    clusters = cluster_exact_duplicates(records)
    assert len(clusters) == 1
    assert len(clusters[0].member_record_ids) == 2


def test_identical_metadata_is_exact_duplicate_not_variant():
    """Regression: record_id must not be counted as 'metadata variance' —
    it always differs between distinct members even when the actual
    metadata fields are identical."""
    records = [
        {"text": "نص مشترك", "law_name": "قانون البيئة"},
        {"text": "نص مشترك", "law_name": "قانون البيئة"},
    ]
    clusters = cluster_exact_duplicates(records, metadata_fields=["law_name"])
    assert clusters[0].relation == ClusterRelation.EXACT_DUPLICATE.value


def test_different_metadata_is_flagged_as_variant_not_dropped():
    """The exact scenario the master prompt warns about: same text,
    different law_name — must be preserved, not silently deduplicated."""
    records = [
        {"text": "نص مشترك", "law_name": "قانون البيئة"},
        {"text": "نص مشترك", "law_name": "New Microsoft Word Document"},
    ]
    clusters = cluster_exact_duplicates(records, metadata_fields=["law_name"])
    assert clusters[0].relation == ClusterRelation.METADATA_VARIANT.value
    assert len(clusters[0].metadata_variants) == 2
    # both variants preserved, not one discarded
    law_names = {v["law_name"] for v in clusters[0].metadata_variants}
    assert law_names == {"قانون البيئة", "New Microsoft Word Document"}


def test_canonical_record_is_first_encountered_deterministic():
    records = [{"text": "نص", "id": "a"}, {"text": "نص", "id": "b"}]
    clusters = cluster_exact_duplicates(records, id_field="id")
    assert clusters[0].canonical_record_id == "a"


def test_record_id_defaults_to_content_derived_positional_index():
    """No id_field given — must use position, never a fabricated id."""
    records = [{"text": "نص أ"}]
    clusters = cluster_exact_duplicates(records)
    assert clusters[0].member_record_ids == ["0"]


def test_empty_text_records_are_skipped_not_clustered():
    records = [{"text": ""}, {"text": None}, {"text": "نص حقيقي"}]
    clusters = cluster_exact_duplicates(records)
    assert len(clusters) == 1


def test_cluster_id_is_deterministic_content_hash():
    records_a = [{"text": "نص ثابت"}]
    records_b = [{"text": "نص ثابت"}]
    clusters_a = cluster_exact_duplicates(records_a)
    clusters_b = cluster_exact_duplicates(records_b)
    assert clusters_a[0].cluster_id == clusters_b[0].cluster_id


def test_no_members_lost_across_clustering():
    records = [{"text": f"نص {i % 3}"} for i in range(9)]  # 3 clusters of 3
    clusters = cluster_exact_duplicates(records)
    total_members = sum(len(c.member_record_ids) for c in clusters)
    assert total_members == 9


def test_to_dict_shape():
    records = [{"text": "نص"}]
    clusters = cluster_exact_duplicates(records)
    d = clusters[0].to_dict()
    assert set(d.keys()) == {
        "cluster_id",
        "content_hash",
        "member_record_ids",
        "canonical_record_id",
        "member_count",
        "metadata_variants",
        "relation",
    }
