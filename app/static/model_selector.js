/**
 * Transforme un <select multiple> natif (liste verticale étroite) en une grille
 * de cases à cocher regroupées par fournisseur, qui occupe la largeur disponible
 * et permet de sélectionner plusieurs modèles sur une même ligne.
 *
 * Le <select> d'origine est conservé (masqué) et synchronisé en permanence,
 * afin que tout code existant reposant sur `select.selectedOptions` ou
 * `select.value` continue de fonctionner sans modification.
 *
 * Utilisation :
 *   <script src="model_selector.js"></script>
 *   enhanceModelSelect(document.getElementById("model-select"));
 *
 *   // ou après chargement dynamique des options :
 *   loadModelsIntoSelect(selectEl).then(() => enhanceModelSelect(selectEl));
 *
 * Options :
 *   { columns: "auto" }  -> largeur de colonne CSS (défaut: "auto", grille fluide)
 *   { minItemWidth: 180 } -> largeur minimale d'un item (px) pour auto-fit
 */

const MODEL_SELECTOR_DEFAULTS = {
  columns: 'auto',
  minItemWidth: 180,
};

/**
 * Construit la grille de cases à cocher à partir des <option> et <optgroup>
 * du <select> fourni.
 * @param {HTMLSelectElement} selectEl
 * @param {Object} [options]
 * @returns {HTMLElement} le conteneur de la grille
 */
function buildModelCheckboxGrid(selectEl, options) {
  const opts = { ...MODEL_SELECTOR_DEFAULTS, ...options };

  const wrapper = document.createElement('div');
  wrapper.className = 'model-checkbox-grid';
  if (opts.columns === 'auto') {
    wrapper.style.gridTemplateColumns =
      `repeat(auto-fit, minmax(${opts.minItemWidth}px, 1fr))`;
  } else if (opts.columns) {
    wrapper.style.gridTemplateColumns = `repeat(${opts.columns}, 1fr)`;
  }

  const groups = Array.from(selectEl.querySelectorAll('optgroup'));
  const standalone = Array.from(selectEl.querySelectorAll(':scope > option'));

  const renderOption = (option) => {
    const item = document.createElement('label');
    item.className = 'model-checkbox-item';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = option.value;
    checkbox.checked = option.selected;
    checkbox.dataset.modelValue = option.value;

    const text = document.createElement('span');
    text.className = 'model-checkbox-label';
    text.textContent = option.textContent;

    item.appendChild(checkbox);
    item.appendChild(text);
    wrapper.appendChild(item);

    return checkbox;
  };

  if (groups.length) {
    groups.forEach((group) => {
      const groupLabel = document.createElement('div');
      groupLabel.className = 'model-checkbox-group-label';
      groupLabel.textContent = group.label;
      wrapper.appendChild(groupLabel);

      Array.from(group.querySelectorAll('option')).forEach(renderOption);
    });
  } else {
    standalone.forEach(renderOption);
  }

  return wrapper;
}

/**
 * Synchronise l'état des checkboxes vers le <select> masqué.
 * @param {HTMLSelectElement} selectEl
 * @param {HTMLElement} grid
 * @param {Function} [onChange] callback appelé après chaque changement
 */
function syncCheckboxesToSelect(selectEl, grid, onChange) {
  grid.addEventListener('change', (event) => {
    const target = event.target;
    if (target.type !== 'checkbox') return;

    const option = selectEl.querySelector(
      `option[value="${CSS.escape(target.value)}"]`
    );
    if (option) {
      option.selected = target.checked;
    }
    selectEl.dispatchEvent(new Event('change', { bubbles: true }));
    if (typeof onChange === 'function') onChange();
  });
}

/**
 * Améliore un <select multiple> en grille de cases à cocher.
 * @param {HTMLSelectElement} selectEl
 * @param {Object} [options]
 * @returns {HTMLElement|null} la grille créée, ou null si l'élément n'est pas multiple
 */
function enhanceModelSelect(selectEl, options = {}) {
  if (!selectEl || !selectEl.multiple) return null;

  // Évite la double initialisation
  if (selectEl.dataset.enhanced === 'true') {
    return selectEl.parentElement.querySelector('.model-checkbox-grid');
  }

  const grid = buildModelCheckboxGrid(selectEl, options);

  // Masque le <select> natif mais le garde dans le DOM pour selectedOptions
  selectEl.hidden = true;
  selectEl.dataset.enhanced = 'true';

  // Insère la grille juste après le <select>
  if (selectEl.nextSibling) {
    selectEl.parentNode.insertBefore(grid, selectEl.nextSibling);
  } else {
    selectEl.parentNode.appendChild(grid);
  }

  syncCheckboxesToSelect(selectEl, grid);

  return grid;
}

