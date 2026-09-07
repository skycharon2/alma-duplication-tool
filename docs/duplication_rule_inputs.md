# Duplication rule inputs and evidence contract

Design version: 0.1. Reviewed: 2026-09-07. Implementation baseline: `9e25010`.
Status: **proposed input contract**, not an implemented request API or rule engine.
This deliverable defines the next model and its acceptance cases. It changes no
ingestion, reconstruction, policy decision, or live-query behavior.

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

The latest project plan cited by the user was not supplied as a readable file
for this change. Section numbering from that plan is not independently verified
here. Phase scope follows the user's supplied requirements.

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
| CONT-FREQ: continuum; A/spectral | Explicit comparison/reference frequency linked to setup; frame | `frequency`, full parsed support, canonical interval | `Ref.Frequency`, SPW frequencies, `Is Sky Freq?`, velocity evidence | Frame comparability and reference-frequency meaning pending Q3; do not require interval overlap as a generic prefilter | Broad spatial retrieval permitted; frequency assessment unavailable |
| CONT-RMS: continuum; A/spectral | RMS, aggregate basis, reference frequency, contributing window IDs and effective reference bandwidth | `cont_sensitivity_bandwidth`, parsed component sensitivities with their bases | `Req.Sensitivity` plus `Ref.Frequency` and `Ref.Freq.Width` | Preserve candidate estimate/request distinction; compatible bases and approved directional comparison needed (Q4/Q5) | Missing candidate basis is candidate-side, not an extra form requirement |
| LINE-COVERAGE: line; A/spectral | Per-window center, bandwidth/bounds, FDM evidence and frame | Full support components and assignments; no authoritative FDM field in selected TAP projection | Same-number SPW frequency/bandwidth/resolution evidence; no approved mode derivation | Compare center with candidate interval only when frames and both modes established | Unknown mode means unavailable line rule; continue broad retrieval; never infer from `em_xel` or bandwidth |
| LINE-RMS: line; A/spectral | Window-linked RMS basis and spectral resolution; smoothing target when applicable | `sensitivity_10kms`, `spectral_resolution`, parsed component sensitivity/resolution | `Req.Sensitivity`, `Ref.Frequency`, `Ref.Freq.Width`; same-window resolution | Keep native, velocity-reference and aggregate RMS separate; approved common-resolution calculation required (Q4/Q5) | Missing width/basis blocks line sensitivity rule; never assume spacing equals resolution |

## 3. Proposed request fields (future model)

All names in this section are planned fields, not existing Python exports.
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
| Setup completeness / `setup_complete` | Explicit Boolean | Incomplete draft supported; missing windows cannot be assumed absent |
| Spectral windows / `spectral_windows[]` | Stable unique `window_id` within one `setup_id` | One or more for a spectrally described request; zero allowed only as a spatial-only draft |
| Frequency input / window `representation` | CENTER_BANDWIDTH or BOUNDS | GHz/MHz/Hz converted to GHz; positive finite quantities; exactly one representation in first UI |
| Window width kind / `bandwidth_kind` | NOMINAL, USABLE, UNKNOWN | Preserve meaning; UNKNOWN allowed for search, formal qualification conditional on Q2 |
| Window mode / `correlator_mode` | FDM, TDM, UNKNOWN plus declared source | Optional; do not populate from intent/channel count/window width |
| Spectral resolution / window `spectral_resolution` | Hz/kHz/MHz to MHz; explicitly resolution, not spacing | Optional for search; positive if supplied; missing blocks relevant line rules |
| Frequency frame / window `frequency_frame` | Explicit supplied frame or UNKNOWN | No silent TOPO/LSRK assumption; first model accepts already sky frequencies; rest-frequency conversion deferred |
| RMS / `sensitivities[]` | Jy/beam or mJy/beam to mJy/beam, positive | Separate entries for continuum and line scopes; never copy one into every window |
| Observing array / `array_context` | Explicit supplied array information or UNKNOWN | No inferred dish diameter; needed only where an approved derivation uses it |

Coordinate parser must validate sexagesimal components and preserve Dec sign,
including negative-zero degrees. HMS minutes/seconds must be below 60; pole Dec
must not have nonzero remaining components. Equivalent valid inputs normalize
consistently, e.g. RA `12:00:00` hourangle and `180` deg.

For CENTER_BANDWIDTH derive `lower=center-width/2`, `upper=center+width/2`.
For BOUNDS derive center and width using overflow-safe arithmetic. Require final
finite `0 < lower < upper`, positive width, and a center inside the interval.
API dual representations must either be rejected as ambiguous or explicitly
validated; version 0.1 chooses rejection. Do not choose one silently.
Boolean values, NaN, infinities, conversion overflow/underflow to zero and rounded
collapsed intervals are invalid. No tolerance may turn the strict continuum
bandwidth boundary into an inclusive boundary.

### Sensitivity association

Each entry has `sensitivity_id`, `purpose`, `window_ids`, `value`, `unit`,
`basis`, `reference_frequency`, and optional `reference_width` with its kind/unit.
Basis values planned: AGGREGATE, NATIVE_CHANNEL, SMOOTHED, UNKNOWN.

