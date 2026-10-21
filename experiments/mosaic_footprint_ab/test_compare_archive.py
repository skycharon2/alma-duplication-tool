"""Regression checks for the 12m observed-case extractor and generic A/B runner."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import tempfile
import unittest

from compare import read_tap, parse_stcs
from compare_archive import read_science_fields, run
from extract_science_fields import dms_degrees, extract, hms_degrees, COLUMNS

HERE = Path(__file__).resolve().parent
TAP = HERE / "data/ngc5248_12m_tap.xml"
LISTOBS = HERE / "data/ngc5248_12m_listobs.txt"
FIELDS = HERE / "data/ngc5248_12m_pointings.csv"


class Observed12mTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tap = read_tap(TAP)

    def test_12m_tap_provenance(self):
        self.assertEqual(self.tap["proposal_id"], "2019.1.01718.S")
        self.assertEqual(self.tap["asdm_uid"], "uid://A002/Xeaae1d/X1a2")
        self.assertEqual(len(parse_stcs(self.tap["s_region"])), 33)

    def test_scan_field_linkage_and_csv_snapshot(self):
        rows = extract(LISTOBS.read_text(encoding="utf-8"), tap_row=self.tap, array="12m")
        self.assertEqual([r["field_id"] for r in rows], list(range(4, 15)))
        self.assertEqual({r["science_scan_count"] for r in rows}, {7})
        self.assertEqual({r["source_id"] for r in rows}, {4})
        self.assertEqual(sum(r["science_scan_count"] for r in rows), 77)
        with FIELDS.open(newline="", encoding="utf-8") as f:
            snapshot = list(csv.DictReader(f))
        self.assertEqual([r["ra_deg"] for r in rows], [r["ra_deg"] for r in snapshot])
        self.assertEqual([str(r["field_id"]) for r in rows], [r["field_id"] for r in snapshot])

    def test_field_4_is_science_and_atmosphere(self):
        raw = LISTOBS.read_text(encoding="utf-8")
        self.assertIn("8      4 NGC5248", raw)
        self.assertIn("11      4 NGC5248", raw)
        rows = extract(raw, tap_row=self.tap, array="12m")
        self.assertEqual(rows[0]["field_id"], 4)
        self.assertEqual(rows[0]["science_scan_ids"], "11;17;23;32;38;47;50")

    def test_sexagesimal_sign_and_positions(self):
        self.assertAlmostEqual(hms_degrees("13:37:31.927000"), 204.38302916666669, places=10)
        self.assertAlmostEqual(dms_degrees("+08.53.07.38000"), 8.88538333333333, places=10)
        self.assertAlmostEqual(dms_degrees("-59.19.39.61139"), -59.32766983055556, places=10)
        self.assertRaises(ValueError, dms_degrees, "+90.01.00.0")

    def test_generic_reader_12m(self):
        rows, array = read_science_fields(FIELDS, self.tap)
        self.assertEqual((array, len(rows)), ("12m", 11))
        self.assertEqual({r["field_id"] for r in rows}, set(range(4, 15)))

    def test_read_rejects_cross_asdm(self):
        with FIELDS.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows[0]["asdm_uid"] = "uid://A002/incorrect"
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp) / "wrong.csv"
            with tmp.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "asdm_uid"):
                read_science_fields(tmp, self.tap)

    def test_existing_7m_snapshot_remains_compatible(self):
        original_tap = HERE / "data/case_E_tap.xml"
        original_fields = HERE / "data/science_pointings.csv"
        if not original_tap.exists() or not original_fields.exists():
            self.skipTest("Original 7m fixture is not installed")
        rows, array = read_science_fields(original_fields, read_tap(original_tap))
        self.assertEqual(array, "7m")
        self.assertEqual(len(rows), 19)

    def test_extract_markdown_wrapped_7m(self):
        tap = read_tap(HERE / "data/case_E_tap.xml")
        raw = (HERE / "data/source_listobs.md").read_text()
        rows = extract(raw, tap_row=tap, array="7m")
        self.assertEqual([r["field_id"] for r in rows], list(range(3, 22)))
        with (HERE / "data/science_pointings.csv").open(newline="") as f:
            snapshot = list(csv.DictReader(f))
        for actual, expected in zip(rows, snapshot):
            self.assertEqual(str(actual["field_id"]), expected["field_id"])
            self.assertAlmostEqual(float(actual["ra_deg"]), float(expected["ra_deg"]), places=10)
            self.assertAlmostEqual(float(actual["dec_deg"]), float(expected["dec_deg"]), places=10)

    def test_reject_missing_wrong_and_ambiguous_ms_headers(self):
        raw = LISTOBS.read_text()
        correct = "uid___A002_Xeaae1d_X1a2.ms"
        for invalid in ("", raw.replace(correct, correct + ".backup"), raw + raw):
            with self.subTest(header=invalid[:60]):
                with self.assertRaisesRegex(ValueError, "MeasurementSet"):
                    extract(invalid, tap_row=self.tap, array="12m")

    def test_compare_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            args = argparse.Namespace(tap=TAP, fields=FIELDS, output_dir=Path(temp),
                                      expected_array="12m", step_arcsec=1.0,
                                      coefficients=[1.13])
            report = run(args)
            self.assertEqual(report["policy_verdict"], "NOT_EVALUATED")
            self.assertEqual(report["science_field_count"], 11)
            val = report["coefficient_results"][0]
            self.assertAlmostEqual(val["radius_arcsec"], 8.50150726885, places=8)
            self.assertAlmostEqual(val["intersection_over_union_raster"],
                                   0.9537848605577689, places=10)
            self.assertTrue((Path(temp) / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
