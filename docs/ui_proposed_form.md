# Proposed input form and shared validation

`/proposed` executes assessments for fixed ICRS targets, single pointing, one
setup and up to 32 windows. Other target/geometry choices are available for
selection, validation and valid-request export only. The initial form has no window rows. Detailed SPW input is optional;
researchers need not enter SPW 0–3 to validate a partial request. The limit is
local to this interface, not a scientific restriction.
The form groups observation type, shared target information, scientific purposes, spectral line
requirements, continuum requirements, optional window evidence, and data sources.
LINE and CONTINUUM remain independent checkboxes and can both be selected.
Changing either checkbox submits the presentation-only `purpose` action; without
JavaScript, use Update requirement sections. This retains all entered values and
row identities, clears stale validation results, and never queries or assesses.
Selecting LINE with no rows creates one blank entry, with no assumed mode or
scientific values. Each entry is a requested correlator window, not an individual
spectral feature. Its central frequency, reference, planned resolution, RMS and mode
appear in Spectral line requirements. Redshift is shared by REST frequencies.
Additional bandwidth evidence and IDs are in a separate optional section, linked
to the same entries. Controls are not duplicated between sections.

Continuum has its own representative frequency, aggregate RMS, explicit setup
qualification declaration and optional contributing-window links. When a purpose
is deselected, entered scientific values stay visible with an inactive-purpose
notice. They remain in request provenance and are still validated; only selected
branches are evaluated. Blank unselected requirement panels are hidden.
All listed windows remain subject to LINE preparation when LINE is selected;
this increment does not introduce per-window purpose selection or new pairing.
The initial form still has no required four-SPW list. Proposed target type and
geometry are explicit; candidate geometry remains independently checked by the backend.
The home route redirects to this working input page. Global navigation separates
Proposed observation from Existing reports; reports are independent of the current form.

## Observation type and support

Target type offers Fixed target, Moving target and Sun; geometry separately offers
Single pointing and Mosaic. Defaults remain FIXED / SINGLE_POINTING, including
older form submissions that omit these fields. Explicit unknown values are kept
for validation, never replaced by a supported choice.

Changing a selector posts the presentation-only `scope` action. Without JavaScript,
use Update observation type. Both paths retain all entered values, units, selected
purposes, row identities and aggregate references, and clear stale validation.
They do not validate, access sources or execute assessments.

Only FIXED / SINGLE_POINTING can reach browser execution. Moving/Mosaic combinations
show their limitation and disable Run assessment. Sun instead shows the Appendix A
exemption and omits that action; retained inputs are collapsed, not discarded.
The server independently rejects direct assessment POSTs for these types before
invoking the execution adapter. No motion trajectory
or mosaic-pattern editor is provided. Retained coordinates do not define either.

Validation and request download use the existing backend contract. Valid moving
or mosaic requests report UNSUPPORTED. Valid Sun requests report NOT_APPLICABLE:
the backend already recognizes Solar exemption, but this increment does not enable
the browser Solar report flow. Sun takes the existing backend exemption path even
when its selected geometry is Mosaic. No choice creates a duplication verdict.

Only valid requests can be exported, even when unsupported for execution. Selected
types are preserved in JSON. Non-fixed targets with both coordinates blank omit
the position value; supplied or partially entered coordinates remain subject to
validation. Switching back to fixed single pointing restores the entered values.
These choices do not claim complete Appendix A implementation.

## Appendix A wording and input meaning

The form explains location AND angular resolution AND either the continuum or
spectral-line conditions for the same other observation. Both purpose checkboxes
may be selected for independent branch results; the UI does not require both
spectral alternatives or introduce a search-wide verdict.

- Fixed single-field location uses the other observation's half-power beam;
  the backend resolves AUTO retrieval separately from that scientific boundary.
- Moving objects use a name field. Name/alias matching remains unimplemented;
  retained RA/Dec do not substitute for identification by name.
