"""Offline provisional Rectangle geometry. No coverage or scientific verdicts.

CSV spacing is explicitly interpreted as 12-m spacing by the batch adapter.
Scaling to 7-m assumes the same beam fraction, including for inferred ACA-only
rows; this is a model assumption, not an independently verified export fact.
"""
from collections import Counter
from dataclasses import asdict, dataclass
import math

from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.domain.queue import QueueMosaicKind
from alma_duplicate.queue_position import candidate_frequency
from alma_duplicate.queue_row_beam import PROFILE, resolve_queue_beam_interpretation

METHOD = "QUEUE_RECTANGLE_TRIANGULAR_GRID_1"
MODEL_APPROVAL = "PROJECT_ACCEPTED"
OT_REFERENCE = "OT_PARITY_A_B_C_D3"
OT_VALIDATED_DOMAIN = "ICRS_NYQUIST_REFERENCE_CASES"
MAX_POINTS = 10000


@dataclass(frozen=True)
class RectangleGeometry:
    ra_deg: float
    dec_deg: float
    longitude_offset_arcsec: float
    latitude_offset_arcsec: float
    length_arcsec: float
    width_arcsec: float
    pa_deg: float
    spacing_arcsec: float
    frame: str


def generate_rectangle_grid(geometry: RectangleGeometry, diameter_m: float, *,
                            spacing_reference_diameter_m: float,
                            max_points: int = MAX_POINTS):
    """Generate a complete bounded model grid, or no points with failure reasons.

    Spacing scaling is an explicit caller convention. Coordinates use successive
    spherical directional offsets: source to field centre, then rotated grid
    offsets about that centre. Nonzero-declination OT parity is unverified.
    """
    if not isinstance(geometry, RectangleGeometry):
        raise TypeError("RectangleGeometry required")
    if type(max_points) is not int or not 1 <= max_points <= MAX_POINTS:
        raise ValueError("max_points must be between 1 and 10000")
    result = dict(grid_method=METHOD, grid_model_status="UNRESOLVED",
                  geometry_status="UNRESOLVED", model_grid_complete=False,
                  scientific_candidate_complete=False,
                  diameter_m=diameter_m, coordinate_frame="ICRS",
                  coordinate_method="SUCCESSIVE_SPHERICAL_DIRECTIONAL_OFFSETS_1",
                  spacing_reference_diameter_m=spacing_reference_diameter_m,
                  spacing_derivation="CSV_SPACING_TIMES_REFERENCE_DIAMETER_OVER_ARRAY_DIAMETER",
                  spacing_arcsec=None, pointing_count=0, pointings=[], reasons=[])

    def fail(reason):
        result["reasons"] = [reason]
        return result

    values = [v for k, v in asdict(geometry).items() if k != "frame"]
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
           for v in values):
        return fail("INVALID_OR_MISSING_GEOMETRY")
    if geometry.frame.strip().lower() != "icrs":
        return fail("COORDINATE_FRAME_UNRESOLVED")
    if (isinstance(diameter_m, bool) or diameter_m not in (7., 12.) or
            isinstance(spacing_reference_diameter_m, bool) or
            spacing_reference_diameter_m not in (7., 12.)):
        return fail("SPACING_ARRAY_CONVENTION_UNRESOLVED")
    g = geometry
    if not 0 <= g.ra_deg < 360 or not -90 < g.dec_deg < 90:
        return fail("REFERENCE_COORDINATES_OUT_OF_DOMAIN")
    if g.ra_deg == 0 and g.dec_deg == 0:
        return fail("POSSIBLE_EPHEMERIS_PLACEHOLDER")
    if min(g.length_arcsec, g.width_arcsec, g.spacing_arcsec) <= 0:
        return fail("NONPOSITIVE_SIZE_OR_SPACING")
    if math.hypot(g.length_arcsec, g.width_arcsec)/2 + math.hypot(
            g.longitude_offset_arcsec, g.latitude_offset_arcsec) >= 90*3600:
        return fail("GEOMETRY_OUTSIDE_LOCAL_HEMISPHERE")
    s = g.spacing_arcsec * (spacing_reference_diameter_m / diameter_m)
    h = math.sqrt(3)/2*s
    result["spacing_arcsec"] = s
    ratio = g.width_arcsec/h if h > 0 else math.inf
    if not math.isfinite(ratio) or ratio >= 2*max_points:
        return fail("POINTING_LIMIT_EXCEEDED")
    n = math.floor(ratio)+1
    rows = []
    total = 0
    for j in range(n):
        phase = .5*((n-1-j) % 2)
        extent = g.length_arcsec/(2*s)
        if not math.isfinite(extent) or extent > max_points:
            return fail("POINTING_LIMIT_EXCEEDED")
        lo, hi = math.ceil(-extent-phase), math.floor(extent-phase)
        total += max(0, hi-lo+1)
        if total > max_points:
            return fail("POINTING_LIMIT_EXCEEDED")
        rows.append((j, phase, lo, hi))
    if not total:
        return fail("EMPTY_MODEL_GRID")
    center = SkyCoord(g.ra_deg*u.deg, g.dec_deg*u.deg, frame="icrs")
    def offset(origin, east, north):
        return origin.directional_offset_by(math.atan2(east, north)*u.rad,
                                            math.hypot(east, north)*u.arcsec)
    center = offset(center, g.longitude_offset_arcsec, g.latitude_offset_arcsec)
    angle = math.radians(g.pa_deg % 360)
    points = []
    for j, phase, lo, hi in rows:
        q = (j-(n-1)/2)*h
        for i in range(lo, hi+1):
            p = (i+phase)*s
            east = p*math.cos(angle)+q*math.sin(angle)
            north = -p*math.sin(angle)+q*math.cos(angle)
            sky = offset(center, east, north)
            points.append(dict(id=f"r{j}:c{i}", ra_deg=float(sky.ra.deg),
                               dec_deg=float(sky.dec.deg), frame="ICRS",
                               east_arcsec=east, north_arcsec=north))
    result.update(geometry_status="GEOMETRY_RECONSTRUCTED",
                  grid_model_status=MODEL_APPROVAL,
                  ot_reference=OT_REFERENCE,
                  validation_scope="MODEL_VALIDATED_ON_REFERENCE_CASES_NOT_INDIVIDUAL_ROW",
                  pointing_count=len(points),
                  pointings=points, center_icrs_deg=[float(center.ra.deg), float(center.dec.deg)],
                  model_grid_complete=True)
    return result


