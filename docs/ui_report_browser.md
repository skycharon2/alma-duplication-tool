# Read-only backend report browser

This increment consumes report v4 and inspection v3. It does not submit a proposal,
query sources, or implement scientific calculations. The [proposed form](ui_proposed_form.md) validates input and exports
request JSON; [offline assessment](ui_offline_assessment.md) creates temporary runs
using configured local sources. Existing reports are not results of the current
form. Both report routes use the same comparison view. The viewer displays the methods supplied by each report.

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
  LINE branch outcomes copied from the report. An absent branch says "No branch
  result"; the viewer does not infer a negative outcome or aggregate candidates.
- Parameter tables show proposed and candidate criterion quantities, including
  their original units and source fields. Position shows the stored separation
  and candidate beam radius. Request-level CONT-SETUP remains separate from
  candidate evidence, including researcher declaration and conflict notices.
- Each LINE pair has its own six-criterion table and setup/window/SPW binding.
  Full identity (Archive association/component or Queue snapshot/row/SPW) remains
  expandable. Pair membership is never rebuilt or combined by the viewer.
- Expand a criterion for backend-derived values, issues, method and eligibility.
  Archive RMS stays in mJy/beam; Queue reference/scaled RMS stays in mJy. Missing
  derived RMS stays "Not computed", with the original dependency reason.
  `ui/report_view.py` labels known fields without unit conversion, calculation,
  rounding or truth aggregation. Unknown derived keys retain their original name
  without a guessed unit. Original criterion/context records remain available.
- Each context shows independent branches, common criteria and expandable LINE
  pairs with original attempt/reference and full criteria. Unit-bearing field
  names, method versions, decision references and unknown reason codes are kept.
  Evidence panels show backend JSON directly, not derived UI calculations.
- Null outcomes say Not computed. Solar explicitly says search not performed.
  No context or NOT_AGGREGATED never becomes a no-duplication verdict.
- Pages contain 20 evaluated contexts each, including contexts beyond the backend
  candidate display cap. All remain accessible through pagination.
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

Form validation and offline execution are implemented. Live Archive integration
and production run storage are separate future increments; the comparison view
continues to consume backend results without querying sources on refresh.


### Queue MIX evidence

A MIX candidate appears once. Its CONTINUUM and LINE summaries use the backend's
complete-variant OR results. Two labeled sections display D=7 m and D=12 m, each
with common/continuum criteria and its own LINE pair tables. Matching diameters
are read from `mix_aggregation`, never computed by Jinja or JavaScript. Complete
JSON exports retain both variants; inspection links refer to that full document.
