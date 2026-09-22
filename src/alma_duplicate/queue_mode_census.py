"""Offline Queue mode census with explicit denominators and conditional scope."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.data.correlator_modes import CATALOG_SCOPE, CATALOG_VERSION, SOURCES
from alma_duplicate.domain.queue import QueueCsvParseResult, RegularSpwEvidence
from alma_duplicate.queue_csv_contract import QUEUE_EVIDENCE_SNAPSHOT_SHA256
from alma_duplicate.queue_mode import (
    ABS_TOL_MHZ,
    REL_TOL,
    derive_queue_mode,
    project_cycle,
)

CENSUS_VERSION = "1"
MODES = ("FDM", "TDM", "UNKNOWN")


def mode_counts(values) -> dict:
    counts = Counter(values)
    total = sum(counts.values())
    return {
        "total": total,
        **{mode: counts[mode] for mode in MODES},
        "unique_percent": (
            (counts["FDM"] + counts["TDM"]) * 100 / total if total else None
        ),
    }


def build_census(
    parsed: QueueCsvParseResult,
) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """No accepted-row-only denominator when the parser rejected source rows."""
    if not parsed.can_reconstruct:
        kinds = sorted({issue.kind.value for issue in parsed.issues})
        raise ValueError(
            "Queue ingestion is incomplete; census refused: " + ", ".join(kinds)
        )
    records = []
    used_configurations = {}
    excluded = []
    groupings = defaultdict(list)
    groups = ("project_cycle", "geometry", "array_requirements", "project_code")
    for row in parsed.row_inputs:
        raw = row.raw_row
        if not isinstance(row.spectral, RegularSpwEvidence):
            excluded.append(
                {
                    "source_row_id": raw.row_id.value,
                    "reason": "SPECTRAL_SCAN_NOT_EXPANDED",
                }
            )
            continue
        for spw in row.spectral.spws:
            evidence = derive_queue_mode(
                project_cycle(row.group_key.project_code),
                row.request.polarization_raw,
                spw.bandwidth_mhz.value,
                spw.spectral_resolution_mhz.value,
            )
            matches = evidence.matched_configurations
            reference_modes = sorted(
                {c.mode for c in matches if "queue_export_n16" not in c.source_id}
            )
            reference_mode = (
                reference_modes[0] if len(reference_modes) == 1 else "UNKNOWN"
            )
            record = {
                "source_row_id": raw.row_id.value,
                "source_ordinal": raw.source_ordinal,
                "physical_start_line": raw.row_id.physical_start_line,
                "physical_end_line": raw.row_id.physical_end_line,
                "content_fingerprint": raw.content_fingerprint,
                "project_code": row.group_key.project_code,
                "project_cycle": evidence.project_cycle,
                "target_name": row.group_key.target_name,
                "spw_number": spw.number,
                "geometry": row.spatial.mosaic_kind.value,
                "use_7m": row.request.use_7m,
                "use_tp": row.request.use_tp,
                "array_requirements": f"7m={row.request.use_7m};TP={row.request.use_tp}",
                "processor": "UNRESOLVED",
                "conditional_processor": "BLC",
                "polarization": evidence.polarization,
                "frequency_raw_ghz": spw.frequency_ghz.raw_text,
                "bandwidth_raw_mhz": spw.bandwidth_mhz.raw_text,
                "bandwidth_mhz": spw.bandwidth_mhz.value,
                "usable_bandwidth_mhz": (
                    spw.usable_bandwidth_ghz * 1000
                    if spw.usable_bandwidth_ghz is not None
                    else None
                ),
                "usable_bandwidth_method": spw.usable_bandwidth_derivation_version,
                "usable_bandwidth_applicability": spw.usable_bandwidth_applicability.value,
                "resolution_raw_mhz": spw.spectral_resolution_mhz.raw_text,
                "resolution_mhz": spw.spectral_resolution_mhz.value,
                "configuration_status": evidence.configuration_status,
                "configuration_reason": evidence.configuration_reason,
                "unique_configuration_mode": evidence.unique_configuration_mode,
                "conditional_mode_consensus": evidence.conditional_mode_consensus,
                "reference_only_mode_consensus": reference_mode,
                "export_compatibility_only": bool(matches)
                and reference_mode == "UNKNOWN",
                "source_bound_mode": evidence.source_bound_mode,
                "source_bound_reason": evidence.source_bound_reason,
                "match_count": len(matches),
                "matched_configuration_ids": [c.configuration_id for c in matches],
                "compatible_modes": list(evidence.compatible_modes),
                "evidence_origin": evidence.evidence_origin,
                "method_status": evidence.method_status,
                "method_version": evidence.method_version,
                "catalog_version": CATALOG_VERSION,
            }
            records.append(record)
            for config in matches:
                used_configurations[config.configuration_id] = asdict(config)
            for field in groups:
                groupings[field, str(record[field])].append(record)
    signatures = {}
    for record in records:
        key = (
            record["project_cycle"],
            record["polarization"],
            record["bandwidth_raw_mhz"],
            record["resolution_raw_mhz"],
        )
        if key not in signatures:
            signatures[key] = {
                name: record[name]
                for name in (
                    "project_cycle",
                    "polarization",
                    "bandwidth_raw_mhz",
                    "resolution_raw_mhz",
                    "configuration_status",
                    "configuration_reason",
                    "unique_configuration_mode",
                    "conditional_mode_consensus",
                    "reference_only_mode_consensus",
                    "export_compatibility_only",
                    "match_count",
                    "matched_configuration_ids",
                )
            }
            signatures[key].update(
                count=0,
                example_source_row_id=record["source_row_id"],
                example_spw_number=record["spw_number"],
            )
        signatures[key]["count"] += 1
    signature_rows = list(signatures.values())
    snapshot = parsed.snapshot
    summary = {
        "census_version": CENSUS_VERSION,
        "method_version": "queue_correlator_configuration_match_1",
        "method_status": "PROVISIONAL",
        "evidence_origin": "APPLICATION_DERIVED",
        "catalog_version": CATALOG_VERSION,
        "conditional_scope": CATALOG_SCOPE,
        "scope_limitations": [
            "A matched signature does not establish processor, smoothing, baseband or configuration-version association.",
            "Submission cycle is not proof of the cycle/version of the eventual observation.",
            "DOUBLE/FULL BLC Hanning subset; no ACA processor, TPS, oversampling, special multi-region or non-Hanning validation.",
            "N16 factor 15.999 is a supplied export-compatibility hypothesis, independently counted below.",
            "No scientific approval, Queue LINE-FDM integration or duplication verdict is produced.",
        ],
        "snapshot": {
            "sha256": snapshot.snapshot_sha256,
            "matches_repository_pinned_snapshot": snapshot.snapshot_sha256
            == QUEUE_EVIDENCE_SNAPSHOT_SHA256,
            "byte_length": snapshot.byte_length,
            "source_url": snapshot.source_url,
            "source_as_of": snapshot.source_as_of.isoformat()
            if snapshot.source_as_of
            else None,
            "source_as_of_status": snapshot.source_as_of_status,
            "source_as_of_raw": snapshot.source_as_of_raw,
            "schema_version": snapshot.schema_version,
            "parser_version": snapshot.parser_version,
        },
        "denominator": {
            "unit": "physical source row x occupied regular SPW slot; no deduplication",
            "raw_rows": len(parsed.raw_rows),
            "typed_rows": len(parsed.row_inputs),
            "regular_rows": len(parsed.row_inputs) - len(excluded),
            "spectral_scan_rows_excluded": len(excluded),
            "regular_spws": len(records),
            "unique_raw_signatures": len(signature_rows),
            "repeated_content_rows": len(parsed.raw_rows)
            - len({r.content_fingerprint for r in parsed.raw_rows}),
        },
        "conditional_unique_configuration": mode_counts(
            r["unique_configuration_mode"] for r in records
        ),
        "conditional_mode_consensus": mode_counts(
            r["conditional_mode_consensus"] for r in records
        ),
        "reference_only_mode_consensus": mode_counts(
            r["reference_only_mode_consensus"] for r in records
        ),
        "source_bound": mode_counts(r["source_bound_mode"] for r in records),
        "unique_configuration_unknown_reasons": dict(
            sorted(
                Counter(
                    r["configuration_reason"]
                    for r in records
                    if r["unique_configuration_mode"] == "UNKNOWN"
                ).items()
            )
        ),
        "source_bound_unknown_reasons": dict(
            sorted(Counter(r["source_bound_reason"] for r in records).items())
        ),
        "export_compatibility_only_spws": sum(
            r["export_compatibility_only"] for r in records
        ),
        "by_group": [
            {
                "field": field,
                "value": value,
                "conditional_unique_configuration": mode_counts(
                    r["unique_configuration_mode"] for r in items
                ),
                "conditional_mode_consensus": mode_counts(
                    r["conditional_mode_consensus"] for r in items
                ),
                "reference_only_mode_consensus": mode_counts(
                    r["reference_only_mode_consensus"] for r in items
                ),
            }
            for (field, value), items in sorted(groupings.items())
        ],
        "spectral_scan_exclusions": excluded,
        "parser_issues": [
            {
                "kind": i.kind.value,
                "severity": i.severity.value,
                "column": i.column,
                "message": i.message,
            }
            for i in parsed.issues
        ],
        "matching_tolerance": {"relative": REL_TOL, "absolute_mhz": ABS_TOL_MHZ},
        "sources": SOURCES,
    }
    return summary, records, signature_rows, list(used_configurations.values())


def _write_csv(path: Path, records: list[dict]) -> None:
    # Empty census is valid but must never claim a 100% success rate.
    with path.open("w", newline="", encoding="utf-8") as stream:
        if records:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            for record in records:
                writer.writerow(
                    {
                        key: json.dumps(value, ensure_ascii=False)
                        if isinstance(value, list)
                        else value
                        for key, value in record.items()
                    }
                )


def run_census(
    csv_path: Path, output_dir: Path, *, require_pinned_snapshot: bool = False
) -> dict:
    """Write reproducible diagnostics without replacing any previous delivery."""
    parsed = QueueCsvClient().load(csv_path)
    if (
        require_pinned_snapshot
        and parsed.snapshot.snapshot_sha256 != QUEUE_EVIDENCE_SNAPSHOT_SHA256
    ):
        raise ValueError(
            "snapshot SHA256 does not match the repository-pinned full Queue CSV"
        )
    summary, records, signatures, configs = build_census(parsed)
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / "spws.csv", records)
    _write_csv(output_dir / "signatures.csv", signatures)
    _write_csv(
        output_dir / "unknown_signatures.csv",
        [r for r in signatures if r["unique_configuration_mode"] == "UNKNOWN"],
    )
    (output_dir / "matched_configurations.json").write_text(
        json.dumps(configs, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary["artifacts_sha256"] = {
        name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
        for name in (
            "spws.csv",
            "signatures.csv",
            "unknown_signatures.csv",
            "matched_configurations.json",
        )
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary
