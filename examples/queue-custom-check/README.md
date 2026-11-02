# Synthetic Custom science request

These JSON files are engineering inputs for the seven-point CSV in
`../queue-mosaic-ot/custom-engineering.csv`. They do not reproduce the 107 GHz
OT session's spectral setup or a real observing proposal. The proposed request
has a one-point Mosaic list at (150,-30) deg, per-pointing continuum RMS 10 mJy/beam,
angular resolution 2.6 arcsec and a representative frequency matching the fixture.
Four supplied usable windows demonstrate the existing continuum setup rule.

Run the command in [the backend documentation](../../docs/queue_custom_science.md).
Expected result: both complete continuum branches TRUE, and
`matching_arrays_by_intent.CONTINUUM = [7.0, 12.0]` under the provisional CSV model.
