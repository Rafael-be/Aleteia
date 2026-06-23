"""
Módulo de Rotas de Chat.

Este módulo registra as rotas da API relacionadas ao histórico de prompts.
As URLs são agrupadas pelo prefixo /api/chat e encaminhadas para os métodos
do ChatController.
"""

from flask import Blueprint

from src.controller.chatController import ChatController


def chat_routes(db) -> Blueprint:
    """
    Cria e configura o Blueprint de rotas para chat.

    Endpoints registrados:
    - POST /api/chat/prompt: salva um novo prompt no histórico do usuário logado.
    - GET /api/chat/prompts: retorna os prompts salvos pelo usuário logado.

    As duas rotas exigem token JWT no header:
    Authorization: Bearer <token>

    :param db: Instância do banco de dados MongoDB (pymongo.database.Database).
               Ela é injetada no ChatController para acesso à coleção de chats.
    :return: Blueprint configurado para registro na aplicação Flask principal.
    """
    chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")
    controller = ChatController(db)

    chat_bp.add_url_rule("/prompt", view_func=controller.save_prompt, methods=["POST"])
    chat_bp.add_url_rule("/prompts", view_func=controller.get_prompts, methods=["GET"])

    return chat_bp
