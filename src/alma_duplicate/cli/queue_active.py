"""Explicit Queue snapshot activation: python -m alma_duplicate.cli.queue_active."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from alma_duplicate.storage.queue_active import QueueActiveRegistry, QueueActiveError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read or manually select a validated Queue snapshot; no downloading or scheduling"
    )
    parser.add_argument("--store-root", type=Path,
                        default=Path("data/cache/queue-snapshots"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="read and verify active pointer")
    commands.add_parser("history", help="show recent activation history")
    activate = commands.add_parser("activate", help="manually approve validated source/run")
    activate.add_argument("--source-id", required=True)
    activate.add_argument("--run-id", required=True)
    activate.add_argument("--reason", required=True)
    activate.add_argument("--allow-same-date-change", action="store_true",
                          help="explicitly approve changed CSV bytes with same source-as-of date")
    rollback = commands.add_parser("rollback", help="reselect one prior activation by revision")
    rollback.add_argument("--revision", required=True)
    rollback.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    registry = QueueActiveRegistry(args.store_root)
    try:
        if args.command == "status":
            current = registry.current()
            result = {"status": "ACTIVE" if current else "NO_ACTIVE_SNAPSHOT",
                      "active": current}
        elif args.command == "history":
            current = registry.current()
            result = {"status": "OK", "active_revision": (
                current["revision"] if current else None),
                "recent_history": list(registry.history())}
        elif args.command == "activate":
            result = registry.activate(args.source_id, args.run_id,
                                       reason=args.reason,
                                       allow_same_date_change=args.allow_same_date_change)
        else:
            result = registry.rollback(args.revision, reason=args.reason)
    except (OSError, QueueActiveError) as exc:
        print(json.dumps({"status": "SELECTION_FAILED", "error": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
