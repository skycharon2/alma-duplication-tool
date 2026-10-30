"""Single Pointing keeps a concise input page without changing source science."""
import pytest

from alma_duplicate.ui import create_app
from tests.ui.test_default_single_pointing_contract import continuum_form
from tests.ui.test_runs import config


@pytest.fixture
def client():
    app = create_app(config())
    yield app.test_client()
    app.extensions["assessment_runs"].close()


def test_single_pointing_has_contextual_help_and_no_candidate_cap(client):
    html = client.get("/proposed").get_data(as_text=True)
    assert 'data-help="coordinates"' in html
    assert 'data-help="purposes"' in html
    assert 'data-help="continuum"' in html
    assert 'data-help="search_scope"' in html
    assert 'data-help="sources"' in html
    assert 'id="auto-scope-details" class="single-only-advanced"' in html
    assert 'id="assessment-sources" class="field-help single-only-advanced"' in html
    assert "auto_scope.method_version" not in html  # Template expression evaluated.
    assert "7 m dishes at 35 GHz" in html  # Technical science is still present.
    assert 'name="result_limit"' not in html
    assert 'Candidate display limit' not in html
    assert 'Display options' not in html
    assert 'Select either or both.' not in html
    assert 'ICRS coordinates. Use colons for HMS / DMS' not in html
    # The declaration still exists for screen readers and non-JS input.
    assert 'id="continuum-choice-note" class="field-note sr-only"' in html
    assert 'name="continuum_setup_declaration"' in html


def test_uncapped_single_pointing_exports_all_retained_candidates_by_default(client):
    form = continuum_form()
    form['action'] = 'download'
    response = client.post('/proposed', data=form)
    assert response.status_code == 200 and response.is_json
    search = response.get_json()['search_options']
    assert search['sources'] == ['ARCHIVE', 'QUEUE']
    assert 'result_limit' not in search
    assert 'line_input_contract' not in response.get_json()['request']


def test_legacy_mosaic_keeps_its_source_details_and_archive_only_policy(client):
    html = client.get('/proposed/mosaic').get_data(as_text=True)
    assert 'id="assessment-sources" class="field-help"' in html
    assert 'data-help="search_scope"' not in html
    assert 'name="sources" value="QUEUE"' not in html
    assert 'name="normal_form_version" value="2"' in html
    assert 'Select either or both.' in html
