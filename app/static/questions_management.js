/**
 * Gestion des Questions/Réponses - JavaScript
 * Ce fichier gère le chargement et l'affichage des questions/réponses par document
 */

// Variables globales
let currentDocumentId = null;
let currentDocumentTitle = null;
let allDocuments = [];
let currentQuestions = [];
let knowledgeItemsByQuestion = {};
// Affichage réduit des cartes de question (ID, page et texte uniquement)
let compactQuestionsView = localStorage.getItem('questionsCompactView') !== '0';

/**
 * Bascule entre l'affichage complet et l'affichage réduit des cartes de question.
 */
function toggleQuestionsView() {
    compactQuestionsView = !compactQuestionsView;
    localStorage.setItem('questionsCompactView', compactQuestionsView ? '1' : '0');
    applyQuestionsView();
}

/**
 * Déplie ou replie les informations détaillées d'une seule carte de question.
 * @param {HTMLElement} btn - Le bouton cliqué, à l'intérieur de la carte
 */
function toggleQuestionDetails(btn) {
    const card = btn.closest('.question-card');
    if (!card) return;
    card.classList.toggle('expanded');
    const expanded = card.classList.contains('expanded');
    btn.textContent = expanded ? 'Masquer les détails' : 'Voir les détails';
    btn.title = expanded ? 'Replier cette question' : 'Afficher toutes les informations de cette question';
}

/**
 * Applique le mode d'affichage courant aux cartes de question.
 */
function applyQuestionsView() {
    const contentElement = document.getElementById('questionsContent');
    if (!contentElement) return;
    contentElement.classList.toggle('compact', compactQuestionsView);
    const viewBtn = document.getElementById('compactViewBtn');
    if (viewBtn) {
        viewBtn.textContent = compactQuestionsView ? 'Affichage complet' : 'Affichage réduit';
        viewBtn.title = compactQuestionsView
            ? "Afficher toutes les informations des questions"
            : "Afficher uniquement l'identifiant, la page et le texte des questions";
    }
}

// Commandes personnalisées prédéfinies pour la génération groupée de réponses
const BULK_PROMPT_COMMANDS = [
    { label: '📝 Réponses détaillées', text: 'Formule des réponses détaillées et argumentées, en appuyant chaque affirmation par des éléments du texte.' },
    { label: '📋 Réponses concises', text: 'Formule des réponses concises et directes, limitées à l\u2019essentiel du texte.' },
    { label: '📚 Réponses pédagogiques', text: 'Formule des réponses à visée pédagogique : reformule avec des mots simples et illustre avec des exemples du texte.' },
    { label: '🔗 Avec citations', text: 'Cite explicitement les passages du texte qui justifient chaque réponse.' },
    { label: '🚫 Exclusions', text: 'N\u2019invente aucune information absente du contexte et évite les réponses par simple oui/non.' }
];

/**
 * Insère une commande prédéfinie dans la zone de commande personnalisée
 * du menu d'actions groupées.
 * @param {number} index - Index de la commande dans BULK_PROMPT_COMMANDS
 */
function insertBulkPromptCommand(index) {
    const textarea = document.getElementById('bulkUserPrompt');
    if (!textarea) return;
    const cmd = BULK_PROMPT_COMMANDS[index];
    if (!cmd) return;
    const current = textarea.value.trim();
    if (current) {
        if (current.includes(cmd.text)) return;
        textarea.value = current + (current.endsWith('.') ? '' : '.') + '\n' + cmd.text;
    } else {
        textarea.value = cmd.text;
    }
    textarea.focus();
}

/**
 * Affiche les chips de commandes prédéfinies dans le menu d'actions groupées.
 */
function renderBulkPromptCommands() {
    const container = document.getElementById('bulkPromptCommands');
    if (!container) return;
    container.innerHTML = BULK_PROMPT_COMMANDS.map((cmd, i) =>
        `<span class="prompt-command-chip" onclick="insertBulkPromptCommand(${i})" title="${escapeHtml(cmd.text)}">${cmd.label}</span>`
    ).join('');
}

/**
 * Initialise la page au chargement
 */
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    if (sessionId) {
        // Mode session : masquer la sidebar et charger les questions de la session
        const sidebar = document.querySelector('.sidebar');
        const header = document.querySelector('.header');
        
        if (sidebar) {
            sidebar.style.display = 'none';
        }
        
        if (header) {
            const title = header.querySelector('h1');
            if (title) {
                title.textContent = '📝 Révision de la session';
            }
            const subtitle = header.querySelector('p');
            if (subtitle) {
                subtitle.textContent = `ID de session: ${sessionId}`;
            }
        }
        
        // Charger les questions de la session
        loadSessionQuestions(sessionId);
    } else {
        // Mode normal : charger les documents
        loadDocuments();
        setupEventListeners();
    }
});

/**
 * Configure les écouteurs d'événements
 */
function setupEventListeners() {
    // Clic sur un document dans la liste
    document.getElementById('documentList').addEventListener('click', function(e) {
        const documentItem = e.target.closest('.document-item');
        if (documentItem) {
            const documentId = documentItem.dataset.documentId;
            selectDocument(documentId);
        }
    });

    // Touche Entrée sur le champ de limite
    document.getElementById('limitFilter').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            applyFilters();
        }
    });
}

/**
 * Charge la liste des documents depuis l'API
 */
async function loadDocuments() {
    const loadingElement = document.getElementById('loadingDocuments');
    const documentListElement = document.getElementById('documentList');

    try {
        loadingElement.classList.add('active');
        documentListElement.innerHTML = '';

        const response = await fetch('/api/documents');
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const data = await response.json();
        allDocuments = data.documents;
        console.log(allDocuments);
        if (allDocuments.length === 0) {
            documentListElement.innerHTML = '<li class="empty-state"><p>Aucun document disponible</p></li>';
            return;
        }

        // Afficher les documents dans la liste
        allDocuments.forEach(doc => {
            const li = document.createElement('li');
            li.className = 'document-item';
            li.dataset.documentId = doc.document_id;
            li.innerHTML = `
                <h4>${doc.title}</h4>
            `;
            li.onclick = () => selectDocument(doc.document_id);
            documentListElement.appendChild(li);
        });

    } catch (error) {
        console.error('Erreur lors du chargement des documents:', error);
        documentListElement.innerHTML = `<li class="empty-state"><p>Erreur: ${error.message}</p></li>`;
    } finally {
        loadingElement.classList.remove('active');
    }
}

/**
 * Charge les questions d'une session utilisateur
 * @param {string} sessionId - L'ID de la session
 */
async function loadSessionQuestions(sessionId) {
    const loadingElement = document.getElementById('loadingQuestions');
    const contentElement = document.getElementById('questionsContent');
    
    try {
        loadingElement.classList.add('active');
        contentElement.innerHTML = '';
        
        const response = await fetch(`/api/sessions/questions/${sessionId}`);
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const sessionData = await response.json();
        
        if (!sessionData || !sessionData.responses) {
            contentElement.innerHTML = `
                <div class="empty-state">
                    <h3>Aucune réponse dans cette session</h3>
                    <p>La session ne contient aucune réponse enregistrée.</p>
                </div>
            `;
            return;
        }
        
        // Convertir les réponses de la session en format compatible avec displayQuestions
        const questions = sessionData.responses.map((response, index) => {
            // Trouver le chunk_id ou la page si disponible
            let chunkId = null;
            let pageInfo = null;
            
            if (sessionData.chunk_ids && sessionData.chunk_ids[index]) {
                chunkId = sessionData.chunk_ids[index];
            }
            if (sessionData.pages && sessionData.pages[index]) {
                pageInfo = sessionData.pages[index];
            }
            
            return {
                question_id: response.question_id,
                content: response.question_text,
                status: 'answered',
                difficulty_level: 3,
                created_by: 'Session utilisateur',
                answers: [{
                    content: response.user_answer,
                    is_correct: response.evaluation ? (response.evaluation.score >= 7) : false,
                    is_user_answer: true
                }],
                chunk_id: chunkId || `session-${pageInfo}`,
                page: pageInfo,
                session_evaluation: response.evaluation
            };
        });
        
        // Afficher les questions avec le message de session
        displayQuestions(questions, questions.length);
        
    } catch (error) {
        console.error('Erreur lors du chargement de la session:', error);
        contentElement.innerHTML = `
            <div class="empty-state">
                <h3>Erreur de chargement</h3>
                <p>Une erreur est survenue: ${error.message}</p>
            </div>
        `;
    } finally {
        loadingElement.classList.remove('active');
    }
}

/**
 * Sélectionne un document et charge ses questions
 * @param {string} documentId - L'ID du document à sélectionner
 */
async function selectDocument(documentId) {
    currentDocumentId = documentId;

    // Mettre à jour l'affichage de la liste des documents
    const documentItems = document.querySelectorAll('.document-item');
    documentItems.forEach(item => {
        item.classList.toggle('active', item.dataset.documentId === documentId);
    });

    // Afficher le nom du document sélectionné
    const selectedDoc = (allDocuments || []).find(doc => doc.document_id === documentId);
    currentDocumentTitle = selectedDoc ? selectedDoc.title : null;

    // Charger les questions pour ce document
    await loadQuestions(documentId);
}

/**
 * Charge les questions pour un document donné
 * @param {string} documentId - L'ID du document
 */
/**
 * Construit l'URL de l'API questions avec les filtres actuels
 * @param {string} documentId - ID du document
 * @returns {string} URL avec paramètres
 */
function buildQuestionsUrl(documentId) {
    const params = new URLSearchParams();
    params.append('include_answers', 'true');

    const statusFilter = document.getElementById('statusFilter').value;
    const difficultyFilter = document.getElementById('difficultyFilter').value;
    const limitFilter = document.getElementById('limitFilter').value;

    if (statusFilter) params.append('status_filter', statusFilter);
    if (difficultyFilter) params.append('difficulty_filter', difficultyFilter);
    if (limitFilter) params.append('nb_limit', limitFilter);

    return `/api/questions/${encodeURIComponent(documentId)}?${params.toString()}`;
}

