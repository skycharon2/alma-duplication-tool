# Captured s_region backend acceptance

Captured from the official ESO TAP endpoint on 2026-10-26. These are engineering
requests derived from CASE2, using the existing actual three-point OT export.
They are not a reproduction of the full original observing proposal.

- `continuum/`: live capture selecting four discovered NGC253 Members.
- `line/`: live capture selecting the two CASE2 Members.
- `*-expected.json`: complete per-context decisions from the corresponding live
  runs, compared exactly with offline replay through the main assessment entry.
- `historical-no-auxiliary.json`: preserved local prior preparation receipt for
  X74/X176, recorded as NO_USABLE_AUXILIARY_PRODUCT. This describes that earlier
  attempt, not a claim that no auxiliary product can ever become available.

Each capture contains the original discovery responses, exact query plans, selected
subset, request and imported proposal, plus per-candidate TAP count, schema and
metadata responses. `bundle.json` checksums all capture files. Metadata replay
also enforces the original ADQL/MAXREC and completeness results.

Both discovery captures returned 214 candidate pairs. Only the declared subsets
were assessed. No auxiliary requests were made. These samples do not establish
Archive-wide completeness, performance or universal geometric format support.

Observed results:

| Member suffix | Continuum position | Continuum joint | Line joint |
| --- | --- | --- | --- |
| X74/X176 | 3/3 inside | FALSE | Not sampled |
| X196/X3d | Unsupported mixed TP scope | UNKNOWN | Not sampled |
| X133d/X9c3 | 3/3 inside | TRUE | TRUE or FALSE by context |
| X133d/X9c5 | 3/3 inside | FALSE | FALSE |

X9c5 has dominant 12m antenna evidence with minority TP-pad tokens. The scope gate
uses the existing classifier rather than treating any TP token as a veto.
X196/X3d exercises the unresolved mixed-TP scope case. Point containment counts
are diagnostic when the scientific scope is unsupported.

No raw measurement sets, auxiliary TAR files, credentials or local caches are
included. Test fixtures are intentionally small metadata evidence, not generated
working reports. Refreshes must record a new capture and review changed outcomes.
