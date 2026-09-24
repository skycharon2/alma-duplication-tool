# Queue continuum executable examples

`queue.csv` is a synthetic modification of the small parser fixture, retaining
its dictionary/header layout. Its target fields, sensitivity, coordinates and
SPWs are artificial; it is not a real captured proposal or the pinned snapshot.

For all four rows the usable windows are 1875 MHz wide at 226, 228, 232 and
234 GHz. There is no overlap: aggregate bandwidth = 7500 MHz. Reference width
is also 7500 MHz, so the aggregate RMS equals the input RMS without rounding.
The request RMS is 0.1 mJy/beam, representative frequency 230 GHz and angular
resolution 0.3 arcsec; candidate angular resolution is 0.45 arcsec.

| Row | Difference | Expected continuum branch |
| --- | --- | --- |
| 1 | RMS 0.15 mJy | CRITERIA_MET |
| 2 | RMS 0.3 mJy > 0.2 | CRITERIA_NOT_MET |
| 3 | Reference frequency zero | INDETERMINATE; no continuum frequency fallback |
| 4 | Use 7-m true; recorded Portal row-beam fallback | CRITERIA_MET |

`ngc6240_diagnostic_request.json` reuses the existing single-point coordinates,
search settings and windows, but adds **assumed** proposed aggregate RMS
0.006 mJy/beam. It is an engineering mapping replay, not a real reviewed proposal.
Run it with the existing project snapshot, not this synthetic CSV:

```bash
python -m alma_duplicate.cli.evaluate \
  --request examples/queue_continuum/ngc6240_diagnostic_request.json \
  --queue-csv "$ALMA_QUEUE_CSV_SNAPSHOT" --queue-continuum \
  --output reports/queue-continuum-ngc6240.json
```

The full pinned CSV remains local and is not included in this example.
