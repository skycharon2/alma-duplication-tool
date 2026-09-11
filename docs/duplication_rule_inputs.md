# Duplication rule inputs and evidence contract

Design version: 0.3. Implementation coverage is specified separately below.

The [offline request validation API](proposed_observation_api.md) implements
the documented request-side subset. [Offline comparison-context construction](comparison_contexts.md)
reuses existing ingestion outputs. [Offline search planning and limited spatial
adaptation](search_plan_spatial.md) are also implemented; orchestrated candidate
search and duplication-rule evaluation remain planned. An accepted
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

Project design source: `Project_Plan_9_07.pdf`, sections 5.4–5.6, covers
comparison contexts, evidence provenance and evaluability. The project review
records these sections as checked against the PDF. Its abstract's statement
that the request API is not implemented is historical. The supplied
`Project_Plan_9_10.pdf` also carries a September 7, 2026 internal update date and
retains that earlier implementation status. Use those plans for architectural
intent, and the [request API](proposed_observation_api.md),
[comparison contract](comparison_contexts.md) and [search/spatial contract](search_plan_spatial.md)
for current executable behavior.

The original `Internship__Duplication_Check_Tool (1).pdf`, Nordic ARC node,
August 2026, section 4 (printed page 2), supplies the CASE search parameters.
`Weekly_Progress_Report.pdf` supplies the later candidate and interpretation
records identified in section 8. These document references record the supplied
project review's verification; they do not assert a new PDF inspection or an
independent reproduction of the reported retrieval results.

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
| POS-SINGLE: fixed, single-field interferometry; A/location | ICRS position | `s_ra`, `s_dec`; `s_region`, optional `s_fov`, `antenna_arrays`, frequency as supporting evidence | `RA`, `Dec`, geometry and array evidence | Spherical separation plus validated candidate beam coverage; an opt-in user-frequency formula selector exists (see primary_beam_search.md), but formal frequency/geometry scope remains pending Q1 | Position required for fixed-target search; missing candidate beam permits bounded search, blocks formal position rule |
| POS-MOSAIC: mosaics; A/location | Proposed pointing list or reproducible pointing-generation inputs | Actual pointing/coverage evidence; generic footprint insufficient | Mosaic fields and offsets are inputs, not a verified pointing list | Future pointing-count coverage calculation | Unsupported formal mode; never reduce to center/FOV or area overlap |
| TARGET-MOVING: moving; A/location | Explicit moving identity | `target_name` alone does not establish normalized identity | Target label alone does not establish normalized identity | Future identity normalization; no fixed-coordinate fallback | Unsupported search in first model |
| SOLAR: Sun; A final sentence | Explicit target kind | Candidate matching unnecessary for exemption | Same | `NOT_APPLICABLE` assessment, distinct from unavailable implementation | Never extend exemption to all Solar System objects |
| ANGULAR: applicable candidate comparison; A/resolution | Positive angular resolution with `REQUESTED_VALUE` meaning | `spatial_resolution` canonical evidence; optional `s_resolution` stays separate | `Req. Ang. Res.` | Convert supported units, preserve requested-versus-estimated semantics; policy comparison after context validation | Missing request or candidate quantity blocks this rule, not spatial retrieval |
| CONT-SETUP: continuum applicability; A/spectral definition | Distinct `window_id`s, per-window bandwidth kind and setup completeness | Not a substitute for proposed setup | Not a substitute for proposed setup | Count qualified proposed windows; usable interpretation reported, approval/mapping pending Q2; unknown widths yield unresolved applicability when evidence cannot settle it | Intent label alone never activates rule; no imputed width or mode |
| CONT-FREQ: continuum; A/spectral | Independent setup representative frequency, optional representative-window link and reference/origin | `frequency`, full parsed support, canonical interval | `Ref.Frequency`, SPW frequencies, `Is Sky Freq?`, velocity evidence | Q3 selects comparison role and compatible reference; no automatic center/RMS fallback or overlap-only prefilter | Broad spatial retrieval permitted; frequency assessment unavailable |
| CONT-RMS: continuum; A/spectral | Direct aggregate RMS with declared basis/setup scope, or reference RMS with conversion inputs | `cont_sensitivity_bandwidth`, parsed component sensitivities with their bases | `Req.Sensitivity` plus `Ref.Frequency` and `Ref.Freq.Width` | Direct declaration does not require a bandwidth conversion; conversion requires reference/target bandwidths and approved Q4/Q5 method; applicability/frequency remain separate | Missing metadata limits affected operations, not request storage; candidate gaps remain candidate-side |
| LINE-COVERAGE: line; A/spectral | Requested SPW center, FDM evidence and frequency reference; width not generally required | Associated candidate FDM interval/reference with authoritative mode evidence; selected TAP projection lacks that mode | Associated SPW interval/reference and validated FDM evidence; no approved automatic mode derivation | Compare requested center with candidate coverage, not whole-window containment | Missing request width alone does not block center coverage; absent candidate interval or mode does |
| LINE-RMS: line; A/spectral | Window-linked RMS with independent bandwidth used for sensitivity, spectral resolution and optional smoothing evidence | `sensitivity_10kms`, `spectral_resolution`, parsed component sensitivity/resolution | `Req.Sensitivity`, `Ref.Frequency`, `Ref.Freq.Width`; same-window resolution | Preserve spacing/resolution/noise width separately; Q4/Q5 common-resolution RMS method still required | Missing noise width is not supplied by resolution; broad search remains possible |

