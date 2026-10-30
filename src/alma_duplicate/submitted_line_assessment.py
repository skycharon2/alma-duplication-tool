"""Separated V2 assessments with source-specific scientific methods.

Single Pointing executes the existing bounded search; Mosaic evaluates only
supplied Archive contexts with the approved geometry evidence. Neither route
makes a search-wide non-duplication claim. The legacy public entrypoint stays
fail-closed for the separated wire format.
"""

from dataclasses import replace

from alma_duplicate.candidate_search import search_candidates
from alma_duplicate.domain.comparison import ArchiveContextEvidence
from alma_duplicate.domain.proposed_observation import SearchReadiness
from alma_duplicate.reporting import json_value, report_document
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.rules.angular import evaluate_angular_resolution
from alma_duplicate.rules.confirmed import approve_angular
from alma_duplicate.rules.evaluation_model import (
    ContextEvaluation, EvaluationConfiguration, EvaluationReport,
)
from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
from alma_duplicate.rules.position_single import evaluate_position_single
from alma_duplicate.rules.submitted_line_evaluation import (
    evaluate_submitted_line_context_v2, prepare_submitted_line_request,
)
from alma_duplicate.separated_setup_input import SEPARATED_INPUT_CONTRACT

SINGLE_REPORT_VERSION = "submitted_line_single_candidate_report_1"
MOSAIC_REPORT_VERSION = "submitted_line_mosaic_supplied_contexts_report_1"
LINE_SCOPE = "SUBMITTED_LINE_REQUIREMENTS_V2"


def _base_validation(prepared, raw_options):
    """Validate the shared search fields before any Archive client is called.

    The internal request has *only* submitted LINE operands. Its detached
    source fields are already parsed by the legacy shared validator in 04B;
    this second validation owns search options, not science authorization.
    """
    shared = dict(prepared.line_request.raw_input)
    validation = validate_proposed_observation(shared, raw_options)
    if not validation.is_valid or not validation.can_search or validation.request is None:
        raise ValueError("V2 Archive search requires valid shared search fields and readiness")
    if not validation.search_options.sources or set(validation.search_options.sources) - {"ARCHIVE", "QUEUE"}:
        raise ValueError("V2 Single Pointing supports Archive and Queue sources")
    if validation.search_options.predicates:
        raise ValueError("V2 assessment does not accept candidate prefilter predicates")
    return replace(validation, request=prepared.line_request)


def _request_report(raw_request, raw_search_options, prepared, options, *, readiness):
    return {
        "raw": json_value(raw_request),
        "raw_search_options": json_value(raw_search_options),
        "normalized": {
            "input_contract": prepared.input_contract,
            "target_kind": prepared.line_request.target_kind,
            "geometry": prepared.line_request.geometry,
            "setup_id": prepared.line_request.setup_id,
            "intents": list(prepared.line_request.intents),
            "target_name": prepared.line_request.target_name,
            "position": json_value(prepared.line_request.position),
            "continuum_request": json_value(prepared.continuum_request),
            "submitted_requirement_ids": list(prepared.submitted_ids),
            "line_windows": json_value(prepared.separated.line_windows),
            "line_sensitivities": json_value(prepared.separated.line_sensitivities),
            "physical_spw_evidence": json_value(prepared.separated.continuum_window_evidence),
            "physical_spw_inventory_complete": prepared.separated.physical_inventory_complete,
        },
        "search_options": json_value(options) if options is not None else None,
        "search_readiness": readiness,
        "validation_version": "8",
        "issues": [],
    }


def _v2_fields(prepared):
    return {
        "input_contract": prepared.input_contract,
        "line_evaluation_scope": LINE_SCOPE,
        "line_context_method_version": "archive_line_context_submitted_or_2",
        "pair_method_version": "archive_line_pair_and_1",
        "submitted_requirement_ids": list(prepared.submitted_ids),
        "physical_inventory_affects_line_verdict": False,
        "search_wide_duplication_verdict": "NOT_EVALUATED",
    }


