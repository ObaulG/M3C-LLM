const API_BASE = window.location.origin;
        const KNOWLEDGE_API = API_BASE + '/api/admin/knowledge-items';
        const DOCUMENTS_API = API_BASE + '/api/documents';
        const QUESTIONS_API = API_BASE + '/api/admin/questions';
        let currentDocumentId = null;
        let currentChunkId = null;
        let currentChunkContent = null;
        let currentChunkQuestions = [];
        let generatedItems = [];
        let generatedItemsFromQuestions = [];

        // === Initialisation ===
        document.addEventListener('DOMContentLoaded', loadInitialData);

        async function loadInitialData() {
            renderGeneratedItems([], 'knowledgeItemsContainer');
            renderGeneratedItems([], 'knowledgeItemsFromQuestionsContainer');
            updateColumnButtons();
            await Promise.all([loadValidDocuments(), loadSavedKnowledgeItems()]);
        }

        // === Documents validés ===
        async function loadValidDocuments() {
            try {
                const response = await fetch(KNOWLEDGE_API + '/valid-documents');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();

                document.getElementById('validDocsCount').textContent = data.count;

                const docsList = document.getElementById('validDocumentsList');
                if (!data.documents || data.documents.length === 0) {
                    docsList.innerHTML = '<span>Aucun document validé</span>';
                } else {
                    docsList.innerHTML = data.documents.map(doc =>
                        `<span>• ${escapeHtml(doc.title)} (Doc: ${doc.document_id}, Resource: ${doc.resource_id})</span>`
                    ).join('');
                }

                const docSelect = document.getElementById('documentSelect');
                let options = '<option value="">-- Sélectionnez un document --</option>';
                data.documents.forEach(doc => {
                    options += `<option value="${doc.document_id}">${escapeHtml(doc.title)} (Doc: ${doc.document_id})</option>`;
                });
                docSelect.innerHTML = options;
                docSelect.onchange = async function() {
                    currentDocumentId = this.value ? parseInt(this.value) : null;
                    await loadChunksForDocument(currentDocumentId);
                };
                resetChunkSelector();
            } catch (error) {
                console.error('Erreur chargement documents:', error);
                document.getElementById('validDocumentsList').innerHTML =
                    '<span style="color:#dc3545;">Erreur de chargement</span>';
            }
        }

        // === Chunks d'un document ===
        async function loadChunksForDocument(documentId) {
            const chunkSelect = document.getElementById('chunkSelect');
            const chunkContentDisplay = document.getElementById('chunkContentDisplay');

            if (!documentId) {
                resetChunkSelector();
                return;
            }

            try {
                chunkSelect.disabled = true;
                chunkSelect.innerHTML = '<option value="">Chargement des chunks...</option>';
                chunkContentDisplay.textContent = 'Chargement des chunks...';

                const response = await fetch(`${DOCUMENTS_API}/${documentId}/chunks`);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();

                if (data.chunks && data.chunks.length > 0) {
                    let options = '<option value="">-- Sélectionnez un chunk --</option>';
                    data.chunks.forEach(chunk => {
                        const preview = (chunk.content || '').substring(0, 80).replace(/\s+/g, ' ');
                        const displayText = `Chunk ${chunk.id} - Page ${chunk.num_page || 'N/A'} - ${preview}...`;
                        const encodedContent = encodeURIComponent(chunk.content || '');
                        options += `<option value="${chunk.id}" data-content="${encodedContent}">${escapeHtml(displayText)}</option>`;
                    });
                    chunkSelect.innerHTML = options;
                    chunkSelect.disabled = false;
                    chunkContentDisplay.textContent = 'Sélectionnez un chunk pour afficher son contenu...';

                    chunkSelect.onchange = function() {
                        console.log("Chunk sélectionné:", chunkSelect.value);
                        const selectedOption = this.options[this.selectedIndex];
                        const content = selectedOption ? selectedOption.dataset.content : null;
                        currentChunkId = chunkSelect.value;
                        if (currentChunkId) {
                            currentChunkContent = decodeURIComponent(content);
                            chunkContentDisplay.textContent = currentChunkContent;
                        } else {
                            currentChunkContent = null;
                            chunkContentDisplay.textContent = 'Sélectionnez un chunk pour afficher son contenu...';
                        }
                        loadChunkQuestions(currentChunkId);
                    };
                } else {
                    chunkSelect.innerHTML = '<option value="">Aucun chunk disponible</option>';
                    chunkSelect.disabled = true;
                    chunkContentDisplay.textContent = 'Aucun chunk trouvé pour ce document.';
                }
            } catch (error) {
                console.error('Erreur chargement chunks:', error);
                chunkSelect.innerHTML = '<option value="">Erreur de chargement</option>';
                chunkSelect.disabled = true;
                chunkContentDisplay.textContent = 'Erreur lors du chargement des chunks.';
            }
        }

        function resetChunkSelector() {
            const chunkSelect = document.getElementById('chunkSelect');
            const chunkContentDisplay = document.getElementById('chunkContentDisplay');
            chunkSelect.innerHTML = '<option value="">Sélectionnez un document d\'abord</option>';
            chunkSelect.disabled = true;
            chunkContentDisplay.textContent = 'Sélectionnez un document puis un chunk...';
            chunkSelect.onchange = null;
            currentChunkId = null;
            currentChunkContent = null;
            resetChunkQuestions();
        }

        function resetChunkQuestions() {
            currentChunkQuestions = [];
            document.getElementById('chunkQuestionsContainer').innerHTML =
                '<p style="color:#888; font-size:13px;">Sélectionnez un chunk pour afficher les questions/réponses associées...</p>';
        }

        // === Questions/Réponses associées au chunk ===
        async function loadChunkQuestions(chunkId) {
            const container = document.getElementById('chunkQuestionsContainer');
            if (!chunkId) {
                resetChunkQuestions();
                return;
            }
            container.innerHTML = '<p style="color:#888; font-size:13px;">Chargement des questions...</p>';
            try {
                const response = await fetch(`${QUESTIONS_API}/chunk/${chunkId}`);
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();
                currentChunkQuestions = data.questions || [];
                renderChunkQuestions(currentChunkQuestions, data.count || 0);
            } catch (error) {
                console.error('Erreur chargement questions du chunk:', error);
                container.innerHTML = '<p style="color:#dc3545; font-size:13px;">Erreur lors du chargement des questions.</p>';
            }
        }

        function renderChunkQuestions(questions, count) {
            const container = document.getElementById('chunkQuestionsContainer');
            if (!questions || questions.length === 0) {
                container.innerHTML = '<p style="color:#888; font-size:13px;">Aucune question associée à ce chunk.</p>';
                return;
            }

            let html = `<div style="font-size:13px; color:#666; margin-bottom:10px;">${count} question(s) associée(s) à ce chunk</div>`;
            html += questions.map(question => {
                let badgeClass = 'q-badge-other';
                if (question.status === 'validated') badgeClass = 'q-badge-validated';
                else if (question.status === 'pending') badgeClass = 'q-badge-pending';
                else if (question.status === 'generated') badgeClass = 'q-badge-generated';

                const stars = getDifficultyStars(question.difficulty_level);

                const answersHtml = (question.answers && question.answers.length > 0) ? `
                    <div class="answers-section">
                        <div class="answers-title">Réponses (${question.answers.length})</div>
                        ${question.answers.map((answer, index) => `
                            <div class="answer-item">
                                <strong>Réponse ${index + 1}:</strong> ${escapeHtml(answer.content)}
                                ${answer.is_correct ? '<span style="color:#28a745; margin-left:10px;">✓ Correcte</span>' : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : '<div class="answers-section"><div class="answers-title">Aucune réponse enregistrée</div></div>';

                return `
                    <div class="question-card">
                        <div class="q-content"><strong>Q:</strong> ${escapeHtml(question.content)}</div>
                        <div class="q-meta">
                            <span class="q-badge ${badgeClass}">${escapeHtml(question.status || 'inconnu')}</span>
                            <span class="q-difficulty">
                                <span class="q-difficulty-stars">${stars}</span>
                                <span>Niveau ${question.difficulty_level != null ? question.difficulty_level : '-'}</span>
                            </span>
                            ${question.created_by ? `<span style="font-size:12px; color:#999;">Créé par: ${escapeHtml(question.created_by)}</span>` : ''}
                        </div>
                        <div class="q-info">
                            <span class="q-info-item"><strong>ID:</strong> ${question.question_id}</span>
                        </div>
                        ${answersHtml}
                    </div>
                `;
            }).join('');
            container.innerHTML = html;
        }

        function getDifficultyStars(level) {
            const fullStar = '★';
            const emptyStar = '☆';
            if (level === null || level === undefined) return fullStar.repeat(3);
            return fullStar.repeat(level) + emptyStar.repeat(5 - level);
        }

        // === Génération via LLM (depuis le chunk) ===
        async function generateKnowledgeItems() {
            if (!currentChunkId) {
                showAlert('Veuillez sélectionner un document et un chunk.', 'error');
                return;
            }

            const model = document.getElementById('modelSelect').value;
            const generateBtn = document.getElementById('generateBtn');

            generateBtn.disabled = true;
            generateBtn.textContent = 'Génération en cours...';
            document.getElementById('loadingIndicator').classList.add('active');
            document.getElementById('resultsSection').style.display = 'block';

            try {
                const response = await fetch(KNOWLEDGE_API + '/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chunk_id: currentChunkId,
                        document_id: currentDocumentId,
                        model: model
                    })
                });

                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error('HTTP ' + response.status + ' : ' + errText);
                }
                const data = await response.json();
                generatedItems = data.knowledge_items || [];

                document.getElementById('chunkColMeta').textContent =
                    `${data.count} item(s) — ${data.model} — ${data.generation_time}s`;

                renderGeneratedItems(generatedItems, 'knowledgeItemsContainer');
                document.getElementById('resultsSection').style.display = 'block';
                updateColumnButtons();

                if (generatedItems.length === 0) {
                    showAlert('Aucun knowledge_item extrait du chunk.', 'error');
                } else {
                    showAlert(`${generatedItems.length} knowledge_items générés depuis le chunk.`, 'success');
                }
            } catch (error) {
                console.error('Erreur génération:', error);
                showAlert('Erreur lors de la génération : ' + error.message, 'error');
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = '✨ Générer depuis le chunk';
                document.getElementById('loadingIndicator').classList.remove('active');
            }
        }

        // === Génération via LLM (depuis les questions/réponses) ===
        async function generateKnowledgeItemsFromQuestions() {
            if (!currentChunkId) {
                showAlert('Veuillez sélectionner un document et un chunk.', 'error');
                return;
            }
            if (!currentChunkQuestions || currentChunkQuestions.length === 0) {
                showAlert('Aucune question/réponse associée à ce chunk. Générez ou associez d\'abord des questions.', 'error');
                return;
            }

            const qaItems = currentChunkQuestions.map(q => ({
                question_id: q.question_id,
                question: q.content,
                answers: (q.answers || []).map(a => a.content).filter(c => c),
            }));

            if (!qaItems.some(qa => qa.answers.length > 0)) {
                showAlert('Aucune réponse enregistrée pour les questions de ce chunk.', 'error');
                return;
            }

            const model = document.getElementById('modelSelect').value;
            const generateBtn = document.getElementById('generateFromQuestionsBtn');

            generateBtn.disabled = true;
            generateBtn.textContent = 'Génération en cours...';
            document.getElementById('loadingIndicator').classList.add('active');
            document.getElementById('resultsSection').style.display = 'block';

            try {
                const response = await fetch(KNOWLEDGE_API + '/generate-from-questions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chunk_id: currentChunkId,
                        document_id: currentDocumentId,
                        qa_items: qaItems,
                        model: model
                    })
                });

                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error('HTTP ' + response.status + ' : ' + errText);
                }
                const data = await response.json();
                generatedItemsFromQuestions = data.knowledge_items || [];

                document.getElementById('questionsColMeta').textContent =
                    `${data.count} item(s) — ${data.model} — ${data.generation_time}s`;

                renderGeneratedItems(generatedItemsFromQuestions, 'knowledgeItemsFromQuestionsContainer');
                document.getElementById('resultsSection').style.display = 'block';
                updateColumnButtons();

                if (generatedItemsFromQuestions.length === 0) {
                    showAlert('Aucun knowledge_item extrait des questions/réponses.', 'error');
                } else {
                    showAlert(`${generatedItemsFromQuestions.length} knowledge_items générés depuis les questions/réponses.`, 'success');
                }
            } catch (error) {
                console.error('Erreur génération depuis questions:', error);
                showAlert('Erreur lors de la génération : ' + error.message, 'error');
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = '✨ Générer depuis les questions';
                document.getElementById('loadingIndicator').classList.remove('active');
            }
        }

        function renderGeneratedItems(items, containerId) {
            const container = document.getElementById(containerId);
            if (!items || items.length === 0) {
                container.innerHTML = '<p class="compare-empty">Aucun knowledge_item généré.</p>';
                return;
            }

            container.innerHTML = items.map((item, idx) => {
                const entities = (item.entities || []).map(e =>
                    `<span class="badge badge-entity">${escapeHtml(e.name)} (${e.type})</span>`
                ).join('');
                const themes = (item.themes || []).map(t =>
                    `<span class="badge badge-theme">${escapeHtml(t.name)}</span>`
                ).join('');
                const src = item.source_reference || {};
                const sourceHtml = src.excerpt ?
                    `<div class="ki-source">📖 ${escapeHtml(src.excerpt.substring(0, 300))}${src.excerpt.length > 300 ? '...' : ''}` +
                    `${src.page != null ? ` <br>(page ${src.page})` : ''}</div>` : '';

                return `
                    <div class="knowledge-card">
                        <div class="ki-proposition">${idx + 1}. ${escapeHtml(item.proposition)}</div>
                        ${item.summary ? `<div class="ki-summary">"${escapeHtml(item.summary)}"</div>` : ''}
                        <div class="ki-meta">
                            <span class="badge badge-confidence">confiance: ${item.confidence}</span>
                            ${entities}
                            ${themes}
                        </div>
                        ${sourceHtml}
                        <label style="display:flex; align-items:center; gap:8px; margin-top:10px; font-size:13px;">
                            <input type="checkbox" data-idx="${idx}" data-col="${containerId}" checked> Inclure dans la sauvegarde
                        </label>
                    </div>
                `;
            }).join('');
        }

        function clearGeneratedItems(mode) {
            if (mode === 'questions') {
                generatedItemsFromQuestions = [];
                document.getElementById('knowledgeItemsFromQuestionsContainer').innerHTML = '';
                document.getElementById('questionsColMeta').textContent = '';
            } else {
                generatedItems = [];
                document.getElementById('knowledgeItemsContainer').innerHTML = '';
                document.getElementById('chunkColMeta').textContent = '';
                document.getElementById('alertContainer').innerHTML = '';
                const genMeta = document.getElementById('generationMeta');
                if (genMeta) genMeta.textContent = '';
            }
            updateColumnButtons();
            if (generatedItems.length === 0 && generatedItemsFromQuestions.length === 0) {
                document.getElementById('resultsSection').style.display = 'none';
            }
        }

        function updateColumnButtons() {
            document.getElementById('saveBtn').disabled = generatedItems.length === 0;
            document.getElementById('clearBtn').disabled = generatedItems.length === 0;
            document.getElementById('saveFromQuestionsBtn').disabled = generatedItemsFromQuestions.length === 0;
            document.getElementById('clearFromQuestionsBtn').disabled = generatedItemsFromQuestions.length === 0;
        }

        // === Sauvegarde en base ===
        async function saveAllKnowledgeItems(mode) {
            const containerId = mode === 'questions' ? 'knowledgeItemsFromQuestionsContainer' : 'knowledgeItemsContainer';
            const items = mode === 'questions' ? generatedItemsFromQuestions : generatedItems;

            if (items.length === 0) {
                showAlert('Aucun knowledge_item à sauvegarder.', 'error');
                return;
            }

            // Filtrer selon les cases cochées de la colonne concernée
            const checkboxes = document.querySelectorAll(`#${containerId} input[type="checkbox"]`);
            const selectedItems = [];
            checkboxes.forEach(cb => {
                if (cb.checked) {
                    selectedItems.push(items[parseInt(cb.dataset.idx)]);
                }
            });

            if (selectedItems.length === 0) {
                showAlert('Aucun knowledge_item sélectionné pour la sauvegarde.', 'error');
                return;
            }

            const saveBtn = document.getElementById(mode === 'questions' ? 'saveFromQuestionsBtn' : 'saveBtn');
            const originalText = saveBtn.textContent;
            saveBtn.disabled = true;
            saveBtn.textContent = 'Sauvegarde en cours...';

            try {
                const response = await fetch(KNOWLEDGE_API + '/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        knowledge_items: selectedItems,
                        chunk_id: currentChunkId,
                        document_id: currentDocumentId,
                        resource_type: mode === 'questions' ? 'questions' : 'chunk'
                    })
                });

                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error('HTTP ' + response.status + ' : ' + errText);
                }

                const data = await response.json();
                if (data.success) {
                    showAlert(`${data.count} knowledge_items sauvegardés (resource_id=${data.resource_id}). ${data.message}`, 'success');
                    await loadSavedKnowledgeItems();
                } else {
                    showAlert('Échec de la sauvegarde.', 'error');
                }
            } catch (error) {
                console.error('Erreur sauvegarde:', error);
                showAlert('Erreur lors de la sauvegarde : ' + error.message, 'error');
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = originalText;
                updateColumnButtons();
            }
        }

        // === Knowledge items déjà en base ===
        async function loadSavedKnowledgeItems() {
            const container = document.getElementById('savedItemsContainer');
            try {
                const response = await fetch(KNOWLEDGE_API + '/items?limit=50');
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();

                document.getElementById('knowledgeItemsCount').textContent = data.count;

                if (!data.knowledge_items || data.knowledge_items.length === 0) {
                    container.innerHTML = '<p style="color:#666; padding:20px;">Aucun knowledge_item en base pour le moment.</p>';
                    return;
                }

                container.innerHTML = data.knowledge_items.map(item => {
                    const entities = (item.entities || []).map(e =>
                        `<span class="badge badge-entity">${escapeHtml(e.name)}</span>`
                    ).join('');
                    const themes = (item.themes || []).map(t =>
                        `<span class="badge badge-theme">${escapeHtml(t.name)}</span>`
                    ).join('');
                    const verified = item.is_verified ? '<span class="badge badge-confidence">vérifié</span>' : '';
                    return `
                        <div class="knowledge-card">
                            <div class="ki-proposition">#${item.id} — ${escapeHtml(item.proposition)}</div>
                            ${item.summary ? `<div class="ki-summary">"${escapeHtml(item.summary)}"</div>` : ''}
                            <div class="ki-meta">${verified} ${entities} ${themes}</div>
                        </div>
                    `;
                }).join('');
            } catch (error) {
                console.error('Erreur chargement knowledge_items en base:', error);
                container.innerHTML = '<p style="color:#dc3545; padding:20px;">Erreur de chargement (base peut être vide ou inaccessible).</p>';
            }
        }

        // === Utilitaires ===
        function showAlert(message, type) {
            console.log("Error:", message);
            const container = document.getElementById('alertContainer');
            const cls = type === 'success' ? 'alert-success' : 'alert-error';
            container.innerHTML = `<div class="alert ${cls}">${escapeHtml(message)}</div>`;
        }

        function escapeHtml(str) {
            if (str == null) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

document.addEventListener("DOMContentLoaded", function () {
    loadModelsIntoSelect(document.getElementById("modelSelect"), { providers: ["mistral"], selected: "mistral-medium" });
  });
