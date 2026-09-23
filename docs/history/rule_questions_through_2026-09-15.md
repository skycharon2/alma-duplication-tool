# Historical rule questions through 2026-09-15

Preserved from PR #76. OPEN/PARTIAL and "Still needed" statements describe the
old record, not new gates for the confirmed Archive scope. Current decisions are
in the [register](../duplication_rule_inputs.md#7-scientific-decision-register).

### Historical register through 2026-09-15 (superseded within the scope above)

The following is retained only to interpret old reports and earlier decisions.
Its OPEN/PARTIAL/provisional wording is historical, not the current development
gate. Queue, mosaic, generic bandwidth conversion and broader scope remain
outside the new approval.


Each entry below records what has been adopted and what is still missing, so
that settled interpretations are usable and the remaining question is the only
thing that has to be asked. Every entry is prepared by the project developer;
no scientific reviewer or review date is agreed yet, and each is recorded on its
entry once it is. The
[scientific follow-up checklist](../scientific_followup.md) holds the remaining
follow-up actions and does not repeat them. Scientific status remains
authoritative here.

Facts, reported feedback and executable-method approval are distinct. The
[reported oral-feedback record](../evidence/scientific_feedback.md) preserves the
user's paraphrase, missing discussion date/original wording, scope and closure
requirements. It is not independent written confirmation. Existing B/O/H/S/AQM/M and
policy citations retain their earlier provenance; this update does not reverify
them. No method in this table is enabled or marked CLOSED by any entry here.

| ID | Existing fact / source | Current decision status | Remaining closure requirement |
| --- | --- | --- | --- |
| Q1 | Full-width FWHM and approximate antenna model (H); coverage belongs to the other observation (A); candidate-side `0.5 * fwhmPB` (S) | PARTIAL: oral feedback reported; the candidate-side radius convention is corroborated for fixed single-field 12-m/7-m interferometry | Archive candidate mapping, exclusion of mosaic, TP, moving and mixed-array candidates, boundary examples, and whether the proposed beam is excluded from the test |
| Q2 | Nominal/output/usable widths differ (H); strict setup-width condition (A) | PARTIAL: usable proposed-window bandwidth reported; written confirmation pending | Approved field mapping and usable-width qualification examples; no blanket Archive conversion |
| Q3 | Representative frequency is a separate role (O); OT/execution references differ (H) | PARTIAL: center-frequency average reported; a later suggestion to use the setup representative frequency instead is not recorded feedback and conflicts with it | Which proposal-side quantity is the comparison frequency, then window membership, averaging definition, enumeration completeness, identity and compatible references |
| Q4 | Spacing, resolution and effective noise width are distinct (B) | OPEN: formula and applicable domain pending | RMS/smoothing method, polarization and beam compatibility |
| Q5 | RMS improvement condition is policy text (A) | OPEN: a direction is read here from the policy wording, candidate RMS at most twice the proposed RMS with no lower bound; not confirmed | Confirmation of that direction, of comparing a Queue requested RMS against an Archive estimated sensitivity, and equality and worse-RMS examples |
| Q6 | The Archive Manual documents per-SPW Frequency Support `Type`: `continuum` = TDM and `line` = FDM (AQM); the selected public TAP `frequency_support` string has no such token (M) | PARTIAL: the semantic meaning of the Archive result-table Type is documented; the current TAP parse path cannot supply it | Identify a reproducible machine-readable source/path for that Type (or equivalent approved mode evidence), bind it to the exact candidate SPW, and define failure/absence behavior |
| Q7 | Reported CASE inputs are recorded in section 8; live weak-recall checks retrieve both expected Member UIDs and AQ-equivalent filtering reproduces the reported one/two entry counts | PARTIAL: retrieval recall and entry-count reproduction are implemented evidence, not scientific labels | Supervisor confirmation of the display/assessment grouping unit, any special-policy scope, and whether either CASE has an approved duplicate/non-duplicate label |
| Q8 | All conditions must hold, with the spectral condition satisfied by either branch (A) | OPEN: the branch structure is transcribed in the plan and not implemented | Unit of assessment when one target carries several setups; agreed evaluation order for the three-valued combination; acceptance cases for a failed branch combined with an unknown branch |

These limit affected formal assessments, not valid request storage or candidate
retrieval. The feedback record provides conditional CONT-SETUP acceptance cases;
they are design expectations, not completed executable policy tests.

### Adopted interpretations and remaining questions

**Q1 positional coverage.** Adopted: Appendix A places the coverage on the other
observation, so the test uses the candidate half-power radius
`0.5 * 1.13 c / (nu D)` at the candidate reference frequency and antenna
diameter (A, H, S). The proposed beam is displayed but does not enter the test
and never replaces the search radius. The 12-m coefficient is documented; its
application to the 7-m antennas is supervisor-adopted. Scope: fixed target,
single pointing, 12-m or 7-m interferometry; mosaic, TP, moving and mixed-array
candidates stay unsupported.
Still needed: the Archive-side mapping for candidate frequency and diameter, and
boundary examples. The retrieval filter currently excludes a candidate whose
position falls outside the beam, so the criterion cannot report a definite
failure on a retained row; whether it should also be evaluated over excluded
rows is undecided.

**Q2 continuum qualification width.** Adopted: two or more windows strictly wider
than 1.8 GHz, equality failing (A). The width is the usable rather than the
nominal one (reported feedback). For the documented configuration family the
usable width is 15/16 of the nominal configuration width, giving the ladder
1875, 937.5, 468.75, 234.375, 117.1875 and 58.59375 MHz at full precision (H).
Still needed: written confirmation of the usable reading, and the evidence that
identifies a proposed window as belonging to that configuration family. Open
conflict: the current mapper converts any nominal width between 1875 and
2000 MHz to 1875 MHz, while the ladder maps 1900 MHz to 1781.25 MHz and
1920 MHz to exactly 1800 MHz, neither of which passes the strict test.

**Q3 continuum comparison frequency.** Adopted: the factor is 1.3, compared
symmetrically as larger over smaller (A). On the candidate side Archive
`frequency` is the observation central frequency and Queue `Ref.Frequency` is
the reference frequency for the requested sensitivity, both from their source
dictionaries.
Still needed: the proposal-side quantity. The record holds an average of
qualifying window centers; a later suggestion to use the setup representative
frequency is a different quantity and is not recorded feedback. Window
membership, averaging definition and enumeration completeness cannot be
specified until one of them is chosen.

**Q4 sensitivity normalisation.** Adopted: within an applicable noise model
`sigma` scales as the inverse square root of the effective noise bandwidth, and
channel spacing, spectral resolution and effective noise bandwidth remain
distinct quantities (B, O). Smoothing cannot recover a finer resolution, so a
common resolution is the coarser of the two.
Still needed: whether the helper script scaling `sqrt(ref_bw / res)` may be
adopted as a named provisional method, given that it puts a spectral resolution
where the noise relation requires an effective noise bandwidth, and that the
script states it ignores system-temperature variation between windows (S).

**Q5 sensitivity direction.** Adopted: the threshold is 2 and the comparison is
directional, since a proposal substantially deeper than the candidate must not
be reported as a duplicate. Read from the policy wording, the condition holds
when the candidate RMS is at most twice the proposed RMS, with no lower bound,
so a candidate deeper than the request still satisfies it. This reading is
derived here.
Still needed: confirmation of that reading, and whether a Queue requested RMS
may be compared against an Archive estimated sensitivity.

**Q6 correlator-mode evidence.** Adopted: the Cycle 13 Science Archive Manual
defines the Archive result-table Frequency Support `Type` values `continuum` and
`line` as TDM and FDM, respectively (AQM). The current public TAP
`frequency_support` string parsed by this project carries five tokens and no
`Type`, so that specific TAP component is not a mode source (M).
Still needed: a reproducible machine-readable Archive path that exposes the
documented Type (or equivalent approved mode evidence) at the correct SPW
granularity, plus explicit behavior when that evidence is absent or cannot be
associated. The remaining problem is data access/provenance and SPW association,
not the documented semantic meaning of the Archive result-table Type.

**Q7 reference retrieval cases.** Adopted: the CASE1 and CASE2 inputs and their
expected project codes are recorded in section 8. Live weak-recall tests retrieve
both expected Member UIDs, CASE1 has a pinned raw-row fixture, and the opt-in
AQ-equivalent filters plus presentation grouping reproduce the reported one/two
entry counts.
Still needed: supervisor confirmation that the display grouping is the intended
scientific review/assessment unit, any special-policy scope, and whether either
CASE is an approved duplicate/non-duplicate example rather than retrieval-only
evidence.

**Q8 aggregation and unit of assessment.** Adopted: Appendix A requires all
conditions to hold with the spectral condition satisfied by either branch, so
the structure is position and angular resolution and either the continuum or
the line branch, evaluated in three-valued logic (A). A conjunction with one
definite failure is a failure whatever else is unknown; a conjunction of true
and unknown is unknown; a disjunction with one satisfied branch is satisfied; a
disjunction of a failed and an unknown branch is unknown, never a failure.
Coverage and sensitivity in the line branch must be satisfied by the same window
pair.
Still needed: the unit of one assessment when a target carries several setups.
Until that is settled each setup is assessed independently and the results are
presented side by side rather than merged.
