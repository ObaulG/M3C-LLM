
// utilise chatFunctions.js

const API_URL_RAG = 'http://localhost:8000/api/query/rag';
const API_URL_DOCUMENTS = 'http://localhost:8000/api/documents';
const API_URL_MESSAGE = 'http://localhost:8000/api/sessions/message/'
const API_URL_SESSION_INIT = 'http://localhost:8000/api/sessions/init';
let currentDocument = null;

let chatContainer, questionInput, sendButton, loading, pdfIframe, documentList, loadingDocuments;
let documentSelector, pdfViewer, backToListButton;

// Fonction pour revenir à la liste
function backToList() {
    documentSelector.style.display = 'block';
    pdfViewer.style.display = 'none';
    pdfIframe.src = ''; // Vider l'iframe
    currentDocument = null;
}

// Fonction pour charger un PDF
function loadPDF(pdfUrl) {
    pdfIframe.src = pdfUrl;
}

// Fonction pour charger la liste des documents
async function loadDocuments() {
    try {
        const response = await fetch(API_URL_DOCUMENTS);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        populateDocumentList(data.documents);

    } catch (error) {
        console.error('Erreur:', error);
        documentList.innerHTML = '<li class="error">Erreur lors du chargement des documents</li>';
    } finally {
        loadingDocuments.style.display = 'none';
    }
}

// Insère les titres de documents dans documentList
function populateDocumentList(documents) {
    documentList.innerHTML = '';

    if (documents.length === 0) {
        documentList.innerHTML = '<li class="no-documents">Aucun document disponible</li>';
        return;
    }

    documents.forEach(doc => {
        const docItem = document.createElement('li');
        docItem.className = 'document-item';
        docItem.innerHTML = `
            <h4>${doc.file_name}</h4>
            <p>Taille: ${formatFileSize(doc.file_size)}</p>
            <p>Créé: ${formatDate(doc.created_at)}</p>
        `;
        docItem.onclick = () => selectDocument(doc.document_id);
        documentList.appendChild(docItem);
    });
}

