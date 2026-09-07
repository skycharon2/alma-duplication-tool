from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
import os

import pytest

from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.parsers.queue_csv import parse_queue_csv_bytes
from tests.unit.test_queue_csv_client import FIXTURE_PATH

FIRST = datetime(2026, 9, 1, 12, tzinfo=UTC)
SECOND = FIRST + timedelta(days=7)
RETRIEVED = datetime(2026, 8, 31, 15, tzinfo=timezone(timedelta(hours=2)))


@pytest.mark.parametrize("retrieved", [None, RETRIEVED])
def test_reparse_changes_only_parse_time(tmp_path, retrieved):
    path = tmp_path / "queue_20990101.csv"
    path.write_bytes(FIXTURE_PATH.read_bytes())
    os.utime(path, (0, 0))
    first = QueueCsvClient(clock=lambda: FIRST).load(path, retrieved_at=retrieved)
    os.utime(path, (SECOND.timestamp(), SECOND.timestamp()))
    second = QueueCsvClient(clock=lambda: SECOND).load(path, retrieved_at=retrieved)
    assert first.snapshot.parsed_at == FIRST
    assert second.snapshot.parsed_at == SECOND
    assert first.snapshot.retrieved_at == second.snapshot.retrieved_at == retrieved
    assert first.snapshot.source_as_of == second.snapshot.source_as_of == date(2026, 3, 3)
    assert first.snapshot.snapshot_sha256 == second.snapshot.snapshot_sha256
    assert replace(first.snapshot, parsed_at=SECOND) == second.snapshot
    assert replace(first, snapshot=second.snapshot) == second


def test_legacy_capture_is_retained_without_reinterpretation():
    legacy = datetime(2020, 1, 1)  # Legacy timezone semantics also unknown.
    result = QueueCsvClient(clock=lambda: FIRST).parse_bytes(
        FIXTURE_PATH.read_bytes(), captured_at=legacy,
    )
    assert result.snapshot.captured_at == legacy
    assert result.snapshot.legacy_capture_status == "LEGACY_UNINTERPRETED"
    assert result.snapshot.retrieved_at is None
    assert result.snapshot.parsed_at == FIRST


def test_legacy_and_explicit_retrieval_are_separate_facts():
    result = QueueCsvClient(clock=lambda: SECOND).load(
        FIXTURE_PATH, captured_at=FIRST, retrieved_at=RETRIEVED,
    )
    assert result.snapshot.captured_at == FIRST
    assert result.snapshot.retrieved_at == RETRIEVED
    assert result.snapshot.retrieved_at.tzinfo == RETRIEVED.tzinfo
    assert result.snapshot.parsed_at == SECOND


@pytest.mark.parametrize("description, expected, status", [
    ("Queue as of 2026 March 3.", date(2026, 3, 3), "PARSED"),
    ("Queue as of 2026-03-03.", date(2026, 3, 3), "PARSED"),
    ("Queue as of 2026 February 30.", None, "INVALID"),
    ("Queue as of 2026-02-30.", None, "INVALID"),
    ("Queue as of 03/04/2026.", None, "UNRECOGNIZED"),
    ("Queue description without a date.", None, "MISSING"),
    ("Queue as of 2026 March 3. Revised as of 2026 March 4.", None, "AMBIGUOUS"),
])
def test_source_date_requires_supported_explicit_declaration(description, expected, status):
    original = FIXTURE_PATH.read_bytes()
    raw = description.encode() + b"\n" + original.split(b"\n", 1)[1]
    result = parse_queue_csv_bytes(raw, parsed_at=FIRST)
    assert result.is_complete
    assert result.snapshot.source_as_of == expected
    assert result.snapshot.source_as_of_status == status
    assert description in result.snapshot.description_raw
    if status not in {"MISSING"}:
        assert result.snapshot.source_as_of_raw is not None


@pytest.mark.parametrize("raw", [b"\xff", b"not a Queue CSV"])
def test_failed_parse_still_preserves_time_provenance(raw):
    result = QueueCsvClient(clock=lambda: FIRST).parse_bytes(raw, retrieved_at=RETRIEVED)
    assert not result.is_complete
    assert result.snapshot.parsed_at == FIRST
    assert result.snapshot.retrieved_at == RETRIEVED
    assert result.snapshot.source_as_of is None


def test_direct_parser_has_explicit_deterministic_parse_time():
    raw = FIXTURE_PATH.read_bytes()
    first = parse_queue_csv_bytes(raw, parsed_at=FIRST, retrieved_at=RETRIEVED)
    second = parse_queue_csv_bytes(raw, parsed_at=FIRST, retrieved_at=RETRIEVED)
    assert first == second
    assert first.snapshot.parser_version == "2"
    assert first.snapshot.provenance_version == "2"
    assert first.snapshot.source_url_kind == "SOURCE_PAGE"
    assert first.snapshot.legacy_capture_status == "NOT_PROVIDED"


@pytest.mark.parametrize("kind", [None, "SOURCE_PAGE", "DOWNLOAD_URL"])
def test_custom_url_kind_is_explicit_not_guessed(kind):
    result = QueueCsvClient(
        "https://example.invalid/queue.csv", source_url_kind=kind,
        clock=lambda: FIRST,
    ).load(FIXTURE_PATH)
    assert result.snapshot.source_url_kind == (kind or "UNSPECIFIED")


@pytest.mark.parametrize("argument", ["parsed_at", "retrieved_at"])
def test_new_timestamps_require_timezone(argument):
    with pytest.raises(ValueError, match=argument):
        parse_queue_csv_bytes(FIXTURE_PATH.read_bytes(), **{argument: datetime(2026, 1, 1)})


def test_invalid_url_kind_is_rejected():
    with pytest.raises(ValueError, match="source_url_kind"):
        QueueCsvClient(source_url_kind="guess")
