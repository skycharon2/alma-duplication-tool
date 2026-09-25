# Queue common rules: row beam and component scope

`--queue-common` selects `queue_pos_single_5` and `queue_angular_factor_7`.
`--queue-continuum` and `--queue-line` include these common rules. The
[current decision](evidence/queue_row_beam_decision_2026-09-24.md) adopts the Cycle 13
Portal row-beam convention. Report v4/evaluation v5 remain compatible; method
versions identify the changed interpretation. Archive behavior is unchanged.

## Row-level POS-SINGLE

| Operational standAlone_ACA | Row diameter |
| --- | --- |
| True | 7 m |
| False | 12 m |
| Absent column | 12 m under recorded Portal assumption |
| Present but empty/invalid | Unresolved |

Use 7-m? and Use TP? record requested auxiliary components and **do not select D**.
A TP request does not mean that the entire row is TP-only. A row beam is not a
component inventory and does not prove main-array membership.

The request must still be fixed celestial and single-point, and the candidate
must have supported frame/centre, SINGLE_FIELD geometry and regular SPWs.
Mosaic, scans, moving/placeholder coordinates and conflicting interpretations
remain unresolved. Resolving D alone does not pass these gates.

Use the existing candidate frequency: positive Ref.Frequency, or the documented
position-only zero-reference sky-SPW fallback. FWHM = 1.13*c/(frequency*D), radius
= FWHM/2. Spherical separation <= radius is inclusive, with no equality band.
Spherical offset transport is reused, including rows requesting TP.

## Shared observation scope

The same coherent Queue row supplies POS-SINGLE, requested ANGULAR and continuum
frequency/RMS. Auxiliary flags and standalone status do not block these rules.
See the [scope correction](evidence/queue_row_continuum_decision_2026-09-24.md).
ANGULAR keeps its exact symmetric factor-two comparison; the row's requested RMS
retains the previously adopted reference-width/usable-union interpretation.
No per-component measurements are invented. Missing quantities remain unknown.

The same POS-SINGLE and ANGULAR objects are passed to formal Queue LINE pair
evaluation. `queue_line_fdm_1`, `queue_line_coverage_1`,
`queue_line_resolution_compatibility_1` and `queue_line_rms_portal_1` operate
only on the bound same-row/same-SPW pair; `queue_line_pair_and_1` and
`queue_line_context_or_1` preserve pair/context boundaries. This does not create
a second position method or change the row diameter. Mosaic and other unsupported
geometry remain outside the supported fixed single-field increment.

## Report evidence

Position exposes source row and snapshot, candidate frequency, D, spherical
separation, FWHM, radius, profile version and decision references. Its details
also preserve:

- diameter_source and standalone_aca_field (ABSENT/PRESENT/INVALID);
- standalone_aca_raw, standalone_aca_interpretation and interpretation kind;
- use_7m_requested, use_tp_requested and requested_components;
- requested_component_anomaly, including TP_WITHOUT_7M.

An absent column never becomes a fabricated source field. The assumption is
recorded separately; the original CSV bytes and raw row are unchanged.

## Search and reproduction

Default retrieval continues conservative retention. All retained rows are
assessed, even with display limit 1. The legacy --queue-candidate-beam search
profile remains conservative and does not drop newly supported standalone rows
using an old 12-m assumption. Excluded rows remain in source/filter audit.

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/single_point/request.json \
  --queue-csv "$ALMA_QUEUE_CSV_SNAPSHOT" --queue-common \
  --output reports/queue-row-beam.json
python -m pytest tests/integration/test_queue_row_beam.py \
  tests/integration/test_queue_common.py -q
```

Old manual --queue-array declarations remain removed. Historical position v3/v4
and angular v4/v5 reports keep their original meaning. Generate a new report;
do not relabel an old one. The roadmap owns remaining dual-source acceptance,
interface and broader-mode work.
