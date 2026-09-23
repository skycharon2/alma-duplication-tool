# Spectral-line evidence and pairing contract

Status: request preparation, association-bound Archive mode evidence and pair
builder implemented. Numerical FDM/coverage/resolution/RMS criteria and line
aggregation are implemented in [PR 3](roadmap.md). Continuum has no mode dependency.

## Pair identity and ownership

`domain/line_pairing.py:LinePairingReference` keeps:

| Reference | Existing owner |
| --- | --- |
| proposed_setup_id / proposed_window_id | ProposedObservationRequest / ProposedWindow |
| proposed_sensitivity_id | ProposedSensitivity with purpose LINE, scope WINDOW and exactly that window_id |
| candidate_context_id / candidate_source_record_id | ComparisonContext / EvidenceReference |
| candidate_association | SourceSpwAssociationKey, including Member, ASDM, source and SPW |
| candidate_component | SupportComponentRef, including raw row, parser version and component index |

`resolve(request, context)` verifies the full relationship before returning the
existing window, its sensitivity and the existing selected component. It does
not copy independent scalars into a new evidence bag. This prevents attaching a
better RMS/resolution from another SPW, execution, source, query, or proposal.
Unassigned mappings and conflicting alternatives cannot make a resolved pair.

The builder emits a result for each proposed-window/candidate-context pair,
including unresolved attempts with structured reasons. Do not discard out-of-band
pairs before producing their negative LINE-COVERAGE evidence. Do not call absence
of pair records a negative result when candidate reconstruction was unresolved.

## Implemented request preparation

Optional `source_redshift` is in ProposedObservationRequest and the validator:
finite numeric input, reject bool, require z > -1. It is preserved in raw/normalized
reports; request/validation versions are 2/6. REST centres need z; absent z is
missing evaluability information, not silently z=0. SKY centres remain direct.

Reuse `ProposedWindow.center`, `correlator_mode`, `spectral_resolution` and
`ProposedSensitivity.rms`, `window_ids`, `smoothing_resolution`. The planned
resolution belongs to that window's sensitivity declaration. A single explicit
planned resolution suffices; if both fields are supplied and disagree, return a
structured conflict rather than choosing one. Unit-normalize to km/s around the
derived sky centre when the planned resolution is a frequency width. Do not
reuse channel spacing as spectral resolution or noise bandwidth.

## Candidate mode evidence

Historical `cf1586a852d1377b3469ba0aae552d698d4f0a1b` was used as a design reference.
Existing `em_xel` acquisition is reused. The versioned evidence object is attached to the exact Source-SPW association:
raw count, metadata validity, UI type, operational TDM/FDM, evidence level
DERIVED, method version, confirmation ref, and failure reasons.

Count <=128 yields continuum/TDM; >=129 yields line/FDM only for positive integral
counts and compatible integer metadata. Missing/masked/invalid/conflicting same
association values yield UNKNOWN. Never fall back to bandwidth, resolution or
ObsCore `type`. This is the project's approved operational Archive UI mapping,
not an assertion about every possible physical correlator configuration.

## Numerical evaluator integration

[`rules/line.py`](../src/alma_duplicate/rules/line.py) builds preparation once,
resolves each reference and computes the four line criteria from that component.
The [rules contract](rules.md#confirmed-archive-line-evaluation) owns formulas,
method versions, dependency blocking and pair/context aggregation. The
[report contract](evaluation_cli.md#line-pair-export-report-4--evaluation-5) owns
the serialized pair results and intermediate units.

Preparation AVAILABLE means required evidence exists, not that FDM, coverage,
resolution compatibility or duplication is satisfied. Known TDM and out-of-band
candidates remain resolved attempts. Preparation is preserved alongside results;
no numerical rule silently reclassifies or drops those attempts.

## Implemented builder and report states

`line_pairing.build_line_pairs(request, context)` produces `LinePairBuildResult`
with one `LinePairAttempt` for every listed window in that single retained context.
It performs no candidate filtering. References are resolved through the existing
Source-SPW component, never through Member-level grouping or scalar RMS fallback.
No LINE intent produces no attempts; a selected empty list produces
NO_PROPOSED_LINE_WINDOWS. Setup completeness is recorded as proposed enumeration
only and cannot certify source/search completeness. Queue and non-single-field
candidates return UNSUPPORTED attempts. Multiple candidate alternatives remain
unresolved even when their channel counts happen to agree.

| Field | Meaning |
| --- | --- |
| association_status | RESOLVED with reference, UNRESOLVED without one, or UNSUPPORTED |
| evidence_status | AVAILABLE or INCOMPLETE; no policy outcome |
| proposed | Derived center/resolution, sensitivity ID, source field names and reasons |
| candidate_mode | Raw counts/types and row IDs, metadata validation, association, mapping versions and confirmation reference |
| assessment | Always NOT_EVALUATED for the builder |

Mode derivation accepts positive Python/NumPy integers with one scalar integer
FIELD descriptor (`short`, `int`, `long`; arraysize absent/1; dimensionless unit).
Float/text/Boolean cells are invalid, even if they spell an integer. Masked raw
count is represented as null plus MASKED_COUNT and its raw type. Invalid scalar
representations unsupported by JSON use diagnostic text plus raw type; original
source rows remain in the context. Missing/invalid counts or different counts in
one association make its mode UNKNOWN, including differing counts that both map
to FDM. Unlinked rows are never pooled. Across runs, executions or SPWs, no group
is merged. The approved operational mapping is distinct from native mode telemetry.

## Pinned guide B acceptance specification

See `examples/confirmed_continuum/line_acceptance_spec.json`: rest 230.538 GHz,
z=0.024 gives 225.134765625 GHz; component [224.8,225.4] GHz; resolution 500 kHz;
mode count 1920; sigma10=0.40 mJy/beam; plan dv=20 km/s and RMS=.30 mJy/beam;
theta_plan=.30 arcsec and theta_archive=.25 arcsec. Expected sigma_at_plan is
0.282842712474619 and sigma_comp is 0.4072935059634514 mJy/beam.

The input is now executable at `examples/confirmed_line/request.json`. Its
synthetic replay has one guide-B candidate and one out-of-band TDM candidate in
the same execution but a different SPW. Both remain explicit pairing attempts;
the evaluator now returns CRITERIA_MET then CRITERIA_NOT_MET. The numerical
specification is executable acceptance, separate from the builder's readiness states.

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/confirmed_line/request.json \
  --archive-replay examples/confirmed_line/archive/manifest.json \
  --output reports/line-evaluation.json
```

Expected: 2 retained/evaluated contexts, 1 shown; both associations RESOLVED;
mode FDM then TDM; proposed sky frequency 225.134765625 GHz and planned
resolution 20 km/s. The first pair has six satisfied conditions and the two RMS
values above. The second pair fails FDM and coverage. Both are evaluated despite
one shown candidate. Numerical regression owner: `tests/integration/test_line_evaluation.py`;
preparation regression owner: `tests/integration/test_line_preparation.py`.
