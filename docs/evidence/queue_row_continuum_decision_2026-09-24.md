# Coherent Queue row interpretation for common and continuum criteria

This corrects the component gate retained in delivery 0017. The user confirmed
that one Queue row is the comparison observation throughout the supported
single-field continuum workflow. This supersedes the component-only restrictions
in the earlier row-beam and continuum decisions, without changing old reports.

[Cycle 13 Users' Policies Appendix A](https://almascience.hq.eso.org/documents-and-tools/cycle13/alma-user-policies)
combines target-field position, angular resolution and the continuum or line
spectral criteria. It does not require auxiliary flags to be false before
applying the angular/continuum comparison. The missing-standalone assumption
remains a separately declared Portal convention, not a statement of policy.

Use the same source-bound row's Req. Ang. Res., positive Ref.Frequency,
Req.Sensitivity, Ref.Freq.Width and regular SPW setup. Requested auxiliary
components and standalone status remain provenance. They do not gate ANGULAR,
CONT-FREQ, CONT-RMS or continuum aggregation. No row quantity is assigned to
individual array components or borrowed from another row.

Existing formula, unit, direct-proposal-RMS, usable-union and exact-boundary
contracts remain unchanged. Fixed-target, supported geometry/frame, valid
standalone interpretation and coherent association gates remain. Missing
quantities still produce unknown conditions. Within supported scope, a definite
position failure AND unknown RMS is a negative continuum branch.

Version changes: queue_angular_factor_7, queue_cont_freq_2,
queue_cont_rms_portal_2, queue_continuum_branch_2. POS-SINGLE remains
queue_pos_single_5 because its formula and interpretation are unchanged.

The evaluator already passes the identical common criterion objects to LINE
pair evaluation. This delivery tests that property for standalone true/false
and absent, and for line-only and mixed intent. It does not implement Queue
line numerical rules or remove their separate unsupported-source gate. Those
unfinished rules must not be mistaken for an unresolved beam diameter.