function addMessageToChat(message, type) {
    const messageInfo = createMessageDiv(message, type);
    chatContainer.appendChild(messageInfo);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
/**
 * Ajoute une question au chat avec son contenu et son numéro de page.
 * @param {Object} sessionStatus - L'état de la session.
 * @param {number} index - L'index de la question à afficher.
 */
function addQuestionToChat(sessionStatus, index) {
    if (!sessionStatus.questions_text ||
        !sessionStatus.pages ||
        sessionStatus.questions_text.length === 0 ||
        sessionStatus.pages.length === 0 ||
        index >= sessionStatus.questions_text.length ||
        index >= sessionStatus.pages.length) {
        console.error("Données de session invalides ou index hors limites.");
        return;
    }

    const questionText = sessionStatus.questions_text[index];
    const pageNumber = sessionStatus.pages[index];

    // Formatage du message avec le numéro de page
    const messageWithPage = `Question (page ${pageNumber}) : ${questionText}`;

    // Ajout du message au chat
    addMessageToChat(messageWithPage, 'bot');
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' octets';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' Ko';
    return (bytes / (1024 * 1024)).toFixed(2) + ' Mo';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// sessionStatus est au format JSON
function saveSessionLocal(sessionStatus){
    localStorage.setItem('sessionId', sessionStatus.session_id);
    localStorage.setItem('documentId', sessionStatus.document_id);
    localStorage.setItem('currentIndex', sessionStatus.current_index);
    localStorage.setItem('completed', sessionStatus.completed);
    localStorage.setItem('createdAt', sessionStatus.created_at);
    localStorage.setItem('timeElapsedSecs', sessionStatus.time_elapsed_secs);
    localStorage.setItem('questionsIds', JSON.stringify(sessionStatus.questions_ids));
    localStorage.setItem('questionsText', JSON.stringify(sessionStatus.questions_text));
    localStorage.setItem('pages', JSON.stringify(sessionStatus.pages));
}

/**
 * Fonction lancée lorsque l'utilisateur sélectionne un document dans la liste,
 * déclarée lorsque les éléments HTML des documents sont créés.
 * Elle requête une route qui déclare le début d'une session de médiation sur le
 * document donné.
 *
 * @param {string}docId l'id du document.
 */
async function selectDocument(docId) {
    // Désélectionner tous les éléments
    const items = document.querySelectorAll('.document-item');
    items.forEach(item => item.classList.remove('active'));

    // Sélectionner l'élément cliqué
    event.target.closest('.document-item').classList.add('active');

    currentDocument = docId;

    // Charger le PDF
    const pdfUrl = `http://localhost:8000/get_pdf?document_id=${encodeURIComponent(docId)}`;
    loadPDF(pdfUrl);

    // Masquer le sélecteur et afficher le visualiseur
    documentSelector.style.display = 'none';
    pdfViewer.style.display = 'block';

    // Ajouter un message dans le chat
    addMessageToChat(`Document sélectionné: ${docId}`, 'info');

    // Ajouter l'exemple
    addMessageToChat("Exemple de question/réponse type :", "info");
    addMessageToChat("Pourquoi la Castagniccia a-t-elle joué un rôle essentiel dans la Révolution de Corse à partir de 1729 ?", "info");
    addMessageToChat("La Castagniccia a joué un rôle essentiel dans la Révolution de Corse à partir de 1729 car elle était la région la plus peuplée de l'île jusqu'au XVIIIe siècle. Cette densité démographique lui a conféré une importance stratégique et politique dans les mouvements révolutionnaires.", "info");
    // Appeler l'API pour initialiser la session de médiation culturelle
    try {
        const response = await fetch(`${API_URL_SESSION_INIT}/${docId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // init retourne l'id de la session
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const sessionStatus = await response.json();
        saveSessionLocal(sessionStatus);
        console.log(sessionStatus);

        // Afficher la première question
        if (sessionStatus.questions_text && sessionStatus.questions_text.length > 0) {
            addQuestionToChat(sessionStatus, 0);
        }

        // Stocker l'ID de la session si nécessaire
        console.log("Session ID:", sessionStatus.session_id);

    } catch (error) {
        console.error("Erreur lors de l'initialisation de la session:", error);
        addMessageToChat("Erreur lors du démarrage de la session de médiation.", 'erreur');
    }
}


async function sendMessage() {
    const message = questionInput.value.trim();

    if (!message) {
        alert('Veuillez entrer un message');
        return;
    }

    /*
    localStorage.setItem('sessionId', sessionStatus.session_id);
    localStorage.setItem('documentId', sessionStatus.document_id);
    localStorage.setItem('currentIndex', sessionStatus.current_index);
    localStorage.setItem('completed', sessionStatus.completed);
    localStorage.setItem('createdAt', sessionStatus.created_at);
    localStorage.setItem('timeElapsedSecs', sessionStatus.time_elapsed_secs);
    localStorage.setItem('questionsIds', JSON.stringify(sessionStatus.questions_ids));
    localStorage.setItem('questionsText', JSON.stringify(sessionStatus.questions_text));
    localStorage.setItem('pages', JSON.stringify(sessionStatus.pages));
     */

    // on détermine le numéro de question en regardant dans le localStorage son numéro

    addMessageToChat(message,'user');

    questionInput.value = '';
    sendButton.disabled = true;
    loading.classList.add('active');

    // request

    let params = {
        session_id: localStorage.getItem('sessionId'),
        user_message: message,
    };
    let response;
    try {
        response = await fetch(API_URL_MESSAGE, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(params)
    })} catch (error) {
        console.error('Erreur:', error);
        addMessageToChat("Erreur lors de la communication avec le serveur.", 'erreur');
        sendButton.disabled = false;
    };

    if (!response.ok) {
        addMessageToChat("Erreur lors de la communication avec le serveur.", 'erreur');
        throw new Error(`HTTP error! status: ${response.status}`);
    }   sendButton.disabled = false;

    const sessionResponse = await response.json();

    /*
    class SessionResponse(BaseModel):
    session_status: SessionStatus
    computed_message_type: str
    # TODO: utiliser une structure pour indiquer les données de consommation
    #       en tokens. Prévoir également un type générique.
    message: str

    # pour faciliter le traitement côté client
    new_question: bool
    is_finished: bool
     */

    //ajouter la réponse dans le chat (data.answer)
    const botResponseDiv = createBotResponse(sessionResponse);
    console.log(botResponseDiv);
    chatContainer.appendChild(botResponseDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    console.log("réponse du bot ajoutée dans le DOM");

    //mettre à jour sessionStatus (potentielles modifications, + stockage des réponses)
    saveSessionLocal(sessionResponse.session_status);

    if (!sessionResponse.is_finished){
        //afficher la nouvelle question
        addQuestionToChat(sessionResponse.session_status, sessionResponse.session_status.current_index);
        sendButton.disabled = false;
    }
    else{
        // indiquer la fin de la session.
        addMessageToChat("Bravo, vous avez terminé cette courte session d'introduction. Avez-vous des retours?", "info");

        const questionnaireUrl = "https://paulpg.limesurvey.net/234267?lang=fr&newtest=Y";
        const response = confirm("Souhaitez-vous accéder au questionnaire maintenant ?");
        if (response) {
          window.open(questionnaireUrl, "_blank");
        }
    }


}


// Fonction pour exporter les questions et réponses en CSV
function exportToCSV() {
    // Récupérer les données depuis localStorage
    const questionsText = JSON.parse(localStorage.getItem('questionsText') || '[]');
    const userMessages = []; // Nous allons collecter les messages de l'utilisateur
    
    // Récupérer tous les messages du chat pour extraire les réponses utilisateur
    const chatMessages = document.querySelectorAll('.message.user');
    chatMessages.forEach(msg => {
        userMessages.push(msg.textContent.trim());
    });
    
    // Créer le contenu CSV
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Question,Réponse\n"; // En-tête
    
    // Ajouter chaque question et sa réponse correspondante
    for (let i = 0; i < questionsText.length && i < userMessages.length; i++) {
        const question = questionsText[i];
        const answer = userMessages[i];
        
        // Échapper les guillemets et les retours à la ligne pour le CSV
        const escapedQuestion = question ? `"${question.replace(/"/g, '""')}"` : '';
        const escapedAnswer = answer ? `"${answer.replace(/"/g, '""')}"` : '';
        
        csvContent += `${escapedQuestion},${escapedAnswer}\n`;
    }
    
    // Créer un lien pour télécharger le fichier
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'questions_reponses.csv');
    document.body.appendChild(link);
    
    // Déclencher le téléchargement
    link.click();
    
    // Supprimer le lien
    document.body.removeChild(link);
}

