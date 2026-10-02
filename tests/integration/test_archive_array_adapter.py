"""Official source binding and complete Archive diameter branches."""
from dataclasses import replace
import hashlib
import json
import shutil

import pytest

from alma_duplicate.archive_array_evidence import ArchiveArrayCatalog, ArrayRecord, load_archive_array_catalog
from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.reporting import report_document
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.rules.archive_position import evaluate_archive_position
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.search_plan import build_search_plan
from tests.integration.test_archive_array_evidence import FIXTURE, SAMPLES, replay, request_at
from tests.integration.test_confirmed_continuum import validated, payload
from tests.integration.test_search_plan_spatial import archive
from alma_duplicate.spatial import adapt_spatial

MANIFEST = FIXTURE / "supporting/aq-manifest.json"


@pytest.mark.parametrize("sample_id,d", [("pure_12m", 12), ("pure_7m", 7),
                                       ("cm_with_tp", 7), ("non_solar_mixed_names", 7)])
def test_real_official_label_resolves_science_target_not_calibrator(sample_id, d, monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("network"))
    source, context = replay(sample_id)
    catalog = load_archive_array_catalog(MANIFEST)
    evidence = catalog.bind(context)
    assert evidence.diameters_m == (d,)
    result = evaluate_archive_position(request_at(SAMPLES[sample_id]), context,
                                      adapt_spatial(context, source), array_evidence=evidence)
    assert result.method_version == "archive_pos_single_2"
    assert result.outcome == "SATISFIED"
    assert dict(result.derived)["antenna_diameter_m"] == d
    assert evidence.records[0].source_name == SAMPLES[sample_id]["target_name"]
    assert evidence.manifest_sha256 == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()


def synthetic(label="12m 7m", *, offset=16, intents=("CONTINUUM",)):
    # Synthetic numerical case, never substitute these labels in real captures.
    document = payload()
    document["request"]["intents"] = list(intents)
    v = validated(document)
    source, context = archive(build_search_plan(v), s_ra=201.365,
                              s_dec=-43.019 + offset / 3600, frequency=240.,
                              spatial_resolution=.45, cont_sensitivity_bandwidth=.15)
    key = context.evidence.row_link.association_key.context
    # Fixture source name must match its reconstructed source, as in real rows.
    source = replace(source, rows=tuple(dict(r, target_name=key.source_name) for r in source.rows))
    record = ArrayRecord(f"{key.member_ous_uid}.source.{key.source_name}", key.member_ous_uid,
                         key.source_name, label, "synthetic-response", "2026-10-02T00:00:00+00:00",
                         "https://example.invalid/synthetic")
    catalog = ArchiveArrayCatalog((record,), "synthetic-manifest")
    search = search_candidates(v, archive_result=source)
    return search, catalog


def test_archive_mixed_diameters_evaluate_whole_branches_and_report_once():
    search, catalog = synthetic(intents=("CONTINUUM", "LINE"))
    report = evaluate_candidate_search(search, archive_arrays=catalog)
    c = report.context_evaluations[0]
    assert len(report.context_evaluations) == 1 and c.criteria == ()
    assert [v.diameter_m for v in c.beam_variants] == [7, 12]
    assert [v.evaluation.branches[0].status for v in c.beam_variants] == ["CRITERIA_MET", "CRITERIA_NOT_MET"]
    assert c.branches[0].status == "CRITERIA_MET"
    assert c.branches[0].method_version == "archive_beam_variant_or_1"
    assert all(v.evaluation.candidate is c.candidate for v in c.beam_variants)
    doc = report_document(report)
    result = doc["context_evaluations"][0]
    assert result["mix_aggregation"]["method_version"] == "archive_beam_variant_or_1"
    assert result["mix_aggregation"]["matching_diameters_m"] == [7.0]
    assert all(v["line_pairs"] for v in result["beam_variants"])
    gaps = inspect_report(doc)["gap_occurrences"]
    pairs = [g for g in gaps if "pair_identity" in g]
    assert {g["pair_identity"]["beam_variant_id"] for g in pairs} == {v.variant_id for v in c.beam_variants}
    for gap in pairs:
        node = doc
        for token in gap["location"].split("/")[1:]:
            node = node[int(token)] if isinstance(node, list) else node[token]
        assert "criterion_id" in node


