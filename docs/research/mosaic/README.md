# Mosaic duplication: research status

This page indexes retained Archive Mosaic research and dated acceptance evidence.
It does not define the current default method, implementation status or delivery
order. Consult [status](../../status.md), [roadmap](../../roadmap.md), and the
[current region contract](../../mosaic_s_region_position.md) for those concerns.

## Reading map

| Purpose | Documents |
| --- | --- |
| Current backend entry and OT import | [Assessment entry](../../assessment_entry.md), [OT file contract](../../ot_pointings_backend.md), [candidate discovery](../../mosaic_candidate_discovery.md) |
| Current region acceptance | [Method and scope](../../mosaic_s_region_position.md), [captured live/replay fixtures](../../../tests/fixtures/archive/s_region_acceptance_2026_10_26/README.md) |
| Scientific decisions | [Decision history](SCIENCE_GATES.md); the 2026-10-23 reconstructed-circle decision remains historically referenced by code |
| Research plan | [Historical Archive acquisition plan](ARCHIVE_PLAN.md), [footprint experiment](../../../experiments/mosaic_footprint_ab/README.md) |

## Retained reconstruction tools (not the default Archive path)

- **Inputs and products:** [local execution reconstruction](../../archive_mosaic_backend.md),
  [product discovery](../../archive_mosaic_products.md),
  [auxiliary acquisition](../../archive_mosaic_acquisition.md),
  [pipeline](../../archive_mosaic_pipeline.md).
- **Inventory and integrity:** [TAP inventory capture](../../archive_mosaic_discovery.md),
  [execution inventory](../../archive_mosaic_inventory.md),
  [execution batches](../../archive_mosaic_batch.md),
  [package audit](../../archive_mosaic_package_audit.md).
- **Position and coverage diagnostics:** [FIELD/scan extraction](../../archive_mosaic_pointings.md),
  [candidate grouping](../../archive_mosaic_groups.md),
  [readiness](../../archive_mosaic_readiness.md),
  [footprint](../../archive_mosaic_footprint.md),
  [multi-SPW footprint checks](../../archive_mosaic_footprint_validation.md),
  [bounded preparation/resume](../../mosaic_candidate_batches.md).

## Dated experiments and historical acceptance

- **Archive surveys:** [acquisition survey and region comparison](../../mosaic_acquisition_survey.md),
  [legacy QA acquisition](../../mosaic_legacy_qa_acquisition.md).
- **Constructed acceptance cases:** [CASE2 OT](../../case2_ot_acceptance.md),
  [CASE2 joint](../../case2_joint_acceptance.md),
  [local scientific regression](../../mosaic_scientific_acceptance.md),
  [multi-target reconstruction](../../mosaic_multitarget_acceptance.md),
  [live preparation batch](../../mosaic_live_batch_acceptance.md).
- **Cross-geometry background:** [Mosaic versus single-field Archive candidates](../../mosaic_cross_geometry.md)
  includes retained reconstruction-route details; its current default is the
  same-context region method.

The following sections preserve the 2026-10-21 research baseline. In particular,
"Current evidence" and "Work order" describe that historical snapshot, not the
2026-10-26 region policy or today's delivery priorities. Dated evidence and
saved decision references are not modified by this index.

Last reviewed: 2026-10-21 (historical baseline only)

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