## 3. Request evidence design and implemented subset

The [request API](proposed_observation_api.md#wire-format) owns accepted fields,
units, shapes, normalization, interval arithmetic and input validation. This
section owns the evidence semantics needed by future rules; its role names are
not additional accepted wire fields or new Python export names.

Three distinctions must survive input normalization and candidate adaptation:

- A listed setup may be complete in enumeration but incomplete in parameters.
  Missing window width does not alone block line-center coverage; it cannot
  create a coverage interval.
- A midpoint/span derived from bounds does not establish a requested SPW center
  or nominal bandwidth. Cropped usable bounds are not proof of centered coverage.
- Nominal intervals, usable coverage and aggregate noise bandwidth have different
  meanings. A scalar usable width without placement evidence cannot supply edges;
  arithmetic or supplied bounds are not automatic scientific validation.

The strict continuum bandwidth boundary remains a policy requirement; numerical
input tolerances cannot turn it into an inclusive threshold. Q2 defines the
accepted bandwidth interpretation for future qualification.

### Frequency roles and reference provenance

Window center, setup `representative_frequency` and sensitivity
`reference_frequency` each store their own value/unit and `frequency_reference`.
Each also has `origin` with kind USER_DECLARED/OT_COPIED/IMPORTED/UNKNOWN, raw
label, source/version and optional source target/epoch. None is a fallback for
another. Representative frequency exists independently of sensitivity entries.
Q3 selects the role for formal continuum comparison; multiple RMS entries must
not cause arbitrary selection. No equality-to-center constraint is imposed.

Frequency kind/frame and origin fields use the [API representation](proposed_observation_api.md#wire-format).
These preserve declarations; they do not implement frame transformations. An OT
Sky label cannot establish execution-time topocentric frequency. REST and unknown
references may support spatial discovery, but require Q3 before automated
frequency comparison. Unknown and known-incompatible references remain different.

### Sensitivity association

The [API sensitivity representation](proposed_observation_api.md#roles-partial-coverage-and-association)
owns request fields, accepted bases, scope validation and missing-value behavior.
For rules, sensitivity must retain its setup/window association, reference,
noise-bandwidth meaning, units and provenance. Unresolved line scope blocks
matched-window assessment without invalidating otherwise valid evidence.

Bandwidth used for sensitivity must not fall back to channel spacing or spectral
resolution. Velocity widths need their own reference and convention; conversion
is not implicit. Smoothing/averaging, Stokes, polarization, beam and weighting
context may block a specific comparison, but are not unconditional search inputs.
These are evidence requirements, not extra top-level wire fields.

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

`SearchOptions` validation and `SearchReadiness` are owned by the
[request API](proposed_observation_api.md#entry-point-and-result); `is_valid` is a
Boolean, not a VALID/INVALID enum. [Search planning](search_plan_spatial.md)
retains explicit predicates and limits separately from observation parameters.
The [status guide](README.md#current-capabilities-and-status-meanings) separates
request readiness, source completeness, query binding and individual selection.
None establishes rule readiness or a duplicate verdict.

Per-rule/per-candidate readiness remains planned: EVALUABLE, UNAVAILABLE,
UNSUPPORTED and NOT_APPLICABLE require coherent evidence and an approved method.
These are design names, not an implemented enum and not changes to ParseStatus.
Request issues expose PROPOSED/METHOD sides; the comparison layer has independent
[evidence dimensions](comparison_contexts.md#evidence-and-states), not a formal
CANDIDATE-side readiness evaluator.

The future per-rule reason contract additionally needs candidate context/window
identity and decision references. Planned reason categories include
MISSING_EVIDENCE, INVALID_EVIDENCE, AMBIGUOUS_ASSOCIATION,
INCOMPATIBLE_REFERENCE, INCOMPATIBLE_UNIT, UNRESOLVED_SEMANTICS and
METHOD_NOT_IMPLEMENTED. This is not a claim that all these are current request
issue codes or attributes. Preserve simultaneous reasons. Bad supplied input
makes `is_valid=False`; a bad candidate quantity cannot invalidate the request.
UNKNOWN reference is uncertain evidence, not proof of known incompatibility.
Readiness is never a duplicate verdict.

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

## 6. Candidate-side guarantees and remaining obligations

### Current context-construction guarantees

The [comparison contract](comparison_contexts.md#context-identity-and-association)
owns implemented row/component membership, alternatives and evidence states.
Its [provenance section](comparison_contexts.md#provenance) defines reference
fields: Queue acquisition/run IDs currently remain `None`, including for parse
results obtained through the snapshot store. The builders preserve source
contexts without retrieving candidates or assessing rules.

### Remaining persistence and assessment requirements

A future store-aware caller/adapter must explicitly bind acquisition and parse-run
records to their resulting contexts, without inventing IDs from checksums. Today
callers retain those records separately. A stored historical summary cannot
reconstruct a full context: explicitly reparse the validated source to obtain
current in-memory evidence, retaining the new run separately until binding exists.

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

Facts, reported feedback and executable-method approval are distinct. The
[reported oral-feedback record](evidence/scientific_feedback.md) preserves the
user's paraphrase, missing discussion date/original wording, scope and closure
requirements. It is not independent written confirmation. Existing B/O/H and
policy citations retain their earlier provenance; this update does not reverify
them. No Q1–Q3 method is enabled or marked CLOSED by this change.

| ID | Existing fact / source | Current decision status | Remaining closure requirement |
| --- | --- | --- | --- |
| Q1 | Full-width FWHM and approximate antenna model (H) | PARTIAL: oral feedback reported | Candidate frequency ownership, Archive mapping, geometry/array scope and boundary examples |
| Q2 | Nominal/output/usable widths differ (H); strict setup-width condition (A) | PARTIAL: usable proposed-window bandwidth reported; written confirmation pending | Approved field mapping and usable-width qualification examples; no blanket Archive conversion |
| Q3 | Representative frequency is a separate role (O); OT/execution references differ (H) | PARTIAL: center-frequency average reported | Window membership on each side, averaging definition, enumeration completeness, identity and compatible references |
| Q4 | Spacing, resolution and effective noise width are distinct (B) | OPEN: formula and applicable domain pending | RMS/smoothing method, polarization and beam compatibility |
| Q5 | RMS improvement condition is policy text (A) | OPEN: not discussed in this feedback | Directional truth table, requested/estimated semantics and equality/worse-RMS examples |
| Q6 | Selected TAP projection has no authoritative mode field (code) | OPEN: not discussed in this feedback | Accepted mode evidence and granularity; UI classification alone is not authoritative mode |
| Q7 | Reported retrieval cases are recorded in section 8 | PARTIAL: no new confirmation in this feedback | Independent UID recall, grouping/count semantics, fixtures and special-policy review |

These limit affected formal assessments, not valid request storage or candidate
retrieval. The feedback record provides conditional CONT-SETUP acceptance cases;
they are design expectations, not completed executable policy tests.

## 8. Acceptance specifications and implementation coverage

The table distinguishes existing executable behavior from remaining acceptance
requirements. Test references identify existing assertions, not complete policy
acceptance. `-a`/`-b` split an original mixed case into its implemented boundary
and remaining work; the original IN/CASE identity is retained. No existing test
is renamed. Future rule and CASE results are not implied by passing input tests.

Test references: [R](../tests/unit/test_proposed_observation.py) = request tests;
[C](../tests/integration/test_comparison_contexts.py) = context tests;
[S](../tests/integration/test_search_plan_spatial.py) = search/spatial tests.
A test name below is within its indicated file.

| Test ID | Input / case | Expected result | Implementation status | Corresponding tests | Remaining work |
| --- | --- | --- | --- | --- | --- |
| IN-01 | 180 deg versus 12:00:00 HMS; 0.5 arcsec versus 500 mas | Same canonical coordinates/resolution; distinct raw input preserved | Implemented at input/context boundary | R: `test_units_coordinates_and_raw_input_are_independent` | Formal assessment remains separate. |
| IN-02 | 100 GHz versus 100000 MHz; 0.001 Jy/beam versus 1 mJy/beam | Same canonical values, scope and unit provenance | Implemented at input/context boundary | R: `test_units_coordinates_and_raw_input_are_independent` | Formal assessment remains separate. |
| IN-03 | RA outside domain, pole with extra arcseconds, invalid HMS, Boolean, NaN, infinity | `is_valid=False` with precise field paths | Implemented at input/context boundary | R: `test_bad_coordinates_rejected`, `test_invalid_quantity_never_produces_request` | Formal assessment remains separate. |
| IN-04 | Conflicting/dual representations, reversed/nonpositive or collapsed bounds, arithmetic overflow | `is_valid=False`; no silently chosen representation | Implemented at input/context boundary | R: `test_invalid_window_arithmetic`, `test_bad_associations`, `test_canonical_overflow_and_underflow` | Formal assessment remains separate. |
| IN-05 | Multiple window IDs, duplicate ID, dangling sensitivity association | Valid independent windows; reject invalid references | Implemented at input/context boundary | R: `test_bad_associations`, `test_line_rms_missing_is_reported_per_window` | Formal assessment remains separate. |
| IN-06 | Complete setup with two qualified widths, widths exactly at boundary, missing width, incomplete setup | Satisfied / not satisfied / unresolved applicability as evidence permits; intent never decides; apply Q2 explicitly | Planned | No completed acceptance test claimed | Resolve Q2 width semantics; implement strict setup qualification and boundary cases. |
| IN-07-a | Valid position/radius, no RMS or unknown mode/basis | Implemented subset: Request search readiness and proposed-side missing evidence are implemented. | Implemented subset | R: `test_missing_requested_width_not_a_line_center_requirement`, `test_line_rms_missing_is_reported_per_window` | See IN-07-b. |
| IN-07-b | Same case; remaining acceptance | Search READY; relevant rules list missing evidence; no assumed values | Planned remainder | No full acceptance test claimed | candidate-specific rule readiness remains planned. |
| IN-08 | Complete user RMS but candidate Queue beam basis absent | CANDIDATE-side reason, not another required user field | Planned | No completed acceptance test claimed | Implement candidate-side beam/basis readiness without adding user-input requirements. |
| IN-09 | Search angular upper limit versus requested angular value | Separate objects/operators; neither overwrites the other | Implemented at input/context boundary | R: `test_search_predicates_keep_operator_and_do_not_fill_request`; S: `test_plan_preserves_single_sided_filter_and_no_observation_parameter_filters` | Formal assessment remains separate. |
| IN-10-a | Mixed intent, aggregate and window sensitivity entries | Implemented subset: Separate aggregate and window records are covered individually. | Implemented subset | R: `test_direct_aggregate_without_windows_or_noise_width_is_valid`, `test_three_widths_and_optional_smoothing_context_never_fill_each_other` | See IN-10-b. |
| IN-10-b | Same case; remaining acceptance | Preserve separate scope; do not force mutually exclusive branches | Planned remainder | No full acceptance test claimed | combined mixed-intent acceptance and formal branch aggregation remain to be verified. |
| IN-11-a | Mosaic/moving/Sun/Kelvin | Implemented subset: Request UNSUPPORTED/NOT_APPLICABLE and unit errors are implemented. | Implemented subset | R: `test_unsupported_modes_preserved`, `test_unit_unsupported_vs_method_unimplemented` | See IN-11-b. |
| IN-11-b | Same case; remaining acceptance | Explicit statuses or unsupported unit; no fixed-target fallback | Planned remainder | No full acceptance test claimed | formal assessment and UI explanation remain planned. |
| IN-12 | Candidate fields from different executions or Queue associations | Reject broken row/component references and preserve coherent source contexts; do not synthesize cross-execution or Queue combinations. | Implemented at input/context boundary | C: `test_tampered_queue_association_fails_instead_of_creating_combination`, `test_selected_component_does_not_borrow_another_windows_rms` | Formal assessment remains separate. |
| IN-13-a | Spacing 0.122, resolution 0.244, RMS effective bandwidth 0.325 MHz (B) | Implemented subset: Normalization and independent missing-field retention are tested. | Implemented subset | R: `test_three_widths_and_optional_smoothing_context_never_fill_each_other` | See IN-13-b. |
| IN-13-b | Same case; remaining acceptance | Normalize and round-trip all three independently; clearing one never fills it from another | Planned remainder | No full acceptance test claimed | full round-trip acceptance and approved noise calculations are not established by the cited test. |
| IN-14-a | Representative frequency differs from center; no sensitivity or multiple RMS reference frequencies | Implemented subset: Independent roles are preserved. | Implemented subset | R: `test_representative_roles_and_no_usable_midpoint_assumption`, `test_direct_aggregate_without_windows_or_noise_width_is_valid` | See IN-14-b. |
| IN-14-b | Same case; remaining acceptance | Preserve independent roles; no automatic comparison-frequency choice | Planned remainder | No full acceptance test claimed | multi-RMS selection acceptance and Q3 formal comparison-frequency choice remain planned. |
| IN-15 | Known center, absent width, all windows listed | Valid partial evidence, no coverage interval; bounded search can be READY despite absent width. No separate parameter-completeness Boolean is exposed. | Implemented at input/context boundary | R: `test_missing_requested_width_not_a_line_center_requirement` | Formal assessment remains separate. |
| IN-16 | Nominal or UNKNOWN width; usable width without placement evidence | No promotion to validated usable coverage; no invented edges | Implemented at input/context boundary | R: `test_interval_kind_is_not_promoted` | Formal assessment remains separate. |
| IN-17-a | Invalid/ambiguous/incompatible/unresolved candidate evidence | Implemented subset: Context diagnostics and separate evidence dimensions are implemented. | Implemented subset | C: `test_bad_other_component_keeps_conservative_mapping_gate_and_raw_evidence`, `test_archive_unit_failure_does_not_erase_context_or_claim_comparability` | See IN-17-b. |
| IN-17-b | Same case; remaining acceptance | Distinct machine-readable reasons, unchanged user validity | Planned remainder | No full acceptance test claimed | complete per-rule candidate reason taxonomy remains planned. |
| IN-18-a | OT Sky label, unknown frame; REST representative value | Implemented subset: REST/unknown or differing references are retained. | Implemented subset | R: `test_unit_unsupported_vs_method_unimplemented`, `test_nominal_membership_preserves_missing_and_known_reference_differences` | See IN-18-b. |
| IN-18-b | Same case; remaining acceptance | Preserve origin/reference; spatial search only until compatible transformation exists | Planned remainder | No full acceptance test claimed | OT-origin end-to-end acceptance and compatible transformations remain unverified/unimplemented. |
| IN-19-a | Direct aggregate RMS/setup scope, absent bandwidth or contributor list | Implemented subset: Partial direct aggregate input is accepted without forced conversion. | Implemented subset | R: `test_direct_aggregate_without_windows_or_noise_width_is_valid` | See IN-19-b. |
| IN-19-b | Same case; remaining acceptance | Valid partial request; no forced conversion; other conditions independently assessed | Planned remainder | No full acceptance test claimed | independent formal condition assessment remains planned. |
| IN-20-a | Reference RMS with absent target/reference bandwidth or unapproved method | Implemented subset: Reference retention and missing/capability issues are implemented. | Implemented subset | R: `test_reference_aggregate_does_not_manufacture_converted_rms` | See IN-20-b. |
| IN-20-b | Same case; remaining acceptance | Reference retained; no derived aggregate RMS; precise conversion reasons | Planned remainder | No full acceptance test claimed | approved conversion and candidate-aware reason completeness remain planned. |
| IN-21-a | FDM center/reference known, requested width absent; valid candidate FDM interval | Implemented subset: Request center is retained without width and without a request-side LINE-COVERAGE missing issue. | Implemented subset | R: `test_missing_requested_width_not_a_line_center_requirement` | See IN-21-b. |
| IN-21-b | Same case; remaining acceptance | Center-coverage condition may be evaluated without request width; RMS still independent | Planned remainder | No full acceptance test claimed | actual candidate FDM coverage/RMS assessment remains planned. |
| IN-22 | Cropped usable bounds | Midpoint/span preserved; no automatic SPW-center evidence | Implemented at input/context boundary | R: `test_bounds_midpoint_is_not_spw_center` | Formal assessment remains separate. |
| IN-23-a | No listed windows, but representative frequency, angular resolution and aggregate RMS supplied | Implemented subset: Empty-window request storage and bounded-search readiness are covered. | Implemented subset | R: `test_direct_aggregate_without_windows_or_noise_width_is_valid`, `test_search_predicates_keep_operator_and_do_not_fill_request` | See IN-23-b. |
| IN-23-b | Same case; remaining acceptance | Retain all scientific inputs; bounded search possible; unresolved setup qualification | Planned remainder | No full acceptance test claimed | the combined three-field acceptance fixture and formal setup qualification remain outstanding. |
| IN-24 | Two qualified distinct windows, list incomplete | Setup qualification established under confirmed width semantics; no enumeration veto | Planned | No completed acceptance test claimed | Resolve Q2; test qualification with incomplete enumeration. |
| IN-25 | No line match among incomplete window list | UNDETERMINED overall line branch; cannot issue exhaustive negative | Planned | No completed acceptance test claimed | Implement incomplete-list line aggregation without an exhaustive negative. |
| IN-26-a | Coverage on W1, better RMS only on W2 or unlinked row scalar | Implemented subset: Context construction preserves SPW/row RMS association. | Implemented subset | C: `test_selected_component_does_not_borrow_another_windows_rms`, `test_queue_preserves_only_observed_combinations_and_no_per_spw_rms_copy` | See IN-26-b. |
| IN-26-b | Same case; remaining acceptance | No combined passing result; matched-pair sensitivity unavailable | Planned remainder | No full acceptance test claimed | formal matched-pair outcomes remain planned. |
| IN-27 | Approximate result with unapproved method | Estimate shown separately; no formal threshold outcome | Planned | No completed acceptance test claimed | Implement method approval status and separation of estimates from formal outcomes. |
| CASE1 | Original task parameters below | Positive retrieval expectation, not a confirmed duplicate | Retrieval executed against live Archive TAP: PASSED (weak recall) | [tests/live/test_case_retrieval.py](../tests/live/test_case_retrieval.py) (`--run-live`) | Grouping/count semantics (Q7) and a formal duplication verdict remain open; see "Executed retrieval evidence" below. |
| CASE2 | Original task parameters below | Same, independently scoped | Retrieval executed against live Archive TAP: PASSED (weak recall) | [tests/live/test_case_retrieval.py](../tests/live/test_case_retrieval.py) (`--run-live`) | Grouping/count semantics (Q7) and a formal duplication verdict remain open; see "Executed retrieval evidence" below. |

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

### Executed retrieval evidence (2026-09-10 run)

[tests/live/test_case_retrieval.py](../tests/live/test_case_retrieval.py) was
run with `--run-live` against the live Archive TAP service (developer
environment; endpoint/date not independently re-verified by this document
beyond the test run itself). Both cases PASSED: every reported Member UID
above was present among the retrieved Archive rows within the test's 10
arcsec engineering search radius. This confirms retrieval recall only, not a
duplication verdict, grouping, or count -- see the test's module docstring
for that boundary.

| Case | Retrieved rows | Disposition split | Matched Member UID row(s) | Local spatial-adapter reason on matched rows |
| --- | ---: | --- | --- | --- |
| CASE1 | 336 | 200 RETAINED_UNEVALUATED / 136 EXCLUDED / 0 MATCHED_FILTERS | 4 SPW rows for `uid://A001/X2df9/X1b` | `TP_OR_UNRECOGNIZED_ARRAY_UNSUPPORTED` (REGION strategy; local array-type recognition failed, server-reported scope retained as unevaluated, not excluded) |
| CASE2 | 871 | 323 RETAINED_UNEVALUATED / 548 EXCLUDED / 0 MATCHED_FILTERS | 9+ SPW rows spanning both `uid://A001/X133d/X9c3` and `uid://A001/X133d/X9c5` | `MOSAIC_OR_UNKNOWN_GEOMETRY_UNSUPPORTED` (REGION strategy; candidate appears to be a mosaic, so local region intersection is not attempted) |

Both cases' matched rows also passed the local `angular_resolution` filter
(`MATCH` against the recorded `< 0.5`/`< 1 arcsec` case filters); the
`spectral_resolution`/`sensitivity` predicates stayed `SKIPPED` as designed
(not implemented by this service yet). No `MATCHED_FILTERS` disposition
occurred for either case's matched rows -- this is expected under the
current spatial/frequency evaluation gaps, not a defect.

A companion measurement,
[tests/live/test_case_beam_strategy_applicability.py](../tests/live/test_case_beam_strategy_applicability.py),
found that in the real Archive rows near both cases, the formula
primary-beam strategy's exact `12-m`/`7-m` `antenna_arrays` label match
resolved a diameter for **0 of 336** CASE1 rows and **0 of 851** CASE2 rows
-- every observed label was a detailed pad:antenna listing or an ACA/TP
array listing instead. This was originally a small, local-neighborhood
sample pending Archive-wide confirmation via
[scripts/beam_array_label_census.py](../scripts/beam_array_label_census.py).

**That census has now been run (2026-09-10) against the full live Archive**:
across all 443,998 `science_observation = 'T'` rows (13,058 distinct
`(antenna_arrays, is_mosaic)` groups, no query-cap overflow), **0%** matched
the exact string `12-m` or `7-m` -- every single row, mosaic and
non-mosaic alike, classified as `OTHER_DETAILED_OR_MIXED` (a detailed
pad:antenna listing or an ACA/TP-only listing). The full report, including
sample raw label values per bucket, is written to
`docs/evidence/primary_beam_array_label_census_2026-09-10.md`. This
upgrades the CASE1/CASE2 finding above from "a concrete zero in two local
neighborhoods" to a **confirmed Archive-wide zero**: the current exact-label
heuristic in `primary_beam.py` does not resolve a diameter for the Archive
side of the formula primary-beam strategy on *any* row in the present
Archive population, not merely a low or unlucky share of it. This makes a
real `classify_array_type()` parser (see
`claude/next_rule_engineering_tasks_2026-09-10.md`) a prerequisite --not
merely a strengthening consideration-- for relying on the Archive side of
this strategy beyond hand-checked cases with a manually supplied diameter.

### Entry-count reproduction (2026-09-11)

With the opt-in Archive Query-equivalent filters (frequency point in SPW,
angular and spectral resolution, AGGREGATE `cont_sensitivity_bandwidth`) and
(Member OUS, target) grouping, the live rows reduce to exactly the reported
entries: CASE1 one entry, `uid://A001/X2df9/X1b` / PKS1830-211, matched by all
filters; CASE2 two entries, `uid://A001/X133d/X9c3` and `X9c5` / NGC253, retained
because their mosaic geometry is not evaluated. The ALMA Archive Query service
keys its observation entries the same way (`<member_ous_uid>.source.<target>`;
2021.A.00028.S has four entries, one science target). This was reproduced from
live rows outside the test runner; `test_case_entry_count_with_aq_equivalent_filters`
pins it and must be run with `--run-live`. It supports, but does not close, Q7:
the grouping still needs the supervisor's confirmation, and the entries remain
retrieval references, not duplicate labels.

Report evidence register (page references recorded in the project review):

| Source | Location | Recorded evidence | Verification boundary |
| --- | --- | --- | --- |
| `Weekly_Progress_Report.pdf` | Page 5 | Candidate Member UIDs listed above | Report contents checked in the project review; independent retrieval reproduction pending |
| `Weekly_Progress_Report.pdf` | Pages 6–7 | Display grouping and continuum RMS interpretation for CASE1/CASE2 | Case-specific report interpretation; executable grouping and candidate-field mapping still need fixtures |
| `Weekly_Progress_Report.pdf` | Page 14 | Sky/rest handling and reference-frame limitations | Recorded method discussion, not blanket approval of reference-frame conversion or RMS comparison |

The continuum RMS interpretation applies to these two case filters. It does
not establish that the original internship task labels the basis, or that every
user sensitivity is continuum RMS. Reported answers and working assumptions
are evidence records, not approved calculation methods or formal duplication
labels. Never use expected project IDs or Member UIDs as search constraints to
make a positive retrieval test pass.

A pinned retrieval acceptance test now exists
([tests/live/test_case_retrieval.py](../tests/live/test_case_retrieval.py)),
asserting only that each reported Member UID is retrieved (weak recall), with
the exact case search parameters transcribed above and the engineering search
radius documented in that file. It has been executed against the live
service and PASSED for both cases; see "Executed retrieval evidence" above
for the retrieved-row counts, dispositions and matched-row reasons. A pinned
grouping/count fixture and executable grouping/count assertions remain
pending until Q7 (CASE grouping/Member UID recall confirmation) closes.
Preserve the report's display grouping; do not silently reinterpret its entry
count as raw TAP rows or unique Members. Coordinate/frequency reference,
search radius/tolerance and the candidate-field mapping for the RMS filter
still need explicit implementation evidence. Formal duplicate/non-duplicate
labels remain unverified. Known report records are retained independently of
these outstanding checks.

## 9. Delivery boundary

The [documentation entry](README.md#next-delivery) owns the next service delivery.
This contract owns scientific decisions and acceptance requirements; Q1–Q7 block
only the affected formal methods. Current mapping limitations remain in the
[data model](data_model.md#spectral-mapping-boundary). A valid request, an available
context or a passed structural test does not establish a duplication verdict.
