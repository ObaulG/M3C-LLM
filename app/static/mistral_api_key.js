/**
 * Gestion de la clé API Mistral côté client.
 *
 * - Stockage dans le localStorage ('mistral_api_key') ;
 * - Synchronisation avec le compte (PUT /api/auth/me/mistral-api-key) quand
 *   l'utilisateur est connecté, pour que le serveur utilise cette clé pour
 *   les rôles user/guest (les admins utilisent la clé interne du serveur) ;
 * - Envoi de la clé dans l'en-tête 'X-Mistral-Api-Key' des requêtes LLM ;
 * - Bannière flottante si aucune clé n'est présente au chargement d'une page.
 */

var MISTRAL_API_KEY_STORAGE_KEY = 'mistral_api_key';
var MISTRAL_API_KEY_BANNER_DISMISSED_KEY = 'mistral_api_key_banner_dismissed';

/**
 * Stocke la clé API Mistral dans le localStorage.
 * @param {string} apiKey - La clé API à stocker
 */
function storeMistralApiKey(apiKey) {
    if (apiKey && apiKey.trim()) {
        localStorage.setItem(MISTRAL_API_KEY_STORAGE_KEY, apiKey.trim());
        return true;
    }
    return false;
}

/**
 * Récupère la clé API Mistral du localStorage.
 * @returns {string|null} La clé API ou null si non configurée
 */
function getMistralApiKey() {
    return localStorage.getItem(MISTRAL_API_KEY_STORAGE_KEY);
}

/**
 * Supprime la clé API Mistral du localStorage.
 */
function removeMistralApiKey() {
    localStorage.removeItem(MISTRAL_API_KEY_STORAGE_KEY);
}

/**
 * Vérifie si une clé API Mistral est configurée.
 * @returns {boolean} True si une clé est configurée, false sinon
 */
function hasMistralApiKey() {
    const apiKey = getMistralApiKey();
    return !!(apiKey && apiKey.length > 0);
}

/**
 * Vérifie si une clé API semble valide (format de base).
 * @param {string} apiKey - La clé à vérifier
 * @returns {boolean} True si la clé semble valide
 */
function isValidMistralApiKeyFormat(apiKey) {
    if (!apiKey) {
        return false;
    }

    // Format de base : commence par 'x' et a au moins 30 caractères
    if (!apiKey.startsWith('x')) {
        return false;
    }

    if (apiKey.length < 30) {
        return false;
    }

    return true;
}

/**
 * En-têtes à ajouter aux requêtes vers le serveur pour transmettre la clé API.
 * @returns {Object} Objet d'en-têtes (vide si aucune clé)
 */
function mistralApiKeyHeaders() {
    const apiKey = getMistralApiKey();
    if (apiKey) {
        return { 'X-Mistral-Api-Key': apiKey };
    }
    return {};
}

/**
 * Enregistre la clé API sur le compte de l'utilisateur connecté (si session active).
 * @param {string|null} apiKey - La clé à enregistrer (null pour effacer)
 * @returns {Promise<boolean>} True si la synchro a réussi (ou pas de session)
 */
function syncMistralApiKeyToServer(apiKey) {
    return fetch('/api/auth/me/mistral-api-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ mistral_api_key: apiKey || null })
    }).then(function (resp) {
        // 401 = non connecté : la clé reste purement locale, ce n'est pas une erreur
        if (resp.status === 401) {
            return false;
        }
        if (!resp.ok) {
            return resp.json().then(function (data) {
                throw new Error(data.detail || 'Erreur lors de l\'enregistrement de la clé');
            });
        }
        return true;
    }).catch(function (err) {
        console.warn('Synchro serveur de la clé API impossible:', err.message);
        return false;
    });
}

/**
 * Enregistre la clé localement ET sur le serveur (si connecté).
 * @param {string} apiKey - La clé à enregistrer
 */
function saveMistralApiKey(apiKey) {
    storeMistralApiKey(apiKey);
    syncMistralApiKeyToServer(apiKey);
    updateApiKeyStatusDisplay();
    hideMistralApiKeyBanner();
}

/**
 * Efface la clé localement ET sur le serveur (si connecté).
 */
function clearMistralApiKey() {
    removeMistralApiKey();
    syncMistralApiKeyToServer(null);
    updateApiKeyStatusDisplay();
}

