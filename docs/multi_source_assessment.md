# Multi-source Single Pointing development

Reviewed 2026-11-16. **Steps 1–6 implemented.**
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
serialization format. Purpose splitting and per-target execution are implemented in step 4; run IDs
and temporary batch manifests are owned by step 3. Browser integration remains
in subsequent steps.

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

## Step 4: serial execution and snapshot consistency

`ui.batch_assessment.execute_batch(values, rows, source_bytes, runner=...,
runs=..., owner=..., submission_token=..., format='csv', progress=None)` is a
synchronous orchestration entry. It returns a batch ID, including for partially
or entirely failed batches; callers inspect the manifest and individual reports.
It does not register routes, launch background workers or change scientific rules.

1. Copy form values and preflight the combined request for every source with
   the standalone Run completeness checks. Prepare each selected purpose using
   the same form mapper and revalidate each child before any source access.
   Invalid scientific inputs raise `BatchValidationError` with all typed
   preflight results; malformed uploads retain the parser's file/row errors.
2. Reserve the ordered manifest and atomically claim one execution attempt.
   Select the requested Archive connection on a copy of the configured runner.
3. Call `pin_queue_for_submission()` once for the batch. The returned runner is
   reused for every branch, preserving pinned bytes/provenance or the original
   acquisition failure. No activation, download or fallback is introduced.
4. Iterate in upload order, with LINE before CONTINUUM when both are selected.
   Run `BrowserAssessment.assess()` and retain each report through `RunStore.add()`.
   Save the source/purpose/run mapping immediately before advancing.
5. Catch ordinary branch exceptions, record a short generic failure and continue
   with siblings. Detailed exceptions go to server logs. A returned scientific
   report with a failed/incomplete source is retained unchanged; report generation
   is distinct from successful retrieval or a scientific conclusion.

The manifest reserves bounded space for run references and the executor's short
ASCII failure messages before source work begins. Other batches cannot consume
that reserved space while work is active. Reservation is released when all
branches terminate. Actual report files still obey the independent run byte,
count and age budgets: oversized reports can fail storage, and earlier reports
can be evicted during a large batch under a small configured run limit. Their
manifest execution state stays COMPLETED while availability becomes EVICTED.
No batch-wide scientific verdict or automatic retry is created.

Duplicate submission protection uses a caller-supplied 32-character lowercase
hexadecimal token scoped to the browser owner. `BatchStore.create()` compares a
fingerprint of source records, upload hash, purposes and shared input. The same
token and inputs return the existing batch; different inputs with the same token
are rejected. `claim_execution()` grants only one attempt even for concurrent
calls. Token mappings are bounded by manifest retention and disappear on expiry,
eviction or close. This is not durable exactly-once execution across restarts.
Future routes must reuse the submission token on repeated POSTs and mint a new
one for an intentional new run.

An optional progress callback receives branch stage events annotated with batch
ID, source ID, purpose and completed/total branch counts. Callback errors do not
change assessment results. If the parent expires, closes or otherwise cannot
record a result, execution stops before the next source query instead of
continuing with untracked reports. A report already saved at that point retains
its normal independent RunStore lifetime.

Parity tests use offline Archive replay and the same pinned Queue bytes and
parse record for the batch and separately filled standalone forms. Full saved
request/report dictionaries match after the existing documented execution-time
normalization; source dates, hashes, scientific methods, context associations,
Queue geometry evidence and outcomes are compared. Tests cover Legacy/V2,
LINE/CONTINUUM/both and REST/SKY. These establish engineering equivalence, not
independently reviewed proposal verdicts or atomic consistency of live Archive.

## Step 5: upload form, batch overview and manifest download

The `batch` blueprint in `ui.batch_routes` owns these routes:

- `GET/POST /proposed/batch`: a dedicated fixed Single Pointing form with source
  upload, preview, per-target diagnostics and shared scientific requirements.
