// feedback.js
// Widget de retours utilisateurs sur les réponses du chatbot M3C.
//
// - Un bouton par réponse (ajouté dans chatFunctions.js) ouvre le panneau
//   latéral gauche avec le message_id correspondant.
// - Trois échelles 1-5 (étoiles) + un champ de commentaire libre.
// - Un seul feedback par message (contrainte BDD) : si un feedback existe déjà,
//   le widget se met en lecture seule après soumission.
//
// Dépend de chatFunctions.js (getAnonymousUserId).

const API_URL_FEEDBACK = 'http://localhost:8000/api/feedback';

// État courant du widget
let feedbackPanel = null;
let feedbackCurrentMessageId = null;
let feedbackSubmitted = false; // empêche la re-soumission côté client

// Libellés des trois échelles
const FEEDBACK_SCALES = [
    { key: 'rating_response',    label: 'La réponse vous convient-elle ?' },
    { key: 'rating_relevance',   label: 'Les documents fournis sont-ils pertinents par rapport à votre question ?' },
    { key: 'rating_formulation', label: 'Êtes-vous satisfait de la formulation de la réponse ?' },
];

/**
 * Ouvre le panneau de retours pour un message donné.
 * Charge l'éventuel feedback existant pour pré-remplir (lecture seule).
 * @param {string} messageId - UUID du message à commenter.
 */
async function openFeedbackPanel(messageId) {
    if (!messageId) {
        alert("Aucun identifiant de message associé à cette réponse (la persistance a peut-être échoué).");
        return;
    }
    feedbackCurrentMessageId = messageId;
    feedbackSubmitted = false;
    ensureFeedbackPanel();
    feedbackPanel.classList.add('open');
    resetFeedbackForm();

    // Tenter de charger un feedback existant
    try {
        const response = await fetch(`${API_URL_FEEDBACK}/${encodeURIComponent(messageId)}`);
        if (response.ok) {
            const existing = await response.json();
            prefillFeedbackForm(existing);
            setFeedbackReadOnly(true, "Vous avez déjà envoyé un retour pour cette réponse.");
            feedbackSubmitted = true;
        }
    } catch (error) {
        console.error("Erreur lors de la vérification du feedback existant:", error);
    }
}

/**
 * Ferme le panneau de retours.
 */
function closeFeedbackPanel() {
    if (feedbackPanel) {
        feedbackPanel.classList.remove('open');
    }
    feedbackCurrentMessageId = null;
    feedbackSubmitted = false;
}

/**
 * Crée le panneau s'il n'existe pas encore et l'ajoute au DOM.
 */
