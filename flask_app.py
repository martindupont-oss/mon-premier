import json
import os
import urllib.parse
import urllib.request
import uuid
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
DATA_FILE = "students_data.json"
EVALS_FILE = "evaluations.json"

# Adresses autorisées comme administrateurs (ajoute tes co-admins dans cette liste)
ADMIN_EMAILS = [
    "martin.dupont@2031.icam.fr",
]


def get_all_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            raw_db = json.load(f)
            cleaned_db = {}
            for k, v in raw_db.items():
                clean_email = k.strip().lower()
                if clean_email in cleaned_db:
                    old_date = cleaned_db[clean_email].get("updatedAt", "")
                    new_date = v.get("updatedAt", "")
                    if new_date >= old_date:
                        cleaned_db[clean_email] = v
                else:
                    cleaned_db[clean_email] = v
            return cleaned_db
        except Exception:
            return {}


def save_all_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_custom_evals():
    if not os.path.exists(EVALS_FILE):
        return []
    with open(EVALS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_custom_evals(evals):
    with open(EVALS_FILE, "w", encoding="utf-8") as f:
        json.dump(evals, f, ensure_ascii=False, indent=2)


@app.route("/")
@app.route("/index.html")
def home():
    return send_from_directory(".", "index.html")


@app.route("/api/save", methods=["POST"])
def save_student():
    payload = request.get_json() or {}
    email = payload.get("email", "").strip().lower()

    if not email:
        return jsonify({"status": "error", "message": "Email manquant"}), 400

    payload["email"] = email
    db = get_all_data()
    db[email] = payload
    save_all_data(db)
    return jsonify({"status": "success", "message": "Sauvegardé avec succès"})


@app.route("/api/students", methods=["GET"])
def get_students():
    return jsonify(get_all_data())


@app.route("/api/admin/delete-student", methods=["POST"])
def delete_student():
    payload = request.get_json() or {}
    admin_email = payload.get("adminEmail", "").strip().lower()
    target_email = payload.get("targetEmail", "").strip().lower()

    if admin_email not in ADMIN_EMAILS:
        return (
            jsonify({
                "status": "error",
                "message": "Accès refusé : vous n'êtes pas administrateur.",
            }),
            403,
        )

    db = get_all_data()
    if target_email in db:
        del db[target_email]
        save_all_data(db)
        return jsonify({
            "status": "success",
            "message": f"Compte {target_email} supprimé.",
        })
    return jsonify({"status": "error", "message": "Élève introuvable."}), 404


# API ÉVALUATIONS ET PROPOSITIONS
@app.route("/api/evaluations", methods=["GET"])
def get_evaluations():
    return jsonify(get_custom_evals())


# Proposer une évaluation (Tout étudiant)
@app.route("/api/propose-evaluation", methods=["POST"])
def propose_evaluation():
    payload = request.get_json() or {}
    title = payload.get("title", "").strip()
    date_str = payload.get("date", "").strip()
    comp = payload.get("competence", "").strip()
    student_email = payload.get("studentEmail", "").strip().lower()

    if not title or not date_str or not student_email:
        return jsonify({"status": "error", "message": "Informations manquantes"}), 400

    evals = get_custom_evals()
    new_eval = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "date": date_str,
        "competence": comp,
        "proposedBy": student_email,
        "status": "pending",  # En attente de validation admin
    }
    evals.append(new_eval)
    save_custom_evals(evals)

    return jsonify({
        "status": "success",
        "message": "Proposition transmise aux administrateurs.",
        "eval": new_eval,
    })


# Valider une évaluation (Admin uniquement)
@app.route("/api/admin/approve-evaluation", methods=["POST"])
def approve_evaluation():
    payload = request.get_json() or {}
    admin_email = payload.get("adminEmail", "").strip().lower()
    eval_id = payload.get("evalId", "").strip()

    if admin_email not in ADMIN_EMAILS:
        return jsonify({"status": "error", "message": "Accès refusé."}), 403

    evals = get_custom_evals()
    found = False
    for e in evals:
        if e.get("id") == eval_id:
            e["status"] = "approved"
            e["approvedBy"] = admin_email
            found = True
            break

    if found:
        save_custom_evals(evals)
        return jsonify({"status": "success", "message": "Évaluation validée et officialisée."})
    return jsonify({"status": "error", "message": "Évaluation introuvable."}), 404


# Supprimer une évaluation (Admin uniquement)
@app.route("/api/admin/delete-evaluation", methods=["POST"])
def delete_evaluation():
    payload = request.get_json() or {}
    admin_email = payload.get("adminEmail", "").strip().lower()
    eval_id = payload.get("evalId", "").strip()

    if admin_email not in ADMIN_EMAILS:
        return jsonify({"status": "error", "message": "Accès refusé."}), 403

    evals = get_custom_evals()
    evals = [e for e in evals if e.get("id") != eval_id]
    save_custom_evals(evals)

    return jsonify({"status": "success", "message": "Évaluation supprimée"})


# Proxy ICAM pour contourner CORS
@app.route("/api/fetch-ical", methods=["POST"])
def fetch_ical():
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"status": "error", "message": "URL manquante"}), 400

    url = url.replace("¶m=", "&param=").replace("¶", "&para")

    if url.startswith("webcal://"):
        url = "https://" + url[9:]

    try:
        parsed_url = urllib.parse.urlsplit(url)
        encoded_path = urllib.parse.quote(parsed_url.path)
        encoded_query = urllib.parse.quote(parsed_url.query, safe="=&?%")
        clean_url = urllib.parse.urlunsplit((
            parsed_url.scheme,
            parsed_url.netloc,
            encoded_path,
            encoded_query,
            parsed_url.fragment,
        ))

        req = urllib.request.Request(
            clean_url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode("utf-8", errors="ignore")
        return jsonify({"status": "success", "content": content})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run()
