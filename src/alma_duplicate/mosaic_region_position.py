"""Standalone Mosaic position rule using the project's Archive s_region policy.

Supports ICRS circles and simple polygons contained within a 10-degree spherical
cap. Polygon edges are minor great-circle arcs; the bounded small interior is
used regardless of vertex order. Compound/large regions fail explicitly.
"""
from collections import Counter
from hashlib import sha256
import math

MAX_VERTICES = 512
MAX_POINTS = 10000
ARCSEC = 180 / math.pi * 3600


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(v):
    length = math.sqrt(dot(v, v))
    if length < 1e-14:
        raise ValueError('DEGENERATE_REGION')
    return tuple(x/length for x in v)


def angle(a, b):
    return math.atan2(math.sqrt(dot(cross(a, b), cross(a, b))), dot(a, b))


def vector(ra, dec):
    if isinstance(ra, bool) or isinstance(dec, bool):
        raise ValueError('INVALID_COORDINATE')
    ra, dec = float(ra), float(dec)
    if not math.isfinite(ra) or not math.isfinite(dec) or not 0 <= ra <= 360 or not -90 <= dec <= 90:
        raise ValueError('INVALID_COORDINATE')
    a, d = math.radians(ra), math.radians(dec)
    return (math.cos(d)*math.cos(a), math.cos(d)*math.sin(a), math.sin(d))


