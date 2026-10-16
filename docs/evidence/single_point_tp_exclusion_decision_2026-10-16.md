# Single-point TP exclusion and proposal-configuration scope

Date: 2026-10-16. The project owner reports this supervisor clarification and
explicitly authorizes its implementation. This records the supplied scientific
basis; it does not claim an independent observatory-policy verification.

For fixed SINGLE_POINTING assessment, TP is provenance only and never supplies
an eligible beam diameter. TP cannot be requested as a standalone observing
component; TP-only is not a supported normal proposal configuration.

This decision supersedes the TP-derived D12 provisions of the October 1
Queue array inference decision and the October 2 Archive TP position decision.
Those historical records and saved reports retain their original meanings.

| Components | Eligible diameters (m) |
| --- | --- |
| 7m | 7 |
| 12m | 12 |
| 7m 12m | 7 and 12, complete independent branches |
| 7m TP | 7 |
| 12m TP | 12 |
| 7m 12m TP | 7 and 12, complete independent branches |

Unexpected TP-only, conflicting or invalid evidence is unresolved. In particular,
absence of an eligible branch is not a successful non-duplication result.
Archive TP-only remains visible as TOTAL_POWER, with TP_IGNORED_FOR_POSITION and
ARCHIVE_TOTAL_POWER_SCIENTIFIC_SCOPE_UNSUPPORTED diagnostics and no radius or
position outcome. CONTINUUM and LINE scope gates force UNKNOWN even if another
criterion is false.

## Queue evidence interpretation

- Valid standAlone_ACA=False supplies main-array D12, plus D7 if requested.
- Valid standAlone_ACA=True and Use 7-m=True supplies D7 only, regardless of TP.
- standAlone_ACA=True with Use 7-m=False is inconsistent and unresolved. Its raw
  value and anomaly remain visible; AR or TP cannot repair the conflict.
- With an absent operational field, Use 7-m=False retains the existing D12
  inference. The owner specifically confirms Use TP=True/Use 7-m=False includes
  main-array 12m; this is not a TP-aperture-derived hypothesis.
- With an absent operational field and Use 7-m=True, apply the existing fixed
  band/AR threshold whether TP is true or false. Strictly finer AR supplies
  D7+D12; equality or coarser supplies D7. Missing required evidence is unresolved.
- Invalid or duplicate operational fields and invalid typed flags remain
  unresolved. No inferred value overwrites raw operational evidence.

The conflict gate supersedes the earlier practice of reporting a standalone
anomaly while still evaluating D7. Otherwise non-TP inference is unchanged.

## Archive and aggregation

Exact AQ observation ID, Member and source-name binding remains unchanged.
All original records, labels, components and capture/live provenance are retained.
Only explicit 7m and 12m components supply eligible diameters; TP neither adds D12
nor suppresses a genuine interferometric component.

Each diameter evaluates a complete CONTINUUM/LINE branch with its own position
criterion. Existing three-valued OR combines complete branches only. No borrowing
across diameters, contexts, SPWs or sources is permitted. Unchanged formulas,
frequency selection, inclusive position boundary, solar exemption, geometry gates,
retrieval and raw snapshots remain outside this revision.

## Method identities and reports

- Queue beam profile: QUEUE_ARRAY_BEAM_INFERENCE_3.
- Queue position: queue_pos_single_8 (previously supported geometry) and
  queue_pos_single_9 (existing blank-Mosaic offset interpretation).
- Archive array evidence: archive_source_array_2.
- Source-bound Archive position: archive_pos_single_4.
- Complete-branch OR methods remain at version 1 because their algorithm and
  contracts are unchanged. Angular and spectral methods are unchanged.

Report schema v4 and inspection v3 remain unchanged: existing method identities,
reasons, provenance and variant fields express this scientific revision. Historical
reports are not reinterpreted. Tests treat TP-only as an unexpected-input defense,
not a supported seventh proposal configuration.
