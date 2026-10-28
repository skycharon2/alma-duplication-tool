# Submitted LINE V2 Mosaic search

`assess_submitted_line_mosaic_search_v2(raw_request, mosaic, ...)` connects the separated LINE request to existing Archive candidate discovery and metadata acquisition. `mosaic` is a `MosaicAssessmentInput` containing imported proposal pointings, an unused output directory, the search margin and optional mirror configuration.

The entry validates the request before discovery and supports only Mosaic geometry with `S_REGION` coverage. It reuses the existing all-geometry candidate search, including the null-region fallback, and fetches metadata by Member OUS and target. Project, Member and target identities are checked before context construction. No auxiliary packages or reconstructed Archive pointings are acquired.

The shared region orchestration accepts an internal evaluator callback. Legacy callers retain their existing evaluator and report schema. The new entry uses the submitted-requirement V2 evaluator and writes `submitted_line_mosaic_search_report_1` to `assessment.json`. It does not enable a browser route or alter the legacy public request contract.

## Results and provenance

The outer report retains discovery receipts, selected mirror information, candidates, metadata rows, field descriptors and query provenance. Each evaluated candidate contains original context references and pair-level LINE evidence. Context results remain independent.

Discovery incompleteness and metadata failures retain `INCOMPLETE` execution status. Successfully evaluated candidates remain visible when discovery is partial. A successful empty discovery completes execution without asserting a search-wide negative. A discovered candidate with no metadata contexts remains unresolved. In every case, `assessment` is `NOT_AGGREGATED` and the search-wide duplication verdict is `NOT_EVALUATED`.

## Regression checks

`tests/integration/test_submitted_line_mosaic_search.py` covers successful orchestration, partial discovery, metadata overflow, identity mismatch, empty discovery and pre-query request rejection. It uses controlled discovery responses and recorded Guide B spectral metadata with synthetic region coordinates. It is not online Archive acceptance.

The separate supplied-context interface remains available for replay and scientific tests. Browser integration and real CASE2 online acceptance are separate work.
