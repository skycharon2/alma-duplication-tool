# Unified browser Queue assessment

Both proposed geometries use the configured Queue source without a candidate-type
selector. Each submission pins the CSV bytes and memoizes parsing (including a
retrieval failure), shared across spectral-line and continuum reports.

- Proposed Mosaic dispatches to the existing unified Queue Mosaic evaluator for
  Single Field, Custom and Rectangle candidates.
- Proposed Single Pointing retains its existing Archive/Queue Single Field report
  and adds `queue_geometry_assessment` for Custom and Rectangle candidates.
- Intent tabs remain separate; Archive and Queue results share the intent page.
  A missing Archive configuration does not prevent available Queue Mosaic results.
- Existing report schemas remain readable. New Queue Mosaic reports use
  `queue_mosaic_assessment_1`. Downloads preserve the complete evaluation evidence.

The cross-geometry section reports candidates and arrays independently; it does
not combine branch evidence. The existing Single Pointing summary is explicitly
scoped to its baseline comparisons, with cross-geometry results below it. Queue
Single Field rows marked outside scope in the extension inventory belong to the
baseline evaluator, rather than being silently discarded.

Scientific criteria are unchanged. SPS expansion, Galactic reconstruction and TP
coverage remain unsupported where recorded by the evaluators. Model confidence,
UNKNOWN and search completeness are retained. Successful retrieval is not a
search-wide absence verdict.

The new Queue geometry section currently provides expandable numerical evidence
and report downloads. It does not add a geometry visualization endpoint; existing
Archive/Single Field visualizations and historical reports remain available.

## Bounded report views

Queue result pages default to matching candidates only. Review and nonmatching
views are explicit links, with 20 candidates per page. Candidate records are
indexed in a private JSONL sidecar; page reads do not deserialize the full
scientific download. The Single Pointing page embeds its first matching Queue
geometry page and links to the same paginated views. Full retained geometry
results remain downloadable, including unresolved and nonmatching candidates.

Submitted-observation Single Pointing browser runs honor the existing `matches`
report detail policy: full matching evidence and shared nonmatching criterion
summaries. Version 7/8 inspection validates that compact encoding just as version
6 does; the public evaluator continues to default to full detail. This changes
storage and presentation, not any scientific outcome.