function ensureFeedbackPanel() {
    if (feedbackPanel && document.body.contains(feedbackPanel)) {
        return;
    }

    feedbackPanel = document.createElement('div');
    feedbackPanel.className = 'feedback-panel';
    feedbackPanel.setAttribute('role', 'dialog');
    feedbackPanel.setAttribute('aria-label', 'Retours sur la réponse');

    const header = document.createElement('div');
    header.className = 'feedback-panel-header';
    header.innerHTML = '<span>Retours sur la réponse</span>';
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'feedback-close-btn';
    closeBtn.textContent = '✕';
    closeBtn.setAttribute('aria-label', 'Fermer');
    closeBtn.onclick = closeFeedbackPanel;
    header.appendChild(closeBtn);
    feedbackPanel.appendChild(header);

    const body = document.createElement('div');
    body.className = 'feedback-panel-body';

    // Les trois échelles
    FEEDBACK_SCALES.forEach(scale => {
        const group = document.createElement('div');
        group.className = 'feedback-scale-group';
        group.dataset.scaleKey = scale.key;

        const label = document.createElement('div');
        label.className = 'feedback-scale-label';
        label.textContent = scale.label;
        group.appendChild(label);

        const stars = document.createElement('div');
        stars.className = 'feedback-stars';
        for (let i = 1; i <= 5; i++) {
            const star = document.createElement('button');
            star.type = 'button';
            star.className = 'feedback-star';
            star.dataset.value = String(i);
            star.textContent = '★';
            star.setAttribute('aria-label', `${i} sur 5`);
            star.onclick = () => selectStar(group, i);
            stars.appendChild(star);
        }
        group.appendChild(stars);
        body.appendChild(group);
    });

    // Champ de commentaire libre
    const commentLabel = document.createElement('label');
    commentLabel.className = 'feedback-comment-label';
    commentLabel.setAttribute('for', 'feedbackComment');
    commentLabel.textContent = 'Commentaire (facultatif) :';
    body.appendChild(commentLabel);

    const commentArea = document.createElement('textarea');
    commentArea.id = 'feedbackComment';
    commentArea.className = 'feedback-comment';
    commentArea.rows = 4;
    commentArea.maxLength = 2000;
    commentArea.placeholder = 'Écrivez vos remarques ici...';
    body.appendChild(commentArea);

    // Zone de message (confirmation / erreur)
    const message = document.createElement('div');
    message.className = 'feedback-message';
    message.id = 'feedbackMessage';
    body.appendChild(message);

    // Bouton d'envoi
    const submitBtn = document.createElement('button');
    submitBtn.type = 'button';
    submitBtn.className = 'btn btn-primary feedback-submit-btn';
    submitBtn.id = 'feedbackSubmitBtn';
    submitBtn.textContent = 'Envoyer le retour';
    submitBtn.onclick = submitFeedback;
    body.appendChild(submitBtn);

    feedbackPanel.appendChild(body);
    document.body.appendChild(feedbackPanel);

    // Overlay pour fermer au clic extérieur
    const overlay = document.createElement('div');
    overlay.className = 'feedback-overlay';
    overlay.id = 'feedbackOverlay';
    overlay.onclick = closeFeedbackPanel;
    document.body.appendChild(overlay);
}

/**
 * Réinitialise le formulaire (échelles à 0, commentaire vide, messages effacés).
 */
function resetFeedbackForm() {
    document.querySelectorAll('.feedback-scale-group').forEach(group => {
        group.dataset.value = '';
        group.querySelectorAll('.feedback-star').forEach(s => s.classList.remove('selected'));
    });
    const comment = document.getElementById('feedbackComment');
    if (comment) {
        comment.value = '';
        comment.disabled = false;
    }
    const msg = document.getElementById('feedbackMessage');
    if (msg) {
        msg.textContent = '';
        msg.className = 'feedback-message';
    }
    const btn = document.getElementById('feedbackSubmitBtn');
    if (btn) {
        btn.disabled = false;
        btn.textContent = 'Envoyer le retour';
    }
    setFeedbackReadOnly(false);
}

/**
 * Pré-remplit le formulaire avec un feedback existant.
 */
function prefillFeedbackForm(feedback) {
    FEEDBACK_SCALES.forEach(scale => {
        const value = feedback[scale.key];
        if (value) {
            const group = document.querySelector(`.feedback-scale-group[data-scale-key="${scale.key}"]`);
            if (group) {
                selectStar(group, value, false);
            }
        }
    });
    const comment = document.getElementById('feedbackComment');
    if (comment && feedback.comment) {
        comment.value = feedback.comment;
    }
}

/**
 * Met le formulaire en lecture seule (après soumission réussie ou feedback existant).
 */
function setFeedbackReadOnly(readOnly, message) {
    document.querySelectorAll('.feedback-star').forEach(s => s.disabled = readOnly);
    const comment = document.getElementById('feedbackComment');
    if (comment) comment.disabled = readOnly;
    const btn = document.getElementById('feedbackSubmitBtn');
    if (btn) btn.disabled = readOnly;
    if (readOnly && message) {
        const msg = document.getElementById('feedbackMessage');
        if (msg) {
            msg.textContent = message;
            msg.className = 'feedback-message feedback-message-success';
        }
    }
}

