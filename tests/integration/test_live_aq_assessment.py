"""Post-TAP AQ wiring, source isolation and report provenance, entirely offline."""
from dataclasses import replace
import json

import pytest

from alma_duplicate.assessment import (
    ArchiveInput, AssessmentOptions, AssessmentSources, assess_observation,
)
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient, ArchiveAqError
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.reporting import report_json_text
from tests.integration.test_archive_array_adapter import synthetic
from tests.integration.test_confirmed_continuum import payload
from tests.unit.test_archive_aq_client import BASE, Http, Reply, hit, response


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", lambda *a, **k: pytest.fail("network"))


def tap_rows(*, empty=False, unlinked=False):
    search, _ = synthetic(offset=0)
    original = search.archive.source_record
    members = ("uid://A001/X3955/X44", "uid://A001/X3955/X45")
    rows = []
    for m, name in [(members[0], "SourceA"), (members[0], "SourceB"), (members[1], "SourceA")]:
        rows.append(dict(original.rows[0], member_ous_uid=m, target_name=name,
                         obs_id=f"{m}.source.{name}.spw.0"))
    if unlinked:
        rows = [dict(rows[0], obs_id="unresolved")]
    if empty:
        rows = []
    return replace(original, rows=tuple(rows), provenance=replace(original.provenance,
                   expected_count=len(rows), retrieved_count=len(rows))), members


def inputs(source, fetcher, *, catalog=None, events=None):
    class Tap:
        def search(self, query):
            if events is not None:
                events.append("TAP")
            if isinstance(source, Exception):
                raise source
            return source
    return AssessmentSources("LIVE", lambda: ArchiveInput(Tap(), array_catalog=catalog),
                             archive_array_fetcher=fetcher)


def run(source, fetcher, **kwargs):
    return assess_observation(**payload(), sources=inputs(source, fetcher, **kwargs))


def acquisition(result):
    return result.document["sources"]["ARCHIVE"]["array_evidence"]["acquisition"]


def fetcher(members, *, empty=False):
    http = Http(Reply({"elasticsearchUrl": BASE}),
                *(Reply(response([] if empty else [hit(m, name) for name in ("SourceA", "SourceB")]))
                  for m in members))
    return ArchiveAqClient(request=http).fetch_members


def test_tap_then_all_retained_linked_members_despite_display_limit():
    source, members = tap_rows()
    events = []
    fetch = fetcher(members)
    def aq(requested):
        assert events == ["TAP"]
        assert requested == members
        events.append("AQ")
        return fetch(requested)
    result = run(source, aq, events=events)
    doc = result.document
    assert events == ["TAP", "AQ"]
    assert result.status == "COMPLETED"
    assert len(doc["context_evaluations"]) == 3
    assert doc["evaluation_scope"]["shown_candidates"] == 1
    assert doc["sources"]["ARCHIVE"]["status"] == "COMPLETED"
    aq_meta = acquisition(result)
    assert aq_meta["status"] == "COMPLETED"
    assert aq_meta["requested_members"] == list(members)
    assert len(aq_meta["queries"]) == 2
    assert all(q["total_hits"] == 2 for q in aq_meta["queries"])
    for c in doc["context_evaluations"]:
        assert c["array_evidence"]["diameters_m"] == [7.0]
        assert c["array_evidence"]["records"][0]["source_name"] in ("SourceA", "SourceB")
    assert json.loads(report_json_text(doc)) == doc
    assert not any(g["code"].startswith("ARCHIVE_AQ_") for g in inspect_report(doc)["gap_occurrences"])


@pytest.mark.parametrize("code,status", [("TRANSPORT_ERROR", "FAILED"), ("INCOMPLETE", "INCOMPLETE")])
def test_aq_failure_keeps_tap_candidates_without_raw_array_fallback(code, status):
    source, members = tap_rows()
    def failed(_):
        raise ArchiveAqError(code, members[0])
    result = run(source, failed)
    assert result.status == "SOURCES_UNAVAILABLE"
    assert result.document["assessment_status"] == "SOURCES_UNAVAILABLE"
    assert result.document["sources"]["ARCHIVE"]["status"] == "COMPLETED"
    assert acquisition(result)["status"] == status
    assert acquisition(result)["error"] == {"code": code, "member_ous_uid": members[0]}
    assert acquisition(result)["queries"] == []
    for c in result.document["context_evaluations"]:
        assert c["array_evidence"]["diameters_m"] == []
        pos = next(r for r in c["criteria"] if r["criterion_id"] == "POS-SINGLE")
        assert pos["method_version"] == "archive_pos_single_3"
        assert pos["outcome"] is None
        assert c["branches"][0]["status"] == "INDETERMINATE"
    inspection = inspect_report(result.document)
    gaps = [g for g in inspection["gap_occurrences"] if g["code"] == f"ARCHIVE_AQ_{status}"]
    assert len(gaps) == 1 and gaps[0]["category"] == "SOURCE_OR_SEARCH_INCOMPLETE"
    assert inspect_report(result.document, inspection_version="2")["inspection_version"] == "2"


