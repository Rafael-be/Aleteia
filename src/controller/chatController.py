"""Rotas do chat autenticadas exclusivamente por ID tokens do Firebase."""

from flask import jsonify, request

from src.models.chatModel import ChatModel
from src.models.userModel import UserModel
from src.services.openai_services import obter_resposta
from src.utils.auth import obter_uid_do_token_firebase


class ChatController:
    def __init__(self, db):
        self.chat_model = ChatModel(db)
        self.user_model = UserModel(db)

    @staticmethod
    def _usuario_autorizado():
        uid, email_verificado = obter_uid_do_token_firebase(request)
        if not uid:
            return None, (jsonify({"error": "Não autorizado."}), 401)
        if not email_verificado:
            return None, (jsonify({"error": "Confirme seu e-mail antes de usar o chat."}), 403)
        return uid, None

    def enviar_mensagem(self):
        uid, erro = self._usuario_autorizado()
        if erro:
            return erro
        data = request.get_json() or {}
        prompt = (data.get("prompt") or "").strip()
        conversa_id = (data.get("conversa_id") or "").strip()
        if not prompt:
            return jsonify({"error": "O prompt não pode estar vazio."}), 400
        if not conversa_id:
            return jsonify({"error": "conversa_id é obrigatório."}), 400
        try:
            pode_usar, usuario = self.user_model.verificar_e_incrementar_uso(uid)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        if not pode_usar:
            limite = usuario.get("limite_diario_perguntas", 10) if usuario else 10
            return jsonify({"error": "limite_diario_excedido", "limite": limite}), 429
        mensagens_anteriores = self.chat_model.get_mensagens_por_conversa(uid, conversa_id)
        historico = [item for mensagem in mensagens_anteriores for item in (
            {"role": "user", "content": mensagem["prompt"]},
            {"role": "assistant", "content": mensagem["resposta"]},
        )]
        try:
            texto_resposta, tokens_gastos = obter_resposta(prompt, historico)
            chat_salvo = self.chat_model.save_mensagem(uid, conversa_id, prompt, texto_resposta)
            self.user_model.registrar_tokens_usados(uid, tokens_gastos)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify({"resposta": texto_resposta, "chat": chat_salvo}), 200

    def get_conversas(self):
        uid, erro = self._usuario_autorizado()
        if erro:
            return erro
        return jsonify({"prompts": self.chat_model.get_conversas_por_usuario(uid)}), 200

    def get_mensagens_por_conversa(self, conversa_id):
        uid, erro = self._usuario_autorizado()
        if erro:
            return erro
        return jsonify({"mensagens": self.chat_model.get_mensagens_por_conversa(uid, conversa_id)}), 200
