"""P1: sky context uses the saved, bound coordinates only (no query or rules)."""
from copy import deepcopy
from hashlib import sha256
import json

from bs4 import BeautifulSoup

from alma_duplicate.ui.mosaic_sky_preview import sky_preview
from alma_duplicate.ui.mosaic_visualization import position_chart, queue_rows
from tests.ui.test_mosaic_execution import browser as case2_browser, form, upload  # noqa: F401
from tests.ui.test_queue_geometry_visualization import sample


def proposed():
    return dict(points=[dict(id='P1', frame='ICRS', ra_deg=359.999, dec_deg=0.),
                        dict(id='P2', frame='ICRS', ra_deg=.001, dec_deg=0.)], array='12m')


def test_archive_region_is_checksum_bound_and_not_a_fabricated_beam():
    raw = 'POLYGON ICRS 359.99 -0.01 0.01 -0.01 0.01 0.01 359.99 0.01'
    row = dict(source='Archive', target='Observed source', footprint_evidence=dict(
        raw_s_region=raw, s_region_sha256=sha256(raw.encode()).hexdigest()), spectra=[])
    before = deepcopy(row)
    scene = sky_preview(row, proposed(), position_chart(row, proposed()))
    assert row == before
    assert scene['available'] and len(scene['proposed']) == 2
    assert scene['candidate']['kind'] == 'region'
    assert scene['candidate']['outline']
    assert 'center' not in scene['candidate']
    row['footprint_evidence']['s_region_sha256'] = 'bad'
    scene = sky_preview(row, proposed(), position_chart(row, proposed()))
    assert scene['candidate'] is None and 'verif' in scene['reason'].lower()


def test_queue_uses_only_confirmed_saved_candidate_array_and_snapshot():
    page = sample()
    row = next(queue_rows(page))
    source = deepcopy(page)
    scene = sky_preview(row, proposed(), position_chart(row, proposed()))
    assert scene['candidate']['kind'] == 'beams'
    assert len(scene['candidate']['beams']) == 2
    assert scene['candidate']['radius_arcsec'] == 12
    assert page == source
    page['document']['geometry_reports']['RECTANGLE']['candidates'][0]['position']['beam_variants'][0]['coverage']['complete'] = False
    row = next(queue_rows(page))
    scene = sky_preview(row, proposed(), position_chart(row, proposed()))
    assert scene['candidate'] is None


def test_invalid_or_oversized_proposed_pointings_not_plotted():
    row = next(queue_rows(sample()))
    points = proposed()
    points['points'][0]['frame'] = 'Galactic'
    assert sky_preview(row, points, position_chart(row, points))['available'] is False
    points['points'] = [dict(id=f'p{i}', frame='ICRS', ra_deg=0., dec_deg=0.) for i in range(2001)]
    assert sky_preview(row, points, position_chart(row, points))['available'] is False


def test_case2_sky_scene_matches_saved_page_without_requery_or_export_mutation(case2_browser):  # noqa: F811
    client, discovery_calls = case2_browser
    token = upload(client)
    reply = client.post('/proposed/mosaic', data=form() | dict(
        action='assess', mosaic_upload_token=token, setup_complete=''))
    assert reply.status_code == 303
    url = reply.headers['Location']
    report_before = client.get(url + '/download/report').data
    request_before = client.get(url + '/download/request').data
    n = len(discovery_calls)
    page = client.get(url + '/mosaic-visualization')
    assert page.status_code == 200
    soup = BeautifulSoup(page.data, 'html.parser')
    data = json.loads(soup.select_one('#mosaic-sky-data').text)
    assert len(data) == len(soup.select('[data-row]')) > 0
    assert all(len(item['proposed']) == 3 for item in data)
    assert all(item['candidate']['kind'] == 'region' for item in data)
    assert soup.select_one('#mosaic-sky-canvas')['data-aladin-module'].endswith('/aladin.js')
    assert len(discovery_calls) == n
    assert client.get(url + '/download/report').data == report_before
    assert client.get(url + '/download/request').data == request_before
