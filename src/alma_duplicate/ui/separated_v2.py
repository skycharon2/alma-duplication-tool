"""Explicit, opt-in browser runner for Step 04C Archive Single Pointing V2.

Do not route V2 output through the legacy RunStore/inspection, which does not
support report_version=7 yet. The editor renders the returned report in-place;
its separate download action repeats the assessment and returns the full JSON.
"""

from alma_duplicate.submitted_line_assessment import assess_submitted_line_single_v2


def run_single_v2(document, config):
    """Choose an administrator-configured Archive source, never form-supplied paths.

    This does not use Archive AQ/Queue or permit Mosaic. The report itself owns
    candidate-scoped status and source-failure provenance, not a global verdict.
    """
    if config.get("SUBMITTED_LINE_V2_UI_ENABLED") is not True:
        raise ValueError("SUBMITTED_LINE_V2_UI_DISABLED")
    if document["request"].get("geometry") != "SINGLE_POINTING":
        raise ValueError("SUBMITTED_LINE_V2_SINGLE_ONLY")
    if document["request"].get("intents") != ["LINE"]:
        raise ValueError("SUBMITTED_LINE_V2_LINE_ONLY")
    if document["search_options"].get("sources") != ["ARCHIVE"]:
        raise ValueError("SUBMITTED_LINE_V2_ARCHIVE_ONLY")
    if config.get("LIVE_AQ"):
        raise ValueError("SUBMITTED_LINE_V2_AQ_NOT_SUPPORTED")

    replay = config.get("OFFLINE_ARCHIVE_REPLAY")
    live = config.get("LIVE_ARCHIVE") is True
    if bool(replay) == live:
        raise ValueError("SUBMITTED_LINE_V2_REQUIRES_ONE_ARCHIVE_SOURCE")
    if live:
        from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
        from alma_duplicate.clients.archive_mirrors import MirroredArchiveClient
        client = MirroredArchiveClient(
            origins=ARCHIVE_ORIGINS, completeness_policy="STATUS_THEN_COUNT",
        )
    else:
        from alma_duplicate.clients.archive_replay import RecordedArchiveClient
        client = RecordedArchiveClient(replay)
    return assess_submitted_line_single_v2(
        document["request"], document["search_options"], archive_client=client,
    )
