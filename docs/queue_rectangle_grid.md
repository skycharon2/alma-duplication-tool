# Queue Rectangle geometry

Offline geometry only; no UI, source loading, Custom scientific rules, or duplication
verdicts are changed. Each Rectangle source row remains independent, including
repeated rows and distinct spectral configurations.

Run with the project Python environment:

```sh
python -m alma_duplicate.cli.queue_rectangle_grid \
  --queue-csv /path/to/duplication-check-csv.csv \
  --output /tmp/rectangle-geometry.json
```

The output must not already exist. It contains the snapshot hash, row identities,
input geometry, array inference, frequency policy evidence and full point lists.

`QUEUE_RECTANGLE_TRIANGULAR_GRID_1` uses the A–C empirical centred triangular grid,
row parity and PA rotation. CSV spacing is assumed to reference 12-m, and scales
by 12/D for the same beam fraction. This assumption applies even to inferred
7-m-only rows and is explicitly recorded, not established as a CSV export fact.
No Nyquist or frequency-derived spacing replaces the supplied CSV spacing.

Only explicit ICRS is supported. Centre offsets and rotated grid offsets use
successive spherical directional offsets. D3 validates this convention against OT for the specific nonzero-declination
and offset configuration below; it does not establish general OT parity. Galactic and blank frames remain
unresolved. Positive longitude is east; no screen orientation enters computation.

The small reference fixture retains three actual exported coordinates per array
case and source-file hashes: A=90x90 PA0, B=90x90 PA30, C=100x70 PA0,
RA150 Dec0, 107 GHz Nyquist. Counts are 14/4, 14/4 and 10/5. Full experimental
archives are not required at runtime or committed. Local offset parity tolerance
is 1e-8 arcsec; spherical projected coordinate tolerance is 1e-5 arcsec.
General sizes, nondefault spacing and coordinate configurations outside the
controlled fixtures remain provisional, not universal OT parity.

`GEOMETRY_RECONSTRUCTED` and `model_grid_complete` only mean all points prescribed
by this model were generated. `grid_model_status=PROVISIONAL` and
`scientific_candidate_complete=false` remain separate. Failure returns no points;
there is no truncation. Per-array output is capped at 10000 points before coordinate
allocation. Boundary inclusion follows floating-point floor/ceil without expanding
rectangle edges by a scientific tolerance.

Next integration can adapt these results to QueueMosaicCoverage, with an explicit
policy for completeness. Geometry success alone must not authorize a scientific
negative. Rectangle combined-image RMS remains outside this module.

## Position-only adapter

`queue_rectangle_backend.assess_queue_rectangle_csv(parsed, proposed, *,
candidate_id=None, boundary_epsilon_arcsec=0.001)` binds each source row's grid
and inferred diameter to the existing `QueueMosaicCoverage` and position rule.
It does not modify Custom logic, browser routes or source acquisition.

`association_confirmed=True` accepts only the program's provisional row/array
model binding. `complete=True` means the model grid was generated in full.
Every result retains `scientific_candidate_completeness=NOT_ESTABLISHED` and
`outcome_scope=CONDITIONAL_ON_RECONSTRUCTED_MODEL`. Model negatives are not
scientific exclusions or global absence of duplication. Arrays and candidates
are never combined. Missing geometry or usable beam frequency leaves a branch
UNKNOWN. The total comparison budget is one million pairs; exceeding it raises
an error before position evaluation, never a partial successful report.

The local 140-row snapshot audit found 138 reconstructed rows / 238 generated
array branches, 13414 total points, and 3–158 points per successful branch.
The two Galactic rows remain unresolved in both array branches. These numbers
characterize this snapshot only. D3 subsequently validates one nonzero-declination configuration.

## Scientific assessment

`assess_queue_rectangle_science` connects the position model to existing angular,
continuum and same-SPW LINE numerical criteria. Separate common-method contracts
admit Rectangle without presenting it as Custom. Each source row supplies its own
spectral and request evidence; complete per-array branches are ANDed before OR.
No cross-row coverage union or cross-array operand borrowing occurs.

Requested sensitivity is compared using the existing numerical policy. Rectangle
combined-image and proposed sensitivity bases are retained as metadata, without
an overlap-gain estimator, pointing-count scaling, or automatic conversion to
per-pointing RMS. This is an explicit project interpretation of the general
requested-sensitivity criteria, not a claim that different image noise measures
are physically identical. Missing numerical evidence still yields UNKNOWN.
Custom's existing per-pointing contract remains unchanged.

Policy reference: ALMA Users' Policies, Cycle 13, Appendix A (printed page 22):
https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies

