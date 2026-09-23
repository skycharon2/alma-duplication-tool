"""Geometry-independent mode evidence bound to typed Queue row/SPW inputs."""

from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction
from enum import StrEnum
from functools import lru_cache
import math

from alma_duplicate.queue_mode import ABS_TOL_MHZ, REL_TOL, _positive, project_cycle
from alma_duplicate.domain.queue import (
    QueueRowInput,
    RegularSpwEvidence,
    QueueMosaicKind,
)
from alma_duplicate.queue_processor_mode import (
    configurations,
    evaluate as processor_evaluate,
)

METHOD_VERSION = "queue_mode_evidence_adapter_2"
DECISION_REF = "docs/evidence/queue_mode_evidence_decision_2026-09-23.md#accepted-scope"
# Reviewed occurrence combinations, not an extrapolation to all cycles/polarizations.
N16_SCOPE = {(11, "FULL"), (12, "DOUBLE"), (12, "FULL")}
COMPATIBILITY_RELATIVE_BOUND = Fraction(1, 16000)


def _close(a, b):
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL_MHZ)


class ProcessorScope(StrEnum):
    INTERFEROMETRIC = "INTERFEROMETRIC"
    REQUESTED_TP_EQUIVALENCE = "REQUESTED_TP_EQUIVALENCE"
    UNRESOLVED = "UNRESOLVED"


def requested_processor_scope(use_tp):
    if use_tp is False:
        return ProcessorScope.INTERFEROMETRIC
    if use_tp is True:
        return ProcessorScope.REQUESTED_TP_EQUIVALENCE
    return ProcessorScope.UNRESOLVED


def derive_mode(cycle, polarization, bandwidth_mhz, resolution_mhz, *, processor_scope):
    """Exact reference priority, then a gated classification-only N16 bound.

    Raw numerical inputs are never replaced. Mode consensus does not establish
    a unique processor, complete catalog, or a duplication branch result.
    """
    result = {
        "method_version": METHOD_VERSION,
        "decision_ref": DECISION_REF,
        "method_status": "PROJECT_ACCEPTED_LIMITED_SCOPE",
        "evidence_origin": "DERIVED",
        "mode": "UNKNOWN",
        "match_path": "NONE",
        "reason": None,
        "enumeration_complete": False,
        "processor_identification": "NOT_RECOVERED",
        "processor_scope": str(processor_scope),
        "processor_evidence": "CONDITIONAL_REFERENCE_CONFIGURATION_SPACE",
        "processor_mappings": [],
        "export_provenance": "UNRESOLVED",
        "input": {
            "cycle": cycle,
            "polarization": polarization,
            "bandwidth_mhz": bandwidth_mhz,
            "resolution_mhz": resolution_mhz,
        },
        "compatible_modes": [],
        "matched_configurations": [],
        "classification_relative_bound": None,
    }
    if type(cycle) is not int or cycle not in (11, 12, 13):
        result["reason"] = "UNSUPPORTED_CYCLE"
    elif polarization not in ("SINGLE", "DOUBLE", "FULL"):
        result["reason"] = "UNSUPPORTED_POLARIZATION"
    elif processor_scope not in (
        ProcessorScope.INTERFEROMETRIC,
        ProcessorScope.REQUESTED_TP_EQUIVALENCE,
    ):
        result["reason"] = "PROCESSOR_APPLICABILITY_UNRESOLVED"
    elif (
        processor_scope == ProcessorScope.REQUESTED_TP_EQUIVALENCE
        and polarization == "FULL"
    ):
        result["reason"] = "FULL_POLARIZATION_TP_UNSUPPORTED"
    elif not _positive(bandwidth_mhz) or not _positive(resolution_mhz):
        result["reason"] = "INVALID_OR_MISSING_NUMERICAL_EVIDENCE"
    if result["reason"]:
        return result
    rows = [
        c
        for c in configurations(cycle)
        if not c.export_compatibility
        and c.cycle == cycle
        and c.polarization == polarization
        and _close(c.bandwidth_mhz, bandwidth_mhz)
    ]
    matches = [c for c in rows if _close(c.resolution_mhz, resolution_mhz)]
    if matches:
        result["match_path"] = "EXACT_REFERENCE"
    else:
        observed = Fraction(str(resolution_mhz))
        # Gate the observed signature before applying any numerical allowance.
        anchors = [
            c
            for c in rows
            if c.mode == "FDM"
            and c.weighting == "HANNING"
            and c.averaging == 16
            and c.response_factor == 16
            and c.quantization == "2X2"
            and c.resource_divisor == 1
        ]
        inside = any(
            Fraction(str(c.resolution_mhz)) * (1 - COMPATIBILITY_RELATIVE_BOUND)
            <= observed
            <= Fraction(str(c.resolution_mhz))
            or _close(
                float(
                    Fraction(str(c.resolution_mhz)) * (1 - COMPATIBILITY_RELATIVE_BOUND)
                ),
                resolution_mhz,
            )
            for c in anchors
        )
        if (
            (cycle, polarization) not in N16_SCOPE
            or not _close(bandwidth_mhz, 1875.0)
            or not inside
        ):
            result["reason"] = (
                "OUTSIDE_N16_COMPATIBILITY_SCOPE" if rows else "NO_SUPPORTED_BANDWIDTH"
            )
            return result
        # Apply the same bound to EVERY mode/profile in the fixed comparison space.
        # A competing TDM interpretation must not disappear behind an FDM-only filter.
        for c in rows:
            prediction = Fraction(str(c.resolution_mhz))
            error = abs(observed - prediction) / prediction
            if (
                error <= COMPATIBILITY_RELATIVE_BOUND
                or _close(
                    resolution_mhz,
                    float(prediction * (1 - COMPATIBILITY_RELATIVE_BOUND)),
                )
                or _close(
                    resolution_mhz,
                    float(prediction * (1 + COMPATIBILITY_RELATIVE_BOUND)),
                )
            ):
                matches.append(c)
        result["match_path"] = "N16_SCOPED_COMPATIBILITY"
        result["classification_relative_bound"] = str(COMPATIBILITY_RELATIVE_BOUND)
    modes = sorted({c.mode for c in matches})
    result["compatible_modes"] = modes
    result["matched_configurations"] = [asdict(c) for c in matches]
    result["mode"] = (
        modes[0] if len(modes) == 1 and modes[0] in ("FDM", "TDM") else "UNKNOWN"
    )
    result["reason"] = (
        "SINGLE_MODE_CONSENSUS"
        if result["mode"] != "UNKNOWN"
        else "COMPETING_MODES"
        if matches
        else "NO_SUPPORTED_MATCH"
    )
    if processor_scope == ProcessorScope.REQUESTED_TP_EQUIVALENCE and matches:
        result["processor_evidence"] = "CONDITIONAL_EQUIVALENCE_MAPPING"
        mappings = []
        for c in matches:
            # Reuse existing equivalence at the configuration prediction. This
            # is a mapping probe, never replacement of the observed resolution.
            view = _mapping_probe(
                c.cycle, c.polarization, c.bandwidth_mhz, c.resolution_mhz
            )
            bound = [
                m
                for m in view["tps_mappings"]
                if m["blc_configuration_id"] == c.configuration_id
            ]
            if not bound:
                result["mode"] = "UNKNOWN"
                result["reason"] = "PROCESSOR_MAPPING_INCOMPLETE"
            mappings.extend(bound)
        result["processor_mappings"] = mappings
    return result


