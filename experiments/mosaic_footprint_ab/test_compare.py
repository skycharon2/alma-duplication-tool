"""Regression checks for the experiment geometry and fixture provenance."""
import math
import unittest
from pathlib import Path

from compare import (Tangent, beam_radius_as, parse_stcs, polygon_contains,
                     read_fields, read_tap, spherical_separation_arcsec)

HERE = Path(__file__).resolve().parent


class GeometryTests(unittest.TestCase):
    def test_wrap_and_roundtrip(self):
        g = Tangent(359.999, -30)
        pos = (0.001, -29.999)
        x, y = g.project(*pos)
        self.assertAlmostEqual(x, 6.235, delta=0.05)
        ra, dec = g.unproject(x, y)
        self.assertAlmostEqual(ra, pos[0], places=9)
        self.assertAlmostEqual(dec, pos[1], places=9)

    def test_polygon_inclusion_and_boundary(self):
        sq = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        self.assertTrue(polygon_contains((0, 0), sq))
        self.assertFalse(polygon_contains((2, 0), sq))
        self.assertIsNone(polygon_contains((1, 0), sq))

    def test_separation(self):
        self.assertAlmostEqual(spherical_separation_arcsec((180, -30), (180, -30)), 0)
        self.assertAlmostEqual(spherical_separation_arcsec((359.999, 0), (0.001, 0)), 7.2, places=5)

    def test_beam_radius(self):
        self.assertAlmostEqual(beam_radius_as(1.13, 350.9853598277315, 7), 14.218, delta=0.02)


class SnapshotTests(unittest.TestCase):
    def test_observed_archive_case(self):
        obs = read_tap(HERE / "data/case_E_tap.xml")
        fields = read_fields(HERE / "data/science_pointings.csv", obs["asdm_uid"])
        self.assertEqual(obs["proposal_id"], "2021.2.00176.S")
        self.assertEqual(len(fields), 19)
        self.assertEqual({x["field_id"] for x in fields}, set(range(3, 22)))
        self.assertEqual({x["source_id"] for x in fields}, {"2"})
        self.assertEqual(len(parse_stcs(obs["s_region"])), 42)
        self.assertTrue(all(x["science_scan_count"] == "6" for x in fields))


if __name__ == "__main__":
    unittest.main()
