"""
Módulo de Rotas de Usuário.

Este módulo registra as rotas da API relacionadas à autenticação e ao
gerenciamento de usuários. As URLs são agrupadas pelo prefixo /api/users
e encaminhadas para os métodos do UserController.
"""

from flask import Blueprint

from src.controller.userController import UserController


def user_routes(db) -> Blueprint:
    """
    Cria e configura o Blueprint de rotas para usuários.

    Endpoints registrados:
    - POST /api/users/register: cadastra um novo usuário.
    - POST /api/users/login: autentica um usuário e retorna um token JWT.

    :param db: Instância do banco de dados MongoDB (pymongo.database.Database).
               Ela é injetada no UserController para manipulação dos dados.
    :return: Blueprint configurado para registro na aplicação Flask principal.
    """
    user_bp = Blueprint("user", __name__, url_prefix="/api/users")
    controller = UserController(db)

    user_bp.add_url_rule("/register", view_func=controller.register, methods=["POST"])
    user_bp.add_url_rule("/login", view_func=controller.login, methods=["POST"])

    return user_bp
