// utilise chatFunctions.js

const API_URL_RAG = 'http://localhost:8000/api/query/rag';
const API_URL_SIMPLE = 'http://localhost:8000/api/query/simple';
const API_URL_COMPARE = 'http://localhost:8000/api/query/compare';
const API_URL_RAG_HISTORY = 'http://localhost:8000/api/query/single-doc-rag';

let chatContainer, questionInput, sendButton, loading, modelSelect, selectedModelsDisplay, selectedDocumentRAG;
let documents = []; // holds the existing documents informations, filled in loadDocumentsId
let sessions = {}; // Stocke les sessions RAG par document_id

// Fonction pour sauvegarder une session dans localStorage
function saveSessionToLocalStorage(documentId, sessionId) {
	localStorage.setItem(`rag_session_${documentId}`, sessionId);
}

// Fonction pour restaurer les sessions depuis localStorage
function restoreSessionsFromLocalStorage() {
	const restoredSessions = {};
	for (let i = 0; i < localStorage.length; i++) {
		const key = localStorage.key(i);
		if (key && key.startsWith('rag_session_')) {
			const documentId = key.substring('rag_session_'.length);
			const sessionId = localStorage.getItem(key);
			restoredSessions[documentId] = sessionId;
		}
	}
	return restoredSessions;
}

// Fonction pour supprimer une session du localStorage
function removeSessionFromLocalStorage(documentId) {
	localStorage.removeItem(`rag_session_${documentId}`);
	delete sessions[documentId];
}

// Fonction pour récupérer une session RAG depuis l'API
async function fetchRAGSession(sessionId) {
	try {
		const response = await fetch(`/api/sessions/rag/${sessionId}`);
		if (!response.ok) {
			throw new Error(`HTTP error! status: ${response.status}`);
		}
		return await response.json();
	} catch (error) {
		console.error("Erreur lors de la récupération de la session:", error);
		return null;
	}
}

// Fonction pour créer une nouvelle session RAG pour un document
async function createRAGSession(documentId) {
	try {
		const response = await fetch(`/api/sessions/rag/init/${documentId}`);
		if (!response.ok) {
			throw new Error(`HTTP error! status: ${response.status}`);
		}

		const data = await response.json();
		console.log(data);
		return data.session_id;
	} catch (error) {
		console.error("Erreur lors de la création de la session:", error);
		return null;
	}
}

