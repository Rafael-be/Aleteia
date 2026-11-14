"""Ponto de entrada Flask da AleteIA."""

import logging
import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials
from flask import Flask, Response, render_template, request, url_for
from src import config
from src.utils.api import configure_api
from src.database import MongoDatabaseProvider
from src.routes.authRoutes import auth_routes
from src.routes.chatRoutes import chat_routes

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://aleteia.onrender.com").rstrip("/")


def url_publica(caminho: str) -> str:
    return f"{PUBLIC_BASE_URL}{caminho}"


def dados_seo(titulo: str, descricao: str, indexavel: bool = False) -> dict:
    return {
        "title": titulo,
        "description": descricao,
        "indexable": indexavel,
        "canonical": url_publica(request.path) if indexavel else None,
        "share_image": url_publica(url_for("static", filename="images/aleteia-share.jpg")),
    }


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
        "site_url": PUBLIC_BASE_URL,
        "search_console_verification": os.getenv("GOOGLE_SITE_VERIFICATION", "").strip(),
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
    return render_template("cadastroTeste/cadastro.html", seo=dados_seo(
        "Criar Conta — AleteIA", "Crie sua conta para usar a AleteIA.", False))


@app.route("/")
def index():
    return render_template("main/main-desktop.html", seo=dados_seo(
        "AleteIA — Análise de Notícias com Inteligência Artificial",
        "Analise notícias e alegações com a AleteIA. Use inteligência artificial para consultar informações, avaliar conteúdos e explorar fontes.", True))


@app.route("/chat")
@app.route("/conversa")
def chat():
    """A proteção de acesso é feita pelo token Firebase no frontend e APIs."""
    return render_template("chat/chatIndex.html", seo=dados_seo(
        "Análise de Notícias — AleteIA", "Área privada de análise da AleteIA.", False))


@app.route("/login")
def login_page():
    return render_template("login/login.html", seo=dados_seo(
        "Entrar — AleteIA", "Entre na sua conta AleteIA.", False))


@app.route("/extension")
def extensao():
    return render_template("extensao/extensao.html", seo=dados_seo(
        "Extensão AleteIA — Análise de Notícias no Navegador",
        "Use a extensão AleteIA para enviar textos selecionados ao chat e analisar notícias enquanto navega.", True))


@app.route("/privacidade")
def privacidade():
    return render_template("privacidade.html", seo=dados_seo(
        "Política de Privacidade — AleteIA", "Saiba como a AleteIA trata dados e informações da sua conta.", False))


@app.route("/sitemap.xml")
def sitemap():
    urls = (url_publica("/"), url_publica("/extension"))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += "".join(f"  <url><loc>{url}</loc></url>\n" for url in urls)
    xml += "</urlset>\n"
    return Response(xml, content_type="application/xml; charset=utf-8")


@app.route("/robots.txt")
def robots():
    producao = os.getenv("APP_ENV", "development").lower() == "production"
    if not producao:
        return Response("User-agent: *\nDisallow: /\n", content_type="text/plain; charset=utf-8")
    texto = "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /chat\nDisallow: /conversa\nDisallow: /login\nDisallow: /cadastro\n"
    texto += f"Sitemap: {url_publica('/sitemap.xml')}\n"
    return Response(texto, content_type="text/plain; charset=utf-8")


@app.errorhandler(404)
def pagina_nao_encontrada(_erro):
    return render_template("404.html", seo=dados_seo(
        "Página não encontrada — AleteIA", "A página solicitada não foi encontrada.", False)), 404


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False)
