"""Ponto de entrada Flask da AleteIA."""

import logging
import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials
from flask import Flask, render_template, request, url_for
from src import config
from src.utils.api import configure_api
from src.database import MongoDatabaseProvider
from src.routes.authRoutes import auth_routes
from src.routes.chatRoutes import chat_routes

BASE_DIR = Path(__file__).resolve().parent


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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
configure_api(app)

mongo_uri = os.getenv("MONGO_URI") or "mongodb://localhost:27017"
mongo_db_name = os.getenv("MONGO_DB_NAME") or "aleteia"
# A conexão é feita sob demanda pelos models e é tentada novamente em cada
# requisição que chegar enquanto o Mongo estiver indisponível.
mongo_db = MongoDatabaseProvider(mongo_uri, mongo_db_name)

app.register_blueprint(auth_routes(mongo_db))
app.register_blueprint(chat_routes(mongo_db))


@app.context_processor
def injetar_firebase_config():
    """Expõe o JSON público do Firebase para os templates que usam o SDK Web."""
    def asset_url(filename):
        """Versiona assets locais por mtime para permitir cache imutável com segurança."""
        caminho = BASE_DIR / "static" / filename
        versao = caminho.stat().st_mtime_ns if caminho.is_file() else None
        return url_for("static", filename=filename, v=versao)

    return {
        "firebase_web_config_json": os.getenv("FIREBASE_WEB_CONFIG_JSON", "{}"),
        "chrome_extension_ids": os.getenv("CHROME_EXTENSION_IDS", "").split(","),
        "asset_url": asset_url,
    }

@app.after_request
def add_coop_headers(response):
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if request.args.get("v") else "public, max-age=3600, must-revalidate"
        )
    return response


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


@app.route("/extension")
def extensao():
    return render_template("extensao/extensao.html")


@app.route("/privacidade")
def privacidade():
    return render_template("privacidade.html")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False)
