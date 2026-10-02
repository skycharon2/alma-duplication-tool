# Archive array evidence review — 2026-10-02

Scope: five selected real observations; engineering evidence and documentary
cross-check, not independent review of genuine proposal duplication labels.
The table below records the TAP-only evaluator at the time of this audit.
The [current boundary](../archive_array_evidence.md) also records the subsequent
optional source-bound adapter; the audit's original results remain unchanged.

## Acquisition and identity

TAP captures were obtained on 2026-10-01. Supporting AQ and QA2 acquisition times
are recorded separately in their manifests. Original bytes and SHA-256 values
are under [the fixture](../../tests/fixtures/archive/array_evidence_2026_10_01/README.md).
The production client performed schema, count and retrieval queries for each
cone, with `QUERY_STATUS=OK` and matched counts. The narrow radius is deliberately
for fixture acquisition and is not a recommended user search radius.

| Case / target | Member OUS | Captured cone rows | Official AQ science-source array | Existing TAP-only formal D |
| --- | --- | --- | --- | --- |
| Pure 12 m / ngc6240 | `uid://A001/X5a3/X18c` | 80 | `12m` | 12 m |
| Pure 7 m / NGC_6240 | `uid://A001/X2fa/X245` | 80 | `7m` | 7 m |
| CM plus TP names / HD14055 | `uid://A001/X2d20/X2e71` | 4 | `7m` | Unresolved |
| Non-solar mixed names / IRAS_09245-5228 | `uid://A001/X3788/Xc194` | 4 | `7m` | Unresolved |
| Solar / Sun_10 | `uid://A001/X133d/X255b` | 4 | `12m 7m` | SUN request is exempt |

The first two cones overlap. Counts describe full captured responses, not five
disjoint populations. `samples.json` pins each selected obs_id, Member UID,
target, representative ASDM UID and exact cone parameters. No candidate values
were fabricated. Tests construct a proposed position at the candidate centre
to isolate the position rule; that proposed request is not a supplied proposal.

## What resolves the apparent contradiction

### HD14055

TAP includes CM antennas and `T701:PM02`, `T702:PM03`, `T703:PM01`, `T704:PM04`.
The AQ record bound to HD14055 reports `7m`. In the same Member OUS, J0423-0120
and J0237+2848 report `12m 7m`. Consequently a Member-only array lookup would
conflate science-target and calibrator evidence.

The [original QA2 report](https://almascience.eso.org/dataPortal/member.uid___A001_X2d20_X2e71.qa2_report.pdf)
identifies that Member OUS and source, reports `Array 7M` on PDF page 1, and
lists the captured ASDM `uid://A002/X1001fdc/X2085` in the execution summary on
page 2. It separately lists the 12-m scheduling blocks in the Group OUS.
Its QA2 state is **SemiPass**; array confirmation does not override that state
or establish duplication eligibility.

### IRAS_09245-5228

TAP includes `A075:DV22`, CM antennas and T-pad PM antennas. The exact science
source has AQ label `7m`, while J1107-4449 and J0904-5735 in the same Member OUS
have `12m 7m` labels.

The [original QA2 report](https://almascience.eso.org/dataPortal/member.uid___A001_X3788_Xc194.qa2_report.pdf)
identifies the Member OUS, source and `Array 7M` on PDF page 1. The execution
summary on page 2 contains the captured ASDM `uid://A002/X11e3e46/Xff4a` and
the second execution `uid://A002/X11eaef9/X7c3a`. QA2 reports Pass.

These two cases support a 7-m **science-source** interpretation. They do not
individually establish the scan role of every listed 12-m antenna. QA2 reports,
their EB summaries, AQ source labels and the public README instructions were
inspected; full WebLogs and raw visibilities were not reconstructed. Original
QA2 PDFs and README files are pinned with URLs and digests in the fixture.

### Solar

The Sun_10 record has DA/DV and CM tokens, and AQ explicitly reports `12m 7m`.
The official [Cycle 13 Proposer's Guide, A.11](https://almascience.eso.org/proposing/proposing/proposers-guide)
describes mixed 12-m/7-m solar interferometry, with a separate restriction for
solar polarization. Solar duplication exemption is a request-level policy
boundary, not a failure to determine D. Do not generalize that exemption to
other Solar System objects or infer SUN solely from an arbitrary source name.

## Official semantics

- The TAP schema describes `antenna_arrays` as Pad:Antenna pairs, not a per-scan
  scientific participation declaration.
- [Archive Primer, Cycle 13, section 5.3.1, printed p.60](https://almascience.eso.org/documents-and-tools/cycle13/archive-primer)
  discusses TP antennas used for calibration of 7-m observations. This is a
  general explanation; its stated Bands 8–10 example is not direct evidence for
  the individual Band 7 and Band 6 observations above.
- [Archive School, pp.4–5](https://www.eso.org/sci/facilities/alma/arc/ArchiveSchool2022/Bendo-ArchiveContent.pdf)
  distinguishes Group and Member OUS. The observed source-level label differences
  show why membership alone does not identify a candidate's science array.

## Delivery conclusion

Keep `array_family_1` and `archive_pos_single_1` unchanged. The regression
captures the current pure-family D results, mixed-list unknown outcomes,
source-bound official labels and Solar exemption. A source-bound official array
adapter is a subsequent change with its own evidence contract; neither majority
voting nor Queue's MIX rule is a substitute.

The sample does not prove that every non-solar Archive observation is single
array. It also does not revise historical census buckets or acceptance labels.

## Engineering verification (2026-10-02)

- New offline evidence regressions: 12 tests, covering all five samples, exact
  source binding of AQ labels, preserved supporting-file hashes and Solar source
  isolation.
- Targeted Archive regression selection: 94 passed.
- Full suite: 1587 passed, 12 skipped. Skips are not passes; the new live captures
  above are separate from opt-in live test execution.
- Ruff F, `git diff --check`, new document relative paths and captured VOTable
  SHA-256 checks passed.

The existing 15-case scientific acceptance catalog and its reference documents
were not changed. This increment does not add a reviewed real-proposal case.

## Subsequent implementation

The project owner subsequently authorized the
[source-bound method](../archive_array_evidence.md#source-bound-method-adoption-2026-10-02).
It can use the captured science-source AQ labels for the two confirmed 7-m
examples. This does not rewrite the TAP-only diameter column, historical test
counts or original captured bytes above.
