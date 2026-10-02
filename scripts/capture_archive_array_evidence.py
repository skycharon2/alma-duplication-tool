"""Capture bounded real Archive array examples; never assign scientific labels.

Run explicitly with --live --output NEW_DIRECTORY. Each cone uses the production
Archive client and can be replayed by RecordedArchiveClient without a network.
The identifier lookup selects an investigation location, not a retrieval filter.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path

import requests
from astropy.io.votable import parse
from pyvo.dal import TAPResults

from alma_duplicate.clients.archive_client import ArchiveClient, PyvoTapExecutor
from alma_duplicate.clients.archive_queries import ArchiveQuerySpec

ENDPOINT = "https://almascience.eso.org/tap"
SAMPLES = {
    "pure_12m": ("uid://A001/X5a3/X18c", "ngc6240"),
    "pure_7m": ("uid://A001/X2fa/X245", "NGC_6240"),
    "cm_with_tp": ("uid://A001/X2d20/X2e71", "HD14055"),
    "non_solar_mixed_names": ("uid://A001/X3788/Xc194", "IRAS_09245-5228"),
    "solar": ("uid://A001/X133d/X255b", "Sun_10"),
}


class CaptureService:
    def __init__(self, folder):
        self.folder = folder
        self.responses = []

    def run_sync(self, query, *, maxrec):
        started = datetime.now(UTC).isoformat()
        response = requests.get(ENDPOINT + "/sync", params={
            "REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable",
            "QUERY": query, "MAXREC": maxrec,
        }, timeout=(10, 60))
        response.raise_for_status()
        data = response.content
        result = TAPResults(parse(io.BytesIO(data)))
        name = f"response-{len(self.responses)}.xml"
        (self.folder / name).write_bytes(data)
        self.responses.append({
            "adql": query, "maxrec": maxrec, "file": name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "started_at": started, "finished_at": datetime.now(UTC).isoformat(),
        })
        return result


def capture(output):
    # Refuse to overwrite evidence; refreshes belong in another directory.
    output.mkdir(parents=True, exist_ok=False)
    lookup_dir = output / "lookup"
    lookup_dir.mkdir()
    lookup = CaptureService(lookup_dir)
    clauses = [f"(member_ous_uid = '{uid}' AND target_name = '{target}')"
               for uid, target in SAMPLES.values()]
    query = ("SELECT member_ous_uid, obs_id, target_name, s_ra, s_dec, antenna_arrays, "
             "science_keyword, is_mosaic, asdm_uid FROM ivoa.obscore "
             "WHERE science_observation = 'T' AND (" + " OR ".join(clauses) + ")")
    result = lookup.run_sync(query, maxrec=1000)
    if result.query_status != "OK":
        raise ValueError("Sample lookup is incomplete")
    table = result.to_table()
    (lookup_dir / "manifest.json").write_text(json.dumps({
        "kind": "TARGETED_SAMPLE_LOOKUP", "endpoint": ENDPOINT,
        "responses": lookup.responses,
    }, indent=2) + "\n")
    samples = []
    for name, (uid, target) in SAMPLES.items():
        rows = [r for r in table if str(r["member_ous_uid"]) == uid
                and str(r["target_name"]) == target]
        if not rows:
            raise ValueError(f"Sample missing: {name}")
        row = sorted(rows, key=lambda r: str(r["obs_id"]))[0]
        folder = output / name
        folder.mkdir()
        spec = ArchiveQuerySpec(float(row["s_ra"]), float(row["s_dec"]),
                                1e-6, science_only=True, spatial_strategy="CENTER")
        service = CaptureService(folder)
        client = ArchiveClient(ENDPOINT, maxrec=1000,
                               executor=PyvoTapExecutor(ENDPOINT, service=service))
        source = client.search(spec)
        if not source.is_complete:
            raise ValueError(f"Incomplete cone for {name}: {source.status}")
        if not any(r["obs_id"] == str(row["obs_id"]) for r in source.rows):
            raise ValueError(f"Selected sample absent from captured cone: {name}")
        p = source.provenance
        manifest = {
            "replay_version": "1", "fixture_kind": "CAPTURED_TAP_RESPONSE",
            "endpoint": ENDPOINT, "maxrec": 1000, "query_run_id": p.query_run_id,
            "started_at": p.started_at.isoformat(), "finished_at": p.finished_at.isoformat(),
            "responses": service.responses, "expected_count": p.expected_count,
            "retrieved_count": p.retrieved_count, "status": source.status.value,
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        samples.append({
            "sample_id": name, "member_ous_uid": uid, "target_name": target,
            "obs_id": str(row["obs_id"]), "asdm_uid": str(row["asdm_uid"]),
            "science_keyword": str(row["science_keyword"]),
            "manifest": f"{name}/manifest.json",
            "query_spec": {"ra_deg": spec.ra_deg, "dec_deg": spec.dec_deg,
                           "radius_deg": spec.radius_deg, "science_only": True,
                           "spatial_strategy": "CENTER"},
        })
        print(f"{name}: {len(source.rows)} rows", flush=True)
    (output / "samples.json").write_text(json.dumps({
        "fixture_kind": "CAPTURED_ENGINEERING_EVIDENCE",
        "scope": "Selected narrow cones; not an Archive census or proposal acceptance",
        "samples": samples,
    }, indent=2) + "\n")


def capture_aq(output):
    """Save source-bound official AQ labels as review evidence, not rule inputs.

    The public website supplies its service configuration. Any browser API key is
    kept in memory and is never included in the captured evidence.
    """
    folder = output / "supporting"
    folder.mkdir(exist_ok=False)
    response = requests.get("https://almascience.eso.org/aq/service/api/v1/properties",
                            timeout=(10, 60))
    response.raise_for_status()
    properties = response.json()
    headers = {"Content-Type": "application/json"}
    if properties.get("elasticsearchApiKey"):
        headers["Authorization"] = "ApiKey " + properties["elasticsearchApiKey"]
    url = properties["elasticsearchUrl"] + "/observations/_search"
    # Never forward even the public browser credential to another origin.
    if not url.startswith("https://almascience.eso.org/aq/service/"):
        raise ValueError("Unexpected public AQ service origin")
    entries = []
    for name, (uid, _) in SAMPLES.items():
        body = {"size": 20, "track_total_hits": True,
                "_source": ["mous", "sourceName", "array", "productFiles", "project", "band", "datasetId"],
                "query": {"term": {"mous": uid}}}
        response = requests.post(url, json=body, headers=headers, timeout=(10, 60))
        response.raise_for_status()
        payload = response.json()
        total = payload["hits"]["total"]
        if total["relation"] != "eq" or total["value"] != len(payload["hits"]["hits"]):
            raise ValueError(f"Incomplete AQ response: {name}")
        filename = name + "-aq.json"
        (folder / filename).write_bytes(response.content)
        entries.append({"file": filename, "url": url, "request_body": body,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                        "sha256": hashlib.sha256(response.content).hexdigest()})
    (folder / "aq-manifest.json").write_text(json.dumps(entries, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-aq", action="store_true",
                        help="Also capture official per-source array labels for review")
    args = parser.parse_args()
    capture(args.output)
    if args.include_aq:
        capture_aq(args.output)