def test_successful_empty_aq_is_not_failure_or_no_duplicate():
    source, members = tap_rows()
    result = run(source, fetcher(members, empty=True))
    assert result.status == "COMPLETED"
    assert acquisition(result)["status"] == "COMPLETED"
    assert [q["total_hits"] for q in acquisition(result)["queries"]] == [0, 0]
    assert result.document["assessment"] == "NOT_AGGREGATED"
    assert all(c["branches"][0]["status"] == "INDETERMINATE" for c in result.document["context_evaluations"])


@pytest.mark.parametrize("kind,reason", [
    ("empty", "NO_RETAINED_ARCHIVE_CONTEXTS"),
    ("unlinked", "NO_LINKED_ARCHIVE_MEMBERS"),
    ("failed", "TAP_NOT_COMPLETED"),
    ("incomplete", "TAP_NOT_COMPLETED"),
])
def test_skips_with_reason_without_invoking_aq(kind, reason):
    source, _ = tap_rows(empty=kind == "empty", unlinked=kind == "unlinked")
    if kind == "failed":
        source = OSError("TAP unavailable")
    if kind == "incomplete":
        source = replace(source, status=ArchiveQueryStatus.OVERFLOW)
    result = run(source, lambda _: pytest.fail("AQ should not run"))
    assert acquisition(result)["status"] == "SKIPPED"
    assert acquisition(result)["reason"] == reason
    if kind == "unlinked":
        assert result.document["context_evaluations"]
        assert not result.document["context_evaluations"][0]["array_evidence"]["diameters_m"]


@pytest.mark.parametrize("kind", ["solar", "invalid", "queue_only"])
def test_exemption_and_configuration_do_not_access_aq(kind):
    document = payload()
    calls = lambda *args: pytest.fail("provider accessed")
    sources = AssessmentSources("LIVE", calls, archive_array_fetcher=calls)
    if kind == "solar":
        document["request"]["target_kind"] = "SUN"
        assert assess_observation(**document, sources=sources).status == "SOLAR_EXEMPTION"
    elif kind == "invalid":
        document["request"]["target_kind"] = "INVALID"
        assert assess_observation(**document, sources=sources).document is None
    else:
        document["search_options"]["sources"] = ["QUEUE"]
        with pytest.raises(ValueError):
            assess_observation(**document, sources=sources)


def test_captured_and_live_options_conflict_before_tap_or_aq():
    _, catalog = synthetic()
    source, _ = tap_rows()
    events = []
    with pytest.raises(ValueError, match="catalog"):
        run(source, lambda _: pytest.fail("AQ"), catalog=catalog, events=events)
    assert events == []


def test_replay_and_live_acquisition_are_explicitly_incompatible():
    with pytest.raises(ValueError, match="LIVE"):
        assess_observation(**payload(), sources=AssessmentSources("REPLAY", lambda: pytest.fail("provider"),
                           archive_array_fetcher=lambda _: pytest.fail("AQ")))


def test_programming_errors_are_not_converted_to_missing_evidence():
    source, _ = tap_rows()
    def broken(_):
        raise RuntimeError("programming error")
    with pytest.raises(RuntimeError, match="programming error"):
        run(source, broken)


def test_disabled_path_matches_existing_report_and_method():
    from tests.integration.test_assessment_entry import normalized
    source, _ = tap_rows()
    original = assess_observation(**payload(), sources=inputs(source, None))
    repeated = run(source, None)
    assert normalized(original.document) == normalized(repeated.document)
    assert "array_evidence" not in repeated.document["sources"]["ARCHIVE"]
    assert "assessment_status" not in repeated.document
    assert all(next(r for r in c["criteria"] if r["criterion_id"] == "POS-SINGLE")["method_version"]
               == "archive_pos_single_1" for c in repeated.document["context_evaluations"])


def test_excluded_and_unlinked_contexts_do_not_expand_member_queries():
    # Exercise actual search predicates and reconstruction before acquisition.
    source, members = tap_rows()
    rows = [dict(r) for r in source.rows]
    rows[2]["spatial_resolution"] = 9.0  # Excluded by explicit angular filter.
    third = "uid://A001/X3955/X46"
    rows.append(dict(rows[0], member_ous_uid=third, obs_id="unresolved"))
    source = replace(source, rows=tuple(rows), provenance=replace(source.provenance,
                     expected_count=4, retrieved_count=4))
    document = payload()
    document["search_options"]["predicates"] = [{"field": "angular_resolution", "operator": "<",
                                                 "quantity": {"value": .5, "unit": "arcsec"}}]
    seen = []
    fetch = fetcher(members[:1])
    def aq(requested):
        seen.append(requested)
        return fetch(requested)
    result = assess_observation(**document, sources=inputs(source, aq))
    assert seen == [members[:1]]
    contexts = result.document["context_evaluations"]
    assert len(contexts) == 3  # Two linked and one retained unlinked context.
    unresolved = [c for c in contexts if not c["array_evidence"]["diameters_m"]]
    assert len(unresolved) == 1
    assert unresolved[0]["array_evidence"]["reasons"] == ["ARCHIVE_ARRAY_SOURCE_IDENTITY_UNRESOLVED"]


