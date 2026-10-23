import json
import pytest
from test_mosaic_coverage_union import ready
from alma_duplicate.mosaic_spw_catalog import build_spw_catalog, select_spws
from alma_duplicate.cli import mosaic_spw_catalog as cli


def catalog(r=None, assume=True):
    return build_spw_catalog(r or ready(),hpbw_coefficient=1.13,assume_uniform_field_antennas=assume)


def test_catalog_uses_execution_frequencies_and_preserves_blocked_spws():
    r=ready()
    r['executions'][1]['fields'][0]['spectral_windows'][0]['reported_centre_hz'] *= 2
    r['executions'][0]['fields'][0]['scans'][0]['spw_ids'].append(99)
    c=catalog(r)
    assert [(e['asdm_uid'],e['spw_id'],e['status']) for e in c['entries']] == [
        ('A',16,'AVAILABLE'),('A',99,'BLOCKED'),('B',16,'AVAILABLE')]
    assert c['entries'][2]['frequency_hz']==2*c['entries'][0]['frequency_hz']
    assert c['completeness']=='MEMBER_COMPLETENESS_NOT_ESTABLISHED'


def test_no_antenna_assumption_blocks_selection():
    c=catalog(assume=False)
    assert all(e['status']=='BLOCKED' for e in c['entries'])
    with pytest.raises(ValueError): select_spws(c,[dict(asdm_uid='A',spw_id=16)])


@pytest.mark.parametrize('pairs',[[],[dict(asdm_uid='Z',spw_id=16)],
    [dict(asdm_uid='A',spw_id=16)]*2,[dict(asdm_uid='A',spw_id=True)]])
def test_invalid_selection(pairs):
    with pytest.raises(ValueError): select_spws(catalog(),pairs)


def test_different_arrays_not_exported():
    r=ready();r['executions'][1]['antenna_evidence']['diameters_m']=[7.0]
    with pytest.raises(ValueError,match='Cross-array'):
        select_spws(catalog(r),[dict(asdm_uid=u,spw_id=16) for u in ('A','B')])


def test_cli_catalog_and_export(tmp_path,monkeypatch):
    monkeypatch.setattr(cli,'build_readiness',lambda *a,**kw:ready())
    common=['--package-audit-dir',str(tmp_path),'--array-catalog',str(tmp_path),
            '--hpbw-coefficient','1.13','--assume-uniform-field-antennas']
    out=tmp_path/'catalog.json'
    assert cli.main(common+['--output',str(out)])==0
    assert len(json.loads(out.read_text())['entries'])==2
    pairs=tmp_path/'pairs.json'
    assert cli.main(common+['--select','A','16','--select','B','16','--output',str(pairs)])==0
    assert json.loads(pairs.read_text())==[dict(asdm_uid=u,spw_id=16) for u in ('A','B')]
    with pytest.raises(SystemExit): cli.main(common+['--output',str(out)])
