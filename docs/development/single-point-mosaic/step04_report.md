# Step 04: Single Pointing report and Explore for Mosaic candidates

The report explains the recorded region classification and adopted half-power
coverage source. Explore reads the region and SHA-256 from the same saved
`POS-SINGLE` criterion, checks context/reference identity, and validates the
region with the scientific parser. It does not fetch replacement metadata or
recalculate a duplication verdict.

Aladin displays a closed sampled spherical boundary; circles are sampled on the
sphere and polygons along minor great-circle arcs. The same outline feeds the
charts and offline sky fallback. A region display reference is labelled separately
from a recorded observation center; no Mosaic central beam, diameter, or
separation/radius ratio is invented. Invalid, mismatched or hemisphere-unprojectable
geometry is explicitly unavailable rather than replaced with a circular beam.

Explore retains its existing matched-comparison selection. Nonmatching and
unknown contexts remain in the report, not promoted into Explore matches.
Downloads remain byte-identical. Existing single-field and Queue beam drawings
are unchanged. Sampled outlines are display approximations; saved formal results
remain authoritative at a boundary.

Offline acceptance includes backend-to-report-to-Explore routes, immutable report
downloads, wrap/polar outlines, evidence checksum/context rejection and JavaScript
region rendering. Live TAP discovery performance and real browser/HiPS image
availability are separate external acceptance checks, not certified by these tests.
