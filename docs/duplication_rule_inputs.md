# Duplication rule inputs and evidence contract

Design version: 0.3. Implementation coverage is specified separately below.

The [offline request validation API](proposed_observation_api.md) implements
the documented request-side subset. Comparison-context construction from existing
ingestion outputs and duplication-rule evaluation remain planned. An accepted
request does not establish that candidate evidence is comparable or that a
duplication condition can be evaluated.

Project goal: a user describes a proposed observation; the system independently
searches Archive and Queue, checks applicable duplication conditions within a
coherent observation context, and displays conclusions, evidence and reasons
why a condition cannot be assessed. Project IDs, Member UIDs and known duplicate
labels are results or developer-test references, never required user inputs.
This document specifies evidence requirements and design acceptance cases.
The API document is the reference for currently executable request behavior.

Scope: one fixed target, single pointing, one proposed setup, multiple windows.
The user supplies proposed observations; adapters supply candidate evidence.
Candidate-side missing evidence cannot be repaired by requiring more user fields.
See the [form sketch](proposed_observation_form.md).

## 1. Sources and authority

Policy source: [Cycle 13 ALMA Users' Policies, Doc. 13.16 v1.0, March 2026,
Appendix A, printed page 22](https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies).
Policy paraphrase (all remaining sections are engineering design):

- Duplication combines position, angular resolution and a spectral condition.
- Single-field positions are compared with the other observation's half-power
  beam coverage; moving targets use names. Mosaic coverage concerns more than
  half of proposed pointings, not footprint area.
- Angular resolutions differ by at most a factor of two.
- Continuum uses aggregate-bandwidth RMS improvement of at most a factor of two
  and frequencies within a factor of 1.3. Its proposed setup needs at least two
  windows individually wider than 1.8 GHz.
- The line condition uses a requested FDM-window center inside another FDM
  observation and channel sensitivity compared after common-resolution smoothing,
  with the stated factor-of-two improvement threshold.
- Solar observations are exempt.

Do not infer a symmetric RMS ratio, HPBW radius convention, representative
continuum frequency or smoothing algorithm from this paraphrase. These need the
explicit decisions in section 7 before executable assessment.

Project-plan alignment: the user's review of `Project_Plan_9_02.pdf` identifies
sections 5.4, 5.6 and 6 as covering conditional inputs, validation and phased
scope. This alignment is based on the supplied review; independent verification
of the plan's wording and page references is pending. The original
`Internship__Duplication_Check_Tool (1).pdf`,
Nordic ARC node, August 2026, section 4 (printed page 2), was read directly for
the CASE parameters in section 8.

Additional verified sources:

