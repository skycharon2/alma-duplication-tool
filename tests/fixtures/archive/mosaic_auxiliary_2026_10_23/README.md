# Captured 7m Auxiliary Evidence

`listobs.txt` contains unmodified bytes read from the public 7m auxiliary package
on 2026-10-23. `acquisition.json` records the selected discovery product, source
receipt hash, download timing, archive hash and size, candidate paths, and result.
The corresponding discovery receipt is in `../mosaic_products_2026_10_23/7m/`.

`comparison.json` records equality of all parsed science fields with the earlier
Markdown-wrapped sample and byte equality of live and cached inspection outputs.
The full auxiliary tar is intentionally retained only in the local ignored cache.

`package-links.xml` is the preliminary package-level DataLink response. Its request
was to the official `/datalink/sync` endpoint with ID
`2021.2.00176.S_uid___A001_X15aa_Xe5_auxiliary.tar`. An exact acquisition timestamp
was not recorded for this preliminary probe. It is supporting layout evidence,
not the receipt used by the production downloader.

The live acquisition receipt predates copying the input discovery files into
output directories; the original receipt is preserved unchanged. Current runs
also save those input files. These records do not establish Member completeness.
