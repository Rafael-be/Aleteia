from flask import request, jsonify
from src.models.chatModel import ChatModel
import jwt
import os

class ChatController:
    def __init__(self, db):
        self.chat_model = ChatModel(db)

    def _get_user_id_from_token(self):
        """Extrai o user_id do JWT enviado no header Authorization."""
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
        """POST /api/chat/prompt — salva um prompt no banco."""
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
        """GET /api/chat/prompts — retorna todos os prompts do usuário."""
        user_id = self._get_user_id_from_token()
        if not user_id:
            return jsonify({"error": "Não autorizado."}), 401

        prompts = self.chat_model.get_prompts_by_user(user_id)
        return jsonify({"prompts": prompts}), 200