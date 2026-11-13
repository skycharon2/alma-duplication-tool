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
  viewport.assignColors(rows);
  const views = {spatial: viewport.fresh(), spectral: viewport.fresh()};
  let project = "", member = "", array = "", isolated = false;
  const filteredRows = () => viewport.filter(rows, project, member, array);
  const visibleRows = () => viewport.visible(filteredRows(), selected, isolated);
  const spatialPoints = list => list.flatMap(row => !row.spatial.available ? [] :
    row.spatial.beams?.length ? [...row.spatial.beams.flatMap(beam => beam.outline || [beam.offset]), ...(row.spatial.rectangle_reference?.outline || [])] :
    (row.spatial.outline || [row.spatial.offset]));
  const expandedSetups = new Set();
  const frequencyValues = list => list.flatMap(row => {
    const f = row.spectral;
    const support = ((data.spectral_setups || {})[row.spectral_setup_id]?.components || []).flatMap(c => c.interval ? [c.interval.low, c.interval.high] : []);
    return [...support, ...(f.coverage || []).flatMap(c => [c.low,c.high,c.nominal_low,c.nominal_high].filter(Number.isFinite)), ...(!f.available ? [] : f.kind === "interval" ? [f.proposed, f.low, f.high] : [f.proposed, f.candidate, ...(f.coverage || []).flatMap(c => [c.low, c.high])])];
  });
  const extent = Math.max(10, spatialPoints(rows).reduce((v,p)=>Math.max(v,Math.abs(p[0]),Math.abs(p[1])),0)) * 1.15;
  const frequencies = frequencyValues(rows);
  const baseCenter = frequencies.length ? (Math.min(...frequencies)+Math.max(...frequencies))/2 : 0;
  const baseSpan = frequencies.length ? Math.max(Math.max(...frequencies)-Math.min(...frequencies), Math.abs(baseCenter)*.0001, 1e-12)*1.16 : 1;
  let spatialShapes = [];
  let gesture = null, suppressClick = false;
  let chooser = null, chooserReturn = null;
  const origins = {spatial: [240, 220], spectral: [350, 0]};
  const render = chart => chart === "spatial" ? spatialChart() : spectralChart();
  const ns = "http://www.w3.org/2000/svg";
  const color = row => row.plot_color;
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
  function selectable(parent, row, description) {
    const g = draw(parent, "g", {role: "button", tabindex: "0", "data-plot-select": row.id,
      "aria-pressed": String(row.id === selected), "aria-label": `Comparison ${row.display_number}: ${row.label}. ${description}`});
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
  const sky = window.createReportSky?.({origin: data.origin, rows: visibleRows, selected: highlighted, select});
  function spatialChart() {
    sky?.update();
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
    visibleRows().slice().sort((a, b) => Number(a.id === highlighted()) - Number(b.id === highlighted())).forEach(row => {
      if (!row.spatial.available) return;
      const spatial = row.spatial, active = row.id === highlighted();
      const desc = spatial.beams?.length ? `${spatial.beams.length} Queue Mosaic beams; array ${fmt(spatial.diameter_m)} m` :
        spatial.sky_outline ? `Archive Mosaic region; target ${spatial.point_status}; region reference only` :
        `Center RA ${fmt(spatial.center[0])}, Dec ${fmt(spatial.center[1])} deg; half-power radius ${fmt(spatial.radius_arcsec)} arcsec`;
      const g = selectable(layer, row, desc);
      if (spatial.beams?.length) {
        const rectangle = spatial.rectangle_reference;
        if (rectangle?.outline?.length) {
          const path = draw(g, 'path', {d: rectangle.outline.map((p,i)=>`${i?'L':'M'}${sx(p[0])},${sy(p[1])}`).join(' ')+'Z',
            fill:'none', stroke:color(row), 'stroke-width':active?2:1,
            'stroke-dasharray':'9 4 2 4', 'stroke-opacity':active?1:.45});
          draw(path, 'title', {}, rectangle.label);
        }
        spatial.beams.forEach(beam => {
          const polygon = (beam.outline || []).map(p => [sx(p[0]), sy(p[1])]);
          if (!polygon.length) return;
          spatialShapes.push({id: row.id, polygon,
            center: [sx(beam.offset[0]), sy(beam.offset[1])]});
          const d = polygon.map((p,j)=>`${j ? 'L' : 'M'}${p[0]},${p[1]}`).join(' ')+'Z';
          if (active) draw(g, 'path', {d, fill:'none',stroke:'white','stroke-width':4,'pointer-events':'none'});
          const colorValue = color(row);
          draw(g,'path',{d,stroke:active?colorValue:color(row),'stroke-width':active?2:1.1,
            fill:colorValue,'fill-opacity':active ? 0.09 : 0,'stroke-opacity':active?1:.4,
            'stroke-dasharray':row.source==='QUEUE'?'5 3':'none'});
          draw(g,'circle',{cx:sx(beam.offset[0]),cy:sy(beam.offset[1]),r:active?3:2,
            fill:colorValue,stroke:'white','stroke-width':.6});
        });
        return;
      }
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
      if (active) draw(g, "text", {x: sx(spatial.offset[0])+8, y: sy(spatial.offset[1])-8}, `#${row.display_number}${previewed === row.id ? " preview" : ""}`);
    });
    if (data.origin) { marker(layer, sx(0), sy(0)); draw(svg, "text", {x: 60, y: 22}, "◆ Your target at (0, 0)"); }
    if (!points.length) draw(svg, "text", {x: 240, y: 190, "text-anchor": "middle"}, "Candidate position evidence unavailable");
  }
  function coverageLabel(row, c) {
    const resolution = c.resolution ? `${fmt(c.resolution.value)} ${c.resolution.unit}` : "not recorded";
    return `SPW ${c.spw ?? row.spw} · Coverage ${fmt(c.low)}–${fmt(c.high)} GHz · Interval width ${fmt(c.bandwidth_ghz)} GHz · Spectral resolution ${resolution}`;
  }
  function spectralChart() {
    const svg = document.getElementById("spectral-chart");
    const shown = visibleRows();
    const entries = [], groups = new Map();
    shown.forEach(row => {
      const setup = (data.spectral_setups || {})[row.spectral_setup_id] || viewport.queueSetup(row);
      if (!setup || !setup.components.some(c => c.interval)) { entries.push({row}); return; }
      if (!groups.has(setup.id)) groups.set(setup.id, {setup, rows:[]});
      groups.get(setup.id).rows.push(row);
    });
    groups.forEach(group => {
      entries.push({group});
      if (expandedSetups.has(group.setup.id)) {
        if (group.setup.queue) {
          group.setup.components.forEach(component => entries.push({component, row:group.rows[0]}));
          group.rows.forEach(row => entries.push({row}));
        }
        else group.rows.forEach(row => entries.push({row}));
      }
    });
    const height = Math.max(330, 90 + entries.length * 40);
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
    entries.forEach((entry, i) => {
      const y = 48 + i*40;
      if (entry.group) {
        const {setup, rows: members} = entry.group;
        const opened = expandedSetups.has(setup.id);
        const g = draw(svg, "g", {role:"button", tabindex:"0", "aria-expanded":String(opened),
          "aria-label":`${opened ? "Collapse" : "Expand"} SPW comparisons for ${members[0].label}`});
        draw(g, "rect", {x:5,y:y-17,width:585,height:34,fill:members.some(r => r.id === highlighted()) ? "#e9f4fa" : "transparent"});
        draw(g, "text", {x:12,y:y+3}, `${opened ? "▾" : "▸"} ${setup.line ? "Evaluated" : "Setup"} · ${setup.queue ? setup.components.length + " SPWs · " + viewport.arrayKey(members[0]) : members.length + " rows"}`);
        draw(g, "title", {}, setup.queue ? members[0].label + " · Recorded Queue SPW coverage; expand for individual windows" : members[0].label+" · ASDM "+(setup.execution?.ASDM || "not recorded")+" · "+members.length+" comparisons · Full frequency_support; expand for SPWs");
        const toggle = () => { if (opened) expandedSetups.delete(setup.id); else expandedSetups.add(setup.id); spectralChart(); };
        g.addEventListener("click", event => { if (suppressClick) return; event.stopPropagation(); toggle(); });
        g.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); } });
        const layer = draw(g, "g", {"clip-path":"url(#frequency-clip)"});
        setup.components.filter(c => c.interval).forEach((c, j) => {
          const bar = draw(layer, "rect", {x:x(c.interval.low),y:y-7+(j%2)*7,
            width:Math.max(.5,x(c.interval.high)-x(c.interval.low)),height:6,fill:color(members[0]),opacity:.65});
          draw(bar, "title", {}, setup.queue ? coverageLabel(members[0], c.interval) : componentText(c));
        });
        const requested = [...new Set(members.filter(r => r.spectral.available).map(r => r.spectral.proposed))];
        requested.forEach(v => marker(layer,x(v),y));
        return;
      }
      if (entry.component) {
        const row = entry.row, c = entry.component.interval;
        const g = draw(svg, "g", {role:"group", "aria-label":`SPW ${c.spw ?? "?"} coverage reference; not a matching comparison`});
        draw(g, "title", {}, coverageLabel(row,c));
        draw(g, "text", {x:12,y:y+3}, `SPW ${c.spw ?? "?"} · coverage`);
        const layer = draw(g, "g", {"clip-path":"url(#frequency-clip)"});
        const nominal = Number.isFinite(c.nominal_low) && Number.isFinite(c.nominal_high) && c.nominal_low > 0 && c.nominal_high > c.nominal_low;
        if(nominal){
          const outer=draw(layer,"rect",{x:x(c.nominal_low),y:y-5,width:Math.max(.5,x(c.nominal_high)-x(c.nominal_low)),height:10,fill:color(row),opacity:.25});
          draw(outer,"title",{},`Nominal interval ${fmt(c.nominal_low)}–${fmt(c.nominal_high)} GHz`);
        }
        const bar = draw(layer, "rect", {x:x(c.low), y:y-3,
          width:Math.max(.5,x(c.high)-x(c.low)), height:6, fill:color(row), opacity:.7});
        draw(bar, "title", {}, coverageLabel(row,c));
        const midpoint=((nominal?c.nominal_low:c.low)+(nominal?c.nominal_high:c.high))/2;
        const dot=draw(layer,"circle",{cx:x(midpoint),cy:y,r:4,fill:"white",stroke:color(row),"stroke-width":1.5});
        draw(dot,"title",{},`${nominal?'Nominal':'Saved coverage'} window midpoint ${fmt(midpoint)} GHz; not a representative frequency`);
        if(Number.isFinite(row.spectral.proposed))marker(layer,x(row.spectral.proposed),y);
        return;
      }
      const row = entry.row, f = row.spectral, active = row.id === highlighted();
      const description = !f.available ? f.reason : f.kind === "interval" ?
        `Requested ${fmt(f.proposed)} GHz; candidate interval ${fmt(f.low)} to ${fmt(f.high)} GHz` :
        `Requested ${fmt(f.proposed)} GHz; candidate representative frequency ${fmt(f.candidate)} GHz`;
      const g = selectable(svg, row, description);
      draw(g, "rect", {x: 5, y: y-15, width: 585, height: 30, fill: active ? "#e9f4fa" : "transparent"});
      draw(g, "text", {x: 12, y: y+3}, `#${row.display_number} ${row.intent === "LINE" ? "LINE" : "CONT"} · ${row.source === "QUEUE" && row.intent === "CONTINUUM" ? "aggregate comparison" : "SPW " + row.spw}`);
      if (!f.available) { draw(g, "text", {x: 145, y: y+3}, "Frequency evidence unavailable"); return; }
      const layer = draw(g, "g", {"clip-path": "url(#frequency-clip)"});
      if (f.kind === "interval") {
        draw(layer, "rect", {x: x(f.low), y: y-4, width: Math.max(.5, x(f.high)-x(f.low)), height: 8, rx: 1,
          fill: color(row), opacity: active ? 1 : .55});
      } else {
        for (const coverage of f.coverage || []) {
          const bar = draw(layer, "rect", {x: x(coverage.low), y: y-5,
            width: Math.max(.5, x(coverage.high)-x(coverage.low)), height: 10,
            fill: color(row), opacity: .25});
          draw(bar, "title", {}, coverageLabel(row, coverage));
        }
        draw(layer, "circle", {cx: x(f.candidate), cy: y, r: 5, fill: color(row)});
      }
      marker(layer, x(f.proposed), y);
    });
  }
  const sensitivityText = entries => entries.length ?
    entries.map(e => `${fmt(e.value)} ${e.unit} (${e.basis})`).join("; ") : "Not recorded";
  function componentText(c) {
    return `Component ${c.index} · ${fmt(c.interval.low)}–${fmt(c.interval.high)} GHz · Width ${fmt(c.interval.bandwidth_ghz)} GHz · Resolution ${c.resolution ? fmt(c.resolution.value)+" "+c.resolution.unit : "not recorded"} · Sensitivity ${sensitivityText(c.sensitivities)} · Polarization ${c.polarization.join(", ")}`;
  }
  function details() {
    const row = rows.find(r => r.id === selected), body = document.getElementById("visual-detail-body");
    body.replaceChildren();
    if (!row) { node("p", {}, "No comparison selected. Clear the filters to show the loaded comparisons.", body); return; }
    node("h3", {}, `#${row.display_number} · ${row.label}`, body);
    node("p", {class: "selected-evidence"}, row.geometry_kind ? `${row.source} · ${row.intent} · ${row.geometry_kind} · ${row.array_diameter_m}-m array` : `${row.source} · ${row.intent} · Selected SPW ${row.spw}`, body);
    const dl = node("dl", {}, null, body);
    Object.entries(row.identity).filter(([key]) => !["Queue candidate", "Context ID", "Source row ID"].includes(key)).forEach(([key, value]) => { node("dt", {}, key, dl); node("dd", {}, value, dl); });
    if (row.window) { node("dt", {}, "Requested window", dl); node("dd", {}, row.window, dl); }
    const s = row.spatial;
    if (s.available && s.beams?.length) {
      if (s.rectangle_reference) node('p', {}, s.rectangle_reference.label + ' (same-color dash-dot boundary).', body);
      node("p", {}, `Queue ${row.geometry_kind} · ${fmt(row.array_diameter_m)}-m · ${s.beams.length} saved beams · ${s.covered_beam_count} cover the proposed point · half-power radius ${fmt(s.radius_arcsec)} arcsec`, body);
      node("p", {class:"notice"}, "The beam outlines are reconstructed from the available observation settings.", body);
      if (row.queue_line_matching_pairs > 1) node('p',{},`${row.queue_line_matching_pairs} matching LINE pairs in this array branch; each is separately selectable. Other evaluated pairs retain their results in the text report.`,body);
    } else if (s.available) {
      node("p", {}, `Separation: ${fmt(s.separation_arcsec)} arcsec · Half-power radius: ${fmt(s.radius_arcsec)} arcsec`, body);
      node("p", {}, `Beam evidence: D = ${fmt(s.diameter_m)} m at ${fmt(s.frequency_ghz)} GHz`, body);
    }
    if (!s.available && s.reason) node("p", {class: "notice"}, s.reason, body);
    const f = row.spectral;
    node("p", {}, !f.available ? f.reason : f.kind === "interval" ?
      `Requested: ${fmt(f.proposed)} GHz · Candidate: ${fmt(f.low)}–${fmt(f.high)} GHz` :
      `Representative frequencies: requested ${fmt(f.proposed)} GHz · candidate ${fmt(f.candidate)} GHz`, body);
    for (const coverage of f.coverage || []) node("p", {}, coverageLabel(row, coverage), body);
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
    document.getElementById("visual-selection-status").textContent = index < 0 ? "No visible comparisons. Clear filters." : `Selected comparison ${rows[index].display_number}: ${rows[index].label}. Showing ${visibleRows().length} of ${rows.length} loaded comparisons.`;
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
  function arrays() {
    options(document.getElementById("visual-array"), viewport.filter(rows,project,member),
      viewport.arrayKey, viewport.arrayKey, "All arrays");
    document.getElementById("visual-array").value = array;
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
    node("strong", {style: `border-left: 5px solid ${color(row)}; padding-left: 8px`}, `#${row.display_number} ${row.label}`, identity);
    node("span", {}, row.geometry_kind ? `Queue · ${row.intent} · ${row.geometry_kind} · ${row.array_diameter_m}-m` : `${row.source === "QUEUE" ? "Queue" : "Archive"} · ${row.intent} · SPW ${row.spw}${row.window ? ` · requested ${row.window}` : ""}${row.beam_variant != null ? ` · beam path ${row.beam_variant+1}` : ""}`, identity);
    node("small", {}, row.identity["Member OUS"] ? `Member ${row.identity["Member OUS"]}` : "Member OUS not recorded", identity);
    if (row.identity.ASDM) node("small", {}, `ASDM ${row.identity.ASDM}`, identity);
    const s=row.spatial, f=row.spectral, relation=viewport.relationships(row);
    const position=node("div", {class:"visual-current-values"}, null, summary);
    node("strong", {}, "Position", position);
    node("span", {}, s.available && s.beams?.length ? `${s.beams.length} recorded Queue beams` :
      s.available ? `Separation ${fmt(s.separation_arcsec)} arcsec` : "Evidence unavailable", position);
    if (s.available) node("small", {}, `Half-power radius ${fmt(s.radius_arcsec)} arcsec`, position);
    if (relation.radiusRatio !== null) node("small", {}, `Separation / half-power radius: ${fmt(relation.radiusRatio)} (1 = boundary; not angular resolution)`, position);
    if (!s.available && s.reason) node("small", {}, s.reason, position);
    const frequency=node("div", {class:"visual-current-values"}, null, summary);
    node("strong", {}, "Frequency", frequency);
    node("span", {}, f.available ? `Requested ${fmt(f.proposed)} GHz` : "Evidence unavailable", frequency);
    if (f.available) node("small", {}, f.kind === "interval" ? `Candidate ${fmt(f.low)}–${fmt(f.high)} GHz` : `Candidate ${fmt(f.candidate)} GHz (representative)`, frequency);
    if (relation.lowerMarginGHz !== null) {
      node("small", {}, `From lower edge: ${fmt(relation.lowerMarginGHz)} GHz; to upper edge: ${fmt(relation.upperMarginGHz)} GHz. Negative = outside interval.`, frequency);
    } else if (f.available) node("small", {}, (f.coverage?.length ? `${f.coverage.length} recorded SPW intervals shown as shaded bars; dots are representative frequencies.` : "Representative markers do not describe frequency coverage."), frequency);
    if (!f.available && f.reason) node("small", {}, f.reason, frequency);
  }
  function preview(id) {
    if (id === previewed) return;
    const scroller=document.querySelector(".frequency-scroll");
    if (previewScroll === null) previewScroll=scroller.scrollTop;
    previewed=id;
    spatialChart(); spectralChart();
    const row=rows.find(row=>row.id===id);
    document.getElementById("visual-preview-status").textContent=row ? `Preview #${row.display_number}: ${row.label}. Click to select; current selection is unchanged.` : "";
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
  members(); arrays();
  document.getElementById("visual-project").addEventListener("change", event => {
    project=event.target.value; member=""; array=""; members(); arrays(); applyFilters();
  });
  document.getElementById("visual-member").addEventListener("change", event => { member=event.target.value; array=""; arrays(); applyFilters(); });
  document.getElementById("visual-array").addEventListener("change", event => { array=event.target.value; applyFilters(); });
  document.getElementById("visual-isolate").addEventListener("click", () => { isolated=!isolated; select(selected); });
  document.getElementById("visual-clear").addEventListener("click", () => {
    project=""; member=""; array=""; isolated=false;
    document.getElementById("visual-project").value=""; members(); arrays(); applyFilters();
  });
  document.getElementById("visual-focus").addEventListener("click", () => {
    sky?.focus();
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
    rows.forEach(row => {
      if (!ids.includes(row.id)) return;
      const b = node("button", {type: "button", "aria-pressed": String(selected === row.id)}, null, list);
      node("strong", {style: `border-left: 5px solid ${color(row)}; padding-left: 8px`}, `#${row.display_number} · ${row.label}`, b);
      node("small", {}, row.geometry_kind ? `Queue · ${row.intent} · ${row.geometry_kind} · ${row.array_diameter_m}-m` : `${row.source} · ${row.intent} · SPW ${row.spw}${row.window ? ` · requested ${row.window}` : ""}${row.beam_variant != null ? ` · beam path ${row.beam_variant+1}` : ""}`, b);
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
      const ids = [...new Set(spatialShapes.filter(s => viewport.hits([p.x,p.y], s.polygon, s.center, tolerance)).map(s => s.id))];
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
    text(`Only selected: ${isolated ? "yes" : "no"}; Selected: ${current ? "#"+current.display_number+" "+current.label : "none"}`);
    text("Legend: purple diamond = proposed; each candidate object has its own color; Queue position boundaries are dashed.");
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
      text(`#${row.display_number} ${row.label} | ${row.source} | ${row.intent} | SPW ${row.spw}`,true);
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
