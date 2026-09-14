"""Versioned, reviewable reports; not lossless source-data archives."""
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime, UTC
from enum import Enum
import json
import math
from numbers import Integral, Real
import os
from pathlib import Path
import tempfile

from alma_duplicate.clients.archive_contract import ArchiveQueryResult


def json_value(value):
    """Convert supported evidence without silently stringifying unknown types."""
    if isinstance(value, Enum):
        return json_value(value.value)
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            return {"non_finite": repr(number)}
        return number
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: json_value(getattr(value, f.name))
            for f in fields(value)
        }
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Report mappings require string keys")
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    raise TypeError(f"Unsupported report value: {type(value).__name__}")


def _criterion(result):
    data = json_value(result)
    data["has_computed_outcome"] = result.has_computed_outcome
    data["eligible_for_formal_aggregation"] = (
        result.eligible_for_formal_aggregation
    )
    return data


def _spatial(evidence):
    """Export row-local geometry without repeating its full source table."""
    if evidence is None:
        return None
    return {
        "context_id": evidence.context.context_id,
        "center": evidence.center,
        "center_status": evidence.center_status,
        "footprint": evidence.footprint,
        "footprint_status": evidence.footprint_status,
        "geometry": evidence.geometry,
        "selection_status": evidence.selection_status,
        "reasons": evidence.reasons,
        "interpretation": evidence.interpretation,
        "adapter_version": evidence.adapter_version,
        "array_classification": evidence.array_classification,
    }


def _source(source):
    record = source.source_record
    metadata = None
    if isinstance(record, ArchiveQueryResult):
        metadata = {
            "status": record.status,
            "provenance": record.provenance,
            "field_metadata": record.field_metadata,
            "missing_columns": record.missing_columns,
            "error_kind": record.error_kind,
            "error_message": record.error_message,
        }
    elif record is not None:
        metadata = {
            "status": record.status,
            "snapshot": record.snapshot,
            "raw_row_count": len(record.raw_rows),
            "typed_row_count": len(record.row_inputs),
            "issues": record.issues,
        }
    return {
        "status": source.status,
        "input_mode": source.input_mode,
        "source_metadata": metadata,
        "query_binding": source.query_binding,
        "reasons": source.reasons,
        "server_predicate_indices": source.server_predicate_indices,
        "requested_filters_fully_evaluated":
            source.requested_filters_fully_evaluated,
        "omitted_candidate_ids": source.omitted_candidate_ids,
        "rows": [
            {
                "context_id": row.context.context_id,
                "reference": row.context.reference,
                "alternative_context_ids":
                    row.context.alternative_context_ids,
                "context_reasons": row.context.reasons,
                "disposition": row.disposition,
                "filters": row.filters,
                "spatial_evidence": _spatial(row.spatial_evidence),
            }
            for row in source.rows
        ],
    }


def report_document(report, *, input_sha256=None):
    search = report.search_result
    validation = search.plan.validation
    return json_value({
        "report_version": "1",
        "generated_at": datetime.now(UTC),
        "input_sha256": input_sha256,
        "evaluation_version": report.evaluation_version,
        "execution": report.execution,
        "assessment": report.assessment,
        "search_assessment": search.assessment,
        "search_service_version": search.service_version,
        "search_started_at": search.started_at,
        "search_finished_at": search.finished_at,
        "request": {
            "raw": validation.raw_input,
            "raw_search_options": validation.raw_search_options,
            "normalized": validation.request,
            "search_options": validation.search_options,
            "validation_version": validation.validation_version,
            "issues": validation.issues,
        },
        "plan": {
            "version": search.plan.version,
            "sources": search.plan.sources,
            "result_limit": search.plan.result_limit,
            "retrieval_radius_deg": search.plan.retrieval_radius_deg,
            "beam_decision_ref": search.plan.beam_decision_ref,
            "archive_filter_semantics":
                search.plan.archive_filter_semantics,
        },
        "sources": {
            source.source: _source(source)
            for source in (search.archive, search.queue)
        },
        "evaluation_scope": {
            "total_retained": search.total_retained,
            "shown_candidates": len(search.candidates),
            "evaluated_contexts": len(report.context_evaluations),
            "display_truncated": search.truncated,
            "unused_interpretation_ids":
                search.unused_interpretation_ids,
        },
        "request_criteria": [
            _criterion(result) for result in report.request_criteria
        ],
        "context_evaluations": [
            {
                "context_id": item.candidate.context.context_id,
                "reference": item.candidate.context.reference,
                "evidence_states": item.candidate.context.items,
                "criteria": [_criterion(r) for r in item.criteria],
            }
            for item in report.context_evaluations
        ],
    })


def write_report(path, document, *, overwrite=False):
    """Publish a complete JSON file; never truncate an existing report."""
    text = json.dumps(
        json_value(document), indent=2, ensure_ascii=False, allow_nan=False
    ) + "\n"
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=".alma-report-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, target)
        else:
            # Atomic no-clobber publication on the same filesystem.
            os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
