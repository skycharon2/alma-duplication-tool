"""Compare native C1 OT centres with the shared-centre 7-m approximation.

Run from any directory; no network access or scientific assessment is performed.
"""

import csv
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "alma-c1-mpl"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/ot_pointings/custom_offsets_2026_11_02"
OUT = ROOT / "reports/custom-aca-c1"
ORIGIN = SkyCoord(150 * u.deg, -30 * u.deg, frame="icrs")
# Native OT displayed HPBW at the controlled case's 107 GHz frequency.
RADIUS = 93.29158 / 2


def read_native(path):
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("--")) + 1
    rows = list(csv.reader(lines[start:]))
    assert all(row[2:] == ["Absolute", "DEGREES"] for row in rows)
    return SkyCoord([float(r[0]) for r in rows] * u.deg,
                    [float(r[1]) for r in rows] * u.deg, frame="icrs")


def offsets(coords):
    local = coords.transform_to(ORIGIN.skyoffset_frame())
    return local.lon.arcsec, local.lat.arcsec


def draw(ax, coords, color, linestyle, marker, prefix, fill=True):
    for i, centre in enumerate(coords, 1):
        ring = centre.directional_offset_by(np.linspace(0, 360, 361) * u.deg,
                                           RADIUS * u.arcsec)
        x, y = offsets(ring)
        if fill:
            ax.fill(x, y, color=color, alpha=0.035)
        ax.plot(x, y, color=color, linestyle=linestyle, linewidth=1.5, alpha=0.85)
        cx, cy = offsets(centre)
        ax.scatter(cx, cy, color=color, marker=marker, s=55, zorder=5)
        ax.annotate(f"{prefix}{i}", (cx, cy), xytext=(5, 6),
                    textcoords="offset points", color=color, fontsize=9)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [FIXTURE / f"ot-{array}-absolute.txt" for array in ("12m", "7m")]
    twelve, seven = map(read_native, paths)
    assert (len(twelve), len(seven)) == (7, 3)
    fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharex=True, sharey=True)
    purple, orange = "#963c83", "#ac5900"
    draw(axes[0], twelve, purple, "--", "x", "P")
    draw(axes[1], seven, orange, "-", "+", "A")
    draw(axes[2], twelve, purple, "--", "x", "P", fill=False)
    draw(axes[2], seven, orange, "-", "+", "A", fill=False)
    titles = ["Shared-centre approximation: 7 centres",
              "Native OT 7-m export: 3 centres", "Overlay: different centres and coverage"]
    for ax, title in zip(axes, titles):
        ax.set(title=title, xlabel="East offset (arcsec)  ←", xlim=(95, -95),
               ylim=(-95, 95), aspect="equal")
        ax.grid(alpha=0.2)
        ax.axhline(0, color="grey", linewidth=0.6, alpha=0.4)
        ax.axvline(0, color="grey", linewidth=0.6, alpha=0.4)
    axes[0].set_ylabel("North offset (arcsec)")
    fig.suptitle("C1 Custom Mosaic · 107 GHz · 7-m geometry comparison", fontsize=17)
    fig.legend(handles=[Line2D([], [], color=purple, linestyle="--", marker="x",
                              label="Approximation: 7-m beams at the 12-m input centres"),
                        Line2D([], [], color=orange, marker="+",
                               label="OT: 7-m beams at the 3 exported 7-m centres")],
               loc="lower center", bbox_to_anchor=(0.5, 0.09), ncol=2, frameon=False)
    fig.text(0.5, 0.035, "Circles: illustrative half-power radius 46.64579″ (OT HPBW / 2). "
             "Not a sensitivity map or duplication verdict.\n"
             "Spherical beam boundaries projected about ICRS (150°, −30°); "
             "native export coordinates are references, not algorithm predictions.",
             ha="center", fontsize=10, color="#45515e")
    fig.tight_layout(rect=(0, 0.24, 1, 0.94))
    for suffix in ("png", "svg"):
        fig.savefig(OUT / f"c1-7m-comparison.{suffix}", dpi=170)
    plt.close(fig)
    evidence = {"case": "C1", "frequency_ghz": 107,
                "ot_7m_hpbw_arcsec": 2 * RADIUS,
                "scientific_assessment": "NOT_EVALUATED", "sources": []}
    for path, coords in zip(paths, (twelve, seven)):
        x, y = offsets(coords)
        evidence["sources"].append({"file": str(path.relative_to(ROOT)),
            "sha256": sha256(path.read_bytes()).hexdigest(), "count": len(coords),
            "icrs_deg": list(zip(coords.ra.deg.tolist(), coords.dec.deg.tolist())),
            "offsets_arcsec": list(zip(x.tolist(), y.tolist()))})
    (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(OUT / "c1-7m-comparison.png")


if __name__ == "__main__":
    main()
