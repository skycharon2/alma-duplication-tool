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
