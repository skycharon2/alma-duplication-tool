# Scientific follow-up checklist

The [decision register](duplication_rule_inputs.md#7-scientific-decision-register)
owns scientific status. This checklist owns follow-up actions only; it does not
replace the register or approve a method.

Owners and dates below are deliberately unassigned. Proposed assignments and
meeting dates require agreement; none are inferred from a report or code change.

| Task | Current action | Scope |
| --- | --- | --- |
| Archive continuum | Implemented; inspect pinned CLI numerical and real-source replay results | Confirmed fixed, single-pointing scope |
| Line request/pairing | Completed in PR #72: redshift, planned resolution binding and association-bound em_xel evidence; see [pairing contract](line_pairing_design.md) | Confirmed Archive preparation |
| Line rules | Implemented confirmed numerical pair rules; review numerical acceptance and independent real-case labels | Engineering PR3; see [rules](rules.md#confirmed-archive-line-evaluation) |
| Queue science mappings | Keep current provisional results; define source-specific mapping in later increment | Not covered by Archive confirmation |
| Nominal bandwidth conversion | Preserve explicit provisional portal option; no arbitrary automatic mapping | Outside direct usable-width path |
| Broader geometry/mixed setup | Separate later milestones | Mosaic, moving, TP and mixed setups excluded |

The current source of approval is the
[2026-09-21 confirmation](evidence/supervisor_confirmation_2026-09-17.md).
The old Q1–Q8 confirmation checklist is superseded for that scope.

For future methods outside the recorded confirmation, record:

1. The answer, source, date and identifiable decision reference.
2. Applicable configurations and explicitly excluded cases.
3. Required input evidence, units and associations.
4. Positive, negative, boundary and unresolved examples.
5. The implementing method version and corresponding acceptance tests.
6. Reviewer agreement and any remaining limitations.

## Bandwidth conversion boundary

Selecting PORTAL_SCRIPT_V1 identifies a source-script mapping; it does not prove
that an arbitrary proposed setup belongs to its applicable configuration.
The handbook establishes 15/16 for its FDM sub-band construction, not arbitrary
bandwidths or processors. Rounded table entries are not exact ratios.

The integrated evaluation defaults to no nominal conversion. A caller-selected
mapping remains provisional. Before introducing an applicability gate, specify
what configuration evidence the caller must provide and which unresolved reason
is returned when that evidence is absent. Do not invent new scientific metadata
merely to make the current examples pass.

## Integration acceptance and scientific acceptance

Review the [same-request real-source replay and narrow scientific questions](dual_source_replay.md)
for the current acquisition/replay evidence. It uses a complete Archive query
response and a fixed real Queue subset; neither source completeness nor method
approval is inferred beyond that scope.

The older [two-source offline example](../examples/evaluate_single_point_offline.py)
can still be used to inspect request-level and candidate-level criteria, source states, filtering,
display omissions and evidence references.

Its inputs and position interpretations are synthetic test fixtures. It is an
engineering integration demonstration, not a new Archive acquisition, CASE
reproduction, or formal single-point duplication decision.

The in-memory EvaluationReport retains the complete original search result.
The example JSON is a readable summary, not a lossless persistence format for
all source evidence.

CASE2 retrieval can be recorded even when candidate geometry is unsupported.
Do not label its candidate as single-point merely because the proposed request
is single-point. Formal geometry assessment and retrieval recall are distinct.

## Verified source findings (2026-09-15)

[Official-source verification](evidence/official_sources.md) establishes the
inclusive angular factor-two threshold and strict continuum width threshold.
These numerical boundaries are not pending questions. Candidate frequency owns
the Queue beam in the new profile. The Cycle 13 Science Archive Manual also
documents Frequency Support `Type`: `continuum` means TDM and `line` means FDM.
The current public TAP `frequency_support` string used here does not expose that
Type, so Q6 is now a machine-readable acquisition/provenance and SPW-association
question rather than an unknown label meaning. Remaining issues concern evidence
association, frame conventions, ambiguous arrays and scientific approval scope.

The current portal script includes the 1875–2000 MHz interval mapping; it was
not removed based on older script versions. The operational CSV lacks
standAlone_ACA, despite including its dictionary definition.
