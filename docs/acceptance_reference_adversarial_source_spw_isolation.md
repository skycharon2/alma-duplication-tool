# Independent reference for adversarial source/SPW isolation

Reference version 1; prepared 2026-09-25.

This record defines the expected engineering behavior for the
`adversarial-source-spw-isolation` acceptance case. It is synthetic numerical
evidence, not a reviewed real-proposal label and not a new scientific method.

## Adversarial purpose

This case deliberately distributes individually favorable LINE evidence across
different Archive contexts and different Queue SPWs. No single legal pair has
all required conditions satisfied.

The acceptance condition is therefore structural: every physical pair must be
evaluated and retained independently, and no favorable value may be borrowed
from another Archive row, Queue SPW, context or source to manufacture a passing
LINE branch.

The report remains `assessment: NOT_AGGREGATED`; there is no search-wide
duplication verdict to combine source-local evidence.

## Proposed request

The request uses the existing synthetic Guide B fixed single-point LINE request
with these deliberate changes:

- source selection is `ARCHIVE` plus `QUEUE`;
- the single proposed line center is an explicit SKY frequency of 240.0 GHz;
- the requested LINE RMS remains 0.30 mJy/beam;
- the planned smoothing resolution remains 20 km/s;
- the requested angular resolution remains 0.30 arcsec.

For the explicit 240 GHz SKY center, the planned 20 km/s spectral width is

    240 GHz * 1000 MHz/GHz * 20 / 299792.458
    = 16.0110765695113 MHz.

The inclusive RMS comparison limit remains

    2 * 0.30 = 0.60 mJy/beam.

## Archive adversarial split

The Archive replay is unchanged Guide B evidence and retains two independent raw
rows.

Archive row 0 is the original in-band-at-225-GHz FDM row. For the new 240 GHz
proposal:

- POS-SINGLE is satisfied;
- ANGULAR is satisfied;
- LINE-FDM is satisfied;
- LINE-COVERAGE is not satisfied because its raw usable interval is
  [224.8, 225.4] GHz;
- LINE-RESOLUTION-COMPATIBILITY is satisfied;
- LINE-RMS is satisfied.

That complete pair is therefore `FALSE` / `CRITERIA_NOT_MET`.

Archive row 1 has raw frequency support [239, 241] GHz, so it contains the
proposed 240 GHz center. However its confirmed operational mode is TDM and its
RMS is not favorable:

- POS-SINGLE is satisfied;
- ANGULAR is satisfied;
- LINE-FDM is not satisfied;
- LINE-COVERAGE is satisfied;
- LINE-RESOLUTION-COMPATIBILITY is satisfied;
- LINE-RMS is not satisfied.

That complete pair is also `FALSE` / `CRITERIA_NOT_MET`.

The Archive source therefore contains favorable FDM/RMS evidence in one context
and favorable coverage evidence in another context, but no Archive pair is true.

## Queue adversarial split

The Queue fixture contains exactly one physical row with exactly two occupied
regular SPWs. The row uses Cycle 11 (`2024.*`), DOUBLE polarization,
`Use TP? = False`, requested angular resolution 0.45 arcsec,
`Req.Sensitivity = 0.3 mJy` and `Ref.Freq.Width = 15 MHz`.

The common Queue conditions are favorable for both SPWs:

- the Queue position equals the proposal position, so POS-SINGLE is satisfied;
- 0.45 / 0.30 = 1.5, inside the inclusive factor-two ANGULAR limit.

### Queue SPW 1: coverage without usable mode/resolution

SPW 1 is centered at 240 GHz with 1875 MHz usable bandwidth. Its usable interval
is

    [239.0625, 240.9375] GHz,

so LINE-COVERAGE is satisfied.

Its 31.25 MHz spectral-resolution signature is the supported TDM configuration
for the row scope, so LINE-FDM is not satisfied. It is also coarser than the
planned 16.0110765695113 MHz width, so LINE-RESOLUTION-COMPATIBILITY is not
satisfied. LINE-RMS is therefore unresolved behind the failed resolution gate.

This pair is `FALSE` / `CRITERIA_NOT_MET`.

### Queue SPW 2: FDM/resolution/RMS without coverage

SPW 2 is centered at 228 GHz with 1875 MHz usable bandwidth. Its usable interval
is

    [227.0625, 228.9375] GHz,

which does not contain 240 GHz, so LINE-COVERAGE is not satisfied.

Its 0.9765625 MHz signature is an accepted FDM configuration in this row scope,
so LINE-FDM is satisfied. The spectral resolution is finer than the planned
16.0110765695113 MHz width, so LINE-RESOLUTION-COMPATIBILITY is satisfied.

With Queue reference RMS 0.3 mJy at 15 MHz, the spectral-width normalization is

    sigma_spectral
      = 0.3 * sqrt(15 / 16.0110765695113)
      = 0.2903732577433742 mJy.

The angular correction from Queue 0.45 arcsec to proposed 0.30 arcsec gives

    sigma_comparable
      = 0.2903732577433742 * (0.30 / 0.45)^2
      = 0.1290547812192774 mJy.

That is below the 0.60 mJy limit, so LINE-RMS is satisfied.

This pair is nevertheless `FALSE` / `CRITERIA_NOT_MET` because coverage belongs
to SPW 1, not SPW 2.

The Queue context-level OR therefore remains `FALSE` /
`CRITERIA_NOT_MET`: neither complete same-SPW pair is true.

## Cross-source isolation expectation

The complete retained pair matrix is:

| Source | Physical pair | FDM | Coverage | Resolution | RMS | Pair truth |
| --- | --- | --- | --- | --- | --- | --- |
| ARCHIVE | raw row 0 | SATISFIED | NOT_SATISFIED | SATISFIED | SATISFIED | FALSE |
| ARCHIVE | raw row 1 | NOT_SATISFIED | SATISFIED | SATISFIED | NOT_SATISFIED | FALSE |
| QUEUE | SPW 1 | NOT_SATISFIED | SATISFIED | NOT_SATISFIED | unresolved | FALSE |
| QUEUE | SPW 2 | SATISFIED | NOT_SATISFIED | SATISFIED | SATISFIED | FALSE |

There is intentionally enough favorable evidence somewhere in the full report to
construct a fictitious passing combination if provenance boundaries are ignored.
Such a combination is invalid.

No Archive row may borrow from another Archive row. No Queue SPW may borrow from
another Queue SPW. No Archive criterion may be combined with a Queue criterion.
Every retained physical pair remains false, so no LINE branch becomes
`CRITERIA_MET`.

## Combined execution expectation

Both selected sources must complete independently:

- Archive status: `COMPLETED`;
- Queue status: `COMPLETED`;
- Archive retained contexts: 2;
- Queue retained contexts: 1;
- total retained contexts: 3;
- evaluated contexts: 3;
- shown candidates: 1;
- display truncation: true.

Formal Queue LINE evaluation is explicitly selected, so effective provenance must
record:

- `queue_common: true`;
- `queue_continuum: false`;
- `queue_line: true`.

Expected context LINE branches are, in retained order:

1. Archive raw row 0: `CRITERIA_NOT_MET`;
2. Archive raw row 1: `CRITERIA_NOT_MET`;
3. Queue row: `CRITERIA_NOT_MET`.

## Review status

This case remains `AWAITING_INDEPENDENT_REVIEW`. It is not a genuine proposal
case and does not change the count of independently reviewed real-proposal cases.
