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
  --live-archive --live-aq \
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
- `csv_load`: reading and parsing the supplied CSV snapshot.
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
`thread_cpu_seconds` are inclusive; `self_wall_seconds` and
`self_thread_cpu_seconds` exclude child stages. Do not sum inclusive parents and
children. Unattributed wall time subtracts only root stages from the run total.
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
