# api_monitor_demo.py
"""
Démonstration de l'utilisation du moniteur API Mistral pour éviter
de dépasser les limites de l'API.

Ce script montre comment utiliser les nouvelles fonctions ajoutées
dans mistral_client.py pour surveiller et gérer la consommation API.
"""

import time
from agents.mistral_client import (
    get_mistral_client, 
    get_api_monitor, 
    track_api_call, 
    check_api_limits,
    get_current_api_usage,
    get_cost_estimate
)
from agents.token_monitor import monitor_agent_call
from agents.qa_agent import get_qa_agent, QuestionRequestInput


def demo_api_monitoring():
    """Démonstration complète du moniteur API."""
    
    print("🚀 DÉMONSTRATION : Surveillance de la Consommation API Mistral")
    print("=" * 70)
    
    # 1. Initialiser le client et le moniteur
    print("\n1️⃣ Initialisation...")
    try:
        client = get_mistral_client()
        monitor = get_api_monitor()
        print("   ✅ Client Mistral et moniteur API initialisés")
    except Exception as e:
        print(f"   ❌ Erreur d'initialisation: {e}")
        return
    
    # 2. Vérifier l'utilisation actuelle
    print("\n2️⃣ Vérification de l'utilisation actuelle de l'API...")
    usage = get_current_api_usage("hour")
    print(f"   📊 Appels dans la dernière heure: {usage['total_calls']}")
    print(f"   📊 Tokens utilisés: {usage['total_tokens']}")
    print(f"   ⏱️  Temps de réponse moyen: {usage['avg_response_time']:.2f}s")
    
    # 3. Estimer les coûts
    print("\n3️⃣ Estimation des coûts...")
    cost_estimate = get_cost_estimate("day")
    print(f"   💰 Coût estimé aujourd'hui: ${cost_estimate['total_cost_usd']:.4f}")
    print(f"   📄 Tokens totaux aujourd'hui: {cost_estimate['total_tokens']}")
    
    # 4. Simuler des appels API avec surveillance
    print("\n4️⃣ Simulation d'appels API avec surveillance...")
    
    # Créer un agent QA pour les tests
    qa_agent = get_qa_agent(model="mistral-medium")
    
    # Faire quelques appels de test
    test_questions = [
        "Qu'est-ce que l'intelligence artificielle ?",
        "Quels sont les avantages de l'IA ?",
        "Comment fonctionne un réseau de neurones ?"
    ]
    
    for i, question in enumerate(test_questions):
        print(f"\n   🔄 Appel {i+1}/{len(test_questions)}: {question}")
        
        # Vérifier les limites avant l'appel
        check_result = check_api_limits("mistral-medium", estimated_tokens=500)
        print(f"   📊 Utilisation RPM: {check_result['rpm_usage_percent']:.1f}%")
        print(f"   📊 Utilisation TPM: {check_result['tpm_usage_percent']:.1f}%")
        
        if not check_result['can_make_call']:
            print(f"   ⚠️  ALERTE: {check_result['warning_messages']}")
            print("   ❌ Annulation de l'appel pour éviter de dépasser les limites")
            continue
        
        # Faire l'appel avec surveillance des tokens
        start_time = time.time()
        
        try:
            user_input = QuestionRequestInput(
                message=question,
                document="L'intelligence artificielle est une technologie révolutionnaire."
            )
            
            response, input_tokens, output_tokens = monitor_agent_call(
                agent=qa_agent,
                user_input=user_input
            )
            
            # Calculer le temps de réponse
            response_time = time.time() - start_time
            
            # Suivre l'appel API
            track_api_call(
                model="mistral-medium",
                input_tokens=input_tokens.total,
                output_tokens=output_tokens,
                response_time=response_time,
                status="success"
            )
            
            print(f"   ✅ Appel réussi")
            print(f"   📥 Tokens entrée: {input_tokens.total}")
            print(f"   📤 Tokens sortie: {output_tokens}")
            print(f"   ⏱️  Temps: {response_time:.2f}s")
            print(f"   💰 Coût estimé: ${check_result['estimated_cost_usd']:.4f}")
            
        except Exception as e:
            response_time = time.time() - start_time
            track_api_call(
                model="mistral-medium",
                input_tokens=0,
                output_tokens=0,
                response_time=response_time,
                status="error"
            )
            print(f"   ❌ Erreur lors de l'appel: {e}")
    
    # 5. Afficher le résumé final
    print("\n5️⃣ Résumé final de l'utilisation API...")
    final_usage = get_current_api_usage("hour")
    final_cost = get_cost_estimate("day")
    
    print(f"   📊 Appels totaux: {final_usage['total_calls']}")
    print(f"   📊 Tokens totaux: {final_usage['total_tokens']}")
    print(f"   💰 Coût estimé aujourd'hui: ${final_cost['total_cost_usd']:.4f}")
    
    # 6. Vérifier les alertes
    print("\n6️⃣ Vérification des alertes...")
    check_result = check_api_limits("mistral-medium", estimated_tokens=500)
    
    if check_result['alert_level'] == 'critical':
        print("   ⚠️  ALERTE CRITIQUE:")
        for msg in check_result['warning_messages']:
            print(f"      - {msg}")
        print("   🛑 Il est recommandé d'arrêter les appels pour éviter les erreurs de limite.")
    
    elif check_result['alert_level'] == 'warning':
        print("   ⚠️  AVERTISSEMENT:")
        for msg in check_result['warning_messages']:
            print(f"      - {msg}")
        print("   👀 Surveillance recommandée.")
    
    else:
        print("   ✅ Utilisation normale de l'API.")
        print("   👍 Vous pouvez continuer à faire des appels.")


