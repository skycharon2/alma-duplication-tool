# Mosaic proposals against Archive candidate geometries

The main assessment entry accepts Mosaic proposals against both explicitly Mosaic
and explicitly single-field Archive contexts. The proposal always uses POS-MOSAIC;
it is never relabelled as Single Pointing.

## Acquisition and routing

Candidate discovery preserves all science-row geometries and stores observed
`geometry_flags` for each Member/target. The VOTable identity parser accepts mixed
geometries for discovery only. The existing Mosaic inventory/package parser still
requires identified science Mosaic rows.

Candidates without a Mosaic flag bypass auxiliary-product discovery and downloads.
They acquire AQ labels and then use the normal complete Member/target TAP metadata
query. Final routing uses normalized geometry from that metadata, not a guess from
the discovery receipt. Unknown geometry remains unresolved.

For a single-field context, the existing spatial adapter verifies query identity,
row identity, coordinate datatype and units. ObsCore s_ra/s_dec are interpreted in
ICRS. The canonical Archive frequency and bound AQ interferometric diameter define
one half-power circle using the existing primary-beam model. No listobs is needed.

Mosaic contexts continue to use verified package science fields, readiness integrity
checks and compatible execution metadata. A package-readiness failure is reported
without hiding independent single-field contexts. A mixed-geometry candidate can
still obtain AQ evidence when its Mosaic acquisition fails.

## Position and result scope

Each proposed row is counted once against the candidate's coverage. Strictly more
than half inside is positive; exactly half is not positive. Numerical boundary
uncertainty and unconfirmed proposal completeness remain explicit unknown states.

A single-field negative result is scoped to that Archive context's complete single
beam. It is not a negative verdict about every execution of a Member or every
observation in the Archive. Unrelated candidates are never pooled to reach a majority.
Mosaic subset negatives retain the existing Member-completeness limitation.

Angular resolution, continuum and line comparisons use the same existing Archive
metadata evaluators and coherent-context aggregation. Single 7m or 12m evidence is
supported under the existing same-array restriction; unresolved/mixed diameter
cases do not silently choose a diameter. TP is not a replacement beam source.

## Verification

```sh
python -m pytest -q tests/integration/test_mosaic_cross_geometry.py \
  tests/integration/test_mosaic_backend.py \
  tests/integration/test_mosaic_scientific_acceptance.py \
  tests/unit/test_mosaic_candidate_discovery.py
python -m ruff check --select F src tests examples
python -m pytest -q
```

Tests cover the common assessment entry with automatic discovery and preparation,
strict-majority outcomes, boundaries, missing units/array/source evidence, unknown
geometry, AQ outage, package-readiness failure and the no-auxiliary single-field
route. Network boundaries use deterministic responses. Existing Mosaic fixtures now
explicitly declare Mosaic geometry rather than relying on ignored single-field flags.

## CASE2 metadata check, 2026-10-26

A read-only ESO TAP query for each exact Member and NGC253 returned:

| Member | Metadata rows | is_mosaic | ASDM represented by TAP rows |
| --- | --- | --- | --- |
| uid://A001/X133d/X9c3 | 4 | T | uid://A002/Xd40be0/X42e2 |
| uid://A001/X133d/X9c5 | 4 | T | uid://A002/Xfeb5e6/X59b7 |

Both queries were COMPLETE and produced four comparison contexts each. Parsed query
receipts are saved locally under
`reports/mosaic-dev/case2-cross-geometry-metadata-01/`. These are serialized client
results with provenance and field descriptors, not raw VOTable captures. This check
does not establish auxiliary-product availability, a complete pointing inventory,
or duplication of a real proposal. A constructed CASE2 proposal and automatic
pointing acquisition remain the next real-data acceptance step.

## Remaining limits

The region prefilter and explicit margin do not establish complete recall relative
to reconstructed beam coverage. Null-region fallback remains bounded and may fail
or overflow. Empty retrieval is not a search-wide non-duplication result. This
increment does not add Queue Mosaic or browser upload/report wiring.
