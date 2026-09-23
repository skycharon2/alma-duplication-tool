# Queue mode evidence decision — 2026-09-23

## Accepted scope

Authority: project owner instructions on 2026-09-23, accepting a separate,
versioned classification allowance for the reviewed N16-like signatures and
separating mode inference from single-point rule applicability. This is a
project-level classification convention, not proof of the exact exporter formula
or an assertion that ALMA certified this implementation.

`queue_mode_evidence_adapter_2` first matches the existing reference configuration
space at the unchanged representation guard. Only empty exact matches enter the
reviewed fallback: Cycle 11/FULL, Cycle 12/DOUBLE or Cycle 12/FULL, 1875 MHz,
original resolution inside [15.999/16,1] times the reference Hanning N16 value.
Within that input gate, a relative difference of at most 1/16000 is accepted
for classification, equally for every reference mode/profile in the fixed
Cycle/polarization/bandwidth space. Representation noise is only allowed at
boundaries. A mixed mode set returns UNKNOWN; exact ambiguity never falls back.

The 1/16000 bound is accepted for these inputs, not calibrated as a universal
CSV uncertainty. Exporter provenance remains UNRESOLVED. Raw bandwidth,
resolution and source tokens are unchanged and predictions do not enter RMS.

Processor applicability follows the requested-array interpretation already used
by PR #76: non-TP inputs use the normal supported interferometric reference grid;
requested TP requires a mapping for every compatible configuration. FULL+TP,
missing applicability or a missing required mapping remain UNKNOWN. TPS mappings
are conditional user-facing equivalence, not independent native enumeration.
No array flag is represented as a recovered processor identifier.

Geometry does not determine correlator mode. SINGLE_FIELD eligibility is a
separate geometry/array gate, not complete scientific rule readiness. Unknown
geometry remains indeterminate there; non-single-field is outside that rule
scope without erasing available mode evidence.

## Fixed snapshot regression

SHA-256: `8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.
Executed on 2026-09-23 using this method and the existing reference catalog.

| Quantity | Occurrences |
| --- | ---: |
| Regular SPWs | 16,216 |
| Exact reference path | 16,140 |
| Scoped N16 compatibility path | 76 |
| Derived FDM | 15,947 |
| Derived TDM | 269 |
| Mode UNKNOWN | 0 |
| Single-point geometry/array supported | 459 |
| Single-point geometry/array indeterminate | 36 |
| Single-point geometry/array unsupported | 15,721 |

One spectral-scan row remains unexpanded and is explicitly excluded. The 76
compatibility occurrences retain four raw resolution signatures in three
Cycle/polarization groups, all FDM. The totals are regression observations, not
classification constants. They do not establish universal 100% recovery.

The previous census/processor methods and historical reports remain unchanged.
The [adapter contract](../queue_mode_adapter.md) describes current behavior;
formal Queue LINE coverage/resolution/RMS and aggregation remain separate work.
