# Read-only backend report browser

This increment consumes report v4 and inspection v3. It does not submit a proposal,
query sources, or implement scientific calculations. The
[proposed form](ui_proposed_form.md) validates input and exports request JSON;
[browser assessment](ui_offline_assessment.md) creates temporary runs using
explicitly configured Archive replay/live TAP and Queue CSV sources. Existing
reports are not results of the current form. Both report routes use the same
comparison view. The viewer displays the methods supplied by each report.

## Run locally

```bash
python -m pip install -e ".[test,ui]"
python -m alma_duplicate.cli.acceptance --catalog examples/acceptance/catalog.json --output-dir reports/ui-report-browser
export ALMA_UI_REPORT_DIR="$PWD/reports/ui-report-browser"
python -m flask --app alma_duplicate.ui.app:create_app run --host 127.0.0.1
```

Open http://127.0.0.1:5000/reports. Generate the output directory only once;
existing acceptance outputs can be reused. The application loads immediate
`*/report.json` children at startup. Operator configuration `REPORT_DIRECTORY`
overrides the environment in `create_app(config)`. No directory is exposed by
default; the empty page says no reports are configured, not no duplicates.

This is a local review tool without authentication. Only select reports approved
for the people using that process. Do not expose the development server publicly.
All configured reports are accessible to that process's visitors. Restart to load
new reports or remove old ones. Nothing is uploaded, written or deleted by routes.
This is not the future per-user assessment storage service.

## Display and export contract

- Source statuses and complete source metadata remain separate from scientific
  outcomes. Failed, incomplete and missing sources stay visible.
- A candidate index links to each coherent context, with separate CONTINUUM and
  LINE branch outcomes copied from the report. Only requested branches appear as table columns. An absent requested branch says "No branch
  result"; the viewer does not infer a negative outcome or aggregate candidates.
- Parameter tables show proposed and candidate criterion quantities, including
  their source-specific units; source field names remain in technical records. Position shows the stored separation
  and candidate beam radius. Request-level CONT-SETUP remains separate from
  candidate evidence, including researcher declaration and conflict notices.
- Each LINE pair has its own six-criterion table and setup/window/SPW binding.
  Full identity (Archive association/component or Queue snapshot/row/SPW) remains
  expandable. Pair membership is never rebuilt or combined by the viewer.
- Open Technical records for backend-derived values, issues, method and eligibility.
  Archive RMS stays in mJy/beam; Queue reference/scaled RMS stays in mJy. Missing
  derived RMS stays "Not computed", with the original dependency reason.
  `ui/report_view.py` labels known fields and rounds display numbers to six
  significant digits without unit conversion, scientific calculation or truth aggregation. Unknown fields retain their original values in technical records, without a guessed unit. Original criterion/context records remain available.
- Each context shows independent branches, common criteria and expandable LINE
  pairs with original attempt/reference and full criteria. Unit-bearing field
  names, method versions, decision references and unknown reason codes are kept.
  JSON evidence is available inside the single Technical records disclosure.
  The default page shows plain-language explanations, not raw reason codes.
- Null or ineligible outcomes say Needs review; non-applicable criteria are labelled separately. Solar explicitly says search not performed.
  No context or NOT_AGGREGATED never becomes a no-duplication verdict.
- The default view lists only contexts with an explicit CRITERIA_MET result in
  at least one requested purpose. It never derives a match from individual pairs,
  beam variants or missing results. Mixed-purpose results keep their independent
  branch labels. Matching Archive contexts are grouped by an unambiguous Member
  OUS identity, then by target and ASDM execution. Every SPW/context remains
  separate; equal SPW labels never collapse evidence from different executions.
  Pages contain up to 20 complete Member groups or independent source contexts,
  including matches beyond the backend display cap. A Member is never split
  between pages, even when its contexts were interleaved in the original report.
  Original candidate IDs remain stable.
- Queue contexts remain independent. Missing or conflicting Member identities
  remain individual comparisons; missing or conflicting target/execution
  identities retain separate children within a known Member. Explicit legacy
  association evidence may supply identity; generated IDs are never parsed to
  guess it. The summary counts matching Member groups separately from matching
  comparisons. It does not claim that every observation in a Member is a duplicate.
- Technical records links to `?view=all`, an optional audit view of all evaluated
  contexts, paginated independently at 20 contexts per page. Evidence-issue links explicitly target that
  view, so excluded/unresolved contexts remain traceable. Both stored-report and
  temporary-run routes use this behavior. Unknown view values return 400.
