from flask import Blueprint
from src.controller.userController import UserController


def user_routes(db):
    """
    Registra as rotas de usuário em um Blueprint Flask.

    :param db: Instância do banco de dados MongoDB.
    :return: Blueprint com as rotas configuradas.
    """
    user_bp = Blueprint("user", __name__, url_prefix="/api/users")

    controller = UserController(db)

    # POST /api/users/register
    user_bp.add_url_rule(
        "/register",
        view_func=controller.register,
        methods=["POST"]
    )

    # POST /api/users/login
    user_bp.add_url_rule(
        "/login",
        view_func=controller.login,
        methods=["POST"]
    )

    return user_bp