// Page admin de démonstration : application manuelle d'observations
// d'éléments de connaissance (schéma user_knowledge_model.sql).

const API_BASE = window.location.origin || window.location.protocol + '//' + window.location.host;
const OBSERVATIONS_ADMIN_API = API_BASE + '/api/observations-admin';

// Cache des options de cibles par type (knowledge / theme / entity)
const targetOptionsCache = { knowledge: [], theme: [], entity: [] };

document.addEventListener('DOMContentLoaded', () => {
    loadUsers();
    loadObservations();
});

// ---------------------------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------------------------

function showStatus(message, type) {
    const zone = document.getElementById('statusZone');
    const cls = type === 'error' ? 'alert-error' : 'alert-success';
    zone.innerHTML = `<div class="alert ${cls}">${escapeHtml(message)}</div>`;
    setTimeout(() => { zone.innerHTML = ''; }, 6000);
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

function parseJsonField(value, fieldId) {
    const raw = value.trim();
    if (!raw) return {};
    try {
        const parsed = JSON.parse(raw);
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
            showStatus(`Le champ ${fieldId} doit contenir un objet JSON.`, 'error');
            return null;
        }
        return parsed;
    } catch (e) {
        showStatus(`JSON invalide dans ${fieldId} : ${e.message}`, 'error');
        return null;
    }
}

async function apiFetch(url, options) {
    const response = await fetch(url, options);
    let data = null;
    try { data = await response.json(); } catch (e) { /* réponse vide */ }
    if (!response.ok) {
        throw new Error((data && data.detail) ? JSON.stringify(data.detail) : `HTTP ${response.status}`);
    }
    return data;
}

// ---------------------------------------------------------------------------
// Chargement des référentiels
// ---------------------------------------------------------------------------

async function loadUsers() {
    const userIdSelect = document.getElementById('userId');
    const filterUserSelect = document.getElementById('filterUser');
    try {
        const users = await apiFetch(`${OBSERVATIONS_ADMIN_API}/users`);
        userIdSelect.innerHTML = '<option value="">-- Choisir un utilisateur --</option>' +
            users.map(u => `<option value="${escapeHtml(u.user_id)}">${escapeHtml(u.label)} (${escapeHtml(u.source)})</option>`).join('');
        filterUserSelect.innerHTML = '<option value="">Tous</option>' +
            users.map(u => `<option value="${escapeHtml(u.user_id)}">${escapeHtml(u.label)}</option>`).join('');
    } catch (e) {
        userIdSelect.innerHTML = '<option value="">Erreur de chargement</option>';
        showStatus(`Impossible de charger les utilisateurs : ${e.message}`, 'error');
    }
}

async function loadTargetOptions(targetType) {
    if (targetOptionsCache[targetType].length) return targetOptionsCache[targetType];
    const options = await apiFetch(`${OBSERVATIONS_ADMIN_API}/targets?target_type=${targetType}&limit=500`);
    targetOptionsCache[targetType] = options;
    return options;
}

// ---------------------------------------------------------------------------
// Éditeur de cibles (observation_targets)
// ---------------------------------------------------------------------------

function addTargetRow() {
    const container = document.getElementById('targetsContainer');
    const row = document.createElement('div');
    row.className = 'target-row';
    row.innerHTML = `
        <select class="target-type" onchange="onTargetTypeChange(this)">
            <option value="knowledge">Connaissance</option>
            <option value="theme">Th\u00e8me</option>
            <option value="entity">Entit\u00e9</option>
        </select>
        <select class="target-id" required>
            <option value="">-- Charger... --</option>
        </select>
        <input type="number" class="target-weight" min="0" max="1" step="0.1" value="1.0" title="Poids" />
        <button type="button" class="target-remove" onclick="this.closest('.target-row').remove()" title="Retirer">✕</button>
    `;
    container.appendChild(row);
    onTargetTypeChange(row.querySelector('.target-type'));
}

async function onTargetTypeChange(selectEl) {
    const row = selectEl.closest('.target-row');
    const targetIdSelect = row.querySelector('.target-id');
    const targetType = selectEl.value;
    targetIdSelect.innerHTML = '<option value="">-- Chargement... --</option>';
    try {
        const options = await loadTargetOptions(targetType);
        if (!options.length) {
            targetIdSelect.innerHTML = '<option value="">Aucune cible disponible</option>';
            return;
        }
        targetIdSelect.innerHTML = options.map(o =>
            `<option value="${o.id}">#${o.id} \u2014 ${escapeHtml(o.label)}</option>`
        ).join('');
    } catch (e) {
        targetIdSelect.innerHTML = '<option value="">Erreur de chargement</option>';
    }
}