All candidate/intent conclusions remain conditional on the provisional geometry
and inferred arrays. No search-wide absence claim or browser integration is added.
The one-million position-pair budget is unchanged; large requests are explicitly
rejected rather than silently truncated. Spatial prefiltering/compact distance
storage remain future work; D3 supplies a controlled nonzero-declination reference.

## D3 production parity

The unchanged production generator was compared with original OT Absolute/Degrees
exports for ICRS (150, -30) degrees, centre offset (+20, -10) arcsec,
100x70 arcsec, PA +30 degrees, 107 GHz default Nyquist spacing. The fixture stores
only the 15 observed coordinates, input parameters and source SHA-256 hashes,
checked against the supplied D2/D3 audit. Predicted coordinates are not used as
the reference. Matching is one-to-one on spherical separation, independent of
file order, with tolerance 0.001 arcsec.

| Array | Matched | Maximum residual (arcsec) | Median residual (arcsec) |
| --- | --- | --- | --- |
| 12-m | 10/10 | 1.850736e-7 | 5.409392e-8 |
| 7-m | 5/5 | 4.298730e-7 | 8.346372e-8 |

This validates the full production transformation for D3, without changing its
method version or global PROVISIONAL status. It does not establish CSV spacing
semantics for 7-m-only rows, nondefault spacing, Galactic coordinates or all sky
positions. D2 audit results were supplied but were not independently rerun here.

## Standard assessment routing and spacing diagnostic

The application entry point accepts an explicit `queue_rectangle=proposed_points`
argument to `assess_observation(request, search_options, sources=..., ...)`.
It is mutually exclusive with `queue_custom` and Archive `mosaic`. Supply a fixed
Mosaic request and QUEUE-only search options. The unchanged lazy `queue_loader`
provides a supplied or managed snapshot; the adapter itself performs no acquisition.
Invalid requests/configuration do not load sources. Missing, failed or incomplete
sources return SOURCES_UNAVAILABLE rather than a successful empty search.
Reports use `queue_rectangle_assessment_1` / `QUEUE_RECTANGLE_MOSAIC`, retain the
science schema, source diagnostics, model status and per-row results. No browser
or CLI selection is added in this increment. Single-point radius/result limits
are not applied; unsupported predicates and single-point flags are rejected.

Each row now includes a nonblocking spacing diagnostic comparing original CSV
spacing with 12-m Nyquist at the original Ref.Frequency (no fallback or Doppler
rewrite). Relative tolerance is 1e-10. Nondefault spacing is retained and marked
NONDEFAULT_SPACING_REFERENCE_REVIEW; missing/invalid inputs yield UNAVAILABLE.
Neither status changes reconstruction or scientific outcomes.

Independent audit of snapshot
`8657108b59295c62d3f1f6635bf3571404f5d43bc5800c4a2e7ea3ba51a111b5`
found all 140 Rectangle rows consistent with the 12-m scale (maximum relative
error 2.4536e-14): D12_ONLY=3, D7_ONLY=35, MIX_7M_12M=102. These classifications
are inferred, not independently established array membership. This numerical
agreement is snapshot evidence, not a permanent official CSV export contract.

## Model acceptance and validation scope (2026-11-05)

`QUEUE_RECTANGLE_TRIANGULAR_GRID_1` is adopted as a **PROJECT_ACCEPTED**
ICRS Rectangle reconstruction algorithm. This is a project engineering decision,
**not** a formal ALMA endorsement or a claim that each Queue row was directly
reproduced in the OT. The independent OT tests A–C and D3 cover 7-m and 12-m
Nyquist reference arrangements, PA rotation, nonzero declination, and two-axis
centre offsets. One-to-one spherical coordinate parity in D3 used a 0.001 arcsec
tolerance. The original tests and their SHA-256 provenance remain in the local
OT audit material; only the minimal numerical fixture is required in Git.

The Queue snapshot's 140 Rectangle rows have `Mos. Spacing` values consistent
with a 12-m Nyquist reference. This is an accepted versioned CSV **convention**,
not a permanent official ALMA CSV export guarantee. Each reconstructed grid
records a separate `ot_validation_scope`: default-spacing ICRS candidates are
in the validated **reference class**, but this does not assert direct per-row
OT parity. Galactic, missing geometry and unusable array/beam evidence remain
unresolved. Nondefault spacing is explicitly outside the controlled OT cases.

`model_status` / `grid_model_status` describe algorithm acceptance only.
`intent_completeness` describes a fully met evaluated intent (for example
CONTINUUM with all required conditions true) separately. `search_completeness`
remains `NOT_ESTABLISHED` where source inventory or unsupported geometry limits
search-wide claims. Historical stored `PROVISIONAL` reports are never rewritten.