document.addEventListener('DOMContentLoaded', () => {
    chatContainer = document.getElementById('chatMessages');
    questionInput = document.getElementById('questionInput');
    sendButton = document.getElementById('sendButton');
    loading = document.getElementById('loading');
    pdfIframe = document.getElementById('pdf-iframe');
    documentList = document.getElementById('documentList');
    loadingDocuments = document.getElementById('loadingDocuments');
    documentSelector = document.querySelector('.document-selector');
    pdfViewer = document.querySelector('.pdf-viewer');
    backToListButton = document.getElementById('backToList');

    backToListButton.addEventListener('click', backToList);
    // Charger les documents au démarrage
    loadDocuments();

    // Auto-focus sur l'input au chargement
    questionInput.focus();

    pdfViewer.style.display = 'none';
    
    // Ajouter un bouton d'export CSV dans l'interface
    const exportButton = document.createElement('button');
    exportButton.id = 'exportButton';
    exportButton.textContent = 'Exporter en CSV';
    exportButton.style.margin = '10px';
    exportButton.style.padding = '8px 16px';
    exportButton.addEventListener('click', exportToCSV);
    
    // Ajouter le bouton à côté du bouton d'envoi
    const sendButtonContainer = sendButton.parentNode;
    sendButtonContainer.appendChild(exportButton);
});
