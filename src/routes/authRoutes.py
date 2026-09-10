"""Rotas de suporte à autenticação feita diretamente pelo Firebase."""

from flask import Blueprint

from src.controller.authController import AuthController


def auth_routes(db) -> Blueprint:
    auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
    controller = AuthController(db)
    auth_bp.add_url_rule("/sincronizar", view_func=controller.sincronizar_usuario, methods=["POST"])
    return auth_bp
