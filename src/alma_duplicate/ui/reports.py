"""Read-only, startup-bound backend report artifacts."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from alma_duplicate.reporting import report_json_text
from alma_duplicate.report_inspection import inspect_report


@dataclass(frozen=True)
class ReportArtifact:
    name: str
    raw: bytes
    document: dict
    inspection: dict
    inspection_bytes: bytes
    sha256: str


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def load_reports(directory):
    """Load only immediate case/report.json files from an operator-selected root.

    No browser-supplied paths, recursive discovery, writes or source access.
    Fail startup for malformed reports rather than presenting an empty result.
    """
    if directory is None:
        return {}
    root = Path(directory)
    if not root.is_dir():
        raise ValueError("UI report directory does not exist")
    result = {}
    for path in sorted(root.glob("*/report.json")):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("UI reports must not be symbolic links")
        raw = path.read_bytes()
        try:
            document = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
            inspection = inspect_report(document, inspection_version="3")
            # Also reject overflowed numeric literals, without changing original bytes.
            report_json_text(document)
            for context in document["context_evaluations"]:
                for field in ("reference", "criteria", "branches", "line_pairs"):
                    if field not in context:
                        raise ValueError(f"Missing context field: {field}")
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ValueError(f"Invalid UI report: {path.parent.name}: {exc}") from exc
        key = str(len(result) + 1)
        result[key] = ReportArtifact(
            path.parent.name, raw, document, inspection,
            report_json_text(inspection).encode("utf-8"), hashlib.sha256(raw).hexdigest(),
        )
    return result
