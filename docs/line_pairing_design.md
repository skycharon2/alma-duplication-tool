# Spectral-line pairing: next-increment implementation contract

Status: confirmed scientific inputs; reference model implemented; matcher, request
redshift extension and line evaluators remain the next PR. Continuum has no mode
dependency. Do not block it on this work.

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

The next matcher emits a result for each proposed-window/candidate-context pair,
including unresolved attempts with structured reasons. Do not discard out-of-band
pairs before producing their negative LINE-COVERAGE evidence. Do not call absence
of pair records a negative result when candidate reconstruction was unresolved.

## Next request changes

Add optional `source_redshift` to ProposedObservationRequest and the validator:
finite real number, reject bool, require z > -1. Preserve it in raw/normalized
reports; bump request/validation versions. REST centres need z; absent z is
missing evaluability information, not silently z=0. SKY centres remain direct.

Reuse `ProposedWindow.center`, `correlator_mode`, `spectral_resolution` and
`ProposedSensitivity.rms`, `window_ids`, `smoothing_resolution`. The planned
resolution belongs to that window's sensitivity declaration. A single explicit
planned resolution suffices; if both fields are supplied and disagree, return a
structured conflict rather than choosing one. Unit-normalize to km/s around the
derived sky centre when the planned resolution is a frequency width. Do not
reuse channel spacing as spectral resolution or noise bandwidth.

## Candidate mode evidence

Restore historical `cf1586a852d1377b3469ba0aae552d698d4f0a1b` as a design reference,
not a patch to apply blindly. Existing `em_xel` acquisition remains sufficient.
Create a versioned evidence object attached to the exact Source-SPW association:
raw count, metadata validity, UI type, operational TDM/FDM, evidence level
DERIVED, method version, confirmation ref, and failure reasons.

Count <=128 yields continuum/TDM; >=129 yields line/FDM only for positive integral
counts and compatible integer metadata. Missing/masked/invalid/conflicting same
association values yield UNKNOWN. Never fall back to bandwidth, resolution or
ObsCore `type`. This is the project's approved operational Archive UI mapping,
not an assertion about every possible physical correlator configuration.

## Rule order within one pair

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

The next pair report will contain `LinePairingReference`, derived nu_sky,
dv_archive, sigma_at_plan, sigma_comp, all criterion results, and method versions.
Common position/angular evidence is attached to the same candidate context.
Use three-valued AND within a pair and OR over coherent eligible pair outcomes;
failed plus unknown pair remains unknown. Preserve individual pairs. The current
patch deliberately does not activate multi-pair/mixed-branch aggregation.

## Pinned guide B acceptance specification

See `examples/confirmed_continuum/line_acceptance_spec.json`: rest 230.538 GHz,
z=0.024 gives 225.134765625 GHz; component [224.8,225.4] GHz; resolution 500 kHz;
mode count 1920; sigma10=0.40 mJy/beam; plan dv=20 km/s and RMS=.30 mJy/beam;
theta_plan=.30 arcsec and theta_archive=.25 arcsec. Expected sigma_at_plan is
0.282842712474619 and sigma_comp is 0.4072935059634514 mJy/beam.

This is a specification for the next PR, not an executable line request in the
current CLI schema and not a claimed passing line evaluator. Acceptance must add
coverage endpoints, z boundaries, SKY-without-z, coarser-resolution blocking,
missing/conflicting modes, multiple windows, mixed intents and crossed-SPW traps.
