#!/usr/bin/env python3
"""
Script pour comparer les évaluations de plusieurs agents à la réponse d'un utilisateur.
Ce script utilise uniquement l'API Mistral pour évaluer les réponses avec 6 types d'agents
et 3 modèles différents (18 combinaisons au total).

Pour chaque question, le script sauvegarde dans un fichier CSV:
- La réponse de l'utilisateur
- La note donnée par chaque agent
- Le temps de traitement
- Le nombre de tokens consommés
- Le feedback détaillé

Utilisation:
    python compare_agent_evaluations.py
"""

import csv
import asyncio
import time
import json
from typing import List, Dict
from agents.answer_evaluator_agent import get_evaluator_agent, get_final_evaluator_agent, EvaluateRequestInput, AgentEvaluationResult, ListAgentEvaluationResult
from agents.evaluator_prompts import (evaluation_system_base, evaluation_system_strict,
                                     evaluation_system_bienveillant, evaluation_system_pedagogique,
                                     evaluation_system_creatif, evaluation_system_minimaliste)
from agents.token_monitor import monitor_agent_call_async
from database.database import get_db_connection, get_questions_by_ids, get_question_by_id

# Document ID et IDs des questions spécifiques
document_id = "dbd5f14a9e6545880b0cd505583ea7d1fe1e8b3d"
question_ids = [249, 370, 737, 786, 115]  # IDs spécifiques depuis question_session.py
responses_file = "../reponses-test-lochi-mondu.txt"  # Fichier contenant les réponses utilisateur
session_id = "test"


