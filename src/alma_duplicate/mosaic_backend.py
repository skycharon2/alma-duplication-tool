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
    cache_directory: Path | None
    margin_arcsec: float
    resource_limits: MosaicResourceLimits | None = None
    preparation_directory: Path | None = None
    coverage_model: str = "S_REGION"
    discovery_origin: str | None = None
    discovery_origins: tuple[str, ...] | None = None


def _run_reconstructed_backend(
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
    if mosaic.preparation_directory is not None:
        directory = Path(mosaic.preparation_directory)
        discovery = json.loads((directory / "discovery.json").read_text())
        from alma_duplicate.mosaic_candidate_discovery import plan_discovery
        if discovery.get("plan") != plan_discovery(mosaic.proposed, margin_arcsec=mosaic.margin_arcsec):
            raise ValueError("Resume discovery differs from proposed pointings or search margin")
        preparation = (preparation_provider or prepare_candidates)(
            discovery, output=directory, cache=mosaic.cache_directory, resume=True,
            **({"resource_limits": mosaic.resource_limits} if mosaic.resource_limits is not None else {}))
    else:
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
        if candidate.get("status") == "PENDING":
            item.update(status="PENDING", reasons=["CANDIDATE_PREPARATION_NOT_STARTED"])
            results.append(item)
            continue
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
            from alma_duplicate.mosaic_pointing_diagnostics import alternative_diagnostics, position_summary
            item["alternative_pointing_diagnostics"] = alternative_diagnostics(candidate)
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
                    position_summary=position_summary(evaluated),
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


def run_mosaic_backend(request, mosaic, *, archive_client=None, array_catalog=None,
                       nominal_conversion=None, discovery_provider=None, preparation_provider=None):
    """Default to direct metadata-region assessment; retain explicit research replay."""
    if mosaic.coverage_model == 'RECONSTRUCTED':
        return _run_reconstructed_backend(request, mosaic, archive_client=archive_client,
            array_catalog=array_catalog, nominal_conversion=nominal_conversion,
            discovery_provider=discovery_provider, preparation_provider=preparation_provider)
    if mosaic.coverage_model != 'S_REGION':
        raise ValueError('Unknown Mosaic coverage model')
    if preparation_provider is not None:
        raise ValueError('s_region assessment does not use package preparation providers')
    from alma_duplicate.assessment import assess_archive_mosaic_contexts

    def evaluate(contexts, metadata):
        return assess_archive_mosaic_contexts(
            request, mosaic.proposed, contexts, package_directories={},
            array_catalog=None, archive_result=metadata,
            boundary_epsilon_arcsec=0.001, nominal_conversion=nominal_conversion,
            use_s_region=True,
        )

    return _run_region_backend(
        mosaic, evaluate, archive_client=archive_client,
        discovery_provider=discovery_provider,
    )


def _run_region_backend(mosaic, evaluate_contexts, *, archive_client=None,
                        discovery_provider=None, report_fields=None):
    """Shared discovery/metadata orchestration; science is selected by the caller."""
    from alma_duplicate.progress import emit_progress
    from alma_duplicate.clients.archive_mirrors import MirroredArchiveClient
    from alma_duplicate.mosaic_pointing_diagnostics import position_summary
    root = Path(mosaic.output_directory)
    root.mkdir(parents=True, exist_ok=False)
    emit_progress("archive_search")
    if mosaic.preparation_directory is not None:
        from alma_duplicate.mosaic_candidate_discovery import plan_discovery
        discovery = json.loads((Path(mosaic.preparation_directory)/'discovery.json').read_text())
        if discovery.get('plan') != plan_discovery(mosaic.proposed, margin_arcsec=mosaic.margin_arcsec):
            raise ValueError('Resume discovery differs from proposed pointings or search margin')
    else:
        discovery = (discovery_provider or discover_candidates)(
            mosaic.proposed, root/'discovery', margin_arcsec=mosaic.margin_arcsec,
            **({'origins': mosaic.discovery_origins} if mosaic.discovery_origins else
               {'origin': mosaic.discovery_origin} if mosaic.discovery_origin else {}))
    client = archive_client if archive_client is not None else MirroredArchiveClient()
    total = len({(c['member_ous_uid'], c['source_name']) for c in discovery['candidates']})
    emit_progress("archive_ready", total, unit="candidates")
    results = []
    seen = set()
    for candidate in discovery['candidates']:
        member, source = candidate['member_ous_uid'], candidate['source_name']
        if (member, source) in seen:
            continue
        seen.add((member, source))
        item = dict(member_ous_uid=member, source_name=source)
        emit_progress("evaluation", len(results), total, "candidates")
        try:
            metadata = client.search(ArchiveQuerySpec(0, 0, 180, member_ous_uid=member, target_name=source))
            if any(row.get('member_ous_uid') != member or row.get('target_name') != source
                   or (candidate.get('project_code') is not None and row.get('proposal_id') != candidate['project_code'])
                   for row in metadata.rows):
                raise ValueError('Archive metadata response identity mismatch')
            built = build_archive_contexts(metadata)
            item.update(metadata_status=built.status.value, metadata_provenance=json_value(metadata.provenance),
                metadata_field_metadata=json_value(metadata.field_metadata), metadata_rows=json_value(metadata.rows))
            if built.status != 'COMPLETE':
                item.update(status='INCOMPLETE', reasons=list(built.reasons))
            else:
                evaluated = evaluate_contexts(built.contexts, metadata)
                item.update(status='EVALUATED' if built.contexts else 'NO_METADATA_CONTEXTS',
                            evaluation=evaluated, position_summary=position_summary(evaluated))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            item.update(status='INCOMPLETE', error=str(exc))
        results.append(item)
        emit_progress("evaluation", len(results), total, "candidates")
    report = dict(schema_version='archive_mosaic_backend_2', proposed=mosaic.proposed,
        coverage_source='ARCHIVE_S_REGION', discovery=discovery, candidates=results,
        preparation=dict(status='NOT_REQUIRED', reason='S_REGION_METADATA_ONLY'),
        assessment_status='COMPLETED' if discovery['status']=='COMPLETED' and all(
            r['status']=='EVALUATED' for r in results) else 'INCOMPLETE',
        duplication_scope='PER_ARCHIVE_CONTEXT_BRANCH_RESULTS',
        absence_interpretation='NO_SEARCH_WIDE_NON_DUPLICATION_CONCLUSION',
        discovery_recall_status=discovery['plan']['recall_status'])
    if report_fields is not None:
        report.update(report_fields)
    (root/'assessment.json').write_text(json.dumps(json_value(report),indent=2,allow_nan=False)+'\n')
    return report