- `GET /batches/<batch_id>`: ordered source/purpose execution states, saved match
  counts, unresolved counts, source completeness and existing text/explorer links.
- `GET /batches/<batch_id>/download/manifest`: a JSON snapshot of settings, source
  provenance, child references and current availability. It does not bundle reports.
- `GET /batches/progress/<token>`: browser-owner-scoped progress for the existing
  asynchronous form enhancement. Native form POST also works without JavaScript.

Navigation exposes Multi-source alongside the existing proposal and report
entries. `/reports` shows one owned batch entry, not all of its child reports.
The overview can refresh a running batch; finished records distinguish failed
branches from saved reports with incomplete data sources. Unavailable children
have a reason and no misleading active report link. Missing/expired/foreign
parents return a neutral 404 page. Back/previous/next navigation within child
reports and purpose-switch navigation are supplied by step 6.

### Reuse and maintenance

`_proposed_shared.html` has explicit heading, metadata, target, coordinate,
export and sidebar blocks. `proposed_batch.html` overrides only workflow-specific
sections; existing scientific controls, edit actions and browser enhancement
remain shared. `form_context()` contains the previous standalone presentation
preparation, now called by both workflows. Legacy and explicit V2 inputs keep
their existing backend and browser restrictions. Batch input has no single-target
coordinate or redshift controls; its uploaded rows exclusively supply those.

The prior owner-scoped Mosaic upload cache was moved unchanged into
`OwnedUploadStore`, with `MosaicUploadStore` kept as a compatibility import.
Batch and Mosaic use separate cache instances. Batch upload reads are bounded
at 100,001 bytes before parser validation, and storage holds at most 64 uploads
for one hour. The retained object includes original bytes, selected format and
row diagnostics. Browser cookies contain opaque ownership/history tokens rather
than uploaded contents or report dictionaries. Application cleanup clears the
batch cache. Unknown extensions do not choose the grammar: users explicitly
select CSV or TXT; changing the selector only affects the next uploaded file.

`RunStore.overview()` reads saved summary and Queue geometry index facts without
loading full candidate reports or rerunning scientific rules. The two count
families are labelled separately, preserving their different grouping units.
Source limitations remain expandable in the table. Zero evaluated contexts are
explicitly labelled and never presented as proof of no duplication.

### Failure and ownership behavior

- POST requires an owner-session form token; malformed, repeated scalar, invalid
  workflow and unknown action inputs are rejected before source work.
- Upload, preview, validation and scientific-field edits never assess sources.
  Scientific validation uses Run completeness checks for every target.
- Upload tokens are owner-scoped. Foreign, removed or expired tokens cannot be
  used to execute. An attempted replacement invalidates the old token even when
  the replacement fails, preventing accidental use of the old target list.
- All scientific fields and a valid retained upload survive validation failures
  and edit actions. File inputs cannot be repopulated by browsers, so the hidden
  upload token preserves the server-side bytes instead.
- All execution goes through step 4. Submission tokens survive an ordinary
  repeated Run POST; edit actions and displayed errors provide a fresh token for
  the corrected input. Conflicting reused tokens never execute new inputs silently.
- Overview, history, manifest and progress routes check browser ownership.
  Existing child report URLs retain their established opaque-ID behavior; this
  step does not claim authenticated multi-user authorization for the whole app.
- GET refresh, export, text-report and visualization navigation do not rerun
  assessment. Manifest availability is a read-time snapshot and may change later.

The layout keeps the established workbench palette, type and scientific form
structure. The overview is an ordered table, with responsive horizontal scrolling
and a keyboard-focusable region; target names and errors are template-escaped.
The shared setup popover omits overridden target coordinates and redshifts.
Desktop and 390px viewport browser checks use offline fixtures only; live Archive
coverage and real-proposal scientific acceptance are separate work.

## Step 6: navigation in existing child reports

