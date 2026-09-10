"""Plan broad searches and verify supplied Archive query provenance offline."""
from alma_duplicate.clients.archive_contract import ArchiveQueryResult
from alma_duplicate.clients.archive_queries import (
    ARCHIVE_CORE_COLUMNS, ArchiveQuerySpec, build_count_adql,
    build_retrieval_adql, normalize_query_parameters,
)
from alma_duplicate.domain.proposed_observation import RequestValidationResult
from alma_duplicate.domain.comparison import ComparisonContext
from alma_duplicate.domain.search import (
    PlannedPredicate, PredicateAction as A, QueryPlanBinding, SearchPlan, SourceSearchPlan, ScalarSelection,
)


def build_search_plan(
    validation: RequestValidationResult, *, archive_science_only: bool = False,
    beam_decision_ref: str | None = None,
) -> SearchPlan:
    """Require spatial search readiness; never infer filters from science requests."""
    if (not validation.is_valid or not validation.can_search
            or validation.request is None or validation.search_options is None):
        raise ValueError("Search planning requires a valid request with search readiness")
    request, options = validation.request, validation.search_options
    if request.position is None or options.radius is None or not options.sources:
        raise ValueError("Position, radius and selected sources are required")
    if request.position.frame != "ICRS" or options.radius.unit != "deg":
        raise ValueError("Planning requires canonical ICRS position and degree radius")
    retrieval_radius = options.radius.value
    if beam_decision_ref is not None:
        if not isinstance(beam_decision_ref, str) or not beam_decision_ref.strip():
            raise ValueError("Beam strategy requires an explicit decision reference")
        from alma_duplicate.primary_beam import requested_beam_frequency, primary_beam_fwhm_deg
        frequency = requested_beam_frequency(request)
        if frequency is not None:
            retrieval_radius = max(retrieval_radius, primary_beam_fwhm_deg(frequency, 7.) / 2 + 1e-10)
    # Also verifies finite coordinates, radius and the explicit science-only choice.
    broad_query = ArchiveQuerySpec(
        request.position.ra_deg, request.position.dec_deg, min(180., retrieval_radius),
        science_only=archive_science_only,
        spatial_strategy="CENTER" if beam_decision_ref is not None else "REGION",
    )
    plans = []
    for source in options.sources:
        if source not in {"ARCHIVE", "QUEUE"}:
            raise ValueError("Unsupported source")
        spatial = "ARCHIVE_REGION_INTERSECTION" if source == "ARCHIVE" else "QUEUE_POINT_CONE"
        predicates = [PlannedPredicate(
            "spatial", A.PLANNED_SERVER if source == "ARCHIVE" else A.PLANNED_LOCAL,
            "s_region" if source == "ARCHIVE" else "row.spatial",
        )]
        if beam_decision_ref is not None:
            spatial = "FORMULA_PRIMARY_BEAM"
            predicates = [PlannedPredicate("spatial", A.PLANNED_LOCAL, "s_ra/s_dec" if source == "ARCHIVE" else "row.spatial")]
            if source == "ARCHIVE":
                predicates.insert(0, PlannedPredicate("retrieval_scope", A.PLANNED_SERVER, "s_ra/s_dec"))
        if source == "ARCHIVE" and archive_science_only:
            predicates.append(PlannedPredicate(
                "science_only", A.PLANNED_SERVER, "science_observation",
            ))
        for p in options.predicates:
            if p.field == "angular_resolution":
                predicates.append(PlannedPredicate(
                    p.field, A.PLANNED_LOCAL,
                    "spatial_resolution" if source == "ARCHIVE" else "Req. Ang. Res.",
                    p, "CANDIDATE_SCALAR_FILTER_NOT_POLICY_CRITERION",
                ))
            else:
                reason = {
                    "frequency": "FREQUENCY_REFERENCE_AND_MATCH_SEMANTICS_UNRESOLVED",
                    "spectral_resolution": "SPW_RESOLUTION_ASSOCIATION_UNRESOLVED",
                    "sensitivity": "RMS_BASIS_AND_ASSOCIATION_NOT_IMPLEMENTED",
                }[p.field]
                predicates.append(PlannedPredicate(p.field, A.SKIPPED, None, p, reason))
        limitations = (
            ("ARCHIVE_REGION_COVERAGE_NOT_UNIVERSAL",) if source == "ARCHIVE" else
            ("QUEUE_FRAME_AND_TARGET_IDENTITY_REQUIRE_EVIDENCE",
             "QUEUE_MOSAIC_OFFSETS_TP_SPS_NOT_SUPPORTED",
             "QUEUE_SCOPE_IS_SUPPLIED_FILE_AND_SOURCE_DATE")
        )
        if beam_decision_ref is not None:
            limitations = ("FORMULA_USES_REQUEST_REPRESENTATIVE_FREQUENCY",
                          "SUPPORTED_FIXED_SINGLE_FIELDS_7M_12M_ONLY",
                          "UNKNOWN_GEOMETRY_OUTSIDE_RETRIEVAL_SCOPE_NOT_COVERED",
                          "NOT_A_FORMAL_POSITION_CRITERION")
        plans.append(SourceSearchPlan(
            source, tuple(predicates), spatial, limitations,
            broad_query if source == "ARCHIVE" else None,
        ))
    return SearchPlan(validation, tuple(plans), options.result_limit,
                      version="2" if beam_decision_ref is not None else "1",
                      beam_decision_ref=beam_decision_ref, retrieval_radius_deg=min(180., retrieval_radius))


