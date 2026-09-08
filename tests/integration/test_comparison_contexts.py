"""Offline cross-boundary tests; no policy verdicts or live calls."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from alma_duplicate.clients.archive_adapter import run_archive_pipeline
from alma_duplicate.clients.archive_contract import ArchiveQueryStatus, ArchiveQueryErrorKind
from alma_duplicate.clients.queue_csv_adapter import run_queue_pipeline
from alma_duplicate.comparison import (
    build_archive_contexts, build_queue_contexts, prepare_comparison,
)
from alma_duplicate.domain.comparison import EvidenceState as E, SourceStatus
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from alma_duplicate.request_validation import validate_proposed_observation
from tests.integration.test_archive_pipeline_fixture import _complete_query_result
from tests.unit.test_queue_csv_parser import _records, _indices, _render

ROOT = Path(__file__).parents[2]


def request():
    payload = json.loads((ROOT / "examples/proposed_observation.json").read_text())
    return validate_proposed_observation(payload["request"], payload["search_options"])


def queue():
    return parse_queue_csv_bytes(
        (ROOT / "tests/fixtures/queue/queue_pipeline_v1.csv").read_bytes()
    )


def archive_rows(*rows):
    original = _complete_query_result()
    return replace(original, rows=rows, provenance=replace(
        original.provenance, expected_count=len(rows), retrieved_count=len(rows),
    ))


def test_existing_pipelines_and_valid_partial_request_are_reused():
    a = run_archive_pipeline(_complete_query_result())
    q = run_queue_pipeline(queue())
    result = prepare_comparison(request(), archive=a, queue=q)
    assert result.archive.status is SourceStatus.COMPLETE
    assert result.queue.status is SourceStatus.COMPLETE
    assert len(result.archive.contexts) == 5
    assert len(result.queue.contexts) == 13
    assert result.archive.contexts[0].evidence.prepared is a.prepared_rows[0]
    assert result.queue.contexts[0].evidence.row is q.parse_result.row_inputs[0]
    assert result.assessment == "NOT_EVALUATED"
    assert result.search_execution == "NOT_EXECUTED"


def test_selected_component_does_not_borrow_another_windows_rms():
    row = dict(_complete_query_result().rows[0])
    row["frequency_support"] = (
        "[99.9..100.1GHz, 1MHz, 9mJy/beam@native, 9mJy/beam@10km/s, XX YY] U "
        "[199.9..200.1GHz, 1MHz, 0.01mJy/beam@native, 0.01mJy/beam@10km/s, XX YY]"
    )
    result = build_archive_contexts(archive_rows(row))
    assert result.status is SourceStatus.COMPLETE
    c = result.contexts[0]
    assert c.evidence.selected_component.frequency_interval.low == 99.9
    assert c.evidence.selected_component.sensitivities[0].value == 9
    assert len(c.evidence.support_evidence.parse_result.components) == 2
    assert c.reference.component_index == c.evidence.selected_component.component_index
    scalar = next(i for i in c.items if i.path.endswith("line_sensitivity.quantity"))
    assert scalar.association is E.UNKNOWN


def test_bad_other_component_keeps_conservative_mapping_gate_and_raw_evidence():
    row = dict(_complete_query_result().rows[0])
    row["frequency_support"] += " U [200..201GHz, 1MHz, -1mJy/beam@native, XX YY]"
    c = build_archive_contexts(archive_rows(row)).contexts[0]
    assert c.evidence.support_evidence.parse_result.components[0].is_valid
    assert not c.evidence.support_evidence.parse_result.components[1].is_valid
    assert c.evidence.selected_component is None
    assert "SUPPORT_PARSE_UNSAFE" in c.reasons
    assert c.evidence.support_evidence.parse_result.raw_value == row["frequency_support"]
    assert c.evidence.prepared.comparison_evidence.frequency.centre.is_available


def test_conflicting_rows_of_same_association_are_retained_as_alternatives():
    first = dict(_complete_query_result().rows[0])
    second = first | {"spatial_resolution": 0.05, "sensitivity_10kms": 0.001}
    contexts = build_archive_contexts(archive_rows(first, second)).contexts
    assert len(contexts) == 2
    assert contexts[0].alternative_context_ids == (contexts[1].context_id,)
    assert contexts[1].alternative_context_ids == (contexts[0].context_id,)
    assert [c.evidence.prepared.comparison_evidence.angular_resolution.quantity.canonical_value
            for c in contexts] == [0.5, 0.05]


def test_missing_rms_keeps_frequency_and_context_identity():
    row = dict(_complete_query_result().rows[0]) | {"sensitivity_10kms": None}
    c = build_archive_contexts(archive_rows(row)).contexts[0]
    rms = next(i for i in c.items if i.path.endswith("line_sensitivity.quantity"))
    frequency = next(i for i in c.items if i.path.endswith("frequency.centre"))
    assert rms.numeric is E.MISSING
    assert frequency.numeric is E.PRESENT
    assert c.evidence.selected_component is not None


def test_queue_preserves_only_observed_combinations_and_no_per_spw_rms_copy():
    q = run_queue_pipeline(queue())
    contexts = build_queue_contexts(q).contexts
    assert {c.evidence.association for c in contexts} == set(q.reconstruction.associations)
    m33 = [c for c in contexts if c.evidence.row.group_key.target_name == "M33"]
    assert len(m33) == 6
    assert len({(c.evidence.association.spatial_component_id,
                 c.evidence.association.spectral_setup_id) for c in m33}) == 5
    for c in contexts:
        rms = next(i for i in c.items if i.path == "row.spectral.sensitivity")
        assert rms.association is E.UNKNOWN
        assert c.reference.acquisition_id is None and c.reference.parse_run_id is None
        assert c.reference.raw_row_id == c.evidence.row.raw_row.row_id.value
        assert c.reference.parser_version == q.parse_result.snapshot.parser_version


def test_queue_missing_scientific_field_fails_source_but_keeps_archive():
    records = _records()
    records[41][_indices(records)["Req.Sensitivity"]] = ""
    q = parse_queue_csv_bytes(_render(records))
    result = prepare_comparison(request(), archive=_complete_query_result(), queue=q)
    assert result.queue.status is SourceStatus.FAILED
    assert result.queue.contexts == ()
    assert result.queue.source_record is q and q.issues
    assert len(q.raw_rows) == 13 and len(q.row_inputs) == 12
    assert result.archive.contexts
    assert result.assessment == "NOT_EVALUATED"


@pytest.mark.parametrize("status", [ArchiveQueryStatus.OVERFLOW, ArchiveQueryStatus.COUNT_MISMATCH,
                                    ArchiveQueryStatus.ERROR])
def test_incomplete_archive_keeps_queue_and_cannot_make_absence_claim(status):
    original = _complete_query_result()
    a = replace(original, status=status,
                error_kind=ArchiveQueryErrorKind.SERVICE_ERROR if status is ArchiveQueryStatus.ERROR else None)
    result = prepare_comparison(request(), archive=a, queue=queue())
    assert result.archive.status in (SourceStatus.FAILED, SourceStatus.INCOMPLETE)
    assert result.archive.contexts == ()
    assert result.archive.source_record is a
    assert len(result.queue.contexts) == 13
    assert result.assessment == "NOT_EVALUATED"


def test_unprovided_source_is_explicit_even_with_ready_request():
    result = prepare_comparison(request())
    assert result.validation.can_search
    assert result.archive.status is SourceStatus.NOT_PROVIDED
    assert result.queue.status is SourceStatus.NOT_PROVIDED
    assert result.search_execution == "NOT_EXECUTED"


def test_invalid_request_is_rejected():
    invalid = validate_proposed_observation({"target_kind": "BAD"}, {})
    with pytest.raises(ValueError, match="validated request"):
        prepare_comparison(invalid)


def test_tampered_queue_association_fails_instead_of_creating_combination():
    q = run_queue_pipeline(queue())
    first = q.reconstruction.associations[0]
    alien = next(x for x in q.reconstruction.associations
                 if x.spectral_setup_id != first.spectral_setup_id)
    rec = replace(q.reconstruction, associations=(
        replace(first, spectral_setup_id=alien.spectral_setup_id),
        *q.reconstruction.associations[1:],
    ))
    result = build_queue_contexts(replace(q, reconstruction=rec))
    assert result.status is SourceStatus.FAILED and not result.contexts


def test_duplicate_archive_mapping_identity_is_not_silently_overwritten():
    a = run_archive_pipeline(_complete_query_result())
    rec = replace(a.reconstruction, support_mappings=(
        *a.reconstruction.support_mappings, a.reconstruction.support_mappings[0],
    ))
    result = build_archive_contexts(replace(a, reconstruction=rec))
    assert result.status is SourceStatus.FAILED and not result.contexts


def test_unlinked_archive_row_keeps_evidence_without_invented_context_key():
    row = dict(_complete_query_result().rows[0]) | {"obs_id": "unparseable"}
    c = build_archive_contexts(archive_rows(row)).contexts[0]
    assert c.evidence.row_link.association_key is None
    assert c.evidence.selected_component is None
    assert c.alternative_context_ids == ()
    assert c.evidence.prepared.raw_row["obs_id"] == "unparseable"


def test_archive_unit_failure_does_not_erase_context_or_claim_comparability():
    source = _complete_query_result()
    source = replace(source, field_metadata=tuple(
        replace(f, unit="not-a-unit") if f.name == "spatial_resolution" else f
        for f in source.field_metadata
    ))
    result = build_archive_contexts(source)
    assert result.status is SourceStatus.COMPLETE
    item = next(i for i in result.contexts[0].items
                if i.path.endswith("angular_resolution.quantity"))
    assert item.unit is E.UNAVAILABLE
    assert item.numeric is E.UNKNOWN
    assert item.method is E.NOT_IMPLEMENTED
    assert result.contexts[0].evidence.prepared.raw_row["spatial_resolution"] == 0.5


def test_unknown_queue_usable_width_retains_nominal_evidence():
    records = _records()
    records[41][_indices(records)["Bandwidth SPW 1"]] = "1234"
    source = parse_queue_csv_bytes(_render(records))
    assert source.can_reconstruct
    result = build_queue_contexts(source)
    c = result.contexts[0]
    item = next(i for i in c.items if i.path == "row.spectral.spws[0].usable_bandwidth_ghz")
    assert item.numeric is E.MISSING
    assert c.evidence.row.spectral.spws[0].nominal_bandwidth_ghz == 1.234
    assert c.evidence.row.spectral.spws[0].usable_bandwidth_ghz is None


def test_existing_archive_pipeline_cannot_be_attached_to_different_query():
    a = run_archive_pipeline(_complete_query_result())
    other = _complete_query_result()
    result = build_archive_contexts(replace(a, query_result=other))
    assert result.status is SourceStatus.FAILED


def test_reordered_archive_pipeline_rows_do_not_change_associations():
    a = run_archive_pipeline(_complete_query_result())
    normal = build_archive_contexts(a)
    shuffled = build_archive_contexts(replace(a, prepared_rows=tuple(reversed(a.prepared_rows))))
    assert {c.context_id: c.evidence.row_link for c in normal.contexts} == {
        c.context_id: c.evidence.row_link for c in shuffled.contexts
    }
