# Persistent reports without sign-in

The default local browser uses temporary storage. To retain single-target reports
and completed batch overviews across service restarts, enable browser-scoped
database storage on a deployment that uses local mode.

Install the database dependencies with
`python -m pip install -e '.[ui,persistence]'`. Supply these settings through
the server environment:

| Setting | Value |
| --- | --- |
| `ALMA_AUTH_MODE` | `local` |
| `ALMA_REPORT_STORAGE` | `database` |
| `ALMA_DATABASE_URL` | The application's `postgresql+psycopg://` connection URL |
| `ALMA_ARTIFACT_ROOT` | A persistent, service-owned directory outside any served static directory |
| `ALMA_BROWSER_SESSION_SECRET` | Stable, independently generated secret of at least 32 characters |
| `ALMA_BROWSER_COOKIE_SECURE` | Defaults to `1` for HTTPS. Use `0` only for loopback HTTP development. |

Run `python -m alembic upgrade head` before starting Flask. The migration adds
browser-scoped metadata tables. PostgreSQL stores report and batch metadata while
the artifact directory stores immutable report files. Preserve both across
restarts. Use the same session secret and artifact directory on every instance
serving this database.

Each browser receives a signed, HttpOnly cookie. A digest of its opaque owner
token scopes every saved report and batch lookup. A shared URL grants no access
to another browser. The same browser profile can reopen its links while its
cookie remains valid. Clearing the cookie, changing the session secret, or
letting the cookie expire removes access from that browser. There is no
account-based recovery or cross-device access. In database mode, **Existing
reports** lists saved standalone reports and completed batches for that
browser. Use **Older reports** to reach earlier assessments. Individual batch
checks are available from their batch overview.
Each older page starts after the last entry already shown in each list, so
newer submissions do not shift that boundary. **Newest reports** returns to
the first page and includes the latest submissions. Older-page links are
signed for the current browser and preserve their page boundary if an operator
removes the report or batch that supplied it.

New reports retain the links between Archive and Queue branches, paired
scientific purposes, and notices for branches that could not complete. Older
reports can still use any navigation information retained in the browser
session.

Completed batches persist as a whole after execution. Uploaded forms and
in-progress assessments remain process-local and are interrupted by a restart.
Database mode uses the existing report-size limit during staging. Saved files
and metadata accumulate until the deployment operator removes them. Plan
storage and backups accordingly.

## Local trial on macOS

For a fresh trial on a Mac with Homebrew, install and start PostgreSQL 16.
The commands use the macOS user that initialized the Homebrew database cluster.
If you already have a local PostgreSQL installation, use it and create the
trial database there.

```bash
brew install postgresql@16
brew services start postgresql@16
pg_bin="$(brew --prefix postgresql@16)/bin"
"$pg_bin/createdb" alma_reuse_trial
"$pg_bin/psql" -d alma_reuse_trial -c 'SELECT current_database();'
```

Create the database once. From the repository root, using the Python environment
from the README quick start, install the persistence dependencies and configure
the trial. Keep the session key file for future launches and keep it outside the
repository.

```bash
python -m pip install -e '.[ui,persistence]'

trial_dir="$HOME/.local/share/alma-reuse-trial"
mkdir -p "$trial_dir/artifacts"
if [ ! -s "$trial_dir/session-key" ]; then
  (umask 077 && python -c 'import secrets; print(secrets.token_hex(32))' > "$trial_dir/session-key")
fi

export ALMA_AUTH_MODE=local
export ALMA_REPORT_STORAGE=database
export ALMA_DATABASE_URL='postgresql+psycopg:///alma_reuse_trial'
export ALMA_ARTIFACT_ROOT="$trial_dir/artifacts"
export ALMA_BROWSER_SESSION_SECRET="$(cat "$trial_dir/session-key")"
export ALMA_BROWSER_COOKIE_SECURE=0

python -m alembic upgrade head
python -m alembic current
```

