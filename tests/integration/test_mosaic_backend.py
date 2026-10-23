"""Common entrypoint to metadata ingestion, verified listobs and shared rules."""

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alma_duplicate.assessment import (
    assess_observation,
    ArchiveInput,
    AssessmentSources,
)
from alma_duplicate.mosaic_backend import MosaicAssessmentInput
from alma_duplicate.archive_array_evidence import load_archive_array_catalog
from alma_duplicate.archive_mosaic_readiness import build_readiness
from alma_duplicate.archive_mosaic_pointings import load_package_executions
from alma_duplicate.proposed_mosaic import import_proposed
from tests.unit.test_archive_mosaic_pointings import package as package
from tests.integration.test_archive_pipeline_fixture import _complete_query_result


@pytest.mark.parametrize("full_preparation", [False, True])
def test_main_entrypoint_metadata_and_real_package_reconstruction(
    tmp_path, monkeypatch, package, full_preparation
):
    import alma_duplicate.mosaic_backend as backend

    executions, _ = load_package_executions(package)
    member, source = executions[0]["member_ous_uid"], executions[0]["source_name"]
    catalog = load_archive_array_catalog(
        Path("tests/fixtures/archive/mosaic_array_2026_10_23/manifest.json")
    )
    readiness = build_readiness(package, catalog=catalog)
    readiness_path = tmp_path / "readiness.json"
    readiness_path.write_text(json.dumps(readiness))
    field = executions[0]["evidence"]["fields"][0]
    proposed = import_proposed(
        (
            "RA,Dec,Coordinate Type,Coordinate Units\n--\n"
            f"{field['ra_deg']},{field['dec_deg']},Absolute,Degrees\n"
        ).encode(),
        source_name="synthetic acceptance proposal",
        array="7m",
        confirm_fixed_icrs=True,
        confirm_complete=True,
    )
    payload = json.loads(Path("examples/proposed_observation.json").read_text())
    payload["request"].update(geometry="MOSAIC", target_name=proposed["source_name"])
    payload["request"].pop("position")
    payload["search_options"]["sources"] = ["ARCHIVE"]
    payload["search_options"]["predicates"] = []
    base = _complete_query_result()
    # Synthetic metadata identities, real captured coordinates. No live-science claim.
    rows = tuple(
        dict(
            base.rows[0],
            member_ous_uid=member,
            target_name=source,
            asdm_uid=e["asdm_uid"],
            obs_id=f"{member}.source.{source}.spw.0",
            is_mosaic="T",
            antenna_arrays="7-m",
        )
        for e in executions
    )
    metadata = replace(
        base,
        rows=rows,
        provenance=replace(
            base.provenance, expected_count=len(rows), retrieved_count=len(rows)
        ),
    )
    calls = []

    def search(spec):
        calls.append(spec)
        assert (spec.member_ous_uid, spec.target_name) == (member, source)
        return metadata

    def discover(*args, **kw):
        return dict(
            schema_version="mosaic_candidate_discovery_1",
            status="COMPLETED",
            plan=dict(recall_status="NOT_ESTABLISHED"),
            candidates=[
                dict(context_id="test", member_ous_uid=member, source_name=source)
            ],
        )

    def prepare(*args, **kw):
        return dict(
            status="COMPLETED",
            candidates=[
                dict(
                    member_ous_uid=member,
                    source_name=source,
                    directory=str(tmp_path),
                    package_audit_dir=str(package),
                    readiness_file=str(readiness_path),
                )
            ],
        )

    monkeypatch.setattr(backend, "discover_candidates", discover)
    if full_preparation:
        from tests.unit.test_archive_mosaic_package_audit import run
        from tests.unit.test_mosaic_candidate_preparation import inventory, products
        from alma_duplicate.mosaic_candidate_preparation import prepare_candidates
        from alma_duplicate.archive_array_evidence import (
            ArchiveArrayCatalogProvenance,
            ArchiveArrayCatalogMode,
        )
        from alma_duplicate.clients.archive_aq_client import (
            ArchiveAqFetchResult,
            ArchiveAqMemberQuery,
        )

        run(
            tmp_path, monkeypatch
        )  # Construct a tar from captured listobs at the download boundary.
        live = replace(
            catalog,
            provenance=ArchiveArrayCatalogProvenance(ArchiveArrayCatalogMode.LIVE),
        )
        record = live.records[0]
        fetched = ArchiveAqFetchResult(
            live,
            (
                ArchiveAqMemberQuery(
                    member,
                    record.url,
                    record.retrieved_at,
                    record.response_sha256,
                    len(live.records),
                    100,
                ),
            ),
        )

        def prepare(discovery, **kw):
            return prepare_candidates(
                discovery,
                **kw,
                inventory_capture=inventory,
                product_discovery=products,
                array_fetcher=lambda members: fetched,
            )

    monkeypatch.setattr(backend, "prepare_candidates", prepare)
    result = assess_observation(
        payload["request"],
        payload["search_options"],
        sources=AssessmentSources(
            "LIVE",
            lambda: ArchiveInput(SimpleNamespace(search=search), array_catalog=catalog),
        ),
        mosaic=MosaicAssessmentInput(
            proposed, tmp_path / "run", tmp_path / "cache", 1.0
        ),
    )
    assert result.validation.can_search
    assert result.status == "COMPLETED"
    assert len(calls) == 1
    candidate = result.document["candidates"][0]
    contexts = candidate["evaluation"]["contexts"]
    assert len(contexts) == 3
    for context in contexts:
        assert context["criteria"][1]["outcome"] == "SATISFIED"
        assert len(context["coverage"]["circles"]) == 66
        assert context["coverage"]["inside_count"] == 1
        assert context["coverage"]["frequency_source"] == "ARCHIVE_CONTEXT_FREQUENCY"
        assert "POS-MOSAIC" in context["branches"][0]["required_criteria"]
    assert (tmp_path / "run/assessment.json").exists()


def test_member_metadata_query_is_exact_and_escaped():
    from alma_duplicate.clients.archive_queries import (
        ArchiveQuerySpec,
        build_where_clause,
        normalize_query_parameters,
    )

    spec = ArchiveQuerySpec(
        0, 0, 180, member_ous_uid="uid://A001/X1/X2", target_name="O'Brien"
    )
    where = build_where_clause(spec)
    assert "target_name = 'O''Brien'" in where
    assert "INTERSECTS" not in where
    assert (
        dict(normalize_query_parameters(spec))["member_ous_uid"] == spec.member_ous_uid
    )
    with pytest.raises(ValueError):
        ArchiveQuerySpec(0, 0, 180, member_ous_uid="M")
