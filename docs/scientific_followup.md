# Scientific follow-up checklist

The [decision register](duplication_rule_inputs.md#7-scientific-decision-register)
owns scientific status. This checklist owns follow-up actions only; it does not
replace the register or approve a method.

Owners and dates below are deliberately unassigned. Proposed assignments and
meeting dates require agreement; none are inferred from a report or code change.

| Item | Material needed for closure | Follow-up owner | Scientific reviewer | Next review |
| --- | --- | --- | --- | --- |
| ANGULAR mapping | Confirm proposed requested resolution versus Archive spatial_resolution estimate and Queue requested resolution; record scope and boundary examples | UNASSIGNED | UNASSIGNED | UNSCHEDULED |
| Q1 | Record candidate-frequency ownership, antenna and geometry scope, beam-radius convention and boundary examples | UNASSIGNED | UNASSIGNED | UNSCHEDULED |
| Q2 | Confirm usable-width interpretation and the evidence needed to apply a nominal-to-usable mapping to a particular proposed configuration | UNASSIGNED | UNASSIGNED | UNSCHEDULED |
| Q3 | Define window membership, averaging, identity deduplication, completeness and compatible frequency references on each side | UNASSIGNED | UNASSIGNED | UNSCHEDULED |
| Q4 | Confirm RMS smoothing formula, effective noise bandwidth, polarization and beam compatibility | UNASSIGNED | UNASSIGNED | UNSCHEDULED |
| Q5 | Approve the directional RMS truth table, including equality, improvement and worse-sensitivity cases | UNASSIGNED | UNASSIGNED | UNSCHEDULED |
| Q6 | Identify accepted per-window mode evidence and limits of derived UI classifications | UNASSIGNED | UNASSIGNED | UNSCHEDULED |
| Q7 | Confirm retrieval and display grouping semantics; pin CASE evidence separately from any scientific duplicate labels | UNASSIGNED | UNASSIGNED | UNSCHEDULED |

Before changing a method from PROVISIONAL to APPROVED, record:

1. The answer, source, date and identifiable decision reference.
2. Applicable configurations and explicitly excluded cases.
3. Required input evidence, units and associations.
4. Positive, negative, boundary and unresolved examples.
5. The implementing method version and corresponding acceptance tests.
6. Reviewer agreement and any remaining limitations.

## Bandwidth conversion boundary

Selecting PORTAL_SCRIPT_V1 identifies a source-script mapping; it does not prove
that an arbitrary proposed setup belongs to its applicable configuration.
Do not describe the mapping as a universal 15/16 conversion.

The integrated evaluation defaults to no nominal conversion. A caller-selected
mapping remains provisional. Before introducing an applicability gate, specify
what configuration evidence the caller must provide and which unresolved reason
is returned when that evidence is absent. Do not invent new scientific metadata
merely to make the current examples pass.

## Integration acceptance and scientific acceptance

Run the [two-source offline example](../examples/evaluate_single_point_offline.py)
to inspect request-level and candidate-level criteria, source states, filtering,
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
