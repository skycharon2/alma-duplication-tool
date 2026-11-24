# Assessment input snapshots

`alma_duplicate.ui.input_snapshot` captures the shared browser
`ProposalFormState` and restores a fresh editable state. The contract is
`assessment_input_snapshot_1`, a JSON object with six required fields.

| Field | Contents |
| --- | --- |
| `schema_version` | `assessment_input_snapshot_1` |
| `workflow` | `SINGLE`, `MULTI_SOURCE_SINGLE`, or `MOSAIC` |
| `form_contract` | `LEGACY` or `V2`, derived with the same predicate as the form builder |
| `form_values` | Allowlisted inputs from the submitted browser form |
| `line_rows` | Ordered IDs of LINE or Legacy window rows |
| `spw_rows` | Ordered IDs of independent physical SPW rows |

Capture retains target and coordinate fields, format selectors, source and
purpose selections, search settings, shared or local redshifts, scientific
quantities and their units, REST/SKY references, inventory declarations,
source-list format, and Mosaic array and confirmation fields. Dynamic field
names must belong to a retained row and use a suffix allowed for that row
kind. Row IDs use the existing browser syntax and limit.

Strings are copied verbatim, including blanks, leading zeros, whitespace and
decimal precision. The order of the row and selection lists is preserved.
Restore returns independent copies. It rejects unknown schema versions,
unexpected fields, invalid field types, inconsistent workflow or form
contract, overlapping row IDs, and payloads over 1 MiB of UTF-8 JSON. Scientific
validation still belongs to the existing form validator.

Action controls, CSRF and upload tokens, execution and validation state,
ownership and session secrets, previews, and fields from removed rows are
excluded. The form snapshot itself stores neither file bytes nor storage keys.
Snapshot capture and restore perform no source queries and create no report or
draft records.

## Persistent storage

Migration `0004_assessment_input_snapshots` adds optional links from newly
published browser reports and completed batch manifests to their immutable
input snapshot. All reports produced by a single submission share one snapshot.
A completed batch links to its shared form and its original CSV or TXT, rather
than storing a separate copy of the source list per target.

In database mode, snapshots use the existing browser owner digest and uploads
use the private artifact store. The filename is normalized for display and the
original bytes, parser-confirmed hash, format and size are kept separately from
report downloads. Lookups require both the parent and the snapshot to belong to
the current browser. Missing legacy links are returned as unavailable, and
damaged file contents fail integrity checks.

Completed snapshots and their uploads follow persistent report storage and have
no automatic expiry. Removing an in-progress preview releases only the temporary
upload. Persistent copies are managed by the deployment operator. Existing
reports and ordinary temporary mode are not backfilled.

## Editable drafts

In database mode, a browser can create a short-lived draft with a CSRF-protected
POST to `/runs/<run_id>/reuse` or `/batches/<batch_id>/reuse`. The server resolves
the parent in the caller's browser scope, verifies its snapshot and any upload,
then redirects with HTTP 303 to the corresponding form. The opaque draft ID
identifies a copy of the saved form inputs in a bounded process-local store.
Opening the form only reads that copy. The regular form POST handles edits,
validation and new runs.

Drafts default to 30 minutes. Configure their lifetime with
`ALMA_ASSESSMENT_DRAFT_TTL_SECONDS`. Restarting the service clears these drafts;
the original saved inputs can be used to create another. Missing, expired,
foreign or wrong-workflow drafts return 404. A damaged saved upload prevents
draft creation and leaves the original report accessible.

For Multi-source drafts, the server reparses the verified CSV or TXT bytes with
the normal source-list parser and allocates a fresh browser-owned temporary
upload. The batch form shows the restored filename and rows in its usual
preview. It supports normal validation, file replacement and submission with a
new batch ID. The original file bytes, target order and per-target redshifts are
preserved. If that temporary upload expires or is removed, reopen the saved
settings to create a fresh copy.

Single Pointing drafts restore the saved form inputs, including V2 spectral
windows. Mosaic drafts also reparse the original OT file with the normal
pointings parser and show the restored preview. The user can validate, replace
the temporary OT file, or submit a fresh assessment. The original saved inputs
and uploaded file remain available for future drafts.

The Existing reports action will be added in a later step.