- Mosaic location uses strictly more than 50% of the proposed pointings within
  the half-power beam area covered by the other observation. It is not an area
  overlap percentage. No pointing editor or coverage evaluator is implied.
- Angular resolution uses the Appendix's inclusive factor-of-two condition.
- Continuum requires at least two windows with bandwidth strictly greater than
  1.8 GHz, plus frequency and aggregate sensitivity conditions. The UI explicitly
  separates that policy wording from the project's usable-bandwidth interpretation
  and researcher-declaration evidence route. Nominal-to-usable interpretation is
  not unit conversion and is not enabled by this browser configuration.
- LINE entries supply requested window centres. FDM is required on both sides;
  one qualifying window can meet the spectral-line condition. The UI explains
  sensitivity comparison after smoothing to the same spectral resolution, without
  implementing calculations. Multiple features in one physical SPW must not be
  entered as distinct windows for continuum qualification.
- Sun is exempt, including Solar mosaics and either selected purpose. It is not
  labeled as a future duplication-checking feature or a successful empty search.

The expandable policy summary is explanatory. Thresholds, scientific methods,
pair association, approval states and aggregation continue to belong to the backend.

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
| Continuum setup confirmation | Separate positive `continuum_setup_declaration`, USER_DECLARED; never inferred from purpose |
| Complete window list | setup_complete, false unless explicitly checked |
| Representative frequency | declared quantity/reference, no window averaging |
| Source redshift | source_redshift; blank is omitted, never assumed zero |
| Window centre | stable window_id, SKY/REST/UNKNOWN, frame UNKNOWN |
| Optional window bandwidth | CENTER_BANDWIDTH; USABLE/NOMINAL/UNKNOWN explicitly selected |
| Correlator mode | declared FDM/TDM/UNKNOWN; no automatic inference |
| Continuum RMS | SETUP / AGGREGATE / DIRECT_DECLARATION; optional contributing IDs |
| LINE RMS and planned resolution | one WINDOW sensitivity per row, SMOOTHED basis, smoothing_resolution |
| Sources, AUTO scope, limit | search_options; source selection does not access sources; legacy explicit radii remain supported |

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
window rows or contribution list. The separate [setup declaration](continuum_setup_declaration.md)
can supply CONT-SETUP evidence without SPW details. Without it, missing widths
retain the backend CONT-SETUP missing-evidence diagnostic. For LINE, omitted centres/resolution/RMS likewise
remain missing evidence. Position, resolved search scope and source selection can still permit
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
artifact, not an evaluation report. Validation and request export do not save the
request or access sources. The current form must be reposted for every action.
When configured, the separate Run assessment action calls the shared entry using
explicit Archive replay/live TAP and Queue CSV source configuration and temporarily
retains an independent input/report pair; see
[browser assessment sources](ui_offline_assessment.md). Source providers remain
lazy, so validation and request export never contact Archive TAP.
Responses inherit no-store. Duplicate scalar fields and malformed row lists fail
400; the application request-size cap is 1 MiB. Jinja escapes reflected values.
These local controls are not a production multi-user authentication/lifecycle system.

## Verification

Tests cover LINE REST input, missing redshift, equivalent units with exact shared
operands, continuum usable widths, mixed intents, per-window sensitivity binding,
row editing, duplicate references, invalid quantities, partial search readiness,
backend diagnostic parity, escaped values, transport limits and request export.
Existing report browser/acceptance tests remain unchanged.

The [browser assessment increment](ui_offline_assessment.md) connects inputs to
explicit AssessmentOptions and `assess_observation()`, with independent run IDs.
Explicit live Archive TAP execution is implemented without replay fallback or
implicit live AQ acquisition. A persistent multi-user run lifecycle remains
future work.

## Automatic search scope

New forms use [AUTO](automatic_retrieval.md), without asking the researcher for
a radius. An expandable explanation shows the current bounded Archive radius,
its basis and limitations; Queue uses the supplied file without a radius filter.
This metadata is generated by the shared backend policy. It does not broaden
the supported observation types or supply missing scientific evidence.
