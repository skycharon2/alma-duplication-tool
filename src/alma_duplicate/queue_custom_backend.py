"""Custom CSV coverage restricted to the project-interpreted pointing owner."""
import math
from dataclasses import asdict

from alma_duplicate.queue_pointing_ownership import (
    resolve_custom_pointing_array, LIMITATION_TITLE, LIMITATION_MESSAGE,
)

from alma_duplicate.geometry import primary_beam_fwhm_deg
from alma_duplicate.queue_mosaic import OFFSET_METHOD, reconstruct_queue_mosaics
from alma_duplicate.queue_position import candidate_frequency
from alma_duplicate.rules.queue_mosaic_position import (
    QueueMosaicCoverage, _points, assess_queue_mosaic_position,
)

PROFILE = "QUEUE_CUSTOM_EXPLICIT_CSV_4"
MODEL_STATUS = "PROJECT_ACCEPTED"
MAX_TOTAL_PAIRS = 1_000_000
ASSUMPTIONS = (
    "STRICT_EXPORT_GROUP_AS_COHERENT_CANDIDATE",
    "CSV_EXPLICIT_CENTERS_RESTRICTED_TO_POINTING_OWNER",
    "COVERAGE_SCOPE_ALL_RECORDED_ROWS_IN_THIS_CUSTOM_GROUP",
    "BLANK_COORDINATE_FRAME_USES_ICRS_CONVENTION",
    "FIXED_COORDINATES_WITHOUT_EPHEMERIS_PLACEHOLDER",
)