- Zero matches remains distinct from complete absence of duplication. Source
  failures and unresolved-evidence guidance remain visible in the default view.
  Filtering changes presentation only; retrieval, evaluation, report bytes and
  complete inspection downloads are unchanged.
- `/reports/<id>/download/report` returns the exact bytes loaded at startup,
  with a displayed SHA-256. It never regenerates timestamps or truncates evidence.
- `/reports/<id>/download/inspection` serializes the existing v3 consumer output.
  Pair locations point into the complete report, not the browser page subset.
- IDs are local to this process/catalog ordering, not stable cross-run identities.
  Downloads use constant-format filenames; no browser input becomes a local path.
- JSON duplicate keys/non-finite values, unsupported versions and invalid inspection
  contracts fail startup. This is a controlled backend-artifact reader, not a
  general report-upload/schema-validation API. Symlink report/case entries fail.
- Responses are no-store; table content uses Jinja autoescaping and raw evidence
  uses its JSON filter. Tables have captions, row/column headers and keyboard
  accessible horizontal scrolling on narrow screens.

## Verification and next step

`tests/ui/test_reports.py` runs the 15 offline catalog cases, renders all pages,
checks byte-identical original downloads and exact inspection equality, and
resolves pair-gap pointers. It also checks Solar, empty configuration, invalid
reports/pages, unknown paths, escaped content and startup snapshot consistency.
Comparison checks cover pair isolation, source-specific units, absent branches,
null RMS with dependency reasons, zero-valued SPW identities, unknown derived
fields, immutable input documents and escaping of displayed quantities.
These are engineering cases, not independently reviewed real proposals.

Form validation, offline execution and explicit live Archive TAP execution are
implemented. Production run storage remains a separate future increment; the
comparison view continues to consume retained backend results without querying
sources on refresh.


### Queue MIX evidence

A MIX candidate appears once. Its CONTINUUM and LINE summaries use the backend's
complete-variant OR results. Two labeled sections display D=7 m and D=12 m, each
with common/continuum criteria and its own LINE pair tables. Matching diameters
are read from `mix_aggregation`, never computed by Jinja or JavaScript. Complete
JSON exports retain both variants; inspection links refer to that full document.

## Scientific result presentation

The overview counts stored branch results across all contexts, not across beam
variants or pair rows. It does not synthesize an observation-wide verdict.
New report v4 documents include additive `display_identity` source labels;
older reports use existing stored bindings where available and otherwise show
an explicit missing identity. Rendering never queries sources for missing labels.
Numeric display uses six significant digits; original values and method versions
remain in expandable evidence and unchanged downloads. LINE RMS comparison uses
the backend's stored comparable RMS; an unavailable comparable value never falls
back to an RMS measured on a different basis. Source failures remain visible.

## Researcher report layout

The default reading order is plain-language findings, source coverage, matching candidates,
expandable comparisons, information to review, then one Technical records
section. No raw JSON, internal outcome/reason/method codes or hashes are visible
until that technical section is opened. All original report, inspection and input
request download links also live inside that section; reading the findings does
not require an export. The primary actions are entering another observation and
opening existing reports. Temporary runs retain an explicit retention notice.
The first candidate comparison on each page opens by default.

Findings describe the stored results separately for each requested purpose.
Matches, unresolved comparisons and scoped non-matches have distinct wording;
zero candidates never becomes a no-duplication finding. Source/evidence warnings
precede those findings when coverage needs attention. Unknown branch statuses
count as needing review, never as a negative result.
The candidate table shows only requested
purposes. Targets, projects and candidate SPWs identify comparisons; long
machine identifiers remain in the original records.

Criterion explanations use explicit stored outcomes and a small map of known
reason codes. They never recalculate thresholds or classify unknown reasons as
missing user input. Calculated but formally ineligible criteria remain Needs
review. Pair headings use recorded sky frequency and candidate window identity;
the pair index distinguishes equal-frequency requests. Exact proposed window
IDs remain in audit records and exports. Identical common criteria are displayed
once for LINE-only comparisons only when every pair contains that exact record;
otherwise the separate common table is retained. Mixed-purpose comparisons keep
that table for the continuum branch.

