/* Presentation only. All scientific validation remains on the server. */
(() => {
let resetActive = () => {};
let pauseActive = () => {};
window.addEventListener('pageshow', () => resetActive());
window.addEventListener('pagehide', () => pauseActive());
function initializeForm(form) {
  if (!form) return;
  let assessing = false;
  const busyMessage = document.getElementById('assessment-busy');
  const elapsedLabel = document.getElementById('assessment-elapsed');
  const waitingNote = document.getElementById('assessment-waiting-note');
  let elapsedTimer;
  let startedAt;
  let pollTimer;
  let pollController;
  let disconnected = false;
  const stageLabel = document.getElementById('assessment-stage');
  const countLabel = document.getElementById('assessment-count');
  const retrievedLabel = document.getElementById('assessment-retrieved');
  const track = form.querySelector('[role="progressbar"]');
  const fill = track?.querySelector('span');
  const stages = {
    validation: 'Checking input', archive_search: 'Searching Archive TAP',
    archive_ready: 'Archive candidates retrieved', queue_load: 'Loading and preparing Queue CSV',
    queue_ready: 'Queue candidates prepared', aq: 'Querying AQ array evidence',
    evaluation: 'Comparing candidates', report: 'Building report',
    storage_wait: 'Waiting to save report', inspection: 'Checking report evidence',
    storage: 'Saving report'
  };
  const stopPolling = () => {
    window.clearTimeout(pollTimer);
    pollController?.abort();
  };
  const showProgress = state => {
    if (stageLabel) stageLabel.textContent = stages[state.stage] || 'Assessment is running';
    const current = state.stages[state.stage] || {};
    const {completed, total, unit} = current;
    const determined = Number.isInteger(total) && total > 0 && Number.isInteger(completed);
    track?.classList.toggle('is-determinate', determined);
    if (determined) {
      const percent = Math.min(100, Math.max(0, completed / total * 100));
      track.setAttribute('aria-valuemin', '0');
      track.setAttribute('aria-valuemax', String(total));
      track.setAttribute('aria-valuenow', String(completed));
      track.setAttribute('aria-valuetext', `${completed} of ${total} ${unit} completed in this stage`);
      fill.style.width = `${percent}%`;
      countLabel.textContent = `${completed.toLocaleString()} / ${total.toLocaleString()} ${unit} · ${Math.floor(percent)}% of this stage`;
    } else {
      for (const attribute of ['aria-valuemin', 'aria-valuemax', 'aria-valuenow', 'aria-valuetext']) track?.removeAttribute(attribute);
      if (fill) fill.style.width = '';
      if (countLabel) countLabel.textContent = unit === 'bytes' && Number.isInteger(completed)
        ? `${(completed / 1048576).toFixed(1)} MiB written` : (total === 0 ? `0 ${unit}` : '');
    }
    track?.setAttribute('aria-label', stages[state.stage] || 'Assessment in progress');
    if (retrievedLabel) {
      retrievedLabel.textContent = [['archive_ready', 'Archive'], ['queue_ready', 'Queue']]
        .filter(([stage]) => state.stages[stage])
        .map(([stage, name]) => `${name}: ${state.stages[stage].completed.toLocaleString()} candidates retained`).join(' · ');
    }
  };
  const updateElapsed = () => {
    const seconds = Math.floor((performance.now() - startedAt) / 1000);
    const minutes = Math.floor(seconds / 60);
    if (elapsedLabel) elapsedLabel.textContent = `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
    if (waitingNote && seconds >= 60) waitingNote.hidden = false;
  };
  const resetAssessment = () => {
    assessing = false;
    stopPolling();
    window.clearInterval(elapsedTimer);
    if (busyMessage) busyMessage.hidden = true;
    if (waitingNote) { waitingNote.hidden = true; waitingNote.textContent = 'This can take several minutes. Keep this page open.'; }
    if (elapsedLabel) elapsedLabel.textContent = '0:00';
    for (const button of form.querySelectorAll('[data-assessment-pending]')) {
      button.removeAttribute('aria-disabled');
      button.removeAttribute('aria-busy');
      button.removeAttribute('data-assessment-pending');
    }
  };
  resetActive = resetAssessment;
  pauseActive = () => { window.clearInterval(elapsedTimer); stopPolling(); };
  form.addEventListener('submit', async event => {
    if (assessing) {
      event.preventDefault();
      return;
    }
    if (event.submitter?.value !== 'assess') return;
    const liveProgress = typeof crypto.randomUUID === 'function' && typeof fetch === 'function';
    const data = new FormData(form);
    data.set('action', 'assess');
    if (liveProgress) event.preventDefault();
    assessing = true;
    disconnected = false;
    showProgress({stage:'validation', stages:{}});
    event.submitter.setAttribute('aria-busy', 'true');
    startedAt = performance.now();
    updateElapsed();
    elapsedTimer = window.setInterval(updateElapsed, 1000);
    if (busyMessage) busyMessage.hidden = false;
    // Keep the submitter enabled so action=assess remains in the POST data.
    for (const button of form.querySelectorAll('button[type="submit"], button:not([type])')) {
      button.setAttribute('aria-disabled', 'true');
      button.setAttribute('data-assessment-pending', '');
    }
    if (!liveProgress) return; // Native POST remains available without this enhancement.
    const token = crypto.randomUUID().replaceAll('-', '');
    const progressUrl = form.dataset.progressUrl.replace('TOKEN', token);
    const problem = (message, retry = true) => {
      stopPolling();
      window.clearInterval(elapsedTimer);
      if (retry) resetAssessment();
      busyMessage.hidden = false;
      stageLabel.textContent = 'Assessment not completed';
      track.hidden = true;
      document.getElementById('assessment-progress-description').hidden = true;
      countLabel.textContent = '';
      waitingNote.hidden = false;
      waitingNote.textContent = message;
    };
    track.hidden = false;
    document.getElementById('assessment-progress-description').hidden = false;
    let missedPolls = 0;
    const poll = async () => {
      if (!assessing) return;
      pollController = new AbortController();
      const timeout = window.setTimeout(() => pollController.abort(), 5000);
      try {
        const response = await fetch(progressUrl, {cache:'no-store', signal:pollController.signal});
        if (!response.ok) throw new Error('Progress unavailable');
        const state = await response.json();
        missedPolls = 0;
        showProgress(state);
        if (state.status === 'COMPLETED') {
          stopPolling();
          window.location.assign(state.report_url);
          return;
        }
        if (state.status === 'FAILED' && disconnected) {
          problem('The assessment did not finish. Your inputs are retained. Check the service before trying again.');
          return;
        }
      } catch {
        missedPolls += 1;
        if (disconnected && missedPolls >= 5) {
          problem('Connection lost. The server may still be running this request. Reload the page to check the service before submitting again.', false);
          return;
        }
      } finally {
        window.clearTimeout(timeout);
      }
      if (assessing) pollTimer = window.setTimeout(poll, 800);
    };
    pollTimer = window.setTimeout(poll, 400);
    try {
      const response = await fetch(form.getAttribute('action'), {
        method:'POST', body:data, headers:{'X-Assessment-Progress':token}
      });
      if (response.ok && response.headers.get('Content-Type')?.includes('application/json')) {
        const state = await response.json();
        stopPolling();
        window.location.assign(state.report_url);
        return;
      }
      if (response.ok) {
        const html = new DOMParser().parseFromString(await response.text(), 'text/html');
        const replacement = html.querySelector('.proposed-form');
        if (replacement) {
          resetAssessment();
          form.replaceWith(replacement);
          initializeForm(replacement);
          return;
        }
      }
      problem(response.status === 429 ? 'The server is busy or this request was already submitted. Wait before trying again.' : 'The request could not be completed. Your inputs are retained; check the service before trying again.');
    } catch {
      disconnected = true;
      waitingNote.hidden = false;
      waitingNote.textContent = 'Connection interrupted. Checking whether the server completed this request…';
    }
  });
  form.addEventListener('click', event => {
    if (assessing && event.target.closest('button')) event.preventDefault();
  });
  const updatePurpose = form.querySelector('[data-update-purpose]');
  updatePurpose.hidden = true;
  const updateScope = form.querySelector('[data-update-scope]');
  updateScope.hidden = true;
  form.addEventListener('change', event => {
    if (event.target.matches('[name="intents"]')) {
      // Re-render the input groups on the server with all current values.
      // This action never validates, queries sources, or runs an assessment.
      form.requestSubmit(updatePurpose);
    } else if (event.target.matches('[name="target_kind"], [name="geometry"]')) {
      form.requestSubmit(updateScope);
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
    form.querySelector('[data-scope-updated]') ||
    form.querySelector('[aria-invalid="true"]') || form.querySelector('[data-validated]');
  if (focusTarget) {
    for (let parent = focusTarget.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    focusTarget.focus();
  }
}

initializeForm(document.querySelector('.proposed-form'));
})();
