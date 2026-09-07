# Proposed observation input API v1

Implementation baseline: `59c6f0d`; implements the request-side subset of
[design 0.3](duplication_rule_inputs.md). No candidate search, policy verdict,
candidate-side readiness or changes to ingestion adapters are included.

## Entry point and result

```python
from alma_duplicate.request_validation import validate_proposed_observation

report = validate_proposed_observation(request_input, search_options_input)
```

Data structures live in `domain/proposed_observation.py`; a single entry module
organizes shape parsing, normalization, reference validation and the report.
Existing Archive/Queue models, special missing-value handling, strict pipeline
gates and normalizers remain unchanged. No additional runtime dependency is added.

Any ERROR produces `request=None`, `search_options=None`, and BLOCKED. The report
retains detached raw input and all diagnostics. A valid partial request is
returned even if coordinates or search radius are missing; search stays BLOCKED
until its spatial prerequisites exist. READY means fixed single-pointing ICRS
position, explicit valid radius and at least one selected source. It does not
mean every predicate is executable, a query was performed or a rule is satisfied.
MOVING/MOSAIC return UNSUPPORTED without degrading into fixed single pointing;
SUN returns NOT_APPLICABLE when no input errors exist.

Issues have category ERROR/MISSING/CAPABILITY, code, path, message, optional
rule ID and side PROPOSED/METHOD. No CANDIDATE-side claims are emitted. A rest
frequency is valid preserved evidence with a conversion limitation; an unsupported
RMS unit such as K is an input error. Method notices are restricted to supplied
rest/velocity/smoothing/conversion inputs and requested continuum applicability.
There are no EVALUABLE or duplicate flags in this API.

## Wire format

See [complete runnable example](../examples/proposed_observation.json).
Use plain string-keyed mappings, lists/tuples and Python str/int/float/bool/None.
The validator snapshots these recursively into read-only mappings/tuples. Cycles,
non-string keys and arbitrary Python objects are errors; unsupported objects
are represented by a diagnostic marker, not retained by reference. This API
does not accept NumPy or Astropy objects as wire values. Explicit NaN/inf in a
quantity is invalid, not a missing Archive scalar. Unknown fields are errors
so a misspelt input is not silently ignored.

Required structural fields: `target_kind`, `geometry`, `setup_id`. Setup/window/
sensitivity IDs are client-generated stable internal labels, not project IDs;
the future form generates them rather than asking the user for archive identity.
Optional `setup_complete` is Boolean or absent and refers only to enumeration.
Empty windows may coexist with independent frequency, angular resolution and RMS.

| Object | Accepted fields |
| --- | --- |
| Request | target_kind, geometry, target_name, position, setup_id, setup_complete, intents, angular_resolution, representative_frequency, representative_window_id, spectral_windows, sensitivities, array_context |
| Position | ra, dec, ra_format (DEG/HMS), dec_format (DEG/DMS), frame (explicit ICRS) |
| Quantity | value, unit; supported units below |
| Frequency | value, unit, kind (SKY/REST/UNKNOWN), frame, origin |
| Origin | kind (USER_DECLARED/OT_COPIED/IMPORTED/UNKNOWN), raw_label, source, version, target, epoch |
| Window | window_id, representation, center, bandwidth, bandwidth_kind, lower, upper, correlator_mode, mode_origin, channel_spacing, spectral_resolution |
| Sensitivity | sensitivity_id, purpose, scope, setup_id, window_ids, rms, basis, aggregate_path, reference_frequency, bandwidth_used_for_sensitivity, bandwidth_meaning, bandwidth_origin, target_aggregate_bandwidth, smoothing_resolution, context |
| Search options | radius, sources (ARCHIVE/QUEUE), result_limit, predicates |
| Predicate | field, operator, quantity, basis, context |

Coordinates accept decimal numbers/numeric text, or colon-separated HMS/DMS.
RA must be [0,360), Dec [-90,90], with minutes/seconds below 60 and no extra
components at a pole. RA 24:00:00 is rejected rather than silently wrapped.
Negative-zero DMS sign is preserved in conversion. ICRS is explicitly selected;
other coordinate frames are not converted by this first implementation.

Frequency frames: TOPOCENTRIC/BARYCENTRIC/LSRK/LSRD/HELIOCENTRIC/UNKNOWN.
These enumerate preserved declarations, not supported frame transformations.
OT_COPIED never implies a frame. UNKNOWN defaults describe absent evidence only.

| Quantity | Input units | Canonical |
| --- | --- | --- |
| Frequency/window width/bounds | Hz, kHz, MHz, GHz | GHz |
| Resolution/spacing/noise width | Hz, kHz, MHz, GHz | MHz |
| Angular resolution | mas, arcsec | arcsec |
| Search radius | arcsec, arcmin, deg | deg; at most 180 |
| RMS | Jy/beam, mJy/beam | mJy/beam |
| Optional noise/smoothing velocity width | m/s, km/s | km/s; no frequency or noise conversion |

