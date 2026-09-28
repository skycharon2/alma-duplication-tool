# Independent reference for source-state completeness matrix

Reference version 1; prepared 2026-09-25.

These are engineering source-state expectations, not reviewed real-proposal
duplication labels. Source execution state, filter completeness and scientific
branch outcomes remain separate. No case below supplies a search-wide
duplication verdict.

## Inspection version 2

The source states remain distinct: NOT_SELECTED, NOT_PROVIDED, FAILED,
INCOMPLETE and COMPLETED.

`REQUESTED_FILTERS_NOT_FULLY_EVALUATED` is emitted only for a COMPLETED source
whose requested filters were not fully evaluated. A false property value on
NOT_SELECTED, NOT_PROVIDED, FAILED or INCOMPLETE is not a second gap.

Every case retains `search_wide_verdict: NOT_PROVIDED`.

## Archive failed, Queue preserved

The formal dual-source LINE request changes only the search radius from 30 to
20 arcsec while replaying the unchanged Guide B Archive capture. The recorded
Archive query therefore fails current-plan binding.

Expected:

- exit code 3;
- Archive FAILED, retained 0;
- Queue COMPLETED, retained 2;
- total/evaluated contexts 2/2;
- shown candidates 1 and display truncation true;
- Queue contexts remain evaluated;
- inspection records Archive FAILED;
- inspection does not add Archive
  REQUESTED_FILTERS_NOT_FULLY_EVALUATED merely because the failed source reports
  that property as false.

## Queue failed, Archive preserved

The request and Archive replay remain unchanged. The Queue CSV deliberately has
one physical data row shorter than the operational header, violating the strict
Queue row-width contract.

Expected:

- exit code 3;
- Archive COMPLETED, retained 2;
- Queue FAILED, retained 0;
- total/evaluated contexts 2/2;
- shown candidates 1 and display truncation true;
- Archive contexts remain evaluated;
- inspection records Queue FAILED only for that failed source and does not add
  Queue REQUESTED_FILTERS_NOT_FULLY_EVALUATED.

## Completed empty Queue

The request selects Queue only. The Queue CSV is structurally complete through
its secondary header but contains zero physical data rows.

Expected:

- exit code 0;
- Archive NOT_SELECTED;
- Queue COMPLETED;
- both retained-row counts 0;
- total/evaluated/shown contexts 0/0/0;
- display truncation false;
- Queue requested_filters_fully_evaluated true;
- no SOURCE_OR_SEARCH_INCOMPLETE occurrence;
- search_wide_verdict remains NOT_PROVIDED.

Therefore a completed zero-row source is neither missing nor failed and is not
a search-wide no-duplication conclusion.

## Archive incomplete, Queue preserved

Archive INCOMPLETE is tested at integration level with an injected OVERFLOW query
result. It is intentionally not represented by weakening the immutable replay
contract.

Expected:

- exit code 3;
- Archive INCOMPLETE, retained 0;
- Queue COMPLETED with available contexts preserved;
- inspection records Archive INCOMPLETE;
- inspection does not add Archive
  REQUESTED_FILTERS_NOT_FULLY_EVALUATED for the incomplete source;
- search_wide_verdict remains NOT_PROVIDED.
