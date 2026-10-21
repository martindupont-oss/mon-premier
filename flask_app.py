import json
import os
import urllib.parse
import urllib.request
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
DATA_FILE = "students_data.json"


def get_all_data():
    """Charge et nettoie les données pour éviter tout doublon d'email."""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            raw_db = json.load(f)
            cleaned_db = {}
            for k, v in raw_db.items():
                clean_email = k.strip().lower()
                # En cas de doublon, on conserve la mise à jour la plus récente
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

    payload["email"] = email  # Normalisation de l'email
    db = get_all_data()
    db[email] = payload  # Écrasement/mise à jour de l'élève unique
    save_all_data(db)
    return jsonify({"status": "success", "message": "Sauvegardé avec succès"})


@app.route("/api/students", methods=["GET"])
def get_students():
    return jsonify(get_all_data())


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