All supplied quantities are finite and positive before and after conversion.
Units are explicit and case-sensitive. Missing quantities are omitted or None;
an object with an absent/blank numeric value is malformed, not a missing object.
No channel-spacing/resolution/noise-bandwidth substitution is performed.

## Roles, partial coverage and association

CENTER_BANDWIDTH/BOUNDS/PARTIAL preserve representation intent; absent components
remain partial. Width and bounds cannot both describe the interval. A center may
accompany bounds as an independent role. BOUNDS computes midpoint/span only,
never a SPW center. Mismatched bound references are retained with a method-side
notice and no interval; comparable reversed or collapsed bounds are errors.
NOMINAL/UNKNOWN center-width arithmetic retains that kind without scientific
approval. USABLE scalar width alone does not locate coverage, so no interval is
inferred. Bounds may record declared usable coverage but remain unvalidated.
Representative-window membership is checked only for comparable, nominal
intervals. Other interval semantics retain unresolved membership evidence.

No continuum qualifying count or line-match conclusion is computed here.
Enumeration completeness does not block search. Incomplete line lists explicitly
cannot support exhaustive negatives. Width interpretation remains a METHOD
limitation; this is not a demand that the user populate more fields.

Sensitivity basis is AGGREGATE/NATIVE_CHANNEL/SMOOTHED/UNKNOWN. Scope is
SETUP/WINDOW/UNRESOLVED. WINDOW requires one existing ID; SETUP requires the actual
setup ID and is used for continuum, with optional contributor IDs. Missing scope
is preserved as UNRESOLVED; dangling IDs or incompatible scope/basis are errors.
AGGREGATE requires DIRECT_DECLARATION or CONVERT_FROM_REFERENCE to prevent
misinterpreting a reference RMS as an already-converted value. DIRECT_DECLARATION
does not require noise width or contributor list. Conversion retains the reference
RMS and reports absent bandwidths/method; it produces no converted RMS.

Sensitivity context accepts stokes_basis, polarization_basis, beam_context,
weighting_context, smoothing, spectral_averaging, velocity_convention and method.
Array context accepts description/origin. These are opaque, immutable provenance,
not validated computational evidence: any later beam/noise calculation must
validate them explicitly before use. An arbitrary method label is not approval.

Predicate fields: frequency/angular_resolution/spectral_resolution/sensitivity;
operators: <, <=, =, >=, >. One-sided predicates remain one-sided and never fill
requested observing parameters. Sensitivity basis uses the four RMS basis labels;
UNKNOWN is retained with a notice that the filter cannot be silently applied.
Predicate context (frequency_reference, reference_frequency,
bandwidth_used_for_sensitivity, origin) is retained as opaque provenance. No
predicate is translated to ArchiveQuerySpec or executed by this PR. Future query
planning must validate context and report which filters were actually applied.

## Offline demonstration and tests

```bash
python examples/validate_proposed_observation.py
python -m pytest -q tests/unit/test_proposed_observation.py tests/integration/test_request_validation.py
```

The demo prints a report summary, not full historical object serialization. A
valid partial example exits 0 even with missing evidence; invalid input exits 1.
The unit tests cover coordinates, equivalent units, independent widths/roles,
mutation isolation, bad values, intervals, references, partial RMS, unsupported
units versus missing methods, modes and one-sided predicates. Integration tests
exercise the wire example, raw-input revalidation and invalid-output suppression.
CASE1/CASE2 retrieval and coherent candidate pairing belong to subsequent work.

# Validation follow-up (version 3)

The request schema and conversion version remain unchanged. Validation reports
now carry `validation_version = "3"`:

- Independently supplied SPW centers must lie within their nominal bounds when
  all three frequency references are explicit and equal. Endpoints are allowed;
  the center need not equal the midpoint. Usable coverage does not impose this
  constraint. Unknown reference information produces `MISSING_EVIDENCE` on the
  `PROPOSED` side. Differing known kinds or frames produce a `METHOD` capability
  diagnostic (`INCOMPATIBLE_REFERENCE`): conversion is needed before direct
  comparison, not necessarily impossible. These checks are independent: unknown
  information does not hide differences already established by known values.
  Both diagnostics can coexist and neither blocks spatial search. Version 3
  replaces version 2's combined diagnostic; no frequency conversion is assumed.
- LINE requests report missing RMS for each listed window without a WINDOW-scoped
  LINE sensitivity containing an RMS value. These are request-side MISSING
  notices and do not block spatial search or imply an exhaustive negative result.
  An associated RMS still needs its own basis/context checks; association alone
  does not establish comparability. RMS values are never copied between windows.
- Numeric parsing rejects nonzero values that underflow to zero. Decimal degree
  coordinates are also range-checked before float rounding can hide a violation.
  Exact signed zero remains valid. Already rounded Python floats cannot reveal
  lost input precision; supply decimal strings to preserve that evidence.
