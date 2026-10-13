/* Read-only charts over the current report. No source requests or verdicts. */
(() => {
  "use strict";
  const payload = document.getElementById("visual-data");
  if (!payload) return;
  const data = JSON.parse(payload.textContent);
  if (!data.rows.length) return;
  const rows = data.rows;
  let selected = rows[0].id;
  const zoom = {spatial: 1, spectral: 1};
  const ns = "http://www.w3.org/2000/svg";
  const color = row => row.source === "QUEUE" ? "#a45b15" : "#17689e";
  const fmt = x => typeof x === "number" ? Number(x.toPrecision(7)).toString() : String(x ?? "Not recorded");
  function node(tag, attrs = {}, text = null, parent = null, svg = false) {
    const element = svg ? document.createElementNS(ns, tag) : document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    if (text !== null) element.textContent = text;
    if (parent) parent.append(element);
    return element;
  }
  const draw = (parent, tag, attrs, text) => node(tag, attrs, text, parent, true);
  function line(parent, x1, y1, x2, y2, stroke = "#dce5ec", extra = {}) {
    return draw(parent, "line", {x1, y1, x2, y2, stroke, ...extra});
  }
  function marker(parent, x, y) {
    draw(parent, "path", {d: `M${x},${y-5}l5,5l-5,5l-5,-5Z`, fill: "#983b64", stroke: "white", "stroke-width": 1});
  }
  function selectable(parent, row, index, description) {
    const g = draw(parent, "g", {role: "button", tabindex: "0", "data-plot-select": row.id,
      "aria-pressed": String(row.id === selected), "aria-label": `Comparison ${index + data.start}: ${row.label}. ${description}`});
    draw(g, "title", {}, `${row.label}\n${row.source} · ${row.intent} · SPW ${row.spw}\n${description}`);
    g.addEventListener("click", () => select(row.id));
    g.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(row.id); }
    });
    return g;
  }
  function clip(svg, name, x, y, width, height) {
    const defs = draw(svg, "defs", {});
    const path = draw(defs, "clipPath", {id: name});
    draw(path, "rect", {x, y, width, height});
  }
  function spatialChart() {
    const svg = document.getElementById("spatial-chart");
    svg.replaceChildren();
    const points = rows.flatMap(row => row.spatial.available ? (row.spatial.outline || [row.spatial.offset]) : []);
    let extent = 10;
    points.forEach(point => { extent = Math.max(extent, Math.abs(point[0]), Math.abs(point[1])); });
    extent = extent * 1.15 / zoom.spatial;
    const sx = x => 240 + x * 185 / extent;
    const sy = y => 220 - y * 185 / extent;
    for (let i = -2; i <= 2; i++) {
      const value = extent * i / 2;
      line(svg, sx(value), 35, sx(value), 405);
      line(svg, 55, sy(value), 425, sy(value));
      draw(svg, "text", {x: sx(value), y: 425, "text-anchor": "middle"}, fmt(-value));
      draw(svg, "text", {x: 46, y: sy(value)+3, "text-anchor": "end"}, fmt(value));
    }
    draw(svg, "text", {x: 240, y: 450, "text-anchor": "middle"}, "East offset (arcsec) ←");
    draw(svg, "text", {transform: "translate(13 220) rotate(-90)", "text-anchor": "middle"}, "North offset (arcsec)");
    clip(svg, "position-clip", 55, 35, 370, 370);
    const layer = draw(svg, "g", {"clip-path": "url(#position-clip)"});
    // Paint the selected geometry last so coincident centers remain visible.
    rows.map((row, i) => [row, i]).sort(([a], [b]) => Number(a.id === selected) - Number(b.id === selected)).forEach(([row, i]) => {
      if (!row.spatial.available) return;
      const spatial = row.spatial, active = row.id === selected;
      const desc = `Center RA ${fmt(spatial.center[0])}, Dec ${fmt(spatial.center[1])} deg; half-power radius ${fmt(spatial.radius_arcsec)} arcsec`;
      const g = selectable(layer, row, i, desc);
      if (spatial.outline) draw(g, "path", {
        d: spatial.outline.map((p, j) => `${j ? "L" : "M"}${sx(p[0])},${sy(p[1])}`).join(" ") + "Z",
        stroke: color(row), "stroke-width": active ? 2.3 : 1,
        fill: color(row), "fill-opacity": active ? .1 : .018, "stroke-opacity": active ? 1 : .35,
        "stroke-dasharray": row.source === "QUEUE" ? "5 3" : "none"
      });
      draw(g, "circle", {cx: sx(spatial.offset[0]), cy: sy(spatial.offset[1]), r: active ? 5 : 3,
        fill: color(row), stroke: "white", "stroke-width": 1});
      if (active) draw(g, "text", {x: sx(spatial.offset[0])+8, y: sy(spatial.offset[1])-8}, `#${i+data.start}`);
    });
    if (data.origin) { marker(layer, sx(0), sy(0)); draw(svg, "text", {x: 60, y: 22}, "◆ Your target at (0, 0)"); }
    if (!points.length) draw(svg, "text", {x: 240, y: 190, "text-anchor": "middle"}, "Candidate position evidence unavailable");
  }
  function spectralChart() {
    const svg = document.getElementById("spectral-chart");
    const height = Math.max(330, 90 + rows.length * 34);
    svg.setAttribute("viewBox", `0 0 600 ${height}`);
    svg.replaceChildren();
    const values = rows.flatMap(row => {
      const f = row.spectral;
      return !f.available ? [] : f.kind === "interval" ? [f.proposed, f.low, f.high] : [f.proposed, f.candidate];
    });
    if (!values.length) {
      draw(svg, "text", {x: 300, y: 100, "text-anchor": "middle"}, "Recorded comparison frequencies unavailable");
      return;
    }
    const low = Math.min(...values), high = Math.max(...values);
    const center = (low+high)/2, span = Math.max(high-low, Math.abs(center)*.0001) * 1.16 / zoom.spectral;
    const x = value => 135 + (value-(center-span/2)) * 430/span;
    const bottom = height - 40;
    for (let i=0; i<=4; i++) {
      const value = center - span/2 + span*i/4, px = x(value);
      line(svg, px, 30, px, bottom);
      draw(svg, "text", {x: px, y: 20, "text-anchor": "middle"}, fmt(value));
      draw(svg, "text", {x: px, y: bottom+16, "text-anchor": "middle"}, fmt(value));
    }
    draw(svg, "text", {x: 350, y: height-3, "text-anchor": "middle"}, "Frequency (GHz)");
    clip(svg, "frequency-clip", 135, 30, 430, bottom-30);
    rows.forEach((row, i) => {
      const y = 48 + i*34, f = row.spectral, active = row.id === selected;
      const description = !f.available ? f.reason : f.kind === "interval" ?
        `Requested ${fmt(f.proposed)} GHz; candidate interval ${fmt(f.low)} to ${fmt(f.high)} GHz` :
        `Requested ${fmt(f.proposed)} GHz; candidate representative frequency ${fmt(f.candidate)} GHz`;
      const g = selectable(svg, row, i, description);
      draw(g, "rect", {x: 5, y: y-15, width: 585, height: 30, fill: active ? "#e9f4fa" : "transparent"});
      draw(g, "text", {x: 12, y: y+3}, `#${i+data.start} ${row.intent === "LINE" ? "LINE" : "CONT"} · ${row.source === "QUEUE" ? "Queue" : "Archive"}`);
      if (!f.available) { draw(g, "text", {x: 145, y: y+3}, "Frequency evidence unavailable"); return; }
      const layer = draw(g, "g", {"clip-path": "url(#frequency-clip)"});
      if (f.kind === "interval") {
        draw(layer, "rect", {x: x(f.low), y: y-4, width: Math.max(.5, x(f.high)-x(f.low)), height: 8, rx: 1,
          fill: color(row), opacity: active ? 1 : .55});
      } else draw(layer, "circle", {cx: x(f.candidate), cy: y, r: 5, fill: color(row)});
      marker(layer, x(f.proposed), y);
    });
  }
  function details() {
    const row = rows.find(r => r.id === selected), body = document.getElementById("visual-detail-body");
    body.replaceChildren();
    node("h3", {}, row.label, body);
    const dl = node("dl", {}, null, body);
    Object.entries(row.identity).forEach(([key, value]) => { node("dt", {}, key, dl); node("dd", {}, value, dl); });
    if (row.window) { node("dt", {}, "Requested window", dl); node("dd", {}, row.window, dl); }
    const s = row.spatial;
    if (s.available) {
      node("p", {}, `Separation: ${fmt(s.separation_arcsec)} arcsec · Half-power radius: ${fmt(s.radius_arcsec)} arcsec`, body);
      node("p", {}, `Beam evidence: D = ${fmt(s.diameter_m)} m at ${fmt(s.frequency_ghz)} GHz`, body);
    }
    if (s.reason) node("p", {class: "notice"}, s.reason, body);
    const f = row.spectral;
    node("p", {}, !f.available ? f.reason : f.kind === "interval" ?
      `Requested: ${fmt(f.proposed)} GHz · Candidate: ${fmt(f.low)}–${fmt(f.high)} GHz` :
      `Representative frequencies: requested ${fmt(f.proposed)} GHz · candidate ${fmt(f.candidate)} GHz`, body);
    const quantity = q => q && q.value !== null ? `${fmt(q.value)} ${q.unit || ""}` : "Not recorded";
    row.criteria.forEach(record => {
      const d = node("details", {class: "visual-condition"}, null, body);
      node("summary", {}, `${record.label} · ${record.result}`, d);
      if (record.proposed || record.candidate) node("p", {}, `Your requirement: ${quantity(record.proposed)} · Candidate: ${quantity(record.candidate)}`, d);
      node("p", {}, record.reason, d);
    });
  }
  function select(id) {
    const focused = document.activeElement;
    const plot = focused?.closest("svg")?.id;
    selected = id;
    document.querySelectorAll("[data-select]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.select === id)));
    spatialChart(); spectralChart(); details();
    const index = rows.findIndex(r => r.id === id);
    document.getElementById("visual-selection-status").textContent = `Selected comparison ${index+data.start}: ${rows[index].label}`;
    if (plot) document.getElementById(plot).querySelector(`[data-plot-select="${id}"]`)?.focus({preventScroll: true});
  }
  document.querySelectorAll("[data-select]").forEach(button => button.addEventListener("click", () => select(button.dataset.select)));
  document.querySelectorAll("[data-zoom]").forEach(button => button.addEventListener("click", () => {
    const [chart, action] = button.dataset.zoom.split(":");
    zoom[chart] = action === "reset" ? 1 : Math.min(64, Math.max(.25, zoom[chart] * (action === "in" ? 1.6 : 1/1.6)));
    if (chart === "spatial") spatialChart(); else spectralChart();
  }));
  select(selected);
})();
