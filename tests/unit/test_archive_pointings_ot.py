"""Verified execution export preserves pointing rows and source identity."""
import pytest
from alma_duplicate.cli.archive_pointings_ot import export_execution
from alma_duplicate.parsers.ot_pointings import parse_ot_pointings
from tests.unit.test_archive_mosaic_pointings import package  # noqa: F401
from alma_duplicate.archive_mosaic_pointings import load_package_executions


def test_export_verified_execution_roundtrip(package, tmp_path):  # noqa: F811
    executions, _ = load_package_executions(package)
    selected = executions[0]
    output = tmp_path / 'ot'
    report = export_execution(package, selected['asdm_uid'], output)
    parsed = parse_ot_pointings((output / 'pointings.txt').read_bytes())
    expected = selected['evidence']['fields']
    assert [(p['ra_deg'], p['dec_deg']) for p in parsed['points']] == [
        (f['ra_deg'], f['dec_deg']) for f in expected]
    assert report['pointing_count'] == len(expected)
    assert report['asdm_uid'] == selected['asdm_uid']
    with pytest.raises(FileExistsError):
        export_execution(package, selected['asdm_uid'], output)
    with pytest.raises(ValueError, match='exactly one'):
        export_execution(package, 'missing', tmp_path / 'bad')
