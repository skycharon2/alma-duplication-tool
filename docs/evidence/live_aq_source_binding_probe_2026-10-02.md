# Live AQ source-binding probe — 2026-10-02

## Purpose

This record documents LIVE-AQ-0, a point-in-time research probe of the
Archive Query (AQ) service used by the public ALMA Archive web application.

The purpose is to determine whether current live AQ responses remain compatible
with the existing exact source-binding contract used by
`archive_source_array_1`.

This is not a runtime live-AQ implementation, a stable API declaration, a new
scientific-method approval, or a real-proposal duplication result.

## Baseline

The probe ran from merged `main` at
`9be2bd5bc8d4697a191595abd16abdfdf970f3ed` (PR #121).

The Git working tree remained unchanged during the probe. Raw live responses and
the research manifest were written only under:

```text
/tmp/alma-live-aq-0-2026-10-02
```

## Service discovery

The AQ properties endpoint used by the public web application returned HTTP 200:

```text
https://almascience.eso.org/aq/service/api/v1/properties
```

Observed property keys:

```text
dataPortalUrl
elasticsearchUrl
requestHandlerNewUrl
requestHandlerUrl
sodaUrl
version
```

The current response did not contain `elasticsearchApiKey`.

The advertised search base was:

```text
https://almascience.eso.org/aq/service/api/search
```

and the derived observation-search endpoint was:

```text
https://almascience.eso.org/aq/service/api/search/observations/_search
```

This is a point-in-time observation of the web application's service
configuration. The project does not treat this search endpoint as a promised
stable public ingestion API.

## Probe contract

Each query used the reviewed Member OUS only as retrieval scope:

```json
{"query": {"term": {"mous": "<member_ous_uid>"}}}
```

A Member hit was not accepted as source identity.

For the reviewed target, the probe separately required:

```text
_id == <member_ous_uid>.source.<source_name>
_source.mous == <member_ous_uid>
_source.sourceName == <source_name>
exactly one matching source record
```

Duplicate IDs, missing exact records, source-name conflicts and Member conflicts
were recorded rather than resolved heuristically.

`datasetId` was measured only as an additional observation. It was not promoted
to a new binding requirement.

No TAP `antenna_arrays` fallback, case folding, approximate target matching or
calibrator substitution was used.

## Results

| Sample | Member hits | Exact ID | Exact source | Live array | Prior captured array |
| --- | ---: | ---: | ---: | --- | --- |
| `pure_12m` | 4 | 1 | 1 | `12m` | `12m` |
| `pure_7m` | 5 | 1 | 1 | `7m` | `7m` |
| `cm_with_tp` | 6 | 1 | 1 | `7m` | `7m` |
| `non_solar_mixed_names` | 4 | 1 | 1 | `7m` | `7m` |
| `solar` | 3 | 1 | 1 | `12m 7m` | `12m 7m` |

For all five probes:

```text
complete=true
exact_identity_consistent=true
duplicate_ids=[]
member_conflicts=[]
dataset_id_matches_expected_id=true
array_unchanged_from_capture=true
```

Every query reported an exact total relation and returned the full stated hit
count.

## Binding conclusion

The current live AQ responses for these five reviewed Members are compatible
with the identity semantics already enforced by `archive_source_array_1`.

The result also reinforces why a Member-only binding is insufficient. Each
reviewed Member returned multiple source records, while the intended science
target was identified by exactly one Member-plus-source observation ID.

Therefore LIVE-AQ work should preserve the existing exact binding:

```text
Member retrieval scope
    -> exact observation ID
    -> exact Member field
    -> exact sourceName field
    -> unique source record
    -> source-bound array label
```

The live acquisition layer must not weaken this to a Member-level array lookup.

## Label observations and limits

The live labels observed in this probe were:

```text
12m
7m
12m 7m
```

The probe did not observe a reviewed target with a live `TP` or `7m TP` label.

Therefore this probe does not newly establish live acquisition behavior for
those label forms. Existing TP diameter/scientific-scope decisions remain
separate from this live-service measurement.

The unchanged labels relative to the earlier captured evidence are useful
point-in-time consistency observations. They do not establish future freshness
or immutability.

## Acquisition/provenance gap

The existing binding semantics can be retained, but the current catalog
provenance model is capture-specific.

`ArchiveArrayCatalog` currently carries a `manifest_sha256`, and report v4
serializes its source-level scope as:

```text
CAPTURED_OFFICIAL_AQ_SOURCE_LABELS
```

The captured loader also validates local response files, sibling paths,
response SHA-256 values and a captured manifest.

A live AQ acquisition must not fabricate a captured manifest or reuse captured
scope wording for live responses.

Before runtime live acquisition is added, the catalog/report contract therefore
needs an explicit distinction between at least:

```text
CAPTURED AQ evidence
LIVE AQ evidence
```

while preserving the same source-binding and label interpretation rules.

Live provenance should retain enough information to review the acquisition,
including the discovered endpoint, Member query scope, timestamps, response
integrity identity, completeness state and source-record identity, without
persisting credentials.

## LIVE-AQ-0 conclusion

LIVE-AQ-0 supports the following engineering decision:

- retain `archive_source_array_1` exact Member/source binding semantics;
- retain the existing supported array-label interpretation;
- do not introduce Member-only binding or TAP-name fallback;
- do not represent live AQ as a captured manifest;
- generalize acquisition/catalog/report provenance before adding live runtime
  acquisition;
- keep AQ service instability explicit;
- preserve UNKNOWN for missing, ambiguous, conflicting, incomplete or
  unsupported evidence;
- do not claim new TP, broader scientific or real-proposal scope.

The next implementation increment should address provenance and acquisition
separation before browser or CLI automatic live AQ wiring.
