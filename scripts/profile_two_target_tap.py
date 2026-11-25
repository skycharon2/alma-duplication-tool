"""Compare two independent Archive searches with one target-tagged TAP query."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from time import perf_counter

from astropy.table import Table

from alma_duplicate.archive_endpoints import ARCHIVE_ORIGINS
from alma_duplicate.clients.archive_client import PyvoTapExecutor
from alma_duplicate.clients.archive_contract import TapExecutionError
from alma_duplicate.clients.archive_projection import plan_archive_projection
from alma_duplicate.clients.archive_queries import ARCHIVE_TABLE, MOSAIC_DISCOVERY_MARGIN_DEG, build_retrieval_adql
from alma_duplicate.reporting import json_value
from alma_duplicate.search_plan import build_search_plan
from alma_duplicate.ui.batch_requests import prepare_batch_form
from alma_duplicate.request_validation import validate_proposed_observation

MAXREC = 10_000
TARGET_IDS = (1, 2)


def row_multiset(rows):
    return Counter(json.dumps(json_value(dict(row)), sort_keys=True) for row in rows)


def group_rows(rows, columns):
    grouped = {target_id: Counter() for target_id in TARGET_IDS}
    for row in rows:
        target_id = row['batch_target']
        if target_id not in grouped:
            raise ValueError('Combined result contains an unknown target ID')
        packed = json.dumps(json_value({column: row[column] for column in columns}), sort_keys=True)
        grouped[target_id][packed] += 1
    return grouped


def fetch(endpoint, adql, columns, *, uploads=None):
    executor = PyvoTapExecutor(endpoint)
    try:
        start = perf_counter()
        response = executor.execute(adql, maxrec=MAXREC, uploads=uploads)
        if (not response.explicit_success or response.query_status_raw != 'OK'
                or len(response.rows) >= MAXREC or response.declared_columns != columns):
            raise ValueError('TAP response failed completeness or projection checks')
        return response, perf_counter() - start
    finally:
        executor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('setup', type=Path)
    parser.add_argument('targets', type=Path, help='CSV with exactly two targets')
    args = parser.parse_args()
    setup = json.loads(args.setup.read_text())
    preflight = prepare_batch_form(setup['values'] | {'sources': ['ARCHIVE']}, setup['rows'],
                                   args.targets.read_bytes(), require_line_complete=True)
    if not preflight['can_search'] or len(preflight['sources']) != 2:
        parser.error('provide exactly two valid searchable targets')
    specs = []
    for child in preflight['sources']:
        document = child['document']
        validation = validate_proposed_observation(document['request'], document['search_options'])
        specs.append(build_search_plan(validation).for_source('ARCHIVE').archive_query)

    endpoint = ARCHIVE_ORIGINS[0] + '/tap'
    executor = PyvoTapExecutor(endpoint)
    try:
        projection = plan_archive_projection(executor)
    finally:
        executor.close()
    if projection.probe_error is not None:
        raise ValueError('TAP column discovery did not complete')
    columns = projection.selected_columns
    if any(spec.spatial_strategy != 'CENTER_OR_MOSAIC_REGION' or spec.science_only
           or spec.frequency_min_ghz is not None or spec.angular_resolution_min_arcsec is not None
           or spec.member_ous_uid is not None for spec in specs):
        parser.error('prototype requires ordinary automatic-area Archive searches')

    radii = {format(spec.radius_deg, '.15g') for spec in specs}
    if len(radii) != 1:
        parser.error('the European TAP prototype requires a shared search radius')
    radius, = radii
    targets = Table({'batch_target': TARGET_IDS, 'ra_deg': [float(format(s.ra_deg, '.15g')) for s in specs],
                     'dec_deg': [float(format(s.dec_deg, '.15g')) for s in specs]})
    selection = ', '.join(f'o.{column}' for column in columns)
    combined = (
        f"SELECT {selection}, b.batch_target FROM {ARCHIVE_TABLE} AS o "
        "JOIN TAP_UPLOAD.targets AS b ON "
        "1 = CONTAINS(POINT('ICRS', o.s_ra, o.s_dec), "
        f"CIRCLE('ICRS', b.ra_deg, b.dec_deg, {radius})) OR "
        "(o.is_mosaic = 'T' AND 1 = INTERSECTS(o.s_region, "
        f"CIRCLE('ICRS', b.ra_deg, b.dec_deg, {MOSAIC_DISCOVERY_MARGIN_DEG:.15g})))"
    )

    start = perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        baseline = list(pool.map(lambda spec: fetch(endpoint, build_retrieval_adql(spec, columns=columns), columns),
                                 specs))
    print('Independent parallel wall seconds:', round(perf_counter() - start, 3), flush=True)
    start = perf_counter()
    try:
        result, combined_seconds = fetch(endpoint, combined, columns + ('batch_target',), uploads={'targets': targets})
    except (TapExecutionError, ValueError) as exc:
        print('Combined query failed after', round(perf_counter() - start, 3), 'seconds:', exc)
        print('Independent row counts:', [len(response.rows) for response, _ in baseline])
        return 1
    print('Combined wall seconds:', round(combined_seconds, 3), 'wire rows:', len(result.rows), flush=True)
    grouped = group_rows(result.rows, columns)
    parity = True
    for (independent, seconds), alias in zip(baseline, TARGET_IDS, strict=True):
        expected = row_multiset(independent.rows)
        actual = grouped[alias]
        missing, extra = sum((expected - actual).values()), sum((actual - expected).values())
        print(alias, 'independent seconds:', round(seconds, 3), 'rows:', len(independent.rows),
              'missing:', missing, 'extra:', extra, flush=True)
        parity = parity and not (missing or extra)
    return 0 if parity else 1


if __name__ == '__main__':
    raise SystemExit(main())
