"""Archive single-field candidates use the proposed Mosaic majority rule."""

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alma_duplicate.assessment import (
    assess_observation,
    AssessmentSources,
    ArchiveInput,
)
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.proposed_mosaic import import_proposed
from alma_duplicate.rules.mosaic_context import evaluate_mosaic_context
from tests.integration.test_search_plan_spatial import validation, archive
from alma_duplicate.search_plan import build_search_plan


def case(positions=(0.0, 0.001, 0.002, 1.0, 2.0), **changes):
    v = validation(sources=("ARCHIVE",))
    metadata, context = archive(build_search_plan(v), **changes)
    request = replace(v.request, geometry="MOSAIC", target_name="test Mosaic")
    proposed = import_proposed(
        (
            "RA,Dec,Coordinate Type,Coordinate Units\n--\n"
            + "\n".join(f"{ra},0,Absolute,Degrees" for ra in positions)
        ).encode(),
        source_name=request.target_name,
        array="12m",
        confirm_fixed_icrs=True,
        confirm_complete=True,
    )
    array = SimpleNamespace(
        context_id=context.context_id,
        source_record_id=context.reference.source_record_id,
        diameters_m=(12.0,),
    )
    return metadata, context, request, proposed, array


@pytest.mark.parametrize(
    "positions,outcome",
    [
        ((0.0, 0.001, 0.002, 1.0, 2.0), "SATISFIED"),
        ((0.0, 0.001, 1.0, 2.0), "NOT_SATISFIED"),
        ((1.0, 2.0, 3.0), "NOT_SATISFIED"),
    ],
)
def test_strict_majority_uses_single_circle(positions, outcome):
    metadata, context, request, proposed, array = case(positions)
    r = evaluate_mosaic_context(
        request, context, proposed, archive_result=metadata, array_evidence=array
    )
    assert r["criteria"][1].outcome == outcome
    assert len(r["coverage"]["circles"]) == 1
    assert r["coverage"]["coverage_scope"] == "SINGLE_ARCHIVE_CONTEXT_NOT_WHOLE_MEMBER"
    assert "POS-MOSAIC" in r["branches"][0].required_criteria


@pytest.mark.parametrize("missing", ["coordinate_unit", "array", "source", "geometry"])
def test_missing_evidence_never_becomes_negative(missing):
    metadata, context, request, proposed, array = case(
        (10.0,), mosaic="" if missing == "geometry" else "F"
    )
    if missing == "coordinate_unit":
        metadata = replace(
            metadata,
            field_metadata=tuple(
                replace(f, unit=None) if f.name == "s_ra" else f
                for f in metadata.field_metadata
            ),
        )
        from alma_duplicate.comparison import build_archive_contexts

        context = build_archive_contexts(metadata).contexts[0]
    if missing == "array":
        array = None
    if missing == "source":
        metadata = None
    r = evaluate_mosaic_context(
        request, context, proposed, archive_result=metadata, array_evidence=array
    )
    assert r["criteria"][1].outcome is None
    assert r["criteria"][1].issues


def test_boundary_and_unconfirmed_proposal():
    metadata, context, request, proposed, array = case((0.0,))
    r = evaluate_mosaic_context(
        request, context, proposed, archive_result=metadata, array_evidence=array
    )
    radius = r["coverage"]["circles"][0]["radius_arcsec"]
    proposed["points"][0]["ra_deg"] = radius / 3600
    r = evaluate_mosaic_context(
        request, context, proposed, archive_result=metadata, array_evidence=array
    )
    assert r["criteria"][1].reasons == ("MOSAIC_BOUNDARY_COUNT_UNRESOLVED",)
    proposed["completeness"] = "NOT_CONFIRMED"
    r = evaluate_mosaic_context(
        request, context, proposed, archive_result=metadata, array_evidence=array
    )
    assert r["criteria"][1].reasons == ("PROPOSED_POINTING_COMPLETENESS_REQUIRED",)


