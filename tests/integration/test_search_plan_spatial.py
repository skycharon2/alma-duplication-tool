"""Offline planning and spatial evidence tests, not duplicate labels."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from alma_duplicate.comparison import build_archive_contexts, build_queue_contexts
from alma_duplicate.clients.archive_queries import (
    ARCHIVE_CORE_COLUMNS, build_count_adql, build_retrieval_adql, normalize_query_parameters,
)
from alma_duplicate.domain.spatial import PositionInterpretation, SpatialStatus as S
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.search_plan import build_search_plan, bind_archive_query, evaluate_angular_filter
from alma_duplicate.spatial import adapt_spatial, evaluate_spatial
from tests.integration.test_archive_pipeline_fixture import _complete_query_result
from tests.unit.test_queue_csv_parser import _records, _indices, _render
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes

ROOT = Path(__file__).parents[2]


def validation(*, sources=("ARCHIVE", "QUEUE"), ra=0, dec=0, radius=1, predicates=None):
    payload = json.loads((ROOT / "examples/proposed_observation.json").read_text())
    # Replace an already validated position to isolate search-plan tests.
    v = validate_proposed_observation(payload["request"], {
        "radius": {"value": radius, "unit": "deg"},
        "sources": list(sources), "predicates": predicates or [],
    })
    return replace(v, request=replace(v.request, position=replace(v.request.position, ra_deg=ra, dec_deg=dec)))


def archive(plan, *, region="CIRCLE ICRS 0 0 0.01", mosaic="F", array="12-m", **changes):
    base = _complete_query_result()
    row = dict(base.rows[0]) | {"s_ra": 0., "s_dec": 0., "s_region": region,
                                "is_mosaic": mosaic, "antenna_arrays": array} | changes
    spec = plan.for_source("ARCHIVE").archive_query
    provenance = replace(base.provenance,
                         normalized_parameters=normalize_query_parameters(spec),
                         count_adql=build_count_adql(spec),
                         retrieval_adql=build_retrieval_adql(spec, columns=ARCHIVE_CORE_COLUMNS),
                         projection=None, expected_count=1, retrieved_count=1)
    source = replace(base, rows=(row,), provenance=provenance)
    # Production descriptors for coordinate normalization are required.
    source = replace(source, field_metadata=tuple(
        replace(f, unit="deg", datatype="double") if f.name in {"s_ra", "s_dec"} else f
        for f in source.field_metadata
    ))
    return source, build_archive_contexts(source).contexts[0]


def queue(**changes):
    records = _records()
    values = {"RA": "0", "Dec": "0", "Long Offset": "0", "Lat Offset": "0"} | changes
    for column, value in values.items():
        records[41][_indices(records)[column]] = value
    source = parse_queue_csv_bytes(_render(records))
    assert source.can_reconstruct
    return source, build_queue_contexts(source).contexts[0]


def interpretation(c, **changes):
    return PositionInterpretation(c.context_id, "ICRS", "FIXED", "test-only-explicit-interpretation", **changes)


def test_plan_preserves_single_sided_filter_and_no_observation_parameter_filters():
    predicates = [{"field": "angular_resolution", "operator": "<",
                   "quantity": {"value": .5, "unit": "arcsec"}}]
    v = validation(predicates=predicates)
    plan = build_search_plan(v)
    query = plan.for_source("ARCHIVE").archive_query
    assert query.frequency_min_ghz is None and query.angular_resolution_max_arcsec is None
    assert query.science_only is False
    assert plan.execution == "NOT_EXECUTED"
    assert plan.for_source("ARCHIVE").predicates[1].requested.operator == "<"
    assert plan.validation.request is v.request


def test_sources_and_science_scope_are_explicit():
    plan = build_search_plan(validation(sources=("QUEUE",)))
    assert plan.for_source("ARCHIVE") is None
    assert len(plan.sources) == 1
    other = build_search_plan(validation(), archive_science_only=True)
    assert other.for_source("ARCHIVE").archive_query.science_only
    assert any(p.name == "science_only" for p in other.for_source("ARCHIVE").predicates)


def test_unresolved_filters_are_retained_with_skip_reason():
    predicates = [
        {"field": "frequency", "operator": "=", "quantity": {"value": 100, "unit": "GHz"}},
        {"field": "sensitivity", "operator": "<", "quantity": {"value": .1, "unit": "mJy/beam"},
         "basis": "AGGREGATE"},
        {"field": "spectral_resolution", "operator": "<", "quantity": {"value": 1, "unit": "MHz"}},
    ]
    plan = build_search_plan(validation(predicates=predicates))
    for source in plan.sources:
        assert all(p.action == "SKIPPED" and p.reason for p in source.predicates[1:])
        assert len(source.predicates) == 4


def test_unready_request_cannot_be_planned():
    with pytest.raises(ValueError):
        build_search_plan(validate_proposed_observation({}, {}))


def test_query_binding_rejects_other_cone_and_hidden_predicate():
    plan = build_search_plan(validation())
    source, c = archive(plan)
    assert bind_archive_query(plan, source).status == "MATCHED"
    other = build_search_plan(validation(ra=1))
    assert bind_archive_query(other, source).status == "MISMATCH"
    changed = replace(source, provenance=replace(source.provenance,
        retrieval_adql=source.provenance.retrieval_adql + " AND proposal_id='expected'"))
    assert bind_archive_query(plan, changed).status == "MISMATCH"
    assert evaluate_spatial(other, adapt_spatial(c, source)).status == "NOT_EVALUATED"


@pytest.mark.parametrize("region,status", [
    ("CIRCLE ICRS 0 0 0.01", "INSIDE"),
    ("CIRCLE ICRS 2 0 0.01", "OUTSIDE"),
    ("CIRCLE ICRS 0 0 -1", "NOT_EVALUATED"),
    ("POLYGON ICRS 0 0 1 0 1 1", "NOT_EVALUATED"),
    ("CIRCLE GALACTIC 0 0 1", "NOT_EVALUATED"),
    ("", "NOT_EVALUATED"),
])
def test_circle_selection_and_unsupported_regions(region, status):
    plan = build_search_plan(validation())
    source, c = archive(plan, region=region)
    evidence = adapt_spatial(c, source)
    assert c.evidence.prepared.raw_row["s_region"] == region
    assert evaluate_spatial(plan, evidence).status == status


@pytest.mark.parametrize("mosaic,array", [("T", "12-m"), ("F", "TP"), ("F", "unrecognized")])
def test_mosaic_tp_unknown_array_not_treated_as_simple_circle(mosaic, array):
    plan = build_search_plan(validation())
    source, c = archive(plan, mosaic=mosaic, array=array)
    evidence = adapt_spatial(c, source)
    assert evidence.footprint is not None
    assert evaluate_spatial(plan, evidence).status == "NOT_EVALUATED"


def test_center_and_footprint_are_retained_separately():
    plan = build_search_plan(validation())
    source, c = archive(plan, s_ra=5)
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    assert evidence.center.ra_deg == 5 and evidence.footprint.center.ra_deg == 0
    assert "CENTER_AND_REGION_CENTER_DIFFER" in evidence.reasons
    # Planned Archive operation uses the declared footprint, not the raw center.
    assert evaluate_spatial(plan, evidence).status == "INSIDE"


@pytest.mark.parametrize("value", [float("nan"), True, "359.99999999999999999", "-1e-999"])
def test_invalid_archive_coordinate_keeps_region_and_raw_evidence(value):
    plan = build_search_plan(validation())
    source, c = archive(plan, s_ra=value)
    evidence = adapt_spatial(c, source)
    assert evidence.center_status is S.INVALID
    assert evidence.footprint_status is S.AVAILABLE


def test_queue_does_not_infer_target_frame_from_mosaic_coordinate_system():
    source, c = queue(**{"Mos. Coord.": "ICRS"})
    evidence = adapt_spatial(c, source)
    assert evidence.center.frame == "UNKNOWN"
    assert evidence.selection_status is S.UNRESOLVED
    assert evaluate_spatial(build_search_plan(validation()), evidence).status == "NOT_EVALUATED"


def test_queue_explicit_fixed_zero_position_can_be_selected():
    source, c = queue()
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    assert evidence.selection_status is S.AVAILABLE
    assert evaluate_spatial(build_search_plan(validation()), evidence).status == "INSIDE"


def test_queue_offsets_remain_unapplied():
    source, c = queue(**{"Long Offset": "1"})
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    assert evidence.center.ra_deg == 0
    assert "NONZERO_OFFSETS_NOT_APPLIED" in evidence.reasons
    assert evidence.selection_status is S.UNSUPPORTED


def test_interpretation_cannot_be_reused_for_another_row():
    source, c = queue()
    wrong = replace(interpretation(c), context_id="another-row")
    with pytest.raises(ValueError):
        adapt_spatial(c, source, interpretation=wrong)


def test_wraparound_and_boundary_are_conservative():
    source, c = queue(RA="359.9")
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    result = evaluate_spatial(build_search_plan(validation(ra=.1, radius=.3)), evidence)
    assert result.status == "INSIDE" and result.separation_deg == pytest.approx(.2)
    source, c = queue(RA="1")
    result = evaluate_spatial(build_search_plan(validation()), adapt_spatial(c, source, interpretation=interpretation(c)))
    assert result.status == "NOT_EVALUATED" and "SPATIAL_BOUNDARY_TOLERANCE" in result.reasons


@pytest.mark.parametrize("operator,status", [("<", "NO_MATCH"), ("<=", "MATCH"), ("=", "MATCH"),
                                             (">", "NO_MATCH"), (">=", "MATCH")])
def test_angular_operators_are_not_changed(operator, status):
    p = [{"field": "angular_resolution", "operator": operator,
          "quantity": {"value": .5, "unit": "arcsec"}}]
    plan = build_search_plan(validation(predicates=p))
    _, c = archive(plan)
    assert evaluate_angular_filter(plan, c, 1).status == status


def test_missing_angular_value_is_not_filter_failure():
    p = [{"field": "angular_resolution", "operator": "<",
          "quantity": {"value": .5, "unit": "arcsec"}}]
    plan = build_search_plan(validation(predicates=p))
    _, c = archive(plan, spatial_resolution=None)
    assert evaluate_angular_filter(plan, c, 1).status == "NOT_EVALUATED"


def test_queue_tp_and_sps_contexts_remain_unsupported():
    source = parse_queue_csv_bytes(
        (ROOT / "tests/fixtures/queue/queue_pipeline_v1.csv").read_bytes())
    contexts = build_queue_contexts(source).contexts
    tp_seen = sps_seen = False
    for c in contexts:
        evidence = adapt_spatial(c, source, interpretation=interpretation(c))
        if c.evidence.row.request.use_tp:
            tp_seen = True
            assert "TP_GEOMETRY_UNSUPPORTED" in evidence.reasons
            assert evidence.selection_status is S.UNSUPPORTED
        if c.evidence.row.spectral.__class__.__name__ == "SpectralScanEvidence":
            sps_seen = True
            assert "SPS_SELECTION_UNSUPPORTED" in evidence.reasons
            assert evidence.selection_status is S.UNSUPPORTED
    assert tp_seen and sps_seen


def test_queue_custom_geometry_not_silently_collapsed():
    source, c = queue(Mosaic="Custom")
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    assert evidence.selection_status is S.UNSUPPORTED
    assert evidence.geometry != "SINGLE_FIELD"


def test_queue_different_parse_result_cannot_supply_provenance():
    source, c = queue()
    another_source, _ = queue()
    assert source.snapshot.snapshot_sha256 == another_source.snapshot.snapshot_sha256
    with pytest.raises(ValueError):
        adapt_spatial(c, another_source, interpretation=interpretation(c))


def test_pole_and_ra_wrap_have_valid_spherical_distance():
    source, c = queue(RA="180", Dec="90")
    result = evaluate_spatial(build_search_plan(validation(ra=0, dec=90, radius=.1)),
                              adapt_spatial(c, source, interpretation=interpretation(c)))
    assert result.status == "INSIDE"
    assert result.separation_deg == pytest.approx(0, abs=1e-12)


def test_missing_coordinate_units_do_not_borrow_region_units():
    plan = build_search_plan(validation())
    source, _ = archive(plan)
    source = replace(source, field_metadata=tuple(
        replace(f, unit=None) if f.name == "s_ra" else f for f in source.field_metadata))
    c = build_archive_contexts(source).contexts[0]
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    assert evidence.center is None
    assert evidence.center_status is S.UNRESOLVED
    assert evidence.footprint.center.frame == "ICRS"


def test_coordinate_unit_conversion_keeps_raw_value():
    plan = build_search_plan(validation())
    source, _ = archive(plan, s_ra=3600)
    source = replace(source, field_metadata=tuple(
        replace(f, unit="arcsec") if f.name == "s_ra" else f for f in source.field_metadata))
    c = build_archive_contexts(source).contexts[0]
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    assert evidence.center.ra_deg == 1
    assert evidence.context.evidence.prepared.raw_row["s_ra"] == 3600


def test_source_not_selected_cannot_be_evaluated():
    source, c = queue()
    evidence = adapt_spatial(c, source, interpretation=interpretation(c))
    plan = build_search_plan(validation(sources=("ARCHIVE",)))
    assert evaluate_spatial(plan, evidence).status == "NOT_EVALUATED"


def test_result_limit_is_retained_without_becoming_archive_maxrec():
    v = validation()
    v = replace(v, search_options=replace(v.search_options, result_limit=7))
    plan = build_search_plan(v)
    assert plan.result_limit == 7
    assert not hasattr(plan.for_source("ARCHIVE").archive_query, "maxrec")


def test_query_binding_is_independent_of_completeness():
    from alma_duplicate.clients.archive_contract import ArchiveQueryStatus
    plan = build_search_plan(validation())
    source, _ = archive(plan)
    incomplete = replace(source, status=ArchiveQueryStatus.OVERFLOW)
    assert bind_archive_query(plan, incomplete).status == "MATCHED"
    assert not incomplete.can_reconstruct
