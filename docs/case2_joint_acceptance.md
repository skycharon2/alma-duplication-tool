# CASE2 joint duplication acceptance

Historical reconstruction-path acceptance. These cases remain regression evidence
for explicit `RECONSTRUCTED` mode; they do not define the default region workflow.
Current [s_region acceptance](../tests/fixtures/archive/s_region_acceptance_2026_10_26/README.md)
records the metadata-only path. Original results and commands are retained below.

This increment tests the existing production assessment entry with actual OT
pointings and captured CASE2 metadata. It adds constructed proposals and regression
coverage; it does not change the scientific comparison formulas or thresholds.

## Constructed proposals

The JSON inputs in `examples/mosaic/case2/` are engineering test proposals, not the
original project proposal or a reconstruction of its requested sensitivity. Both use
the actual three-point OT 12m export in
`tests/fixtures/archive/case2_mosaic_2026_10_26/ot-12m.txt` and a requested angular
resolution of 0.07 arcsec.

- `continuum-test-request.json`: representative sky frequency 690.8931792321085 GHz,
  four explicitly declared usable 1.875 GHz windows centred on the captured X9c3
  frequencies, and aggregate continuum RMS 0.4 mJy/beam.
- `line-test-request.json`: one explicitly FDM sky-frequency window centred at
  690.8931792321085 GHz, with requested RMS 8 mJy/beam at a smoothed resolution of
  10 km/s. This tests the existing Archive LINE rule and its sensitivity basis.

Frequency reference frames remain UNKNOWN where the source does not establish a
frame. No REST/LSRK conversion or listobs spectral inference is introduced. Usable
window placement is not claimed by the continuum width declarations. These evidence
limitations remain visible to the existing validators; the tested rules use the
same approved semantics as the single-pointing workflow.

The 0.07 arcsec value is compatible with X9c3's recorded approximately 0.066806 arcsec
resolution and incompatible with X9c5's approximately 0.223310 arcsec resolution.
The inputs deliberately exercise that difference rather than claiming both Members
must give a positive complete result.

## Acceptance results

For the unchanged CASE2 metadata and actual OT pointings:

| Test | X9c3 expected branch result |
| --- | --- |
| Constructed continuum positive | CRITERIA_MET |
| Constructed line positive | At least one coherent spectral context CRITERIA_MET |
| Requested angular resolution changed to 1 arcsec | FALSE |
| Requested frequency changed to 100 GHz | FALSE |
| Requested RMS changed to 0.001 mJy/beam | FALSE |
| Requested RMS removed | UNKNOWN where no other criterion fails |
| Required candidate sensitivity evidence removed | UNKNOWN where no other criterion fails |
| Line planned resolution changed to 0.1 km/s | FALSE |

Position remains SATISFIED in these tests. A separate constructed metadata variant
makes X9c3 fail frequency while X9c5 fails angular resolution. Neither candidate
passes: criteria from different Members are never pooled into a positive result.
Missing-candidate and split-candidate scenarios explicitly modify copies of captured
metadata for fault injection. Positive scenarios leave candidate metadata unchanged.

The main-entry tests replace only network discovery/preparation boundaries with
captured evidence. They rebuild readiness, reparse listobs, ingest full metadata and
run shared angular, continuum and line evaluators and aggregation. They are not a
fresh network end-to-end duplication verdict for a real user's science proposal.

```sh
python -m pytest -q tests/integration/test_case2_joint_acceptance.py
```

Detailed local reports are under `reports/mosaic-dev/case2-joint-acceptance-01/`.
The summary records each mode, controlled change and per-Member branch truth set.
These reports and large caches are not committed.

## Live candidate retrieval, 2026-10-26

The actual OT export was queried against the live Archive with a 1 arcsec discovery
margin. Discovery completed with 214 Member/target candidates and included both
`uid://A001/X133d/X9c3` and `uid://A001/X133d/X9c5`, associated with the expected
TAP ASDMs. Raw query receipts and the candidate manifest remain under
`reports/mosaic-dev/case2-live-discovery-01/`.

This establishes retrieval of these two known cases, not general completeness of
the s_region prefilter. The recorded recall status remains NOT_ESTABLISHED.
The 214-candidate result exceeds the current 100-candidate preparation limit. No
full automatic evaluation of all 214 was attempted. Bounded batching/resume and
explicit whole-run resource accounting are the next integration priority; silently
truncating candidates or treating unprocessed ones as negative would be incorrect.
