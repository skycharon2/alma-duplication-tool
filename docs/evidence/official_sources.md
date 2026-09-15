# Verified ALMA source evidence

Checked 2026-09-15. Byte-pinned downloaded sources are recorded with URLs, byte
counts and SHA-256 values in `official_source_manifest.json`; the repository
stores identifiers and paraphrased findings, not full copies. The Science Archive
Manual check below is an official-PDF semantic check that has not yet been added
to that byte-level manifest, and is labelled accordingly.

## Policy facts

[Users' Policies](https://almascience.nrao.edu/documents-and-tools/cycle13/alma-user-policies),
Doc 13.16 v1.0, March 2026, Appendix A, printed page 22 (PDF page 24), visually
checked against the PDF:

- Single-field location refers to the other observation's half-power beam.
- Moving objects require name-based identification; the exemption is for solar
  observations, not all Solar System targets.
- The angular-resolution factor is at most two, including equality.
- Continuum qualification requires at least two windows strictly wider than
  1.8 GHz. Equality does not qualify.
- The continuum frequency factor is 1.3; spectral-line comparison requires FDM
  evidence and compatible spectral resolution for sensitivity comparison.

These facts do not require another decision to establish the numerical thresholds.
They do not alone specify every exported field mapping, frequency aggregation,
coordinate convention, or processor-specific bandwidth conversion. A sum of two
beam radii is not introduced by this implementation.

## Archive Frequency Support Type semantics

[Cycle 13 ALMA Science Archive Manual](https://almascience.eso.org/alma-data/documents-and-tools/latest/science-archive-manual),
Doc 12.15 v1.0, March 2026, Appendix A, was checked on 2026-09-15. Its
result-table column description states that `Frequency Support` includes a per-SPW
`Type`, where `continuum` indicates Time Domain Mode (TDM) and `line` indicates
Frequency Domain Mode (FDM). This establishes the documented meaning of that
Archive result-table field.

It does **not** establish that the public TAP projection used by this repository
exposes the `Type`, nor that a value obtained through another interface can be
bound safely to the exact reconstructed candidate SPW. The PDF check is not yet
byte-pinned in `official_source_manifest.json`; Q6 therefore remains open at the
machine-readable acquisition/provenance and SPW-association boundary, not at the
semantic meaning of the documented Archive Type.

## Queue position profile

[Current Queue CSV](https://almascience.eso.org/documents-and-tools/latest/duplication-check-csv)
and [current portal script](https://almascience.eso.org/documents-and-tools/latest/python-script)
were downloaded successfully. The source page describes the script as user
contributed and unsupported by the ARCs; this is implementation evidence, not
an approved ALMA policy implementation.

Profile `QUEUE_PORTAL_CANDIDATE_1` is opt-in. It records each derived interpretation
against its existing context ID and source snapshot. It uses candidate
Ref.Frequency. A zero value invokes the candidate's bandwidth-weighted normalized
sky-SPW mean for supported regular setups. Proposal frequency is not used.
Half-FWHM is the directional selection radius; no symmetric-radius sum is used.

The source dictionary describes RA zero for Solar System targets. The script
uses a zero RA/Dec pair as its ephemeris sentinel. This profile treats that pair
as unresolved for coordinate selection, retaining the row for future name checks.
It is not proof that the object is the Sun or a globally valid celestial classifier.

The blank-frame interpretation follows the script's equatorial convention and is
explicitly labelled as such in row reasons. It does not establish that FK5 J2000
and ICRS are identical. Unsupported frame labels remain unresolved.

## Array evidence limits

The downloaded CSV has 79 operational columns. `standAlone_ACA` is described in
its dictionary but absent from the operational header, just as in the repository
fixture. A dictionary definition is not a row value.

The current script handles this absence by filling False, with a warning, and
elsewhere handles explicit ACA standalone values using 7 m. Thus the older-script
claim that it always hardcodes 12 m is not true of the downloaded version.

This profile deliberately does not fill that missing column: when Use 7-m? and
Use TP? are both False it resolves the remaining interferometric array as 12 m.
When Use 7-m? is True, the row does not identify a unique array and stays unresolved.
TP is unsupported. The current parser does not add an unverified 7 m-only schema.
A future operational standalone column needs a versioned schema extension and tests.

## Geometry and offsets

The dictionary identifies N/A as a single pointing. Parser v6 accepts that literal
in addition to its existing blank-with-zero-offset convention. Blank-with-nonzero
offsets remains unspecified geometry; Custom and Rectangle remain mosaic evidence.

For explicit single fields, the profile transports east/north angular offsets on
the sphere in the declared equatorial or Galactic offset frame. Raw RA/Dec and
offsets remain unchanged. This numerical method is named `TANGENT_OFFSETS_SPHERICAL_1`;
it improves on the portal's local linear RA/cos(Dec) approximation and is not
claimed to be bit-for-bit script reproduction. Offsets at least 90 degrees are
outside its local-offset domain. Mosaics are not silently converted to single fields.

## Bandwidth verification

[Cycle 13 Technical Handbook](https://almascience.eso.org/documents-and-tools/cycle13/alma-technical-handbook),
Doc 13.3 v1.0, March 1 2026: section 5.1.2, page 71 explains the FDM sub-band
15/16 reduction; page 78 Table 5.2 lists rounded usable widths. Both were inspected.
Exact FDM widths include 58.59375, 117.1875, 234.375 and 468.75 MHz; rounded entries
include 58.6, 117.2, 234.4 and 468.8 MHz. Ratios of rounded entries are not exactly
15/16. The rule is tied to the stated processor configuration, not arbitrary inputs.

The downloaded script's `getUsableBandwidth` includes the open interval
1875 < bandwidth < 2000 mapped to 1875 MHz. The existing implementation therefore
retains this branch; removing it based on a Cycle 5/6 version would be unjustified.
The script cites Table 5.3, but the table in the inspected handbook is Table 5.2.
The repository mapper also conservatively preserves near-usable input values
rather than snapping them upward, so it is not an exact floating-point clone.

The [OT bandwidth FAQ](https://help.almascience.org/kb/articles/new-default-for-the-bandwidth-used-for-sensitivity-in-the-ot)
addresses per-channel effective noise bandwidth. That quantity and its Hanning
factor must not be substituted for a window's usable spectral width.

## Helper-script method verification

The Cycle 13 duplication-check helper script was read on 2026-09-15; its
identifier is in `official_source_manifest.json`. Its page states that it is
user contributed, distributed as-is and not supported by the ARCs. The lines
below are recorded as implementation evidence of an existing convention, never
as an approved method.

- `fwhmPB(freqGHz, diameter)` returns `1.13 c / (freqGHz * 1e9) / diameter` in
  arcsec, and the plotted candidate beam uses
  `radius = 0.5 * fwhmPB(freq, diameter)`. The radius is half of a full width,
  and the frequency and diameter belong to the candidate, not to the proposal.
- Continuum sensitivity is scaled as
  `rmsContinuum_mJy = req_sen * np.sqrt(ref_bw / aggregateBandwidth)`.
- Per-window sensitivity at a spectral resolution is scaled as
  `rms_resolution_mJy = req_sen * np.sqrt(ref_bw / res)`.
- `computeAggregateBandwidth` sets overlapping range bounds to zero before
  summing, so an overlap contributes once.

The script also states that its per-window sensitivity uses the reference
frequency and reference bandwidth and does not account for system-temperature
variation between spectral windows. A square-root bandwidth scaling taken from
here is therefore a named provisional method with a stated domain, and `res` in
that expression is a spectral resolution rather than the effective noise
bandwidth that the noise relation requires. Adopting it needs the Q4 and Q5
register entries, not this file.

## Archive frequency_support token census

Every bracket component in the pinned NGC6240 Archive fixture carries five
comma-separated tokens, for example:

    [331.76..333.78GHz,31250.00kHz,2.2mJy/beam@10km/s,160.2uJy/beam@native, XX YY]

These are the frequency range, the spectral resolution, the 10 km/s sensitivity,
the native-resolution sensitivity and the polarization products. No `Type` token
appears in this TAP string. This does not contradict the Science Archive Manual,
which documents a per-SPW Frequency Support `Type` in the Archive result table and
defines `continuum`/`line` as TDM/FDM. Instead, the two observations identify the
current Q6 boundary: the documented semantic field is not exposed by the parsed
public-TAP representation used here. This measurement excludes that TAP string as
a mode source; it does not establish that no other reproducible Archive path can
supply the documented Type, and it is taken from one pinned fixture rather than
from an Archive-wide census.

## Remaining implementation scope

ANGULAR already computes the inclusive factor-two comparison and retains Archive
estimated versus Queue requested semantics. No approval status is changed here.
CONT-SETUP already implements strict >1.8. The example declares usable widths
explicitly; it does not assert that hypothetical hardware has been validated.
CONT-FREQ's numeric factor is known, but selection of representative compatible
frequency evidence remains a separate contract. Q6 likewise no longer needs the
meaning of Archive `Type` to be guessed; it needs a reproducible machine-readable
path and SPW association for that documented evidence. These are not unknown
thresholds. Queue POS-SINGLE remains provisional and Archive POS-SINGLE plus
overall aggregation are not implemented; executed source filters remain visible
in the report.
