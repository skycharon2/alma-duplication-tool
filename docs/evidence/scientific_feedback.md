# Reported scientific feedback and closure requirements

## Evidence status

Record ID: `reported-feedback-q1-q3-01`.

Source: the project owner's supplied development review summarizing supervisor
oral feedback. The discussion date, exact supervisor wording and original
written confirmation were not supplied with this record. This is a paraphrase,
not a quotation, a verified PDF annotation or a signed method specification.
No source date is inferred from a file name, Git timestamp or this record ID.

The review also reports that Weekly_Progress_Report.pdf page 16 still asks Q1/Q2
as questions. That PDF was not independently re-read for this change. Its
questions are not used as evidence of approval. Keep earlier report observations
and later reported oral feedback as distinct evidence events.

The [Q1–Q7 register](../duplication_rule_inputs.md#7-scientific-decision-register)
owns decision status. This record owns the reported feedback, its scope and
closure checklist. No production method is enabled by this document.

## Q1: primary beam and position

Reported progress: partial oral confirmation of the beam approach. Exact wording,
discussion date and the complete approved parameter choices remain to be attached.

Safe preparation: specify a numerical interface with explicit frequency, antenna
diameter, units and full-width/radius roles. Successful numerical calculation
alone must not produce a formal position result.

Still required: which frequency belongs to the candidate; array/geometry scope;
Archive field-to-role mapping; supported pointing coverage; boundary examples.
The currently selected TAP fields do not establish a confirmed mapping to the
original declared representative frequency. This is not a claim that the entire
Archive lacks it. One example agreeing with an SPW average does not approve a
universal fallback. Search radius remains separate from policy coverage.

## Q2: proposed continuum setup

Reported answer (paraphrase): use usable bandwidth for the setup-width test.
Written confirmation and precise input mapping are pending.

Scope: distinct windows in the proposed setup. This does not authorize a global
nominal-to-usable conversion for Archive evidence or transfer the Queue conversion
table to Archive. Unknown usable widths stay unknown. A scalar usable width may
support qualification without establishing usable coverage edges.

Prepare the following acceptance specification; these are not executed policy
tests and do not change request validation or candidate filters:

| Proposed evidence | Expected qualification after method approval |
| --- | --- |
| Two distinct windows, each usable width 1.8001 GHz | Satisfied |
| Complete two-window list: usable widths 1.8 and 1.9 GHz | Not satisfied; the boundary is strict |
| Same positive widths expressed in MHz | Same result after unit conversion |
| One qualifying window repeated under the same identity | Must not count as two; conflicting duplicate evidence needs a diagnostic |
| Two qualifying distinct windows, list incomplete | Satisfied; further windows cannot undo the positive evidence |
| One qualifying window and one unknown width | Unresolved |
| No qualifying listed windows, list incomplete | Unresolved; cannot establish an exhaustive negative |
| Complete list, all usable widths known, fewer than two qualify | Not satisfied |
| Only nominal widths known | Unresolved unless a separately approved applicable conversion supplies usable evidence |
| Negative, nonfinite or otherwise invalid supplied width | Invalid evidence, not a negative policy result |

Existing request validation already owns duplicate IDs and invalid input rejection;
future qualification must consume validated evidence without weakening those gates.
Formal evaluation status and condition result must remain separate. These expected
results are conditional on approval of the usable-width interpretation.

## Q3: comparison frequency

Reported answer (paraphrase): average window center frequencies. Written scope and
an executable definition of the participating window set remain pending.

Before implementation, specify separately for request and candidate: qualifying
window membership; arithmetic or other averaging method; complete-list requirement;
duplicate-window identity; treatment of unknown/incompatible references; execution
and setup boundaries. Do not average across executions merely sharing a Member OUS.
A complete average over the listed windows is not necessarily the intended average
over the actual setup. Preserve centers, representative frequency and RMS reference
frequency as independent roles. Multiple RMS selection is a separate open question.

## Q4–Q7

Q4 still needs the RMS formula and applicable domain; no automatic noise scaling
is approved here. Q5–Q7 were not discussed in the supplied feedback. Preserve prior
facts, case records and open items; silence does not close or reopen a decision.
Mode evidence and Archive UI classification are not interchangeable merely because
a classification is derived. CASE grouping and formal labels remain unconfirmed.

## Next retrieval evidence delivery

Use the implemented candidate-search service. Capture the validated input, actual
plan and query, source dates, completeness, all row/filter audits and omitted IDs.
Persist the full retained set before presentation limiting. Expected Member UIDs
belong only in assertions, never in retrieval filters.

First test expected-UID recall. Skipped frequency/RMS/resolution filters can produce
a broader set, so do not assert exactly one/two candidates until effective filters
and grouping semantics are fixed. Member grouping is a view retaining context,
execution and component references, not a merge of the best quantities.
A failed/incomplete source or an unevaluated filter remains visible in the report.
This document does not claim a new live query, fixed CASE fixture or duplicate label.

## Updating this record

Attach the actual discussion date and original answer or durable source reference
when available. Preserve this paraphrase as a historical evidence event. For each
approved method record its scope, excluded cases, input-field mapping, version and
boundary examples, then update the central register. An answer to a formula question
does not implicitly approve every reference, geometry or source conversion.
