"""Optional diagnostic plot of the 7m Archive footprint comparison (matplotlib)."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from compare import HERE, Tangent, beam_radius_as, parse_stcs, read_fields, read_tap


def main():
    obs = read_tap(HERE / "data/case_E_tap.xml")
    tangent = Tangent(float(obs["s_ra"]), float(obs["s_dec"]))
    fields = read_fields(HERE / "data/science_pointings.csv", obs["asdm_uid"])
    poly = [tangent.project(*p) for p in parse_stcs(obs["s_region"])]
    radius = beam_radius_as(1.13, float(obs["frequency"]), 7)
    fig, ax = plt.subplots(figsize=(7, 10))
    ax.fill([p[0] for p in poly], [p[1] for p in poly], alpha=.12, label="Archive s_region (projected polygon)")
    ax.plot([p[0] for p in poly + poly[:1]], [p[1] for p in poly + poly[:1]], linewidth=1.5)
    for i, f in enumerate(fields):
        x, y = tangent.project(f["ra_deg"], f["dec_deg"])
        circle = Circle((x,y),radius,fill=False,linewidth=.75,alpha=.45)
        ax.add_patch(circle)
        ax.scatter([x],[y],s=12,marker="+",label="Observed science FIELD centre" if i == 0 else None)
    disagree = HERE / "results/grid_disagreements_coeff_1.13.csv"
    with disagree.open(newline="",encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for label in ["polygon_only", "beam_only"]:
        items = [r for r in rows if r["classification"] == label]
        if items:
            ax.scatter([float(r["east_arcsec"]) for r in items],
                       [float(r["north_arcsec"]) for r in items],
                       s=17, marker="x", label=label.replace("_"," "))
    ax.set_aspect("equal")
    ax.set_xlabel("East offset (arcsec)")
    ax.set_ylabel("North offset (arcsec)")
    ax.set_title("SPT0303-59: s_region vs. circular beam-union model\n7m; coefficient 1.13; diagnostic, not a policy verdict")
    ax.grid(alpha=.2)
    ax.legend(loc="best",fontsize="small")
    fig.tight_layout()
    destination = HERE / "results/overlay_coeff_1.13.png"
    fig.savefig(destination,dpi=150)
    print(f"Saved: {destination}")


if __name__ == "__main__":
    main()
