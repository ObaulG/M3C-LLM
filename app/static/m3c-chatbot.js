
// utilise chatFunctions.js

const API_URL_RAG = 'http://localhost:8000/api/query/rag';
const API_URL_SIMPLE = 'http://localhost:8000/api/query/simple';
const API_URL_COMPARE = 'http://localhost:8000/api/query/compare';

let chatContainer, questionInput, sendButton, loading, modelSelect, selectedModelsDisplay;

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

async function sendQuestion() {
    const question = questionInput.value.trim();

    if (!question) {
        alert('Veuillez entrer une question');
        return;
    }

    // Ajouter le message de l'utilisateur
    const userMessageDiv = createUserMessage(question);
    chatContainer.appendChild(userMessageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    questionInput.value = '';

    // Désactiver le bouton et afficher le loading
    sendButton.disabled = true;
    loading.classList.add('active');

    // Récupérer les paramètres
    const params = {
        question: question,
        models: Array.from(document.getElementById('model-select').selectedOptions).map(option => option.value),
        k: parseInt(document.getElementById('numSources').value),
        use_rag: document.getElementById("useRAG").checked,
        use_reranking: document.getElementById('useReranking').checked,
        use_ontology_enrichment: document.getElementById('useOntology').checked
    };

    if (params.models.length > 1) {
        await compareQuery(params);
    } else {
        await simpleQuery(params);
    }
    sendButton.disabled = false;
    loading.classList.remove('active');
}

async function simpleQuery(params){
    try {
        let route_to_fetch = params.use_rag ? API_URL_RAG : API_URL_SIMPLE;
        const response = await fetch(route_to_fetch, {
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
    const data = await response.json();
    const botResponseDiv = createBotResponse(data);
    console.log("botResponseDiv créé");
    chatContainer.appendChild(botResponseDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    } catch (error) {
        console.error('Erreur:', error);
        showError('Erreur lors de la communication avec le serveur. Vérifiez que l\'API est démarrée.');
    }
}

async function compareQuery(params){
    try {
        console.log(params.models);

        const response = await fetch(API_URL_COMPARE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params)
            });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        /*
        class QueryCompareResponse(BaseModel):
        responses: List[str, QueryResponse]
        total_time: float = Field(..., description="Temps total de la génération")
        metadata: Dict = Field(..., description="Métadonnées de la requête")
        timestamp: str = Field(..., description="Horodatage de la réponse")
        */
        console.log(data);
        const llmResponse = createLLMResponsesTabs(data.responses, chatContainer);
        chatContainer.appendChild(llmResponse);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    } catch (error) {
        console.error('Erreur:', error);
        showError('Erreur lors de la communication avec le serveur. Vérifiez que l\'API est démarrée.');
    }
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = '❌ ' + message;

    const container = document.querySelector('.container');
    container.insertBefore(errorDiv, chatContainer);

    setTimeout(() => errorDiv.remove(), 5000);
}

document.addEventListener('DOMContentLoaded', () => {
    chatContainer = document.getElementById('chatContainer');
    questionInput = document.getElementById('questionInput');
    sendButton = document.getElementById('sendButton');
    loading = document.getElementById('loading');
    modelSelect = document.getElementById('model-select');
    selectedModelsDisplay = document.getElementById('selectedModels');

    updateSelectedModels();
    modelSelect.addEventListener('change', updateSelectedModels);

    // Auto-focus sur l'input au chargement
    questionInput.focus();
});