# Scientific workflow in the browser

This map follows `ノート 3.pdf` (17 pages; scientific content on pages 3–17).
It describes implementation, not a new scientific policy. The notes remain
unchanged. The [request contract](proposed_observation_api.md),
[Queue mapping](queue_csv_contract.md) and versioned rule decisions own semantics.

## Researcher inputs and candidate evidence

The browser sends the proposal to `validate_proposed_observation()` and
`assess_observation()`. `BrowserAssessment.assess()` enables formal Queue common,
continuum and line methods for the selected purposes. Researchers do not need
to re-enter candidate windows, reference noise widths or array flags.

| Notes | Input / source evidence | Backend | Browser |
| --- | --- | --- | --- |
| 3, 7–8 | RA/Dec, fixed target, single pointing | Validation, retrieval and candidate position rules | Position inputs; separation, candidate frequency, diameter and half-power radius |
| 4, 7 | REST/lab frequency and redshift, or SKY frequency | `proposed_line.prepare_line_window()` | Line frequency/reference/redshift inputs; per-pair input/preparation panel |
| 5, 7 | Planned spectral resolution in velocity or frequency units | Shared preparation and LINE resolution compatibility | Resolution input; entered units, prepared km/s and candidate resolution |
| 5–7 | Planned LINE RMS and angular resolution | Archive per-SPW 10 km/s RMS, spectral scaling and angular correction in `rules/line.py` | LINE RMS and angular inputs; source RMS, RMS at planned resolution and corrected RMS |
| 5–6 | Same target, execution and SPW; FDM on both sides | Exact Archive pairing and mode evidence | Member → target/execution → SPW comparisons; mode criterion |
| 9 | Representative SKY frequency, aggregate RMS, setup qualification | Confirmed continuum and setup/declaration rules | Continuum inputs; setup, frequency and aggregate RMS comparisons |
| 10–12 | Candidate nominal width, resolution, polarization and response | `queue_normalization.py`, `queue_mode_adapter.py` | Automatic preparation; recorded mode criterion. Unknown mode stays unresolved |
| 13 | Queue geometry, candidate array, position, angular resolution | `rules/queue_common.py` and candidate beam paths | Common criteria; separate 7 m / 12 m hypotheses where recorded |
| 14 | Queue nominal widths → usable intervals → union; reference RMS/width | `rules/queue_continuum.py` | Aggregate RMS, expandable nominal/usable SPW table, union bandwidth and reference RMS |
| 15 | Queue sky/rest flag, velocity convention and frame | `queue_normalization.py` | Per-line candidate frequency, Doppler factor, convention and frame |
| 15–17 | Queue SPW resolution, reference noise width, planned resolution/RMS | `rules/queue_line.py`, same proposed window and candidate row/SPW | Separate resolution, reference-width, spectral-scaling and angular-correction steps |

The form accepts frequency units GHz/MHz/kHz/Hz, spectral resolution km/s, m/s
or frequency units, angular resolution arcsec/mas, and RMS mJy/beam or Jy/beam.
These are passed to the existing validator. JavaScript does not convert science
quantities. Queue mJy values retain their source unit; the comparison uses the
documented requested-flux-density interpretation, not measured image RMS.

## Usable bandwidth: two paths

Page 14 describes **Queue candidate** processing. The browser already invokes
that backend path: supported nominal widths become usable widths, overlapping
intervals are counted once, and reference RMS is scaled over the complete
aggregate usable bandwidth. Missing evidence cannot produce a partial aggregate
RMS. The main comparison now shows stored `aggregate_rms_mjy`, rather than
the original `Req.Sensitivity` at its reference width.

**Proposed** nominal widths have a separate contract. The browser does not enable
the provisional `PORTAL_SCRIPT_V1` proposed conversion. Researchers can supply
known USABLE widths or explicitly confirm the supported continuum setup
declaration. Selecting CONTINUUM alone does not qualify a setup. Extending the
proposed conversion to a formal path requires a method/applicability decision;
candidate conversion does not establish that decision.

## Reading the calculations

Each criterion has **How this comparison was made**. Each LINE pair has
**Input and frequency preparation for this line**. These show stored operands,
units and missing values. They do not evaluate formulas, supply missing evidence,
borrow another window's RMS, change a verdict or fetch source data. Raw inputs
appear only when setup/window/sensitivity identities bind unambiguously.

Matching-only results and Member grouping remain unchanged. A matching SPW is
not a verdict on every observation in its Member. Historical reports with absent
evidence remain readable; original exports retain their bytes.

## Clarifications when transcribing the notes

- Page 11's handwritten 500 MHz mapping reads 466.8 MHz. The versioned
  [Queue table](queue_csv_contract.md) and implementation use **468.8 MHz**;
  this UI work retains that implementation.
- Page 15 interchanges velocity convention and frame labels. RADIO, OPTICAL
  and RELATIVISTIC are conventions; frame metadata is kept separately.
- Page 16's planned resolution example is approximately **0.3836 MHz** at
  230 GHz and 0.5 km/s; the isolated GHz label is not used as an input unit.
- Representative continuum frequency remains an explicit input, not an average
  invented from window centres.
- Channel spacing, spectral resolution and RMS reference noise bandwidth remain
  distinct. Neither reference noise width nor channel spacing fills a missing
  planned resolution. Selecting LINE does not itself establish FDM mode.

## Verification and remaining scope

`tests/ui/test_calculation_view.py` checks the notes' Archive example against an
actual backend report: 225.134765625 GHz sky frequency, approximately
0.2828427125 mJy/beam after spectral scaling and 0.4072935060 mJy/beam after
angular correction. Queue tests use four 1000 MHz nominal windows, each mapped
to 0.9375 GHz usable: the union is 3750 MHz for separated windows and 937.5 MHz
for coincident windows. Tests cover missing aggregates, ambiguous bindings,
HTML escaping and unchanged downloads. Deliberately inconsistent stored values
prove that presentation does not recalculate them.

Existing browser/CLI parity tests exercise both sources and equivalent input
units. Backend tests cover Queue LINE numerics and velocity conventions.

This work exposes supported methods. It does not enable mosaic/moving-target
evaluation, Kelvin conversion, arbitrary frame transformations, new correlator
inference or universal proposed nominal-to-usable conversion. Solar exemption
remains distinct from unsupported moving objects. These limits remain explicit
when incomplete inputs are accepted for search.
