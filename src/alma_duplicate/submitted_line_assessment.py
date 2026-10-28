"""Step 04C: explicitly opted-in Archive V2 LINE assessments.

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
    if validation.search_options.sources != ("ARCHIVE",):
        raise ValueError("V2 Archive LINE assessment requires ARCHIVE only")
    if validation.search_options.predicates:
        raise ValueError("V2 assessment does not accept candidate prefilter predicates")
    return replace(validation, request=prepared.line_request)


def _request_report(raw_request, raw_search_options, prepared, options, *, readiness):
    return {
        "raw": json_value(raw_request),
        "raw_search_options": json_value(raw_search_options),
        "normalized": {
            "input_contract": SEPARATED_INPUT_CONTRACT,
            "target_kind": prepared.line_request.target_kind,
            "geometry": prepared.line_request.geometry,
            "setup_id": prepared.line_request.setup_id,
            "intents": ["LINE"],
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
        "input_contract": SEPARATED_INPUT_CONTRACT,
        "line_evaluation_scope": LINE_SCOPE,
        "line_context_method_version": "archive_line_context_submitted_or_2",
        "pair_method_version": "archive_line_pair_and_1",
        "submitted_requirement_ids": list(prepared.submitted_ids),
        "physical_inventory_affects_line_verdict": False,
        "search_wide_duplication_verdict": "NOT_EVALUATED",
    }


def assess_submitted_line_single_v2(
    raw_request, raw_search_options, *, archive_client=None, archive_result=None,
    input_sha256=None,
):
    """Explicit Archive-only Single Pointing V2 search + reviewable full report.

    The caller must inject an Archive client or a query-bound recorded result.
    This entrypoint never silently activates V2 on the default public API.
    """
    prepared = prepare_submitted_line_request(raw_request)
    if (archive_client is None) == (archive_result is None):
        raise ValueError("Supply exactly one Archive client or query-bound recorded result")
    if prepared.line_request.geometry != "SINGLE_POINTING":
        raise ValueError("Single Pointing V2 entry requires SINGLE_POINTING geometry")
    validated = _base_validation(prepared, raw_search_options)
    search = search_candidates(
        validated, archive_client=archive_client, archive_result=archive_result,
    )
    contexts = []
    for row in search.archive.retained_rows:
        context = row.context
        position = evaluate_position_single(prepared.line_request, context, row.spatial_evidence)
        angular = approve_angular(
            evaluate_angular_resolution(prepared.line_request, context),
            prepared.line_request, context,
        )
        v2 = evaluate_submitted_line_context_v2(prepared, context, (angular, position))
        contexts.append(ContextEvaluation(
            candidate=row, criteria=(angular, position),
            branches=(v2.result.branch,),
            line_pairing=v2.pairing, line_pairs=v2.result.pairs,
        ))

    report = EvaluationReport(
        search_result=search, request_criteria=(),
        context_evaluations=tuple(contexts),
        evaluation_configuration=EvaluationConfiguration(),
    )
    document = report_document(report, input_sha256=input_sha256, detail="full")
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
        v2_science=_v2_fields(prepared),
    )
    # Explicitly separate successful orchestration from exhaustive discovery.
    document["assessment"] = "NOT_AGGREGATED"
    document["assessment_status"] = (
        "COMPLETED" if search.archive.status == "COMPLETED"
        else "SOURCES_UNAVAILABLE"
    )
    document["evaluation_scope"]["context_scope"] = (
        "ALL_RETAINED_ARCHIVE_CONTEXTS_ONLY; no search-wide absence inference"
    )
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
        v2 = evaluate_submitted_line_context_v2(
            prepared, context, tuple(evaluated["criteria"][:2]),
        )
        results.append({
            "context_id": context.context_id,
            "source_reference": json_value(context.reference),
            "display_identity": {
                "project": context.evidence.prepared.raw_row.get("proposal_id"),
                "member_ous_uid": context.evidence.prepared.raw_row.get("member_ous_uid"),
                "target_name": context.evidence.prepared.raw_row.get("target_name"),
            },
            "criteria": json_value(evaluated["criteria"]),
            "coverage": json_value(evaluated["coverage"]),
            "branches": json_value((v2.result.branch,)),
            "line_pairing": json_value(v2.pairing),
            "line_pairs": json_value(v2.result.pairs),
            "submitted_requirement_ids": list(v2.result.submitted_requirement_ids),
            "missing_requirement_ids": list(v2.result.missing_requirement_ids),
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
            "schema_version": "submitted_line_mosaic_search_report_1",
            "report_kind": "SUBMITTED_LINE_V2_MOSAIC_SEARCH",
            "request": _request_report(
                raw_request, None, prepared, None, readiness="READY",
            ),
            "v2_science": _v2_fields(prepared),
            "assessment": "NOT_AGGREGATED",
        },
    )
