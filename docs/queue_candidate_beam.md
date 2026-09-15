# Queue candidate-beam profile

Run from an installed checkout:

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/single_point/request.json \
  --queue-csv tests/fixtures/queue/queue_pipeline_v1.csv \
  --queue-candidate-beam \
  --output reports/candidate-beam.json
```

No interpretations sidecar or global decision-reference string is required.
The explicit profile flag selects `QUEUE_PORTAL_CANDIDATE_1`; its source references,
frame convention, frequency origin, array derivation and limitations are recorded
per row. See [verified sources](evidence/official_sources.md).

The flag affects Queue only. Archive retains its existing region query, binding
and filtering; no request-derived radius is substituted for unknown candidate
beams in Archive retrieval. The example selects Queue only. It is an offline
fixed-row integration case, not a live two-source recall demonstration.

The old `--beam-decision-ref` behavior remains a legacy request-frequency
exploration mode. It cannot be combined with the new profile, and is not described
as the Appendix A candidate-beam policy. External Python interpretations cannot
be mixed with the automatic profile. Without either flag the original conservative
behavior is unchanged.

## Evidence and outcomes

The existing Queue fixture has 13 unmodified source records. All were matched
against the downloaded full Queue CSV on 2026-09-15; the source still declares
March 3 2026. Download date is not a new observation date.

The NGC6240 row uses candidate Ref.Frequency = 338.5 GHz, no requested 7 m or TP,
and the recorded portal coordinate convention. Its half-power radius is about
8.601 arcsec. Changing the proposed frequency does not change that radius.
The hypothetical complete request directly declares two usable 1.875 GHz windows
and requested resolution 0.5 arcsec; the candidate requests 0.4 arcsec.
CONT-SETUP and ANGULAR therefore compute provisional satisfied outcomes.

Only a subset of rows have supported geometry and array evidence. Unsupported
rows remain retained with reasons, not classified as matches. A display limit of
one never limits rule evaluation: all retained contexts are evaluated. Numerical
position equality within 1e-10 degree remains unresolved, not a definitive exclusion.
No report-level duplicate verdict is produced.

## Replay and versioning

Parser v6 accepts literal N/A single fields and the documented zero Ref.Frequency
fallback sentinel. Raw frequency stays zero; the profile derives a separate beam
frequency. Negative values remain invalid. Other scientific consumers must not
treat that raw zero as a physical frequency. Source identities still hash exact
CSV bytes; parser version records the changed semantics.

The report adds `plan.queue_candidate_beam`, and spatial records add
`beam_frequency_source` and `antenna_diameter_source`. Existing report-v1 fields
keep their meaning. Captured report and validation metadata are in `docs/evidence/`;
new runtime reports go to ignored `reports/`. Timestamps vary on rerun; compare
input hashes, methods, numeric results and scope rather than whole-report bytes.

CASE1/CASE2 retrieval evidence and scientific duplicate labels remain distinct.
This delivery does not establish CASE2 group counts or any new scientific labels.
