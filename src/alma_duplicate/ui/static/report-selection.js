const selectionForm = document.getElementById('report-selection');

if (selectionForm) {
  const counter = document.getElementById('report-selection-count');
  const buttons = selectionForm.querySelectorAll('button');
  const entries = Array.from(selectionForm.elements).filter(control => control.name === 'entry');

  function updateSelection() {
    const count = entries.filter(entry => entry.checked).length;
    counter.textContent = `${count} selected`;
    for (const button of buttons) button.disabled = count === 0;
  }

  counter.hidden = false;
  for (const entry of entries) entry.addEventListener('change', updateSelection);
  selectionForm.addEventListener('reset', () => setTimeout(updateSelection, 0));
  window.addEventListener('pageshow', updateSelection);
  updateSelection();
}
