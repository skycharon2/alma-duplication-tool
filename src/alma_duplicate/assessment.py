"""Transport-independent request validation, execution and report assembly.

Source providers are lazy: invalid and Solar requests never invoke them.
This module owns no paths, network client defaults, output writing or exit codes.
"""
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from alma_duplicate.performance import measure_stage
from alma_duplicate.candidate_search import ArchiveSearcher, search_candidates
from alma_duplicate.domain.queue import QueueCsvParseResult
from alma_duplicate.domain.proposed_observation import RequestValidationResult
from alma_duplicate.progress import emit_progress
from alma_duplicate.reporting import report_document
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.search_plan import validate_search_plan_configuration
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.continuum_setup import PORTAL_SCRIPT_V1
from alma_duplicate.rules.evaluation_model import SolarExemptionReport
from alma_duplicate.archive_array_evidence import (
    ArchiveArrayCatalog,
    archive_array_catalog_report_metadata,
)
from alma_duplicate.archive_array_acquisition import ArchiveArrayFetcher, acquire_archive_arrays


class AssessmentStatus(StrEnum):
    REQUEST_NOT_SEARCH_READY = "REQUEST_NOT_SEARCH_READY"
    SOLAR_EXEMPTION = "SOLAR_EXEMPTION"
    COMPLETED = "COMPLETED"
    SOURCES_UNAVAILABLE = "SOURCES_UNAVAILABLE"


@dataclass(frozen=True)
class AssessmentOptions:
    beam_decision_ref: str | None = None
    queue_candidate_beam: bool = False
    aq_equivalent_filters: bool = False
    queue_common: bool = False
    queue_continuum: bool = False
    queue_line: bool = False
    nominal_conversion: str | None = PORTAL_SCRIPT_V1


@dataclass(frozen=True)
class ArchiveInput:
    client: ArchiveSearcher
    replay_metadata: dict | None = None
    array_catalog: ArchiveArrayCatalog | None = None


@dataclass(frozen=True)
class AssessmentSources:
    archive_kind: str | None = None
    archive_provider: Callable[[], ArchiveInput] | None = None
    queue_loader: Callable[[], QueueCsvParseResult] | None = None
    archive_array_fetcher: ArchiveArrayFetcher | None = None


@dataclass(frozen=True)
class AssessmentResult:
    status: AssessmentStatus
    validation: RequestValidationResult
    document: dict | None