def spacing_diagnostic(spacing_arcsec, reference_frequency_ghz):
    """Snapshot diagnostic only; never replace spacing or authorize array ownership.

    Uses the original Ref.Frequency, not a frequency fallback or Doppler rewrite.
    Relative tolerance 1e-10 admits export roundoff, not arbitrary spacing changes.
    """
    result = dict(status="UNAVAILABLE", frequency_basis="CSV_REF_FREQUENCY_UNCONVERTED",
                  reference_diameter_m=12., expected_nyquist_arcsec=None, ratio=None,
                  relative_tolerance=1e-10, blocking=False)
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or
           not math.isfinite(v) or v <= 0 for v in (spacing_arcsec, reference_frequency_ghz)):
        return result
    expected = (299792458. / math.sqrt(3) / reference_frequency_ghz / 1e9 / 12 *
                (180*3600/math.pi))
    if not math.isfinite(expected) or expected <= 0:
        return result
    ratio = spacing_arcsec/expected
    if not math.isfinite(ratio):
        return result
    result.update(expected_nyquist_arcsec=expected, ratio=ratio,
                  status="CONSISTENT_WITH_12M_NYQUIST" if abs(ratio-1) <= 1e-10 else
                  "NONDEFAULT_SPACING_REFERENCE_REVIEW")
    return result


def reconstruct_queue_rectangles(parsed):
    """Dry-run all Rectangle source rows; preserve repeats and spectral identity."""
    if not parsed.can_reconstruct:
        raise ValueError("Complete parsed snapshot required")
    candidates = []
    for row in parsed.row_inputs:
        if row.raw_row.row_id.snapshot_sha256 != parsed.snapshot.snapshot_sha256:
            raise ValueError("Row snapshot mismatch")
        if row.spatial.mosaic_kind is not QueueMosaicKind.RECTANGULAR_MOSAIC:
            continue
        s = row.spatial
        def value(q):
            return None if q is None else q.value
        geometry = RectangleGeometry(value(s.ra_deg), value(s.dec_deg),
            value(s.long_offset_arcsec), value(s.lat_offset_arcsec),
            value(s.mosaic_length_arcsec), value(s.mosaic_width_arcsec),
            value(s.mosaic_pa_deg), value(s.mosaic_spacing_arcsec), s.coordinate_system_raw)
        beam = resolve_queue_beam_interpretation(row)
        frequency, evidence, reasons = candidate_frequency(row)
        arrays = [generate_rectangle_grid(geometry, d, spacing_reference_diameter_m=12.)
                  for d in beam.diameters_m]
        diagnostic = spacing_diagnostic(geometry.spacing_arcsec,
            row.spectral.sensitivity.reference_frequency_ghz.value)
        # The model is accepted as an algorithm; OT parity was established on
        # controlled Nyquist ICRS cases, not each arbitrary CSV row.
        for array in arrays:
            array['ot_validation_scope'] = (
                OT_VALIDATED_DOMAIN if array['geometry_status'] == 'GEOMETRY_RECONSTRUCTED'
                and diagnostic['status'] == 'CONSISTENT_WITH_12M_NYQUIST'
                else 'OUTSIDE_OT_REFERENCE_DOMAIN')
        candidates.append(dict(geometry_kind="RECTANGLE", source_row_id=row.raw_row.row_id.value,
            source_content_fingerprint=row.raw_row.content_fingerprint,
            group=asdict(row.group_key), input_geometry=asdict(geometry),
            array_inference=dict(profile=PROFILE, status="ARRAY_INFERRED", **asdict(beam)),
            frequency=dict(value_ghz=frequency, evidence=evidence, reasons=reasons,
                           role="EXISTING_CANDIDATE_FREQUENCY_POLICY_NOT_USED_FOR_GRID_SPACING"),
            spacing_convention="ASSUMED_CSV_12M_SAME_BEAM_FRACTION",
            spacing_diagnostic=diagnostic,
            scientific_candidate_complete=False, arrays=arrays,
            reasons=[] if arrays else ["ARRAY_INFERENCE_UNRESOLVED"]))
    counts = Counter(a["geometry_status"] for c in candidates for a in c["arrays"])
    return dict(schema_version="queue_rectangle_geometry_1", grid_method=METHOD,
        grid_model_status=MODEL_APPROVAL, ot_reference=OT_REFERENCE,
        validation_domain=OT_VALIDATED_DOMAIN, snapshot_sha256=parsed.snapshot.snapshot_sha256,
        source_url=parsed.snapshot.source_url, parser_version=parsed.snapshot.parser_version,
        candidates=candidates, summary=dict(rectangle_rows=len(candidates),
            reconstructed_rows=sum(bool(c["arrays"]) and all(a["geometry_status"] ==
                "GEOMETRY_RECONSTRUCTED" for a in c["arrays"]) for c in candidates),
            array_statuses=dict(counts)), scientific_status="NOT_EVALUATED")
