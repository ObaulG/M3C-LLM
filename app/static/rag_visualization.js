/**
 * RAG Embeddings Visualization with t-SNE
 * 
 * This script handles:
 * - Loading embeddings from the API
 * - Computing t-SNE projection via the API
 * - Rendering the visualization with Plotly.js
 * - Interactive features (hover, filtering, etc.)
 */

// ============================================================================
// GLOBAL STATE
// ============================================================================

const API_BASE = window.location.origin + '/api/viz';

let state = {
    documents: [],           // List of available documents
    chunks: [],              // Loaded chunk data with embeddings
    queries: [],             // Query data (if available)
    projectedData: null,     // t-SNE projected coordinates
    selectedDocument: null,  // Currently selected document filter
    plot: null,              // Plotly plot reference
    colors: {},              // Color map for documents
    isComputing: false       // Flag to prevent multiple computations
};

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initialize();
});

function initialize() {
    // Bind event listeners
    bindEvents();
    
    // Check API connection
    checkAPIConnection();
    
    // Load documents list
    loadDocuments();
    
    // Initialize plot
    initializePlot();
    
    updateStatus('Prêt');
}

function bindEvents() {
    // Load embeddings button
    document.getElementById('load-btn').addEventListener('click', loadEmbeddings);
    
    // Compute t-SNE button
    document.getElementById('compute-tsne-btn').addEventListener('click', computeTSNE);
    
    // Reset view button
    document.getElementById('reset-view-btn').addEventListener('click', resetView);
    
    // Document select change
    document.getElementById('document-select').addEventListener('change', (e) => {
        state.selectedDocument = e.target.value;
        updateComputeButton();
    });
    
    // Page filter change
    document.getElementById('page-filter').addEventListener('input', debounce(filterByPage, 300));
    
    // Show query toggle
    document.getElementById('show-query-toggle').addEventListener('change', updatePlot);
    
    // Close info panel
    document.getElementById('close-info-btn').addEventListener('click', () => {
        document.getElementById('info-panel').classList.remove('visible');
    });
    
    // Parameter inputs
    ['perplexity-input', 'learning-rate-input', 'iterations-input', 'limit-input'].forEach(id => {
        document.getElementById(id).addEventListener('input', updateComputeButton);
    });
}

// ============================================================================
// API FUNCTIONS
// ============================================================================

async function checkAPIConnection() {
    try {
        const response = await fetch('/api/health');
        if (response.ok) {
            const data = await response.json();
            document.getElementById('api-status').textContent = 'Connected';
            document.getElementById('api-status').classList.add('connected');
            return true;
        }
    } catch (error) {
        console.error('API connection error:', error);
    }
    
    document.getElementById('api-status').textContent = 'Disconnected';
    document.getElementById('api-status').classList.add('error');
    return false;
}

async function loadDocuments() {
    updateStatus('Chargement des documents...');
    
    try {
        const response = await fetch("/api/documents");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        state.documents = data.documents || [];
        
        // Populate document selector
        const select = document.getElementById('document-select');
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '-- Tous les documents --';
        select.innerHTML = '';
        select.appendChild(option);
        
        state.documents.forEach(doc => {
            const option = document.createElement('option');
            option.value = doc.document_id;
            option.textContent = `${doc.file_name} (${doc.chunk_count} chunks)`;
            select.appendChild(option);
        });
        
        updateStatus(`Prêt - ${state.documents.length} documents disponibles`);
        
    } catch (error) {
        console.error('Error loading documents:', error);
        updateStatus('Erreur: Impossible de charger les documents', true);
    }
}

