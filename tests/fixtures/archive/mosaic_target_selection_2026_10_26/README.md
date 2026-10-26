# Multi-target listobs regression evidence

These small text files were captured from public auxiliary packages on 2026-10-26.
`provenance.json` records their hashes, package URLs and package hashes.

- `lmc-listobs.txt` is the original `uid___A002_Xb8f857_X3977.ms`
  listobs from the calibration weblog for Member `uid://A001/X879/X6e7`.
  Science FIELD IDs 2–4 belong to LMC0NT197, 6–8 to LMC1N127 and
  9–11 to LMC2N113. Each requested target must select its own three fields.
  Scan-to-FIELD name disagreement remains an error, including for excluded targets.
- `n55-calibrated.log` is the complete 208-byte `casapy-20160427-020916.log`
  inside `log/calibrated.log.tgz` for Member `uid://A001/X145/X43d`.
  It contains CASA startup/version information only. It cannot establish pointing
  coordinates or execution identity and is a negative parser fixture.

These fixtures establish neither complete Member coverage nor duplication results.
Large auxiliary packages remain in the local cache and are not versioned.
