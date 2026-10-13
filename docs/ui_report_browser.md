# Read-only backend report browser

The viewer consumes full report v4, historical report v5,
[matching-detail report v6](matching_report.md) and inspection v3.
New non-solar browser runs use v6; Solar exemptions retain v4, and existing
v4/v5 reports remain unchanged.
The viewer does not submit a proposal,
query sources, or implement scientific calculations. The
[proposed form](ui_proposed_form.md) validates input and exports request JSON;
[browser assessment](ui_offline_assessment.md) creates temporary runs using
explicitly configured Archive replay/live TAP and Queue CSV sources. Existing
reports are not results of the current form. Both report routes use the same
comparison view. The viewer displays the methods supplied by each report.

This document owns report reading, exports and visualization. Startup for new
assessments and generated-run storage belong to the browser assessment contract;
input controls belong to the form contract. [Status](status.md) owns the current
implementation baseline and verification register. Dated checks below retain
their original scope and counts; they are not tests rerun on every new baseline.

Normal source coverage and retrieval details are collapsed; source problems open
the coverage section automatically and retain the warning in the result summary.
Member scope is explained once in the overview. With matching results, review
groups show their categories and affected-comparison counts in collapsed sections.
Proposed-input guidance and review groups when no matches exist remain open.
Unresolved totals and source-failure warnings remain visible in the overview.
Empty review sections are omitted.
Parameter tables, scientific calculations, provenance and exports remain available.

## Scientific calculation steps

Criterion rows expand into labelled stored operands and calculation explanations.
LINE pairs additionally show the bound original inputs and prepared frequency
and resolution. Queue continuum compares the stored aggregate RMS, with its
reference RMS and nominal/usable window evidence available underneath. Missing
aggregate RMS stays unavailable rather than falling back to reference RMS.
See the [scientific workflow map](ui_scientific_workflow.md) for the relationship
to the handwritten design, supported conversions and remaining limits.

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
new reports or remove old ones. Saved-report routes do not modify the configured
artifacts. Temporary `/runs` have a separate expiry/eviction lifecycle; they are
not added to the Existing reports list. Neither route provides per-user isolation.

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
- In the operator view (`technical=1`), open Technical records for raw values, issues, method and eligibility.
  Archive RMS stays in mJy/beam; Queue reference/scaled RMS stays in mJy. Missing
  derived RMS stays "Not computed", with the original dependency reason.
  `ui/report_view.py` labels known fields and rounds display numbers to six
  significant digits without unit conversion, scientific calculation or truth aggregation. Unknown fields retain their original values in technical records, without a guessed unit. Original criterion/context records remain available.
- Each context shows independent branches, common criteria and expandable LINE
  pairs with original attempt/reference and full criteria. Unit-bearing field
  names, method versions, decision references and unknown reason codes are kept.
  JSON evidence is available inside the operator view's Technical records disclosure.
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
- In `technical=1`, Technical records links to `?view=all`, an optional audit view of all evaluated
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

Current next steps are maintained only in the [roadmap](roadmap.md). The checks
below describe report behavior; dates and counts later on this page are historical.

`tests/ui/test_reports.py` runs the 15 offline catalog cases, renders all pages,
checks byte-identical original downloads and exact inspection equality, and
resolves pair-gap pointers. It also checks Solar, empty configuration, invalid
reports/pages, unknown paths, escaped content and startup snapshot consistency.
Comparison checks cover pair isolation, source-specific units, absent branches,
null RMS with dependency reasons, zero-valued SPW identities, unknown derived
fields, immutable input documents and escaping of displayed quantities.
These are engineering cases, not independently reviewed real proposals.

Form validation, configured offline/live assessment and temporary disk retention
are implemented. Persistent multi-user storage remains outside the current
lifecycle; report refresh does not query sources.


### Queue MIX evidence

A MIX candidate appears once. Its CONTINUUM and LINE summaries use the backend's
complete-variant OR results. Two labeled sections display D=7 m and D=12 m, each
with common/continuum criteria and its own LINE pair tables. Matching diameters
are read from `mix_aggregation`, never computed by Jinja or JavaScript. Complete
JSON exports retain both variants; inspection links refer to that full document.

## Scientific result presentation

The overview counts stored branch results across all contexts, not across beam
variants or pair rows. It does not synthesize an observation-wide verdict.
Current full and matching-detail reports include `display_identity` source labels;
older reports use existing stored bindings where available and otherwise show
an explicit missing identity. Rendering never queries sources for missing labels.
Numeric display uses six significant digits; original values and method versions
remain in expandable evidence and unchanged downloads. LINE RMS comparison uses
the backend's stored comparable RMS; an unavailable comparable value never falls
back to an RMS measured on a different basis. Source failures remain visible.

