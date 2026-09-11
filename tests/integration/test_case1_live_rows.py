"""Offline candidate search over unmodified live Archive rows for CASE1.

The fixture holds ten real ivoa.obscore rows retrieved on 2026-09-11 (see its
ECSV metadata). It pins real-data formats that the synthetic fixture does not
exercise: ``Circle ICRS`` casing, Pad:Antenna lists, a masked Group OUS and a
non-mosaic polygon. The reported Member OUS is a retrieval reference, not a
confirmed duplicate label; the search assessment stays NOT_EVALUATED.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from astropy.table import Table

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_client import ArchiveClient
from alma_duplicate.clients.archive_contract import TapFieldMetadata, TapResponse
from alma_duplicate.domain.candidate_search import CandidateDisposition as D, SearchSourceStatus as S
from alma_duplicate.domain.proposed_observation import SearchReadiness
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.search_plan import build_search_plan
from tests.fakes import FakeTapExecutor
from tests.integration.test_archive_pipeline_fixture import _field_metadata

FIXTURE = Path(__file__).parents[1] / "fixtures" / "archive" / "case1_live_rows_2026-09-11.ecsv"
EXPECTED_MEMBER = "uid://A001/X2df9/X1b"


def case1_request(predicates=None):
    request = {
        "target_kind": "FIXED",
        "geometry": "SINGLE_POINTING",
        "target_name": "CASE1 retrieval reference, not a confirmed duplicate",
        "position": {"ra": "18:33:39.920", "dec": "-21:03:39.900",
                     "ra_format": "HMS", "dec_format": "DMS", "frame": "ICRS"},
        "setup_id": "case1-search",
        "setup_complete": False,
        "intents": [],
        "representative_frequency": {
            "value": 290.420, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN",
            "origin": {"kind": "IMPORTED", "raw_label": "Internship task CASE1 frequency"},
        },
    }
    options = {
        "radius": {"value": 10.0, "unit": "arcsec"},
        "sources": ["ARCHIVE"],
        "result_limit": 500,
        "predicates": predicates if predicates is not None else [
            {"field": "angular_resolution", "operator": "<",
             "quantity": {"value": 0.5, "unit": "arcsec"}},
        ],
    }
    validation = validate_proposed_observation(request, options)
    assert validation.search_readiness is SearchReadiness.READY, validation.issues
    return validation


def fixture_table() -> Table:
    return Table.read(FIXTURE, format="ascii.ecsv")


def live_rows_client() -> ArchiveClient:
    """ArchiveClient whose scripted TAP responses are the recorded live rows and fields."""
    table = fixture_table()
    rows = tuple({column: row[column] for column in table.colnames} for row in table)
    fields = tuple(
        TapFieldMetadata(name=f["name"], datatype=f["datatype"], arraysize=f["arraysize"],
                         unit=f["unit"], ucd=f["ucd"], utype=None, xtype=None, description=None)
        for f in table.meta["tap_fields"]
    )
    executor = FakeTapExecutor([
        TapResponse(rows=({"total_matches": len(rows)},), declared_columns=("total_matches",),
                    field_metadata=_field_metadata(("total_matches",)), query_status_raw="OK"),
        TapResponse(rows=rows, declared_columns=tuple(table.colnames),
                    field_metadata=fields, query_status_raw="OK"),
    ])
    timestamp = datetime(2026, 9, 11, 9, 0, tzinfo=UTC)
    return ArchiveClient("https://example.invalid/tap", executor=executor, maxrec=5000,
                         clock=lambda: timestamp, run_id_factory=lambda: "case1-live-rows")


def rows_by_member(result):
    grouped = {}
    for row in result.archive.rows:
        member = row.context.evidence.prepared.raw_row["member_ous_uid"]
        grouped.setdefault(str(member), []).append(row)
    return grouped


def outcome(row, name):
    return next(f for f in row.filters if f.name == name)


def test_fixture_provenance_is_recorded():
    table = fixture_table()
    assert len(table) == 10
    assert table.meta["retrieved_utc"] == "2026-09-11"
    assert table.meta["full_result_rows"] == 336
    assert sum(str(m) == EXPECTED_MEMBER for m in table["member_ous_uid"]) == 4
    assert all(str(r).startswith(("Circle ICRS", "Polygon ICRS")) for r in table["s_region"])


def test_real_case1_rows_pass_the_local_spatial_check():
    validation = case1_request()
    result = search_candidates(validation, archive_client=live_rows_client())
    assert result.archive.status is S.COMPLETED
    assert result.archive.query_binding.status == "MATCHED"
    assert len(result.archive.rows) == 10
    expected = rows_by_member(result)[EXPECTED_MEMBER]
    assert len(expected) == 4
    for row in expected:
        spatial = outcome(row, "spatial")
        assert spatial.outcome == "MATCH", spatial.reasons
        assert spatial.spatial.status == "INSIDE"
        assert row.spatial_evidence.array_classification.family == "MAIN_ARRAY_12M"
        assert outcome(row, "angular_resolution").outcome == "MATCH"
        assert row.disposition is D.MATCHED_FILTERS
    assert result.assessment == "NOT_EVALUATED"


@pytest.mark.parametrize("member,disposition,reason", [
    # Non-mosaic polygon: unsupported shape, never silently excluded.
    ("uid://A001/X2fe/X874", D.RETAINED_UNEVALUATED, "REGION_REPRESENTATION_UNSUPPORTED"),
    # 12-m, ACA and T-pad antennas without a dominant family.
    ("uid://A002/X5d7935/X2fb", D.RETAINED_UNEVALUATED, "ARRAY_FAMILY_MIXED"),
    # 7-m ACA row, spatially supported but its angular resolution is 6.6 arcsec.
    ("uid://A001/X1234/X1d8", D.EXCLUDED, None),
    # 12-m row with 0.59 arcsec resolution.
    ("uid://A001/X2fe/X856", D.EXCLUDED, None),
])
def test_other_real_rows_keep_their_specific_outcomes(member, disposition, reason):
    result = search_candidates(case1_request(), archive_client=live_rows_client())
    (row,) = rows_by_member(result)[member]
    assert row.disposition is disposition
    if reason is not None:
        assert reason in outcome(row, "spatial").reasons


def test_masked_group_ous_from_an_early_cycle_row_is_preserved():
    result = search_candidates(case1_request(), archive_client=live_rows_client())
    (row,) = rows_by_member(result)["uid://A002/X36d874/X7a"]
    group = row.context.evidence.prepared.normalized_metadata.group_ous_uid
    assert group.value is None
    assert group.missing_status.value == "MASKED"
    # A 12-m array that correlated one PM antenna on an A pad stays 12-m.
    assert row.spatial_evidence.array_classification.family == "MAIN_ARRAY_12M"
    assert outcome(row, "spatial").outcome == "MATCH"


def test_plan_query_is_the_recorded_cone():
    plan = build_search_plan(case1_request())
    spec = plan.for_source("ARCHIVE").archive_query
    assert spec.spatial_strategy == "REGION"
    assert spec.radius_deg == pytest.approx(10 / 3600)
