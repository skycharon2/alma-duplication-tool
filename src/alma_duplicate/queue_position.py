"""Opt-in Queue candidate-beam convention, grounded in the captured portal sources.

The portal script is a reference implementation, not policy approval. In
particular its blank-frame convention is recorded, never labelled a measured
ICRS frame. Unknown arrays and ephemeris placeholders are not silently excluded.
"""
from dataclasses import replace
import math

from alma_duplicate.domain.queue import QueueMosaicKind, RegularSpwEvidence
from alma_duplicate.domain.spatial import PositionInterpretation, SkyPosition, SpatialSelection, SpatialStatus as S
from alma_duplicate.primary_beam import primary_beam_fwhm_deg
from alma_duplicate.spatial import adapt_spatial, _separation

PROFILE = "QUEUE_PORTAL_CANDIDATE_1"
SOURCE_REF = "docs/evidence/official_sources.md#queue-position-profile"


def candidate_frequency(row):
    """Positive Ref.Frequency; zero falls back to normalized sky-SPW weighted mean."""
    ref = row.spectral.sensitivity.reference_frequency_ghz
    if ref.canonical_unit != "GHz" or not math.isfinite(ref.value) or ref.value < 0:
        return None, "Ref.Frequency", ("CANDIDATE_REFERENCE_FREQUENCY_INVALID",)
    if ref.value > 0:
        return ref.value, "Ref.Frequency", ()
    if not isinstance(row.spectral, RegularSpwEvidence) or not row.spectral.spws:
        return None, "Ref.Frequency", ("CANDIDATE_FREQUENCY_FALLBACK_UNSUPPORTED",)
    spws = row.spectral.spws
    frequencies = [s.frequency_derivation.sky_frequency_ghz for s in spws]
    weights = [s.bandwidth_mhz.value for s in spws]
    if any(not math.isfinite(v) or v <= 0 for v in frequencies + weights):
        return None, "sky_spw_weighted_mean", ("CANDIDATE_FREQUENCY_FALLBACK_INVALID",)
    # Scaled weights avoid overflow; never use proposed SPWs or usable widths.
    scale = max(weights)
    weights = [w / scale for w in weights]
    value = math.fsum(f * w for f, w in zip(frequencies, weights)) / math.fsum(weights)
    return value, "sky_spw_weighted_mean", ("ZERO_REFERENCE_FREQUENCY_SKY_SPW_FALLBACK",)


def candidate_diameter(row):
    """Resolve only the array supported by actual row fields, not dictionary-only fields."""
    if row.request.use_tp:
        return None, "Use TP?", ("TP_GEOMETRY_UNSUPPORTED",)
    # The current strict 79-column schema has no operational standAlone_ACA.
    # Unlike the portal script we do not fill missing values with False.
    if not row.request.use_7m:
        return 12.0, "Use 7-m?=False;Use TP?=False", ("MAIN_ARRAY_FROM_NEGATIVE_AUXILIARY_FLAGS",)
    return None, "Use 7-m?=True;standAlone_ACA=ABSENT", ("QUEUE_ARRAY_COMBINATION_UNRESOLVED",)


