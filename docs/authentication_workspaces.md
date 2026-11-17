# OIDC identity and personal workspaces — Phase 3, step 06

Authentication is opt-in. `AUTH_MODE=local` retains the existing single-process
research browser behavior. `AUTH_MODE=oidc` enables a separate authenticated
boundary; an unknown mode or incomplete configuration fails startup rather than
silently falling back to local mode. Optional dependencies are installed with:

```sh
python -m pip install -e '.[ui,persistence,auth]'
```

## Configuration

Supply the following through deployment secrets/configuration, not checked-in
files. The application factory also accepts the names without the `ALMA_` prefix.

| Environment variable | Meaning |
| --- | --- |
| `ALMA_AUTH_MODE` | `oidc` |
| `ALMA_AUTH_SESSION_SECRET` | Stable, securely generated secret of at least 32 characters |
| `ALMA_DATABASE_URL` | Explicit `postgresql+psycopg://` URL |
| `ALMA_ARTIFACT_ROOT` | Existing persistent artifact directory |
| `ALMA_OIDC_ISSUER` | Exact HTTPS issuer identifier |
| `ALMA_OIDC_METADATA_URL` | Optional HTTPS discovery URL; default issuer plus standard well-known path |
| `ALMA_OIDC_CLIENT_ID` | Registered confidential client identifier |
| `ALMA_OIDC_CLIENT_SECRET` | Provider-issued client secret |
| `ALMA_OIDC_REDIRECT_URI` | Fixed HTTPS application URL ending in `/auth/callback` |

Apply Alembic through `0002_auth_sessions` explicitly before enabling this mode.
No migration runs on application startup. Do not use the test-only injected engine
outside tests; production connections use the configured PostgreSQL URL.

Register the exact callback URL with the provider. The application uses Authlib's
OIDC authorization-code flow, state, nonce and PKCE S256; ID-token signature,
audience, issuer, nonce and expiry are validated. The issuer is pinned separately
from discovery. No email-based account linking is performed. Access, refresh and
ID tokens are not retained in the browser session after login.

HTTPS is required even when Flask sits behind a proxy. Configure only a trusted
proxy boundary to report the original request scheme; arbitrary forwarded headers
are not trusted by this implementation. The callback hostname is Flask's trusted
host, and cookies are Secure, HttpOnly, SameSite=Lax and host-only. The callback URL
is configuration, never constructed from an untrusted incoming Host or `next` URL.

## Sessions and workspace authorization

Verified `(issuer, subject)` identifies a user. Provisioning serializes on the user
row and reuses an owned personal workspace. Each login receives a random opaque
browser secret; the database stores only its SHA-256 digest, user, workspace and
expiry. Lifetime is at most eight hours and never beyond ID-token expiry. Each
protected request checks the database session and current workspace ownership.
A caller-supplied workspace ID, run ID or browser history is not authority.

Logout is POST-only with a session-bound CSRF token. It deletes the server-side
session before clearing the cookie, so replaying the old signed cookie cannot
restore access. A signed-out page avoids immediately restarting provider SSO.
Provider-wide logout is not implemented; the identity provider may retain its
own session. Expired database rows remain until a later cleanup policy removes
them, but they cannot authorize requests.

## Deliberate rollout boundary

Authenticated mode currently enables workspace landing, logout and authorized
persistent Run text, Queue, visualization and download routes. It installs the
workspace-aware SavedReport resolver automatically. Missing and foreign-workspace
reports return the same 404 response. Every protected route is denied by default;
static assets, OIDC entry/callback, signed-out page and health check are public.

The old temporary form submissions, Batch manifests, progress tokens and static
report directory are **not** exposed as a multi-user workflow. Those routes are
blocked in authenticated mode until the planned persistent Worker/Web integration.
Local mode is unchanged. This prevents a transitional deployment from attaching
formal identities to globally accessible process-local reports.

There is no team membership management, report sharing, identity-provider token
refresh, legacy browser-token migration or durable submission UI in this step.
The existing artifact root and database remain authoritative across restarts;
revocable session secrets also survive restart when the stable signing key is kept.

## Verification

`python -m pytest -q tests/persistence` includes locally signed RSA ID tokens
through the real Authlib callback parser, PKCE challenge/verifier correspondence,
invalid signature/issuer/audience/nonce/expiry, single-use state, session expiry,
logout revocation and old-cookie replay. Two independently signed-in users exercise
private text reports, visualization and all original downloads; changing a
client-side workspace field cannot grant access. Local prototype regression tests
remain unchanged.

These are offline provider simulations, not a login to a real institutional IdP.
PostgreSQL variants require `ALMA_TEST_DATABASE_URL` or the dedicated CI service.
Real IdP configuration, PostgreSQL concurrency, trusted-proxy HTTPS deployment and
operational access controls still require deployment acceptance before public use.

References: [Authlib Flask OIDC integration](https://docs.authlib.org/en/latest/oauth2/client/web/flask.html)
and [Authlib web client validation](https://docs.authlib.org/en/latest/oauth2/client/web/).
