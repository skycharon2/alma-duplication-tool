"""Captured array metadata and official labels, not reviewed proposal verdicts."""
import hashlib
import json
from pathlib import Path

import pytest

from alma_duplicate.assessment import AssessmentSources, AssessmentStatus, assess_observation
from alma_duplicate.clients.archive_queries import ArchiveQuerySpec
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.comparison import build_archive_contexts
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.position_single import evaluate_position_single
from alma_duplicate.spatial import adapt_spatial

FIXTURE = Path(__file__).parents[1] / "fixtures/archive/array_evidence_2026_10_01"
SAMPLES = {s["sample_id"]: s for s in json.loads((FIXTURE / "samples.json").read_text())["samples"]}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    def forbidden(*args, **kwargs):
        pytest.fail("Array evidence regression must run offline")
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


def replay(sample_id):
    sample = SAMPLES[sample_id]
    client = RecordedArchiveClient(FIXTURE / sample["manifest"])
    source = client.search(ArchiveQuerySpec(**sample["query_spec"]))
    assert source.is_complete
    assert len(source.rows) == source.provenance.expected_count
    # The cone is replayed in full; only the assertion selects the reviewed row.
    contexts = [c for c in build_archive_contexts(source).contexts
                if c.evidence.prepared.raw_row["obs_id"] == sample["obs_id"]]
    assert len(contexts) == 1
    context = contexts[0]
    row = context.evidence.prepared.raw_row
    assert row["member_ous_uid"] == sample["member_ous_uid"]
    assert row["target_name"] == sample["target_name"]
    assert row["asdm_uid"] == sample["asdm_uid"]
    return source, context


def request_at(sample):
    spec = sample["query_spec"]
    validated = validate_proposed_observation({
        "target_kind": "FIXED", "geometry": "SINGLE_POINTING",
        "setup_id": "array-evidence-test", "intents": ["CONTINUUM"],
        "position": {"ra": spec["ra_deg"], "dec": spec["dec_deg"],
                     "ra_format": "DEG", "dec_format": "DEG", "frame": "ICRS"},
    }, {"sources": ["ARCHIVE"], "radius": {"value": 1, "unit": "arcsec"}})
    assert validated.is_valid and validated.can_search
    return validated.request


@pytest.mark.parametrize("sample_id,diameter", [
    ("pure_12m", 12.0), ("pure_7m", 7.0),
    ("cm_with_tp", None), ("non_solar_mixed_names", None),
])
def test_real_candidate_position_diameter_remains_evidence_bound(sample_id, diameter):
    source, context = replay(sample_id)
    result = evaluate_position_single(request_at(SAMPLES[sample_id]), context,
                                      adapt_spatial(context, source))
    assert result.method_version == "archive_pos_single_1"
    assert result.context_id == context.context_id
    assert dict(result.derived)["antenna_diameter_m"] == diameter
    assert dict(result.details)["diameter_gate"] == "ALL_RECOGNIZED_TOKENS_ONE_FAMILY_OR_LEGACY_LABEL"
    if diameter is None:
        assert result.outcome is None
        assert result.evaluation == "INSUFFICIENT_INFORMATION"
        assert result.reasons == ("UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED",)
        assert dict(result.derived)["candidate_radius_deg"] is None
    else:
        assert result.outcome == "SATISFIED"  # constructed request at candidate centre
        assert result.evaluation == "EVALUATED"
        assert result.decision_refs
        assert dict(result.derived)["candidate_radius_deg"] > 0


@pytest.mark.parametrize("sample_id,label", [
    ("pure_12m", "12m"), ("pure_7m", "7m"), ("cm_with_tp", "7m"),
    ("non_solar_mixed_names", "7m"), ("solar", "12m 7m"),
])
def test_official_array_label_binds_to_source_within_member(sample_id, label):
    sample = SAMPLES[sample_id]
    data = json.loads((FIXTURE / "supporting" / f"{sample_id}-aq.json").read_text())
    assert data["hits"]["total"]["relation"] == "eq"
    assert data["hits"]["total"]["value"] == len(data["hits"]["hits"])
    sources = [hit["_source"] for hit in data["hits"]["hits"]]
    assert all(s["mous"] == sample["member_ous_uid"] for s in sources)
    target = [s for s in sources if s["sourceName"] == sample["target_name"]]
    assert len(target) == 1 and target[0]["array"] == label
    if sample_id in {"cm_with_tp", "non_solar_mixed_names"}:
        # A Member UID alone cannot bind a calibrator's array label to its target.
        assert any(s["array"] == "12m 7m" and s["sourceName"] != sample["target_name"]
                   for s in sources)


def test_solar_sample_is_exempt_before_any_source_or_diameter_evaluation():
    _, context = replay("solar")
    raw = context.evidence.prepared.raw_row["antenna_arrays"]
    assert ":CM" in raw and ":DA" in raw
    def forbidden():
        pytest.fail("Solar exemption must not open a source")
    result = assess_observation({
        "target_kind": "SUN", "geometry": "SINGLE_POINTING",
        "target_name": SAMPLES["solar"]["target_name"],
        "setup_id": "solar-evidence-test", "intents": ["CONTINUUM"],
    }, {}, sources=AssessmentSources("LIVE", forbidden, forbidden))
    assert result.status == AssessmentStatus.SOLAR_EXEMPTION
    assert result.document["report_kind"] == "SOLAR_EXEMPTION"


@pytest.mark.parametrize("name", ["aq-manifest.json", "qa-manifest.json"])
def test_supporting_evidence_original_bytes_are_pinned(name):
    folder = FIXTURE / "supporting"
    for entry in json.loads((folder / name).read_text()):
        assert hashlib.sha256((folder / entry["file"]).read_bytes()).hexdigest() == entry["sha256"]
        assert entry["url"].startswith("https://almascience.eso.org/")
