"""Read-only Queue operations health check, suitable for local/host monitoring.

This command never downloads, parses, selects or modifies Queue evidence.
It observes PR1 checks.jsonl and PR2's validated active pointer. It is an
operator-only CLI; do not expose source diagnostics as a public web endpoint.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Callable

from alma_duplicate.storage.queue_active import QueueActiveError, QueueActiveRegistry

MAX_CHECK_LOG_BYTES = 256 * 1024
MAX_CHECK_LINE_BYTES = 16 * 1024
SUCCESS = frozenset({"NEW_VALIDATED", "UNCHANGED"})


class QueueHealthError(ValueError):
    """Untrusted or unreadable operational check log."""


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise QueueHealthError("duplicate key in Queue check record")
        result[key] = value
    return result


def _read_recent_checks(root: Path) -> tuple[dict | None, dict | None]:
    """Read a bounded complete-line suffix, rejecting corrupt recent records.

    The append-only PR1 updater records one JSON object per line. The suffix
    bounds memory even if the service has operated for years. A truncated first
    line is skipped; a truncated final line is a log-integrity error.
    """
    path = root / "checks.jsonl"
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        raise QueueHealthError("Queue check log cannot be opened safely") from exc
    try:
        size = os.fstat(fd).st_size
        offset = max(0, size - MAX_CHECK_LOG_BYTES)
        os.lseek(fd, offset, os.SEEK_SET)
        raw = os.read(fd, min(size, MAX_CHECK_LOG_BYTES))
    except OSError as exc:
        raise QueueHealthError("Queue check log cannot be read") from exc
    finally:
        os.close(fd)
    if offset:
        cut = raw.find(b"\n")
        if cut < 0:
            raise QueueHealthError("Queue check record exceeds scan limit")
        raw = raw[cut + 1:]
    if raw and not raw.endswith(b"\n"):
        raise QueueHealthError("incomplete final Queue check record")
    records = []
    for line in raw.splitlines():
        if not line.strip():
            raise QueueHealthError("blank Queue check record")
        if len(line) > MAX_CHECK_LINE_BYTES:
            raise QueueHealthError("oversized Queue check record")
        try:
            item = json.loads(line.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
        except (ValueError, UnicodeDecodeError) as exc:
            raise QueueHealthError("invalid Queue check JSON") from exc
        if (not isinstance(item, dict)
                or not isinstance(item.get("status"), str)
                or not isinstance(item.get("checked_at"), str)):
            raise QueueHealthError("invalid Queue check record fields")
        records.append(item)
    latest = records[-1] if records else None
    # An older successful check may be outside the bounded suffix, in which
    # case the value is intentionally unknown rather than inferred.
    successful = next((record for record in reversed(records)
                       if record["status"] in SUCCESS), None)
    return latest, successful


def _instant(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise QueueHealthError("invalid check timestamp") from exc
    if instant.utcoffset() is None:
        raise QueueHealthError("Queue check timestamp lacks timezone")
    return instant


def queue_health(
    store_root: str | Path,
    *,
    now: datetime | None = None,
    max_check_age_hours: int = 48,
    check_reader: Callable[[Path], tuple[dict | None, dict | None]] = _read_recent_checks,
) -> dict:
    """Summarize availability, verification cadence and approval backlog.

    A download check is never a claim of current scientific coverage. Pending
    validated bytes remain unselected until explicit PR2 administrator approval.
    """
    if type(max_check_age_hours) is not int or not 1 <= max_check_age_hours <= 8760:
        raise ValueError("max_check_age_hours must be an integer in 1..8760")
    now = now or datetime.now(UTC)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("health clock must be timezone-aware")
    root = Path(store_root)
    alerts = []
    result = {
        "status": "OK", "alerts": alerts,
        "active": None, "last_check": None,
        "last_successful_check_at": None,
        "candidate_pending_approval": False,
        "max_check_age_hours": max_check_age_hours,
        "observed_at": now.isoformat(),
    }
    active = None
    try:
        active = QueueActiveRegistry(root).current()
    except (QueueActiveError, OSError, ValueError) as exc:
        alerts.append("ACTIVE_SNAPSHOT_INVALID")
        result["active_error"] = str(exc)
    else:
        if active is None:
            alerts.append("NO_ACTIVE_SNAPSHOT")
        else:
            result["active"] = {
                field: active[field] for field in (
                    "source_id", "run_id", "revision", "snapshot_sha256",
                    "source_as_of", "activated_at",
                )
            }
    latest = successful = None
    try:
        latest, successful = check_reader(root)
    except (QueueHealthError, OSError, ValueError) as exc:
        alerts.append("CHECK_LOG_INVALID")
        result["check_error"] = str(exc)
    else:
        if successful is not None:
            result["last_successful_check_at"] = successful["checked_at"]
        if latest is None:
            alerts.append("NO_CHECK_HISTORY")
        else:
            result["last_check"] = {
                "status": latest["status"],
                "checked_at": latest["checked_at"],
                "snapshot_sha256": latest.get("snapshot_sha256"),
                "source_as_of": latest.get("source_as_of"),
            }
            if latest.get("error"):
                result["last_check"]["error"] = str(latest["error"])
            try:
                age = now - _instant(latest["checked_at"])
            except QueueHealthError:
                alerts.append("INVALID_CHECK_TIMESTAMP")
            else:
                if age < -timedelta(minutes=5):
                    alerts.append("CHECK_TIMESTAMP_IN_FUTURE")
                elif age > timedelta(hours=max_check_age_hours):
                    alerts.append("CHECK_OVERDUE")
            if latest["status"] not in SUCCESS:
                alerts.append("LAST_CHECK_UNSUCCESSFUL")
            # This includes repeated UNCHANGED checks of a candidate which
            # was validated earlier but still has not been selected.
            elif (active is not None and isinstance(latest.get("snapshot_sha256"), str)
                    and latest["snapshot_sha256"] != active["snapshot_sha256"]):
                alerts.append("CANDIDATE_AWAITING_APPROVAL")
                result["candidate_pending_approval"] = True

    warning_only = {"CANDIDATE_AWAITING_APPROVAL"}
    result["status"] = ("CRITICAL" if any(x not in warning_only for x in alerts)
                        else "WARNING" if alerts else "OK")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Queue operations health; no download or activation")
    parser.add_argument("--store-root", type=Path,
                        default=Path("data/cache/queue-snapshots"))
    parser.add_argument("--max-check-age-hours", type=int, default=48)
    parser.add_argument("--fail-on-warning", action="store_true",
                        help="treat a pending manual approval as a non-zero exit")
    args = parser.parse_args(argv)
    try:
        report = queue_health(args.store_root,
                              max_check_age_hours=args.max_check_age_hours)
    except ValueError as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 2 if report["status"] == "CRITICAL" or (
        args.fail_on_warning and report["status"] == "WARNING") else 0


if __name__ == "__main__":
    raise SystemExit(main())
