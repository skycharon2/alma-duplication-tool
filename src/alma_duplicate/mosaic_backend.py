"""Automatic Archive Mosaic acquisition behind the common assessment entrypoint."""

from dataclasses import dataclass
import json
from pathlib import Path

from alma_duplicate.mosaic_candidate_discovery import discover_candidates
from alma_duplicate.mosaic_candidate_preparation import prepare_candidates
from alma_duplicate.clients.archive_queries import ArchiveQuerySpec
from alma_duplicate.comparison import build_archive_contexts
from alma_duplicate.reporting import json_value
from alma_duplicate.mosaic_resource_limits import MosaicResourceLimits


@dataclass(frozen=True)
class MosaicAssessmentInput:
    proposed: dict
    output_directory: Path
    cache_directory: Path
    margin_arcsec: float
    resource_limits: MosaicResourceLimits | None = None


def run_mosaic_backend(
    request,
    mosaic,
    *,
    archive_client=None,
    array_catalog=None,
    nominal_conversion=None,
    discovery_provider=None,
    preparation_provider=None,
):
    """Preserve partial acquisition and metadata failures without absence verdicts."""
    from alma_duplicate.assessment import assess_archive_mosaic_contexts
    from alma_duplicate.clients.archive_mirrors import MirroredArchiveClient

    root = Path(mosaic.output_directory)
    root.mkdir(parents=True, exist_ok=False)
    discovery = (discovery_provider or discover_candidates)(
        mosaic.proposed, root / "discovery", margin_arcsec=mosaic.margin_arcsec
    )
    preparation = (preparation_provider or prepare_candidates)(
        discovery, output=root / "preparation", cache=mosaic.cache_directory,
        **({"resource_limits": mosaic.resource_limits} if mosaic.resource_limits is not None else {})
    )
    client = archive_client if archive_client is not None else MirroredArchiveClient()
    results = []
    for candidate in preparation["candidates"]:
        member, source = candidate["member_ous_uid"], candidate["source_name"]
        item = dict(member_ous_uid=member, source_name=source, preparation=candidate)
        try:
            metadata = client.search(
                ArchiveQuerySpec(
                    0.0, 0.0, 180.0, member_ous_uid=member, target_name=source
                )
            )
            # Do not accept a replay or service response for a different target.
            if any(
                row.get("member_ous_uid") != member or row.get("target_name") != source
                for row in metadata.rows
            ):
                raise ValueError("Archive metadata response identity mismatch")
            built = build_archive_contexts(metadata)
            item["metadata_status"] = built.status.value
            item["metadata_provenance"] = json_value(metadata.provenance)
            item["metadata_field_metadata"] = json_value(metadata.field_metadata)
            item["metadata_rows"] = json_value(metadata.rows)
            if built.status != "COMPLETE":
                item.update(status="INCOMPLETE", reasons=list(built.reasons))
            else:
                # Reuse the exact candidate-local AQ evidence used for readiness.
                # A caller-supplied catalog may describe a different acquisition.
                from alma_duplicate.mosaic_readiness_binding import (
                    load_candidate_catalog,
                    verify_candidate_readiness,
                )
                catalog = load_candidate_catalog(candidate, fallback=array_catalog)
                directories, ready = {}, {}
                key = (member, source)
                if candidate.get("package_audit_dir") and candidate.get(
                    "readiness_file"
                ):
                    try:
                        ready[key] = verify_candidate_readiness(candidate, catalog=catalog)
                        directories[key] = candidate["package_audit_dir"]
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        # A bad Mosaic package must not hide independent single-field contexts.
                        item['pointing_error'] = str(exc)
                        ready[key] = set()
                evaluated = assess_archive_mosaic_contexts(
                    request,
                    mosaic.proposed,
                    built.contexts,
                    package_directories=directories,
                    array_catalog=catalog,
                    ready_executions=ready,
                    archive_result=metadata,
                    nominal_conversion=nominal_conversion,
                )
                item.update(
                    status=("PARTIAL_EVIDENCE" if item.get("pointing_error") else "EVALUATED") if built.contexts else "NO_METADATA_CONTEXTS",
                    evaluation=evaluated,
                )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            item.update(status="INCOMPLETE", error=str(exc))
        results.append(item)
    report = dict(
        schema_version="archive_mosaic_backend_1",
        proposed=mosaic.proposed,
        discovery=discovery,
        preparation=preparation,
        candidates=results,
        assessment_status="COMPLETED"
        if discovery["status"] == "COMPLETED"
        and preparation["status"] == "COMPLETED"
        and all(r["status"] == "EVALUATED" for r in results)
        else "INCOMPLETE",
        duplication_scope="PER_ARCHIVE_CONTEXT_BRANCH_RESULTS",
        absence_interpretation="NO_SEARCH_WIDE_NON_DUPLICATION_CONCLUSION",
        discovery_recall_status=discovery["plan"]["recall_status"],
    )
    (root / "assessment.json").write_text(
        json.dumps(json_value(report), indent=2, allow_nan=False) + "\n"
    )
    return report
