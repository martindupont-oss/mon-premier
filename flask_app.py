import json
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "students_data.json")
EVALS_FILE = os.path.join(BASE_DIR, "evaluations.json")
TITLES_FILE = os.path.join(BASE_DIR, "ra_titles.json")  # titres des RA lus sur PITCH (partagés)

# Adresses autorisées comme administrateurs
ADMIN_EMAILS = [
    "martin.dupont@2031.icam.fr",
]


# --- GESTION GLOBALE DU CORS (Extension & Frontend) ---
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "86400"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE"
    return response


# --- FONCTIONS UTILITAIRES DE LECTURE / ÉCRITURE JSON ---
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


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_all_data(data):
    _write_json(DATA_FILE, data)


def get_ra_titles():
    if not os.path.exists(TITLES_FILE):
        return {}
    with open(TITLES_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}


def save_ra_titles(titles):
    _write_json(TITLES_FILE, titles)


def get_custom_evals():
    if not os.path.exists(EVALS_FILE):
        return []
    with open(EVALS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_custom_evals(evals):
    _write_json(EVALS_FILE, evals)


def update_student_stats(student):
    """Moyenne, nombre de RA évalués et trajectoire. Un score -1 = RA connu mais non évalué."""
    scores = student.get("scores", {})
    clean_scores = {}

    for code, score in scores.items():
        try:
            clean_code = str(code).strip().upper()
            clean_scores[clean_code] = float(score)
        except (ValueError, TypeError):
            continue

    student["scores"] = clean_scores
    evaluated = [v for v in clean_scores.values() if v >= 0]
    total_ra = len(evaluated)

    if total_ra > 0:
        acquired_70 = sum(1 for val in evaluated if val >= 70)
        student["globalProgress"] = round(sum(evaluated) / total_ra, 1)
        student["acquiredCount"] = acquired_70
        student["totalRA"] = total_ra
        student["trajectoirePercent"] = round((acquired_70 / total_ra) * 100, 1)
    else:
        student["globalProgress"] = 0
        student["acquiredCount"] = 0
        student["totalRA"] = 0
        student["trajectoirePercent"] = 0

    return student


# --- ROUTES PRINCIPALES ---
@app.route("/")
@app.route("/index.html")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/save", methods=["POST", "OPTIONS"])
def save_student():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"})

    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()

    if not email:
        return jsonify({"status": "error", "message": "Email manquant"}), 400

    db = get_all_data()
    student = db.get(email, {"email": email, "scores": {}})

    # Seuls ces champs viennent du navigateur. Les scores, eux, ne viennent que de l'extension.
    for field in ("name", "promo", "validation"):
        if field in payload:
            student[field] = payload[field]
    student["email"] = email
    student["savedAt"] = datetime.now(timezone.utc).isoformat()

    student = update_student_stats(student)
    db[email] = student
    save_all_data(db)

    return jsonify({"status": "success", "message": "Sauvegardé avec succès", "student": student})


@app.route("/api/sync-pitch", methods=["POST", "OPTIONS"])
def sync_pitch():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"})

    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    scores = payload.get("scores", {})
    titles = payload.get("titles", {})

    if not email:
        return jsonify({"status": "error", "message": "Email non détecté"}), 400
    if not isinstance(scores, dict):
        return jsonify({"status": "error", "message": "Format de scores invalide"}), 400

    db = get_all_data()
    student = db.get(
        email,
        {
            "name": email.split("@")[0].replace(".", " ").title(),
            "email": email,
            "promo": "Bachelor International",
            "scores": {},
        },
    )

    if "scores" not in student or not isinstance(student["scores"], dict):
        student["scores"] = {}

    # Fusion : on ne garde que les codes RA-..., et "non évalué" (-1) n'écrase jamais un vrai score
    accepted = 0
    for code, value in scores.items():
        code = str(code).strip().upper()
        if not code.startswith("RA-"):
            continue
        try:
            value = float(value)
        except (ValueError, TypeError):
            continue
        old = student["scores"].get(code)
        if value < 0 and old is not None and float(old) >= 0:
            continue
        student["scores"][code] = value
        accepted += 1

    # Titres des RA (communs à tous les élèves, utilisés par la recherche du portail)
    new_titles = 0
    if isinstance(titles, dict) and titles:
        all_titles = get_ra_titles()
        for code, title in titles.items():
            code = str(code).strip().upper()
            if code.startswith("RA-") and isinstance(title, str) and title.strip():
                if all_titles.get(code) != title.strip():
                    all_titles[code] = title.strip()[:300]
                    new_titles += 1
        if new_titles:
            save_ra_titles(all_titles)

    now = datetime.now(timezone.utc).isoformat()
    student["updatedAt"] = now
    student["syncedAt"] = now
    student["email"] = email

    student = update_student_stats(student)
    db[email] = student
    save_all_data(db)

    return jsonify(
        {
            "status": "success",
            "message": f"Synchronisation réussie pour {email} : {accepted} RA reçus, {new_titles} titres mis à jour.",
            "totalRA": student["totalRA"],
            "globalProgress": student["globalProgress"],
            "trajectoirePercent": student["trajectoirePercent"],
        }
    )


@app.route("/api/ra-titles", methods=["GET"])
def ra_titles():
    return jsonify(get_ra_titles())


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


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
            jsonify(
                {
                    "status": "error",
                    "message": "Accès refusé : vous n'êtes pas administrateur.",
                }
            ),
            403,
        )

    db = get_all_data()
    if target_email in db:
        del db[target_email]
        save_all_data(db)
        return jsonify(
            {
                "status": "success",
                "message": f"Compte {target_email} supprimé.",
            }
        )
    return jsonify({"status": "error", "message": "Élève introuvable."}), 404


# --- GESTION DES ÉVALUATIONS ---
@app.route("/api/evaluations", methods=["GET"])
def get_evaluations():
    return jsonify(get_custom_evals())


@app.route("/api/propose-evaluation", methods=["POST"])
def propose_evaluation():
    payload = request.get_json() or {}
    title = payload.get("title", "").strip()
    date_str = payload.get("date", "").strip()
    comp = payload.get("competence", "").strip()
    student_email = payload.get("studentEmail", "").strip().lower()

    if not title or not date_str or not student_email:
        return (
            jsonify({"status": "error", "message": "Informations manquantes"}),
            400,
        )

    evals = get_custom_evals()
    new_eval = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "date": date_str,
        "competence": comp,
        "proposedBy": student_email,
        "status": "pending",
    }
    evals.append(new_eval)
    save_custom_evals(evals)

    return jsonify(
        {
            "status": "success",
            "message": "Proposition transmise aux administrateurs.",
            "eval": new_eval,
        }
    )


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
        return jsonify(
            {
                "status": "success",
                "message": "Évaluation validée et officialisée.",
            }
        )
    return jsonify({"status": "error", "message": "Évaluation introuvable."}), 404


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


# --- ROUTE PROXY DE MANGEMENT EMPLOI DU TEMPS (iCal) ---
@app.route("/api/fetch-ical", methods=["POST"])
def fetch_ical():
    data = request.get_json() or {}
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"status": "error", "message": "URL manquante"}), 400

    if url.startswith("webcal://"):
        url = "https://" + url[9:]

    try:
        parsed_url = urllib.parse.urlsplit(url)
        encoded_path = urllib.parse.quote(parsed_url.path)
        encoded_query = urllib.parse.quote(parsed_url.query, safe="=&?%")
        clean_url = urllib.parse.urlunsplit(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                encoded_path,
                encoded_query,
                parsed_url.fragment,
            )
        )

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
