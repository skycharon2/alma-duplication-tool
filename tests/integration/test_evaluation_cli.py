"""Offline CLI tests; production code does not import test helpers."""
import json
import os
from pathlib import Path
import subprocess
import sys

from alma_duplicate.cli.evaluate import main
from alma_duplicate.reporting import report_document
from alma_duplicate.rules.evaluation import evaluate_candidate_search
from tests.integration.test_context_rule_evaluation import sample
from tests.integration.test_candidate_search import queue_rows, SpyClient
from tests.integration.test_search_plan_spatial import archive
from alma_duplicate.search_plan import build_search_plan
from alma_duplicate.request_validation import validate_proposed_observation

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "tests/fixtures/queue/queue_pipeline_v1.csv"


def request_file(tmp_path, sources):
    payload = json.loads(
        (ROOT / "examples/proposed_observation.json").read_text()
    )
    payload["search_options"]["sources"] = sources
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload))
    return path, payload


def test_default_does_not_create_archive_client_and_reports_missing_source(tmp_path):
    request, _ = request_file(tmp_path, ["ARCHIVE", "QUEUE"])
    output = tmp_path / "report.json"

    def forbidden():
        raise AssertionError("Network client must not be created")

    code = main([
        "--request", str(request), "--queue-csv", str(QUEUE),
        "--output", str(output),
    ], archive_client_factory=forbidden)
    assert code == 3
    data = json.loads(output.read_text())
    assert data["sources"]["ARCHIVE"]["status"] == "NOT_PROVIDED"
    assert data["sources"]["QUEUE"]["status"] == "COMPLETED"
    assert data["assessment"] == "NOT_AGGREGATED"
    assert len(data["input_sha256"]) == 64


def test_live_flag_uses_injected_fake_and_preserves_query(tmp_path):
    request, payload = request_file(tmp_path, ["ARCHIVE", "QUEUE"])
    v = validate_proposed_observation(
        payload["request"], payload["search_options"]
    )
    result, _ = archive(build_search_plan(v))
    client = SpyClient(result)
    output = tmp_path / "report.json"
    code = main([
        "--request", str(request), "--queue-csv", str(QUEUE),
        "--live-archive", "--output", str(output),
    ], archive_client_factory=lambda: client)
    assert code == 0 and len(client.calls) == 1
    data = json.loads(output.read_text())
    metadata = data["sources"]["ARCHIVE"]["source_metadata"]
    assert metadata["provenance"]["retrieval_adql"]
    assert data["sources"]["ARCHIVE"]["query_binding"]["status"] == "MATCHED"


def test_source_failure_still_writes_other_source_report(tmp_path):
    request, _ = request_file(tmp_path, ["ARCHIVE", "QUEUE"])
    output = tmp_path / "report.json"
    code = main([
        "--request", str(request), "--queue-csv", str(QUEUE),
        "--live-archive", "--output", str(output),
    ], archive_client_factory=lambda: SpyClient(error=RuntimeError("fake failure")))
    assert code == 3
    data = json.loads(output.read_text())
    assert data["sources"]["ARCHIVE"]["status"] == "FAILED"
    assert data["sources"]["QUEUE"]["status"] == "COMPLETED"


def test_invalid_json_does_not_write_report(tmp_path):
    request = tmp_path / "bad.json"
    request.write_text('{"request": NaN}')
    output = tmp_path / "report.json"
    assert main(["--request", str(request), "--output", str(output)]) == 2
    assert not output.exists()


def test_input_cannot_be_overwritten(tmp_path):
    request, _ = request_file(tmp_path, ["QUEUE"])
    original = request.read_bytes()
    assert main([
        "--request", str(request), "--output", str(request), "--overwrite",
    ]) == 2
    assert request.read_bytes() == original


def test_report_preserves_all_contexts_despite_display_limit():
    search = sample(limit=1, q=queue_rows({}, {"RA": ".1"}))
    document = report_document(evaluate_candidate_search(search))
    assert document["evaluation_scope"]["shown_candidates"] == 1
    assert document["evaluation_scope"]["evaluated_contexts"] == 3
    assert len(document["context_evaluations"]) == 3
    for item in document["context_evaluations"]:
        assert item["reference"]["raw_row_id"]
        assert item["criteria"][0]["eligible_for_formal_aggregation"] == (item["reference"]["source"] == "ARCHIVE")


def test_module_runs_from_another_working_directory(tmp_path):
    request, _ = request_file(tmp_path, ["QUEUE"])
    output = tmp_path / "report.json"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run([
        sys.executable, "-m", "alma_duplicate.cli.evaluate",
        "--request", str(request), "--queue-csv", str(QUEUE),
        "--output", str(output),
    ], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["report_version"] == "2"


def test_spatial_report_does_not_repeat_whole_source_records():
    search = sample(q=queue_rows({}, {"RA": ".1"}))
    document = report_document(evaluate_candidate_search(search))
    for source in document["sources"].values():
        for row in source["rows"]:
            spatial = row["spatial_evidence"]
            assert spatial["context_id"] == row["context_id"]
            assert "source_record" not in spatial
            assert "context" not in spatial


def test_duplicate_json_keys_are_rejected(tmp_path):
    request = tmp_path / "duplicate.json"
    request.write_text('{"request": {}, "request": {}, "search_options": {}}')
    output = tmp_path / "report.json"
    assert main(["--request", str(request), "--output", str(output)]) == 2
    assert not output.exists()


def test_invalid_request_returns_validation_errors(tmp_path, capsys):
    request, payload = request_file(tmp_path, ["QUEUE"])
    payload["search_options"]["radius"] = {"value": -1, "unit": "arcsec"}
    request.write_text(json.dumps(payload))
    output = tmp_path / "report.json"
    assert main(["--request", str(request), "--output", str(output)]) == 2
    assert not output.exists()
    assert json.loads(capsys.readouterr().err)["error"] == "REQUEST_NOT_SEARCH_READY"
