import json
import os
import urllib.request
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
DATA_FILE = "students_data.json"


def get_all_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
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
    payload = request.get_json()
    email = payload.get("email")
    if not email:
        return jsonify({"status": "error", "message": "Email manquant"}), 400

    db = get_all_data()
    db[email] = payload
    save_all_data(db)
    return jsonify({"status": "success", "message": "Sauvegardé avec succès"})


@app.route("/api/students", methods=["GET"])
def get_students():
    return jsonify(get_all_data())


# Proxy iCal pour contourner les blocages CORS (Hyperplanning, Pronote, Apple)
@app.route("/api/fetch-ical", methods=["POST"])
def fetch_ical():
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"status": "error", "message": "URL manquante"}), 400

    # Conversion automatique de webcal:// en https://
    if url.startswith("webcal://"):
        url = "https://" + url[9:]

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode("utf-8", errors="ignore")
        return jsonify({"status": "success", "content": content})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run()
