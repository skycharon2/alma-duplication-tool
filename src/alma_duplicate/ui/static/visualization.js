/* Read-only charts over the current report. No source requests or verdicts. */
(() => {
  "use strict";
  const payload = document.getElementById("visual-data");
  if (!payload) return;
  const data = JSON.parse(payload.textContent);
  if (!data.rows.length) return;
  const rows = data.rows;
  let selected = rows[0].id, previewed = null, previewScroll = null;
  const highlighted = () => previewed ?? selected;
  const viewport = window.ReportViewport;
  const views = {spatial: viewport.fresh(), spectral: viewport.fresh()};
  let project = "", member = "", isolated = false;
  const filteredRows = () => viewport.filter(rows, project, member);
  const visibleRows = () => viewport.visible(filteredRows(), selected, isolated);
  const number = row => rows.indexOf(row) + data.start;
  const spatialPoints = list => list.flatMap(row => row.spatial.available ? (row.spatial.outline || [row.spatial.offset]) : []);
  const frequencyValues = list => list.flatMap(row => {
    const f = row.spectral;
    return !f.available ? [] : f.kind === "interval" ? [f.proposed, f.low, f.high] : [f.proposed, f.candidate];
  });
  const extent = Math.max(10, ...spatialPoints(rows).flat().map(Math.abs)) * 1.15;
  const frequencies = frequencyValues(rows);
  const baseCenter = frequencies.length ? (Math.min(...frequencies)+Math.max(...frequencies))/2 : 0;
  const baseSpan = frequencies.length ? Math.max(Math.max(...frequencies)-Math.min(...frequencies), Math.abs(baseCenter)*.0001, 1e-12)*1.16 : 1;
  let spatialShapes = [];
  let gesture = null, suppressClick = false;
  let chooser = null, chooserReturn = null;
  const origins = {spatial: [240, 220], spectral: [350, 0]};
  const render = chart => chart === "spatial" ? spatialChart() : spectralChart();
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
    g.addEventListener("click", event => {
      if (suppressClick || parent.closest("svg").id === "spatial-chart") return;
      event.stopPropagation(); select(row.id);
    });
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
    const points = spatialPoints(visibleRows());
    const view = views.spatial, span = extent / view.k;
    const cx = -view.x * extent / (185 * view.k), cy = view.y * extent / (185 * view.k);
    const sx = x => 240 + x * 185 / extent * view.k + view.x;
    const sy = y => 220 - y * 185 / extent * view.k + view.y;
    spatialShapes = [];
    for (let i = -2; i <= 2; i++) {
      const vx = cx + span*i/2, vy = cy + span*i/2;
      line(svg, sx(vx), 35, sx(vx), 405);
      line(svg, 55, sy(vy), 425, sy(vy));
      draw(svg, "text", {x: sx(vx), y: 425, "text-anchor": "middle"}, Number((-vx).toPrecision(3)).toString());
      draw(svg, "text", {x: 46, y: sy(vy)+3, "text-anchor": "end"}, Number(vy.toPrecision(3)).toString());
    }
    draw(svg, "text", {x: 240, y: 450, "text-anchor": "middle"}, "East offset (arcsec) ←");
    draw(svg, "text", {transform: "translate(13 220) rotate(-90)", "text-anchor": "middle"}, "North offset (arcsec)");
    clip(svg, "position-clip", 55, 35, 370, 370);
    const layer = draw(svg, "g", {"clip-path": "url(#position-clip)"});
    // Paint the selected geometry last so coincident centers remain visible.
    visibleRows().map(row => [row, rows.indexOf(row)]).sort(([a], [b]) => Number(a.id === highlighted()) - Number(b.id === highlighted())).forEach(([row, i]) => {
      if (!row.spatial.available) return;
      const spatial = row.spatial, active = row.id === highlighted();
      const desc = `Center RA ${fmt(spatial.center[0])}, Dec ${fmt(spatial.center[1])} deg; half-power radius ${fmt(spatial.radius_arcsec)} arcsec`;
      const g = selectable(layer, row, i, desc);
      const polygon = (spatial.outline || []).map(p => [sx(p[0]), sy(p[1])]);
      spatialShapes.push({id: row.id, polygon, center: [sx(spatial.offset[0]), sy(spatial.offset[1])]});
      if (active && polygon.length) draw(g, "path", {
        d: polygon.map((p,j) => `${j ? "L" : "M"}${p[0]},${p[1]}`).join(" ")+"Z",
        fill: "none", stroke: "white", "stroke-width": 6, "pointer-events": "none"
      });
      if (spatial.outline) draw(g, "path", {
        d: spatial.outline.map((p, j) => `${j ? "L" : "M"}${sx(p[0])},${sy(p[1])}`).join(" ") + "Z",
        stroke: color(row), "stroke-width": active ? 3 : 1.2,
        fill: color(row), "fill-opacity": active ? .05 : 0, "stroke-opacity": active ? 1 : .45,
        "stroke-dasharray": row.source === "QUEUE" ? "5 3" : "none"
      });
      draw(g, "circle", {cx: sx(spatial.offset[0]), cy: sy(spatial.offset[1]), r: active ? 5 : 3,
        fill: color(row), stroke: "white", "stroke-width": 1});
      if (active) draw(g, "text", {x: sx(spatial.offset[0])+8, y: sy(spatial.offset[1])-8}, `#${i+data.start}${previewed === row.id ? " preview" : ""}`);
    });
    if (data.origin) { marker(layer, sx(0), sy(0)); draw(svg, "text", {x: 60, y: 22}, "◆ Your target at (0, 0)"); }
    if (!points.length) draw(svg, "text", {x: 240, y: 190, "text-anchor": "middle"}, "Candidate position evidence unavailable");
  }
  function spectralChart() {
    const svg = document.getElementById("spectral-chart");
    const shown = visibleRows();
    const height = Math.max(330, 90 + shown.length * 34);
    svg.setAttribute("viewBox", `0 0 600 ${height}`);
    svg.replaceChildren();
    const values = frequencyValues(shown);
    if (!values.length) {
      draw(svg, "text", {x: 300, y: 100, "text-anchor": "middle"}, "Recorded comparison frequencies unavailable");
      return;
    }
    const span = baseSpan / views.spectral.k;
    const center = baseCenter - views.spectral.x * span / 430;
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
    shown.forEach((row, i) => {
      const y = 48 + i*34, f = row.spectral, active = row.id === highlighted();
      const description = !f.available ? f.reason : f.kind === "interval" ?
        `Requested ${fmt(f.proposed)} GHz; candidate interval ${fmt(f.low)} to ${fmt(f.high)} GHz` :
        `Requested ${fmt(f.proposed)} GHz; candidate representative frequency ${fmt(f.candidate)} GHz`;
      const g = selectable(svg, row, rows.indexOf(row), description);
      draw(g, "rect", {x: 5, y: y-15, width: 585, height: 30, fill: active ? "#e9f4fa" : "transparent"});
      draw(g, "text", {x: 12, y: y+3}, `#${number(row)} ${row.intent === "LINE" ? "LINE" : "CONT"} · ${row.source === "QUEUE" ? "Queue" : "Archive"}`);
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
    if (!row) { node("p", {}, "No comparison selected. Clear the filters to show the loaded comparisons.", body); return; }
    node("h3", {}, `#${rows.indexOf(row)+data.start} · ${row.label}`, body);
    node("p", {class: "selected-evidence"}, `${row.source} · ${row.intent} · Selected SPW ${row.spw}`, body);
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
  function revealWithin(container, element) {
    if (!element) return;
    const outer = container.getBoundingClientRect(), inner = element.getBoundingClientRect();
    if (inner.top < outer.top) container.scrollTop += inner.top - outer.top;
    else if (inner.bottom > outer.bottom) container.scrollTop += inner.bottom - outer.bottom;
  }
  function select(id) {
    const focused = document.activeElement;
    const plot = focused?.closest("svg")?.id;
    closeChooser(false);
    selected = viewport.selection(filteredRows(), id);
    updateControls();
    document.querySelectorAll("[data-select]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.select === selected)));
    spatialChart(); spectralChart(); details();
    revealWithin(document.querySelector(".visual-list"), document.querySelector("[data-select][aria-pressed='true']"));
    revealWithin(document.querySelector(".frequency-scroll"), document.querySelector("#spectral-chart [aria-pressed='true']"));
    const index = rows.findIndex(r => r.id === selected);
    document.getElementById("visual-selection-status").textContent = index < 0 ? "No visible comparisons. Clear filters." : `Selected comparison ${index+data.start}: ${rows[index].label}. Showing ${visibleRows().length} of ${rows.length} loaded comparisons.`;
    if (plot) document.getElementById(plot).querySelector(`[data-plot-select="${selected}"]`)?.focus({preventScroll: true});
  }
  document.querySelectorAll("[data-select]").forEach(button => button.addEventListener("click", () => select(button.dataset.select)));
  function fitChart(chart, list) {
    if (chart === "spatial") {
      const points = spatialPoints(list);
      return points.length ? viewport.fit([[240,220], ...points.map(p => [240+p[0]*185/extent,220-p[1]*185/extent])], origins.spatial,185,185) : null;
    }
    return viewport.fit(frequencyValues(list).map(v => [350+(v-baseCenter)*430/baseSpan,0]), origins.spectral,215,1,true);
  }
  function fitCharts(list) {
    for (const chart of ["spatial", "spectral"]) views[chart] = fitChart(chart, list) || viewport.fresh();
  }
  function options(select, list, key, label, all) {
    select.replaceChildren(); node("option", {value: ""}, all, select);
    const seen = new Set();
    list.forEach(row => {
      const value = key(row);
      if (!seen.has(value)) { node("option", {value}, label(row), select); seen.add(value); }
    });
  }
  function members() {
    options(document.getElementById("visual-member"), viewport.filter(rows,project), viewport.memberKey,
      row => `${row.source === "QUEUE" ? "Queue" : "Archive"}: ${row.identity["Member OUS"] || "No Member OUS recorded"}`, "All Members / contexts");
    document.getElementById("visual-member").value = member;
  }
  function updateControls() {
    const shown = visibleRows(), ids = new Set(shown.map(row=>row.id));
    document.querySelectorAll(".visual-candidate").forEach(element => { element.hidden = !ids.has(element.dataset.row); });
    document.getElementById("visual-visible-count").textContent = `Showing ${shown.length} of ${rows.length} loaded comparisons`;
    document.getElementById("visual-list-count").textContent = `${shown.length} shown`;
    document.getElementById("visual-spatial-count").textContent = `${shown.filter(row=>row.spatial.available).length} / ${shown.length}`;
    document.getElementById("visual-spectral-count").textContent = `${shown.filter(row=>row.spectral.available).length} / ${shown.length}`;
    document.getElementById("visual-empty").hidden = shown.length > 0;
    document.getElementById("visual-isolate").setAttribute("aria-pressed", String(isolated));
    const row = rows.find(row=>row.id===selected), summary=document.getElementById("visual-current");
    summary.replaceChildren();
    document.getElementById("visual-focus").disabled = !row || (!row.spatial.available && !row.spectral.available);
    if (!row) { node("p", {}, "No comparison selected.", summary); return; }
    const identity=node("div", {class:"visual-current-identity"}, null, summary);
    node("strong", {}, `#${number(row)} ${row.label}`, identity);
    node("span", {}, `${row.source === "QUEUE" ? "Queue" : "Archive"} · ${row.intent} · SPW ${row.spw}${row.window ? ` · requested ${row.window}` : ""}${row.beam_variant != null ? ` · beam path ${row.beam_variant+1}` : ""}`, identity);
    node("small", {}, row.identity["Member OUS"] ? `Member ${row.identity["Member OUS"]}` : "Member OUS not recorded", identity);
    if (row.identity.ASDM) node("small", {}, `ASDM ${row.identity.ASDM}`, identity);
    const s=row.spatial, f=row.spectral, relation=viewport.relationships(row);
    const position=node("div", {class:"visual-current-values"}, null, summary);
    node("strong", {}, "Position", position);
    node("span", {}, s.available ? `Separation ${fmt(s.separation_arcsec)} arcsec` : "Evidence unavailable", position);
    if (s.available) node("small", {}, `Half-power radius ${fmt(s.radius_arcsec)} arcsec`, position);
    if (relation.radiusRatio !== null) node("small", {}, `Separation / half-power radius: ${fmt(relation.radiusRatio)} (1 = boundary; not angular resolution)`, position);
    if (!s.available && s.reason) node("small", {}, s.reason, position);
    const frequency=node("div", {class:"visual-current-values"}, null, summary);
    node("strong", {}, "Frequency", frequency);
    node("span", {}, f.available ? `Requested ${fmt(f.proposed)} GHz` : "Evidence unavailable", frequency);
    if (f.available) node("small", {}, f.kind === "interval" ? `Candidate ${fmt(f.low)}–${fmt(f.high)} GHz` : `Candidate ${fmt(f.candidate)} GHz (representative)`, frequency);
    if (relation.lowerMarginGHz !== null) {
      node("small", {}, `From lower edge: ${fmt(relation.lowerMarginGHz)} GHz; to upper edge: ${fmt(relation.upperMarginGHz)} GHz. Negative = outside interval.`, frequency);
    } else if (f.available) node("small", {}, "Representative markers do not describe frequency coverage.", frequency);
    if (!f.available && f.reason) node("small", {}, f.reason, frequency);
  }
  function preview(id) {
    if (id === previewed) return;
    const scroller=document.querySelector(".frequency-scroll");
    if (previewScroll === null) previewScroll=scroller.scrollTop;
    previewed=id;
    spatialChart(); spectralChart();
    const row=rows.find(row=>row.id===id);
    document.getElementById("visual-preview-status").textContent=row ? `Preview #${number(row)}: ${row.label}. Click to select; current selection is unchanged.` : "";
    revealWithin(scroller, document.querySelector(`#spectral-chart [data-plot-select="${id}"]`));
  }
  function clearPreview() {
    if (previewed === null) return;
    previewed=null;
    spatialChart(); spectralChart();
    if (previewScroll !== null) document.querySelector(".frequency-scroll").scrollTop=previewScroll;
    previewScroll=null;
    document.getElementById("visual-preview-status").textContent="";
  }
  function applyFilters() {
    selected=viewport.selection(filteredRows(),selected);
    fitCharts(visibleRows()); select(selected);
  }
  options(document.getElementById("visual-project"), rows, viewport.projectKey,
    row => row.identity.Project || "Project not recorded", "All projects");
  members();
  document.getElementById("visual-project").addEventListener("change", event => {
    project=event.target.value; member=""; members(); applyFilters();
  });
  document.getElementById("visual-member").addEventListener("change", event => { member=event.target.value; applyFilters(); });
  document.getElementById("visual-isolate").addEventListener("click", () => { isolated=!isolated; select(selected); });
  document.getElementById("visual-clear").addEventListener("click", () => {
    project=""; member=""; isolated=false;
    document.getElementById("visual-project").value=""; members(); applyFilters();
  });
  document.getElementById("visual-focus").addEventListener("click", () => {
    closeChooser(false); fitCharts(rows.filter(row=>row.id===selected));
    select(selected);
    const row=rows.find(row=>row.id===selected);
    document.getElementById("visual-selection-status").textContent += row && (!row.spatial.available || !row.spectral.available) ? " Focused available evidence only; one panel lacks evidence." : " Focused selected comparison and your observation.";
  });
  document.getElementById("visual-controls").hidden=false;
  document.getElementById("visual-current").hidden=false;
  function point(svg, event) {
    return new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse());
  }
  function closeChooser(restore = true) {
    if (!chooser) return;
    clearPreview();
    chooser.remove(); chooser = null;
    if (restore) chooserReturn?.focus({preventScroll: true});
  }
  function chooseOverlap(ids, event, svg) {
    closeChooser(false);
    chooserReturn = svg;
    chooser = node("div", {class: "overlap-chooser", role: "dialog", "aria-label": "Overlapping comparisons"}, null, document.body);
    const head = node("div", {class: "overlap-heading"}, null, chooser);
    node("strong", {}, `${ids.length} comparisons at this position`, head);
    const close = node("button", {type: "button", "aria-label": "Close overlapping comparisons"}, "×", head);
    close.addEventListener("click", () => closeChooser());
    node("p", {}, "Hover or focus to preview both plots. Click to select.", chooser);
    const list = node("div", {class: "overlap-list"}, null, chooser);
    rows.forEach((row, i) => {
      if (!ids.includes(row.id)) return;
      const b = node("button", {type: "button", "aria-pressed": String(selected === row.id)}, null, list);
      node("strong", {}, `#${i+data.start} · ${row.label}`, b);
      node("small", {}, `${row.source} · ${row.intent} · SPW ${row.spw}${row.window ? ` · requested ${row.window}` : ""}${row.beam_variant != null ? ` · beam path ${row.beam_variant+1}` : ""}`, b);
      const identity = [row.identity["Member OUS"], row.identity.ASDM].filter(Boolean).join(" · ");
      if (identity) node("small", {class: "overlap-identity"}, identity, b);
      b.addEventListener("pointerenter", event => { if (event.pointerType !== "touch") preview(row.id); });
      b.addEventListener("pointerleave", () => { if (document.activeElement !== b) clearPreview(); });
      b.addEventListener("focus", () => preview(row.id));
      b.addEventListener("blur", () => clearPreview());
      b.addEventListener("click", () => { select(row.id); svg.focus({preventScroll: true}); });
    });
    const bounds = chooser.getBoundingClientRect();
    chooser.style.left = `${Math.max(8, Math.min(event.clientX+12, innerWidth-bounds.width-8))}px`;
    chooser.style.top = `${Math.max(8, Math.min(event.clientY+12, innerHeight-bounds.height-8))}px`;
    close.focus({preventScroll: true});
  }
  document.addEventListener("pointerdown", event => {
    if (chooser && !chooser.contains(event.target)) closeChooser(false);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && chooser) { event.preventDefault(); closeChooser(); }
  });
  window.addEventListener("resize", () => closeChooser(false));
  window.addEventListener("scroll", event => {
    if (event.target === document.querySelector(".frequency-scroll")) return;
    if (chooser && !chooser.contains(event.target)) closeChooser(false);
  }, true);
  for (const chart of ["spatial", "spectral"]) {
    const svg = document.getElementById(chart === "spatial" ? "spatial-chart" : "spectral-chart");
    svg.setAttribute("tabindex", "0");
    const inPlot = p => chart === "spatial" ? p.x>=55 && p.x<=425 && p.y>=35 && p.y<=405 : p.x>=135 && p.x<=565 && p.y>=30 && p.y<=svg.viewBox.baseVal.height-40;
    svg.addEventListener("pointerdown", event => {
      if (event.button !== 0 || event.isPrimary === false || event.pointerType === "touch") return;
      const p = point(svg, event);
      if (!inPlot(p)) return;
      suppressClick = false;
      gesture = {chart, id: event.pointerId, x: event.clientX, y: event.clientY, p, view: {...views[chart]}, moved: false};
    });
    svg.addEventListener("pointermove", event => {
      if (!gesture || gesture.chart !== chart || gesture.id !== event.pointerId) return;
      if (!gesture.moved && Math.hypot(event.clientX-gesture.x, event.clientY-gesture.y)<5) return;
      gesture.moved = true; suppressClick = true;
      svg.setPointerCapture(event.pointerId);
      svg.classList.add("is-panning");
      const p = point(svg, event);
      views[chart] = viewport.pan(gesture.view, p.x-gesture.p.x, p.y-gesture.p.y, chart === "spectral");
      render(chart);
    });
    function end(event, cancel = false) {
      if (!gesture || gesture.id !== event.pointerId) return;
      if (cancel) views[chart] = gesture.view;
      gesture = null; svg.classList.remove("is-panning");
      if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
      if (cancel) render(chart);
      setTimeout(() => { suppressClick = false; }, 0);
    }
    svg.addEventListener("pointerup", event => end(event));
    svg.addEventListener("pointercancel", event => end(event, true));
    svg.addEventListener("click", event => {
      if (suppressClick || chart !== "spatial") return;
      const p = point(svg, event);
      if (!inPlot(p)) return;
      const tolerance = 7 / Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b);
      const ids = spatialShapes.filter(s => viewport.hits([p.x,p.y], s.polygon, s.center, tolerance)).map(s => s.id);
      if (ids.length > 1) chooseOverlap(ids, event, svg);
      else if (ids.length) select(ids[0]);
    });
    svg.addEventListener("wheel", event => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const p = point(svg, event);
      if (!inPlot(p)) return;
      event.preventDefault(); closeChooser(false);
      views[chart] = viewport.zoom(views[chart], event.deltaY < 0 ? 1.15 : 1/1.15, [p.x,p.y], origins[chart], chart === "spectral");
      render(chart);
    }, {passive: false});
    svg.addEventListener("keydown", event => {
      if (event.target !== svg) return;
      const delta = {ArrowLeft: [24,0], ArrowRight: [-24,0], ArrowUp: [0,24], ArrowDown: [0,-24]}[event.key];
      if (delta && (chart === "spatial" || !delta[1])) {
        event.preventDefault(); views[chart] = viewport.pan(views[chart], ...delta, chart === "spectral"); render(chart);
      }
      if (["+", "=", "-", "Home"].includes(event.key)) {
        event.preventDefault();
        views[chart] = event.key === "Home" ? (fitChart(chart, visibleRows()) || viewport.fresh()) : viewport.zoom(views[chart], event.key === "-" ? 1/1.6 : 1.6, origins[chart], origins[chart], chart === "spectral");
        render(chart);
      }
    });
  }
  document.querySelectorAll("[data-zoom]").forEach(button => button.addEventListener("click", () => {
    closeChooser(false);
    const [chart, action] = button.dataset.zoom.split(":");
    views[chart] = action === "reset" ? (fitChart(chart, visibleRows()) || viewport.fresh()) : viewport.zoom(views[chart], action === "in" ? 1.6 : 1/1.6, origins[chart], origins[chart], chart === "spectral");
    render(chart);
  }));
  function exportFigure() {
    closeChooser(false);
    const shown=visibleRows(), reportLink=document.querySelector(".visual-heading > a");
    const figure=node("svg", {xmlns:ns, width:1200, role:"img"}, null, null, true);
    draw(figure,"title",{},"ALMA observation comparison: position and frequency");
    draw(figure,"rect",{width:"100%",height:"100%",fill:"white"});
    let y=30;
    function text(value, bold=false) {
      // Fixed-width text makes long project/Member identities wrap predictably.
      for (const part of String(value).match(/.{1,138}/gu) || [""]) {
        draw(figure,"text",{x:24,y,fill:"#203e52","font-family":"monospace","font-size":13,
          "font-weight":bold ? 700 : 400},part);
        y+=19;
      }
    }
    text(document.querySelector(".visual-heading h1").textContent,true);
    text(`Report: ${reportLink.href}`);
    text(`Exported: ${new Date().toISOString()} | Current zoom; complete visible frequency rows`);
    text(document.querySelector(".visual-scope").textContent.replace(/\s+/g," ").trim());
    text(`Batch ${data.plot_page}/${data.plot_pages}; showing ${shown.length}/${rows.length} loaded comparisons. Other batches excluded.`);
    text(`Project: ${document.getElementById("visual-project").selectedOptions[0].textContent}; Member: ${document.getElementById("visual-member").selectedOptions[0].textContent}`);
    const current=rows.find(row=>row.id===selected);
    text(`Only selected: ${isolated ? "yes" : "no"}; Selected: ${current ? "#"+number(current)+" "+current.label : "none"}`);
    text("Legend: purple diamond = proposed; blue = Archive; orange = Queue (dashed position boundary).");
    text("Position circles are half-power boundaries, not angular resolution. Continuum dots are representative frequencies.");
    text("Display relationships do not recompute decisions. Matches do not establish absence of duplication elsewhere.");
    if (data.continuum_declaration) text("Continuum setup qualification uses a researcher declaration; review the text report for evidence.");
    const top=y+12;
    let chartHeight=0;
    for (const [index,id] of ["spatial-chart","spectral-chart"].entries()) {
      const original=document.getElementById(id), copy=original.cloneNode(true);
      const box=original.viewBox.baseVal, width=560, height=width*box.height/box.width;
      copy.setAttribute("x",index ? 616 : 24); copy.setAttribute("y",top+24);
      copy.setAttribute("width",width); copy.setAttribute("height",height);
      copy.querySelectorAll("text").forEach(element=>{
        element.setAttribute("font-family","Arial, sans-serif"); element.setAttribute("font-size","10");
        element.setAttribute("fill","#36586f");
      });
      copy.querySelectorAll("[tabindex]").forEach(element=>element.removeAttribute("tabindex"));
      draw(figure,"text",{x:index ? 616 : 24,y:top+12,"font-family":"Arial, sans-serif","font-size":16,fill:"#203e52"},index ? "Frequency (GHz)" : "Position (arcsec)");
      figure.append(copy); chartHeight=Math.max(chartHeight,height);
    }
    y=top+chartHeight+52;
    text(`Evidence available: position ${shown.filter(r=>r.spatial.available).length}/${shown.length}; frequency ${shown.filter(r=>r.spectral.available).length}/${shown.length}.`);
    text("Comparison identities (numbers remain stable across filters)",true);
    for (const row of shown) {
      text(`#${number(row)} ${row.label} | ${row.source} | ${row.intent} | SPW ${row.spw}`,true);
      text(`Requested window: ${row.window ?? "not recorded"}; beam path: ${row.beam_variant == null ? "not applicable" : row.beam_variant+1}`);
      for (const [key,value] of Object.entries(row.identity)) text(`${key}: ${value}`);
      if (!row.spatial.available) text(`Position: ${row.spatial.reason}`);
      if (!row.spectral.available) text(`Frequency: ${row.spectral.reason}`);
      text(`Evidence: ${reportLink.href.split("#")[0]}#${row.anchor}`);
      y+=8;
    }
    draw(figure,"metadata",{},JSON.stringify({report:reportLink.href,project,member,isolated,selected,views,rows:shown}));
    figure.setAttribute("height",y+16); figure.setAttribute("viewBox",`0 0 1200 ${y+16}`);
    const blob=new Blob([new XMLSerializer().serializeToString(figure)],{type:"image/svg+xml;charset=utf-8"});
    const url=URL.createObjectURL(blob), link=node("a",{href:url,download:"alma-comparison.svg"},null,document.body);
    link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),60000);
    document.getElementById("visual-preview-status").textContent=`Exported ${shown.length} comparisons with current filters, zoom and report references.`;
  }
  document.getElementById("visual-export").hidden=false;
  document.getElementById("visual-export-svg").addEventListener("click",exportFigure);
  select(selected);
})();
