"""Run the expanded, conditional processor-equivalence census offline."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.data.correlator_modes import SOURCES
from alma_duplicate.queue_csv_contract import QUEUE_EVIDENCE_SNAPSHOT_SHA256
from alma_duplicate.queue_mode_census import build_census, mode_counts
from alma_duplicate.queue_processor_mode import (
    MAPPING_SOURCES, METHOD_VERSION, configuration_record, evaluate, match,
)


def run(csv_path: Path, output_dir: Path, *, require_pinned_snapshot=False):
    parsed = QueueCsvClient().load(csv_path)
    if require_pinned_snapshot and parsed.snapshot.snapshot_sha256 != QUEUE_EVIDENCE_SNAPSHOT_SHA256:
        raise ValueError("snapshot SHA256 does not match pinned Queue CSV")
    baseline, records, _, _ = build_census(parsed)
    results = []
    configs = {}
    for row in records:
        args = (row["project_cycle"], row["polarization"], row["bandwidth_mhz"], row["resolution_mhz"])
        views = {}
        for profile, compatibility in (("reference", False), ("compatibility", True)):
            for scope, tp in (("all_families", row["polarization"] != "FULL"),
                              ("requested_arrays", row["use_tp"] is not False)):
                views[f"{profile}_{scope}"] = evaluate(*args, require_tp=tp,
                    include_export_compatibility=compatibility)
            for c in match(*args, include_export_compatibility=compatibility):
                configs[c.configuration_id] = configuration_record(c)
        results.append({"input": row, "views": views})
    keys = [f"{p}_{s}" for p in ("reference", "compatibility")
            for s in ("all_families", "requested_arrays")]
    summary = {"method_version": METHOD_VERSION, "status": "PROVISIONAL",
               "scientific_closure": "NOT_ESTABLISHED", "enumeration_complete": False,
               "snapshot": baseline["snapshot"], "denominator": baseline["denominator"],
               "baseline_v1": {k: baseline[k] for k in (
                   "conditional_mode_consensus", "reference_only_mode_consensus")},
               "views": {k: mode_counts(r["views"][k]["conditional_processor_consensus"] for r in results) for k in keys},
               "single_field": {k: mode_counts(r["views"][k]["conditional_processor_consensus"] for r in results if r["input"]["geometry"] == "SINGLE_FIELD") for k in keys},
               "reason_counts": {k: dict(Counter(reason for r in results for reason in r["views"][k]["reasons"])) for k in keys},
               "coverage_gaps": ["OT response revision is not a Cycle 11-13 release manifest",
                   "Averaged HAMMING/BARTLETT/BLACKMANN/BLACKMANN_HARRIS profiles unavailable",
                   "TPS uses documented user-facing equivalence, not independent native inversion",
                   "15.999 export coefficient has no retrieved official provenance",
                   "Legacy ACA contingency operation excluded; normal Cycle 11-13 scope only",
                   "Queue export bandwidth conventions and profile applicability remain conditional"],
               "sources": {**SOURCES, **MAPPING_SOURCES},
               "parser_issues": baseline["parser_issues"]}
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, content in (("spws.json", results), ("matched_configurations.json", list(configs.values()))):
        (output_dir / name).write_text(json.dumps(content, indent=2, allow_nan=False) + "\n")
    summary["artifacts_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output_dir.iterdir())}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-pinned-snapshot", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = run(args.queue_csv, args.output_dir, require_pinned_snapshot=args.require_pinned_snapshot)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(summary["views"], indent=2))
    print("Scientific closure: NOT_ESTABLISHED; conditional experiment only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
