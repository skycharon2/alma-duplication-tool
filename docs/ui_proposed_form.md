# Proposed input form and shared validation

This document owns the current form controls and request mapping. Use
[browser assessment](ui_offline_assessment.md) for startup and source configuration,
[the scientific workflow](ui_scientific_workflow.md) for backend calculations and
[the report browser](ui_report_browser.md) for results and visualization.
[Status](status.md) owns the implementation baseline and verification register.

## Input scope and structure

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
appear in Spectral line requirements. Redshift is a single shared input. With JavaScript it sits beside the first visible LINE frequency, or the continuum frequency when no LINE panel is visible; without JavaScript it remains in shared scientific requirements. Both LINE and
CONTINUUM REST frequencies use it through [backend preparation](proposed_frequency.md).
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

The default view prioritizes fields and short entry hints. Appendix A explanations,
bandwidth conversion notes, source configuration and display limits are available
in expandable help. Run assessment and Validate input remain the primary actions;
request download is under Export input. Errors, missing evidence and unsupported
observation types remain visible. Links from diagnostics expand the containing
section before focusing the affected control. Collapsing help does not remove
inputs from submissions or change scientific validation.

## Workbench layout and help

The working Flask form visually groups Target, Scientific requirements and Data
sources, with stable anchors retained for field diagnostics. LINE, CONTINUUM and
window evidence sit within the science group. Optional explanations use floating
help or collapsed details; errors and missing-evidence diagnostics stay visible.

The form uses a compact main column and a right-hand observation
summary on desktop; small screens place the summary after the form. This is the
assessment form, not a static preview. The summary displays entered values only,
while the separate input-status panel reports the shared validator's result.
Target name, target type and geometry share a desktop row, followed by the
coordinate pair. Parameter columns use compact 36-pixel controls; phone layouts
stack the fields and retain 44-pixel controls for touch input.
Typography, page width, header and photograph attribution belong to the shared
workbench stylesheet so report pages retain the same visual shell. The proposal
stylesheet contains only form-specific layout and interactions.

Field help opens in a floating panel on mouse hover or click, with keyboard
activation and Escape-to-close. Closing with the keyboard returns focus to the
help button. Frequency and bandwidth diagrams are labelled illustrations, not
candidate data. Help text and diagrams perform no scientific calculations.
Without JavaScript, inline explanations and server form actions remain available.

The first requested LINE window stays visible. Additional requested windows are
expandable, retain distinct values and IDs, and open when a diagnostic targets
them. For continuum-only input, window centres are under optional frequency
evidence; individual bandwidths and the shared representative frequency remain
separate. All controls, including collapsed inputs, keep their existing wire
names. Switching purposes, adding windows and validation responses preserve
values. The browser reinitializes help and the summary after an assessment POST
returns validation errors.

## Observation type and support

During assessment, proposed NOMINAL widths use the shared entry's approved
nominal-to-usable mapping for CONTINUUM setup qualification. The report records
input and usable widths; unknown wider values remain unresolved. Validation and
request export do not run scientific evaluation or replace NOMINAL inputs.
See [the method decision](evidence/proposed_usable_bandwidth_decision_2026-10-07.md).

Target type offers Fixed target, Moving target and Sun; geometry separately offers
Single pointing and Mosaic. Defaults remain FIXED / SINGLE_POINTING, including
older form submissions that omit these fields. Explicit unknown values are kept
for validation, never replaced by a supported choice.

Changing a selector posts the presentation-only `scope` action. Without JavaScript,
use Update observation type. Both paths retain all entered values, units, selected
purposes, row identities and aggregate references, and clear stale validation.
They do not validate, access sources or execute assessments.

