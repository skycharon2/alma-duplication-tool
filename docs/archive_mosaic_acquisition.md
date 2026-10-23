# Archive Auxiliary Acquisition and Listobs Inspection

## Scope

This increment downloads an explicitly selected Member auxiliary tar, validates and
reuses a local cache, and locates listobs evidence for one ASDM and target. It uses
the existing parser to validate candidates but does not create a complete Member
Mosaic or perform duplication assessment. Single Pointing execution is unchanged.

The acquisition entry is `archive_auxiliary.acquire_listobs()`. Its inputs are a
saved discovery receipt, an explicit zero-based product row, cache and output
locations, ASDM UID, target name, and an optional offline flag. The CLI exposes the
same operation. Product discovery remains a separate step.

## Verified 7m route

The package-level DataLink service lists individual products, including a directly
addressable weblog tarball. The implemented route currently uses the previously
selected complete auxiliary tar (56,154,112 bytes), preserving its Member-level
association. Direct weblog acquisition is not implemented in this increment.

The observed nesting is:

```text
2021.2.00176.S_uid___A001_X15aa_Xe5_auxiliary.tar
  .../qa/member.uid___A001_X15aa_Xe5.hifa_calimage_renorm.weblog.tgz
    pipeline-20220718T122852/html/sessionsession_2/
      uid___A002_Xfb8480_X4f37.ms/listobs.txt
      uid___A002_Xfb8480_X4f37_target.ms/listobs.txt
```

The exact MS header selects the first candidate; the `_target.ms` file remains
listed as another measurement set. The matched file contains 19 science fields.
All parsed field values, including scan/SPW associations, match the prior local
reference. The downloaded plain text and the older Markdown-wrapped reference
have different raw hashes, as expected.

Original listobs bytes, acquisition evidence, and comparison results are retained
in `tests/fixtures/archive/mosaic_auxiliary_2026_10_23/`. The full downloaded package
remains in the ignored local cache. Package-level metadata inspection identified
the route but is not currently followed automatically.

## Run

From the repository root in the installed project environment:

```bash
mkdir -p reports/mosaic-dev

python -m alma_duplicate.cli.archive_auxiliary \
  --receipt tests/fixtures/archive/mosaic_products_2026_10_23/7m/discovery.json \
  --product-row 3 \
  --asdm uid://A002/Xfb8480/X4f37 \
  --source SPT0303-59 \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/7m-listobs-01
```

Expected status: `FOUND`. A valid cache is reused; otherwise the command downloads
the selected auxiliary product. Each output directory must be new. Offline replay:

```bash
python -m alma_duplicate.cli.archive_auxiliary \
  --receipt tests/fixtures/archive/mosaic_products_2026_10_23/7m/discovery.json \
  --product-row 3 \
  --asdm uid://A002/Xfb8480/X4f37 \
  --source SPT0303-59 \
  --cache data/cache/archive-auxiliary \
  --output-dir reports/mosaic-dev/7m-listobs-offline-01 \
  --offline
```

Each output retains `acquisition.json`, the discovery receipt, and its original
response. `listobs.txt` is written only for a unique validated match. Acquisition
records include download times, URL, size, SHA-256, cache reuse, archive paths,
candidate outcomes, and inspection scope. Local preflight errors can occur before
a receipt is written; an output directory is never overwritten.

Exit codes: 0 for FOUND, 3 for failed or unresolved acquisition/inspection, and 2
for local argument or preflight errors.

## Integrity and limits

- Reparse the original discovery response after checking its saved size and hash.
  Select a row from that response rather than trusting copied product metadata.
- Require a usable auxiliary row, an official HTTPS dataPortal tar URL, and scope
  agreement when the discovery receipt already identifies an ASDM.
- Cap downloads at 300 MB, with a 30-second socket timeout and a 180-second elapsed
  budget checked between reads. A blocked read may exceed the elapsed budget until
  its socket timeout expires. Redirects are disabled.
- Validate advertised and HTTP sizes when present. Publish downloads without
  overwriting existing cache entries, then save their manifest. Partial downloads
  are removed. An interrupted publication may leave an incomplete entry, which is
  rejected on reuse. Existing cache entries are checked by size and SHA-256.
- Inspect archives in memory without extracting archive paths into the filesystem.
  Reject absolute paths, parent traversal, duplicate paths, and linked candidate
  files. Unrelated nonregular entries are recorded and never followed.
- Traverse nested archives only when their basename contains `weblog`. Other
  packages are explicitly outside scope. Inspect direct listobs candidates too.
- Bound nesting to two nested levels, total inspected entries to 20,000, summed
  declared member sizes to 1 GB, each regular member to 100 MB, each listobs to
  5 MB, and candidate count to 100. These are implementation limits, not scientific
  completeness guarantees.

Multiple matches return `AMBIGUOUS`. Malformed candidate headers or a matching MS
that fails parsing return `UNRESOLVED_CANDIDATES`. `NOT_FOUND` means no match within
the declared inspection scope, not that the observation has no pointings.

Cache hashes establish local consistency, not cryptographic authenticity of the
remote dataset. This release has been exercised online only for the 7m case.
A found listobs establishes neither the complete execution inventory nor a general
mapping between FIELD centres and approved Mosaic coverage.

## Validation

```bash
python -m pytest -q tests/unit/test_archive_auxiliary.py
python -m pytest -q
```

Recorded validation on `b6587b0` plus this uncommitted increment: 16 focused
tests passed; the full Python suite completed with 2276 passed and 12 skipped.
Python compilation and tracked diff whitespace checks passed. Ruff was unavailable
in the local environment. The 7m live acquisition and offline replay both returned
FOUND with identical listobs bytes and all 19 science fields matching the earlier
reference.

Tests cover receipt tampering, explicit row selection, nested weblog inspection,
MS distinction, ambiguous and malformed candidates, unsafe members, budget limits,
interrupted downloads, corrupted caches, offline cache misses, output preservation,
CLI output, and the captured 19-field reference comparison. Default tests do not
contact remote services.

## Next step

Extend validation to the independent 12m sample, then connect the acquisition
receipt to execution reconstruction with explicit metadata provenance. Cross-EB
inventory reconciliation remains separate from this package-level operation.