def load_user_responses_from_file(file_path: str) -> List[str]:
    """
    Charge les réponses utilisateur depuis un fichier texte.

    Args:
        file_path: Chemin vers le fichier contenant les réponses

    Returns:
        Liste des réponses utilisateur
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Lire toutes les lignes et supprimer les espaces vides
            responses = [line.strip() for line in f.readlines() if line.strip()]
        return responses
    except FileNotFoundError:
        print(f"Erreur: Le fichier {file_path} n'a pas été trouvé.")
        return []
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier: {e}")
        return []


class AgentEvaluatorComparator:
    def __init__(self):
        """Initialise le comparateur avec la configuration pour l'API Mistral."""
        self.agents_config = self._generate_mistral_api_config()

    def _generate_mistral_api_config(self) -> List[Dict]:
        """Génère la configuration pour 6 agents × 3 modèles Mistral API."""
        # Modèles Mistral disponibles via API
        mistral_models = ["ministral-3b-latest", "ministral-8b-latest", "mistral-small"]

        # Types d'agents avec leurs prompts
        agent_types = [
            ("base", evaluation_system_base),
            ("strict", evaluation_system_strict),
            ("bienveillant", evaluation_system_bienveillant),
            ("pedagogique", evaluation_system_pedagogique),
            ("creatif", evaluation_system_creatif),
            ("minimaliste", evaluation_system_minimaliste)
        ]

        # Générer toutes les combinaisons pour API Mistral
        config = []
        for agent_name, prompt in agent_types:
            for model in mistral_models:
                config.append({
                    "name": f"{agent_name}_{model}",
                    "agent_type": agent_name,
                    "model": model,
                    "provider": "mistral",
                    "prompt": prompt
                })

        return config

    async def fetch_questions_from_database(self, document_id: str, question_ids: List[int]) -> List[Dict]:
        """
        Récupère les questions spécifiques depuis la base de données PostgreSQL.

        Args:
            document_id: ID du document (pour référence)
            question_ids: Liste spécifique d'IDs de questions à récupérer

        Returns:
            Liste de dictionnaires avec les questions et leurs réponses
        """
        conn = None
        try:
            # Établir la connexion à la base de données
            conn = await get_db_connection()

            # Récupérer uniquement les questions spécifiques par leurs IDs
            # Sans aucun filtre de statut
            questions = await get_questions_by_ids(question_ids, conn)

            # Formater les données pour correspondre au format attendu
            session_data = []
            for question in questions:
                # Trouver la réponse correcte (is_correct = True)
                correct_answer = None
                for answer in question.get("answers", []):
                    if answer.get("is_correct", False):
                        correct_answer = answer["content"]
                        break

                # Si pas de réponse correcte, prendre la première réponse
                if not correct_answer and question.get("answers"):
                    correct_answer = question["answers"][0]["content"]

                # Créer l'entrée pour la session
                if correct_answer:
                    session_data.append({
                        "session_id": f"eval_{document_id}_{question['question_id']}",
                        "question_id": question["question_id"],
                        "question_text": question["content"],
                        "expected_answer": correct_answer,
                        "user_answer": correct_answer  # Utilisation de la réponse correcte comme réponse utilisateur
                    })
                else:
                    print(f"Avertissement: La question {question['question_id']} n'a pas de réponse valide.")

            return session_data

        except Exception as e:
            print(f"Erreur lors de la récupération des questions: {e}")
            return []

        finally:
            if conn:
                await conn.close()

    async def fetch_questions_and_responses(self, document_id: str, question_ids: List[int], responses_file: str) -> List[Dict]:
        """
        Récupère les questions depuis la base de données et les associe aux réponses utilisateur.

        Args:
            document_id: ID du document (pour référence)
            question_ids: Liste spécifique d'IDs de questions à récupérer
            responses_file: Chemin vers le fichier contenant les réponses utilisateur

        Returns:
            Liste de dictionnaires avec les questions, réponses attendues et réponses utilisateur
        """
        # Charger les réponses utilisateur
        user_responses = load_user_responses_from_file(responses_file)

        if len(user_responses) != len(question_ids):
            print(f"⚠️  Avertissement: Nombre de réponses ({len(user_responses)}) différent du nombre de questions ({len(question_ids)})")
            print("Seules les questions avec une réponse correspondante seront évaluées.")

        conn = None
        try:
            # Établir la connexion à la base de données
            conn = await get_db_connection()

            # Récupérer les questions spécifiques par leurs IDs
            questions_tasks = [get_question_by_id(conn, question_id, include_answers=True)
                               for question_id in question_ids]
            questions = await asyncio.gather(*questions_tasks)
            print(questions)
            # Formater les données pour correspondre au format attendu
            session_data = []
            for i, question in enumerate(questions):
                # Trouver la réponse correcte (is_correct = True)
                correct_answer = None
                for answer in question.get("answers", []):
                    if answer.get("is_correct", False):
                        correct_answer = answer["content"]
                        break

                # Si pas de réponse correcte, prendre la première réponse
                if not correct_answer and question.get("answers"):
                    correct_answer = question["answers"][0]["content"]

                # Vérifier qu'il y a une réponse utilisateur correspondante
                if i < len(user_responses) and correct_answer:
                    session_data.append({
                        "session_id": f"eval_{document_id}_{question['question_id']}",
                        "question_id": question["question_id"],
                        "question_text": question["content"],
                        "expected_answer": correct_answer,
                        "user_answer": user_responses[i]  # Utilisation de la réponse utilisateur préfaute
                    })
                elif correct_answer:
                    print(f"Avertissement: Pas de réponse utilisateur pour la question {question['question_id']}")
                else:
                    print(f"Avertissement: La question {question['question_id']} n'a pas de réponse valide.")

            return session_data

        except Exception as e:
            print(f"Erreur lors de la récupération des questions: {e}")
            return []

        finally:
            if conn:
                await conn.close()

    async def _evaluate_single_agent(self,
                                     question_id: int,
                                     question_text: str,
                                     config: Dict,
                                     input_data: EvaluateRequestInput) -> Dict:
        """Évalue avec un seul agent via API Mistral avec mesures de performance."""
        start_time = time.time()
        # Créer l'agent pour API Mistral
        agent = get_evaluator_agent(
            model=config["model"],
            provider=config["provider"],
            async_mode=True,
            custom_system_prompt_generator=config["prompt"]
        )

        # Déclarer toutes les variables en amont
        response = None
        input_tokens = None
        output_tokens = None
        processing_time = None
        error = None

        data_dict = {
            "question_id": question_id,
            "question_text": question_text,
            "agent_name": config["name"],
            "agent_type": config["agent_type"],
            "model": config["model"],
            "provider": config["provider"],
            "score": None,
            "feedback": None,
            "processing_time_sec": None,
            "input_tokens_total": None,
            "input_tokens_system": None,
            "input_tokens_history": None,
            "input_tokens_tools": None,
            "output_tokens": None,
            "total_tokens": None,
            "error": None,
            "model_used": None
        }

        try:
            # Utiliser le moniteur de tokens pour l'évaluation
            response, input_tokens, output_tokens = await monitor_agent_call_async(
                agent, input_data, "run_async"
            )
        except Exception as e:
            error = e
            print(e)

        # Calculer le temps de traitement
        processing_time = time.time() - start_time

        # Mettre à jour le dictionnaire avec les valeurs obtenues ou l'erreur
        if response is not None:
            data_dict["score"] = response.score
            data_dict["feedback"] = response.feedback
            data_dict["input_tokens_total"] = input_tokens.total
            data_dict["input_tokens_system"] = input_tokens.system_prompt
            data_dict["input_tokens_history"] = input_tokens.history
            data_dict["input_tokens_tools"] = input_tokens.tools
            data_dict["output_tokens"] = output_tokens
            data_dict["total_tokens"] = input_tokens.total + output_tokens
            data_dict["model_used"] = input_tokens.model
            print(f"{config["model"]}: ({response.score}) {response.feedback}")
        else:
            data_dict["error"] = str(error)

        data_dict["processing_time_sec"] = round(processing_time, 3)

        #print("Data dict correctement généré!")
        #print(data_dict)
        return data_dict

    async def evaluate_with_all_agents(self, question_id: int,
                                       question_text: str,
                                       expected_answer: str,
                                       user_answer: str) -> List[Dict]:
        """Évalue une réponse avec les 18 combinaisons via API Mistral."""
        results = []
        tasks = []

        # Créer les tâches d'évaluation
        input_data = EvaluateRequestInput(
            question=question_text,
            expected_answer=expected_answer,
            user_answer=user_answer
        )

        for config in self.agents_config:
            task = self._evaluate_single_agent(question_id, question_text, config, input_data)
            tasks.append(task)

        # Exécuter par lots de 3 pour éviter la surcharge de l'API Mistral
        for i in range(0, len(tasks), 3):
            batch = tasks[i:i+3]
            batch_results = await asyncio.gather(*batch)
            results.extend(batch_results)
            # Délai entre les lots pour respecter les limites de taux de l'API
            await asyncio.sleep(5.0)

        return results

    def save_results_to_csv(self, results: List[Dict], session_id: str, question_id: int, question_text: str, output_file: str):
        """Sauvegarde les résultats dans un fichier CSV optimisé pour l'analyse."""
        fieldnames = [
            "session_id", "question_id", "question_text",
            "agent_name", "agent_type", "model", "provider",
            "score", "feedback",
            "processing_time_sec",
            "input_tokens_total", "input_tokens_system", "input_tokens_history", "input_tokens_tools",
            "output_tokens", "total_tokens",
            "error", "model_used", "timestamp"
        ]

        # Ajouter le timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        for result in results:
            result["timestamp"] = timestamp

        # Vérifier si le fichier existe et a l'en-tête
        mode = 'a' if self._file_exists_and_has_header(output_file, fieldnames) else 'w'

        with open(output_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if mode == 'w':
                writer.writeheader()

            for result in results:
                # Convertir les valeurs None en chaînes vides pour le CSV
                row_data = {}
                for field in fieldnames:
                    value = result.get(field, "")
                    row_data[field] = value if value is not None else ""
                writer.writerow(row_data)

    def _file_exists_and_has_header(self, filepath: str, fieldnames: List[str]) -> bool:
        """Vérifie si le fichier existe et contient déjà l'en-tête."""
        try:
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                return header is not None and header == fieldnames
        except (FileNotFoundError, StopIteration):
            return False

    def generate_summary_statistics(self, results: List[Dict]) -> Dict:
        """Génère des statistiques complètes pour l'analyse des performances."""
        successful_evals = [r for r in results if r["error"] is None]
        failed_evals = [r for r in results if r["error"] is not None]

        # Statistiques de temps
        processing_times = [r["processing_time_sec"] for r in successful_evals if r["processing_time_sec"] is not None]
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
        min_time = min(processing_times) if processing_times else 0
        max_time = max(processing_times) if processing_times else 0

        # Statistiques de tokens
        total_tokens_list = [r["total_tokens"] for r in successful_evals if r["total_tokens"] is not None]
        avg_tokens = sum(total_tokens_list) / len(total_tokens_list) if total_tokens_list else 0
        min_tokens = min(total_tokens_list) if total_tokens_list else 0
        max_tokens = max(total_tokens_list) if total_tokens_list else 0

        # Statistiques par type d'agent
        agent_stats = {}
        for result in successful_evals:
            agent_type = result["agent_type"]
            if agent_type not in agent_stats:
                agent_stats[agent_type] = {
                    "count": 0,
                    "scores": [],
                    "times": [],
                    "tokens": [],
                    "models": []
                }

            stats = agent_stats[agent_type]
            stats["count"] += 1
            if result["score"] is not None:
                stats["scores"].append(result["score"])
            if result["processing_time_sec"] is not None:
                stats["times"].append(result["processing_time_sec"])
            if result["total_tokens"] is not None:
                stats["tokens"].append(result["total_tokens"])
            if result["model_used"]:
                stats["models"].append(result["model_used"])

        # Calculer les moyennes par agent
        for agent_type, stats in agent_stats.items():
            stats["avg_score"] = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0
            stats["avg_time"] = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            stats["avg_tokens"] = sum(stats["tokens"]) / len(stats["tokens"]) if stats["tokens"] else 0
            stats["models_used"] = list(stats["models"])

        # Statistiques par modèle
        model_stats = {}
        for result in successful_evals:
            model = result["model_used"]
            if model not in model_stats:
                model_stats[model] = {
                    "count": 0,
                    "times": [],
                    "tokens": [],
                    "agent_types": set()
                }

            stats = model_stats[model]
            stats["count"] += 1
            if result["processing_time_sec"] is not None:
                stats["times"].append(result["processing_time_sec"])
            if result["total_tokens"] is not None:
                stats["tokens"].append(result["total_tokens"])
            stats["agent_types"].add(result["agent_type"])

        for model, stats in model_stats.items():
            stats["avg_time"] = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            stats["avg_tokens"] = sum(stats["tokens"]) / len(stats["tokens"]) if stats["tokens"] else 0
            stats["agent_types"] = list(stats["agent_types"])

        return {
            "total_evaluations": len(results),
            "successful_evaluations": len(successful_evals),
            "failed_evaluations": len(failed_evals),
            "success_rate": len(successful_evals) / len(results) if results else 0,
            "time_statistics": {
                "average_sec": round(avg_time, 3),
                "minimum_sec": round(min_time, 3),
                "maximum_sec": round(max_time, 3),
                "total_sec": round(sum(processing_times), 1)
            },
            "token_statistics": {
                "average": round(avg_tokens, 2),
                "minimum": min_tokens,
                "maximum": max_tokens,
                "total": sum(total_tokens_list)
            },
            "agent_statistics": agent_stats,
            "model_statistics": model_stats,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    async def evaluate_session_questions(self, session_data: List[Dict], output_file: str) -> Dict:
        """Évalue toutes les questions d'une session avec rapport complet."""
        all_results = []
        session_id = session_data[0]["session_id"] if session_data else "unknown"

        print(f"\n{'='*80}")
        print(f"DÉBUT DE L'ÉVALUATION - Session: {session_id}")
        print(f"{'='*80}")
        print(f"Configuration:")
        print(f"  - Nombre de questions: {len(session_data)}")
        print(f"  - Évaluations par question: {len(self.agents_config)}")
        print(f"  - Total d'évaluations: {len(session_data) * len(self.agents_config)}")
        print(f"  - Modèles utilisés: mistral-small, mistral-medium, mistral-large")
        print(f"  - Types d'agents: base, strict, bienveillant, pedagogique, creatif, minimaliste")
        print(f"{'='*80}\n")

        for i, question_data in enumerate(session_data, 1):
            question_id = question_data["question_id"]
            question_text = question_data["question_text"]
            expected_answer = question_data["expected_answer"]
            user_answer = question_data["user_answer"]

            print(f"[{i}/{len(session_data)}] Question {question_id}:")
            print(f"  Q: {question_text[:60]}...")
            print(f"  A: {user_answer[:40]}...")

            start_question_time = time.time()

            results = await self.evaluate_with_all_agents(
                question_id=question_id,
                question_text=question_text,
                expected_answer=expected_answer,
                user_answer=user_answer
            )

            self.save_results_to_csv(
                results=results,
                session_id=session_id,
                question_id=question_id,
                question_text=question_text,
                output_file=output_file
            )

            all_results.extend(results)

            question_time = time.time() - start_question_time
            successful = sum(1 for r in results if r['error'] is None)
            print(f"  ✓ Terminée en {question_time:.1f} sec")
            print(f"  ✓ Évaluations réussies: {successful}/{len(results)}")
            if successful > 0:
                avg_time = sum(r['processing_time_sec'] for r in results if r['processing_time_sec']) / successful
                print(f"  ✓ Temps moyen: {avg_time:.2f} sec")
            else:
                print(f"  ✗ Aucune évaluation réussie")
            print()

        # Générer les statistiques globales
        summary_stats = self.generate_summary_statistics(all_results)
        print(summary_stats)
        # Sauvegarder les statistiques
        stats_filename = output_file.replace('.csv', '_stats.json')
        self._save_summary_statistics(summary_stats, stats_filename)

        # Afficher le rapport final
        self._display_final_report(summary_stats, output_file, stats_filename, session_id)

        return summary_stats

    def _save_summary_statistics(self, stats: Dict, filename: str):
        """Sauvegarde les statistiques au format JSON."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def _display_final_report(self, stats: Dict, csv_file: str, stats_file: str, session_id: str):
        """Affiche un rapport final complet dans la console."""
        print(f"{'='*80}")
        print(f"RAPPORT FINAL - Session: {session_id}")
        print(f"{'='*80}")

        # Résumé général
        print(f"\n📊 RÉSUMÉ GÉNÉRAL:")
        print(f"  Évaluations totales: {stats['total_evaluations']}")
        print(f"  Réussites: {stats['successful_evaluations']} ({stats['success_rate']:.1%})")
        print(f"  Échecs: {stats['failed_evaluations']}")

        # Performances temporelles
        print(f"\n⏱️  PERFORMANCES TEMPORELLES:")
        time_stats = stats['time_statistics']
        print(f"  Temps moyen: {time_stats['average_sec']} sec")
        print(f"  Temps minimum: {time_stats['minimum_sec']} sec")
        print(f"  Temps maximum: {time_stats['maximum_sec']} sec")
        print(f"  Temps total: {time_stats['total_sec']} sec")

        # Consommation de tokens
        print(f"\n🪙 CONSOMMATION DE TOKENS:")
        token_stats = stats['token_statistics']
        print(f"  Tokens moyens: {token_stats['average']}")
        print(f"  Tokens minimum: {token_stats['minimum']}")
        print(f"  Tokens maximum: {token_stats['maximum']}")
        print(f"  Tokens totaux: {token_stats['total']}")

        # Statistiques par modèle
        print(f"\n🤖 PERFORMANCES PAR MODÈLE:")
        for model, model_data in stats['model_statistics'].items():
            print(f"  {model}:")
            print(f"    Évaluations: {model_data['count']}")
            print(f"    Temps moyen: {model_data['avg_time']:.3f} sec")
            print(f"    Tokens moyens: {model_data['avg_tokens']:.1f}")
            print(f"    Types d'agents: {', '.join(model_data['agent_types'])}")

        # Fichiers générés
        print(f"\n📁 FICHIERS GÉNÉRÉS:")
        print(f"  Résultats détaillés: {csv_file}")
        print(f"  Statistiques: {stats_file}")

        print(f"\n{'='*80}\n")

    def load_evaluations_from_csv(self, csv_file: str) -> Dict[int, Dict[str, List[Dict]]]:
        """
        Charge les évaluations depuis le fichier CSV et les regroupe par question et modèle.

        Args:
            csv_file: Chemin vers le fichier CSV contenant les évaluations

        Returns:
            Dictionnaire organisé par question_id, puis par model, contenant les évaluations
        """
        evaluations_by_question = {}

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    question_id = int(row['question_id'])
                    model = row['model']
                    agent_type = row['agent_type']

                    # Créer la structure si elle n'existe pas
                    if question_id not in evaluations_by_question:
                        evaluations_by_question[question_id] = {}

                    if model not in evaluations_by_question[question_id]:
                        evaluations_by_question[question_id][model] = []

                    # Ajouter l'évaluation
                    evaluations_by_question[question_id][model].append({
                        "agent_type": agent_type,
                        "score": int(row['score']) if row['score'] else None,
                        "feedback": row['feedback'],
                        "processing_time_sec": float(row['processing_time_sec']) if row['processing_time_sec'] else None,
                        "total_tokens": int(row['total_tokens']) if row['total_tokens'] else None
                    })

            return evaluations_by_question

        except FileNotFoundError:
            print(f"Erreur: Le fichier {csv_file} n'a pas été trouvé.")
            return {}
        except Exception as e:
            print(f"Erreur lors de la lecture du CSV: {e}")
            return {}

    async def create_final_evaluations(self, evaluations_by_question: Dict[int, Dict[str, List[Dict]]],
                                       output_file: str) -> None:
        """
        Crée des évaluations finales en utilisant l'agent final pour chaque question et modèle.

        Args:
            evaluations_by_question: Évaluations regroupées par question et modèle
            output_file: Chemin pour sauvegarder les évaluations finales
        """
        final_evaluations = []
        final_stats = {
            "total_questions": len(evaluations_by_question),
            "total_final_evaluations": 0,
            "successful_evaluations": 0,
            "failed_evaluations": 0,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"\n{'='*80}")
        print("DÉBUT DE L'ÉVALUATION FINALE")
        print(f"{'='*80}")

        for question_id, models_data in evaluations_by_question.items():
            print(f"\nTraitement de la question {question_id}...")

            for model, evaluations in models_data.items():
                # Nous voulons 3 évaluations par modèle (une par type d'agent)
                # Sélectionner les 3 premières évaluations disponibles
                selected_evaluations = evaluations[:3]

                if len(selected_evaluations) < 3:
                    print(f"  ⚠️  Moins de 3 évaluations disponibles pour {model} (seulement {len(selected_evaluations)})")
                    continue

                print(f"  Évaluation finale pour {model} avec {len(selected_evaluations)} évaluations...")

                # Préparer les données pour l'agent final
                input_data = ListAgentEvaluationResult(
                    evaluations=[AgentEvaluationResult(
                        score=eval_data["score"],
                        feedback=eval_data["feedback"]
                    ) for eval_data in selected_evaluations]
                )

                try:
                    # Obtenir l'agent final pour le modèle actuel
                    final_agent = get_final_evaluator_agent(model=model, provider="mistral", async_mode=True)

                    start_time = time.time()

                    # Exécuter l'évaluation finale
                    final_result = await final_agent.run_async(input_data)

                    processing_time = time.time() - start_time

                    # Enregistrer le résultat final
                    final_evaluations.append({
                        "question_id": question_id,
                        "model": model,
                        "agent_types": [eval_data["agent_type"] for eval_data in selected_evaluations],
                        "final_score": final_result.score,
                        "final_feedback": final_result.feedback,
                        "processing_time_sec": round(processing_time, 3),
                        "input_evaluations": selected_evaluations,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })

                    final_stats["total_final_evaluations"] += 1
                    final_stats["successful_evaluations"] += 1
                    print(f"    ✓ Évaluation finale réussie - Score: {final_result.score}/10")

                except Exception as e:
                    processing_time = time.time() - start_time
                    print(f"    ✗ Erreur lors de l'évaluation finale: {str(e)}")

                    final_evaluations.append({
                        "question_id": question_id,
                        "model": model,
                        "agent_types": [eval_data["agent_type"] for eval_data in selected_evaluations],
                        "final_score": None,
                        "final_feedback": None,
                        "processing_time_sec": round(processing_time, 3),
                        "input_evaluations": selected_evaluations,
                        "error": str(e),
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })

                    final_stats["total_final_evaluations"] += 1
                    final_stats["failed_evaluations"] += 1

        # Sauvegarder les résultats finaux
        self.save_final_evaluations_to_csv(final_evaluations, output_file)
        self.save_final_statistics(final_stats, output_file.replace('.csv', '_final_stats.json'))

        # Afficher le rapport final
        self.display_final_evaluation_report(final_stats, output_file)

        print(f"\n{'='*80}")
        print("ÉVALUATION FINALE TERMINÉE")
        print(f"{'='*80}")

    def save_final_evaluations_to_csv(self, final_evaluations: List[Dict], output_file: str) -> None:
        """Sauvegarde les évaluations finales dans un fichier CSV."""
        fieldnames = [
            "question_id", "model", "agent_types",
            "final_score", "final_feedback",
            "processing_time_sec", "timestamp", "error"
        ]

        # Ajouter les champs pour les évaluations d'entrée
        for i in range(3):  # 3 évaluations max par modèle
            fieldnames.extend([f"input_agent_{i+1}", f"input_score_{i+1}", f"input_feedback_{i+1}"])

        mode = 'w'  # Toujours créer un nouveau fichier pour les évaluations finales

        with open(output_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for eval_data in final_evaluations:
                row = {
                    "question_id": eval_data["question_id"],
                    "model": eval_data["model"],
                    "agent_types": ", ".join(eval_data["agent_types"]),
                    "final_score": eval_data["final_score"],
                    "final_feedback": eval_data["final_feedback"],
                    "processing_time_sec": eval_data["processing_time_sec"],
                    "timestamp": eval_data["timestamp"],
                    "error": eval_data.get("error", "")
                }

                # Ajouter les données des évaluations d'entrée
                for i, input_eval in enumerate(eval_data["input_evaluations"][:3]):
                    row[f"input_agent_{i+1}"] = input_eval["agent_type"]
                    row[f"input_score_{i+1}"] = input_eval["score"]
                    row[f"input_feedback_{i+1}"] = input_eval["feedback"]

                writer.writerow(row)

    def save_final_statistics(self, stats: Dict, filename: str) -> None:
        """Sauvegarde les statistiques des évaluations finales."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def display_final_evaluation_report(self, stats: Dict, output_file: str) -> None:
        """Affiche un rapport des évaluations finales."""
        print(f"\n📊 RAPPORT DES ÉVALUATIONS FINALES:")
        print(f"  Questions traitées: {stats['total_questions']}")
        print(f"  Évaluations finales totales: {stats['total_final_evaluations']}")
        if stats['total_final_evaluations'] > 0:
            success_rate = stats['successful_evaluations'] / stats['total_final_evaluations'] * 100
            print(f"  Réussites: {stats['successful_evaluations']} ({success_rate:.1f}%)")
        else:
            print(f"  Réussites: 0 (0%)")
        print(f"  Échecs: {stats['failed_evaluations']}")
        print(f"\n📁 Fichier sauvegardé: {output_file}")

    def generate_comprehensive_statistics(self, csv_files: List[str], output_dir: str = "stats_analysis") -> None:
        """
        Génère une analyse statistique complète des résultats par modèle et type de prompt.

        Args:
            csv_files: Liste des fichiers CSV à analyser
            output_dir: Répertoire de sortie pour les rapports
        """
        import os
        import statistics
        from collections import defaultdict

        # Créer le répertoire de sortie s'il n'existe pas
        os.makedirs(output_dir, exist_ok=True)

        # Structures de données pour l'analyse
        all_data = []
        stats_by_model = defaultdict(lambda: defaultdict(list))
        stats_by_agent_type = defaultdict(lambda: defaultdict(list))
        stats_by_question = defaultdict(lambda: defaultdict(list))

        print(f"\n{'='*80}")
        print("ANALYSE STATISTIQUE COMPLÈTE")
        print(f"{'='*80}")

        # Étape 1: Charger et organiser les données
        print("\n1. Chargement des données...")
        for csv_file in csv_files:
            if not os.path.exists(csv_file):
                print(f"  ⚠️  Fichier non trouvé: {csv_file}")
                continue

            print(f"  Chargement de {csv_file}...")
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            data = {
                                "question_id": int(row['question_id']),
                                "model": row['model'],
                                "agent_type": row['agent_type'],
                                "score": int(row['score']) if row['score'] else None,
                                "processing_time": float(row['processing_time_sec']) if row['processing_time_sec'] else None,
                                "total_tokens": int(row['total_tokens']) if row['total_tokens'] else None,
                                "feedback": row['feedback'],
                                "error": row.get('error', None)
                            }

                            if data['score'] is not None:  # Ignorer les évaluations échouées
                                all_data.append(data)

                                # Organiser par modèle
                                stats_by_model[data['model']][data['agent_type']].append(data)

                                # Organiser par type d'agent
                                stats_by_agent_type[data['agent_type']][data['model']].append(data)

                                # Organiser par question
                                stats_by_question[data['question_id']][f"{data['model']}_{data['agent_type']}"].append(data)

                        except (ValueError, KeyError) as e:
                            print(f"    ⚠️  Erreur de lecture de ligne: {e}")

            except Exception as e:
                print(f"  ✗ Erreur lors de la lecture de {csv_file}: {e}")

        if not all_data:
            print("  ❌ Aucune donnée valide trouvée. Arrêt de l'analyse.")
            return

        print(f"  ✓ {len(all_data)} évaluations chargées avec succès")

        # Étape 2: Calculer les statistiques globales
        print("\n2. Calcul des statistiques globales...")

        # Scores globaux
        global_scores = [d['score'] for d in all_data if d['score'] is not None]
        global_times = [d['processing_time'] for d in all_data if d['processing_time'] is not None]
        global_tokens = [d['total_tokens'] for d in all_data if d['total_tokens'] is not None]

        global_stats = {
            "total_evaluations": len(all_data),
            "score": {
                "mean": statistics.mean(global_scores) if global_scores else None,
                "median": statistics.median(global_scores) if global_scores else None,
                "min": min(global_scores) if global_scores else None,
                "max": max(global_scores) if global_scores else None,
                "std_dev": statistics.stdev(global_scores) if len(global_scores) > 1 else None
            },
            "performance": {
                "mean_time": statistics.mean(global_times) if global_times else None,
                "median_time": statistics.median(global_times) if global_times else None,
                "min_time": min(global_times) if global_times else None,
                "max_time": max(global_times) if global_times else None
            },
            "tokens": {
                "mean": statistics.mean(global_tokens) if global_tokens else None,
                "median": statistics.median(global_tokens) if global_tokens else None,
                "min": min(global_tokens) if global_tokens else None,
                "max": max(global_tokens) if global_tokens else None,
                "total": sum(global_tokens) if global_tokens else None
            }
        }

        # Étape 3: Analyser par modèle
        print("\n3. Analyse par modèle...")
        model_stats = {}
        for model, agent_data in stats_by_model.items():
            model_stats[model] = {
                "total_evaluations": sum(len(evals) for evals in agent_data.values()),
                "agent_types": {}
            }

            for agent_type, evaluations in agent_data.items():
                scores = [e['score'] for e in evaluations]
                times = [e['processing_time'] for e in evaluations]
                tokens = [e['total_tokens'] for e in evaluations]

                model_stats[model]['agent_types'][agent_type] = {
                    "count": len(evaluations),
                    "score": {
                        "mean": statistics.mean(scores) if scores else None,
                        "median": statistics.median(scores) if scores else None,
                        "min": min(scores) if scores else None,
                        "max": max(scores) if scores else None,
                        "std_dev": statistics.stdev(scores) if len(scores) > 1 else None
                    },
                    "performance": {
                        "mean_time": statistics.mean(times) if times else None,
                        "median_time": statistics.median(times) if times else None
                    },
                    "tokens": {
                        "mean": statistics.mean(tokens) if tokens else None,
                        "median": statistics.median(tokens) if tokens else None
                    }
                }

        # Étape 4: Analyser par type d'agent
        print("\n4. Analyse par type d'agent...")
        agent_type_stats = {}
        for agent_type, model_data in stats_by_agent_type.items():
            agent_type_stats[agent_type] = {
                "total_evaluations": sum(len(evals) for evals in model_data.values()),
                "models": {}
            }

            for model, evaluations in model_data.items():
                scores = [e['score'] for e in evaluations]
                times = [e['processing_time'] for e in evaluations]
                tokens = [e['total_tokens'] for e in evaluations]

                agent_type_stats[agent_type]['models'][model] = {
                    "count": len(evaluations),
                    "score": {
                        "mean": statistics.mean(scores) if scores else None,
                        "median": statistics.median(scores) if scores else None
                    },
                    "performance": {
                        "mean_time": statistics.mean(times) if times else None
                    }
                }

        # Étape 5: Analyser par question
        print("\n5. Analyse par question...")
        question_stats = {}
        for question_id, evaluations in stats_by_question.items():
            question_stats[question_id] = {
                "total_evaluations": sum(len(evals) for evals in evaluations.values()),
                "combinations": {}
            }

            for combo, evals in evaluations.items():
                scores = [e['score'] for e in evals]
                question_stats[question_id]['combinations'][combo] = {
                    "count": len(evals),
                    "score_mean": statistics.mean(scores) if scores else None,
                    "score_range": (min(scores), max(scores)) if scores else None
                }

        # Étape 6: Générer les rapports
        print("\n6. Génération des rapports...")

        # Rapport global
        global_report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "files_analyzed": csv_files,
            "global_statistics": global_stats,
            "model_statistics": model_stats,
            "agent_type_statistics": agent_type_stats,
            "question_statistics": question_stats
        }

        # Sauvegarder le rapport complet
        global_report_file = os.path.join(output_dir, "comprehensive_statistics_report.json")
        with open(global_report_file, 'w', encoding='utf-8') as f:
            json.dump(global_report, f, indent=2, ensure_ascii=False)

        # Générer un rapport Markdown lisible
        md_report = self.generate_markdown_report(global_report)
        md_report_file = os.path.join(output_dir, "statistics_report.md")
        with open(md_report_file, 'w', encoding='utf-8') as f:
            f.write(md_report)

        # Générer des visualisations simples
        self.generate_simple_visualizations(global_report, output_dir)

        print(f"  ✓ Rapport JSON sauvegardé: {global_report_file}")
        print(f"  ✓ Rapport Markdown sauvegardé: {md_report_file}")
        print(f"  ✓ Visualisations générées dans {output_dir}/")

        print(f"\n{'='*80}")
        print("ANALYSE STATISTIQUE TERMINÉE")
        print(f"{'='*80}")

    def generate_markdown_report(self, stats: Dict) -> str:
        """Génère un rapport Markdown lisible."""
        md = f"# Rapport d'Analyse Statistique\n\n"
        md += f"**Généré le:** {stats['generated_at']}\n\n"
        md += f"**Fichiers analysés:** {', '.join(stats['files_analyzed'])}\n\n"

        # Statistiques globales
        md += "## 📊 Statistiques Globales\n\n"
        md += f"- **Évaluations totales:** {stats['global_statistics']['total_evaluations']}\n"
        md += f"- **Score moyen:** {stats['global_statistics']['score']['mean']:.2f}/10\n"
        md += f"- **Score médian:** {stats['global_statistics']['score']['median']:.2f}/10\n"
        md += f"- **Écart-type des scores:** {stats['global_statistics']['score']['std_dev']:.2f}\n"
        md += f"- **Temps moyen de traitement:** {stats['global_statistics']['performance']['mean_time']:.3f} sec\n"
        md += f"- **Tokens moyens:** {stats['global_statistics']['tokens']['mean']:.1f}\n\n"

        # Par modèle
        md += "## 🤖 Analyse par Modèle\n\n"
        for model, model_data in stats['model_statistics'].items():
            md += f"### {model}\n"
            md += f"- **Évaluations totales:** {model_data['total_evaluations']}\n\n"
            md += "| Type d'Agent | Count | Score Moy | Score Méd | Écart-type | Temps Moy |\n"
            md += "|--------------|-------|-----------|-----------|------------|-----------|\n"

            for agent_type, agent_stats in model_data['agent_types'].items():
                md += f"| {agent_type} | {agent_stats['count']} | "
                md += f"{agent_stats['score']['mean']:.2f} | "
                md += f"{agent_stats['score']['median']:.2f} | "
                md += f"{agent_stats['score']['std_dev']:.2f} | "
                md += f"{agent_stats['performance']['mean_time']:.3f} |\n"

            md += "\n"

        # Par type d'agent
        md += "## 🎭 Analyse par Type d'Agent\n\n"
        for agent_type, agent_data in stats['agent_type_statistics'].items():
            md += f"### {agent_type}\n"
            md += f"- **Évaluations totales:** {agent_data['total_evaluations']}\n\n"
            md += "| Modèle | Count | Score Moy | Temps Moy |\n"
            md += "|--------|-------|-----------|-----------|\n"

            for model, model_stats in agent_data['models'].items():
                md += f"| {model} | {model_stats['count']} | "
                md += f"{model_stats['score']['mean']:.2f} | "
                md += f"{model_stats['performance']['mean_time']:.3f} |\n"

            md += "\n"

        # Par question
        md += "## ❓ Analyse par Question\n\n"
        for question_id, question_data in stats['question_statistics'].items():
            md += f"### Question {question_id}\n"
            md += f"- **Évaluations totales:** {question_data['total_evaluations']}\n\n"
            md += "| Combinaison | Count | Score Moy | Plage de Scores |\n"
            md += "|-------------|-------|-----------|-----------------|\n"

            for combo, combo_stats in question_data['combinations'].items():
                score_range = combo_stats['score_range']
                md += f"| {combo} | {combo_stats['count']} | "
                md += f"{combo_stats['score_mean']:.2f} | "
                md += f"{score_range[0]}-{score_range[1]} |\n"

            md += "\n"

        return md

    def generate_simple_visualizations(self, stats: Dict, output_dir: str) -> None:
        """Génère des visualisations simples sous forme de fichiers texte."""
        import os

        # 1. Distribution des scores par modèle
        score_dist_file = os.path.join(output_dir, "score_distribution_by_model.txt")
        with open(score_dist_file, 'w', encoding='utf-8') as f:
            f.write("DISTRIBUTION DES SCORES PAR MODÈLE\n")
            f.write("="*50 + "\n\n")

            for model, model_data in stats['model_statistics'].items():
                f.write(f"{model}:\n")
                f.write("-"*len(model) + "\n")

                for agent_type, agent_stats in model_data['agent_types'].items():
                    score_mean = agent_stats['score']['mean']
                    score_std = agent_stats['score']['std_dev']
                    count = agent_stats['count']

                    # Barre de distribution simple
                    bar_length = int(score_mean * 2)  # 2 caractères par point
                    bar = "█" * bar_length + " " * (20 - bar_length)

                    f.write(f"  {agent_type:15}: {bar} {score_mean:.1f}±{score_std:.1f} (n={count})\n")

                f.write("\n")

        # 2. Performance temporelle
        perf_file = os.path.join(output_dir, "performance_summary.txt")
        with open(perf_file, 'w', encoding='utf-8') as f:
            f.write("PERFORMANCE TEMPORELLE\n")
            f.write("="*30 + "\n\n")

            f.write(f"Temps moyen global: {stats['global_statistics']['performance']['mean_time']:.3f} sec\n\n")

            for model, model_data in stats['model_statistics'].items():
                f.write(f"{model}:\n")
                for agent_type, agent_stats in model_data['agent_types'].items():
                    mean_time = agent_stats['performance']['mean_time']
                    f.write(f"  {agent_type:15}: {mean_time:.3f} sec\n")
                f.write("\n")

        print(f"  ✓ Visualisations générées: {score_dist_file}, {perf_file}")


async def evaluation_etape_1(comparator: AgentEvaluatorComparator):
    """Fonction principale utilisant les questions de la base de données et les réponses préfaites."""

    print(f"Récupération des questions pour le document: {document_id}")
    print(f"IDs des questions spécifiques: {question_ids}")
    print(f"Fichier de réponses utilisateur: {responses_file}")

    # Charger les réponses pour vérification
    user_responses = load_user_responses_from_file(responses_file)
    print(f"\nNombre de réponses utilisateur chargées: {len(user_responses)}")
    for i, response in enumerate(user_responses, 1):
        print(f"  Réponse {i}: {response[:60]}...")

    # Récupérer les questions et les associer aux réponses
    session_data = await comparator.fetch_questions_and_responses(document_id, question_ids, responses_file)

    if not session_data:
        print("Aucune question trouvée dans la base de données ou pas de réponses correspondantes.")
        return

    print(f"\nNombre de paires question/réponse prêtes pour évaluation: {len(session_data)}/{len(question_ids)}")
    for i, question in enumerate(session_data, 1):
        print(f"  {i}. Q{question['question_id']}: {question['question_text'][:50]}...")
        print(f"     → Réponse utilisateur: {question['user_answer'][:50]}...")

    # Vérifier si toutes les questions ont été trouvées et ont une réponse
    found_ids = [q['question_id'] for q in session_data]
    missing_ids = [qid for qid in question_ids if qid not in found_ids]

    if missing_ids:
        print(f"\n⚠️  Avertissement: Les questions suivantes n'ont pas été trouvées ou n'ont pas de réponse: {missing_ids}")

    """
    # Demander confirmation avant de lancer l'évaluation
    confirm = input("\nVoulez-vous lancer l'évaluation de ces paires question/réponse? (o/n): ")
    if confirm.lower() != 'o':
        print("Évaluation annulée.")
        return
    """

    # Étape 1: Évaluation initiale
    print(f"\n{'='*80}")
    print("ÉTAPE 1: ÉVALUATION INITIALE DES AGENTS")
    print(f"{'='*80}")

    start_time = time.time()
    stats = await comparator.evaluate_session_questions(
        session_data=session_data,
        output_file=f"mistral_api_evaluations_{document_id}_with_user_responses.csv"
    )
    initial_time = time.time() - start_time


async def evaluation_etape_2(comparator: AgentEvaluatorComparator()):
    # Étape 2: Évaluation finale
    print(f"\n{'=' * 80}")
    print("ÉTAPE 2: ÉVALUATION FINALE PAR AGENT FINAL")
    print(f"{'=' * 80}")

    # Charger les évaluations depuis le CSV
    evaluations_by_question = comparator.load_evaluations_from_csv(
        f"mistral_api_evaluations_{document_id}_with_user_responses.csv")

    if not evaluations_by_question:
        print("Aucune évaluation trouvée dans le fichier CSV. Arrêt de l'évaluation finale.")
        return

    # Créer les évaluations finales
    await comparator.create_final_evaluations(evaluations_by_question,
                                              f"mistral_api_final_evaluations_{document_id}.csv")

    start_time = time.time()
    print(f"\n{'=' * 80}")
    print("RAPPORT GLOBAL")
    print(f"{'=' * 80}")

    print(f"Fichiers générés:")
    print(f"  - Évaluations initiales: mistral_api_evaluations_{document_id}_with_user_responses.csv")
    print(f"  - Évaluations finales: mistral_api_final_evaluations_{document_id}.csv")
    print(f"{'=' * 80}")

    # Analyse statistique des résultats
    print(f"\n{'=' * 80}")
    print("ANALYSE STATISTIQUE DES RÉSULTATS")
    print(f"{'=' * 80}")

    # Analyser les résultats générés
    await comparator.generate_comprehensive_statistics([
        f"mistral_api_evaluations_{document_id}_with_user_responses.csv",
        f"mistral_api_final_evaluations_{document_id}.csv"
    ], "stats_analysis")

    print(f"\nTous les rapports ont été générés dans le dossier 'stats_analysis/'")

async def main(etape1: bool, etape2: bool):
    comparator = AgentEvaluatorComparator()
    if etape1:
        await evaluation_etape_1(comparator)
    if etape2:
        await evaluation_etape_2(comparator)

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(etape1=False, etape2=True))