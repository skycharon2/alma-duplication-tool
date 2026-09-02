from __future__ import annotations

import math

import pytest

from alma_duplicate.domain.queue import (
    QueueFrequencyDerivationKind,
    QueueQuantity,
    QueueUnitInterpretation,
    QueueUsableBandwidthDerivationKind,
    QueueVelocityContext,
)
from alma_duplicate.queue_normalization import (
    QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION,
    SPEED_OF_LIGHT_KMS,
    QueueFrequencyDerivationError,
    centred_frequency_interval,
    derive_sky_frequency,
    derive_usable_bandwidth,
    derive_usable_bandwidth_ghz,
    derived_sky_interval,
    observed_to_velocity_kms,
)


def _quantity(value: float, unit: str) -> QueueQuantity:
    raw = str(value)
    return QueueQuantity(
        raw_text=raw,
        raw_value=value,
        value=value,
        dictionary_unit=f"[{unit}]",
        secondary_unit=f"[{unit}]",
        canonical_unit=unit,
        unit_interpretation=QueueUnitInterpretation.DIRECT,
        normalization_version="1",
    )


def _velocity(
    value: float,
    convention: str,
    *,
    is_sky: bool = False,
) -> QueueVelocityContext:
    return QueueVelocityContext(
        velocity_kms=_quantity(value, "km/s"),
        frame_raw="lsrk",
        convention_raw=convention,
        is_sky_frequency=is_sky,
    )


@pytest.mark.parametrize(
    ("convention", "expected_factor", "kind"),
    [
        (
            "RADIO",
            1.0 - 300.0 / SPEED_OF_LIGHT_KMS,
            QueueFrequencyDerivationKind.RADIO_DOPPLER,
        ),
        (
            "OPTICAL",
            1.0 / (1.0 + 300.0 / SPEED_OF_LIGHT_KMS),
            QueueFrequencyDerivationKind.OPTICAL_DOPPLER,
        ),
        (
            "RELATIVISTIC",
            math.sqrt(
                (1.0 - 300.0 / SPEED_OF_LIGHT_KMS)
                / (1.0 + 300.0 / SPEED_OF_LIGHT_KMS)
            ),
            QueueFrequencyDerivationKind.RELATIVISTIC_DOPPLER,
        ),
    ],
)
def test_supported_doppler_conventions_are_traceable(
    convention: str,
    expected_factor: float,
    kind: QueueFrequencyDerivationKind,
) -> None:
    frequency = _quantity(230.0, "GHz")

    result = derive_sky_frequency(
        frequency,
        _velocity(300.0, convention),
    )

    assert result.kind is kind
    assert result.doppler_factor == pytest.approx(expected_factor)
    assert result.sky_frequency_ghz == pytest.approx(
        230.0 * expected_factor
    )
    assert result.source_frequency_ghz is frequency


def test_declared_sky_frequency_is_not_shifted() -> None:
    result = derive_sky_frequency(
        _quantity(93.188, "GHz"),
        _velocity(-39.4, "RADIO", is_sky=True),
    )

    assert result.kind is (
        QueueFrequencyDerivationKind.DECLARED_SKY_FREQUENCY
    )
    assert result.doppler_factor == 1.0
    assert result.sky_frequency_ghz == 93.188


def test_nominal_bandwidth_is_not_doppler_scaled() -> None:
    derivation = derive_sky_frequency(
        _quantity(230.0, "GHz"),
        _velocity(300.0, "RADIO"),
    )

    nominal_width, lower, upper = derived_sky_interval(
        derivation,
        _quantity(1875.0, "MHz"),
    )

    assert derivation.doppler_factor != pytest.approx(1.0)
    assert nominal_width == pytest.approx(1.875)
    assert upper - lower == pytest.approx(nominal_width)
    assert (upper + lower) / 2.0 == pytest.approx(
        derivation.sky_frequency_ghz
    )


