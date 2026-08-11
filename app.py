"""
Ponto de entrada da aplicação Flask da AleteIA.

Este arquivo configura a aplicação, conecta ao MongoDB, registra os
blueprints da API e define as rotas que renderizam as páginas HTML.
"""

import os
from pathlib import Path
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, session, redirect, url_for, jsonify
from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parent
example_env = BASE_DIR / "Exemplo.env"
if example_env.exists():
    load_dotenv(example_env, override=False)

project_env = BASE_DIR / ".env"
if project_env.exists():
    load_dotenv(project_env, override=True)

# NOVO: não importamos mais "gemini_bp" aqui — o Blueprint continua existindo
# em src/routes/chatRoutes.py, só deixamos de registrá-lo.
from src.routes.chatRoutes import chat_routes
from src.routes.userRoutes import user_routes

app = Flask(__name__, template_folder="public", static_folder="static", static_url_path="/static")

# REMOVIDO: app.register_blueprint(gemini_bp)
# O Gemini continua no código-fonte, mas nenhuma rota do Flask aponta pra ele.

# SECRET_KEY é obrigatório para sessões Flask funcionarem
app.secret_key = os.getenv("SECRET_KEY", "criptografia123")

# Configurações de segurança do cookie de sessão
app.config["SESSION_COOKIE_HTTPONLY"] = True   # JS não consegue ler o cookie
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Proteção contra CSRF básica
# app.config["SESSION_COOKIE_SECURE"] = True   # Descomente em produção (HTTPS)

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

# Rotas de API:
# - /api/users/register
# - /api/users/login
# - /api/chat/mensagem
# - /api/chat/conversas
# - /api/chat/conversas/<conversa_id>
app.register_blueprint(user_routes(db))


# ------------------------------------------------------------------
# Decorator: protege rotas que exigem login
# ------------------------------------------------------------------
def login_required(f):
    """
    Use @login_required em qualquer rota que precise de autenticação.
    Redireciona para /login se o usuário não estiver logado.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

app.register_blueprint(chat_routes(db))


@app.route("/cadastro")
def cadastro():
    """Renderiza a página de cadastro de usuário."""
    return render_template("cadastroTeste/cadastro.html")


@app.route("/")
def index():
    """Renderiza a página inicial do site."""
    return render_template("main/main-desktop.html")


@app.route("/chat")
@login_required          # ← protege a rota /chat
def logado():
    """Renderiza a página principal do chat."""
    return render_template("chat/chatIndex.html")


@app.route("/conversa")
def conversa():
    """
    Renderiza a mesma página de chat. Mantida por compatibilidade, mas não é
    mais usada pelo fluxo atual (o chat.js não faz mais redirect pra cá).
    """
    return render_template("chat/chatIndex.html")


@app.route("/login")
def login_page():
    """Renderiza a página de login."""
    return render_template("login/login.html")

@app.route("/logout", methods=["POST"])
def logout():
    """Encerra a sessão do servidor e redireciona para a página inicial."""
    session.clear()
    return redirect(url_for("index"))

@app.route("/api/session-status")
def session_status():
    """Retorna se o usuário está logado e seus dados básicos (usado pelo JS)."""
    if "user_id" in session:
        return jsonify({
            "logado": True,
            "email": session.get("email"),
            "user_id": session.get("user_id")
        })
    return jsonify({"logado": False})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    print(app.url_map)
    app.run(host=host, port=port, debug=False)
