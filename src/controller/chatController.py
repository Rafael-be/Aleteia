"""
Módulo de Controlador de Chat.

Este módulo gerencia as rotas da API relacionadas ao histórico de chats,
realizando a validação de tokens JWT, sanitização de entrada e mediação
entre a requisição HTTP e o modelo de persistência (ChatModel).
"""

import os

import jwt
from flask import jsonify, request

from src.models.chatModel import ChatModel


class ChatController:
    """
    Controlador para gerenciar operações de chat via API.

    Todas as rotas deste controlador exigem um token JWT válido no header:
    Authorization: Bearer <token>
    """

    def __init__(self, db):
        """
        Inicializa o controlador com a instância do banco de dados.

        :param db: Instância do banco de dados MongoDB (pymongo.database.Database).
        """
        self.chat_model = ChatModel(db)

    def _get_user_id_from_token(self) -> str | None:
        """
        Extrai o user_id do token JWT enviado no header Authorization.

        :return: O ID do usuário, armazenado na claim 'sub', se o token for
                 válido. Retorna None quando o header está ausente, malformado
                 ou o token não pode ser decodificado.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        try:
            secret = os.getenv("JWT_SECRET_KEY", "troque-essa-chave-no-env")
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload.get("sub")
        except Exception:
            return None

    def save_prompt(self):
        """
        Endpoint POST /api/chat/prompt.

        Salva um novo prompt no histórico do usuário autenticado.

        Body JSON esperado:
        {
            "prompt": "Texto que o usuário deseja verificar"
        }

        :return: JSON com o documento salvo e status 201, ou mensagem de erro:
                 - 400: Prompt vazio ou corpo inválido.
                 - 401: Token ausente ou inválido.
        """
        user_id = self._get_user_id_from_token()
        if not user_id:
            return jsonify({"error": "Não autorizado."}), 401

        data = request.get_json()
        prompt = data.get("prompt", "").strip() if data else ""

        if not prompt:
            return jsonify({"error": "O prompt não pode estar vazio."}), 400

        saved = self.chat_model.save_prompt(user_id, prompt)
        return jsonify({"message": "Prompt salvo.", "chat": saved}), 201

    def get_prompts(self):
        """
        Endpoint GET /api/chat/prompts.

        Retorna o histórico de prompts do usuário autenticado, ordenado do mais
        recente para o mais antigo.

        :return: JSON no formato {"prompts": [...]} e status 200, ou erro 401
                 quando o token está ausente ou inválido.
        """
        user_id = self._get_user_id_from_token()
        if not user_id:
            return jsonify({"error": "Não autorizado."}), 401

        prompts = self.chat_model.get_prompts_by_user(user_id)
        return jsonify({"prompts": prompts}), 200
