"""Queue-side unit-safe frequency derivations."""

from __future__ import annotations

import math

from alma_duplicate.domain.queue import (
    QueueFrequencyDerivation,
    QueueFrequencyDerivationKind,
    QueueQuantity,
    QueueVelocityContext,
)

QUEUE_FREQUENCY_DERIVATION_VERSION = "2"
QUEUE_UNIT_NORMALIZATION_VERSION = "1"
QUEUE_USABLE_BANDWIDTH_DERIVATION_VERSION = (
    "cycle13-technical-handbook-table-5.3-v1"
)
SPEED_OF_LIGHT_KMS = 299792.458

# Cycle 13 Technical Handbook, Table 5.3. Keep this as a finite,
# versioned mapping so a future correlator setup cannot silently inherit
# an unverified usable-width rule.
_USABLE_BANDWIDTH_MHZ_BY_NOMINAL_MHZ = {
    62.5: 58.6,
    125.0: 117.2,
    250.0: 234.4,
    500.0: 468.8,
    1000.0: 937.5,
    1875.0: 1875.0,
    2000.0: 1875.0,
}


class QueueFrequencyDerivationError(ValueError):
    """Raised when Queue frequency evidence has an invalid domain."""


def _doppler_factor(
    velocity_kms: float,
    convention: str,
) -> tuple[float, QueueFrequencyDerivationKind]:
    beta = velocity_kms / SPEED_OF_LIGHT_KMS
    normalized = convention.strip().upper()

    if normalized == "RADIO":
        if beta >= 1.0:
            raise QueueFrequencyDerivationError(
                "RADIO convention requires v/c < 1"
            )
        return (
            1.0 - beta,
            QueueFrequencyDerivationKind.RADIO_DOPPLER,
        )

    if normalized == "OPTICAL":
        if 1.0 + beta <= 0.0:
            raise QueueFrequencyDerivationError(
                "OPTICAL convention requires 1 + v/c > 0"
            )
        return (
            1.0 / (1.0 + beta),
            QueueFrequencyDerivationKind.OPTICAL_DOPPLER,
        )

    if normalized == "RELATIVISTIC":
        if abs(beta) >= 1.0:
            raise QueueFrequencyDerivationError(
                "RELATIVISTIC convention requires |v/c| < 1"
            )
        return (
            math.sqrt((1.0 - beta) / (1.0 + beta)),
            QueueFrequencyDerivationKind.RELATIVISTIC_DOPPLER,
        )

    raise QueueFrequencyDerivationError(
        f"unsupported velocity convention: {convention!r}"
    )


def derive_sky_frequency(
    source_frequency_ghz: QueueQuantity,
    velocity: QueueVelocityContext,
) -> QueueFrequencyDerivation:
    """Convert one Queue source frequency in its declared frame."""

    if (
        not math.isfinite(source_frequency_ghz.value)
        or source_frequency_ghz.value <= 0.0
    ):
        raise QueueFrequencyDerivationError(
            "source frequency must be finite and positive"
        )

    if velocity.is_sky_frequency:
        factor = 1.0
        kind = (
            QueueFrequencyDerivationKind
            .DECLARED_SKY_FREQUENCY
        )
    else:
        factor, kind = _doppler_factor(
            velocity.velocity_kms.value,
            velocity.convention_raw,
        )

    sky_frequency = source_frequency_ghz.value * factor
    if not math.isfinite(sky_frequency) or sky_frequency <= 0.0:
        raise QueueFrequencyDerivationError(
            "derived sky frequency must be finite and positive"
        )

    return QueueFrequencyDerivation(
        source_frequency_ghz=source_frequency_ghz,
        sky_frequency_ghz=sky_frequency,
        doppler_factor=factor,
        kind=kind,
        velocity_frame_raw=velocity.frame_raw,
        velocity_convention_raw=velocity.convention_raw,
        derivation_version=(
            QUEUE_FREQUENCY_DERIVATION_VERSION
        ),
    )


