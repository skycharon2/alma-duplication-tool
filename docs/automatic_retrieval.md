# Automatic retrieval scope

**Current contract.** Browser requests default to `search_options.radius_mode =
"AUTO"`. Validation version 8 resolves the scope; search plan version 4 records
policy `auto_fixed_single_1`. Scientific criteria and report v4 are unchanged.

## Request compatibility

```json
{"radius_mode": "AUTO", "sources": ["ARCHIVE", "QUEUE"], "result_limit": 20}
```

Omit `radius` (or supply null) with AUTO. A non-null radius is a diagnosed
`AUTO_RADIUS_CONFLICT`, never silently discarded. Missing `radius_mode` means
EXPLICIT in the backend: old radius requests retain their conversions and
region/point-cone selection. EXPLICIT still needs a valid radius to search.
Unknown modes are invalid. Browser POSTs from the older form that contain a
radius continue to use EXPLICIT; fresh forms use AUTO without a radius input.

AUTO still requires fixed single-point ICRS coordinates and a selected source.
It does not infer a scientific frequency from missing inputs. Solar exemption,
unsupported moving/mosaic requests and source-access guards remain unchanged.
AUTO cannot be combined with legacy request-beam or Queue candidate-beam
selection. Configuration conflicts are rejected before source providers run.
Existing replay manifests must match the actual mode, radius and complete ADQL;
a legacy region query cannot be replayed as an AUTO centre query.

## Archive: a bounded centre query

The envelope is the largest candidate half-power radius within the supported
profile: candidate frequency at least 35 GHz and aperture diameter at least 7 m.
The existing beam model is `FWHM = 1.13 c / (frequency × diameter)` in radians.
The [official beam explanation](https://help.almascience.org/kb/articles/how-do-i-model-the-alma-primary-beam-and-how-can-i-use-that-model-to-obtain-the-sensitivity-pr)
describes the coefficient; **35 GHz is this retrieval policy's declared lower
bound**, not a value inferred for missing candidate metadata.

`R = FWHM(35 GHz, 7 m) / 2`, rounded outward to `0.0396119023 deg`
(about `142.603 arcsec`). Because the radius decreases with frequency and
aperture, this encloses the half-power discs for 7-m and 12-m candidates within
that profile. It also bounds a 12-m TP beam; TP scientific applicability is still
handled separately by existing rules.

TAP uses the existing CENTER query on `s_ra/s_dec`, without a footprint,
requested-frequency or scientific angular-resolution filter. The same radius
applies to LINE, continuum and mixed intents; display limits do not change it.
No local spatial selector removes returned contexts. AQ acquisition and exact
source binding then precede the existing candidate-specific POS calculation.
A satisfied retrieval constraint never means a satisfied scientific criterion.

**Coverage limits:** missing centres, candidate frequencies below 35 GHz or
unknown frequencies outside the cone, and mosaic extents are not guaranteed to
be retrieved. The bound is for fixed single pointings. It must not produce a
search-wide “no duplication” conclusion. Unknown candidate evidence returned
inside the cone remains available for formal unresolved results.

## Queue: the supplied file

AUTO loads the whole supplied CSV through the existing parser and reconstructs
all valid contexts, with no radius prefilter. Missing frame/beam evidence and
large separations do not remove contexts at this stage. Malformed files retain
the existing failure behavior; AUTO does not bypass source validation.

Explicit API scalar predicates can still filter contexts and are recorded in
the plan. The browser supplies none. Candidate-specific position, array branches
and other scientific criteria run in the existing evaluator. This first policy
makes no new performance claim about early position pruning.

## Limits, audit and display

- `result_limit` limits display only; all retained contexts are assessed and all
  linked retained Archive Members remain eligible for AQ retrieval.
- TAP overflow/count mismatch/failure remains unavailable or incomplete source
  evidence. The assessment does not shrink the cone, retry with a smaller scope,
  substitute replay, or accept a partial catalogue as complete.
- Report `request.raw_search_options` retains AUTO without invented raw radius;
  `request.search_options.radius` stores the resolved radius in degrees.
- `plan.retrieval_policy` records the method, numerical envelope, strategies and
  limitations. Existing source provenance records actual ADQL, counts and status.
- The report page renders its stored scope, including when opened later with a
  different server configuration. JSON, request and inspection downloads remain
  the original artifacts of that run. Historical explicit reports need no edit.

Offline tests cover envelope bounds, malformed/conflicting modes, legacy
compatibility, display independence, TAP-to-AQ binding, incomplete retrieval,
Queue retention, browser downloads and saved report rendering. The earlier
[real LINE smoke](evidence/live_browser_line_aq_smoke_2026-10-05.md) used an explicit
radius and is not live validation of this new AUTO policy.
