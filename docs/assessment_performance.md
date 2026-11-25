# Assessment performance measurements

The optional profiler measures the same `BrowserAssessment` and `RunStore` used
by the browser. It does not modify predicates, methods, display limits, scientific outcomes
or the source snapshot. Report detail defaults to the browser matching-detail mode;
`--report-detail full` measures legacy full v4 generation. It publishes a small timing record and removes temporary
report artifacts after measurement. This is a developer diagnostic, not a new
researcher input or a scientific acceptance test.

## Reproduce

Use the project's Python environment with the UI extra installed:

```bash
python -m alma_duplicate.cli.profile_assessment REQUEST.json \
  --queue-csv SNAPSHOT.csv --analyze-size \
  --output reports/performance/queue.json

python -m alma_duplicate.cli.profile_assessment REQUEST.json \
  --live-archive --live-aq --archive-connection AUTO --require-complete-sources \
  --output reports/performance/archive.json

python -m alma_duplicate.cli.analyze_report_size SAVED_REPORT.json \
  --output reports/performance/report-size.json
```

`REQUEST.json` contains `request` and `search_options`, as exported by the form.
Sources must be selected in that request. Live access is explicit; omitting
`--live-archive` never starts an Archive client. An offline alternative is
`--archive-replay MANIFEST.json`, optionally with
`--archive-array-evidence MANIFEST.json`. Existing timing files are never overwritten.

The default retention budget remains 1024 MiB. `--storage-mib 4096` permits a
larger diagnostic run only; it does not change the web application's configuration.
If retention fails, the timing record preserves the failed write stage and the
already-computed candidate/outcome counts. A failed write is not a scientific
negative result. Source failures can still produce a report; inspect `sources`
and `assessment_status` as well as the profiler's `execution` field.
Use `--require-complete-sources` when collecting a performance baseline. It
preserves the diagnostic JSON and returns a nonzero exit code if a selected
source did not complete. Check AQ status separately for runs requiring live AQ.
`source_diagnostics` preserves source reasons, upstream status/error kind and AQ
status/skip reason. A stage's `failed` flag indicates an exception crossing the
timing boundary; a client returning a structured failure can have `failed=false`.
Inspect diagnostic records before sharing them: source reasons may contain
exception text. They omit raw rows and HTTP response bodies.

## Reading the measurements

- `wall_seconds`: elapsed time for assessment, storage and first-page projection.
  Input-file loading/hashing, run-store creation, final diagnostic formatting and
  cleanup are outside this interval. HTTP, Jinja rendering, browser painting and
  progress polling are not measured.
- `thread_cpu_seconds`: CPU time consumed by the calling thread. The difference
  from wall time includes waiting and scheduling; it is not an exact network timer.
- `tap_acquisition`: TAP client call including response parsing/materialization.
  Its child stages distinguish `tap_projection_metadata`, `tap_unit_metadata`,
  `tap_count` and `tap_retrieval`. Only executed calls appear. These measure the
  executor call, including materialization, rather than wire transit alone.
  With the browser retrieval-first policy, `tap_count` appears only if a separate
  completeness check was needed; its absence is not a zero-duration COUNT.
- `queue_pin`: freezing the selected Queue snapshot at submission, including
  reading the supplied CSV bytes. This stage is omitted for Archive-only runs.
- `csv_load`: loading and parsing Queue data. For a pinned CSV, its file read
  is already accounted for in `queue_pin`.
- `archive_binding`, `*_contexts`, `*_filter`: query binding, context construction
  and retrieval filtering, before scientific evaluation.
- `aq_acquisition`: acquisition orchestration including discovery, Member requests
  and response validation. A skipped/unconfigured AQ path may take nearly zero.
  `aq_discovery` measures the properties request and decoding. Each `aq_member`
  measures one Member request, decoding and completeness validation, in input
  order. Timings contain no URLs, credentials, query bodies or Member names.
- `scientific_evaluation`: all retained contexts, independent of the display cap.
- `report_assembly`: building the JSON-native report, including evidence conversion.
- `inspection`: report inspection and evidence diagnostics.
- `write_*`: serialization, hashing and file writes together; not pure disk latency.
- Current browser storage records context byte ranges during `write_report` and
  stores them in `view.json`. It no longer writes a separate context file, so
  `write_context_index` appears only in older measurements.
- `view_projection` / `first_page_projection`: preparing the report index and
  loading its first page. The remaining bookkeeping is reported as unattributed time.