def demo_rate_limit_prevention():
    """Démonstration de la prévention des dépassements de limite."""
    
    print("\n" + "=" * 70)
    print("🛡️  DÉMONSTRATION : Prévention des Dépassements de Limite")
    print("=" * 70)
    
    # Simuler un scénario où nous approchons des limites
    print("\n📊 Scénario: Nous avons déjà fait beaucoup d'appels aujourd'hui...")
    
    # Ajouter des appels simulés pour atteindre les limites
    monitor = get_api_monitor()
    
    # Simuler 150 appels avec 1000 tokens chacun (approche des limites)
    for i in range(150):
        monitor.track_api_call(
            model="mistral-medium",
            input_tokens=500,
            output_tokens=500,
            response_time=1.5,
            status="success"
        )
    
    print("   ✅ 150 appels simulés ajoutés")
    
    # Vérifier l'état actuel
    usage = get_current_api_usage("hour")
    print(f"\n📊 État actuel:")
    print(f"   - Appels: {usage['total_calls']}")
    print(f"   - Tokens: {usage['total_tokens']}")
    
    # Vérifier si nous pouvons faire un nouvel appel
    print("\n🔍 Vérification avant un nouvel appel...")
    check_result = check_api_limits("mistral-medium", estimated_tokens=1000)
    
    print(f"   📊 Utilisation RPM: {check_result['rpm_usage_percent']:.1f}%")
    print(f"   📊 Utilisation TPM: {check_result['tpm_usage_percent']:.1f}%")
    print(f"   💰 Coût estimé: ${check_result['estimated_cost_usd']:.4f}")
    
    if check_result['alert_level'] == 'critical':
        print("\n❌ DECISION: Annuler l'appel pour éviter de dépasser les limites")
        print("   🛑 Le système a automatiquement empêché l'appel")
        print("   💡 Suggestion: Attendre le début de la nouvelle heure ou utiliser un modèle moins gourmand")
    
    else:
        print("\n✅ DECISION: L'appel peut être effectué en toute sécurité")


def demo_cost_analysis():
    """Démonstration de l'analyse des coûts."""
    
    print("\n" + "=" * 70)
    print("💰 DÉMONSTRATION : Analyse des Coûts")
    print("=" * 70)
    
    # Obtenir les estimations de coût pour différentes périodes
    periods = ['hour', 'day', 'week']
    
    for period in periods:
        print(f"\n📊 Période: {period}")
        cost_data = get_cost_estimate(period)
        
        print(f"   💰 Coût total: ${cost_data['total_cost_usd']:.4f}")
        print(f"   📄 Tokens totaux: {cost_data['total_tokens']}")
        print(f"   📅 Période: {cost_data['start_time']} à {cost_data['end_time']}")
        
        if cost_data['model_costs']:
            print(f"   📊 Répartition par modèle:")
            for model, model_data in cost_data['model_costs'].items():
                print(f"      - {model}: ${model_data['cost_usd']:.4f} ({model_data['tokens']} tokens)")


def main():
    """Fonction principale."""
    
    try:
        # Exécuter les démonstrations
        demo_api_monitoring()
        demo_rate_limit_prevention()
        demo_cost_analysis()
        
        print("\n" + "=" * 70)
        print("🎉 DÉMONSTRATION TERMINÉE")
        print("=" * 70)
        print("\n💡 Points clés à retenir:")
        print("   1. Utilisez check_api_limits() avant chaque appel important")
        print("   2. Surveillez régulièrement get_current_api_usage()")
        print("   3. Analysez les coûts avec get_cost_estimate()")
        print("   4. Utilisez track_api_call() pour enregistrer tous les appels")
        print("   5. Configurez des alertes pour les niveaux critiques")
        
    except Exception as e:
        print(f"\n❌ Erreur lors de la démonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()