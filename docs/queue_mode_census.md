# Queue mode census contract

This offline diagnostic answers how many **physical regular SPW occurrences**
match a versioned configuration catalog. It does not implement Queue LINE-FDM,
change POS-SINGLE, or turn derived evidence into an approved scientific method.
The production Archive and Queue evaluators are unchanged.

## Run

```bash
python -m alma_duplicate.cli.queue_mode_census \
  --queue-csv "/path/to/duplication-check-csv (1).csv" \
  --require-pinned-snapshot \
  --output-dir reports/queue-mode-census
```

`python scripts/queue_mode_census.py` accepts the same arguments after installing
the package. The output directory must not already exist. Omit the pin guard
only when deliberately measuring another snapshot; its real hash and pin status
are always reported. No network call is made. Exit 0 means a census was produced,
including UNKNOWN results; exit 2 means input/output or completeness failure.

The parser is the existing production Queue parser. An incomplete parse is an
error, not a smaller successful denominator. Spectral scans are listed separately:
there is no invented expansion into SPWs. Duplicate physical rows remain in the
count; the report also gives repeated-content counts. Empty denominators have a
null percentage, not 100%.

## Three different questions

| Output | Meaning | Can it supply Queue LINE-FDM today? |
| --- | --- | --- |
| `conditional_unique_configuration` | Exactly one catalog entry matches cycle, polarization, nominal bandwidth and resolution; multiple matches remain UNKNOWN even when all are FDM | No: conditional on the supported BLC and response scope |
| `conditional_mode_consensus` | At least one entry matches and all matching entries have the same mode; does not recover a unique averaging/resource/quantization setup | No: diagnostic mode agreement only |
| `source_bound` | Mode with processor applicability established for this exact source row/SPW | No entries available from this CSV alone; all UNKNOWN |

`reference_only_mode_consensus` additionally excludes the supplied N=16 export
compatibility hypothesis. This sensitivity analysis prevents a provisional numeric
bridge from appearing to have independent official-source verification.

Neither `Use 7-m?` nor `Use TP?`, including both being False, is promoted into a
source-provided processor identifier. They describe requested arrays, not a raw
execution/processor association. A future source binding may establish a supported
BLC context, but it must carry its own evidence. This diagnostic does not silently
use an assumed processor to authorize a formal rule.

## Configuration and numerical scope

The catalog is keyed separately to project-submission Cycles 11, 12 and 13:
2024, 2025 and 2026, including `.A.` DDT project labels. A Cycle 13 download can
contain projects submitted in earlier cycles. Project year does not prove the
processor or software version used for eventual observations.

The conditional catalog covers DOUBLE and FULL polarization, BLC Hanning
responses, standard non-oversampled 2x2 configurations with resource fractions
1, 1/2 and 1/4 where permitted, plus full-resource dual-pol 4x4 configurations.
It is **not a complete operational setup validator**. SINGLE polarization,
ACA processor, TPS, special multi-region modes, oversampling, non-Hanning
responses, and baseband association are outside the catalog. Missing/unsupported
cycle, polarization, bandwidth or resolution yields a named unavailable result.
A narrow bandwidth alone cannot override an inconsistent resolution.

Forward generation starts with a documented channel spacing, applies the allowed
polarization/resource setting, and multiplies by the smoothing response. It never
computes a channel count by dividing the observed bandwidth by its resolution.
Queue's 1875 MHz export label is matched to the 2000 MHz nominal BLC configuration;
its spacing uses that configuration, not `1875 / 4096`. Existing Queue portal
usable-width evidence is retained as a separate field, including its pending
applicability status; it is not used to manufacture a channel count.

For example, DOUBLE/1875 has native spacing 2000/4096 = 0.48828125 MHz in FDM,
and 2000/128 = 15.625 MHz in TDM. Hanning with averaging 1 gives 31.25 MHz for
TDM; averaging 2 has factor 2.312 and gives 36.125 MHz. FULL polarization doubles
spacing. For DOUBLE/62.5 with half correlator resources, native spacing is
62.5/2048; multiplying by 2.312 gives 0.070556640625 MHz.

