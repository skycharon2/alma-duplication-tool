"""Offline Queue Mosaic reconstruction evidence, not a duplication evaluator.

Custom groups are strict same-snapshot export-equivalence hypotheses, not SGs.
Rectangle rows remain independent, including identical repeated records.
Array inference is reused; inferred diameters do not establish pointing ownership.
"""

from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
import math

from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.domain.queue import QueueMosaicKind as Kind
from alma_duplicate.queue_reconstruction import reconstruct_queue_rows
from alma_duplicate.queue_row_beam import PROFILE, resolve_queue_beam_interpretation

SCHEMA = "queue_mosaic_reconstruction_1"
GROUPING_METHOD = "strict_export_fields_except_offsets_and_display_coordinates_1"
OFFSET_METHOD = "TANGENT_OFFSETS_SPHERICAL_1"
_CUSTOM_VARIABLES = {"Long Offset", "Lat Offset", "RA_HMS", "Dec_DMS"}


def _identity(payload):
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return "queue-mosaic:" + sha256(encoded.encode()).hexdigest()


def _center(row):
    """Diagnostic projection using the existing local spherical-offset convention.

    Galactic export reference-frame ambiguity is deliberately not guessed.
    No result here grants scientific coverage or array ownership.
    """
    s = row.spatial
    frame = s.coordinate_system_raw.strip().lower()
    result = dict(status="UNRESOLVED", icrs_deg=None, method=OFFSET_METHOD,
                  reference_frame="UNRESOLVED", offset_frame="UNRESOLVED",
                  source_frame_raw=s.coordinate_system_raw, reasons=[])
    if frame not in ("", "icrs"):
        result["reasons"] = ["GALACTIC_REFERENCE_FRAME_UNVERIFIED" if frame == "galactic"
                             else "OFFSET_FRAME_UNSUPPORTED"]
        return result
    ra, dec = s.ra_deg.value, s.dec_deg.value
    x, y = s.long_offset_arcsec.value, s.lat_offset_arcsec.value
    if (not all(math.isfinite(v) for v in (ra, dec, x, y))
            or not 0 <= ra < 360 or not -90 <= dec <= 90
            or math.hypot(x, y) >= 90 * 3600):
        result["reasons"] = ["COORDINATES_OUTSIDE_LOCAL_DOMAIN"]
        return result
    if ra == 0 and dec == 0:
        result["reasons"] = ["POSSIBLE_EPHEMERIS_PLACEHOLDER"]
        return result
    origin = SkyCoord(ra=ra*u.deg, dec=dec*u.deg, frame="icrs")
    # Match the existing adapter's zero tolerance without altering source values.
    if abs(x) > s.zero_tolerance_arcsec or abs(y) > s.zero_tolerance_arcsec:
        origin = origin.directional_offset_by(math.atan2(x, y)*u.rad,
                                             math.hypot(x, y)*u.arcsec)
    result.update(status="DIAGNOSTIC_ONLY", icrs_deg=[origin.ra.deg, origin.dec.deg],
                  reference_frame="ICRS", offset_frame="ICRS",
                  zero_tolerance_arcsec=s.zero_tolerance_arcsec,
                  reasons=["OT_OFFSET_PARITY_NOT_VERIFIED"] +
                  (["BLANK_FRAME_EQUATORIAL_CONVENTION"] if not frame else []))
    return result