/**
 * Sélectionne une étoile dans un groupe d'échelle.
 * @param {HTMLElement} group - Élément .feedback-scale-group
 * @param {number} value - Valeur 1-5
 * @param {boolean} userInitiated - True si c'est un clic utilisateur (false pour prefill)
 */
function selectStar(group, value, userInitiated = true) {
    if (group.querySelector('.feedback-star:disabled')) {
        return; // en lecture seule
    }
    group.dataset.value = String(value);
    group.querySelectorAll('.feedback-star').forEach(star => {
        const starValue = parseInt(star.dataset.value, 10);
        if (starValue <= value) {
            star.classList.add('selected');
        } else {
            star.classList.remove('selected');
        }
    });
}

/**
 * Soumet le feedback au backend.
 */
async function submitFeedback() {
    if (!feedbackCurrentMessageId || feedbackSubmitted) {
        return;
    }
    const ratingResponse = getScaleValue('rating_response');
    const ratingRelevance = getScaleValue('rating_relevance');
    const ratingFormulation = getScaleValue('rating_formulation');
    const commentEl = document.getElementById('feedbackComment');
    const commentText = commentEl ? commentEl.value.trim() : '';

    const hasRating = ratingResponse || ratingRelevance || ratingFormulation;
    if (!hasRating && !commentText) {
        showFeedbackMessage("Veuillez donner au moins une note ou écrire un commentaire.", "error");
        return;
    }

    const payload = {
        message_id: feedbackCurrentMessageId,
        rating_response: ratingResponse,
        rating_relevance: ratingRelevance,
        rating_formulation: ratingFormulation,
        comment: commentText || null,
        anonymous_id: getAnonymousUserId(),
    };

    const btn = document.getElementById('feedbackSubmitBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = "Envoi...";
    }

    try {
        const response = await fetch(API_URL_FEEDBACK, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (response.status === 201) {
            feedbackSubmitted = true;
            showFeedbackMessage("Merci ! Votre retour a bien été enregistré.", "success");
            setFeedbackReadOnly(true);
        } else if (response.status === 409) {
            feedbackSubmitted = true;
            showFeedbackMessage("Un retour existe déjà pour cette réponse.", "info");
            setFeedbackReadOnly(true);
        } else if (response.status === 404) {
            showFeedbackMessage("Ce message n'existe plus côté serveur.", "error");
            if (btn) { btn.disabled = false; btn.textContent = "Envoyer le retour"; }
        } else {
            const data = await response.json().catch(() => ({}));
            showFeedbackMessage(data.detail || "Erreur lors de l'envoi du retour.", "error");
            if (btn) { btn.disabled = false; btn.textContent = "Envoyer le retour"; }
        }
    } catch (error) {
        console.error("Erreur lors de l'envoi du feedback:", error);
        showFeedbackMessage("Erreur réseau lors de l'envoi du retour.", "error");
        if (btn) { btn.disabled = false; btn.textContent = "Envoyer le retour"; }
    }
}

/**
 * Récupère la valeur sélectionnée d'une échelle.
 * @param {string} key - Clé de l'échelle (rating_response, etc.)
 * @returns {number|null}
 */
function getScaleValue(key) {
    const group = document.querySelector(`.feedback-scale-group[data-scale-key="${key}"]`);
    if (!group || !group.dataset.value) {
        return null;
    }
    return parseInt(group.dataset.value, 10);
}

/**
 * Affiche un message dans le formulaire.
 * @param {string} text
 * @param {string} type - 'success' | 'error' | 'info'
 */
function showFeedbackMessage(text, type) {
    const msg = document.getElementById('feedbackMessage');
    if (!msg) return;
    msg.textContent = text;
    msg.className = 'feedback-message';
    if (type === 'success') {
        msg.classList.add('feedback-message-success');
    } else if (type === 'error') {
        msg.classList.add('feedback-message-error');
    } else if (type === 'info') {
        msg.classList.add('feedback-message-info');
    }
}
