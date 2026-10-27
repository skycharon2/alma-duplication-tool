# Mosaic duplication: research status

This page preserves the earlier research baseline. Current Archive implementation
and remaining work are maintained in [status](../../status.md) and
[roadmap](../../roadmap.md). The [region contract](../../mosaic_s_region_position.md)
owns the default coverage method; the research questions below are not a current
implementation checklist.

Last reviewed: 2026-10-21

## Objective

Extend the ALMA Duplication Tool to assess Mosaic observations in the Queue and Archive without changing the existing Single Pointing checks. A duplication result must be traceable to the observation, the relevant pointing positions, and the applicable position, angular-resolution, and continuum or line criteria.

The development priority is to map Appendix A requirements to required inputs, available evidence, explicit missing-data handling, and acceptance tests. OT experiments are supporting evidence, not a separate research programme or a prerequisite to complete every planned experiment. Existing Single Pointing behaviour remains unchanged.

## Current evidence

| Area | Established | Missing |
| --- | --- | --- |
| Duplication policy | More than 50% of proposed Mosaic pointings must fall within the other observation's half-power-beam coverage. This is a pointing count, not an area fraction. | Coverage model, frequency, boundary handling, and mode-specific applicability. |
| Archive | Local diagnostic fixtures contain 19 science fields for the SPT0303-59 7m sample and 11 for the independent NGC5248 12m sample; comparison summaries are reproducible. | Complete acquisition provenance, direction semantics, and Member-wide execution/setup completeness. |
| Queue | The inspected snapshot has 3,200 rows: 2,940 Custom, 140 Rectangle, and 120 blank. | A source-authoritative key linking Custom rows to complete mosaics. |
| OT | Controlled exports show that displayed coordinates and native export formats can have different precision. | Source-native identity and array binding remain limited. Further OT work is needed only when it resolves a concrete implementation requirement. |

Archive `s_region`, `s_fov`, and central coordinates describe coverage or metadata, not the individual science fields. A successful search or download does not establish that a pointing list is complete.

## Work order

1. Map each applicable Appendix A requirement to its official statement, required inputs, data source, missing-evidence behaviour, and acceptance cases. Keep scientific interpretations distinct from direct policy statements.
2. Use [SCIENCE_GATES.md](SCIENCE_GATES.md) to identify the interpretations that still need confirmation. Do not treat exploratory coverage models as approved policy.
3. Follow [ARCHIVE_PLAN.md](ARCHIVE_PLAN.md) to close input provenance and completeness gaps. The [standalone Archive experiment](../../../experiments/mosaic_footprint_ab/README.md) provides diagnostic fixtures and tests, not duplication verdicts.
4. Implement only the supported scope, with explicit evidence limitations and Single Pointing regression coverage. Queue grouping still needs an authoritative source association.

Keep existing original responses, manifests, hashes, and OT exports as supporting evidence. The previous numbered research documents are not present in this checkout; restoring them or completing the old M01–M12/OT programme is not a prerequisite under the revised scope. Historical manifests may refer to those documents; such references are limitations, not proof that the documents are archived here.

Policy references: [Users' Policies, Appendix A](https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies) and [Proposer's Guide, Appendix A.8](https://almascience.eso.org/documents-and-tools/cycle13/alma-proposers-guide).
