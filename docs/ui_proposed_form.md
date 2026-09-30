# Proposed input form and shared validation

`/proposed` supports fixed ICRS targets, single pointing, one setup and up to 32
windows. The initial form has no window rows. Detailed SPW input is optional;
researchers need not enter SPW 0–3 to validate a partial request. The limit is
local to this interface, not a scientific restriction.
The home route redirects to this working input page. Global navigation separates
Proposed observation from Existing reports; reports are independent of the current form.

Install `.[test,ui]` and start the existing Flask application, then open
http://127.0.0.1:5000/proposed. `ALMA_UI_REPORT_DIR` is optional and independent:
existing reports may be browsed, but form validation never selects or updates one.

## Ownership

The adapter creates the existing `request` and `search_options` wire mappings.
Values remain strings until the backend validator parses them. There is no UI
unit conversion, REST-to-SKY formula, bandwidth qualification or aggregation.
The integer-only display limit is converted to an integer when its spelling is
valid; malformed values go to the backend for diagnostics.

Each Validate action calls `validate_proposed_observation()`. Categories, paths,
codes, rules, readiness and validity come directly from that result. Diagnostic
links point to the relevant control or window section; inline messages preserve
original entered values. Missing scientific evidence can coexist with valid,
search-ready inputs. Evidence notes are not errors or requests for candidate data.

## Supported form mapping

| Form | Backend field / interpretation |
| --- | --- |
| Target coordinates | position with DEG/HMS and DEG/DMS, ICRS |
| Purpose | CONTINUUM and/or LINE, independently selected |
| Complete window list | setup_complete, false unless explicitly checked |
| Representative frequency | declared quantity/reference, no window averaging |
| Source redshift | source_redshift; blank is omitted, never assumed zero |
| Window centre | stable window_id, SKY/REST/UNKNOWN, frame UNKNOWN |
| Optional window bandwidth | CENTER_BANDWIDTH; USABLE/NOMINAL/UNKNOWN explicitly selected |
| Correlator mode | declared FDM/TDM/UNKNOWN; no automatic inference |
| Continuum RMS | SETUP / AGGREGATE / DIRECT_DECLARATION; optional contributing IDs |
| LINE RMS and planned resolution | one WINDOW sensitivity per row, SMOOTHED basis, smoothing_resolution |
| Sources, radius, limit | search_options; source selection does not access sources |

LINE sensitivity is emitted when either its RMS or resolution is supplied, so
missing counterpart evidence remains diagnosable. No aggregate or neighboring
window RMS substitutes for it. Frequency and velocity resolution units use the
backend's current accepted units. Channel spacing and effective noise bandwidth
are distinct and are not inferred or exposed by this limited form. Kelvin,
interval endpoint entry, arbitrary predicates, mosaics, moving targets and
request-file import are outside this increment; the existing backend API remains
available for its wider supported input contract.

Purpose checkboxes declare the intended branches; they do not qualify a setup.
Continuum representative frequency and aggregate RMS can be entered without any
window rows or contribution list. Missing widths retain the backend CONT-SETUP
missing-evidence diagnostic. For LINE, omitted centres/resolution/RMS likewise
remain missing evidence. Position, radius and source selection can still permit
candidate search. The interface does not invent windows, widths or sensitivities.

## Editing and export

Add/remove posts rerender the form without executing validation or search. Setup
and window IDs are generated automatically and displayed read-only in technical
details. Hidden row tokens keep each window's inputs together. Contributing
windows are selected with checkboxes; the adapter preserves their explicit IDs.
Removing a window requires a confirmation POST and removes its LINE sensitivity.
Any continuum reference to that window remains visible as an unavailable selection;
the researcher must review the aggregate RMS and explicitly clear the reference.
The interface never recalculates RMS or silently repairs the declaration. The
previous whitespace-separated input representation is still accepted by the adapter.

The status column separates errors and missing information from expandable full
backend diagnostics. Aggregate-reference diagnostics target the contribution
selector. Browser presentation hides irrelevant empty purpose sections, while
retaining and showing previously entered values; without JavaScript all sections
remain available. Editing a validated form marks its status stale. Diagnostics
focus their controls and expand technical details as needed. Validation, export,
window editing and removal confirmation also work without JavaScript.

Download revalidates current fields. Only is_valid permits a request JSON download;
can_search can remain false and missing evidence can remain. It is an input
artifact, not an evaluation report. No request is stored, and there is no server
session shared between users. The current form must be reposted for every action.
No assess_observation(), Archive provider, Queue loader, or network call is used.
Responses inherit no-store. Duplicate scalar fields and malformed row lists fail
400; the application request-size cap is 1 MiB. Jinja escapes reflected values.
These local controls are not a production multi-user authentication/lifecycle system.

## Verification

Tests cover LINE REST input, missing redshift, equivalent units with exact shared
operands, continuum usable widths, mixed intents, per-window sensitivity binding,
row editing, duplicate references, invalid quantities, partial search readiness,
backend diagnostic parity, escaped values, transport limits and request export.
Existing report browser/acceptance tests remain unchanged.

Next increment connects validated inputs to explicit AssessmentOptions and
assess_observation(), with controlled sources and per-run result identity.