`batch_navigation.navigation_context()` builds a read-only navigation model from
an owned manifest, source ID, purpose and text/visual mode. It preserves source
upload order and the current purpose. The batch blueprint supplies that model
through an endpoint-scoped template context processor for existing run text,
visualization, Queue detail and unavailable-download pages. It resolves the
current run through the stored reverse index, not user-supplied batch parameters.

The common base template renders `_batch_navigation.html` only when that owned
relationship is present. The bar offers Back to batch overview, target position,
previous/next target, text/visualization links, and other requested purposes.
Standalone and preloaded reports keep their existing content and routes without
a batch bar. Another browser with an opaque run URL does not receive the owner's
batch identity, target list or sibling links. Expired/removed parents stop
providing batch context while their surviving child reports remain readable.

Switching target or purpose resets to the destination's first page; pagination,
filter and plot selection from a different report must not be copied. The
current text/visual mode is preserved. A failed, waiting or unavailable target's
corresponding purpose links to its anchored status in the overview, never to a
different purpose or silently skipped target. The first/last target boundaries
are labelled. The overview assigns stable source-ID anchors, not target names,
so repeated names remain independently navigable.

If the current run is evicted or expires before its parent, the existing 404
report page still offers the batch navigation and return link. No dead current
text/visual links are shown. A later race between rendering and clicking a
sibling link is handled by that same unavailable-report page. Navigation reads
only manifests/availability; it never reruns assessment or alters report bytes,
scientific status, filtering, pagination, plotting or download contracts.

## Delivery increments and acceptance

| Step | Deliverable | Exit gate |
| --- | --- | --- |
| 1 (implemented) | Parser, fixtures, diagnostics | Numerical coordinates, z, identity, malformed inputs and limits tested offline |
| 2 (implemented) | Shared input → independent validated requests | Batch/standalone equivalence for Legacy and V2, LINE/CONTINUUM/both, REST/SKY, absent z, window overrides; shared input never mutated |
| 3 (implemented) | Batch manifest and child report lifecycle | Ordered source/purpose/run mapping, reverse lookup, expiry/eviction, byte/count limits and scoped history; no false persistence promise |
| 4 (implemented) | Serial orchestration using existing assessment | One pinned Queue snapshot across all children; source/purpose failures isolated; fixed replay parity with standalone; progress per target; duplicate submission guarded |
| 5 (implemented) | `/proposed/batch`, preview and `/batches/<batch_id>` | Reuse shared form fields, preflight all rows, preserve inputs on errors; validation performs no queries; manifest JSON download |
| 6 (implemented) | Existing text/explorer batch navigation | Back/previous/next and purpose switch retain identity; failed/expired children navigable as status; standalone URLs, filtering, pagination and downloads unchanged |

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

## Step 4 verification (2026-11-13)

```sh
python -m pytest -q tests/ui tests/unit/test_source_list.py tests/unit/test_batch_request.py tests/integration/test_separated_setup_contract_step03ba.py tests/integration/test_continuum_frequency_preparation.py
python -m ruff check --select F src tests examples
python -m compileall -q src tests
git diff --check
```

841 tests passed, including all existing UI tests. Static checks, compilation
and diff whitespace checks passed. The focused execution/store suite passed
38 tests: complete report parity across the supported input/purpose/reference
matrix; serial target/purpose order; one Queue parse despite file mutation;
managed-snapshot activation during execution; frozen acquisition failure;
branch assessment/no-report/storage failures; preflight before source access;
concurrent and repeated submissions; owner separation; progress-observer
failure; five targets/ten reports with explicit eviction; and stopping after
parent expiry. No live Archive/Queue service was queried for acceptance.

## Step 5 verification (2026-11-13)

```sh
python -m pytest -q tests/ui tests/unit/test_source_list.py tests/unit/test_batch_request.py
node --test tests/ui/*.test.cjs
node --check src/alma_duplicate/ui/static/proposed.js
python -m ruff check --select F src tests examples
python -m compileall -q src tests
git diff --check
```

