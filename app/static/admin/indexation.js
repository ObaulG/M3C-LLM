// Administration - Indexation des Documents
// Version simplifiée : indexation de TOUS les documents

const API_BASE = '';

// Variables globales pour SSE
let currentJobId = null;
let eventSource = null;

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    setupRadioButtons();
    loadEmbedders();
    loadIndexingCount();
});

// ============================================================================
// GESTION DES EMBEDDERS
// ============================================================================

let availableEmbedders = [];

async function loadEmbedders() {
    try {
        const response = await fetch(`${API_BASE}/api/embedders`);
        if (!response.ok) {
            console.warn('Impossible de charger les embedders:', response.status);
            // Masquer le sélecteur si l'API n'est pas disponible
            const select = document.getElementById('embedderSelect');
            if (select) {
                select.innerHTML = '<option value="">Embedders non disponibles</option>';
            }
            return;
        }
        
        availableEmbedders = await response.json();
        populateEmbedderSelect();
    } catch (error) {
        console.error('Erreur lors du chargement des embedders:', error);
        const select = document.getElementById('embedderSelect');
        if (select) {
            select.innerHTML = '<option value="">Erreur de chargement</option>';
        }
    }
}

async function loadIndexingCount() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/documents/index/count`);
        if (!response.ok) {
            console.warn('Impossible de charger le compte des documents:', response.status);
            return;
        }
        
        const data = await response.json();
        const badge = document.getElementById('m3cCountBadge');
        if (badge && data.pdf_from_m3c_count !== undefined) {
            badge.textContent = `(${data.pdf_from_m3c_count} documents disponibles)`;
        }
    } catch (error) {
        console.error('Erreur lors du chargement du compte:', error);
    }
}

function populateEmbedderSelect() {
    const select = document.getElementById('embedderSelect');
    if (!select) return;
    
    if (availableEmbedders.length === 0) {
        select.innerHTML = '<option value="">Aucun embedder disponible</option>';
        return;
    }
    
    let html = '';
    // Ajouter un embedder par défaut si disponible
    const defaultEmbedder = availableEmbedders.find(e => e.is_default);
    
    availableEmbedders.forEach(embedder => {
        const isDefault = embedder.is_default;
        html += `<option value="${embedder.model_name}" ${isDefault ? 'selected' : ''}>`;
        html += `${embedder.name} (${embedder.type})`;
        if (embedder.model_name) {
            html += ` - ${embedder.model_name}`;
        }
        if (embedder.dimension) {
            html += ` [${embedder.dimension}d]`;
        }
        html += `</option>`;
    });
    
    select.innerHTML = html;
}

function getSelectedEmbedder() {
    const select = document.getElementById('embedderSelect');
    if (select && select.value) {
        return select.value;
    }
    // Retourner le premier embedder par défaut si disponible
    const defaultEmbedder = availableEmbedders.find(e => e.is_default);
    return defaultEmbedder ? defaultEmbedder.name : null;
}

// ============================================================================
// GESTION DES OPTIONS D'INDEXATION
// ============================================================================

function setupRadioButtons() {
    const options = document.querySelectorAll('.indexation-option');
    options.forEach(option => {
        option.addEventListener('click', function() {
            // Sélectionner cette option
            options.forEach(o => o.classList.remove('selected'));
            this.classList.add('selected');
            
            // Afficher/masquer les paramètres de chunk
            const radio = this.querySelector('input[type="radio"]');
            updateChunkParametersVisibility(radio.value);
        });
    });
}

function updateChunkParametersVisibility(type) {
    const paramsDiv = document.getElementById('chunkParameters');
    if (type === 'all-with-text' || type === 'pdf-from-m3c') {
        paramsDiv.style.display = 'block';
    } else {
        paramsDiv.style.display = 'none';
    }
}

// ============================================================================
// INDEXATION
// ============================================================================

async function startIndexation() {
    const indexType = document.querySelector('input[name="indexType"]:checked').value;
    
    if (indexType === 'all-with-text' || indexType === 'pdf-from-m3c') {
        const chunkSize = parseInt(document.getElementById('chunkSize').value);
        const chunkOverlap = parseInt(document.getElementById('chunkOverlap').value);
        
        if (isNaN(chunkSize) || chunkSize < 100 || chunkSize > 10000) {
            showError('La taille des chunks doit être comprise entre 100 et 10000 caractères');
            return;
        }
        
        if (isNaN(chunkOverlap) || chunkOverlap < 0 || chunkOverlap >= chunkSize) {
            showError('Le recouvrement doit être positif et inférieur à la taille des chunks');
            return;
        }
    }
    
    const selectedEmbedder = getSelectedEmbedder();
    
    showLoading(true);
    updateProgress(0, 'Préparation...');
    
    try {
        const requestBody = {
            indexation_type: indexType,
            chunk_size: indexType === 'all-with-text' ? parseInt(document.getElementById('chunkSize').value) : 2700,
            chunk_overlap: indexType === 'all-with-text' ? parseInt(document.getElementById('chunkOverlap').value) : 400
        };
        
        // Ajouter l'embedder si sélectionné
        if (selectedEmbedder) {
            requestBody.embedder_name = selectedEmbedder;
        }
        
        const response = await fetch(`${API_BASE}/api/admin/documents/index`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) throw new Error(`HTTP: ${response.status}`);
        
        const data = await response.json();
        
        // Extraire le job_id de la réponse
        let jobId = null;
        if (data.errors && data.errors.length > 0) {
            // Le job_id est dans le message d'erreur (format: "Job XXX démarré...")
            const match = data.errors[0].match(/Job ([a-f0-9\-]+) démarré/);
            if (match) {
                jobId = match[1];
            }
        }
        // Sinon, vérifier si la réponse contient directement un job_id
        if (!jobId && data.job_id) {
            jobId = data.job_id;
        }
        
        // S'abonner aux événements SSE si on a un job_id
        if (jobId) {
            subscribeToJobEvents(jobId);
            // Ne pas appeler showLoading(false) ici, car le job est en cours
            // La fonction SSE gérera l'affichage de fin
        } else {
            showLoading(false);
        }
        
        displayResults(data);
    } catch (error) {
        showLoading(false);
        console.error('Erreur indexation:', error);
        showError('Erreur lors de l\'indexation: ' + error.message);
    }
}

function displayResults(data) {
    const container = document.getElementById('resultsContainer');
    const card = document.createElement('div');
    
    let className = 'result-card';
    let title = '✅ Indexation terminée';
    
    if (data.errors && data.errors.length > 0) {
        className += ' warning';
        title = '⚠️ Indexation partielle';
    }
    
    if (!data.success) {
        className += ' error';
        title = '❌ Erreur d\'indexation';
    }
    
    card.className = className;
    
    let html = `
        <div class="result-header">
            <div class="result-title">${title}</div>
            <div class="result-time">${new Date(data.timestamp).toLocaleTimeString()}</div>
        </div>
        <div class="result-details">
            <p><strong>Documents traités:</strong> ${data.processed_documents}</p>
            <p><strong>Chunks créés:</strong> ${data.chunks_created}</p>
            <p><strong>Embeddings générés:</strong> ${data.embeddings_generated}</p>
    `;
    
    if (data.chunks_by_document && Object.keys(data.chunks_by_document).length > 0) {
        html += '<p style="margin-top: 10px;"><strong>Détails par document:</strong></p>';
        html += '<div style="margin-left: 10px;">';
        const maxShow = 10;
        let shown = 0;
        for (const [docId, chunkCount] of Object.entries(data.chunks_by_document)) {
            if (shown >= maxShow) {
                html += `<div class="result-item">... et ${Object.keys(data.chunks_by_document).length - maxShow} autres</div>`;
                break;
            }
            html += `<div class="result-item">- ${docId}: ${chunkCount} ${chunkCount === 1 ? 'chunk' : 'chunks'}</div>`;
            shown++;
        }
        html += '</div>';
    }
    
    if (data.errors && data.errors.length > 0) {
        html += '<p style="margin-top: 10px;"><strong>Erreurs:</strong></p>';
        data.errors.forEach(error => {
            html += `<div class="error-item">- ${error}</div>`;
        });
    }
    
    html += '</div>';
    card.innerHTML = html;
    container.innerHTML = '';
    container.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ============================================================================
// UTILITAIRES D'AFFICHAGE
// ============================================================================

function showLoading(show) {
    const loading = document.getElementById('loadingIndicator');
    if (loading) loading.classList.toggle('active', show);
}

function updateProgress(percentage, message) {
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    if (progressFill) progressFill.style.width = `${Math.min(100, Math.max(0, percentage))}%`;
    if (progressText) progressText.textContent = `${Math.round(percentage)}%`;
}

function showError(message) {
    const container = document.getElementById('resultsContainer');
    if (container) {
        container.innerHTML = `
            <div class="result-card error">
                <div class="result-header">
                    <div class="result-title">❌ Erreur</div>
                </div>
                <div class="result-details">
                    <p>${message}</p>
                </div>
            </div>
        `;
    }
    console.error(message);
}

function showSuccess(message) {
    const container = document.getElementById('resultsContainer');
    if (container) {
        container.innerHTML = `
            <div class="result-card success">
                <div class="result-header">
                    <div class="result-title">✅ Succès</div>
                </div>
                <div class="result-details">
                    <p>${message}</p>
                </div>
            </div>
        `;
    }
}

// ==========================================================================
// SERVER-SENT EVENTS (SSE)
// ==========================================================================

function subscribeToJobEvents(jobId) {
    // Fermer la connexion existante
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    currentJobId = jobId;
    const eventUrl = `${API_BASE}/api/admin/documents/index/job/${jobId}/events`;
    eventSource = new EventSource(eventUrl);
    
    eventSource.onopen = function() {
        console.log(`[SSE] Connecté au job ${jobId}`);
    };
    
    eventSource.onerror = function(error) {
        console.error('[SSE] Erreur:', error);
        showLoading(false);
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        showError(`Erreur de connexion SSE pour le job ${jobId}`);
    };
    
    eventSource.addEventListener('job_completed', function(event) {
        const data = JSON.parse(event.data);
        console.log('[SSE] Job terminé:', data);
        
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        
        showLoading(false);
        
        if (data.status === 'completed') {
            showSuccess(`✅ Job ${data.job_id} terminé! ${data.processed_items}/${data.total_items} documents traités`);
        } else {
            showError(`❌ Job ${data.job_id} terminé avec erreurs. ${data.processed_items}/${data.total_items} documents traités`);
        }
    });
}
