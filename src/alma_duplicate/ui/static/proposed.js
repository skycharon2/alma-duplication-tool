/* Presentation only. All scientific validation remains on the server. */
const form = document.querySelector('.proposed-form');
if (form) {
  const updatePurpose = form.querySelector('[data-update-purpose]');
  updatePurpose.hidden = true;
  form.addEventListener('change', event => {
    if (event.target.matches('[name="intents"]')) {
      // Re-render the input groups on the server with all current values.
      // This action never validates, queries sources, or runs an assessment.
      form.requestSubmit(updatePurpose);
    }
  });
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
    target.hidden = false;
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
      if (parent.hidden) parent.hidden = false;
    }
    if (!target.hasAttribute('tabindex') && !target.matches('input, select, button')) target.tabIndex = -1;
    target.focus();
  });
  const focusTarget = document.getElementById('execution-error') ||
    document.getElementById('remove-confirmation') ||
    form.querySelector('[data-added-row] input[type="text"]') ||
    form.querySelector('[data-purpose-updated]') ||
    form.querySelector('[aria-invalid="true"]') || form.querySelector('[data-validated]');
  if (focusTarget) {
    for (let parent = focusTarget.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    focusTarget.focus();
  }
}
