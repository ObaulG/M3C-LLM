import ollama

response = ollama.generate(
    model="ministral-3:3b",
    prompt="""Génère un JSON contenant un score compris entre 1 et 10, ainsi qu'une phrase pour le feedback.
Retournez UNIQUEMENT un JSON valide au format :
{
    "score": int,
    "feedback": "string"
}""",
    options={"temperature": 0.05}
)

print("Réponse brute d'Ollama :")
print(response["response"])
