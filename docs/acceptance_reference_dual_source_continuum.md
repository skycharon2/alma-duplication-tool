# Independent reference for formal dual-source continuum acceptance

Reference version 1; prepared 2026-09-25.

This record defines the expected engineering behavior for the
`dual-source-continuum` acceptance case. It does not create a reviewed
real-proposal label and does not introduce or approve a new scientific method.

## Request identity

The request is the existing synthetic Guide A continuum request with exactly one
search change: source selection is `ARCHIVE` plus `QUEUE` instead of Archive
alone. The target, position, setup, representative frequency, four usable
continuum windows, angular resolution and requested aggregate RMS are unchanged.

The request therefore has:

- fixed single-point target at RA 201.365 deg, Dec -43.019 deg;
- CONTINUUM intent;
- requested angular resolution 0.30 arcsec;
- representative SKY frequency 230 GHz;
- four declared usable windows, each 1.875 GHz;
- requested aggregate continuum RMS 0.10 mJy/beam.

Archive and Queue evidence are evaluated independently against that same request.
No value from one source may satisfy a condition for the other source.

## Archive expectation

The Archive input is the unchanged synthetic Guide A replay already documented
in `acceptance_reference_values.md`.

Its four retained contexts therefore remain, in raw-row order:

1. `CRITERIA_MET`
2. `CRITERIA_NOT_MET`
3. `INDETERMINATE`
4. `CRITERIA_NOT_MET`

Adding Queue selection does not alter those Archive raw rows, their associations,
their source-specific criteria or their branch outcomes.

## Queue expectation

The Queue input is `examples/queue_continuum/queue.csv`. Its four retained
synthetic rows are evaluated independently against the same proposed request.

For rows 1, 2 and 4, the source position is the proposed position, so the
separation is zero and POS-SINGLE is satisfied within the supported row scope.
The candidate requested angular resolution is 0.45 arcsec, giving
0.45 / 0.30 = 1.5, within the inclusive factor-two ANGULAR limit. Their positive
`Ref.Frequency` is 230 GHz, equal to the proposed representative frequency, so
the CONT-FREQ factor is 1.0 and within the inclusive factor-1.3 limit.

The request-side continuum setup is unchanged from Guide A: four declared usable
windows of 1.875 GHz satisfy the approved setup condition. The Queue rows also
contain four regular SPWs centred at 226, 228, 232 and 234 GHz with 1875 MHz
usable width each. Those intervals do not overlap, so their usable union is

    4 * 1875 MHz = 7500 MHz.

The Queue sensitivity reference width is also 7500 MHz. Therefore the adopted
width normalization gives

    sigma_aggregate = sigma_reference * sqrt(7500 / 7500)
                    = sigma_reference.

For the proposed RMS of 0.10 mJy/beam, the inclusive factor-two limit is
0.20 mJy. Row 1 has `Req.Sensitivity = 0.15 mJy`, so CONT-RMS is satisfied.
Row 2 has `Req.Sensitivity = 0.30 mJy`, so CONT-RMS is not satisfied. With all
other required conditions satisfied, their branch outcomes are respectively
`CRITERIA_MET` and `CRITERIA_NOT_MET`.

Row 3 has the zero `Ref.Frequency` sentinel. The Queue continuum frequency and
RMS methods require a positive source reference frequency and do not substitute
another value for those criteria. With no definite failing condition, the
continuum branch remains `INDETERMINATE`.

Row 4 has `Use 7-m? = True`, but the adopted coherent row-level Queue common and
continuum contract does not use that auxiliary flag as a branch veto. Its
position, angular, setup and frequency conditions remain satisfied, and its
`Req.Sensitivity = 0.15 mJy` satisfies the same 0.20-mJy RMS limit. Its branch is
therefore `CRITERIA_MET`.

The expected Queue continuum branch sequence is therefore:

1. `CRITERIA_MET`
2. `CRITERIA_NOT_MET`
3. `INDETERMINATE`
4. `CRITERIA_MET`

Formal Queue continuum aggregation uses method version
`queue_continuum_branch_2`.

## Combined execution expectation

Both selected sources must complete independently:

- Archive status: `COMPLETED`;
- Queue status: `COMPLETED`;
- Archive retained contexts: 4;
- Queue retained contexts: 4;
- total retained contexts: 8;
- evaluated contexts: 8;
- shown candidates: 1;
- display truncation: true.

The report remains `assessment: NOT_AGGREGATED`; this acceptance case does not
create a search-wide duplication verdict.

The acceptance case explicitly requests Queue continuum evaluation. Effective
evaluation provenance must therefore record:

- `queue_common: true`;
- `queue_continuum: true`;
- `queue_line: false`.

The acceptance runner verifies that requested-to-effective configuration
separately from the scientific assertions in this reference.

## Review status

This is synthetic numerical acceptance evidence. Its review status remains
`AWAITING_INDEPENDENT_REVIEW`. It is not a genuine proposal case and does not
change the count of independently reviewed real-proposal cases.
