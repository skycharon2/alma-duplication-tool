# Queue continuum project adoption — 2026-09-24

This records the supplied handwritten continuum procedure and Queue single-field
development guide, applied only to the source-only main-12m scope of
[Queue common](../queue_common.md). It is project method approval, not a claim
that the source supplies an aggregate RMS or an official duplication verdict.

Supplied reference identities (unaltered SHA-256):

- Queue development guide: `d622011ffbc17d5bbba458bd3ac1feb619af53eb970b7cb05f7feccd574a56f6`.
- Handwritten notes, continuum pages 13–14: `dfa5d3e870987e186722cc7435cedd0e43b855557c56a39ca7e3c131a694e222`.

The [Cycle 13 Portal helper](https://almascience.eso.org/documents-and-tools/cycle13/python-script/view)
provides the adopted usable-width conversion, overlap removal and
`requested sensitivity * sqrt(reference width / aggregate width)` convention.
It is a user-contributed helper, not authoritative source telemetry. This
limited adoption does not establish its assumptions for every observation.

## Accepted scope

- Fixed target, single field, regular SPWs, explicit `Use 7-m?=False` and
  `Use TP?=False`, source-bound common position interpretation.
- Positive Queue `Ref.Frequency` (GHz) versus user representative SKY frequency;
  symmetric ratio at most 1.3. No fallback from weighted SPW centres or REST input.
- Request CONT-SETUP still requires the approved direct USABLE-width path;
  this decision does not approve nominal proposal bandwidth conversion.
- Candidate usable widths use exactly `cycle13-portal-plotobs-v1.3.1-v2`.
  Sky centres use the existing versioned Queue frequency derivation. Union of
  usable intervals counts overlap once. An unknown width blocks aggregate RMS.
- Positive `Req.Sensitivity` (mJy), `Ref.Freq.Width` (MHz) and
  `Ref.Frequency` (GHz) must belong to that same row/setup.
- Adopt the requested flux-density RMS interpretation at the requested angular
  resolution for comparison with the proposal's direct aggregate mJy/beam RMS.
  Preserve the source unit mJy; do not relabel the raw field as mJy/beam.
- Candidate aggregate RMS is sigma_ref * sqrt(B_ref/B_union). Compare it with
  twice the proposed aggregate RMS, inclusively. Use squared exact arithmetic
  for the decision. No continuum angular correction, no 10-km/s conversion.
- Tsys variation across SPWs is not modelled by this adopted approximation.
  No FDM/TDM evidence is needed for this continuum path.

Method versions: `queue_cont_freq_1`, `queue_cont_rms_portal_1`,
`queue_continuum_branch_1`. Old reports and default evaluation remain unchanged.
Select the new workflow explicitly with `--queue-continuum`.

Unsupported TP, standalone-uncertain 7-m, mixed, mosaic, moving and scan scopes
remain unknown. This is not completion of every Queue common/continuum mode.
LINE and a search-wide absence assessment remain separate work.