Timing schema 2 records `stage_id` and `parent_id`. `wall_seconds` and
`thread_cpu_seconds` are inclusive. `self_wall_seconds` and
`self_thread_cpu_seconds` subtract child stages on the same thread.
The `source_search` stage measures elapsed time across concurrent Archive and Queue
searches. Queue worker stages can overlap Archive stages, so their times should
be read separately. Unattributed wall time subtracts root stages from the run total.
Schema 1 records retain their original, unnested interpretation. Stages are
listed in completion order, with IDs assigned when they start.

No timing fields are added to scientific reports.
Instrumentation is inactive unless a `PerformanceRecorder` is installed
in the current execution context. Exceptions retain their original behavior.
Tests compare scientific records with and without recording, and cover write
failure and timing scope reset.

## Report size analysis

`--analyze-size` walks the generated JSON-native report after the assessment and
storage timer stops. `size_analysis_wall_seconds` records this additional work;
it is excluded from `wall_seconds`. The browser does not run this analysis.
The standalone command loads a saved report and performs no retrieval or evaluation.
It leaves that file unchanged and records its SHA-256 and actual byte count.

The analyzer calculates UTF-8 bytes using the publication serializer's indentation,
escaping and trailing newline, without constructing another complete JSON string.
It still requires the parsed report in memory. Large reports can take substantial
additional time to analyze.

- `formatted_bytes`: size in the standard report publication format. A saved file
  with different whitespace may have a different actual size.
- `root_value_bytes` plus `root_structure_bytes`: an exact partition of that size.
- `compact_bytes`: the same document without indentation, retaining the final newline;
  a diagnostic estimate, not a change to the report format.
- `largest_field_groups`: top 30 aggregated paths through depth 8, with array
  indices replaced by `*`. These nested sizes overlap and must not be summed.
- `repeated_containers`: top 30 repeated objects/lists of at least 4096 compact
  bytes, detected by ordered structural SHA-256 fingerprints. Reports contain
  occurrence counts and two example paths, without raw field values. Different
  key orders remain distinct. Nested repetitions overlap: these figures are
  neither additive nor a promise of savings from a future reference format.

Tests reconcile byte counts with the production serializer, including Unicode,
escaped strings, nesting and empty containers. A profiled stored report is also
checked against its actual file size.

Run one profile at a time on a quiet machine. Keep request and snapshot hashes,
source modes, storage budget, Python/platform information and the reviewed Git
baseline with results. Live services and filesystem caches vary: a single run
locates likely bottlenecks but cannot establish a general speedup. Compare repeated
runs with identical inputs before accepting a performance optimization.

## Initial measurements

See the [stage and report-size investigation](evidence/assessment_stage_size_2026-10-12.md)
for a live Archive case and a full-snapshot Queue LINE case after single-copy storage.

See the [measurement record](evidence/assessment_performance_2026-10-09.md)
for inputs, measured stages, failures and limits. These measurements establish
where to investigate; this increment does not implement a speed optimization.

## Retrieval-first live Archive comparison

The [CASE1 comparison](evidence/tap_retrieval_first_2026-10-12.md) measures
`COUNT_FIRST` against the browser's `STATUS_THEN_COUNT` policy with the same
request. Inspect both source status and candidate parity; report creation by
itself does not establish successful acquisition.

## Browser submission timings

To time a real Single Pointing or Mosaic submission, set
`ALMA_UI_ASSESSMENT_TIMINGS=1` in the Flask terminal before starting the server.
Run the assessment as usual and find the `Assessment timings` JSON line in
that terminal. `browser_assessment` starts after form validation and ends
when the server generates the report URL or stops the assessment. It excludes
browser rendering and network time between the browser and Flask.

Use `parent_id` to group stages under each source and purpose. For Archive
Mosaic, `mosaic_discovery` finds candidates, `mosaic_candidate_metadata`
measures each candidate's Archive metadata lookup, and
`mosaic_candidate_evaluation` measures its comparison and spectral display
preparation. Queue Mosaic elapsed time is recorded on its branch. `report_save`
measures group storage. Concurrent branches overlap, so their times should
not be added to get total latency. Check source status in the resulting report.
Timing logs contain stage names and durations, without submitted inputs or report IDs.

## Browser Mosaic source concurrency

Within a browser Mosaic Archive branch, each TAP mirror's successful optional
column probe is reused for subsequent candidates. Failed or malformed probes
are retried as needed. Each candidate still retrieves and validates its own rows.
Compare `tap_projection_metadata` call counts with `mosaic_candidate_metadata`
call counts when measuring the effect.

The browser Mosaic Archive branch also reuses one TAP HTTP session per mirror
for its sequential candidate queries. Sessions close when the branch exits,
including on failure. Compare cumulative `tap_retrieval` time and candidate
results using the same Mosaic input and mirror selection.

