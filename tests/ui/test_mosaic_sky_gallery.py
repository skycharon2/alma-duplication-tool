"""P1.1: Mosaic evidence gallery matches Single Pointing page structure."""
from bs4 import BeautifulSoup

from tests.ui.test_mosaic_execution import browser as case2_browser, form, upload  # noqa: F401


def test_mosaic_gallery_is_separate_from_filters_and_slides_remain_mounted(case2_browser):  # noqa: F811
    client, _discovery = case2_browser
    token = upload(client)
    response = client.post('/proposed/mosaic', data=form() | dict(
        action='assess', mosaic_upload_token=token, setup_complete=''))
    assert response.status_code == 303
    page = client.get(response.headers['Location'] + '/mosaic-visualization')
    assert page.status_code == 200
    soup = BeautifulSoup(page.data, 'html.parser')

    filters = soup.select_one('section.visual-controls')
    assert filters is not None
    assert filters.select_one('#comparison-count') is not None
    assert filters.select_one('.evidence-gallery-heading') is None
    gallery = soup.select_one('#mosaic-evidence-gallery')
    assert gallery is not None
    slides = gallery.find_all(recursive=False)
    assert [slide.get('id') for slide in slides] == ['charts', 'sky']
    assert all('evidence-slide' in slide.get('class', []) for slide in slides)
    assert not slides[1].has_attr('hidden')
    assert soup.select_one('script#mosaic-sky-data') is not None
    assert soup.select_one('.visual-bottom').find_parent(id='mosaic-evidence-gallery') is None
