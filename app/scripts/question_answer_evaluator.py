#!/usr/bin/env python3
"""
Script d'évaluation de réponses à des questions avec combinatoire de modèles LLM.

Ce script:
1. Lit un CSV avec les colonnes: question_id, réponse humaine, note sur 10 attendue
2. Pour chaque réponse, évalue avec TOUS les modèles disponibles (distants + locaux)
3. Stocke séparément les résultats de chaque modèle
4. Calcule les moyennes de chaque combinaison de 1, 2, 3, 4 modèles
5. Génère un rapport détaillé avec toutes les évaluations

Modèles utilisés:
- Distants (Mistral): mistral-small-latest, ministral-3b-latest, ministral-8b-latest, mistral-medium
- Locaux (Ollama): ministral-3:3b, cas/ministral-8b-instruct-2410_q4km, llama3.1:8b

Auteur: Généré par Mistral Vibe
"""

import asyncio
import json
import csv
import time
import os
import itertools
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Imports des dépendances locales
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas non disponible, utilisation du module csv standard")

# Imports du projet
try:
    from app.agents.answer_evaluator_agent import (
        get_evaluator_agent,
        get_final_evaluator_agent,
        EvaluateRequestInput,
        AgentEvaluationResult,
        ListAgentEvaluationResult
    )
    from app.question_answer.answer_evaluation import (
        EvaluationResult,
        from_AgentEvaluationResult_to_EvaluationResult
    )
    from app.database.database import get_db_connection, get_question_by_id
    from app.agents.token_monitor import monitor_agent_call, monitor_agent_call_async
    logger.info("Tous les imports du projet réussis")
except ImportError as e:
    logger.error(f"Erreur d'import: {str(e)}")
    raise


# ============================================================================
# CLASSES DE DONNÉES
# ============================================================================

