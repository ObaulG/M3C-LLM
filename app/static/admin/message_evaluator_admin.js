// Configuration de l'API
const API_BASE = window.location.origin || window.location.protocol + '//' + window.location.host;
const SESSIONS_API = API_BASE + '/api/sessions/questions';
const MESSAGE_EVALUATOR_API = API_BASE + '/api/admin/message-evaluator';

// Variables globales
let currentSession = null;
let currentSessionId = null;
let currentDocumentId = null;
let premadeDocuments = {};
let testedAnswersCount = 0;

// Configuration des documents prédéfinis (PREMADE_QUESTIONS_BY_DOCUMENT_ID)
// Ces valeurs sont extraites de question_session.py
const PREMADE_QUESTIONS_BY_DOCUMENT_ID = {
    "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d": [249, 370, 737, 786, 115],
    "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56": [9158, 9235, 9389, 10040],
    116782: [1356, 1410, 1582, 1652, 1667]
};

// Initialisation de la page
document.addEventListener('DOMContentLoaded', () => {
    initializePage();
});

function initializePage() {
    // Remplir le select avec les documents prédéfinis
    populateDocumentSelect();
    
    // Vérifier l'état du CSV
    checkCsvStatus();
}

function populateDocumentSelect() {
    const select = document.getElementById('documentSelect');
    
    // Ajouter les documents depuis PREMADE_QUESTIONS_BY_DOCUMENT_ID
    for (const [docId, questionIds] of Object.entries(PREMADE_QUESTIONS_BY_DOCUMENT_ID)) {
        const option = document.createElement('option');
        option.value = docId;
        option.textContent = `Document ${docId} (${questionIds.length} questions)`;
        select.appendChild(option);
    }
}

function updateSessionInfo() {
    const select = document.getElementById('documentSelect');
    const selectedValue = select.value;
    
    if (selectedValue) {
        currentDocumentId = selectedValue;
        // Effacer le champ session ID
        document.getElementById('sessionIdInput').value = '';
    }
}

