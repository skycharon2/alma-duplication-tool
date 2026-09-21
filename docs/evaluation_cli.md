# Evaluation CLI and JSON report

**2026-09-21 update:** [Confirmed Archive continuum implementation](confirmed_continuum.md) adds candidate-side position, continuum frequency/RMS and branch assessments. Report/evaluation versions are 2/3. Queue methods retain their previous status; line pairing references are implemented, line rules are the next increment. Older provisional descriptions below apply to historical methods unless superseded by this update.


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
| 0    | Report written; selected sources completed. Scientific limitations may remain. |
| 2    | Invalid invocation/input, execution value error or report write failure.       |
| 3    | Report written; at least one selected source is missing, failed or incomplete. |

A provisional criterion or insufficient scientific evidence is not a CLI error.
No-candidate reports do not establish absence of duplicates. Code 3 deliberately
allows a useful report from the other source. Unexpected programming errors
propagate; they are not relabelled as scientific missing evidence.

Existing outputs require --overwrite. Report publication uses a temporary file
in the destination directory and an atomic no-clobber link or replacement.
The output must not replace either input file.

## Report version 1

The JSON contains the raw and normalized request, validation issues, input-byte
SHA256, source plans, actual Archive query provenance, Queue snapshot provenance,
all row filtering records, display omissions, request-level criteria and all
retained context evaluations. Missing acquisition/run IDs remain missing.

assessment remains NOT_AGGREGATED. The nested search-stage assessment remains
NOT_EVALUATED. Criterion result and method versions are retained independently.

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

Evaluation version 2 adds provisional `POS-SINGLE` for every retained context.
The Queue method requires `--queue-candidate-beam`; other contexts report
insufficient information. See [the method contract](pos_single.md).
Per-source `filter_summary` counts are derived from processed row audits;
excluded rows remain auditable and server-unreturned rows are outside the count.
