"""Explicit request-frequency beam approximation; never a duplication verdict."""
import math
from numbers import Real

from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.domain.spatial import SpatialSelection, SpatialStatus, SkyPosition


def primary_beam_fwhm_deg(frequency_ghz: float, diameter_m: float) -> float:
    """Full width, not radius; fixed coefficient 1.13 and exact SI speed of light."""
    for value in (frequency_ghz, diameter_m):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
            raise ValueError("Frequency and diameter must be finite positive numbers")
    width = math.degrees(1.13 * 299792458. / 1e9 / frequency_ghz / diameter_m)
    if not math.isfinite(width) or not 0 < width <= 360:
        raise ValueError("Beam cannot be represented as a physical sky width")
    return width


def requested_beam_frequency(request):
    f = request.representative_frequency
    if f is None or f.kind != "SKY" or f.quantity.unit != "GHz":
        return None
    value = f.quantity.value
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
        return None
    return value


def evaluate_primary_beam(plan, evidence):
    """Use centers only; raw footprints neither supply nor veto formula coverage.

    Queue diameter must be supplied explicitly per context; use_7m is not a
    declaration of a unique array. The decision reference records a convention,
    not proof of scientific approval.
    """
    from alma_duplicate.spatial import _separation
    from alma_duplicate.search_plan import bind_archive_query
    from alma_duplicate.parsers.array_classification import classify_array_type

    reasons = []
    request = plan.validation.request
    frequency = requested_beam_frequency(request)
    diameter = None
    width = None
    separation = None
    source = plan.for_source(evidence.context.reference.source)
    if plan.beam_decision_ref is None or source is None or source.spatial_operation != "FORMULA_PRIMARY_BEAM":
        reasons.append("FORMULA_STRATEGY_NOT_SELECTED")
    if isinstance(evidence.context.evidence, ArchiveContextEvidence):
        if bind_archive_query(plan, evidence.source_record).status != "MATCHED":
            reasons.append("QUERY_NOT_BOUND_TO_PLAN")
        payload = evidence.context.evidence
        if payload.prepared.normalized_metadata.is_mosaic.value is not False:
            reasons.append("MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED")
        array = evidence.array_classification or classify_array_type(
            payload.prepared.raw_row.get("antenna_arrays"))
        diameter = array.interferometric_diameter_m
        if diameter is None:
            reasons.extend(("ARRAY_DIAMETER_UNRESOLVED", f"ARRAY_FAMILY_{array.family.value}"))
    else:
        if evidence.selection_status is not SpatialStatus.AVAILABLE:
            reasons.extend(evidence.reasons or ("QUEUE_GEOMETRY_OR_POSITION_UNAVAILABLE",))
        diameter = evidence.interpretation.antenna_diameter_m if evidence.interpretation else None
        if isinstance(diameter, bool) or diameter not in (7., 12.):
            diameter = None
            reasons.append("EXPLICIT_QUEUE_DIAMETER_REQUIRED")
    interpretation = evidence.interpretation
    if interpretation is None or interpretation.frame != "ICRS" or interpretation.target_kind != "FIXED":
        reasons.append("FIXED_TARGET_AND_ICRS_INTERPRETATION_REQUIRED")
    if evidence.center_status is not SpatialStatus.AVAILABLE or evidence.center is None:
        reasons.append("CENTER_UNAVAILABLE")
    else:
        separation = _separation(SkyPosition(request.position.ra_deg, request.position.dec_deg, "ICRS"), evidence.center)
        if (isinstance(evidence.context.evidence, ArchiveContextEvidence)
                    and separation > plan.retrieval_radius_deg + 1e-10):
            # Do not silently trust an inconsistent returned Archive row. Queue
            # unknown geometry outside the bounded scope remains auditable too.
            reasons.append("OUTSIDE_DOCUMENTED_CENTER_SCOPE")
    if frequency is None:
        reasons.append("REQUEST_SKY_REPRESENTATIVE_FREQUENCY_REQUIRED")
    elif diameter is not None:
        width = primary_beam_fwhm_deg(frequency, diameter)
    status = "NOT_EVALUATED"
    if not reasons:
        if abs(separation - width / 2) <= 1e-10:
            reasons.append("SPATIAL_BOUNDARY_TOLERANCE")
        else:
            status = "INSIDE" if separation < width / 2 else "OUTSIDE"
    return SpatialSelection(evidence.context.context_id, status, "FORMULA_PRIMARY_BEAM",
                            separation, width / 2 if width else None,
                            tuple(reasons) + ("REQUEST_FREQUENCY_CONVENTION_NOT_POLICY_VERDICT",),
                            method_version="primary_beam_2", beam_frequency_ghz=frequency,
                            antenna_diameter_m=diameter, beam_fwhm_deg=width,
                            decision_ref=plan.beam_decision_ref)