For a browser-submitted Mosaic with both Archive and Queue selected, the
two sources now run concurrently within each scientific purpose. The limit
is two active source branches per submission, independent of the Multi-source
worker setting. Report publication retains the submitted purpose and source
order. Measure the live gain with identical Mosaic inputs and the same Queue
snapshot before and after the change.

## Five-target batch baseline

`python -m alma_duplicate.cli.profile_batch` uses `execute_batch`, including
preflight, pinned Queue acquisition, target concurrency and the existing retention
policy. It accepts a JSON object with browser form `values` and `rows`, and a
CSV/TXT source list. The supplied setup is a reproducible diagnostic configuration,
not a reconstruction of a user's complete observing proposal.

```bash
python -m alma_duplicate.cli.profile_batch \
  examples/acceptance/batch/performance-setup.json \
  tests/fixtures/source_list/five_targets.csv \
  --sources both --workers 2 \
  --queue-csv examples/acceptance/queue/dual-source-line.csv \
  --archive-replay examples/confirmed_line/archive/manifest.json \
  --output /tmp/batch-both-2.json
```

Run each combination of `--sources queue|archive|both` and `--workers 1|2` in a
fresh process. Replace replay with `--live-archive --live-aq` only for explicitly
intended network measurements. Queue measurements require an explicit snapshot.
Outputs never overwrite an existing record. Input file SHA-256 hashes identify
setup, targets and supplied source manifests/snapshot; replay manifest hashes do
not recursively hash their referenced files. Preserve the referenced evidence
files alongside the manifest for reproducibility.

Match the browser's mirror selection with `--archive-connection AUTO`, or
choose the same explicit mirror used in the browser. `summary.slowest_target`
reports the largest sum of elapsed purpose-branch times for any target.
`summary.stages` aggregates call counts and inclusive elapsed time by stage.
`aq_repeated_member_queries` counts the occurrences beyond the first for each
Member across successful AQ query records. Failed attempts may still appear in
stage timings. No Member UIDs are added to the diagnostic output.

Each profiled branch also records `archive_tap`, with the requested connection,
the reported Archive source status, the TAP region and attempted regions in order.
The browser logs the same fields at INFO level using the
`alma_duplicate.ui.batch_assessment` logger. Compare `tap_retrieval` timings
using the same inputs, worker count and Queue snapshot, and check the candidate
decision digest and source statuses before attributing changes to the mirror.

`archive_tap.retrieval_phases` summarizes HTTP send through response headers,
streamed response body reads, VOTable processing outside those operations,
and conversion to typed rows. Header time includes connection setup and server
wait. Body read time includes decompression. VOTable overhead includes parser
work and request bookkeeping. These measurements do not isolate server time.

### Continuum TAP predicate comparison

Using the public CENA target from the five-target fixture, a 230 GHz SKY
continuum request with automatic search area, and the European mirror, a
single live comparison returned the following results. Each query used the
same resolved projection, `MAXREC=10000`, and an explicit OK response. Row
comparison ignored ordering and preserved multiplicity.

| Retrieval | Elapsed | Rows |
| --- | ---: | ---: |
| Existing center-or-mosaic predicate | 53.98 s | 502 |
| Center query plus mosaic footprints outside the center cone | 49.49 s + 0.70 s | 502 + 0 |
| Existing predicate, rerun | 50.92 s | 502 |
| Replace center `CONTAINS` with `DISTANCE <= radius` | 12.32 s | 106 |

The split matched all baseline rows on this target, with the center query
still accounting for most elapsed time. The distance variant omitted 396 rows.
The production query remains the existing center-or-mosaic predicate.

A follow-up compared the same production predicate with an inclusive
declination range on the center branch, expanded by `1e-8` degrees and
clamped at the poles. It retained the original `CONTAINS` and the independent
mosaic footprint branch. The experiment used the five-target fixture and at
most four concurrent comparisons against Europe, with the same projection and
completeness checks in each pair.

| Target | Existing query | With declination range | Rows |
| --- | ---: | ---: | ---: |
| B0218+357 | 50.14 s | 50.33 s | 46 |
| PKS1830-211 | 50.72 s | 50.95 s | 336 |
| CENA | 51.86 s | 51.10 s | 502 |
| WHya | 51.76 s | 51.82 s | 129 |
| M33 | 50.19 s | 51.86 s | 268 |

All five row multisets matched, including duplicate multiplicity. Median
retrieval was 50.72 s with the existing query and 51.10 s with the range.
The range was excluded from production because it did not reduce latency.

