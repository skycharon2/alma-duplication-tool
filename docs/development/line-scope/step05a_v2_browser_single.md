# Step 05A — opt-in Archive LINE V2 browser Single Pointing

## Status and scope

This step explicitly exposes **only** the existing Step 04C Single Pointing
V2 assessment (`assess_submitted_line_single_v2`) through the separated browser
editor. It does not alter the old `/proposed` route, the shared public
`assess_observation`, LINE pairing or criteria, Queue, Continuum, or Mosaic.

Unlike a global duplication check, V2's branch `FALSE` means that *one retained
Archive candidate context* fails every explicitly submitted LINE requirement.
Even when all retained contexts are FALSE, the report has
`assessment=NOT_AGGREGATED` and
`v2_science.search_wide_duplication_verdict=NOT_EVALUATED`.
The Archive source state and its query provenance remain in the full JSON.

## Explicit opt-in and source selection

The browser feature is **off by default**. It is enabled at process startup
only when `ALMA_UI_SUBMITTED_LINE_V2=1`. The server must have **exactly one**
Archive source configured: existing `ALMA_UI_ARCHIVE_REPLAY` or
`ALMA_UI_LIVE_ARCHIVE=1`. It does not accept Archive paths, endpoints, or source
flags supplied through an HTML form. It reuses the server-configured Archive
client, and never silently falls back from replay to live.

The separated editor accepts `assess-v2` for on-page candidate results and
`download-v2` for a complete V2 JSON attachment. The download button executes
a **new query/replay**; it is not a download of a previously stored run.
The legacy `assess` action stays unavailable.

`ALMA_UI_LIVE_ARCHIVE_AQ=1` is intentionally rejected for the new V2 browser
route, because Step 04C does not acquire/bind the corresponding AQ array
catalog. This avoids pretending that full Archive array evidence was collected.

## Report compatibility / retention boundary

Step 04C reports have `report_version=7`. The existing `RunStore`,
`inspect_report` and legacy report pages accept versions 4–6. Step 05A therefore
**does not** publish V2 runs into legacy `/runs/` or claim an indexed report.
The on-page view is ephemeral. Both HTML and JSON show complete candidate-scoped
LINE pairing conditions, including the actual `line_context_method_version`.
Unified V2 report storage and report inspection require a separate review.

The `assess-v2` action is server-side, synchronous, and may trigger a live
Archive request. It is intended for locally managed browser deployments, not
an unauthenticated public internet service. Existing 1 MiB form size and
no-store headers remain in effect.

## Safety and error behavior

- Invalid form fields and duplicate/unknown row IDs are rejected before science.
- A missing per-LINE RMS, resolution, or invalid REST input stops execution.
- Mosaic and Continuum new-contract requests cannot run through this UI.
- No configured Archive source, conflicting source modes or LIVE_AQ fail before
  a client is constructed.
- Archive source acquisition failure is visible as source-unavailable status,
  never silently transformed into no duplication.
- Old browser and public APIs retain their prior routes and behavior.

## Local acceptance

```bash
python -m pytest -q tests/ui/test_separated_v2_browser_step05a.py
python -m pytest -q tests/ui/test_separated_editor_step03bb.py \
  tests/integration/test_submitted_line_assessment_step04c.py \
  tests/integration/test_submitted_line_context_evaluation_step04b.py \
  tests/integration/test_submitted_line_aggregation_step04a.py
python -m pytest -q
ruff check src/alma_duplicate/ui/separated_v2.py \
  src/alma_duplicate/ui/separated_editor.py \
  tests/ui/test_separated_v2_browser_step05a.py
git diff --check
```

## Example: opt-in with recorded Archive data

```bash
export ALMA_UI_SUBMITTED_LINE_V2=1
export ALMA_UI_ARCHIVE_REPLAY="$PWD/examples/confirmed_line/archive/manifest.json"
unset ALMA_UI_LIVE_ARCHIVE ALMA_UI_LIVE_ARCHIVE_AQ
python -m flask --app alma_duplicate.ui.app:create_app run --host 127.0.0.1 --port 5051
```

Open `http://127.0.0.1:5051/proposed/separated`. Use the Guide B
single-point target (RA 201.365, Dec -43.019, search radius 30 arcsec),
add one FDM LINE window at 225.1 GHz, resolution 20 km/s, RMS 0.3 mJy/beam;
validate before choosing `Run V2 Archive LINE`.

## Follow-up

Step 05B should upgrade report inspection and `RunStore` indexing for V2
version 7 without reinterpreting V1 reports; add persisted download/linkable
report pages with explicit candidate/source limitations. Later steps can add
reviewed Mosaic and mixed-intent browser workflows.