- [B: ALMA effective-bandwidth knowledgebase, updated 2026-03-18](https://help.almascience.org/kb/articles/new-default-for-the-bandwidth-used-for-sensitivity-in-the-ot):
  spacing, spectral resolution and effective noise bandwidth are distinct.
  Its example gives approximately 0.122, 0.244 and 0.325 MHz respectively.
  OT `RepWindowEffectiveChannelWidth` differs from `Resolution (smoothed)`.
- [O: Cycle 13 OT Reference Manual, Doc. 13.6 v1.0, section 5.4.4.7](https://almascience.eso.org/documents-and-tools/cycle13/alma-ot-refmanual):
  representative frequency can differ from the selected window center; for
  spectral-line setups it is defined in the source rest frame.
- [H: Cycle 13 Technical Handbook, sections 3.2, 6.4 and 6.8](https://almascience.eso.org/documents-and-tools/cycle13/alma-technical-handbook):
  primary-beam FWHM is a full width, approximately `1.13 lambda/D` for ALMA
  antennas; nominal and usable widths differ; execution adds Earth-motion
  corrections to relevant OT frequency settings.

These facts justify separate storage fields; they do not by themselves specify
cross-source comparison algorithms. B/O/H below refer to these sources.

Source contracts inspected:
[Archive projection](../src/alma_duplicate/clients/archive_queries.py),
[Archive evidence](archive_client_contract.md),
[Queue fields and semantics](queue_csv_contract.md), and
[Queue persistence](queue_snapshot_store.md).

## 2. Rule-to-evidence matrix

References A/location, A/resolution and A/spectral below refer to Appendix A's
corresponding headings, not invented official clause numbers. Each row requires
coherent evidence from the same candidate context, as defined in section 6.

| ID / applicability / policy | Proposed input | Archive evidence | Queue evidence | Derivation and readiness | Missing behavior |
| --- | --- | --- | --- | --- | --- |
| POS-SINGLE: fixed, single-field interferometry; A/location | ICRS position | `s_ra`, `s_dec`; `s_region`, optional `s_fov`, `antenna_arrays`, frequency as supporting evidence | `RA`, `Dec`, geometry and array evidence | Spherical separation plus validated candidate beam coverage; beam convention/method pending Q1 | Position required for fixed-target search; missing candidate beam permits bounded search, blocks formal position rule |
| POS-MOSAIC: mosaics; A/location | Proposed pointing list or reproducible pointing-generation inputs | Actual pointing/coverage evidence; generic footprint insufficient | Mosaic fields and offsets are inputs, not a verified pointing list | Future pointing-count coverage calculation | Unsupported formal mode; never reduce to center/FOV or area overlap |
| TARGET-MOVING: moving; A/location | Explicit moving identity | `target_name` alone does not establish normalized identity | Target label alone does not establish normalized identity | Future identity normalization; no fixed-coordinate fallback | Unsupported search in first model |
| SOLAR: Sun; A final sentence | Explicit target kind | Candidate matching unnecessary for exemption | Same | `NOT_APPLICABLE` assessment, distinct from unavailable implementation | Never extend exemption to all Solar System objects |
| ANGULAR: applicable candidate comparison; A/resolution | Positive angular resolution with `REQUESTED_VALUE` meaning | `spatial_resolution` canonical evidence; optional `s_resolution` stays separate | `Req. Ang. Res.` | Convert supported units, preserve requested-versus-estimated semantics; policy comparison after context validation | Missing request or candidate quantity blocks this rule, not spatial retrieval |
| CONT-SETUP: continuum applicability; A/spectral definition | Distinct `window_id`s, per-window bandwidth kind and setup completeness | Not a substitute for proposed setup | Not a substitute for proposed setup | Count qualified proposed windows; nominal/usable interpretation pending Q2; unknown widths yield unresolved applicability when evidence cannot settle it | Intent label alone never activates rule; no imputed width or mode |
| CONT-FREQ: continuum; A/spectral | Independent setup representative frequency, optional representative-window link and reference/origin | `frequency`, full parsed support, canonical interval | `Ref.Frequency`, SPW frequencies, `Is Sky Freq?`, velocity evidence | Q3 selects comparison role and compatible reference; no automatic center/RMS fallback or overlap-only prefilter | Broad spatial retrieval permitted; frequency assessment unavailable |
| CONT-RMS: continuum; A/spectral | Direct aggregate RMS with declared basis/setup scope, or reference RMS with conversion inputs | `cont_sensitivity_bandwidth`, parsed component sensitivities with their bases | `Req.Sensitivity` plus `Ref.Frequency` and `Ref.Freq.Width` | Direct declaration does not require a bandwidth conversion; conversion requires reference/target bandwidths and approved Q4/Q5 method; applicability/frequency remain separate | Missing metadata limits affected operations, not request storage; candidate gaps remain candidate-side |
| LINE-COVERAGE: line; A/spectral | Requested SPW center, FDM evidence and frequency reference; width not generally required | Associated candidate FDM interval/reference with authoritative mode evidence; selected TAP projection lacks that mode | Associated SPW interval/reference and validated FDM evidence; no approved automatic mode derivation | Compare requested center with candidate coverage, not whole-window containment | Missing request width alone does not block center coverage; absent candidate interval or mode does |
| LINE-RMS: line; A/spectral | Window-linked RMS with independent bandwidth used for sensitivity, spectral resolution and optional smoothing evidence | `sensitivity_10kms`, `spectral_resolution`, parsed component sensitivity/resolution | `Req.Sensitivity`, `Ref.Frequency`, `Ref.Freq.Width`; same-window resolution | Preserve spacing/resolution/noise width separately; Q4/Q5 common-resolution RMS method still required | Missing noise width is not supplied by resolution; broad search remains possible |

## 3. Request evidence design and implemented subset

Consult the [API wire format](proposed_observation_api.md#wire-format) for
accepted fields. Requirements here also cover future comparison operations.

Names in this section describe evidence roles. Some are implemented by the
[request API](proposed_observation_api.md#wire-format); others specify future
comparison requirements. They are not all Python export names.
Every supplied quantity retains exact raw value/unit text, canonical value/unit,
conversion version and diagnostics. Preserve entered strings including blanks;
blank optional fields become explicit missing evidence, not zero. Reject invalid
supplied values rather than dropping them to make a request searchable.

| UI label / field | First-version format and units | Conditional requirement / semantics |
| --- | --- | --- |
| Target type / `target_kind` | FIXED, MOVING, SUN | Explicit selection; FIXED supported for search |
| Geometry / `geometry` | SINGLE_POINTING, MOSAIC | Explicit selection; single pointing supported |
| Target name / `target_name` | Original text | Optional display/provenance for fixed target; no online resolver dependency |
| Coordinates / `position` | Frame ICRS explicitly shown; RA decimal deg or HMS hourangle; Dec decimal deg or signed DMS | Required for fixed search; canonical degrees, `0 <= RA < 360`, `-90 <= Dec <= 90`; reject out-of-range raw input, do not silently wrap |
| Purpose / `intents[]` | CONTINUUM, LINE; multiple allowed | Describes intent, not proof of branch applicability |
| Angular resolution / `angular_resolution` | arcsec or mas, canonical arcsec, positive | Optional for broad search; needed for resolution rule; `meaning=REQUESTED_VALUE`, never a search upper limit |
| All windows listed? / `setup_complete` | Explicit Boolean | Only means the list contains all actual windows; parameter completeness is tracked independently |
| Representative frequency / `representative_frequency` | Independent setup-level frequency record | Optional for search; not filled from window center or RMS reference frequency |
| Representative window / `representative_window_id` | Optional stable window reference | If supplied, must refer to an existing window; membership validation is conditional on comparable frequencies and known bounds |
| Spectral windows / `spectral_windows[]` | Stable unique `window_id` within one `setup_id` | Empty lists allowed for partial scientific requests; preserve setup frequency, angular resolution and aggregate RMS independently; no invented windows |
| Frequency input / window `representation` | CENTER_BANDWIDTH, BOUNDS or PARTIAL | GHz/MHz/Hz converted to GHz; PARTIAL permits known center and missing width or a single known bound; no interval until sufficient inputs exist |
| Window width kind / `bandwidth_kind` | NOMINAL, USABLE, UNKNOWN | Preserve meaning; UNKNOWN allowed for search, formal qualification conditional on Q2 |
| Window mode / `correlator_mode` | FDM, TDM, UNKNOWN plus declared source | Optional; do not populate from intent/channel count/window width |
| Spectral resolution / window `spectral_resolution` | Hz/kHz/MHz to MHz; explicitly resolution, not spacing | Optional for search; positive if supplied; missing blocks relevant line rules |
| Frequency reference / `frequency_reference` | Record defined below, used for each frequency role | Capture sky/rest/unknown and frame separately; no implicit conversion |
| Channel spacing / window `channel_spacing` | Hz/kHz/MHz to MHz | Optional, independent from resolution and noise bandwidth |
| RMS / `sensitivities[]` | Jy/beam or mJy/beam to mJy/beam, positive | Separate entries for continuum and line scopes; never copy one into every window |
| Observing array / `array_context` | Explicit supplied array information or UNKNOWN | No inferred dish diameter; needed only where an approved derivation uses it |

Coordinate parser must validate sexagesimal components and preserve Dec sign,
including negative-zero degrees. HMS minutes/seconds must be below 60; pole Dec
must not have nonzero remaining components. Equivalent valid inputs normalize
consistently, e.g. RA `12:00:00` hourangle and `180` deg.

For complete CENTER_BANDWIDTH derive `lower=center-width/2`, `upper=center+width/2`.
For complete BOUNDS derive `interval_midpoint` and `interval_span` using
overflow-safe arithmetic, preserving the input interval kind and derivation
version. These are not automatically `requested_spw_center` or nominal bandwidth.
Using a midpoint as SPW center requires explicit, validated evidence that this
interval is centered on that SPW; cropped usable coverage supplies no such proof.
An independently declared center may accompany coverage bounds as a separate
role, not a second interval representation. Check their relationship only when
its declared semantics justify the check; do not require equality to midpoint.
Require finite `0 < lower < upper` and positive span when an interval can be
established. PARTIAL retains a known center with absent
width and `coverage_interval=None`; a known bound alone also remains partial.
Every supplied value is validated, including in incomplete windows. Negative
widths and reversed bounds are INVALID, not partial. No missing value is zero.
Dual center/width and bounds representations are rejected rather than silently
chosen. A full list of windows may still have incomplete parameters.

An interval has `kind=NOMINAL/USABLE/UNKNOWN`, origin and validation evidence.
NOMINAL arithmetic produces a nominal interval only. UNKNOWN arithmetic stays
unverified. A scalar usable width alone does not establish its placement around
the center: preserve the width but require explicit bounds or an evidenced
placement method before creating usable coverage. Explicit usable bounds retain
their declared origin; no automatic promotion to validated scientific coverage.
Keep `nominal_interval`, `usable_coverage` and sensitivity aggregate bandwidth
separate. Neither arithmetic interval nor aggregate noise bandwidth guarantees
uninterrupted usable frequency coverage.
Boolean values, NaN, infinities, conversion overflow/underflow to zero and rounded
collapsed intervals are invalid. No tolerance may turn the strict continuum
bandwidth boundary into an inclusive boundary.

### Frequency roles and reference provenance

Window center, setup `representative_frequency` and sensitivity
`reference_frequency` each store their own value/unit and `frequency_reference`.
Each also has `origin` with kind USER_DECLARED/OT_COPIED/IMPORTED/UNKNOWN, raw
label, source/version and optional source target/epoch. None is a fallback for
another. Representative frequency exists independently of sensitivity entries.
Q3 selects the role for formal continuum comparison; multiple RMS entries must
not cause arbitrary selection. No equality-to-center constraint is imposed.

`frequency_reference` records `kind=SKY/REST/UNKNOWN` and
`frame=TOPOCENTRIC/BARYCENTRIC/LSRK/LSRD/HELIOCENTRIC/UNKNOWN`, plus the raw label.
These are storage enums, not a declaration that frame transformations exist.
Unrecognized imported labels are retained with UNKNOWN and a diagnostic.
An OT value labelled Sky is recorded as OT_COPIED/SKY with its actual supplied
frame or UNKNOWN, not guessed to be execution-time topocentric. OT source-rest
representative values remain REST. REST/unknown values may be saved and searched
spatially; automated conversion/comparison is unavailable in the first model.
Window membership is checked only with sufficient compatible references/bounds;
otherwise record unresolved validation rather than declaring an invalid number.

### Sensitivity association

Each entry has identity, value/unit, purpose, basis and scope. The model also
stores optional `reference_frequency`, `bandwidth_used_for_sensitivity` and
context evidence when supplied. A storage field is not automatically required
for submission or for every calculation. Missing optional metadata remains
missing; malformed supplied values remain invalid.

Scope is SETUP (linked `setup_id`, optional contributing `window_ids`) or WINDOW
(linked window). Partial line entries may retain unresolved scope explicitly;
they remain unavailable for matched-window assessment until resolved. Supplied
dangling references are invalid. Aggregate entries may target the whole setup
even when its window list is empty or incomplete.
Basis values planned: AGGREGATE, NATIVE_CHANNEL, SMOOTHED, UNKNOWN.

`bandwidth_used_for_sensitivity` stores value/unit, meaning
EFFECTIVE_CHANNEL/AGGREGATE/USER_DEFINED/UNKNOWN, origin (including original OT
option label where applicable), and validation status. Canonical frequency width
is MHz. Missing bandwidth never falls back to resolution or spacing. A velocity
width declaration retains its unit/reference/convention; no frequency conversion
is implicit. Optional `smoothing` and `spectral_averaging` records preserve method,
factor/kernel and origin when known, without deriving missing noise bandwidth.
Optional `stokes_basis`, `polarization_basis`, `beam_context` (axes/PA/units) and
`weighting_context` preserve comparison context. Absence is explicit and may block
assessment; these are not unconditional search requirements.

- AGGREGATE has two distinct paths. DIRECT_DECLARATION stores the supplied
  aggregate continuum RMS, explicit aggregate basis and setup scope; contributing
  window IDs and effective aggregate bandwidth may be incomplete. Do not demand
  conversion inputs merely to preserve or directly compare a declared RMS when
  its relevant semantics and comparison method are established. Continuum setup
  qualification, frequency and other conditions are checked independently.
  CONVERT_FROM_REFERENCE preserves the reference RMS unchanged and requires its
  noise bandwidth, target aggregate bandwidth, applicability evidence and an
  approved conversion method before emitting a derived aggregate RMS. Missing
  conversion inputs do not invalidate the stored reference measurement. Never
  silently sum nominal widths, count overlapping bands twice or assume a noise law.
- NATIVE_CHANNEL links exactly one window and independently stores the bandwidth
  used for its RMS. Window spectral resolution remains separate evidence needed
  for resolution matching; it cannot supply effective noise bandwidth.
- SMOOTHED links its window, the target frequency or velocity resolution and the
  independent bandwidth used for sensitivity; neither substitutes for the other.
  Store velocity widths in km/s with convention/reference frequency when supplied;
  frequency conversion and noise scaling remain unavailable pending Q3/Q4.
- UNKNOWN allows a valid draft and search but produces a field-specific readiness
  reason. Dangling/duplicate supplied window references are invalid input.
- Kelvin and plain Jy/mJy without beam semantics are unsupported *user* units
  in the first model. This does not authorize relabelling Queue's existing mJy evidence.

## 4. SearchOptions and readiness

`SearchOptions` is a separate future object: explicit `radius` in arcsec/arcmin/deg,
source selection, result limit and optional candidate-filter predicates with
operators. Require a finite positive radius for bounded spatial retrieval.
It is not HPBW, source size, pointing coverage or angular resolution.
No hidden numerical default is specified by this contract.

| State axis | Planned values | Meaning |
| --- | --- | --- |
| Input validity | VALID / INVALID | Supplied values and cross-field references satisfy the contract; optional missing evidence is allowed |
| Search readiness | READY / BLOCKED / UNSUPPORTED / NOT_APPLICABLE | Fixed ICRS pointing plus valid search radius can be searched even without spectra/RMS; invalid data blocks; unsupported geometry stays explicit; Sun is separate |
| Rule readiness, per rule and candidate | EVALUABLE / UNAVAILABLE / UNSUPPORTED / NOT_APPLICABLE | Full proposed and coherent candidate evidence plus approved method required; UNAVAILABLE carries precise reason codes |

These are proposed status names, not changes to existing `ParseStatus` enums.
Readiness is not a duplicate verdict. Each reason carries rule ID, side
(PROPOSED/CANDIDATE/METHOD), field path, context/window ID, message and decision
reference. All missing reasons must remain available; one boolean is insufficient.

Reason codes: MISSING_EVIDENCE, INVALID_EVIDENCE, AMBIGUOUS_ASSOCIATION,
INCOMPATIBLE_REFERENCE, INCOMPATIBLE_UNIT, UNRESOLVED_SEMANTICS and
METHOD_NOT_IMPLEMENTED. Multiple reasons may coexist; do not compress invalid
or ambiguous evidence into missing evidence. A bad supplied request is INVALID;
a bad candidate quantity leaves request validity intact and blocks only its
affected rules. UNKNOWN reference is missing/uncertain evidence, not proof of a
known incompatibility. Valid but unconfirmed meaning is UNRESOLVED_SEMANTICS.

Candidate upper bounds such as angular resolution `<0.5 arcsec` retain their
operator inside SearchOptions. They are not a requested value of 0.5 arcsec.
Restrictive user filters and result caps must be reported with search scope and
completeness; a negative result must not imply absence of duplications globally.
Continuum retrieval cannot reuse an interval-overlap-only line prefilter without
a demonstrated recall argument. Use bounded spatial retrieval while unresolved.

### Condition completeness and result explanation

`setup_complete` concerns enumeration, not a blanket readiness gate. Given an
established bandwidth interpretation, two distinct qualifying listed windows
establish continuum setup qualification even if more windows are unlisted.
Conversely, fewer qualifying windows do not establish failure when unlisted or
unknown-width windows could change the answer. Record unresolved applicability.
For the existential line branch, a demonstrated matching window pair can support
that condition; no matches among an incomplete list cannot exclude all possible
line matches. Coverage and RMS must be satisfied by the same eligible pair.
Track request enumeration, per-field completeness, per-source retrieval
completeness and method availability separately.

For each condition store readiness independently of outcome. Planned outcomes:
SATISFIED, NOT_SATISFIED, UNDETERMINED, NOT_APPLICABLE. Only an approved applicable
method with sufficient evidence can issue a threshold result. Unsupported or
unavailable computation yields UNDETERMINED, never NOT_SATISFIED. A numerical
estimate carries approximation/method status and cannot automatically become
approved evidence for a formal threshold. Satisfaction of one condition is not
a duplicate verdict; future aggregation must preserve AND/OR scope and unknowns.

The future result must expose candidate/source IDs, matched source/execution/SPW
or Queue association, condition results, raw and canonical values/units, evidence
references, method/version/approval status and reasons/approximations. Include
independent Archive/Queue retrieval outcomes, search predicates, caps and
completeness. Failure of one source does not erase the other's returned evidence;
it marks the overall search incomplete. No-candidate results are scoped to the
executed search, not proof of non-duplication.

## 5. Deferred modes

| Mode | First-model behavior | Needed later |
| --- | --- | --- |
| Mosaic | UNSUPPORTED formal/search mode; no single-point fallback | Pointing membership or verified generation and beam coverage |
| Moving target | UNSUPPORTED; retain supplied identity | Name normalization and matching strategy |
| Sun | Assessment NOT_APPLICABLE | Separate UI explanation, no planet exemption |
| Multiple targets/upload | Unsupported | Dedicated versioned request format with per-target setup links |
| Large Program | Formal applicability pending | Explicit policy clause review; no guessed exemption |
| Kelvin | Reject unsupported input unit with explanation | Frequency, beam axes/shape, approved conversion |
| Rest-frequency evidence / SPS expansion | Preserve declared values; unsupported conversion/expansion | Explicit frame/velocity/setup methods |

## 6. Candidate-side obligations for the next adapter task

Archive: retain query provenance, completeness/projection decisions, raw-row ID,
actual source/execution/SPW association and frequency-support component reference
(row + parser version + index). Retain unassigned/ambiguous alternatives; do not
select a convenient one to make a rule evaluable. `s_resolution` and
`spatial_resolution` remain separate. Optional NULL and non-retrieved fields
retain different statuses.

Queue: use a real `QueueRowAssociation`, its raw-row identity, snapshot checksum,
source acquisition ID, and parse-run ID. Do not combine independently factorized
request/spatial/spectral components unless that association actually exists.
The stored historical summary cannot reconstruct a full context; explicitly
reparse the validated source and reference the new run when needed.

Queue `Req.Sensitivity` is mJy, linked to `Ref.Frequency` and `Ref.Freq.Width`.
Its beam meaning and relation to Archive estimated RMS are unresolved; retain
them as different evidence types. Full `frequency_support` parse results do not
by themselves establish authoritative mode, frame or sensitivity equivalence.

For LINE-RMS, select sensitivity attached to the actual matched candidate SPW
first, with its basis/reference and source context. Row-level `sensitivity_10kms`
is usable only when its representative-window relationship to that matched SPW
is confirmed; row co-location alone is not that confirmation. Queue reference
RMS used across SPWs must carry the explicit applicability method or assumption,
including approval status. An unapproved assumption is explanatory only.
Never choose the best RMS from another window, execution or source to complete
a coverage match. Return multiple coherent pair alternatives with individual
readiness rather than mixing their most favorable quantities.

## 7. Scientific decision register

Facts and application decisions are tracked separately. B/O/H facts were checked
2026-09-07; policy facts retain the Appendix A citation above. Application sign-off
by supervisor/ARC and executable-method approval are still unset. Documentation
confirmation does not imply that an application algorithm has been approved.

| ID | Confirmed fact / source | Remaining application decision and status | Blocks / required closure evidence |
| --- | --- | --- | --- |
| Q1 | Full-width FWHM and approximate antenna model (H) | OPEN: mapping to candidate pointing coverage, frequency and Archive regions | Formal position; coverage method and boundary examples |
| Q2 | Nominal/output/usable widths differ (H); policy has a strict setup-width condition (A) | OPEN: proposed width meaning used in qualification | Affected continuum applicability; explicit field/method mapping |
| Q3 | Representative frequency is a separate role (O); OT and execution references differ (H) | OPEN: formal comparison role and transformations | Frequency comparison; supported frame/epoch assumptions and examples |
| Q4 | Spacing, resolution and effective noise width are distinct (B) | OPEN: cross-source RMS, smoothing, polarization and beam compatibility | Sensitivity; approved method and valid domain; separate fields can be implemented now |
| Q5 | RMS improvement condition is policy text (A) | OPEN: directional truth table and requested/estimated semantics | Formal threshold; equality/worse-RMS examples |
| Q6 | Current selected TAP projection has no authoritative mode field (code) | OPEN: accepted candidate mode source and granularity | Line assessment; evidence validation, no channel-count inference |
| Q7 | Original task supplies positive retrieval cases (section 8) | PARTIAL: case parameters recorded; grouping/UIDs/fixtures and special-policy review OPEN | Case acceptance/special verdicts; confirmed expectations and clauses |

These block affected assessments, not implementation of valid requests or broad
candidate retrieval.

## 8. Acceptance specifications for the next implementation

These are planned tests, not tests executed by this documentation change.

| Test ID | Input / case | Expected result |
| --- | --- | --- |
| IN-01 | 180 deg versus 12:00:00 HMS; 0.5 arcsec versus 500 mas | Same canonical coordinates/resolution; distinct raw input preserved |
| IN-02 | 100 GHz versus 100000 MHz; 0.001 Jy/beam versus 1 mJy/beam | Same canonical values, scope and unit provenance |
| IN-03 | RA outside domain, pole with extra arcseconds, invalid HMS, Boolean, NaN, infinity | INVALID with precise field paths |
| IN-04 | Conflicting/dual representations, reversed/nonpositive or collapsed bounds, arithmetic overflow | INVALID; no silently chosen representation |
| IN-05 | Multiple window IDs, duplicate ID, dangling sensitivity association | Valid independent windows; reject invalid references |
| IN-06 | Complete setup with two qualified widths, widths exactly at boundary, missing width, incomplete setup | Satisfied / not satisfied / unresolved applicability as evidence permits; intent never decides; apply Q2 explicitly |
| IN-07 | Valid position/radius, no RMS or unknown mode/basis | Search READY; relevant rules list missing evidence; no assumed values |
| IN-08 | Complete user RMS but candidate Queue beam basis absent | CANDIDATE-side reason, not another required user field |
| IN-09 | Search angular upper limit versus requested angular value | Separate objects/operators; neither overwrites the other |
| IN-10 | Mixed intent, aggregate and window sensitivity entries | Preserve separate scope; do not force mutually exclusive branches |
| IN-11 | Mosaic/moving/Sun/Kelvin | Explicit statuses or unsupported unit; no fixed-target fallback |
| IN-12 | Candidate fields from different executions or Queue associations | Context rejected; never synthesize evidence |
| IN-13 | Spacing 0.122, resolution 0.244, RMS effective bandwidth 0.325 MHz (B) | Normalize and round-trip all three independently; clearing one never fills it from another |
| IN-14 | Representative frequency differs from center; no sensitivity or multiple RMS reference frequencies | Preserve independent roles; no automatic comparison-frequency choice |
| IN-15 | Known center, absent width, all windows listed | Valid partial evidence, no coverage interval; search possible; parameter completeness remains false |
| IN-16 | Nominal or UNKNOWN width; usable width without placement evidence | No promotion to validated usable coverage; no invented edges |
| IN-17 | Invalid/ambiguous/incompatible/unresolved candidate evidence | Distinct machine-readable reasons, unchanged user validity |
| IN-18 | OT Sky label, unknown frame; REST representative value | Preserve origin/reference; spatial search only until compatible transformation exists |
| IN-19 | Direct aggregate RMS/setup scope, absent bandwidth or contributor list | Valid partial request; no forced conversion; other conditions independently assessed |
| IN-20 | Reference RMS with absent target/reference bandwidth or unapproved method | Reference retained; no derived aggregate RMS; precise conversion reasons |
| IN-21 | FDM center/reference known, requested width absent; valid candidate FDM interval | Center-coverage condition may be evaluated without request width; RMS still independent |
| IN-22 | Cropped usable bounds | Midpoint/span preserved; no automatic SPW-center evidence |
| IN-23 | No listed windows, but representative frequency, angular resolution and aggregate RMS supplied | Retain all scientific inputs; bounded search possible; unresolved setup qualification |
| IN-24 | Two qualified distinct windows, list incomplete | Setup qualification established under confirmed width semantics; no enumeration veto |
| IN-25 | No line match among incomplete window list | UNDETERMINED overall line branch; cannot issue exhaustive negative |
| IN-26 | Coverage on W1, better RMS only on W2 or unlinked row scalar | No combined passing result; matched-pair sensitivity unavailable |
| IN-27 | Approximate result with unapproved method | Estimate shown separately; no formal threshold outcome |
| CASE1 | Original task parameters below | Positive retrieval expectation, not a confirmed duplicate |
| CASE2 | Original task parameters below | Same, independently scoped |

### Recorded CASE inputs

Transcribed from original internship task section 4, printed page 2; operators
and units preserved. These belong to case search conditions, not exact proposed
observation values. The frequency is a source-specified point query; no matching
tolerance or frame is supplied.

User-facing case search inputs:

| Case | RA (HMS) | Dec (DMS) | Frequency | Angular filter | Spectral filter | RMS filter |
| --- | --- | --- | --- | --- | --- | --- |
| CASE1 | 18:33:39.920 | -21:03:39.900 | 290.420 GHz | < 0.5 arcsec | < 1500 kHz | < 0.02 mJy/beam |
| CASE2 | 00:47:33.064 | -25:17:18.280 | 690.0 GHz | < 1 arcsec | < 4000 kHz | < 1 mJy/beam |

Developer reference results, not query requirements or user request fields:

| Case | Reported project | Source-stated entries | Reported Member UID(s) | Formal verdict |
| --- | --- | --- | --- | --- |
| CASE1 | 2021.A.00028.S | 1 | `uid://A001/X2df9/X1b` | Unverified |
| CASE2 | 2018.1.00294.S | 2 | `uid://A001/X133d/X9c3`, `uid://A001/X133d/X9c5` | Unverified |

The user's latest report review interprets these two RMS filters as continuum
RMS filters. Record that as case-specific supplied interpretation, not a claim
that the original task PDF labels the basis or that every request uses continuum
RMS. Member UIDs above are supplied report-review records, not independently
verified retrieval fixtures. The report filename/version/page and candidate-field
mapping remain to be pinned. Never use
expected project IDs as search constraints to make a positive test pass.

Still unresolved: independent verification of reported Member UIDs, entry grouping/count semantics, pinned
fixture, coordinate/frequency reference and search radius/tolerance, sensitivity
basis and its candidate-field mapping, and formal duplicate/non-duplicate labels.
Do not interpret stated entries as raw TAP rows or Member count without confirmation.
Known parameters are stored now; these unknowns do not justify discarding them.

## 9. Delivery boundary

The offline request model and validator are implemented as documented in the
[API](proposed_observation_api.md). The cases above mix request validation with
future comparison acceptance criteria; their presence does not claim all are
implemented tests. Comparison-context construction will reuse existing ingestion
outputs. Candidate search, verified CASE fixtures, formal rules and HTML remain
planned. Request round-trip validation does not restore historical Python objects.

Current spectral mapping uses an overall parse-result validity gate, not
independent frequency and RMS usability. See the
[implemented mapping boundary](data_model.md#spectral-mapping-boundary).
