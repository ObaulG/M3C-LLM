#!/usr/bin/env python3
"""
Script de session de médiation avec évaluation variable des modèles LLM.

Ce script reproduit le flux de session de l'API mais en mode batch, permettant
d'évaluer les performances avec différentes configurations de modèles et nombre
d'évaluateurs. Il mesure également les temps de réponse pour chaque évaluation.

Fonctionnalités:
- Initialisation de session avec document prédéfini
- Évaluation avec modèles Mistral et Ministral
- Variation du nombre d'évaluateurs (1, 3, 5)
- Mesure précise des temps de réponse
- Export des résultats détaillés
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import des dépendances locales
from question_session import (
    PREMADE_QUESTIONS_BY_DOCUMENT_ID,
    SessionManager,
    UserResponse,
    SessionStatus,
    EvaluationResult,
    from_AgentEvaluationResult_to_EvaluationResult
)

from agents.answer_evaluator_agent import (
    get_evaluator_agent,
    get_final_evaluator_agent,
    EvaluateRequestInput,
    AgentEvaluationResult,
    ListAgentEvaluationResult
)
from agents.message_evaluator_agent import get_message_type_agent, MessageTypeRequestInput

from database.database import (
    get_db_connection,
    get_question_by_id,
    get_chunks_by_question_id
)

from agents.token_monitor import monitor_agent_call, monitor_agent_call_async


class SessionEvaluationConfig:
    """Configuration pour une évaluation de session."""
    
    def __init__(self, 
                 evaluator_models: List[str], 
                 nb_evaluators: int = 3,
                 with_final_evaluator: bool = True,
                 final_evaluator_model: str = "mistral-large-latest"):
        self.evaluator_models = evaluator_models
        self.nb_evaluators = nb_evaluators
        self.with_final_evaluator = with_final_evaluator
        self.final_evaluator_model = final_evaluator_model
        
    def get_description(self) -> str:
        """Description textuelle de la configuration."""
        eval_desc = ", ".join(self.evaluator_models)
        final_desc = f" + final({self.final_evaluator_model})" if self.with_final_evaluator else ""
        return f"{self.nb_evaluators} eval({eval_desc}){final_desc}"


class SessionEvaluationResult:
    """Résultats d'une évaluation de session."""
    
    def __init__(self, 
                 config: SessionEvaluationConfig,
                 session_status: SessionStatus,
                 total_evaluation_time: float,
                 token_usage: Dict[str, int],
                 model_execution_times: Dict[str, float]):
        self.config = config
        self.session_status = session_status
        self.total_evaluation_time = total_evaluation_time
        self.token_usage = token_usage
        self.model_execution_times = model_execution_times
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour export JSON."""
        return {
            "config": {
                "evaluator_models": self.config.evaluator_models,
                "nb_evaluators": self.config.nb_evaluators,
                "with_final_evaluator": self.config.with_final_evaluator,
                "final_evaluator_model": self.config.final_evaluator_model,
                "description": self.config.get_description()
            },
            "session_id": self.session_status.session_id,
            "document_id": self.session_status.document_id,
            "total_evaluation_time_seconds": self.total_evaluation_time,
            "token_usage": self.token_usage,
            "model_execution_times": self.model_execution_times,
            "responses": [self._serialize_response(r) for r in self.session_status.responses],
            "timestamp": self.timestamp
        }
        
    def _serialize_response(self, response: UserResponse) -> Dict:
        """Sérialise une réponse utilisateur."""
        eval_data = None
        if response.evaluation:
            eval_data = {
                "score": response.evaluation.score,
                "feedback": response.evaluation.feedback,
                "cosine_similarity": 0,
                "model": response.evaluation.model
            }
        
        return {
            "question_id": response.question_id,
            "question_text": response.question_text,
            "user_answer": response.user_answer,
            "date_sent": response.date_sent.isoformat(),
            "evaluation": eval_data
        }


class MediationSessionEvaluator:
    """Classe principale pour évaluer les sessions de médiation."""
    
    def __init__(self):
        # Configuration du document à utiliser
        self.document_id = "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56"
        self.question_ids = PREMADE_QUESTIONS_BY_DOCUMENT_ID[self.document_id]
        
        # Charger les réponses utilisateur
        self.user_answers = self._load_user_answers()
        
        # Initialiser le gestionnaire de sessions
        self.session_manager = SessionManager()
        
        # Initialiser les agents
        self.message_type_agent = get_message_type_agent()
        
        # Liste des modèles disponibles
        self.available_models = {
            "mistral": ["mistral-small-latest", "mistral-medium", "mistral-large-2411"],
            "ministral": ["ministral-3b-latest", "ministral-8b-latest"]
        }
        
    def _load_user_answers(self) -> List[str]:
        """Charge les réponses utilisateur depuis le fichier."""
        try:
            with open("../reponses-test-lochi-mondu.txt", "r", encoding="utf-8") as f:
                answers = [line.strip() for line in f.readlines() if line.strip()]
            if len(answers) != len(self.question_ids):
                logger.warning(f"Nombre de réponses ({len(answers)}) différent du nombre de questions ({len(self.question_ids)})")
            return answers
        except FileNotFoundError:
            logger.error("Fichier reponses-test-lochi-mondu.txt non trouvé")
            raise
            
    async def initialize_session(self) -> str:
        """Initialise une nouvelle session pour le document spécifié."""
        session_id = self.session_manager.create_session(self.document_id, premade_session=True)
        
        # Ajouter les questions à la session
        conn = await get_db_connection()
        questions_tasks = [get_question_by_id(conn, question_id, include_answers=False) 
                          for question_id in self.question_ids]
        questions = await asyncio.gather(*questions_tasks)
        
        # Récupérer les chunks pour chaque question
        questions_chunks_tasks = [get_chunks_by_question_id(question_id, conn) 
                                for question_id in self.question_ids]
        questions_chunks = await asyncio.gather(*questions_chunks_tasks)
        
        questions_texts = [question["content"] for question in questions]
        question_pages = [chunk[0]["num_page"] for chunk in questions_chunks]
        
        self.session_manager.add_questions(session_id, self.question_ids, questions_texts, question_pages)
        
        return session_id
        
    async def evaluate_session(self, session_id: str, config: SessionEvaluationConfig, is_local: bool = True) -> SessionEvaluationResult:
        """Évalue une session complète avec la configuration donnée."""
        start_time = time.time()
        total_input_tokens = 0
        total_output_tokens = 0
        model_execution_times = {}  # Track individual model execution times
        
        # Initialiser les évaluateurs pour cette configuration
        # TODO: bricolage avec is_local à corriger plus tard
        provider = "ollama" if is_local else "mistral"
        evaluators = [get_evaluator_agent(model, provider, async_mode=True) for model in config.evaluator_models]
        final_evaluator = get_final_evaluator_agent(config.final_evaluator_model, provider, async_mode=True) if config.with_final_evaluator else None
        
        # Initialiser la liste des réponses
        responses = []
        
        # Traiter chaque question
        for i, question_id in enumerate(self.question_ids):
            question_start = time.time()
            
            # Récupérer la question et ses réponses
            conn = await get_db_connection()
            question = await get_question_by_id(conn, question_id, include_answers=True)
            
            if not question["answers"]:
                logger.warning(f"Pas de réponse attendue pour la question {question_id}")
                continue
                
            expected_answer = question["answers"][0]["content"]
            user_answer = self.user_answers[i] if i < len(self.user_answers) else ""
            
            # Déterminer le type de message (toujours "réponse" dans notre cas)
            message_type = "réponse"  # Simplification pour ce script
            
            # Préparer l'évaluation
            evaluation_input = EvaluateRequestInput(
                question=question['content'],
                expected_answer=expected_answer,
                user_answer=user_answer
            )
            
            # Évaluer avec tous les évaluateurs
            evaluations = []
            eval_start_time = time.time()

            # Appels asynchrones aux évaluateurs avec timing individuel
            coroutines = []
            for i, evaluator in enumerate(evaluators):
                model_name = config.evaluator_models[i]
                start_model_time = time.time()

                async def _evaluate_with_timing(evaluator, model_name, start_time, evaluation_input):
                    logger.info(f"Modèle {model_name}...")
                    result = await monitor_agent_call_async(evaluator, evaluation_input, "run_async")

                    model_time = time.time() - start_time
                    # Store the timing
                    if model_name not in model_execution_times:
                        model_execution_times[model_name] = 0.0
                    model_execution_times[model_name] += model_time
                    return result

                coroutines.append(_evaluate_with_timing(evaluator, model_name, start_model_time, evaluation_input))

            logger.info("Début de l'évaluation")
            eval_results = await asyncio.gather(*coroutines)
            logger.info("Evaluation terminée. Début du traitement des résultats")
            # Traiter les résultats
            for result in eval_results:
                evaluation, token_count_result, output_tokens = result
                evaluations.append(evaluation)
                total_input_tokens += token_count_result.total
                total_output_tokens += output_tokens
                
            eval_time = time.time() - eval_start_time
            
            # Consolider les évaluations si plusieurs évaluateurs
            if len(evaluations) > 1 and config.with_final_evaluator:
                final_eval_start = time.time()
                final_evaluation, token_count_result, output_tokens = monitor_agent_call(
                    final_evaluator,
                    ListAgentEvaluationResult(evaluations=evaluations),
                    "run"
                )
                final_eval_time = time.time() - final_eval_start
                total_input_tokens += token_count_result.total
                total_output_tokens += output_tokens
                
                # Track final evaluator time
                final_model_name = f"final_{config.final_evaluator_model}"
                if final_model_name not in model_execution_times:
                    model_execution_times[final_model_name] = 0.0
                model_execution_times[final_model_name] += final_eval_time
                
                # Créer l'évaluation finale
                evaluation_result = from_AgentEvaluationResult_to_EvaluationResult(final_evaluation)
                evaluation_result.model = f"final_{config.final_evaluator_model}"
                
            elif len(evaluations) == 1:
                logger.info("Un seul évaluateur")
                # Un seul évaluateur
                evaluation_result = from_AgentEvaluationResult_to_EvaluationResult(evaluations[0])
                evaluation_result.model = config.evaluator_models[0]
            else:
                # Plusieurs évaluateurs sans final - faire la moyenne
                avg_score = sum(eval.score for eval in evaluations) // len(evaluations)
                avg_cosine = sum(eval.cosine_similarity for eval in evaluations) / len(evaluations)
                feedbacks = "; ".join(eval.feedback for eval in evaluations)
                
                evaluation_result = EvaluationResult(
                    score=avg_score,
                    feedback=f"Moyenne de {len(evaluations)} évaluateurs: {feedbacks}",
                    model="consolidated"
                )
            
            # Créer la réponse utilisateur
            user_response = UserResponse(
                question_id=question_id,
                question_text=question['content'],
                user_answer=user_answer,
                date_sent=datetime.now(),
                evaluation=evaluation_result
            )
            
            responses.append(user_response)
            
            # Avancer à la question suivante si le score est suffisant
            if evaluation_result.score >= 7:
                self.session_manager.increment_current_index(session_id)
                
            question_time = time.time() - question_start
            logger.info(f"Question {i+1} évaluée en {question_time:.2f}s (eval: {eval_time:.2f}s)")
            
        # Mettre à jour la session avec toutes les réponses
        for response in responses:
            self.session_manager.add_response(session_id, response)
            
        # Calculer le temps total
        total_evaluation_time = time.time() - start_time
        
        # Créer le statut de session final
        session_status = self.session_manager.get_session_status(session_id)
        
        return SessionEvaluationResult(
            config=config,
            session_status=session_status,
            total_evaluation_time=total_evaluation_time,
            token_usage={
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens
            },
            model_execution_times=model_execution_times
        )
        
    async def run_comprehensive_evaluation(self) -> List[SessionEvaluationResult]:
        """Exécute une évaluation complète avec différentes configurations."""
        configurations = [
            SessionEvaluationConfig(
                evaluator_models=["ministral-3b-latest"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-3b-latest"
            ),
            SessionEvaluationConfig(
                evaluator_models=["ministral-8b-latest"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-3b-latest"
            ),
            SessionEvaluationConfig(
                evaluator_models=["mistral-small"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-3b-latest"
            ),
            SessionEvaluationConfig(
                evaluator_models=["mistral-medium"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-3b-latest"
            ),
            SessionEvaluationConfig(
                evaluator_models=["mistral-large-latest"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-3b-latest"
            ),

            SessionEvaluationConfig(
                evaluator_models=["ministral-3b-latest" for _ in range(3)],
                nb_evaluators=3,
                with_final_evaluator=True,
                final_evaluator_model="ministral-3b-latest"
            ),

            SessionEvaluationConfig(
                evaluator_models=["ministral-8b-latest" for _ in range(3)],
                nb_evaluators=3,
                with_final_evaluator=True,
                final_evaluator_model="ministral-8b-latest"
            ),



        ]
        
        logger.info(f"Début de l'évaluation complète avec {len(configurations)} configurations...")
        
        results = []
        
        for i, config in enumerate(configurations):
            logger.info(f"\n=== Configuration {i+1}/{len(configurations)}: {config.get_description()} ===")
            
            try:
                # Créer une nouvelle session pour cette configuration
                session_id = await self.initialize_session()
                logger.info(f"Session créée: {session_id}")
                
                # Évaluer la session
                result = await self.evaluate_session(session_id, config, is_local=False)
                results.append(result)
                
                logger.info(f"Évaluation terminée en {result.total_evaluation_time:.2f}s")
                logger.info(f"Tokens utilisés: {result.token_usage['total_tokens']}")
                logger.info(f"Score moyen: {self._calculate_average_score(result.session_status):.1f}")
                
            except Exception as e:
                logger.error(f"Erreur lors de l'évaluation avec {config.get_description()}: {str(e)}")
                continue
        
        return results

    async def run_comprehensive_evaluation_local(self) -> List[SessionEvaluationResult]:
        """Exécute une évaluation complète avec différentes configurations."""

        # Définir les configurations à tester
        configurations = [

            SessionEvaluationConfig(
                evaluator_models=["ministral-3:3b"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-3:3b"
            ),
            SessionEvaluationConfig(
                evaluator_models=["cas/ministral-8b-instruct-2410_q4km"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-8b-latest"
            ),
            SessionEvaluationConfig(
                evaluator_models=["llama3.1:8b"],
                nb_evaluators=1,
                with_final_evaluator=False,
                final_evaluator_model="ministral-8b-latest"
            ),
        ]

        logger.info(f"Début de l'évaluation complète avec {len(configurations)} configurations...")

        results = []

        for i, config in enumerate(configurations):
            logger.info(f"\n=== Configuration {i + 1}/{len(configurations)}: {config.get_description()} ===")

            try:
                # Créer une nouvelle session pour cette configuration
                session_id = await self.initialize_session()
                logger.info(f"Session créée: {session_id}")

                # Évaluer la session
                result = await self.evaluate_session(session_id, config)
                results.append(result)

                logger.info(f"Évaluation terminée en {result.total_evaluation_time:.2f}s")
                logger.info(f"Tokens utilisés: {result.token_usage['total_tokens']}")
                logger.info(f"Score moyen: {self._calculate_average_score(result.session_status):.1f}")

            except Exception as e:
                logger.error(f"Erreur lors de l'évaluation avec {config.get_description()}: {str(e)}")
                continue

        return results
    def _calculate_average_score(self, session_status: SessionStatus) -> float:
        """Calcule le score moyen pour une session."""
        scores = []
        for response in session_status.responses:
            if response.evaluation:
                scores.append(response.evaluation.score)
        return sum(scores) / len(scores) if scores else 0.0
        
    def export_results_to_json(self, results: List[SessionEvaluationResult], filename: str = "mediation_session_results.json") -> None:
        """Exporte les résultats au format JSON."""
        results_dict = [result.to_dict() for result in results]
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Résultats exportés dans {filename}")
    
    def export_results_to_csv(self, results: List[SessionEvaluationResult], filename: str = "mediation_session_results.csv") -> None:
        """Exporte les résultats au format CSV avec questions et réponses de chaque modèle."""
        import csv
        
        # Préparer les données pour le CSV
        csv_data = []
        
        # Pour chaque configuration (modèle), ajouter les questions et réponses
        for result in results:
            config = result.config
            session_status = result.session_status
            
            # Créer un nom de configuration lisible
            config_name = config.get_description()
            
            # Pour chaque question/réponse dans la session
            for i, response in enumerate(session_status.responses):
                question_text = response.question_text
                user_answer = response.user_answer
                
                # Ajouter une ligne avec la question et la réponse
                csv_data.append({
                    "Configuration": config_name,
                    "Question": question_text,
                    "Réponse": user_answer,
                    "Score": response.evaluation.score if response.evaluation else "N/A",
                    "Feedback": response.evaluation.feedback if response.evaluation else "N/A",
                    "Modèle": response.evaluation.model if response.evaluation else "N/A"
                })
            
            # Ajouter les temps d'exécution par modèle
            for model_name, exec_time in result.model_execution_times.items():
                csv_data.append({
                    "Configuration": config_name,
                    "Model": model_name,
                    "Execution Time (s)": f"{exec_time:.3f}",
                    "Type": "Model Timing"
                })
        
        # Écrire dans le fichier CSV
        with open(filename, "w", encoding="utf-8", newline='') as f:
            if csv_data:
                # Get all possible fieldnames from the data
                all_fieldnames = set()
                for row in csv_data:
                    all_fieldnames.update(row.keys())
                fieldnames = list(all_fieldnames)
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_data)
        
        logger.info(f"Résultats exportés en CSV dans {filename}")
        
    def generate_comparison_report(self, results: List[SessionEvaluationResult]) -> str:
        """Génère un rapport comparatif des résultats."""
        report = """
