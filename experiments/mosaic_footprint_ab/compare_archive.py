"""Compare Archive s_region with science FIELD circular half-power beam unions.

Supports 7m and 12m independently using the existing baseline geometry.
No claim is made that either model is an official duplication-policy region.
Standard library only; Python 3.11+.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from compare import (Tangent, beam_radius_as, digest, edge_sample, grid_sample,
                     minimum_separation, parse_stcs, read_tap, write_csv)

HERE = Path(__file__).resolve().parent
ARRAY_DIAMETERS = {"7m": 7.0, "12m": 12.0}


def read_science_fields(path: Path, tap: dict) -> tuple[list[dict], str]:
    """Validate CSV provenance, positions, science scans and array identity."""
    required = {"project_code", "member_ous_uid", "asdm_uid", "array", "field_id",
                "target_name", "source_id", "frame", "ra_deg", "dec_deg",
                "science_scan_count", "science_scan_ids", "science_intent"}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"Pointing CSV missing columns: {sorted(required - set(reader.fieldnames or []))}")
        rows = list(reader)
    if not rows:
        raise ValueError("Empty science pointing CSV")
    ids = set()
    positions = set()
    arrays = set()
    for row in rows:
        for csv_key, tap_key in (("project_code", "proposal_id"),
                                 ("member_ous_uid", "member_ous_uid"),
                                 ("asdm_uid", "asdm_uid"),
                                 ("target_name", "target_name")):
            if row[csv_key] != tap[tap_key]:
                raise ValueError(f"Pointing CSV {csv_key} differs from TAP")
        if row["science_intent"] != "OBSERVE_TARGET#ON_SOURCE" or row["frame"] != "ICRS":
            raise ValueError("Expected ICRS ON_SOURCE science fields")
        arrays.add(row["array"])
        fid = int(row["field_id"])
        if fid in ids:
            raise ValueError(f"Repeated FIELD_ID {fid}")
        ids.add(fid)
        ra, dec = float(row["ra_deg"]), float(row["dec_deg"])
        if not (math.isfinite(ra) and math.isfinite(dec) and 0 <= ra < 360 and -90 <= dec <= 90):
            raise ValueError(f"Invalid FIELD position: {fid}")
        if (ra, dec) in positions:
            raise ValueError("Repeated FIELD centre: review pointing provenance")
        positions.add((ra, dec))
        scans = row["science_scan_ids"].split(";")
        if not scans or any(not x.isdecimal() for x in scans):
            raise ValueError("Invalid scan IDs")
        if len(scans) != len(set(scans)) or len(scans) != int(row["science_scan_count"]):
            raise ValueError("Science scan count/IDs mismatch")
        row["field_id"] = fid
        row["ra_deg"], row["dec_deg"] = ra, dec
    if len(arrays) != 1 or not arrays <= ARRAY_DIAMETERS.keys():
        raise ValueError(f"Expected a single 7m or 12m array, got {sorted(arrays)}")
    return rows, next(iter(arrays))


def run(args: argparse.Namespace) -> dict:
    tap_path, fields_path = Path(args.tap), Path(args.fields)
    tap = read_tap(tap_path)
    fields, array = read_science_fields(fields_path, tap)
    if args.expected_array and args.expected_array != array:
        raise ValueError(f"Expected {args.expected_array}, CSV contains {array}")
    if not math.isfinite(args.step_arcsec) or args.step_arcsec <= 0:
        raise ValueError("Positive finite grid step required")
    if not args.coefficients or any(not math.isfinite(c) or c <= 0 for c in args.coefficients):
        raise ValueError("Positive finite beam coefficients required")
    diameter = ARRAY_DIAMETERS[array]
    frequency = float(tap["frequency"])
    if not math.isfinite(frequency) or frequency <= 0:
        raise ValueError("Positive finite frequency required")
    tangent = Tangent(float(tap["s_ra"]), float(tap["s_dec"]))
    polygon_sky = parse_stcs(tap["s_region"])
    polygon_xy = [tangent.project(*p) for p in polygon_sky]
    centers = [(f["ra_deg"], f["dec_deg"]) for f in fields]
    vertex_distances = [minimum_separation(p, centers) for p in polygon_sky]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for coefficient in args.coefficients:
        radius = beam_radius_as(coefficient, frequency, diameter)
        sample = grid_sample(polygon_xy, centers, tangent, radius, args.step_arcsec)
        edge_probes = edge_sample(polygon_xy, centers, tangent, radius)
        results.append({
            "coefficient": coefficient,
            "radius_arcsec": radius,
            "vertex_to_nearest_field_arcsec": {
                "min": min(vertex_distances),
                "mean": sum(vertex_distances) / len(vertex_distances),
                "max": max(vertex_distances),
            },
            "grid": sample["grid"],
            "raster_counts": sample["raster_counts"],
            "intersection_over_union_raster": sample["intersection_over_union_raster"],
            "edge_probe_count": len(edge_probes),
            "edge_probe_disagreements": sum(
                1 for p in edge_probes if p["polygon"] is not None
                and p["beam_union"] is not None and p["polygon"] != p["beam_union"]
            ),
        })
        write_csv(
            output_dir / f"grid_disagreements_coeff_{coefficient:.2f}.csv",
            [dict(east_arcsec=x, north_arcsec=y, classification=kind,
                  nearest_beam_arcsec=dist)
             for x, y, kind, dist in sample["disagreements"]],
            ["east_arcsec", "north_arcsec", "classification", "nearest_beam_arcsec"],
        )
        write_csv(
            output_dir / f"edge_probes_coeff_{coefficient:.2f}.csv",
            [dict(edge_id=p["edge_id"], offset_arcsec=p["offset_arcsec"],
                  ra_deg=p["ra_dec"][0], dec_deg=p["ra_dec"][1],
                  s_region_inside=p["polygon"], beam_union_inside=p["beam_union"],
                  nearest_beam_arcsec=p["nearest_beam_arcsec"])
             for p in edge_probes],
            ["edge_id", "offset_arcsec", "ra_deg", "dec_deg",
             "s_region_inside", "beam_union_inside", "nearest_beam_arcsec"],
        )
    output = {
        "experiment": "Archive Mosaic footprint A/B: s_region vs circular beam union",
        "policy_verdict": "NOT_EVALUATED",
        "scope": "single ASDM/Execution Block; Member-wide completeness unverified",
        "s_region_semantics": "official half-power equivalence not established",
        "polygon_model": "locally projected straight STC-S polygon edges (approximate)",
        "beam_model": "circular half-power disks per science FIELD (hypothesis)",
        "project_code": tap["proposal_id"],
        "target_name": tap["target_name"],
        "member_ous_uid": tap["member_ous_uid"],
        "asdm_uid": tap["asdm_uid"],
        "array": array,
        "diameter_m": diameter,
        "frequency_ghz": frequency,
        "science_field_count": len(fields),
        "science_field_ids": sorted(f["field_id"] for f in fields),
        "s_region_vertex_count": len(polygon_sky),
        "source_sha256": {"tap": digest(tap_path), "fields": digest(fields_path)},
        "coefficient_results": results,
    }
    (output_dir / "summary.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"ASDM: {tap['asdm_uid']} | array: {array} | science fields: {len(fields)} "
          f"| s_region vertices: {len(polygon_sky)}")
    for result in results:
        counts = result["raster_counts"]
        print(f"coefficient={result['coefficient']:.2f} "
              f"radius={result['radius_arcsec']:.3f}\" "
              f"IoU={result['intersection_over_union_raster']:.4f} "
              f"A-only={counts['polygon_only']} B-only={counts['beam_only']} "
              f"edge disagreements={result['edge_probe_disagreements']}/{result['edge_probe_count']}")
    print("Policy verdict: NOT_EVALUATED")
    print(f"Outputs: {output_dir}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tap", type=Path, required=True)
    parser.add_argument("--fields", type=Path, required=True)
    parser.add_argument("--expected-array", choices=("7m", "12m"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--step-arcsec", type=float, default=1.0)
    parser.add_argument("--coefficients", nargs="+", type=float, default=[1.13, 1.15, 1.17])
    args = parser.parse_args()
    try:
        run(args)
    except (KeyError, ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
