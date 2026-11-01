/* Locally pinned Aladin loader. Geometry must not depend on reference imagery. */
(function (root) {
  'use strict';
  function bounded(promise, ms, description) {
    let timer;
    return Promise.race([
      Promise.resolve(promise),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(description + ' timed out')), ms);
      })
    ]).finally(() => clearTimeout(timer));
  }
  const imports = new Map();
  async function load(moduleUrl) {
    if (!moduleUrl) throw new Error('Local Aladin module URL missing');
    if (!imports.has(moduleUrl)) imports.set(moduleUrl, import(moduleUrl));
    let module;
    try {
      module = await bounded(imports.get(moduleUrl), 15000, 'Aladin module');
    } catch (error) {
      imports.delete(moduleUrl);
      throw error;
    }
    const A = module.default;
    if (!A || typeof A.aladin !== 'function' || !A.init) {
      throw new Error('Invalid local Aladin module');
    }
    await bounded(A.init, 15000, 'Aladin initialization');
    return A;
  }
  async function waitForImagery(viewer, timeoutMs = 10000, expectedLayer = null) {
    // Aladin 3.8.2 publishes the base layer only after asynchronous attachment.
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const layer = viewer.getBaseImageLayer();
      if (layer && (!expectedLayer || layer === expectedLayer)) {
        if (layer.query) await bounded(layer.query, Math.max(1, deadline - Date.now()), 'Survey metadata');
        return layer;
      }
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    throw new Error('Survey layer initialization timed out');
  }

  const surveys = Object.freeze({
    dss: 'https://skies.esac.esa.int/DSSColor/',
    dssBackup: 'https://alasky.cds.unistra.fr/DSS/DSSColor/',
    panStarrs: 'https://alasky.cds.unistra.fr/Pan-STARRS/DR1/color-z-zg-g/'
  });
  async function changeSurvey(A, viewer, url, current = () => true) {
    // Direct URLs avoid the additional MOCServer registry dependency.
    const previous = viewer.getBaseImageLayer();
    let attached = false;
    try {
      const prepared = A.HiPS(url.replace(/\/+$/, ''));
      await bounded(prepared.query, 12000, 'Survey metadata');
      if (!current()) return null;
      attached = true;
      const layer = await bounded(viewer.setBaseImageLayer(prepared), 12000, 'Survey attachment');
      await waitForImagery(viewer, 12000, layer || prepared);
      return current() ? viewer.getBaseImageLayer() : null;
    } catch (error) {
      if (current() && attached && previous) {
        await bounded(viewer.setBaseImageLayer(previous), 12000, 'Restore previous survey');
      }
      throw error;
    }
  }
  async function loadReferenceImagery(viewer) {
    try {
      return await waitForImagery(viewer);
    } catch (primaryError) {
      // Keep the same viewer, pointing catalogue and geometry overlay.
      const layer = viewer.setBaseImageLayer(surveys.dssBackup);
      try {
        if (layer && layer.query) await bounded(layer.query, 10000, 'CDS survey metadata');
        return await waitForImagery(viewer, 10000, layer);
      } catch (backupError) {
        throw new Error('ESA DSS: ' + String(primaryError.message || primaryError)
          + '; CDS DSS: ' + String(backupError.message || backupError));
      }
    }
  }
  const api = { bounded, load, waitForImagery, loadReferenceImagery, changeSurvey, surveys };
  root.AlmaSkyRuntime = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
