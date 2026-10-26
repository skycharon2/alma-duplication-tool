# Archive Mosaic scientific acceptance (local validation)

Baseline: main `b13714c1` (2026-10-23). This patch tests the shared Appendix A
criterion pipeline: `POS-MOSAIC` replaces `POS-SINGLE`, while ANGULAR,
CONT-SETUP, CONT-FREQ, CONT-RMS and the four LINE pair tests are reused.

## Run the patch

```bash
git switch main && git pull --ff-only
git switch -c local/mosaic-scientific-acceptance
git apply --check mosaic_scientific_acceptance.patch
git apply mosaic_scientific_acceptance.patch
python -m pytest -q tests/integration/test_mosaic_scientific_acceptance.py tests/unit/test_mosaic_readiness_binding.py
python -m pytest -q tests/integration/test_mosaic_context.py tests/integration/test_mosaic_backend.py tests/unit/test_mosaic_candidate_discovery.py
python -m pytest -q
```

## Acceptance boundaries

* The tests are offline and deterministic, and assert the strict `>50%` rule,
  negative and unresolved states, positive/negative/unknown LINE branches,
  identical shared continuum/line evaluators, component-scoped association,
  coherent context identity and saved readiness integrity.
* They are **not** gold labels for independent real proposal scientific review.
* Cross-geometry routing now includes Archive Single Pointing candidates. Their
  verified TAP centre, metadata frequency and AQ diameter define one beam; Mosaic
  candidates retain the verified package path. Both use the proposed Mosaic
  pointing-count criterion. See [cross-geometry support](mosaic_cross_geometry.md).
* Discovery recall relative to true beam union remains **unestablished**.
* Locally consistent receipts do not prove all Member executions were retrieved.
  Keep UNKNOWN for negative claims until Member completeness is proven.
* `build_readiness` is replayed once per prepared candidate. Verify performance
  with a large archived Mosaic before deploying this as an interactive workflow.

## Next scientific validation

Record at least one independently reviewed real example for: continuum positive,
continuum negative, spectral line positive, line negative, boundary, partial
Member inventory, missing AQ array evidence, mixed Archive geometry, and search
recall. Each record should contain proposal input, exact Archive query response,
AQ capture, auxiliary package checksum, expected per-criterion outcome,
reviewer/date and disagreement notes. Do not label a test gold standard solely
because its expected output was computed by this tool.
