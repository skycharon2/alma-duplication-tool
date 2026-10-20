/* Combine purpose and explicit confirmation only after a user's choice.
   Existing POST inputs and scientific validation keep their separate meanings. */
window.initializeContinuumChoice = form => {
  const choice = form.querySelector('[name="intents"][value="CONTINUUM"]');
  const declaration = form.querySelector('[name="continuum_setup_declaration"]');
  const fallback = form.querySelector('[data-continuum-confirmation]');
  const note = form.querySelector('[data-combined-continuum]');
  if (!choice || !declaration || !fallback || !note) return;
  const render = () => {
    // Legacy selections without a declaration still need explicit confirmation.
    fallback.hidden = !choice.checked || declaration.checked;
    note.hidden = false;
  };
  choice.addEventListener('change', () => {
    declaration.checked = choice.checked;
    render();
  });
  declaration.addEventListener('change', render);
  form.addEventListener('reset', () => setTimeout(render, 0));
  render();
};
