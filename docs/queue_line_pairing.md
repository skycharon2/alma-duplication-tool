# Queue spectral-line evidence and pairing contract

Status: same-row regular-SPW evidence preparation implemented. Formal Queue
LINE-FDM, coverage, resolution, RMS and branch aggregation remain pending.
The independent preparation API and CLI leave the existing evaluation entry
point, Archive LINE, Queue continuum and evaluation report schema unchanged.

The builder version is `queue_line_pair_builder_1`; the standalone preparation
report schema is `1`. Preparation always reports `assessment: NOT_EVALUATED`.
The implementation follows the supplied Queue development guide, sections 4
and 11-17, and the matched-SPW method in the project notes, pages 15-17.

## Pair identity and ownership

`queue_line_pairing.QueueLinePairReference` retains the full relationship:

| Reference | Existing owner |
| --- | --- |
| proposed_setup_id / proposed_window_id | ProposedObservationRequest / ProposedWindow |
| candidate_context_id | ComparisonContext |
| snapshot_sha256 / source_row_id | QueueRawRowId, including the physical CSV line |
| content_fingerprint | RawQueueRow |
| spw_number | One occupied regular SPW slot in that physical row |

`resolve(request, context)` verifies these identities against the owning row
and its reconstruction association. Foreign contexts, rows, snapshots or
proposal setups, ambiguous windows, and missing or repeated SPW numbers raise
`ValueError`. Association errors are not scientific failures.

The builder enumerates every listed proposed window against every occupied
regular SPW in one physical row. Two proposed windows and four SPWs produce
eight attempts. Repeated target names, project codes or identical row values
do not merge physical rows. Out-of-band, TDM and unresolved-mode attempts
remain present; no coverage or mode filter runs during preparation.

## Bound candidate evidence

| Evidence | Source and interpretation |
| --- | --- |
| Mode | `classify_spw(row, spw_number)` with complete adapter provenance |
| SKY centre and interval | The selected QueueSpw's existing frequency derivation and usable bounds |
| Usable bandwidth | The selected SPW's versioned nominal-to-usable mapping |
| Spectral resolution | The same `Spec.Res. SPW N`, preserving its raw MHz token |
| Reference sensitivity | The owning row's complete Req.Sensitivity, Ref.Frequency and Ref.Freq.Width triplet |
| Angular resolution | The owning row's Req. Ang. Res. |
| Proposed line | Existing `prepare_line_window` with sensitivity declarations from the same setup/window |

Mode derivation reuses `queue_mode_evidence_adapter_2`; its FDM/TDM/UNKNOWN
value is evidence, not a formal LINE-FDM criterion outcome. Geometry and
requested-array applicability remain separate diagnostics.

The sensitivity binding is `SAME_ROW_REFERENCE_TRIPLET_NOT_SPW_RMS`. This
retains the input basis for later Queue normalization without asserting that
the row's requested RMS is already the RMS at every SPW or proposed resolution.
Raw mJy quantities are not relabelled mJy/beam, and no Archive 10-km/s basis is
introduced. No spectral smoothing or angular correction runs in this increment.

Candidate evidence is a preparation snapshot. Criterion consumers must resolve
the reference again against the owning context, rather than combining detached
report scalars. Doppler normalization and usable-width construction are reused
from ingestion; the builder does not repeat or replace those derivations.

## Preparation states and scope

| Condition | Preparation behavior |
| --- | --- |
| Missing or ambiguous proposed RMS declaration | Retain the pair and independent candidate evidence; record the preparation reason |
| Queue mode UNKNOWN | Retain the pair with QUEUE_MODE_UNRESOLVED and the adapter reason |
| Missing usable interval | Record QUEUE_USABLE_INTERVAL_REQUIRED; no nominal-coverage substitution |
| Zero reference-frequency sentinel | Retain the raw value and QUEUE_REFERENCE_FREQUENCY_UNRESOLVED; no beam-frequency fallback |
| Unsupported geometry or requested TP scope | Retain regular-SPW diagnostic attempts with scope reasons; no scientific outcome |
| Spectral scan | Return SPECTRAL_SCAN_NOT_EXPANDED with no fabricated regular SPWs |
| LINE not selected | Return LINE_NOT_SELECTED with no attempts |
| Empty proposed window list | Return NO_PROPOSED_LINE_WINDOWS |
| Incomplete proposed setup | Preserve PROPOSED_ENUMERATION_INCOMPLETE |

