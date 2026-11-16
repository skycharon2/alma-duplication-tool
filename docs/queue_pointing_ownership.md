# Queue Custom pointing ownership

Project decision, 2026-11-16. This interpretation supersedes the Custom shared
centre assumption in `QUEUE_CUSTOM_EXPLICIT_CSV_3`. It does not certify all
future Queue exports or reconstruct missing ACA pointings.

| Existing beam classification | CSV pointing owner | Coverage allowed |
| --- | --- | --- |
| D12_ONLY | 12M | 12-m only |
| D7_ONLY | 7M | 7-m only, retaining inference evidence |
| MIX_7M_12M | 12M | 12-m only; 7-m unassessed |
| UNRESOLVED | UNKNOWN | No deterministic array coverage |

`resolve_custom_pointing_array` reuses `resolve_queue_beam_interpretation` and
preserves its field status, raw value, angular-resolution threshold, inference
kind and anomalies. `7M_COMPATIBLE_INFERENCE` is not promoted into an explicit
source declaration. TP remains outside interferometric duplication scope.

The resolver reports requested and available pointing arrays. Its
`evaluated_arrays` is empty because resolving ownership does not evaluate science.
Assessment consumers populate evaluated and unassessed arrays from actual
coverage/branches, including missing or invalid coordinates. An unassessed
array must remain UNKNOWN even if other numerical criteria would fail. A positive
12-m branch may establish a 12-m match, but never a 7-m match or complete coverage
of both requested arrays.

Supporting discussion: the supplied `alma_custom_mosaic_english_research_briefing.html`
describes a controlled 7-point 12-m input producing a distinct 3-point ACA export.
It explicitly limits universal ownership claims and labels the ACA predictor
experimental. `alma_rectangle_mosaic_english_visual_simplified.html` limits OT
parity to ICRS/default-Nyquist reference cases. Neither authorizes operational use
of the experimental Custom-to-ACA predictor or certifies Galactic grids.

Supplied briefing checksums (SHA-256), for traceability without redistributing
the presentation files:

- Custom: `75247bab90bd55f22aa912409f99f57ddd089c985474f9080d9cd812630caae4`
- Rectangle: `d74f942ee425cb0a06333322339b9392e5ae767c21df4bcdc962801dfd1c7080`

The coverage implementation uses `QUEUE_CUSTOM_EXPLICIT_CSV_4` and retains a
7-m position variant with no coverage, radius or fabricated point relations.
Both Mosaic and Single Pointing consumers force its complete scientific branch
to UNKNOWN. The 12-m branch still uses the existing numerical formulae.
Candidate and object summaries retain unassessed arrays; JSON, text pages and
matching Explorer comparisons show the missing-ACA notice. A TRUE aggregate
means at least one supported array matched; it does not assess the missing array.
