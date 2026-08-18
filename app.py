import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request
from openai import OpenAI
from tavily import TavilyClient


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

app = Flask(__name__)


# =========================================================
# GROQ
# =========================================================

groq_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


# =========================================================
# TAVILY
# =========================================================

tavily_client = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)


# =========================================================
# PAGE PRINCIPALE
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# ROUTE CHAT
# =========================================================

@app.route("/prompt", methods=["POST"])
def prompt():

    try:

        data = request.get_json()

        if not data or "messages" not in data:
            return Response(
                "Aucun message reçu.",
                status=400,
                mimetype="text/plain"
            )

        messages = data["messages"]

        conversation = build_conversation_dict(messages)

        print("\n==============================")
        print("NOUVELLE CONVERSATION")
        print("==============================")

        print("Conversation :", conversation)

        return Response(
            event_stream(conversation),
            mimetype="text/plain"
        )

    except Exception as e:

        print("ERREUR ROUTE /prompt :", repr(e))

        return Response(
            f"Erreur serveur : {str(e)}",
            status=500,
            mimetype="text/plain"
        )


# =========================================================
# CONSTRUIRE LA CONVERSATION
# =========================================================

def build_conversation_dict(messages):

    conversation = []

    for i, message in enumerate(messages):

        role = "user" if i % 2 == 0 else "assistant"

        conversation.append({
            "role": role,
            "content": str(message)
        })

    return conversation


# =========================================================
# RECHERCHE WEB AVEC TAVILY
# =========================================================

def search_web(question):

    print("\n==============================")
    print("RECHERCHE WEB")
    print("==============================")

    print("Requête Tavily :", question)

    try:

        results = tavily_client.search(
            question,
            search_depth="basic",
            max_results=3
        )

        sources = []

        for result in results.get("results", []):

            sources.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", "")[:1500]
            })

        print("Nombre de résultats :", len(sources))

        return sources

    except Exception as e:

        print("ERREUR TAVILY :", repr(e))

        return []


# =========================================================
# CONSTRUIRE LA REQUÊTE WEB
# =========================================================

def build_search_query(conversation):

    """
    Construit une requête Web à partir des derniers
    messages de l'utilisateur.

    Exemple :

    Utilisateur :
    Qui a remporté la Coupe du monde ?

    Utilisateur :
    2026

    devient :

    Qui a remporté la Coupe du monde ?
    2026
    """

    recent_messages = conversation[-6:]

    user_messages = [
        message["content"]
        for message in recent_messages
        if message["role"] == "user"
    ]

    search_query = "\n".join(user_messages)

    # Évite une requête trop longue
    return search_query[-3000:]


# =========================================================
# DÉCISION : FAUT-IL UTILISER INTERNET ?
# =========================================================

def needs_web_search(conversation):

    if not conversation:
        return False

    question = conversation[-1]["content"]

    question_lower = question.lower().strip()

    # =====================================================
    # MOTS-CLÉS QUI DEMANDENT DIRECTEMENT UNE RECHERCHE
    # =====================================================

    current_keywords = [

        # Temps / actualité
        "actuellement",
        "actuel",
        "actuelle",
        "actuels",
        "actuelles",
        "aujourd'hui",
        "aujourd’hui",
        "maintenant",
        "en ce moment",
        "ces jours-ci",
        "cette semaine",
        "cette année",
        "hier",
        "récemment",
        "récente",
        "récent",
        "récentes",
        "dernièrement",

        # Dernières informations
        "dernier",
        "dernière",
        "dernières",
        "actualité",
        "actualités",
        "news",

        # Politique
        "qui est le président",
        "qui est la présidente",
        "qui est le premier ministre",
        "premier ministre actuel",

        # Sportifs
        "où joue",
        "dans quel club",
        "dans quelle équipe",
        "club actuel",
        "équipe actuelle",

        # Résultats
        "qui a gagné",
        "qui a remporté",
        "qui est le vainqueur",
        "vainqueur",
        "champion",
        "championne",
        "gagnant",
        "gagnante",
        "victoire",
        "résultat du match",
        "résultats du match",
        "score du match",

        # Prix
        "prix actuel",
        "prix aujourd'hui",
        "cours actuel",
        "taux actuel",

        # Compétitions
        "coupe du monde",
        "ligue des champions",
        "champions league",
        "can",
        "mondial",
        "premier league",
        "liga",
        "ligue 1"
    ]

    # =====================================================
    # RECHERCHE DIRECTE
    # =====================================================

    for keyword in current_keywords:

        if keyword in question_lower:

            print(
                "Recherche Web nécessaire par mot-clé :",
                keyword
            )

            return True

    # =====================================================
    # CAS DES QUESTIONS COURTES
    # =====================================================

    # Exemple :
    #
    # Qui a remporté la Coupe du monde ?
    # 2026
    #
    # Le message "2026" tout seul doit utiliser
    # le contexte précédent.

    if len(question_lower.split()) <= 3 and len(conversation) > 1:

        print(
            "Question courte détectée : "
            "analyse du contexte nécessaire."
        )

        # On laisse Groq décider avec le contexte.

    # =====================================================
    # DÉCISION AVEC GROQ
    # =====================================================

    recent_messages = conversation[-6:]

    context = "\n".join(
        [
            f"{message['role'].upper()} : {message['content']}"
            for message in recent_messages
        ]
    )

    print("\nContexte utilisé pour la décision Web :")
    print(context)

    try:

        response = groq_client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[

                {
                    "role": "system",
                    "content": """
Tu dois déterminer si la dernière question de
l'utilisateur nécessite une recherche sur Internet.

Réponds UNIQUEMENT :

OUI

ou

NON


Réponds OUI si :

- l'information peut avoir changé récemment ;
- la question concerne l'actualité ;
- la question concerne un résultat sportif ;
- la question concerne une compétition ;
- la question concerne le club actuel d'un sportif ;
- la question concerne une personne actuellement ;
- la question concerne une fonction politique actuelle ;
- la question concerne un prix actuel ;
- la question concerne un événement récent ;
- la question concerne une entreprise actuellement ;
- la question demande ce qui s'est passé récemment ;
- la question fait référence à une question précédente
  nécessitant des informations actuelles ;
- le dernier message est une précision courte comme :
  "2026", "et lui ?", "actuellement ?", "et maintenant ?"

Exemple :

UTILISATEUR :
Qui a remporté la Coupe du monde ?

UTILISATEUR :
2026

Réponse :
OUI


Autre exemple :

UTILISATEUR :
Quel est le club de Ferran Torres ?

UTILISATEUR :
Actuellement ?

Réponse :
OUI


Réponds NON pour :

- salutations ;
- mathématiques ;
- programmation générale ;
- traduction ;
- explications générales ;
- connaissances historiques ;
- conversations normales.

IMPORTANT :

Si tu hésites entre OUI et NON,
réponds OUI.
"""
                },

                {
                    "role": "user",
                    "content": f"""
Voici les derniers messages de la conversation :

{context}

La dernière question est :

{question}

La dernière question nécessite-t-elle
une recherche Internet ?

Réponds uniquement OUI ou NON.
"""
                }
            ],

            max_tokens=3
        )

        decision = (
            response.choices[0]
            .message
            .content
            .strip()
            .upper()
        )

        print("Décision Groq recherche Web :", decision)

        return decision == "OUI"

    except Exception as e:

        print("ERREUR DÉCISION GROQ :", repr(e))

        # En cas de doute, on préfère rechercher.
        return True


