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
excluded. This contract does not store uploaded CSV/TXT or OT bytes. Future
persistence will bind verified file artifacts and owner metadata separately.
The same original upload must be supplied separately to reproduce a batch or
a Mosaic submission. Snapshot capture and restore perform no source queries
and create no report or draft records.
