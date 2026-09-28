"""Spatial selection strategy dispatch and legacy import compatibility.

Evidence adaptation is owned by spatial_evidence; spherical calculations by
geometry. Selection remains separate from scientific position criteria.
"""
from __future__ import annotations

from alma_duplicate.clients.archive_contract import ArchiveQueryResult
from alma_duplicate.domain.search import SearchPlan
from alma_duplicate.domain.spatial import SkyPosition, SpatialEvidence, SpatialSelection, SpatialStatus as S
from alma_duplicate.geometry import angular_separation_deg
from alma_duplicate.search_plan import bind_archive_query

# Historical paths remain importable; production adapters import their owner.
from alma_duplicate.spatial_evidence import (
    adapt_spatial as adapt_spatial,
    _text as _text,
    _coordinate as _coordinate,
    _archive_center as _archive_center,
    _circle as _circle,
)

_separation = angular_separation_deg


def evaluate_spatial(plan: SearchPlan, evidence: SpatialEvidence) -> SpatialSelection:
    """Evaluate only the planned spatial predicate, never a full search/criterion."""
    if plan.queue_candidate_beam and evidence.context.reference.source == "QUEUE":
        from alma_duplicate.queue_position import evaluate_queue_candidate_beam
        return evaluate_queue_candidate_beam(plan, evidence)
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
    separation = angular_separation_deg(target, position)
    # Numerical boundary band is unresolved, never a false definite exclusion.
    if abs(separation - threshold) <= 1e-10:
        return SpatialSelection(evidence.context.context_id, "NOT_EVALUATED", operation,
                                separation, threshold, tuple(reasons) + ("SPATIAL_BOUNDARY_TOLERANCE",))
    return SpatialSelection(evidence.context.context_id,
                            "INSIDE" if separation < threshold else "OUTSIDE",
                            operation, separation, threshold, tuple(reasons))
