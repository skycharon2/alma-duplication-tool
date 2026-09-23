# Duplication rule inputs and evidence contract

Design version: 0.3. Implementation coverage is specified separately below.

Reviewed implementation baseline: `13c41d5` (PR #76). Archive fixed-target,
single-point continuum implements five approved conditions and per-context
three-valued aggregation. Direct usable widths and direct aggregate RMS are
supported; arbitrary nominal/noise conversions and Queue scientific mappings
remain separate. Solar has a request-level exemption without source access.
Line has versioned input/mode preparation, a reference-bound builder, four numerical
criteria, pair AND and context-local pair OR. Remaining tasks are tracked in the
[sole remaining-work plan](roadmap.md).

The [request API](proposed_observation_api.md), [rule contract](rules.md) and
[CLI/report contract](evaluation_cli.md) own current executable behavior.
Accepted input alone never establishes candidate comparability or a verdict.

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
continuum frequency or smoothing algorithm from this paraphrase. Use the confirmed
scope in section 7; its historical questions are not a new approval prerequisite.

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
- [S: Cycle 13 duplication-check helper script, read 2026-09-15](https://almascience.eso.org/documents-and-tools/cycle13/python-script/view):
  the plotted candidate beam uses `radius = 0.5 * fwhmPB(freq, diameter)` at the
  candidate frequency and diameter; continuum sensitivity is scaled as
  `req_sen * sqrt(ref_bw / aggregateBandwidth)`; per-window sensitivity at a
  resolution is scaled as `req_sen * sqrt(ref_bw / res)`; the aggregate
  bandwidth counts an overlap once. The page states the script is user
  contributed, distributed as-is and unsupported by the ARCs, and the script
  states that its per-window sensitivity ignores system-temperature variation
  between windows.
- [AQM: Cycle 13 ALMA Science Archive Manual, Doc. 12.15 v1.0, March 2026, Appendix A, checked 2026-09-15](https://almascience.eso.org/alma-data/documents-and-tools/latest/science-archive-manual):
  the Archive result-table `Frequency Support` dictionary includes a per-SPW
  `Type`; `continuum` and `line` indicate TDM and FDM, respectively. This settles
  the documented meaning of that Archive display field. It does not establish
  that the current public TAP `frequency_support` string selected by this project
  exposes the `Type`, nor how to bind an auxiliary machine-readable value to the
  exact candidate SPW. This PDF check is not yet byte-pinned in the repository
  source manifest.
- [M: measured here against the pinned NGC6240 Archive fixture](../tests/fixtures/archive/ngc6240/):
  every `frequency_support` bracket component carries five tokens, namely
  frequency range, spectral resolution, 10 km/s sensitivity, native-resolution
  sensitivity and polarization products. No correlator-mode token is present.

These facts justify separate storage fields; they do not by themselves specify
cross-source comparison algorithms. B/O/H/S/AQM/M below refer to these sources.

A letter records where a statement comes from, and that origin limits what the
statement can support. A carries policy thresholds. B, O and H carry instrument
and tool facts. AQM carries official Archive result-table field semantics. S is
implementation evidence from a tool the observatory
publishes but does not support: it can show that a convention exists and can
never carry scientific approval. M is a measurement on pinned data here, which
can exclude a proposed evidence path but cannot establish an Archive-wide
convention. Reported oral feedback and readings derived here from policy text
carry neither; they are marked in the register rows and are not promoted by
being repeated.

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
| POS-SINGLE: fixed, single-field interferometry; A/location | ICRS position | `s_ra`, `s_dec`; `s_region`, optional `s_fov`, `antenna_arrays`, frequency as supporting evidence | `RA`, `Dec`, geometry and array evidence | Archive: approved candidate-frequency/unique-diameter position method. Queue: provisional candidate-beam profile, with explicit geometry/frame/array evidence; see queue_single_point_mapping.md | Position required for fixed-target search; missing candidate beam permits bounded search, blocks formal position rule |
| POS-MOSAIC: mosaics; A/location | Proposed pointing list or reproducible pointing-generation inputs | Actual pointing/coverage evidence; generic footprint insufficient | Mosaic fields and offsets are inputs, not a verified pointing list | Future pointing-count coverage calculation | Unsupported formal mode; never reduce to center/FOV or area overlap |
| TARGET-MOVING: moving; A/location | Explicit moving identity | `target_name` alone does not establish normalized identity | Target label alone does not establish normalized identity | Future identity normalization; no fixed-coordinate fallback | Unsupported search in first model |
| SOLAR: Sun; A final sentence | Explicit target kind | Candidate matching unnecessary for exemption | Same | `NOT_APPLICABLE` assessment, distinct from unavailable implementation | Never extend exemption to all Solar System objects |
| ANGULAR: applicable candidate comparison; A/resolution | Positive angular resolution with `REQUESTED_VALUE` meaning | `spatial_resolution` canonical evidence; optional `s_resolution` stays separate | `Req. Ang. Res.` | Convert supported units, preserve requested-versus-estimated semantics; policy comparison after context validation | Missing request or candidate quantity blocks this rule, not spatial retrieval |
| CONT-SETUP: continuum applicability; A/spectral definition | Distinct `window_id`s, per-window bandwidth kind and setup completeness | Not a substitute for proposed setup | Not a substitute for proposed setup | Approved direct USABLE-width path; count distinct qualified proposed windows. Explicit nominal conversion stays provisional and does not prove configuration applicability; unknown widths remain unresolved where decisive | Intent label alone never activates rule; no imputed width or mode |
| CONT-FREQ: continuum; A/spectral | Independent setup representative frequency, optional representative-window link and reference/origin | `frequency`, full parsed support, canonical interval | `Ref.Frequency`, SPW frequencies, `Is Sky Freq?`, velocity evidence | Archive: confirmed proposed representative SKY frequency versus candidate frequency. Queue: comparison-frequency mapping remains separate; beam fallback is not automatic CONT-FREQ evidence | Broad spatial retrieval permitted; frequency assessment unavailable |
| CONT-RMS: continuum; A/spectral | Direct aggregate RMS with declared basis/setup scope, or reference RMS with conversion inputs | `cont_sensitivity_bandwidth`, parsed component sensitivities with their bases | `Req.Sensitivity` plus `Ref.Frequency` and `Ref.Freq.Width` | Archive: approved direct aggregate RMS comparison. Queue: requested sensitivity basis/setup mapping remains unresolved; no automatic Archive sensitivity or beam-unit substitution | Missing metadata limits affected operations, not request storage; candidate gaps remain candidate-side |
| LINE-COVERAGE: line; A/spectral | Requested SPW center, FDM evidence and frequency reference; width not generally required | Assigned component interval plus versioned association-bound em_xel mode evidence | Associated SPW interval/reference and validated FDM evidence; no approved automatic mode derivation | Compare requested center with candidate coverage, not whole-window containment | Missing width does not block center coverage; absent interval blocks coverage and absent mode affects the separate FDM rule |
| LINE-RMS: line; A/spectral | Window-linked RMS and explicit planned spectral/smoothing resolution; noise bandwidth remains independent | Assigned parsed component @10km/s sensitivity and frequency resolution | `Req.Sensitivity`, `Ref.Frequency`, `Ref.Freq.Width`; same-window resolution | Archive: confirmed same-component smoothing and angular correction implemented. Queue: resolution/RMS associations and normalization remain separate; no row-scalar fallback | Missing noise width is not supplied by resolution; broad search remains possible |

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
  planned-resolution conversion and noise scaling have distinct implementation states;
  use the current API and rule contracts, not another Q3/Q4 approval gate.
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

Per-criterion execution uses the implemented [rule-result contract](rules.md),
not the earlier design labels EVALUABLE, UNAVAILABLE and UNSUPPORTED. Runtime
`EvaluationStatus` is EVALUATED, INSUFFICIENT_INFORMATION, NOT_APPLICABLE or
NOT_EVALUATED; `MethodApplicability` is APPLICABLE, UNRESOLVED or NOT_APPLICABLE,
while `MethodApproval` remains a separate dimension. These states do not
establish an aggregate duplicate verdict. Request issues expose PROPOSED/METHOD
sides; the comparison layer keeps its independent
[evidence dimensions](comparison_contexts.md#evidence-and-states).

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

For each condition, computation status, condition outcome and method status are
independent. The implemented [rule-result contract](rules.md) owns their schema
and migration rules. A provisional method may compute a threshold outcome; that
outcome is not eligible for formal aggregation. Missing or unusable evidence is
reported through evaluation status and all affected-side issues, never silently
converted to NOT_SATISFIED. Satisfaction of one condition is not a duplicate
verdict; continuum aggregation preserves AND scope and unknowns, while line
aggregation ANDs within a pair and ORs only whole pairs in the same context.

The current report exposes candidate/source IDs and reference-bound line pair calculations. Required evidence includes candidate/source IDs, matched source/execution/SPW
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
| Large Program | Project category alone is not an implemented observation-level exclusion or exemption | Submission eligibility and special-policy decisions are outside the numerical evaluator; apply supported geometry/evidence requirements |
| Kelvin | Reject unsupported input unit with explanation | Frequency, beam axes/shape, approved conversion |
| Rest-frequency evidence / SPS expansion | Proposed REST line centres support explicit redshift preparation; Queue SPS expansion remains outside the regular-SPW path | Keep proposed preparation, Queue velocity evidence and scan expansion distinct |

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

### Current confirmed scope (2026-09-21)

The [confirmation record](evidence/supervisor_confirmation_2026-09-17.md#confirmed-2026-09-21)
supersedes the historical Q1–Q8 open/partial statements below for the fixed-target,
single-pointing Archive workflow. The project developer supplied supervisor
confirmation dated 2026-09-17 and implementation clarifications dated 2026-09-21.

| Item | Current status | Implementation boundary |
| --- | --- | --- |
| ANGULAR/Q1 | CONFIRMED and implemented | Archive estimated angular resolution; candidate frequency and unique diameter; inclusive candidate beam |
| Q2 | CONFIRMED for direct usable widths | No arbitrary nominal conversion; optional portal mapping remains provisional |
| Q3 | CONFIRMED and implemented | User representative SKY frequency, not window average |
| Q4 | CONFIRMED and implemented for line formula | Same-component 10km/s smoothing and angular correction; coarse resolution blocks RMS; no continuum smoothing/correction |
| Q5 | CONFIRMED and implemented for direct Archive continuum | Candidate estimated aggregate RMS <=2 times proposed RMS; Queue mapping excluded |
| Q6 | CONFIRMED operational em_xel/UI mapping | Versioned association-bound evidence and unknown/conflict gates implemented |
| Q7 | CONFIRMED coherent context unit | Reference model, builder and numerical pair results delivered; CASE retrieval is not a scientific label |
| Q8 | CONFIRMED; continuum AND and line pair AND / context OR implemented | Incomplete enumeration remains unknown unless a whole pair passes; no mixed-setup/search-wide absence verdict |

See [current implementation and CLI acceptance](confirmed_continuum.md) and the
[PR plan](roadmap.md). These items are coding/acceptance tasks, not
questions to resubmit before implementing the confirmed workflow.

### Historical register through 2026-09-15 (superseded within the scope above)

Preserved in the [historical register](history/rule_questions_through_2026-09-15.md);
current confirmed scope is defined above.

### Adopted interpretations and remaining questions

Preserved in the [historical register](history/rule_questions_through_2026-09-15.md);
current confirmed scope is defined above.

## 8. Acceptance specifications and implementation coverage

The [acceptance catalog](acceptance_cases.md) owns executable case inventory and
review status. Its [reference ledger](acceptance_reference_values.md) is hash-pinned;
this cleanup does not alter it or any catalog hash.
The [old input inventory](history/input_acceptance_inventory_pr76.md) is retained
for traceability, not maintained as a second coverage table.
Queue-specific current tests and remaining gates are in the
[mapping contract](queue_single_point_mapping.md).

### Recorded CASE inputs

See [preserved CASE evidence](evidence/case_retrieval_2026-09.md).

### Executed retrieval evidence (2026-09-10 run)

See [preserved CASE evidence](evidence/case_retrieval_2026-09.md).

### Entry-count reproduction (2026-09-11)

See [preserved CASE evidence](evidence/case_retrieval_2026-09.md).

## 9. Delivery boundary

[Status](status.md) owns current capabilities and [roadmap](roadmap.md) owns
engineering order. This contract owns evidence requirements and scientific
decisions. Historical Q1–Q8 wording is not a blanket gate on the confirmed Archive
scope. Queue mappings require their own applicability evidence. An available
context or passing structural test does not establish a duplication verdict.