def test_queue_results_survive_archive_aq_failure_unchanged():
    from pathlib import Path
    from alma_duplicate.clients.queue_csv_client import QueueCsvClient
    queue_file = Path(__file__).parents[2] / "examples/queue_continuum/queue.csv"
    source, members = tap_rows()
    document = payload()
    document["search_options"]["sources"] = ["ARCHIVE", "QUEUE"]
    loader = lambda: QueueCsvClient().load(queue_file)
    options = AssessmentOptions(queue_continuum=True)
    baseline = assess_observation(**document, options=options,
                                 sources=replace(inputs(source, None), queue_loader=loader))
    def failed(_):
        raise ArchiveAqError("HTTP_ERROR", members[0])
    result = assess_observation(**document, options=options,
                               sources=replace(inputs(source, failed), queue_loader=loader))
    queue_contexts = lambda d: [c for c in d["context_evaluations"] if c["reference"]["source"] == "QUEUE"]
    assert queue_contexts(result.document)
    assert queue_contexts(result.document) == queue_contexts(baseline.document)
    assert result.document["sources"]["QUEUE"]["status"] == "COMPLETED"
    assert result.status == "SOURCES_UNAVAILABLE"


def test_whole_batch_failure_preserves_no_partial_success_catalog():
    source, members = tap_rows()
    http = Http(Reply({"elasticsearchUrl": BASE}),
                Reply(response([hit(members[0], "SourceA")])), Reply({}, 503))
    result = run(source, ArchiveAqClient(request=http).fetch_members)
    assert len(http.calls) == 3
    assert acquisition(result)["error"]["member_ous_uid"] == members[1]
    assert acquisition(result)["queries"] == []
    assert all(not c["array_evidence"]["diameters_m"] for c in result.document["context_evaluations"])


@pytest.mark.parametrize("damage", ["captured", "missing_query", "foreign_record", "count", "hash"])
def test_invalid_fetcher_contract_cannot_supply_scientific_evidence(damage):
    from alma_duplicate.archive_array_evidence import ArchiveArrayCatalogProvenance, ArchiveArrayCatalogMode
    source, members = tap_rows()
    acquired = fetcher(members)(members)
    if damage == "captured":
        acquired = replace(acquired, catalog=replace(acquired.catalog,
            provenance=ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.CAPTURED, "synthetic")))
    elif damage == "missing_query":
        acquired = replace(acquired, queries=acquired.queries[:1])
    elif damage == "foreign_record":
        records = (replace(acquired.catalog.records[0], member_ous_uid="uid://A001/X999/X999"),)
        acquired = replace(acquired, catalog=replace(acquired.catalog, records=records))
    elif damage == "count":
        acquired = replace(acquired, queries=(replace(acquired.queries[0], total_hits=0), *acquired.queries[1:]))
    else:
        acquired = replace(acquired, queries=(replace(acquired.queries[0], response_sha256="wrong"), *acquired.queries[1:]))
    with pytest.raises(ValueError, match="AQ"):
        run(source, lambda _: acquired)


def test_mixed_line_pairs_and_exports_keep_source_and_variant_binding():
    from alma_duplicate.ui.reports import report_artifact
    search, cat = synthetic(intents=("CONTINUUM", "LINE"))
    record = cat.records[0]
    document = payload()
    document["request"]["intents"] = ["CONTINUUM", "LINE"]
    http = Http(Reply({"elasticsearchUrl": BASE}), Reply(response([
        hit(record.member_ous_uid, record.source_name, "12m 7m"),
        hit(record.member_ous_uid, "calibrator", "12m"),
    ])))
    result = assess_observation(**document, sources=inputs(
        search.archive.source_record, ArchiveAqClient(request=http).fetch_members))
    contexts = result.document["context_evaluations"]
    assert len(contexts) == 1 and len(contexts[0]["beam_variants"]) == 2
    assert contexts[0]["array_evidence"]["records"][0]["source_name"] == record.source_name
    raw = report_json_text(result.document).encode()
    artifact = report_artifact("live AQ test", raw)
    assert artifact.raw == raw
    pairs = [g for g in artifact.inspection["gap_occurrences"] if "pair_identity" in g]
    assert len({p["pair_identity"]["beam_variant_id"] for p in pairs}) == 2
    for p in pairs:
        node = result.document
        for token in p["location"].split("/")[1:]:
            node = node[int(token)] if isinstance(node, list) else node[token]
        assert "criterion_id" in node


def test_missing_science_source_cannot_borrow_same_member_calibrator_array():
    search, catalog = synthetic()
    r = catalog.records[0]
    http = Http(Reply({"elasticsearchUrl": BASE}), Reply(response([hit(r.member_ous_uid, "calibrator", "7m")])))
    result = run(search.archive.source_record, ArchiveAqClient(request=http).fetch_members)
    c = result.document["context_evaluations"][0]
    assert acquisition(result)["status"] == "COMPLETED"
    assert c["array_evidence"]["reasons"] == ["ARCHIVE_ARRAY_EVIDENCE_MISSING"]
    assert c["branches"][0]["status"] == "INDETERMINATE"
