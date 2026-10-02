# Archive array evidence and diameter boundary

This document owns the optional, source-bound Archive array adapter and its
project-adopted diameter interpretation. The legacy TAP-only method remains
available. Queue's independent beam inference is unchanged.

## Three different facts

1. TAP `antenna_arrays` is a list of Pad:Antenna names. It does not identify the
   role of every antenna in every science-target scan or image.
2. The official Archive Query (AQ) interface exposes an `array` label per source
   observation. Sources within one Member OUS can have different labels.
3. A scientific primary-beam diameter must belong to the candidate science
   component being compared. A project, Group OUS, or calibrator label alone
   cannot establish that diameter.

The [five-case review](evidence/archive_array_review_2026-10-02.md) contains two
non-solar examples whose TAP lists include multiple antenna families, while
their science-target AQ label and QA2 report both identify 7-m observations.
The capture also contains genuinely mixed solar metadata. Neither observation
supports treating every mixed token list as Queue-style D7/D12 alternatives.

## Legacy executable boundary (without an official array catalog)

| Evidence available to the existing formal evaluator | Diameter / treatment |
| --- | --- |
| Recognized tokens all from the 12-m interferometric family; no unknown tokens | D = 12 m, subject to the other position applicability checks |
| Recognized tokens all from the 7-m family; no unknown tokens | D = 7 m, subject to the other position applicability checks |
| Explicit legacy `12-m` or `7-m` label | Retain existing fixture/API compatibility |
| Multiple families, including CM plus T-pad antennas | No formal D; `UNIQUE_INTERFEROMETRIC_DIAMETER_REQUIRED` |
| Unknown/missing tokens, or TP only | No formal D; retain insufficient information |
| A majority family reaches the retrieval classifier's threshold | Not sufficient for a formal unique D |
| Proposed target is explicitly SUN | Request-level Solar exemption; do not retrieve or evaluate candidates |

`array_family_1` is application-derived classification. Its family/diameter
property is not itself approval to use that diameter in a formal criterion.
`archive_pos_single_1` applies the stricter all-recognized-tokens-one-family gate.
The governing recorded scope remains the
[existing confirmation](evidence/supervisor_confirmation_2026-09-17.md).
The criterion reports its method, context, diameter, frequency, radius, gate and
decision reference; mixed evidence does not acquire an effective diameter.

## Source-bound method adoption (2026-10-02)

The project owner requested an official array evidence adapter bound to the
specific science target, complete 7-m/12-m alternatives for Archive mixed labels
as for Queue, and recognition of TP's physical 12-m aperture. This is a **project
method adoption**, not a new observatory approval or an independent proposal
validation. Method identities are `archive_source_array_1` for binding,
`archive_pos_single_2` for position, and `archive_beam_variant_or_1` for OR of
complete diameter branches.

The loader consumes a captured official AQ response manifest. It checks the
official observation endpoint, query Member, timezone-aware capture timestamp,
response SHA-256, successful query completeness and sibling file paths. An
invalid capture fails explicitly; it does not silently select a different method.
Hashes ensure replay integrity, not independent authentication of a locally
edited manifest. Capture provenance must remain available for review.

Binding requires the existing reconstructed Source–SPW association to be linked.
Its Member UID and source name must agree with the TAP target name and exactly
one AQ observation whose ID is `<member>.source.<sourceName>`. The hit's own
Member and source fields must also agree. No Member-only matching, case folding,
approximate naming or calibrator substitution is used. Duplicate hits, even with
equal labels, are ambiguous. Missing, conflicting or unsupported labels produce
unresolved evidence; they do not fall back to the raw antenna list once this
catalog has been selected.

| Bound AQ source label | Diameter paths | Scientific treatment |
| --- | --- | --- |
| `7m` | 7 m | Existing supported fixed single-field criteria |
| `12m` | 12 m | Existing supported fixed single-field criteria |
| `7m 12m` (either order) | 7 m and 12 m | Evaluate both complete branches, OR their three-valued results |
| `TP` | 12 m, retaining `TOTAL_POWER` identity | POS-SINGLE uses D=12 m and returns the geometric result; broader interferometric CONTINUUM/LINE branch scope remains UNKNOWN |
| `7m TP` | 7 m and 12 m | 7-m branch is evaluated normally; the TP D=12 m position is evaluated, while the TP science branch remains UNKNOWN; OR complete results |
| Any label including both `12m` and `TP` | Unique 12-m diameter, plus 7 m if present | D=12 m is valid for POS-SINGLE, but broader 12-m science scope remains UNKNOWN because this evidence does not separate main-array and TP observing modes |

