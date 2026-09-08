"""Build row-scoped comparison contexts from existing ingestion outputs.

No network calls, predicate filtering, reference transformations or RMS smoothing.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from alma_duplicate.clients.archive_adapter import ArchivePipelineBatch, run_archive_pipeline
from alma_duplicate.clients.archive_contract import ArchiveQueryResult, ArchiveQueryStatus
from alma_duplicate.clients.queue_csv_adapter import run_queue_pipeline
from alma_duplicate.domain.archive_evidence import ArchiveQuantity, ArchiveQuantityStatus
from alma_duplicate.domain.comparison import (
    ArchiveContextEvidence, ComparisonContext, ComparisonPreparation,
    ComparisonSourceResult, EvidenceItem, EvidenceReference, EvidenceState as E,
    QueueContextEvidence, SourceStatus,
)
from alma_duplicate.domain.proposed_observation import RequestValidationResult
from alma_duplicate.domain.queue import QueueCsvParseResult, QueuePipelineBatch, RegularSpwEvidence


def _index(items, key):
    result = {}
    for item in items:
        identity = key(item)
        if identity in result:
            raise ValueError(f"Duplicate evidence identity: {identity}")
        result[identity] = item
    return result


def _quantity(path: str, quantity: ArchiveQuantity, association=E.PRESENT):
    status = quantity.status
    if status is ArchiveQuantityStatus.AVAILABLE:
        numeric, unit = E.PRESENT, E.PRESENT
    elif status is ArchiveQuantityStatus.MISSING_VALUE:
        numeric, unit = E.MISSING, E.PRESENT
    elif status is ArchiveQuantityStatus.INVALID_VALUE:
        numeric, unit = E.INVALID, E.PRESENT
    else:
        numeric, unit = E.UNKNOWN, E.UNAVAILABLE
    return EvidenceItem(path, numeric, unit, association, reasons=(status.value,))


def _archive_contexts(batch: ArchivePipelineBatch) -> tuple[ComparisonContext, ...]:
    rec = batch.reconstruction
    rows = _index(batch.prepared_rows, lambda x: x.raw_row_id)
    links = _index(rec.row_reconstructions, lambda x: x.raw_row_id)
    mappings = _index(rec.support_mappings, lambda x: x.raw_row_id)
    support = _index(rec.frequency_support_evidence, lambda x: x.raw_row_id)
    if not rows.keys() == links.keys() == mappings.keys() == support.keys():
        raise ValueError("Archive pipeline row identities do not agree")
    expected = {
        f"{batch.query_result.provenance.query_run_id}:{i:08d}"
        for i in range(len(batch.query_result.rows))
    }
    if rows.keys() != expected:
        raise ValueError("Archive contexts do not cover the supplied query rows")
    contexts = []
    groups = defaultdict(list)
    for row_id, prepared in rows.items():
        if (prepared.result_index < 0 or prepared.result_index >= len(batch.query_result.rows)
                or prepared.raw_row is not batch.query_result.rows[prepared.result_index]
                or prepared.reconstruction_input.raw_row_id != row_id):
            raise ValueError("Archive prepared row does not belong to supplied query")
        link, mapping, parsed = links[row_id], mappings[row_id], support[row_id]
        if mapping.association_key != link.association_key:
            raise ValueError("Archive mapping and row association disagree")
        component = None
        # Preserve the existing whole-support safety gate.
        if mapping.component_ref is not None and parsed.parse_result.is_valid:
            component = parsed.resolve(mapping.component_ref)
        association = E.PRESENT if link.is_linked else E.UNAVAILABLE
        evidence = prepared.comparison_evidence
        items = [
            _quantity("prepared.comparison_evidence.frequency.centre", evidence.frequency.centre, association),
            _quantity("prepared.comparison_evidence.frequency.bandwidth", evidence.frequency.bandwidth, association),
            _quantity("prepared.comparison_evidence.angular_resolution.quantity", evidence.angular_resolution.quantity, association),
            _quantity("prepared.comparison_evidence.spectral_resolution.quantity", evidence.spectral_resolution.quantity, E.UNKNOWN),
            _quantity("prepared.comparison_evidence.line_sensitivity.quantity", evidence.line_sensitivity.quantity, E.UNKNOWN),
            _quantity("prepared.comparison_evidence.continuum_sensitivity.quantity", evidence.continuum_sensitivity.quantity, E.UNKNOWN),
            EvidenceItem("prepared.raw_row", E.UNKNOWN, E.UNKNOWN, association,
                         reasons=("SPATIAL_ADAPTER_NOT_IMPLEMENTED",)),
            EvidenceItem("selected_component", E.PRESENT if component else E.UNAVAILABLE,
                         E.UNKNOWN, E.PRESENT if component else E.UNAVAILABLE,
                         reasons=(mapping.status.value,)),
        ]
        if component:
            items.extend((
                EvidenceItem("selected_component.frequency_interval",
                             E.PRESENT if component.frequency_interval else E.MISSING,
                             E.UNKNOWN, E.PRESENT, reasons=("SOURCE_UNIT_RETAINED",)),
                EvidenceItem("selected_component.resolution",
                             E.PRESENT if component.resolution else E.MISSING,
                             E.UNKNOWN, E.PRESENT, reasons=("SOURCE_UNIT_RETAINED",)),
                EvidenceItem("selected_component.sensitivities",
                             E.PRESENT if component.sensitivities else E.MISSING,
                             E.UNKNOWN, E.PRESENT, reasons=("COMPONENT_RMS_BASIS_RETAINED",)),
            ))
        context_id = f"ARCHIVE:{row_id}"
        contexts.append(ComparisonContext(
            context_id,
            EvidenceReference("ARCHIVE", row_id, batch.query_result.provenance.query_run_id,
                              parsed.parse_result.parser_version, rec.reconstruction_version,
                              batch.adapter_version, component.component_index if component else None),
            ArchiveContextEvidence(prepared, link, mapping, parsed, component),
            tuple(items),
            reasons=(
                link.status.value, mapping.status.value,
                "ROW_SCALAR_RMS_SPW_ASSOCIATION_UNVERIFIED",
                "FREQUENCY_REFERENCE_UNVERIFIED",
                "CRITERIA_NOT_IMPLEMENTED",
            ),
        ))
        if link.association_key is not None:
            groups[link.association_key].append(context_id)
    return tuple(
        replace(c, alternative_context_ids=tuple(
            other for other in groups[c.evidence.row_link.association_key]
            if other != c.context_id
        ), reasons=c.reasons + ("MULTIPLE_ROWS_FOR_ASSOCIATION",))
        if len(groups[c.evidence.row_link.association_key]) > 1 else c
        for c in contexts
    )


def _queue_contexts(batch: QueuePipelineBatch) -> tuple[ComparisonContext, ...]:
    result, rec = batch.parse_result, batch.reconstruction
    rows = _index(result.row_inputs, lambda x: x.raw_row.row_id)
    raw_rows = _index(result.raw_rows, lambda x: x.row_id)
    if rows.keys() != raw_rows.keys():
        raise ValueError("Queue typed rows do not cover raw rows")
    associations = _index(rec.associations, lambda x: x.raw_row_id)
    spatial = _index(rec.spatial_components, lambda x: x.component_id)
    spectral = _index(rec.spectral_setups, lambda x: x.setup_id)
    requests = _index(rec.request_contexts, lambda x: x.context_id)
    if rows.keys() != associations.keys():
        raise ValueError("Queue associations do not cover typed rows")
    contexts = []
    for row_id, row in rows.items():
        if (row.raw_row != raw_rows[row_id]
                or row_id.snapshot_sha256 != result.snapshot.snapshot_sha256):
            raise ValueError("Queue row does not belong to snapshot")
        a = associations[row_id]
        if a.group_key != row.group_key or a.content_fingerprint != row.raw_row.content_fingerprint:
            raise ValueError("Queue association belongs to different raw evidence")
        for component, expected in (
            (spatial[a.spatial_component_id], row.spatial),
            (spectral[a.spectral_setup_id], row.spectral),
            (requests[a.request_context_id], row.request),
        ):
            if (row_id not in component.source_row_ids or component.group_key != row.group_key
                    or component.evidence != expected):
                raise ValueError("Queue component is not associated with this source row")
        items = [
            EvidenceItem("row.spatial", E.PRESENT, E.PRESENT, E.PRESENT,
                         reasons=("GEOMETRY_COMPARISON_NOT_IMPLEMENTED",)),
            EvidenceItem("row.request.requested_angular_resolution_arcsec",
                         E.PRESENT, E.PRESENT, E.PRESENT),
            EvidenceItem("row.spectral.sensitivity", E.PRESENT, E.PRESENT, E.UNKNOWN,
                         reasons=("REFERENCE_RMS_NOT_ASSIGNED_TO_EVERY_SPW",)),
        ]
        if isinstance(row.spectral, RegularSpwEvidence):
            for index, spw in enumerate(row.spectral.spws):
                prefix = f"row.spectral.spws[{index}]"
                items.extend((
                    EvidenceItem(prefix + ".frequency_derivation", E.PRESENT, E.PRESENT, E.PRESENT,
                                 reasons=("CROSS_SOURCE_FRAME_UNVERIFIED",)),
                    EvidenceItem(prefix + ".spectral_resolution_mhz", E.PRESENT, E.PRESENT, E.PRESENT),
                    EvidenceItem(prefix + ".usable_bandwidth_ghz",
                                 E.MISSING if spw.usable_bandwidth_ghz is None else E.PRESENT,
                                 E.PRESENT, E.PRESENT,
                                 reasons=("USABLE_COVERAGE_APPLICABILITY_REQUIRES_REVIEW",)),
                ))
        else:
            items.append(EvidenceItem("row.spectral.window_expansion_status", E.UNAVAILABLE,
                                      E.UNKNOWN, E.UNKNOWN, reasons=("SPS_EXPANSION_UNAVAILABLE",)))
        contexts.append(ComparisonContext(
            f"QUEUE:{row_id.value}",
            EvidenceReference("QUEUE", row_id.value, result.snapshot.snapshot_sha256,
                              result.snapshot.parser_version, rec.reconstruction_version,
                              batch.adapter_version),
            QueueContextEvidence(row, a), tuple(items),
            reasons=("PLANNED_OBSERVATION_EVIDENCE", "CRITERIA_NOT_IMPLEMENTED"),
        ))
    return tuple(contexts)


def build_archive_contexts(source: ArchivePipelineBatch | ArchiveQueryResult | None) -> ComparisonSourceResult:
    """Retain failure provenance; never reconstruct an incomplete query."""
    if source is None:
        return ComparisonSourceResult("ARCHIVE", SourceStatus.NOT_PROVIDED, None)
    result = source.query_result if isinstance(source, ArchivePipelineBatch) else source
    if not result.can_reconstruct:
        status = SourceStatus.FAILED if result.status is ArchiveQueryStatus.ERROR else SourceStatus.INCOMPLETE
        return ComparisonSourceResult("ARCHIVE", status, result, reasons=(result.status.value,))
    try:
        batch = source if isinstance(source, ArchivePipelineBatch) else run_archive_pipeline(result)
        contexts = _archive_contexts(batch)
    except (ValueError, KeyError) as exc:
        return ComparisonSourceResult("ARCHIVE", SourceStatus.FAILED, result,
                                      reasons=("CONTEXT_CONSTRUCTION_FAILED", str(exc)))
    return ComparisonSourceResult("ARCHIVE", SourceStatus.COMPLETE, result, contexts)


def build_queue_contexts(source: QueuePipelineBatch | QueueCsvParseResult | None) -> ComparisonSourceResult:
    """Retain the strict whole-file Queue gate, independent of Archive."""
    if source is None:
        return ComparisonSourceResult("QUEUE", SourceStatus.NOT_PROVIDED, None)
    result = source.parse_result if isinstance(source, QueuePipelineBatch) else source
    if not result.can_reconstruct:
        return ComparisonSourceResult("QUEUE", SourceStatus.FAILED, result,
                                      reasons=(result.status.value, "STRICT_QUEUE_PARSE_GATE"))
    try:
        batch = source if isinstance(source, QueuePipelineBatch) else run_queue_pipeline(result)
        contexts = _queue_contexts(batch)
    except (ValueError, KeyError) as exc:
        return ComparisonSourceResult("QUEUE", SourceStatus.FAILED, result,
                                      reasons=("CONTEXT_CONSTRUCTION_FAILED", str(exc)))
    return ComparisonSourceResult("QUEUE", SourceStatus.COMPLETE, result, contexts)


def prepare_comparison(
    validation: RequestValidationResult,
    *,
    archive: ArchivePipelineBatch | ArchiveQueryResult | None = None,
    queue: QueuePipelineBatch | QueueCsvParseResult | None = None,
) -> ComparisonPreparation:
    """Bind a valid (possibly partial) request to unfiltered source contexts."""
    if not validation.is_valid or validation.request is None:
        raise ValueError("Comparison preparation requires a validated request")
    return ComparisonPreparation(validation, build_archive_contexts(archive), build_queue_contexts(queue))