# Rapport d'évaluation des sessions de médiation

## Résumé des configurations testées

"""
        
        # Grouper par type de modèle principal
        by_model_type = {}
        for result in results:
            config = result.config
            # Déterminer le type principal
            if any("ministral" in model for model in config.evaluator_models):
                model_type = "ministral"
            else:
                model_type = "mistral"
            
            if model_type not in by_model_type:
                by_model_type[model_type] = []
            by_model_type[model_type].append(result)
        
        # Analyser chaque type de modèle
        for model_type in by_model_type:
            report += f"### Modèles {model_type}\n\n"
            type_results = by_model_type[model_type]
            
            # Trouver la meilleure configuration pour ce type
            best_config = min(type_results, key=lambda x: x.total_evaluation_time / self._calculate_average_score(x.session_status))
            
            report += f"**Meilleure configuration**: {best_config.config.get_description()}\n"
            report += f"- Score moyen: {self._calculate_average_score(best_config.session_status):.1f}\n"
            report += f"- Temps total: {best_config.total_evaluation_time:.2f}s\n"
            report += f"- Tokens totaux: {best_config.token_usage['total_tokens']}\n"
            report += f"- Efficacité (score/temps): {self._calculate_average_score(best_config.session_status) / best_config.total_evaluation_time:.2f} score/s\n\n"
            
            # Tableau comparatif
            report += "| Configuration | Score moyen | Temps (s) | Tokens | Efficacité (score/s) |\n"
            report += "|---------------|-------------|-----------|--------|---------------------|\n"
            
            for result in sorted(type_results, key=lambda x: x.total_evaluation_time):
                avg_score = self._calculate_average_score(result.session_status)
                efficiency = avg_score / result.total_evaluation_time if result.total_evaluation_time > 0 else 0
                report += f"| {result.config.get_description()} | {avg_score:.1f} | {result.total_evaluation_time:.2f} | {result.token_usage['total_tokens']} | {efficiency:.3f} |\n"
            
            report += "\n"
        
        # Analyse des temps d'exécution par modèle
        report += "## Analyse des temps d'exécution par modèle\n\n"

        # Group by model and calculate statistics
        model_timing_stats = {}
        for result in results:
            for model_name, exec_time in result.model_execution_times.items():
                if model_name not in model_timing_stats:
                    model_timing_stats[model_name] = []
                model_timing_stats[model_name].append(exec_time)

        # Generate timing table
        report += "| Modèle | Temps moyen (s) | Temps min (s) | Temps max (s) | Écart-type |\n"
        report += "|--------|-----------------|---------------|---------------|------------|\n"

        for model_name in sorted(model_timing_stats.keys()):
            times = model_timing_stats[model_name]
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            std_dev = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5 if len(times) > 1 else 0

            report += f"| {model_name} | {avg_time:.3f} | {min_time:.3f} | {max_time:.3f} | {std_dev:.3f} |\n"

        report += "\n"

        # Analyse globale
        all_scores = [self._calculate_average_score(r.session_status) for r in results]
        all_times = [r.total_evaluation_time for r in results]
        all_tokens = [r.token_usage['total_tokens'] for r in results]
        
        report += "## Analyse globale\n"
        report += f"- Score moyen global: {((sum(all_scores) / len(all_scores)) if all_scores else 0):.1f}\n"
        report += f"- Temps moyen: {((sum(all_times) / len(all_times)) if all_times else 0):.2f}s\n"
        report += f"- Tokens moyens: {(sum(all_tokens) / len(all_tokens) if all_tokens else 0):.0f}\n"

        if results:
        # Meilleure configuration globale (meilleur compromis score/temps)
            best_global = max(results,
                              key=lambda x: self._calculate_average_score(x.session_status) / x.total_evaluation_time,
                              default=0)
            report += f"- Meilleure configuration globale: {best_global.config.get_description()}\n"
            report += f"  - Score: {self._calculate_average_score(best_global.session_status):.1f}\n"
            report += f"  - Temps: {best_global.total_evaluation_time:.2f}s\n"
            report += f"  - Efficacité: {self._calculate_average_score(best_global.session_status) / best_global.total_evaluation_time:.3f} score/s\n"
        
        return report


async def main():
    """Fonction principale asynchrone."""
    logger.info("Début du script d'évaluation des sessions de médiation")
    
    try:
        # Créer l'évaluateur
        evaluator = MediationSessionEvaluator()
        
        # Exécuter l'évaluation complète
        results = await evaluator.run_comprehensive_evaluation()
        
        # Exporter les résultats
        evaluator.export_results_to_json(results)
        evaluator.export_results_to_csv(results)  # Export CSV ajouté
        
        # Générer et afficher le rapport
        report = evaluator.generate_comparison_report(results)
        print(report)
        
        # Sauvegarder le rapport
        with open("mediation_session_report.md", "w", encoding="utf-8") as f:
            f.write(report)
        
        logger.info("Évaluation terminée avec succès!")
        
    except Exception as e:
        logger.error(f"Erreur fatale: {str(e)}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    # Exécuter la fonction principale asynchrone
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    exit_code = asyncio.run(main())
    exit(exit_code)