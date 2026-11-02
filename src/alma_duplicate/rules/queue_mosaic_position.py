"""Per-array Queue Mosaic position checks over explicitly bound coverage.

No inferred OT grid, no cross-setup union, no full duplication verdict. A caller
confirmation is recorded evidence, not independent authentication or policy approval.
"""

from dataclasses import asdict, dataclass
import math

from alma_duplicate.domain.spatial import SkyPosition
from alma_duplicate.geometry import angular_separation_deg, primary_beam_fwhm_deg
from alma_duplicate.queue_mosaic import SCHEMA

METHOD = "queue_mosaic_position_bound_disks_1"
MAX_PAIRS = 1_000_000


@dataclass(frozen=True)
class QueueMosaicCoverage:
    candidate_id: str
    snapshot_sha256: str
    source_row_ids: tuple[str, ...]
    diameter_m: float
    frequency_ghz: float
    frequency_evidence_ref: str
    points: tuple[dict, ...]
    geometry_evidence_ref: str
    association_confirmed: bool
    complete: bool


def _points(points):
    if not isinstance(points, (list, tuple)) or not 1 <= len(points) <= 10_000:
        raise ValueError("Expected 1 to 10000 pointings")
    ids, checked = set(), []
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("Pointing must be an object")
        pid = point.get("id")
        ra, dec = point.get("ra_deg"), point.get("dec_deg")
        if not isinstance(pid, str) or not pid.strip() or pid in ids:
            raise ValueError("Pointing IDs must be nonempty and unique")
        if point.get("frame") != "ICRS" or any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v)
            for v in (ra, dec)
        ) or not 0 <= ra < 360 or not -90 <= dec <= 90:
            raise ValueError("Fixed ICRS coordinates required")
        ids.add(pid)
        checked.append((pid, SkyPosition(ra, dec, "ICRS")))
    return checked


def _validate_binding(binding, candidate, snapshot, diameters):
    if (binding.candidate_id != candidate["candidate_id"]
            or binding.snapshot_sha256 != snapshot):
        raise ValueError("Coverage belongs to another candidate or snapshot")
    expected = {r["source_row_id"] for r in candidate["source_rows"]}
    ids = binding.source_row_ids
    if (not isinstance(ids, (list, tuple)) or any(not isinstance(i, str) for i in ids)
            or len(set(ids)) != len(ids) or set(ids) != expected):
        raise ValueError("Coverage must bind exactly the candidate source rows")
    if isinstance(binding.diameter_m, bool) or binding.diameter_m not in diameters:
        raise ValueError("Coverage diameter is not an inferred candidate branch")
    for value in (binding.association_confirmed, binding.complete):
        if type(value) is not bool:
            raise ValueError("Coverage confirmation and completeness must be booleans")
    for value in (binding.frequency_evidence_ref, binding.geometry_evidence_ref):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Frequency and geometry evidence references required")
    radius = primary_beam_fwhm_deg(binding.frequency_ghz, binding.diameter_m)*1800
    if radius >= 90*3600:
        raise ValueError("Coverage beam must lie within a hemisphere")
    return _points(binding.points), radius


