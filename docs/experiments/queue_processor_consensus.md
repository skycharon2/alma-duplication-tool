# Queue processor-equivalence experiment

This additive experiment preserves census v1 and does not feed formal LINE-FDM.
Its question is whether known compatible configurations agree on comparison mode,
not whether one exact hardware configuration can be recovered.

## Scope and interpretation

Inputs are Cycle, polarization, raw Queue bandwidth and resolution. The optional
requested-array view also uses UseTP. SINGLE, DOUBLE and FULL are enumerated for
Cycles 11–13. BLC 2x2 resource splits are generated forward from full bandwidth;
4x4 remains DOUBLE-only, one full-resource SPW per baseband. The numerical grid
uses the handbook/proposer tables, not ambiguous prose about 4x4 channel counts.
Public OT response profiles extend Hanning with numerical Uniform, Welch and
unaveraged Hamming, Bartlett, Blackmann and Blackmann-Harris profiles.

TPS entries are **user-facing FPS equivalence mappings**, not independently
recovered native configurations. Their native mode is null. A BLC 4x4 mapping
records the distinct fourfold-bandwidth 2x2 counterpart at the same resolution;
it never changes the original Queue coverage. A counterpart above 2 GHz is
unresolved, not an invented 4 GHz SPW. FULL polarization excludes TP in the
all-family view; a FULL request explicitly requiring TP remains unresolved.
UseTP=false removes TP only from the requested-array view. It does not identify
a source-bound processor. Legacy ACA contingency operation is outside scope.

Every compatible BLC explanation must have a mapping if TP is required. Missing
mappings block conditional consensus even when the matched BLC modes all agree.
Same-mode configuration ambiguity is retained and does not block mode consensus.

The catalog is **not exhaustive**: averaged profiles for four weighting functions
are unavailable, retrieved OT code is not a Cycle-specific release manifest,
TPS response/export applicability is conditional, and coefficient 15.999 lacks
retrieved official export provenance. `enumeration_complete=false`,
`formal_mode=UNKNOWN`, and `scientific_closure=NOT_ESTABLISHED` are intentional.
Do not advertise this as universal processor-independent recovery.

## Reproduce

```bash
python -m alma_duplicate.cli.queue_processor_census \
  --queue-csv /path/to/queue.csv \
  --output-dir reports/processor-consensus \
  --require-pinned-snapshot
```

A new output directory is required. `spws.json` retains each physical row/slot,
raw fields, old evidence and four new views; `matched_configurations.json` holds
configuration/profile details. `summary.json` gives counts, single-field counts,
reason counts, provenance, parser warnings and artifact hashes. Spectral scans
remain excluded and no physical SPW is deduplicated.

## Pinned snapshot result

See the [dated measurement](../evidence/queue_processor_consensus_2026-09-23.md).

## Sources and applicability gaps

Per-cycle official Technical Handbook sections 5 and 6, Proposer's Guide spectral
setup tables and TP counterpart notes, and OT User Manual polarization and
multi-region tables underpin this experiment. Exact URLs and existing handbook
hashes are exported in `sources`; public OT revisions remain pinned by commit.
TPS mappings cite their specific cycle. BLC weighting factors are not presented
as independently measured TPS native responses.

The 14 counterpart gaps, 76 export signatures and missing profile/applicability
evidence delimit this experiment. They are not a blanket blocker on continuum.
The [roadmap](../roadmap.md) owns engineering order; the [Queue mapping table](../queue_single_point_mapping.md)
owns scoped rule requirements. No formal Queue adapter is approved by this experiment.
