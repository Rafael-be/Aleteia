"""
Ponto de entrada da aplicação Flask da AleteIA.

Este arquivo configura a aplicação, conecta ao MongoDB, registra os
blueprints da API e define as rotas que renderizam as páginas HTML.
"""

import os

from dotenv import load_dotenv
from flask import Flask, render_template
from pymongo import MongoClient

from src.routes.chatRoutes import chat_routes
from src.routes.userRoutes import user_routes

load_dotenv()

app = Flask(__name__, template_folder="public", static_folder=".", static_url_path="")

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]

# Rotas de API:
# - /api/users/register
# - /api/users/login
# - /api/chat/prompt
# - /api/chat/prompts
app.register_blueprint(user_routes(db))
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
def logado():
    """Renderiza a página principal do chat."""
    return render_template("chat/chatIndex.html")


@app.route("/login")
def login_page():
    """Renderiza a página de login."""
    return render_template("login/login.html")


if __name__ == "__main__":
    print(app.url_map)
    app.run(debug=True)
