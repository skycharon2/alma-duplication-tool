# Cross-execution candidate pointing groups

Retained reconstruction/research tool. Its inputs and completeness requirements
apply to this tool, not the default Archive Mosaic assessment. Start with the
[current s_region workflow](mosaic_s_region_position.md) for production evaluation.

Candidate grouping follows the verified field-centre comparison layer. It associates
records for diagnostics while retaining every original field and its ASDM identity.
It does not deduplicate records, average coordinates, select a representative centre,
reconstruct a footprint, or evaluate duplication policy.

## Usage

```bash
python -m alma_duplicate.cli.archive_mosaic_groups \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --tolerance-arcsec 0.1 \
  --output reports/mosaic-dev/ic1954-pointing-groups-02.json
```

The input goes through the same saved receipt, execution hash and reparsed listobs
checks as the comparison command. No network access or full archive rescan occurs.
The tolerance is required, finite and positive; 0.1 arcsec is an illustrative
diagnostic choice, not an ALMA policy or astrometric uncertainty. An existing output
is never overwritten, and its parent directory must exist. Exit 0 means the report
was generated, including when it contains ambiguous groups; invalid input exits 2.

## Conservative grouping rule

Build an undirected graph with one node per `(ASDM UID, FIELD_ID)` and edges between
fields in different executions whose spherical separation is within the inclusive
tolerance. Use every in-tolerance neighbour, not only previously accepted matches,
so ambiguous nearby records cannot disappear from the grouping decision.

Each connected component is checked against every member pair. It qualifies as a
candidate only if it contains at most one field per execution and all pairwise
separations meet tolerance. A chain A-B-C with A-C outside tolerance remains one
AMBIGUOUS component; no arbitrary partition or preferred matching is selected.

- CANDIDATE_FULL: at least two members, all supplied executions represented, all checks pass.
- CANDIDATE_PARTIAL: at least two members and all checks pass, but some supplied executions are missing.
- UNMATCHED: one isolated field, retained with the missing execution list.
- AMBIGUOUS: repeated execution identity or an out-of-tolerance pair in the component.

FULL refers only to the supplied executions and is not a Member completeness claim.
Every input field belongs to exactly one reported component. Members retain the
original coordinate strings, numerical coordinates and scan/SPW records. Reports
include maximum group separation, duplicate execution identities, missing executions,
and out-of-tolerance pairs. Component IDs hash sorted ASDM/FIELD membership; they are
stable under input ordering but are not global physical pointing identifiers.

Only ICRS and the comparison layer's validated single Member/target scope are
supported. Cross-execution distance evaluation and component diameter evaluation
each have a five-million-pair bound. Larger inputs fail explicitly.

## Validation

At 0.1 arcsec, the captured IC1954 evidence forms 22 CANDIDATE_FULL groups, each with
three execution-local records and zero separation in the printed field-centre
coordinates. All 66 records remain present. This does not establish physical pointing
identity beyond the source precision or antenna pointing time-series equivalence.

Tests cover captured IC1954 data, unequal FIELD IDs, non-transitive chains,
multiple fields from one execution, partial groups, isolated fields, stable ordering,
invalid tolerances and output overwrite protection. Coordinate and evidence validation
remain covered by the shared comparison loader's regression tests.