async function loadQuestions(documentId) {
    const loadingElement = document.getElementById('loadingQuestions');
    const contentElement = document.getElementById('questionsContent');
    const emptyStateElement = document.getElementById('emptyState');

    try {
        loadingElement.classList.add('active');
        contentElement.innerHTML = '';

        const chunkFilter = document.getElementById('chunkFilter')?.value || '';

        const url = buildQuestionsUrl(documentId);

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const data = await response.json();

        // Filtrer par numéro de chunk si spécifié
        let filteredQuestions = data.questions;
        if (chunkFilter) {
            filteredQuestions = data.questions.filter(question => 
                question.chunk_id && question.chunk_id.includes(`-${chunkFilter}`)
            );
        }

        if (filteredQuestions.length === 0) {
            contentElement.innerHTML = `
                <div class="empty-state">
                    <h3>Aucune question trouvée</h3>
                    <p>Aucune question n'a été générée pour ce document avec les filtres actuels.</p>
                </div>
            `;
            return;
        }

        // Afficher les questions
        displayQuestions(filteredQuestions, filteredQuestions.length);

    } catch (error) {
        console.error('Erreur lors du chargement des questions:', error);
        contentElement.innerHTML = `
            <div class="empty-state">
                <h3>Erreur de chargement</h3>
                <p>Une erreur est survenue: ${error.message}</p>
            </div>
        `;
    } finally {
        loadingElement.classList.remove('active');
    }
}

/**
 * Rafraîchit une seule carte de question sans recharger toute la page.
 * Met à jour currentQuestions, remplace uniquement la carte ciblée et
 * conserve la position de défilement ainsi que l'état déplié de la carte.
 * @param {number} questionId - ID de la question à rafraîchir
 * @returns {Promise<HTMLElement|null>} La carte rafraîchie, ou null en cas d'échec
 */
async function refreshQuestionCard(questionId) {
    if (!currentDocumentId) return null;

    const oldCard = document.querySelector(`[data-question-id="${questionId}"]`);
    if (!oldCard) return null;

    const wasExpanded = oldCard.classList.contains('expanded');
    const previousScroll = window.scrollY;

    try {
        const questionsResponse = await fetch(buildQuestionsUrl(currentDocumentId));
        if (!questionsResponse.ok) return null;

        const data = await questionsResponse.json();
        const refreshedQuestion = (data.questions || []).find(
            q => parseInt(q.question_id) === parseInt(questionId)
        );
        if (!refreshedQuestion) return null;

        const updatedIndex = currentQuestions.findIndex(
            q => parseInt(q.question_id) === parseInt(questionId)
        );
        if (updatedIndex !== -1) {
            currentQuestions[updatedIndex] = refreshedQuestion;
        }

        // Remplacer uniquement la carte de la question modifiée
        const newCardHtml = generateQuestionCardHtml(refreshedQuestion, currentQuestions.length);
        oldCard.outerHTML = newCardHtml;
        window.scrollTo(0, previousScroll);

        const newCard = document.querySelector(`[data-question-id="${questionId}"]`);
        if (newCard && wasExpanded) {
            newCard.classList.add('expanded');
            const detailsBtn = newCard.querySelector('.card-details-btn');
            if (detailsBtn) {
                detailsBtn.textContent = 'Masquer les détails';
                detailsBtn.title = 'Replier cette question';
            }
        }
        return newCard;
    } catch (error) {
        console.error('Erreur lors du rafraîchissement de la question:', error);
        return null;
    }
}

/**
 * Génère le HTML pour une seule carte de question
 * @param {Object} question - La question à rendre
 * @param {number} totalCount - Nombre total de questions
 * @returns {string} - HTML de la carte de question
 */
function generateQuestionCardHtml(question, totalCount) {
    // Déterminer la classe du badge en fonction du statut
    let badgeClass = 'badge-generated';
    switch (question.status) {
        case 'validated':
            badgeClass = 'badge-validated';
            break;
        case 'pending':
            badgeClass = 'badge-pending';
            break;
        default:
            badgeClass = 'badge-generated';
    }

    // Créer les étoiles de difficulté
    const stars = getDifficultyStars(question.difficulty_level);

    // Récupérer la réponse LLM (première réponse par défaut)
    const llmAnswer = question.answers.length > 0 ? question.answers[0] : null;
    const llmAnswerContent = llmAnswer ? escapeHtml(llmAnswer.content) : '';

    // Formater les faits de réponse
    const answerFactsHtml = (answer) => {
        if (!answer.facts || answer.facts.length === 0) return '';
        return `
            <div class="answer-facts">
                <div class="answer-facts-title">Faits de réponse (${answer.facts.length})</div>
                <ul class="answer-facts-list">
                    ${answer.facts.map(fact => `
                        <li class="answer-fact-item importance-${escapeHtml(fact.importance || 'essential')}" data-fact-id="${fact.fact_id || ''}">
                            <span class="fact-importance-badge ${fact.importance === 'optional' ? 'badge-optional' : 'badge-essential'}" ${fact.fact_id ? `onclick="toggleFactImportance(${fact.fact_id}, this)" title="Cliquer pour basculer entre Essentiel et Facultatif"` : ''}>
                                ${fact.importance === 'optional' ? 'Facultatif' : 'Essentiel'}
                            </span>
                            <span class="answer-fact-content">${escapeHtml(fact.content)}</span>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    };

    // Formater les réponses
    const answersHtml = question.answers.length > 0 ? `
        <div class="answers-section">
            <div class="answers-title">Réponses (${question.answers.length})</div>
            ${question.answers.map((answer, index) => {
                const answerId = answer.answer_id || answer.id || '';
                return `
                <div class="answer-item" data-answer-index="${index}" data-answer-id="${answerId}">
                    <strong>Réponse ${index + 1}:</strong> ${escapeHtml(answer.content)}
                    ${answer.is_correct ? '<span style="color: #28a745; margin-left: 10px;">✓ Correcte</span>' : ''}
                    ${index === 0 ? '<span style="color: #007bff; margin-left: 10px;">[LLM]</span>' : ''}
                    ${answerId ? `<button class="btn btn-set-reference ${answer.is_correct ? 'is-reference' : ''}" onclick="setReferenceAnswer(${question.question_id}, ${answerId}, this)" title="Déclarer cette réponse comme réponse de référence">${answer.is_correct ? '★ Référence' : '☆ Référence'}</button>` : ''}
                    ${answerId ? `<button class="btn btn-generate-facts" onclick="generateAnswerFacts(${answerId}, this)" title="Générer les faits de réponse via l\'agent d\'extraction">✨ Faits</button>` : ''}
                    <div class="answer-facts-container">${answerFactsHtml(answer)}</div>
                    <div class="generation-status" id="facts-status-${answerId}" style="display: none;"></div>
                </div>
            `;}).join('')}
        </div>
    ` : '';

    // Récupérer la réponse de référence
    let hasReferenceAnswer = false;
    if (question.answers && question.answers.length > 0) {
        let referenceAnswer = null;
        let referenceAnswerObj = null;
        for (let i = 0; i < question.answers.length; i++) {
            if (question.answers[i].is_correct) {
                referenceAnswer = question.answers[i].content;
                referenceAnswerObj = question.answers[i];
                break;
            }
        }
        if (!referenceAnswer && question.answers.length > 0) {
            referenceAnswer = question.answers[0].content;
            referenceAnswerObj = question.answers[0];
        }
        if (referenceAnswer) {
            hasReferenceAnswer = true;
        }
    } else if (referenceAnswers[question.question_id]) {
        hasReferenceAnswer = true;
    }

    // Section d'évaluation
    const evaluationSection = `
        <div class="evaluation-section" data-question-id="${question.question_id}" data-has-reference="${hasReferenceAnswer}">
            <h4>📊 Évaluation de réponse</h4>
            
            <input type="hidden" id="eval-source-${question.question_id}" value="llm">

            <div class="evaluation-mode-controls">
                <span class="evaluation-mode-label">Base d'évaluation :</span>
                <label class="evaluation-mode-option">
                    <input type="radio" name="eval-mode-${question.question_id}" value="references" checked>
                    Réponses de référence
                </label>
                <label class="evaluation-mode-option">
                    <input type="radio" name="eval-mode-${question.question_id}" value="facts">
                    Faits
                </label>
                <label class="evaluation-mode-option">
                    <input type="radio" name="eval-mode-${question.question_id}" value="both">
                    Les deux (comparaison)
                </label>
            </div>

            <textarea 
                id="answer-to-evaluate-${question.question_id}" 
                class="evaluation-textarea" 
                placeholder="Réponse à évaluer..."
                rows="3"
                data-llm-answer="${llmAnswerContent}"
            >${llmAnswerContent}</textarea>
            <div class="evaluation-controls">
                <button class="btn btn-evaluate" onclick="evaluateAnswer(${question.question_id})">
                    Évaluer avec l'agent
                </button>
                <button class="btn btn-save" onclick="saveEvaluation(${question.question_id})">
                    Sauvegarder l'évaluation
                </button>
                    <input type="radio" id="refAnswer-${question.question_id}" name="answer-${question.question_id}" value="refAnswer" />
                <label for="refAnswer-${question.question_id}">Réponse de référence</label>
                <input type="radio" id="allAnswers-${question.question_id}" name="answer-${question.question_id}" value="allAnswers" />
                <label for="allAnswers-${question.question_id}">Toutes les réponses</label>
            </div>
            
            <div class="evaluation-result" id="eval-result-${question.question_id}" style="display: none;">
                <p><strong>Score:</strong> <span id="score-${question.question_id}" class="score-display"></span>/10</p>
                <p><strong>Feedback:</strong> <span id="feedback-${question.question_id}"></span></p>
            </div>
            <div class="evaluation-comparison" id="eval-comparison-${question.question_id}" style="display: none;">
                <h5>Comparaison des évaluations</h5>
                <div class="comparison-grid">
                    <div class="comparison-column comparison-references">
                        <h6>Par réponses de référence</h6>
                        <p><strong>Score:</strong> <span id="score-references-${question.question_id}" class="score-display"></span>/10</p>
                        <p><strong>Feedback:</strong> <span id="feedback-references-${question.question_id}"></span></p>
                    </div>
                    <div class="comparison-column comparison-facts">
                        <h6>Par faits</h6>
                        <p><strong>Score:</strong> <span id="score-facts-${question.question_id}" class="score-display"></span>/10</p>
                        <p><strong>Feedback:</strong> <span id="feedback-facts-${question.question_id}"></span></p>
                    </div>
                </div>
                <p class="comparison-summary" id="comparison-summary-${question.question_id}"></p>
            </div>
            <div class="manual-evaluation">
                <label>Note manuelle: 
                    <input type="number" id="manual-score-${question.question_id}" min="1" max="10" placeholder="1-10">
                </label>
                <label>Commentaire: 
                    <textarea id="manual-feedback-${question.question_id}" placeholder="Commentaire manuel..."></textarea>
                </label>
            </div>
            <div class="evaluation-status" id="eval-status-${question.question_id}"></div>
        </div>
    `;

    // Générer le HTML de la carte
    return `
        <div class="question-card" data-question-id="${question.question_id}" data-chunk-id="${question.chunk_id || ''}">
            <div class="question-header">
                <div class="question-content">
                    ${marked.parse(question.content)}
                </div>
                <div class="question-meta-row">
                    <div class="question-meta">
                        <span class="badge ${badgeClass}">${question.status}</span>
                        <span class="difficulty">
                            <span class="difficulty-stars">${stars}</span>
                            <span>Niveau ${question.difficulty_level}</span>
                        </span>
                        ${question.created_by ? `<span style="font-size: 12px; color: #999;">Créé par: ${question.created_by}</span>` : ''}
                    </div>
                    <div class="question-info">
                        <span class="info-item info-id" title="Identifiant de la question">
                            <strong>ID:</strong> ${question.question_id}
                        </span>
                        ${question.chunk_id ? `<span class="info-item" title="Identifiant du chunk">
                            <strong>Chunk:</strong> ${question.chunk_id}
                        </span>` : ''}
                        ${question.page ? `<span class="info-item info-page" title="Page du document">
                            <strong>Page:</strong> ${question.page}
                        </span>` : ''}
                        ${question.page_number ? `<span class="info-item info-page" title="Page du document">
                            <strong>Page:</strong> ${question.page_number}
                        </span>` : ''}
                        ${question.num_page ? `<span class="info-item info-page" title="Page du document">
                            <strong>Page:</strong> ${question.num_page}
                        </span>` : ''}
                        <button class="btn btn-secondary card-details-btn" title="Afficher toutes les informations de cette question" onclick="toggleQuestionDetails(this)">Voir les détails</button>
                    </div>
                </div>
            </div>
            
            ${answersHtml}
            
            <!-- Boutons d'édition -->
            <div class="edit-actions">
                <button class="btn btn-edit-question" onclick="enableQuestionEditing(${question.question_id})">
                    ⚙️ Modifier
                </button>
                <button class="btn btn-knowledge-items" onclick="getKnowledgeItemsForQuestion(${question.question_id})">
                    🧠 Éléments de connaissance
                </button>
                <button class="btn btn-delete-question-answers" onclick="deleteAllAnswersForQuestion(${question.question_id}, this)" title="Supprimer toutes les réponses de cette question et leurs faits associés">
                    🗑 Supprimer toutes les réponses
                </button>
                <button class="btn btn-save-changes" onclick="saveQuestionChanges(${question.question_id})" style="display: none;">
                    ✓ Sauvegarder les modifications
                </button>
                <button class="btn btn-secondary btn-cancel-edit" onclick="cancelQuestionEditing(${question.question_id})" style="display: none;">
                    × Annuler
                </button>
            </div>
            
            <!-- Section des éléments de connaissance associés -->
            <div class="knowledge-items-section" id="knowledge-items-${question.question_id}" style="display: none;">
                <h4>🧠 Éléments de connaissance associés</h4>
                <div class="knowledge-items-container" id="knowledge-items-container-${question.question_id}">
                    <p style="font-size: 13px; color: #666;">Cliquez sur le bouton pour afficher les éléments de connaissance de cette question.</p>
                </div>
                <div class="evaluation-status" id="knowledge-items-status-${question.question_id}"></div>
            </div>
            
            ${evaluationSection}
            
            <!-- Section de méta-évaluation (critique de l'évaluation IA) -->
            <div class="meta-evaluation-section" id="meta-eval-${question.question_id}" style="display: none;">
                <h4>🔍 Critiquer l'évaluation IA</h4>
                <div style="margin-bottom: 10px; padding: 10px; background: white; border-radius: 5px;">
                    <p><strong>Note IA:</strong> <span id="meta-ai-score-${question.question_id}"></span>/10</p>
                    <p><strong>Commentaire IA:</strong> <span id="meta-ai-feedback-${question.question_id}"></span></p>
                </div>
                <div class="meta-evaluation-controls">
                    <div class="meta-evaluation-input">
                        <label>Note sur l'évaluation IA (1-10): 
                            <input type="number" id="meta-rating-${question.question_id}" min="1" max="10" placeholder="1-10">
                        </label>
                    </div>
                    <div class="meta-evaluation-input">
                        <label>Commentaire sur l'évaluation IA:
                            <textarea id="meta-comment-${question.question_id}" placeholder="Votre avis sur la qualité de l'évaluation IA..."></textarea>
                        </label>
                    </div>
                </div>
                <div style="margin-top: 15px;">
                    <button class="btn btn-meta-save" onclick="saveMetaEvaluation(${question.question_id})">
                        Sauvegarder la critique
                    </button>
                </div>
                <div class="evaluation-status" id="meta-eval-status-${question.question_id}"></div>
            </div>
        </div>
    `;
}

