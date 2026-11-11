"""Render production Rectangle grids against independent OT D3 coordinates."""
import json
import math
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'alma-c1-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from alma_duplicate.queue_rectangle_grid import RectangleGeometry, generate_rectangle_grid
from alma_duplicate.queue_mosaic_binding import _match

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/rectangle-array-plot'


def main():
    fixture = json.loads((ROOT / 'tests/fixtures/queue/rectangle_d3_reference.json').read_text())
    geometry = RectangleGeometry(**fixture['geometry'])
    origin = SkyCoord(geometry.ra_deg*u.deg, geometry.dec_deg*u.deg)
    frame = origin.skyoffset_frame()

    def xy(coords):
        c = coords.transform_to(frame)
        return c.lon.arcsec, c.lat.arcsec

    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharex=True, sharey=True)
    audit = []
    for ax, reference, color in zip(axes, fixture['arrays'], ['#1565a8', '#a55700']):
        diameter = reference['diameter_m']
        grid = generate_rectangle_grid(geometry, diameter, spacing_reference_diameter_m=12)
        points = SkyCoord([[p['ra_deg'], p['dec_deg']] for p in grid['pointings']], unit='deg')
        ot = SkyCoord(reference['coordinates_icrs_deg'], unit='deg')
        distances = points[:, None].separation(ot[None, :]).arcsec
        matching = _match([[j for j, d in enumerate(row) if d <= .001] for row in distances])
        assert len(matching) == len(points) == len(ot)
        radius = 1.13 * 299792458 / (fixture['representative_frequency_ghz'] * 1e9 * diameter) * 180 * 3600 / math.pi / 2
        for i, point in enumerate(points, 1):
            ring = point.directional_offset_by(np.linspace(0, 360, 361)*u.deg, radius*u.arcsec)
            ax.fill(*xy(ring), color=color, alpha=.035)
            ax.plot(*xy(ring), color=color, alpha=.6, linewidth=1)
            x, y = xy(point)
            ax.annotate(str(i), (x, y), xytext=(6, 5), textcoords='offset points', fontsize=8)
        ax.scatter(*xy(points), s=85, facecolors='none', edgecolors=color, linewidths=1.5, zorder=4)
        ax.scatter(*xy(ot), s=38, marker='+', color='black', linewidths=1.3, zorder=5)
        centre = SkyCoord(*grid['center_icrs_deg'], unit='deg')
        angle = math.radians(geometry.pa_deg)
        vertices = []
        half_length, half_width = geometry.length_arcsec / 2, geometry.width_arcsec / 2
        for p, q in [(-half_length, -half_width), (half_length, -half_width),
                     (half_length, half_width), (-half_length, half_width),
                     (-half_length, -half_width)]:
            east, north = p*math.cos(angle)+q*math.sin(angle), -p*math.sin(angle)+q*math.cos(angle)
            vertices.append(centre.directional_offset_by(math.atan2(east,north)*u.rad, math.hypot(east,north)*u.arcsec))
        ax.plot(*xy(SkyCoord(vertices)), '--', color='#6b6872', linewidth=1)
        ax.set(title=f'{diameter}-m array · {len(points)} pointings',
               xlabel='East offset (arcsec) ←', xlim=(125,-85), ylim=(-115,95), aspect='equal')
        ax.grid(alpha=.2)
        maximum = max(float(distances[i,j]) for i,j in matching.items())
        audit.append(dict(diameter_m=diameter, count=len(points), matched=len(matching),
                          maximum_residual_arcsec=maximum, spacing_arcsec=grid['spacing_arcsec'],
                          half_power_radius_arcsec=radius))
    axes[0].set_ylabel('North offset (arcsec)')
    fig.suptitle('Rectangle D3 · production grids versus native OT coordinates', fontsize=15)
    fig.legend(handles=[Line2D([],[],marker='o',markerfacecolor='none',color='#1565a8',linestyle='none',label='Production centre'),
                        Line2D([],[],marker='+',color='black',linestyle='none',label='OT centre'),
                        Line2D([],[],linestyle='--',color='#6b6872',label='Input rectangle')],
               loc='lower center', bbox_to_anchor=(.5,.1), ncol=3, frameon=False)
    fig.text(.5,.025,'100″ × 70″ · PA 30° · centre offset (+20″, −10″) · 107 GHz\n'
             'Equal angular scale; circles show illustrative half-power beams, not sensitivity.',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.2,1,.94))
    OUT.mkdir(parents=True,exist_ok=True)
    for extension in ['png','svg']:
        fig.savefig(OUT/f'rectangle-arrays.{extension}',dpi=170)
    plt.close(fig)
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))


if __name__ == '__main__':
    main()