`association_status: RESOLVED` means the row/SPW relationship is established.
`evidence_status: AVAILABLE` means no preparation gaps were recorded; it does
not establish criterion approval, applicability or duplication.

`candidate_enumeration_complete` concerns only the regular SPWs in this
successfully parsed physical row. `proposed_enumeration_complete` reflects the
request's `setup_complete` declaration. Neither certifies search completeness,
mode-catalog completeness or a negative duplication result.

The CLI uses strict whole-file Queue context construction. A failed CSV parse
cannot produce a partial report from its surviving rows. Solar requests are
rejected as not applicable before the CSV is read.

## Preparation API

Use a request returned by `validate_proposed_observation` and contexts returned
by successful `build_queue_contexts`:

```python
from alma_duplicate.clients.queue_csv_client import QueueCsvClient
from alma_duplicate.comparison import build_queue_contexts
from alma_duplicate.queue_line_pairing import build_queue_line_pairs

source = build_queue_contexts(QueueCsvClient().load("queue.csv"))
if source.status != "COMPLETE":
    raise ValueError(source.reasons)
for context in source.contexts:
    preparation = build_queue_line_pairs(request, context)
    for attempt in preparation.attempts:
        proposed, candidate = attempt.reference.resolve(request, context)
```

The standalone report has `report_kind: QUEUE_LINE_PREPARATION`. It includes
the normalized request, snapshot metadata, request/parser issues, and every
context's pair references, raw/derived evidence and preparation reasons.

## Offline acceptance

Run from the repository root with Python 3.11 or later:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
python -m pytest -q tests/integration/test_queue_line_pairing.py
python -m alma_duplicate.cli.queue_line_pairs \
  --request examples/queue_line_pairing/request.json \
  --queue-csv examples/queue_continuum/queue.csv \
  --output queue-line-pairs.json
```

Expected: four contexts, four attempts per context, sixteen attempts in total,
and NOT_EVALUATED. These are synthetic preparation checks, not sixteen matches
or independently reviewed real-proposal labels.

The CLI visits all rows in the supplied CSV. Search radius, predicates and
result_limit do not filter or truncate preparation. The output path must not
already exist and its parent directory must exist. Success returns exit code
0; invalid inputs, incomplete ingestion or an existing output return 2.

Regression coverage includes cross-row/snapshot rejection, same-SPW mode and
resolution binding, foreign proposed sensitivity exclusion, missing usable
coverage, REST-to-SKY provenance, unsupported scope, spectral scans, duplicate
identities, strict JSON and offline execution without network access.

Validation at baseline `b1dc21dc9faeff81214435a53771ffb187dbea1f`, Python 3.12.14:
17 pairing tests passed; the offline suite passed 1293 tests with 12 live or
external-snapshot tests deselected. No live Archive query or external snapshot
scientific acceptance is claimed.

```bash
python -m pytest -q -m 'not live and not snapshot'
git diff --check
```

## Evaluator integration boundary

The next increment can implement formal LINE-FDM against the proposed window
and the resolved candidate SPW, using the existing approval/applicability and
criterion-result contracts. Coverage, resolution, Queue RMS normalization and
whole-pair aggregation follow on the same references.

Future Queue LINE evaluation should consume the already computed common
POS-SINGLE and ANGULAR results. This builder does not read or calculate an
antenna diameter. The existing row-beam method and its ABSENT /
PORTAL_HELPER_ASSUMPTION provenance remain unchanged. Resolving the pending
primary-beam interpretation therefore does not require rebuilding line pairing.
