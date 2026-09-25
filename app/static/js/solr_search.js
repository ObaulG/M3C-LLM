// État de l'application
        let currentState = {
            query: '',
            rows: 25,
            start: 0,
            filters: [],
            sort: '',
            numFound: 0,
            results: []
        };

        // Liste des champs Solr courants (à adapter selon votre schéma)
        const solrFields = [
            'id',
            'title',
            'content',
            'author',
            'type',
            'date',
            'file_name',
            'file_path',
            'document_id',
            'resource_id',
            'chunk_text',
            'extracted_text'
        ];

        // Initialisation
        document.addEventListener('DOMContentLoaded', function() {
            updateFiltersDisplay();
        });

        // Effectue la recherche
        function performSearch() {
            currentState.query = document.getElementById('searchInput').value;
            currentState.start = 0;
            currentState.filters = getFiltersFromDOM();
            currentState.sort = document.getElementById('sortSelect').value;
            
            if (!currentState.query || currentState.query.trim() === '') {
                alert('Veuillez entrer une requête de recherche');
                return;
            }

            executeSearch();
        }

        // Exécute la requête Solr via l'API
        async function executeSearch() {
            showLoading(true);
            document.getElementById('searchButton').disabled = true;
            
            try {
                const response = await fetch('/api/solr/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: currentState.query,
                        rows: currentState.rows,
                        start: currentState.start,
                        filters: formatFiltersForSolr(currentState.filters),
                        sort: currentState.sort,
                        fields: ['id', 'title', 'content', 'author', 'type', 'file_name', 'score']
                    })
                });

                if (!response.ok) {
                    throw new Error(`Erreur HTTP: ${response.status}`);
                }

                const data = await response.json();
                
                if (data.error) {
                    throw new Error(data.error);
                }

                currentState.numFound = data.num_found;
                currentState.results = data.results;
                
                displayResults();
                
            } catch (error) {
                console.error('Erreur lors de la recherche:', error);
                showError('Une erreur est survenue: ' + error.message);
            } finally {
                showLoading(false);
                document.getElementById('searchButton').disabled = false;
            }
        }

        // Formate les filtres pour Solr
        function formatFiltersForSolr(filters) {
            const formatted = {};
            filters.forEach(f => {
                if (f.field && f.value) {
                    formatted[f.field] = f.value;
                }
            });
            return formatted;
        }

        // Récupère les filtres du DOM
        function getFiltersFromDOM() {
            const filters = [];
            const filterRows = document.querySelectorAll('.filter-row');
            filterRows.forEach(row => {
                const fieldSelect = row.querySelector('select');
                const valueInput = row.querySelector('input[type="text"]');
                if (fieldSelect && valueInput && valueInput.value.trim() !== '') {
                    filters.push({
                        field: fieldSelect.value,
                        value: valueInput.value
                    });
                }
            });
            return filters;
        }

        // Affiche les résultats
        function displayResults() {
            const resultsList = document.getElementById('resultsList');
            const resultsInfo = document.getElementById('resultsInfo');
            const noResults = document.getElementById('noResults');
            const pagination = document.getElementById('pagination');
            
            // Masquer les messages de "aucune requête"
            noResults.style.display = 'none';
            
            // Afficher l'info des résultats
            const start = currentState.start + 1;
            const end = Math.min(currentState.start + currentState.results.length, currentState.numFound);
            resultsInfo.textContent = `Affichage des résultats ${start} à ${end} sur ${currentState.numFound} trouvés en ${currentState.query_time || 0}ms`;
            resultsInfo.style.display = 'block';
            
            // Afficher les résultats
            if (currentState.results.length === 0) {
                resultsList.innerHTML = '<div class="no-results">Aucun résultat trouvé pour cette requête.</div>';
            } else {
                resultsList.innerHTML = currentState.results.map((result, index) => {
                    return createResultCard(result, index);
                }).join('');
            }
            
            // Afficher la pagination
            updatePagination();
        }

        // Crée une carte de résultat
        function createResultCard(result, index) {
            const score = result.score !== undefined ? `<span style="color: #b74420; font-weight: bold; font-size: 13px;">Score: ${result.score.toFixed(4)}</span>` : '';
            
            let content = '';
            for (const [key, value] of Object.entries(result)) {
                if (key === 'score') continue;
                if (value && typeof value === 'string') {
                    // Tronquer le contenu trop long
                    const displayValue = (key === 'content' || key === 'extracted_text' || key === 'chunk_text') 
                        ? value.substring(0, 200) + (value.length > 200 ? '...' : '')
                        : value;
                    content += `<div class="field-item"><span class="field-name">${escapeHtml(key)}:</span><span class="field-value">${escapeHtml(displayValue)}</span></div>`;
                } else if (Array.isArray(value)) {
                    content += `<div class="field-item"><span class="field-name">${escapeHtml(key)}:</span><span class="field-value">[${value.length} éléments]</span></div>`;
                } else if (value !== null && value !== undefined) {
                    content += `<div class="field-item"><span class="field-name">${escapeHtml(key)}:</span><span class="field-value">${escapeHtml(String(value))}</span></div>`;
                }
            }
            
            return `
                <div class="result-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <div class="result-title">Résultat #${index + 1}</div>
                        ${score}
                    </div>
                    <div class="result-fields">
                        ${content}
                    </div>
                </div>
            `;
        }

        // Met à jour la pagination
        function updatePagination() {
            const pagination = document.getElementById('pagination');
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            const pageInfo = document.getElementById('pageInfo');
            
            if (currentState.numFound === 0) {
                pagination.style.display = 'none';
                return;
            }
            
            pagination.style.display = 'flex';
            
            const totalPages = Math.ceil(currentState.numFound / currentState.rows);
            const currentPage = Math.floor(currentState.start / currentState.rows) + 1;
            
            pageInfo.textContent = `Page ${currentPage} sur ${totalPages}`;
            
            prevBtn.disabled = currentState.start === 0;
            nextBtn.disabled = currentState.start + currentState.rows >= currentState.numFound;
        }

        // Page précédente
        function prevPage() {
            if (currentState.start > 0) {
                currentState.start -= currentState.rows;
                if (currentState.start < 0) currentState.start = 0;
                executeSearch();
            }
        }

        // Page suivante
        function nextPage() {
            if (currentState.start + currentState.rows < currentState.numFound) {
                currentState.start += currentState.rows;
                executeSearch();
            }
        }

        // Met à jour le nombre de résultats par page
        function updateRows() {
            const rows = parseInt(document.getElementById('rowsSelect').value);
            if (!isNaN(rows)) {
                currentState.rows = rows;
                // Réinitialiser à la première page
                currentState.start = 0;
                if (currentState.query) {
                    executeSearch();
                }
            }
        }

        // Ajoute un filtre
        function addFilter() {
            const container = document.getElementById('filtersContainer');
            
            const filterRow = document.createElement('div');
            filterRow.className = 'filter-row';
            filterRow.innerHTML = `
                <select onchange="updateFiltersDisplay()">
                    ${solrFields.map(field => `<option value="${field}">${field}</option>`).join('')}
                </select>
                <input type="text" placeholder="Valeur..." onchange="updateFiltersDisplay()">
                <button class="remove-btn" onclick="removeFilter(this)">×</button>
            `;
            
            container.appendChild(filterRow);
        }

        // Supprime un filtre
        function removeFilter(button) {
            const filterRow = button.parentElement;
            filterRow.remove();
            updateFiltersDisplay();
        }

        // Met à jour l'affichage des filtres (rafraîchit la recherche si nécessaire)
        function updateFiltersDisplay() {
            const newFilters = getFiltersFromDOM();
            const filtersEqual = JSON.stringify(newFilters) === JSON.stringify(currentState.filters);
            
            if (!filtersEqual) {
                currentState.filters = newFilters;
                if (currentState.query) {
                    currentState.start = 0;
                    // Petits délai pour éviter les requêtes trop fréquentes
                    setTimeout(() => {
                        if (getFiltersFromDOM().length === newFilters.length) {
                            executeSearch();
                        }
                    }, 300);
                }
            }
        }

        // Affiche/Masque le chargement
        function showLoading(show) {
            const loading = document.getElementById('loadingIndicator');
            loading.style.display = show ? 'block' : 'none';
        }

        // Affiche une erreur
        function showError(message) {
            const resultsList = document.getElementById('resultsList');
            resultsList.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
            document.getElementById('resultsInfo').style.display = 'none';
            document.getElementById('pagination').style.display = 'none';
        }

        // Échappement HTML pour sécurité
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // ========================================================================
        // FONCTIONS D'INDEXATION SOLR
        // ========================================================================

        // Bascule entre les onglets
        function switchTab(tabName) {
            // Masquer tous les onglets
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });

            // Afficher l'onglet sélectionné
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
            
            // Charger les jobs si on passe à l'onglet indexation
            if (tabName === 'indexing') {
                loadJobs();
            }
        }

        // État pour l'indexation
        let indexingState = {
            jobs: [],
            currentJobId: null,
            isLoading: false
        };

        // Charge la liste des jobs
        async function loadJobs() {
            try {
                const response = await fetch('/api/solr/index/jobs');
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const data = await response.json();
                indexingState.jobs = data.jobs;
                displayJobs();
            } catch (error) {
                console.error('Erreur chargement jobs:', error);
                document.getElementById('jobsList').innerHTML = `
                    <div class="indexing-result error">
                        Erreur de chargement: ${escapeHtml(error.message)}
                    </div>
                `;
            }
        }

        // Affiche la liste des jobs
        function displayJobs() {
            const jobsList = document.getElementById('jobsList');
            
            if (indexingState.jobs.length === 0) {
                jobsList.innerHTML = '<div style="text-align: center; padding: 20px; color: #999;">Aucun job d\'indexation trouvé.</div>';
                return;
            }

            jobsList.innerHTML = indexingState.jobs.map(job => {
                const canCancel = job.status === 'pending' || job.status === 'running';
                const progressText = job.processed_items && job.total_items 
                    ? `(${job.processed_items}/${job.total_items} documents)`
                    : '';
                
                return `
                    <div class="job-card">
                        <div class="job-info">
                            <div class="job-id">Job: ${job.job_id.substring(0, 8)}...</div>
                            <div>
                                <span class="job-status ${job.status}">${job.status}</span>
                                <span class="job-progress">${progressText}</span>
                            </div>
                            <div style="font-size: 11px; color: #888; margin-top: 5px;">
                                Créé: ${new Date(job.created_at).toLocaleString('fr-FR')}
                                ${job.parameters.solr_core ? ` | Core: ${job.parameters.solr_core}` : ''}
                            </div>
                        </div>
                        <div class="job-actions">
                            <button class="job-action-btn" onclick="viewJobDetails('${job.job_id}')">Détails</button>
                            ${canCancel ? `<button class="job-action-btn danger" onclick="cancelJob('${job.job_id}')">Annuler</button>` : ''}
                            ${job.status === 'failed' ? `<button class="job-action-btn" onclick="retryJob('${job.job_id}')">Relancer</button>` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Lance un job d'indexation
        async function startIndexingJob() {
            const solrCore = document.getElementById('indexSolrCore').value;
            const batchSize = parseInt(document.getElementById('indexBatchSize').value);
            const commit = document.getElementById('indexCommit').checked;
            const clearIndex = document.getElementById('indexClearIndex').checked;
            
            const confirmClear = clearIndex ? confirm('⚠️ ATTENTION: Cela va SUPPRIMER tous les documents du core "' + solrCore + '". Voulez-vous continuer?') : true;
            
            if (!confirmClear) {
                return;
            }

            const startBtn = document.getElementById('startIndexingBtn');
            const resultDiv = document.getElementById('indexingResult');
            
            startBtn.disabled = true;
            startBtn.textContent = 'Lancement...';
            resultDiv.style.display = 'none';
            
            try {
                const response = await fetch('/api/solr/index/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        solr_core: solrCore,
                        batch_size: batchSize,
                        commit: commit,
                        clear_index: clearIndex
                    })
                });

                if (!response.ok) {
                    throw new Error(`Erreur HTTP: ${response.status}`);
                }

                const data = await response.json();
                
                if (!data.success) {
                    throw new Error(data.message || 'Erreur inconnue');
                }

                indexingState.currentJobId = data.job_id;
                
                // Afficher le résultat
                resultDiv.innerHTML = `
                    <strong>✅ Job lancé avec succès!</strong><br>
                    ID: ${data.job_id}<br>
                    Core: ${data.solr_core}<br>
                    Documents à indexer: ${data.total_items}
                `;
                resultDiv.className = 'indexing-result';
                resultDiv.style.display = 'block';
                
                // Charger les jobs après un délai
                setTimeout(loadJobs, 1000);
                
                // Suivre le job en temps réel
                followJobProgress(data.job_id);
                
            } catch (error) {
                console.error('Erreur lancement job:', error);
                resultDiv.innerHTML = `<strong>❌ Erreur:</strong> ${escapeHtml(error.message)}`;
                resultDiv.className = 'indexing-result error';
                resultDiv.style.display = 'block';
            } finally {
                startBtn.disabled = false;
                startBtn.textContent = 'Lancer l\'indexation';
            }
        }

        // Suivre la progression d'un job en temps réel (polling simple)
        function followJobProgress(jobId) {
            const checkJob = async () => {
                try {
                    const response = await fetch(`/api/solr/index/status/${jobId}`);
                    if (!response.ok) return;
                    
                    const data = await response.json();
                    
                    // Si le job est terminé, arrêter le suivi
                    if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
                        loadJobs();
                        return;
                    }
                    
                    // Sinon, continuer à vérifier
                    setTimeout(checkJob, 2000);
                    
                } catch (error) {
                    console.error('Erreur suivi job:', error);
                }
            };
            
            // Démarrer le suivi
            setTimeout(checkJob, 1000);
        }

        // Annule un job
        async function cancelJob(jobId) {
            if (!confirm('Voulez-vous vraiment annuler ce job?')) {
                return;
            }
            
            try {
                const response = await fetch(`/api/solr/index/${jobId}/cancel`, {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                if (data.success) {
                    showIndexingNotification('Job annulé avec succès', 'success');
                    loadJobs();
                } else {
                    showIndexingNotification(data.message || 'Erreur', 'error');
                }
            } catch (error) {
                console.error('Erreur annulation:', error);
                showIndexingNotification('Erreur: ' + error.message, 'error');
            }
        }

        // Affiche une notification pour l'indexation
        function showIndexingNotification(message, type = 'info') {
            const resultDiv = document.getElementById('indexingResult');
            resultDiv.innerHTML = `<strong>${type === 'success' ? '✅' : '❌'} ${type === 'success' ? 'Succès' : 'Erreur'}</strong>: ${escapeHtml(message)}`;
            resultDiv.className = type === 'success' ? 'indexing-result' : 'indexing-result error';
            resultDiv.style.display = 'block';
            
            // Masquer après 5 secondes
            setTimeout(() => {
                resultDiv.style.display = 'none';
            }, 5000);
        }

        // Affiche les détails d'un job
        async function viewJobDetails(jobId) {
            try {
                const response = await fetch(`/api/solr/index/status/${jobId}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                
                const details = `
                    <strong>Détails du job ${data.job_id.substring(0, 8)}...</strong><br><br>
                    Statut: <span class="job-status ${data.status}">${data.status}</span><br>
                    Type: ${data.job_type}<br>
                    Core: ${data.parameters.solr_core || 'm3c'}<br>
                    Batch size: ${data.parameters.batch_size || 50}<br>
                    Commit: ${data.parameters.commit ? 'Oui' : 'Non'}<br>
                    Clear index: ${data.parameters.clear_index ? 'Oui' : 'Non'}<br><br>
                    Progression: ${data.processed_items || 0}/${data.total_items || 0} documents<br>
                    Créé: ${new Date(data.created_at).toLocaleString('fr-FR')}<br>
                    Mis à jour: ${new Date(data.updated_at).toLocaleString('fr-FR')}
                    ${data.error_message ? `<br><br><strong>Erreur:</strong> ${escapeHtml(data.error_message)}` : ''}
                `;
                
                const resultDiv = document.getElementById('indexingResult');
                resultDiv.innerHTML = details;
                resultDiv.className = 'indexing-result';
                resultDiv.style.display = 'block';
                
            } catch (error) {
                console.error('Erreur détails job:', error);
                showIndexingNotification('Erreur: ' + error.message, 'error');
            }
        }

        // Relance un job échoué
        async function retryJob(jobId) {
            if (!confirm('Voulez-vous relancer ce job?')) {
                return;
            }
            
            try {
                // Récupérer les paramètres du job existant
                const response = await fetch(`/api/solr/index/status/${jobId}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const oldJob = await response.json();
                
                // Lancer un nouveau job avec les mêmes paramètres
                const newResponse = await fetch('/api/solr/index/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(oldJob.parameters)
                });
                
                if (!newResponse.ok) {
                    throw new Error(`HTTP ${newResponse.status}`);
                }
                
                const data = await newResponse.json();
                showIndexingNotification(`Nouveau job lancé: ${data.job_id}`, 'success');
                loadJobs();
                
            } catch (error) {
                console.error('Erreur relancement job:', error);
                showIndexingNotification('Erreur: ' + error.message, 'error');
            }
        }

        // Initialisation: charger les jobs au démarrage
        document.addEventListener('DOMContentLoaded', function() {
            updateFiltersDisplay();
            // Charger les jobs si on est sur l'onglet indexation
            // (sera chargé quand on cliquera sur l'onglet)
        });
