"""Shared strict JSON input contract for executable request CLIs."""

import json
from pathlib import Path


def _reject_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_request_document(path: Path):
    raw = Path(path).read_bytes()
    payload = json.loads(
        raw.decode("utf-8-sig"),
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )
    if not isinstance(payload, dict):
        raise ValueError("Request file must be a JSON object")
    if set(payload) != {"request", "search_options"}:
        raise ValueError("Expected exactly 'request' and 'search_options'")
    if not isinstance(payload["request"], dict):
        raise ValueError("'request' must be a JSON object")
    if not isinstance(payload["search_options"], dict):
        raise ValueError("'search_options' must be a JSON object")
    return raw, payload
