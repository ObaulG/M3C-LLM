/**
 * Gestion de la clé API Mistral côté client.
 *
 * - La clé n'est JAMAIS stockée dans le navigateur (plus de localStorage) :
 *   elle est enregistrée côté serveur via PUT /api/auth/me/mistral-api-key
 *   (table SQL dédiée, user_mistral_api_keys) ;
 * - Le serveur utilise cette clé automatiquement pour les rôles
 *   user/guest (les admins utilisent la clé interne du serveur) ;
 * - Le statut (clé configurée ou non) est obtenu via
 *   GET /api/auth/me/mistral-api-key, qui ne renvoie jamais la clé ;
 * - Bannière flottante si aucune clé n'est enregistrée.
 */

var MISTRAL_API_KEY_BANNER_DISMISSED_KEY = 'mistral_api_key_banner_dismissed';

/**
 * Vérifie si une clé API Mistral semble valide (format de base).
 * @param {string} apiKey - La clé à vérifier
 * @returns {boolean} True si la clé semble valide
 */
function isValidMistralApiKeyFormat(apiKey) {
    if (!apiKey) {
        return false;
    }

    // Format de base : commence par 'mstrl' et a au moins 30 caractères
    if (!apiKey.startsWith('mstrl')) {
        return false;
    }

    if (apiKey.length < 30) {
        return false;
    }

    return true;
}

/**
 * Récupère l'état de la clé API Mistral enregistrée sur le serveur.
 * @returns {Promise<Object|null>} {has_api_key: boolean, masked: string|null} ou null si non connecté
 */
function fetchMistralApiKeyStatus() {
    return fetch('/api/auth/me/mistral-api-key', {
        method: 'GET',
        credentials: 'same-origin'
    }).then(function (resp) {
        if (resp.status === 401) {
            return null;
        }
        if (!resp.ok) {
            throw new Error('Erreur lors de la récupération du statut de la clé');
        }
        return resp.json();
    }).catch(function (err) {
        console.warn('Récupération du statut de la clé API impossible:', err.message);
        return null;
    });
}

/**
 * Enregistre la clé API sur le compte de l'utilisateur connecté.
 * @param {string|null} apiKey - La clé à enregistrer (null pour effacer)
 * @returns {Promise<boolean>} True si l'enregistrement a réussi
 */
function syncMistralApiKeyToServer(apiKey) {
    return fetch('/api/auth/me/mistral-api-key', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ mistral_api_key: apiKey || null })
    }).then(function (resp) {
        // 401 = non connecté : impossible d'enregistrer la clé côté serveur
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
        console.warn('Enregistrement serveur de la clé API impossible:', err.message);
        return false;
    });
}

/**
 * Enregistre la clé API sur le serveur.
 * @param {string} apiKey - La clé à enregistrer
 * @returns {Promise<boolean>} True si l'enregistrement a réussi
 */
function saveMistralApiKey(apiKey) {
    return syncMistralApiKeyToServer(apiKey).then(function (ok) {
        updateApiKeyStatusDisplay();
        if (ok) {
            hideMistralApiKeyBanner();
        }
        return ok;
    });
}

/**
 * Efface la clé API enregistrée sur le serveur.
 * @returns {Promise<boolean>} True si l'effacement a réussi
 */
