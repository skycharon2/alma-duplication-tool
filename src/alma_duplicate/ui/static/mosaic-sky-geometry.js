/* Read-only ICRS projection for Mosaic geometry-only fallback and fit. */
(function (root) {
  'use strict';
  const DEG = Math.PI / 180;
  const ARCSEC = 180 * 3600 / Math.PI;
  function offset(origin, point) {
    if (!Array.isArray(origin) || !Array.isArray(point) ||
        [...origin, ...point].some(v => !Number.isFinite(v))) return null;
    const a = origin[0] * DEG, d = origin[1] * DEG;
    const ra = point[0] * DEG, dec = point[1] * DEG;
    const delta = Math.atan2(Math.sin(ra - a), Math.cos(ra - a));
    const z = Math.sin(d) * Math.sin(dec) + Math.cos(d) * Math.cos(dec) * Math.cos(delta);
    if (z <= 0) return null;
    return [-(Math.cos(dec) * Math.sin(delta) / z) * ARCSEC,
            -(Math.cos(d) * Math.sin(dec) - Math.sin(d) * Math.cos(dec) * Math.cos(delta)) / z * ARCSEC];
  }
  function coordinates(scene) {
    if (!scene?.available) return [];
    return [
      ...(scene.proposed || []).map(p => p.center),
      ...(scene.candidate?.kind === 'region' ? scene.candidate.outline : []),
      ...(scene.candidate?.kind === 'beams' ? scene.candidate.beams.map(p => p.center) : [])
    ];
  }
  function extent(scene, visible = []) {
    const origin = scene?.proposed?.[0]?.center;
    if (!origin) return null;
    let max = 0;
    for (const entry of [scene, ...visible]) {
      for (const point of coordinates(entry)) {
        const p = offset(origin, point);
        if (!p) return null;
        max = Math.max(max, Math.hypot(...p));
      }
      const includeBeam = (center, radius) => {
        const p = offset(origin, center);
        if (!p || !Number.isFinite(radius) || radius <= 0) return false;
        // Gnomonic radial distance of the furthest spherical beam edge.
        const edge = Math.atan(Math.hypot(...p) / ARCSEC) + radius / ARCSEC;
        if (edge >= Math.PI / 2) return false;
        max = Math.max(max, Math.tan(edge) * ARCSEC);
        return true;
      };
      for (const beam of entry?.proposed_beams || [])
        for (const point of entry.proposed || [])
          if (!includeBeam(point.center, beam.radius_arcsec)) return null;
      if (entry?.candidate?.kind === 'beams')
        for (const beam of entry.candidate.beams)
          if (!includeBeam(beam.center, beam.radius_arcsec ?? entry.candidate.radius_arcsec)) return null;
    }
    return {origin, arcsec:Math.max(10, max), fov:Math.min(120, Math.max(2 / 3600, 2.8 * Math.atan(max / ARCSEC) / DEG))};
  }
  function fallback(container, selected, others = [], options = {}) {
    const view = extent(selected, options.others ? others : []);
    if (!view) {container.textContent='Recorded sky geometry unavailable.'; return false;}
    const NS='http://www.w3.org/2000/svg', width=640, height=400;
    const svg=document.createElementNS(NS,'svg');
    for (const [k,v] of Object.entries({viewBox:`0 0 ${width} ${height}`,width:'100%',height:'100%',
      role:'img','aria-label':'Geometry only; optical imagery unavailable'})) svg.setAttribute(k,v);
    function add(type,attrs,parent=svg) {
      const node=document.createElementNS(NS,type);
      for (const [k,v] of Object.entries(attrs)) node.setAttribute(k,String(v));
      parent.append(node);return node;
    }
    add('rect',{x:0,y:0,width,height,fill:'#071016'});
    const scale=.40*Math.min(width,height)/view.arcsec, cx=width/2, cy=height/2;
    function xy(coord) {const p=offset(view.origin,coord);return p && [cx+p[0]*scale,cy+p[1]*scale];}
    function plot(entry,highlight) {
      if (!entry?.candidate || options.candidates === false) return;
      const color=entry.source==='Queue'?'#d88a00':'#176fba';
      const c=entry.candidate;
      if (c.kind==='region') {
        const points=c.outline.map(xy);
        if (points.every(Boolean)) {
          const coords=points.map(p=>p.join(',')).join(' ');
          if(highlight) add('polyline',{points:coords,fill:'none',stroke:'#ffffff','stroke-width':5});
          add('polyline',{points:coords,fill:'none',stroke:color,
            'stroke-width':highlight?2.9:1.6});
        }
      } else if (c.kind==='beams') {
        for(const beam of c.beams) {
          const p=xy(beam.center);if (!p) continue;
          if(highlight) add('circle',{cx:p[0],cy:p[1],r:(beam.radius_arcsec ?? c.radius_arcsec)*scale,
            fill:'none',stroke:'#ffffff','stroke-width':5.2});
          add('circle',{cx:p[0],cy:p[1],r:(beam.radius_arcsec ?? c.radius_arcsec)*scale,fill:'none',
            stroke:color,'stroke-width':highlight?2.9:1.6,
            'stroke-dasharray':entry.source==='Queue'?'6 4':'none'});
          add('circle',{cx:p[0],cy:p[1],r:2.5,fill:color});
        }
      }
    }
    if(options.others) for(const entry of others) plot(entry,false);
    plot(selected,true);
    if (options.proposed !== false) {
      for (const beam of selected.proposed_beams || []) for(const point of selected.proposed) {
        const p=xy(point.center);if(p) add('circle',{cx:p[0],cy:p[1],r:beam.radius_arcsec*scale,
          fill:'none',stroke:'#a12b9b','stroke-width':1.7,'stroke-dasharray':'6 5'});
      }
      for (const point of selected.proposed || []) {
        const p=xy(point.center);if(!p)continue;
        const cross=`M ${p[0]-6} ${p[1]} H ${p[0]+6} M ${p[0]} ${p[1]-6} V ${p[1]+6}`;
        add('path',{d:cross,fill:'none',stroke:'#ffffff','stroke-width':5});
        add('path',{d:cross,fill:'none',stroke:'#00b9af','stroke-width':2.7});
      }
    }
    add('text',{x:14,y:25,fill:'#eef7ff','font-size':14}).textContent='Saved geometry only · no optical imagery';
    add('text',{x:14,y:height-15,fill:'#acc5d2','font-size':12}).textContent='ICRS offsets · not an ALMA detection or duplication verdict';
    container.replaceChildren(svg);
    return true;
  }
  const api={offset,coordinates,extent,fallback};
  root.MosaicSkyGeometry=api;
  if (typeof module==='object' && module.exports) module.exports=api;
})(typeof window==='undefined'?globalThis:window);
