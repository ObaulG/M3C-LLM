// Administration - Indexation des Documents
// Version simplifiée : indexation de TOUS les documents

const API_BASE = '';

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    setupRadioButtons();
});

// ============================================================================
// GESTION DES STATISTIQUES
// ============================================================================

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/stats`);
        if (!response.ok) throw new Error(`HTTP: ${response.status}`);
        
        const data = await response.json();
        
        // Mettre à jour les stats principales
        document.getElementById('documentsCount').textContent = data.documents_count || 0;
        document.getElementById('chunksCount').textContent = data.chunks_count || 0;
        
        // Total embeddings
        const totalEmbeddings = Object.values(data.embeddings_count || {}).reduce((sum, count) => sum + count, 0);
        document.getElementById('totalEmbeddings').textContent = totalEmbeddings || 0;
        
        // Documents avec extracted_text
        const docsWithText = data.documents_with_extracted_text_count || 0;
        document.getElementById('docsWithExtractedText').textContent = docsWithText;
        document.getElementById('totalDocsCount').textContent = data.documents_count || 0;
        document.getElementById('docsWithTextCount').textContent = docsWithText;
        
        // Liste des embeddings par modèle
        const embeddingsList = document.getElementById('embeddingsList');
        embeddingsList.innerHTML = '';
        
        if (data.embeddings_count && Object.keys(data.embeddings_count).length > 0) {
            for (const [model, count] of Object.entries(data.embeddings_count)) {
                const item = document.createElement('div');
                item.className = 'embedding-item';
                item.innerHTML = `<span>${model}</span><strong>${count}</strong>`;
                embeddingsList.appendChild(item);
            }
        } else {
            embeddingsList.innerHTML = '<div style="font-size: 12px; color: #999;">Aucun embedding trouvé</div>';
        }
    } catch (error) {
        console.error('Erreur chargement stats:', error);
        showError('Impossible de charger les statistiques: ' + error.message);
    }
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
    if (type === 'all-with-text') {
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
    
    if (indexType === 'all-with-text') {
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
    
    showLoading(true);
    updateProgress(0, 'Préparation...');
    
    try {
        const response = await fetch(`${API_BASE}/api/admin/documents/index`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                indexation_type: indexType,
                chunk_size: indexType === 'all-with-text' ? parseInt(document.getElementById('chunkSize').value) : 2700,
                chunk_overlap: indexType === 'all-with-text' ? parseInt(document.getElementById('chunkOverlap').value) : 400
            })
        });
        
        if (!response.ok) throw new Error(`HTTP: ${response.status}`);
        
        const data = await response.json();
        showLoading(false);
        displayResults(data);
        loadStats();
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
