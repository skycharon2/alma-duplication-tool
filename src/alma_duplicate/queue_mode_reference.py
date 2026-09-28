"""Supported Queue reference configurations and conditional processor mappings.

This catalog is incomplete; mappings do not recover native TPS configurations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import math
import re

from alma_duplicate.data.correlator_modes import RESPONSES, PROJECT_CYCLES

# Only absorb representation noise (e.g. 7.812011718750001). Do not round
# 7.81201171875 to 7.8125 or 0.060577392578125 to 0.06103515625.
REL_TOL = 1e-12
ABS_TOL_MHZ = 1e-12


def project_cycle(project_code: str) -> int | None:
    """Submission cycle, never the year in the snapshot filename."""
    if not re.fullmatch(r"\d{4}\.[12A]\.[0-9]{5}\.[A-Z]", project_code):
        return None
    return PROJECT_CYCLES.get(project_code[:4])


def _positive(value: float | None) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


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


@dataclass(frozen=True)
class TpCounterpart:
    blc_configuration_id: str
    mapping_kind: str
    processor: str
    native_mode: None
    comparison_mode: str
    counterpart_nominal_bandwidth_mhz: float
    counterpart_resolution_mhz: float
    source_id: str


@dataclass(frozen=True)
class ProcessorMapping:
    counterpart: TpCounterpart | None
    reasons: tuple[str, ...] = ()


def map_tp_counterpart(c: Configuration) -> ProcessorMapping:
    """Map one supported configuration; preserve explicit applicability gaps."""
    if c.polarization == "FULL":
        return ProcessorMapping(None, ("FULL_POLARIZATION_TP_UNSUPPORTED",))
    bandwidth = c.bandwidth_mhz * (4 if c.quantization == "4X4" else 1)
    if bandwidth > 2000:
        return ProcessorMapping(None, ("TP_COUNTERPART_EXCEEDS_SUPPORTED_BASEBAND",))
    return ProcessorMapping(TpCounterpart(
        c.configuration_id, "USER_FACING_FPS_EQUIVALENCE", "ACA_SPECTROMETER",
        None, c.mode, bandwidth, c.resolution_mhz,
        f"proposers_guide{c.cycle}+handbook{c.cycle}",
    ))


def configuration_record(c: Configuration) -> dict:
    return asdict(c)