def reconstruct_queue_mosaics(parsed):
    """Return deterministic JSON-ready evidence from a complete parsed snapshot.

    No network, active snapshot mutation, prefilter, grid inference or verdict.
    Full raw columns/values and parser issues accompany every observed association.
    """
    if not parsed.can_reconstruct:
        raise ValueError("Complete Queue parsing is required for Mosaic reconstruction")
    snapshot = parsed.snapshot.snapshot_sha256
    if any(row.raw_row.row_id.snapshot_sha256 != snapshot for row in parsed.row_inputs):
        raise ValueError("Queue rows must belong to the parsed snapshot")
    reconstruction = reconstruct_queue_rows(parsed.row_inputs)
    associations = {a.raw_row_id: a for a in reconstruction.associations}
    groups = defaultdict(list)
    excluded = []
    for row in parsed.row_inputs:
        raw = row.raw_row
        kind = row.spatial.mosaic_kind
        if kind is Kind.CUSTOM_POINTING:
            # Include unknown operational columns and standalone evidence as well.
            fields = [(k, v) for k, v in zip(raw.declared_columns, raw.raw_values)
                      if k not in _CUSTOM_VARIABLES]
            key = _identity([SCHEMA, snapshot, GROUPING_METHOD, fields])
        elif kind is Kind.RECTANGULAR_MOSAIC:
            key = _identity([SCHEMA, snapshot, "RECTANGLE_SOURCE_ROW", raw.row_id.value])
        else:
            excluded.append(dict(source_row_id=raw.row_id.value, kind=kind.value,
                                 reason="OUTSIDE_MOSAIC_RECONSTRUCTION_SCOPE"))
            continue
        groups[key].append(row)

    candidates = []
    for key, rows in sorted(groups.items()):
        rows.sort(key=lambda r: r.raw_row.row_id.physical_start_line)
        first = rows[0]
        custom = first.spatial.mosaic_kind is Kind.CUSTOM_POINTING
        records = []
        for row in rows:
            a = associations[row.raw_row.row_id]
            records.append(dict(source_row_id=a.raw_row_id.value,
                physical_lines=[a.raw_row_id.physical_start_line, a.raw_row_id.physical_end_line],
                content_fingerprint=a.content_fingerprint,
                raw_values=list(row.raw_row.raw_values),
                spatial_component_id=a.spatial_component_id,
                spectral_setup_id=a.spectral_setup_id, request_context_id=a.request_context_id,
                center_role="EXPLICIT_POINTING" if custom else "RECTANGLE_CENTER",
                center=_center(row)))
        beam = resolve_queue_beam_interpretation(first)
        # No branch receives the diagnostic centers until array ownership is verified.
        variants = [dict(diameter_m=d, pointing_centers_icrs=None,
                         geometry_status="UNRESOLVED",
                         reasons=["EXPLICIT_POINTING_ARRAY_BINDING_UNVERIFIED" if custom
                                  else "OT_RECTANGLE_GRID_NOT_IMPLEMENTED"])
                    for d in beam.diameters_m]
        s = first.spatial
        rectangle = None if custom else dict(
            length_arcsec=None if s.mosaic_length_arcsec is None else s.mosaic_length_arcsec.value,
            width_arcsec=None if s.mosaic_width_arcsec is None else s.mosaic_width_arcsec.value,
            pa_deg=None if s.mosaic_pa_deg is None else s.mosaic_pa_deg.value,
            spacing_arcsec=None if s.mosaic_spacing_arcsec is None else s.mosaic_spacing_arcsec.value,
            frame_raw=s.coordinate_system_raw,
            pa_convention="OT_P_SIDE_FROM_HORIZONTAL_SIGN_NOT_VERIFIED",
            grid_status="NOT_GENERATED")
        candidates.append(dict(candidate_id=key, geometry_kind="CUSTOM" if custom else "RECTANGLE",
            group=asdict(first.group_key), grouping_method=GROUPING_METHOD if custom else "SOURCE_ROW",
            association_status="INFERRED_EXPORT_GROUP_NOT_OFFICIAL_SG" if custom else "SOURCE_ROW_ONLY",
            coverage_completeness="NOT_ESTABLISHED", scientific_status="NOT_EVALUATED",
            array_inference=dict(profile=PROFILE, **asdict(beam)),
            tp_treatment="IGNORED" if first.request.use_tp else "NOT_REQUESTED",
            beam_variants=variants, source_rows=records, rectangle=rectangle,
            unique_offset_count=len({(r.spatial.long_offset_arcsec.value,
                                      r.spatial.lat_offset_arcsec.value) for r in rows})))
    mosaic_rows = [r for c in candidates for r in c["source_rows"]]
    fingerprints = Counter(r["content_fingerprint"] for r in mosaic_rows)
    return dict(schema_version=SCHEMA, snapshot_sha256=snapshot,
        source_url=parsed.snapshot.source_url, source_description=parsed.snapshot.description_raw,
        source_as_of=parsed.snapshot.source_as_of.isoformat() if parsed.snapshot.source_as_of else None,
        source_as_of_status=parsed.snapshot.source_as_of_status,
        parser_version=parsed.snapshot.parser_version, parse_status=parsed.status.value,
        parser_issues=[asdict(issue) for issue in parsed.issues],
        operational_columns=list(parsed.snapshot.operational_columns),
        source_units=list(parsed.snapshot.secondary_header_row),
        source_dictionary=[asdict(entry) for entry in parsed.snapshot.dictionary_entries],
        summary=dict(total_rows=len(parsed.row_inputs), mosaic_rows=len(mosaic_rows),
            excluded_rows=len(excluded), candidate_count=len(candidates),
            candidates_by_kind=dict(Counter(c["geometry_kind"] for c in candidates)),
            exact_repeated_mosaic_rows=sum(n-1 for n in fingerprints.values())),
        candidates=candidates, excluded_rows=sorted(excluded, key=lambda r: r["source_row_id"]),
        scientific_status="NOT_EVALUATED", scope="SUPPLIED_SNAPSHOT_RECONSTRUCTION_ONLY")
