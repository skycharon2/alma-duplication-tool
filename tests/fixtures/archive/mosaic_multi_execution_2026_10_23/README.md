# IC1954 multi-execution evidence

Captured on 2026-10-23 from the official Archive service. The TAP capture returns
one ASDM; the Member auxiliary package contains three original MS listobs and their
three target-only variants. Original files retain their bytes and hashes.

The package audit records three supported IC1954 executions with 22 science fields
each. It is a historical receipt: its execution_file entries refer to generated
outputs in the recorded run, not files included in this fixture. Regenerate them
with the package audit command or replay tests. The full auxiliary tar is excluded.
See docs/archive_mosaic_package_audit.md for scope and reproduction details.
