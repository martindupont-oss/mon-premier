# ---------------------------------------------------------------
#  Mon premier site Web avec Flask
# ---------------------------------------------------------------
#  Ce fichier est le "cerveau" de votre site : c'est lui qui
#  reçoit les demandes des navigateurs et qui fabrique les réponses.
#
#  Vous allez le compléter petit à petit, exercice après exercice.
#  Les consignes sont dans le dossier "exercices/".
# ---------------------------------------------------------------

from flask import Flask

app = Flask(__name__)


# Une "route" associe une adresse (URL) à une fonction Python.
# Ici : quand quelqu'un visite la page d'accueil "/",
# Flask exécute la fonction accueil() et renvoie son résultat au navigateur.
@app.get("/")
def accueil():
    return "Bienvenue sur le site de DUPONT GIRARD Martin john Charles 🚀"


# ---------------------------------------------------------------
#  Ajoutez vos nouvelles routes ci-dessous 👇
# ---------------------------------------------------------------

@app.get("/presentation")
def presentation():
    return """
    <h1>Dupont Martin</h1>
    <p>Je suis étudiante en <strong>deuxième année d'ingenieure</strong>.</p>
    <h2>Ce que j'aime</h2>
    <ul>
        <li>Les jeux vidéo</li>
        <li>La musique</li>
        <li>Le sport (bientôt !)</li>
        <img src="https://thumb.wikimedia.org/wikipedia/fr/thumb/f/ff/Logo_Paris_Saint-Germain_2024.svg/langfr-960px-Logo_Paris_Saint-Germain_2024.svg.png?utm_source=fr.wikipedia.org&utm_campaign=imageinfo&utm_content=thumbnail">
    </ul>
    """




# ---------------------------------------------------------------
#  Ne pas modifier : utile seulement pour lancer le site
#  sur votre propre ordinateur (python flask_app.py)
# ---------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
