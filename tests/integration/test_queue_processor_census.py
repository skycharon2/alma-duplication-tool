import hashlib
import json
from pathlib import Path

from alma_duplicate.cli.queue_processor_census import main, run

FIXTURE = Path(__file__).parents[1] / "fixtures/queue/queue_pipeline_v1.csv"


def test_report_is_reproducible_and_preserves_denominator(tmp_path):
    first = run(FIXTURE, tmp_path / "first")
    second = run(FIXTURE, tmp_path / "second")
    assert first == second
    rows = json.loads((tmp_path / "first/spws.json").read_text())
    assert len(rows) == first["denominator"]["regular_spws"]
    for view in first["views"].values():
        assert sum(view[k] for k in ("FDM", "TDM", "UNKNOWN")) == len(rows)
    assert first["scientific_closure"] == "NOT_ESTABLISHED"
    for name, digest in first["artifacts_sha256"].items():
        assert hashlib.sha256((tmp_path / "first" / name).read_bytes()).hexdigest() == digest
    assert all(v["formal_mode"] == "UNKNOWN" for r in rows for v in r["views"].values())


def test_cli_pin_and_existing_directory(tmp_path):
    output = tmp_path / "report"
    args = ["--queue-csv", str(FIXTURE), "--output-dir", str(output)]
    assert main(args + ["--require-pinned-snapshot"]) == 2
    assert not output.exists()
    assert main(args) == 0
    before = (output / "summary.json").read_bytes()
    assert main(args) == 2
    assert (output / "summary.json").read_bytes() == before
