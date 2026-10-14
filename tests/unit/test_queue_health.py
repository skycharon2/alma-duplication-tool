"""Offline operations checks: explicit approvals, missing jobs and failed checks."""

from datetime import UTC, datetime, timedelta
import json

import pytest

from alma_duplicate.cli import queue_health as health

NOW = datetime(2026, 10, 14, 11, tzinfo=UTC)
CHECKSUM_A = "a" * 64
CHECKSUM_B = "b" * 64


def _active():
    return {
        "source_id": "1" * 32, "run_id": "2" * 32,
        "revision": "3" * 32, "snapshot_sha256": CHECKSUM_A,
        "source_as_of": "2026-03-03", "activated_at": NOW.isoformat(),
    }


def _check(status="UNCHANGED", *, when=NOW, sha=CHECKSUM_A):
    return {"status": status, "checked_at": when.isoformat(),
            "snapshot_sha256": sha, "source_as_of": "2026-03-03",
            "activated": False}


def _registry(monkeypatch, current):
    class FakeRegistry:
        def __init__(self, root):
            self.root = root

        def current(self):
            return current

    monkeypatch.setattr(health, "QueueActiveRegistry", FakeRegistry)


def _events(tmp_path, *records):
    (tmp_path / "checks.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in records), encoding="utf-8")


def test_healthy_active_and_recent_check(monkeypatch, tmp_path):
    _registry(monkeypatch, _active())
    _events(tmp_path, _check("NEW_VALIDATED"), _check("UNCHANGED"))
    status = health.queue_health(tmp_path, now=NOW + timedelta(hours=1))
    assert status["status"] == "OK"
    assert status["alerts"] == []
    assert status["active"]["source_as_of"] == "2026-03-03"
    assert status["last_successful_check_at"] == NOW.isoformat()


def test_pending_review_survives_unchanged_rechecks(monkeypatch, tmp_path):
    _registry(monkeypatch, _active())
    _events(tmp_path, _check("NEW_VALIDATED", sha=CHECKSUM_B),
            _check("UNCHANGED", sha=CHECKSUM_B))
    status = health.queue_health(tmp_path, now=NOW)
    assert status["status"] == "WARNING"
    assert status["alerts"] == ["CANDIDATE_AWAITING_APPROVAL"]
    assert status["candidate_pending_approval"] is True
    assert status["active"]["snapshot_sha256"] == CHECKSUM_A


def test_no_active_or_checks_reports_critical(monkeypatch, tmp_path):
    _registry(monkeypatch, None)
    status = health.queue_health(tmp_path, now=NOW)
    assert status["status"] == "CRITICAL"
    assert status["alerts"] == ["NO_ACTIVE_SNAPSHOT", "NO_CHECK_HISTORY"]


def test_old_or_failed_check_is_not_confused_with_old_source_date(monkeypatch, tmp_path):
    _registry(monkeypatch, _active())
    _events(tmp_path, _check(when=NOW - timedelta(days=3)))
    result = health.queue_health(tmp_path, now=NOW)
    assert "CHECK_OVERDUE" in result["alerts"]
    _events(tmp_path, _check(), _check("DOWNLOAD_FAILED"))
    result = health.queue_health(tmp_path, now=NOW)
    assert result["status"] == "CRITICAL"
    assert result["last_successful_check_at"] == NOW.isoformat()
    assert "LAST_CHECK_UNSUCCESSFUL" in result["alerts"]
    assert result["active"]["source_as_of"] == "2026-03-03"


def test_log_symlinks_corruption_and_duplicate_keys_fail_closed(monkeypatch, tmp_path):
    _registry(monkeypatch, _active())
    path = tmp_path / "checks.jsonl"
    target = tmp_path / "other.jsonl"
    target.write_text(json.dumps(_check()) + "\n")
    path.symlink_to(target)
    assert health.queue_health(tmp_path, now=NOW)["alerts"] == ["CHECK_LOG_INVALID"]
    path.unlink()
    path.write_text('{"status":"UNCHANGED","status":"NEW_VALIDATED","checked_at":"2026-10-14T11:00:00+00:00"}\n')
    assert health.queue_health(tmp_path, now=NOW)["alerts"] == ["CHECK_LOG_INVALID"]
    path.write_text(json.dumps(_check()).rstrip("}") + "\n")
    assert health.queue_health(tmp_path, now=NOW)["alerts"] == ["CHECK_LOG_INVALID"]


def test_future_timestamp_and_no_timezone_do_not_fake_health(monkeypatch, tmp_path):
    _registry(monkeypatch, _active())
    _events(tmp_path, _check(when=NOW + timedelta(hours=2)))
    assert "CHECK_TIMESTAMP_IN_FUTURE" in health.queue_health(tmp_path, now=NOW)["alerts"]
    bad = _check()
    bad["checked_at"] = NOW.replace(tzinfo=None).isoformat()
    _events(tmp_path, bad)
    assert "INVALID_CHECK_TIMESTAMP" in health.queue_health(tmp_path, now=NOW)["alerts"]


def test_cli_exit_code_and_json_are_monitor_friendly(monkeypatch, tmp_path, capsys):
    _registry(monkeypatch, _active())
    _events(tmp_path, _check(sha=CHECKSUM_B))
    original = health.queue_health
    monkeypatch.setattr(
        health, "queue_health",
        lambda store_root, *, max_check_age_hours: original(
            store_root, now=NOW, max_check_age_hours=max_check_age_hours),
    )
    assert health.main(["--store-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "WARNING"
    assert health.main(["--store-root", str(tmp_path), "--fail-on-warning"]) == 2
    capsys.readouterr()
    (tmp_path / "checks.jsonl").unlink()
    assert health.main(["--store-root", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "CRITICAL"


def test_rejects_invalid_cli_threshold(monkeypatch, tmp_path, capsys):
    _registry(monkeypatch, _active())
    assert health.main(["--store-root", str(tmp_path), "--max-check-age-hours", "0"]) == 2
    assert "max_check_age_hours" in capsys.readouterr().err
    with pytest.raises(ValueError):
        health.queue_health(tmp_path, now=NOW, max_check_age_hours=True)
