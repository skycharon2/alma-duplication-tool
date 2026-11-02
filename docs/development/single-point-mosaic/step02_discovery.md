# Step 02: automatic Single Pointing discovery of Archive Mosaic coverage

The default AUTO Single Pointing plan now uses `auto_fixed_single_2` and search
plan version 5. It retrieves the union of:

1. the existing candidate-center cone (unchanged radius); and
2. identified Mosaic rows (`is_mosaic = 'T'`) whose `s_region` intersects a
   0.002 arcsec circle around the proposed position.

The small outward margin exceeds the geometry classifier's 0.001 arcsec boundary
tolerance. It is a retrieval allowance, not a changed scientific beam or position
verdict. Server-side geometry behavior still requires live acceptance.

## One combined query

Rather than issuing two requests and merging their results, COUNT and retrieval
use the same parenthesized OR predicate. A row satisfying both arms is returned
once by the predicate. Existing physical rows and their Member/target/component
identities are retained; no project-level deduplication or footprint pooling is
introduced. Existing handling of repeated source rows remains unchanged.

The combined query retains existing count, MAXREC, overflow, mismatch and failure
checks. On failure it does not retry with the center-only scope or substitute replay.
Queue executes independently and retains its existing behavior. Explicit-radius
REGION and legacy formula-beam modes retain their previous semantics; the latter
is not upgraded by this step.

Normalized provenance identifies `CENTER_OR_MOSAIC_REGION`. A saved center-only
response cannot bind to the new plan. Historical saved reports still describe their
original scope. Existing center-only replay captures need their original strategy
or a new capture; changing their metadata to claim wider retrieval is invalid.

Missing/invalid regions and unclassified geometry outside the center cone remain
recall limitations. The union does not establish a search-wide absence verdict.

## Evaluation remains unchanged

Retrieved Mosaic candidates still have the legacy unsupported formal position
result. Step 03 will supply their versioned position method. Retrieval does not
assert region containment, nor does it certify LINE or CONTINUUM duplication.

## Validation

`test_single_point_mosaic_discovery.py` exercises shared ADQL scope, production
ArchiveClient with synthetic TAP responses, near/far candidate centers, separate
Member identities, Queue coexistence, failure isolation and provenance rejection.
`test_auto_retrieval.py` also checks overflow/count-mismatch handling and the
unchanged single-field cone envelope. These are offline tests, not a live TAP
performance or footprint-recall acceptance run.
