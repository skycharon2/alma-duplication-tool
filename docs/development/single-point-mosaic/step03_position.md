# Step 03: Single Pointing position against Archive Mosaic coverage

The supervisor-adopted interpretation in [Step 01](step01_contract.md) now applies
to identified Archive Mosaic candidates in formal Single Pointing evaluation.
Method: `archive_pos_single_mosaic_s_region_1`; criterion: `POS-SINGLE`.

The existing spherical region classifier supplies INSIDE, OUTSIDE, BOUNDARY or
UNKNOWN for the proposed fixed ICRS point. INSIDE and BOUNDARY satisfy position;
OUTSIDE fails position; UNKNOWN remains unresolved. The 0.001 arcsec numerical
boundary band is inclusive. No strict-majority Mosaic-proposal aggregation is
used, and no candidate center, observing frequency or beam diameter is needed to
infer the supplied coverage geometry.

Raw region, SHA-256, point classification, boundary tolerance and polygon
convention are retained in the criterion. Regions are bound to the current
context, never pooled across Members. Missing/invalid/unsupported compound
regions remain unknown. Existing TP/mixed-TP screening follows the Mosaic region
adapter; conflicting coordinate interpretation remains unsupported.

Ordinary Archive single-field candidates retain their existing beam formula and
method versions. Unknown candidate geometry stays unsupported. Queue CSV and
Mosaic proposal position calculations are unchanged.

Legacy and submitted-V2 LINE pairing now allow identified Mosaic candidates;
common position evidence flows into existing six-criterion comparisons. Continuum
uses the same position criterion. Numerical angular, frequency and sensitivity
rules and LINE aggregation versions are unchanged. As before, a decisive false
criterion may yield a negative context even when another criterion is unknown;
unsupported scope remains unknown. No result implies search-wide absence.

Step 01 legacy rejection assertions were replaced with the fixed target outcomes.
Tests cover spherical cases, no-center/no-frequency position evidence, scope
exclusions, context binding, Continuum and both LINE paths. Step 04 still needs
report/Explore footprint presentation and live end-to-end acceptance. In
particular, a central-beam drawing must not be interpreted as Mosaic coverage.

## Captured-data expectation changes

The existing 144-row Archive replay includes eight Mosaic contexts. Four remain
scope-unsupported; four now have satisfied region position. Those four still fail
spectral conditions, changing legacy LINE negative/unknown counts from 96/48 to
100/44 and Continuum from 91/53 to 95/49. Queue counts and source captures are
unchanged. The acceptance catalog records these intentional expectation changes.
