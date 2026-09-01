from __future__ import annotations

import math

import pytest

from alma_duplicate.domain.queue import (
    QueueFrequencyDerivationKind,
    QueueQuantity,
    QueueUnitInterpretation,
    QueueVelocityContext,
)
from alma_duplicate.queue_normalization import (
    SPEED_OF_LIGHT_KMS,
    QueueFrequencyDerivationError,
    derive_sky_frequency,
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


def test_bandwidth_uses_same_doppler_factor_as_centre() -> None:
    derivation = derive_sky_frequency(
        _quantity(230.0, "GHz"),
        _velocity(300.0, "RADIO"),
    )

    sky_width, lower, upper = derived_sky_interval(
        derivation,
        _quantity(1875.0, "MHz"),
    )

    assert sky_width == pytest.approx(
        1.875 * derivation.doppler_factor
    )
    assert upper - lower == pytest.approx(sky_width)
    assert (upper + lower) / 2.0 == pytest.approx(
        derivation.sky_frequency_ghz
    )


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
