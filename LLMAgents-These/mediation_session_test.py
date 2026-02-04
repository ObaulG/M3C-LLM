import csv
import datetime
import os
from typing import List, Dict

import instructor
import mistralai
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from atomic_agents.context import ChatHistory, SystemPromptGenerator
from atomic_agents import AtomicAgent, AgentConfig, BasicChatInputSchema, BasicChatOutputSchema, BaseIOSchema
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class QuestionRequestInput(BaseIOSchema):
    """
    This schema represent the input of a user or a agent requesting questions/answers
     from a given document.
    The message can give instructions on how to generate questions/answers
    """
    message: str
    document: str

class QuestionAnswer(BaseIOSchema):
    """
    The result of a question/answer generation.
    """
    question_text: str
    answer_text: str

class QuestionAnswerList(BaseIOSchema):
    """
    A list of questions/answers
    """
    questions_answers: list[QuestionAnswer]

class EvaluateRequestInput(BaseIOSchema):
    """
    Schema pour l'entrée de l'agent d'évaluation.
    Contient la question, la réponse attendue et la réponse de l'utilisateur.
    """
    question: str
    expected_answer: str
    user_answer: str

class EvaluationResult(BaseIOSchema):
    """
    Contains the evaluation given by a LM to the answer. Also, with cos sim.
    """
    score: int  # Note de 1 à 10
    feedback: str  # Commentaire sur la réponse
    cosine_similarity: float  # Similarité cosinus entre la question et la réponse

def calculate_cosine_similarity(text1: str, text2: str) -> float:
    """
    Calcule la similarité cosinus entre deux textes.
    """
    embeddings = model.encode([text1, text2])
    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    return round(similarity, 2)  # Arrondi à 2 décimales

def ask_question_and_evaluate(
    question: str,
    expected_answer: str,
    evaluation_agent,
    max_attempts: int = 3,
) -> Dict:
    """
    Pose une question à l'utilisateur, évalue sa réponse, et gère les reformulations.
    Retourne un dictionnaire avec les résultats.
    """
    attempts = 0
    while attempts < max_attempts:
        # Poser la question
        console.print(f"\n[bold yellow]Question:[/bold yellow] {question}")
        user_answer = console.input("[bold blue]Votre réponse:[/bold blue] ")

        # Préparer l'entrée pour l'agent d'évaluation
        evaluation_input = EvaluateRequestInput(
            question=question,
            expected_answer=expected_answer,
            user_answer=user_answer,
        )

        # Évaluer la réponse
        evaluation = evaluation_agent.run(evaluation_input)

        # Calculer la similarité cosinus
        cosine_sim = calculate_cosine_similarity(question, user_answer)

        # Afficher les résultats
        console.print(f"\n[bold green]Note:[/bold green] {evaluation.score}/10")
        console.print(f"[bold green]Commentaire:[/bold green] {evaluation.feedback}")
        console.print(f"[bold green]Similarité cosinus:[/bold green] {cosine_sim}")

        # Si la réponse est acceptable (note >= 7), retourner les résultats
        if evaluation.score >= 7:
            result = {
                "question": question,
                "expected_answer": expected_answer,
                "user_answer": user_answer,
                "score": evaluation.score,
                "feedback": evaluation.feedback,
                "cosine_similarity": cosine_sim,
            }
            return result

        # Sinon, demander une reformulation
        console.print(f"[bold red]Votre réponse est incomplète ou incorrecte. Veuillez reformuler.[/bold red]")
        attempts += 1

    # Si le nombre maximal de tentatives est atteint
    console.print(f"[bold red]Nombre maximal de tentatives ({max_attempts}) atteint.[/bold red]")
    result = {
        "question": question,
        "expected_answer": expected_answer,
        "user_answer": user_answer,
        "score": evaluation.score,
        "feedback": evaluation.feedback,
        "cosine_similarity": cosine_sim,
    }
    return result

# --- Boucle principale ---
def run_interactive_session(response: QuestionAnswerList, evaluation_agent):
    """
    Boucle principale pour poser les questions et gérer les réponses.
    """
    global user_responses  # Accès à la liste globale des réponses

    console.print("\n[bold cyan]=== Début de la session ===[/bold cyan]")
    console.print("Répondez aux questions. Tapez '/quit' pour quitter à tout moment.\n")

    for qa in response.questions_answers:
        question = qa.question_text
        expected_answer = qa.answer_text

        # Poser la question et gérer les reformulations
        result = ask_question_and_evaluate(question, expected_answer, evaluation_agent)

        # Stocker la réponse en mémoire
        user_responses.append(result)

        # Vérifier si l'utilisateur veut quitter
        user_input = console.input("\n[bold magenta]Tapez Entrée pour continuer ou '/quit' pour quitter :[/bold magenta] ")
        if user_input.lower() == "/quit":
            console.print("\n[bold cyan]=== Session terminée par l'utilisateur ===[/bold cyan]")
            return

    console.print("\n[bold cyan]=== Toutes les questions ont été traitées ===[/bold cyan]")

def save_responses_to_csv(responses: List[Dict], filename: str = "user_responses.csv"):
    """
    Sauvegarde les réponses dans un fichier CSV.
    """
    # Ajouter un timestamp au nom du fichier pour éviter les écrasements
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"{filename.split('.')[0]}_{timestamp}.csv"

    # Définir les colonnes du CSV
    fieldnames = [
        "timestamp",
        "question",
        "expected_answer",
        "user_answer",
        "score",
        "feedback",
        "cosine_similarity",
    ]

    # Écrire dans le fichier CSV
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for response in responses:
            # Ajouter un timestamp à chaque réponse
            row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                **response,  # Déballer le dictionnaire de réponse
            }
            writer.writerow(row)

    console.print(f"\n[bold green]Les réponses ont été sauvegardées dans {csv_filename}.[/bold green]")
user_responses: List[Dict] = []

# Charger le modèle pour les embeddings
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')  # Modèle multilingue

document = "Teghime, c'est ce col qui permet aux Bastiais d'aller d'est en ouest. Les gens disent qu'arrivé là-haut, on peut contempler « les deux mers ». Bizarrerie de l'homme fidèle à ses lieux qui modèle son espace à sa manière: la Méditerranée est une seule mer, mais Teghime la divise en deux et invente ainsi la Tyrrhénienne. Comme dans bien des cas, le col constitue ici la limite d'un territoire. Celui des Bastiacci, des Villesi ou des Cardinchi qui se dépaysent dès qu'ils le franchissent. Teghime est une limite haute. Hauts plateaux des bergers qui mettaient et mettent toujours en synergie la plaine, la ville et la montagne. Par exemple, en allant de Subigna à la Serra di Pignu et en vendant leurs produits au marché de Bastia. Bergers hauts en couleurs dans la lignée de Filidatu et Filimonda, héros bucoliques de l'écrivain Sébastien Dalzeto, familier de ces lieux comme l'indique son pseudonyme. Teghime, c'est aussi l'accès aux « nivere » , ces superbes lieux de stockage de la neige qui, transformée en glace, était ramenée à la ville afin de rafraîchir les familles les plus aisées. Par l'aménagement de ces glacières en pierres et ardoises équipées d'un puits à neige, les hommes, depuis l'Antiquité, cherchent à retenir un peu l'hiver. E nivere ! Lieux devenus mythiques. Mais Teghime, c'est aussi une image moins idyllique: celle de la décharge publique de Bastia jusqu'à la fin du xx• siècle. Le lieu symbolique de bien des débats sur l' écologie, de la question des déchets à l'opportunité (ou l'opportunisme) des éoliennes. En tout cas, s'il y a une chose qui ne doit pas terminer dans les poubelles de l'histoire, c'est l'épisode de 1943. Tout d'abord les lieux investis par plus de deux milliers d'italiens errants pris dans l'étau d'une guerre finissante et d'une paix non encore aboutie. Triste ironie du sort pour ces pauvres soldats tentant une fuite par l'ouest. Ils furent bloqués après Teghime, traqués d'un côté par les Allemands, sans être de l' autre dans le camp des Alliés. Mais le fait majeur de Teghime arrivera quelques mois après, en octobre 1943. Les goumiers marocains franchirent Teghime dans leurs djellabas de grosse laine brune qui leur servaient de couverture, de tenue de camouflage et éventuellement de linceul. Ils vainquirent au col, et la Corse fut libérée à Bastia le 4 octobre 1943. Pourrons-nous oublier le sang de la libération de la Corse sur les djellabas ? Aujourd'hui, Teghime est la promenade favorite des Bastiais qui vont, en guise de glacière, « se manger une glace à Saint-Florent». Pour autant, Teghime restera à jamais un lieu de partage: partage des saisons, de la mer, des terres, de la mémoire et, bien sûr, de la parole et de l' image par les ondes."

# API Key setup
API_KEY = ""
if not API_KEY:
    API_KEY = os.getenv("MISTRAL_API_KEY")

