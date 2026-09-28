"""Scoped processor-equivalence experiment; never formal Queue LINE-FDM evidence."""
from __future__ import annotations

from dataclasses import asdict

# Compatibility exports preserve existing diagnostic callers.
from alma_duplicate.queue_mode_reference import (
    Configuration as Configuration,
    EXTRA_RESPONSES as EXTRA_RESPONSES,
    MAPPING_SOURCES as MAPPING_SOURCES,
    configurations as configurations,
    configuration_record as configuration_record,
    consensus as consensus,
    match as match,
    map_tp_counterpart,
)

METHOD_VERSION = "queue_processor_equivalence_1"


def evaluate(cycle, polarization, bandwidth_mhz, resolution_mhz, *,
             require_tp=True, include_export_compatibility=False) -> dict:
    """Conditional agreement under documented user-facing FPS equivalence.

    TPS records are mappings, not independently recovered native configurations.
    Every compatible BLC explanation must have a mapping when TP is required.
    """
    matches = match(cycle, polarization, bandwidth_mhz, resolution_mhz,
                    include_export_compatibility=include_export_compatibility)
    mappings = []
    reasons = []
    if not matches:
        reasons.append("NO_SUPPORTED_SIGNATURE")
    if require_tp and polarization == "FULL":
        reasons.append("FULL_POLARIZATION_TP_UNSUPPORTED")
    for c in matches:
        if not require_tp or polarization == "FULL":
            continue
        mapping = map_tp_counterpart(c)
        reasons.extend(mapping.reasons)
        if mapping.counterpart is not None:
            mappings.append(asdict(mapping.counterpart))
    return {"method_version": METHOD_VERSION, "method_status": "PROVISIONAL",
            "enumeration_complete": False, "require_tp": require_tp,
            "matched_configuration_ids": [c.configuration_id for c in matches],
            "compatible_modes": sorted({c.mode for c in matches}),
            "known_profile_consensus": consensus(c.mode for c in matches),
            "conditional_processor_consensus": "UNKNOWN" if reasons else consensus(c.mode for c in matches),
            "reasons": sorted(set(reasons)), "tps_mappings": mappings,
            "formal_mode": "UNKNOWN"}
