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
  --queue-csv SNAPSHOT.csv \
  --output reports/performance/queue.json

python -m alma_duplicate.cli.profile_assessment REQUEST.json \
  --live-archive --live-aq \
  --output reports/performance/archive.json
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
- `csv_load`: reading and parsing the supplied CSV snapshot.
- `archive_binding`, `*_contexts`, `*_filter`: query binding, context construction
  and retrieval filtering, before scientific evaluation.
- `aq_acquisition`: acquisition orchestration including discovery, Member requests
  and response validation. A skipped/unconfigured AQ path may take nearly zero.
- `scientific_evaluation`: all retained contexts, independent of the display cap.
- `report_assembly`: building the JSON-native report, including evidence conversion.
- `inspection`: report inspection and evidence diagnostics.
- `write_*`: serialization, hashing and file writes together; not pure disk latency.
- `view_projection` / `first_page_projection`: preparing the report index and
  loading its first page. The remaining bookkeeping is reported as unattributed time.

Current measured stages do not overlap. No timing fields are added to scientific
reports. Instrumentation is inactive unless a `PerformanceRecorder` is installed
in the current execution context. Exceptions retain their original behavior.
Tests compare scientific records with and without recording, and cover write
failure and timing scope reset.

Run one profile at a time on a quiet machine. Keep request and snapshot hashes,
source modes, storage budget, Python/platform information and the reviewed Git
baseline with results. Live services and filesystem caches vary: a single run
locates likely bottlenecks but cannot establish a general speedup. Compare repeated
runs with identical inputs before accepting a performance optimization.

## Initial measurements

See the [measurement record](evidence/assessment_performance_2026-10-09.md)
for inputs, measured stages, failures and limits. These measurements establish
where to investigate; this increment does not implement a speed optimization.
