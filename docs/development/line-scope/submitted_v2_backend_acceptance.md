# Submitted LINE V2 backend acceptance

The backend regression suite exercises the public V2 assessment functions without changing browser routes or legacy request semantics.

## Coverage

`tests/integration/test_submitted_line_backend_acceptance.py` adds 14 cases:

- Default Mosaic `s_region` containment: strict majority, exactly half, frequency mismatch and unavailable region evidence, with physical inventory completeness both enabled and disabled.
- Multiple submitted requirements: frequency coverage from one requirement cannot combine with sensitivity from another. A complete matching pair makes the context match.
- Single Pointing display limits do not remove retained contexts from scientific evaluation.
- Successful empty retrieval, overflow and provider failure retain distinct source statuses. None creates a search-wide duplication verdict.

Mosaic geometry variants are synthetic. Spectral metadata comes from the existing Guide B replay. This is deterministic backend regression coverage, not online Archive acceptance or a labelled real-proposal validation.

## Entry points and remaining boundary

`assess_submitted_line_single_v2` validates the separated request, performs the existing bounded Archive search and reports all retained contexts.

`assess_submitted_line_mosaic_v2` evaluates supplied Archive contexts and imported proposal pointings. Its default geometry is Archive `s_region`. It does not discover candidates or establish search completeness. Callers must preserve that distinction; an empty supplied context list is not an exhaustive negative result.

Both interfaces retain the submitted requirement IDs and context-bound pair evidence. The legacy public assessment entry remains unchanged. The next integration must connect Mosaic candidate discovery to V2 evaluation while retaining source completeness and candidate identity; it must not route a new request through legacy aggregation.

## Validation

The new suite and related Step 04, legacy scope and region-position suites passed: 112 tests. No production code or UI was changed.
