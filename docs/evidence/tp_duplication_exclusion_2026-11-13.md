# TP exclusion from duplication assessment

Project owner instruction, 2026-11-13: retain TP in source evidence, but ignore it
throughout duplication assessment. TP must neither create a scientific branch
nor contribute UNKNOWN/INDETERMINATE or a negative decision. This is the project's
chosen assessment scope, not a claim about ALMA policy.

For mixed objects, existing complete 7 m and 12 m branches remain independent;
any satisfying interferometric branch may qualify the object. TP does not block
region containment, aperture inference, or Queue LINE processor mode evidence.
A positively identified TP-only Archive context is retained with
`TP_IGNORED_FOR_DUPLICATION` and empty criteria, branches, and LINE pairs. It is
excluded before these calculations and is not categorized as a match, nonmatch,
or scientific review item. Missing/ambiguous array evidence is not assumed TP-only.
Source retrieval may still return TP metadata; inspection of that metadata is
necessary to identify the exclusion. Raw acquisition records are unchanged.

Queue `Use TP?` is an auxiliary request flag, not an assertion that the observation
is exclusively TP. Existing standalone ACA / 7 m / inferred main-array rules
still identify interferometric branches. TP is retained in provenance and
`tp_treatment`, but is not a coverage limitation. General processor diagnostics
may still inspect TP when explicitly requested; duplication pairing always uses
interferometric processor scope.

Reports from earlier runs remain immutable. Re-run an assessment for the new
scope. Tests cover TP-only short-circuiting, all official mixed labels,
Queue DOUBLE/FULL polarization mode parity, source-bound exclusion serialization,
and omission from Mosaic scientific-review buckets.