def orient(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def on_segment(a, b, c):
    return (abs(orient(a, b, c)) <= 1e-16 and
            min(a[0], b[0])-1e-14 <= c[0] <= max(a[0], b[0])+1e-14 and
            min(a[1], b[1])-1e-14 <= c[1] <= max(a[1], b[1])+1e-14)


def edge_distance(p, a, b):
    normal = unit(cross(a, b))
    projection = tuple(p[i]-dot(p, normal)*normal[i] for i in range(3))
    best = min(angle(p, a), angle(p, b))
    if dot(projection, projection) > 1e-28:
        q = unit(projection)
        # Closest projection must lie on the minor arc, not its extension.
        if angle(a, q)+angle(q, b) <= angle(a, b)+1e-12:
            best = min(best, angle(p, q))
    return best*ARCSEC


class Region:
    def __init__(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ValueError('S_REGION_MISSING')
        if len(text) > 100000:
            raise ValueError('REGION_SIZE_LIMIT')
        parts = text.split()
        if len(parts) < 2 or parts[1].upper() != 'ICRS':
            raise ValueError('UNSUPPORTED_REGION_FRAME')
        self.kind = parts[0].upper()
        if self.kind not in ('POLYGON', 'CIRCLE'):
            raise ValueError('UNSUPPORTED_REGION_SHAPE')
        try:
            values = list(map(float, parts[2:]))
        except ValueError:
            raise ValueError('UNSUPPORTED_OR_INVALID_REGION_SYNTAX') from None
        if not all(map(math.isfinite, values)):
            raise ValueError('NONFINITE_REGION')
        if self.kind == 'CIRCLE':
            if len(values) != 3 or not 0 < values[2] < 90:
                raise ValueError('UNSUPPORTED_CIRCLE')
            self.center = vector(*values[:2])
            self.radius = values[2]*3600
            return
        if len(values) < 6 or len(values) % 2 or len(values)//2 > MAX_VERTICES+1:
            raise ValueError('INVALID_POLYGON_VERTEX_COUNT')
        self.vertices = [vector(a, d) for a, d in zip(values[::2], values[1::2])]
        if angle(self.vertices[0], self.vertices[-1]) < 1e-14:
            self.vertices.pop()
        if not 3 <= len(self.vertices) <= MAX_VERTICES:
            raise ValueError('INVALID_POLYGON_VERTEX_COUNT')
        for i, a in enumerate(self.vertices):
            if any(angle(a, b) < 1e-14 for b in self.vertices[i+1:]):
                raise ValueError('REPEATED_POLYGON_VERTEX')
        self.center = unit(tuple(sum(v[i] for v in self.vertices) for i in range(3)))
        self.cap = max(angle(self.center, v) for v in self.vertices)
        if self.cap > math.radians(10):
            raise ValueError('POLYGON_OUTSIDE_SUPPORTED_CAP')
        axis = (0, 0, 1) if abs(self.center[2]) < .9 else (1, 0, 0)
        self.east = unit(cross(axis, self.center))
        self.north = cross(self.center, self.east)
        self.xy = [self.project(v) for v in self.vertices]
        self.edges = list(zip(self.vertices, self.vertices[1:]+self.vertices[:1]))
        edges = list(zip(self.xy, self.xy[1:]+self.xy[:1]))
        area = sum(a[0]*b[1]-b[0]*a[1] for a, b in edges)
        if abs(area) < 1e-16:
            raise ValueError('DEGENERATE_POLYGON')
        for i, (a, b) in enumerate(edges):
            for j in range(i+1, len(edges)):
                c, d = edges[j]
                if j == i+1 or (i == 0 and j == len(edges)-1):
                    continue
                if (orient(a,b,c)*orient(a,b,d) < 0 and orient(c,d,a)*orient(c,d,b) < 0
                        or any((on_segment(a,b,c), on_segment(a,b,d), on_segment(c,d,a), on_segment(c,d,b)))):
                    raise ValueError('SELF_INTERSECTING_POLYGON')
        # Adjacent collinear backtracking is also an overlapping edge.
        for i, b in enumerate(self.xy):
            a, c = self.xy[i-1], self.xy[(i+1) % len(self.xy)]
            if abs(orient(a,b,c)) < 1e-16 and dot((a[0]-b[0],a[1]-b[1]),(c[0]-b[0],c[1]-b[1])) > 0:
                raise ValueError('OVERLAPPING_POLYGON_EDGES')

    def project(self, p):
        return dot(p, self.east)/dot(p, self.center), dot(p, self.north)/dot(p, self.center)

    def classify(self, point, epsilon):
        p = vector(point['ra_deg'], point['dec_deg'])
        if self.kind == 'CIRCLE':
            delta = angle(p, self.center)*ARCSEC-self.radius
            return 'BOUNDARY' if abs(delta) <= epsilon else 'INSIDE' if delta < 0 else 'OUTSIDE'
        # A small spherical cap is convex and contains the entire small polygon.
        if angle(p, self.center) > self.cap+epsilon/ARCSEC:
            return 'OUTSIDE'
        if min(edge_distance(p,a,b) for a,b in self.edges) <= epsilon:
            return 'BOUNDARY'
        x, y = self.project(p)
        inside = False
        for (ax,ay),(bx,by) in zip(self.xy,self.xy[1:]+self.xy[:1]):
            if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
                inside = not inside
        return 'INSIDE' if inside else 'OUTSIDE'


def assess_region_position(proposed, s_region, *, candidate_id, boundary_arcsec=0.001):
    """Evaluate one candidate only. Invalid regions yield UNKNOWN, never absence.

    Caller supplies the region from that candidate's metadata context. This pure
    function records the identity but does not verify upstream receipt binding.
    """
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError('Candidate identity required')
    if isinstance(boundary_arcsec, bool) or not math.isfinite(boundary_arcsec) or not 0 < boundary_arcsec <= 1:
        raise ValueError('Boundary tolerance must be in (0, 1] arcsec')
    points = proposed.get('points')
    if not isinstance(points, list) or not 0 < len(points) <= MAX_POINTS:
        raise ValueError('Require 1..10000 proposed pointings')
    ids = [p.get('id') for p in points]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Require unique pointing IDs')
    for p in points:
        vector(p['ra_deg'], p['dec_deg'])
    reasons = []
    try:
        region = Region(s_region)
        statuses = [region.classify(p, boundary_arcsec) for p in points]
    except (ValueError, TypeError) as exc:
        statuses = ['UNKNOWN']*len(points)
        reasons.append(str(exc))
    counts = Counter(statuses)
    lower = counts['INSIDE']
    upper = lower+counts['BOUNDARY']+counts['UNKNOWN']
    outcome = 'UNKNOWN'
    if proposed.get('frame_basis') != 'USER_CONFIRMED_FIXED_ICRS':
        reasons.append('PROPOSED_FIXED_ICRS_REQUIRED')
    elif proposed.get('completeness') != 'USER_CONFIRMED_COMPLETE':
        reasons.append('PROPOSED_POINTING_COMPLETENESS_REQUIRED')
    elif lower*2 > len(points):
        outcome = 'SATISFIED'
    elif upper*2 <= len(points):
        outcome = 'NOT_SATISFIED'
    elif counts['BOUNDARY']:
        reasons.append('BOUNDARY_MAY_CHANGE_STRICT_MAJORITY')
    return dict(schema_version='mosaic_s_region_position_1', candidate_id=candidate_id,
        coverage_source='ARCHIVE_S_REGION', coverage_policy='PROJECT_SUPERVISOR_CONFIRMED_2026_10_26',
        raw_s_region=s_region, s_region_sha256=sha256(s_region.encode()).hexdigest() if isinstance(s_region,str) else None,
        polygon_convention='SMALL_INTERIOR_MINOR_GREAT_CIRCLE_EDGES',
        boundary_arcsec=boundary_arcsec, pointing_count=len(points), inside_count=lower,
        outside_count=counts['OUTSIDE'], boundary_count=counts['BOUNDARY'], unknown_count=counts['UNKNOWN'],
        covered_fraction_lower=lower/len(points), covered_fraction_upper=upper/len(points),
        points=[dict(p,status=s) for p,s in zip(points,statuses)], outcome=outcome, reasons=reasons,
        threshold='STRICTLY_MORE_THAN_HALF', other_criteria='NOT_EVALUATED')