def adapt_queue_position(context, source_record):
    row = context.evidence.row
    spatial = row.spatial
    ra, dec = spatial.ra_deg.value, spatial.dec_deg.value
    zero = ra == 0 and dec == 0
    frame_label = spatial.coordinate_system_raw.strip().lower()
    frame_supported = frame_label in ("", "icrs", "j2000", "galactic")
    diameter, _, array_reasons = candidate_diameter(row)
    interpretation = PositionInterpretation(
        context.context_id, "ICRS" if frame_supported else "UNKNOWN",
        "UNKNOWN" if zero else "FIXED", SOURCE_REF, diameter,
    )
    evidence = adapt_spatial(context, source_record, interpretation=interpretation)
    reasons = list(evidence.reasons) + list(array_reasons)
    reasons.append("PORTAL_EQUATORIAL_FRAME_CONVENTION_NOT_MEASURED_FRAME")
    if zero:
        return replace(evidence, selection_status=S.UNRESOLVED,
                       center_status=S.UNRESOLVED,
                       reasons=tuple(reasons) + ("POSSIBLE_EPHEMERIS_PLACEHOLDER_NAME_CHECK_REQUIRED",),
                       adapter_version=PROFILE)
    if not frame_supported:
        return replace(evidence, selection_status=S.UNRESOLVED,
                       reasons=tuple(reasons) + ("QUEUE_OFFSET_FRAME_UNSUPPORTED",),
                       adapter_version=PROFILE)
    # No upgrade of rectangle/custom or blank-with-offset geometry to single field.
    if spatial.mosaic_kind is not QueueMosaicKind.SINGLE_FIELD:
        return replace(evidence, reasons=tuple(reasons), adapter_version=PROFILE)
    dx, dy = spatial.long_offset_arcsec.value, spatial.lat_offset_arcsec.value
    if not all(math.isfinite(v) for v in (dx, dy)) or math.hypot(dx, dy) >= 90 * 3600:
        return replace(evidence, selection_status=S.INVALID,
                       reasons=tuple(reasons) + ("QUEUE_OFFSET_OUTSIDE_LOCAL_DOMAIN",), adapter_version=PROFILE)
    if abs(dx) > spatial.zero_tolerance_arcsec or abs(dy) > spatial.zero_tolerance_arcsec:
        from astropy.coordinates import SkyCoord
        from astropy import units as u
        center = SkyCoord(ra=ra*u.deg, dec=dec*u.deg, frame="icrs")
        native = center.galactic if frame_label == "galactic" else center
        # Tangent-plane arc offsets: east/north define position angle and length.
        # This is spherical transport, not naive addition of arcseconds to RA.
        center = native.directional_offset_by(math.atan2(dx, dy)*u.rad,
                                             math.hypot(dx, dy)*u.arcsec).icrs
        evidence = replace(evidence, center=SkyPosition(center.ra.deg, center.dec.deg, "ICRS"))
        reasons = [r for r in reasons if r != "NONZERO_OFFSETS_NOT_APPLIED"]
        reasons.append("TANGENT_OFFSETS_SPHERICAL_1")
        # Only lift the offset gate; TP/SPS and all other unsupported states remain.
        if not row.request.use_tp and isinstance(row.spectral, RegularSpwEvidence):
            evidence = replace(evidence, selection_status=S.AVAILABLE)
    return replace(evidence, reasons=tuple(reasons), adapter_version=PROFILE)


def evaluate_queue_candidate_beam(plan, evidence):
    """Directional candidate half-FWHM selection; unresolved evidence retains rows."""
    row = evidence.context.evidence.row
    frequency, frequency_field, frequency_notes = candidate_frequency(row)
    diameter, diameter_field, diameter_notes = candidate_diameter(row)
    blockers = []
    if evidence.selection_status is not S.AVAILABLE or evidence.center_status is not S.AVAILABLE:
        blockers.extend(evidence.reasons or ("QUEUE_POSITION_UNAVAILABLE",))
    if frequency is None:
        blockers.extend(frequency_notes)
    if diameter is None:
        blockers.extend(diameter_notes)
    request = plan.validation.request
    separation = None
    if evidence.center is not None and evidence.center_status is S.AVAILABLE:
        separation = _separation(SkyPosition(request.position.ra_deg, request.position.dec_deg, "ICRS"), evidence.center)
    else:
        blockers.append("CENTER_UNAVAILABLE")
    width = primary_beam_fwhm_deg(frequency, diameter) if frequency is not None and diameter is not None else None
    status = "NOT_EVALUATED"
    if not blockers:
        if abs(separation - width/2) <= 1e-10:
            blockers.append("SPATIAL_BOUNDARY_TOLERANCE")
        else:
            status = "INSIDE" if separation < width/2 else "OUTSIDE"
    return SpatialSelection(
        evidence.context.context_id, status, "QUEUE_CANDIDATE_PRIMARY_BEAM",
        separation, width/2 if width else None,
        tuple(dict.fromkeys(blockers + list(frequency_notes) + list(diameter_notes))) + ("CANDIDATE_BEAM_PROFILE_PROVISIONAL",),
        method_version=PROFILE, beam_frequency_ghz=frequency, antenna_diameter_m=diameter,
        beam_fwhm_deg=width, decision_ref=SOURCE_REF,
        beam_frequency_source=frequency_field, antenna_diameter_source=diameter_field,
    )
