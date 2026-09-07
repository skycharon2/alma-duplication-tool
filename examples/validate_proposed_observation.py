"""Offline input-to-report demo; no candidate search or duplication verdict."""

from dataclasses import asdict
import json
from pathlib import Path
import sys

from alma_duplicate.request_validation import validate_proposed_observation


def main():
    path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).with_name("proposed_observation.json")
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = validate_proposed_observation(
        payload["request"], payload.get("search_options")
    )
    summary = {
        "is_valid": report.is_valid,
        "search_readiness": report.search_readiness.value,
        "issues": [asdict(issue) for issue in report.issues],
        "normalized_position": (
            asdict(report.request.position)
            if report.request and report.request.position
            else None
        ),
        "request_returned": report.request is not None,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report.is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
