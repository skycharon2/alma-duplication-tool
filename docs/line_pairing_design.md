# Spectral-line evidence and pairing contract

Status: request preparation, association-bound Archive mode evidence and pair
builder implemented. Numerical FDM/coverage/resolution/RMS criteria and line
aggregation remain in [PR 3](pr_plan_2026-09-21.md). Continuum has no mode dependency.

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
reports; request/validation versions are 2/5. REST centres need z; absent z is
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

## Numerical evaluator requirements (not implemented here)

1. Convert REST centre using nu_sky = nu_rest/(1+z), or retain declared SKY centre.
2. LINE-FDM: proposed mode FDM and the exact candidate SPW operational mode FDM.
3. LINE-COVERAGE: exact selected component interval includes nu_sky, endpoints inclusive.
4. LINE-RESOLUTION-COMPATIBILITY: c * delta_nu / nu_sky <= planned delta_v.
5. If coarser, LINE-RMS is blocked with ARCHIVE_RESOLUTION_COARSER_THAN_PLANNED;
   it receives no computed pass/fail or fabricated finer resolution.
6. Take the selected component's @10km/s estimate. Do not borrow a row scalar
   unless its association is established explicitly.
7. Compute sigma_at_plan = sigma10 * sqrt(10/dv_plan).
8. Compute sigma_comp = sigma_at_plan * (theta_plan/theta_archive)^2.
9. LINE-RMS is sigma_comp <= 2*sigma_plan, with ANGULAR remaining a separate rule.

Current outputs contain the reference, proposed sky frequency/planned resolution,
mode provenance and preparation reasons. Future numerical outputs must add
candidate resolution and both RMS intermediate values through that same reference.
Preparation AVAILABLE means required preparation evidence exists, not FDM,
coverage, resolution compatibility or duplication satisfied. A known TDM or
out-of-band candidate is still a resolved pair. Pair AND/OR remains unimplemented.

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
LINE status is still NOT_IMPLEMENTED. The old numeric specification's final
RMS/branch values remain targets for PR 3, not passing results of this builder.

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/confirmed_line/request.json \
  --archive-replay examples/confirmed_line/archive/manifest.json \
  --output reports/line-pairing.json
```

Expected: 2 retained/evaluated contexts, 1 shown; both associations RESOLVED;
mode FDM then TDM; proposed sky frequency 225.134765625 GHz and planned
resolution 20 km/s. No LINE-* criterion or RMS correction is computed.
Regression owner: `tests/integration/test_line_preparation.py`.
