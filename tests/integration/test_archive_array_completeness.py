"""Captured and live AQ must reject the same incomplete response evidence."""

import hashlib
import json

import pytest

from alma_duplicate.archive_array_evidence import load_archive_array_catalog
from alma_duplicate.clients.archive_aq_client import ArchiveAqClient, ArchiveAqError
from tests.unit.test_archive_aq_client import MEMBER, http_for, response


def capture(directory, payloads):
    """Write correct checksums so tests exercise completeness, not corruption."""
    entries = []
    for index, payload in enumerate(payloads):
        raw = json.dumps(payload).encode()
        name = f"response-{index}.json"
        (directory / name).write_bytes(raw)
        entries.append({
            "file": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "url": "https://almascience.eso.org/aq/service/api/search/observations/_search",
            "retrieved_at": "2026-10-16T00:00:00+00:00",
            "request_body": {"query": {"term": {"mous": MEMBER}}},
        })
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps(entries))
    return manifest


MISSING = object()


@pytest.mark.parametrize("path,value", [
    (("terminated_early",), True),
    (("terminated_early",), 0),
    (("terminated_early",), "false"),
    (("terminated_early",), None),
    (("timed_out",), True),
    (("timed_out",), MISSING),
    (("timed_out",), 0),
    (("timed_out",), "false"),
    (("timed_out",), None),
    (("_shards",), MISSING),
    (("_shards",), []),
    (("_shards", "failed"), MISSING),
    (("_shards", "failed"), 1),
    (("_shards", "failed"), -1),
    (("_shards", "failed"), False),
    (("_shards", "failed"), 0.0),
    (("_shards", "failed"), "0"),
    (("hits", "total"), []),
    (("hits", "total", "value"), MISSING),
    (("hits", "total", "value"), True),
    (("hits", "total", "value"), 1.0),
    (("hits", "total", "value"), "1"),
    (("hits", "total", "value"), -1),
    (("hits", "total", "value"), 0),
    (("hits", "total", "value"), 2),
    (("hits", "total", "relation"), MISSING),
    (("hits", "total", "relation"), "gte"),
    (("hits", "hits"), None),
    (("hits", "hits"), {}),
])
def test_incomplete_or_malformed_evidence_is_rejected_by_both_entries(tmp_path, path, value):
    payload = response()
    parent = payload
    for key in path[:-1]:
        parent = parent[key]
    if value is MISSING:
        del parent[path[-1]]
    else:
        parent[path[-1]] = value
    manifest = capture(tmp_path, [payload])

    with pytest.raises(ValueError):
        load_archive_array_catalog(manifest)
    with pytest.raises(ArchiveAqError) as error:
        ArchiveAqClient(request=http_for(payload)).fetch_members([MEMBER])
    assert error.value.code in {"INCOMPLETE", "RESPONSE_INVALID"}


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize("terminated_early", [MISSING, False])
def test_complete_empty_and_nonempty_responses_keep_provenance(tmp_path, empty, terminated_early):
    payload = response([] if empty else None)
    if terminated_early is not MISSING:
        payload["terminated_early"] = terminated_early
    manifest = capture(tmp_path, [payload])
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    captured = load_archive_array_catalog(manifest)
    live = ArchiveAqClient(request=http_for(payload)).fetch_members([MEMBER]).catalog
    assert len(captured.records) == len(live.records) == (0 if empty else 1)
    assert captured.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert captured.input_paths == (manifest.resolve(), (tmp_path / "response-0.json").resolve())
    for record in captured.records:
        assert record.response_sha256 == hashlib.sha256(original["response-0.json"]).hexdigest()
        assert record.member_ous_uid == MEMBER
        assert record.raw_label == "7m"
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == original


def test_early_termination_in_later_capture_rejects_whole_catalog(tmp_path):
    incomplete = response()
    incomplete["terminated_early"] = True
    manifest = capture(tmp_path, [response(), incomplete])
    with pytest.raises(ValueError, match="Incomplete"):
        load_archive_array_catalog(manifest)
