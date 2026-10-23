"""Metadata discovery preserves source binding and never follows product links."""
import json
from hashlib import sha256
from pathlib import Path
from urllib.error import URLError
import xml.etree.ElementTree as ET

import pytest

from alma_duplicate.clients.archive_products import (
    MAX_RESPONSE_BYTES, MetadataResponse, discover_archive_products, parse_archive_products,
)
from alma_duplicate.cli.archive_products import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'docs/research/mosaic/evidence/case_E_datalink.xml'
MEMBER = 'uid://A001/X15aa/Xe5'
ASDM = 'uid://A002/Xfb8480/X4f37'
NS = '{http://www.ivoa.net/xml/VOTable/v1.3}'


def change(edit):
    root = ET.fromstring(FIXTURE.read_bytes())
    edit(root)
    return ET.tostring(root)


def rows(root):
    return root.find('.//' + NS + 'TABLEDATA')


def test_real_member_products_preserve_duplicates_and_roles():
    raw = FIXTURE.read_bytes()
    result = parse_archive_products(raw, member_ous_uid=MEMBER, asdm_uid=ASDM)
    assert result.status == 'DISCOVERED'
    assert result.response_sha256 == sha256(raw).hexdigest()
    assert len(result.products) == 6
    assert [p.kind for p in result.products] == [
        'DOCUMENTATION', 'DATASET', 'SERVICE_REFERENCE',
        'AUXILIARY_CANDIDATE', 'SERVICE_REFERENCE', 'PROGENITOR',
    ]
    auxiliary = result.products[3]
    assert auxiliary.content_length == 56154112
    assert auxiliary.pointing_content == 'NOT_INSPECTED'
    assert auxiliary.asdm_binding == 'NOT_ESTABLISHED'
    assert result.requested_asdm_uid == ASDM
    assert result.completeness == 'MEMBER_PRODUCT_INVENTORY_NOT_ESTABLISHED'


@pytest.mark.parametrize('filename,member', [
    ('case_C_datalink.xml', 'uid://A001/X133d/X22e8'),
    ('case_D_datalink.xml', 'uid://A001/X1296/X832'),
])
def test_other_preserved_member_responses(filename, member):
    raw = (FIXTURE.parent / filename).read_bytes()
    result = parse_archive_products(raw, member_ous_uid=member)
    assert result.status == 'DISCOVERED'
    assert any(p.kind == 'AUXILIARY_CANDIDATE' for p in result.products)


def test_mismatched_member_never_returns_products():
    result = parse_archive_products(FIXTURE.read_bytes(), member_ous_uid='uid://A001/X1/X2')
    assert result.status == 'INVALID_RESPONSE'
    assert result.products == ()
    assert result.issues == ('MEMBER_ID_MISMATCH',)


@pytest.mark.parametrize('raw,reason', [
    (b'<broken', 'MALFORMED_XML'),
    (b'<html/>', 'UNSUPPORTED_VOTABLE_NAMESPACE'),
    (b'<!DOCTYPE VOTABLE><VOTABLE/>', 'XML_DECLARATIONS_UNSUPPORTED'),
    (b' ' * (MAX_RESPONSE_BYTES + 1), 'RESPONSE_TOO_LARGE'),
])
def test_invalid_response(raw, reason):
    assert parse_archive_products(raw, member_ous_uid=MEMBER).issues == (reason,)


def test_overflow_and_bad_lengths_and_row_width():
    def overflow(root):
        ET.SubElement(root.find(NS + 'RESOURCE'), NS + 'INFO',
                      name='QUERY_STATUS', value='OVERFLOW')
    assert parse_archive_products(change(overflow), member_ous_uid=MEMBER).status == 'INVALID_RESPONSE'
    for value in ('-1', '1.2', 'bad'):
        raw = change(lambda root: setattr(rows(root)[0][8], 'text', value))
        assert parse_archive_products(raw, member_ous_uid=MEMBER).issues == ('INVALID_CONTENT_LENGTH',)
    raw = change(lambda root: rows(root)[0].remove(rows(root)[0][0]))
    assert parse_archive_products(raw, member_ous_uid=MEMBER).issues == ('ROW_COLUMN_COUNT_MISMATCH',)


def test_multiple_candidates_are_not_selected_or_collapsed():
    def duplicate(root):
        rows(root).append(ET.fromstring(ET.tostring(rows(root)[3])))
    result = parse_archive_products(change(duplicate), member_ous_uid=MEMBER)
    assert len([p for p in result.products if p.kind == 'AUXILIARY_CANDIDATE']) == 2


def test_empty_distinct_from_errors_and_denied_access():
    raw = change(lambda root: rows(root).clear())
    result = parse_archive_products(raw, member_ous_uid=MEMBER)
    assert result.status == 'EMPTY'
    assert result.completeness != 'COMPLETE'
    raw = change(lambda root: setattr(rows(root)[0][11], 'text', 'false'))
    assert parse_archive_products(raw, member_ous_uid=MEMBER).status == 'DISCOVERED_WITH_ISSUES'
    raw = change(lambda root: setattr(rows(root)[0][3], 'text', 'NotFoundFault: unavailable'))
    result = parse_archive_products(raw, member_ous_uid=MEMBER)
    assert result.products[0].kind == 'ERROR'
    assert 'DATALINK_ROW_ERROR' in result.issues