# =========================================================
# STREAMING DE LA RÉPONSE
# =========================================================

def event_stream(conversation):

    print("\n==============================")
    print("EVENT STREAM")
    print("==============================")

    try:

        if not conversation:
            yield "Aucun message."
            return

        # =================================================
        # DERNIÈRE QUESTION
        # =================================================

        question = conversation[-1]["content"]

        print("Question :", question)


        # =================================================
        # DATE ET HEURE ACTUELLES
        # =================================================

        current_datetime = datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )

        print(
            "Date et heure du serveur :",
            current_datetime
        )


        # =================================================
        # RECHERCHE WEB
        # =================================================

        if needs_web_search(conversation):

            search_query = build_search_query(
                conversation
            )

            print(
                "\nRequête envoyée à Tavily :",
                search_query
            )

            sources = search_web(
                search_query
            )

        else:

            sources = []

            print(
                "Pas de recherche Web nécessaire."
            )


        # =================================================
        # CONSTRUIRE LE CONTEXTE WEB
        # =================================================

        if sources:

            web_context = "\n\n".join(

                [
                    f"""
SOURCE {i + 1}

TITRE :
{source['title']}

URL :
{source['url']}

CONTENU :
{source['content']}
"""
                    for i, source in enumerate(sources)
                ]

            )

        else:

            web_context = (
                "Aucun résultat de recherche Web disponible."
            )


        # =================================================
        # MESSAGE SYSTÈME
        # =================================================

        system_message = {

            "role": "system",

            "content": f"""
Tu es un assistant intelligent et utile.

DATE ET HEURE ACTUELLES :
{current_datetime}

IMPORTANT POUR LA DATE :

Lorsque l'utilisateur demande la date,
le jour ou l'heure actuelle, utilise
la date et l'heure fournies ci-dessus.

Ne donne pas une ancienne date provenant
de tes connaissances.


IMPORTANT POUR INTERNET :

Lorsque des résultats Web sont fournis,
utilise-les en priorité pour les informations
récentes ou actuelles.

Les résultats Web peuvent contenir plusieurs
sources.

Ne prétends pas qu'une information est récente
si les sources ne permettent pas de la confirmer.

Si aucune source fiable ne permet de répondre,
dis-le clairement.

Si la question ne nécessite pas Internet,
réponds normalement.


CONTEXTE WEB :

{web_context}


LANGUE :

Réponds en français sauf si l'utilisateur
utilise une autre langue.
"""
        }


        messages_for_groq = [
            system_message
        ] + conversation[-10:]


        # =================================================
        # APPEL GROQ
        # =================================================

        print("\nEnvoi de la requête à Groq...")

        response = groq_client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=messages_for_groq,

            stream=True
        )


        print("Réponse Groq reçue.")



        for chunk in response:

            if not chunk.choices:
                continue

            text = chunk.choices[0].delta.content

            if text:

                print(
                    "Texte :",
                    repr(text)
                )

                yield text


    except Exception as e:

        print(
            "\nERREUR EVENT STREAM :",
            repr(e)
        )

        yield (
            "\n\nUne erreur est survenue : "
            + str(e)
        )



if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )