
/**
 * Crée une div pour le contenu du message
 * @returns {HTMLElement}
 */
function createDivWithClass(className) {
    const contentDiv = document.createElement('div');
    contentDiv.className = className;
    return contentDiv;
}

/**
 * Crée le conteneur principal d'un message
 * @param {string} type - Type de message (ex: 'user', 'bot', 'error', 'info').
 * @returns {HTMLElement}
 */
function createMessageContainer(type) {
    return createDivWithClass(`message ${type}`);
}


/**
 * Crée une div représentant un message dans une interface de chat.
 *
 * @param {string} text - Le contenu textuel du message à afficher.
 * @param {string} type - Le type de message (ex: 'user', 'bot', 'error', 'info').
 *                        Ce paramètre est utilisé pour appliquer une classe CSS spécifique au message.
 * @returns {HTMLElement} - L'élément DOM div représentant le message, prêt à être inséré dans le DOM.
 *
 */
function createMessageDiv(text, type) {
    const messageDiv = createMessageContainer(type);

    const contentDiv = createDivWithClass('message-content');
    contentDiv.textContent = text;

    messageDiv.appendChild(contentDiv);
    return messageDiv;
}

/**
 * Crée l'en-tête d'une réponse LLM, contenant entre autres le modèle utilisé,
 * le temps de réponse, le nombre de tokens consommés, et si possible,
 * la consommation énergétique de la requête
 * @param {Object} response - Réponse d'un modèle LLM
 * @returns {HTMLElement}
 */
function createResponseHeader(response) {
    const header = document.createElement('div');
    header.className = 'bot-response-header';

    const model = response.metadata?.model;
    const totalTime = response.total_time;
    const inputTokens = response.metadata?.token_usage?.input_tokens;
    const outputTokens = response.metadata?.token_usage?.output_tokens;
    const consumedEnergyWh = response.metadata?.consumed_energy_Wh;

    let parts = [];

    if (model) {
        parts.push(`<strong>Modèle :</strong> ${model}`);
    }

    if (totalTime !== undefined) {
        parts.push(`<strong>Temps :</strong> ${totalTime.toFixed(2)} sec`);
    }

    if (inputTokens !== undefined && outputTokens !== undefined) {
        parts.push(`<strong>Tokens :</strong> ${inputTokens} (in) / ${outputTokens} (out)`);
    }

    if (consumedEnergyWh !== undefined && consumedEnergyWh > 0.0) {
        parts.push(`<strong>Énergie :</strong> ${consumedEnergyWh.toFixed(3)} Wh`);
    }

    header.innerHTML = parts.join(' &nbsp;|&nbsp; ');

    return header;
}

/**
 * Crée l'en-tête d'une source
 * @param {Object} source - Source individuelle
 * @param {number} index - Index de la source
 * @returns {HTMLElement}
 */
function createSourceHeader(source, index) {
    const sourceHeader = createDivWithClass(`source-header`);

    const docName = source.metadata.nom || source.metadata.source || 'N/A';
    const pageNumber = source.metadata.num_page || '?';

    // Extract document title from document_data if available
    let documentTitle = 'N/A';
    if (source.metadata.document_data && source.metadata.document_data.file_name) {
        documentTitle = source.metadata.document_data.file_name;
    }

    sourceHeader.textContent = `${index + 1}. ${documentTitle} (page ${pageNumber}) (score: ${source.score_cossim.toFixed(3)})`;

    return sourceHeader;
}

/**
 * Crée une section pour afficher les sources d'une réponse
 * @param {Object} response - Réponse d'un modèle LLM
 * @returns {HTMLElement}
 */
function createSourcesSection(response) {
    const sourcesDiv = createDivWithClass('sources');
    sourcesDiv.innerHTML = '<strong>📚 Sources (' + response.sources.length + ') :</strong>';

    response.sources.forEach((source, index) => {
        const sourceItem = createSourceItem(source, index);
        sourcesDiv.appendChild(sourceItem);
    });

    return sourcesDiv;
}

/**
 * Crée un bouton pour afficher le PDF d'une source
 * @param {Object} source - Source individuelle
 * @param {string} route - la route sur laquelle effectuer la requête
 * @returns {HTMLElement}
 */
function createShowPdfButton(source) {
    const showPdfButton = createDivWithClass('show-pdf-button');
    showPdfButton.textContent = 'Afficher le PDF';

    showPdfButton.onclick = () => {
        // Try to get file name from document_data first, then fallback to existing metadata
        const fileName = source.metadata.document_data?.file_name ||
                        source.metadata.source || source.metadata.nom;
        if (fileName) {
            // Logique pour afficher le PDF (comme dans ton code original)
            const divIframe = document.getElementById("pdf-display");
            let pdfIframe = divIframe.querySelector('iframe');

            if (!pdfIframe) {
                pdfIframe = document.createElement('iframe');
                divIframe.appendChild(pdfIframe);
            }

            const numPage = source.metadata.num_page;
            const serverUrl = "http://localhost:8000";
            let pdfUrl = `${serverUrl}/get_pdf?document_id=${encodeURIComponent(fileName)}`;

            if (numPage !== undefined && numPage !== null) {
                pdfUrl += `#page=${numPage}`;
            }

            pdfIframe.src = pdfUrl;
            pdfIframe.width = '100%';
            pdfIframe.height = '100%';
            pdfIframe.style.border = 'none';
            divIframe.style.display = "flex";
        } else {
            alert("Le nom du fichier source n'est pas disponible.");
        }
    };

    return showPdfButton;
}

/**
 * Crée le contenu d'une source (extrait)
 * @param {Object} source - Source individuelle
 * @returns {HTMLElement}
 */
function createSourceContent(source) {
    const sourceContent = createDivWithClass('source-content');
    const preview = source.content.substring(0, 100) + '...';
    sourceContent.textContent = preview;

    return sourceContent;
}

/**
 * Crée un élément pour une source spécifique
 * @param {Object} source - Source individuelle
 * @param {number} index - Index de la source
 * @returns {HTMLElement}
 */
function createSourceItem(source, index) {
    const sourceItem = createDivWithClass('source-item');

    const sourceHeader = createSourceHeader(source, index);
    const sourceContent = createSourceContent(source);
    const showPdfButton = createShowPdfButton(source);

    sourceItem.appendChild(sourceHeader);
    sourceItem.appendChild(sourceContent);
    sourceItem.appendChild(showPdfButton);

    return sourceItem;
}

/**
 * Crée le contenu principal d'une réponse LLM avec support Markdown
 * @param {Object} response - Réponse d'un modèle LLM
 * @returns {HTMLElement}
 */
function createResponseContent(response) {
    console.log("Création de la zone de contenu pour la réponse");

    const content = createDivWithClass('bot-response-content');

    // selon la route, le message est contenu dans un de ces deux attributs
    const markdownContent = response.answer || response.message;
    console.log("llm correction of the question:  " + markdownContent);
    const htmlContent = marked.parse(markdownContent);
    content.innerHTML = htmlContent;

    if (response.sources && response.sources.length > 0) {
        const sourcesDiv = createSourcesSection(response);
        content.appendChild(sourcesDiv);
    }

    return content;
}


/**
 * Crée un conteneur d'onglets pour afficher les réponses de chaque modèle,
 * et le remplit à partir des réponses fournies.
 * @param {Array} responses - Tableau des réponses des modèles
 * @returns {HTMLElement}
 */
function createTabContainer(responses) {
    const tabContainer = createDivWithClass('tab-container');
    const tabHeader = createTabHeader(responses);
    const tabContents = createTabContents(responses);

    tabContainer.appendChild(tabHeader);
    tabContainer.appendChild(tabContents);

    return tabContainer;
}

/**
 * Crée l'en-tête des onglets avec les boutons de navigation
 * @param {Array} responses - Tableau des réponses des modèles
 * @returns {HTMLElement}
 */