def derived_sky_interval(
    derivation: QueueFrequencyDerivation,
    source_bandwidth_mhz: QueueQuantity,
) -> tuple[float, float, float]:
    """Return nominal correlator bandwidth and sky-centred bounds.

    Queue rest frequencies require a Doppler conversion for the SPW
    centre.  ``Bandwidth SPW N`` is a nominal correlator setup value,
    however, so it is converted from MHz to GHz but is not multiplied by
    the centre-frequency Doppler factor.
    """

    bandwidth_mhz = source_bandwidth_mhz.value
    if not math.isfinite(bandwidth_mhz) or bandwidth_mhz <= 0.0:
        raise QueueFrequencyDerivationError(
            "source bandwidth must be finite and positive"
        )

    nominal_bandwidth_ghz = bandwidth_mhz / 1000.0
    lower, upper = centred_frequency_interval(
        derivation.sky_frequency_ghz,
        nominal_bandwidth_ghz,
    )

    return nominal_bandwidth_ghz, lower, upper


def derive_usable_bandwidth_ghz(
    source_bandwidth_mhz: QueueQuantity,
) -> float:
    """Map a recognized nominal correlator width to usable GHz."""

    nominal_mhz = source_bandwidth_mhz.value
    if not math.isfinite(nominal_mhz) or nominal_mhz <= 0.0:
        raise QueueFrequencyDerivationError(
            "source bandwidth must be finite and positive"
        )

    for expected_mhz, usable_mhz in (
        _USABLE_BANDWIDTH_MHZ_BY_NOMINAL_MHZ.items()
    ):
        if math.isclose(
            nominal_mhz,
            expected_mhz,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            return usable_mhz / 1000.0

    raise QueueFrequencyDerivationError(
        "nominal SPW bandwidth has no verified Cycle 13 usable-width "
        f"mapping: {nominal_mhz!r} MHz"
    )


def centred_frequency_interval(
    centre_ghz: float,
    bandwidth_ghz: float,
) -> tuple[float, float]:
    """Return validated bounds for a positive, centred GHz interval."""

    if not math.isfinite(centre_ghz) or centre_ghz <= 0.0:
        raise QueueFrequencyDerivationError(
            "interval centre must be finite and positive"
        )
    if not math.isfinite(bandwidth_ghz) or bandwidth_ghz <= 0.0:
        raise QueueFrequencyDerivationError(
            "interval bandwidth must be finite and positive"
        )

    lower = centre_ghz - bandwidth_ghz / 2.0
    upper = centre_ghz + bandwidth_ghz / 2.0
    if lower <= 0.0 or lower >= upper:
        raise QueueFrequencyDerivationError(
            "derived frequency interval is invalid"
        )
    return lower, upper


def observed_to_velocity_kms(
    rest_frequency_ghz: float,
    observed_frequency_ghz: float,
    convention: str,
) -> float:
    """Invert the v1 formula for deterministic regression tests."""

    if rest_frequency_ghz <= 0.0 or observed_frequency_ghz <= 0.0:
        raise QueueFrequencyDerivationError(
            "frequencies must be positive"
        )

    normalized = convention.strip().upper()
    if normalized == "RADIO":
        beta = 1.0 - observed_frequency_ghz / rest_frequency_ghz
    elif normalized == "OPTICAL":
        beta = rest_frequency_ghz / observed_frequency_ghz - 1.0
    elif normalized == "RELATIVISTIC":
        rest_squared = rest_frequency_ghz**2
        observed_squared = observed_frequency_ghz**2
        beta = (
            (rest_squared - observed_squared)
            / (rest_squared + observed_squared)
        )
    else:
        raise QueueFrequencyDerivationError(
            f"unsupported velocity convention: {convention!r}"
        )

    return beta * SPEED_OF_LIGHT_KMS
