"""Opt-in live CASE1/CASE2 retrieval acceptance test.

Independently reproduces the two reported internship-task CASE searches
(docs/duplication_rule_inputs.md section 8, "Recorded CASE inputs") against
the live ALMA Archive TAP service, using search_candidates() -- the same
orchestration service the tool uses for any real search.

test_case_reported_member_is_retrieved tests WEAK RECALL only: "is the
reported candidate Member UID retrieved at all for this coordinate search".
test_case_entry_count_with_aq_equivalent_filters (added 2026-09-11) opts into
the AQ-equivalent frequency/resolution/RMS filters and asserts the exact
visible (Member OUS, target) entries. The weak-recall test does NOT assert:

- an exact candidate count (frequency/RMS/spectral-resolution predicates are
  still SKIPPED by the planner -- see docs/candidate_search.md -- so the
  retained set is broader than a formal duplication search would produce);
- a MATCHED_FILTERS disposition (the matched row may legitimately be
  RETAINED_UNEVALUATED because of skipped predicates or unresolved spatial
  interpretation);
- any duplication verdict. CandidateSearchResult.assessment always stays
  NOT_EVALUATED; this file never changes that.

Per docs/evidence/scientific_feedback.md ("Next retrieval evidence
delivery"): expected Member UIDs belong only in assertions, never in
retrieval filters. This file follows that rule -- the reported UIDs below are
compared against retrieved rows, never used to build the query.

Network access to https://almascience.eso.org/tap is required. This module
is excluded from the default test run via the "live" marker (see
tests/conftest.py); opt in with `pytest --run-live`.
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

# Engineering retrieval radius, independent of the reported "angular filter"
# below (which is a candidate angular-RESOLUTION upper bound, i.e. a beam-size
# predicate, not a search cone -- see docs/duplication_rule_inputs.md section
# 8). Wide enough to tolerate catalog-position rounding between the original
# internship-task transcription and the Archive's stored coordinates, while
# staying a small, fast cone query. This value is an engineering choice, not
# a policy-approved search radius.
CASE_SEARCH_RADIUS_ARCSEC = 10.0

# Transcribed verbatim from docs/duplication_rule_inputs.md section 8
# ("Recorded CASE inputs" / "Developer reference results"). These are
# reported case-search parameters and a reported developer reference result,
# not independently reproduced or policy-approved values. Do not "correct"
# them from any other source without updating that document first.
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
        "angular_arcsec": 0.5,
        "spectral_khz": 1500.0,
        "rms_mjy_beam": 0.02,
        "expected_member_ous_uid": ("uid://A001/X2df9/X1b",),
        "reported_project": "2021.A.00028.S",
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
        "angular_arcsec": 1.0,
        "spectral_khz": 4000.0,
        "rms_mjy_beam": 1.0,
        # Two reported Members for this case; either is sufficient for recall.
        "expected_member_ous_uid": ("uid://A001/X133d/X9c3", "uid://A001/X133d/X9c5"),
        "reported_project": "2018.1.00294.S",
    },
}


def _build_case_validation(case: dict):
    request = {
        "target_kind": "FIXED",
        "geometry": "SINGLE_POINTING",
        "target_name": f"Reported case search, not a confirmed duplicate ({case['reported_project']})",
        "position": case["position"],
        "setup_id": "case-search",
        "setup_complete": False,
        "intents": [],
        "representative_frequency": case["representative_frequency"],
    }
    search_options = {
        "radius": {"value": CASE_SEARCH_RADIUS_ARCSEC, "unit": "arcsec"},
        "sources": ["ARCHIVE"],
        "result_limit": 500,
        "predicates": [
            {
                "field": "angular_resolution", "operator": "<",
                "quantity": {"value": case["angular_arcsec"], "unit": "arcsec"},
            },
            {
                "field": "spectral_resolution", "operator": "<",
                "quantity": {"value": case["spectral_khz"], "unit": "kHz"},
            },
            {
                "field": "sensitivity", "operator": "<",
                "quantity": {"value": case["rms_mjy_beam"], "unit": "mJy/beam"},
            },
        ],
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


def _member_uids(rows) -> set[str]:
    """Best-effort raw member_ous_uid text from each retrieved Archive row.

    Reads the raw TAP column directly rather than the parsed obs_id, so a
    parse failure elsewhere cannot hide a row that was genuinely retrieved.
    """
    values = set()
    for row in rows:
        raw = row.context.evidence.prepared.raw_row.get("member_ous_uid")
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            values.add(text)
    return values


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_case_reported_member_is_retrieved(case_id, live_archive_client, record_property):
    """Weak recall only -- see module docstring for what this does not claim."""
    case = CASES[case_id]
    validation = _build_case_validation(case)
    result = search_candidates(validation, archive_client=live_archive_client)
    archive = result.archive

    print(
        f"\n{case_id} live retrieval: query_run_id={result.plan.for_source('ARCHIVE').archive_query} "
        f"status={archive.status} input_mode={archive.input_mode} rows={len(archive.rows)}"
    )
    print(f"{case_id} disposition counts: {dict(Counter(r.disposition for r in archive.rows))}")
    if archive.reasons:
        print(f"{case_id} archive execution reasons: {archive.reasons}")

    assert archive.status is S.COMPLETED, (
        f"{case_id}: Archive source did not complete: {archive.status} {archive.reasons}"
    )

    retrieved = _member_uids(archive.rows)
    print(f"{case_id} retrieved member_ous_uid values: {sorted(retrieved)}")
    record_property(f"{case_id}_retrieved_member_ous_uid", sorted(retrieved))

    expected = set(case["expected_member_ous_uid"])
    matched = retrieved & expected
    assert matched, (
        f"{case_id}: none of the reported Member UID(s) {sorted(expected)} were retrieved "
        f"within {CASE_SEARCH_RADIUS_ARCSEC} arcsec of the reported position. "
        f"Retrieved instead: {sorted(retrieved)}. This means either the reported case "
        "position/UID needs review, or the search radius/endpoint needs adjustment -- "
        "it does not by itself mean the candidate search service is broken."
    )

    # Record disposition/filter audit for the matched row(s). A
    # RETAINED_UNEVALUATED disposition is expected and acceptable: spatial
    # formal evaluation is not policy-approved (Q1) and frequency/RMS/
    # spectral-resolution predicates are SKIPPED by design.
    for row in archive.rows:
        raw = row.context.evidence.prepared.raw_row.get("member_ous_uid")
        if raw is not None and str(raw).strip() in matched:
            print(
                f"{case_id} matched row {row.context.context_id}: "
                f"disposition={row.disposition} "
                f"filters={[(f.name, f.outcome, f.reasons) for f in row.filters]}"
            )

    # This service never issues a duplication verdict; guard that invariant
    # explicitly so a future change cannot silently turn recall into a label.
    assert result.assessment == "NOT_EVALUATED"


# Expected visible Archive Query entries, (Member OUS, target). Reported by the
# internship task as "one entry" / "two entries"; reproduced offline on
# 2026-09-11 from the live rows with the same filter semantics. CASE2 targets
# are mosaics, so their spatial check stays NOT_EVALUATED (RETAINED).
EXPECTED_ENTRIES = {
    "CASE1": ({("uid://A001/X2df9/X1b", "PKS1830-211")}, "MATCHED_FILTERS"),
    "CASE2": ({("uid://A001/X133d/X9c3", "NGC253"), ("uid://A001/X133d/X9c5", "NGC253")},
              "RETAINED_UNEVALUATED"),
}


def _build_aq_case_validation(case: dict):
    frequency = case["representative_frequency"]
    request = {
        "target_kind": "FIXED",
        "geometry": "SINGLE_POINTING",
        "target_name": f"Reported case search, not a confirmed duplicate ({case['reported_project']})",
        "position": case["position"],
        "setup_id": "case-search",
        "setup_complete": False,
        "intents": [],
        "representative_frequency": frequency,
    }
    search_options = {
        "radius": {"value": CASE_SEARCH_RADIUS_ARCSEC, "unit": "arcsec"},
        "sources": ["ARCHIVE"],
        "result_limit": 500,
        "predicates": [
            {"field": "frequency", "operator": "=",
             "quantity": {"value": frequency["value"], "unit": frequency["unit"]}},
            {"field": "angular_resolution", "operator": "<",
             "quantity": {"value": case["angular_arcsec"], "unit": "arcsec"}},
            {"field": "spectral_resolution", "operator": "<",
             "quantity": {"value": case["spectral_khz"], "unit": "kHz"}},
            {"field": "sensitivity", "operator": "<", "basis": "AGGREGATE",
             "quantity": {"value": case["rms_mjy_beam"], "unit": "mJy/beam"}},
        ],
    }
    validation = validate_proposed_observation(request, search_options)
    assert validation.search_readiness is SearchReadiness.READY, validation.issues
    return validation


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_case_entry_count_with_aq_equivalent_filters(case_id, live_archive_client, record_property):
    """Exact entry count under opt-in AQ-equivalent filters; still no duplication verdict."""
    from alma_duplicate.grouping import group_candidates, visible_groups

    case = CASES[case_id]
    result = search_candidates(_build_aq_case_validation(case), archive_client=live_archive_client,
                               aq_equivalent_filters=True)
    assert result.archive.status is S.COMPLETED, result.archive.reasons
    visible = visible_groups(group_candidates(result))
    keys = {g.key for g in visible}
    print(f"\n{case_id} visible entries: {[(g.label, g.disposition.value) for g in visible]}")
    record_property(f"{case_id}_visible_entries", sorted(" | ".join(k) for k in keys))
    expected_keys, expected_disposition = EXPECTED_ENTRIES[case_id]
    assert keys == expected_keys
    assert all(g.disposition == expected_disposition for g in visible)
    assert result.assessment == "NOT_EVALUATED"
