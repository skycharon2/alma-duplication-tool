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
