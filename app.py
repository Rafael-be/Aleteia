"""Ponto de entrada Flask da AleteIA."""

import json
import os
from pathlib import Path

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials
from flask import Flask, render_template
from pymongo import MongoClient

from src.routes.authRoutes import auth_routes
from src.routes.chatRoutes import chat_routes

BASE_DIR = Path(__file__).resolve().parent
for env_file, override in ((BASE_DIR / "Exemplo.env", False), (BASE_DIR / ".env", True)):
    if env_file.exists():
        load_dotenv(env_file, override=override)


def inicializar_firebase_admin() -> None:
    """Inicializa o Admin SDK com a service account armazenada no ambiente."""
    if firebase_admin._apps:
        return
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not service_account_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON não foi configurada.")
    try:
        service_account = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON contém JSON inválido.") from exc
    firebase_admin.initialize_app(credentials.Certificate(service_account))


inicializar_firebase_admin()

app = Flask(__name__, template_folder="public", static_folder="static", static_url_path="/static")

mongo_uri = os.getenv("MONGO_URI") or "mongodb://localhost:27017"
mongo_db_name = os.getenv("MONGO_DB_NAME") or "aleteia"
try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    db = client[mongo_db_name]
    print(f"MongoDB conectado em {mongo_uri}")
except Exception as exc:
    print(f"MongoDB indisponível: {exc}")
    db = None

app.register_blueprint(auth_routes(db))
app.register_blueprint(chat_routes(db))


@app.context_processor
def firebase_web_config():
    """Expõe somente a configuração pública usada pelo SDK Web do Firebase."""
    raw_config = os.getenv("FIREBASE_WEB_CONFIG_JSON", "{}")
    try:
        return {"firebase_web_config": json.loads(raw_config)}
    except json.JSONDecodeError:
        return {"firebase_web_config": {}}


@app.route("/cadastro")
def cadastro():
    return render_template("cadastroTeste/cadastro.html")


@app.route("/")
def index():
    return render_template("main/main-desktop.html")


@app.route("/chat")
@app.route("/conversa")
def chat():
    """A proteção de acesso é feita pelo token Firebase no frontend e APIs."""
    return render_template("chat/chatIndex.html")


@app.route("/login")
def login_page():
    return render_template("login/login.html")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False)