/**
 * Affiche les questions dans le DOM
 * @param {Array} questions - Liste des questions à afficher
 * @param {number} count - Nombre total de questions
 */
function displayQuestions(questions, count) {
    const contentElement = document.getElementById('questionsContent');
    
    let headerHtml = `
        <div class="questions-header">
            <h2>${currentDocumentTitle ? escapeHtml(currentDocumentTitle) : 'Questions pour ce document'}</h2>
            <div class="questions-header-right">
                <span class="questions-count">${count} question(s) trouvée(s)</span>
                <button class="btn btn-secondary" id="compactViewBtn" onclick="toggleQuestionsView()"></button>
            </div>
        </div>
        <div class="bulk-actions">
            <button class="btn" id="bulkMenuBtn" onclick="toggleBulkMenu()">⚙️ Actions groupées ▾</button>
            <div class="bulk-menu" id="bulkMenu" style="display: none;">
                <div class="bulk-menu-title">Générer des réponses pour toutes les questions</div>
                <div class="bulk-menu-field">
                    <label for="bulkNumAnswers">Réponses par question</label>
                    <input type="number" id="bulkNumAnswers" value="1" min="1" max="10">
                </div>
                <div class="bulk-menu-field">
                    <label for="bulkModel">Modèle de génération</label>
                    <select id="bulkModel"><option value="">Modèle par défaut (filtre « génération »)</option></select>
                </div>
                <div class="bulk-menu-field">
                    <label for="bulkUserPrompt">Commande personnalisée (optionnel)</label>
                    <div class="bulk-prompt-commands" id="bulkPromptCommands"></div>
                    <textarea id="bulkUserPrompt" rows="3" placeholder="Ex. : Formule des réponses détaillées avec des exemples tirés du texte..."></textarea>
                    <div class="bulk-menu-description">Ces instructions seront intégrées au prompt de l'agent pour chaque génération de réponse.</div>
                </div>
                <div class="bulk-menu-field">
                    <label class="bulk-checkbox">
                        <input type="checkbox" id="bulkGenerateFacts" checked>
                        Générer aussi les faits des réponses
                    </label>
                </div>
                <button class="btn" onclick="bulkGenerateAnswers()">✨ Générer les réponses</button>
                <div class="bulk-menu-progress" id="bulkProgress" style="display: none;"></div>
            </div>
        </div>
    `;

    let questionsHtml = questions.map(question => generateQuestionCardHtml(question, count)).join('');

    currentQuestions = questions;
    contentElement.innerHTML = headerHtml + questionsHtml;

    // Charger les modèles dans le sélecteur du menu d'actions groupées
    const bulkModelSelect = document.getElementById('bulkModel');
    if (bulkModelSelect && typeof loadModelsIntoSelect === 'function') {
        loadModelsIntoSelect(bulkModelSelect, { prefixProvider: true, keepFirst: true });
    }

    // Afficher les chips de commandes personnalisées prédéfinies
    renderBulkPromptCommands();

    // Appliquer le mode d'affichage courant (complet / réduit)
    applyQuestionsView();
}

/**
 * Applique les filtres sélectionnés
 */
function applyFilters() {
    if (currentDocumentId) {
        loadQuestions(currentDocumentId);
    }
}

/**
 * Réinitialise tous les filtres
 */
function resetFilters() {
    document.getElementById('statusFilter').value = '';
    document.getElementById('difficultyFilter').value = '';
    document.getElementById('limitFilter').value = '';
    document.getElementById('chunkFilter').value = '';
    document.getElementById('modelFilter').value = '';
    const generationModelFilter = document.getElementById('generationModelFilter');
    if (generationModelFilter) generationModelFilter.value = '';
    
    if (currentDocumentId) {
        loadQuestions(currentDocumentId);
    }
}

/**
 * Retourne les étoiles de difficulté en fonction du niveau
 * @param {number} level - Niveau de difficulté (1-5)
 * @returns {string} - HTML des étoiles
 */
function getDifficultyStars(level) {
    const fullStar = '★';
    const emptyStar = '☆';
    
    if (level === null || level === undefined) {
        return fullStar.repeat(3);
    }
    
    // Niveau 1-5, on affiche 1-5 étoiles
    return fullStar.repeat(level) + emptyStar.repeat(5 - level);
}

/**
 * Formate la taille d'un fichier en octets en une chaîne lisible
 * @param {number} bytes - Taille en octets
 * @returns {string} - Taille formatée
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 octets';
    
    const k = 1024;
    const sizes = ['octets', 'Ko', 'Mo', 'Go'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Déclare une réponse comme réponse de référence pour une question
 * @param {number} questionId - ID de la question
 * @param {number} answerId - ID de la réponse à déclarer comme référence
 * @param {HTMLElement} button - Bouton cliqué
 */
async function setReferenceAnswer(questionId, answerId, button) {
    if (!button || button.disabled) return;
    button.disabled = true;
    const originalButtonText = button.innerHTML;
    button.innerHTML = '...';

    try {
        const response = await fetch(`/api/questions/${questionId}/set-reference-answer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ answer_id: answerId })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Erreur HTTP: ${response.status}`);
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.message || 'Échec de la déclaration de la référence');
        }

        // Rafraîchir l'affichage de la question sans recharger toute la page
        await refreshQuestionCard(questionId);
    } catch (error) {
        console.error('Erreur lors de la déclaration de la réponse de référence:', error);
        alert('Une erreur est survenue: ' + error.message);
        if (button) {
            button.innerHTML = originalButtonText;
            button.disabled = false;
        }
    }
}