def assess_observation(request: dict, search_options: dict, *,
                       options: AssessmentOptions = AssessmentOptions(),
                       sources: AssessmentSources = AssessmentSources(),
                       input_sha256: str | None = None,
                       report_detail: str = 'full', mosaic=None) -> AssessmentResult:
    """Run one assessment, preserving missing-source and independent branch states.

    COMPLETED describes execution only, never a search-wide duplication verdict.
    Queue science remains explicitly selected; callers must supply the intended
    options and display the report's effective evaluation_configuration.
    """
    if report_detail not in {'full', 'matches'}:
        raise ValueError('Report detail must be full or matches')
    with measure_stage("validation"):
        validated = validate_proposed_observation(request, search_options)
    if validated.is_valid and validated.request.target_kind == "SUN":
        return AssessmentResult(
            AssessmentStatus.SOLAR_EXEMPTION, validated,
            report_document(SolarExemptionReport(validation=validated),
                            input_sha256=input_sha256),
        )
    if mosaic is not None and validated.is_valid:
        from dataclasses import replace
        from alma_duplicate.domain.proposed_observation import SearchReadiness
        from alma_duplicate.mosaic_backend import run_mosaic_backend
        if validated.request.target_kind != 'FIXED' or validated.request.geometry != 'MOSAIC':
            raise ValueError('OT pointings require a fixed Mosaic request')
        if validated.search_options.sources != ('ARCHIVE',):
            raise ValueError('Automatic Mosaic assessment currently requires ARCHIVE only')
        if validated.search_options.predicates:
            raise ValueError('Mosaic candidate prefilter predicates are not implemented; omit them')
        if sources.queue_loader is not None or options.queue_common or options.queue_continuum or options.queue_line:
            raise ValueError('Queue evaluation is not supported by this Archive Mosaic workflow')
        if sources.archive_kind != 'LIVE':
            raise ValueError('Automatic Mosaic acquisition requires explicit LIVE Archive input')
        if (sources.archive_kind is None) != (sources.archive_provider is None):
            raise ValueError('Archive kind and provider must be supplied together')
        if sources.archive_array_fetcher is not None:
            raise ValueError('Mosaic preparation owns AQ acquisition; provide a catalog for replay')
        if mosaic.proposed['source_name'] != validated.request.target_name:
            raise ValueError('OT pointings belong to another proposed target')
        if options.nominal_conversion not in (None, PORTAL_SCRIPT_V1):
            raise ValueError('Unknown proposed nominal bandwidth conversion')
        validated = replace(validated, search_readiness=SearchReadiness.READY,
            issues=tuple(i for i in validated.issues if not
                         (i.category == 'CAPABILITY' and i.path == 'request' and i.code == 'METHOD_NOT_IMPLEMENTED')))
        archive = sources.archive_provider() if sources.archive_provider else None
        document = run_mosaic_backend(validated.request, mosaic,
            archive_client=archive.client if archive else None,
            array_catalog=archive.array_catalog if archive else None,
            nominal_conversion=options.nominal_conversion)
        document['input_sha256'] = input_sha256
        return AssessmentResult(AssessmentStatus.COMPLETED if document['assessment_status'] == 'COMPLETED'
                                else AssessmentStatus.SOURCES_UNAVAILABLE, validated, document)
    if not validated.is_valid or not validated.can_search:
        return AssessmentResult(AssessmentStatus.REQUEST_NOT_SEARCH_READY, validated, None)

    selected = validated.search_options.sources
    if options.nominal_conversion not in (None, PORTAL_SCRIPT_V1):
        raise ValueError('Unknown proposed nominal bandwidth conversion')
    if (options.queue_common or options.queue_continuum or options.queue_line) and "QUEUE" not in selected:
        raise ValueError("--queue-common/--queue-continuum/--queue-line requires QUEUE selection")
    if options.queue_continuum and "CONTINUUM" not in validated.request.intents:
        raise ValueError("--queue-continuum requires CONTINUUM intent")
    if options.queue_line and "LINE" not in validated.request.intents:
        raise ValueError("--queue-line requires LINE intent")
    if sources.archive_kind not in (None, "LIVE", "REPLAY"):
        raise ValueError("Unknown Archive source kind")
    if (sources.archive_kind is None) != (sources.archive_provider is None):
        raise ValueError("Archive kind and provider must be supplied together")
    if sources.archive_kind == "LIVE" and "ARCHIVE" not in selected:
        raise ValueError("--live-archive requires ARCHIVE selection")
    if sources.queue_loader is not None and "QUEUE" not in selected:
        raise ValueError("--queue-csv requires QUEUE selection")
    if options.beam_decision_ref is not None and not options.beam_decision_ref.strip():
        raise ValueError("--beam-decision-ref must not be blank")
    if sources.archive_kind == "REPLAY" and "ARCHIVE" not in selected:
        raise ValueError("--archive-replay requires ARCHIVE selection")
    if sources.archive_array_fetcher is not None:
        if sources.archive_kind != "LIVE" or "ARCHIVE" not in selected:
            raise ValueError("Live AQ acquisition requires selected LIVE Archive input")
        if not callable(sources.archive_array_fetcher):
            raise ValueError("Archive array fetcher must be callable")

    validate_search_plan_configuration(
        validated,
        beam_decision_ref=options.beam_decision_ref,
        aq_equivalent_filters=options.aq_equivalent_filters,
        queue_candidate_beam=options.queue_candidate_beam,
    )

    with measure_stage("source_initialization"):
        archive = sources.archive_provider() if sources.archive_provider is not None else None
    if (sources.archive_array_fetcher is not None and archive is not None
            and archive.array_catalog is not None):
        raise ValueError("An array catalog and live AQ fetcher are mutually exclusive")
    search = search_candidates(
        validated, archive_client=archive.client if archive else None,
        queue_loader=sources.queue_loader, beam_decision_ref=options.beam_decision_ref,
        aq_equivalent_filters=options.aq_equivalent_filters,
        queue_candidate_beam=options.queue_candidate_beam,
    )
    with measure_stage("aq_acquisition"):
        acquisition = (acquire_archive_arrays(search.archive, sources.archive_array_fetcher)
                       if sources.archive_array_fetcher is not None else None)
    catalog = acquisition.catalog if acquisition is not None else archive.array_catalog if archive else None
    with measure_stage("scientific_evaluation"):
        report = evaluate_candidate_search(
            search, queue_common=options.queue_common,
            queue_continuum=options.queue_continuum, queue_line=options.queue_line,
            archive_arrays=catalog,
            nominal_conversion=(options.nominal_conversion
                                if 'CONTINUUM' in validated.request.intents
                                and validated.request.continuum_setup_declaration is None
                                and any(w.bandwidth_kind == 'NOMINAL' or
                                        (w.interval is not None and w.interval.kind == 'NOMINAL')
                                        for w in validated.request.spectral_windows)
                                else None),
        )
    emit_progress("report")
    with measure_stage("report_assembly"):
        document = report_document(
            report, input_sha256=input_sha256,
            archive_replay_metadata=archive.replay_metadata if archive else None,
            detail=report_detail,
        )
    if acquisition is not None:
        document["sources"]["ARCHIVE"]["array_evidence"] = acquisition.metadata
    elif catalog is not None:
        document["sources"]["ARCHIVE"]["array_evidence"] = (
            archive_array_catalog_report_metadata(catalog)
        )
    unavailable = any(source.status in {"FAILED", "INCOMPLETE", "NOT_PROVIDED"}
                      for source in (search.archive, search.queue))
    unavailable = unavailable or (acquisition is not None and acquisition.unavailable)
    status = AssessmentStatus.SOURCES_UNAVAILABLE if unavailable else AssessmentStatus.COMPLETED
    if acquisition is not None:
        document["assessment_status"] = status.value
    return AssessmentResult(status, validated, document)


