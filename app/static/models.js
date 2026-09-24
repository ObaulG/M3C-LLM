/**
 * Charge la liste des modèles et de leurs fournisseurs depuis l'API
 * (GET /api/models), elle-même alimentée par config/models/models.csv,
 * et peuple les éléments de sélection de modèle des pages HTML.
 *
 * Utilisation :
 *   - Inclure ce script dans la page : <script src="/static/models.js"></script>
 *   - Appeler loadModelsIntoSelect(selectEl, options) avec un <select>
 *     (supporte l'attribut multiple pour la sélection multiple).
 */

const MODELS_API_URL = '/api/models';
const PROVIDER_LABELS = {
  mistral: 'Mistral',
  google: 'Gemini',
  ollama: 'Local'
};

/**
 * Récupère la liste des modèles depuis l'API.
 * @returns {Promise<Array<{model: string, provider: string, label: string}>>}
 */
async function fetchModels() {
  const response = await fetch(MODELS_API_URL);
  if (!response.ok) {
    throw new Error(`Échec du chargement des modèles (${response.status})`);
  }
  const data = await response.json();
  return data.models || [];
}

/**
 * Crée une liste d'<option> groupées par fournisseur (<optgroup>).
 * @param {Array<{model: string, provider: string, label: string}>} models
 * @param {Array<string>} providerOrder - ordre d'affichage des fournisseurs
 * @returns {HTMLOptGroupElement[]}
 */
function buildOptionGroups(models, providerOrder) {
  const byProvider = new Map();
  for (const m of models) {
    if (!byProvider.has(m.provider)) byProvider.set(m.provider, []);
    byProvider.get(m.provider).push(m);
  }

  const order = providerOrder
    ? [...providerOrder.filter((p) => byProvider.has(p))]
    : [];
  for (const p of byProvider.keys()) {
    if (!order.includes(p)) order.push(p);
  }

  return order.map((provider) => {
    const group = document.createElement('optgroup');
    group.label = PROVIDER_LABELS[provider] || provider;
    group.dataset.provider = provider;
    for (const m of byProvider.get(provider)) {
      const option = document.createElement('option');
      option.value = m.model;
      option.textContent = m.label;
      group.appendChild(option);
    }
    return group;
  });
}

/**
 * Peuple un <select> avec les modèles disponibles, groupés par fournisseur.
 * @param {HTMLSelectElement} selectEl - élément <select> à remplir
 * @param {Object} [options]
 * @param {Array<string>} [options.providerOrder] - ordre des fournisseurs
 * @param {Array<string>} [options.providers] - limite la liste à ces fournisseurs
 * @param {boolean} [options.keepFirst] - conserve la première option existante
 * @param {string|Array<string>} [options.selected] - modèle(s) présélectionné(s)
 * @param {boolean} [options.prefixProvider] - préfixe la valeur par le fournisseur
 *   ("mistral/mistral-small"), attendu par certaines routes /api/qa-single, /api/evaluate
 * @returns {Promise<Array<{model: string, provider: string, label: string}>>}
 */
async function loadModelsIntoSelect(selectEl, options = {}) {
  if (!selectEl) {
    throw new Error("Élément <select> de modèles introuvable");
  }

  let models = await fetchModels();
  if (options.providers && options.providers.length) {
    models = models.filter((m) => options.providers.includes(m.provider));
  }
  const firstOption = selectEl.options[0];
  const keepFirst = options.keepFirst && firstOption && firstOption.value === '';

  selectEl.innerHTML = '';
  if (keepFirst) {
    selectEl.appendChild(firstOption.cloneNode(true));
  }

  for (const group of buildOptionGroups(models, options.providerOrder)) {
    if (options.prefixProvider) {
      for (const option of group.options) {
        option.value = group.dataset.provider + '/' + option.value;
      }
    }
    selectEl.appendChild(group);
  }

  const selected = options.selected
    ? (Array.isArray(options.selected) ? options.selected : [options.selected])
    : [];
  for (const value of selected) {
    const option = selectEl.querySelector(`option[value="${CSS.escape(value)}"]`);
    if (option) option.selected = true;
  }

  selectEl.dispatchEvent(new Event('change', { bubbles: true }));
  return models;
}

window.fetchModels = fetchModels;
window.loadModelsIntoSelect = loadModelsIntoSelect;
