"""Conservative spatial adaptation and local candidate geometry checks.

Only explicit ICRS circles or explicitly interpreted fixed Queue points are
supported. This module implements no primary-beam or duplication criterion.
"""
from __future__ import annotations

import math
from decimal import Decimal, DecimalException, localcontext
from numbers import Real

from alma_duplicate.clients.archive_contract import ArchiveQueryResult
from alma_duplicate.domain.comparison import ArchiveContextEvidence, ComparisonContext, QueueContextEvidence
from alma_duplicate.domain.queue import QueueCsvParseResult, QueueMosaicKind, SpectralScanEvidence
from alma_duplicate.domain.search import SearchPlan
from alma_duplicate.parsers.array_classification import classify_array_type
from alma_duplicate.domain.spatial import (
    CircleFootprint, PositionInterpretation, SkyPosition, SpatialEvidence,
    SpatialSelection, SpatialStatus as S,
)
from alma_duplicate.search_plan import bind_archive_query


def _text(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8").strip()
        except UnicodeDecodeError:
            return ""
    return value.strip() if isinstance(value, str) else ""


def _coordinate(value, unit, *, ra):
    # Deliberately narrow scalar/unit support; original values remain in context.
    if isinstance(value, bool) or not isinstance(value, (Real, str, Decimal)):
        raise ValueError("Unsupported coordinate scalar")
    factors = {"deg": 1.0, "arcsec": 1 / 3600, "rad": 180 / math.pi}
    if unit not in factors:
        raise ValueError("Unsupported coordinate unit")
    original = Decimal(str(value).strip())
    with localcontext() as decimal_context:
        decimal_context.prec = max(60, len(original.as_tuple().digits) + 30)
        exact = original if unit == "deg" else original * Decimal(str(factors[unit]))
    converted = float(value) * factors[unit]
    if (not exact.is_finite() or not math.isfinite(converted)
            or (converted == 0 and exact != 0)):
        raise ValueError("Invalid or underflowing coordinate")
    if ra:
        valid = 0 <= exact < 360 and 0 <= converted < 360
    else:
        valid = -90 <= exact <= 90 and -90 <= converted <= 90
    if not valid:
        raise ValueError("Coordinate outside canonical range")
    return converted


def _archive_center(row, fields, frame):
    values = []
    for name in ("s_ra", "s_dec"):
        value = row.get(name)
        if value is None:
            return None, S.MISSING, ("COORDINATE_MISSING",)
        descriptors = [f for f in fields if f.name == name]
        if len(descriptors) != 1:
            return None, S.UNRESOLVED, ("COORDINATE_METADATA_MISSING_OR_AMBIGUOUS",)
        descriptor = descriptors[0]
        if descriptor.datatype not in {"double", "float", "int", "long", "short"}:
            return None, S.UNSUPPORTED, ("COORDINATE_DATATYPE_UNSUPPORTED",)
        if descriptor.unit not in {"deg", "rad", "arcsec"}:
            return None, S.UNRESOLVED, ("COORDINATE_UNIT_UNVERIFIED",)
        try:
            values.append(_coordinate(value, descriptor.unit, ra=name == "s_ra"))
        except (ValueError, OverflowError, DecimalException):
            return None, S.INVALID, ("COORDINATE_INVALID",)
    position = SkyPosition(*values, frame)
    return position, S.AVAILABLE if frame == "ICRS" else S.UNRESOLVED, (
        () if frame == "ICRS" else ("CENTER_FRAME_UNSPECIFIED",)
    )


def _circle(value):
    """Parse the limited ``CIRCLE ICRS ra dec radius`` form.

    Keyword comparison is case-insensitive: the live ALMA TAP service emits
    ``Circle ICRS ...`` (verified 2026-09-11), while older synthetic fixtures use
    upper case. Only the keywords are normalized; the raw text is never rewritten.
    """
    text = _text(value)
    if not text:
        return None, S.MISSING, ("REGION_MISSING",)
    tokens = text.split()
    if (len(tokens) != 5 or tokens[0].upper() != "CIRCLE"
            or tokens[1].upper() != "ICRS"):
        return None, S.UNSUPPORTED, ("REGION_REPRESENTATION_UNSUPPORTED",)
    try:
        ra = _coordinate(tokens[2], "deg", ra=True)
        dec = _coordinate(tokens[3], "deg", ra=False)
        radius = float(tokens[4])
        exact_radius = Decimal(tokens[4])
        if (not exact_radius.is_finite() or not math.isfinite(radius)
                or not 0 < exact_radius <= 180 or not 0 < radius <= 180):
            raise ValueError("Invalid circle radius")
    except (ValueError, OverflowError, DecimalException):
        return None, S.INVALID, ("REGION_INVALID",)
    return CircleFootprint(SkyPosition(ra, dec, "ICRS"), radius), S.AVAILABLE, ()


def _separation(a: SkyPosition, b: SkyPosition) -> float:
    """Great-circle angle via atan2 of cross-product norm and dot product."""
    ra1, dec1, ra2, dec2 = map(math.radians, (a.ra_deg, a.dec_deg, b.ra_deg, b.dec_deg))
    delta = ra2 - ra1
    x = math.cos(dec2) * math.sin(delta)
    y = math.cos(dec1) * math.sin(dec2) - math.sin(dec1) * math.cos(dec2) * math.cos(delta)
    dot = math.sin(dec1) * math.sin(dec2) + math.cos(dec1) * math.cos(dec2) * math.cos(delta)
    return math.degrees(math.atan2(math.hypot(x, y), dot))


def adapt_spatial(
    context: ComparisonContext,
    source_record: ArchiveQueryResult | QueueCsvParseResult,
    *,
    interpretation: PositionInterpretation | None = None,
) -> SpatialEvidence:
    """Preserve source geometry; unresolved inputs never become single pointings."""
    if interpretation and interpretation.context_id != context.context_id:
        raise ValueError("Spatial interpretation belongs to another context")
    frame = interpretation.frame if interpretation else "UNKNOWN"
    payload = context.evidence
    if isinstance(payload, ArchiveContextEvidence):
        if (not isinstance(source_record, ArchiveQueryResult)
                or not source_record.can_reconstruct
                or context.reference.source_record_id != source_record.provenance.query_run_id
                or payload.prepared.raw_row is not source_record.rows[payload.prepared.result_index]):
            raise ValueError("Archive spatial evidence belongs to another source result")
        row = payload.prepared.raw_row
        center, center_status, reasons = _archive_center(row, source_record.field_metadata, frame)
        circle, footprint_status, footprint_reasons = _circle(row.get("s_region"))
        reasons += footprint_reasons
        mosaic = payload.prepared.normalized_metadata.is_mosaic.value
        array = classify_array_type(row.get("antenna_arrays"))
        geometry = "SINGLE_FIELD" if mosaic is False else ("MOSAIC" if mosaic is True else "UNKNOWN")
        if circle and center and center.frame == "ICRS" and _separation(center, circle.center) > 1e-9:
            reasons += ("CENTER_AND_REGION_CENTER_DIFFER",)
        # Circle footprint and raw center are separate evidence. Neither overwrites the other.
        if mosaic is not False:
            status = S.UNSUPPORTED
            reasons += ("MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED",)
        elif array.interferometric_diameter_m is None:
            # Total Power, mixed, missing and unrecognized arrays stay unsupported.
            status = S.UNSUPPORTED
            reasons += ("TP_OR_UNRECOGNIZED_ARRAY_UNSUPPORTED", f"ARRAY_FAMILY_{array.family.value}")
        else:
            status = footprint_status
        return SpatialEvidence(context, source_record, center, center_status, circle,
                               footprint_status, geometry, status, reasons, interpretation,
                               array_classification=array)
    if not isinstance(payload, QueueContextEvidence) or not isinstance(source_record, QueueCsvParseResult):
        raise TypeError("Unsupported spatial source")
    row = payload.row
    if (not source_record.can_reconstruct
            or context.reference.source_record_id != source_record.snapshot.snapshot_sha256
            or row.raw_row not in source_record.raw_rows
            or not any(row is item for item in source_record.row_inputs)
            or context.reference.parser_version != source_record.snapshot.parser_version):
        raise ValueError("Queue spatial evidence belongs to another source result")
    spatial = row.spatial
    reasons = []
    try:
        center = SkyPosition(
            _coordinate(spatial.ra_deg.raw_text, spatial.ra_deg.canonical_unit, ra=True),
            _coordinate(spatial.dec_deg.raw_text, spatial.dec_deg.canonical_unit, ra=False),
            frame,
        )
        center_status = S.AVAILABLE if frame == "ICRS" else S.UNRESOLVED
    except (ValueError, OverflowError, DecimalException):
        center, center_status = None, S.INVALID
        reasons.append("COORDINATE_INVALID")
    status = center_status
    if interpretation is None or frame != "ICRS" or interpretation.target_kind != "FIXED":
        status = S.UNRESOLVED
        reasons.append("FIXED_TARGET_AND_ICRS_INTERPRETATION_REQUIRED")
    if center_status is S.INVALID:
        status = S.INVALID
    if spatial.mosaic_kind is not QueueMosaicKind.SINGLE_FIELD:
        status = S.UNSUPPORTED
        reasons.append("QUEUE_GEOMETRY_UNSUPPORTED")
    offsets = (spatial.long_offset_arcsec.value, spatial.lat_offset_arcsec.value)
    if any(abs(v) > spatial.zero_tolerance_arcsec for v in offsets):
        status = S.UNSUPPORTED
        reasons.append("NONZERO_OFFSETS_NOT_APPLIED")
    elif any(v != 0 for v in offsets):
        reasons.append("OFFSETS_WITHIN_SOURCE_ZERO_TOLERANCE")
    if row.request.use_tp:
        status = S.UNSUPPORTED
        reasons.append("TP_GEOMETRY_UNSUPPORTED")
    if isinstance(row.spectral, SpectralScanEvidence):
        status = S.UNSUPPORTED
        reasons.append("SPS_SELECTION_UNSUPPORTED")
    return SpatialEvidence(context, source_record, center, center_status, None, S.MISSING,
                           spatial.mosaic_kind.value, status, tuple(reasons), interpretation)


def evaluate_spatial(plan: SearchPlan, evidence: SpatialEvidence) -> SpatialSelection:
    """Evaluate only the planned spatial predicate, never a full search/criterion."""
    if plan.beam_decision_ref is not None:
        from alma_duplicate.primary_beam import evaluate_primary_beam
        return evaluate_primary_beam(plan, evidence)
    source = plan.for_source(evidence.context.reference.source)
    operation = source.spatial_operation if source else "NOT_SELECTED"
    reasons = list(evidence.reasons)
    if source is None:
        reasons.append("SOURCE_NOT_SELECTED")
    elif isinstance(evidence.source_record, ArchiveQueryResult):
        binding = bind_archive_query(plan, evidence.source_record)
        if binding.status != "MATCHED":
            reasons.extend(("QUERY_NOT_BOUND_TO_PLAN", *binding.reasons))
            source = None
    if source is None or evidence.selection_status is not S.AVAILABLE:
        return SpatialSelection(evidence.context.context_id, "NOT_EVALUATED", operation,
                                None, None, tuple(reasons))
    request = plan.validation.request
    options = plan.validation.search_options
    assert request is not None and request.position is not None and options is not None and options.radius is not None
    target = SkyPosition(request.position.ra_deg, request.position.dec_deg, "ICRS")
    threshold = options.radius.value
    if operation == "ARCHIVE_REGION_INTERSECTION":
        assert evidence.footprint is not None
        position = evidence.footprint.center
        threshold = min(180.0, threshold + evidence.footprint.radius_deg)
    else:
        assert evidence.center is not None
        position = evidence.center
    separation = _separation(target, position)
    # Numerical boundary band is unresolved, never a false definite exclusion.
    if abs(separation - threshold) <= 1e-10:
        return SpatialSelection(evidence.context.context_id, "NOT_EVALUATED", operation,
                                separation, threshold, tuple(reasons) + ("SPATIAL_BOUNDARY_TOLERANCE",))
    return SpatialSelection(evidence.context.context_id,
                            "INSIDE" if separation < threshold else "OUTSIDE",
                            operation, separation, threshold, tuple(reasons))
