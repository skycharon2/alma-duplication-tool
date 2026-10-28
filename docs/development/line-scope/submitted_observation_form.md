# Submitted observation form

The existing `/proposed` page supports fixed Single Pointing and Mosaic observations
with LINE, Continuum, or both selected. The separated execution path is Archive-only;
legacy Queue requests retain their existing path.

## Input and evaluation

`SEPARATE_OBSERVATION_REQUIREMENTS_V2` extends the separated input contract with
`continuum_requirement`: aggregate `rms` and contributing `physical_spw_ids`.
Each requested LINE retains its own frequency, redshift override, resolution and RMS.
Physical SPW records remain separate, with optional links to LINE requirements.
Adding bandwidth evidence does not add a LINE requirement or count a linked SPW twice.

Continuum uses the shared representative frequency, aggregate sensitivity and existing
setup qualification rules. Its calculation receives only physical SPW evidence.
LINE receives only submitted LINE requirements. Both branches evaluate the same
retrieved candidates independently; their criteria are never combined into one branch.
Missing Archive evidence and incomplete retrieval retain their existing uncertainty.
Single Pointing retains configured array acquisition and captured array evidence.

New browser forms carry `normal_form_version=2`. Validation, request export and
execution use the same versioned input. Older form submissions and V1 separated
requests retain their previous interpretation. Switching to an unsupported scope
preserves entries and blocks execution rather than silently changing contracts.

Single Pointing reports use version 8 and `submitted_observation_single_report_2`.
Mosaic search reports use `submitted_observation_mosaic_search_report_2`.
Existing report pages show the selected independent branches.

## Verification

Fixed-data integration and browser-route tests cover each geometry with LINE,
Continuum and combined inputs, request/download parity, independent records,
invalid continuum inputs and unavailable array evidence. These tests do not
constitute a new live Archive acceptance run.

## Next boundary: independent observations

Multiple LINE requirements currently belong to one observation with shared position
and angular requirements. Batch queries should contain separate observation records,
each with its own ID, position or pointings, scientific requirements and result state.
Failure or cancellation of one observation must not erase the others. Results must
remain grouped by observation; no criteria or coverage may be aggregated across them.
Batch execution is not implemented by this change.

## Mosaic report grouping

Mosaic reports follow the Single Pointing presentation rule: Member, target,
then an unambiguous recorded ASDM, with comparison contexts underneath.
New contexts reuse the shared Archive identity serializer for LINE and Continuum.
Legacy LINE associations remain readable. Missing or conflicting execution IDs
keep contexts separate; target-level metadata never supplies an inferred ASDM.
Member matching navigation still retains sibling contexts and their own outcomes.
Grouping does not change scientific results or rewrite saved reports.

## Frequency-local redshift

New separated browser submissions carry `frequency_local_redshift=1` and omit
request-level redshift. Each LINE supplies its own z beside its central frequency.
Continuum supplies `continuum_requirement.source_redshift` beside its representative
frequency. REST conversion uses the corresponding value; SKY is not redshifted.
Existing requests retain shared-redshift fallback semantics. The optional continuum
redshift overrides that fallback only in the continuum calculation.
