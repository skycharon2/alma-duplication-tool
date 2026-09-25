# Independent reference for formal dual-source LINE acceptance

Reference version 1; prepared 2026-09-25.

This record defines the expected engineering behavior for the
`dual-source-line` acceptance case. It does not create a reviewed real-proposal
label and does not introduce or approve a new scientific method.

## Request identity

The request is the existing synthetic Guide B LINE request with exactly one
search change: source selection is `ARCHIVE` plus `QUEUE` instead of Archive
alone. The fixed target, position, one requested LINE window, requested angular
resolution, requested RMS, smoothing resolution and source redshift are
unchanged.

The proposed line has rest frequency 230.538 GHz and redshift 0.024, so the
prepared sky frequency is

    230.538 / (1 + 0.024) = 225.134765625 GHz.

The planned spectral width corresponding to 20 km/s is

    225.134765625 GHz * 1000 MHz/GHz * 20 / 299792.458
    = 15.01937487867023 MHz.

The proposed angular resolution is 0.30 arcsec and the requested line RMS is
0.30 mJy/beam.

Archive and Queue evidence are evaluated independently against that same request.
No value from one source may satisfy a condition for the other source.

## Archive expectation

The Archive input is the unchanged synthetic Guide B replay already documented
in `acceptance_reference_values.md`.

Its two retained contexts therefore remain, in raw-row order:

1. `CRITERIA_MET`
2. `CRITERIA_NOT_MET`

Adding Queue selection does not alter those Archive rows, pair identities,
source-specific criteria or LINE branch outcomes.

## Queue fixture identity

The Queue fixture contains exactly two synthetic rows. Each row contains exactly
one regular SPW and therefore exactly one Queue LINE pair.

Both rows use the proposed position exactly, so POS-SINGLE has zero separation.
Both rows use requested angular resolution 0.45 arcsec, giving

    0.45 / 0.30 = 1.5,

inside the inclusive factor-two ANGULAR limit.

Both rows are Cycle 11 (`2024.*` project code), DOUBLE polarization,
interferometric (`Use TP? = False`) observations with a 1875 MHz SPW and
7.8125 MHz spectral resolution. Under the versioned Queue mode contract this is
an exact supported FDM reference configuration, so LINE-FDM is satisfied.

The only Queue SPW is centred at 225.1 GHz. Its 1875 MHz usable interval is

    225.1 +/- 0.9375 GHz = [224.1625, 226.0375] GHz.

The prepared 225.134765625 GHz line centre is inside that same SPW, so
LINE-COVERAGE is satisfied.

The Queue spectral resolution is 7.8125 MHz, which is finer than the planned
15.01937487867023 MHz width, so LINE-RESOLUTION-COMPATIBILITY is satisfied.

## Queue row A: positive whole pair

Row A has `Req.Sensitivity = 0.3 mJy` at `Ref.Freq.Width = 15 MHz`.
The Queue LINE RMS normalization gives

    sigma_spectral
      = 0.3 * sqrt(15 / 15.01937487867023)
      = 0.2998064387044582 mJy.

The angular correction to the proposed 0.30 arcsec resolution from the Queue
0.45 arcsec requested resolution gives

    sigma_comparable
      = 0.2998064387044582 * (0.30 / 0.45)^2
      = 0.1332473060908703 mJy.

The inclusive factor-two requested limit is

    2 * 0.30 = 0.60 mJy.

Therefore LINE-RMS is satisfied. All six conditions in the single physical pair
are satisfied, so the Queue pair is `TRUE` / `CRITERIA_MET` and its context LINE
branch is `CRITERIA_MET`.

## Queue row B: RMS-only negative whole pair

Row B keeps the same position, angular value, mode evidence, SPW centre,
bandwidth and spectral resolution. Its only changed scientific scalar is
`Req.Sensitivity = 2.0 mJy`.

The same normalization gives

    sigma_spectral
      = 2.0 * sqrt(15 / 15.01937487867023)
      = 1.9987095913630544 mJy,

and

    sigma_comparable
      = 1.9987095913630544 * (0.30 / 0.45)^2
      = 0.8883153739391353 mJy.

That exceeds the 0.60 mJy limit. LINE-RMS is therefore not satisfied while the
other five same-pair conditions remain satisfied. The pair is `FALSE` /
`CRITERIA_NOT_MET` and the context LINE branch is `CRITERIA_NOT_MET`.

No condition is borrowed across Queue rows or SPWs. Cross-SPW adversarial
borrowing is covered by a separate later acceptance increment; this fixture is
deliberately one-SPW-per-row so positive and negative whole-pair evidence is
directly reviewable.

## Versioned Queue LINE identities

The expected formal Queue method identities are:

- `queue_pos_single_5`
- `queue_angular_factor_7`
- `queue_line_fdm_1`
- `queue_line_coverage_1`
- `queue_line_resolution_compatibility_1`
- `queue_line_rms_portal_1`
- pair conjunction `queue_line_pair_and_1`
- context disjunction `queue_line_context_or_1`

## Combined execution expectation

Both selected sources must complete independently:

- Archive status: `COMPLETED`;
- Queue status: `COMPLETED`;
- Archive retained contexts: 2;
- Queue retained contexts: 2;
- total retained contexts: 4;
- evaluated contexts: 4;
- shown candidates: 1;
- display truncation: true.

The report remains `assessment: NOT_AGGREGATED`; this acceptance case does not
create a search-wide duplication verdict.

The acceptance case explicitly requests Queue LINE evaluation. Effective
evaluation provenance must therefore record:

- `queue_common: true`;
- `queue_continuum: false`;
- `queue_line: true`.

## Review status

This is synthetic numerical acceptance evidence. Its review status remains
`AWAITING_INDEPENDENT_REVIEW`. It is not a genuine proposal case and does not
change the count of independently reviewed real-proposal cases.
