# Persistence and authentication integration gate

Accepted locally on 2026-11-17 against PostgreSQL 16.16 and Dex 2.46.0.
This gate validates the persistence and authentication foundation before durable
workers or persistent Web submission are enabled. It is not acceptance of an
institutional identity provider or a production reverse proxy.

## Reproduction

Install the project with `.[persistence,auth,ui,test]`. Provision a disposable
PostgreSQL database and a Dex executable. Set `ALMA_TEST_DATABASE_URL` to an
explicit `postgresql+psycopg://...` URL whose database role may create schemas.
Never point acceptance runs at a production database or identity provider.

```sh
python -m pytest -q -rs tests/persistence
python -m pytest -q -rs
python examples/acceptance/persistence/oidc_gate.py --dex /absolute/path/to/dex
```

The last command starts a real Dex process and two independent HTTPS Flask
processes on temporary loopback ports. It creates two disposable users, a temporary
certificate trusted only by the test clients, a private artifact directory and a
unique `test_alma_gate_*` PostgreSQL schema. It terminates its own children and
removes its own schema and temporary files on success or failure. A forced kill
may require manual cleanup of those test resources. It does not start or stop the
caller-provided PostgreSQL service. Do not run Python with `-O`: assertions are
part of this executable acceptance check.

Provider and Web request logging is suppressed to avoid retaining authorization
codes. Output contains check descriptions and a report digest, never cookies,
credentials or tokens. TLS certificate verification remains enabled. The fixed
local test password is the fixture published in
[Dex local connector documentation](https://dexidp.io/docs/connectors/local/).

## Observed results

- SQLite plus actual PostgreSQL persistence suite: **52 passed, 0 skipped**.
- Complete regression suite with PostgreSQL enabled: **3704 passed, 12 skipped**.
- Real discovery, authorization-code exchange and JWKS token verification passed.
  The application uses S256 PKCE; login begins in Web process A and its callback
  is delivered to B using the same signed browser state.
- Both processes serve the authorized user's text report, visualization and exact
  report download. The second independently signed-in user receives 404 for each.
  The old batch submission page remains forbidden in authenticated mode.
- Restarting A preserves the authenticated session and the exact saved report
  bytes. Its new process ID is checked. Report-serving processes have assessment
  entry points replaced with failure guards: saved reads cannot recompute science.
- Logging out through B invalidates a copied pre-logout cookie when replayed to A.
- Signature, issuer, audience, nonce, expiry, invalid state, callback replay,
  session expiry, cookie flags and transaction rollback are covered by the
  persistence tests; the real-provider script complements those negative tests.

The 12 skips are intentional external inputs, not PostgreSQL omissions:

| Group | Count | Activation/input |
| --- | ---: | --- |
| `tests/live/test_archive_tap_smoke.py` | 3 | `--run-live` |
| `tests/live/test_case_beam_strategy_applicability.py` | 2 | `--run-live` |
| `tests/live/test_case_retrieval.py` | 4 | `--run-live` |
| `tests/acceptance/test_queue_csv_snapshot.py` | 1 | pinned `ALMA_QUEUE_CSV_SNAPSHOT` |
| `tests/acceptance/test_queue_mode_adapter_snapshot.py` | 1 | pinned `ALMA_QUEUE_CSV_SNAPSHOT` |
| `tests/acceptance/test_queue_mode_snapshot.py` | 1 | pinned `ALMA_QUEUE_CSV_SNAPSHOT` |

## Scientific equivalence

The fixed 15-case acceptance catalog was executed using both `e54100b` and
`abc4e38`, with the same checksum-validated input paths. Both passed their
reference assertions. Complete resulting JSON report documents were equal after
normalizing only the four execution timestamps already enumerated by
`tests/ui/test_cli_parity.py::normalized_times`. Input hashes, acquisition dates,
source diagnostics, assessment results and numerical values remained compared.
Per-case normalized digests are recorded in
[equivalence evidence](evidence/persistence_science_equivalence_2026-11-17.json).

This is equivalence for the catalog, not proof over all possible scientific inputs.
The Custom ownership and Galactic coordinate implementation files have no changes
between this scientific baseline and the accepted engineering tip. Their existing
regression tests are included in the full run. Previously documented uncertainty
about OT coordinate/grid parity remains unchanged.

## Commit boundaries and next step

The unpublished combined commit `18096c9` was preserved on
`backup/persistence-auth-combined-18096c9`, then separated into:

| Step | Commit | Independent cumulative persistence tests |
| --- | --- | ---: |
| 03 — schema and migrations | `c4168e7` | 9 passed |
| 04 — scoped repositories | `b0a3ecb` | 15 passed |
| 05 — immutable reports | `9dfe0b9` | 26 passed |
| 06 — authentication/authorization | `abc4e38` | 52 passed |

All these runs included PostgreSQL. The final tree of `abc4e38` is identical to
`18096c9`. No remote branch history was rewritten or pushed.

The next implementation is Commit 07: durable workers. Atomic claiming, lease
renewal, fencing under contention, crash recovery, global TAP/AQ budgets and
immutable per-batch Queue snapshots are not implemented or accepted by this gate.
Institutional IdP configuration and production HTTPS/proxy settings also remain
deployment-specific acceptance work.