/**
 * Échappe les caractères HTML pour éviter les injections XSS
 * @param {string} text - Texte à échapper
 * @returns {string} - Texte échappé
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Récupère la réponse de référence pour une question donnée
 * @param {number} questionId - ID de la question
 * @returns {string|null} - Réponse de référence ou null
 */
function getReferenceAnswerForQuestion(questionId) {
    if (referenceAnswers[questionId]) {
        return referenceAnswers[questionId].response_answer;
    }
    return null;
}

/**
 * Met à jour la liste des documents avec un filtre
 * @param {string} filter - Terme de filtrage
 */
function filterDocuments(filter) {
    const documentItems = document.querySelectorAll('.document-item');
    const lowerFilter = filter.toLowerCase();

    documentItems.forEach(item => {
        const fileName = item.querySelector('h4').textContent.toLowerCase();
        const shouldShow = fileName.includes(lowerFilter);
        item.style.display = shouldShow ? 'block' : 'none';
    });
}

/**
 * Exporte les questions actuelles au format JSON
 */
async function exportQuestions() {
    if (!currentDocumentId) {
        alert('Veuillez sélectionner un document d\'abord');
        return;
    }

    try {
        const params = new URLSearchParams();
        params.append('include_answers', 'true');
        
        const statusFilter = document.getElementById('statusFilter').value;
        const difficultyFilter = document.getElementById('difficultyFilter').value;
        const limitFilter = document.getElementById('limitFilter').value;

        if (statusFilter) params.append('status_filter', statusFilter);
        if (difficultyFilter) params.append('difficulty_filter', difficultyFilter);
        if (limitFilter) params.append('nb_limit', limitFilter);

        const url = `/api/questions/${encodeURIComponent(currentDocumentId)}?${params.toString()}`;
        const response = await fetch(url);
        const data = await response.json();

        // Créer un blob et le télécharger
        const jsonStr = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const urlBlob = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = urlBlob;
        a.download = `questions_${currentDocumentId}_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(urlBlob);

    } catch (error) {
        console.error('Erreur lors de l\'export:', error);
        alert('Une erreur est survenue lors de l\'export');
    }
}

/**
 * Sauvegarde un feedback humain sur une évaluation IA
 * @param {number} questionId - ID de la question
 */
async function saveMetaEvaluation(questionId) {
    const ratingInput = document.getElementById(`meta-rating-${questionId}`);
    const commentInput = document.getElementById(`meta-comment-${questionId}`);
    const aiScoreElement = document.getElementById(`score-${questionId}`);
    const aiFeedbackElement = document.getElementById(`feedback-${questionId}`);
    const answerTextarea = document.getElementById(`answer-to-evaluate-${questionId}`);
    const statusElement = document.getElementById(`meta-eval-status-${questionId}`);
    const saveButton = document.querySelector(`[onclick*="saveMetaEvaluation(${questionId}"]`);
    
    if (!ratingInput || !aiScoreElement || !aiFeedbackElement) {
        alert('Données d\'évaluation IA manquantes');
        return;
    }
    
    const humanRating = parseInt(ratingInput.value);
    const humanComment = commentInput ? commentInput.value.trim() : '';
    const aiScore = parseInt(aiScoreElement.textContent) || 0;
    const aiFeedback = aiFeedbackElement.textContent || '';
    const userAnswer = answerTextarea ? answerTextarea.value.trim() : '';
    
    if (!humanRating || humanRating < 1 || humanRating > 10) {
        alert('Veuillez entrer une note valide entre 1 et 10');
        return;
    }
    
    const originalButtonText = saveButton ? saveButton.innerHTML : 'Sauvegarder la critique';
    if (saveButton) {
        saveButton.innerHTML = 'Sauvegarde en cours...';
        saveButton.disabled = true;
    }
    
    // Récupérer les infos de la question depuis le DOM
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    let questionContent = '';
    let chunkId = null;
    
    if (questionCard) {
        const qContent = questionCard.querySelector('.question-content');
        if (qContent) {
            questionContent = qContent.textContent.replace('Q:', '').trim();
        }
        chunkId = questionCard.dataset.chunkId || null;
    }
    
    try {
        const response = await fetch('/api/evaluation-feedback/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question_id: questionId,
                chunk_id: chunkId,
                question_content: questionContent,
                user_answer: userAnswer,
                ai_score: aiScore,
                ai_feedback: aiFeedback,
                human_rating: humanRating,
                human_comment: humanComment
            })
        });
        
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('Feedback sur évaluation IA sauvegardé:', result);
        
        if (statusElement) {
            statusElement.innerHTML = '<span class="success-message">Critique sauvegardée avec succès !</span>';
        }
        
        // Réinitialiser le formulaire après sauvegarde
        if (commentInput) {
            commentInput.value = '';
        }
        ratingInput.value = '';
        
    } catch (error) {
        console.error('Erreur lors de la sauvegarde du feedback:', error);
        if (statusElement) {
            statusElement.innerHTML = `<span style="color: #dc3545;">Erreur: ${error.message}</span>`;
        }
        alert('Une erreur est survenue: ' + error.message);
    } finally {
        if (saveButton) {
            saveButton.innerHTML = originalButtonText;
            saveButton.disabled = false;
        }
    }
}

/**
 * Retourne le mode d'évaluation choisi pour une question
 * @param {number} questionId - ID de la question
 * @returns {string} 'references', 'facts' ou 'both'
 */
function getEvaluationMode(questionId) {
    const checkedRadio = document.querySelector(`input[name="eval-mode-${questionId}"]:checked`);
    return checkedRadio ? checkedRadio.value : 'references';
}

/**
 * Retourne la liste des réponses de référence sélectionnées pour une question
 * @param {number} questionId - ID de la question
 * @param {HTMLElement} questionCard - Carte de la question
 * @returns {string[]}
 */
function getReferenceAnswerList(questionId, questionCard) {
    const answerType = Array.from(document.querySelectorAll('input[name="answer"]'))
        .find(radio => radio.checked)?.id;
    let answerList = [];
    let answerDivArray = questionCard.querySelectorAll('.answer-item');
    if (answerType == "refAnswer"){
        const hasReference = document.querySelector(`[data-question-id="${questionId}"]`)?.dataset.hasReference === 'true';

        if (hasReference && referenceAnswers[questionId]) {
            answerList.push(referenceAnswers[questionId].response_answer);
        } else if (answerDivArray.length > 0) {
            answerList.push(answerDivArray[0].childNodes[1].textContent.trim());
        }
    } else {
        answerDivArray.forEach((answerDiv) => {
            const responseText = answerDiv.childNodes[1].textContent.trim();
            answerList.push(responseText);
        });
    }
    return answerList;
}

/**
 * Retourne la liste des faits de réponse d'une question
 * @param {HTMLElement} questionCard - Carte de la question
 * @returns {string[]}
 */
function getFactsList(questionCard) {
    if (!questionCard) return [];
    const factItems = questionCard.querySelectorAll('.answer-fact-item .answer-fact-content');
    if (factItems.length > 0) {
        return Array.from(factItems).map(item => item.textContent.trim());
    }
    const legacyFactItems = questionCard.querySelectorAll('.answer-fact-item');
    return Array.from(legacyFactItems).map(item => item.textContent.trim());
}

/**
 * Lance une évaluation via l'API
 * @param {string} questionText - Contenu de la question
 * @param {string[]} expectedAnswers - Réponses attendues
 * @param {string} userAnswer - Réponse de l'utilisateur
 * @param {string} model - Modèle sélectionné
 * @returns {Promise<Object>}
 */
async function runEvaluation(questionText, expectedAnswers, userAnswer, model) {
    const response = await fetch('/api/evaluate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question: questionText,
            expected_answers: expectedAnswers,
            user_answer: userAnswer,
            model: model
        })
    });

    if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
    }

    return await response.json();
}

/**
 * Affiche ou masque le bloc de comparaison des évaluations (références vs faits)
 * @param {number} questionId - ID de la question
 * @param {Object|null} comparison - { references: {score, feedback}, facts: {score, feedback} } ou null
 */
function displayComparison(questionId, comparison) {
    const comparisonDiv = document.getElementById(`eval-comparison-${questionId}`);
    if (!comparisonDiv) return;

    if (!comparison) {
        comparisonDiv.style.display = 'none';
        return;
    }

    const scoreReferences = document.getElementById(`score-references-${questionId}`);
    const feedbackReferences = document.getElementById(`feedback-references-${questionId}`);
    const scoreFacts = document.getElementById(`score-facts-${questionId}`);
    const feedbackFacts = document.getElementById(`feedback-facts-${questionId}`);
    const summary = document.getElementById(`comparison-summary-${questionId}`);

    if (scoreReferences) scoreReferences.textContent = comparison.references.score;
    if (feedbackReferences) feedbackReferences.textContent = comparison.references.feedback;
    if (scoreFacts) scoreFacts.textContent = comparison.facts.score;
    if (feedbackFacts) feedbackFacts.textContent = comparison.facts.feedback;

    if (summary) {
        const diff = comparison.references.score - comparison.facts.score;
        if (diff === 0) {
            summary.textContent = `Les deux évaluations sont identiques (${comparison.references.score}/10).`;
        } else if (diff > 0) {
            summary.textContent = `L'évaluation par réponses de référence est plus sévère de ${diff} point${diff > 1 ? 's' : ''} (${comparison.references.score}/10 vs ${comparison.facts.score}/10).`;
        } else {
            summary.textContent = `L'évaluation par faits est plus sévère de ${-diff} point${-diff > 1 ? 's' : ''} (${comparison.facts.score}/10 vs ${comparison.references.score}/10).`;
        }
    }

    comparisonDiv.style.display = 'block';
}

/**
 * Évalue une réponse par rapport à la réponse de référence
 * @param {number} questionId - ID de la question
 */
