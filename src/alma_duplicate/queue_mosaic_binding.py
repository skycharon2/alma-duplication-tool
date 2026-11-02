"""Bind Custom CSV geometry only after source-bound OT coordinate parity.

Coordinate agreement does not establish target/array ownership or completeness;
those assertions remain explicit, hash-bound caller evidence.
"""
from dataclasses import asdict, dataclass
import math

from alma_duplicate.domain.spatial import SkyPosition
from alma_duplicate.geometry import angular_separation_deg
from alma_duplicate.parsers.ot_pointings import parse_ot_pointings
from alma_duplicate.queue_mosaic import OFFSET_METHOD, reconstruct_queue_mosaics
from alma_duplicate.queue_position import candidate_frequency
from alma_duplicate.rules.queue_mosaic_position import QueueMosaicCoverage

SCHEMA = "queue_custom_ot_binding_1"
MAX_PAIRS = 1_000_000


@dataclass(frozen=True)
class CustomOTBinding:
    candidate_id: str
    snapshot_sha256: str
    ot_sha256: str
    diameter_m: float
    evidence_ref: str
    confirm_fixed_icrs: bool = False
    association_confirmed: bool = False
    complete: bool = False


def _match(adjacency):
    """Maximum bipartite matching; preserve multiplicity, independent of row order.

    Iterative augmenting paths avoid recursion limits for large exports. A valid
    matching is a coordinate correspondence, not proof of unique source identity.
    """
    right_to_left = {}
    for start in range(len(adjacency)):
        queue, previous, visited = [start], {}, {start}
        free = None
        for left in queue:
            for right in adjacency[left]:
                if right in previous:
                    continue
                previous[right] = left
                owner = right_to_left.get(right)
                if owner is None:
                    free = right
                    break
                if owner not in visited:
                    visited.add(owner)
                    queue.append(owner)
            if free is not None:
                break
        if free is None:
            continue
        left_to_right = {left: right for right, left in right_to_left.items()}
        while free is not None:
            left = previous[free]
            old = left_to_right.get(left)
            right_to_left[free] = left
            free = old
    return {left: right for right, left in right_to_left.items()}


