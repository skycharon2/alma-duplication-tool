# Multi-source Single Pointing development

Reviewed 2026-11-13. **Steps 1–3 implemented; steps 4–6 are planned.**
This is a batch of independent fixed ICRS targets using shared scientific input.
It is not a Mosaic, an ALMA scheduling validator, or a new duplication rule.

## Review baseline and decision

The supplied two feature proposals fit the existing architecture with the
corrections below. Local commit `5b9782502e744fb9d5933bc95ea26e1567e0f4cc`
and GitHub main merge `79ad7c20e04f836064536a3ab844e0a6d06dee6b` have the same
Git tree `b88b440851ccb694b73e601e759f0d40e9a5b5eb`.
The review followed README, status, roadmap, architecture, request/frequency and
report contracts, the source parser package, request validation, separated input,
browser form execution, Queue pinning and report storage/navigation code. It is
not an independent scientific audit of every rule or historical experiment.

- Keep each request `FIXED` / `SINGLE_POINTING`; never combine target evidence.
  Candidate Mosaic comparisons already available in Single Pointing remain usable.
- Reuse `BrowserAssessment.pin_queue_for_submission()` once for the entire batch,
  then reuse its returned runner for every target and purpose. This already
  freezes snapshot bytes or acquisition failure; a second snapshot facility is
  unnecessary. Live Archive queries are sequential, not an atomic Archive snapshot.
- Reuse coordinate validation, scientific request validation, assessment dispatch,
  existing report versions and visualization. No scientific method changes.
- Preserve the original frequency reference. SKY is not shifted; REST uses each
  source's z. Missing z stays missing, never zero or a leftover shared value.
  Legacy, separated V1/V2 and submitted-observation paths need explicit handling:
  `separated_setup_input.py` accepts local `source_redshift` on LINE entries.
  Clear/replace these overrides as well as the shared redshift. Do not preconvert
  all frequencies or silently reuse candidate-side frequency evidence.
- Browser run-readiness and backend partial-evidence validation differ. Show a
  source's missing REST redshift at preflight; do not fabricate a successful run.
  Test the intended readiness policy against the existing standalone browser.
- `RunStore` is temporary disk storage with a process-local index, age, count
  (default 20) and byte limits. A batch manifest must share that lifetime.
  Persistent restart recovery/multi-user ownership is a separate project.
  Five targets can create ten purpose reports; this alone does not guarantee
  they fit the byte budget. Preserve completed siblings if another fails, and
  expose evicted/expired/missing reports explicitly.
- Execution state, source completeness and scientific outcomes are separate axes.
  There is no whole-batch Duplicate/Not Duplicate verdict. An empty or failed
  query never proves absence of duplication.

