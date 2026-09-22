"""Diagnostic Queue mode evidence; never source-provided or approved."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueueModeConfiguration:
    """One supported spectral signature, not a recovered baseband identity."""

    configuration_id: str
    cycle: int
    processor: str
    polarization: str
    bandwidth_mhz: float
    resolution_mhz: float
    mode: str
    averaging: int
    resource_fraction: float
    quantization: str
    channel_spacing_mhz: float
    source_id: str


@dataclass(frozen=True, slots=True)
class QueueCorrelatorModeEvidence:
    """Separate configuration uniqueness, mode consensus and applicability."""

    project_cycle: int | None
    polarization: str
    bandwidth_mhz: float | None
    resolution_mhz: float | None
    matched_configurations: tuple[QueueModeConfiguration, ...]
    configuration_status: str
    configuration_reason: str
    unique_configuration_mode: str
    compatible_modes: tuple[str, ...]
    conditional_mode_consensus: str
    # CSV array requirements do not bind a row to a particular processor.
    source_bound_mode: str = "UNKNOWN"
    source_bound_reason: str = "PROCESSOR_ASSOCIATION_UNRESOLVED"
    evidence_origin: str = "APPLICATION_DERIVED"
    method_status: str = "PROVISIONAL"
    method_version: str = "queue_correlator_configuration_match_1"