async function loadEmbeddings() {
    const documentId = document.getElementById('document-select').value;
    const limit = parseInt(document.getElementById('limit-input').value) || 200;
    
    updateStatus(`Chargement des embeddings...`);
    setLoading(true);
    
    try {
        let url = `${API_BASE}/embeddings?limit=${limit}`;
        if (documentId) {
            url += `&document_id=${encodeURIComponent(documentId)}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log(data);
        state.chunks = data.chunks || [];
        state.queries = data.queries || [];
        state.selectedDocument = documentId;
        
        updateStatus(`Chargé: ${state.chunks.length} chunks, ${state.queries.length} requêtes`);
        updateComputeButton();
        
    } catch (error) {
        console.error('Error loading embeddings:', error);
        updateStatus('Erreur: Impossible de charger les embeddings', true);
    } finally {
        setLoading(false);
    }
}

async function computeTSNE() {
    if (state.isComputing || state.chunks.length === 0) {
        return;
    }
    
    state.isComputing = true;
    setLoading(true);
    updateStatus('Calcul de la projection t-SNE...');
    
    try {
        const perplexity = parseFloat(document.getElementById('perplexity-input').value) || 30;
        const learningRate = parseFloat(document.getElementById('learning-rate-input').value) || 200;
        const iterations = parseInt(document.getElementById('iterations-input').value) || 1000;
        
        // Extract embeddings from chunks
        const embeddings = state.chunks.map(c => c.embedding);
        
        const requestBody = {
            embeddings: embeddings,
            n_components: 2,
            perplexity: perplexity,
            learning_rate: learningRate,
            n_iter: iterations,
            random_state: 42
        };
        
        updateStatus(`Envoi des ${embeddings.length} embeddings au serveur...`);
        
        const response = await fetch(`${API_BASE}/visualization/tsne`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        state.projectedData = {
            coordinates: data.projected_embeddings,
            parameters: data.parameters
        };
        
        // Assign coordinates to chunks
        state.chunks.forEach((chunk, index) => {
            chunk.x = data.projected_embeddings[index][0];
            chunk.y = data.projected_embeddings[index][1];
        });
        
        updateStatus(`Projection terminée!`);
        renderPlot();
        
    } catch (error) {
        console.error('Error computing t-SNE:', error);
        updateStatus('Erreur: Impossible de calculer t-SNE', true);
    } finally {
        state.isComputing = false;
        setLoading(false);
    }
}

// ============================================================================
// PLOTLY VISUALIZATION
// ============================================================================

function initializePlot() {
    const container = document.getElementById('plot-container');
    
    const initialData = [{
        x: [],
        y: [],
        mode: 'markers',
        type: 'scatter',
        text: [],
        marker: {
            size: 8,
            opacity: 0.6
        }
    }];
    
    const layout = {
        title: 'Projection t-SNE des Embeddings',
        xaxis: { title: 'Composante 1', zeroline: false },
        yaxis: { title: 'Composante 2', zeroline: false },
        hovermode: 'closest',
        margin: { l: 50, r: 50, t: 50, b: 50 },
        height: 700
    };
    
    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false
    };
    
    Plotly.newPlot(container, initialData, layout, config);
}

function renderPlot() {
    if (!state.projectedData || state.chunks.length === 0) {
        return;
    }
    
    // Generate colors for documents
    generateColors();
    
    // Separate chunks by document
    const chunksByDoc = {};
    state.chunks.forEach(chunk => {
        if (!chunksByDoc[chunk.document_id]) {
            chunksByDoc[chunk.document_id] = [];
        }
        chunksByDoc[chunk.document_id].push(chunk);
    });
    
    // Create traces for each document
    const traces = [];
    let traceIndex = 0;
    
    for (const [docId, chunks] of Object.entries(chunksByDoc)) {
        const docName = state.documents.find(d => d.document_id === docId)?.file_name || docId;
        const color = state.colors[docId] || getColor(traceIndex);
        
        // Filter by page if specified
        const pageFilter = document.getElementById('page-filter').value;
        let filteredChunks = chunks;
        
        if (pageFilter) {
            filteredChunks = chunks.filter(c => matchesPageFilter(c.num_page, pageFilter));
        }
        
        traces.push({
            x: filteredChunks.map(c => c.x),
            y: filteredChunks.map(c => c.y),
            mode: 'markers',
            type: 'scatter',
            name: docName,
            text: filteredChunks.map(c => createTooltip(c)),
            marker: {
                size: 8,
                color: color,
                opacity: 0.7,
                line: {
                    color: 'white',
                    width: 0.5
                }
            },
            hovertemplate: '%{text}<extra></extra>'
        });
        
        traceIndex++;
    }
    
    // Add queries trace if enabled
    const showQueries = document.getElementById('show-query-toggle').checked;
    if (showQueries && state.queries.length > 0) {
        traces.push({
            x: state.queries.map(q => q.x),
            y: state.queries.map(q => q.y),
            mode: 'markers',
            type: 'scatter',
            name: 'Requêtes',
            text: state.queries.map(q => createQueryTooltip(q)),
            marker: {
                size: 12,
                symbol: 'star',
                color: '#ff0000',
                opacity: 0.9,
                line: {
                    color: 'white',
                    width: 1
                }
            },
            hovertemplate: '%{text}<extra></extra>'
        });
    }
    
    const layout = {
        title: `Projection t-SNE des Embeddings (${state.chunks.length} chunks)`,
        xaxis: { title: 'Composante 1', zeroline: false },
        yaxis: { title: 'Composante 2', zeroline: false },
        hovermode: 'closest',
        margin: { l: 50, r: 50, t: 50, b: 50 },
        height: 700,
        showlegend: true,
        legend: {
            x: 1.05,
            y: 1
        }
    };
    
    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false
    };
    
    const container = document.getElementById('plot-container');
    Plotly.react(container, traces, layout, config);
    
    // Add click event for info panel
    container.on('plotly_click', (data) => {
        const point = data.points[0];
        const trace = data.points[0].data;
        const traceIndex = data.points[0].dataIndex;
        
        if (traceIndex < traces.length - (showQueries ? 1 : 0)) {
            // It's a chunk
            const docId = Object.keys(chunksByDoc)[traceIndex];
            const chunkIndex = trace.text.indexOf(point.text);
            const chunk = chunksByDoc[docId][chunkIndex];
            showInfo(chunk);
        } else if (showQueries) {
            // It's a query
            const queryIndex = trace.text.indexOf(point.text);
            const query = state.queries[queryIndex];
            showInfo(query, true);
        }
    });
    
    // Store plot reference
    state.plot = container;
}

function updatePlot() {
    // Simply re-render the plot with current filters
    renderPlot();
}

function resetView() {
    if (state.plot) {
        Plotly.relayout(state.plot, {
            'xaxis.autorange': true,
            'yaxis.autorange': true
        });
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function updateStatus(text, isError = false) {
    const statusEl = document.getElementById('status-text');
    statusEl.textContent = text;
    
    const progressEl = document.getElementById('progress-text');
    if (isError) {
        progressEl.textContent = '';
        statusEl.style.color = '#dc3545';
    } else {
        progressEl.textContent = '';
        statusEl.style.color = '#333';
    }
}

function setLoading(isLoading) {
    const loadBtn = document.getElementById('load-btn');
    const computeBtn = document.getElementById('compute-tsne-btn');
    
    if (isLoading) {
        loadBtn.disabled = true;
        computeBtn.disabled = true;
        loadBtn.textContent = 'Chargement...';
    } else {
        loadBtn.disabled = false;
        computeBtn.disabled = !state.chunks.length;
        loadBtn.textContent = 'Charger les embeddings';
    }
}

function updateComputeButton() {
    const computeBtn = document.getElementById('compute-tsne-btn');
    computeBtn.disabled = state.chunks.length === 0 || state.isComputing;
}

function generateColors() {
    // Generate consistent colors for documents
    const colorPalette = [
        '#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b',
        '#fa709a', '#fee140', '#30cfd0', '#a8edea', '#fed6e3',
        '#c471ed', '#f8b500', '#00d2ff', '#3a7bd5', '#00d2d3',
        '#5f27cd', '#00cec9', '#a29bfe', '#fd79a8', '#e84393'
    ];
    
    state.documents.forEach((doc, index) => {
        state.colors[doc.document_id] = colorPalette[index % colorPalette.length];
    });
}

function getColor(index) {
    const colorPalette = [
        '#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b',
        '#fa709a', '#fee140', '#30cfd0', '#a8edea', '#fed6e3'
    ];
    return colorPalette[index % colorPalette.length];
}

function createTooltip(chunk) {
    const content = chunk.content.substring(0, 200) + (chunk.content.length > 200 ? '...' : '');
    return `
        <b>Document:</b> ${chunk.document_id}<br>
        <b>Page:</b> ${chunk.num_page || 'N/A'}<br>
        <b>Position:</b> ${chunk.position_in_page || 'N/A'}<br>
        <b>Tokens:</b> ${chunk.token_count || 'N/A'}<br>
        <b>Contenu:</b> ${content.replace(/\n/g, '<br>')}
    `;
}

function createQueryTooltip(query) {
    const content = query.text.substring(0, 150) + (query.text.length > 150 ? '...' : '');
    return `
        <b>Requête:</b><br>${content.replace(/\n/g, '<br>')}<br>
        <b>Modèle:</b> ${query.model || 'N/A'}<br>
        <b>Timestamp:</b> ${query.timestamp || 'N/A'}
    `;
}

function showInfo(item, isQuery = false) {
    const panel = document.getElementById('info-panel');
    const content = document.getElementById('info-content');
    
    if (isQuery) {
        content.innerHTML = `
            <h4>Requête</h4>
            <p><strong>Texte:</strong> ${item.text}</p>
            <p><strong>Modèle:</strong> ${item.model || 'N/A'}</p>
            <p><strong>Timestamp:</strong> ${item.timestamp || 'N/A'}</p>
            ${item.metadata ? `<div class="metadata"><strong>Métadonnées:</strong> ${JSON.stringify(item.metadata, null, 2)}</div>` : ''}
        `;
    } else {
        content.innerHTML = `
            <h4>Chunk: ${item.chunk_id}</h4>
            <p><strong>Document:</strong> ${item.document_id}</p>
            <p><strong>Page:</strong> ${item.num_page || 'N/A'}</p>
            <p><strong>Position:</strong> ${item.position_in_page || 'N/A'}</p>
            <p><strong>Tokens:</strong> ${item.token_count || 'N/A'}</p>
            <div class="metadata"><strong>Contenu:</strong><br><pre>${item.content}</pre></div>
            ${item.metadata ? `<div class="metadata"><strong>Métadonnées:</strong> ${JSON.stringify(item.metadata, null, 2)}</div>` : ''}
        `;
    }
    
    panel.classList.add('visible');
}

function matchesPageFilter(page, filter) {
    if (!page || !filter) return true;
    
    // Support comma-separated values and ranges
    const parts = filter.split(',').map(p => p.trim());
    
    for (const part of parts) {
        if (part.includes('-')) {
            const [start, end] = part.split('-').map(n => parseInt(n.trim()));
            if (page >= start && page <= end) return true;
        } else {
            const num = parseInt(part);
            if (page === num) return true;
        }
    }
    
    return false;
}

function filterByPage() {
    updatePlot();
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ============================================================================
// SESSION INTEGRATION (Optional)
// ============================================================================

async function loadSessionInteractions(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/sessions/${sessionId}/interactions`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        // Process session interactions to extract embeddings
        // This would need to be implemented based on your session data structure
        
        return data.interactions || [];
        
    } catch (error) {
        console.error('Error loading session interactions:', error);
        return [];
    }
}