@lru_cache(maxsize=4096)
def _mapping_probe(cycle, polarization, bandwidth, resolution):
    return processor_evaluate(
        cycle, polarization, bandwidth, resolution, require_tp=True
    )


def single_point_applicability(geometry, use_tp):
    """Geometry/array gate only; never a declaration of full rule readiness."""
    if geometry in (QueueMosaicKind.UNKNOWN, QueueMosaicKind.UNSPECIFIED_WITH_OFFSET):
        return {
            "status": "INDETERMINATE",
            "reason": "GEOMETRY_UNRESOLVED",
            "scope": "GEOMETRY_AND_ARRAY_ONLY",
        }
    if geometry != QueueMosaicKind.SINGLE_FIELD:
        return {
            "status": "UNSUPPORTED",
            "reason": "NON_SINGLE_FIELD_OUTSIDE_CURRENT_SCOPE",
            "scope": "GEOMETRY_AND_ARRAY_ONLY",
        }
    if use_tp is True:
        return {
            "status": "UNSUPPORTED",
            "reason": "TP_RULES_OUTSIDE_CURRENT_SCOPE",
            "scope": "GEOMETRY_AND_ARRAY_ONLY",
        }
    if use_tp is not False:
        return {
            "status": "INDETERMINATE",
            "reason": "ARRAY_REQUIREMENT_UNRESOLVED",
            "scope": "GEOMETRY_AND_ARRAY_ONLY",
        }
    return {
        "status": "SUPPORTED",
        "reason": "SINGLE_FIELD_INTERFEROMETRIC_SCOPE",
        "scope": "GEOMETRY_AND_ARRAY_ONLY",
    }


def classify_spw(row: QueueRowInput, spw_number: int):
    """Resolve a slot inside its owning typed row; never accept a detached SPW."""
    if not isinstance(row.spectral, RegularSpwEvidence):
        raise ValueError("SPECTRAL_SCAN_NOT_EXPANDED")
    matches = [spw for spw in row.spectral.spws if spw.number == spw_number]
    if len(matches) != 1:
        raise ValueError("SPW_SLOT_NOT_UNIQUELY_BOUND_TO_ROW")
    spw = matches[0]
    return {
        "source": {
            "snapshot_sha256": row.raw_row.row_id.snapshot_sha256,
            "source_row_id": row.raw_row.row_id.value,
            "physical_start_line": row.raw_row.row_id.physical_start_line,
            "source_ordinal": row.raw_row.source_ordinal,
            "project_code": row.group_key.project_code,
            "target_name": row.group_key.target_name,
            "spw_number": spw.number,
            "geometry": row.spatial.mosaic_kind.value,
            "use_7m": row.request.use_7m,
            "use_tp": row.request.use_tp,
            "bandwidth_raw_mhz": spw.bandwidth_mhz.raw_text,
            "resolution_raw_mhz": spw.spectral_resolution_mhz.raw_text,
            "bandwidth_mhz": spw.bandwidth_mhz.value,
            "resolution_mhz": spw.spectral_resolution_mhz.value,
        },
        "mode_evidence": derive_mode(
            project_cycle(row.group_key.project_code),
            row.request.polarization_raw,
            spw.bandwidth_mhz.value,
            spw.spectral_resolution_mhz.value,
            processor_scope=requested_processor_scope(row.request.use_tp),
        ),
        "single_point_applicability": single_point_applicability(
            row.spatial.mosaic_kind, row.request.use_tp
        ),
    }