class IndividualEvaluation:
    """Résultat d'une évaluation individuelle par un modèle."""
    
    def __init__(
        self,
        model: str,
        provider: str,
        score: int,
        feedback: str,
        execution_time: float
    ):
        self.model = model
        self.provider = provider
        self.score = score
        self.feedback = feedback
        self.execution_time = execution_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour export JSON."""
        return {
            "model": self.model,
            "provider": self.provider,
            "score": self.score,
            "feedback": self.feedback,
            "execution_time": round(self.execution_time, 3)
        }
    
    def __repr__(self) -> str:
        return f"IndividualEvaluation({self.model}, score={self.score})"


class CombinationResult:
    """Résultat d'une combinaison de modèles."""
    
    def __init__(
        self,
        models: List[str],
        average_score: float,
        individual_scores: List[int]
    ):
        self.models = models
        self.average_score = average_score
        self.individual_scores = individual_scores
        self.size = len(models)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour export JSON."""
        return {
            "models": self.models,
            "size": self.size,
            "average_score": round(self.average_score, 2),
            "individual_scores": self.individual_scores
        }
    
    def get_key(self) -> str:
        """Retourne une clé unique pour cette combinaison."""
        return ",".join(sorted(self.models))
    
    def __repr__(self) -> str:
        return f"CombinationResult({self.size} models, avg={self.average_score:.2f})"


class QuestionResult:
    """Résultats complets pour une question."""
    
    def __init__(
        self,
        question_id: str,
        question_text: str,
        human_answer: str,
        expected_score: int,
        individual_evaluations: List[IndividualEvaluation],
        combination_results: List[CombinationResult],
        total_execution_time: float
    ):
        self.question_id = question_id
        self.question_text = question_text
        self.human_answer = human_answer
        self.expected_score = expected_score
        self.individual_evaluations = individual_evaluations
        self.combination_results = combination_results
        self.total_execution_time = total_execution_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour export JSON."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "human_answer": self.human_answer,
            "expected_score": self.expected_score,
            "individual_evaluations": [e.to_dict() for e in self.individual_evaluations],
            "combination_results": [c.to_dict() for c in self.combination_results],
            "total_execution_time": round(self.total_execution_time, 3)
        }
    
    def get_best_combination(self) -> Optional[CombinationResult]:
        """Retourne la combinaison dont la moyenne est la plus proche de la note attendue."""
        if not self.combination_results:
            return None
        
        best = None
        min_diff = float('inf')
        
        for combo in self.combination_results:
            diff = abs(combo.average_score - self.expected_score)
            if diff < min_diff:
                min_diff = diff
                best = combo
        
        return best


# ============================================================================
# CLASSE PRINCIPALE
# ============================================================================

class QuestionAnswerEvaluator:
    """
    Classe principale pour évaluer des réponses à des questions avec plusieurs modèles LLM.
    """
    
    # Modèles distants (Mistral)

    MISTRAL_MODELS = [
        "ministral-3b-2512",
        "ministral-8b-2512",
        "ministral-14b-2512",
        "mistral-small-2603",
        "mistral-medium-latest"
    ]

    #MISTRAL_MODELS = []
    # Modèles locaux (Ollama)
    OLLAMA_MODELS = [
        "ministral-3:3b",
        "llama3.2:1b",
        "llama3.2:3b",
        "qwen3.5:2b",
        "qwen3.5:4b"
    ]

    OLLAMA_MODELS = []
    def __init__(
        self,
        csv_path: str,
        output_dir: str = "results",
        use_local: bool = True,
        use_remote: bool = True
    ):
        """
        Initialise l'évaluateur.
        
        Args:
            csv_path: Chemin vers le CSV d'entrée
            output_dir: Dossier de sortie pour les résultats
            use_local: Utiliser les modèles locaux (Ollama)
            use_remote: Utiliser les modèles distants (Mistral)
        """
        self.csv_path = csv_path
        self.output_dir = output_dir
        self.use_local = use_local
        self.use_remote = use_remote
        
        # Cache pour les agents évaluateurs
        self._agent_cache: Dict[Tuple[str, str], Any] = {}
        
        # Créer le dossier de sortie
        os.makedirs(output_dir, exist_ok=True)
        
        # Charger les données du CSV
        self.questions_data = self._load_questions_from_csv()
        
        logger.info(f"Évaluateur initialisé avec {len(self.questions_data)} questions")
        logger.info(f"Modèles distants: {self.use_remote}, Modèles locaux: {self.use_local}")
    
    def _load_questions_from_csv(self) -> List[Dict[str, Any]]:
        """
        Charge les questions depuis le CSV.
        
        Le CSV doit avoir les colonnes:
        - question_id
        - reponse (ou human_answer)
        - expected_grading (ou expected_score)
        
        Returns:
            Liste de dictionnaires avec les données des questions
        """
        questions = []
        
        if HAS_PANDAS:
            try:
                df = pd.read_csv(self.csv_path)
                for _, row in df.iterrows():
                    question = {
                        "question_id": str(self._get_column_value(
                            row, ["question_id", "id"], ""
                        )),
                        "human_answer": str(self._get_column_value(
                            row, ["reponse", "human_answer", "response", "réponse humaine", "reponse humaine"], ""
                        )),
                        "expected_score": int(self._get_column_value(
                            row, ["expected_grading", "expected_score", "note", "note sur 10 attendue"], 0
                        ))
                    }
                    if question["human_answer"] != "":
                        questions.append(question)
                logger.info(f"Chargé {len(questions)} questions depuis {self.csv_path} (pandas)")
            except Exception as e:
                logger.warning(f"Erreur avec pandas: {str(e)}, essayons avec csv module")
                questions = self._load_with_csv_module()
        else:
            questions = self._load_with_csv_module()
        
        return questions
    
    def _load_with_csv_module(self) -> List[Dict[str, Any]]:
        """Charge le CSV avec le module csv standard."""
        import csv as csv_module
        
        questions = []
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv_module.DictReader(f)
            for row in reader:
                question = {
                    "question_id": str(self._get_column_value(
                        row, ["question_id", "id"], ""
                    )),
                    "human_answer": str(self._get_column_value(
                        row, ["reponse", "human_answer", "response", "réponse humaine", "reponse humaine"], ""
                    )),
                    "expected_score": int(self._get_column_value(
                        row, ["expected_grading", "expected_score", "note", "note sur 10 attendue"], 0
                    ))
                }
                questions.append(question)
        
        logger.info(f"Chargé {len(questions)} questions depuis {self.csv_path} (csv module)")
        return questions
    
    def _get_all_models(self) -> List[Tuple[str, str]]:
        """
        Retourne tous les modèles avec leur provider.
        
        Returns:
            Liste de tuples (model_name, provider)
        """
        models = []
        
        if self.use_remote:
            models.extend([(m, "mistral") for m in self.MISTRAL_MODELS])
            logger.info(f"Ajout de {len(self.MISTRAL_MODELS)} modèles distants (Mistral)")
        
        if self.use_local:
            models.extend([(m, "ollama") for m in self.OLLAMA_MODELS])
            logger.info(f"Ajout de {len(self.OLLAMA_MODELS)} modèles locaux (Ollama)")
        
        if not models:
            raise ValueError("Aucun modèle sélectionné. Activez use_local ou use_remote.")
        
        logger.info(f"Total: {len(models)} modèles disponibles")
        return models
    
    def _get_column_value(
        self, 
        row: Dict[str, Any], 
        possible_names: List[str], 
        default: Any = None
    ) -> Any:
        """
        Récupère une valeur d'un dictionnaire en essayant plusieurs noms de clés.
        
        Args:
            row: Dictionnaire de données
            possible_names: Liste des noms de colonnes possibles
            default: Valeur par défaut si aucune clé n'est trouvée
            
        Returns:
            La première valeur trouvée ou la valeur par défaut
        """
        for name in possible_names:
            if name in row:
                return row[name]
        return default
    
    def _get_cached_evaluator(self, model_name: str, provider: str) -> Any:
        """
        Récupère ou crée un agent évaluateur et le met en cache.
        
        Args:
            model_name: Nom du modèle
            provider: Fournisseur (mistral, ollama)
            
        Returns:
            Agent évaluateur
        """
        cache_key = (model_name, provider)
        if cache_key not in self._agent_cache:
            logger.info(f"Création de l'agent pour {provider}:{model_name}")
            self._agent_cache[cache_key] = get_evaluator_agent(model_name, provider, async_mode=True)
        return self._agent_cache[cache_key]
    
    async def _get_question_details(
        self, 
        question_id: str
    ) -> Tuple[str, List[str]]:
        """
        Récupère le texte de la question et les réponses de référence depuis la DB.
        
        Args:
            question_id: ID de la question
            
        Returns:
            Tuple de (question_text, list of expected_answers)
        """
        conn = None
        try:
            async with await get_db_connection() as conn:
                question = await get_question_by_id(conn, int(question_id), include_answers=True)
            
                if not question:
                    logger.warning(f"Question {question_id} non trouvée en base de données")
                    return f"Question {question_id}", []
            
            question_text = question.get("content", "")
            answers = question.get("answers", [])
            expected_answers = [
                answer.get("content", "") 
                for answer in answers 
                if answer.get("content")
            ]
            
            if not expected_answers:
                logger.warning(f"Pas de réponses attendues pour la question {question_id}")
            
            return question_text, expected_answers
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la question {question_id}: {str(e)}")
            return f"Question {question_id}", []

    
    async def _evaluate_with_all_models(
        self, 
        question_data: Dict[str, Any]
    ) -> List[IndividualEvaluation]:
        """
        Évalue une question avec TOUS les modèles disponibles.
        
        Args:
            question_data: Dictionnaire avec question_id, human_answer, expected_score
            
        Returns:
            Liste de toutes les évaluations individuelles
        """
        all_models = self._get_all_models()
        individual_evaluations = []
        
        # Récupérer les détails de la question
        question_text, expected_answers = await self._get_question_details(
            question_data["question_id"]
        )
        
        if not expected_answers:
            expected_answers = [""]  # Au moins une réponse vide
        
        # Créer l'entrée d'évaluation
        evaluation_input = EvaluateRequestInput(
            question=question_text,
            expected_answers=expected_answers,
            user_answer=question_data["human_answer"]
        )
        
        logger.info(f"Évaluation de la question {question_data['question_id']} avec {len(all_models)} modèles...")
        
        # Préparer les coroutines pour chaque modèle
        coroutines = []
        for model_name, provider in all_models:
            evaluator = self._get_cached_evaluator(model_name, provider)
            start_time = time.time()
            
            async def _evaluate_model(
                evaluator, 
                model_name: str, 
                provider: str, 
                start_time: float
            ) -> IndividualEvaluation:
                """Évalue avec un seul modèle."""
                try:
                    result = await monitor_agent_call_async(
                        evaluator, 
                        evaluation_input, 
                        "run_async"
                    )
                    eval_result, token_count, output_tokens = result
                    exec_time = time.time() - start_time
                    
                    return IndividualEvaluation(
                        model=model_name,
                        provider=provider,
                        score=eval_result.score,
                        feedback=eval_result.feedback,
                        execution_time=exec_time
                    )
                except Exception as e:
                    logger.error(f"Erreur avec {model_name} ({provider}): {str(e)}")
                    return IndividualEvaluation(
                        model=model_name,
                        provider=provider,
                        score=0,
                        feedback=f"Erreur: {str(e)}",
                        execution_time=0
                    )
            
            coroutines.append(_evaluate_model(evaluator, model_name, provider, start_time))
        
        # Exécuter toutes les évaluations en parallèle
        individual_evaluations = await asyncio.gather(*coroutines)
        
        logger.info(f"Terminé: {len(individual_evaluations)} évaluations individuelles")
        return individual_evaluations
    
    def _calculate_all_combinations(
        self, 
        evaluations: List[IndividualEvaluation]
    ) -> List[CombinationResult]:
        """
        Calcule les moyennes pour toutes les combinaisons de 1 à 4 modèles.
        
        Args:
            evaluations: Liste des évaluations individuelles
            
        Returns:
            Liste de CombinationResult pour toutes les combinaisons
        """
        if not evaluations:
            return []
        
        # Créer un dictionnaire pour accéder rapidement aux scores
        # Utiliser (provider, model) comme clé
        eval_dict = {}
        for eval in evaluations:
            key = f"{eval.provider}:{eval.model}"
            eval_dict[key] = eval
        
        # Obtenir la liste de tous les modèles disponibles
        all_model_keys = list(eval_dict.keys())
        
        combination_results = []
        
        # Générer toutes les combinaisons de 1 à 4 modèles
        max_size = min(4, len(all_model_keys))
        for r in range(1, max_size + 1):
            for combo_keys in itertools.combinations(all_model_keys, r):
                # Extraire les scores de cette combinaison
                scores = [eval_dict[key].score for key in combo_keys]
                avg_score = sum(scores) / len(scores)
                
                # Créer un CombinationResult
                combo_result = CombinationResult(
                    models=list(combo_keys),
                    average_score=avg_score,
                    individual_scores=scores
                )
                combination_results.append(combo_result)
        
        logger.info(f"Calculé {len(combination_results)} combinaisons")
        return combination_results
    
    async def _evaluate_single_question(
        self, 
        question_data: Dict[str, Any]
    ) -> QuestionResult:
        """
        Évalue complètement une question:
        1. Évalue avec tous les modèles
        2. Calcule toutes les combinaisons
        
        Args:
            question_data: Dictionnaire avec les données de la question
            
        Returns:
            QuestionResult avec toutes les évaluations
        """
        start_time = time.time()
        
        # Étape 1: Évaluer avec tous les modèles
        individual_evaluations = await self._evaluate_with_all_models(question_data)
        
        # Étape 2: Calculer toutes les combinaisons
        combination_results = self._calculate_all_combinations(individual_evaluations)
        
        # Récupérer le texte de la question
        question_text, _ = await self._get_question_details(question_data["question_id"])
        
        total_time = time.time() - start_time
        
        return QuestionResult(
            question_id=question_data["question_id"],
            question_text=question_text,
            human_answer=question_data["human_answer"],
            expected_score=question_data["expected_score"],
            individual_evaluations=individual_evaluations,
            combination_results=combination_results,
            total_execution_time=total_time
        )
    
    async def run_full_evaluation(self) -> List[QuestionResult]:
        """
        Exécute l'évaluation complète de toutes les questions.
        
        Returns:
            Liste de QuestionResult pour chaque question
        """
        results = []
        
        logger.info(f"Début de l'évaluation de {len(self.questions_data)} questions...")
        
        for i, question_data in enumerate(self.questions_data):
            logger.info(f"\n=== Question {i+1}/{len(self.questions_data)}: {question_data['question_id']} ===")
            
            try:
                result = await self._evaluate_single_question(question_data)
                results.append(result)
                logger.info(f"  Terminé en {result.total_execution_time:.2f}s")
                
                # Afficher un résumé rapide
                avg_score = sum(e.score for e in result.individual_evaluations) / len(result.individual_evaluations)
                logger.info(f"  Score moyen: {avg_score:.2f}/10")
                
            except Exception as e:
                logger.error(f"  Erreur pour question {question_data['question_id']}: {str(e)}")
                # Créer un résultat d'erreur
                results.append(QuestionResult(
                    question_id=question_data["question_id"],
                    question_text="",
                    human_answer=question_data["human_answer"],
                    expected_score=question_data["expected_score"],
                    individual_evaluations=[],
                    combination_results=[],
                    total_execution_time=0
                ))
        
        logger.info(f"\nÉvaluation complète terminée! {len(results)} questions traitées")
        return results

    def export_results_to_json(
        self, 
        results: List[QuestionResult], 
        filename: str = None
    ) -> None:
        """
        Exporte les résultats au format JSON.
        
        Args:
            results: Liste des résultats d'évaluation
            filename: Nom du fichier (optionnel)
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/evaluation_results_{timestamp}.json"
        
        results_dict = [result.to_dict() for result in results]
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Résultats exportés en JSON: {filename}")
    
    def export_results_to_csv(
        self, 
        results: List[QuestionResult], 
        filename: str = None
    ) -> None:
        """
        Exporte les résultats au format CSV.
        
        Le CSV contient:
        - Une ligne par évaluation individuelle
        - Une ligne par combinaison
        
        Args:
            results: Liste des résultats d'évaluation
            filename: Nom du fichier (optionnel)
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.output_dir}/evaluation_results_{timestamp}.csv"
        
        csv_data = []
        
        for question_result in results:
            question_id = question_result.question_id
            question_text = question_result.question_text
            human_answer = question_result.human_answer
            expected_score = question_result.expected_score
            
            # Ajouter les évaluations individuelles
            for ie in question_result.individual_evaluations:
                csv_data.append({
                    "question_id": question_id,
                    "question_text": question_text,
                    "human_answer": human_answer,
                    "expected_score": expected_score,
                    "type": "individual",
                    "model": f"{ie.provider}:{ie.model}",
                    "score": ie.score,
                    "feedback": ie.feedback,
                    "execution_time": round(ie.execution_time, 3)
                })
            
            # Ajouter les combinaisons
            for combo in question_result.combination_results:
                csv_data.append({
                    "question_id": question_id,
                    "question_text": question_text,
                    "human_answer": human_answer,
                    "expected_score": expected_score,
                    "type": "combination",
                    "model": ",".join(combo.models),
                    "score": round(combo.average_score, 2),
                    "feedback": "",
                    "combination_size": combo.size,
                    "execution_time": ""
                })
        
        if csv_data:
            # Collecter toutes les clés uniques de tous les dictionnaires
            all_fieldnames = set()
            for row in csv_data:
                all_fieldnames.update(row.keys())
            fieldnames = list(all_fieldnames)
            
            with open(filename, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)
            
            logger.info(f"Résultats exportés en CSV: {filename}")
        else:
            logger.warning("Aucune donnée à exporter en CSV")
    
    def generate_report(
        self, 
        results: List[QuestionResult]
    ) -> str:
        """
        Génère un rapport Markdown détaillé.
        
        Args:
            results: Liste des résultats d'évaluation
            
        Returns:
            Chaîne Markdown du rapport
        """
        report = "# 📊 Rapport d'évaluation des réponses\n\n"
        report += f"Généré le: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        report += f"Fichier CSV source: {self.csv_path}\n\n"
        
        all_models_used = set()
        total_questions = len(results)
        
        # ===== STATISTIQUES GLOBALES =====
        report += "## 📈 Statistiques globales\n\n"
        report += f"- **Nombre de questions évaluées**: {total_questions}\n"
        
        # Collecter tous les modèles utilisés
        for qr in results:
            for ie in qr.individual_evaluations:
                all_models_used.add(f"{ie.provider}:{ie.model}")
        report += f"- **Nombre de modèles utilisés**: {len(all_models_used)}\n"
        report += f"- **Modèles**: {', '.join(sorted(all_models_used))}\n\n"
        
        # ===== TABLEAU DES SCORES PAR MODÈLE =====
        report += "## 🎯 Scores moyens par modèle\n\n"
        
        # Calculer les scores moyens par modèle
        model_scores = {}
        model_counts = {}
        for qr in results:
            for ie in qr.individual_evaluations:
                model_key = f"{ie.provider}:{ie.model}"
                if model_key not in model_scores:
                    model_scores[model_key] = 0
                    model_counts[model_key] = 0
                model_scores[model_key] += ie.score
                model_counts[model_key] += 1
        
        model_avg_scores = {}
        for model in model_scores:
            count = model_counts.get(model, 1)
            if count > 0:
                model_avg_scores[model] = model_scores[model] / count
            else:
                model_avg_scores[model] = 0
        
        report += "| Modèle | Score moyen | Nombre d'évaluations |\n"
        report += "|--------|-------------|---------------------|\n"
        for model in sorted(model_avg_scores.keys()):
            report += f"| {model} | {model_avg_scores[model]:.2f} | {model_counts[model]} |\n"
        report += "\n"
        
        # ===== DÉTAILS PAR QUESTION =====
        for idx, qr in enumerate(results, 1):
            report += f"## Question {idx}: {qr.question_id}\n\n"
            report += f"**Texte**: {qr.question_text}\n\n"
            report += f"**Réponse humaine**: {qr.human_answer}\n\n"
            report += f"**Note attendue**: {qr.expected_score}/10\n\n"
            report += f"**Temps total**: {qr.total_execution_time:.2f}s\n\n"
            
            # Évaluations individuelles
            report += "### 🔍 Évaluations individuelles\n\n"
            report += "| Modèle | Score | Feedback | Temps (s) |\n"
            report += "|--------|-------|---------|-----------|\n"
            for ie in sorted(qr.individual_evaluations, key=lambda x: x.score, reverse=True):
                report += f"| {ie.provider}:{ie.model} | {ie.score}/10 | {ie.feedback[:50]}... | {ie.execution_time:.3f} |\n"
            report += "\n"
            
            # Meilleure combinaison
            best_combo = qr.get_best_combination()
            if best_combo:
                report += f"### 🏆 Meilleure combinaison"
                report += f" (la plus proche de la note attendue {qr.expected_score}/10):\n\n"
                report += f"- **Modèles**: {', '.join(best_combo.models)}\n"
                report += f"- **Score moyen**: {best_combo.average_score:.2f}/10\n"
                report += f"- **Écart avec la note attendue**: {abs(best_combo.average_score - qr.expected_score):.2f}\n\n"
            
            # Stats par taille de combinaison
            report += "### 📊 Moyennes par taille de combinaison\n\n"
            combo_by_size = {}
            for combo in qr.combination_results:
                if combo.size not in combo_by_size:
                    combo_by_size[combo.size] = []
                combo_by_size[combo.size].append(combo.average_score)
            
            for size in sorted(combo_by_size.keys()):
                scores = combo_by_size[size]
                avg = sum(scores) / len(scores)
                min_score = min(scores)
                max_score = max(scores)
                report += f"- **{size} modèle(s)**: moyenne={avg:.2f}, min={min_score:.2f}, max={max_score:.2f}\n"
            report += "\n"
        
        # ===== ANALYSE FINALE =====
        report += "## 🎉 Analyse finale\n\n"
        
        # Comparaison globale
        all_consolidated_scores = []
        for qr in results:
            if qr.combination_results:
                # Prendre la moyenne de toutes les combinaisons de taille 1
                size1_combos = [c for c in qr.combination_results if c.size == 1]
                if size1_combos:
                    avg_score = sum(c.average_score for c in size1_combos) / len(size1_combos)
                    all_consolidated_scores.append(avg_score)
        
        if all_consolidated_scores:
            global_avg = sum(all_consolidated_scores) / len(all_consolidated_scores)
            report += f"- **Score moyen global**: {global_avg:.2f}/10\n\n"
        
        report += "---\n"
        report += f"Rapport généré par QuestionAnswerEvaluator | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return report


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

async def main():
    """Fonction principale asynchrone."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Évalue des réponses à des questions avec plusieurs configurations LLM"
    )
    parser.add_argument(
        "--csv", 
        type=str, 
        required=True, 
        help="Chemin vers le CSV d'entrée avec colonnes: question_id,réponse humaine,note sur 10 attendue"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="results", 
        help="Dossier de sortie pour les résultats (défaut: results/)"
    )
    parser.add_argument(
        "--no-local", 
        action="store_true", 
        help="Désactiver les modèles locaux (Ollama)"
    )
    parser.add_argument(
        "--no-remote", 
        action="store_true", 
        help="Désactiver les modèles distants (Mistral)"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=None, 
        help="Limiter le nombre de questions à traiter (pour tests rapides)"
    )
    
    args = parser.parse_args()
    
    # Configuration pour Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        logger.info("Début du script d'évaluation des réponses")
        logger.info(f"CSV: {args.csv}")
        logger.info(f"Sortie: {args.output}")
        
        # Créer l'évaluateur
        evaluator = QuestionAnswerEvaluator(
            csv_path=args.csv,
            output_dir=args.output,
            use_local=not args.no_local,
            use_remote=not args.no_remote
        )
        
        # Limiter les questions si demandé
        if args.limit and args.limit < len(evaluator.questions_data):
            evaluator.questions_data = evaluator.questions_data[:args.limit]
            logger.info(f"Limité à {args.limit} questions")
        
        # Exécuter l'évaluation complète
        results = await evaluator.run_full_evaluation()
        
        # Exporter les résultats
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"{args.output}/evaluation_results_{timestamp}.json"
        csv_filename = f"{args.output}/evaluation_results_{timestamp}.csv"
        report_filename = f"{args.output}/evaluation_report_{timestamp}.md"
        
        evaluator.export_results_to_json(results, json_filename)
        evaluator.export_results_to_csv(results, csv_filename)
        
        # Générer et sauvegarder le rapport
        try:
            report = evaluator.generate_report(results)
            with open(report_filename, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info(f"Rapport sauvegardé: {report_filename}")
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport: {str(e)}", exc_info=True)
            logger.warning(f"Le rapport n'a pas pu être généré, mais les résultats JSON et CSV sont disponibles")
        
        # Afficher un résumé
        print("\n" + "="*70)
        print(" ✅ ÉVALUATION TERMINÉE AVEC SUCCÈS!")
        print("="*70)
        print(f"Questions évaluées: {len(evaluator.questions_data)}")
        print(f"Résultats: {args.output}/")
        print(f"  - JSON: {os.path.basename(json_filename)}")
        print(f"  - CSV: {os.path.basename(csv_filename)}")
        print(f"  - Rapport: {os.path.basename(report_filename)}")
        print("="*70)
        
        return 0
        
    except Exception as e:
        logger.error(f"Erreur fatale: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
