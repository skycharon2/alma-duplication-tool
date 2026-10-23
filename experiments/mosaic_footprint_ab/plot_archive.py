"""Optional diagnostic overlay for a 7m/12m Archive Mosaic A/B experiment.

Requires matplotlib. The displayed beam boundaries are model assumptions.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from compare import Tangent, beam_radius_as, parse_stcs, read_tap
from compare_archive import read_science_fields, ARRAY_DIAMETERS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tap", type=Path, required=True)
    parser.add_argument("--fields", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--coefficient", type=float, default=1.13)
    args = parser.parse_args()

    row = read_tap(args.tap)
    fields, array = read_science_fields(args.fields, row)
    tangent = Tangent(float(row["s_ra"]), float(row["s_dec"]))
    vertices = [tangent.project(*p) for p in parse_stcs(row["s_region"])]
    radius = beam_radius_as(args.coefficient, float(row["frequency"]), ARRAY_DIAMETERS[array])

    fig, ax = plt.subplots(figsize=(8.5, 8.3))
    px, py = zip(*(vertices + [vertices[0]]))
    ax.fill(px, py, alpha=0.12, label="Archive s_region")
    ax.plot(px, py, lw=1.5)
    field_positions = []
    for field in fields:
        x, y = tangent.project(field["ra_deg"], field["dec_deg"])
        field_positions.append((x, y))
        ax.add_patch(Circle((x, y), radius, fill=False, lw=0.9, alpha=0.65))
        ax.annotate(str(field["field_id"]), (x, y), xytext=(3, 4),
                    textcoords="offset points", fontsize=7)
    ax.scatter([p[0] for p in field_positions], [p[1] for p in field_positions],
               s=16, marker="+", label="Science FIELD centre")
    disagreement = args.results_dir / f"grid_disagreements_coeff_{args.coefficient:.2f}.csv"
    if disagreement.exists():
        with disagreement.open(newline="", encoding="utf-8") as f:
            points = list(csv.DictReader(f))
        for kind, marker in (("polygon_only", "x"), ("beam_only", ".")):
            selected = [p for p in points if p["classification"] == kind]
            if selected:
                ax.scatter([float(p["east_arcsec"]) for p in selected],
                           [float(p["north_arcsec"]) for p in selected],
                           s=25, marker=marker, label=kind.replace("_", " "))
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("East offset (arcsec)")
    ax.set_ylabel("North offset (arcsec)")
    ax.set_title(f"{row['target_name']} | {array} | {float(row['frequency']):.3f} GHz\n"
                 f"s_region vs circular beam union, coefficient {args.coefficient:.2f}"
                 "\nExploratory geometry; no ALMA policy verdict", fontsize=11)
    ax.grid(alpha=0.2)
    ax.legend(loc="best", fontsize="small")
    fig.tight_layout()
    output = args.results_dir / f"overlay_coeff_{args.coefficient:.2f}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=170)
    plt.close(fig)
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
