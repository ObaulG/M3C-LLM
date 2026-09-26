// Données des réponses de référence chargées au démarrage
        let referenceAnswers = {};
        
        // Charge les réponses de référence au démarrage
        async function loadReferenceAnswers() {
            try {
                console.log('Chargement des réponses de référence depuis /api/reference-answers...');
                const response = await fetch('/api/reference-answers');
                if (response.ok) {
                    const data = await response.json();
                    referenceAnswers = data.reference_answers || {};
                    console.log('✓ Réponses de référence chargées:', Object.keys(referenceAnswers).length, 'questions');
                    console.log('IDs des questions avec référence:', Object.keys(referenceAnswers));
                } else {
                    console.warn('Aucune réponse de référence trouvée, mais cela est normal si le fichier CSV est vide');
                }
            } catch (error) {
                console.error('Erreur lors du chargement des réponses de référence:', error);
            }
        }
        
        // Appel au chargement de la page
        document.addEventListener('DOMContentLoaded', function() {
            loadReferenceAnswers();
        });

document.addEventListener("DOMContentLoaded", function () {
    loadModelsIntoSelect(document.getElementById("modelFilter"), { prefixProvider: true, keepFirst: true });
  });
