"""
Módulo de Controlador de Chat.

Gerencia as rotas da API relacionadas à conversa com a Aleteia: valida o
token JWT, aplica o limite diário de tokens (exceto para administradores),
chama o serviço da OpenAI e persiste prompt + resposta no ChatModel.
"""

import os

import jwt
from flask import jsonify, request

from src.models.chatModel import ChatModel
from src.models.userModel import UserModel
from src.services.openai_services import obter_resposta
from src.utils.token_limiter import usuario_pode_usar_ia, registrar_uso_de_tokens

LIMITE_DIARIO_USUARIO = int(os.getenv("TOKENS_LIMITE_DIARIO_USUARIO", "20000"))


class ChatController:
    """
    Controlador para gerenciar a conversa com a Aleteia via API.

    Todas as rotas deste controlador exigem um token JWT válido no header:
    Authorization: Bearer <token>
    """

    def __init__(self, db):
        """
        Inicializa o controlador com a instância do banco de dados.

        :param db: Instância do banco de dados MongoDB (pymongo.database.Database).
        """
        self.chat_model = ChatModel(db)
        self.user_model = UserModel(db)

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

    def enviar_mensagem(self):
        """
        Endpoint POST /api/chat/mensagem.

        Body JSON esperado:
        {
            "conversa_id": "uuid-gerado-no-frontend",
            "prompt": "Texto que o usuário quer verificar"
        }

        Fluxo:
        1. Valida o token e extrai o user_id.
        2. Confere se o usuário pode usar a IA (admin sempre pode; usuário
           comum precisa estar abaixo do limite diário de tokens).
        3. Busca o histórico da conversa no Mongo para dar contexto à IA.
        4. Chama a OpenAI e salva prompt + resposta juntos.
        5. Atualiza o contador de tokens do usuário (ignorado se for admin).

        :return: JSON com a resposta da IA e status 200, ou erro:
                 - 400: prompt vazio ou conversa_id ausente.
                 - 401: token ausente ou inválido.
                 - 429: limite diário de tokens excedido.
                 - 502: falha ao chamar a OpenAI.
        """
        user_id = self._get_user_id_from_token()
        if not user_id:
            return jsonify({"error": "Não autorizado."}), 401

        data = request.get_json() or {}
        prompt = (data.get("prompt") or "").strip()
        conversa_id = (data.get("conversa_id") or "").strip()

        if not prompt:
            return jsonify({"error": "O prompt não pode estar vazio."}), 400
        if not conversa_id:
            return jsonify({"error": "conversa_id é obrigatório."}), 400

        pode_usar, tokens_usados, limite = usuario_pode_usar_ia(
            self.user_model, user_id, LIMITE_DIARIO_USUARIO
        )
        if not pode_usar:
            return jsonify({
                "error": "limite_diario_excedido",
                "tokens_usados": tokens_usados,
                "limite": limite
            }), 429

        mensagens_anteriores = self.chat_model.get_mensagens_por_conversa(conversa_id)
        historico = []
        for m in mensagens_anteriores:
            historico.append({"role": "user", "content": m["prompt"]})
            historico.append({"role": "assistant", "content": m["resposta"]})

        try:
            texto_resposta, tokens_gastos = obter_resposta(prompt, historico)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

        chat_salvo = self.chat_model.save_mensagem(user_id, conversa_id, prompt, texto_resposta)
        registrar_uso_de_tokens(self.user_model, user_id, tokens_gastos)

        return jsonify({"resposta": texto_resposta, "chat": chat_salvo}), 200

    def get_conversas(self):
        """
        Endpoint GET /api/chat/conversas.

        Retorna uma linha por conversa do usuário autenticado (para a sidebar),
        ordenada da mais recente para a mais antiga.

        :return: JSON {"prompts": [...]} e status 200, ou erro 401.
        """
        user_id = self._get_user_id_from_token()
        if not user_id:
            return jsonify({"error": "Não autorizado."}), 401

        conversas = self.chat_model.get_conversas_por_usuario(user_id)
        return jsonify({"prompts": conversas}), 200

    def get_mensagens_por_conversa(self, conversa_id):
        """
        Endpoint GET /api/chat/conversas/<conversa_id>.

        Retorna todas as mensagens (prompt + resposta) de uma conversa
        específica, usado para recarregar uma conversa antiga clicada na
        sidebar.

        :return: JSON {"mensagens": [...]} e status 200, ou erro 401.
        """
        user_id = self._get_user_id_from_token()
        if not user_id:
            return jsonify({"error": "Não autorizado."}), 401

        mensagens = self.chat_model.get_mensagens_por_conversa(conversa_id)
        return jsonify({"mensagens": mensagens}), 200