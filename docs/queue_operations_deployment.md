# PR4 — Scheduled Queue checks and service operations

PR4 completes the **operator-side** scheduled retrieval for PR1–PR3. It adds an
admin-only, read-only health CLI, Linux systemd timer/service examples, and a
loopback-only production browser service example. **It never changes
`current.json`**: a downloaded `NEW_VALIDATED` candidate must be reviewed and
explicitly activated through PR2. A check of today's URL is *not* evidence that
the scientific Queue was updated today. Archive TAP is a separate live source.

## Local validation (including a Mac developer laptop)

Install the existing project (`python -m pip install -e '.[ui,test]'`). On the
Mac, use the same persistent local root that PR2 and PR3 used:

```bash
python -m alma_duplicate.cli.queue_update --once \
  --store-root data/cache/queue-snapshots
python -m alma_duplicate.cli.queue_health \
  --store-root data/cache/queue-snapshots --max-check-age-hours 48
python -m alma_duplicate.cli.queue_active \
  --store-root data/cache/queue-snapshots status
python -m pytest -q tests/unit/test_queue_health.py
```

`queue_health` exits **0** for `OK` and `WARNING`, **2** for `CRITICAL` or bad
CLI parameters. Add `--fail-on-warning` to exit **2** when a newer, validated
snapshot awaits review. Machine output is JSON. The command does not trigger
network access, create a snapshot or change the active selection.

The check log is a bounded tail of PR1's append-only `checks.jsonl`; malformed
records and symlinked logs fail closed. These distinctions matter:

| Signal | Meaning |
| --- | --- |
| `OK` | Approved active pointer and recent successful check |
| `WARNING` / `CANDIDATE_AWAITING_APPROVAL` | Recent validated bytes differ from active snapshot; manual review needed |
| `NO_ACTIVE_SNAPSHOT` / `ACTIVE_SNAPSHOT_INVALID` | Missing or invalid approved selection (critical) |
| `NO_CHECK_HISTORY` / `CHECK_OVERDUE` | No evidence that scheduled checks run recently (critical) |
| `LAST_CHECK_UNSUCCESSFUL` | Latest download/validation attempt did not pass (critical); active source is not silently replaced |
| `CHECK_LOG_INVALID` | Operational check log cannot be trusted (critical) |

`source_as_of` may legitimately be older than the most recent `checked_at`.
The default 48-hour age threshold applies **only to check attempts**, not to
the scientific dataset date. The newest check record takes precedence even if
an earlier check succeeded. A `NEW_VALIDATED` or repeated `UNCHANGED` check
with a different SHA from the active snapshot is a pending-approval warning;
`UNCHANGED` does not imply it is already approved.

## Linux deployment reference (systemd)

These templates target a trusted Linux host, **not macOS launchd**. Review and
adapt the absolute paths and non-root service account before installation:

- code and venv: `/srv/alma-duplication-tool` and its `.venv`
- writable persistent snapshot store: `/var/lib/alma-duplication/queue-snapshots`
- service account: `alma` (non-root, permission to read code and write store)

For example, after the repository is checked out to `/srv/alma-duplication-tool`,
using a Python 3.11+ interpreter:

```bash
sudo useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin alma
sudo mkdir -p /var/lib/alma-duplication/queue-snapshots
sudo chown -R alma:alma /var/lib/alma-duplication
sudo chmod 700 /var/lib/alma-duplication /var/lib/alma-duplication/queue-snapshots
# As the service account, create a venv and install the checkout and Gunicorn.
# Ensure the code checkout and venv are readable/executable by alma.
# python3.11 -m venv /srv/alma-duplication-tool/.venv
# /srv/alma-duplication-tool/.venv/bin/pip install -e '.[ui]' gunicorn
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now alma-queue-update.timer alma-queue-health.timer
sudo systemctl list-timers 'alma-queue-*'
```

Create the `alma` user only if not already present. Set code/venv ownership
so installation does not require making source trees world-writable. Verify
that systemd `ReadWritePaths` and filesystem permissions allow **the same**
service account to write the store. For the first acquisition, run:

```bash
sudo systemctl start alma-queue-update.service
sudo journalctl -u alma-queue-update.service -n 70 --no-pager
```

After inspecting the candidate `source_id`, `run_id`, source date, SHA-256 and
parser warnings, manually activate with `queue_active activate --source-id
ACTUAL_SOURCE_ID --run-id ACTUAL_RUN_ID --reason '...review...'`, **as `alma`
and against the server's persistent store root**. Do not copy local Mac
`current.json` into production blindly: it references source and parse-run
evidence that must also be present and verified on the server.

Then enable the web service:

```bash
sudo systemctl enable --now alma-browser.service
sudo systemctl status alma-browser.service
curl -fsS http://127.0.0.1:5050/healthz
```

The browser binds **only** `127.0.0.1:5050`. Put it behind your institution's
HTTPS reverse proxy and working authentication/SSO and authorization rules.
Never expose the Flask development server, raw snapshot directory, the
approval CLI, or the unauthenticated loopback service on a public network.
Consult the institution's IT/security team before sharing the site with
colleagues. The sample enables live Archive and AQ; disable or configure them
if your deployment must remain Queue-only. A single Gunicorn worker is
intentional: PR3 run/report storage is process-local and does not yet support
multi-worker shared sessions. Restarts can expire temporary report links.

## Operational checks and approval runbook

```bash
sudo systemctl list-timers 'alma-queue-*'
sudo journalctl -u alma-queue-update.service -n 80 --no-pager
sudo journalctl -u alma-queue-health.service -n 80 --no-pager
sudo -u alma /srv/alma-duplication-tool/.venv/bin/python \
  -m alma_duplicate.cli.queue_health \
  --store-root /var/lib/alma-duplication/queue-snapshots
sudo -u alma /srv/alma-duplication-tool/.venv/bin/python \
  -m alma_duplicate.cli.queue_active \
  --store-root /var/lib/alma-duplication/queue-snapshots status
```

On `WARNING`, inspect newly validated source/run manifests and download
provenance; activate with the PR2 CLI only after scientific review. On `CRITICAL`,
review journal errors, network/DNS/TLS, disk capacity, store permissions and
`checks.jsonl`; preserve the previous approved snapshot. Review the stored
log before changing anything. `systemd` records nonzero update and health
service exit codes, but **does not itself send email or paging alerts**.
Connect failed units to your existing institutional monitoring/on-call system.
The timer does not guarantee execution while the host is off; `Persistent=true`
asks systemd to catch up after boot.

### Rollback

Read `queue_active history`, then run an explicit `queue_active rollback` with
a real previous revision and a recorded reason. Do not modify immutable source
manifests or hand-edit `current.json`. Keep the snapshot store on persistent
local storage with backups, restricted service-account permissions and a
recovery plan; these templates do not provision backups, SSO, TLS or storage.

### Scope and tests

```bash
python -m pytest -q tests/unit/test_queue_health.py
python -m pytest -q
python -m alma_duplicate.cli.acceptance \
  --catalog examples/acceptance/catalog.json \
  --output-dir reports/queue-pr4-acceptance
```

This PR adds no changes to scientific selection rules, report format, Flask
routes, PR1 downloader, PR2 active-pointer policy or PR3 pinned report sources.
It does not auto-publish newly downloaded Queue CSV bytes.
