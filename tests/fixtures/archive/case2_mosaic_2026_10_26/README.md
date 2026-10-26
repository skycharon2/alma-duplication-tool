# CASE2 captured evidence

`ot-12m.txt` is the unmodified file supplied after importing the reconstructed
three-field NGC253 list into OT and exporting Absolute / Degrees. It has no trailing
newline; preserve its original bytes. Array and fixed-ICRS bindings come from the
user's OT workflow, not from the four-column file itself.

The X9c3 and X9c5 directories retain the locally verified package receipts, small
listobs files, reconstructed executions, parsed AQ acquisition records and serialized
TAP client results from 2026-10-26. The approximately 932 MB and 487 MB tar packages
remain in the ignored cache. The package loader verifies local hashes and reparses
listobs; offline tests do not re-download or rescan the original tar files.

`metadata.json` is a serialized client result with field descriptors and provenance,
not an original VOTable capture. The tests restore these recorded contract values.
No Member identity, frequency or coordinate is replaced with a synthetic value.

Tests with moved or extra proposed points are explicit engineering variants. The
non-position request is an existing synthetic test request and cannot establish a
scientifically approved full duplication verdict. The historical CASE2 thresholds
are not treated as a complete proposal. Positive position results apply only to
contexts whose Archive metadata binds the reconstructed execution; extra package
executions are excluded when their compatible metadata is absent.
