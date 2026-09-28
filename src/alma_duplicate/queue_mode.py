"""Conditional per-SPW inverse lookup for the Queue census, not LINE-FDM."""

from __future__ import annotations

import math
from functools import lru_cache

from alma_duplicate.data.correlator_modes import configurations
from alma_duplicate.domain.queue_mode import QueueCorrelatorModeEvidence

from alma_duplicate.queue_mode_reference import (
    ABS_TOL_MHZ as ABS_TOL_MHZ,
    REL_TOL as REL_TOL,
    _positive as _positive,
    project_cycle as project_cycle,
)


@lru_cache(maxsize=4096)
def derive_queue_mode(
    cycle: int | None,
    polarization: str,
    bandwidth_mhz: float | None,
    resolution_mhz: float | None,
) -> QueueCorrelatorModeEvidence:
    """Match all supported BLC configurations, preserving same-mode ambiguity.

    No processor is supplied by the CSV. Therefore source_bound_mode remains
    UNKNOWN even if a conditional configuration or mode is unique. Neither
    array requirement flags nor scientific intents are classifier arguments.
    """
    matches = ()
    reason = "NONSTANDARD_RESOLUTION"
    if cycle not in (11, 12, 13):
        reason = "UNSUPPORTED_CYCLE"
    elif polarization not in ("DOUBLE", "FULL"):
        reason = "UNKNOWN_OR_UNSUPPORTED_POLARIZATION"
    elif bandwidth_mhz is None or resolution_mhz is None:
        reason = "INCOMPLETE_EVIDENCE"
    elif not _positive(bandwidth_mhz):
        reason = "INVALID_BANDWIDTH"
    elif not _positive(resolution_mhz):
        reason = "INVALID_RESOLUTION"
    else:
        band_matches = tuple(
            c
            for c in configurations(cycle)
            if c.polarization == polarization
            and math.isclose(
                c.bandwidth_mhz, bandwidth_mhz, rel_tol=REL_TOL, abs_tol=ABS_TOL_MHZ
            )
        )
        if not band_matches:
            reason = "UNSUPPORTED_BANDWIDTH"
        matches = tuple(
            c
            for c in band_matches
            if math.isclose(
                c.resolution_mhz, resolution_mhz, rel_tol=REL_TOL, abs_tol=ABS_TOL_MHZ
            )
        )
        if matches:
            reason = (
                "UNIQUE_CONFIGURATION_MATCH"
                if len(matches) == 1
                else "AMBIGUOUS_CONFIGURATION"
            )
    modes = tuple(sorted({c.mode for c in matches}))
    return QueueCorrelatorModeEvidence(
        project_cycle=cycle,
        polarization=polarization,
        bandwidth_mhz=bandwidth_mhz,
        resolution_mhz=resolution_mhz,
        matched_configurations=matches,
        configuration_status=(
            "AVAILABLE"
            if len(matches) == 1
            else "AMBIGUOUS"
            if matches
            else "UNAVAILABLE"
        ),
        configuration_reason=reason,
        unique_configuration_mode=matches[0].mode if len(matches) == 1 else "UNKNOWN",
        compatible_modes=modes,
        conditional_mode_consensus=modes[0] if len(modes) == 1 else "UNKNOWN",
    )
