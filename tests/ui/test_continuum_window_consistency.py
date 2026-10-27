"""A complete optional window inventory must not contradict continuum selection."""

from alma_duplicate.ui.proposed import validate_form

ROW_A = 'w123456abcdef'
ROW_B = 'wabcdef123456'
ROW_C = 'w987654abcdef'


def values(**overrides):
    data = {
        'target_kind': 'FIXED', 'geometry': 'SINGLE_POINTING',
        'setup_id': 'setup-1', 'intents': ['CONTINUUM'],
        'continuum_setup_declaration': 'on', 'setup_complete': 'on',
        'ra': '11.887', 'dec': '-25.288', 'angular': '0.3',
        'representative': '230', 'aggregate': '0.1', 'sources': ['ARCHIVE'],
    }
    data.update(overrides)
    return data


def test_no_window_details_are_optional_without_list_completeness():
    data = values(setup_complete='')
    document, result, issues = validate_form(data, [])
    assert result.is_valid and result.can_search
    assert document['request']['continuum_setup_declaration']
    assert document['request']['spectral_windows'] == []
    assert not document['request']['setup_complete']


def test_confirmed_empty_list_conflicts_with_continuum():
    _, result, issues = validate_form(values(), [])
    assert not result.is_valid
    assert any(i['issue'].code == 'CONTINUUM_SETUP_DECLARATION_CONFLICT'
               and i['field'] == 'continuum_setup_declaration' for i in issues)


def test_confirmed_one_narrow_window_conflicts_with_continuum():
    _, result, issues = validate_form(values(**{
        ROW_A + '_id': 'spw-0', ROW_A + '_bandwidth': '1200',
        ROW_A + '_bandwidth_kind': 'USABLE',
    }), [ROW_A])
    assert not result.is_valid
    assert any(i['issue'].code == 'CONTINUUM_SETUP_DECLARATION_CONFLICT' for i in issues)


def test_confirmed_incomplete_width_evidence_reports_error():
    data = values(**{
        ROW_A + '_id': 'spw-0', ROW_A + '_bandwidth': '2000',
        ROW_A + '_bandwidth_kind': 'USABLE', ROW_B + '_id': 'spw-1',
    })
    _, result, issues = validate_form(data, [ROW_A, ROW_B])
    assert not result.is_valid
    assert any(i['issue'].code == 'INCOMPLETE_CONTINUUM_WINDOW_EVIDENCE'
               for i in issues)


def test_two_distinct_usable_wide_windows_are_accepted():
    data = values(**{
        ROW_A + '_id': 'spw-0', ROW_A + '_bandwidth': '2000',
        ROW_A + '_bandwidth_kind': 'USABLE',
        ROW_B + '_id': 'spw-1', ROW_B + '_bandwidth': '2.1',
        ROW_B + '_bandwidth_unit': 'GHz', ROW_B + '_bandwidth_kind': 'USABLE',
    })
    _, result, _ = validate_form(data, [ROW_A, ROW_B])
    assert result.is_valid and result.can_search


def test_line_only_search_does_not_require_window_evidence():
    data = values(intents=['LINE'], continuum_setup_declaration='', setup_complete='')
    _, result, _ = validate_form(data, [])
    assert result.is_valid and result.can_search


def test_two_verified_wide_windows_are_sufficient_with_a_third_unknown_width():
    # The continuum rule requires two qualifying windows, not that all
    # enumerated SPWs qualify. The third width does not negate this proof.
    data = values(**{
        ROW_A + '_id': 'wide-a', ROW_A + '_bandwidth': '2000',
        ROW_A + '_bandwidth_kind': 'USABLE',
        ROW_B + '_id': 'wide-b', ROW_B + '_bandwidth': '2200',
        ROW_B + '_bandwidth_kind': 'USABLE',
        ROW_C + '_id': 'other-spw',
    })
    _, result, issues = validate_form(data, [ROW_A, ROW_B, ROW_C])
    assert result.is_valid and result.can_search
    assert not any(item['issue'].code in (
        'INCOMPLETE_CONTINUUM_WINDOW_EVIDENCE',
        'CONTINUUM_SETUP_DECLARATION_CONFLICT') for item in issues)


