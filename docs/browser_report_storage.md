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
account-based recovery or cross-device access. The report index lists recent
items tracked by that browser.

Completed batches persist as a whole after execution. Uploaded forms and
in-progress assessments remain process-local and are interrupted by a restart.
Database mode uses the existing report-size limit during staging. Saved files
and metadata accumulate until the deployment operator removes them. Plan
storage and backups accordingly.
