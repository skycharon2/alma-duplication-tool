"""A saved Queue Rectangle branch joins the ORIGINAL Explore chart and sky data."""
from copy import deepcopy
import json
import re
from types import SimpleNamespace

from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.ui import create_app
from tests.ui.test_calculation_view import serialized, report
from tests.ui.test_queue_geometry_visualization import sample


def test_single_explore_archive_and_queue_mosaic_use_one_visual_payload(tmp_path):
    document=serialized(report())
    queue=sample()['document']
    # The standalone Queue fixture deliberately tests RA wrapping at 0/360 deg.
    # This route test instead needs Queue beams near the saved Archive proposal:
    # projecting the original 0-deg fixture from RA~201, Dec~-43 would correctly
    # reject it as lying beyond the display hemisphere.
    proposed=document['request']['normalized']['position']
    origin=SkyCoord(ra=proposed['ra_deg']*u.deg,
                    dec=proposed['dec_deg']*u.deg, frame='icrs')
    points=queue['geometry_reports']['RECTANGLE']['candidates'][0][
        'position']['beam_variants'][0]['coverage']['points']
    # One point inside the saved 12-arcsec beam, one outside; the fixture's
    # matched_point_ids=['a'] remains consistent with the test geometry.
    for point, separation in zip(points, (3., 20.), strict=True):
        sky=origin.directional_offset_by(90*u.deg, separation*u.arcsec)
        point.update(ra_deg=sky.ra.deg, dec_deg=sky.dec.deg)
    document['queue_geometry_assessment']=deepcopy(queue)
    app=create_app({'TESTING':True, 'REPORT_DIRECTORY':None, 'LIVE_ARCHIVE':False,
                    'LIVE_AQ':False})
    store=app.extensions['assessment_runs']
    try:
        run_id=store.add({'request':document['request']},
                         SimpleNamespace(document=document,status='COMPLETED'))
        client=app.test_client()
        path=f'/runs/{run_id}'
        before=client.get(path+'/download/report').data
        response=client.get(path+'/visualization')
        assert response.status_code==200,response.text[:900]
        # No independent Queue plot. The original list, charts and sky are used.
        assert 'id="queue-geometry-chart"' not in response.text
        assert 'id="spatial-chart"' in response.text
        assert 'id="report-sky-panel"' in response.text
        found=re.search(r'<script id="visual-data" type="application/json">(.*?)</script>',
                        response.text,re.S)
        assert found
        payload=json.loads(found.group(1))
        assert {r['source'] for r in payload['rows']}=={'ARCHIVE','QUEUE'}
        row=next(r for r in payload['rows'] if r['source']=='QUEUE')
        assert row['geometry_kind']=='RECTANGLE'
        assert row['identity']['Project']=='2025.1.TEST'
        assert row['spatial']['available']
        assert row['spatial']['covered_beam_count']==1
        assert len(row['spatial']['beams'])==2
        assert f'data-select="{row["id"]}"' in response.text
        assert client.get(path+'/download/report').data==before
        assert client.get(path+'/visualization?queue_page=0').status_code==400
    finally:
        store.close()