def test_two_verified_wide_windows_are_sufficient_with_a_narrow_third():
    data = values(**{
        ROW_A + '_id': 'wide-a', ROW_A + '_bandwidth': '2000',
        ROW_A + '_bandwidth_kind': 'USABLE',
        ROW_B + '_id': 'wide-b', ROW_B + '_bandwidth': '2200',
        ROW_B + '_bandwidth_kind': 'USABLE',
        ROW_C + '_id': 'narrow', ROW_C + '_bandwidth': '1200',
        ROW_C + '_bandwidth_kind': 'USABLE',
    })
    _, result, _ = validate_form(data, [ROW_A, ROW_B, ROW_C])
    assert result.is_valid and result.can_search


def test_exact_usable_threshold_is_not_qualifying():
    data = values(**{
        ROW_A + '_id': 'one', ROW_A + '_bandwidth': '1800',
        ROW_A + '_bandwidth_kind': 'USABLE',
        ROW_B + '_id': 'two', ROW_B + '_bandwidth': '2.1',
        ROW_B + '_bandwidth_unit': 'GHz', ROW_B + '_bandwidth_kind': 'USABLE',
    })
    _, result, issues = validate_form(data, [ROW_A, ROW_B])
    assert not result.is_valid
    assert any(x['issue'].code == 'CONTINUUM_SETUP_DECLARATION_CONFLICT'
               for x in issues)


def test_raw_api_retains_conflicting_claim_for_scientific_audit():
    from alma_duplicate.request_validation import validate_proposed_observation
    from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup

    document, browser, _ = validate_form(values(), [])
    assert not browser.is_valid
    api = validate_proposed_observation(document['request'], document['search_options'])
    assert api.is_valid
    recorded = evaluate_continuum_setup(api.request)
    assert recorded.outcome is None
    assert 'CONTINUUM_SETUP_DECLARATION_CONFLICT' in recorded.reasons


def test_continuum_intent_alone_does_not_forge_setup_evidence_in_raw_post():
    # A real browser click marks the explicit declaration checkbox in JS.
    # Programmatic/legacy posts with only the intent must retain the original
    # direct-width science path (including nominal conversion in CLI parity).
    payload = values(continuum_setup_declaration='', setup_complete='')
    document, result, _ = validate_form(payload, [])
    assert result.is_valid and result.can_search
    assert 'continuum_setup_declaration' not in document['request']


def test_both_purposes_accept_wide_fdm_spws():
    # LINE and CONTINUUM are independent purposes. Two wide FDM windows can
    # qualify the requested CONT-SETUP and simultaneously supply LINE evidence.
    from alma_duplicate.rules.continuum_setup import evaluate_continuum_setup

    data = values(intents=['LINE', 'CONTINUUM'], **{
        ROW_A + '_id': 'wide-fdm-a',
        ROW_A + '_center': '230.0', ROW_A + '_mode': 'FDM',
        ROW_A + '_bandwidth': '1875', ROW_A + '_bandwidth_kind': 'USABLE',
        ROW_B + '_id': 'wide-fdm-b',
        ROW_B + '_center': '231.0', ROW_B + '_mode': 'FDM',
        ROW_B + '_bandwidth': '1875', ROW_B + '_bandwidth_kind': 'USABLE',
    })
    document, result, _ = validate_form(data, [ROW_A, ROW_B])
    assert result.is_valid and result.can_search
    assert set(document['request']['intents']) == {'LINE', 'CONTINUUM'}
    assert [w.correlator_mode for w in result.request.spectral_windows] == ['FDM', 'FDM']
    assert evaluate_continuum_setup(result.request).outcome == 'SATISFIED'


def test_line_only_does_not_assert_continuum_condition_even_with_wide_spws():
    data = values(intents=['LINE'], continuum_setup_declaration='', **{
        ROW_A + '_id': 'wide-fdm-a', ROW_A + '_center': '230.0',
        ROW_A + '_mode': 'FDM', ROW_A + '_bandwidth': '1875',
        ROW_A + '_bandwidth_kind': 'USABLE',
        ROW_B + '_id': 'wide-fdm-b', ROW_B + '_center': '231.0',
        ROW_B + '_mode': 'FDM', ROW_B + '_bandwidth': '1875',
        ROW_B + '_bandwidth_kind': 'USABLE',
    })
    document, result, _ = validate_form(data, [ROW_A, ROW_B])
    assert result.is_valid
    assert document['request']['intents'] == ['LINE']
    assert 'continuum_setup_declaration' not in document['request']
