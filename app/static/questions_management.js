/**
 * Gestion des Questions/Réponses - JavaScript
 * Ce fichier gère le chargement et l'affichage des questions/réponses par document
 */

// Variables globales
let currentDocumentId = null;
let allDocuments = [];

/**
 * Initialise la page au chargement
 */
document.addEventListener('DOMContentLoaded', function() {
    loadDocuments();
    setupEventListeners();
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
                <h4>${doc.file_name}</h4>
                <p>Taille: ${formatFileSize(doc.file_size)}</p>
            `;
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

    // Charger les questions pour ce document
    await loadQuestions(documentId);
}

/**
 * Charge les questions pour un document donné
 * @param {string} documentId - L'ID du document
 */
async function loadQuestions(documentId) {
    const loadingElement = document.getElementById('loadingQuestions');
    const contentElement = document.getElementById('questionsContent');
    const emptyStateElement = document.getElementById('emptyState');

    try {
        loadingElement.classList.add('active');
        contentElement.innerHTML = '';

        // Construire l'URL avec les filtres actuels
        const params = new URLSearchParams();
        params.append('include_answers', 'true');
        
        const statusFilter = document.getElementById('statusFilter').value;
        const difficultyFilter = document.getElementById('difficultyFilter').value;
        const limitFilter = document.getElementById('limitFilter').value;
        const chunkFilter = document.getElementById('chunkFilter')?.value || '';

        if (statusFilter) params.append('status_filter', statusFilter);
        if (difficultyFilter) params.append('difficulty_filter', difficultyFilter);
        if (limitFilter) params.append('nb_limit', limitFilter);

        const url = `/api/questions/${encodeURIComponent(documentId)}?${params.toString()}`;
        
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
 * Affiche les questions dans le DOM
 * @param {Array} questions - Liste des questions à afficher
 * @param {number} count - Nombre total de questions
 */
function displayQuestions(questions, count) {
    const contentElement = document.getElementById('questionsContent');
    
    let headerHtml = `
        <div class="questions-header">
            <h2>Questions pour ce document</h2>
            <span class="questions-count">${count} question(s) trouvée(s)</span>
        </div>
    `;

    let questionsHtml = questions.map(question => {
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
        const llmAnswerId = llmAnswer ? (llmAnswer.answer_id || llmAnswer.id || '') : '';

        // Formater les réponses
        const answersHtml = question.answers.length > 0 ? `
            <div class="answers-section">
                <div class="answers-title">Réponses (${question.answers.length})</div>
                ${question.answers.map((answer, index) => `
                    <div class="answer-item" data-answer-index="${index}" data-answer-id="${answer.answer_id || answer.id || ''}">
                        <strong>Réponse ${index + 1}:</strong> ${escapeHtml(answer.content)}
                        ${answer.is_correct ? '<span style="color: #28a745; margin-left: 10px;">✓ Correcte</span>' : ''}
                        ${index === 0 ? '<span style="color: #007bff; margin-left: 10px;">[LLM]</span>' : ''}
                    </div>
                `).join('')}
            </div>
        ` : '';

        // Informations sur le chunk
        const chunkInfo = question.chunk_id ? `
            <div class="chunk-info">
                Chunk ID: ${question.chunk_id}
            </div>
        ` : '';

        // Récupérer la réponse de référence si disponible
        // 1. D'abord vérifier si la question a des réponses dans ses answers
        // 2. Sinon, vérifier dans referenceAnswers
        let referenceAnswerData = null;
        let hasReferenceAnswer = false;
        
        // Vérifier si la question a des réponses (answers)
        if (question.answers && question.answers.length > 0) {
            // Trouver la première réponse marquée comme correcte, sinon utiliser la première
            let referenceAnswer = null;
            let referenceAnswerObj = null;
            for (let i = 0; i < question.answers.length; i++) {
                if (question.answers[i].is_correct) {
                    referenceAnswer = question.answers[i].content;
                    referenceAnswerObj = question.answers[i];
                    break;
                }
            }
            // Si aucune réponse correcte n'a été trouvée, utiliser la première
            if (!referenceAnswer && question.answers.length > 0) {
                referenceAnswer = question.answers[0].content;
                referenceAnswerObj = question.answers[0];
            }
            
            if (referenceAnswer) {
                referenceAnswerData = {
                    answer_id: referenceAnswerObj.answer_id || referenceAnswerObj.id || '',
                    question_content: question.content,
                    response_answer: referenceAnswer
                };
                hasReferenceAnswer = true;
            }
        } else if (referenceAnswers[question.question_id]) {
            // Sinon, utiliser le CSV de référence
            referenceAnswerData = referenceAnswers[question.question_id];
            hasReferenceAnswer = true;
        }
        
        // Section d'évaluation - TOUJOURS affichée pour permettre l'évaluation
        const referenceAnswerText = hasReferenceAnswer ? escapeHtml(referenceAnswerData.response_answer) : '';
        const referenceAnswerId = hasReferenceAnswer ? (referenceAnswerData.answer_id || '') : '';
        
        const evaluationSection = `
            <div class="evaluation-section" data-question-id="${question.question_id}" data-has-reference="${hasReferenceAnswer}">
                <h4>📊 Évaluation de réponse</h4>
                ${hasReferenceAnswer ? `
                    <p style="font-size: 13px; color: #28a745; margin-bottom: 10px;">
                        <strong>✓ Réponse de référence actuelle:</strong> ${referenceAnswerText}
                    </p>
                ` : `
                    <p style="font-size: 13px; color: #dc3545; margin-bottom: 10px;">
                        <strong>⚠️ Aucune réponse de référence trouvée.</strong>
                        Vous pouvez quand même évaluer, mais vous devrez fournir une réponse de référence.
                    </p>
                `}
                <textarea 
                    id="reference-answer-${question.question_id}" 
                    class="evaluation-textarea" 
                    placeholder="${hasReferenceAnswer ? 'Modifiez la réponse de référence si nécessaire...' : 'Saisissez une réponse de référence ici (optionnel)...'}"
                    rows="2"
                    style="margin-bottom: 10px; ${hasReferenceAnswer ? 'background: #e8f5e9;' : 'background: #fff3cd;'}"
                >${hasReferenceAnswer ? escapeHtml(referenceAnswerText) : ''}</textarea>
                
                <!-- Sélecteur de source de réponse -->
                <div class="evaluation-source-selector" style="margin: 10px 0;">
                    <label style="display: flex; align-items: center; gap: 10px; font-size: 14px;">
                        <input type="radio" name="eval-source-${question.question_id}" value="llm" 
                               checked onchange="switchEvaluationSource(${question.question_id}, 'llm')">
                        <span>Évaluer la <strong>réponse LLM</strong></span>
                    </label>
                    <label style="display: flex; align-items: center; gap: 10px; font-size: 14px; margin-left: 20px;">
                        <input type="radio" name="eval-source-${question.question_id}" value="user" 
                               onchange="switchEvaluationSource(${question.question_id}, 'user')">
                        <span>Évaluer une <strong>réponse utilisateur</strong></span>
                    </label>
                </div>
                
                <input type="hidden" id="eval-source-${question.question_id}" value="llm">
                
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
                </div>
                <div class="evaluation-result" id="eval-result-${question.question_id}" style="display: none;">
                    <p><strong>Score:</strong> <span id="score-${question.question_id}" class="score-display"></span>/10</p>
                    <p><strong>Feedback:</strong> <span id="feedback-${question.question_id}"></span></p>
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

        return `
            <div class="question-card" data-question-id="${question.question_id}" data-chunk-id="${question.chunk_id || ''}">
                <div class="question-header">
                    <div class="question-content">
                        <strong>Q:</strong> ${marked.parse(question.content)}
                    </div>
                </div>
                
                <div class="question-meta">
                    <span class="badge ${badgeClass}">${question.status}</span>
                    <span class="difficulty">
                        <span class="difficulty-stars">${stars}</span>
                        <span>Niveau ${question.difficulty_level}</span>
                    </span>
                    ${question.created_by ? `<span style="font-size: 12px; color: #999;">Créé par: ${question.created_by}</span>` : ''}
                </div>
                
                <div class="question-info">
                    <span class="info-item" title="Identifiant de la question">
                        <strong>ID:</strong> ${question.question_id}
                    </span>
                    ${question.chunk_id ? `<span class="info-item" title="Identifiant du chunk">
                        <strong>Chunk:</strong> ${question.chunk_id}
                    </span>` : ''}
                    ${question.page ? `<span class="info-item" title="Page du document">
                        <strong>Page:</strong> ${question.page}
                    </span>` : ''}
                    ${question.page_number ? `<span class="info-item" title="Page du document">
                        <strong>Page:</strong> ${question.page_number}
                    </span>` : ''}
                    ${question.num_page ? `<span class="info-item" title="Page du document">
                        <strong>Page:</strong> ${question.num_page}
                    </span>` : ''}
                </div>
                
                ${answersHtml}
                ${chunkInfo}
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
    }).join('');

    contentElement.innerHTML = headerHtml + questionsHtml;
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
 * Bascule entre l'évaluation de la réponse LLM et une réponse utilisateur
 * @param {number} questionId - ID de la question
 * @param {string} source - Source de la réponse ('llm' ou 'user')
 */
function switchEvaluationSource(questionId, source) {
    const textarea = document.getElementById(`answer-to-evaluate-${questionId}`);
    const llmAnswer = textarea.dataset.llmAnswer || '';
    const hiddenInput = document.getElementById(`eval-source-${questionId}`);
    const resultDiv = document.getElementById(`eval-result-${questionId}`);
    const statusElement = document.getElementById(`eval-status-${questionId}`);
    
    if (source === 'llm') {
        textarea.value = llmAnswer;
        textarea.readOnly = true;
        textarea.style.backgroundColor = '#f8f9fa';
    } else {
        textarea.value = '';
        textarea.readOnly = false;
        textarea.style.backgroundColor = '';
    }
    
    if (hiddenInput) {
        hiddenInput.value = source;
    }
    
    // Effacer les résultats d'évaluation précédents quand on change de source
    if (resultDiv) {
        resultDiv.style.display = 'none';
    }
    if (statusElement) {
        statusElement.innerHTML = '';
    }
    
    // Réinitialiser les métadonnées d'évaluation
    const scoreElement = document.getElementById(`score-${questionId}`);
    if (scoreElement) {
        scoreElement.dataset.evaluationType = '';
        scoreElement.dataset.modelUsed = '';
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
 * Évalue une réponse par rapport à la réponse de référence
 * @param {number} questionId - ID de la question
 */
async function evaluateAnswer(questionId) {
    const answerTextarea = document.getElementById(`answer-to-evaluate-${questionId}`);
    const userAnswer = answerTextarea.value.trim();
    
    if (!userAnswer) {
        alert('Veuillez entrer une réponse à évaluer');
        return;
    }

    // Récupérer la réponse de référence
    let expectedAnswer = '';
    const hasReference = document.querySelector(`[data-question-id="${questionId}"]`)?.dataset.hasReference === 'true';
    
    if (hasReference && referenceAnswers[questionId]) {
        expectedAnswer = referenceAnswers[questionId].response_answer;
    } else {
        // Essayer de récupérer depuis le champ de référence
        const refAnswerTextarea = document.getElementById(`reference-answer-${questionId}`);
        if (refAnswerTextarea) {
            expectedAnswer = refAnswerTextarea.value.trim();
        }
    }
    
    if (!expectedAnswer) {
        alert('Veuillez fournir une réponse de référence pour évaluer. Vous pouvez en saisir une dans le champ prévus à cet effet.');
        return;
    }

    // Récupérer la question depuis le DOM
    const questionCard = document.querySelector(`[data-question-id="${questionId}"]`);
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
        console.log(`Évaluation: questionId=${questionId}, question="${questionText}", expected="${expectedAnswer.substring(0,50)}...", user="${userAnswer.substring(0,50)}..."`);
        const response = await fetch('/api/evaluate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: questionText,
                expected_answer: expectedAnswer,
                user_answer: userAnswer
            })
        });

        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const evaluation = await response.json();
        
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
        
        // Stocker les résultats pour la sauvegarde
        if (scoreElement) {
            scoreElement.dataset.evaluationType = 'auto';
            scoreElement.dataset.modelUsed = 'mistral-small';
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