def test_high_redshift_centre_does_not_collapse_correlator_width() -> None:
    derivation = derive_sky_frequency(
        _quantity(3375.28913187956, "GHz"),
        _velocity(274836.78847531846, "RADIO"),
    )

    nominal_width, lower, upper = derived_sky_interval(
        derivation,
        _quantity(1875.0, "MHz"),
    )

    assert derivation.sky_frequency_ghz == pytest.approx(
        280.96971047028603
    )
    assert nominal_width == pytest.approx(1.875)
    assert lower == pytest.approx(280.03221047028603)
    assert upper == pytest.approx(281.90721047028603)


@pytest.mark.parametrize(
    ("nominal_mhz", "usable_mhz"),
    [
        (62.5, 58.6),
        (125.0, 117.2),
        (250.0, 234.4),
        (500.0, 468.8),
        (1000.0, 937.5),
        (1875.0, 1875.0),
        (2000.0, 1875.0),
    ],
)
def test_cycle13_usable_bandwidth_mapping(
    nominal_mhz: float,
    usable_mhz: float,
) -> None:
    assert derive_usable_bandwidth_ghz(
        _quantity(nominal_mhz, "MHz")
    ) == pytest.approx(usable_mhz / 1000.0)
    assert QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION == (
        "cycle13-portal-plotobs-v1.3.1-v1"
    )


@pytest.mark.parametrize(
    ("input_mhz", "usable_mhz"),
    [
        (62.50000001, 58.6),
        (58.6, 58.6),
        (117.2, 117.2),
        (937.5, 937.5),
        (1900.0, 1875.0),
    ],
)
def test_portal_script_tolerances_and_already_usable_values(
    input_mhz: float,
    usable_mhz: float,
) -> None:
    result = derive_usable_bandwidth(_quantity(input_mhz, "MHz"))

    assert result.usable_bandwidth_ghz == pytest.approx(
        usable_mhz / 1000.0
    )
    assert result.kind in {
        QueueUsableBandwidthDerivationKind.NOMINAL_MAPPED,
        QueueUsableBandwidthDerivationKind.ALREADY_USABLE,
    }


def test_unrecognized_usable_bandwidth_is_explicit_evidence() -> None:
    result = derive_usable_bandwidth(_quantity(750.0, "MHz"))

    assert result.usable_bandwidth_ghz is None
    assert result.kind is (
        QueueUsableBandwidthDerivationKind.UNRECOGNIZED
    )


def test_unknown_nominal_bandwidth_fails_closed() -> None:
    with pytest.raises(
        QueueFrequencyDerivationError,
        match="UNRECOGNIZED",
    ):
        derive_usable_bandwidth_ghz(_quantity(750.0, "MHz"))


def test_usable_interval_is_centred_without_doppler_scaling() -> None:
    lower, upper = centred_frequency_interval(100.0, 0.9375)

    assert lower == pytest.approx(99.53125)
    assert upper == pytest.approx(100.46875)


@pytest.mark.parametrize(
    "convention",
    ["RADIO", "OPTICAL", "RELATIVISTIC"],
)
def test_frequency_velocity_conversion_round_trips(
    convention: str,
) -> None:
    velocity = 1250.0
    result = derive_sky_frequency(
        _quantity(230.0, "GHz"),
        _velocity(velocity, convention),
    )

    recovered = observed_to_velocity_kms(
        230.0,
        result.sky_frequency_ghz,
        convention,
    )

    assert recovered == pytest.approx(velocity)


@pytest.mark.parametrize(
    ("velocity", "convention"),
    [
        (SPEED_OF_LIGHT_KMS, "RADIO"),
        (-SPEED_OF_LIGHT_KMS, "OPTICAL"),
        (SPEED_OF_LIGHT_KMS, "RELATIVISTIC"),
        (0.0, "UNKNOWN"),
    ],
)
def test_invalid_doppler_domains_are_rejected(
    velocity: float,
    convention: str,
) -> None:
    with pytest.raises(QueueFrequencyDerivationError):
        derive_sky_frequency(
            _quantity(230.0, "GHz"),
            _velocity(velocity, convention),
        )