After the migration succeeds, use the README quick-start source settings and
Flask command in the same terminal. Open
[Existing reports](http://127.0.0.1:5051/reports) in your browser. The cookie
setting above is for loopback HTTP. For a shared trial, provide a hosted HTTPS
URL and use `ALMA_BROWSER_COOKIE_SECURE=1` on the server. PostgreSQL stays on
the server side, and each visitor uses their own browser profile.

## Reuse settings from a saved report

1. In **Existing reports**, choose **Reuse settings** beside a saved assessment.
2. Review the restored inputs. For Multi-source or Mosaic, review the restored
   source list or OT pointings. You can replace the file before validating.
3. Choose **Validate input**, then **Run assessment** when ready. The new
   assessment receives its own report or batch ID. **View original assessment**
   in the draft opens the original result.

Reuse supports Legacy and V2 Single Pointing, Multi-source with its original
CSV or TXT, and Mosaic with its original OT pointings. Older reports without
saved input snapshots, preloaded reports, and reports in temporary mode are
view-only in **Existing reports**.

Saved inputs and original uploads survive restarts with the database, artifact
directory, and browser cookie. An opened draft lasts 30 minutes by default
and is held by the web process that created it. After expiry or a restart,
return to **Existing reports** and create a fresh draft. Access uses the same
browser profile and cookie as the original report.

See [Assessment input snapshots](assessment_input_snapshot.md) for the input
contract, upload integrity checks, and draft lifetime configuration.

## Report management storage

Migration `0006_browser_assessment_trash` adds a browser-owned trash record
for each batch or standalone assessment placed in trash. All reports generated
by a new standalone submission share one group identifier. For older
standalone reports, the migration groups reports with a shared input snapshot.
Reports without a durable grouping identifier are treated individually.

A trash record hides the assessment and its branches from normal history,
report access, downloads, and new reuse requests. The database rows and
artifacts are retained. Database mode provides CSRF-protected POST endpoints
for moving browser-owned assessments to trash and restoring them. Moving
a batch always applies to its child reports. Repeated requests leave the
existing trash timestamp and retention deadline intact if already trashed.
The planned retention defaults to seven days and can be configured with
`ALMA_REPORT_TRASH_RETENTION_DAYS`. Each entry keeps the deadline assigned
when it entered Trash. **Trash** shows that deadline in UTC. An entry can
still be restored while it is present, including after its deadline if the
operator's scheduled cleanup has yet to process it.

In **Existing reports**, choose **Move to trash** next to an assessment.
Open **Trash** from the same page, then choose **Restore** to return the
assessment and its reports to the history. Moving a report to trash keeps
its saved files on disk.

Migration `0007_browser_artifact_cleanup` adds the persistent file cleanup
queue. In database mode, operators can drain one batch with
`python -m flask --app alma_duplicate.ui.app:create_app cleanup-browser-artifacts`.
Files with database references and failed removals remain queued for another
run. The command only processes explicitly queued file paths. Moving a report
to trash does not enqueue its files.

The permanent-delete endpoint accepts only an assessment that is already in
the current browser's trash. It removes the assessment, child report records,
and unshared input snapshots, and enqueues candidate files in the same
transaction. A failed transaction leaves the trash entry intact. Physical
space is reclaimed by the cleanup command after reference checks.
In **Trash**, choose **Delete permanently**, review the assessment and its
deletion time, then choose **Delete permanently** on the confirmation page.
**Cancel** returns to Trash with the assessment still available to restore.

### Scheduled cleanup

To enforce retention, schedule these two commands in order using the same
database and artifact directory as the web app. Run them as the application
service user.

```bash
python -m flask --app alma_duplicate.ui.app:create_app purge-expired-browser-assessments
python -m flask --app alma_duplicate.ui.app:create_app cleanup-browser-artifacts
```

The first command processes up to 100 due assessments by default and
rechecks each deadline in the same transaction that removes the assessment.
If a browser restores an assessment before that transaction takes the lock,
the command skips it. Moving the restored assessment back to Trash starts
a fresh retention period.
The second processes up to 100 queued file paths. Each command supports
`--limit`. The application itself does not schedule these commands.
