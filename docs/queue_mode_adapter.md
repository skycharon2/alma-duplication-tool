# Queue mode evidence and independent single-point applicability

Method `queue_mode_evidence_adapter_2` implements the
[accepted scope](evidence/queue_mode_evidence_decision_2026-09-23.md#accepted-scope).
This delivers reusable derived mode evidence, not a complete Queue LINE evaluator.
It has no dependency on the separately proposed N16 assessment modules.

## Three boundaries

1. Reference/compatibility matching fixes Cycle, polarization, bandwidth and
   profile scope. Exact mode consensus is tried first; an empty set can enter
   the reviewed N16 allowance. Exact ambiguity stays UNKNOWN.
2. Processor applicability uses an explicit ProcessorScope. Requested TP must
   have conditional equivalence mappings for every compatible configuration.
   Unresolved scope, FULL+TP and missing mappings cannot silently pass.
3. `single_point_applicability` assesses geometry/array scope independently.
   Mode can be FDM while this gate is UNSUPPORTED or INDETERMINATE.

`derive_mode` deliberately has no geometry argument. It returns FDM/TDM/UNKNOWN,
DERIVED origin, PROJECT_ACCEPTED_LIMITED_SCOPE status, decision reference,
method version, original numeric inputs, exact/compatibility path, accepted
configuration records and processor mappings. `enumeration_complete=false`,
`processor_identification=NOT_RECOVERED` and `export_provenance=UNRESOLVED` preserve
the limits. These custom evidence fields are not a new generic rule approval enum.

Fallback only supports (11,FULL), (12,DOUBLE), (12,FULL), bandwidth 1875 MHz and
resolution within [15.999/16,1] times the reference Hanning N16 prediction.
Every reference mode/profile in that space receives the same classification-only
relative allowance 1/16000. Competitive TDM interpretations force UNKNOWN.
No global isclose changes, source-value correction, RMS or coverage calculation.

## Source binding

`classify_spw(row: QueueRowInput, spw_number)` finds exactly one slot inside the
owning typed row. It rejects missing/duplicate slots and unexpanded scans. The
caller cannot supply a detached SPW from a different execution or row. The result
keeps snapshot SHA, physical row identity, project/target, SPW slot, original
numeric values and raw tokens next to mode_evidence and single_point_applicability.

The CLI reads QueueCsvClient typed rows directly. It does not import the census
or consume census JSON. A future evaluator should resolve the same typed row and
SPW through existing association references and call this same entry point.
It must not substitute catalog predictions into coverage/resolution/RMS.

SUPPORTED applicability means only SINGLE_FIELD with explicit non-TP arrays;
position/frame/frequency/RMS and other rule evidence still require evaluation.
UNKNOWN/UNSPECIFIED_WITH_OFFSET geometry is INDETERMINATE; other geometry is
UNSUPPORTED. Neither gate changes mode evidence. Mode processor scope is selected
from use_tp without using geometry; the 7-m flag remains source evidence and is
not a native-processor identifier under the accepted normal-cycle scope.

## Offline export

```bash
python -m alma_duplicate.cli.queue_mode_adapter \
  --queue-csv "$ALMA_QUEUE_CSV_SNAPSHOT" \
  --output-dir reports/queue-mode-evidence-v2 \
  --require-pinned-snapshot
```

Incomplete ingestion is refused; no silent accepted-row denominator. A fresh
output directory is required. `spws.json` contains all regular occurrences,
including unknown/unsupported results. `summary.json` separately counts mode,
matching path, mode reason and single-point scope, with snapshot/catalog hashes,
source versions, parser issues, excluded scan identities and artifact checksum.
Exit 0 means evidence was exported; duplication_assessment=NOT_PERFORMED.

The [dated measurement](evidence/queue_mode_evidence_decision_2026-09-23.md#fixed-snapshot-regression)
records 15,947 FDM, 269 TDM and zero mode UNKNOWN under this fixed snapshot and
requested-array interpretation. It is not a universal coverage claim and does
not erase geometry exclusions. No overall duplication conclusion is produced.

## Regression gates

Tests cover the actual four raw N16 signatures; exact FDM/TDM for Cycle 11–13
and all three polarizations; exact ambiguity; bounded compatibility and injected
opposite-mode competitors; missing profiles/bandwidth; invalid values;
FULL+TP, missing processor evidence and incomplete equivalence mappings;
geometry invariance; typed same-row slot binding and differing row evidence.

Pinned acceptance verifies all 16,216 unique physical row/SPW identities, 76
compatibility occurrences, independent applicability counts, original resolution
preservation, repeated output reproducibility and strict report checksums.
The earlier census and processor modules are unchanged and remain diagnostic.
Queue continuum remains independent; the [roadmap](roadmap.md) owns next work.
