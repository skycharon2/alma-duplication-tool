"""Source-list contract and numerical examples; no external acquisition."""
import hashlib
from pathlib import Path

import pytest

from alma_duplicate.parsers.source_list import MAX_BYTES, parse_source_list

FIXTURES = Path(__file__).parents[1] / 'fixtures' / 'source_list'


@pytest.mark.parametrize('format', ['csv', 'txt'])
def test_five_target_example(format):
    raw = (FIXTURES / f'five_targets.{format}').read_bytes()
    result = parse_source_list(raw, format=format)
    assert result['is_valid'] and result['row_count'] == 5
    assert result['input_sha256'] == hashlib.sha256(raw).hexdigest()
    expected = [
        ('B0218+357', 35.27279166666667, 35.93713888888889, '0.685'),
        ('PKS1830-211', 278.4164041666667, -21.06105555555556, '0.886'),
        ('CENA', 201.365, -43.01916666666667, '0.002'),
        ('WHya', 207.25833333333333, -28.36763888888889, '0.0'),
        ('M33', 23.4625, 30.66, '0.0'),
    ]
    for row, (name, ra, dec, z) in zip(result['sources'], expected):
        assert row['name'] == name and row['redshift'] == z
        assert row['ra_deg'] == pytest.approx(ra, abs=1e-10)
        assert row['dec_deg'] == pytest.approx(dec, abs=1e-10)
        assert row['frame'] == 'ICRS'
    assert result == parse_source_list(raw, format=format)


def test_identity_and_diagnostics_preserve_bad_rows_and_duplicates():
    result = parse_source_list(b'# comment\nname,ra,dec\n\na,0,0\na,0,0\nb,360,91\nc,1,2\n')
    assert not result['is_valid']
    assert [s['source_id'] for s in result['sources']] == ['line-4', 'line-5', 'line-6', 'line-7']
    assert result['sources'][1]['is_valid']
    assert {i['code'] for i in result['sources'][1]['issues']} == {'DUPLICATE_NAME', 'DUPLICATE_POSITION'}
    assert {i['field'] for i in result['sources'][2]['issues']} == {'ra', 'dec'}
    assert result['sources'][3]['is_valid']


@pytest.mark.parametrize('ra,dec', [('360', '0'), ('-1', '0'), ('NaN', '0'),
    ('0', 'inf'), ('24:00:00', '0'), ('12:60:00', '0'), ('12:00:60', '0'),
    ('-00:00:01', '0'), ('0', '90:00:01'), ('0', '-90:00:01')])
def test_invalid_coordinates(ra, dec):
    result = parse_source_list(f'name,ra,dec\na,{ra},{dec}'.encode())
    assert not result['is_valid']
    assert result['sources'][0]['issues']


@pytest.mark.parametrize('z', ['-1', '-2', 'NaN', 'Infinity', 'true', '1e9999', '1_0'])
def test_invalid_redshift(z):
    result = parse_source_list(f'name,ra,dec,redshift\na,0,0,{z}'.encode())
    assert not result['is_valid']
    assert result['sources'][0]['issues'][0]['code'] == 'INVALID_REDSHIFT'


@pytest.mark.parametrize('z,expected', [('', None), ('0', '0'), ('-0.01', '-0.01'),
    ('0.1234567890123456789', '0.1234567890123456789')])
def test_redshift_missing_zero_blueshift_and_precision(z, expected):
    result = parse_source_list(f'name,ra,dec,redshift\na,0,-90,{z}'.encode())
    assert result['is_valid']
    assert result['sources'][0]['redshift'] == expected


def test_bom_crlf_reordered_headers_and_quoted_names():
    raw = '\ufeffDEC,Name,RA,Redshift\r\n+90,"A, B",0,0\r\n'.encode()
    result = parse_source_list(raw)
    assert result['is_valid'] and result['sources'][0]['name'] == 'A, B'
    txt = parse_source_list(b'name ra dec\n"A B" 0 -00:30:00', format='txt')
    assert txt['sources'][0]['name'] == 'A B'
    assert txt['sources'][0]['dec_deg'] == -0.5


@pytest.mark.parametrize('row', ['a,0', 'a,0,0,extra', ',0,0', '"a,0,0'])
def test_malformed_rows_are_not_silently_dropped(row):
    result = parse_source_list(f'name,ra,dec\n{row}\ngood,0,0'.encode())
    assert not result['is_valid'] and result['row_count'] == 2
    assert result['sources'][1]['is_valid']


@pytest.mark.parametrize('raw', [b'', b'name,ra,dec\n', b'ra,dec\n0,0',
    b'name,ra,ra\na,0,0', b'name,ra,dec,epoch\na,0,0,2000',
    b'\xff', b'name,ra,dec\na,0,\x00', b'x' * (MAX_BYTES + 1),
    b'"name,ra,dec\na,0,0'])
def test_file_failures(raw):
    with pytest.raises(ValueError):
        parse_source_list(raw)


def test_limit_counts_invalid_rows_and_never_truncates():
    raw = b'name,ra,dec\n' + b'bad\n' * 11
    with pytest.raises(ValueError, match='limit'):
        parse_source_list(raw)
    at_limit = b'name,ra,dec\n' + b'bad\n' * 10
    assert parse_source_list(at_limit)['row_count'] == 10
    assert parse_source_list(raw, max_sources=11)['row_count'] == 11
    with pytest.raises(ValueError):
        parse_source_list(raw, max_sources=True)
    with pytest.raises(ValueError):
        parse_source_list(raw, format='auto')
    with pytest.raises(ValueError):
        parse_source_list('name,ra,dec\na,0,0')
