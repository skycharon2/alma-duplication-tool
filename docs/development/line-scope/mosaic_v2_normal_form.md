# Mosaic submitted LINE evaluation in the normal form

The existing `/proposed` Run action now maps fixed Mosaic, LINE-only,
Archive-only submissions to the separated LINE contract and the verified Mosaic
V2 search backend. Existing OT upload, coordinate confirmation, connection
selection, progress handling and Member-group report templates are reused.
No new page, CSS or scientific criterion is introduced.

Each explicit requested window becomes one LINE requirement. Its optional
bandwidth becomes a linked physical SPW evidence record. Missing RMS never causes
a window to disappear: the existing required-field gate and adapter reject it.
The original completeness checkbox maps to physical inventory completeness and
has no effect on V2 LINE aggregation. This adapter does not add an independent
physical-SPW editor to the normal form.

The retained request contains the actual separated input passed to the evaluator,
plus the confirmed proposal pointings. The original V2 report schema and methods
remain intact in stored JSON. The existing Mosaic projection accepts the new
schema for presentation only; pagination and Member grouping do not recompute
results. Reopening views and downloading a report never reruns Archive.

Single Pointing, Queue, mixed LINE/Continuum and Continuum-only execution retain
their existing paths. The standalone separated editor is unchanged. The normal
form's pre-run request export still represents its legacy editable form model;
the retained request download is the exact versioned input used for the run.

Tests cover normal upload and Run, unchecked inventory, mirror selection,
Member/SPW headings, saved request/report agreement, all result views, byte-stable
report downloads, linked bandwidth and rejection of an incomplete added window.
Network access is disabled in browser regression tests; captured CASE2 metadata
passes through the real backend evaluator and report store.

Validation on 2026-10-28: full regression passed (2954 tests, 12 skipped),
changed Python files passed Ruff, and `git diff --check` passed. Real Chromium acceptance subsequently passed using the original desktop OT
export and captured CASE2 metadata through a local Flask server. The normal form
imported three pointings, retained unchecked inventory completeness, ran the V2
backend and displayed the existing Member/SPW report. Saved request and report
inputs agreed; reopening and repeated report downloads preserved identical bytes.
Screenshots were inspected without changing layout or styles. This browser run
used fixed metadata, not another live Archive search. The only console error was
the existing missing favicon (HTTP 404).

## Independent form records

The existing `/proposed` Mosaic LINE form now keeps requested LINE rows and
optional physical SPW rows in separate collections. Each LINE row has its own
redshift override; the shared default remains above the collection. Adding or
removing an SPW does not change the LINE list. Removing a linked LINE preserves
the SPW reference so validation can flag it for correction.

Validation, input download and assessment use the same separated request.
Physical inventory completeness does not affect V2 LINE aggregation. Existing
bandwidth values on older form rows are preserved as linked evidence. Row IDs
are bounded and checked for duplicates and overlap between collections.

The initial integration supported Mosaic LINE only. The subsequent
[submitted observation form](submitted_observation_form.md) also supports
Single Pointing and Continuum, including combined LINE/Continuum requests.
The separated form currently uses Archive only.
Changing scope while independent records are present blocks execution and
retains the entries; it does not silently send them to the legacy evaluator.

Validation: eight browser-route regression cases cover export/run parity,
independent redshifts, invalid input, stale links, scope changes and independent
add/remove operations. The real Mosaic backend runs against fixed CASE2
metadata in these tests. Browser layout and add/remove controls were also
checked locally. This is not a new live Archive acceptance run.