802 Python tests and 118 JavaScript tests passed; syntax, static, compilation and
whitespace checks passed. Browser-route tests cover real Legacy/V2 offline runs,
preview/validation without source access, form edits, CSV/TXT, escaped names,
owner isolation, form-token validation, malformed/repeated fields, invalid and
oversized uploads, cache capacity/expiry/removal, failed replacement invalidation,
missing REST z, duplicate submissions, progress ownership, one-entry history,
manifest downloads, existing report/explorer links, failed branches and eviction.

A local browser session completed five-target CSV upload, preview, purpose
change with input retention, shared Continuum entry, validation, Run, overview,
manifest download, text report and visualization navigation. Desktop and 390px
viewport screenshots were inspected. The browser used only configured replay
and Queue fixtures; the five widely separated example targets did not match the
recorded Archive query and correctly showed Archive unavailable alongside Queue
retrieval. This is failure-visibility evidence, not live scientific acceptance.
Only a missing favicon was logged on the initial page; the report page had no
console errors. Local screenshots and browser session files are not source
artifacts; `.playwright-cli/` is ignored.

At the step 5 delivery, step 4 was staged and step 5 remained in the working
tree. These describe the delivery boundary, not the current Git index.

## Step 6 verification (2026-11-16)

The eight navigation tests cover target and purpose switching in both text and
visualization modes, first/last boundaries, overview anchors, failed siblings,
evicted reports, owner isolation, parent expiry, standalone reports and unchanged
download bytes. Assessment is disabled during navigation tests to detect accidental
re-execution. The combined UI, source-list and batch-request regression suite
passed all 810 tests in 43.97 seconds. Static analysis and whitespace checks
also pass.

Desktop and 390px navigation screenshots were inspected on 2026-11-13. The final
interactive next-target click was not executed because automatic approval was
unavailable; the old local preview server is no longer running. HTTP route tests
follow next/previous links in both modes, but do not replace that outstanding
interactive browser check. All assessment fixtures are offline; live Archive
scientific acceptance remains separate.

The outstanding click was subsequently completed on 2026-11-16 using the
[reproducible offline preview](../examples/acceptance/batch/README.md). The browser
also verified purpose switching, text/visual mode, previous-target navigation
and the return anchor. The preview uses a matching recorded cone for both
synthetic targets, so Archive and Queue retrieval both complete.

Steps 4–6 were committed together as `5fff580`. The subsequent offline preview
script, fixture and acceptance record are a separate working-tree increment.

## Catalog-backed workflow acceptance (2026-11-16)

The offline preview increment was committed as `fd69b0c`. A subsequent
[catalog-backed acceptance record](evidence/batch_catalog_acceptance_2026-11-16.md)
covers eight CSV/TXT upload-to-export workflows using NGC 6240 captured evidence
and synthetic dual-source cases. Independently submitted Single Pointing forms
match the batch requests, reports and inspection exports under fixed source
inputs. The catalog's independent-review status is unchanged. Actual proposal
review and live acquisition acceptance remain outstanding.

## Bounded target concurrency (2026-11-16)

The browser defaults to four concurrent targets. Set `ALMA_UI_BATCH_WORKERS`
before starting the server to choose 1–4; 1 restores serial execution. Direct
`execute_batch` callers retain the serial default unless they pass `max_workers`.
Purposes within a target remain sequential. Stored source order is upload order;
completion and storage-eviction order can differ. The limit is per batch, not a
global admission limit across browser sessions or serving processes.

All workers use the same pinned Queue loader. Its cached result or acquisition
failure is initialized under a lock. Scientific evaluation and report formats
are unchanged. Progress callbacks serialize completed counts and retain stage
counts by source/purpose; the page identifies the target whose stage is shown.
Stage percentages remain local to that stage, not overall batch completion.