/* ------------------------------------------------------------------ */
/* Bannière flottante : absence de clé API                            */
/* ------------------------------------------------------------------ */

function mistralApiKeyBannerStyles() {
    return `
        #mistralApiKeyBanner {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 2000;
            max-width: 360px;
            background: #fff8e6;
            border: 1px solid #ffc107;
            border-left: 5px solid #b74420;
            border-radius: 10px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.18);
            padding: 14px 16px;
            font-size: 14px;
            color: #5a4500;
            line-height: 1.5;
        }
        #mistralApiKeyBanner .banner-title {
            font-weight: 700;
            color: #b74420;
            margin-bottom: 6px;
        }
        #mistralApiKeyBanner a {
            color: #b74420;
            font-weight: 700;
        }
        #mistralApiKeyBanner .banner-close {
            position: absolute;
            top: 6px;
            right: 10px;
            cursor: pointer;
            font-size: 18px;
            font-weight: bold;
            color: #a08c5b;
            border: none;
            background: none;
            padding: 0 4px;
        }
        #mistralApiKeyBanner .banner-actions {
            margin-top: 10px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        #mistralApiKeyBanner .banner-btn {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            background: #b74420;
            color: #fff;
            text-decoration: none;
            font-weight: 600;
            font-size: 13px;
        }
        #mistralApiKeyBanner .banner-dismiss {
            background: transparent;
            color: #8a7a55;
            border: 1px solid #d8c9a3;
        }
    `;
}

/**
 * Affiche la bannière flottante d'alerte si aucune clé API n'est en localStorage.
 * Ne s'affiche pas sur la page de profil ni sur la page de connexion, ni si
 * l'utilisateur l'a fermée pour cette session.
 */
function maybeShowMistralApiKeyBanner() {
    if (hasMistralApiKey()) {
        return;
    }
    const page = (window.location.pathname.split('/').pop() || 'index.html');
    if (page === 'profile.html' || page === 'auth.html') {
        return;
    }
    if (sessionStorage.getItem(MISTRAL_API_KEY_BANNER_DISMISSED_KEY) === '1') {
        return;
    }
    if (document.getElementById('mistralApiKeyBanner')) {
        return;
    }

    const style = document.createElement('style');
    style.textContent = mistralApiKeyBannerStyles();
    document.head.appendChild(style);

    const banner = document.createElement('div');
    banner.id = 'mistralApiKeyBanner';
    banner.setAttribute('role', 'alert');
    banner.innerHTML =
        '<button type="button" class="banner-close" aria-label="Fermer">&times;</button>' +
        '<div class="banner-title">&#128273; Aucune cl&eacute; API Mistral configur&eacute;e</div>' +
        '<div>Vos requ&ecirc;tes ne pourront pas aboutir sans cl&eacute; API Mistral. ' +
        'Renseignez la v&ocirc;tre dans votre profil.</div>' +
        '<div class="banner-actions">' +
        '<a class="banner-btn" href="profile.html">Aller sur mon profil</a>' +
        '<button type="button" class="banner-btn banner-dismiss">Masquer</button>' +
        '</div>';
    document.body.appendChild(banner);

    banner.querySelector('.banner-close').addEventListener('click', hideMistralApiKeyBanner);
    banner.querySelector('.banner-dismiss').addEventListener('click', hideMistralApiKeyBanner);
}

/**
 * Masque la bannière (pour la session courante).
 */
function hideMistralApiKeyBanner() {
    const banner = document.getElementById('mistralApiKeyBanner');
    if (banner) {
        banner.remove();
    }
    sessionStorage.setItem(MISTRAL_API_KEY_BANNER_DISMISSED_KEY, '1');
}

/* ------------------------------------------------------------------ */
/* Modal de configuration (pages statiques)                           */
/* ------------------------------------------------------------------ */

function showMistralApiConfigModal() {
    const modal = document.getElementById('mistralApiModal');
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';

        const input = document.getElementById('mistralApiKeyInput');
        if (input) {
            input.value = getMistralApiKey() || '';
        }
    }
}