## Researcher report layout

The default reading order is plain-language findings, source coverage, matching
candidates, expandable comparisons and information to review. Technical records
and their navigation links are hidden in the researcher view. Operators can add
`technical=1` to a report URL to reveal the existing technical disclosure and
original report and inspection exports, plus input export for generated runs.
Use `?technical=1` on a URL without query parameters, or append `&technical=1`
when it already has parameters such as `page`. This is a display option, not an
access-control boundary; technical records remain in the HTML and download routes
remain unchanged. Rendering and navigation do not run a new assessment.

The report header has normal links styled as buttons for entering another
observation and opening existing reports. The latter lists operator-configured
saved reports, not a history of temporary runs. Temporary runs show their
retention period in a compact disclosure; expiry and restart limitations remain
available. Storage-detail wording is omitted from the primary reading flow.
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

Inline raw candidate records are limited to the current page; the saved
report download remains byte-identical. In v6, matching contexts retain full
calculations and other contexts retain decision summaries. Neither the audit
view nor the download reconstructs intentionally omitted calculation payloads;
an omitted payload is different from missing scientific evidence.
No UI action recomputes
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
details (`technical=1`). The page still presents summary counts, source status, provenance and
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


## Matching-result reading order

Result headings use stored target names and project codes. Archive Member OUS
identifiers remain visible beside each group; grouping, pagination, target and
execution boundaries are unchanged. Missing identities use the existing fallback
label. Headings are derived when a page is read, including from existing disk
indexes, without modifying reports or indexes.

In the matching view, LINE pairs recorded as `CRITERIA_MET` appear first and open
by default within their candidate. Other pairs are retained under **Other evaluated
window pairs**, with their original outcomes and original pair anchors. Each beam
variant keeps its own pairs. The all-comparisons view retains original pair order.
No pair outcome becomes a new context or whole-Member verdict.

The overview gives one matching-comparison count per requested purpose, plus
matching source groups and unresolved counts. It omits empty source-group counts
such as zero Archive Members on a Queue-only result. Retrieval failures, empty
results and the limit on search-wide conclusions remain explicit.

Verification on 2026-10-12: 244 UI tests passed, including unchanged report and
inspection exports, matching-pair disclosure and stable anchors in both stored
reports and temporary runs. Ruff F and whitespace checks passed. The four saved
Archive/Queue CONTINUUM/LINE reports from the post-PR #134 regression were opened
in a fresh browser preview with outbound source requests blocked. Their results
remained unchanged; the Queue LINE matching pair was expanded and its other
three pairs could be opened separately. This verifies presentation, not a new
live-source or scientific acceptance run.

## Single-pointing report explorer

The report action **Explore this report** and the contextual **Explore report**
navigation open `/reports/<id>/visualization` or `/runs/<id>/visualization`.
The explorer reads that exact report. It does not search, acquire AQ evidence,
convert scientific inputs, or recompute decisions. Downloads remain unchanged.

The desktop layout places position and frequency panels side by side, with a
comparison selector and recorded evidence below. On narrow screens the panels
stack. Selecting a plot or list row highlights the same comparison in both
panels. Selecting another comparison preserves both viewports.

- Drag with a mouse or trackpad button to pan position in two dimensions or
  frequency horizontally. A movement threshold prevents a drag from selecting
  the comparison beneath it. Touch scrolling keeps the normal page behavior.
- Ctrl/Command + wheel zooms around the pointer. Ordinary wheel scrolling stays
  available for the page and frequency rows. The +/− buttons zoom around the plot
  center; Reset restores the original fit for that plot.
- Click overlapping position boundaries, interiors or nearby centers to open a
  chooser listing every hit on the current comparison page. Comparison number,
  source, SPW, requested window, beam path and available Member/ASDM identity
  distinguish records. Scroll the chooser for longer lists; Escape, the close
  button or an outside click dismisses it. Coordinates are never shifted to
  separate overlaps, and the picker does not determine duplication.
- Archive stays blue and Queue orange; Queue boundaries are dashed. The selected
  boundary has a white halo and stronger outline, paired with the same numbered
  frequency row, list entry and evidence panel. Unselected areas are unfilled so
  overlapping records do not produce a misleading density map.
- Focus the plot itself for arrow-key panning, +/− zoom and Home reset. Focus a
  comparison and press Enter/Space to select it. Mouse-only gestures therefore
  have keyboard alternatives. On touch devices use the buttons and list.

Hover titles and the detail panel expose values. These interactions change only
view state; stored geometry, scientific values, verdicts and downloads are
unchanged. The text-report links remain usable without JavaScript.

