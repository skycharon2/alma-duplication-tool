import pytest
from alma_duplicate.ui import create_app

@pytest.fixture
def client():
    return create_app({'TESTING': True, 'REPORT_DIRECTORY': None, 'LIVE_ARCHIVE': False,
                       'OFFLINE_QUEUE_CSV': None, 'MANAGED_QUEUE_ROOT': None}).test_client()

@pytest.mark.parametrize('ra,dec,rf,df,expected', [
    ('180','-30','DEG','DEG','ICRS 180.000000°, -30.000000°'),
    ('12:00:00','-00:30:00','HMS','DMS','ICRS 180.000000°, -0.500000°'),
])
def test_coordinates_without_full_assessment(client, ra, dec, rf, df, expected):
    response = client.post('/sky-preview', data=dict(ra=ra,dec=dec,ra_format=rf,dec_format=df,target_kind='FIXED'))
    assert response.status_code == 200
    assert expected in response.json['html']

@pytest.mark.parametrize('ra,dec,kind', [('360','0','FIXED'),('0','91','FIXED'),('','','FIXED'),('0','0','MOVING')])
def test_invalid_input_never_renders_external_viewer(client, ra, dec, kind):
    response = client.post('/sky-preview', data=dict(ra=ra,dec=dec,ra_format='DEG',dec_format='DEG',target_kind=kind))
    assert response.status_code == 422
    assert 'html' not in response.json
