// Widget de declaration de lecture prealable d'un document.
// Lorsqu'un document est presente dans le chatbot RAG ou dans le systeme
// de mediation inverse, une petite zone flottante demande au visiteur s'il a
// deja consulte ou lu ce document avant sa visite. Reponses Oui / Non / Fermer :
// Fermer ne declenche aucun appel API.

const PRIOR_READ_API = (window.location.origin) + '/api/knowledge-declarations/document-prior-read';
const PRIOR_READ_STORAGE_PREFIX = 'm3c_prior_read_declared_';

let priorReadWidget = null;

function getAnonymousUserId() {
    let anonymousId = localStorage.getItem('m3c_anonymous_id');
    if (!anonymousId) {
        anonymousId = crypto.randomUUID();
        localStorage.setItem('m3c_anonymous_id', anonymousId);
    }
    return anonymousId;
}

/**
 * Affiche le widget flottant de declaration de lecture prealable.
 * Le widget n'est affiche qu'une seule fois par document et par visiteur
 * (marqueur localStorage), et jamais si une declaration a deja ete envoyee.
 *
 * @param {number} resourceId - Identifiant du document (resource_id).
 * @param {string} origin - Page d'origine ('m3c-chatbot.html' ou 'question_session.html').
 */
function showPriorReadWidget(resourceId, origin) {
    if (!resourceId || priorReadWidget) return;
    const marker = PRIOR_READ_STORAGE_PREFIX + resourceId;
    if (localStorage.getItem(marker) === 'declared' || sessionStorage.getItem(marker) === 'dismissed') return;

    priorReadWidget = document.createElement('div');
    priorReadWidget.className = 'prior-read-widget';
    priorReadWidget.innerHTML =
        '<div class="prior-read-question">Avez-vous d&eacute;j&agrave; consult&eacute; ou lu ce document avant votre visite&nbsp;?</div>' +
        '<div class="prior-read-buttons">' +
        '<button type="button" class="prior-read-btn prior-read-yes">Oui</button>' +
        '<button type="button" class="prior-read-btn prior-read-no">Non</button>' +
        '<button type="button" class="prior-read-btn prior-read-close" title="Fermer">Fermer</button>' +
        '</div>';

    const dismiss = () => {
        sessionStorage.setItem(marker, 'dismissed');
        closePriorReadWidget();
    };

    const answer = async (alreadyRead) => {
        localStorage.setItem(marker, 'declared');
        closePriorReadWidget();
        try {
            await fetch(PRIOR_READ_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    resource_id: resourceId,
                    already_read: alreadyRead,
                    anonymous_id: getAnonymousUserId(),
                    metadata: { page: origin || window.location.pathname.split('/').pop() }
                })
            });
        } catch (e) {
            // echec reseau : la declaration locale reste enregistree pour ne pas harceler le visiteur
        }
    };

    priorReadWidget.querySelector('.prior-read-yes').addEventListener('click', () => answer(true));
    priorReadWidget.querySelector('.prior-read-no').addEventListener('click', () => answer(false));
    priorReadWidget.querySelector('.prior-read-close').addEventListener('click', dismiss);

    document.body.appendChild(priorReadWidget);
}

function closePriorReadWidget() {
    if (priorReadWidget) {
        priorReadWidget.remove();
        priorReadWidget = null;
    }
}

// Styles injectes une seule fois
if (!document.getElementById('prior-read-widget-styles')) {
    const style = document.createElement('style');
    style.id = 'prior-read-widget-styles';
    style.textContent =
        '.prior-read-widget {' +
        'position: fixed; bottom: 20px; right: 20px; z-index: 9999;' +
        'background: #fff; border: 1px solid #ccc; border-radius: 12px;' +
        'box-shadow: 0 4px 16px rgba(0,0,0,0.18); padding: 14px 16px; max-width: 320px;' +
        'font-size: 14px; font-family: inherit;' +
        '}' +
        '.prior-read-question { margin-bottom: 10px; color: #333; }' +
        '.prior-read-buttons { display: flex; gap: 8px; }' +
        '.prior-read-btn {' +
        'padding: 6px 14px; border: 1px solid #ccc; border-radius: 18px;' +
        'background: #fff; cursor: pointer; font-size: 13px;' +
        '}' +
        '.prior-read-btn:hover { background: #f0f0f0; }' +
        '.prior-read-close { color: #888; }';
    document.head.appendChild(style);
}