Information to review groups existing inspection occurrences, with their overlap
caveat, known explanations and links to affected candidate pages. Long candidate
link lists explicitly indicate omitted links and retain the complete inspection
download. Failed/incomplete sources, failed array acquisition, zero-hit array
lookups and unresolved retrieval filters remain visible outside technical panels.
Recognized synthetic examples and recorded Archive inputs are labelled as such.
Solar reports explicitly show an exemption instead of a zero-candidate summary.

Inline raw candidate records are limited to the current page; the original
report download remains complete and byte-identical. No UI action recomputes
scientific results or queries a source. Tests cover default visibility, original
exports, unresolved evidence, unknown codes, method eligibility and pair isolation.

Verification on 2026-10-05: full regression `1780 passed, 12 skipped`; after the
final presentation adjustments, all `147` UI tests passed. Ruff F passed.
Browser review used stored reports with external requests disabled: a real LINE
smoke artifact and a synthetic missing-RMS case. Expanded comparisons showed
readable criteria without raw JSON/status codes; the missing-RMS guidance was
visible. A 390-pixel viewport had no document-wide horizontal overflow. This is
report-presentation verification, not a new live acquisition or scientific
acceptance result.

Follow-up verification on 2026-10-05: `152` UI tests passed, including empty
results with completed, failed, incomplete and unconfigured sources; optional
exports are hidden by default on both stored reports and assessment runs.
Unknown and absent branch results remain unresolved. Original report downloads
remain byte-identical. Ruff F passed. Browser checks confirmed disclosure behavior
and no document-wide overflow at 390 pixels, using stored reports with outbound
requests disabled.

Matching-only verification on 2026-10-05: `155` UI tests passed and Ruff F passed.
Coverage includes positive parent-branch selection, mixed purposes, stable
candidate identifiers across filtered pages, unresolved-result guidance,
complete exports, and the optional all-comparisons view. Browser replay of the
saved live CASE1 report displayed 16 matching comparisons from 336 evaluated
contexts, with outbound requests disabled. This confirms presentation of the
stored results; it is not an additional live query or scientific acceptance.

Member grouping verification on 2026-10-05: `159` UI tests passed and Ruff F
passed. Tests cover interleaved Member contexts across page boundaries, a Member
with more than 20 matching comparisons, separate targets/executions, repeated SPW
labels, ambiguous and legacy identities, Queue isolation, escaped labels, and
unchanged complete report/inspection downloads. The shared viewer remains in
use for both stored reports and temporary runs. In a browser with outbound
requests disabled, the retained CASE1 report showed four Member OUS groups
containing 16 matching comparisons. SPW disclosure showed the stored comparison
values, and the 390-pixel viewport had no document-wide horizontal overflow.


## Large generated Queue reports

Temporary `/runs/<id>` reports use the indexed disk store described in
[temporary local retention](ui_offline_assessment.md#temporary-local-retention).
The viewer shares its grouping and pagination with `/reports/<id>`, but reads
only contexts needed for the current page. Original context indices and Member,
target and execution boundaries are preserved; no scientific outcomes are
recomputed during presentation.

Generated-run HTML excludes the full inspection and per-row source payloads.
Their complete contents remain in the original JSON downloads under technical
details. The page still presents summary counts, source status, provenance and
information to review. No matching results with indeterminate candidates must
continue to show uncertainty, not a conclusion of no duplication.

`tests/ui/test_run_store.py` covers exact downloads, reports above the old 32 MiB
limit, indexed pagination, private permissions, expiry, eviction, active download
leases and failed-write isolation. The full 3200-row Queue engineering smoke on
2026-10-06 produced a 180,891,463-byte report within the default 1 GiB budget;
the result page was 34,767 bytes. Outcomes remained 0 criteria met, 110 not met
and 3090 indeterminate. This verifies storage and presentation, not scientific
acceptance of those indeterminate cases. Local replay artifacts are under
`reports/queue-disk-smoke-2026-10-06/` (ignored generated output).


## Queue scope explanations

Information to review counts unique affected candidates within each group. Repeated
criterion/beam diagnostics remain available under Technical records. For recorded
Queue scope blockers, the viewer separates custom mosaic pointings, rectangular
mosaics and spectral scans instead of telling every researcher to check the CSV.
Groups can overlap and do not count duplicate observations. Unknown codes retain
the existing fallback; the viewer never changes scientific results. See the
[blank-Mosaic interpretation](queue_blank_mosaic.md) for newly supported offsets.
