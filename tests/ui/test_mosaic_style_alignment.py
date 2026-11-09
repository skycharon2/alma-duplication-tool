"""P0.6 visual-shell parity: Mosaic reuses Single Pointing presentation classes.

The assertions operate on a real saved Mosaic assessment rather than trying to
mock the scientific chart geometry or make an external HTTP request.
"""
from bs4 import BeautifulSoup

from tests.ui.test_mosaic_execution import browser as case2_browser, form, upload  # noqa: F401


def test_mosaic_visual_shell_uses_single_pointing_layout(case2_browser):  # noqa: F811
    client, _discovery = case2_browser
    token = upload(client)
    response = client.post('/proposed/mosaic', data=form() | dict(
        action='assess', mosaic_upload_token=token, setup_complete=''))
    assert response.status_code == 303
    page = client.get(response.headers['Location'] + '/mosaic-visualization')
    assert page.status_code == 200
    soup = BeautifulSoup(page.data, 'html.parser')

    # The unchanged Single Pointing stylesheet remains the typography source.
    hrefs = [link.get('href', '') for link in soup.select('link[rel="stylesheet"]')]
    assert any(href.endswith('/visualization.css') for href in hrefs)
    assert any(href.endswith('/mosaic-visualization.css') for href in hrefs)
    panels = soup.select('#charts > section.visual-panel')
    assert len(panels) == 2
    assert [p.select_one('header h2').get_text(strip=True) for p in panels] == [
        'Position', 'Frequency']
    assert panels[0].select_one('header #mosaic-position-tools') is not None
    assert panels[1].select_one('header #mosaic-frequency-tools') is not None
    assert soup.select_one('.evidence-gallery-heading #evidence-page-number').get_text(strip=True) == '1 / 2'
    assert len(soup.select('.visual-bottom > section.visual-panel')) == 2
    assert len(soup.select('.visual-bottom .visual-candidate .visual-select')) == len(
        soup.select('[data-row]'))
    assert soup.select_one('#clear-filters').find_parent(class_='visual-filter-actions') is not None
    assert soup.select_one('.visual-panel .mosaic-frequency-explanation') is not None
    assert soup.select_one('.mosaic-position-summary') is not None
