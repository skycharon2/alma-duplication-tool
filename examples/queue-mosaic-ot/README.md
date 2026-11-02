# Custom OT coordinate validation — controlled engineering case

These files are synthetic test inputs, NOT OT exports or a real Queue target.
`custom-engineering.csv` adapts the existing reduced Queue fixture: seven Custom
rows replace its targets, positions and offsets; other metadata, including project
code and the fixture's source preamble, are retained only for parser compatibility.
They do not establish a relationship to the original project or observing queue.
Do not activate this CSV as an operational Queue snapshot.

## OT operation

1. Create a local test source `OT_CUSTOM_GEOMETRY_TEST`, fixed ICRS,
   RA **150 deg (10:00:00)**, Dec **−30 deg (−30:00:00)**.
2. Select **Individual Pointing(s)** and the **12-m** pointing list.
   Import `offsets.txt` into the **Pointings** table. It contains seven offsets
   in arcseconds. Verify seven rows, including positive and negative offsets.
3. Export the **Pointings** as **Absolute / Degrees**, preserving the downloaded
   file unchanged, e.g. `ot-12m-absolute.txt`. Do not use the Sources export.
4. Record OT version, reference coordinates/frame, chosen array, seven-point
   count, and import/export settings in a session note. Keep the local OT project
   if available. Nothing needs to be submitted to ALMA.

OT supports Offset imports in Arcsecs and export conversion to Absolute coordinates:
[Cycle 13 Reference Manual §5.4.2.3](https://almascience.eso.org/documents-and-tools/cycle13/alma-ot-refmanual).
The Degrees choice retains more precision than the existing captured sexagesimal
fixture. Importing already-computed absolute coordinates would not test the CSV
**offset conversion**, so use the supplied offset input for this experiment.

The two off-axis offsets are (+10,+10) and (−10,−10) arcsec. The remaining points
are the origin and (±15,0), (0,±15). Positive longitude means celestial east;
do not use the display's right direction as the sign convention.

## Backend round trip

Create a new output directory, then reconstruct:

```sh
python -m alma_duplicate.cli.queue_mosaic \
  --queue-csv examples/queue-mosaic-ot/custom-engineering.csv \
  --output /path/to/new/reconstruction.json
shasum -a 256 /path/to/ot-12m-absolute.txt
```

Copy `binding-template.json` to your output directory. Insert the actual export
hash and session-note path. Set the three confirmations to true only after
checking this controlled source's frame, source/setup/array binding and complete
seven-point export. These confirmations apply to this synthetic experiment only. For an initial
coordinate-only experiment, leave `association_confirmed` and `complete` false:
`parity_status: MATCHED` can still establish the local coordinate comparison,
while coverage remains unresolved. Do not claim setup equivalence from coordinate
agreement; a later end-to-end engineering binding must record the assumed
frequency/setup metadata as well.

```sh
python -m alma_duplicate.cli.queue_mosaic_binding \
  --queue-csv examples/queue-mosaic-ot/custom-engineering.csv \
  --ot-pointings /path/to/ot-12m-absolute.txt \
  --binding /path/to/new/binding.json \
  --output /path/to/new/binding-audit.json
```

Inspect `parity_status`, every pair's error and unmatched rows. The default
0.001 arcsec tolerance is a comparison setting, not a guarantee of OT accuracy.
If parity fails, retain the report and investigate before changing the tolerance.

A match validates this controlled offset conversion only. It cannot establish
which array owns the original CSV's Custom list or its completeness. Do not use
this template for a real candidate. No 7-m coverage is assigned by this test;
the independently generated ACA grid requires separate validation.

Actual OT coordinate validation: **MATCHED**, 2026-11-02, using manual entry
of the seven offsets. See [native exports and scope](../../tests/fixtures/ot_pointings/custom_offsets_2026_11_02/README.md).
File-import acceptance itself remains untested. This validates geometry only;
OT and CSV spectral setup equivalence remains unconfirmed.