def assess_submitted_line_single_v2(
    raw_request, raw_search_options, *, archive_client=None, archive_result=None,
    input_sha256=None, archive_arrays=None, archive_array_fetcher=None, archive_replay_metadata=None,
    queue_loader=None,
):
    """Single Pointing V2 search across selected Archive and Queue sources.

    Archive clients and CSV loaders are injected; missing sources remain unavailable.
    This entrypoint never silently activates V2 on the default public API.
    """
    prepared = prepare_submitted_line_request(raw_request)
    if archive_client is not None and archive_result is not None:
        raise ValueError("Supply at most one Archive client or query-bound recorded result")
    if prepared.line_request.geometry != "SINGLE_POINTING":
        raise ValueError("Single Pointing V2 entry requires SINGLE_POINTING geometry")
    if archive_arrays is not None and archive_array_fetcher is not None:
        raise ValueError("An array catalog and live AQ fetcher are mutually exclusive")
    validated = _base_validation(prepared, raw_search_options)
    search = search_candidates(
        validated, archive_client=archive_client, archive_result=archive_result,
        queue_loader=queue_loader, queue_candidate_beam="QUEUE" in validated.search_options.sources,
    )
    from alma_duplicate.archive_array_acquisition import acquire_archive_arrays
    acquisition = (acquire_archive_arrays(search.archive, archive_array_fetcher)
                   if archive_array_fetcher is not None else None)
    catalog = acquisition.catalog if acquisition is not None else archive_arrays

    def evaluate_row(row, array_evidence=None, diameter=None):
        context = row.context
        if array_evidence is None:
            position = evaluate_position_single(prepared.line_request, context, row.spatial_evidence)
        else:
            from alma_duplicate.rules.archive_position import evaluate_archive_position
            position = evaluate_archive_position(prepared.line_request, context, row.spatial_evidence,
                                                  array_evidence=array_evidence, beam_diameter_m=diameter)
        angular = approve_angular(
            evaluate_angular_resolution(prepared.line_request, context),
            prepared.line_request, context,
        )
        v2 = (evaluate_submitted_line_context_v2(prepared, context, (angular, position))
              if "LINE" in prepared.line_request.intents else None)
        from alma_duplicate.submitted_observation import continuum_context
        extra, continuum_branches = continuum_context(prepared, context, (angular, position))
        return ContextEvaluation(
            candidate=row, criteria=(angular, position, *extra), array_evidence=array_evidence,
            branches=continuum_branches + (() if v2 is None else (v2.result.branch,)),
            line_pairing=None if v2 is None else v2.pairing, line_pairs=() if v2 is None else v2.result.pairs,
        )

    contexts = []
    from alma_duplicate.rules.evaluation_model import BeamVariant
    from alma_duplicate.rules.queue_beam import aggregate_beam_variants
    for row in search.archive.retained_rows:
        evidence = catalog.bind(row.context) if catalog is not None else None
        if evidence is not None and len(evidence.diameters_m) == 2:
            variants = tuple(BeamVariant(d, evaluate_row(row, evidence, d)) for d in evidence.diameters_m)
            contexts.append(ContextEvaluation(candidate=row, criteria=(),
                branches=aggregate_beam_variants(variants, source="ARCHIVE"),
                beam_variants=variants, array_evidence=evidence))
        else:
            contexts.append(evaluate_row(row, evidence))

    from alma_duplicate.rules.queue_common import evaluate_queue_common
    from alma_duplicate.rules.queue_line import evaluate_queue_line
    from alma_duplicate.rules.queue_continuum import evaluate_queue_continuum, scope_supported
    from alma_duplicate.rules.aggregation import aggregate_continuum
    from alma_duplicate.queue_row_beam import resolve_queue_beam_interpretation
    from alma_duplicate.submitted_observation import continuum_setup
    setup = continuum_setup(prepared)

    def evaluate_queue_row(row, diameter=None):
        common = tuple(evaluate_queue_common(prepared.line_request, row.context,
                       row.spatial_evidence, beam_diameter_m=diameter))
        branches, extra = [], ()
        pairing, pairs = None, ()
        if prepared.continuum_request is not None:
            extra = tuple(evaluate_queue_continuum(prepared.continuum_request, row.context, common))
            branches.append(aggregate_continuum(row.context, (setup, *common, *extra),
                            supported=scope_supported(common), queue_method=True))
        if "LINE" in prepared.line_request.intents:
            pairing, pairs, branch = evaluate_queue_line(prepared.line_request, row.context,
                                                        common, submitted_scope=True)
            branches.append(branch)
        return ContextEvaluation(candidate=row, criteria=common + extra,
                                 branches=tuple(branches), line_pairing=pairing, line_pairs=pairs)

    for row in search.queue.retained_rows:
        diameters = resolve_queue_beam_interpretation(row.context.evidence.row).diameters_m
        if len(diameters) == 2:
            variants = tuple(BeamVariant(d, evaluate_queue_row(row, d)) for d in diameters)
            contexts.append(ContextEvaluation(candidate=row, criteria=(),
                branches=aggregate_beam_variants(variants, source="QUEUE"), beam_variants=variants))
        else:
            contexts.append(evaluate_queue_row(row, diameters[0] if diameters else None))
    report = EvaluationReport(
        search_result=search, request_criteria=() if setup is None else (setup,),
        context_evaluations=tuple(contexts),
        evaluation_configuration=EvaluationConfiguration(queue_common="QUEUE" in validated.search_options.sources,
            queue_line="QUEUE" in validated.search_options.sources and "LINE" in prepared.line_request.intents,
            queue_continuum="QUEUE" in validated.search_options.sources and "CONTINUUM" in prepared.line_request.intents),
    )
    document = report_document(report, input_sha256=input_sha256, detail="full",
                               archive_replay_metadata=archive_replay_metadata)
    if acquisition is not None:
        document['sources']['ARCHIVE']['array_evidence'] = acquisition.metadata
    elif catalog is not None:
        from alma_duplicate.archive_array_evidence import archive_array_catalog_report_metadata
        document['sources']['ARCHIVE']['array_evidence'] = archive_array_catalog_report_metadata(catalog)
    # The search uses an internal, LINE-only typed request. Never publish that
    # compatibility view as though it were the user's legacy wire input.
    document["request"] = _request_report(
        raw_request, raw_search_options, prepared, validated.search_options,
        readiness=SearchReadiness.READY.value,
    )
    document.update(
        report_version="7",
        evaluation_version="submitted_line_v2_1",
        assessment_schema_version=SINGLE_REPORT_VERSION,
        report_kind="SUBMITTED_LINE_V2_CANDIDATE_EVALUATION",
        v2_science=_v2_fields(prepared) | {"queue_line_context_method_version": "queue_line_context_submitted_or_2",
            "queue_pair_method_version": "queue_line_pair_and_1"},
    )
    # Explicitly separate successful orchestration from exhaustive discovery.
    document["assessment"] = "NOT_AGGREGATED"
    selected_sources = [source for name, source in
                        (("ARCHIVE", search.archive), ("QUEUE", search.queue))
                        if name in validated.search_options.sources]
    document["assessment_status"] = (
        "COMPLETED" if all(source.status == "COMPLETED" for source in selected_sources)
        and not (acquisition is not None and acquisition.unavailable)
        else "SOURCES_UNAVAILABLE"
    )
    document["evaluation_scope"]["context_scope"] = (
        "ALL_RETAINED_SELECTED_SOURCE_CONTEXTS_ONLY; no search-wide absence inference"
    )
    if prepared.input_contract != SEPARATED_INPUT_CONTRACT:
        document.update(report_version="8", assessment_schema_version="submitted_observation_single_report_2",
                        report_kind="SUBMITTED_OBSERVATION_V2_CANDIDATE_EVALUATION")
    return document


