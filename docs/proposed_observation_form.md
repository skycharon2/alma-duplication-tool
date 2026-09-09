# Proposed-observation form sketch

Form design version 0.3; the browser form is not implemented.
The [offline request API](proposed_observation_api.md) is implemented.
The form remains a design sketch; the API does not implement candidate results.
Goal: describe a proposed observation, retrieve Archive/Queue candidates and
explain applicable conditions using coherent evidence. Users do not supply
expected project IDs, Member UIDs or duplicate labels.
Accepted backend fields and request readiness: [request API](proposed_observation_api.md).
Future rule evidence and scientific decisions: [input contract](duplication_rule_inputs.md).
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

For the supported fixed single-pointing ICRS request, users can proceed with
position, search radius and at least one selected source; the form supplies
the required internal setup identity. Panels below progressively
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
| Representative frequency | Optional value/unit, Sky/rest/Not sure, optional window label | Independent from center and RMS reference frequency; detailed frame/origin folded away |

### Repeatable spectral-window card

| Row | Controls | Association behavior |
| --- | --- | --- |
| Header | Window 1, Window 2, ...; Remove | Stable IDs stay internal; relabelling preserves associations, deletion prompts only for affected RMS entries |
| Frequency representation | Center + bandwidth OR lower + upper; unknown values allowed | Complete values produce labelled derived intervals; incomplete values stay partial |
| Frequency/width | Values + GHz/MHz/Hz; Nominal / Usable / Not sure next to width | Meaning visible at entry; derived intervals labelled nominal/usable/unverified |
| Frequency reference | Sky / Rest / Not sure beside frequency | Detailed frame/origin collapsible; no guessed execution reference |
| Correlator mode | FDM / TDM / Unknown | No automatic mode derived from purpose or channel count |
| Spectral resolution | Value + Hz/kHz/MHz | Label explicitly excludes channel spacing |
| Advanced channel spacing | Optional value + unit | Independent of both spectral resolution and RMS bandwidth |
| Footer | Add window | No copying sensitivity implicitly |

### Repeatable sensitivity card

| Control | Conditional display |
| --- | --- |
| Purpose | Continuum or line for this entry |
| Applies to | Aggregate continuum RMS may select Entire proposed setup, with optional contributing windows; line entries select their window or retain unresolved scope |
| Requested RMS | Value + Jy/beam or mJy/beam |
| RMS basis | Aggregate continuum RMS / Native channel / Smoothed / Not sure |
| RMS reference frequency | Value + frequency unit and Sky/rest/Not sure; distinct from setup representative frequency |
| Aggregate continuum RMS help | RMS declared for the combined continuum measurement of this setup, not per-channel RMS |
| Aggregate path | Already have aggregate RMS / Convert a reference RMS; conversion controls expand only for the latter |
| Bandwidth used for this RMS | Independent value/unit and meaning; optional source label such as OT RepWindowEffectiveChannelWidth |
| Smoothed spectral resolution | Separate optional control when smoothed; never fills the RMS bandwidth |
| Velocity width | If supplied: km/s, convention/reference context; comparison pending approved conversion |

Native basis identifies the window; it does not copy its resolution into the RMS
bandwidth. Advanced optional details include smoothing/averaging, Stokes,
polarization, beam and weighting evidence. Unknown basis or effective width
does not force a false selection. Kelvin is visibly unsupported, with an
explanation that additional beam/frequency context and a method are needed.

For a directly supplied aggregate RMS, allow missing contribution lists and
bandwidth. Conversion from a reference RMS separately requests reference and
target bandwidths and a supported method; until available, retain the reference
RMS and explain why conversion cannot run. Do not imply aggregate setup eligibility
from this selection. A request with no window cards may still retain frequency,
resolution and RMS entries; it is not reduced to position-only information.

For bounds input, display Interval midpoint rather than SPW center. A usable
coverage midpoint cannot become a requested center without relationship evidence.

## Panel 3 — Candidate search options

Visually separate from proposed-observation controls.

| Control | Meaning |
| --- | --- |
| Search radius | Summary/edit of the first-screen control; one SearchOptions value, not a second independent field |
| Sources | Archive / controlled Queue snapshot |
| Optional candidate constraints | Operator + value + unit, for example angular resolution `< 0.5 arcsec` |
| Sensitivity constraint | Explicit basis (e.g. continuum aggregate or specified channel width), operator, value/unit and applicable context; no unlabeled universal sensitivity filter |
| Result limit | Retrieval cap; reaching it requires explicit completeness reporting |

Do not prefill observation parameters from example search constraints. Queue
selection shows snapshot date (with its date meaning) and status; unknown dates
remain labelled unknown. Acquisition ID/checksum and parse-run ID appear in
collapsed source details, not required user controls. The
user must not re-enter missing Archive or Queue scientific evidence.
An unresolved filter basis must be explained and left unapplied rather than
silently mapped to a convenient candidate scalar; report the effective filters.

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

## After search — Minimum result explanation

This is the future result contract, not an additional rule-engine implementation
in this document change. Search candidates remains the first-stage action;
later assessment fills condition outcomes without changing input semantics.

| Result area | Required explanation |
| --- | --- |
| Candidate | Source (Archive/Queue), project/Member where available and stable source record identifiers |
| Matched context | Actual source/execution/SPW pair or Queue association; alternatives stay separate |
| Conditions | Position, angular resolution, frequency and RMS: readiness plus separate satisfied/not satisfied/undetermined/not applicable outcome |
| Evidence details | Original value/unit, canonical value/unit, source reference, method/version and approval status |
| Gaps/estimates | Which input, candidate or method is unavailable; approximation assumptions visible and not automatically approved for threshold use |
| Search scope | Radius, effective filters, caps, separate Archive/Queue completion and incomplete-source explanations |

Example: frequency coverage is satisfied for Window 1, but RMS cannot be assessed
because the available scalar belongs to an unconfirmed representative window.
Display that reason; do not borrow Window 2's better RMS or label the candidate
non-duplicate. Likewise, an incomplete requested window list cannot support an
exhaustive negative line conclusion. The output is useful even when some
conditions remain undetermined.

## Review checklist

- Can a reader distinguish search radius, primary beam and angular resolution?
- Can two windows carry different sensitivity bases without accidental sharing?
- Does selecting continuum leave configuration qualification independent?
- Does missing candidate evidence stay on the candidate side?
- Are missing optional fields different from invalid supplied values?
- Do the IN-* cases in the contract cover each conditional control?

This sketch has not undergone user usability testing or scientific sign-off.