Only FIXED / SINGLE_POINTING can reach browser execution. Moving/Mosaic combinations
show their limitation and disable Run assessment. FIXED / MOSAIC additionally shows
a read-only OT export preview using the existing backend parser; it does not run
candidate discovery or change the browser execution scope. The preview requires
the native Absolute four-column header, bounds its input by the browser's 1 MiB
request limit (versus the parser's 2 MB byte limit), preserves input-row identity,
reports duplicate coordinates, and shows at most the first 20 points. It retains
the full parsed collection in session-owned server memory for one hour, with a
64-upload process limit. The form carries an opaque token; coordinates are not
stored in the session cookie. Editing requirements preserves the token. A valid
replacement invalidates the old token; an invalid replacement preserves the old
collection. Removal, expiry or server restart requires a new import. Separate
browser sessions cannot read each other's tokens. This is temporary single-process
form state, not persistent storage or an assessment result.

Mosaic uses OT positions instead of visible single-centre RA/Dec inputs. Previously
entered coordinates remain hidden for switching back to Single Pointing. Mosaic
source selection is Archive-only, and single-point AUTO-radius guidance is hidden.
The original file hash and coordinate table are expandable technical details.
Proposed 7m/12m selection and fixed-ICRS / completeness confirmations are displayed
as user declarations, not assertions inferred from the OT file. A preview without
those confirmations is allowed but does not authorize scientific evaluation.
Sun instead shows the Appendix A exemption and omits the assessment action;
retained inputs are collapsed, not discarded. The server independently rejects
direct assessment POSTs for these types before invoking the execution adapter.
No motion trajectory or executable mosaic assessment is provided yet.

Validation and request download use the existing backend contract. Valid moving
or mosaic requests report UNSUPPORTED. Valid Sun requests report NOT_APPLICABLE:
the backend already recognizes Solar exemption, but the form does not enable
the browser Solar report flow. Sun takes the existing backend exemption path even
when its selected geometry is Mosaic. No choice creates a duplication verdict.

Only valid requests can be exported, even when unsupported for execution. Selected
types are preserved in JSON. Non-fixed targets with both coordinates blank omit
the position value; supplied or partially entered coordinates remain subject to
validation. Switching back to fixed single pointing restores the entered values.
These choices do not claim complete Appendix A implementation.

## Appendix A wording and input meaning

A newly opened form selects both Archive and Queue by default. Researchers can
deselect either or both; validation and section updates preserve the submitted
selection, including an empty selection. These defaults do not configure a
source, download Queue data or contact Archive services.

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
  not unit conversion; the browser assessment uses the approved backend mapping described above.
- LINE entries supply requested window centres. FDM is required on both sides;
  one qualifying window can meet the spectral-line condition. The UI explains
  sensitivity comparison after smoothing to the same spectral resolution, without
  implementing calculations. Multiple features in one physical SPW must not be
  entered as distinct windows for continuum qualification.
- Sun is exempt, including Solar mosaics and either selected purpose. It is not
  labeled as a future duplication-checking feature or a successful empty search.

The expandable policy summary is explanatory. Thresholds, scientific methods,
pair association, approval states and aggregation continue to belong to the backend.

Follow [Run locally](ui_offline_assessment.md#run-locally) for a configured
assessment form. `ALMA_UI_REPORT_DIR` is optional and independent: existing
reports may be browsed, but form validation never selects or updates one.

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
interval endpoint entry, arbitrary predicates, mosaic/moving-target execution and
request-file import are outside the current form; the existing backend API remains
available for its wider supported input contract.

Purpose checkboxes declare the intended branches; they do not qualify a setup.
Continuum representative frequency and aggregate RMS can be entered without any
window rows or contribution list. The separate [setup declaration](continuum_setup_declaration.md)
can supply CONT-SETUP evidence without SPW details. Without it, missing widths
can leave CONT-SETUP unresolved; the backend evaluates supplied widths during
assessment. Two distinct qualifying widths can establish the condition without
per-window centre frequencies or a complete list. Fewer than two qualifying
widths do not establish a negative result unless the remaining evidence and list
completeness justify it. A declaration does not override a contradictory complete
list. These rules belong to the [setup contract](continuum_setup_declaration.md)
and [rule methods](rules.md), not to form validation.

For LINE, the proposed window bandwidth is not required for the central-frequency
coverage check. The candidate's usable coverage is separate source evidence.
Requested centre/reference, FDM evidence, planned resolution and RMS are still
needed for the corresponding LINE criteria; REST also needs shared redshift.
Omitted centres/resolution/RMS
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
These tests verify engineering behavior; current recorded verification baselines
are listed in [status](status.md#verification-register).

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

### Compact purpose choices (2026-10-20)

Each purpose has an adjacent Rules popover containing its Appendix A conditions.
The shared position, angular-resolution and independent-branch requirements are
included in both. The former full Appendix A block is no longer shown on the form.

With JavaScript enabled, explicitly checking Continuum also checks the existing
setup-declaration field. The qualification statement is visible beside the choice:
at least two distinct windows, each with usable bandwidth strictly greater than
1.8 GHz. Unchecking clears that confirmation. This is researcher-declared evidence,
not independent verification; backend conflict handling and scientific methods
are unchanged. Initial rendering never upgrades older unconfirmed selections.
Those retain a visible confirmation control, and may still use window evidence.
Without JavaScript, purpose and confirmation remain separate accessible controls.
LINE and CONTINUUM POST fields and backend evaluation contracts remain unchanged.
