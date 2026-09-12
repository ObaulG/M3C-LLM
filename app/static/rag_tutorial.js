
const layout = {
    title: { text: 'Projection UMAP' },
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

const baseChunkDisplayParams = {
    mode: 'markers',
    type: 'scatter',
    marker: {
        size: 8,
        opacity: 0.7,
        line: {
            color: 'white',
            width: 0.5
        }
    },
}

const baseQueryDisplayParams = {
    mode: 'markers',
    type: 'scatter',
    name: `Requête`,
    marker: {
        size: 12,
        color: 'red',
        symbol: 'star',
        opacity: 1,
        line: {
            color: 'darkred',
            width: 1
        }
    },
}
/**
 * Récupère tous les paramètres de la requête RAG et les retourne sous forme d'objet.
 * @returns {Object} Un objet contenant tous les paramètres configurés.
 */
function getRAGParameters() {
  // Récupérer le prompt utilisateur
  let questionInput = document.getElementById('user-prompt');
  let question = questionInput ? questionInput.value.trim() : '';

  // Récupérer les modèles sélectionnés
  let modelSelect = document.getElementById('model-select');
  let selectedModels = modelSelect
    ? Array.from(modelSelect.selectedOptions).map(option => option.value)
    : [];

  // Récupérer les options RAG
  let useRAG = document.getElementById('useRAG') ? document.getElementById('useRAG').checked : true;
  let useReranking = document.getElementById('useReranking') ? document.getElementById('useReranking').checked : true;
  let numSources = document.getElementById('numSources') ? parseInt(document.getElementById('numSources').value) : 3;

  // Récupérer le document spécifique pour le RAG (si activé)
  let useSingleDocument = document.getElementById('useSingleDocument') ? document.getElementById('useSingleDocument').checked : false;
  let selectedDocumentRAG = document.getElementById('selectedDocumentRAG') ? document.getElementById('selectedDocumentRAG').value : '';
  let rag_monodocument_id = useSingleDocument && selectedDocumentRAG ? parseInt(selectedDocumentRAG) : null;

  // Construire l'objet de paramètres
  let params = {
    question: question,
    models: selectedModels,
    k: numSources,
    use_rag: useRAG,
    use_reranking: useReranking,
    rag_monodocument_id: null,
    session_id: null,
  };
  return params;
}

async function launchRAGRequest(){
    let params = getRAGParameters();
    console.log(params);

    let data;
	try {
		const response = await fetch("http://localhost:8000/api/query/rag/tutorial", {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify(params)
		});

		// Traiter la réponse
		if (!response.ok) {
			throw new Error(`HTTP error! status: ${response.status}`);
		}
		data = await response.json();
        console.log(data);

	} catch (error) {
		console.error('Erreur:', error);
		showError('Erreur lors de la communication avec le serveur. Vérifiez que l\'API est démarrée.');
	}

    // affichage de la réponse en réutilisant  chatFunctions.js
    let answerZone = document.getElementById('ragResponse');
    let botResponseDiv = createBotResponse(data);
    answerZone.append(botResponseDiv);

    // affichage du plot UMAP
    renderPlot(data);
}

// Fonction pour mettre à jour l'affichage des modèles sélectionnés
function updateSelectedModels() {
	const selectedOptions = Array.from(modelSelect.selectedOptions);
	const badgesContainer = selectedModelsDisplay;
	if (selectedOptions.length === 0) {
		badgesContainer.innerHTML = '<span class="selected-model-badge">Aucun modèle sélectionné</span>';
		return;
	}
	badgesContainer.innerHTML = '';
	selectedOptions.forEach(option => {
		const badge = document.createElement('span');
		badge.className = 'selected-model-badge';
		badge.textContent = option.text;
		badgesContainer.appendChild(badge);
	});
}

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
        title: 'Projection UMAP',
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

function renderPlot(ragResponse) {
    const chunks = ragResponse.metadata.tutorial_metadata.best_chunks;
    const colourPalette = [
        '#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b',
        '#fa709a', '#fee140', '#30cfd0', '#a8edea', '#fed6e3',
        '#c471ed', '#f8b500', '#00d2ff', '#3a7bd5', '#00d2d3',
        '#5f27cd', '#00cec9', '#a29bfe', '#fd79a8', '#e84393'
    ];

    // Séparer les chunks par document
    const chunksByDoc = {};
    const coloursByDoc = {};
    let coloursIndex = 0;
    chunks.forEach(chunk => {
        if (!chunksByDoc[chunk.document_id]) {
            chunksByDoc[chunk.document_id] = [];
            coloursByDoc[chunk.document_id] = colourPalette[coloursIndex % colourPalette.length];
            coloursIndex++;
        }
        chunksByDoc[chunk.document_id].push(chunk);
    });

    // Créer une trace par document (au lieu d'une par chunk)
    const traces = [];
    Object.entries(chunksByDoc).forEach(([docId, docChunks]) => {
        const color = coloursByDoc[docId];
        const x = [];
        const y = [];
        const texts = [];
        const chunkIndices = []; // Pour retrouver le chunk cliqué

        docChunks.forEach((chunk, idx) => {
            const chunkProjection = ragResponse.metadata.tutorial_metadata.chunk_projections[chunks.indexOf(chunk)];
            x.push(chunkProjection[0]);
            y.push(chunkProjection[1]);
            texts.push(createTooltip(chunk));
            chunkIndices.push(idx);
        });

        traces.push({
            x: x,
            y: y,
            mode: 'markers',
            type: 'scatter',
            name: docId,
            text: texts,
            customdata: chunkIndices, // Pour retrouver le chunk cliqué
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
    });

    // Ajouter la requête
    const queryProjection = ragResponse.metadata.tutorial_metadata.prompt_projection;
    const queryX = queryProjection[0];
    const queryY = queryProjection[1];
    traces.push({
        x: [queryX],
        y: [queryY],
        mode: 'markers',
        type: 'scatter',
        name: `Requête`,
        text: ragResponse.question || `Requête`,
        marker: {
            size: 12,
            color: 'red',
            symbol: 'star',
            opacity: 1,
            line: {
                color: 'darkred',
                width: 1
            }
        },
        hovertemplate: '%{text}<extra></extra>'
    });

    // Ajouter les lignes des 3 premiers chunks vers la requête
    const firstThreeChunks = chunks.slice(0, 3);
    firstThreeChunks.forEach((chunk, idx) => {
        const chunkProjection = ragResponse.metadata.tutorial_metadata.chunk_projections[chunks.indexOf(chunk)];
        const color = coloursByDoc[chunk.document_id];

        traces.push({
            x: [chunkProjection[0], queryX],
            y: [chunkProjection[1], queryY],
            mode: 'lines',
            type: 'scatter',
            name: `Lien vers requête (Chunk ${idx + 1})`,
            line: {
                color: color,
                width: 1,
                dash: 'dash' // Ligne en pointillés pour distinguer
            },
            showlegend: false, // On cache ces traces de la légende
            hoverinfo: 'skip' // Pas d'infobulle
        });
    });

    // Layout
    const layout = {
        title: { text: 'Projection UMAP' },
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

    // Config
    const config = {
        responsive: true,
        displayModeBar: true,
        displaylogo: false
    };

    // Rendu du graphique
    const container = document.getElementById('plot-container');
    Plotly.react(container, traces, layout, config);

    // Gestion du clic
    container.addEventListener('click', (event) => {
        if (!event.points || event.points.length === 0) return;

        const point = event.points[0];
        const trace = traces[point.curveNumber];
        const traceIndex = point.curveNumber;

        if (traceIndex < traces.length - 1) { // On exclut la requête
            // Récupérer le document_id et le chunk cliqué
            const docId = trace.name;
            const chunkIndexInDoc = point.pointIndex;
            const chunk = chunksByDoc[docId][chunkIndexInDoc];
            if (chunk) showInfo(chunk);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initializePlot();
    chatContainer = document.getElementById('chatContainer');
    questionInput = document.getElementById('questionInput');
    sendButton = document.getElementById('sendButton');
    loading = document.getElementById('loading');
    modelSelect = document.getElementById('model-select');
    selectedModelsDisplay = document.getElementById('selectedModels');
    selectedDocumentRAG = document.getElementById('selectedDocumentRAG');

    updateSelectedModels();
    modelSelect.addEventListener('change', updateSelectedModels);
});