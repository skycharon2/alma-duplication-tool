# LMC multi-target acceptance capture

Member: `uid://A001/X879/X6e7`; target: `LMC0NT197`;
project: `2016.1.00063.S`; execution: `uid://A002/Xb8f857/X3977`.

`metadata.json` contains four complete TAP rows captured on 2026-10-26 using an
exact Member/target query through the normal Archive client. Query provenance and
field metadata are preserved. `array_acquisition.json` contains the AQ Member
response records, response hash, retrieval time and endpoint. The target label is
7m; records for other sources are retained to test exact source selection.

`package/` is the successful offline audit of the cached public auxiliary product.
It includes the original and target-MS listobs, response and inventory receipts,
package hash and reconstructed execution. Only the original MS is used for
reconstruction. No complete tar archive is versioned.

The proposed pointings in the integration test are constructed from selected FIELD
coordinates, not exported by a user from OT. Other proposal values are explicitly
constructed from captured Archive metadata for criterion regression. They are not
a scientific observing recommendation or an independent sensitivity measurement.
