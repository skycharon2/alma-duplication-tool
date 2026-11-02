# Native OT Custom offset validation, 2026-11-02

These are unmodified native Absolute / Degrees downloads from Cycle 13 web OT,
https://cycle-13.sps.alma.cl/ngot/science-goals/0/field-setup/5 .
The exact application build was not exposed in the inspected field page.

Controlled source: OT_CUSTOM_GEOMETRY_TEST in existing test project
MOSAIC_P2B_OT_TEST / SG-C100. Reference ICRS RA 150 deg, Dec -30 deg;
no solar-system selection, zero proper motion and parallax. Individual Pointing(s).
The seven 12-m relative arcsec offsets were entered manually into the table:
(0,0), (+15,0), (-15,0), (0,+15), (0,-15), (+10,+10), (-10,-10).
The attempted local file upload was unavailable through the browser extension;
manual entry was verified against the visible table before export. This is not
an import-file acceptance test.

The OT displayed representative sky frequency 107 GHz, 12-m HPBW 54.42009 arcsec,
7-m HPBW 93.29158 arcsec, seven 12-m pointings and three automatically generated
7-m pointings. Switching the Field Centre Coordinates array selector showed three
disabled 7-m offset rows approximately (+16.79151,-16.79151),
(-36.18068,-2.59766), (+2.59766,+36.18068) arcsec. Each array was exported
separately as Absolute / Degrees. The page was left on 12-m. No proposal submitted.

`ot-12m-absolute.txt` matches all seven reconstructed CSV diagnostic centres at
0.001 arcsec tolerance; maximum separation is about 8.715e-9 arcsec. This is
numerical agreement for this controlled input, not an astrometric accuracy claim.
`parity-audit.json` retains the unchanged output and comparison evidence.
`binding-geometry-only.json` reproduces it with the binding CLI.

The engineering CSV has different spectral metadata from this OT SG. Therefore
association_confirmed and complete remain false, coverages remains empty, and
scientific status remains NOT_EVALUATED. Coordinate parity is MATCHED independently.
This case does not establish original operational Queue array ownership or
completeness, nor validate all reference frames, offset sizes or declinations.

The 7-m export is evidence of a separate generated grid, not an expected match to
the seven CSV rows. Its grid reconstruction and scientific binding remain pending.
Screenshot evidence is stored locally in reports/queue-mosaic-ot-2026-11-02/.
