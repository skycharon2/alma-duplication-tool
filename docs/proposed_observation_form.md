# Proposed-observation form sketch

Design only, version 0.2; no HTML or executable request model in this PR.
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
| Search radius | Value + arcsec/arcmin/deg | First-screen search control, visibly separate from observation values; not HPBW |

Users can proceed with position and search radius alone. Panels below progressively
add observation evidence; they do not block broad search when optional facts are
unknown. Keep search radius in SearchOptions despite its early visual placement.

Fixed-target validation appears inline next to coordinates. For unsupported
target/geometry combinations, keep entered values but disable candidate search
with a specific reason; Sun displays assessment not applicable.

## Panel 2 — Proposed observation

| Control | Initial display | Interaction |
| --- | --- | --- |
| Purpose | Continuum / Spectral line checkboxes | Both may be selected; explanatory text says configuration determines rule applicability |
| Requested angular resolution | Value + arcsec/mas | Optional for broad search; never labelled as a maximum candidate resolution |
| Array information | Unknown / explicit information | Expand only if supplied; no automatic diameter |
| Have you listed all spectral windows? | Explicit yes/no | List completeness only; some listed windows may still lack parameters |
| Representative frequency | Optional value/unit and window label | Independent from center and RMS reference frequency; advanced reference/origin details |

### Repeatable spectral-window card

| Row | Controls | Association behavior |
| --- | --- | --- |
| Header | Window 1, Window 2, ...; Remove | Stable IDs stay internal; relabelling preserves associations, deletion prompts only for affected RMS entries |
| Frequency representation | Center + bandwidth OR lower + upper; unknown values allowed | Complete values produce labelled derived intervals; incomplete values stay partial |
| Frequency/width | Values + GHz/MHz/Hz; width meaning under advanced information | Not sure remains explicit; derived intervals labelled nominal/usable/unverified |
| Advanced frequency reference | Sky/rest/unknown; supplied frame / Not sure; origin example: copied from OT | No guessed execution reference; retain original label |
| Correlator mode | FDM / TDM / Unknown | No automatic mode derived from purpose or channel count |
| Spectral resolution | Value + Hz/kHz/MHz | Label explicitly excludes channel spacing |
| Advanced channel spacing | Optional value + unit | Independent of both spectral resolution and RMS bandwidth |
| Footer | Add window | No copying sensitivity implicitly |

### Repeatable sensitivity card

| Control | Conditional display |
| --- | --- |
| Purpose | Continuum or line for this entry |
| Applies to | Select Window 1/Window 2 labels; IDs maintained internally; one for line/native/smoothed scope |
| Requested RMS | Value + Jy/beam or mJy/beam |
| RMS basis | Aggregate / Native channel / Smoothed / Not sure |
| Reference frequency | Value + frequency unit |
| Bandwidth used for this RMS | Independent value/unit and meaning; optional source label such as OT RepWindowEffectiveChannelWidth |
| Smoothed spectral resolution | Separate optional control when smoothed; never fills the RMS bandwidth |
| Velocity width | If supplied: km/s, convention/reference context; comparison pending approved conversion |

Native basis identifies the window; it does not copy its resolution into the RMS
bandwidth. Advanced optional details include smoothing/averaging, Stokes,
polarization, beam and weighting evidence. Unknown basis or effective width
does not force a false selection. Kelvin is visibly unsupported, with an
explanation that additional beam/frequency context and a method are needed.

## Panel 3 — Candidate search options

Visually separate from proposed-observation controls.

| Control | Meaning |
| --- | --- |
| Search radius | Summary/edit of the first-screen control; one SearchOptions value, not a second independent field |
| Sources | Archive / controlled Queue snapshot |
| Optional candidate constraints | Operator + value + unit, for example angular resolution `< 0.5 arcsec` |
| Result limit | Retrieval cap; reaching it requires explicit completeness reporting |

Do not prefill observation parameters from example search constraints. Queue
selection shows snapshot date (with its date meaning) and status; unknown dates
remain labelled unknown. Acquisition ID/checksum and parse-run ID appear in
collapsed source details, not required user controls. The
user must not re-enter missing Archive or Queue scientific evidence.

## Panel 4 — Review and action

| Summary row | Example wording |
| --- | --- |
| Input validity | Inputs valid / Correct the indicated field |
| Search readiness | Ready for bounded candidate search |
| Assessment readiness | Line sensitivity comparison unavailable: Window 1 lacks the bandwidth used for its RMS |
| Candidate-side evidence | Will be checked per returned candidate; request validity is not a duplicate verdict |
| Search scope | Display radius, sources and restrictive predicates explicitly |
| Action | Search candidates; enabled only when search readiness permits |

Example partial draft: valid ICRS target and radius, line intent, W1 with unknown
mode and sensitivity basis. Show search enabled plus separate missing reasons
for Window 1; do not label the request ready for a complete duplication assessment.

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
