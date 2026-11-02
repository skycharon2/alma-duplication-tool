# Direct Custom CSV position backend

`assess_queue_custom_csv(parsed, proposed)` and `cli.queue_custom_check` now run
CSV → Custom reconstruction → per-array beam coverage → POS-MOSAIC without an OT
file, manually written candidate pointing JSON, or per-candidate confirmation.
OT exports remain development validation fixtures. This is an offline position
backend; it is not yet wired into the shared assessment entry or browser, and
does not evaluate complete duplication criteria.

## Run

```sh
python -m alma_duplicate.cli.queue_custom_check \
  --queue-csv /path/to/duplication-check-csv.csv \
  --proposed /path/to/proposed.json \
  --output /path/to/new-position-report.json
```

Optionally select one reconstructed `--candidate-id`; otherwise all Custom groups
are evaluated separately. Rectangle candidates and non-Mosaic rows are listed as
excluded from this path. The existing Single Pointing path remains unchanged.
The output parent must exist and existing files are never overwritten. Exit 0
means a report was produced, including UNKNOWN outcomes; malformed input returns 2.

The proposed input is the existing fixed-ICRS point-list contract and can be
constructed directly by a caller; OT import is not required. Minimal example:

```json
{
  "frame_basis": "USER_CONFIRMED_FIXED_ICRS",
  "completeness": "USER_CONFIRMED_COMPLETE",
  "points": [{"id": "p1", "frame": "ICRS", "ra_deg": 150, "dec_deg": -30}]
}
```

These flags describe the caller's proposed list, not candidate CSV completeness.
An unconfirmed proposed list cannot establish a positive result. This interface
compares the same supplied proposed list geometrically to each candidate array;
it does not generate a separate proposed ACA grid or authorize cross-array policy.

## Provisional model `QUEUE_CUSTOM_EXPLICIT_CSV_1`

The report explicitly records these conventions rather than claiming observed
array ownership or official Science Goal identity:

- Reuse strict same-snapshot export-field grouping from `queue_mosaic`.
- Reuse `resolve_queue_beam_interpretation`, including standalone evidence,
  resolution-based inference and TP exclusion.
- When an inferred 12-m branch exists, interpret explicit Custom CSV offsets as
  its pointing list. For a sole inferred 7-m branch, interpret them as its list.
  This mapping is a provisional model convention, including when standalone
  status itself is inferred. It is not independently verified for each target.
- In a mixed-array candidate, retain the generated ACA 7-m grid as UNKNOWN.
  Do not reuse the 12-m centres, invent a bounding-grid approximation or discard
  the usable 12-m branch.
- Use the existing spherical east/north offset transport. Blank frame follows
  the recorded ICRS convention; Galactic/unsupported frames and placeholder
  coordinates remain unresolved. The raw frame and diagnostic provenance remain
  in the report. The diagnostic reconstruction itself is not rewritten as verified.
- Reuse `candidate_frequency`: positive candidate Ref.Frequency or its existing
  normalized sky-SPW bandwidth-weighted fallback at zero. Retain field and notes.

Source rows, columns/units, setup identities, frequency selection, method version
and all assumptions accompany the result. Internal `association_confirmed=True`
in the reused coverage evaluator authorizes computation **under this named model**;
`association_basis` and `coverage_basis` explicitly identify a profile convention,
not an external/caller confirmation. Consumers must retain these fields and the
PROVISIONAL status when displaying or integrating these results.

## Coverage and result meaning

Circular beams use the candidate frequency and inferred branch diameter. Count
membership in the beam union once per proposed point; strict majority means >50%.
Separation is spherical, including RA wrap and high declination. Candidate groups
are never pooled across setups or targets. Total batch work is limited to one
million proposed/candidate point pairs; failure does not produce a partial report.

CSV group completeness is NOT_ESTABLISHED. Known inside points can support a
conditional SATISFIED result under the provisional profile. Unmatched points stay
UNKNOWN rather than becoming negative evidence about a complete candidate.
Consequently this increment generally returns SATISFIED or UNKNOWN, not a
conclusive NOT_SATISFIED for the candidate. Boundary points remain uncertain.
Missing geometry/frequency produces UNKNOWN with specific reasons. Unresolved
array inference retains the candidate without invented branches.

There is no position-only OR of the two array results. Full continuum/line,
resolution, sensitivity and complete branch aggregation remain separate work.

## Validation

The native seven-point OT experiment supports one controlled offset conversion;
it is not a runtime dependency or a blanket ownership/completeness certificate.
Automated tests cover CSV-only execution, inferred/explicit 7-m-only and 12-m-only
branches, mixed-array partial availability, source/setup isolation, blank-frame
convention, frequency fallback, unresolved geometry, unmatched coverage, proposed
completeness, input validation, resource limits and output protection.

Read-only acceptance used the supplied 2026-03-03 snapshot
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`.
A synthetic single-point probe at the exported reference (300.162415,
-0.088206) deg evaluated 420 Custom groups and 840 array branches: 2 provisional
position SATISFIED, 838 UNKNOWN. All 420 mixed-array 7-m branches stayed UNKNOWN.
140 Rectangle records and 120 non-Mosaic rows were accounted for separately.
This is pipeline acceptance with an engineering probe, not an actual proposed
science request, current Queue census or duplication verdict. Full source and
report remain untracked in `reports/queue-custom-csv-step4/`.
