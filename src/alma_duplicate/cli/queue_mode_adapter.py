"""Export derived Queue modes and separate single-point scope from typed input."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.domain.queue import RegularSpwEvidence
from alma_duplicate.data.correlator_modes import SOURCES
from alma_duplicate.queue_csv_contract import QUEUE_EVIDENCE_SNAPSHOT_SHA256
from alma_duplicate.queue_mode_adapter import DECISION_REF, METHOD_VERSION, classify_spw
from alma_duplicate.queue_processor_mode import (
    MAPPING_SOURCES,
    METHOD_VERSION as CONFIGURATION_METHOD,
    configurations,
)


def run(csv_path, output_dir, *, require_pinned_snapshot=False):
    parsed = QueueCsvClient().load(csv_path)
    if (
        require_pinned_snapshot
        and parsed.snapshot.snapshot_sha256 != QUEUE_EVIDENCE_SNAPSHOT_SHA256
    ):
        raise ValueError("snapshot SHA256 does not match pinned Queue CSV")
    if not parsed.can_reconstruct:
        raise ValueError("Queue ingestion incomplete; mode export refused")
    records = []
    excluded = []
    for row in parsed.row_inputs:
        if not isinstance(row.spectral, RegularSpwEvidence):
            excluded.append(
                {
                    "source_row_id": row.raw_row.row_id.value,
                    "reason": "SPECTRAL_SCAN_NOT_EXPANDED",
                }
            )
            continue
        records.extend(classify_spw(row, spw.number) for spw in row.spectral.spws)
    summary = {
        "method_version": METHOD_VERSION,
        "decision_ref": DECISION_REF,
        "configuration_method_version": CONFIGURATION_METHOD,
        "reference_catalog_sha256": hashlib.sha256(
            json.dumps(
                [
                    asdict(c)
                    for cycle in (11, 12, 13)
                    for c in configurations(cycle)
                    if not c.export_compatibility
                ],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        "snapshot": {
            "sha256": parsed.snapshot.snapshot_sha256,
            "source_url": parsed.snapshot.source_url,
            "source_as_of": str(parsed.snapshot.source_as_of)
            if parsed.snapshot.source_as_of
            else None,
        },
        "denominator": {
            "unit": "physical source row x occupied regular SPW slot; no deduplication",
            "raw_rows": len(parsed.raw_rows),
            "typed_rows": len(parsed.row_inputs),
            "regular_spws": len(records),
            "excluded_rows": excluded,
        },
        "mode_counts": {
            mode: sum(r["mode_evidence"]["mode"] == mode for r in records)
            for mode in ("FDM", "TDM", "UNKNOWN")
        },
        "path_counts": dict(Counter(r["mode_evidence"]["match_path"] for r in records)),
        "mode_reason_counts": dict(
            Counter(r["mode_evidence"]["reason"] for r in records)
        ),
        "compatibility_mode_counts": dict(
            Counter(
                r["mode_evidence"]["mode"]
                for r in records
                if r["mode_evidence"]["match_path"] == "N16_SCOPED_COMPATIBILITY"
            )
        ),
        "single_point_scope_counts": dict(
            Counter(r["single_point_applicability"]["status"] for r in records)
        ),
        "single_point_reason_counts": dict(
            Counter(r["single_point_applicability"]["reason"] for r in records)
        ),
        "enumeration_complete": False,
        "export_provenance": "UNRESOLVED",
        "duplication_assessment": "NOT_PERFORMED",
        "sources": {**SOURCES, **MAPPING_SOURCES},
        "parser_issues": [asdict(issue) for issue in parsed.issues],
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    content = json.dumps(records, indent=2, allow_nan=False) + "\n"
    (output_dir / "spws.json").write_text(content, encoding="utf-8")
    summary["artifacts_sha256"] = {
        "spws.json": hashlib.sha256(content.encode()).hexdigest()
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--require-pinned-snapshot", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(
            args.queue_csv,
            args.output_dir,
            require_pinned_snapshot=args.require_pinned_snapshot,
        )
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "mode_counts",
                    "path_counts",
                    "compatibility_mode_counts",
                    "single_point_scope_counts",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