The source registry in `data/correlator_modes` pins URLs, handbook versions and
PDF hashes. The Cycle 11–13 handbooks supply the hardware, polarization and
resource scope (Tables 5.1–5.2, sections 5.1.3, 5.5.2 and 6.3.2). Public OT
`ConfigModeDecoderImpl` provides a cross-check of bandwidth/spacing combinations.
The retrieved OT source is not a Cycle 11–13 release manifest: it must not be
presented as proof that a particular row used that release.

Numerical profiles remain distinct rather than loosening a tolerance:

| Averaging | Retrieved historical OT response | Retrieved rounded OT response | Supplied Queue export compatibility |
| --- | --- | --- | --- |
| 1 | 2 | 2 | — |
| 2 | 2.312 | 2.312 | — |
| 4 | 3.97 | 4 | — |
| 8 | 7.996 | 8 | — |
| 16 | 16 | 16 | 15.999 |

The 15.999 coefficient follows the supplied method's exact examples:
7.81201171875 / 0.48828125 = 15.999; the FULL example scales by two. It is not
claimed to have been found in the two retrieved OT revisions or in the rounded
handbook table. Its 76 affected source SPWs are separately marked
`export_compatibility_only`. Confirmation of the exporting software's actual
semantics remains a source-mapping task, not a reopening of Archive formulas.

Retrieved source references:

- [Cycle 11 handbook](https://almascience.eso.org/documents-and-tools/cycle11/alma-technical-handbook), Doc 11.3 v1.4.
- [Cycle 12 handbook](https://almascience.eso.org/documents-and-tools/cycle12/alma-technical-handbook), Doc 12.3 v1.0.
- [Cycle 13 handbook](https://almascience.eso.org/documents-and-tools/cycle13/alma-technical-handbook), Doc 13.3 v1.0.
- [Public OT decoder](https://asw.alma.cl/ASW/OBSPREP/-/blob/678f32bab95530ad8741817ded1bdde633c95288/ObservingTool/src/alma/obsprep/bo/schedblock/ConfigModeDecoderImpl.java).
- [Historical response definition](https://asw.alma.cl/ASW/OBSPREP/-/blob/6864764fdd083afb540e83a61de62c3e6500305a/ObservingTool/src/alma/obsprep/bo/enumerations/SpectralAverage.java).
- [Rounded response definition](https://asw.alma.cl/ASW/OBSPREP/-/blob/678f32bab95530ad8741817ded1bdde633c95288/ObservingTool/src/alma/obsprep/bo/enumerations/SpectralAverage.java).

Matching tolerance is relative 1e-12 or absolute 1e-12 MHz, solely for floating
representation noise. Thus 7.812011718750001 matches 7.81201171875; 7.81225
matches neither that signature nor 7.8125. Multiple matches are retained.

## Artifacts and provenance

- `summary.json`: versioned method/sources, exact snapshot identity and date,
  denominator, all four count views, UNKNOWN reasons, geometry/cycle/project/
  array-requirement strata, parser warnings and artifact SHA256 values.
- `spws.csv`: every source row/SPW, raw values, physical line identity, project,
  target, geometry, array requirements, processor gap, nominal/usable bandwidth,
  all matching configuration IDs and both conditional outcomes.
- `signatures.csv`: all raw cycle/polarization/bandwidth/resolution signatures,
  occurrence counts and a source-row/SPW example. Binary-noise spellings remain
  visible as separate raw signatures even when they match the same configuration.
- `unknown_signatures.csv`: configuration-ambiguous or unmatched signatures.
  Processor-binding UNKNOWNs are counted independently in the summary; this
  smaller file must not be mistaken for the complete source-bound UNKNOWN set.
- `matched_configurations.json`: numerical parameters, averaging, resource
  fraction, quantization and source IDs for every matched catalog entry.

All methods stay `APPLICATION_DERIVED`, `PROVISIONAL` and versioned. No report v4
schema changes are needed: these are separate diagnostic artifacts.

See the [measured snapshot census](evidence/queue_mode_census_2026-09-22.md)
for counts, ambiguity examples and the single-field limitation. Remaining delivery
work is owned only by the [PR plan](roadmap.md).