def bind_custom_ot(parsed, ot_raw, binding, *, tolerance_arcsec=0.001):
    """Reconstruct from parsed CSV, compare absolute OT points, produce coverage.

    Failed parity or missing confirmations returns an audit with no coverage.
    Invalid input/source identity raises ValueError. Tolerance is explicit and
    local to this export; successful parity does not approve the offset method
    globally. The candidate frequency follows the existing Queue convention.
    """
    if not isinstance(binding, CustomOTBinding):
        raise ValueError("Typed CustomOTBinding required")
    for value in (binding.confirm_fixed_icrs, binding.association_confirmed, binding.complete):
        if type(value) is not bool:
            raise ValueError("Confirmations must be booleans")
    if not isinstance(binding.evidence_ref, str) or not binding.evidence_ref.strip():
        raise ValueError("Target/setup/array association evidence reference required")
    if (isinstance(tolerance_arcsec, bool) or not isinstance(tolerance_arcsec, (int, float))
            or not math.isfinite(tolerance_arcsec) or not 0 < tolerance_arcsec <= 1):
        raise ValueError("Parity tolerance must be positive and at most 1 arcsec")
    reconstruction = reconstruct_queue_mosaics(parsed)
    if binding.snapshot_sha256 != reconstruction["snapshot_sha256"]:
        raise ValueError("Binding belongs to another CSV snapshot")
    ot = parse_ot_pointings(ot_raw)
    if binding.ot_sha256 != ot["input_sha256"]:
        raise ValueError("Binding belongs to another OT export")
    candidates = [c for c in reconstruction["candidates"] if c["candidate_id"] == binding.candidate_id]
    if len(candidates) != 1:
        raise ValueError("Select exactly one reconstructed candidate")
    candidate = candidates[0]
    if candidate["geometry_kind"] != "CUSTOM":
        raise ValueError("Custom geometry required; Rectangle grids are not inferred")
    if isinstance(binding.diameter_m, bool) or binding.diameter_m not in candidate["array_inference"]["diameters_m"]:
        raise ValueError("Binding diameter is not an inferred candidate branch")
    rows = candidate["source_rows"]
    if len(rows)*len(ot["points"]) > MAX_PAIRS:
        raise ValueError("OT parity comparison budget exceeded")
    source_ids = [r["source_row_id"] for r in rows]
    typed = {r.raw_row.row_id.value: r for r in parsed.row_inputs}
    frequencies = [candidate_frequency(typed[rid]) for rid in source_ids]
    frequency, frequency_source, frequency_notes = frequencies[0]
    reasons = []
    if any(f != frequencies[0] for f in frequencies) or frequency is None:
        reasons.append("CANDIDATE_FREQUENCY_UNRESOLVED")
    if not binding.confirm_fixed_icrs:
        reasons.append("FIXED_ICRS_UNCONFIRMED")
    if not binding.association_confirmed:
        reasons.append("TARGET_SETUP_ARRAY_ASSOCIATION_UNCONFIRMED")
    resolved = all(r["center"]["icrs_deg"] is not None for r in rows)
    if not resolved:
        reasons.append("CSV_CENTERS_UNRESOLVED")
    adjacency, distances = [], []
    if resolved:
        for row in rows:
            ra, dec = row["center"]["icrs_deg"]
            center = SkyPosition(ra, dec, "ICRS")
            errors = [angular_separation_deg(center, SkyPosition(p["ra_deg"], p["dec_deg"], "ICRS"))*3600
                      for p in ot["points"]]
            distances.append(errors)
            adjacency.append([i for i, error in enumerate(errors) if error <= tolerance_arcsec])
    matching = _match(adjacency)
    parity = resolved and len(rows) == len(ot["points"]) == len(matching)
    if not parity:
        reasons.append("OT_POINTING_PARITY_NOT_ESTABLISHED")
    pairs = [dict(source_row_id=source_ids[i], ot_point_id=ot["points"][j]["id"],
                  separation_arcsec=distances[i][j]) for i, j in sorted(matching.items())]
    coverages = []
    if not reasons:
        points = tuple(dict(id=r["source_row_id"], frame="ICRS", ra_deg=r["center"]["icrs_deg"][0],
                            dec_deg=r["center"]["icrs_deg"][1]) for r in rows)
        coverages.append(asdict(QueueMosaicCoverage(
            binding.candidate_id, binding.snapshot_sha256, tuple(source_ids), binding.diameter_m,
            frequency, f"queue:{binding.snapshot_sha256}:{frequency_source}", points,
            f"{SCHEMA}:ot-sha256:{binding.ot_sha256}:tolerance-arcsec:{tolerance_arcsec}:{binding.evidence_ref}",
            True, binding.complete)))
    return dict(schema_version=SCHEMA, binding=asdict(binding),
        status="BOUND" if coverages else "UNRESOLVED", reasons=reasons,
        candidate_id=binding.candidate_id, snapshot_sha256=binding.snapshot_sha256,
        source_row_ids=source_ids, source_rows=rows, operational_columns=reconstruction["operational_columns"],
        source_units=reconstruction["source_units"], array_inference=candidate["array_inference"],
        tp_treatment=candidate["tp_treatment"], offset_method=OFFSET_METHOD,
        ot_export=ot, tolerance_arcsec=tolerance_arcsec,
        parity_status="MATCHED" if parity else "NOT_ESTABLISHED",
        matching_method="ONE_TO_ONE_WITH_MULTIPLICITY_WITHIN_TOLERANCE",
        pairs=pairs, max_matched_error_arcsec=max((p["separation_arcsec"] for p in pairs), default=None),
        unmatched_source_row_ids=[rid for i, rid in enumerate(source_ids) if i not in matching],
        unmatched_ot_point_ids=[p["id"] for j, p in enumerate(ot["points"]) if j not in matching.values()],
        frequency=dict(value_ghz=frequency, source=frequency_source, reasons=list(frequency_notes)),
        coverages=coverages, scientific_status="NOT_EVALUATED",
        confirmation_basis="CALLER_ASSERTION_NOT_INDEPENDENT_AUTHENTICATION",
        scope="SELECTED_CUSTOM_CANDIDATE_AND_OT_EXPORT_ONLY")