if not API_KEY:
    raise ValueError(
        "API key is not set. Please set the API key as a static variable or in the environment variable OPENAI_API_KEY."
    )

# Initialize a Rich Console for pretty console outputs
console = Console()

# History setup
history = ChatHistory()

# Initialize history with an initial message from the assistant
initial_message = BasicChatOutputSchema(chat_message="Hello! How can I assist you today?")
history.add_message("assistant", initial_message)

# Instead of the default system prompt, we can set a custom system prompt
system_prompt_generator = SystemPromptGenerator(
    background=[
        "This agent is specialized in generating comprehension questions and answer from a text.",
    ],
    steps=["analyse the user request",
           "Understand the document content",
           "List the main facts of the text",
           "Generate the questions and their answers from the facts"],
    output_instructions=[
        "The number of questions is given by the user. Default is 3",
        "Questions should not be trivial, the visitor should not answer immediately",
        "Questions should be directly justified by the text",
        "If an information is not clearly present, don't invent it and adapt the question",
        "Questions and answers in French"
    ],
)

# OpenAI client setup using the Instructor library
client = instructor.from_mistral(client=mistralai.Mistral(api_key=API_KEY))

# Agent setup with specified configuration
qa_agent = AtomicAgent[QuestionRequestInput, QuestionAnswerList](
    config=AgentConfig(
        client=client,
        model="mistral-medium",
        history=history,
        system_prompt_generator=system_prompt_generator,
    )
)

# Generate the default system prompt for the agent
default_system_prompt = qa_agent.system_prompt_generator.generate_prompt()
# Display the system prompt in a styled panel
console.print(Panel(default_system_prompt, width=console.width, style="bold cyan"), style="bold cyan")

# Display the initial message from the assistant
console.print(Text("Agent:", style="bold green"), end=" ")
console.print(Text(initial_message.chat_message, style="bold green"))

# Prompt the user for input with a styled prompt
user_input = console.input("[bold blue]You:[/bold blue] ")
# Check if the user wants to exit the chat
#if user_input.lower() in ["/exit", "/quit"]:
#    console.print("Exiting chat...")
#    break
# Check if the user wants to see token count
if user_input.lower() == "/tokens":
    token_info = qa_agent.get_context_token_count()
    console.print("[bold magenta]Token Usage:[/bold magenta]")
    console.print(f"  Total: {token_info.total} tokens")
    console.print(f"  System prompt: {token_info.system_prompt} tokens")
    console.print(f"  History: {token_info.history} tokens")
    if token_info.utilization:
        console.print(f"  Context utilization: {token_info.utilization:.1%}")

# Process the user's input through the agent and get the response
input_schema = QuestionRequestInput(message=user_input, document=document)
response = qa_agent.run(input_schema)
qa_dict = {}
for qa in response:
    question, answer = qa
    qa_dict[question] = answer
    console.print(question)
    console.print(answer)



# Générateur de prompt pour l'agent d'évaluation
evaluation_system_prompt_generator = SystemPromptGenerator(
    background=[
        "Cet agent est spécialisé dans l'évaluation des réponses des utilisateurs à des questions de compréhension.",
        "Il compare la réponse de l'utilisateur avec la réponse attendue et attribue une note de 1 à 10.",
    ],
    steps=[
        "Analyser la question et la réponse attendue.",
        "Comparer la réponse de l'utilisateur avec la réponse attendue.",
        "Évaluer la pertinence, la précision et la complétude de la réponse.",
        "Attribuer une note de 1 à 10 (1 = complètement incorrect, 10 = parfait).",
        "Fournir un commentaire constructif pour expliquer la note.",
    ],
    output_instructions=[
        "La note doit être un entier entre 1 et 10.",
        "Le commentaire doit être clair, constructif et en français.",
        "L'évaluation ne doit pas strictement faire référence à chaque élément de la réponse."
        "La réponse doit être rédigée. Pas de réponse en mots-clefs."
    ],
)

# Initialisation de l'agent d'évaluation



# Session de "médiation"
run_interactive_session(response, evaluation_agent)

# Afficher un résumé des réponses (optionnel)
console.print("\n[bold cyan]=== Résumé des réponses ===[/bold cyan]")
for i, response in enumerate(user_responses, 1):
    console.print(f"\n[bold yellow]Question {i}:[/bold yellow] {response['question']}")
    console.print(f"[bold green]Réponse utilisateur:[/bold green] {response['user_answer']}")
    console.print(f"[bold green]Note:[/bold green] {response['score']}/10")
    console.print(f"[bold green]Commentaire:[/bold green] {response['feedback']}")