# Archive pipeline fixture

`archive_pipeline_v04.ecsv` is a small offline fixture derived from the
structural cases established in the Archive exploration notebooks and v0.4
unit tests. It is intentionally synthetic/minimized and must not be interpreted
as an Archive-wide prevalence sample.

The fixture preserves the explicit Archive projection, scalar data types, raw
structured strings, timestamps, and frequency units needed by the adapter.
It covers:

- bracket frequency-support parsing;
- sparse Source-SPW associations (`SourceA` has SPWs 0 and 2 only);
- brace frequency-support parsing;
- two SPWs mapping to one brace support component;
- mixed per-SPW mode evidence (`em_xel=128` and `em_xel=1920`);
- a blank optional Group OUS value;
- a `3000-01-01` release-date sentinel;
- a publisher-DID mismatch; and
- a 64-character `obs_id` that is unsafe for reconstruction.

The fixture is loaded locally through Astropy ECSV. Tests do not contact the
ALMA TAP service.

The blank Group OUS fixture cell uses a Unicode non-breaking space. Astropy
interprets an ASCII-whitespace-only ECSV field as a masked value; the
non-breaking space remains a real string while still normalizing to blank via
`str.strip()`. This preserves the contract distinction between `MASKED` and
`BLANK_NORMALIZED`.

## Live CASE1 rows

`case1_live_rows_2026-09-11.ecsv` holds ten unmodified rows returned by the live
ALMA TAP service (`ivoa.obscore`) on 2026-09-11 for the CASE1 cone (10 arcsec
around 18:33:39.920 -21:03:39.900). The ECSV metadata records the query, the
336-row size of the full result, the selection rationale, a SHA-256 of the
transcribed source text, and the live `TAP_SCHEMA` field descriptors used to
rebuild the scripted TAP response.

It covers real formats absent from the synthetic fixture: `Circle ICRS`
casing, Pad:Antenna `antenna_arrays` lists (12-m, 7-m ACA, 12-m with a PM
antenna, mixed 12-m/ACA/TP), a masked Group OUS, and a non-mosaic polygon.
The reported Member OUS is a retrieval reference, not a duplicate label.
