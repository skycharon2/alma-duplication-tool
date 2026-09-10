"""Opt-in live report: does the formula primary-beam strategy apply to real rows?

docs/primary_beam_search.md documents the opt-in FORMULA_PRIMARY_BEAM
candidate-selection strategy (Q1 partial confirmation: theta_FWHM =
1.13*lambda/D). Its Archive-side diameter lookup only resolves an EXACT
`12-m` or `7-m` antenna_arrays label on an explicitly non-mosaic row; every
other label yields ARRAY_DIAMETER_UNRESOLVED, and a mosaic/unknown-geometry
row yields MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED. How often that happens on
real rows was previously unmeasured (see
claude/next_rule_engineering_tasks_2026-09-10.md, "阵列类型分类目前完全没做").

This module measures it for the CASE1/CASE2 coordinate neighborhoods only --
a small, concrete, real-data sample, not an Archive-wide census (see
scripts/beam_array_label_census.py for that). It deliberately supplies NO
PositionInterpretation objects. Per docs/primary_beam_search.md, supplying
one requires "justified" evidence obtained by inspecting a real row after it
is retrieved -- inventing one here just to make a result "green" is exactly
what docs/evidence/scientific_feedback.md warns against ("do not fabricate
frame/target interpretations to turn an example green"). Every row is
therefore expected to end up NOT_EVALUATED with
FIXED_TARGET_AND_ICRS_INTERPRETATION_REQUIRED among its reasons; what this
file actually measures is which OTHER reasons accompany it -- in particular
whether the array-label diameter lookup itself resolved.

No formal position result is produced or claimed by this file.
"""
from __future__ import annotations

import os
from collections import Counter

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_client import ArchiveClient
from alma_duplicate.domain.candidate_search import SearchSourceStatus as S
from alma_duplicate.domain.proposed_observation import SearchReadiness
from alma_duplicate.request_validation import validate_proposed_observation

pytestmark = pytest.mark.live

DEFAULT_ALMA_TAP_ENDPOINT = "https://almascience.eso.org/tap"
CASE_SEARCH_RADIUS_ARCSEC = 10.0
BEAM_DECISION_REF = "case-beam-applicability-review-2026-09-10"

# Same recorded positions/frequencies as tests/live/test_case_retrieval.py
# (docs/duplication_rule_inputs.md section 8). Kept independent (not
# imported) so this file's scope stays obviously separable from the recall
# acceptance test.
CASES = {
    "CASE1": {
        "position": {
            "ra": "18:33:39.920", "dec": "-21:03:39.900",
            "ra_format": "HMS", "dec_format": "DMS", "frame": "ICRS",
        },
        "representative_frequency": {
            "value": 290.420, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN",
            "origin": {"kind": "IMPORTED", "raw_label": "Internship task CASE1 frequency"},
        },
    },
    "CASE2": {
        "position": {
            "ra": "00:47:33.064", "dec": "-25:17:18.280",
            "ra_format": "HMS", "dec_format": "DMS", "frame": "ICRS",
        },
        "representative_frequency": {
            "value": 690.0, "unit": "GHz", "kind": "SKY", "frame": "UNKNOWN",
            "origin": {"kind": "IMPORTED", "raw_label": "Internship task CASE2 frequency"},
        },
    },
}


def _build_case_validation(case: dict):
    request = {
        "target_kind": "FIXED",
        "geometry": "SINGLE_POINTING",
        "target_name": "Beam-strategy applicability review, not a confirmed duplicate",
        "position": case["position"],
        "setup_id": "beam-applicability-review",
        "setup_complete": False,
        "intents": [],
        "representative_frequency": case["representative_frequency"],
    }
    search_options = {
        "radius": {"value": CASE_SEARCH_RADIUS_ARCSEC, "unit": "arcsec"},
        "sources": ["ARCHIVE"],
        "result_limit": 500,
    }
    validation = validate_proposed_observation(request, search_options)
    assert validation.search_readiness is SearchReadiness.READY, (
        f"Case request must reach search readiness before retrieval: {validation.issues}"
    )
    return validation


@pytest.fixture(scope="module")
def live_archive_client() -> ArchiveClient:
    endpoint = os.environ.get("ALMA_TAP_ENDPOINT", DEFAULT_ALMA_TAP_ENDPOINT)
    return ArchiveClient(endpoint, maxrec=5000)


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_case_beam_strategy_diameter_resolution(case_id, live_archive_client, record_property):
    case = CASES[case_id]
    validation = _build_case_validation(case)
    result = search_candidates(
        validation, archive_client=live_archive_client, beam_decision_ref=BEAM_DECISION_REF,
    )
    archive = result.archive
    assert archive.status is S.COMPLETED, (
        f"{case_id}: Archive source did not complete: {archive.status} {archive.reasons}"
    )
    assert result.plan.beam_decision_ref == BEAM_DECISION_REF
    assert result.plan.for_source("ARCHIVE").spatial_operation == "FORMULA_PRIMARY_BEAM"

    array_labels = Counter()
    reason_counts = Counter()
    resolved_diameter_rows = 0
    total = 0

    for row in archive.rows:
        total += 1
        raw = row.context.evidence.prepared.raw_row
        array_labels[str(raw.get("antenna_arrays"))] += 1
        spatial_filter = next((f for f in row.filters if f.name == "spatial"), None)
        if spatial_filter is None or spatial_filter.spatial is None:
            reason_counts["NO_SPATIAL_FILTER_EXECUTED"] += 1
            continue
        selection = spatial_filter.spatial
        for reason in selection.reasons:
            reason_counts[reason] += 1
        if selection.antenna_diameter_m is not None:
            resolved_diameter_rows += 1
        # This strategy must never itself claim a formal position verdict.
        assert selection.assessment == "NOT_EVALUATED"

    print(f"\n{case_id} beam-applicability sample: {total} Archive rows within "
          f"{CASE_SEARCH_RADIUS_ARCSEC} arcsec")
    print(f"{case_id} antenna_arrays raw label counts: {dict(array_labels)}")
    print(f"{case_id} spatial-selection reason counts: {dict(reason_counts)}")
    print(f"{case_id} rows with a resolved antenna diameter: {resolved_diameter_rows}/{total}")

    record_property(f"{case_id}_antenna_arrays_labels", dict(array_labels))
    record_property(f"{case_id}_spatial_reason_counts", dict(reason_counts))
    record_property(f"{case_id}_resolved_diameter_rows", resolved_diameter_rows)
    record_property(f"{case_id}_total_rows", total)

    # This is a measurement, not a pass/fail policy gate: an empty local
    # neighborhood, or one entirely made of unresolved labels, is itself a
    # valid (and reportable) applicability finding, not a test failure.