def assess_mosaic_candidates(proposed: dict, candidates: list, *,
                             hpbw_coefficient=1.13, boundary_epsilon_arcsec=0.000001,
                             assume_uniform_field_antennas=False) -> dict:
    """Assess supplied Archive candidates independently using the shared rule model.

    Candidate acquisition is explicit: this entrypoint does not use the existing
    single-pointing search or claim exhaustive candidate discovery. Each candidate
    binds a verified readiness bundle to its Member and target before evaluation.
    Missing bundles yield insufficient information; identity conflicts are errors.
    """
    from dataclasses import asdict
    from alma_duplicate.rules.position_mosaic import evaluate_mosaic_position
    import math
    for value, positive in ((hpbw_coefficient, True), (boundary_epsilon_arcsec, False)):
        if isinstance(value, bool) or not math.isfinite(value) or value < 0 or (positive and value == 0):
            raise ValueError('Invalid Mosaic beam coefficient or boundary epsilon')
    results, seen = [], set()
    for candidate in candidates:
        identity = candidate['context_id']
        if not isinstance(identity, str) or not identity.strip() or identity in seen:
            raise ValueError('Candidate context IDs must be nonempty and unique')
        seen.add(identity)
        member, source = candidate['member_ous_uid'], candidate['source_name']
        if not isinstance(member,str) or not member or not isinstance(source,str) or not source:
            raise ValueError('Candidate Member and source identity required')
        readiness = candidate.get('readiness')
        if readiness is not None and (readiness['member_ous_uid'] != member or
                                      readiness['source_name'] != source):
            raise ValueError('Mosaic evidence belongs to a different candidate')
        criterion, coverage = evaluate_mosaic_position(proposed,context_id=identity,
            readiness=readiness,selections=candidate.get('selections'),
            hpbw_coefficient=hpbw_coefficient,boundary_epsilon_arcsec=boundary_epsilon_arcsec,
            assume_uniform_field_antennas=assume_uniform_field_antennas)
        results.append(dict(context_id=identity,member_ous_uid=member,source_name=source,
            criteria=[asdict(criterion)],coverage=coverage,duplication_status='NOT_EVALUATED'))
    return dict(schema_version='mosaic_candidate_assessment_1',candidates=results,
        candidate_discovery_scope='EXPLICITLY_SUPPLIED_CANDIDATES_NOT_EXHAUSTIVE_SEARCH',
        assessment_status='COMPLETED',duplication_status='NOT_EVALUATED')


def assess_archive_mosaic_contexts(request, proposed, contexts, *, package_directories,
                                  array_catalog, boundary_epsilon_arcsec=0.000001,
                                  nominal_conversion=None, ready_executions=None, archive_result=None):
    """Reuse Archive comparison contexts and rules with verified Mosaic pointings.

    package_directories maps (Member UID, target name) to local audited packages.
    Contexts are constructed by the existing Archive ingestion pipeline; listobs
    contributes positions only. This does not invoke single-pointing search filters.
    """
    from dataclasses import asdict
    from pathlib import Path
    from alma_duplicate.archive_mosaic_pointings import load_package_executions
    from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
    from alma_duplicate.domain.comparison import ArchiveContextEvidence
    contexts = tuple(contexts)
    loaded, seen, results = {}, set(), []
    for context in contexts:
        if context.context_id in seen or not isinstance(context.evidence,ArchiveContextEvidence):
            raise ValueError('Unique Archive contexts required')
        seen.add(context.context_id)
        raw=context.evidence.prepared.raw_row
        key=(raw.get('member_ous_uid'),raw.get('target_name'))
        if key not in loaded:
            directory=package_directories.get(key)
            loaded[key]=load_package_executions(Path(directory))[0] if directory is not None else ()
        executions = loaded[key]
        evaluated=evaluate_mosaic_context(request,context,proposed,executions=executions,
            metadata_contexts=contexts, archive_result=archive_result,
            ready_asdm_uids=None if ready_executions is None else ready_executions.get(key, ()),
            array_evidence=array_catalog.bind(context) if array_catalog is not None else None,
            boundary_epsilon_arcsec=boundary_epsilon_arcsec,nominal_conversion=nominal_conversion)
        results.append(dict(context_id=context.context_id,
            criteria=[asdict(c) for c in evaluated['criteria']],
            request_criteria=[asdict(c) for c in evaluated['request_criteria']],
            branches=[asdict(b) for b in evaluated['branches']],
            line_pairing=asdict(evaluated['line_pairing']) if evaluated['line_pairing'] is not None else None,
            line_pairs=[asdict(p) for p in evaluated['line_pairs']],coverage=evaluated['coverage']))
    return dict(schema_version='archive_mosaic_context_assessment_1',contexts=results,
        metadata_source='EXISTING_ARCHIVE_COMPARISON_CONTEXTS',pointing_source='VERIFIED_PACKAGE_EXECUTIONS',
        discovery_scope='SUPPLIED_CONTEXTS_NOT_EXHAUSTIVE_SEARCH',assessment_status='COMPLETED')
