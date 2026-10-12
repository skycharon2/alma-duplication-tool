# Proposed REST and SKY frequency preparation

## Scope and design decision

The project requirement confirmed on 2026-10-12 accepts an observed SKY frequency
or a REST frequency with source redshift for both LINE and CONTINUUM. This closes
the earlier implementation gap where continuum required direct SKY input. It is
a project input-method decision, not a new ALMA policy or a claim of external
scientific validation.

`proposed_frequency.prepare_frequency()` is shared by LINE preparation and both
Archive and Queue continuum frequency evaluators. It does not change candidate
frequency mappings. The legacy explicit request-frequency beam selector also
uses the prepared value; the default AUTO spatial search bound and the scientific
position criterion continue to use their existing candidate-based contracts. LINE continues to compare a requested window centre with
candidate coverage; continuum uses an independently declared representative
frequency, never a line centre or a mean of window centres as a fallback.

## Input and calculation

- SKY: use the declared frequency directly, even if redshift is supplied.
- REST: require a finite source redshift z > -1 and compute
  `nu_sky = nu_rest / (1 + z)`. Explicit z=0 and negative z > -1 are supported.
- Missing redshift or UNKNOWN reference: keep CONT-FREQ unresolved. A valid
  spatial request can still retrieve candidates; missing evidence is not a pass.
- Invalid supplied numbers, including Boolean redshift, are validation errors.
- Preserve original frequency, unit, reference and redshift. Shared redshift is
  stored once on the proposed observation and serves both selected purposes.
- Use exact decimal input frequency and unit scales (GHz/MHz/kHz/Hz), and the
  decimal spelling of the validated redshift, for rational arithmetic. Do not
  round the prepared frequency before the symmetric max/min <= 1.3 comparison.
  Unrepresentable display operands leave the comparison unresolved.
- Do not infer an observing reference frame, Doppler tracking, bandwidth
  conversion, RMS scaling, or a new continuum setup qualification from this step.

The redshift relation follows the [ALMA Technical Handbook, Cycle 13](https://almascience.hq.eso.org/documents-and-tools/cycle13/alma-technical-handbook).

## Versions and reporting

Frequency preparation is `proposed_sky_frequency_1`. Active CONT-FREQ methods are
`archive_cont_freq_2` and `queue_cont_freq_3`; previous versions remain valid
historical identities and saved reports are not rewritten. LINE method identities
remain unchanged because its existing preparation behavior is preserved.

New CONT-FREQ records store the entered value/unit/reference/frame, preparation
version, exact prepared GHz operand, applicable source redshift, displayed GHz
operand and comparison factor. The report's calculation details render these
stored facts without recomputing them. Missing fields in historical reports do
not imply that any conversion took place. Raw request downloads preserve REST.

## Validation

`tests/integration/test_continuum_frequency_preparation.py` covers both source
paths, unit equivalence, inclusive boundaries and values beyond float precision,
missing/unknown evidence, valid and invalid redshifts, overflow and LINE parity.
Browser tests in `tests/ui/test_runs.py` run the shared backend with offline
Archive and Queue fixtures and compare SKY/REST reports, unchanged aggregate RMS,
request downloads and rendered conversion details. These are engineering
regressions; they are not additional live scientific acceptance cases.