@pytest.mark.parametrize(
    "aq_failure,corrupt_package", [(False, False), (True, False), (False, True)]
)
def test_main_automatic_single_route_never_downloads_listobs(
    tmp_path, monkeypatch, aq_failure, corrupt_package
):
    from alma_duplicate.archive_array_evidence import (
        ArchiveArrayCatalog,
        ArchiveArrayCatalogProvenance,
        ArchiveArrayCatalogMode,
        ArrayRecord,
    )
    from alma_duplicate.clients.archive_aq_client import (
        ArchiveAqClient,
        ArchiveAqFetchResult,
        ArchiveAqMemberQuery,
    )
    import alma_duplicate.mosaic_candidate_discovery as discovery
    import alma_duplicate.mosaic_candidate_preparation as preparation

    metadata, context, request, proposed, _ = case()
    raw = context.evidence.prepared.raw_row
    member, source = raw["member_ous_uid"], raw["target_name"]
    row = tuple(
        str(raw[k])
        for k in (
            "proposal_id",
            "member_ous_uid",
            "asdm_uid",
            "target_name",
            "science_observation",
            "is_mosaic",
        )
    )
    from xml.sax.saxutils import escape

    names = (
        "proposal_id",
        "member_ous_uid",
        "asdm_uid",
        "target_name",
        "science_observation",
        "is_mosaic",
    )
    response = (
        '<VOTABLE xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE type="results">'
        '<INFO name="QUERY_STATUS" value="OK"/><TABLE>'
        + "".join(f'<FIELD name="{n}"/>' for n in names)
        + "<DATA><TABLEDATA><TR>"
        + "".join(f"<TD>{escape(v)}</TD>" for v in row)
        + "</TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"
    ).encode()
    monkeypatch.setattr(discovery, "_fetch", lambda url: (200, response))

    def forbidden(*args, **kwargs):
        pytest.fail("Single-field candidates must not acquire Mosaic packages")

    monkeypatch.setattr(preparation, "capture_inventory", forbidden)
    monkeypatch.setattr(preparation, "discover_archive_products", forbidden)
    record = ArrayRecord(
        f"{member}.source.{source}",
        member,
        source,
        "12m",
        "test-hash",
        "2026-10-26T00:00:00+00:00",
        "https://almascience.eso.org/aq/service/api/search/observations/_search",
    )
    catalog = ArchiveArrayCatalog(
        (record,), ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.LIVE)
    )
    fetched = ArchiveAqFetchResult(
        catalog,
        (
            ArchiveAqMemberQuery(
                member, record.url, record.retrieved_at, record.response_sha256, 1, 100
            ),
        ),
    )

    def fetch(self, members):
        if aq_failure:
            raise OSError("simulated AQ outage")
        return fetched

    monkeypatch.setattr(ArchiveAqClient, "fetch_members", fetch)
    payload = json.loads(Path("examples/proposed_observation.json").read_text())
    payload["request"].update(geometry="MOSAIC", target_name=request.target_name)
    payload["request"].pop("position")
    payload["search_options"].update(sources=["ARCHIVE"], predicates=[])

    def search(spec):
        assert (spec.member_ous_uid, spec.target_name) == (member, source)
        return metadata

    if corrupt_package:
        import alma_duplicate.mosaic_backend as backend

        real_prepare = backend.prepare_candidates

        def corrupt(*args, **kwargs):
            report = real_prepare(*args, **kwargs)
            report["candidates"][0].update(
                package_audit_dir=str(tmp_path / "missing-package"),
                readiness_file=str(tmp_path / "missing-readiness.json"),
            )
            return report

        monkeypatch.setattr(backend, "prepare_candidates", corrupt)
    r = assess_observation(
        payload["request"],
        payload["search_options"],
        sources=AssessmentSources(
            "LIVE", lambda: ArchiveInput(SimpleNamespace(search=search))
        ),
        mosaic=MosaicAssessmentInput(
            proposed, tmp_path / "run", tmp_path / "cache", 1.0
        ),
    )
    assert r.status == (
        "SOURCES_UNAVAILABLE" if aq_failure or corrupt_package else "COMPLETED"
    )
    c = r.document["candidates"][0]
    if aq_failure:
        assert c["preparation"]["readiness_status"] == "UNAVAILABLE"
        assert c["evaluation"]["contexts"][0]["criteria"][1]["outcome"] is None
    else:
        assert c["preparation"]["status"] == "METADATA_ONLY_PREPARED"
        assert c["evaluation"]["contexts"][0]["criteria"][1]["outcome"] == "SATISFIED"
    assert not list((tmp_path / "run").rglob("package"))