Each branch records wall time and per-stage wall/thread CPU times using the
existing performance recorder. These are emitted at INFO level by
`alma_duplicate.ui.batch_assessment`, outside scientific reports; enable that
logger when profiling. When both sources are selected for Single Pointing,
Archive search and Queue loading and candidate filtering can overlap. Use the
branch wall time for elapsed time because individual stage times can overlap.
Threaded execution overlaps network waits but does not
promise proportional acceleration of CPU-bound Python evaluation. No live
speedup measurement has been completed. Running requests keep the old code until
the serving process is restarted.

Queue initialization, two-target overlap, five-target concurrency limits,
failure isolation and monotonic progress have dedicated tests. Existing full
report parity tests now run both serially and with two workers, for legacy/V2,
LINE/CONTINUUM/both and REST/SKY inputs. Parent removal stops queued work when
detected; already-running network operations cannot be forcibly cancelled.

### Retention observed during live browser acceptance

The supplied screenshots show two earlier reports evicted before the five-target
batch was reviewed. The default report budget is 1 GiB across retained report
artifacts, with a separate 20-report count limit. It is not a guarantee that five
large reports fit. Parallelism does not solve this storage constraint.

`ALMA_UI_MAX_RETAINED_BYTES` now exposes the existing disk budget at startup.
For example, `4294967296` allows up to 4 GiB of retained artifacts when local disk
capacity permits; it does not reserve disk space or guarantee a batch will fit.
The overview explicitly warns when completed reports are unavailable and no
longer labels such entries simply "Report saved". Existing evicted files cannot
be recovered through a manifest or a configuration change. Batch-wide atomic
retention and durable storage are not implemented in this increment.

The same screenshots show incomplete AQ array acquisition and a proposed-window
completeness diagnostic. Neither is a non-duplication verdict. Completeness must
only be declared when the entire proposed window list is supplied; no input
confirmation or scientific evidence is automatically inferred by this change.

Verification: the full UI/source-list/batch-request suite passed 840 tests after
the initial concurrency change. After adding the five-target bound test,
environment configuration test and retention warning, the affected route,
catalog, navigation, progress and concurrency suite passed 45 tests. All 118
existing JavaScript tests, static analysis, JavaScript syntax and whitespace
checks passed. The prior catalog acceptance increment remains staged; these
concurrency and retention-visibility changes are not staged or committed.

## Batch report protection (Phase 1, 2026-11-16)

New Batch publications opt into atomic capacity protection in RunStore. Protection
is installed under the same lock as publication, so another target, batch or
standalone save cannot evict the report between publication and manifest linking.
It lasts until the report's existing fixed expiry (default 24 hours from save),
including after batch completion. Reads do not extend it. Expiry and service
shutdown still remove reports; an open download retains its files until closed.
Protection does not imply restart persistence or a physical disk reservation.

When count or byte limits cannot accommodate a new report, the save fails with
an explicit capacity error. Earlier protected reports remain available. Victims
are removed only after capacity checks and staging succeed; a failed save does
not evict unrelated ordinary reports. Staging files are cleaned on failure.
Standalone reports retain their previous eviction policy. Protected reports may
consume all capacity, in which case later submissions fail to save until expiry
or a service restart; restarting also loses the reports and is not a retention
solution. No automatic unpinning or user deletion UI is introduced in this step.

The manifest's detached `storage_budget` snapshot records process-wide limits,
usage, protected reports and retired download bytes, without exposing other run
identities. The overview shows usage and per-branch errors. Manifest capacity
is separate: a completed manifest can still be removed under manifest pressure;
this does not release its reports' protection before their original expiry.
Already-evicted historical reports cannot be recovered by this change.

This supersedes the earlier live-acceptance description allowing same-batch
capacity eviction. It does not change assessment results, source pinning or
scientific report contents. The reservation covers existing short error text;
capacity failures are execution/storage failures, never non-duplication results.
