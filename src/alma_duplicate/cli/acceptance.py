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

from alma_duplicate.cli.evaluate import main as evaluate_main
from alma_duplicate.cli.json_input import _reject_constant, _unique_object
from alma_duplicate.report_inspection import inspect_report
from alma_duplicate.reporting import write_report


CATALOG_VERSIONS = {"1", "2"}
EVALUATION_OPTION_FLAGS = (
    ("queue_common", "--queue-common"),
    ("queue_continuum", "--queue-continuum"),
    ("queue_line", "--queue-line"),
)
EVALUATION_OPTION_KEYS = tuple(key for key, _ in EVALUATION_OPTION_FLAGS)
EVALUATION_OPTION_KEY_SET = frozenset(EVALUATION_OPTION_KEYS)
V2_CASE_KEYS = frozenset(
    {
        "case_id",
        "evidence_kind",
        "review",
        "inputs",
        "queue_candidate_beam",
        "evaluation_options",
        "expected_exit_code",
        "assertions",
    }
)


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


def _evaluation_options(case, catalog_version):
    if catalog_version == "1":
        if "evaluation_options" in case:
            raise ValueError(
                "Acceptance catalog version 1 does not define evaluation_options"
            )
        return {key: False for key in EVALUATION_OPTION_KEYS}

    options = case.get("evaluation_options")
    if not isinstance(options, dict) or set(options) != EVALUATION_OPTION_KEY_SET:
        raise ValueError(
            "Catalog v2 evaluation_options must contain exactly "
            "queue_common, queue_continuum and queue_line"
        )
    if any(type(options[key]) is not bool for key in EVALUATION_OPTION_KEYS):
        raise ValueError("Catalog v2 evaluation options must be JSON booleans")
    return {key: options[key] for key in EVALUATION_OPTION_KEYS}


def _evaluation_flags(options):
    return tuple(
        flag for key, flag in EVALUATION_OPTION_FLAGS if options[key]
    )


def _effective_evaluation_configuration(options):
    return {
        "nominal_conversion": None,
        "queue_common": (
            options["queue_common"]
            or options["queue_continuum"]
            or options["queue_line"]
        ),
        "queue_continuum": options["queue_continuum"],
        "queue_line": options["queue_line"],
    }


def _validate_evaluation_request(request_path, options):
    if not any(options.values()):
        return

    document = read_json(request_path)
    try:
        selected = document["search_options"]["sources"]
        intents = document["request"]["intents"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "Acceptance request must declare search sources and intents"
        ) from exc

    if not isinstance(selected, list) or not all(
        isinstance(value, str) for value in selected
    ):
        raise ValueError("Acceptance request sources must be a list of strings")
    if not isinstance(intents, list) or not all(
        isinstance(value, str) for value in intents
    ):
        raise ValueError("Acceptance request intents must be a list of strings")
    if "QUEUE" not in selected:
        raise ValueError("Queue evaluation options require QUEUE source selection")
    if options["queue_continuum"] and "CONTINUUM" not in intents:
        raise ValueError(
            "queue_continuum acceptance option requires CONTINUUM intent"
        )
    if options["queue_line"] and "LINE" not in intents:
        raise ValueError("queue_line acceptance option requires LINE intent")


def load_catalog(path):
    path = Path(path).resolve()
    catalog = read_json(path)
    if not isinstance(catalog, dict):
        raise ValueError("Acceptance catalog must be a JSON object")
    version = catalog.get("catalog_version")
    if version not in CATALOG_VERSIONS or not catalog.get("cases"):
        raise ValueError("Expected nonempty acceptance catalog version 1 or 2")
    if version == "2" and set(catalog) != {"catalog_version", "cases"}:
        raise ValueError(
            "Catalog v2 top level must contain exactly catalog_version and cases"
        )
    seen, loaded = set(), []
    for case in catalog["cases"]:
        if not isinstance(case, dict):
            raise ValueError("Acceptance cases must be JSON objects")
        if version == "2" and set(case) != V2_CASE_KEYS:
            raise ValueError(
                "Catalog v2 case keys must match the versioned case contract"
            )
        evaluation_options = _evaluation_options(case, version)
        if version == "2" and type(case["queue_candidate_beam"]) is not bool:
            raise ValueError(
                "Catalog v2 queue_candidate_beam must be a JSON boolean"
            )
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
        if version == "2":
            _validate_evaluation_request(inputs["request"], evaluation_options)
        # Verify every captured response before any report directory is created.
        if "archive_replay" in inputs:
            from alma_duplicate.clients.archive_replay import RecordedArchiveClient

            RecordedArchiveClient(inputs["archive_replay"])
        loaded.append((case, inputs, evaluation_options))
    return catalog, loaded


def run_catalog(catalog_path, output):
    catalog, loaded = load_catalog(catalog_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for case, inputs, evaluation_options in loaded:
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
        args.extend(_evaluation_flags(evaluation_options))
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
            if catalog["catalog_version"] == "2":
                expected_configuration = _effective_evaluation_configuration(
                    evaluation_options
                )
                actual_configuration = document.get("evaluation_configuration")
                if actual_configuration != expected_configuration:
                    differences.append(
                        {
                            "path": ["report", "evaluation_configuration"],
                            "expected": expected_configuration,
                            "actual": actual_configuration,
                            "reference": (
                                "Catalog v2 requested-to-effective "
                                "evaluation configuration"
                            ),
                        }
                    )
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
            "evaluation_options": evaluation_options,
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
        "acceptance_run_version": "2",
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
