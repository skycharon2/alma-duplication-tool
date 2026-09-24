# Evaluation CLI and JSON report



Run from an installed development checkout:

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/proposed_observation.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --output reports/evaluation.json
```

The input JSON envelope contains exactly `request` and `search_options`.
Source selection remains in search_options.sources. Paths are resolved relative
to the current working directory; the implementation has no repository-root
assumption and imports no test helpers.

No Archive network client is created unless --live-archive is supplied.
A selected source without input is reported as NOT_PROVIDED.
--beam-decision-ref explicitly selects the existing formula strategy.
--aq-equivalent-filters enables the existing opt-in filter semantics.
Neither option approves a scientific method.
`--queue-candidate-beam` selects the separately versioned, source-documented Queue
profile; it cannot be combined with the legacy `--beam-decision-ref` strategy.
It derives row position/array conventions and candidate-frequency beams without
a sidecar. It does not select any nominal-to-usable conversion. See the
[profile contract](queue_candidate_beam.md).

## Exit codes

| Code | Meaning                                                                        |
| ---- | ------------------------------------------------------------------------------ |
| 0    | Report written; selected sources completed, or valid Solar request exempted. |
| 2    | Invalid invocation/input, execution value error or report write failure.       |
| 3    | Report written; at least one selected source is missing, failed or incomplete. |

A provisional criterion or insufficient scientific evidence is not a CLI error.
No-candidate reports do not establish absence of duplicates. Code 3 deliberately
allows a useful report from the other source. Unexpected programming errors
propagate; they are not relabelled as scientific missing evidence.

Existing outputs require --overwrite. Report publication uses a temporary file
in the destination directory and an atomic no-clobber link or replacement.
The output must not replace either input file.

## Report version 4

The JSON contains the raw and normalized request, validation issues, input-byte
SHA256, source plans, actual Archive query provenance, Queue snapshot provenance,
all row filtering records, display omissions, request-level criteria and all
retained context evaluations. Missing acquisition/run IDs remain missing.

Candidate reports have `report_kind=CANDIDATE_EVALUATION`; assessment remains
NOT_AGGREGATED and search assessment remains NOT_EVALUATED. Continuum and LINE results
are in `context_evaluations[].branches`. Rule result schema 2, evaluation version 5
and method versions are independent. Request validation is now version 6:
ERROR invalidates input; MISSING describes selected-branch/search requirements;
CAPABILITY describes relevant unavailable methods; EVIDENCE preserves raw input
limitations and unselected-branch notes without asserting a selected rule failed.
UI consumers should show EVIDENCE separately from blocking/missing-input notices.

Valid `target_kind=SUN` produces `report_kind=SOLAR_EXEMPTION` and
`assessment=NOT_APPLICABLE`, with reason SOLAR_EXEMPT and a versioned confirmation
reference. Search is NOT_EXECUTED, plan and search timestamps are null, sources
are NOT_QUERIED and context counts are zero. These zeros are not a completed empty
search. Neither position, radius nor selected sources is required for exemption;
supplied malformed fields still fail validation. Source flags are ignored without
opening files or creating clients. Input/output equality and no-clobber checks
remain active. For Solar only, combining --archive-replay with --overwrite is
rejected: replay response paths cannot be protected without opening the manifest.
Use a new output path and omit --overwrite in that combination.

Consumers of versions 3 and 4 must switch on report_kind before accessing plan/source
query fields. Historical reports are not rewritten.

Non-finite scalars use an explicit object such as {"non_finite": "nan"} rather
than invalid JSON numeric tokens or silent null substitution. Existing evidence
issues remain present. Unsupported serialization types fail explicitly.

This is a reviewable report, not a lossless Archive/Queue raw-data backup.
It does not serialize full original source tables or establish retrieval beyond
the executed scope. generated_at changes on each export; source-run timestamps
and identities retain their original values.

See [the rule contract](rules.md) and [scientific follow-up](scientific_followup.md).

Spatial evidence is exported as row-local geometry, status and interpretation
references. The source record and full comparison context are not recursively
embedded in every row; source provenance is stored once per source.

For same-request Archive and Queue replay, use `--archive-replay` with the
[captured NGC6240 example](dual_source_replay.md). It is mutually exclusive with
`--live-archive` and never falls back to a network query.

Evaluation version 3 selects branches by intent and adds the confirmed Archive
continuum methods and context aggregation. The separate provisional Queue
POS-SINGLE method requires `--queue-candidate-beam`. See [the method contract](pos_single.md).
Per-source `filter_summary` counts are derived from processed row audits;
excluded rows remain auditable and server-unreturned rows are outside the count.

## Line pair export (report 4 / evaluation 5)

`context_evaluations[].line_pairing` retains the unchanged preparation-only
[builder contract](line_pairing_design.md). Its `assessment=NOT_EVALUATED` describes
the builder, not the subsequent line evaluation. RESOLVED and AVAILABLE remain
association/evidence states, never scientific success.

`context_evaluations[].line_pairs` is an ordered list matching the builder's
attempts. It is empty when LINE is not selected or no windows are listed. Each item has:

- `attempt`: proposed window, candidate context, full Source-SPW/component reference,
  prepared sky frequency/resolution, mode evidence and preparation reasons.
- `criteria`: POS-SINGLE, ANGULAR and four LINE results, each with approval,
  applicability, outcome, issues, method version, confirmation references and
  `eligible_for_formal_aggregation`.
- `truth`, `status`, `reasons`, `scope`, `method_version`, `decision_refs`:
  the coherent pair's three-valued AND result.

LINE-RMS `derived` contains `archive_resolution_kms`, `planned_resolution_kms`,
`sigma_10kms_mjy_beam`, `theta_plan_arcsec`, `theta_archive_arcsec`,
`sigma_at_plan_mjy_beam`, `sigma_comp_mjy_beam`, `sigma_requested_mjy_beam` and
`max_factor`. Blocked calculations remain null with explicit reasons.
LINE-COVERAGE records the sky center and exact component endpoints in GHz.
The [rules contract](rules.md#confirmed-archive-line-evaluation) owns formula and
numeric semantics; the JSON encodes `derived` and `details` as key/value arrays.

The LINE entry in `branches` is the context-local OR of whole pairs. It reports
CRITERIA_MET, CRITERIA_NOT_MET or INDETERMINATE. Incomplete proposed enumeration
adds an unknown alternative; it does not certify source/search completeness.
Continuum remains a separate branch. All retained contexts are assessed despite
display truncation; source failures produce no fabricated pair or absence verdict.
Solar remains a separate report with no source access.

Request model 2, validation 6 and context model/construction 2 identify input and
evidence semantics. Report versions 1–3 and evaluation versions through 4 retain
their historical meanings; consumers should explicitly support report version 4.

## Opt-in Queue common methods

`--queue-common` selects the [versioned single-array Queue common rules](queue_common.md).
It requires Queue source selection, does not enable candidate-beam retrieval,
and does not complete Queue continuum/LINE branches. Without it, legacy methods
are unchanged. See the linked contract for fixed-target assumptions and source gates.

Explicit exclusive-array interpretations use repeatable `--queue-array ROW_ID=7M_ONLY`
or `ROW_ID=TP_ONLY` plus `--queue-array-decision-ref REF`, with `--queue-common`.
See the [row-binding and conflict contract](queue_common.md#explicit-array-declarations-without-a-sidecar).
They do not infer exclusive membership from a positive auxiliary flag.
