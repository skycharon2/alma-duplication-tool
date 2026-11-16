"""Independent spherical/ERFA references; these are not native OT exports."""
import math

import erfa
import pytest

from alma_duplicate.queue_mosaic import reconstruct_queue_mosaics
from alma_duplicate.queue_rectangle_grid import RectangleGeometry, generate_rectangle_grid
from tests.unit.test_queue_custom_backend import parsed


def offset(lon, lat, east, north):
    """Great-circle destination, independent of SkyCoord.directional_offset_by."""
    distance = math.radians(math.hypot(east, north) / 3600)
    bearing = math.atan2(east, north)
    out_lat = math.asin(math.sin(lat)*math.cos(distance) +
                        math.cos(lat)*math.sin(distance)*math.cos(bearing))
    out_lon = lon + math.atan2(math.sin(bearing)*math.sin(distance)*math.cos(lat),
                               math.cos(distance)-math.sin(lat)*math.sin(out_lat))
    return out_lon, out_lat


def assert_icrs(actual, expected):
    ra, dec = map(math.radians, actual)
    # ERFA's angular-separation routine handles wrap and near-pole coordinates.
    assert math.degrees(erfa.seps(ra, dec, *expected))*3600 < 0.0001


@pytest.mark.parametrize('lon,lat', [(0, 0), (359.999, 20), (123, 85), (45, -80)])
@pytest.mark.parametrize('east,north', [(0, 0), (30, 0), (0, -45), (20, -10)])
def test_custom_native_offsets_against_spherical_reference(lon, lat, east, north):
    ra, dec = map(math.degrees, erfa.g2icrs(math.radians(lon), math.radians(lat)))
    source = parsed(lambda r: r.update(RA=str(ra), Dec=str(dec), **{
        'Mos. Coord.': 'galactic', 'Long Offset': str(east), 'Lat Offset': str(north)}))
    candidate = next(c for c in reconstruct_queue_mosaics(source)['candidates'] if c['geometry_kind'] == 'CUSTOM')
    center = candidate['source_rows'][0]['center']
    expected = erfa.g2icrs(*offset(math.radians(lon), math.radians(lat), east, north))
    assert_icrs(center['icrs_deg'], expected)
    assert center['reference_frame'] == 'ICRS' and center['offset_frame'] == 'GALACTIC'
    assert center['source_reference_icrs_deg'] == [ra, dec]
    assert 'GALACTIC_OFFSET_MODEL_NOT_OT_VALIDATED' in center['reasons']


@pytest.mark.parametrize('pa', [0, 30, 90, 210])
@pytest.mark.parametrize('diameter', [12, 7])
def test_rectangle_rotates_complete_lattice_in_native_frame(pa, diameter):
    lon, lat = math.radians(359.999), math.radians(65)
    ra, dec = map(math.degrees, erfa.g2icrs(lon, lat))
    geometry = RectangleGeometry(ra, dec, 20, -10, 100, 70, pa, 30, 'galactic')
    grid = generate_rectangle_grid(geometry, diameter, spacing_reference_diameter_m=12)
    assert grid['pointing_count'] == (10 if diameter == 12 else 3) and grid['model_grid_complete']
    center = offset(lon, lat, 20, -10)
    assert_icrs(grid['center_icrs_deg'], erfa.g2icrs(*center))
    # Independently enumerated 3/4/3 lattice for this fixed rectangle.
    h = math.sqrt(3)*15
    lattice = [(x, -h) for x in (-30, 0, 30)] + [(x, 0) for x in (-45, -15, 15, 45)] + [(x, h) for x in (-30, 0, 30)]
    if diameter == 7:
        spacing = 30*12/7
        # Independent 2/1 lattice enumeration for the coarser 7-m spacing.
        h = math.sqrt(3)*spacing/2
        lattice = [(-spacing/2, -h/2), (spacing/2, -h/2), (0, h/2)]
    angle = math.radians(pa)
    for actual, (x, y) in zip(grid['pointings'], lattice):
        east, north = x*math.cos(angle)+y*math.sin(angle), -x*math.sin(angle)+y*math.cos(angle)
        assert_icrs([actual['ra_deg'], actual['dec_deg']], erfa.g2icrs(*offset(*center, east, north)))
    assert grid['offset_frame'] == 'GALACTIC'
    assert grid['ot_reference'] is None
    assert grid['validation_scope'] == 'SPHERICAL_REFERENCE_TESTS_NOT_OT_PARITY'
