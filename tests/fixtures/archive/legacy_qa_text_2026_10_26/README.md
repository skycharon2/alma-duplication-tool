# Legacy QA FIELD evidence

Public Member `uid://A001/X140/X6`, target `RX_J1347.5-1145`, project
`2013.1.00246.S`, captured on 2026-10-26. The auxiliary package is 121,027,072
bytes. `inspection.json` records its URL, hash and the four alternative evidence
entries. The included original `uid___A002_X984bbe_X2df7__textfile.txt` is one
representative text; its hash is in that inspection report. The other texts and
complete package remain in local reports/cache.

Each QA summary reports eight target FIELD coordinates in J2000 and describes an
`.ms.split` dataset. The scan listing uses truncated names and an `Obs Target`
label. The production ICRS/original-MS parser cannot interpret these as equivalent
without additional validation. This fixture tests automatic evidence discovery and
retention, not scientific readiness. Coordinates remain in their original strings;
no inferred ICRS conversion or synthetic original-MS header is introduced.

## Follow-up evidence

`package/` retains the four small QA texts and the bound package audit/metadata
receipts for offline verification. `metadata.json` is a separately captured full
Archive query result for the candidate's shared comparison criteria.
`calibration-script.py.txt` preserves the original Python 2 calibration script as
text; it was inspected, never executed. Its provenance file binds the bytes to the
same downloaded package. The script confirms the named split operation but is not
an independent coordinate reference. The seven science FIELD records (3–9) exclude
FIELD 2, which is used only for calibration. Historical inspection summaries retain
their original eight-record diagnostic counts; current results are reparsed.
