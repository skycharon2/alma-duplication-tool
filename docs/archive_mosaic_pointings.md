# Cross-execution Archive field-centre comparison

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

This diagnostic compares reported ICRS field centres across executions of one
project, Member and target. It keeps every execution-local field, identified by
`(ASDM UID, FIELD_ID)`. It neither merges records nor evaluates duplication policy.

## Run

```bash
python -m alma_duplicate.cli.archive_mosaic_pointings \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --tolerance-arcsec 0.1 \
  --output reports/mosaic-dev/ic1954-pointing-comparison-02.json
```

The output parent must exist and the output file must be new. The tolerance is
required, finite and positive. The example value of 0.1 arcsec is a diagnostic
choice, not an ALMA policy threshold or a claimed coordinate uncertainty. No network
access or archive download occurs. CLI success means a report was generated, not
that every field matched. Invalid input or an existing output exits with code 2.

## Evidence verification

The loader accepts resolved package audit directories, including those produced by
package-bound batch reuse. It checks the saved TAP capture, Member-bound discovery,
original-MS candidate inventory, execution hashes and listobs hashes. It reparses
each original listobs and compares the complete execution and provenance to the
saved document. It rejects ambiguous original MS candidates, unsafe recorded output
names, incomplete audits and changed evidence. The report records input hashes.

This verifies local evidence consistency. It does not redownload or rescan the full
auxiliary archive, nor authenticate independently edited receipts. The reported
verification scope makes that distinction explicit.

## Matching definition

For every pair of executions, the diagnostic computes the great-circle angular
separation using an atan2 expression stable at small angles, RA wraparound and poles.
Only ICRS inputs are supported; other frames are rejected instead of silently mixed.
Coordinates must be finite and within their angular ranges. Duplicate FIELD IDs
within an execution, mixed source identities and repeated ASDM inputs are rejected.
The total comparison budget is five million field-pair distances.

A match requires exactly one candidate within the inclusive tolerance in both
directions, and mutual nearest-neighbour agreement. Multiple in-tolerance candidates
are AMBIGUOUS even if one is closer. A field with no in-tolerance candidates is
UNMATCHED. Each direction records nearest field IDs, nearest angular distance and
all in-tolerance field IDs; nearest-distance ties use an explicit 1e-9 arcsec
numerical reporting tolerance. This is not an astrometric precision claim.

The report retains all original coordinate strings, numerical coordinates, source
IDs and scan/SPW associations, with ASDM identity attached to each field. Pair results
include diagnostic matches and maximum/median matched separation. No global grouping
is inferred from pairwise matches. No offsets, proper motions, precession or pointing
time-series corrections are fitted. A field centre is not a primary-beam footprint.

## IC1954 validation

The three recorded executions each contain 22 science fields. At the example
0.1 arcsec tolerance, all three execution pairs have 22 unambiguous matches and
zero separation between the printed field-centre coordinates. The report retains
66 records. This does not establish 66 distinct pointings or prove actual antenna
pointing histories were identical beyond the precision recorded in listobs.

Tests cover this captured dataset, execution-local FIELD identity, known offsets,
tolerance sensitivity, RA wraparound, poles, antipodes, many-to-one ambiguity,
nearest ties, invalid frames and coordinates, evidence tampering and output protection.
Member completeness and duplication policy remain unevaluated.
