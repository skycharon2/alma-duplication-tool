"""Exploratory comparison of Archive STC-S footprints and per-field beam unions.

No formal duplication assessment is produced by this program.
Standard-library only; run with Python 3.11+.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ARCSEC_PER_RADIAN = 180.0 * 3600.0 / math.pi
C_M_S = 299_792_458.0
HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_tap(path: Path) -> dict:
    """Only a single TAP result row is accepted to prevent accidental row mixing."""
    root = ET.parse(path).getroot()
    table = next((e for e in root.iter() if local_name(e.tag) == "TABLE"), None)
    if table is None:
        raise ValueError("TAP VOTable has no TABLE")
    names = [e.attrib["name"] for e in table if local_name(e.tag) == "FIELD"]
    rows = []
    for tr in table.iter():
        if local_name(tr.tag) == "TR":
            cells = ["".join(td.itertext()).strip() for td in tr if local_name(td.tag) == "TD"]
            if len(cells) != len(names):
                raise ValueError("TAP row/column count mismatch")
            rows.append(dict(zip(names, cells)))
    if len(rows) != 1:
        raise ValueError(f"Expected 1 TAP row, found {len(rows)}; select one member explicitly")
    row = rows[0]
    if row.get("is_mosaic") != "T" or row.get("science_observation") != "T":
        raise ValueError("Expected a science Mosaic observation")
    return row


def read_fields(path: Path, asdm_uid: str) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("Empty science pointing CSV")
    field_ids = set()
    for row in rows:
        if row["asdm_uid"] != asdm_uid:
            raise ValueError("CSV ASDM does not match TAP ASDM")
        if row["science_intent"] != "OBSERVE_TARGET#ON_SOURCE":
            raise ValueError("Non-science intent in the supplied science field list")
        if row["frame"] != "ICRS" or row["array"] != "7m":
            raise ValueError("This case expects ICRS science fields from 7m array")
        k = int(row["field_id"])
        if k in field_ids:
            raise ValueError("Duplicate FIELD_ID in one ASDM")
        field_ids.add(k)
        ra, dec = float(row["ra_deg"]), float(row["dec_deg"])
        if not (math.isfinite(ra) and math.isfinite(dec) and 0 <= ra < 360 and -90 <= dec <= 90):
            raise ValueError("Invalid field RA/Dec")
        scans = [int(x) for x in row["science_scan_ids"].split(";") if x]
        if len(scans) != int(row["science_scan_count"]):
            raise ValueError("Science scan count does not match scan IDs")
        row["field_id"] = k
        row["ra_deg"], row["dec_deg"] = ra, dec
    return rows


def parse_stcs(s: str) -> list[tuple[float, float]]:
    parts = s.split()
    if len(parts) < 10 or parts[0].upper() != "POLYGON" or parts[1].upper() != "ICRS":
        raise ValueError("Expected STC-S Polygon ICRS with at least four vertices")
    nums = [float(v) for v in parts[2:]]
    if len(nums) % 2:
        raise ValueError("Odd STC-S coordinate count")
    coords = list(zip(nums[::2], nums[1::2]))
    if any(not (math.isfinite(ra) and math.isfinite(dec) and 0 <= ra < 360 and -90 <= dec <= 90)
           for ra, dec in coords):
        raise ValueError("Invalid STC-S coordinate")
    return coords


class Tangent:
    """Azimuthal-equidistant local tangent plane; x east, y north, in arcseconds."""

    def __init__(self, ra_deg: float, dec_deg: float):
        a, d = math.radians(ra_deg), math.radians(dec_deg)
        self.c = (math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d))
        self.e = (-math.sin(a), math.cos(a), 0.0)
        self.n = (-math.sin(d) * math.cos(a), -math.sin(d) * math.sin(a), math.cos(d))

    def project(self, ra_deg: float, dec_deg: float) -> tuple[float, float]:
        a, d = math.radians(ra_deg), math.radians(dec_deg)
        v = (math.cos(d) * math.cos(a), math.cos(d) * math.sin(a), math.sin(d))
        x = sum(v[i] * self.e[i] for i in range(3))
        y = sum(v[i] * self.n[i] for i in range(3))
        z = sum(v[i] * self.c[i] for i in range(3))
        length = math.hypot(x, y)
        theta = math.atan2(length, z)
        if theta > math.radians(3):
            raise ValueError("Footprint exceeds supported local projection extent (3 deg)")
        scale = ARCSEC_PER_RADIAN * (theta / length if length else 1.0)
        return (x * scale, y * scale)

    def unproject(self, x_as: float, y_as: float) -> tuple[float, float]:
        radius = math.hypot(x_as, y_as) / ARCSEC_PER_RADIAN
        if radius >= math.radians(3):
            raise ValueError("Unprojected point outside local projection extent")
        if radius == 0:
            v = self.c
        else:
            t = math.sin(radius) / math.hypot(x_as, y_as)
            v = tuple(math.cos(radius) * self.c[i]
                      + t * (x_as * self.e[i] + y_as * self.n[i]) for i in range(3))
        ra = math.degrees(math.atan2(v[1], v[0])) % 360
        dec = math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))
        return ra, dec


def point_segment_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    r2 = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / r2)) if r2 else 0.0
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def polygon_contains(point, vertices, boundary_tolerance_as=1e-6):
    """Return True/False, or None if extremely close to a polygon edge.

    Edges are straight in local azimuthal-equidistant coordinates; this is not an
    exact generic spherical STC-S polygon implementation.
    """
    x, y = point
    inside = False
    for i, (ax, ay) in enumerate(vertices):
        bx, by = vertices[(i + 1) % len(vertices)]
        if point_segment_dist(point, (ax, ay), (bx, by)) <= boundary_tolerance_as:
            return None
        if (ay > y) != (by > y):
            xc = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < xc:
                inside = not inside
    return inside


def spherical_separation_arcsec(p: tuple[float, float], q: tuple[float, float]) -> float:
    a1, d1 = map(math.radians, p)
    a2, d2 = map(math.radians, q)
    da = (a1 - a2 + math.pi) % (2 * math.pi) - math.pi
    s = math.sin((d1 - d2) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin(da / 2) ** 2
    return ARCSEC_PER_RADIAN * 2 * math.asin(math.sqrt(max(0, min(1, s))))


def minimum_separation(p, centers):
    return min(spherical_separation_arcsec(p, v) for v in centers)


def beam_radius_as(coeff: float, frequency_ghz: float, diameter_m: float) -> float:
    if min(coeff, frequency_ghz, diameter_m) <= 0:
        raise ValueError("Beam coefficient, frequency and diameter must be positive")
    return (coeff * C_M_S / (frequency_ghz * 1e9 * diameter_m)) * ARCSEC_PER_RADIAN / 2


def classify(p, polygon, centers, radius, tangent):
    xy = tangent.project(*p)
    a = polygon_contains(xy, polygon)
    distance = minimum_separation(p, centers)
    b = None if abs(distance - radius) <= 1e-6 else distance < radius
    return a, b, distance


def grid_sample(polygon, centers, tangent, radius, step_as=1.0, padding_as=3.0):
    xmin = min(x for x, _ in polygon) - radius - padding_as
    xmax = max(x for x, _ in polygon) + radius + padding_as
    ymin = min(y for _, y in polygon) - radius - padding_as
    ymax = max(y for _, y in polygon) + radius + padding_as
    nx = math.ceil((xmax - xmin) / step_as)
    ny = math.ceil((ymax - ymin) / step_as)
    if nx * ny > 250_000:
        raise ValueError("Too many raster points; increase --step-arcsec")
    counts = {"both": 0, "polygon_only": 0, "beam_only": 0, "neither": 0, "boundary_unclassified": 0}
    disagreements = []
    for yi in range(ny):
        y = ymin + (yi + 0.5) * step_as
        for xi in range(nx):
            x = xmin + (xi + 0.5) * step_as
            a, b, distance = classify(tangent.unproject(x, y), polygon, centers, radius, tangent)
            if a is None or b is None:
                counts["boundary_unclassified"] += 1
                continue
            k = ("both" if a and b else "polygon_only" if a else "beam_only" if b else "neither")
            counts[k] += 1
            if a != b:
                disagreements.append((round(x, 6), round(y, 6), k, round(distance, 6)))
    denom = counts["both"] + counts["polygon_only"] + counts["beam_only"]
    return {
        "raster_counts": counts,
        "intersection_over_union_raster": (counts["both"] / denom) if denom else None,
        "grid": {"step_arcsec": step_as, "nx": nx, "ny": ny,
                 "pixel_area_arcsec2": step_as ** 2},
        "disagreements": disagreements,
    }


def edge_sample(poly, centers, tangent, radius, offsets_as=(0.1, 0.5, 1.0)):
    rows = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            continue
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        nx, ny = -dy / length, dx / length
        for offset in offsets_as:
            for sign in (-1, 1):
                x, y = mx + sign * offset * nx, my + sign * offset * ny
                a_hit, b_hit, dist = classify(tangent.unproject(x, y), poly, centers, radius, tangent)
                rows.append({"edge_id": i, "offset_arcsec": sign * offset,
                             "ra_dec": tangent.unproject(x, y), "polygon": a_hit,
                             "beam_union": b_hit, "nearest_beam_arcsec": dist})
    return rows


def write_csv(path, rows, headers):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def run(args):
    tap_path, csv_path = Path(args.tap), Path(args.fields)
    row = read_tap(tap_path)
    fields = read_fields(csv_path, row["asdm_uid"])
    if len(fields) != 19 or {x["field_id"] for x in fields} != set(range(3, 22)):
        raise ValueError("Unexpected science FIELD_ID set; check supplied fixture")
    tangent = Tangent(float(row["s_ra"]), float(row["s_dec"]))
    polygon_sky = parse_stcs(row["s_region"])
    polygon = [tangent.project(*p) for p in polygon_sky]
    centers = [(x["ra_deg"], x["dec_deg"]) for x in fields]
    if len(centers) != len(set(centers)):
        raise ValueError("Unexpected identical science field coordinates")
    freq = float(row["frequency"])
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for coeff in args.coefficients:
        radius = beam_radius_as(coeff, freq, args.diameter_m)
        sample = grid_sample(polygon, centers, tangent, radius, args.step_arcsec)
        boundary = edge_sample(polygon, centers, tangent, radius)
        vertex_distances = [minimum_separation(p, centers) for p in polygon_sky]
        results.append({
            "coefficient": coeff, "radius_arcsec": radius,
            "vertex_to_nearest_field_arcsec": {
                "min": min(vertex_distances),
                "mean": sum(vertex_distances) / len(vertex_distances),
                "max": max(vertex_distances)},
            "grid": sample["grid"],
            "raster_counts": sample["raster_counts"],
            "intersection_over_union_raster": sample["intersection_over_union_raster"],
            "edge_probe_count": len(boundary),
            "edge_probe_disagreements": sum(1 for item in boundary if item["polygon"] is not None and item["beam_union"] is not None and item["polygon"] != item["beam_union"]),
        })
        write_csv(out / f"grid_disagreements_coeff_{coeff:.2f}.csv", [
            {"east_arcsec": x, "north_arcsec": y, "classification": klass,
             "nearest_beam_arcsec": distance}
            for x, y, klass, distance in sample["disagreements"]],
            ["east_arcsec", "north_arcsec", "classification", "nearest_beam_arcsec"])
        write_csv(out / f"edge_probes_coeff_{coeff:.2f}.csv", [
            {"edge_id": item["edge_id"], "offset_arcsec": item["offset_arcsec"],
             "ra_deg": item["ra_dec"][0], "dec_deg": item["ra_dec"][1],
             "s_region_inside": item["polygon"], "beam_union_inside": item["beam_union"],
             "nearest_beam_arcsec": item["nearest_beam_arcsec"]}
            for item in boundary],
            ["edge_id", "offset_arcsec", "ra_deg", "dec_deg",
             "s_region_inside", "beam_union_inside", "nearest_beam_arcsec"])
    output = {
        "experiment": "Archive s_region vs. science-FIELD circular beam-union model",
        "scope": "one public 7m Execution Block, not full Member completion",
        "policy_verdict": "NOT_EVALUATED",
        "footprint_semantics": "not established by this comparison",
        "s_region_polygon_model": "straight edges in local azimuthal-equidistant projection; approximate",
        "beam_union_model": "isotropic circular half-power beams; exploratory coefficient sweep",
        "project_code": row["proposal_id"], "target": row["target_name"],
        "member_ous_uid": row["member_ous_uid"], "asdm_uid": row["asdm_uid"],
        "frequency_ghz": freq, "diameter_m": args.diameter_m,
        "field_ids": sorted(int(x["field_id"]) for x in fields),
        "field_count": len(fields), "polygon_vertices": len(polygon),
        "source_sha256": {"tap_xml": digest(tap_path), "pointings_csv": digest(csv_path)},
        "coefficient_results": results,
    }
    (out / "summary.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ASDM: {row['asdm_uid']} | fields: {len(fields)} | s_region vertices: {len(polygon)}")
    for r in results:
        c = r["raster_counts"]
        print(f"coefficient={r['coefficient']:.2f} radius={r['radius_arcsec']:.3f} arcsec "
              f"IoU={r['intersection_over_union_raster']:.4f} "
              f"A-only={c['polygon_only']} B-only={c['beam_only']} "
              f"edge disagreements={r['edge_probe_disagreements']}/{r['edge_probe_count']}")
    print(f"Outputs: {out}")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tap", default=HERE / "data/case_E_tap.xml", type=Path)
    parser.add_argument("--fields", default=HERE / "data/science_pointings.csv", type=Path)
    parser.add_argument("--output", default=HERE / "results", type=Path)
    parser.add_argument("--diameter-m", type=float, default=7.0)
    parser.add_argument("--step-arcsec", type=float, default=1.0)
    parser.add_argument("--coefficients", type=float, nargs="+", default=[1.13, 1.15, 1.17])
    args = parser.parse_args()
    if args.step_arcsec <= 0:
        parser.error("--step-arcsec must be positive")
    run(args)


if __name__ == "__main__":
    main()
