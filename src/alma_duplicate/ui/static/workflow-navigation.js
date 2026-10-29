/* Dedicated Mosaic navigation: never reinterpret Single Pointing science inputs. */
(function(root) {
  'use strict';
  const scienceFields = ['target_name', 'ra', 'dec', 'angular', 'representative',
    'aggregate', 'redshift', 'continuum_redshift'];
  function hasEnteredScience(form) {
    return scienceFields.some(name => String(form.elements.namedItem(name)?.value || '').trim()) ||
      Boolean(form.querySelector('[name="rows"], [name="spw_rows"]')) ||
      Boolean(form.elements.namedItem('continuum_setup_declaration')?.checked);
  }
  const message = 'Opening another form starts a new observation. Current inputs will not transfer. Continue?';
  function confirmLeavingWorkflow(form, confirmLeave) {
    return !hasEnteredScience(form) || confirmLeave(message);
  }
  function maybeNavigateToMosaic(form, field, navigate, confirmLeave) {
    if (!field || field.name !== 'geometry' || field.value !== 'MOSAIC' ||
        form.dataset.workflow !== 'single' ||
        form.elements.namedItem('target_kind')?.value !== 'FIXED' ||
        !form.dataset.mosaicUrl) return false;
    if (!confirmLeavingWorkflow(form, confirmLeave)) {
      field.value = 'SINGLE_POINTING';
      return true;
    }
    navigate(form.dataset.mosaicUrl);
    return true;
  }
  root.maybeNavigateToMosaic = maybeNavigateToMosaic;
  root.confirmLeavingWorkflow = confirmLeavingWorkflow;
  if (typeof module !== 'undefined' && module.exports) module.exports = {
    maybeNavigateToMosaic, confirmLeavingWorkflow,
  };
})(typeof window === 'undefined' ? globalThis : window);
