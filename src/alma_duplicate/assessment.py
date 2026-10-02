"""Transport-independent request validation, execution and report assembly.

Source providers are lazy: invalid and Solar requests never invoke them.
This module owns no paths, network client defaults, output writing or exit codes.
"""
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from alma_duplicate.candidate_search import ArchiveSearcher, search_candidates
from alma_duplicate.domain.queue import QueueCsvParseResult
from alma_duplicate.domain.proposed_observation import RequestValidationResult
from alma_duplicate.reporting import report_document
from alma_duplicate.request_validation import validate_proposed_observation
from alma_duplicate.search_plan import validate_search_plan_configuration
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from alma_duplicate.rules.evaluation_model import SolarExemptionReport
from alma_duplicate.archive_array_evidence import ArchiveArrayCatalog


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


@dataclass(frozen=True)
class AssessmentResult:
    status: AssessmentStatus
    validation: RequestValidationResult
    document: dict | None


def assess_observation(request: dict, search_options: dict, *,
                       options: AssessmentOptions = AssessmentOptions(),
                       sources: AssessmentSources = AssessmentSources(),
                       input_sha256: str | None = None) -> AssessmentResult:
    """Run one assessment, preserving missing-source and independent branch states.

    COMPLETED describes execution only, never a search-wide duplication verdict.
    Queue science remains explicitly selected; callers must supply the intended
    options and display the report's effective evaluation_configuration.
    """
    validated = validate_proposed_observation(request, search_options)
    if validated.is_valid and validated.request.target_kind == "SUN":
        return AssessmentResult(
            AssessmentStatus.SOLAR_EXEMPTION, validated,
            report_document(SolarExemptionReport(validation=validated),
                            input_sha256=input_sha256),
        )
    if not validated.is_valid or not validated.can_search:
        return AssessmentResult(AssessmentStatus.REQUEST_NOT_SEARCH_READY, validated, None)

    selected = validated.search_options.sources
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

    validate_search_plan_configuration(
        validated,
        beam_decision_ref=options.beam_decision_ref,
        aq_equivalent_filters=options.aq_equivalent_filters,
        queue_candidate_beam=options.queue_candidate_beam,
    )

    archive = sources.archive_provider() if sources.archive_provider is not None else None
    search = search_candidates(
        validated, archive_client=archive.client if archive else None,
        queue_loader=sources.queue_loader, beam_decision_ref=options.beam_decision_ref,
        aq_equivalent_filters=options.aq_equivalent_filters,
        queue_candidate_beam=options.queue_candidate_beam,
    )
    report = evaluate_candidate_search(
        search, queue_common=options.queue_common,
        queue_continuum=options.queue_continuum, queue_line=options.queue_line,
        archive_arrays=archive.array_catalog if archive else None,
    )
    document = report_document(
        report, input_sha256=input_sha256,
        archive_replay_metadata=archive.replay_metadata if archive else None,
    )
    if archive is not None and archive.array_catalog is not None:
        from alma_duplicate.archive_array_evidence import METHOD
        document["sources"]["ARCHIVE"]["array_evidence"] = {
            "method_version": METHOD,
            "manifest_sha256": archive.array_catalog.manifest_sha256,
            "record_count": len(archive.array_catalog.records),
            "scope": "CAPTURED_OFFICIAL_AQ_SOURCE_LABELS",
        }
    unavailable = any(source.status in {"FAILED", "INCOMPLETE", "NOT_PROVIDED"}
                      for source in (search.archive, search.queue))
    status = AssessmentStatus.SOURCES_UNAVAILABLE if unavailable else AssessmentStatus.COMPLETED
    return AssessmentResult(status, validated, document)
