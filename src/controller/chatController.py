"""Rotas do chat autenticadas exclusivamente por ID tokens do Firebase."""

import json
import logging

from flask import Response, jsonify, request, stream_with_context

from src.models.chatModel import ChatModel
from src.models.userModel import UserModel
from src.services.markdown_service import formatar_resposta_ia, renderizar_markdown
from src.services.openai_services import obter_resposta, transmitir_resposta
from src.services.chat_events import separar_veredito, etapa
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
            mensagens_anteriores = self.chat_model.get_mensagens_por_conversa(uid, conversa_id)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        if not pode_usar:
            limite = usuario.get("limite_diario_perguntas", 10) if usuario else 10
            return jsonify({"error": "limite_diario_excedido", "limite": limite}), 429
        historico = [item for mensagem in mensagens_anteriores for item in (
            {"role": "user", "content": mensagem["prompt"]},
            {"role": "assistant", "content": mensagem["resposta"]},
        )]
        if request.accept_mimetypes.best == "text/event-stream":
            return self._transmitir(uid, conversa_id, prompt, historico)
        try:
            texto_resposta, tokens_gastos = obter_resposta(prompt, historico)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        try:
            chat_salvo = self.chat_model.save_mensagem(uid, conversa_id, prompt, texto_resposta)
            self.user_model.registrar_tokens_usados(uid, tokens_gastos)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({
            "resposta": texto_resposta,
            "resposta_formatada": formatar_resposta_ia(texto_resposta),
            "veredito": separar_veredito(texto_resposta)[1],
            "chat": chat_salvo,
        }), 200

    def _transmitir(self, uid, conversa_id, prompt, historico):
        def serializar(evento):
            return f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"

        @stream_with_context
        def gerar():
            resposta = transmitir_resposta(prompt, historico)
            texto_parcial = ""
            try:
                for evento in resposta:
                    if evento["type"] == "delta":
                        texto_parcial += evento["text"]
                        # Mesmo renderizador seguro durante e depois da geração.
                        evento = {**evento, "html": renderizar_markdown(texto_parcial)}
                    if evento["type"] != "result":
                        yield serializar(evento)
                        continue
                    texto = evento["text"]
                    veredito = separar_veredito(texto)[1]
                    # O fallback também fica no histórico e no contexto seguinte.
                    corpo, _ = separar_veredito(texto)
                    texto = f"{corpo}\n\n**Veredicto:** {veredito['code']}"
                    yield serializar({"type": "verdict", "veredito": veredito})
                    yield serializar(etapa("saving", "Salvando a conversa..."))
                    salvo = self.chat_model.save_mensagem(uid, conversa_id, prompt, texto, veredito)
                    self.user_model.registrar_tokens_usados(uid, evento["tokens"])
                    yield serializar({"type": "done", "resposta": texto,
                                      "resposta_formatada": formatar_resposta_ia(texto),
                                      "veredito": veredito, "chat": salvo})
            except Exception:
                logging.getLogger(__name__).exception("Falha no streaming do chat")
                yield serializar({"type": "error", "message":
                    "Não foi possível concluir ou salvar a resposta. Tente novamente.",
                    "veredito": {"version": 1, "code": "INCONCLUSIVO", "metrics": []}})
            finally:
                resposta.close()

        return Response(gerar(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
        })

    def get_conversas(self):
        uid, erro = self._usuario_autorizado()
        if erro:
            return erro
        try:
            conversas = self.chat_model.get_conversas_por_usuario(uid)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({"prompts": conversas}), 200

    def pesquisar_conversas(self):
        uid, erro = self._usuario_autorizado()
        if erro:
            return erro
        termo = request.args.get("q", "").strip()
        if not termo:
            return jsonify({"error": "Informe um termo de busca."}), 400
        try:
            conversas = self.chat_model.pesquisar_conversas(uid, termo)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({"prompts": conversas}), 200

    def apagar_conversa(self, conversa_id):
        uid, erro = self._usuario_autorizado()
        if erro:
            return erro
        try:
            apagadas = self.chat_model.apagar_conversa(uid, conversa_id)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        if apagadas == 0:
            return jsonify({"error": "Conversa não encontrada."}), 404
        return jsonify({"apagadas": apagadas}), 200

    def get_mensagens_por_conversa(self, conversa_id):
        uid, erro = self._usuario_autorizado()
        if erro:
            return erro
        try:
            mensagens = self.chat_model.get_mensagens_por_conversa(uid, conversa_id)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        for mensagem in mensagens:
            mensagem["resposta_formatada"] = formatar_resposta_ia(mensagem["resposta"])
            salvo = mensagem.get("veredito")
            # Corrige também históricos afetados pelo parser antigo sem perder métricas.
            mensagem["veredito"] = salvo if salvo and salvo.get("metrics") else separar_veredito(mensagem["resposta"])[1]
        return jsonify({"mensagens": mensagens}), 200