async function evaluateAnswer(questionId) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    const answerTextarea = document.getElementById(`answer-to-evaluate-${questionId}`);
    const userAnswer = answerTextarea.value.trim();
    
    if (!userAnswer) {
        alert('Veuillez entrer une réponse à évaluer');
        return;
    }

    // Récupérer le mode d'évaluation choisi
    const evaluationMode = getEvaluationMode(questionId);

    // Récupérer les réponses de référence
    const referenceList = getReferenceAnswerList(questionId, questionCard);

    // Récupérer les faits de réponse
    const factsList = getFactsList(questionCard);

    const wantsReferences = evaluationMode === 'references' || evaluationMode === 'both';
    const wantsFacts = evaluationMode === 'facts' || evaluationMode === 'both';

    if (wantsReferences && referenceList.length === 0) {
        alert('Veuillez fournir une réponse de référence pour évaluer. Vous pouvez en saisir une dans le champ prévu à cet effet.');
        return;
    }
    if (wantsFacts && factsList.length === 0) {
        alert('Aucun fait de réponse trouvé pour cette question. Générez d\u2019abord les faits ou choisissez un autre mode d\u2019évaluation.');
        return;
    }

    // Récupérer la question depuis le DOM
    let questionText = '';
    if (questionCard) {
        const questionContent = questionCard.querySelector('.question-content');
        if (questionContent) {
            questionText = questionContent.textContent.replace('Q:', '').trim();
        }
    }

    // Si pas de questionText, essayer de la récupérer depuis referenceAnswers
    if (!questionText && referenceAnswers[questionId]) {
        questionText = referenceAnswers[questionId].question_content;
    }
    
    // Afficher l'état de chargement
    const evalButton = event.target.closest('.btn-evaluate') || document.querySelector(`[onclick*="evaluateAnswer(${questionId}"]`);
    const originalButtonText = evalButton ? evalButton.innerHTML : 'Évaluer avec l\'agent';
    if (evalButton) {
        evalButton.innerHTML = 'Évaluation en cours... <span class="loading-evaluation"></span>';
        evalButton.disabled = true;
    }

    try {
        // Récupérer le modèle sélectionné
        const modelSelect = document.getElementById('modelFilter');
        const selectedModel = modelSelect ? modelSelect.value : '';

        const evaluationPromises = [];
        if (wantsReferences) {
            evaluationPromises.push(runEvaluation(questionText, referenceList, userAnswer, selectedModel));
        }
        if (wantsFacts) {
            evaluationPromises.push(runEvaluation(questionText, factsList, userAnswer, selectedModel));
        }

        const settledResults = await Promise.allSettled(evaluationPromises);
        const evaluations = settledResults
            .filter(result => result.status === 'fulfilled')
            .map(result => result.value);

        if (evaluations.length === 0) {
            const firstError = settledResults.find(result => result.status === 'rejected');
            throw firstError ? firstError.reason : new Error('Erreur inconnue lors de l\u2019évaluation');
        }

        let evaluation;
        let comparison = null;
        if (wantsReferences && wantsFacts && evaluations.length === 2) {
            const [referenceEvaluation, factsEvaluation] = evaluations;
            evaluation = referenceEvaluation;
            comparison = { references: referenceEvaluation, facts: factsEvaluation };
        } else {
            evaluation = evaluations[0];
        }

        // Afficher les résultats
        const scoreElement = document.getElementById(`score-${questionId}`);
        const feedbackElement = document.getElementById(`feedback-${questionId}`);
        const resultDiv = document.getElementById(`eval-result-${questionId}`);
        
        if (scoreElement) {
            scoreElement.textContent = evaluation.score;
            scoreElement.className = 'score-display';
        }
        if (feedbackElement) {
            feedbackElement.textContent = evaluation.feedback;
        }
        if (resultDiv) {
            resultDiv.style.display = 'block';
        }

        // Afficher la comparaison si les deux modes ont été évalués
        displayComparison(questionId, comparison);
        
        // Stocker les résultats pour la sauvegarde
        if (scoreElement) {
            scoreElement.dataset.evaluationType = 'auto';
            scoreElement.dataset.modelUsed = selectedModel || 'mistral-small';
        }
        
        // Afficher un message de succès
        const statusElement = document.getElementById(`eval-status-${questionId}`);
        if (statusElement) {
            statusElement.innerHTML = '<span class="success-message">Évaluation terminée !</span>';
        }
        
        // Afficher la section de méta-évaluation (critique de l'évaluation IA)
        const metaEvalSection = document.getElementById(`meta-eval-${questionId}`);
        const metaScoreElement = document.getElementById(`meta-ai-score-${questionId}`);
        const metaFeedbackElement = document.getElementById(`meta-ai-feedback-${questionId}`);
        
        if (metaEvalSection && metaScoreElement && metaFeedbackElement) {
            metaScoreElement.textContent = evaluation.score;
            metaFeedbackElement.textContent = evaluation.feedback;
            metaEvalSection.style.display = 'block';
        }
        
    } catch (error) {
        console.error('Erreur lors de l\'évaluation:', error);
        const statusElement = document.getElementById(`eval-status-${questionId}`);
        if (statusElement) {
            statusElement.innerHTML = `<span style="color: #dc3545;">Erreur: ${error.message}</span>`;
        }
        alert('Une erreur est survenue lors de l\'évaluation: ' + error.message);
    } finally {
        if (evalButton) {
            evalButton.innerHTML = originalButtonText;
            evalButton.disabled = false;
        }
    }
}

/**
 * Sauvegarde une évaluation dans le fichier CSV
 * @param {number} questionId - ID de la question
 */
async function saveEvaluation(questionId) {
    const answerTextarea = document.getElementById(`answer-to-evaluate-${questionId}`);
    const userAnswer = answerTextarea.value.trim();
    
    if (!userAnswer) {
        alert('Veuillez entrer une réponse à évaluer');
        return;
    }

    // Récupérer les données d'évaluation
    const scoreElement = document.getElementById(`score-${questionId}`);
    const feedbackElement = document.getElementById(`feedback-${questionId}`);
    const manualScoreInput = document.getElementById(`manual-score-${questionId}`);
    const manualFeedbackTextarea = document.getElementById(`manual-feedback-${questionId}`);
    
    let score, feedback, evaluationType, modelUsed;
    
    if (scoreElement && scoreElement.textContent && scoreElement.dataset.evaluationType === 'auto') {
        // Évaluation automatique
        score = parseInt(scoreElement.textContent);
        feedback = feedbackElement ? feedbackElement.textContent : '';
        evaluationType = 'auto';
        modelUsed = scoreElement.dataset.modelUsed || 'mistral-small';
    } else if (manualScoreInput && manualScoreInput.value) {
        // Évaluation manuelle
        score = parseInt(manualScoreInput.value);
        feedback = manualFeedbackTextarea ? manualFeedbackTextarea.value : '';
        evaluationType = 'manual';
        modelUsed = null;
    } else {
        alert('Veuillez d\'abord évaluer la réponse (automatiquement ou manuellement)');
        return;
    }
    
    if (!score || score < 1 || score > 10) {
        alert('Veuillez entrer une note valide entre 1 et 10');
        return;
    }

    // Récupérer la source de l'évaluation (llm ou user)
    const sourceInput = document.getElementById(`eval-source-${questionId}`);
    const evaluationSource = sourceInput ? sourceInput.value : 'user';
    
    // Récupérer la question et la réponse de référence
    let questionText = '';
    let referenceAnswer = '';
    let answerId = '';
    
    // 1. D'abord essayer de récupérer depuis referenceAnswers
    if (referenceAnswers[questionId]) {
        referenceAnswer = referenceAnswers[questionId].response_answer;
        answerId = referenceAnswers[questionId].answer_id;
        questionText = referenceAnswers[questionId].question_content;
    } else {
        // 2. Sinon, essayer de récupérer depuis le champ de référence dans l'UI
        const refAnswerTextarea = document.getElementById(`reference-answer-${questionId}`);
        if (refAnswerTextarea && refAnswerTextarea.value.trim()) {
            referenceAnswer = refAnswerTextarea.value.trim();
        }
    }
    
    // 3. Récupérer la question depuis le DOM
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    if (questionCard && !questionText) {
        const questionContent = questionCard.querySelector('.question-content');
        if (questionContent) {
            questionText = questionContent.textContent.replace('Q:', '').trim();
        }
    }

    const saveButton = event.target.closest('.btn-save') || document.querySelector(`[onclick*="saveEvaluation(${questionId}"]`);
    const originalButtonText = saveButton ? saveButton.innerHTML : 'Sauvegarder';
    
    if (saveButton) {
        saveButton.innerHTML = 'Sauvegarde en cours...';
        saveButton.disabled = true;
    }

    try {
        const response = await fetch('/api/evaluations/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question_id: questionId,
                answer_id: answerId,
                evaluated_answer: userAnswer,
                score: score,
                feedback: feedback,
                evaluation_type: evaluationType,
                evaluation_source: evaluationSource,
                model_used: modelUsed,
                question_content: questionText,
                reference_answer: referenceAnswer
            })
        });

        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const result = await response.json();
        console.log('Évaluation sauvegardée:', result);
        
        // Afficher un message de succès
        const statusElement = document.getElementById(`eval-status-${questionId}`);
        if (statusElement) {
            statusElement.innerHTML = '<span class="success-message">Évaluation sauvegardée avec succès !</span>';
        }
        
        // Réinitialiser le champ de réponse
        if (answerTextarea) {
            answerTextarea.value = '';
        }
        
    } catch (error) {
        console.error('Erreur lors de la sauvegarde:', error);
        const statusElement = document.getElementById(`eval-status-${questionId}`);
        if (statusElement) {
            statusElement.innerHTML = `<span style="color: #dc3545;">Erreur: ${error.message}</span>`;
        }
        alert('Une erreur est survenue lors de la sauvegarde: ' + error.message);
    } finally {
        if (saveButton) {
            saveButton.innerHTML = originalButtonText;
            saveButton.disabled = false;
        }
    }
}


/**
 * Active le mode d'édition pour une question
 * @param {number} questionId - ID de la question à modifier
 */