The dependency-free viewport helper has Node tests for anchored zoom after pan,
zoom limits, horizontal-only frequency movement, coincident hit selection and
missing outlines. Run `node --test tests/ui/visualization_view.test.cjs`; CI runs
these checks alongside the existing Python tests.

### Filtering and focus

The compact controls above the plots filter **only the loaded comparison batch**
(up to 30 comparisons within the current report page). They do not fetch other
pages or change assessment results. The counter always shows visible versus
loaded comparisons, alongside the batch and report-page scope.

- Project restricts the Member choices to that project's loaded rows. Changing
  project clears the previous Member filter. Member keys include the source;
  Queue records without a Member remain individually selectable comparisons and
  are labeled "No Member OUS recorded". Filtering never merges SPWs or contexts.
- The existing selection stays when eligible; otherwise the first eligible
  comparison is selected and announced. Comparison numbers and text-report
  anchors stay stable when rows are hidden. An empty view asks the user to clear
  filters and does not imply a negative duplication result.
- **Only selected** toggles the plots and list between the current comparison and
  the filtered set. **Clear filters** restores the entire loaded batch and turns
  off isolation. Counts and evidence-availability captions follow the visible set.
- **Focus selected** fits the requested target plus the selected candidate's
  stored boundary/center in the position plot, keeping equal spatial scale.
  Frequency focus includes the requested marker and the candidate interval ends
  (LINE), or both representative markers (CONTINUUM). Missing evidence is not
  reconstructed. Focus is disabled if neither panel has evidence.
- Reset/Home fits the visible comparisons in that panel. Changing filters fits
  the new visible set; ordinary selection retains the viewport. The compact
  summary identifies the source, project, Member, execution, SPW and requested
  window/beam path where recorded, with separation, half-power radius and
  frequencies in their units.

Browser verification used saved CASE1 continuum evidence (16 → 12 by project →
4 by Member → 1 isolated comparison, then 16 after clearing) and saved Queue
LINE evidence (a full interval retained during focus). No new source query was
performed. UI regression: 271 passed; display interaction tests: 10 passed.

### What is drawn

- Fixed-target, single-pointing requests only. Only recorded matching branches
  and matching LINE pairs appear. Different targets, executions, SPWs, requested
  windows and beam variants remain separate. A plotted match does not make the
  entire Member OUS a duplicate.
- Position uses the proposed ICRS origin, the candidate center, and the candidate
  half-power radius stored in its eligible POS-SINGLE result. It does not derive
  a beam from diameter/frequency, draw an invented proposed beam, or treat an
  Archive footprint as the duplication boundary. Coordinates use an azimuthal
  equidistant display projection with east left and north up, including RA wrap
  and polar positions. Boundaries are sampled spherical small circles; drawing
  precision never changes the backend's inclusion decision.
- Archive centers are bound using the exact context ID and source reference,
  single-field geometry and the confirmed fixed-ICRS position interpretation.
  Ambiguous duplicate bindings are unavailable. Queue centers come from the
  POS-SINGLE operands. No geometry is borrowed across contexts or diameters.
- LINE draws the recorded prepared SKY frequency and candidate coverage interval.
  CONTINUUM draws requested and candidate representative frequencies as markers;
  it does not imply that continuum requires interval overlap. Shared CONT-SETUP
  evidence remains visible, including the researcher-declaration basis.
- Missing geometry or frequency evidence produces an explicit unavailable state.
  Available counts describe the displayed comparisons. Old temporary indexes
  without the new center index remain readable; their Archive position panel
  can be unavailable while the spectral panel remains usable.

### Pagination and storage

`page` selects the existing matching-result page of up to 20 Member groups or
independent Queue contexts. `plot_page` selects at most 30 individual comparisons
within that page. Both levels expose navigation and counts. This display limit
never changes retrieval, evaluation, or report contents.

The existing disk projection now retains a small exact-context center index for
matching contexts. Source rows remain in the original report; full contexts are
still read through their existing byte offsets. Temporary explorer URLs share
the report's expiry, eviction and server-session lifecycle.

Verification covers saved Archive LINE and CONTINUUM reports, synthetic Queue
CONTINUUM, and offline dual-source LINE runs. Tests cover immutable exports,
run isolation, source-free reads, stale indexes, ambiguous centers, polar/RA-wrap
projection, pair/beam identity, unsupported scope and pagination. This verifies
presentation against stored evidence, not a new scientific acceptance run.

Verification on 2026-10-13: 271 UI tests passed; Ruff F, JavaScript syntax and
whitespace checks passed. Browser checks exercised the saved Archive LINE case,
the CASE1 continuum report (4 Members / 16 comparisons), and a clearly labeled
synthetic Queue continuum report. Selection, zoom, text-report navigation and
a 390 px stacked layout were checked without new source queries.
