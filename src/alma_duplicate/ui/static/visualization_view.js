/* Display coordinates only; never alter report evidence. Also testable in Node. */
(function (root) {
  "use strict";
  const fresh = () => ({x: 0, y: 0, k: 1});
  function zoom(view, factor, anchor, origin, horizontal = false) {
    const k = Math.min(64, Math.max(.25, view.k * factor)), ratio = k / view.k;
    return {k, x: anchor[0] - origin[0] - (anchor[0] - origin[0] - view.x) * ratio,
      y: horizontal ? 0 : anchor[1] - origin[1] - (anchor[1] - origin[1] - view.y) * ratio};
  }
  function pan(view, dx, dy, horizontal = false) {
    return {...view, x: view.x + dx, y: horizontal ? 0 : view.y + dy};
  }
  function hits(point, polygon, center, tolerance) {
    const [x, y] = point;
    if (Math.hypot(x-center[0], y-center[1]) <= tolerance) return true;
    let inside = false;
    for (let i=0, j=polygon.length-1; i<polygon.length; j=i++) {
      const a=polygon[j], b=polygon[i], dx=b[0]-a[0], dy=b[1]-a[1];
      const t=Math.max(0, Math.min(1, ((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy || 1)));
      if (Math.hypot(x-a[0]-t*dx, y-a[1]-t*dy) <= tolerance) return true;
      if ((a[1]>y)!==(b[1]>y) && x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]) inside=!inside;
    }
    return inside;
  }
  const projectKey = row => JSON.stringify(row.identity.Project ?? null);
  const memberKey = row => JSON.stringify([row.source, row.identity["Member OUS"] ?? null]);
  function filter(rows, project = "", member = "") {
    return rows.filter(row => (!project || projectKey(row) === project) && (!member || memberKey(row) === member));
  }
  function visible(rows, selected, isolated) {
    return isolated ? rows.filter(row => row.id === selected) : rows;
  }
  function selection(rows, previous) {
    return rows.some(row => row.id === previous) ? previous : rows[0]?.id ?? null;
  }
  // Fit already-projected display points with padding, without changing evidence.
  function fit(points, origin, halfWidth, halfHeight, horizontal = false) {
    if (!points.length) return null;
    const xs=points.map(p=>p[0]), ys=points.map(p=>p[1]);
    const minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
    const k=Math.min(64, Math.max(.25, Math.min(halfWidth*1.76/Math.max(1,maxX-minX),
      horizontal ? Infinity : halfHeight*1.76/Math.max(1,maxY-minY))));
    return {k, x: (origin[0]-(minX+maxX)/2)*k, y: horizontal ? 0 : (origin[1]-(minY+maxY)/2)*k};
  }
  const api={fresh, zoom, pan, hits, projectKey, memberKey, filter, visible, selection, fit};
  if (typeof module === "object" && module.exports) module.exports=api;
  else root.ReportViewport=api;
})(globalThis);
