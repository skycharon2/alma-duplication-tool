# Single-execution/SPW footprint diagnostic

The first footprint implementation represents a union of circular half-power disks
at verified listobs field centres. This coverage model was accepted for project use
on 2026-10-23 following Yuki Shi's confirmation with the project supervisor; see
[the recorded decision](research/mosaic/SCIENCE_GATES.md#coverage-model-decision--2026-10-23).
The current interface remains a geometry diagnostic, with no complete duplication
policy evaluation or combined sensitivity map.

## Scientific boundary

Cycle 13 Users' Policies Appendix A describes the Mosaic spatial condition in terms
of more than half of proposed pointings falling within the other observation's
half-power coverage. It is not an area-overlap fraction. Other duplication conditions
also apply. The project's SCIENCE_GATES.md still records unresolved coverage and
counting choices beyond the accepted circular beam-union model. Existing diagnostic
status strings do not encode the subsequent model acceptance; they must not be read
as a claim that the supervisor confirmation is still pending.

The primary-beam approximation uses full HPBW = coefficient × c / frequency / diameter.
For circular symmetry, the half-power radius is HPBW / 2. The ALMA handbook describes
an approximate 1.13 coefficient; it is exposed as a required diagnostic parameter,
not silently fixed as policy. Source references:

- [Cycle 13 Users' Policies, Appendix A](https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies).
- [Cycle 13 Technical Handbook](https://almascience.eso.org/documents-and-tools/cycle13/alma-technical-handbook).
- [ALMA primary-beam planning guidance](https://help.almascience.org/kb/articles/how-do-i-model-the-alma-primary-beam-and-how-can-i-use-that-model-to-obtain-the-sensitivity-pr), which recommends CASA simulation for Mosaic sensitivity profiles.

## Run

```bash
python -m alma_duplicate.cli.archive_mosaic_footprint \
  --package-audit-dir reports/mosaic-dev/ic1954-package-reuse-02 \
  --array-catalog tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json \
  --asdm uid://A002/Xc63024/X4c8 \
  --spw 16 \
  --hpbw-coefficient 1.13 \
  --frequency-choice reported-spw-centre \
  --assume-uniform-field-antennas \
  --output reports/mosaic-dev/ic1954-footprint-spw16-02.json
```

The output must be new. Inputs are revalidated through the readiness builder, including
AQ catalog and original listobs evidence. The selected SPW must be explicitly labelled
FULL_RES, TOPO and referenced by science scans. Only a bound single-diameter 7m or
12m array is supported. Missing evidence, mixed arrays, unsupported frequency frames,
invalid coefficients or inconsistent frequencies fail rather than produce empty coverage.
Fields not linked to the selected SPW are explicitly excluded.

The frequency choice uses the rounded reported SPW centre, not an average over
selected windows or the approximate channel edges. The required antenna flag declares
an assumption: the execution's uniform dish population applies to the selected fields.
The listobs antenna table alone does not prove active per-field baseline membership.
Changing SPW, ASDM or coefficient requires a distinct diagnostic run; no cross-execution
or cross-frequency union is constructed automatically.

The output stores individual spherical disk centres and radii, full HPBW, frequency,
diameter, selected scan IDs, source hashes, array evidence and model assumptions.
The circles define union membership without polygon tessellation. No union area,
sensitivity weighting, representative pointing or final duplication verdict is computed.

## Optional probe points

Supply `--probes FILE --boundary-epsilon-arcsec VALUE` together. FILE contains a JSON
list of objects with unique string id, frame ICRS, ra_deg and dec_deg. All angular
coordinates must be finite and within valid ranges. At most five million circle/probe
comparisons are accepted. The report preserves each probe and lists contributing fields.

INSIDE means a point is farther inside at least one circle than the epsilon band.
BOUNDARY means no circle places it clearly inside, but at least one edge is within
that band. OUTSIDE means neither condition holds. A boundary on one circle does not
override being inside another. The underlying disks are closed, but boundary cases
remain explicit for later scientific decisions. Epsilon is a numerical classification
band, not coordinate uncertainty. No proposed-pointing denominator or >50% decision
is evaluated. CLI exit 0 means diagnostic generation succeeded; invalid inputs exit 2.

## Validation

IC1954 ASDM X4c8, SPW 16, coefficient 1.13 and the reported centre yield 22 disks
with half-power radius approximately 21.728172 arcsec. This is a worked diagnostic
under the stated assumptions, not an independently measured coverage boundary.
Tests cover full width versus radius, inverse frequency/diameter scaling, exact
boundary reporting, RA wraparound, union membership, unrelated SPWs, and invalid or
unready input rejection. Existing readiness/evidence regressions remain applicable.