function hideMistralApiConfigModal() {
    const modal = document.getElementById('mistralApiModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

function saveMistralApiKeyFromModal() {
    const input = document.getElementById('mistralApiKeyInput');
    const messageDiv = document.getElementById('mistralApiMessage');

    if (!input) {
        return;
    }

    const apiKey = input.value.trim();

    if (!apiKey) {
        if (messageDiv) {
            messageDiv.textContent = 'Veuillez entrer une clé API.';
            messageDiv.style.display = 'block';
            messageDiv.style.background = '#fff3cd';
            messageDiv.style.color = '#856404';
        }
        return;
    }

    if (!isValidMistralApiKeyFormat(apiKey)) {
        if (messageDiv) {
            messageDiv.textContent = 'La clé API semble invalide. Vérifiez que vous avez copié la bonne clé.';
            messageDiv.style.display = 'block';
            messageDiv.style.background = '#f8d7da';
            messageDiv.style.color = '#721c24';
        }
        return;
    }

    saveMistralApiKey(apiKey);

    if (messageDiv) {
        messageDiv.textContent = 'Clé API enregistrée avec succès !';
        messageDiv.style.display = 'block';
        messageDiv.style.background = '#d4edda';
        messageDiv.style.color = '#155724';
    }

    updateApiKeyStatusDisplay();

    setTimeout(hideMistralApiConfigModal, 1500);
}

function clearMistralApiKeyFromModal() {
    clearMistralApiKey();
    const input = document.getElementById('mistralApiKeyInput');
    if (input) {
        input.value = '';
    }

    const messageDiv = document.getElementById('mistralApiMessage');
    if (messageDiv) {
        messageDiv.textContent = 'Clé API effacée.';
        messageDiv.style.display = 'block';
        messageDiv.style.background = '#d4edda';
        messageDiv.style.color = '#155724';
    }

    updateApiKeyStatusDisplay();
}

/**
 * Met à jour l'affichage du statut de la clé API dans le widget de profil.
 */
function updateApiKeyStatusDisplay() {
    const apiKey = getMistralApiKey();
    const apiStatus = document.getElementById('profileApiStatus');
    const apiKeyStatus = document.getElementById('apiKeyStatus');

    if (apiStatus) {
        if (apiKey && apiKey.length > 0) {
            apiStatus.textContent = '✓';
            apiStatus.title = 'Clé API Mistral configurée';
            apiStatus.style.color = '#28a745';
        } else {
            apiStatus.textContent = '✗';
            apiStatus.title = 'Clé API Mistral non configurée';
            apiStatus.style.color = '#dc3545';
        }
    }

    if (apiKeyStatus) {
        if (apiKey && apiKey.length > 0) {
            apiKeyStatus.innerHTML = '<span style="font-size: 16px; color: #28a745;">✓</span> Clé API configurée';
        } else {
            apiKeyStatus.innerHTML = '<span style="font-size: 16px; color: #dc3545;">✗</span> Clé API non configurée';
        }
    }
}

/**
 * Récupère la clé API Mistral pour l'utiliser dans une requête.
 * @returns {string} La clé API ou une chaîne vide si non configurée
 */
function getMistralApiKeyForRequest() {
    return getMistralApiKey() || '';
}

// Initialiser l'affichage du statut et la bannière au chargement de la page
document.addEventListener('DOMContentLoaded', function () {
    updateApiKeyStatusDisplay();
    maybeShowMistralApiKeyBanner();
});

// Exporter les fonctions pour les autres scripts
window.mistralApiKey = {
    store: storeMistralApiKey,
    get: getMistralApiKey,
    remove: removeMistralApiKey,
    has: hasMistralApiKey,
    isValid: isValidMistralApiKeyFormat,
    headers: mistralApiKeyHeaders,
    syncToServer: syncMistralApiKeyToServer,
    save: saveMistralApiKey,
    clear: clearMistralApiKey,
    showModal: showMistralApiConfigModal,
    hideModal: hideMistralApiConfigModal,
    saveFromModal: saveMistralApiKeyFromModal,
    clearFromModal: clearMistralApiKeyFromModal,
    updateStatus: updateApiKeyStatusDisplay,
    getForRequest: getMistralApiKeyForRequest,
    maybeShowBanner: maybeShowMistralApiKeyBanner,
    hideBanner: hideMistralApiKeyBanner
};
