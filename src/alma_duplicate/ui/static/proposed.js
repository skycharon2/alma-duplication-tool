/* Presentation only. All scientific validation remains on the server. */
const form = document.querySelector('.proposed-form');
if (form) {
  const syncPurpose = () => {
    const selected = [...form.querySelectorAll('[name="intents"]:checked')].map(input => input.value);
    for (const section of form.querySelectorAll('[data-purpose]')) {
      // Retain and reveal entered values even when the purpose is deselected.
      const hasValues = [...section.querySelectorAll('input, select')].some(input =>
        input.type === 'checkbox' ? input.checked :
        input.tagName === 'SELECT' ? input.value !== input.options[0]?.value : input.value.trim());
      section.hidden = selected.length > 0 && !selected.includes(section.dataset.purpose) && !hasValues;
    }
    const hint = form.querySelector('[data-continuum-hint]');
    hint.hidden = selected.includes('CONTINUUM');
  };
  syncPurpose();
  form.addEventListener('change', syncPurpose);
  form.addEventListener('input', () => {
    const status = document.querySelector('[data-validated]');
    if (status) {
      status.querySelector('#validation-current').hidden = true;
      status.querySelector('#validation-stale').hidden = false;
      for (const strong of status.querySelectorAll('strong')) strong.textContent = 'Revalidate';
      for (const note of form.querySelectorAll('[data-category]')) note.hidden = true;
      for (const control of form.querySelectorAll('[aria-invalid]')) control.removeAttribute('aria-invalid');
    }
  });
  // Expand technical details when a diagnostic points to a control inside them.
  form.addEventListener('click', event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link) return;
    const target = document.getElementById(link.hash.slice(1));
    if (!target) return;
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
      if (parent.dataset.purpose) parent.hidden = false;
    }
    if (!target.hasAttribute('tabindex') && !target.matches('input, select, button')) target.tabIndex = -1;
    target.focus();
  });
  const focusTarget = document.getElementById('remove-confirmation') ||
    form.querySelector('[aria-invalid="true"]') || form.querySelector('[data-validated]');
  if (focusTarget) {
    for (let parent = focusTarget.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    focusTarget.focus();
  }
}
