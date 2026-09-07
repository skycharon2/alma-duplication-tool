import math

import pytest

from alma_duplicate.clients.archive_field_contract import (
    build_archive_comparison_evidence,
    validate_archive_comparison_metadata,
)
from alma_duplicate.domain.archive_evidence import (
    ArchiveEvidenceIssueKind, ArchiveQuantityStatus,
)
from tests.unit.test_archive_field_contract import _metadata, _row


def _build(changes, units=None):
    return build_archive_comparison_evidence(
        _row() | changes,
        validate_archive_comparison_metadata(_metadata(unit_overrides=units)),
        query_run_id="numeric-test", raw_row_id="numeric-test:0", result_index=0,
    )


def _quantities(evidence):
    return (
        evidence.frequency.centre, evidence.frequency.bandwidth,
        evidence.spectral_resolution.quantity, evidence.angular_resolution.quantity,
        evidence.line_sensitivity.quantity, evidence.continuum_sensitivity.quantity,
    )


@pytest.mark.parametrize("field,unit,value", [
    ("spatial_resolution", "deg", 1e308),
    ("spectral_resolution", "GHz", 1e308),
    ("sensitivity_10kms", "Jy / beam", 1e308),
    ("cont_sensitivity_bandwidth", "Jy / beam", 1e308),
    ("frequency", "THz", 1e308),
    ("bandwidth", "THz", 1e308),
    ("bandwidth", "Hz", 5e-324),
    ("frequency", "Hz", 5e-324),
])
def test_conversion_overflow_and_underflow_keep_raw_evidence(field, unit, value):
    evidence = _build({field: value}, {field: unit})
    quantity = next(q for q in _quantities(evidence) if q.provenance.source_field == field)
    assert quantity.status is ArchiveQuantityStatus.INVALID_VALUE
    assert quantity.canonical_value is None
    assert quantity.raw_value == value
    assert quantity.source_unit == unit
    assert quantity.provenance.raw_row_id == "numeric-test:0"
    assert "canonical" in quantity.invalid_reason
    assert any(issue.kind is ArchiveEvidenceIssueKind.VALUE_INVALID
               and issue.source_field == field and quantity.invalid_reason in issue.message
               for issue in evidence.issues)
    for q in _quantities(evidence):
        if q.is_available:
            assert math.isfinite(q.canonical_value) and q.canonical_value > 0
    if field in {"frequency", "bandwidth"}:
        assert not evidence.has_frequency_coverage


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 10**1000])
def test_invalid_source_numeric_conversion_does_not_escape(value):
    quantity = _build({"frequency": value}).frequency.centre
    assert quantity.status is ArchiveQuantityStatus.INVALID_VALUE
    assert quantity.canonical_value is None
    assert quantity.raw_value is value
    assert quantity.invalid_reason.startswith("source")


@pytest.mark.parametrize("centre,bandwidth", [
    (1.7e308, 1.0e308),  # finite quantities, overflowing upper endpoint
    (1.0, 5e-324),     # half-width underflows and endpoints collapse
    (1e100, 1.0),      # float rounding collapses distinct mathematical endpoints
    (1.0, 2.0),       # lower endpoint zero
    (1.0, 3.0),       # lower endpoint negative
])
def test_invalid_interval_does_not_invalidate_individually_valid_quantities(centre, bandwidth):
    evidence = _build({"frequency": centre, "bandwidth": bandwidth}, {"bandwidth": "GHz"})
    assert evidence.frequency.centre.is_available
    assert evidence.frequency.bandwidth.is_available
    assert evidence.frequency.lower_ghz is None
    assert evidence.frequency.upper_ghz is None
    assert not evidence.has_frequency_coverage
    assert any(issue.kind is ArchiveEvidenceIssueKind.FREQUENCY_INTERVAL_INVALID
               for issue in evidence.issues)


def test_normal_conversions_keep_expected_canonical_values():
    evidence = _build(
        {"frequency": 100000, "bandwidth": 200,
         "spatial_resolution": 0.5 / 3600, "spectral_resolution": 0.97656,
         "sensitivity_10kms": 0.001, "cont_sensitivity_bandwidth": 0.0002},
        {"frequency": "MHz", "bandwidth": "MHz", "spatial_resolution": "deg",
         "spectral_resolution": "MHz", "sensitivity_10kms": "Jy / beam",
         "cont_sensitivity_bandwidth": "Jy / beam"},
    )
    for quantity, expected in zip(_quantities(evidence), (100, 0.2, 976.56, 0.5, 1, 0.2)):
        assert quantity.is_available
        assert quantity.invalid_reason is None
        assert quantity.canonical_value == pytest.approx(expected)
    assert evidence.frequency.lower_ghz == pytest.approx(99.9)
    assert evidence.frequency.upper_ghz == pytest.approx(100.1)


def test_finite_positive_subnormal_is_not_arbitrarily_rejected():
    quantity = _build({"spatial_resolution": 5e-324}).angular_resolution.quantity
    assert quantity.is_available
    assert quantity.canonical_value == 5e-324
    assert quantity.invalid_reason is None
