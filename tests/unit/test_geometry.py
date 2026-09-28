"""Independent geometry checks and compatibility of the extracted pure helpers."""
import subprocess
import sys

import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord

from alma_duplicate.domain.spatial import SkyPosition
from alma_duplicate.geometry import angular_separation_deg, primary_beam_fwhm_deg


@pytest.mark.parametrize('coordinates', [
    (0, 0, 0, 0), (359.999, 0, .001, 0),
    (0, 89.999, 180, 89.999), (0, -89.999, 180, -89.999),
    (0, 0, 180, 0), (12, 30, 12.000000001, 30),
    (201.365, -43.019, 201.37, -43.02),
])
def test_spherical_separation_against_independent_coordinate_library(coordinates):
    ra1, dec1, ra2, dec2 = coordinates
    a, b = SkyPosition(ra1, dec1, 'ICRS'), SkyPosition(ra2, dec2, 'ICRS')
    expected = SkyCoord(ra1*u.deg, dec1*u.deg).separation(SkyCoord(ra2*u.deg, dec2*u.deg)).deg
    assert angular_separation_deg(a, b) == pytest.approx(expected, abs=1e-12)


def test_legacy_imports_are_the_same_functions():
    from alma_duplicate.spatial import _separation
    from alma_duplicate.primary_beam import primary_beam_fwhm_deg as legacy_beam
    assert _separation is angular_separation_deg
    assert legacy_beam is primary_beam_fwhm_deg


def test_geometry_import_does_not_load_runtime_evidence_or_strategies():
    subprocess.run([sys.executable, '-c', '''
import sys
import alma_duplicate.geometry
for name in sys.modules:
    assert not name.startswith((
        'alma_duplicate.clients', 'alma_duplicate.rules',
        'alma_duplicate.domain', 'alma_duplicate.search_plan',
        'alma_duplicate.spatial', 'alma_duplicate.queue_position',
        'alma_duplicate.primary_beam',
    )), name
'''], check=True)
