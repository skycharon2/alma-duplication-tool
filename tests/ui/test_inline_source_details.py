"""Source details live next to their Single Pointing checkboxes, without changing source policy."""
from html.parser import HTMLParser

import pytest

from alma_duplicate.ui import create_app
from tests.ui.test_runs import config


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = 0
        self.help_controls = []
        self.ids = []
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'label':
            self.labels += 1
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'input' and attrs.get('name') == 'sources':
            self.sources.append(attrs['value'])
        if tag == 'button' and 'source-choice-help' in attrs.get('class', '').split():
            self.help_controls.append((attrs, self.labels))

    def handle_endtag(self, tag):
        if tag == 'label':
            self.labels -= 1


@pytest.mark.parametrize('live', [False, True])
def test_single_source_help_buttons_are_non_submitting_and_target_existing_popovers(live):
    options = config()
    if live:
        options.update(LIVE_ARCHIVE=True, OFFLINE_ARCHIVE_REPLAY=None)
    app = create_app(options)
    try:
        html = app.test_client().get('/proposed').text
        parsed = Controls()
        parsed.feed(html)
        assert parsed.sources == ['ARCHIVE', 'QUEUE']
        assert len(parsed.help_controls) == 2
        targets = [a['popovertarget'] for a, _ in parsed.help_controls]
        assert targets == [
            'archive-connection-popover' if live else 'archive-source-popover',
            'queue-source-popover',
        ]
        for (attrs, label_depth), target in zip(parsed.help_controls, targets):
            assert attrs['type'] == 'button' and label_depth == 0
            assert target in parsed.ids
            assert 'name' not in attrs  # Must not change sources or trigger a form action.
        assert 'queue-source-status' not in targets
    finally:
        app.extensions['assessment_runs'].close()


def test_mosaic_source_controls_remain_unchanged():
    app = create_app(config(LIVE_ARCHIVE=True, OFFLINE_ARCHIVE_REPLAY=None))
    try:
        html = app.test_client().get('/proposed/mosaic').text
        parsed = Controls()
        parsed.feed(html)
        assert parsed.sources == ['ARCHIVE']
        assert not parsed.help_controls
        assert 'class="archive-details-button"' in html
        assert 'popovertarget="archive-connection-popover"' in html
    finally:
        app.extensions['assessment_runs'].close()
