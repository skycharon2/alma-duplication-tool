# Proposed-observation form sketch

Design only, version 0.1; no HTML or executable request model in this PR.
Normative field/readiness specification: [input contract](duplication_rule_inputs.md).
The tables below are the reviewable low-fidelity layout, in display order.

## Panel 1 — Target and scope

| Control | Initial display | Interaction |
| --- | --- | --- |
| Target type | Fixed target / Moving target / Sun | Explicit choice; unsupported or exempt choices show explanation |
| Geometry | Single pointing / Mosaic | Independent of scientific purpose; mosaic does not silently use one center |
| Target name | Optional text | Display/provenance only |
| RA format | Degrees / Hours:minutes:seconds | Unit shown next to entry; changing format must explicitly convert or clear |
| RA, Dec | Empty fields; Dec format degrees or signed DMS | Frame shown as ICRS; no name lookup or frame guess |

Fixed-target validation appears inline next to coordinates. For unsupported
target/geometry combinations, keep entered values but disable candidate search
with a specific reason; Sun displays assessment not applicable.

## Panel 2 — Proposed observation

| Control | Initial display | Interaction |
| --- | --- | --- |
| Purpose | Continuum / Spectral line checkboxes | Both may be selected; explanatory text says configuration determines rule applicability |
| Requested angular resolution | Value + arcsec/mas | Optional for broad search; never labelled as a maximum candidate resolution |
| Array information | Unknown / explicit information | Expand only if supplied; no automatic diameter |
| Setup complete? | Explicit yes/no | Distinguish an unfinished setup from evidence that no other windows exist |

### Repeatable spectral-window card

| Row | Controls | Association behavior |
| --- | --- | --- |
| Header | Window label; stable internal ID; Remove | Removing a referenced window requires resolving its sensitivity references |
| Frequency representation | Center + bandwidth OR lower + upper | Only one editable representation; derived values shown read-only |
| Frequency/width | Values + GHz/MHz/Hz; bandwidth kind | Unknown width meaning remains explicit |
| Frequency frame | Supplied frame / Unknown | No guessed frame |
| Correlator mode | FDM / TDM / Unknown | No automatic mode derived from purpose or channel count |
| Spectral resolution | Value + Hz/kHz/MHz | Label explicitly excludes channel spacing |
| Footer | Add window | No copying sensitivity implicitly |

### Repeatable sensitivity card

| Control | Conditional display |
| --- | --- |
| Purpose | Continuum or line for this entry |
| Applies to | Select contributing window IDs; one for line/native/smoothed scope |
| Requested RMS | Value + Jy/beam or mJy/beam |
| Measured over | Aggregate bandwidth / Native spectral resolution / Smoothed resolution / Unknown |
| Reference frequency | Value + frequency unit |
| Reference width | Aggregate bandwidth or smoothing resolution, labelled by selected basis |
| Velocity width | If supplied: km/s, convention/reference context; comparison pending approved conversion |

Native basis points to that window's supplied actual resolution. Missing basis
does not force a false selection. Kelvin is visibly unsupported, with an
explanation that additional beam/frequency context and a method are needed.

## Panel 3 — Candidate search options

Visually separate from proposed-observation controls.

| Control | Meaning |
| --- | --- |
| Search radius | Explicit positive value and arcsec/arcmin/deg; search bound, not primary beam |
| Sources | Archive / controlled Queue snapshot |
| Optional candidate constraints | Operator + value + unit, for example angular resolution `< 0.5 arcsec` |
| Result limit | Retrieval cap; reaching it requires explicit completeness reporting |

Do not prefill observation parameters from example search constraints. Queue
selection should eventually show acquisition ID/checksum and parse-run ID; the
user must not re-enter missing Archive or Queue scientific evidence.

## Panel 4 — Review and action

| Summary row | Example wording |
| --- | --- |
| Input validity | Inputs valid / Correct the indicated field |
| Search readiness | Ready for bounded candidate search |
| Assessment readiness | Line sensitivity comparison unavailable: window W1 lacks its RMS reference resolution |
| Candidate-side evidence | Will be checked per returned candidate; request validity is not a duplicate verdict |
| Search scope | Display radius, sources and restrictive predicates explicitly |
| Action | Search candidates; enabled only when search readiness permits |

Example partial draft: valid ICRS target and radius, line intent, W1 with unknown
mode and sensitivity basis. Show search enabled plus separate missing reasons
for W1; do not label the request ready for a complete duplication assessment.

No button is labelled “Confirm duplicate”. Unsupported geometry and solar
exemption must not be displayed as “no duplicates found”. Backend output must
carry the same distinctions independently of the future web framework.

## Review checklist

- Can a reader distinguish search radius, primary beam and angular resolution?
- Can two windows carry different sensitivity bases without accidental sharing?
- Does selecting continuum leave configuration qualification independent?
- Does missing candidate evidence stay on the candidate side?
- Are missing optional fields different from invalid supplied values?
- Do the IN-* cases in the contract cover each conditional control?

This sketch has not undergone user usability testing or scientific sign-off.
