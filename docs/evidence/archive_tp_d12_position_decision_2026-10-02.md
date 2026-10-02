# Archive TP D=12 position decision

Date: 2026-10-02. Scope: source-bound Archive fixed-target, single-point
POS-SINGLE evaluation when official AQ evidence identifies a Total Power
component.

## Confirmed project decision

The project owner reports supervisor confirmation that a Total Power observation
uses **D = 12 m** for the candidate primary-beam/location calculation.

This decision is intentionally narrow:

- bound TP evidence contributes the physical beam diameter D=12 m;
- POS-SINGLE uses the existing candidate frequency, FWHM formula, half-FWHM
  radius and inclusive spherical separation comparison;
- a TP position result is therefore SATISFIED or NOT_SATISFIED when the existing
  fixed-single-field position evidence is otherwise complete;
- TP keeps its TOTAL_POWER identity;
- this does **not** make TP equivalent to the main interferometric 12-m Array for
  CONTINUUM, LINE, angular-resolution, RMS or spectral applicability.

The official Cycle 13 Proposer's Guide independently documents the physical
hardware fact that the TP Array uses 12-m antennas for single-dish observations:
https://almascience.eso.org/proposing/proposing/proposers-guide

The use of that 12-m aperture specifically in this project's duplication
POS-SINGLE calculation is the supervisor-confirmed project decision recorded
here, not an observatory policy claim.

## Runtime boundary

The source-bound AQ adapter remains responsible for identifying TOTAL_POWER and
binding it to the exact Archive candidate. The position rule must not infer TP
from raw mixed antenna names.

For a bound TP path:

```text
diameter_m = 12
candidate_radius = primary_beam_fwhm(candidate_frequency, 12 m) / 2
position outcome = separation <= candidate_radius
```

`ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED` remains attached as a
branch-scope reason so current Archive CONTINUUM and LINE aggregation stays
INDETERMINATE for TP. It is no longer a position-evidence issue and therefore
must not erase an otherwise computable POS-SINGLE result.

Method version for source-bound Archive position becomes
`archive_pos_single_3`. Historical reports using `archive_pos_single_2` retain
their original meaning.

## Acceptance

Regression coverage must demonstrate both sides of the geometric boundary with
TP evidence, verify D=12 and the calculated radius, require an evaluated
POS-SINGLE outcome with no position issue, and simultaneously verify that
CONTINUUM/LINE branches remain INDETERMINATE. No live AQ integration, TP
continuum/line method, Mosaic or moving-target behavior is added by this
increment.
