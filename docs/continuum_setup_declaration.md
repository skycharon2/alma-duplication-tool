# Researcher declaration of continuum setup qualification

## Project decision and scope

Adopted on 2026-09-30 for the requested researcher-confirmation workflow. A
researcher may explicitly declare that a proposed setup contains at least two
distinct spectral windows, each with usable bandwidth strictly greater than
1.8 GHz, without entering every SPW. This is an accepted project input-evidence
route. It is not independent verification of the correlator setup, an ALMA
endorsement of the declaration mechanism, or a new supervisor confirmation.

The separate CONTINUUM intent still selects a branch only. No threshold,
candidate criterion, RMS rule or LINE association changes. Qualification does
not imply that any candidate or entire proposal is a duplicate.

## Input contract

Request model 3 and validation version 7 add the optional field:

```json
{
  "continuum_setup_declaration": "AT_LEAST_TWO_USABLE_WINDOWS_GT_1_8_GHZ"
}
```

Absence or null means no declaration. Booleans, arbitrary text and the ordinary
CONTINUUM intent are not declarations. The exact enum is a positive assertion
about the request's `setup_id`; its fixed provenance is USER_DECLARED. The raw
and normalized request retain it. No window identities, widths, centers or
complete-list claim are generated from it. Existing request payloads remain valid.

The validator checks the declaration's format and adds an EVIDENCE note. It
does not calculate CONT-SETUP or decide conflicts. With a declaration, missing
SPW widths are not a mandatory CONT-SETUP input; other missing-input diagnostics
and all invalid supplied values still apply. A retained declaration with no
CONTINUUM intent does not activate that branch. Unchecking it removes the field.

## Method and contradictions

`continuum_setup_declaration_1` records USER_DECLARED, the exact statement,
setup ID, supplied window evidence and whether widths independently corroborate
the assertion. The count of evidenced qualifying windows can be zero; it is
never fabricated as two. Its decision reference is this document. APPROVED
means accepted for this project's formal aggregation under this explicit input
contract; it does not certify the researcher's assertion as independently true.

- With no contradicting evidence, CONT-SETUP is SATISFIED and eligible for
  aggregation. Frequency, sensitivity, position and angular criteria remain
  independent and may still be indeterminate or not met.
- For a declared complete list, count every window not definitely disqualified
  as potentially qualifying. If fewer than two could qualify, return a null
  outcome with INSUFFICIENT_INFORMATION, reason
  `CONTINUUM_SETUP_DECLARATION_CONFLICT` and a PROPOSED/CONFLICTING_EVIDENCE issue.
  A complete list with zero or one window therefore conflicts too.
- A partial list containing narrow windows alone does not disprove the assertion:
  qualifying windows may be unlisted. Unknown widths are not contradictory.
- Direct USABLE and bounding NOMINAL evidence use the existing exact threshold
  logic. Optional nominal conversion does not decide declaration consistency.
- Invalid units, negative widths and duplicate IDs remain validator errors.

A conflict is an unresolved criterion, not an automatic negative duplication
verdict. Existing three-valued branch aggregation is unchanged: another false
criterion can still establish CRITERIA_NOT_MET even with this conflict.

No declaration preserves `continuum_setup_2` / `continuum_setup_3` behavior.
The approval wrapper must not relabel the new route as the historical confirmed
width method or attach the old supervisor reference. Historical evidence and
acceptance fixture files are not rewritten. New reports retain report v4 and
inspection v3; their nested request/validation versions identify this extension.

## Browser and verification

The independent confirmation appears under continuum sensitivity, unchecked by
default. Detailed SPWs remain optional. Reports identify the declaration path
and show a prominent conflict warning when supplied complete-list evidence
contradicts it. Input-valid and search-ready labels do not assert consistency;
the conflict is evaluated when Run assessment is invoked.

Tests cover omitted and invalid declarations, incomplete/complete lists, exact
1.8 GHz boundaries, nominal and unknown widths, invalid supplied quantities,
legacy method preservation, remaining missing evidence, report provenance,
inspection conflict visibility, and shared CLI/browser results with both sources.