def test_tp_has_twelve_metre_dish_but_never_inherits_interferometric_science_pass():
    search, catalog = synthetic("TP", intents=("CONTINUUM", "LINE"))
    c = evaluate_candidate_search(search, archive_arrays=catalog).context_evaluations[0]
    assert c.array_evidence.components == ("TOTAL_POWER",)
    assert c.array_evidence.diameters_m == (12.,)
    pos = c.criteria[1]
    assert dict(pos.derived)["antenna_diameter_m"] == 12
    assert dict(pos.derived)["candidate_radius_deg"] > 0
    assert pos.outcome is None
    assert "ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED" in pos.reasons
    assert all(b.status == "INDETERMINATE" for b in c.branches)


@pytest.mark.parametrize("mode", ["missing", "other_source", "duplicate", "conflict", "unknown_label", "missing_label"])
def test_unusable_official_evidence_does_not_fall_back_to_raw_twelve_metre_label(mode):
    search, catalog = synthetic("12m")
    r = catalog.records[0]
    records = {
        "missing": (), "other_source": (replace(r, observation_id=r.observation_id + "x"),),
        "duplicate": (r, r), "conflict": (replace(r, source_name="calibrator"),),
        "unknown_label": (replace(r, raw_label="ACA"),), "missing_label": (replace(r, raw_label=None),),
    }[mode]
    c = evaluate_candidate_search(search, archive_arrays=replace(catalog, records=records)).context_evaluations[0]
    assert not c.beam_variants
    assert c.criteria[1].outcome is None
    assert c.branches[0].status == "INDETERMINATE"


def test_catalog_rejects_corrupt_bytes_and_incomplete_official_response(tmp_path):
    directory = tmp_path / "capture"
    shutil.copytree(MANIFEST.parent, directory)
    m = directory / MANIFEST.name
    entries = json.loads(m.read_text())
    p = directory / entries[0]["file"]
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_archive_array_catalog(m)
    data = json.loads(p.read_bytes())
    data["timed_out"] = True
    p.write_text(json.dumps(data))
    entries[0]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    m.write_text(json.dumps(entries))
    with pytest.raises(ValueError, match="Incomplete"):
        load_archive_array_catalog(m)


def test_wrong_context_array_evidence_cannot_be_reused():
    source, context = replay("pure_7m")
    evidence = load_archive_array_catalog(MANIFEST).bind(context)
    with pytest.raises(ValueError, match="another candidate"):
        evaluate_archive_position(request_at(SAMPLES["pure_7m"]), context, adapt_spatial(context, source),
                                  array_evidence=replace(evidence, context_id="another"))


@pytest.mark.parametrize("offset,status", [(0, "CRITERIA_MET"), (25, "CRITERIA_NOT_MET")])
def test_archive_both_diameters(offset, status):
    search, catalog = synthetic(offset=offset)
    c = evaluate_candidate_search(search, archive_arrays=catalog).context_evaluations[0]
    assert all(v.evaluation.branches[0].status == status for v in c.beam_variants)
    assert c.branches[0].status == status


@pytest.mark.parametrize("offset,status", [(0, "CRITERIA_MET"), (25, "INDETERMINATE")])
def test_seven_with_tp_preserves_unknown_twelve_metre_branch(offset, status):
    search, catalog = synthetic("7m TP", offset=offset)
    c = evaluate_candidate_search(search, archive_arrays=catalog).context_evaluations[0]
    assert [v.diameter_m for v in c.beam_variants] == [7, 12]
    assert c.beam_variants[1].evaluation.branches[0].status == "INDETERMINATE"
    assert c.branches[0].status == status
    gaps = inspect_report(report_document(evaluate_candidate_search(search, archive_arrays=catalog)))["gap_occurrences"]
    assert all(g["category"] == "SCOPE_UNSUPPORTED" for g in gaps
               if g["code"] == "ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED")


