# Queue common rules: row beam and component scope

`--queue-common` selects `queue_pos_single_6` and `queue_angular_factor_7` for
previously supported geometry. Newly interpreted blank-Mosaic offset rows use
`queue_pos_single_7` and `queue_angular_factor_8`; see the
[blank-Mosaic contract](queue_blank_mosaic.md).
`--queue-continuum` and `--queue-line` include these common rules. The
[current decision](evidence/queue_array_beam_inference_decision_2026-10-01.md)
implements `QUEUE_ARRAY_BEAM_INFERENCE_2`. Archive methods and raw Queue records
are unchanged. The earlier Portal fallback is historical, not the current rule.

## Row-level beam interpretation

| Operational standAlone_ACA | Additional evidence | Diameters (m) |
| --- | --- | --- |
| True | TP false / true | 7 / 7 and 12 |
| False | Use 7-m false / true | 12 / 7 and 12 |
| Absent | Use 7-m false | 12 (including TP if requested) |
| Absent | Use 7-m true, TP true | 7 and 12; no AR comparison needed |
| Absent | Use 7-m true, TP false, Req.AR < band threshold | 7 and 12 |
| Absent | Use 7-m true, TP false, Req.AR >= band threshold | 7 |
| Empty, invalid or duplicate operational field | No absent fallback | Unresolved |
| Absent and required AR/band unavailable, or invalid typed array flags | No default diameter | Unresolved |

Thresholds are the fixed Cycle 13 table in the decision record. Equality belongs
to the 7-m side; there is no epsilon, interpolation or Ref.Frequency rescaling.
AR comparison uses the parsed canonical arcsec values. These values do not recover
precision lost during parsing. Numeric source tokens remain available as evidence.

Valid operational standalone evidence takes precedence. Standalone true with
Use 7-m false records an inconsistency without replacing that standalone value.
TP contributes a 12-m hypothesis. Main-array and TP reasons are retained together
but never create duplicate 12-m variants. An absent field keeps standalone UNKNOWN;
a 7-m-compatible inference never fabricates source-provided standalone status.

The request must still be fixed celestial and single-point, and the candidate
must have supported frame/centre, effective single-field geometry and regular SPWs.
The blank-Mosaic contract adds an explicit interpretation of blank offset rows
without relabelling their raw or parsed source geometry.
Mosaic, scans, moving/placeholder coordinates and conflicting interpretations
remain unresolved. Resolving D alone does not pass these gates.

Use the existing candidate frequency: positive Ref.Frequency, or the documented
position-only zero-reference sky-SPW fallback. FWHM = 1.13*c/(frequency*D), radius
= FWHM/2. Spherical separation <= radius is inclusive, with no equality band.
Spherical offset transport is reused, including rows requesting TP.

## Shared observation scope

The same coherent Queue row supplies POS-SINGLE, requested ANGULAR and continuum
frequency/RMS. The resolved hypotheses govern position scope; unresolved array evidence remains unknown.
See the [scope correction](evidence/queue_row_continuum_decision_2026-09-24.md).
ANGULAR keeps its exact symmetric factor-two comparison; the row's requested RMS
retains the previously adopted reference-width/usable-union interpretation.
No per-component measurements are invented. Missing quantities remain unknown.

The same POS-SINGLE and ANGULAR objects are passed to formal Queue LINE pair
evaluation. `queue_line_fdm_1`, `queue_line_coverage_2`,
`queue_line_resolution_compatibility_2` and `queue_line_rms_portal_2` operate
only on the bound same-row/same-SPW pair; `queue_line_pair_and_1` and
`queue_line_context_or_1` preserve pair/context boundaries. This does not create
another position formula. Each beam hypothesis supplies its own common conditions. Mosaic and other unsupported
geometry remain outside the supported fixed single-field increment.

## MIX evaluation and report evidence

One retained source row remains one `context_evaluations` entry. For MIX, the
backend independently evaluates the complete requested CONTINUUM/LINE branches
with D=7 and D=12, using the same source row, snapshot and SPW associations.
`queue_beam_variant_or_1` ORs **complete branch truths**: MET dominates, otherwise
any unknown stays INDETERMINATE, otherwise NOT_MET. Criteria are never borrowed
between beam variants. CONTINUUM and LINE remain separate branch summaries.

Report v4 has an additive optional `beam_variants` collection and `mix_aggregation`
object. Each variant contains report-local `variant_id`, original `context_id`,
`diameter_m`, criteria, branches, line_pairing and line_pairs. MIX's top-level
criteria/line_pairs are empty and line_pairing is null; its branches are the
backend OR results. `mix_aggregation` records matching diameters per branch and
across branches. Consumers must traverse variants to inspect MIX scientific evidence.
Single-diameter and historical reports keep their existing flat representation.
No historical report is relabeled or overwritten.

Position evidence preserves source row/checksum, source flags, operational field
status/raw value, classification, inference reason/kind, requested AR, band,
fixed table threshold/representative frequency, reference frequency, selected D,
spherical separation, FWHM, radius and versioned decision references.
Unresolved interpretations retain their diagnostics and never become false.

Inspection v3 visits both variants, counts common conditions once per variant,
and adds `beam_variant_id` to pair identities. Pair JSON Pointers traverse
`beam_variants/<index>`; branch counts still count the original context once.
The browser only renders these backend records and exports original report bytes.

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

Old manual --queue-array declarations remain removed. Historical position v3/v4/v5
and angular v4/v5 reports keep their original meaning. Generate a new report;
do not relabel an old one. The roadmap owns remaining interface and
broader-mode work; genuine-proposal review remains a separate external validation
gate.
