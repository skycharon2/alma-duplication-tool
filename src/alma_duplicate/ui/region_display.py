"""Read-only spherical outlines from the exact region saved with a criterion."""
import math
from hashlib import sha256

from alma_duplicate.mosaic_region_position import Region, angle, unit


def coordinates(v):
    return [math.degrees(math.atan2(v[1], v[0])) % 360,
            math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))]


def saved_region_outline(detail):
    raw = detail.get('raw_s_region')
    if not isinstance(raw, str) or sha256(raw.encode()).hexdigest() != detail.get('s_region_sha256'):
        raise ValueError('Region evidence checksum mismatch')
    region = Region(raw)
    vertices = []
    if region.kind == 'CIRCLE':
        c = region.center
        a, d = map(math.radians, coordinates(c))
        north = (-math.sin(d)*math.cos(a), -math.sin(d)*math.sin(a), math.cos(d))
        east = (-math.sin(a), math.cos(a), 0)
        radius = math.radians(region.radius / 3600)
        for i in range(145):
            t = 2*math.pi*i/144
            vertices.append(coordinates(tuple(x*math.cos(radius) + math.sin(radius)*(n*math.cos(t)+e*math.sin(t))
                                               for x, n, e in zip(c, north, east))))
    else:
        for a, b in region.edges:
            length = angle(a, b)
            for i in range(16):
                t = i/16
                vertices.append(coordinates(unit(tuple(
                    math.sin((1-t)*length)*x + math.sin(t*length)*y for x, y in zip(a, b)))))
        vertices.append(vertices[0])
    return coordinates(region.center), vertices