def test_archive_cannot_borrow_criteria_between_diameters():
    from alma_duplicate.rules.aggregation import aggregate_continuum
    from alma_duplicate.rules.model import CriterionOutcome
    from alma_duplicate.rules.queue_beam import aggregate_beam_variants

    search, catalog = synthetic()
    report = evaluate_candidate_search(search, archive_arrays=catalog)
    c = report.context_evaluations[0]
    variants = []
    for v in c.beam_variants:
        criteria = tuple(replace(r, outcome=CriterionOutcome.NOT_SATISFIED)
                         if v.diameter_m == 7 and r.criterion_id == "CONT-FREQ" else r
                         for r in v.evaluation.criteria)
        branch = aggregate_continuum(c.candidate.context, (*report.request_criteria, *criteria), supported=True)
        variants.append(replace(v, evaluation=replace(v.evaluation, criteria=criteria, branches=(branch,))))
    assert all(v.evaluation.branches[0].status == "CRITERIA_NOT_MET" for v in variants)
    assert aggregate_beam_variants(variants, source="ARCHIVE")[0].status == "CRITERIA_NOT_MET"


def write_synthetic_catalog(directory, record):
    """Temporary protocol fixture; not an independent official observation."""
    path = directory / "aq.json"
    raw = json.dumps({"timed_out": False, "_shards": {"failed": 0}, "hits": {
        "total": {"relation": "eq", "value": 1}, "hits": [{"_id": record.observation_id,
        "_source": {"mous": record.member_ous_uid, "sourceName": record.source_name, "array": record.raw_label}}],
    }}).encode()
    path.write_bytes(raw)
    manifest = directory / "aq-manifest.json"
    manifest.write_text(json.dumps([{"file": path.name, "sha256": hashlib.sha256(raw).hexdigest(),
        "url": "https://almascience.eso.org/aq/service/api/search/observations/_search",
        "retrieved_at": record.retrieved_at, "request_body": {"query": {"term": {"mous": record.member_ous_uid}}}}]))
    return manifest


def test_cli_and_shared_entry_export_bound_catalog_and_protect_inputs(tmp_path):
    from alma_duplicate.assessment import ArchiveInput, AssessmentSources, assess_observation
    from alma_duplicate.cli.evaluate import main
    from tests.integration.test_assessment_entry import normalized

    search, catalog = synthetic()
    manifest = write_synthetic_catalog(tmp_path, catalog.records[0])
    catalog = load_archive_array_catalog(manifest)
    class Client:
        def search(self, *args, **kwargs):
            return search.archive.source_record
    request_file = tmp_path / "request.json"
    raw = json.dumps(payload()).encode()
    request_file.write_bytes(raw)
    output = tmp_path / "report.json"
    result = assess_observation(**payload(), input_sha256=hashlib.sha256(raw).hexdigest(),
        sources=AssessmentSources("LIVE", lambda: ArchiveInput(Client(), array_catalog=catalog)))
    args = ["--request", str(request_file), "--live-archive", "--archive-array-evidence", str(manifest)]
    assert main([*args, "--output", str(output)], archive_client_factory=Client) == 0
    doc = json.loads(output.read_bytes())
    assert normalized(doc) == normalized(result.document)
    assert doc["sources"]["ARCHIVE"]["array_evidence"]["manifest_sha256"] == catalog.manifest_sha256
    assert len(doc["context_evaluations"][0]["beam_variants"]) == 2
    for protected in (manifest, tmp_path / "aq.json"):
        before = protected.read_bytes()
        assert main([*args, "--output", str(protected), "--overwrite"], archive_client_factory=Client) == 2
        assert protected.read_bytes() == before


def test_solar_does_not_load_array_catalog(tmp_path):
    from alma_duplicate.cli.evaluate import main
    document = payload()
    document["request"]["target_kind"] = "SUN"
    request = tmp_path / "request.json"
    request.write_text(json.dumps(document))
    output = tmp_path / "solar.json"
    assert main(["--request", str(request), "--live-archive", "--archive-array-evidence",
                 str(tmp_path / "missing.json"), "--output", str(output)],
                archive_client_factory=lambda: pytest.fail("Solar source access")) == 0
    assert json.loads(output.read_bytes())["report_kind"] == "SOLAR_EXEMPTION"
