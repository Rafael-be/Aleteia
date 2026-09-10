"""
Módulo de Rotas de Chat.

Registra as rotas da API relacionadas à conversa com a Aleteia (Blueprint
"chat"), encaminhadas para os métodos do ChatController.

O Blueprint "gemini" (rota antiga /api/chat/responder, baseada no Gemini)
continua definido neste arquivo por referência/histórico, mas NÃO é mais
registrado em app.py — ou seja, o código continua existindo no projeto,
só está inativo e não interfere no fluxo atual baseado em OpenAI.
"""

from flask import Blueprint

from src.controller.chatController import ChatController


def chat_routes(db) -> Blueprint:
    """
    Cria e configura o Blueprint de rotas para o chat com a Aleteia (OpenAI).

    Endpoints registrados:
    - POST /api/chat/mensagem: envia um prompt, obtém a resposta da IA e
      salva os dois juntos no histórico da conversa.
    - GET /api/chat/conversas: lista as conversas do usuário logado (sidebar).
    - GET /api/chat/conversas/<conversa_id>: retorna todas as mensagens de
      uma conversa específica.

    Todas exigem um ID token Firebase no header: Authorization: Bearer <token>

    :param db: Instância do banco de dados MongoDB (pymongo.database.Database).
    :return: Blueprint configurado para registro na aplicação Flask principal.
    """
    chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")
    controller = ChatController(db)

    chat_bp.add_url_rule("/mensagem", view_func=controller.enviar_mensagem, methods=["POST"])
    chat_bp.add_url_rule("/conversas", view_func=controller.get_conversas, methods=["GET"])
    chat_bp.add_url_rule(
        "/conversas/<conversa_id>",
        view_func=controller.get_mensagens_por_conversa,
        methods=["GET"]
    )

    return chat_bp


# ------------------------------------------------------------------
# Rota antiga do Gemini — mantida no código por referência, mas NÃO é
# registrada em app.py (ver Passo 8). Não é chamada por nenhum lugar
# do frontend atualmente.
# ------------------------------------------------------------------
