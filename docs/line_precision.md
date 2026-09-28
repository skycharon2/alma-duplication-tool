# Shared LINE decision precision

Implemented from baseline `065aefe636576e04ac30d1fd501a017fbf81d341`.

`proposed_line_preparation_2` retains `sky_frequency_ghz_exact` and
`planned_resolution_kms_exact` as positive rational strings (integer or
numerator/denominator). Existing floating-point fields are display values.
Archive and Queue coverage, resolution compatibility and RMS read the exact
operands, never reconstructing them from rounded display values.

Validated request quantities retain their original decimal values and units.
The LINE preparation path applies exact powers-of-ten unit scales to those
inputs before REST/redshift and resolution derivations. This prevents a MHz
input from changing at the MHz-to-velocity-to-MHz boundary. It does not recover
precision already lost before JSON input, or change candidate CSV values.

Affected Archive coverage/resolution/RMS methods and Queue coverage/resolution/
RMS methods advance to version 2. Their numeric method is
`exact_prepared_line_rationals_2`. FDM, common conditions and AND/OR aggregation
are unchanged. Report v4 gains additive preparation fields; existing display
fields retain their meaning. Historical reports are not rewritten.

No global epsilon or approximate comparison is introduced. Missing/conflicting
preparation evidence remains unavailable. RMS continues to be blocked by a
coarser candidate resolution and consumes the same exact planned resolution as
the compatibility condition.

Regression: `tests/integration/test_line_precision.py` covers both sources at
and immediately around the frequency-resolution boundary, equivalent input
units, REST/redshift preparation, missing resolution and strict JSON output.
Existing line tests continue to cover RMS calculations and evidence isolation.

Pair inspection identities and the thin UI remain separate increments.

The active acceptance catalog expects the new numerical method versions; its
scientific reference values, source captures and expected outcomes are unchanged.