function collectTargets() {
    const targets = [];
    for (const row of document.querySelectorAll('#targetsContainer .target-row')) {
        const targetType = row.querySelector('.target-type').value;
        const targetId = row.querySelector('.target-id').value;
        const weight = parseFloat(row.querySelector('.target-weight').value);
        if (targetId) {
            targets.push({ target_type: targetType, target_id: parseInt(targetId, 10), weight: isNaN(weight) ? 1.0 : weight });
        }
    }
    return targets;
}

// ---------------------------------------------------------------------------
// Soumission du formulaire (POST /api/observations-admin/observations)
// ---------------------------------------------------------------------------

async function submitObservation(event) {
    event.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Enregistrement...';
    try {
        const userId = document.getElementById('userId').value;
        if (!userId) {
            showStatus('Choisissez un utilisateur observé.', 'error');
            return false;
        }
        const context = parseJsonField(document.getElementById('contextJson').value, 'Contexte');
        const payload = parseJsonField(document.getElementById('payloadJson').value, 'Payload');
        if (context === null || payload === null) return false;

        const body = {
            user_id: userId,
            observation_type: document.getElementById('observationType').value,
            specific_type: document.getElementById('specificType').value.trim(),
            context: context,
            confidence: parseFloat(document.getElementById('confidence').value),
            is_raw: true,
            payload: Object.keys(payload).length ? payload : null,
            targets: collectTargets(),
        };

        const result = await apiFetch(`${OBSERVATIONS_ADMIN_API}/observations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        showStatus(`Observation #${result.observation_id} enregistrée pour ${result.user_id} ` +
                   `(${result.observation_type}/${result.specific_type}, ${result.targets_count} cible(s)).`, 'success');
        loadObservations();
    } catch (e) {
        showStatus(`Erreur lors de l'enregistrement : ${e.message}`, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enregistrer l\'observation';
    }
    return false;
}

function resetForm() {
    document.getElementById('observationForm').reset();
    document.getElementById('targetsContainer').innerHTML = '';
    document.getElementById('statusZone').innerHTML = '';
}

// ---------------------------------------------------------------------------
// Listing des observations (GET /api/observations-admin/observations)
// ---------------------------------------------------------------------------

async function loadObservations() {
    const loading = document.getElementById('obsLoading');
    const body = document.getElementById('observationsBody');
    loading.classList.add('active');
    try {
        const params = new URLSearchParams();
        const filterUser = document.getElementById('filterUser').value;
        const filterType = document.getElementById('filterType').value;
        if (filterUser) params.set('user_id', filterUser);
        if (filterType) params.set('observation_type', filterType);
        params.set('limit', '50');

        const data = await apiFetch(`${OBSERVATIONS_ADMIN_API}/observations?${params.toString()}`);
        document.getElementById('observationsCount').textContent = data.count;
        if (!data.observations.length) {
            body.innerHTML = '<tr><td colspan="9" class="empty-state">Aucune observation pour ces filtres.</td></tr>';
            return;
        }
        body.innerHTML = data.observations.map(obs => renderObservationRow(obs)).join('');
    } catch (e) {
        body.innerHTML = `<tr><td colspan="9" class="empty-state">Erreur : ${escapeHtml(e.message)}</td></tr>`;
        showStatus(`Impossible de charger les observations : ${e.message}`, 'error');
    } finally {
        loading.classList.remove('active');
    }
}

function renderObservationRow(obs) {
    const typeBadge = `<span class="badge badge-${obs.observation_type}">${obs.observation_type}</span>`;
    const targetsHtml = obs.targets.length
        ? obs.targets.map(t => `<span class="badge badge-target" title="poids ${t.weight}">${t.target_type} #${t.target_id}${t.label ? ' \u2014 ' + escapeHtml(truncate(t.label, 40)) : ''}</span>`).join('')
        : '<span style="color:#999">\u2014</span>';
    const contextHtml = Object.keys(obs.context).length
        ? `<div class="json-preview">${escapeHtml(JSON.stringify(obs.context, null, 1))}</div>`
        : '<span style="color:#999">\u2014</span>';
    const payloadsHtml = obs.payloads.length
        ? obs.payloads.map(p => `<div class="json-preview"><b>${escapeHtml(p.payload_type)}</b>\n${escapeHtml(JSON.stringify(p.payload, null, 1))}</div>`).join('<hr/>')
        : '<span style="color:#999">\u2014</span>';
    return `
        <tr>
            <td>${obs.id}</td>
            <td>${escapeHtml(obs.user_id)}</td>
            <td>${typeBadge}</td>
            <td>${escapeHtml(obs.specific_type)}</td>
            <td>${escapeHtml(obs.timestamp || '')}</td>
            <td class="conf-value">${obs.confidence}</td>
            <td>${targetsHtml}</td>
            <td>${contextHtml}</td>
            <td>${payloadsHtml}</td>
        </tr>`;
}

function truncate(text, max) {
    return text.length > max ? text.slice(0, max) + '…' : text;
}