Live Archive batches with more targets than configured workers can admit one
additional target. Its TAP search waits for a shared slot, measured as
`tap_slot_wait`, and can start as soon as another target finishes TAP.
The TAP limit defaults to the configured target worker count. Set
`ALMA_UI_BATCH_TAP_WORKERS=5` for the web server or use `--workers 4
--tap-workers 5` for the profiler to try five simultaneous TAP searches.
After releasing its TAP slot, each branch waits for local capacity before
continuing to AQ, scientific evaluation and report publication. Replay and
Queue-only runs retain their original scheduling.

A ten-target CONTINUUM check at 230 GHz SKY used four local workers and
five TAP slots on the European mirror, with the Queue test snapshot and
temporary report storage. The profiler recorded five TAP starts at batch
start and the remaining five 55.1–59.5 seconds later. All ten Archive and
Queue searches completed and all ten reports were available. Nine AQ
acquisitions completed and one was skipped. Total wall time was 169.0
seconds. The last target (3C273) spent 44.7 seconds in AQ after its 55.7-second
TAP retrieval. This is one live run, not an estimate for every ten-target list.
That AQ acquisition issued 1,218 Member searches, with a median of 55 ms
and a maximum of 349 ms per search. The cumulative work, rather than an
individual slow request, accounted for the long AQ stage.

With the same input hashes and four TAP slots, the ten-target comparison
took 207.8 seconds. Its last two TAP searches started at 101.9 and 104.0
seconds. The five-slot run finished 38.9 seconds sooner (18.7%). Both runs
had the same source completion statuses and candidate decision digests.

### Two-target TAP experiment

`scripts/profile_two_target_tap.py` accepts a batch setup JSON and a two-target
CSV. It compares parallel independent queries against a single European TAP
query joining an uploaded table of target positions. The prototype requires
automatic search areas with a shared radius and uses a literal radius because
the European service rejected a radius supplied as an uploaded column.
It retains both the center and Mosaic footprint conditions. Each joined row
is tagged with the matching target, and comparison preserves duplicate rows.
The script requires explicit successful responses below the row cap and
returns a failure status if the joined query fails or its per-target results differ.

For PKS1830-211 and CENA at 230 GHz SKY, independent requests completed in
51.96 seconds wall time and returned 336 and 502 rows respectively. The
joined request timed out after 60.22 seconds, so live row parity could not
be established. It is not used by batch execution.

Multi-source runs up to two AQ Member queries per target at a time, using
separate HTTP sessions. With four target workers, a batch has at most eight
active AQ Member queries. Each mirror attempt still requires a complete set
of validated results, published in Member input order. Use `aq_acquisition`
for a target's elapsed time because its `aq_member` timings can overlap.
For an AQ concurrency comparison, keep `--workers`, inputs and mirror selection
fixed and run once with `--aq-member-workers 1` and once with
`--aq-member-workers 2`. Compare source and AQ statuses, `retained_contexts`
and `branch_outcomes` per target and purpose alongside timing.
`candidate_outcome_sha256` additionally compares the multiset of retained
candidate display identities, source/component, and branch status, truth and
reasons. It ignores candidate order and per-run identifiers. A matching digest
covers these published decisions and does not compare raw TAP values or
intermediate criterion calculations.

`branches` remains in source/purpose order, irrespective of completion order.
Each record includes source acquisition statuses, assessment status, nested stage
timings, execution state, final availability and retained file sizes. Storage
failure does not erase successful acquisition status. `COMPLETED` means all
reports remain available at the end, **not** that all sources succeeded or all
scientific comparisons were determinate. Evicted files have no measured final
size; zero retained bytes is not an estimate of their original report size.

`queue_geometry_evaluation` measures the additional browser Queue geometry path.
Existing scientific evaluation, TAP/AQ acquisition, assembly, inspection and
write stages remain separate. Writes include serialization and hashing; they
are not pure filesystem latency. Branch timing includes evaluation and storage;
batch wall time also includes preflight, setup, scheduling and final inventory.
Never sum overlapping branches or inclusive nested stages to obtain batch time.
The performance observer is optional and cannot change scientific output.

`process_lifetime_peak_rss_bytes` is the OS process high-water mark (macOS/Linux),
including imports and all threads, not per-target memory or an interval delta.
Use a fresh CLI process per measurement. `process_cpu_seconds` includes worker
threads. Cleanup and final diagnostic JSON publication are outside batch timing.
No browser rendering or HTTP latency is measured.

The small fixture/replay matrix verifies instrumentation and failure visibility;
it is not a full Queue snapshot or live Archive speed benchmark. In particular,
the replay cone does not cover all five supplied targets. Do not interpret quick
failed acquisition as a speedup. Record live source completeness, repeated trials,
source versions and the reviewed Git revision before comparing performance.
