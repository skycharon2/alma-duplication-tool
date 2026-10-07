# Proposed nominal-to-usable bandwidth: project adoption

Decision date: 2026-10-07.

The project owner explicitly authorized formal adoption of the existing proposed
nominal-to-usable method, reporting that the usable-bandwidth interpretation in
the handwritten design had been confirmed with their supervisor. This records
the owner's confirmation; it is not a new independently obtained supervisor
statement or a claim of official ALMA software certification.

## Adopted method

`continuum_setup_4` is APPROVED for proposed CONT-SETUP qualification with
`nominal_conversion="PORTAL_SCRIPT_V1"`. It reuses
`queue_normalization.map_nominal_to_usable_mhz()` and records mapping version
`cycle13-portal-plotobs-v1.3.1-v2`. No new conversion table or general 15/16
approximation is introduced.

The existing mapping includes nominal MHz values 62.5→58.6, 125→117.2,
250→234.4, 500→468.8, 1000→937.5, 1875→1875 and 2000→1875. Its existing
recognition tolerances, recognition of already-usable table values, and
1875 < nominal < 2000 MHz → 1875 MHz behavior are retained. These are
versioned project conventions, not an inference of correlator hardware.

Qualification uses at least two distinct proposed windows whose usable widths
are strictly greater than 1.8 GHz. NOMINAL widths at or below 1.8 GHz cannot
qualify because usable width cannot exceed nominal width, even if their exact
usable value is unavailable. Unrecognized larger widths and UNKNOWN width
semantics remain unresolved. Two qualified windows suffice for a positive
setup result; an exhaustive negative still requires a complete resolved list.

This is proposed setup qualification only. It does not change candidate
bandwidths, LINE coverage, noise bandwidth, RMS formulas, frame handling,
mode inference or unsupported target/geometry scope. The original request
retains its NOMINAL values; derived widths do not replace user inputs.

## Integration and provenance

The shared assessment entry selects this mapping by default only when CONTINUUM
is requested, NOMINAL window evidence is present and no explicit setup
declaration owns qualification. Browser and CLI use the same entry. An explicit
`AssessmentOptions(nominal_conversion=None)` or CLI `--nominal-conversion NONE`
retains the unconverted path. Unsupported option names fail before source access.

Reports record the effective selection, method/approval/decision reference,
mapping version and per-window input, derived usable width and qualification.
The browser renders that stored evidence. A missing conversion never receives a
synthetic value or a positive qualification merely because the method is approved.

Direct USABLE qualification remains `continuum_setup_3`; the researcher
declaration remains `continuum_setup_declaration_1`. Historical `_2` reports
with provisional conversion retain their original identities and contents.
This decision supersedes the earlier provisional status for new evaluations
within the adopted mapping, without rewriting dated evidence or acceptance files.

## Verification

- Unit tests: recognized widths, 1.8 GHz boundary, unknown widths/semantics,
  incomplete lists, recorded operands and formal eligibility.
- Integration: approved conversion can support a positive continuum branch;
  invalid configuration is rejected before source access.
- Browser/CLI parity: two-source requests in GHz and MHz, positive, negative
  and unresolved cases; unchanged raw NOMINAL request exports; readable
  per-window conversion evidence.
