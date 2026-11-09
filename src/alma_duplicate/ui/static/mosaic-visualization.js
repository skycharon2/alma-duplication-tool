(() => {
  const root = document.querySelector(".mosaic-explorer");
  const filters = [...root.querySelectorAll("[data-filter]")];
  const rows = [...root.querySelectorAll("[data-row]")];
  let selected = rows[0]?.dataset.row;

  function render() {
    const visible = rows.filter(row => filters.every(filter =>
      !filter.value || row.dataset[filter.dataset.filter] === filter.value));
    if (!visible.some(row => row.dataset.row === selected)) selected = visible[0]?.dataset.row;
    for (const row of rows) {
      row.hidden = !visible.includes(row);
      row.setAttribute("aria-pressed", String(row.dataset.row === selected));
    }
    for (const panel of root.querySelectorAll("[data-evidence]")) {
      panel.toggleAttribute("hidden", panel.dataset.evidence !== selected);
    }
    root.querySelector("#comparison-count").textContent = visible.length
      ? `${visible.length} of ${rows.length} comparisons`
      : !rows.length ? "No matching comparisons on this report page."
      : "No comparisons match these filters. Clear filters to see all comparisons.";
  }

  for (const filter of filters) filter.addEventListener("change", render);
  for (const row of rows) row.addEventListener("click", () => {
    selected = row.dataset.row;
    render();
  });
  root.querySelector("#clear-filters").addEventListener("click", () => {
    for (const filter of filters) filter.value = "";
    render();
  });
  const pages = [...root.querySelectorAll(".evidence-pager button")];
  for (const button of pages) button.addEventListener("click", () => {
    for (const page of pages) {
      const active = button === page;
      root.querySelector("#" + page.getAttribute("aria-controls")).hidden = !active;
      page.setAttribute("aria-pressed", String(active));
    }
  });
  render();
})();