async function loadSession() {
    const documentSelect = document.getElementById('documentSelect');
    const sessionIdInput = document.getElementById('sessionIdInput');
    const loadBtn = document.getElementById('loadSessionBtn');
    const loading = document.getElementById('loadingIndicator');
    
    let sessionIdToLoad = sessionIdInput.value.trim();
    
    // Si un document est sélectionné, créer une nouvelle session pour ce document
    if (documentSelect.value && !sessionIdToLoad) {
        currentDocumentId = documentSelect.value;
        
        try {
            loadBtn.disabled = true;
            loading.classList.add('active');
            
            // Créer une nouvelle session pour ce document
            const initResponse = await fetch(`${SESSIONS_API}/init/${currentDocumentId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ premade_session: true })
            });
            
            if (!initResponse.ok) {
                throw new Error(`Erreur: ${initResponse.status} - ${initResponse.statusText}`);
            }
            
            const initData = await initResponse.json();
            sessionIdToLoad = initData.session_id;
            currentSessionId = sessionIdToLoad;
            
            // Attendre un instant pour que la session soit prête
            await new Promise(resolve => setTimeout(resolve, 500));
            
        } catch (error) {
            console.error('Erreur lors de la création de la session:', error);
            alert('❌ Erreur: ' + error.message);
            loadBtn.disabled = false;
            loading.classList.remove('active');
            return;
        }
    } else if (sessionIdToLoad) {
        // Utiliser le session ID fourni
        currentSessionId = sessionIdToLoad;
        currentDocumentId = null;
    } else {
        alert('⚠️ Veuillez sélectionner un document ou entrer un Session ID');
        return;
    }
    
    try {
        // Charger la session
        const response = await fetch(`${SESSIONS_API}/${currentSessionId}`);
        
        if (!response.ok) {
            throw new Error(`Erreur: ${response.status} - ${response.statusText}`);
        }
        
        currentSession = await response.json();
        
        // Mettre à jour l'affichage
        displaySessionInfo();
        displayQuestions();
        
        // Afficher le lien CSV
        showCsvDownload();
        
    } catch (error) {
        console.error('Erreur lors du chargement de la session:', error);
        alert('❌ Erreur: ' + error.message);
    } finally {
        loadBtn.disabled = false;
        loading.classList.remove('active');
    }
}

function displaySessionInfo() {
    const sessionInfo = document.getElementById('sessionInfo');
    
    if (!currentSession) {
        sessionInfo.style.display = 'none';
        return;
    }
    
    sessionInfo.style.display = 'block';
    
    document.getElementById('sessionDocumentId').textContent = currentSession.document_id || 'N/A';
    document.getElementById('sessionIdDisplay').textContent = currentSession.session_id || 'N/A';
    document.getElementById('sessionQuestionCount').textContent = currentSession.questions_ids?.length || 0;
    
    // Mettre à jour les stats
    updateStats();
}

function displayQuestions() {
    const container = document.getElementById('questionsContainer');
    
    if (!currentSession || !currentSession.questions_ids || currentSession.questions_ids.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">Aucune question trouvée dans cette session.</p>';
        return;
    }
    
    let html = '';
    
    for (let i = 0; i < currentSession.questions_ids.length; i++) {
        const questionId = currentSession.questions_ids[i];
        const questionText = currentSession.questions_text[i];
        const page = currentSession.pages[i] || 'N/A';
        
        // Trouver la réponse existante si elle existe
        const existingResponse = currentSession.responses?.find(r => r.question_id === questionId);
        const userAnswer = existingResponse?.user_answer || '';
        const messageType = existingResponse?.message_type || null;
        const evaluationScore = existingResponse?.evaluation?.score || null;
        const evaluationFeedback = existingResponse?.evaluation?.feedback || '';
        
        const questionIndex = i + 1;
        
        html += `
            <div class="question-card" data-question-id="${questionId}">
                <div class="question-header">
                    <span class="question-id">Question #${questionIndex} | ID: ${questionId} | Page: ${page}</span>
                </div>
                <div class="question-text">${escapeHtml(questionText)}</div>
                
                <div class="answer-section">
                    <label for="answer_${questionId}">Réponse à tester:</label>
                    <textarea id="answer_${questionId}" class="answer-textarea" placeholder="Entrez la réponse à évaluer...">${escapeHtml(userAnswer)}</textarea>
                </div>
                
                <div class="action-buttons">
                    <button class="btn" onclick="evaluateAnswer(${questionId}, '${escapeHtmlForAttribute(questionText)}')">
                        🤖 Évaluer avec l'agent
                    </button>
                </div>
                
                <div id="agent_result_${questionId}" class="evaluation-result" style="display: none;">
                    <div class="result-label">✅ Résultat de l'agent message_evaluator_agent:</div>
                    <div class="result-value">
                        <strong>Type:</strong> <span id="agent_type_${questionId}">-</span><br>
                        <strong>Confiance:</strong> <span id="agent_confidence_${questionId}">-</span><br>
                        <strong>Explication:</strong> <span id="agent_explanation_${questionId}">-</span>
                    </div>
                </div>
                
                <div class="manual-eval-section">
                    <div class="result-label">📋 Évaluation manuelle:</div>
                    <div class="radio-group">
                        <div class="radio-option">
                            <input type="radio" id="manual_in_${questionId}" name="manual_eval_${questionId}" value="true" 
                                   ${messageType === 'reponse' ? 'checked' : ''}>
                            <label for="manual_in_${questionId}">✅ Dans le contexte</label>
                        </div>
                        <div class="radio-option">
                            <input type="radio" id="manual_out_${questionId}" name="manual_eval_${questionId}" value="false"
                                   ${messageType === 'hors_sujet' ? 'checked' : ''}>
                            <label for="manual_out_${questionId}">❌ Hors sujet</label>
                        </div>
                        <div class="radio-option">
                            <input type="radio" id="manual_none_${questionId}" name="manual_eval_${questionId}" value=""
                                   checked>
                            <label for="manual_none_${questionId}">Non évalué</label>
                        </div>
                    </div>
                    <button class="btn btn-secondary" onclick="saveManualEvaluation(${questionId}, '${escapeHtmlForAttribute(questionText)}')">
                        💾 Sauvegarder l'évaluation
                    </button>
                </div>
                
                ${messageType ? `
                <div class="session-info-item" style="margin-top: 10px;">
                    <span class="session-info-label">Message type (session):</span>
                    <span class="status-badge ${getStatusBadgeClass(messageType)}">${messageType}</span>
                </div>
                ` : ''}
                
                ${evaluationScore !== null ? `
                <div class="session-info-item">
                    <span class="session-info-label">Score:</span>
                    <span>${evaluationScore}/10</span>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    container.innerHTML = html;
}

async function evaluateAnswer(questionId, questionText) {
    const answerTextarea = document.getElementById(`answer_${questionId}`);
    const userAnswer = answerTextarea.value.trim();
    
    if (!userAnswer) {
        alert('⚠️ Veuillez entrer une réponse à évaluer');
        return;
    }
    
    const resultDiv = document.getElementById(`agent_result_${questionId}`);
    const typeSpan = document.getElementById(`agent_type_${questionId}`);
    const confidenceSpan = document.getElementById(`agent_confidence_${questionId}`);
    const explanationSpan = document.getElementById(`agent_explanation_${questionId}`);
    
    try {
        // Afficher le loading
        resultDiv.style.display = 'block';
        typeSpan.textContent = 'Évaluation en cours...';
        confidenceSpan.textContent = '';
        explanationSpan.textContent = '';
        
        // Appeler l'API pour évaluer la réponse
        const response = await fetch(`${MESSAGE_EVALUATOR_API}/evaluate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                document_id: String(currentSession.document_id || currentDocumentId || 'unknown'),
                question_id: Number(questionId),
                question_text: questionText,
                user_answer: userAnswer,
                manual_evaluation: null  // Pas d'évaluation manuelle pour l'instant
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur: ${response.status} - ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Mettre à jour l'affichage
        typeSpan.textContent = data.agent_message_type;
        confidenceSpan.textContent = (data.agent_confidence * 100).toFixed(2) + '%';
        explanationSpan.textContent = data.agent_explanation;
        
        // Incrémenter le compteur
        testedAnswersCount++;
        updateStats();
        
        // Afficher le lien CSV
        showCsvDownload();
        
    } catch (error) {
        console.error('Erreur lors de l\'évaluation:', error);
        typeSpan.textContent = 'Erreur';
        confidenceSpan.textContent = '';
        explanationSpan.textContent = error.message;
        resultDiv.style.background = '#f8d7da';
        resultDiv.style.borderLeftColor = '#dc3545';
    }
}

async function saveManualEvaluation(questionId, questionText) {
    const answerTextarea = document.getElementById(`answer_${questionId}`);
    const userAnswer = answerTextarea.value.trim();
    
    if (!userAnswer) {
        alert('⚠️ Veuillez entrer une réponse');
        return;
    }
    
    // Récupérer l'évaluation manuelle
    const radioName = `manual_eval_${questionId}`;
    const selectedRadio = document.querySelector(`input[name="${radioName}"]:checked`);
    
    if (!selectedRadio) {
        alert('⚠️ Veuillez sélectionner une évaluation manuelle');
        return;
    }
    
    const manualEvaluation = selectedRadio.value === 'true' ? true : 
                          selectedRadio.value === 'false' ? false : null;
    
    try {
        // Appeler l'API pour sauvegarder l'évaluation manuelle
        const response = await fetch(`${MESSAGE_EVALUATOR_API}/evaluate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                document_id: String(currentSession.document_id || currentDocumentId || 'unknown'),
                question_id: Number(questionId),
                question_text: questionText,
                user_answer: userAnswer,
                manual_evaluation: manualEvaluation
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur: ${response.status} - ${response.statusText}`);
        }
        
        const data = await response.json();
        
        alert('✅ Évaluation manuelle sauvegardée avec succès!');
        
        // Afficher le lien CSV
        showCsvDownload();
        
    } catch (error) {
        console.error('Erreur lors de la sauvegarde:', error);
        alert('❌ Erreur: ' + error.message);
    }
}

async function checkCsvStatus() {
    try {
        const response = await fetch(`${MESSAGE_EVALUATOR_API}/csv-path`);
        
        if (response.ok) {
            const data = await response.json();
            const csvStatus = document.getElementById('csvStatus');
            csvStatus.textContent = data.exists ? '✅ Existe' : '❌ Non créé';
            
            if (data.exists) {
                showCsvDownload();
            }
        }
    } catch (error) {
        console.error('Erreur lors de la vérification du CSV:', error);
    }
}

function showCsvDownload() {
    const csvDownload = document.getElementById('csvDownload');
    const csvFileLink = document.getElementById('csvFileLink');
    
    csvDownload.style.display = 'block';
    csvFileLink.href = '/question_answer/message_evaluator_results.csv';
    csvFileLink.textContent = 'message_evaluator_results.csv';
}

function updateStats() {
    const evaluatedSessions = currentSession ? 1 : 0;
    document.getElementById('evaluatedSessionsCount').textContent = evaluatedSessions;
    document.getElementById('testedAnswersCount').textContent = testedAnswersCount;
}

function getStatusBadgeClass(messageType) {
    switch (messageType) {
        case 'reponse':
            return 'status-in-context';
        case 'hors_sujet':
            return 'status-out-of-context';
        case 'demande_renseignement':
        case 'autre':
            return 'status-not-evaluated';
        default:
            return 'status-not-evaluated';
    }
}

// Fonction pour échapper le HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Fonction pour échapper le HTML pour les attributs
function escapeHtmlForAttribute(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;')
               .replace(/"/g, '&quot;')
               .replace(/'/g, '&#039;');
}
