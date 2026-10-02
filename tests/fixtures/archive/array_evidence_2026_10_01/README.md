# Real Archive array evidence

Five selected real samples, captured by `scripts/capture_archive_array_evidence.py`.
Each sample directory is an existing-format `RecordedArchiveClient` replay:
schema query, count query and full retrieval response, with exact queries,
timestamps, maxrec, counts and SHA-256 in `manifest.json`.

`samples.json` identifies the row used for assertions inside each full cone.
`lookup/` retains the separate targeted query used to select capture coordinates;
it is not part of a production search or a recall test. The two NGC6240 cones
overlap and must not be summed as independent observation populations.

`supporting/` contains original official AQ responses, two QA2 PDFs and their
public README files. Manifests pin URLs, query bodies, times and file digests.
AQ queries return all sources within each selected Member OUS, so the fixtures
preserve differences between science-target and calibrator array labels.
The public site's API credential is not stored. The optional source-bound
Archive array adapter loads `supporting/aq-manifest.json`; QA2 PDFs and README
files remain documentary evidence only. The legacy TAP-only evaluator ignores
these supplemental records. Mixed-beam numerical acceptance uses separately
marked synthetic tests, not altered versions of these real responses.

See the [review](../../../../docs/evidence/archive_array_review_2026-10-02.md)
and [diameter boundary](../../../../docs/archive_array_evidence.md).
These are captured engineering examples, not independently reviewed real
proposal outcomes. Test requests at the captured coordinates are constructed.
Preserve existing bytes; future refreshes belong in a new dated directory.
