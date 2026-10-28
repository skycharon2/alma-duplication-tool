"""Characterize the *legacy* LINE scope before introducing a versioned successor.

These checks intentionally pin ``archive_line_context_or_1``. They are not the
proposed submitted-requirements-scoped verdict and must not be reinterpreted
as its acceptance tests. No Archive network requests are made.
"""

from dataclasses import replace

import pytest

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.clients.archive_replay import RecordedArchiveClient
from alma_duplicate.rules.aggregation import Truth
from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
from alma_duplicate.ui.proposed import build_document
from tests.integration.test_line_evaluation import evaluate as evaluate_single
from tests.integration.test_line_evaluation import sky_request
from tests.integration.test_line_preparation import EXAMPLE, validate
from tests.integration.test_mosaic_scientific_acceptance import _line_case


@pytest.fixture(scope="module")
def single_source():
    """Reuse the approved fixed Archive LINE replay, not live TAP or invented RMS."""
    return search_candidates(
        validate(),
        archive_client=RecordedArchiveClient(EXAMPLE / "archive/manifest.json"),
    ).archive.source_record


def _single_comparison(source, *, misses_frequency, inventory_complete):
    requested = sky_request(240 if misses_frequency else 225.134765625)
    requested["request"]["setup_complete"] = inventory_complete
    result = evaluate_single(source, requested)
    item = result.context_evaluations[0]
    return item.line_pairs, item.branches[0]


def _mosaic_comparison(*, misses_frequency, inventory_complete):
    request, context, pointings, execution, array_evidence = _line_case()
    request = replace(request, setup_complete=inventory_complete)
    if misses_frequency:
        window = request.spectral_windows[0]
        quantity = replace(window.center.quantity, value=500.0, raw_value=500.0)
        request = replace(request, spectral_windows=(replace(
            window, center=replace(window.center, quantity=quantity)),))
    result = evaluate_mosaic_context(
        request, context, pointings, executions=[execution], array_evidence=array_evidence,
    )
    return result["line_pairs"], result["branches"][0]


@pytest.mark.parametrize("geometry", ["SINGLE_POINTING", "MOSAIC"])
@pytest.mark.parametrize(
    "misses_frequency,inventory_complete,expected_pair,expected_context",
    [
        (True, False, Truth.FALSE, Truth.UNKNOWN),
        (True, True, Truth.FALSE, Truth.FALSE),
        (False, False, Truth.TRUE, Truth.TRUE),
    ],
)
def test_legacy_line_pair_and_context_scopes_are_distinct(
    single_source, geometry, misses_frequency, inventory_complete,
    expected_pair, expected_context,
):
    """The recorded pair remains definitive even when the legacy OR is UNKNOWN."""
    if geometry == "SINGLE_POINTING":
        pairs, branch = _single_comparison(
            single_source, misses_frequency=misses_frequency,
            inventory_complete=inventory_complete,
        )
    else:
        pairs, branch = _mosaic_comparison(
            misses_frequency=misses_frequency,
            inventory_complete=inventory_complete,
        )

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.truth is expected_pair
    assert branch.truth is expected_context
    assert pair.method_version == "archive_line_pair_and_1"
    assert branch.method_version == "archive_line_context_or_1"

    if misses_frequency:
        coverage = next(c for c in pair.criteria if c.criterion_id == "LINE-COVERAGE")
        assert coverage.outcome == "NOT_SATISFIED"
    if not inventory_complete:
        assert "PROPOSED_ENUMERATION_INCOMPLETE" in branch.reasons
    else:
        assert "PROPOSED_ENUMERATION_INCOMPLETE" not in branch.reasons


@pytest.mark.parametrize("inventory_complete", [False, True])
def test_browser_wire_mapping_keeps_line_inputs_separate_from_optional_bandwidth(
    inventory_complete,
):
    """A filled requested LINE row does not itself assert a full physical inventory."""
    row = "w123456abcdef"
    values = {
        "setup_id": "setup-1", "intents": ["LINE"],
        "ra": "201.365", "dec": "-43.019", "radius": "30",
        "sources": ["ARCHIVE"], "angular": "0.3",
        "redshift": "0.024", row + "_id": "line-0",
        row + "_center": "230.538", row + "_center_kind": "REST",
        row + "_mode": "FDM", row + "_resolution": "20", row + "_rms": "0.3",
    }
    if inventory_complete:
        values["setup_complete"] = "on"
    document, _ = build_document(values, [row])
    request = document["request"]
    assert request["setup_complete"] is inventory_complete
    assert len(request["spectral_windows"]) == 1
    window = request["spectral_windows"][0]
    assert window["window_id"] == "line-0"
    assert window["correlator_mode"] == "FDM"
    assert window["center"]["value"] == "230.538"
    assert "bandwidth" not in window
    assert len(request["sensitivities"]) == 1
    sensitivity = request["sensitivities"][0]
    assert sensitivity["purpose"] == "LINE"
    assert sensitivity["window_ids"] == ["line-0"]
    assert sensitivity["smoothing_resolution"]["value"] == "20"
    assert sensitivity["rms"]["value"] == "0.3"


