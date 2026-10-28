# CASE2 submitted LINE V2 acceptance

## Inputs and scope

The user-supplied `ngc253-X9c3-pointings.txt` is byte-identical to
`examples/mosaic/case2/ngc253-X9c3-pointings.txt`:
SHA-256 `530a5f23c2a3dd1ee413d6e93d37eb178b737fa85d7d3f3340954054f4eaa60a`.
It contains three absolute ICRS pointings; the acceptance run confirms the complete
12m proposal list explicitly.

`examples/mosaic/case2/submitted-line-v2-request.json` translates the existing
synthetic LINE example into separated requirements: 690.8931792321085 GHz SKY,
FDM, 10 km/s, 8 mJy/beam and 0.07 arcsec angular resolution. These are constructed
test requirements, not the original CASE2 retrieval thresholds or an independently
approved real proposal. Optional physical SPW evidence is empty.

## Reproduce

From the repository root, with the project environment active:

```bash
PYTHONPATH=src python scripts/accept_case2_mosaic_v2.py \
  --output-dir reports/mosaic-dev/case2-v2-offline-new

PYTHONPATH=src python scripts/accept_case2_mosaic_v2.py \
  --live \
  --output-dir reports/mosaic-dev/case2-v2-live-new

python -m pytest -q tests/integration/test_case2_submitted_v2_end_to_end.py
```

Use a new output directory for each run. `--pointings /absolute/path/to/file.txt`
can select the supplied file. Offline transport accepts only the original file's
hash. The offline discovery VOTable is generated from two captured Members;
it is a bounded fixture universe, not an original exhaustive TAP replay. Both
the region query and null-region fallback execute through the production parser,
then metadata construction, s_region geometry and V2 LINE evaluation run normally.
The live mode has no project filter and uses actual discovery and metadata queries.

## Results, 2026-10-28

The fixed suite covers the original request, frequency and sensitivity failures,
inventory independence, identity preservation, persisted-report reads and rejection
of altered offline pointings. Both captured Members contain four SPW contexts.
All eight contexts cover 3/3 proposed positions. X9c3/SPW 25 meets the submitted
conditions; SPW 27/29/31 fail frequency coverage. X9c5 fails angular resolution.

The online run at `reports/mosaic-dev/case2-v2-live-02` completed discovery and
metadata evaluation for 214 candidate Member/target groups and 871 contexts:

| Context result | Count |
| --- | ---: |
| TRUE | 1 |
| FALSE | 694 |
| UNKNOWN | 176 |

The CASE2 Members reproduce the fixed results. All 176 UNKNOWN contexts include
`ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED`; some also lack component
assignment or compatible resolution evidence. They remain unresolved, not negative.
`COMPLETED` describes orchestration, not universal scientific certainty.

An earlier sandboxed run failed DNS resolution and correctly saved `INCOMPLETE`
with no search-wide negative claim. Online counts are observations from this run,
not stable regression expectations. Reports and raw discovery receipts stay in
ignored `reports/`; no large runtime outputs or downloaded packages enter Git.

The full assessment and compact acceptance summary can be reread locally without
querying Archive. Browser UI and downloadable-report integration remain separate.