function enableQuestionEditing(questionId) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    
    // Ajouter la classe edit-mode
    questionCard.classList.add('edit-mode');
    
    // Rendre le contenu de la question éditable
    const questionContentDiv = questionCard.querySelector('.question-content');
    const originalQuestionContent = questionContentDiv.textContent.replace('Q:', '').trim();
    
    const questionTextarea = document.createElement('textarea');
    questionTextarea.className = 'editable-question-text';
    questionTextarea.value = originalQuestionContent;
    questionTextarea.dataset.originalContent = originalQuestionContent;
    
    // Remplacer le contenu
    questionContentDiv.innerHTML = '';
    questionContentDiv.appendChild(questionTextarea);
    
    // Rendre toutes les réponses existantes éditables
    const answerItems = questionCard.querySelectorAll('.answer-item');
    answerItems.forEach((answerItem, index) => {
        // Ne pas modifier les réponses qui sont déjà en mode édition
        if (answerItem.classList.contains('editing')) {
            return;
        }
        
        const answerText = answerItem.textContent
            .replace(/Réponse \d+: /, '')
            .replace(/\s*\[LLM\]/, '')
            .replace(/\s*✓ Correcte/, '')
            .trim();
        
        const answerTextarea = document.createElement('textarea');
        answerTextarea.className = 'editable-answer-text';
        answerTextarea.value = answerText;
        answerTextarea.dataset.answerIndex = index;
        
        // Conserver l'answer_id pour la mise à jour
        const answerId = answerItem.dataset.answerId || '';
        
        // Créer un conteneur pour la réponse
        const answerContainer = document.createElement('div');
        answerContainer.className = 'answer-item editing';
        if (answerId) {
            answerTextarea.dataset.answerId = answerId;
            answerContainer.dataset.answerId = answerId;
        }
        
        // Ajouter un bouton de suppression
        const deleteButton = document.createElement('button');
        deleteButton.className = 'btn btn-secondary btn-delete-answer';
        deleteButton.textContent = '×';
        deleteButton.title = 'Supprimer cette réponse';
        deleteButton.onclick = () => deleteAnswerField(questionId, answerContainer);
        deleteButton.style.marginLeft = '10px';
        deleteButton.style.padding = '2px 8px';
        deleteButton.style.fontSize = '12px';
        
        answerContainer.appendChild(answerTextarea);
        answerContainer.appendChild(deleteButton);
        
        // Remplacer l'ancien élément de réponse
        answerItem.parentNode.replaceChild(answerContainer, answerItem);
    });
    
    // Ajouter un bouton "Ajouter une réponse"
    let answersSection = questionCard.querySelector('.answers-section');
    if (!answersSection) {
        // Si answers-section n'existe pas (cas où il n'y a pas de réponses), le créer
        const evaluationSection = questionCard.querySelector('.evaluation-section');
        if (evaluationSection) {
            answersSection = document.createElement('div');
            answersSection.className = 'answers-section';
            questionCard.insertBefore(answersSection, evaluationSection);
        }
    }
    
    if (answersSection) {
        // Vérifier si le bouton "Ajouter une réponse" existe déjà
        if (!answersSection.querySelector('.btn-add-answer')) {
            const buttonsDiv = document.createElement('div');
            buttonsDiv.className = 'answers-action-buttons';
            buttonsDiv.style.marginTop = '10px';

            const addAnswerButton = document.createElement('button');
            addAnswerButton.className = 'btn btn-secondary btn-add-answer';
            addAnswerButton.textContent = 'Ajouter une réponse';
            addAnswerButton.onclick = () => addNewAnswerField(questionId);

            const generateAnswerButton = document.createElement('button');
            generateAnswerButton.className = 'btn btn-secondary btn-generate-answer';
            generateAnswerButton.textContent = '✨ Générer une réponse';
            generateAnswerButton.title = 'Générer une réponse via l\u2019agent LLM à partir de la question et de son contexte';
            generateAnswerButton.style.marginLeft = '10px';
            generateAnswerButton.onclick = () => generateAnswerForQuestion(questionId, generateAnswerButton);

            buttonsDiv.appendChild(addAnswerButton);
            buttonsDiv.appendChild(generateAnswerButton);
            answersSection.appendChild(buttonsDiv);
        }
    }
    
    // Masquer/Afficher les boutons
    const editButton = questionCard.querySelector('.btn-edit-question');
    const saveButton = questionCard.querySelector('.btn-save-changes');
    const cancelButton = questionCard.querySelector('.btn-cancel-edit');
    
    if (editButton) editButton.style.display = 'none';
    if (saveButton) saveButton.style.display = 'inline-block';
    if (cancelButton) cancelButton.style.display = 'inline-block';
}

/**
 * Ajoute un nouveau champ pour une réponse
 * @param {number} questionId - ID de la question
 */
function addNewAnswerField(questionId) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    const answersSection = questionCard.querySelector('.answers-section');
    const actionButtons = answersSection.querySelector('.answers-action-buttons') || answersSection.querySelector('.btn-add-answer');
    
    const newAnswerDiv = document.createElement('div');
    newAnswerDiv.className = 'answer-item editing new-answer-item';
    
    const answerTextarea = document.createElement('textarea');
    answerTextarea.className = 'editable-answer-text';
    answerTextarea.placeholder = 'Nouvelle réponse';
    answerTextarea.dataset.isNew = 'true';
    
    const deleteButton = document.createElement('button');
    deleteButton.className = 'btn btn-secondary btn-delete-answer';
    deleteButton.textContent = '×';
    deleteButton.title = 'Supprimer cette réponse';
    deleteButton.onclick = () => deleteAnswerField(questionId, newAnswerDiv);
    deleteButton.style.marginLeft = '10px';
    deleteButton.style.padding = '2px 8px';
    deleteButton.style.fontSize = '12px';
    
    newAnswerDiv.appendChild(answerTextarea);
    newAnswerDiv.appendChild(deleteButton);
    
    answersSection.insertBefore(newAnswerDiv, actionButtons);
}

/**
 * Génère une réponse à la question via l'agent LLM (endpoint /api/admin/questions/generate-answers)
 * et l'ajoute comme nouveau champ de réponse dans le formulaire d'édition.
 * La réponse générée est sauvegardée en base uniquement lorsque l'utilisateur clique sur « Sauvegarder ».
 * @param {number} questionId - ID de la question
 * @param {HTMLElement} button - Bouton cliqué
 */
async function generateAnswerForQuestion(questionId, button) {
    const originalButtonText = button ? button.innerHTML : '✨ Générer une réponse';

    if (button) {
        button.innerHTML = '⏳ Génération...';
        button.disabled = true;
    }

    try {
        const modelFilter = document.getElementById('generationModelFilter');
        const modelName = modelFilter && modelFilter.value ? modelFilter.value : 'mistral-small';

        const response = await fetch('/api/admin/questions/generate-answers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question_id: questionId,
                num_answers: 1,
                model_name: modelName
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `Erreur ${response.status}`);
        }

        const data = await response.json();

        if (!data.answers || data.answers.length === 0) {
            throw new Error('L\u2019agent n\u2019a généré aucune réponse');
        }

        // Basculer la question en mode édition si nécessaire
        const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
        if (questionCard && !questionCard.classList.contains('edit-mode')) {
            enableQuestionEditing(questionId);
        }

        // Ajouter la réponse générée dans un nouveau champ
        addNewAnswerField(questionId);
        const newFields = document.querySelectorAll(`[data-question-id="${questionId}"] .new-answer-item .editable-answer-text`);
        const newField = newFields[newFields.length - 1];
        if (newField) {
            newField.value = data.answers[0];
            newField.dataset.generatedBy = data.model_used || '';
        }
    } catch (error) {
        console.error('Erreur lors de la génération de la réponse:', error);
        alert(`Erreur lors de la génération de la réponse : ${error.message}`);
    } finally {
        if (button) {
            button.innerHTML = originalButtonText;
            button.disabled = false;
        }
    }
}

/**
 * Supprime un champ de réponse
 * @param {number} questionId - ID de la question
 * @param {HTMLElement} answerElement - Élément DOM de la réponse à supprimer
 */
function deleteAnswerField(questionId, answerElement) {
    // Ne supprimer que les nouveaux champs (pas encore sauvegardés)
    if (answerElement.classList.contains('new-answer-item')) {
        answerElement.remove();
    } else {
        // Pour les réponses existantes, marquer pour suppression
        answerElement.style.display = 'none';
        answerElement.dataset.markedForDeletion = 'true';
    }
}

/**
 * Annule l'édition d'une question
 * @param {number} questionId - ID de la question
 */
function cancelQuestionEditing(questionId) {
    // Recharger la question depuis le serveur
    if (currentDocumentId) {
        loadQuestions(currentDocumentId);
    }
}


/**
 * Active le mode d'édition pour une question
 * @param {number} questionId - ID de la question à modifier
 */
function enableQuestionEditing(questionId) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    
    // Ajouter la classe edit-mode
    questionCard.classList.add('edit-mode');
    
    // Rendre le contenu de la question éditable
    const questionContentDiv = questionCard.querySelector('.question-content');
    const originalQuestionContent = questionContentDiv.textContent.replace('Q:', '').trim();
    
    const questionTextarea = document.createElement('textarea');
    questionTextarea.className = 'editable-question-text';
    questionTextarea.value = originalQuestionContent;
    questionTextarea.dataset.originalContent = originalQuestionContent;
    
    // Remplacer le contenu
    questionContentDiv.innerHTML = '';
    questionContentDiv.appendChild(questionTextarea);
    
    // Rendre toutes les réponses existantes éditables
    const answerItems = questionCard.querySelectorAll('.answer-item');
    answerItems.forEach((answerItem, index) => {
        // Ne pas modifier les réponses qui sont déjà en mode édition
        if (answerItem.classList.contains('editing')) {
            return;
        }
        
        const answerText = answerItem.textContent
            .replace(/Réponse \d+: /, '')
            .replace(/\s*\[LLM\]/, '')
            .replace(/\s*✓ Correcte/, '')
            .trim();
        
        const answerTextarea = document.createElement('textarea');
        answerTextarea.className = 'editable-answer-text';
        answerTextarea.value = answerText;
        answerTextarea.dataset.answerIndex = index;
        
        // Conserver l'answer_id pour la mise à jour
        const answerId = answerItem.dataset.answerId || '';
        
        // Créer un conteneur pour la réponse
        const answerContainer = document.createElement('div');
        answerContainer.className = 'answer-item editing';
        if (answerId) {
            answerTextarea.dataset.answerId = answerId;
            answerContainer.dataset.answerId = answerId;
        }
        
        // Ajouter un bouton de suppression
        const deleteButton = document.createElement('button');
        deleteButton.className = 'btn btn-secondary btn-delete-answer';
        deleteButton.textContent = '×';
        deleteButton.title = 'Supprimer cette réponse';
        deleteButton.onclick = () => deleteAnswerField(questionId, answerContainer);
        deleteButton.style.marginLeft = '10px';
        deleteButton.style.padding = '2px 8px';
        deleteButton.style.fontSize = '12px';
        
        answerContainer.appendChild(answerTextarea);
        answerContainer.appendChild(deleteButton);
        
        // Remplacer l'ancien élément de réponse
        answerItem.parentNode.replaceChild(answerContainer, answerItem);
    });
    
    // Ajouter un bouton "Ajouter une réponse"
    let answersSection = questionCard.querySelector('.answers-section');
    if (!answersSection) {
        // Si answers-section n'existe pas, le créer
        const evaluationSection = questionCard.querySelector('.evaluation-section');
        if (evaluationSection) {
            answersSection = document.createElement('div');
            answersSection.className = 'answers-section';
            questionCard.insertBefore(answersSection, evaluationSection);
        }
    }
    
    if (answersSection) {
        // Vérifier si le bouton existe déjà
        if (!answersSection.querySelector('.btn-add-answer')) {
            const buttonsDiv = document.createElement('div');
            buttonsDiv.className = 'answers-action-buttons';
            buttonsDiv.style.marginTop = '10px';

            const addAnswerButton = document.createElement('button');
            addAnswerButton.className = 'btn btn-secondary btn-add-answer';
            addAnswerButton.textContent = 'Ajouter une réponse';
            addAnswerButton.onclick = () => addNewAnswerField(questionId);

            const generateAnswerButton = document.createElement('button');
            generateAnswerButton.className = 'btn btn-secondary btn-generate-answer';
            generateAnswerButton.textContent = '✨ Générer une réponse';
            generateAnswerButton.title = 'Générer une réponse via l\u2019agent LLM à partir de la question et de son contexte';
            generateAnswerButton.style.marginLeft = '10px';
            generateAnswerButton.onclick = () => generateAnswerForQuestion(questionId, generateAnswerButton);

            buttonsDiv.appendChild(addAnswerButton);
            buttonsDiv.appendChild(generateAnswerButton);
            answersSection.appendChild(buttonsDiv);
        }
    }
    
    // Masquer/Afficher les boutons
    const editButton = questionCard.querySelector('.btn-edit-question');
    const saveButton = questionCard.querySelector('.btn-save-changes');
    const cancelButton = questionCard.querySelector('.btn-cancel-edit');
    
    if (editButton) editButton.style.display = 'none';
    if (saveButton) saveButton.style.display = 'inline-block';
    if (cancelButton) cancelButton.style.display = 'inline-block';
}

