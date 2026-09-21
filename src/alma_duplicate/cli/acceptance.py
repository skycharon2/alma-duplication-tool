"""Run pinned offline acceptance cases and compare explicit reference assertions."""

import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

from alma_duplicate.cli.evaluate import (
    main as evaluate_main,
    _reject_constant,
    _unique_object,
)
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.reporting import write_report


def read_json(path):
    result = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )
    json.dumps(result, allow_nan=False)
    return result


def _path(base, entry):
    path = (base / entry["path"]).resolve()
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError(f"Acceptance input checksum mismatch: {entry['path']}")
    return path


def _lookup(document, path):
    value = document
    for part in path:
        value = value[part]
    return value


def compare_assertions(document, assertions):
    """Stored expectations only: this runner never generates scientific truth."""
    differences = []
    for assertion in assertions:
        missing = False
        try:
            actual = _lookup(document, assertion["path"])
        except (KeyError, IndexError, TypeError):
            actual, missing = None, True
        expected = assertion["equals"]
        tolerance = assertion.get("absolute_tolerance")
        if tolerance is None:
            same = type(actual) is type(expected) and actual == expected
        else:
            numeric = lambda v: (
                isinstance(v, (int, float))
                and not isinstance(v, bool)
                and math.isfinite(v)
            )
            same = (
                numeric(actual)
                and numeric(expected)
                and abs(actual - expected) <= tolerance
            )
        if missing or not same:
            differences.append(
                {
                    "path": assertion["path"],
                    "expected": expected,
                    "actual": actual,
                    "missing_path": missing,
                    "absolute_tolerance": tolerance,
                    "reference": assertion["reference"],
                }
            )
    return differences


def load_catalog(path):
    path = Path(path).resolve()
    catalog = read_json(path)
    if catalog["catalog_version"] != "1" or not catalog["cases"]:
        raise ValueError("Expected nonempty acceptance catalog version 1")
    seen, loaded = set(), []
    for case in catalog["cases"]:
        identifier = case["case_id"]
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", identifier)
            or identifier in seen
        ):
            raise ValueError("Case IDs must be unique safe directory names")
        seen.add(identifier)
        if case["evidence_kind"] not in {
            "SYNTHETIC_NUMERICAL",
            "REAL_CAPTURE_ENGINEERING",
            "REAL_PROPOSAL",
            "HYBRID_DIAGNOSTIC",
            "SOURCE_FAILURE_ENGINEERING",
        }:
            raise ValueError("Unknown acceptance evidence kind")
        review = case["review"]
        if review["status"] not in {"AWAITING_INDEPENDENT_REVIEW", "REVIEWED"}:
            raise ValueError("Unknown review status")
        if review["status"] == "REVIEWED" and not all(
            review.get(k) for k in ("reviewer", "reviewed_at", "record")
        ):
            raise ValueError("Reviewed cases require reviewer, date and review record")
        if not case["assertions"] or case["expected_exit_code"] not in {0, 3}:
            raise ValueError(
                "Cases require assertions and an expected evaluation exit code"
            )
        for a in case["assertions"]:
            if not isinstance(a["path"], list) or not a["path"] or not a["reference"]:
                raise ValueError("Assertions require a path and independent reference")
            if any(
                isinstance(part, bool)
                or not isinstance(part, (str, int))
                or (isinstance(part, int) and part < 0)
                for part in a["path"]
            ):
                raise ValueError(
                    "Assertion path components must be keys or nonnegative indices"
                )
            if "absolute_tolerance" in a:
                t = a["absolute_tolerance"]
                if (
                    isinstance(t, bool)
                    or not isinstance(t, (int, float))
                    or not math.isfinite(t)
                    or t < 0
                ):
                    raise ValueError("Tolerance must be finite and nonnegative")
        inputs = {
            key: _path(path.parent, value) for key, value in case["inputs"].items()
        }
        if "request" not in inputs or set(inputs) - {
            "request",
            "archive_replay",
            "queue_csv",
            "reference",
        }:
            raise ValueError("Unsupported case input")
        if "reference" not in inputs:
            raise ValueError("An independent reference document is required")
        # Verify every captured response before any report directory is created.
        if "archive_replay" in inputs:
            from alma_duplicate.clients.archive_replay import RecordedArchiveClient

            RecordedArchiveClient(inputs["archive_replay"])
        loaded.append((case, inputs))
    return catalog, loaded


def run_catalog(catalog_path, output):
    catalog, loaded = load_catalog(catalog_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for case, inputs in loaded:
        directory = output / case["case_id"]
        directory.mkdir()
        report_path = directory / "report.json"
        args = ["--request", str(inputs["request"]), "--output", str(report_path)]
        for key, flag in (
            ("archive_replay", "--archive-replay"),
            ("queue_csv", "--queue-csv"),
        ):
            if key in inputs:
                args.extend((flag, str(inputs[key])))
        if case.get("queue_candidate_beam", False):
            args.append("--queue-candidate-beam")
        log = io.StringIO()
        with redirect_stdout(log), redirect_stderr(log):
            code = evaluate_main(args)
        (directory / "execution.txt").write_text(log.getvalue(), encoding="utf-8")
        differences = []
        if code != case["expected_exit_code"]:
            differences.append(
                {
                    "path": ["exit_code"],
                    "expected": case["expected_exit_code"],
                    "actual": code,
                }
            )
        if report_path.exists():
            document = read_json(report_path)
            inspection = inspect_report(document)
            differences.extend(
                compare_assertions(
                    {"report": document, "inspection": inspection}, case["assertions"]
                )
            )
            write_report(directory / "inspection.json", inspection)
        else:
            differences.append(
                {"path": ["report"], "expected": "REPORT_WRITTEN", "actual": "MISSING"}
            )
        result = {
            "case_id": case["case_id"],
            "evidence_kind": case["evidence_kind"],
            "review": case["review"],
            "inputs": case["inputs"],
            "exit_code": code,
            "status": "PASS" if not differences else "FAIL",
            "differences": differences,
            "report": f"{case['case_id']}/report.json"
            if report_path.exists()
            else None,
        }
        write_report(directory / "comparison.json", result)
        results.append(result)
    summary = {
        "acceptance_run_version": "1",
        "catalog_version": catalog["catalog_version"],
        "catalog_sha256": hashlib.sha256(Path(catalog_path).read_bytes()).hexdigest(),
        "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
        "scientific_review_inferred_from_test_pass": False,
        "review_status_source": "CATALOG_DECLARATION",
        "reviewed_real_proposal_cases": sum(
            r["evidence_kind"] == "REAL_PROPOSAL"
            and r["review"]["status"] == "REVIEWED"
            for r in results
        ),
        "cases": results,
    }
    write_report(output / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = run_catalog(args.catalog, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Acceptance failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"Acceptance {summary['status']}: {len(summary['cases'])} cases; {args.output_dir / 'summary.json'}"
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
