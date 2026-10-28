# Step 04C — explicit V2 Archive assessment and traceable reports

## Status and feature boundary

Step 04C adds **opt-in Python APIs**, not implicit activation of the legacy
`assess_observation()` / CLI / browser routes. The Step 03b-A shared validator
continues to reject a separated wire format with `SEPARATED_INPUT_NOT_EXECUTABLE`
unless its caller intentionally invokes the named V2 assessment API below.
The reserved legacy-wire `line_evaluation_scope=SUBMITTED_LINE_REQUIREMENTS_V2`
remains rejected. These are separate contract namespaces, not aliases.

Only FIXED, **LINE-only**, Archive-scoped requests are supported. New-format
Continuum-only or combined LINE+CONTINUUM remains outside this approved path.
Queue, moving targets, Solar, arbitrary physical-SPW completeness assumptions,
implicit client-supplied context support, and search-wide duplication/absence
claims are explicitly excluded. No scientific pairing threshold is changed.

## Public opt-in functions

`alma_duplicate.submitted_line_assessment.assess_submitted_line_single_v2`
accepts the original separated request JSON, search options and **one explicit**
Archive client or query-bound recorded Archive result. The shared search-options
validator and `search_candidates()` supply bounded, authenticated query and
source completeness checks. Every **retained** Archive context receives its
own POS-SINGLE and ANGULAR criteria, 04B reference-bound LINE pairs, and 04A
`archive_line_context_submitted_or_2` branch.

The returned JSON-native dictionary contains:

- `report_version="7"`, `evaluation_version="submitted_line_v2_1"` and a
  distinct `report_kind="SUBMITTED_LINE_V2_CANDIDATE_EVALUATION"`;
- exact original request and search-options JSON, not the internal LINE-only
  compatibility view used for retrieval;
- source status, query binding, provenance, excluded rows, retained and
  displayed candidate counts from the existing search layer;
- full per-context branch, six-criterion pair outcomes, original component
  references, submitted requirement IDs and method versions;
- `assessment=NOT_AGGREGATED`, explicitly distinct from per-context FALSE;
- `v2_science.search_wide_duplication_verdict=NOT_EVALUATED`.

If the Archive client fails, the source is FAILED / SOURCES_UNAVAILABLE and
there is no negative verdict invented from missing rows. Context result arrays
are evaluated for **all retained contexts**, not just display-limited rows.

`alma_duplicate.submitted_line_assessment.assess_submitted_line_mosaic_v2`
accepts original separated JSON, imported OT pointings, **existing typed Archive
comparison contexts**, and real s_region or audited geometry evidence. It
computes Mosaic common criteria with the established geometry rules, then
runs 04B/04A on the same context. Its report is clearly scoped to the supplied
contexts (`SUPPLIED_ARCHIVE_CONTEXTS_NOT_EXHAUSTIVE_SEARCH`). It does **not**
claim to discover the rest of the Archive. This API does not silently launch
TAP or synthesize Mosaic pointings. The caller owns trustworthy candidate
acquisition and the imported pointings' provenance.

## Scientific guarantees

1. No physical SPW appears in the LINE pairing operand list. A physical record
   linked to a LINE requirement is counted **zero additional times** for LINE;
   there is no frequency-based coalescing of distinct physical identities.
2. The original per-pair method `archive_line_pair_and_1` executes all six
   approved criteria on a single Source-SPW component. No cross-pair selection
   of the most favourable coverage, RMS or mode.
3. The V2 method `archive_line_context_submitted_or_2` performs OR only over
   submitted LINE requirements inside **one candidate context**. A missing or
   unknown pair remains UNKNOWN unless another complete pair is TRUE.
4. `physical_spw_inventory_complete` is copied into request provenance but
   is **never** mapped to legacy `setup_complete`. Internal old-field
   `proposed_enumeration_complete=False` is intentionally ignored for V2.
5. A candidate context FALSE never means a source-level or search-wide
   non-duplication. Failed/incomplete sources, omitted contexts, and candidate
   discovery limitations remain visible.
6. A report exposes the original wire request and the normalized, *separately
   scoped* operands; it does not present an internal legacy compatibility
   request as if the user supplied it.

## Follow-up activation boundary

UI `/proposed/separated`, default `assess_observation()`, existing CLI commands,
Queue, mixed scientific purposes and automatic Mosaic discovery are **not**
repointed by this PR. Enabling each needs a separate compatibility and user-facing
scope review, including input hashing, report navigation and persistent storage.
A synthetic Guide B / recorded s_region integration run is engineering acceptance,
not independent Cycle 13 policy approval for a genuine science proposal.

## Checks

```bash
python -m pytest -q tests/integration/test_submitted_line_assessment_step04c.py
python -m pytest -q tests/integration/test_submitted_line_context_evaluation_step04b.py \
  tests/integration/test_submitted_line_aggregation_step04a.py \
  tests/integration/test_separated_cross_scope_step03bc.py \
  tests/integration/test_line_scope_transition_baseline.py \
  tests/integration/test_mosaic_scientific_acceptance.py
python -m pytest -q
ruff check src/alma_duplicate/submitted_line_assessment.py \
  tests/integration/test_submitted_line_assessment_step04c.py
git diff --check
```