def assess_submitted_line_mosaic_v2(
    raw_request, contexts, proposed, *, use_s_region=True,
    executions=(), array_evidence=None, archive_result=None,
):
    """Evaluate provided Archive Mosaic contexts, with no discovery claim.

    The caller supplies original typed contexts and imported pointings. Mosaic
    common criteria come from the unchanged geometry evaluator with LINE
    disabled only in the internal *common-criteria* view, not the V2 request.
    No user-asserted support flag, pair truth or scalar evidence is accepted.
    """
    prepared = prepare_submitted_line_request(raw_request)
    if prepared.line_request.geometry != "MOSAIC":
        raise ValueError("Mosaic V2 entry requires MOSAIC geometry")
    if type(use_s_region) is not bool:
        raise TypeError("Mosaic use_s_region must be Boolean")
    if not use_s_region and archive_result is None and not executions:
        raise ValueError("Mosaic requires audited geometry evidence")

    original_contexts = tuple(contexts)
    if (len({c.context_id for c in original_contexts}) != len(original_contexts)
            or any(c.reference.source != "ARCHIVE"
                   or not isinstance(c.evidence, ArchiveContextEvidence)
                   for c in original_contexts)):
        raise ValueError("Mosaic requires unique original Archive contexts")

    results = []
    for context in original_contexts:
        # No legacy LINE evaluation is invoked: get position and angular from
        # the existing, unchanged Mosaic geometry / association rules.
        common_only = replace(prepared.line_request, intents=())
        evaluated = evaluate_mosaic_context(
            common_only, context, proposed,
            use_s_region=use_s_region, executions=executions,
            array_evidence=array_evidence, archive_result=archive_result,
            metadata_contexts=original_contexts,
        )
        v2 = (evaluate_submitted_line_context_v2(
            prepared, context, tuple(evaluated["criteria"][:2]),
        ) if "LINE" in prepared.line_request.intents else None)
        from alma_duplicate.submitted_observation import continuum_context, continuum_setup
        extra, continuum_branches = continuum_context(prepared, context, tuple(evaluated["criteria"][:2]), mosaic=True)
        setup = continuum_setup(prepared)
        from alma_duplicate.reporting import _display_identity
        results.append({
            "context_id": context.context_id,
            "source_reference": json_value(context.reference),
            "display_identity": {
                **_display_identity(context),
                # Preserve the original Mosaic report keys for existing consumers.
                "project": context.evidence.prepared.raw_row.get("proposal_id"),
                "member_ous_uid": context.evidence.prepared.raw_row.get("member_ous_uid"),
                "target_name": context.evidence.prepared.raw_row.get("target_name"),
            },
            "criteria": json_value((*evaluated["criteria"], *extra)),
            "request_criteria": json_value(() if setup is None else (setup,)),
            "coverage": json_value(evaluated["coverage"]),
            "branches": json_value(continuum_branches + (() if v2 is None else (v2.result.branch,))),
            "line_pairing": json_value(None if v2 is None else v2.pairing),
            "line_pairs": json_value(() if v2 is None else v2.result.pairs),
            "submitted_requirement_ids": list(prepared.submitted_ids),
            "missing_requirement_ids": list(() if v2 is None else v2.result.missing_requirement_ids),
        })
    return {
        "schema_version": MOSAIC_REPORT_VERSION,
        "report_kind": "SUBMITTED_LINE_V2_SUPPLIED_MOSAIC_CONTEXTS",
        "request": _request_report(raw_request, None, prepared, None, readiness="NOT_SEARCHED"),
        "v2_science": _v2_fields(prepared),
        "assessment_status": "COMPLETED",
        "assessment": "NOT_AGGREGATED",
        "discovery_scope": "SUPPLIED_ARCHIVE_CONTEXTS_NOT_EXHAUSTIVE_SEARCH",
        "pointing_source": (
            "ARCHIVE_S_REGION" if use_s_region else "AUDITED_MOSAIC_GEOMETRY"
        ),
        "contexts": json_value(results),
    }