function createTabHeader(responses) {
    const tabHeader = createDivWithClass('tab-header');

    responses.forEach((response, index) => {
        const tabButton = createTabButton(response.metadata.model, index);
        tabHeader.appendChild(tabButton);
    });

    return tabHeader;
}

/**
 * Crée un bouton d'onglet pour un modèle spécifique
 * @param {string} modelName - Nom du modèle
 * @param {number} index - Index de l'onglet
 * @returns {HTMLElement}
 */
function createTabButton(modelName, index) {
    const tabButton = createDivWithClass('tab-button');
    tabButton.textContent = modelName;
    tabButton.dataset.tabIndex = index;
    return tabButton;
}

/**
 * Crée les contenus des onglets pour chaque modèle
 * @param {Array} responses - Tableau des réponses des modèles
 * @returns {HTMLElement}
 */
function createTabContents(responses) {
    const tabContents = document.createElement('div');

    responses.forEach((response, index) => {
        const tabContent = createTabContent(response);
        tabContents.appendChild(tabContent);
    });

    return tabContents;
}

/**
 * Crée le contenu d'un onglet pour une réponse spécifique
 * @param {Object} response - Réponse d'un modèle LLM
 * @returns {HTMLElement}
 */
function createTabContent(response) {
    const tabContent = createDivWithClass('tab-content');

    const header = createResponseHeader(response);
    const content = createResponseContent(response);

    tabContent.appendChild(header);
    tabContent.appendChild(content);

    return tabContent;
}

/**
 * Active le premier onglet d'un conteneur d'onglets et configure les événements
 * @param {HTMLElement} tabContainer - Conteneur d'onglets
 */
function activateFirstTab(tabContainer) {
    const tabHeader = tabContainer.querySelector('.tab-header');
    const tabContents = tabContainer.querySelectorAll('.tab-content');
    const tabButtons = tabHeader.querySelectorAll('.tab-button');

    // Activer le premier onglet par défaut
    tabButtons[0].classList.add('active');
    tabContents[0].classList.add('active');

    // Configurer les événements de clic pour les onglets
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Désactiver tous les onglets
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Activer l'onglet cliqué
            button.classList.add('active');
            const tabIndex = button.dataset.tabIndex;
            tabContents[tabIndex].classList.add('active');
        });
    });
}

function createUserMessage(text) {
    const messageDiv = createDivWithClass('message user');
    const contentDiv = createDivWithClass('message-content');
    contentDiv.textContent = text;
    messageDiv.appendChild(contentDiv);
    return messageDiv;

}
/**
 * Crée le conteneur représentant la réponse d'un bot par la route query_simple,
 * qui retourne la réponse d'un seul LLM à une requête au format Markdown.
 */
function createBotResponse(data) {
    console.log(data);

    const messageDiv = createMessageContainer('bot');
    const contentDiv = createDivWithClass('message-content');

    const container = createDivWithClass("bot-response-container");

    const header = createResponseHeader(data);
    container.appendChild(header);
    contentDiv.appendChild(container);

    const content = createResponseContent(data);
    contentDiv.appendChild(content);

    messageDiv.appendChild(contentDiv);

    return messageDiv;

}


/**
 * Crée le conteneur de la réponse du serveur, contenant une réponse par LLM appelé.
 * La fonction crée le conteneur, les onglets, et remplit le contenu.
 * @param {Array} responses - Tableau des réponses des modèles LLM
 * @param {HTMLElement} chatContainer - Conteneur du chat où ajouter le message
 */
function createLLMResponsesTabs(responses, chatContainer) {
    const combinedMessageDiv = createMessageContainer('bot');
    const contentDiv = createDivWithClass('message-content');

    const tabContainer = createTabContainer(responses);
    contentDiv.appendChild(tabContainer);
    // Activer le premier onglet par défaut
    activateFirstTab(tabContainer);

    combinedMessageDiv.appendChild(contentDiv);
    return combinedMessageDiv;



}