def test_unsafe_url_remains_diagnostic():
    raw = change(lambda root: setattr(rows(root)[0][1], 'text', 'file:///tmp/file'))
    result = parse_archive_products(raw, member_ous_uid=MEMBER)
    assert result.status == 'DISCOVERED_WITH_ISSUES'
    assert result.products[0].issues == ('UNSUPPORTED_ACCESS_URL',)


def test_network_fetch_only_requests_member_metadata():
    calls = []
    def fetch(url):
        calls.append(url)
        return MetadataResponse(200, FIXTURE.read_bytes())
    result, raw, url = discover_archive_products(MEMBER, asdm_uid=ASDM, fetch=fetch)
    assert result.status == 'DISCOVERED'
    assert raw == FIXTURE.read_bytes()
    assert calls == [url]
    assert url == 'https://almascience.eso.org/datalink/sync?ID=uid%3A%2F%2FA001%2FX15aa%2FXe5'


@pytest.mark.parametrize('code,status', [(403, 'ACCESS_DENIED'), (401, 'ACCESS_DENIED'),
                                        (302, 'REQUEST_FAILED'), (500, 'REQUEST_FAILED')])
def test_http_failures(code, status):
    result, raw, _ = discover_archive_products(MEMBER, fetch=lambda url: MetadataResponse(code, b'failed'))
    assert result.status == status
    assert raw == b'failed'
    assert result.products == ()


def test_transport_failure_and_size_limit():
    def unavailable(url):
        raise URLError('unavailable')
    result, raw, _ = discover_archive_products(MEMBER, fetch=unavailable)
    assert result.status == 'REQUEST_FAILED' and raw is None
    result, _, _ = discover_archive_products(
        MEMBER, fetch=lambda url: MetadataResponse(200, b'x' * (MAX_RESPONSE_BYTES + 1)))
    assert result.issues == ('RESPONSE_TOO_LARGE',)


def test_invalid_configuration_before_network():
    def forbidden(url):
        pytest.fail('Unexpected network request')
    with pytest.raises(ValueError):
        discover_archive_products('bad', fetch=forbidden)
    with pytest.raises(ValueError):
        discover_archive_products(MEMBER, origin='https://example.org', fetch=forbidden)


def test_cli_preserves_bytes_and_rejects_existing_receipt(tmp_path):
    output = tmp_path / 'receipt'
    args = ['--member', MEMBER, '--asdm', ASDM, '--response', str(FIXTURE), '--output-dir', str(output)]
    assert main(args) == 0
    doc = json.loads((output / 'discovery.json').read_text())
    assert doc['mode'] == 'OFFLINE_REPLAY'
    assert doc['historical_acquisition_time'] is None
    assert doc['request_started_at'] is None
    assert doc['request_url'] is None
    assert doc['capture_truncated'] is False
    assert (output / 'response.xml').read_bytes() == FIXTURE.read_bytes()
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


def test_cli_saves_invalid_response(tmp_path):
    source = tmp_path / 'bad.xml'
    source.write_bytes(b'not xml')
    output = tmp_path / 'receipt'
    assert main(['--member', MEMBER, '--response', str(source), '--output-dir', str(output)]) == 3
    assert (output / 'response.xml').read_bytes() == b'not xml'


@pytest.mark.parametrize('array,count', [('7m', 6), ('12m', 7)])
def test_live_capture_receipts_replay_without_network(array, count):
    directory = ROOT / 'tests/fixtures/archive/mosaic_products_2026_10_23' / array
    receipt = json.loads((directory / 'discovery.json').read_text())
    raw = (directory / 'response.xml').read_bytes()
    recorded = receipt['discovery']
    assert sha256(raw).hexdigest() == recorded['response_sha256']
    result = parse_archive_products(raw, member_ous_uid=recorded['member_ous_uid'],
                                   asdm_uid=recorded['requested_asdm_uid'])
    assert result.status == 'DISCOVERED'
    assert len(result.products) == count
    assert any(p.kind == 'AUXILIARY_CANDIDATE' for p in result.products)
    assert all(p.asdm_binding == 'NOT_ESTABLISHED' for p in result.products)
    assert receipt['mode'] == 'LIVE_METADATA'
    assert receipt['request_started_at'] and receipt['request_finished_at']


def test_http_status_and_partial_response_failure():
    from http.client import IncompleteRead
    result, _, _ = discover_archive_products(MEMBER, fetch=lambda url: MetadataResponse(200, FIXTURE.read_bytes()))
    assert result.http_status == 200
    def incomplete(url):
        raise IncompleteRead(b'partial', 100)
    result, raw, _ = discover_archive_products(MEMBER, fetch=incomplete)
    assert result.status == 'REQUEST_FAILED'
    assert raw is None


def test_ambiguous_table_and_missing_access_route():
    def duplicate_table(root):
        resource = root.find(NS + 'RESOURCE')
        resource.append(ET.fromstring(ET.tostring(resource.find(NS + 'TABLE'))))
    assert parse_archive_products(change(duplicate_table), member_ous_uid=MEMBER).issues == ('AMBIGUOUS_LINK_TABLE',)
    raw = change(lambda root: setattr(rows(root)[0][1], 'text', ''))
    assert 'MISSING_ACCESS_ROUTE' in parse_archive_products(raw, member_ous_uid=MEMBER).issues