def assess_queue_mosaic_position(proposed, reconstruction, candidate_id, coverages=(), *,
                                 boundary_epsilon_arcsec=0.001):
    """Evaluate each inferred array over the same supplied proposed pointing list.

    Missing array coverage stays UNKNOWN. No array selection, cross-array policy,
    spectral compatibility or complete-branch OR is inferred by this position-only
    interface. The imported proposal's array binding is retained in the result.
    """
    if not isinstance(proposed, dict) or not isinstance(reconstruction, dict):
        raise ValueError("Proposal and reconstruction must be JSON objects")
    if reconstruction.get("schema_version") != SCHEMA:
        raise ValueError("Unsupported Queue Mosaic reconstruction schema")
    candidates = [c for c in reconstruction["candidates"] if c["candidate_id"] == candidate_id]
    if len(candidates) != 1:
        raise ValueError("Select exactly one reconstructed candidate")
    candidate = candidates[0]
    snapshot = reconstruction["snapshot_sha256"]
    if not isinstance(snapshot, str) or not snapshot or not candidate["source_rows"]:
        raise ValueError("Candidate requires snapshot and source rows")
    if any(not isinstance(r["source_row_id"], str) or
           not r["source_row_id"].startswith(snapshot + ":") for r in candidate["source_rows"]):
        raise ValueError("Candidate source rows disagree with snapshot")
    if proposed.get("frame_basis") != "USER_CONFIRMED_FIXED_ICRS":
        raise ValueError("Confirmed fixed ICRS proposal required")
    points = _points(proposed.get("points"))
    if (isinstance(boundary_epsilon_arcsec, bool)
            or not isinstance(boundary_epsilon_arcsec, (int, float))
            or not math.isfinite(boundary_epsilon_arcsec)
            or not 0 <= boundary_epsilon_arcsec <= 1):
        raise ValueError("Numerical boundary tolerance must be between 0 and 1 arcsec")
    diameters = candidate["array_inference"]["diameters_m"]
    if list(diameters) not in ([], [7.0], [12.0], [7.0, 12.0]):
        raise ValueError("Invalid inferred array branches")
    bindings = {}
    pair_count = 0
    for binding in coverages:
        if not isinstance(binding, QueueMosaicCoverage):
            raise ValueError("Typed QueueMosaicCoverage required")
        centers, radius = _validate_binding(binding, candidate, snapshot, diameters)
        if binding.diameter_m in bindings:
            raise ValueError("Duplicate array coverage binding")
        pair_count += len(points)*len(centers)
        if pair_count > MAX_PAIRS:
            raise ValueError("Pointing comparison budget exceeded")
        bindings[binding.diameter_m] = binding, centers, radius

    variants = []
    total = len(points)
    for diameter in diameters:
        probes, reasons = [], []
        selected = bindings.get(diameter)
        if selected is None:
            reasons.append("ARRAY_COVERAGE_NOT_BOUND")
        elif not selected[0].association_confirmed:
            reasons.append("COVERAGE_ASSOCIATION_UNCONFIRMED")
        for pid, point in points:
            relations = []
            if selected is not None:
                _, centers, radius = selected
                for cid, center in centers:
                    separation = angular_separation_deg(point, center)*3600
                    delta = separation-radius
                    relation = ("INSIDE" if delta < -boundary_epsilon_arcsec else
                                "OUTSIDE" if delta > boundary_epsilon_arcsec else "BOUNDARY")
                    relations.append(dict(candidate_point_id=cid, separation_arcsec=separation,
                                          boundary_delta_arcsec=delta, relation=relation))
            if reasons:
                status = "UNKNOWN"
            elif any(r["relation"] == "INSIDE" for r in relations):
                status = "INSIDE"
            elif not selected[0].complete:
                status = "UNKNOWN"
            elif any(r["relation"] == "BOUNDARY" for r in relations):
                status = "BOUNDARY"
            else:
                status = "OUTSIDE"
            probes.append(dict(proposed_point_id=pid, status=status,
                               matched_point_ids=[r["candidate_point_id"] for r in relations
                                                  if r["relation"] == "INSIDE"],
                               relations=relations))
        counts = {s: sum(p["status"] == s for p in probes)
                  for s in ("INSIDE", "OUTSIDE", "BOUNDARY", "UNKNOWN")}
        lower = counts["INSIDE"]
        upper = total-counts["OUTSIDE"]
        outcome = "SATISFIED" if 2*lower > total else "NOT_SATISFIED" if 2*upper <= total else "UNKNOWN"
        if selected and not selected[0].complete:
            reasons.append("CANDIDATE_COVERAGE_INCOMPLETE")
        if proposed.get("completeness") != "USER_CONFIRMED_COMPLETE":
            outcome = "UNKNOWN"
            reasons.append("PROPOSED_COMPLETENESS_UNCONFIRMED")
        variants.append(dict(diameter_m=diameter, criterion_id="POS-MOSAIC", outcome=outcome,
            reasons=reasons, counts=counts, covered_count_lower=lower, covered_count_upper=upper,
            covered_fraction_lower=lower/total, covered_fraction_upper=upper/total,
            radius_arcsec=None if selected is None else selected[2],
            coverage=None if selected is None else asdict(selected[0]), points=probes))
    return dict(schema_version="queue_mosaic_position_1", method_version=METHOD,
        candidate_id=candidate_id, snapshot_sha256=snapshot,
        source_row_ids=[r["source_row_id"] for r in candidate["source_rows"]],
        proposed=proposed, array_inference=candidate["array_inference"],
        tp_treatment=candidate["tp_treatment"], beam_variants=variants,
        reasons=[] if diameters else ["ARRAY_INFERENCE_UNRESOLVED"],
        threshold="STRICTLY_MORE_THAN_HALF", boundary_epsilon_arcsec=boundary_epsilon_arcsec,
        boundary_scope="NUMERICAL_NOT_ASTROMETRIC_UNCERTAINTY",
        coverage_basis="CALLER_SUPPLIED_AND_CONFIRMED_NOT_INDEPENDENTLY_AUTHENTICATED",
        assessment_scope="POSITION_ONLY_SUPPLIED_PROPOSED_LIST_PER_CANDIDATE_ARRAY",
        duplication_status="NOT_EVALUATED", array_aggregation="DEFERRED_TO_COMPLETE_SCIENTIFIC_BRANCHES")
