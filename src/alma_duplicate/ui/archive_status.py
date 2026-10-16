"""Present recorded Archive retrieval state without probing remote services."""
from urllib.parse import urlsplit

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS

REGIONS = dict(zip(ARCHIVE_ORIGINS, ("Europe", "East Asia", "North America")))


def _region(url):
    if not isinstance(url, str):
        return "Not recorded"
    try:
        parsed = urlsplit(url)
        return REGIONS.get(f"{parsed.scheme}://{parsed.netloc}", "Other / unrecognized endpoint")
    except ValueError:
        return "Unrecognized endpoint"


def _stage(name, status, provenance, endpoint):
    attempts = provenance.get("mirror_attempts") or []
    complete = status == "COMPLETED"
    switched = complete and len(attempts) > 1
    return {
        "name": name,
        "label": {"COMPLETED": "Completed", "FAILED": "Unavailable", "INCOMPLETE": "Incomplete",
                  "SKIPPED": "Not queried", "NOT_PROVIDED": "Not configured"}.get(status, "Not recorded"),
        "tone": "ready" if complete else "neutral" if status == "SKIPPED" else "warning",
        "region": _region(endpoint), "switched": switched,
        "attempts": [{"region": _region(a.get("origin")), "status": a.get("status"),
                      "error": a.get("error"), "finished_at": a.get("finished_at")}
                     for a in attempts],
    }


def archive_run_status(document):
    source = (document.get("sources") or {}).get("ARCHIVE")
    if not source or source.get("status") == "NOT_SELECTED":
        return None
    if source.get("replay"):
        return {"label": "Recorded data", "tone": "neutral", "stages": [],
                "note": "This report used recorded Archive data. No live mirror availability was checked."}
    provenance = (source.get("source_metadata") or {}).get("provenance") or {}
    stages = [_stage("Candidate search (TAP)", source.get("status"), provenance, provenance.get("endpoint"))]
    acquisition = (source.get("array_evidence") or {}).get("acquisition") or {}
    if acquisition:
        stages.append(_stage("Array evidence (AQ)", acquisition.get("status"), acquisition,
                             acquisition.get("properties_url")))
    warning = any(s["tone"] == "warning" for s in stages)
    return {"label": "Needs attention" if warning else "Retrieval completed",
            "tone": "warning" if warning else "ready", "stages": stages,
            "note": "Recorded for this assessment only; this is not a live service health check. "
                    "Retrieval success does not establish that there is no duplication."}


def archive_configuration_status(kind):
    if kind == "LIVE":
        return {"label": "Not checked · automatic fallback enabled", "tone": "neutral", "stages": [],
                "note": "When you run an Archive assessment, try Europe → East Asia → North America. "
                        "The report shows the sites actually used for TAP and, when enabled, AQ. "
                        "Opening this page does not contact the Archive."}
    return {"label": "Recorded data" if kind == "REPLAY" else "Not configured",
            "tone": "neutral", "stages": [],
            "note": "Live mirror availability has not been checked. Automatic switching applies to live retrieval only."}
