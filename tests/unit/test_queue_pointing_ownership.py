"""Custom ownership adopts beam evidence without inventing array pointings."""
import pytest

from alma_duplicate.domain.queue import QueueMosaicKind
from alma_duplicate.queue_pointing_ownership import resolve_custom_pointing_array
from tests.unit.test_queue_custom_backend import parsed


@pytest.mark.parametrize('standalone,changes,owner,requested', [
    ('False', {'Use 7-m?': 'False'}, '12M', ('12M',)),
    ('True', {}, '7M', ('7M',)),
    ('False', {}, '12M', ('7M', '12M')),
    (None, {'Req. Ang. Res.': '30'}, '7M', ('7M',)),
    ('invalid', {}, 'UNKNOWN', ('7M', 'UNKNOWN')),
])
def test_ownership_preserves_inference(standalone, changes, owner, requested):
    data = parsed(lambda r: r.update(changes), standalone=standalone)
    row = next(r for r in data.row_inputs if r.spatial.mosaic_kind is QueueMosaicKind.CUSTOM_POINTING)
    result = resolve_custom_pointing_array(row)
    assert result.pointing_array == owner
    assert result.requested_arrays == requested
    assert result.evaluated_arrays == ()
    assert result.unassessed_arrays == requested
    assert dict(result.ownership_basis)['standalone_aca_raw'] == (standalone or '')
    if standalone is None:
        assert dict(result.ownership_basis)['standalone_aca_interpretation_kind'] == '7M_COMPATIBLE_INFERENCE'
        assert dict(result.ownership_basis)['requested_angular_resolution_arcsec'] == '30.0'


def test_non_custom_row_rejected():
    row = next(r for r in parsed().row_inputs if r.spatial.mosaic_kind is not QueueMosaicKind.CUSTOM_POINTING)
    with pytest.raises(ValueError, match='Custom'):
        resolve_custom_pointing_array(row)