/**
 * Ajoute un nouveau champ pour une réponse
 * @param {number} questionId - ID de la question
 */
function addNewAnswerField(questionId) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    const answersSection = questionCard.querySelector('.answers-section');
    const actionButtons = answersSection.querySelector('.answers-action-buttons') || answersSection.querySelector('.btn-add-answer');
    
    const newAnswerDiv = document.createElement('div');
    newAnswerDiv.className = 'answer-item editing new-answer-item';
    
    const answerTextarea = document.createElement('textarea');
    answerTextarea.className = 'editable-answer-text';
    answerTextarea.placeholder = 'Nouvelle réponse';
    answerTextarea.dataset.isNew = 'true';
    
    const deleteButton = document.createElement('button');
    deleteButton.className = 'btn btn-secondary btn-delete-answer';
    deleteButton.textContent = '×';
    deleteButton.title = 'Supprimer cette réponse';
    deleteButton.onclick = () => deleteAnswerField(questionId, newAnswerDiv);
    deleteButton.style.marginLeft = '10px';
    deleteButton.style.padding = '2px 8px';
    deleteButton.style.fontSize = '12px';
    
    newAnswerDiv.appendChild(answerTextarea);
    newAnswerDiv.appendChild(deleteButton);
    
    answersSection.insertBefore(newAnswerDiv, actionButtons);
}

/**
 * Supprime un champ de réponse
 * @param {number} questionId - ID de la question
 * @param {HTMLElement} answerElement - Élément DOM de la réponse
 */
function deleteAnswerField(questionId, answerElement) {
    // Ne supprimer que les nouveaux champs
    if (answerElement.classList.contains('new-answer-item')) {
        answerElement.remove();
    } else {
        // Pour les réponses existantes, marquer pour suppression
        answerElement.style.display = 'none';
        answerElement.dataset.markedForDeletion = 'true';
    }
}

/**
 * Annule l'édition d'une question
 * @param {number} questionId - ID de la question
 */
function cancelQuestionEditing(questionId) {
    // Recharger depuis le serveur
    if (currentDocumentId) {
        loadQuestions(currentDocumentId);
    }
}

/**
 * Sauvegarde les modifications d'une question et de ses réponses
 * @param {number} questionId - ID de la question
 */
async function saveQuestionChanges(questionId) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    const questionTextarea = questionCard.querySelector('.editable-question-text');
    const answerTextareas = questionCard.querySelectorAll('.editable-answer-text');
    
    const requestData = {
        question_content: questionTextarea ? questionTextarea.value : undefined,
        answers: [],
        deleted_answer_ids: []
    };
    
    // Collecter les IDs des réponses marquées pour suppression
    const allAnswerItems = questionCard.querySelectorAll('.answer-item');
    allAnswerItems.forEach((answerItem) => {
        if (answerItem.dataset.markedForDeletion === 'true') {
            const answerId = parseInt(answerItem.dataset.answerId);
            if (answerId) {
                requestData.deleted_answer_ids.push(answerId);
            }
        }
    });
    
    // Collecter toutes les réponses (hors celles marquées pour suppression)
    answerTextareas.forEach((textarea) => {
        const answerContainer = textarea.closest('.answer-item');
        
        // Ignorer les réponses marquées pour suppression
        if (answerContainer.dataset.markedForDeletion === 'true') {
            return;
        }
        
        const answerData = {
            content: textarea.value,
            is_correct: false
        };
        
        // Si answer_id existe, c'est une mise à jour
        if (textarea.dataset.answerId) {
            answerData.answer_id = parseInt(textarea.dataset.answerId);
        } else if (answerContainer.dataset.answerId) {
            answerData.answer_id = parseInt(answerContainer.dataset.answerId);
        }
        
        // Ne pas ajouter les réponses vides
        if (answerData.content.trim() === '' && !answerData.answer_id) {
            return;
        }
        
        requestData.answers.push(answerData);
    });
    
    // Afficher le chargement
    const saveButton = questionCard.querySelector('.btn-save-changes');
    const originalButtonText = saveButton.innerHTML;
    saveButton.innerHTML = 'Sauvegarde en cours...';
    saveButton.disabled = true;
    
    try {
        const response = await fetch(`/api/questions/${questionId}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Erreur HTTP: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            // Rafraîchir uniquement la carte de la question mise à jour, sans recharger toute la page
            const newCard = await refreshQuestionCard(questionId);

            // Afficher un message de succès
            const editStatus = document.createElement('div');
            editStatus.className = 'edit-status';
            editStatus.style.color = '#28a745';
            editStatus.style.marginTop = '10px';
            editStatus.style.fontWeight = 'bold';
            editStatus.textContent = 'Modifications sauvegardées avec succès !';
            const card = newCard || document.querySelector(`[data-question-id="${questionId}"]`);
            if (card) card.appendChild(editStatus);
        } else {
            alert(`Erreur: ${result.message || 'Échec de la sauvegarde'}`);
        }
    } catch (error) {
        console.error('Erreur lors de la sauvegarde:', error);
        alert('Une erreur est survenue: ' + error.message);
    } finally {
        saveButton.innerHTML = originalButtonText;
        saveButton.disabled = false;
    }
}

async function getKnowledgeItemsForQuestion(questionId) {
    const section = document.getElementById(`knowledge-items-${questionId}`);
    const container = document.getElementById(`knowledge-items-container-${questionId}`);
    const statusElement = document.getElementById(`knowledge-items-status-${questionId}`);
    const generateButton = document.querySelector(`[onclick*="getKnowledgeItemsForQuestion(${questionId})"]`);

    // Basculer l'affichage si la section est déjà visible et remplie
    if (section.style.display === 'block' && knowledgeItemsByQuestion[questionId]) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    container.innerHTML = '<p style="font-size: 13px; color: #666;">Chargement des éléments de connaissance...</p>';
    if (statusElement) statusElement.innerHTML = '';

    const originalButtonText = generateButton ? generateButton.innerHTML : '🧠 Éléments de connaissance';
    if (generateButton) {
        generateButton.innerHTML = 'Chargement...';
        generateButton.disabled = true;
    }

    try {
        const response = await fetch(`/api/admin/knowledge-items/by-question/${questionId}`);

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`HTTP ${response.status} : ${errText}`);
        }

        const data = await response.json();
        knowledgeItemsByQuestion[questionId] = data.knowledge_items || [];

        renderKnowledgeItems(questionId, knowledgeItemsByQuestion[questionId]);

        if (statusElement) {
            if (knowledgeItemsByQuestion[questionId].length === 0) {
                statusElement.innerHTML = '<span style="color: #dc3545;">Aucun élément de connaissance en base pour cette question.</span>';
            } else {
                statusElement.innerHTML = `<span class="success-message">${knowledgeItemsByQuestion[questionId].length} élément(s) de connaissance trouvé(s) en base.</span>`;
            }
        }
    } catch (error) {
        console.error('Erreur lors du chargement des éléments de connaissance:', error);
        container.innerHTML = '';
        if (statusElement) {
            statusElement.innerHTML = `<span style="color: #dc3545;">Erreur: ${error.message}</span>`;
        }
    } finally {
        if (generateButton) {
            generateButton.innerHTML = originalButtonText;
            generateButton.disabled = false;
        }
    }
}

function renderKnowledgeItems(questionId, items) {
    const container = document.getElementById(`knowledge-items-container-${questionId}`);

    if (!items || items.length === 0) {
        container.innerHTML = '<p style="font-size: 13px; color: #666;">Aucun élément de connaissance en base pour cette question.</p>';
        return;
    }

    const itemsHtml = items.map((item, index) => {
        const entities = (item.entities || []).map(e =>
            `<span class="knowledge-badge knowledge-badge-entity">${escapeHtml(e.name)} (${escapeHtml(e.type)})</span>`
        ).join('');
        const themes = (item.themes || []).map(t =>
            `<span class="knowledge-badge knowledge-badge-theme">${escapeHtml(t.name)}</span>`
        ).join('');
        const verifiedHtml = item.is_verified ?
            '<span class="knowledge-badge">✓ vérifié</span>' : '';

        return `
            <div class="knowledge-item-card">
                <div class="knowledge-item-proposition">${index + 1}. ${escapeHtml(item.proposition)}</div>
                ${item.summary ? `<div class="knowledge-item-summary">"${escapeHtml(item.summary)}"</div>` : ''}
                <div class="knowledge-item-meta">
                    ${verifiedHtml}
                    ${entities}
                    ${themes}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = itemsHtml;
}

/**
 * Bascule l'importance d'un fait de réponse (Essentiel <-> Facultatif) via l'API
 * et applique la modification directement dans le DOM sans rechargement.
 * @param {number} factId - ID du fait dans text_answer_facts
 * @param {HTMLElement} badgeElement - Élément DOM du badge cliqué
 */
async function toggleFactImportance(factId, badgeElement) {
    const factItem = badgeElement.closest('.answer-fact-item');
    if (!factItem) return;

    const currentImportance = factItem.classList.contains('importance-optional') ? 'optional' : 'essential';
    const newImportance = currentImportance === 'optional' ? 'essential' : 'optional';

    badgeElement.style.opacity = '0.5';
    badgeElement.style.pointerEvents = 'none';

    try {
        const response = await fetch(`/api/admin/questions/facts/${factId}/update-importance`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ importance: newImportance })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `Erreur ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            factItem.classList.remove('importance-essential', 'importance-optional');
            factItem.classList.add(`importance-${data.importance}`);

            badgeElement.classList.remove('badge-essential', 'badge-optional');
            badgeElement.classList.add(data.importance === 'optional' ? 'badge-optional' : 'badge-essential');
            badgeElement.textContent = data.importance === 'optional' ? 'Facultatif' : 'Essentiel';
        } else {
            throw new Error(data.message || 'Échec de la mise à jour');
        }
    } catch (error) {
        console.error('Erreur lors du basculement de l\u2019importance du fait:', error);
        alert(`Erreur lors du changement d\u2019importance : ${error.message}`);
    } finally {
        badgeElement.style.opacity = '';
        badgeElement.style.pointerEvents = '';
    }
}

/**
 * Génère les faits de réponse d'une réponse de référence via l'API.
 * @param {number|string} answerId - ID de la réponse dans text_question_answers
 * @param {HTMLElement} button - Bouton cliqué
 */
async function generateAnswerFacts(answerId, button) {
    const statusElement = document.getElementById(`facts-status-${answerId}`);
    const factsContainer = button ? button.closest('.answer-item').querySelector('.answer-facts-container') : null;
    const originalButtonText = button ? button.innerHTML : '✨ Faits';

    if (button) {
        button.innerHTML = '⏳ Génération...';
        button.disabled = true;
    }
    if (statusElement) {
        statusElement.style.display = 'block';
        statusElement.innerHTML = '<span style="color: #007bff;">Génération des faits en cours...</span>';
    }

    try {
        const modelFilter = document.getElementById('generationModelFilter');
        const modelName = modelFilter && modelFilter.value ? modelFilter.value : 'mistral-small';

        const response = await fetch(`/api/admin/questions/answers/${answerId}/generate-facts?model_name=${encodeURIComponent(modelName)}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `Erreur ${response.status}`);
        }

        const data = await response.json();

        if (statusElement) {
            statusElement.innerHTML = `<span style="color: ${data.success ? '#28a745' : '#dc3545'};">${escapeHtml(data.message)}</span>`;
        }

        if (data.success && data.facts && data.facts.length > 0 && factsContainer) {
            factsContainer.innerHTML = `
                <div class="answer-facts">
                    <div class="answer-facts-title">Faits de réponse (${data.facts.length})</div>
                    <ul class="answer-facts-list">
                        ${data.facts.map(fact => `
                            <li class="answer-fact-item importance-${escapeHtml(fact.importance || 'essential')}" data-fact-id="${fact.fact_id || ''}">
                                <span class="fact-importance-badge ${fact.importance === 'optional' ? 'badge-optional' : 'badge-essential'}" ${fact.fact_id ? `onclick="toggleFactImportance(${fact.fact_id}, this)" title="Cliquer pour basculer entre Essentiel et Facultatif"` : ''}>
                                    ${fact.importance === 'optional' ? 'Facultatif' : 'Essentiel'}
                                </span>
                                <span class="answer-fact-content">${escapeHtml(fact.content)}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }
    } catch (error) {
        console.error('Erreur lors de la génération des faits:', error);
        if (statusElement) {
            statusElement.innerHTML = `<span style="color: #dc3545;">Erreur: ${escapeHtml(error.message)}</span>`;
        }
    } finally {
        if (button) {
            button.innerHTML = originalButtonText;
            button.disabled = false;
        }
    }
}

