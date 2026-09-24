# Adopt the Cycle 13 Portal row primary-beam convention

Date: 2026-09-24. This project decision adopts the user's supplied revised
Queue diameter analysis for **row-level POS-SINGLE**. It supersedes the diameter
and auxiliary-array exclusions in queue_pos_single_4; historical reports retain
their original method identity. It does not approve TP component duplication.

Source checked: [Cycle 13 Portal helper](https://almascience.eso.org/documents-and-tools/cycle13/python-script/view),
`readObservations`: missing operational standAlone_ACA is filled as false;
row diameter starts at 12 m and changes to 7 m where standalone is true.
The script is user-contributed/as-is. Its fallback is an adopted operational
assumption, not proof that a main-array observation exists in a given row.

| Operational standalone evidence | Row diameter | Evidence kind |
| --- | --- | --- |
| True | 7 m | SOURCE_PROVIDED |
| False | 12 m | SOURCE_PROVIDED |
| Column absent | 12 m | PORTAL_HELPER_ASSUMPTION |
| Present but empty/invalid | Unknown | UNRESOLVED; no absent-column fallback |

Only case-insensitive True/False tokens, with surrounding whitespace removed,
are accepted as boolean source evidence. Original tokens are retained. A
standalone entry in the embedded dictionary is not an operational column.
Duplicate columns remain parser errors. Parser 7 admits this one optional column
alongside the 79 required columns; other unexpected columns remain errors.

The profile is `QUEUE_CYCLE13_PORTAL_ROW_BEAM_1`; Cycle 13 identifies the adopted
helper, not the year of every project in the released multi-cycle snapshot.
No project-code suffix or Use 7-m?/Use TP? value is used to select the diameter.
Those flags remain requested-component evidence; TP without 7-m is explicitly
reported as an anomaly, but does not turn into a different beam diameter.

The approved row method is `queue_pos_single_5`. Use the candidate frequency and
half of FWHM = 1.13*c/(frequency*D), with inclusive separation <= radius.
The previous frequency convention, spherical offsets, fixed-target/frame checks,
placeholder handling, regular-SPW scope and single-field scope remain in force.
No user array declaration or sidecar is introduced.

Position and other scientific scopes are independent. `queue_angular_factor_6`
retains the component interpretation restriction, with a more accurate
QUEUE_COMPONENT_SCOPE_NOT_ADOPTED reason. Continuum frequency/RMS and branch
scope remain restricted as in the prior delivery. A valid row beam does not
upgrade auxiliary-array sensitivity/resolution into supported component science.

The old retrieval/legacy method remains conservative. Rows with the newly
accepted operational standalone column cannot be discarded using the older
auxiliary-flag diameter profile: that path retains an unresolved diameter for
later row-level evaluation. Default retrieval is not replaced with an assumed
complete spatial search. Archive behavior is unchanged.

Supplied analysis SHA-256: `ea19cc083eaa070c6a323bc4bdd2ef06e24d911fd15188650805d36130ea43cf`.