@pytest.mark.parametrize(
    "misses_frequency,inventory_complete,expected_pair,expected_context",
    [
        (True, False, "CRITERIA_NOT_MET", "INDETERMINATE"),
        (True, True, "CRITERIA_NOT_MET", "CRITERIA_NOT_MET"),
        (False, False, "CRITERIA_MET", "CRITERIA_MET"),
    ],
)
def test_legacy_line_scope_through_default_mosaic_s_region_assessment(
    misses_frequency, inventory_complete, expected_pair, expected_context,
):
    """Exercise the actual s_region Mosaic assessment entrypoint, not AQ pointings.

    Use the existing synthetic Guide B Archive row and *its recorded s_region*.
    Point the imported test OT at that row's recorded spatial centre; the
    spectral operands, comparison context and scientific methods stay unchanged.
    """
    from alma_duplicate.assessment import assess_archive_mosaic_contexts
    from alma_duplicate.proposed_mosaic import import_proposed

    request, context, _, _, _ = _line_case()
    request = replace(request, setup_complete=inventory_complete)
    if misses_frequency:
        window = request.spectral_windows[0]
        quantity = replace(window.center.quantity, value=500.0, raw_value=500.0)
        request = replace(
            request, spectral_windows=(replace(
                window, center=replace(window.center, quantity=quantity)),),
        )

    archive_row = context.evidence.prepared.raw_row
    assert archive_row["s_region"], "The test must use recorded Archive region evidence"
    ra, dec = float(archive_row["s_ra"]), float(archive_row["s_dec"])
    proposed = import_proposed(
        ("RA,Dec,Coordinate Type,Coordinate Units\n--\n"
         f"{ra:.15g},{dec:.15g},Absolute,Degrees\n").encode("ascii"),
        source_name=request.target_name, array="12m",
        confirm_fixed_icrs=True, confirm_complete=True,
    )
    result = assess_archive_mosaic_contexts(
        request, proposed, [context],
        package_directories={}, array_catalog=None,
        use_s_region=True,
    )

    assert result["pointing_source"] == "ARCHIVE_S_REGION"
    assert result["metadata_source"] == "EXISTING_ARCHIVE_COMPARISON_CONTEXTS"
    assert len(result["contexts"]) == 1
    evaluated = result["contexts"][0]
    coverage = evaluated["coverage"]
    assert coverage["coverage_source"] == "ARCHIVE_S_REGION"
    assert coverage["raw_s_region"] == archive_row["s_region"]
    assert coverage["inside_count"] == coverage["pointing_count"] == 1
    assert coverage["scope_status"] == "NO_TP_SCOPE_EXCLUSION"
    position = next(c for c in evaluated["criteria"] if c["criterion_id"] == "POS-MOSAIC")
    assert position["method_version"] == "archive_pos_mosaic_s_region_1"
    assert position["outcome"] == "SATISFIED"

    assert evaluated["line_pairing"]["proposed_enumeration_complete"] is inventory_complete
    assert len(evaluated["line_pairs"]) == 1
    pair = evaluated["line_pairs"][0]
    branch = evaluated["branches"][0]
    assert pair["method_version"] == "archive_line_pair_and_1"
    assert branch["method_version"] == "archive_line_context_or_1"
    assert pair["status"] == expected_pair
    assert branch["status"] == expected_context
    if misses_frequency:
        coverage_rule = next(c for c in pair["criteria"] if c["criterion_id"] == "LINE-COVERAGE")
        assert coverage_rule["outcome"] == "NOT_SATISFIED"
    if not inventory_complete:
        assert "PROPOSED_ENUMERATION_INCOMPLETE" in branch["reasons"]
    else:
        assert "PROPOSED_ENUMERATION_INCOMPLETE" not in branch["reasons"]