/**
 * Supprime toutes les réponses d'une question (et leurs faits associés),
 * via l'endpoint /api/admin/questions/{question_id}/delete-answers.
 * @param {number} questionId - ID de la question
 * @param {HTMLElement} button - Bouton cliqué
 */
async function deleteAllAnswersForQuestion(questionId, button) {
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
    const answersSection = questionCard ? questionCard.querySelector('.answers-section') : null;
    const answersCount = answersSection ? answersSection.querySelectorAll('.answer-item').length : 0;

    if (answersCount === 0) {
        alert('Cette question n\'a aucune réponse à supprimer.');
        return;
    }

    if (!confirm(`Supprimer les ${answersCount} réponse(s) de cette question ?\n\nLes faits associés à chaque réponse seront également supprimés. Cette action est irréversible.`)) {
        return;
    }

    const originalButtonText = button ? button.innerHTML : '';
    if (button) {
        button.innerHTML = '⏳ Suppression...';
        button.disabled = true;
    }

    try {
        const response = await fetch(`/api/admin/questions/${questionId}/delete-answers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => null);
            throw new Error(errorData?.detail || `Erreur ${response.status}`);
        }

        const data = await response.json();
        console.log(`✅ ${data.message}`);
        // Mettre à jour uniquement la carte concernée, sans recharger toute la page
        await refreshQuestionCard(questionId);
    } catch (error) {
        console.error('Erreur lors de la suppression des réponses:', error);
        alert('❌ Erreur lors de la suppression des réponses : ' + error.message);
    } finally {
        if (button) {
            button.innerHTML = originalButtonText || '🗑 Supprimer toutes les réponses';
            button.disabled = false;
        }
    }
}

/**
 * Affiche/masque le menu d'actions groupées.
 */
function toggleBulkMenu() {
    const menu = document.getElementById('bulkMenu');
    if (!menu) return;
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
}

/**
 * Génère des réponses pour toutes les questions du document affiché.
 * Parcourt les questions une à une, en réutilisant les endpoints
 * /generate-answers, /add-answer et /generate-facts.
 * Option : générer ou non les faits des réponses générées.
 */
async function bulkGenerateAnswers() {
    const questions = currentQuestions || [];
    if (questions.length === 0) {
        alert('Aucune question à traiter pour ce document.');
        return;
    }

    const numAnswers = parseInt(document.getElementById('bulkNumAnswers').value) || 1;
    const bulkModelSelect = document.getElementById('bulkModel');
    const generateFacts = document.getElementById('bulkGenerateFacts').checked;
    const userPrompt = (document.getElementById('bulkUserPrompt').value || '').trim();
    const modelFilter = document.getElementById('generationModelFilter');
    const modelName = (bulkModelSelect && bulkModelSelect.value)
        ? bulkModelSelect.value
        : ((modelFilter && modelFilter.value) ? modelFilter.value : 'mistral-small');

    if (!confirm(`Générer ${numAnswers} réponse(s) pour chacune des ${questions.length} question(s) de ce document ?\n\n`
        + `Modèle : ${modelName}\n`
        + `Faits : ${generateFacts ? 'génération des faits activée' : 'pas de génération de faits'}\n`
        + (userPrompt ? `Commande personnalisée : « ${userPrompt.substring(0, 120)}${userPrompt.length > 120 ? '...' : ''} »\n` : '')
        + `\nCette opération peut prendre plusieurs minutes.`)) {
        return;
    }

    const progressElement = document.getElementById('bulkProgress');
    const bulkButton = document.querySelector('#bulkMenu .btn');
    if (bulkButton) bulkButton.disabled = true;
    progressElement.style.display = 'block';

    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < questions.length; i++) {
        const question = questions[i];
        progressElement.innerHTML = `⏳ Question ${i + 1}/${questions.length} — ${escapeHtml(question.content.substring(0, 80))}${question.content.length > 80 ? '...' : ''}`;
        try {
            const generateResponse = await fetch('/api/admin/questions/generate-answers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question_id: question.question_id,
                    num_answers: numAnswers,
                    model_name: modelName,
                    user_prompt: userPrompt || null
                })
            });

            if (!generateResponse.ok) {
                const errorData = await generateResponse.json().catch(() => null);
                throw new Error(errorData?.detail || `Erreur ${generateResponse.status}`);
            }

            const data = await generateResponse.json();
            if (!data.answers || data.answers.length === 0) {
                throw new Error('L\'agent n\'a généré aucune réponse');
            }

            for (const answerText of data.answers) {
                const addResponse = await fetch(`/api/admin/questions/${question.question_id}/add-answer`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        answer_text: answerText,
                        is_correct: true,
                        model_name: modelName
                    })
                });

                if (!addResponse.ok) {
                    const errorData = await addResponse.json().catch(() => null);
                    throw new Error(errorData?.detail || `Erreur ${addResponse.status} à l'ajout de la réponse`);
                }

                if (generateFacts) {
                    const addData = await addResponse.json();
                    if (addData.answer_id) {
                        const factsResponse = await fetch(`/api/admin/questions/answers/${addData.answer_id}/generate-facts?model_name=${encodeURIComponent(modelName)}`, {
                            method: 'POST'
                        });
                        if (!factsResponse.ok) {
                            console.warn(`Faits non générés pour la réponse ${addData.answer_id} : ${factsResponse.status}`);
                        }
                    }
                }
            }

            successCount++;
        } catch (error) {
            console.error(`Erreur pour la question ${question.question_id}:`, error);
            errorCount++;
            progressElement.innerHTML += `<div style="color: #dc3545;">❌ Question ${question.question_id} : ${escapeHtml(error.message)}</div>`;
        }
    }

    progressElement.innerHTML = `✅ ${successCount} question(s) traitée(s) avec succès`
        + (errorCount > 0 ? ` — ❌ ${errorCount} échec(s)` : '');
    if (bulkButton) bulkButton.disabled = false;

    await loadQuestions(currentDocumentId);
}
