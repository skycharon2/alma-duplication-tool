"""Scheduled cleanup drains queued files even when trash expiry fails."""

import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / 'deploy/systemd/run-browser-cleanup.sh'


@pytest.mark.skipif(os.name != 'posix', reason='The systemd wrapper uses POSIX shell')
@pytest.mark.parametrize(('expire_status', 'cleanup_status', 'expected'), [
    (0, 0, 0),
    (4, 0, 4),
    (0, 5, 5),
    (4, 5, 4),
])
def test_cleanup_wrapper_runs_both_commands(tmp_path, expire_status, cleanup_status, expected):
    python = tmp_path / 'fake-python'
    python.write_text(
        """#!/bin/sh
printf '%s\n' "$*"
case "$5" in
    purge-expired-browser-assessments) exit "$EXPIRE_STATUS" ;;
    cleanup-browser-artifacts) exit "$CLEANUP_STATUS" ;;
    *) exit 99 ;;
esac
""",
        encoding='utf-8',
    )
    python.chmod(0o700)
    result = subprocess.run(
        ['sh', str(SCRIPT), str(python)],
        env=os.environ | {
            'EXPIRE_STATUS': str(expire_status),
            'CLEANUP_STATUS': str(cleanup_status),
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == expected, result.stderr
    assert result.stdout.splitlines() == [
        '-m flask --app alma_duplicate.ui.app:create_app purge-expired-browser-assessments',
        '-m flask --app alma_duplicate.ui.app:create_app cleanup-browser-artifacts',
    ]