window.enhanceModelSelect = enhanceModelSelect;

/**
 * Bascule l'état replié/déplié de la zone de paramètres.
 * @param {HTMLElement} headerEl - le bouton .settings-header cliqué
 */
function toggleSettings(headerEl) {
  const settings = headerEl.closest('.settings');
  if (!settings) return;
  const collapsed = settings.classList.toggle('collapsed');
  headerEl.setAttribute('aria-expanded', String(!collapsed));
  if (collapsed) updateSettingsSummary(settings);
}

/**
 * Ouvre/ferme le widget flottant des paramètres (.settings-panel + .settings-fab).
 * Utilisé sur les pages chatbot où les paramètres vivent dans la marge droite.
 */
function toggleSettingsPanel() {
  const panel = document.getElementById('settingsPanel');
  const fab = document.getElementById('settingsFab');
  if (!panel || !fab) return;
  const open = panel.classList.toggle('open');
  fab.classList.toggle('open', open);
  fab.setAttribute('aria-expanded', String(open));
}

/**
 * Ferme le widget flottant si l'utilisateur clique en dehors du panneau
 * et du bouton, ou appuie sur Échap.
 */
function initSettingsPanelDismiss() {
  document.addEventListener('click', (event) => {
    const panel = document.getElementById('settingsPanel');
    const fab = document.getElementById('settingsFab');
    if (!panel || !panel.classList.contains('open')) return;
    if (panel.contains(event.target) || fab.contains(event.target)) return;
    panel.classList.remove('open');
    fab.classList.remove('open');
    fab.setAttribute('aria-expanded', 'false');
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const panel = document.getElementById('settingsPanel');
    const fab = document.getElementById('settingsFab');
    if (!panel || !panel.classList.contains('open')) return;
    panel.classList.remove('open');
    fab.classList.remove('open');
    fab.setAttribute('aria-expanded', 'false');
  });
}

/**
 * Construit un résumé textuel des paramètres actifs et l'affiche dans
 * .settings-header-summary. Utilisé quand le panneau est replié pour que
 * l'utilisateur voie l'état courant sans le déplier.
 * @param {HTMLElement} settingsEl - le conteneur .settings
 */
function updateSettingsSummary(settingsEl) {
  const summaryEl = settingsEl.querySelector('.settings-header-summary');
  if (!summaryEl) return;

  const parts = [];

  const useRAG = settingsEl.querySelector('#useRAG');
  if (useRAG && useRAG.checked) parts.push('RAG');

  const useReranking = settingsEl.querySelector('#useReranking');
  if (useReranking && useReranking.checked) parts.push('Reranking');

  const numSources = settingsEl.querySelector('#numSources');
  if (numSources && numSources.value) parts.push(`${numSources.value} sources`);

  const modelSelect = settingsEl.querySelector('#model-select');
  if (modelSelect) {
    const selected = Array.from(modelSelect.selectedOptions).map((o) => o.textContent);
    if (selected.length) {
      parts.push(selected.length === 1 ? selected[0] : `${selected.length} modèles`);
    } else {
      parts.push('Aucun modèle');
    }
  }

  summaryEl.textContent = parts.join(' · ');
}

/**
 * Met à jour le résumé de tous les panneaux .settings repliés de la page.
 * À appeler quand un paramètre change (dépendances : change sur le select,
 * input sur les checkboxes/number).
 */
function refreshAllSettingsSummaries() {
  document.querySelectorAll('.settings.collapsed').forEach(updateSettingsSummary);
}

document.addEventListener('DOMContentLoaded', () => {
  // Met à jour le résumé quand un paramètre change, même si le panneau est replié.
  // Couvre le panneau inline (.settings, tutorials) et le widget flottant (.settings-panel, chatbot).
  document.querySelectorAll('.settings, .settings-panel').forEach((settings) => {
    const modelSelect = settings.querySelector('#model-select');
    if (modelSelect) {
      modelSelect.addEventListener('change', refreshAllSettingsSummaries);
    }
    settings.querySelectorAll('input[type="checkbox"], input[type="number"]').forEach((input) => {
      input.addEventListener('change', refreshAllSettingsSummaries);
      input.addEventListener('input', refreshAllSettingsSummaries);
    });
  });

  // Fermeture du widget flottant au clic extérieur / Échap (pages chatbot)
  initSettingsPanelDismiss();
});

window.toggleSettings = toggleSettings;
window.toggleSettingsPanel = toggleSettingsPanel;
window.updateSettingsSummary = updateSettingsSummary;