- AGGREGATE links all contributing distinct windows and an explicit effective
  bandwidth; do not silently sum overlapping windows or nominal widths.
- NATIVE_CHANNEL links exactly one window and its actual spectral-resolution
  evidence. A bare channel count/spacing cannot supply that resolution.
- SMOOTHED links its window and the stated frequency or velocity resolution.
  Store velocity widths in km/s with convention/reference frequency when supplied;
  frequency conversion and noise scaling remain unavailable pending Q3/Q4.
- UNKNOWN allows a valid draft and search but produces a field-specific readiness
  reason. Dangling/duplicate window references are invalid input.
- Kelvin and plain Jy/mJy without beam semantics are unsupported *user* units
  in version 0.1. This does not authorize relabelling Queue's existing mJy evidence.

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
| Rule readiness, per rule and candidate | EVALUABLE / MISSING_EVIDENCE / PENDING_INTERPRETATION / UNSUPPORTED / NOT_APPLICABLE | Full proposed and coherent candidate evidence plus approved method required; a valid request alone cannot establish EVALUABLE |

These are proposed status names, not changes to existing `ParseStatus` enums.
Readiness is not a duplicate verdict. Each reason carries rule ID, side
(PROPOSED/CANDIDATE/METHOD), field path, context/window ID, message and decision
reference. All missing reasons must remain available; one boolean is insufficient.

Candidate upper bounds such as angular resolution `<0.5 arcsec` retain their
operator inside SearchOptions. They are not a requested value of 0.5 arcsec.
Restrictive user filters and result caps must be reported with search scope and
completeness; a negative result must not imply absence of duplications globally.
Continuum retrieval cannot reuse an interval-overlap-only line prefilter without
a demonstrated recall argument. Use bounded spatial retrieval while unresolved.

## 5. Deferred modes

| Mode | Version 0.1 behavior | Needed later |
| --- | --- | --- |
| Mosaic | UNSUPPORTED formal/search mode; no single-point fallback | Pointing membership or verified generation and beam coverage |
| Moving target | UNSUPPORTED; retain supplied identity | Name normalization and matching strategy |
| Sun | Assessment NOT_APPLICABLE | Separate UI explanation, no planet exemption |
| Multiple targets/upload | Unsupported | Dedicated versioned request format with per-target setup links |
| Large Program | Formal applicability pending | Explicit policy clause review; no guessed exemption |
| Kelvin | Reject unsupported input unit with explanation | Frequency, beam axes/shape, approved conversion |
| Rest-frequency request / SPS expansion | Unsupported conversion/expansion | Explicit frame/velocity/setup methods |

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

## 7. Scientific decision register

All items are OPEN. Proposed owner: supervisor/ARC for scientific confirmation;
developer records the answer and executable method. Confirmed by/date: **unset**.
No item may silently become an implementation default.

| ID | Decision needed | Blocks | Evidence to record on resolution |
| --- | --- | --- | --- |
| Q1 | HPBW coverage convention, reference frequency, antenna/array model and applicability of `s_fov`/regions | Formal position rule | Approved formula, diameter/shape assumptions, handbook version, boundary tests |
| Q2 | Nominal versus usable bandwidth for proposed setup qualification, distinct-window identity | Formal continuum applicability where semantics unknown | Definition, setup scope, strict-boundary tests |
| Q3 | Comparable frequency frames and representative continuum frequency; velocity conversion convention | Frequency assessment | Source semantics, transform inputs, numerical examples |
| Q4 | RMS basis, smoothing method, correlations, beam/weighting compatibility; no assumed square-root law | Sensitivity assessment | Valid domain, algorithm/version, examples and unsupported cases |
| Q5 | Directional RMS improvement interpretation, equality and worse-sensitivity cases; Queue requested vs Archive estimated comparison | Formal RMS threshold | Signed-off truth table, field meanings and boundary tests |
| Q6 | Authoritative candidate FDM evidence and granularity | Line branch | Accepted source and validation; channel-count inference excluded |
| Q7 | Large Program and other special applicability; case ground truth | Special modes / verdict acceptance | Policy clauses and supervisor-confirmed labels |

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
| CASE1 | Supervisor positive retrieval case: project `2021.A.00028.S` | Retrieve confirmed expected Member OUS once exact case fixture is supplied |
| CASE2 | Supervisor positive retrieval case: project `2018.1.00294.S` | Same, with independent provenance and predicates |

CASE project identifiers are supplied context, not enough to fabricate a Member
UID, exact coordinates or an expected duplicate verdict. Before implementation,
pin each case's original predicates, expected Member UID(s), source fixture and
supervisor confirmation. Missing specifics remain TODO, not invented fixture data.

## 9. Delivery boundary

This PR delivers this contract and a static form sketch. Next PR implements the
fixed-target request model/validator and IN-01 through IN-11 as applicable.
The following PR implements coherent adapters and candidate search (IN-12 and
confirmed CASE fixtures). Formal verdict rules and full HTML follow separately.