The official [Archive Target List help](https://help.almascience.org/kb/articles/can-i-search-for-a-list-of-sources-at-the-same-time)
describes a list of names or positions for retrieval. The four-column import is
an application contract, not that Archive format or a native OT export.
[Science Goal restrictions](https://help.almascience.org/kb/articles/how-many-pointings-can-my-proposal-contain)
require shared parameters including receiver band. A batch sharing REST input
can span bands after redshift conversion; do not label it an executable SG.
[Duplication guidance](https://almascience.eso.org/proposing/duplications) requires
checking both Archive and Queue. The dynamic AQ page itself does not specify
batch scientific assessment semantics.

## Step 1: implemented source-list contract

`alma_duplicate.parsers.source_list.parse_source_list(raw, format='csv',
max_sources=5)` accepts bytes and returns a JSON-compatible preview. It reads no
files, resolves no source names and calls no Archive/Queue service.

- UTF-8, optional BOM; LF or CRLF; maximum 100,000 input bytes.
- Explicit `csv` or `txt` format, not guessed from coordinate punctuation.
- Required header `name,ra,dec`; optional `redshift`; case-insensitive, any order.
  Duplicate, unknown or missing headers fail. TXT uses whitespace and supports
  quoted names. CSV supports quoted commas. One target per physical line;
  multiline quoted records are unsupported.
- Empty lines and full-line `#` comments are ignored; inline comments are not.
  For TXT with the redshift header, use `""` for a missing value. Alternatively
  omit the redshift column entirely when no targets supply it.
- Decimal RA/Dec mean degrees. Colon RA means HMS; colon Dec means DMS.
  Reuse `validate_preview_position()` so range checks match standalone requests:
  RA in [0,360), Dec in [-90,90], no silent wrapping. Frame is explicitly ICRS
  by this import contract; no epoch/frame transformation or coordinate lookup.
- Supplied z must be finite and greater than -1, also representable within the
  downstream numeric validator's range. Zero and negative z > -1 are accepted.
  Preserve decimal text for request construction; missing is `None`.
- Each physical row has a local `source_id` (`line-N`), original line number,
  raw line, original fields, normalized coordinates, redshift and issues.
  IDs are stable for the same file; editing/reordering a file creates a new
  preview. Global identity is `(batch_id, source_id)`, not name or coordinates.
- Preserve duplicate names and coordinates as independent rows, with warnings.
- File/encoding/header/limit failures raise `ValueError`. Row failures remain in
  the ordered preview with ERROR diagnostics and `is_valid=False`. Reject the
  batch preflight until corrected; never silently run just the valid subset.
- Default limit is five input rows, including malformed rows. The parser accepts
  an explicit alternative limit; browser v1 will keep five. No truncation.
- Record schema version `source_list_1` and SHA-256 of the exact uploaded bytes.
  `raw_text` is decoded text (BOM removed); the hash identifies original bytes.

The [five-target CSV](../tests/fixtures/source_list/five_targets.csv) and
[TXT](../tests/fixtures/source_list/five_targets.txt) transcribe the supplied
proposal. They are engineering examples, not verified astrophysical metadata.
The actual original Sebastien TXT was not supplied; this TXT is a documented
supported format, not a claim of compatibility with an unseen file.

## Step 2: independent request generation and offline preflight

`batch_request.build_batch_requests(shared_document, source_bytes, format='csv')`
returns `batch_requests_1`, the upload hash and ordered `source` / `document`
children. It parses the original bytes through the step 1 contract and rejects
any row errors before expansion. Fixed Single Pointing scope is required;
Mosaic, Solar and moving-target inputs are rejected rather than reinterpreted.

Each child is a deep copy. Only target identity, position and source-dependent
redshift fields change. Coordinates retain the uploaded spelling and explicit
DEG/HMS/DMS formats, so standalone coordinate validation sees the original
input precision. Search options, frequency references, units, widths, RMS,
physical SPW links and scientific setup identifiers remain unchanged. Source
identity stays outside the scientific request. Repeated names/positions remain
separate children.

The uploaded z replaces the shared top-level z. Separated V1/V2 LINE overrides
and V2 continuum overrides are removed so both purposes inherit the target's z.
Missing upload z removes every old override; it cannot fall back to a value in
the shared form. No REST-to-SKY calculation is performed by the builder.
Existing scientific preparation owns that calculation, and SKY remains SKY.
Unknown contracts and malformed local-override containers are rejected.

`ui.batch_requests.prepare_batch_form(values, rows, source_bytes, ...)` builds
the shared document using the existing form mapper, expands the sources, and
runs each child through `validate_document_for_browser()`. That helper is the
unchanged validation portion extracted from `validate_form()`; standalone
field-binding diagnostics remain in `validate_form()`. No network, Queue pinning,
assessment or report storage occurs during preflight.

All children retain their validation results, including invalid scientific
inputs. Batch `is_valid` and `can_search` require every child to satisfy the
corresponding existing validator property; callers must inspect both before
execution. `require_line_complete=True` applies the standalone Run checks.
Missing LINE REST z blocks Run, while a missing continuum REST z follows the
existing partial-evidence policy. V2 keeps the current one-LINE-configuration
browser restriction. Separated V1 documents can be generated for inspection,
but their existing execution gate is not bypassed. A successful build alone
does not establish scientific readiness.

The wire builder returns JSON-compatible data. The browser preflight result
also contains typed request-validation objects and is not the future manifest
serialization format. Purpose splitting, per-target execution, run IDs and
batch persistence belong to subsequent steps.

## Step 3: batch manifests and child-report lifecycle

Every `RunStore` owns `batches`, a `BatchStore` with small process-local JSON
manifests. Large report artifacts remain exclusively in the existing temporary
run directories. No second copy of scientific reports is made. The manifest is
not persistent across process restart and does not add a database.

The interface provides:

- `create(owner, shared_setup, sources, input_sha256, purposes)` reserves a batch
  with ordered source records and explicit LINE/CONTINUUM slots. It copies all
  input data, requires unique source IDs (names may repeat), and preserves the
  uploaded file hash and shared setup.
- `update(...)` records RUNNING, COMPLETED with a saved run ID, or FAILED with an
  optional bounded error message. PENDING can transition directly to a terminal
  state. Terminal records cannot be replaced; an identical repeated completion
  is idempotent. Retry requires a later explicit design.
- `get(batch_id, owner)` returns a detached JSON-compatible `batch_manifest_1`
  snapshot. Each child records execution state separately from current report
  availability: AVAILABLE, EVICTED, EXPIRED, CLOSED, OTHER_SESSION, UNKNOWN, or
  NO_REPORT as supplied by the existing run lifecycle. `execution_complete`
  only means all branches reached a terminal execution state, including failure.
- `lookup_run(run_id, owner)` resolves the batch/source/purpose navigation context.
  A report can belong to only one batch branch. Only available saved reports can
  initially be attached. The orchestrator remains responsible for passing the
  report produced by the corresponding source/purpose request.
- `summaries(explicit_batch_ids, owner)` filters and deduplicates the caller's
  history; it never enumerates another browser's batches. Owner tokens provide
  browser scope separation, not a new authentication service. Route wiring and
  cookie handling remain in step 5.

Defaults are 20 batch records and a 1,000,000-byte serialized-manifest budget,
separate from the report-file byte/count budget. `RunStore` accepts
`max_batches` and `max_batch_bytes` overrides. Both sizes and counts are bounded;
failed serialization or updates publish no partial state. New batch insertion
can evict the oldest finished batches; active batches are protected from capacity
eviction. If protected records consume the budget, insertion fails explicitly.
An oversized update fails without evicting siblings or altering the old record.

Batch age uses the same maximum age and monotonic clock as its RunStore, anchored
at batch creation. Reports keep their own publication-based expiry. Thus the
parent can expire before a later child; removing a manifest removes its reverse
links but does not delete otherwise valid report artifacts or interrupt download
leases. Reports evicted while a parent survives remain listed as unavailable.
Old run removal reasons may eventually become UNKNOWN under the existing bounded
notice policy. No unavailable report is converted into a scientific no-match.

`RunStore.prune()` also prunes batch manifests; `RunStore.close()` closes both
stores. A batch lock serializes mutations and reverse-index publication. Run
locks are released before acquiring the batch lock to avoid lock-order cycles.
The existing browser finalizer and per-request pruning therefore cover batch
state without enabling any new routes or executing assessments.

## Remaining increments and acceptance

| Step | Deliverable | Exit gate |
| --- | --- | --- |
| 1 (implemented) | Parser, fixtures, diagnostics | Numerical coordinates, z, identity, malformed inputs and limits tested offline |
| 2 (implemented) | Shared input → independent validated requests | Batch/standalone equivalence for Legacy and V2, LINE/CONTINUUM/both, REST/SKY, absent z, window overrides; shared input never mutated |
| 3 (implemented) | Batch manifest and child report lifecycle | Ordered source/purpose/run mapping, reverse lookup, expiry/eviction, byte/count limits and scoped history; no false persistence promise |
| 4 | Serial orchestration using existing assessment | One pinned Queue snapshot across all children; source/purpose failures isolated; fixed replay parity with standalone; progress per target; duplicate submission guarded |
| 5 | `/proposed/batch`, preview and `/batches/<batch_id>` | Reuse shared form fields, preflight all rows, preserve inputs on errors; validation performs no queries; manifest JSON download |
| 6 | Existing text/explorer batch navigation | Back/previous/next and purpose switch retain identity; failed/expired children navigable as status; standalone URLs, filtering, pagination and downloads unchanged |

Storage precedes orchestration so execution does not accumulate ad hoc session
URL lists. Steps are reviewable increments, not a requirement to make exactly
six commits. The first browser release needs all six.

Data relationship: `BatchRecord -> ordered SourceRecord -> purpose/run_id`.
Only batch IDs belong in browser history; server storage owns the child mapping
and reverse lookup. Keep `/runs/<run_id>`, `/runs/<run_id>/visualization` and
existing download URLs. New manifest URL:
`/batches/<batch_id>/download/manifest`. Do not substitute batch IDs for run IDs.
Summary counts come from saved reports without recomputing scientific rules.
Previous/next navigation preserves purpose where available; missing reports show
an explicit unavailable state instead of silently selecting a different purpose.

ZIP export, retry, filtering, TAP concurrency, moving targets, name resolution
and persistent storage are deferred. Batch/standalone parity is tested against
fixed source inputs, with only documented time/identity metadata normalized;
sequential live results cannot guarantee identical source state.

## Step 1 verification (2026-11-13)

Executed with the existing `alma-duplication` Python environment:

```sh
python -m pytest -q tests/unit/test_source_list.py tests/unit/test_ot_pointings.py tests/unit/test_proposed_observation.py tests/ui/test_proposed.py tests/ui/test_runs.py
python -m ruff check --select F src tests examples
git diff --check
```

217 tests passed; Pyflakes and diff whitespace checks passed. No live Archive or
Queue assessment was run, and no full-suite or end-to-end batch acceptance is
claimed. The new parser has no browser route yet.

## Step 2 verification (2026-11-13)

```sh
python -m pytest -q tests/ui tests/unit/test_source_list.py tests/unit/test_batch_request.py tests/unit/test_ot_pointings.py tests/unit/test_proposed_observation.py tests/integration/test_separated_setup_contract_step03ba.py tests/integration/test_continuum_frequency_preparation.py
python -m ruff check --select F src tests examples
python -m compileall -q src tests
git diff --check
```

913 tests passed, including the complete existing UI suite. Static checks,
compilation and diff whitespace checks passed. New tests compare child wire
documents and typed validation results against independently filled standalone
forms, verify exact prepared REST/SKY operands, enforce missing-redshift and V1
execution gates, and check input/sibling isolation. Preflight tests forbid
network calls, assessment and Queue pinning. This is offline input equivalence;
assessment-result parity is reserved for the orchestration increment.

## Step 3 verification (2026-11-13)

```sh
python -m pytest -q tests/ui tests/unit/test_source_list.py tests/unit/test_batch_request.py
python -m ruff check --select F src tests examples
python -m compileall -q src tests
git diff --check
```

761 tests passed, including all existing UI tests. Static checks, compilation
and diff whitespace checks passed. Lifecycle coverage uses actual offline saved
reports and an injected clock: ordered same-name sources, multiple purposes,
owner isolation, detached snapshots, failure isolation, terminal idempotency,
report eviction during an open download, report/parent expiry, store closure,
count/byte pressure, atomic budget failures and concurrent reference assignment.
No new network assessment, batch route or restart-persistence claim is included.
