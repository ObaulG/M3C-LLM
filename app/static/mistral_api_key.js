/**
 * Gestion de la clé API Mistral côté client.
 * 
 * Ce fichier fournit des fonctions pour :
 * - Stocker et récupérer la clé API Mistral dans le localStorage
 * - Vérifier si une clé est configurée
 * - Afficher/masquer la modal de configuration
 */

/**
 * Stocke la clé API Mistral dans le localStorage.
 * @param {string} apiKey - La clé API à stocker
 */
function storeMistralApiKey(apiKey) {
    if (apiKey && apiKey.trim()) {
        localStorage.setItem('mistral_api_key', apiKey.trim());
        return true;
    }
    return false;
}

/**
 * Récupère la clé API Mistral du localStorage.
 * @returns {string|null} La clé API ou null si non configurée
 */
function getMistralApiKey() {
    return localStorage.getItem('mistral_api_key');
}

/**
 * Supprime la clé API Mistral du localStorage.
 */
function removeMistralApiKey() {
    localStorage.removeItem('mistral_api_key');
}

/**
 * Vérifie si une clé API Mistral est configurée.
 * @returns {boolean} True si une clé est configurée, false sinon
 */
function hasMistralApiKey() {
    const apiKey = getMistralApiKey();
    return apiKey && apiKey.length > 0;
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
 * Affiche la modal de configuration de la clé API Mistral.
 */
function showMistralApiConfigModal() {
    const modal = document.getElementById('mistralApiModal');
    if (modal) {
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
        
        // Pré-remplir le champ si une clé existe
        const input = document.getElementById('mistralApiKeyInput');
        if (input) {
            input.value = getMistralApiKey() || '';
        }
    }
}

/**
 * Masque la modal de configuration de la clé API Mistral.
 */
function hideMistralApiConfigModal() {
    const modal = document.getElementById('mistralApiModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

/**
 * Enregistre la clé API Mistral depuis la modal.
 */
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
    
    // Stocker la clé
    storeMistralApiKey(apiKey);
    
    if (messageDiv) {
        messageDiv.textContent = 'Clé API enregistrée avec succès !';
        messageDiv.style.display = 'block';
        messageDiv.style.background = '#d4edda';
        messageDiv.style.color = '#155724';
    }
    
    // Mettre à jour l'affichage du statut
    updateApiKeyStatusDisplay();
    
    // Fermer la modal après un court délai
    setTimeout(hideMistralApiConfigModal, 1500);
}

/**
 * Efface la clé API Mistral.
 */
function clearMistralApiKey() {
    removeMistralApiKey();
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
    
    // Mettre à jour l'affichage du statut
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

// Initialiser l'affichage du statut au chargement de la page
document.addEventListener('DOMContentLoaded', function() {
    updateApiKeyStatusDisplay();
});

// Exporter les fonctions pour les autres scripts
window.mistralApiKey = {
    store: storeMistralApiKey,
    get: getMistralApiKey,
    remove: removeMistralApiKey,
    has: hasMistralApiKey,
    isValid: isValidMistralApiKeyFormat,
    showModal: showMistralApiConfigModal,
    hideModal: hideMistralApiConfigModal,
    save: saveMistralApiKeyFromModal,
    clear: clearMistralApiKey,
    updateStatus: updateApiKeyStatusDisplay,
    getForRequest: getMistralApiKeyForRequest
};
