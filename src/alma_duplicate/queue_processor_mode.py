"""Scoped processor-equivalence experiment; never formal Queue LINE-FDM evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import math

from alma_duplicate.data.correlator_modes import RESPONSES
from alma_duplicate.queue_mode import ABS_TOL_MHZ, REL_TOL, _positive

METHOD_VERSION = "queue_processor_equivalence_1"
MAPPING_SOURCES = {
    f"{kind}{cycle}": {
        "url": f"https://almascience.eso.org/documents-and-tools/cycle{cycle}/alma-{slug}",
        "role": role,
    }
    for cycle in (11, 12, 13)
    for kind, slug, role in (
        ("proposers_guide", "proposers-guide", "Spectral setups and fourfold TP counterpart bandwidth"),
        ("ot_manual", "ot-usermanual", "Single polarization, FULL/TP restriction and multi-region resource table"),
    )
}
# Public OT numerical profiles. These are not a Cycle-specific release manifest.
EXTRA_RESPONSES = {
    "UNIFORM": ((1, 1.207), (2, 1.639), (4, 4.063), (8, 8.033), (16, 16.017)),
    "WELCH": ((1, 1.590), (2, 1.952), (4, 4.007), (8, 8.001), (16, 16.0)),
    "HAMMING": ((1, 1.815),), "BARTLETT": ((1, 1.772),),
    "BLACKMANN": ((1, 2.299),), "BLACKMANN_HARRIS": ((1, 2.666),),
}


@dataclass(frozen=True)
class Configuration:
    configuration_id: str
    cycle: int
    polarization: str
    bandwidth_mhz: float
    resolution_mhz: float
    mode: str
    quantization: str
    resource_divisor: int
    averaging: int
    weighting: str
    response_factor: float
    source_id: str
    export_compatibility: bool


@lru_cache(maxsize=3)
def configurations(cycle: int) -> tuple[Configuration, ...]:
    if cycle not in (11, 12, 13):
        return ()
    profiles = [("HANNING", n, f, s) for n, f, s in RESPONSES]
    profiles += [(w, n, f, "ot_response_rounded")
                 for w, entries in EXTRA_RESPONSES.items() for n, f in entries]
    rows = []
    for pol, products in (("SINGLE", 1), ("DOUBLE", 2), ("FULL", 4)):
        setups = [(1875.0, 2000 / (256 / products), "TDM", "2X2", 1)]
        # Forward resource split: bandwidth and channels decrease together.
        for full_bw in (2000., 1000., 500., 250., 125., 62.5):
            for divisor in (1, 2, 4):
                bw = full_bw / divisor
                if bw < 62.5:
                    continue
                setups.append((1875. if bw == 2000 else bw,
                               full_bw / (8192 / products), "FDM", "2X2", divisor))
        if pol == "DOUBLE":
            setups += [(bw, bw / 1024, "FDM", "4X4", 1)
                       for bw in (1000., 500., 250., 125., 62.5)]
        for bw, spacing, mode, quant, divisor in setups:
            for weighting, n, factor, source in profiles:
                identifier = f"C{cycle}_{pol}_{bw:g}_{mode}_{quant}_R{divisor}_{weighting}_N{n}_{factor:g}"
                rows.append(Configuration(identifier, cycle, pol, bw, spacing * factor,
                                          mode, quant, divisor, n, weighting, factor,
                                          source, source == "queue_export_n16"))
    return tuple(rows)


def consensus(modes) -> str:
    values = set(modes)
    return next(iter(values)) if len(values) == 1 else "UNKNOWN"


@lru_cache(maxsize=4096)
def match(cycle, polarization, bandwidth_mhz, resolution_mhz,
          *, include_export_compatibility=False) -> tuple[Configuration, ...]:
    if not _positive(bandwidth_mhz) or not _positive(resolution_mhz):
        return ()
    return tuple(c for c in configurations(cycle)
                 if c.polarization == polarization
                 and (include_export_compatibility or not c.export_compatibility)
                 and math.isclose(c.bandwidth_mhz, bandwidth_mhz,
                                  rel_tol=REL_TOL, abs_tol=ABS_TOL_MHZ)
                 and math.isclose(c.resolution_mhz, resolution_mhz,
                                  rel_tol=REL_TOL, abs_tol=ABS_TOL_MHZ))


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
        counterpart = c.bandwidth_mhz * (4 if c.quantization == "4X4" else 1)
        if counterpart > 2000:
            reasons.append("TP_COUNTERPART_EXCEEDS_SUPPORTED_BASEBAND")
            continue
        mappings.append({"blc_configuration_id": c.configuration_id,
                         "mapping_kind": "USER_FACING_FPS_EQUIVALENCE",
                         "processor": "ACA_SPECTROMETER", "native_mode": None,
                         "comparison_mode": c.mode,
                         "counterpart_nominal_bandwidth_mhz": counterpart,
                         "counterpart_resolution_mhz": c.resolution_mhz,
                         "source_id": f"proposers_guide{cycle}+handbook{cycle}"})
    return {"method_version": METHOD_VERSION, "method_status": "PROVISIONAL",
            "enumeration_complete": False, "require_tp": require_tp,
            "matched_configuration_ids": [c.configuration_id for c in matches],
            "compatible_modes": sorted({c.mode for c in matches}),
            "known_profile_consensus": consensus(c.mode for c in matches),
            "conditional_processor_consensus": "UNKNOWN" if reasons else consensus(c.mode for c in matches),
            "reasons": sorted(set(reasons)), "tps_mappings": mappings,
            "formal_mode": "UNKNOWN"}


def configuration_record(c: Configuration) -> dict:
    return asdict(c)
