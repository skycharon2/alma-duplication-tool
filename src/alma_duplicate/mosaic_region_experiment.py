"""Diagnostic STC-S polygon versus circular beam union; never a policy evaluator."""
import math
from collections import Counter

from alma_duplicate.archive_mosaic_pointings import separation_arcsec


def compare_region(region, circles, *, grid_size=41, boundary_arcsec=0.001):
    """Compare sampled membership using local gnomonic great-circle polygon edges.

    Restricted to simple small ICRS polygons. No pointing inversion or completeness
    assertion is made. Boundary points are excluded from definite disagreements.
    """
    if not circles or type(grid_size) is not int or not 3 <= grid_size <= 101:
        raise ValueError('Nonempty circles and grid size 3..101 required')
    if not math.isfinite(boundary_arcsec) or boundary_arcsec <= 0:
        raise ValueError('Positive numerical boundary tolerance required')
    parts=region.split()
    if parts[:2] != ['Polygon','ICRS'] and [x.upper() for x in parts[:2]] != ['POLYGON','ICRS']:
        raise ValueError('Only ICRS Polygon supported by this experiment')
    values=list(map(float,parts[2:]))
    if len(values)<6 or len(values)%2 or not all(map(math.isfinite,values)):
        raise ValueError('Invalid polygon vertices')
    vertices=list(zip(values[::2],values[1::2]))
    ra0,dec0=circles[0]['ra_deg'],circles[0]['dec_deg']
    a0,d0=map(math.radians,(ra0,dec0))
    scale=180/math.pi*3600
    def project(ra,dec):
        if not 0<=ra<360 or not -90<=dec<=90:raise ValueError('Invalid coordinates')
        a,d=map(math.radians,(ra,dec));delta=a-a0
        cosine=math.sin(d0)*math.sin(d)+math.cos(d0)*math.cos(d)*math.cos(delta)
        if cosine<math.cos(math.radians(1)):raise ValueError('Experiment limited to one degree from origin')
        return (math.cos(d)*math.sin(delta)/cosine*scale,
                (math.cos(d0)*math.sin(d)-math.sin(d0)*math.cos(d)*math.cos(delta))/cosine*scale)
    def inverse(x,y):
        x,y=x/scale,y/scale;rho=math.hypot(x,y)
        if rho==0:return ra0,dec0
        c=math.atan(rho)
        d=math.asin(math.cos(c)*math.sin(d0)+y*math.sin(c)*math.cos(d0)/rho)
        a=a0+math.atan2(x*math.sin(c),rho*math.cos(d0)*math.cos(c)-y*math.sin(d0)*math.sin(c))
        return math.degrees(a)%360,math.degrees(d)
    polygon=[project(*p) for p in vertices]
    if polygon[0]==polygon[-1]:polygon.pop()
    if len(polygon)<3 or len(set(polygon))!=len(polygon):raise ValueError('Repeated or missing polygon vertex')
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon,polygon[1:]+polygon[:1]))
    if abs(area)<1e-12:raise ValueError('Degenerate polygon')
    def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    edges=list(zip(polygon,polygon[1:]+polygon[:1]))
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges):
            if j<=i+1 or (i==0 and j==len(edges)-1):continue
            if orient(a,b,c)*orient(a,b,d)<0 and orient(c,d,a)*orient(c,d,b)<0:
                raise ValueError('Self-intersecting polygon')
    centers=[]
    for c in circles:
        r=c['radius_arcsec']
        if not math.isfinite(r) or not 0<r<=1800:raise ValueError('Invalid radius')
        x,y=project(c['ra_deg'],c['dec_deg']);centers.append((x,y,r))
    xs=[p[0] for p in polygon]+[x+sign*r for x,y,r in centers for sign in [-1,1]]
    ys=[p[1] for p in polygon]+[y+sign*r for x,y,r in centers for sign in [-1,1]]
    xmin,xmax=min(xs)-1,max(xs)+1;ymin,ymax=min(ys)-1,max(ys)+1
    samples=[(xmin+(xmax-xmin)*i/(grid_size-1),ymin+(ymax-ymin)*j/(grid_size-1))
             for i in range(grid_size) for j in range(grid_size)] + polygon
    for x,y,r in centers:
        samples.append((x,y))
        samples.extend((x+r*f*math.cos(t*math.pi/24),y+r*f*math.sin(t*math.pi/24))
                       for f in [.99,1,1.01] for t in range(48))
    counts=Counter();witnesses=[]
    for x,y in samples:
        inside=False;edge_distance=float('inf')
        for (ax,ay),(bx,by) in edges:
            dx,dy=bx-ax,by-ay;length=dx*dx+dy*dy
            if length==0:raise ValueError('Degenerate polygon edge')
            t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/length))
            edge_distance=min(edge_distance,math.hypot(x-ax-t*dx,y-ay-t*dy))
            if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:inside=not inside
        ra,dec=inverse(x,y);point=dict(ra_deg=ra,dec_deg=dec)
        delta=min(separation_arcsec(point,c)-c['radius_arcsec'] for c in circles)
        if edge_distance<=boundary_arcsec or abs(delta)<=boundary_arcsec:key='BOUNDARY'
        elif inside and delta<0:key='BOTH_INSIDE'
        elif not inside and delta>0:key='BOTH_OUTSIDE'
        elif inside:key='REGION_ONLY'
        else:key='BEAM_ONLY'
        counts[key]+=1
        if key in ('REGION_ONLY','BEAM_ONLY') and len(witnesses)<100:
            witnesses.append(dict(**point,classification=key,beam_boundary_delta_arcsec=delta))
    return dict(schema_version='mosaic_region_experiment_1',sample_count=len(samples),
        counts=dict(counts),witnesses=witnesses,grid_size=grid_size,boundary_arcsec=boundary_arcsec,
        projection='LOCAL_GNOMONIC_MINOR_GREAT_CIRCLE_EDGES',
        conclusion='DIAGNOSTIC_SAMPLES_NOT_EQUIVALENCE_PROOF',policy_status='NOT_EVALUATED')