TP antennas are 12-m single dishes; see the official
[Technical Handbook](https://almascience.eso.org/proposing/documents-and-tools/latest/alma-technical-handbook).
Physical aperture alone does not establish interferometric angular, RMS or
spectral applicability.

### TP D=12 position follow-up

The supervisor-confirmed project decision is recorded in
[the dated decision](evidence/archive_tp_d12_position_decision_2026-10-02.md).
For a source-bound TP path, POS-SINGLE uses D=12 m and the existing inclusive
half-power-beam comparison normally. Source-bound Archive position reports from
this method use `archive_pos_single_3`; historical `archive_pos_single_2` reports
retain their original meaning.

`ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED` remains visible as a
downstream branch-scope reason. It does not erase an otherwise computable TP
position result, but it still keeps current Archive CONTINUUM/LINE aggregation
on that TP path UNKNOWN.

Both diameter alternatives reuse exactly the same retained source context and
its bound SPWs, frequency, resolution and sensitivity. They are **diameter
hypotheses**, not a decomposition of a combined image into independently measured
7-m/12-m products, and not an effective mixed-array beam model. Component-specific
products or sensitivities need a later evidence contract. No criteria may be
borrowed across diameters, sources, contexts or SPWs. TRUE OR UNKNOWN is TRUE;
FALSE OR UNKNOWN is UNKNOWN. No search-wide absence verdict is introduced.

The adapter does not alter TAP retrieval, spatial filtering or search recall.
One original candidate remains one reported context with nested beam variants.
Report v4 carries source-level catalog provenance, context-level binding evidence,
and the new method identities. Inspection v3 and browser export preserve both
paths and pair pointers. Solar request exemption still occurs before catalog or
source access. Without an explicitly supplied catalog, historical methods and
acceptance results remain unchanged.

## Documentary evidence and runtime boundary

For HD14055 and IRAS_09245-5228, the captured AQ science-source labels and
Member-bound QA2 reports support **7-m science observations**. This is a recorded
review finding that the new adapter can use through the exact AQ source binding.
The legacy TAP-only method still reports unresolved diameter for these mixed
name lists. QA2 PDFs are documentary cross-checks; they are not parsed or promoted
automatically by the runtime adapter. No hard-coded target overrides are used.
General per-antenna calibration roles were not reconstructed from raw visibilities
or full WebLogs. The captured AQ service is not promised as a stable public API.

## Enable explicitly

Python callers pass `ArchiveInput(client, array_catalog=load_archive_array_catalog(path))`
to their lazy source provider. Direct evaluator callers use
`evaluate_candidate_search(search, archive_arrays=catalog)`.

The evaluation CLI accepts `--archive-array-evidence /path/to/aq-manifest.json`
together with `--archive-replay` or `--live-archive`. Evidence responses and their
manifest are protected from output overwrite. Even with live TAP selected,
this adapter reads captured AQ evidence; it does not fetch fresh AQ labels.

For the offline browser, additionally set
`ALMA_UI_ARCHIVE_ARRAY_EVIDENCE=/path/to/aq-manifest.json` alongside a compatible
`ALMA_UI_ARCHIVE_REPLAY`. Paths are operator configuration, not researcher input.
Catalog and TAP captures retain their separate dates and hashes; a captured label
does not establish live freshness. A catalog covering only a few sources leaves
other sources unresolved. Do not combine the five real-source catalog with
unrelated synthetic Guide A/B replays and expect matching evidence.

## Replay and regression

The [fixture](../tests/fixtures/archive/array_evidence_2026_10_01/README.md)
contains complete, narrow **engineering** cone captures. The full response is
replayed through `RecordedArchiveClient`; the test then locates the reviewed row
by its identity. These cones do not measure search recall or establish a
duplicate/non-duplicate label for a real proposal.

Run:

```bash
python -m pytest -q tests/integration/test_archive_array_evidence.py \
  tests/integration/test_archive_array_adapter.py
```

Refresh into a new directory, keeping the existing dated capture immutable:

```bash
python scripts/capture_archive_array_evidence.py --live --include-aq \
  --output /tmp/archive-array-review-new
```

The script records raw VOTables, exact ADQL, maxrec, timestamps and SHA-256. Its
optional AQ capture follows the official page's public search service and saves
the request body and response bytes without authentication material. An AQ
capture is not a stable supported ingestion API or a scientific approval.