def bind_archive_query(plan: SearchPlan, result: ArchiveQueryResult) -> QueryPlanBinding:
    """Exact current-builder provenance check; not a general ADQL equivalence parser.

    Binding is independent of query completeness. MATCHED never means a successful
    retrieval, all local filters applied, or a complete duplication search.
    """
    source = plan.for_source("ARCHIVE")
    p = result.provenance
    if source is None:
        return QueryPlanBinding("SOURCE_NOT_SELECTED", p.query_run_id, ("ARCHIVE_NOT_SELECTED",))
    spec = source.archive_query
    if spec is None:
        raise ValueError("Archive plan lacks query spec")
    reasons = []
    if p.normalized_parameters != normalize_query_parameters(spec):
        reasons.append("QUERY_PARAMETERS_DIFFER")
    if p.count_adql != build_count_adql(spec):
        reasons.append("COUNT_ADQL_DIFFERS")
    columns = p.projection.selected_columns if p.projection else ARCHIVE_CORE_COLUMNS
    if not set(ARCHIVE_CORE_COLUMNS).issubset(columns):
        reasons.append("REQUIRED_PROJECTION_MISSING")
    if not columns:
        reasons.append("RETRIEVAL_PROJECTION_EMPTY")
    elif p.retrieval_adql != build_retrieval_adql(spec, columns=columns):
        reasons.append("RETRIEVAL_ADQL_DIFFERS")
    return QueryPlanBinding("MISMATCH" if reasons else "MATCHED", p.query_run_id, tuple(reasons))


def evaluate_angular_filter(
    plan: SearchPlan, context: ComparisonContext, predicate_index: int,
) -> ScalarSelection:
    """Evaluate one explicit local scalar filter; missing evidence is not NO_MATCH."""
    import math
    from alma_duplicate.domain.comparison import ArchiveContextEvidence, QueueContextEvidence

    source = plan.for_source(context.reference.source)
    if source is None:
        return ScalarSelection(context.context_id, "NOT_EVALUATED", None, None, ("SOURCE_NOT_SELECTED",))
    predicate = source.predicates[predicate_index]
    if predicate.name != "angular_resolution" or predicate.action is not A.PLANNED_LOCAL:
        return ScalarSelection(context.context_id, "NOT_EVALUATED", None, None, ("PREDICATE_NOT_SUPPORTED",))
    requested = predicate.requested
    assert requested is not None
    if isinstance(context.evidence, ArchiveContextEvidence):
        quantity = context.evidence.prepared.comparison_evidence.angular_resolution.quantity
        value, unit = quantity.canonical_value, quantity.canonical_unit
        if not quantity.is_available:
            return ScalarSelection(context.context_id, "NOT_EVALUATED", value, unit, (quantity.status.value,))
    elif isinstance(context.evidence, QueueContextEvidence):
        quantity = context.evidence.row.request.requested_angular_resolution_arcsec
        value, unit = quantity.value, quantity.canonical_unit
    else:
        raise TypeError("Unsupported context")
    if (value is None or isinstance(value, bool) or not math.isfinite(value)
            or value <= 0 or unit != "arcsec" or requested.quantity.unit != "arcsec"):
        return ScalarSelection(context.context_id, "NOT_EVALUATED", value, unit, ("QUANTITY_NOT_USABLE",))
    threshold = requested.quantity.value
    matches = {
        "<": value < threshold, "<=": value <= threshold, "=": value == threshold,
        ">=": value >= threshold, ">": value > threshold,
    }[requested.operator]
    return ScalarSelection(context.context_id, "MATCH" if matches else "NO_MATCH",
                           value, unit, ("SCALAR_FILTER_ONLY",))