def assess_queue_custom_csv(parsed, proposed, *, candidate_id=None, boundary_epsilon_arcsec=0.001):
    """Assess one selected or all Custom candidates in a complete CSV snapshot.

    Candidate associations follow the accepted CSV profile. Coverage is scoped to recorded CSV rows.
    Unresolved centres leave the union incomplete. No manual candidate
    binding, OT export, invented ACA grid, or cross-candidate union is required.
    """
    if not isinstance(proposed, dict) or proposed.get("frame_basis") != "USER_CONFIRMED_FIXED_ICRS":
        raise ValueError("Confirmed fixed ICRS proposal required")
    proposed_count = len(_points(proposed.get("points")))
    if (isinstance(boundary_epsilon_arcsec, bool)
            or not isinstance(boundary_epsilon_arcsec, (int, float))
            or not math.isfinite(boundary_epsilon_arcsec)
            or not 0 <= boundary_epsilon_arcsec <= 1):
        raise ValueError("Numerical boundary tolerance must be between 0 and 1 arcsec")
    reconstruction = reconstruct_queue_mosaics(parsed)
    all_candidates = reconstruction["candidates"]
    if candidate_id is None:
        candidates = [c for c in all_candidates if c["geometry_kind"] == "CUSTOM"]
    else:
        candidates = [c for c in all_candidates if c["candidate_id"] == candidate_id]
        if len(candidates) != 1 or candidates[0]["geometry_kind"] != "CUSTOM":
            raise ValueError("Select a Custom candidate from this snapshot")
    if sum(len(c["source_rows"])*proposed_count*len(c["array_inference"]["diameters_m"])
           for c in candidates) > MAX_TOTAL_PAIRS:
        raise ValueError("Custom batch pointing comparison budget exceeded")
    typed = {r.raw_row.row_id.value: r for r in parsed.row_inputs}
    results = []
    for candidate in candidates:
        rows = candidate["source_rows"]
        diameters = candidate["array_inference"]["diameters_m"]
        ownerships = [resolve_custom_pointing_array(typed[r["source_row_id"]]) for r in rows]
        ownership = asdict(ownerships[0])
        if any(o != ownerships[0] for o in ownerships):
            raise ValueError("Custom group has conflicting pointing ownership evidence")
        owned_diameters = {"12M": [12.], "7M": [7.]}.get(ownership['pointing_array'], [])
        frequencies = [candidate_frequency(typed[r["source_row_id"]]) for r in rows]
        frequency, frequency_source, frequency_notes = frequencies[0]
        blockers = []
        if frequency is None or any(f != frequencies[0] for f in frequencies):
            blockers.append("CANDIDATE_FREQUENCY_UNRESOLVED")
        known_rows = [r for r in rows if r["center"]["icrs_deg"] is not None]
        coordinate_notes = ([] if len(known_rows) == len(rows) else
                            ["CUSTOM_CSV_COORDINATES_PARTIALLY_UNRESOLVED"])
        if not known_rows:
            blockers.append("CUSTOM_CSV_COORDINATES_UNRESOLVED")
        if not diameters:
            blockers.append("EXPLICIT_POINT_ARRAY_UNRESOLVED")
        coverages = []
        beam_errors = {}
        if not blockers:
            points = tuple(dict(id=r["source_row_id"], frame="ICRS",
                                ra_deg=r["center"]["icrs_deg"][0], dec_deg=r["center"]["icrs_deg"][1])
                           for r in known_rows)
            for diameter in owned_diameters:
                # Validate only candidate beam data here. Binding, proposal and
                # resource errors must still propagate rather than being hidden.
                try:
                    width = primary_beam_fwhm_deg(frequency, diameter)
                    if width >= 180:
                        raise ValueError("Coverage beam must lie within a hemisphere")
                except ValueError:
                    beam_errors[diameter] = "CANDIDATE_BEAM_UNREPRESENTABLE"
                    continue
                coverages.append(QueueMosaicCoverage(
                    candidate["candidate_id"], reconstruction["snapshot_sha256"],
                    tuple(r["source_row_id"] for r in rows), diameter, frequency,
                    f"{PROFILE}:{frequency_source}", points,
                    f"{PROFILE}:" + ','.join(sorted({r['center'].get('method', OFFSET_METHOD) for r in known_rows})),
                    association_confirmed=True, complete=len(known_rows) == len(rows)))
        # Only the selected source context enters the position evaluator.
        position = assess_queue_mosaic_position(proposed, reconstruction, candidate["candidate_id"],
            coverages, boundary_epsilon_arcsec=boundary_epsilon_arcsec)
        position["coverage_basis"] = "PROJECT_ADOPTED_CUSTOM_POINTING_OWNERSHIP"
        for variant in position["beam_variants"]:
            variant["model_status"] = MODEL_STATUS if variant["outcome"] != "UNKNOWN" else "UNRESOLVED"
            variant["association_basis"] = "PROFILE_CONVENTION_NOT_CALLER_CONFIRMATION"
            variant["geometry_model"] = "CSV_OWNER_CENTERS_ARRAY_SPECIFIC_BEAM_UNION"
            variant["reasons"].extend(blockers + coordinate_notes)
            if variant["diameter_m"] in beam_errors:
                variant["reasons"].append(beam_errors[variant["diameter_m"]])
        ownership['evaluated_arrays'] = [f'{int(c.diameter_m)}M' for c in coverages]
        ownership['unassessed_arrays'] = [a for a in ownership['requested_arrays']
                                          if a not in ownership['evaluated_arrays']]
        for variant in position['beam_variants']:
            if f"{int(variant['diameter_m'])}M" in ownership['unassessed_arrays']:
                variant['reasons'].append('CUSTOM_ARRAY_POINTINGS_UNAVAILABLE')
        limitations = ([dict(code='ACA_7M_POINTINGS_UNAVAILABLE', title=LIMITATION_TITLE,
                            message=(LIMITATION_MESSAGE if '12M' in ownership['evaluated_arrays'] else
                                'The CSV pointings are interpreted as the 12-m Array configuration. '
                                'Corresponding ACA 7-m pointings are unavailable; the 12-m coverage '
                                'also could not be assessed. Both limitations remain unresolved.'))]
                      if ownership['pointing_array'] == '12M' and '7M' in ownership['requested_arrays'] else [])
        results.append(dict(pointing_ownership=ownership, limitations=limitations,candidate_id=candidate["candidate_id"], group=candidate["group"],
            grouping_method=candidate["grouping_method"], association_status=candidate["association_status"],
            source_rows=rows, explicit_point_diameters_m=owned_diameters,
            coverage_completeness=("COMPLETE_FOR_CSV_GROUP" if coverages and
                len(coverages) == len(diameters) and all(c.complete for c in coverages)
                else "NOT_ESTABLISHED"), profile_assumptions=list(ASSUMPTIONS),
            frequency=dict(value_ghz=frequency, source=frequency_source, reasons=list(frequency_notes)),
            position=position))
    selected_ids = {c["candidate_id"] for c in candidates}
    ignored = [dict(candidate_id=c["candidate_id"], geometry_kind=c["geometry_kind"],
                    reason="OUTSIDE_CUSTOM_GEOMETRY_SCOPE" if c["geometry_kind"] != "CUSTOM"
                    else "OUTSIDE_SELECTED_CANDIDATE")
               for c in all_candidates if c["candidate_id"] not in selected_ids]
    return dict(schema_version="queue_custom_csv_position_3", profile=PROFILE,
        model_status=MODEL_STATUS, snapshot_sha256=reconstruction["snapshot_sha256"],
        source_as_of=reconstruction["source_as_of"], source_url=reconstruction["source_url"],
        operational_columns=reconstruction["operational_columns"], source_units=reconstruction["source_units"],
        parser_issues=reconstruction["parser_issues"], proposed=proposed, candidates=results,
        excluded_mosaic_candidates=ignored, excluded_non_mosaic_rows=reconstruction["excluded_rows"],
        summary=dict(custom_candidates_evaluated=len(results),
            beam_variants=sum(len(r["position"]["beam_variants"]) for r in results),
            position_outcomes={outcome: sum(v["outcome"] == outcome for r in results
                for v in r["position"]["beam_variants"])
                for outcome in ("SATISFIED", "NOT_SATISFIED", "UNKNOWN")}),
        validation_evidence_ref="tests/fixtures/ot_pointings/custom_offsets_2026_11_02/README.md",
        scientific_status="POSITION_ONLY", duplication_status="NOT_EVALUATED",
        candidate_union="NONE", array_aggregation="DEFERRED_TO_COMPLETE_SCIENTIFIC_BRANCHES")