function clearMistralApiKey() {
    return syncMistralApiKeyToServer(null).then(function (ok) {
        updateApiKeyStatusDisplay();
        return ok;
    });
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
 * Affiche la bannière flottante d'alerte si aucune clé API Mistral n'est
 * enregistrée sur le serveur. Ne s'affiche pas sur la page de profil ni sur
 * la page de connexion, ni si l'utilisateur l'a fermée pour cette session.
 */
function maybeShowMistralApiKeyBanner() {
    const page = (window.location.pathname.split('/').pop() || 'index.html');
    if (page === 'profile.html' || page === 'profile' || page === 'auth.html') {
        return;
    }
    if (sessionStorage.getItem(MISTRAL_API_KEY_BANNER_DISMISSED_KEY) === '1') {
        return;
    }
    if (document.getElementById('mistralApiKeyBanner')) {
        return;
    }

    fetchMistralApiKeyStatus().then(function (status) {
        if (!status || status.has_api_key) {
            return;
        }
        if (status.required === false) {
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
            '<div class="banner-title">&#128273; Aucune clé API Mistral configurée</div>' +
            '<div>Vos requêtes ne pourront pas aboutir sans clé API Mistral. ' +
            'Renseignez la vôtre dans votre profil.</div>' +
            '<div class="banner-actions">' +
            '<a class="banner-btn" href="profile.html">Aller sur mon profil</a>' +
            '<button type="button" class="banner-btn banner-dismiss">Masquer</button>' +
            '</div>';
        document.body.appendChild(banner);

        banner.querySelector('.banner-close').addEventListener('click', hideMistralApiKeyBanner);
        banner.querySelector('.banner-dismiss').addEventListener('click', hideMistralApiKeyBanner);
    });
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
            input.value = '';
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

    saveMistralApiKey(apiKey).then(function (ok) {
        if (!messageDiv) {
            return;
        }
        if (ok) {
            messageDiv.textContent = 'Clé API enregistrée avec succès !';
            messageDiv.style.display = 'block';
            messageDiv.style.background = '#d4edda';
            messageDiv.style.color = '#155724';
            setTimeout(hideMistralApiConfigModal, 1500);
        } else {
            messageDiv.textContent = 'Impossible d\'enregistrer la clé. Êtes-vous connecté ?';
            messageDiv.style.display = 'block';
            messageDiv.style.background = '#f8d7da';
            messageDiv.style.color = '#721c24';
        }
    });

    updateApiKeyStatusDisplay();
}

function clearMistralApiKeyFromModal() {
    clearMistralApiKey().then(function (ok) {
        const messageDiv = document.getElementById('mistralApiMessage');
        if (messageDiv) {
            if (ok) {
                messageDiv.textContent = 'Clé API effacée.';
                messageDiv.style.display = 'block';
                messageDiv.style.background = '#d4edda';
                messageDiv.style.color = '#155724';
            } else {
                messageDiv.textContent = 'Impossible d\'effacer la clé. Êtes-vous connecté ?';
                messageDiv.style.display = 'block';
                messageDiv.style.background = '#f8d7da';
                messageDiv.style.color = '#721c24';
            }
        }
    });
    const input = document.getElementById('mistralApiKeyInput');
    if (input) {
        input.value = '';
    }

    updateApiKeyStatusDisplay();
}

/**
 * Met à jour l'affichage du statut de la clé API (interroge le serveur).
 */
function updateApiKeyStatusDisplay() {
    fetchMistralApiKeyStatus().then(function (status) {
        const hasKey = !!(status && status.has_api_key);
        const apiStatus = document.getElementById('profileApiStatus');
        const apiKeyStatus = document.getElementById('apiKeyStatus');

        if (apiStatus) {
            if (hasKey) {
                apiStatus.textContent = '\u2713';
                apiStatus.title = 'Clé API Mistral configurée';
                apiStatus.style.color = '#28a745';
            } else if (status && status.required === false) {
                apiStatus.textContent = '\u2713';
                apiStatus.title = 'Clé API Mistral non requise : la clé du serveur est utilisée';
                apiStatus.style.color = '#28a745';
            } else {
                apiStatus.textContent = '\u2717';
                apiStatus.title = 'Clé API Mistral non configurée';
                apiStatus.style.color = '#dc3545';
            }
        }

        if (apiKeyStatus) {
            if (hasKey) {
                apiKeyStatus.innerHTML = '<span style="font-size: 16px; color: #28a745;">\u2713</span> Clé API configurée';
            } else if (status && status.required === false) {
                apiKeyStatus.innerHTML = '<span style="font-size: 16px; color: #28a745;">\u2713</span> Clé API non requise : la clé du serveur est utilisée';
            } else {
                apiKeyStatus.innerHTML = '<span style="font-size: 16px; color: #dc3545;">\u2717</span> Clé API non configurée';
            }
        }
    });
}

// Initialiser l'affichage du statut et la bannière au chargement de la page
document.addEventListener('DOMContentLoaded', function () {
    updateApiKeyStatusDisplay();
    maybeShowMistralApiKeyBanner();
});

// Exporter les fonctions pour les autres scripts
window.mistralApiKey = {
    isValid: isValidMistralApiKeyFormat,
    fetchStatus: fetchMistralApiKeyStatus,
    syncToServer: syncMistralApiKeyToServer,
    save: saveMistralApiKey,
    clear: clearMistralApiKey,
    showModal: showMistralApiConfigModal,
    hideModal: hideMistralApiConfigModal,
    saveFromModal: saveMistralApiKeyFromModal,
    clearFromModal: clearMistralApiKeyFromModal,
    updateStatus: updateApiKeyStatusDisplay,
    maybeShowBanner: maybeShowMistralApiKeyBanner,
    hideBanner: hideMistralApiKeyBanner
};