def assess_submitted_line_mosaic_search_v2(
    raw_request, mosaic, *, archive_client=None, discovery_provider=None,
):
    """Discover Archive candidates and evaluate their metadata with V2 LINE scope.

    Uses the existing all-geometry s_region discovery and mirror handling.
    Candidate-local failures and discovery incompleteness remain in the report;
    neither empty nor partial retrieval establishes search-wide absence.
    """
    from alma_duplicate.mosaic_backend import _run_region_backend
    from alma_duplicate.mosaic_candidate_discovery import plan_discovery

    prepared = prepare_submitted_line_request(raw_request)
    if prepared.line_request.geometry != "MOSAIC":
        raise ValueError("Mosaic V2 search requires MOSAIC geometry")
    if mosaic.coverage_model != "S_REGION":
        raise ValueError("Mosaic V2 search requires S_REGION coverage")
    # Validate coordinates and margin before creating output or accessing Archive.
    plan_discovery(mosaic.proposed, margin_arcsec=mosaic.margin_arcsec)

    def evaluate(contexts, metadata):
        return assess_submitted_line_mosaic_v2(
            raw_request, contexts, mosaic.proposed, archive_result=metadata,
        )

    return _run_region_backend(
        mosaic, evaluate, archive_client=archive_client,
        discovery_provider=discovery_provider,
        report_fields={
            "schema_version": ("submitted_line_mosaic_search_report_1" if prepared.input_contract == SEPARATED_INPUT_CONTRACT
                               else "submitted_observation_mosaic_search_report_2"),
            "report_kind": "SUBMITTED_LINE_V2_MOSAIC_SEARCH",
            "request": _request_report(
                raw_request, None, prepared, None, readiness="READY",
            ),
            "v2_science": _v2_fields(prepared),
            "assessment": "NOT_AGGREGATED",
        },
    )
