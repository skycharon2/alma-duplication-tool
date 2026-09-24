# Queue common-rule adoption — 2026-09-24

The original adoption below records the superseded declaration-capable v3/v4
methods. The [source-only correction](#source-evidence-only-correction) is the
current contract. Historical statements are retained for old report references.

## Common rules

Project authority: the owner-provided handwritten synthesis (PDF pp. 13–17),
development guide dated 2026-09-24, and instruction to implement QUEUE-COMMON.
This is project adoption within a restricted workflow, not an ALMA endorsement
of the software. The method approval does not assert all candidate evidence is
present or that every source has been proved fixed celestial from CSV telemetry.

`queue_pos_single_3` adopts candidate-frequency 1.13*c/(nu*D) full FWHM,
half-FWHM radius, spherical separation and literal float64 separation <= radius.
It introduces no equality band or epsilon snapping. Legacy queue_pos_single_1
and all retrieval selectors retain their existing numerical boundary behavior.

`queue_angular_factor_4` uses Queue Req. Ang. Res. (requested/expected), proposal
requested angular resolution, canonical arcsec and the existing exact symmetric
factor <=2 calculation. Archive estimated semantics are not copied onto Queue.

The owner's subsequent scope clarification adopts D=7 m for exclusive 7-m
candidates and D=12 m for exclusive TP candidates. Both Use 7-m? and Use TP?
true remain mixed and unsupported. Neither single-positive flag proves the
main array absent in the operational CSV schema. An explicit snapshot/row-bound
array declaration and source/review reference therefore supplies that missing
interpretation without a sidecar. Main 12 m keeps the negative-auxiliary-flags
profile. Conflicting flags, frame, target or diameter block evaluation.

The revised methods are queue_pos_single_3 and queue_angular_factor_4; previous
v2/v3 reports retain their old meanings. Only the legacy TP spatial-selection
gate is lifted for declared TP_ONLY, after all frame, fixed-centre, single-field,
regular-SPW and offset-domain guards. No TP branch/RMS completion is implied.

Selecting --queue-common adopts the existing Queue Portal fixed-celestial/
equatorial workflow and offset convention for supported rows. This is explicitly
an interpretation, not a measured CSV frame or independently recovered target
type. Zero RA/Dec placeholders, unsupported frames, mosaics, scans and unsupported
arrays remain unresolved. Confirm that the input belongs to this fixed-target
workflow before selecting it; no moving-target name inference is added.

Positive candidate Ref.Frequency supplies the beam; the existing versioned
zero-reference sky-SPW weighted fallback remains POSITION ONLY. It is not a
Queue CONT-FREQ mapping. Existing spherical offset transport is reused with
strict snapshot/row/context binding. Raw inputs stay unchanged.

No complete Queue continuum/LINE branch is enabled by this delivery. Existing
branch scope guards stay in place even when these two common criteria pass.
Missing evidence is not a definite failure. No search-wide absence conclusion.

## Adopted next-branch decisions, not implemented here

The supplied guide adopts regular-SPW Portal rest-to-sky normalization, continuum
union-of-usable-bandwidth RMS scaling, and row-reference sensitivity projected
to a matched line SPW/common resolution with the Portal Tsys limitation retained.
The shared line angular correction applies to Queue; Archive's 10 km/s starting
basis does not. These decisions supersede the old blanket warning against Queue
angular correction; implementation/acceptance remains in future increments.

The guide resolves transcription issues in the notes: RADIO/OPTICAL/RELATIVISTIC
are velocity conventions; LSRK/barycentric/etc. are frames. The 230 GHz, 0.5 km/s
example produces approximately 0.3836 MHz, not GHz. The text note's literal
10 km/s smoothing input belongs to Archive, not Queue. None is implemented here.

## Source identities

Original attachments remain outside the repository; hashes identify the exact
reviewed versions without copying private hand notes into production contracts.

| Supplied file | SHA-256 |
| --- | --- |
| `queue_single_field_duplication_development_guide(1).md` | `d622011ffbc17d5bbba458bd3ac1feb619af53eb970b7cb05f7feccd574a56f6` |
| `duplication_notes(1).txt` | `3c22a727981a2fcc3879b3d611c16add50e41b330ca52ae5f05ddcd148d2bd11` |
| `ノート 3(1).pdf` | `dfa5d3e870987e186722cc7435cedd0e43b855557c56a39ca7e3c131a694e222` |

Public sources opened on 2026-09-24:

- [Cycle 13 Users' Policies, Appendix A](https://almascience.eso.org/documents-and-tools/cycle13/alma-user-policies): other-observation half-power location and angular factor <=2.
- [Cycle 13 Portal helper](https://almascience.eso.org/documents-and-tools/cycle13/python-script/view): version 1.3.1, user-contributed/as-is, not an ARC-supported official product.
- [Existing captured Queue position interpretation](official_sources.md#queue-position-profile): implementation provenance for the reused source adapter.

The [current contract](../queue_common.md) owns scope, execution and regression gates.

## Source evidence only correction

The project owner's subsequent review retracts the manual exclusive-array
interpretation path for the current interferometric method. Current versions are
queue_pos_single_4 and queue_angular_factor_5. The original inclusive position
comparison, candidate frequency, exact angular comparison, source binding and
fixed-target/geometry gates remain in effect.

- Both auxiliary flags explicitly False: 12 m under the normal supported profile.
- Use 7-m? True without a supported authoritative standalone source: unresolved.
- Use TP? True: outside this interferometry method, irrespective of its 12-m dish.
- Unknown flags: unresolved; never silently fill missing source evidence.

Remove QueueArrayDeclaration, CLI --queue-array/--queue-array-decision-ref and
corresponding evaluator arguments. A reference string alone is not verified
array evidence. TP cannot be enabled by any manual declaration or spatial
interpretation. No existing raw CSV, legacy retrieval method or historical report
is rewritten. Future authoritative standalone information requires a separate
source adapter and versioned adoption.

The Cycle 13 Proposer's Guide A.1/A.3/A.4 distinguishes accompanying and
standalone ACA and the TP single-dish component. The Portal helper uses 7 m
only for standalone ACA; missing standalone values are replaced with False for
its plotting convention. That fallback is not adopted as formal source evidence.
See the public links above and the project's captured official-source record.

The pinned snapshot has 3,200 observation rows: 108 with both flags False,
16 with 7-m True/TP False, zero with 7-m False/TP True, and 3,076 with both True.
These are row counts, not counts of assessable single-field candidates. The
16 rows remain unresolved; neither the counts nor target names prove standalone.