// Fonction pour reconstruire les échanges d'une session dans le chat
function rebuildSessionInChat(session) {
	// Conserver le message de bienvenue
	const hasWelcomeMessage = chatContainer.children.length > 0 &&
		chatContainer.children[0].classList.contains('bot') &&
		chatContainer.children[0].textContent.includes('Bonjour');

	// Vider le chat (sauf le message de bienvenue)
	while (chatContainer.children.length > (hasWelcomeMessage ? 1 : 0)) {
		chatContainer.removeChild(chatContainer.lastChild);
	}

	// Reconstruire chaque interaction
	session.interactions.forEach(interaction => {
		// Message utilisateur
		const userMessage = createUserMessage(interaction.question);
		chatContainer.appendChild(userMessage);

		// Message bot - adapter le format attendu par createBotResponse
		const botData = {
			answer: interaction.answer,
			sources: interaction.sources || [],
			total_time: interaction.total_time,
			metadata: {
				model: interaction.model,
				k: interaction.k,
				use_reranking: interaction.use_reranking,
				consumed_energy_Wh: interaction.consumed_energy_Wh,
				document_id: session.document_id,
				...interaction.metadata
			},
			timestamp: interaction.timestamp
		};
		const botMessage = createBotResponse(botData);
		chatContainer.appendChild(botMessage);
	});

	// Faire défiler vers le bas
	chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Fonction pour charger une session et reconstruire le chat
async function loadSessionForDocument(documentId) {
	const sessionId = sessions[documentId] || localStorage.getItem(`rag_session_${documentId}`);
	if (sessionId) {
		console.log("trying to load session for document:");
		const session = await fetchRAGSession(sessionId);
		if (session) {
			sessions[documentId] = sessionId;
			rebuildSessionInChat(session);
			return true;
		} else {
			removeSessionFromLocalStorage(documentId);
		}
	}

	// Si aucune session n'existe, en créer une nouvelle
	const newSessionId = await createRAGSession(documentId);
	if (newSessionId) {
		sessions[documentId] = newSessionId;
		saveSessionToLocalStorage(documentId, newSessionId);
		console.log(`Nouvelle session créée pour document ${documentId}: ${newSessionId}`);
		// Reconstruire avec une session vide (pas d'interactions encore)
		rebuildSessionInChat({ document_id: documentId, interactions: [] });
		return true;
	} else {
		sessions[documentId] = null;
		return false;
	}
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

// Fonction pour afficher/masquer le sélecteur
function toggleDocumentSelector() {
	const checkbox = document.getElementById("useSingleDocument");
	const selectorDiv = document.getElementById("documentSelector");
	selectorDiv.style.display = checkbox.checked ? "block" : "none";
}

// Fonction pour peupler le sélecteur
// fonctionne à partir de documents (disponible globalement)
function populateDocumentSelector() {
	const selector = document.getElementById("selectedDocumentRAG");
	const currentSelection = selector.value; // Sauvegarde la sélection actuelle
	selector.innerHTML = ""; // Vide le sélecteur

	// Ajoute une option par défaut
	const defaultOption = document.createElement("option");
	defaultOption.value = null;
	defaultOption.textContent = "Sélectionnez un document";
	selector.appendChild(defaultOption);

	// Ajoute les documents au sélecteur
	documents.forEach(doc => {
		const option = document.createElement("option");
		option.value = doc.document_id;

		// Vérifier si une session existe pour ce document
		const hasSession = sessions[doc.document_id] || localStorage.getItem(`rag_session_${doc.document_id}`);
		option.textContent = doc.title + (hasSession ? " 💾" : "");
		selector.appendChild(option);
	});

	// Restaurer la sélection précédente si elle existe toujours
	if (currentSelection && documents.some(doc => doc.document_id === currentSelection)) {
		selector.value = currentSelection;
	}
	selector.disabled = false;
}

// Fonction pour charger les documents depuis l'API
async function loadDocumentsId() {
	try {
		const response = await fetch("/api/documents");
		if (!response.ok) throw new Error("Erreur lors du chargement des documents");
		const data = await response.json();
		documents = data.documents;
		console.log(documents);
		populateDocumentSelector();
	} catch (error) {
		console.error("Erreur:", error);
	}
}

async function sendQuestion() {
	const question = questionInput.value.trim();
	if (!question) {
		showError('Veuillez entrer une question');
		return;
	}

	// Vérifier qu'un modèle est sélectionné
	const selectedModels = Array.from(document.getElementById('model-select').selectedOptions).map(option => option.value);
	if (selectedModels.length === 0) {
		showError('Veuillez sélectionner au moins un modèle de langage');
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
	const rag_monodocument_id = parseInt(selectedDocumentRAG.value);
	const params = {
		question: question,
		models: selectedModels,
		k: parseInt(document.getElementById('numSources').value),
		use_rag: document.getElementById("useRAG").checked,
		use_reranking: document.getElementById('useReranking').checked,
		use_ontology_enrichment: false,
		rag_monodocument_id: rag_monodocument_id,
		session_id: rag_monodocument_id ? (sessions[rag_monodocument_id] || localStorage.getItem(`rag_session_${rag_monodocument_id}`)) : null,
	};

	if (params.models.length > 1) {
		await compareQuery(params);
	} else {
		await simpleQuery(params);
	}

	sendButton.disabled = false;
	loading.classList.remove('active');
}

async function simpleQuery(params) {
	try {
		let route_to_fetch = API_URL_SIMPLE;
		if (params.use_rag) {
			route_to_fetch = API_URL_RAG;
			if (params.rag_monodocument_id) {
				route_to_fetch = API_URL_RAG_HISTORY;
			}
		}

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

		// Stocker le session_id si présent dans la réponse (pour RAG monodocument)
		if (data.metadata && data.metadata.session_id && params.rag_monodocument_id) {
			sessions[params.rag_monodocument_id] = data.metadata.session_id;
			saveSessionToLocalStorage(params.rag_monodocument_id, data.metadata.session_id);
			console.log(`Session stockée pour document ${params.rag_monodocument_id}: ${data.metadata.session_id}`);
			// Rafraîchir le sélecteur pour afficher l'indicateur
			populateDocumentSelector();
		}

		// Remarque: data.source contient un Array de RAGSource. Ces RAGSource ne contiennent pas
		// les noms et auteurs, mais on peut les récupérer avec une autre requête
		const botResponseDiv = createBotResponse(data);
		console.log("botResponseDiv créé");
		chatContainer.appendChild(botResponseDiv);
		chatContainer.scrollTop = chatContainer.scrollHeight;
	} catch (error) {
		console.error('Erreur:', error);
		showError('Erreur lors de la communication avec le serveur. Vérifiez que l\'API est démarrée.');
	}
}

async function compareQuery(params) {
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
	loadDocumentsId().catch(error => {
		console.error("Erreur lors du chargement initial des documents:", error);
	});

	chatContainer = document.getElementById('chatContainer');
	questionInput = document.getElementById('questionInput');
	sendButton = document.getElementById('sendButton');
	loading = document.getElementById('loading');
	modelSelect = document.getElementById('model-select');
	selectedModelsDisplay = document.getElementById('selectedModels');
	selectedDocumentRAG = document.getElementById('selectedDocumentRAG');

	// Restaurer les sessions depuis localStorage
	sessions = restoreSessionsFromLocalStorage();
	updateSelectedModels();
	modelSelect.addEventListener('change', updateSelectedModels);

	// Charger la session si un document est déjà sélectionné
	const initialDocument = selectedDocumentRAG.value;
	if (initialDocument) {
		loadSessionForDocument(initialDocument).catch(err => console.error(err));
	}

	// Écouteur pour la sélection d'un document
	selectedDocumentRAG.addEventListener('change', async (event) => {
		const documentId = event.target.value;
		if (documentId) {
			await loadSessionForDocument(documentId);
		}
	});

	// Auto-focus sur l'input au chargement
	questionInput.focus();
});
