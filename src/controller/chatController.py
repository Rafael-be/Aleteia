"""Rotas do chat autenticadas exclusivamente por ID tokens do Firebase."""

import json
import logging
from typing import TypedDict

from flask import Response, jsonify, request, stream_with_context, g
from pymongo.errors import PyMongoError
from time import perf_counter

from src.models.chatModel import ChatModel
from src.models.userModel import UserModel
from src.services.markdown_service import formatar_resposta_ia, renderizar_markdown
from src.services.openai_services import obter_resposta, transmitir_resposta
from src.services.chat_events import separar_veredito, etapa
from src.services.analysis_service import UsageLedger
from src.services.analysis_errors import operational_error
from src.services.prompt_images import IMAGE_ONLY_PROMPT, validate_images
from src.core.input_gate import is_noise
from src.utils.auth import obter_uid_do_token_firebase


class Paginacao(TypedDict):
    limit: int
    offset: int


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
        if uid is None:
            assert erro is not None
            return erro
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or any(not isinstance(data.get(k), str) for k in ('prompt', 'conversa_id')):
            return jsonify(code='invalid_payload', message='Envie prompt e conversa_id como texto.', error='Payload inválido.'), 400
        prompt, conversa_id = data['prompt'].strip(), data['conversa_id'].strip()
        mode = data.get('mode', 'standard')
        if mode not in ('standard', 'experimental'):
            return jsonify(code='invalid_mode', message='Modo de resposta inválido.', error='Modo inválido.'), 400
        if len(prompt) > 12000 or len(conversa_id) > 128:
            return jsonify(code='invalid_payload', message='Texto ou ID excede o limite.', error='Entrada muito longa.'), 400
        try:
            images = validate_images(data.get('images', []))
        except ValueError as exc:
            return jsonify(code='invalid_images', message=str(exc), error=str(exc)), 400
        if images and not prompt:
            prompt = IMAGE_ONLY_PROMPT
        attachment_options = {'images': images} if images else {}
        if not prompt:
            return jsonify({"error": "O prompt não pode estar vazio."}), 400
        if not conversa_id:
            return jsonify({"error": "conversa_id é obrigatório."}), 400
        try:
            self.user_model.sincronizar_usuario_firebase(uid, getattr(g, 'firebase_claims', {}).get('email'))
            mensagens_anteriores = self.chat_model.get_mensagens_por_conversa(uid, conversa_id, limit=12, recent=True)
            pode_usar, usuario = self.user_model.verificar_e_incrementar_uso(uid)
        except (RuntimeError, PyMongoError):
            return jsonify(code="database_unavailable", message="Banco de dados indisponível. Tente novamente.", error="Banco de dados indisponível."), 503
        if usuario is None:
            return jsonify(code='profile_unavailable', message='Perfil indisponível.', error='Perfil indisponível.'), 503
        if not pode_usar:
            if usuario.get('quota_reason') == 'rate_limited':
                return jsonify(code='rate_limited', message='Aguarde antes de enviar outra pergunta.', error='Aguarde antes de enviar outra pergunta.'), 429
            limite = usuario.get("limite_diario_perguntas", 10) if usuario else 10
            return jsonify({"error": "limite_diario_excedido", "limite": limite}), 429
        # Noise still traverses authenticated, atomic traffic reservation. It is
        # refunded as an analysis, but its minute rate count is never refunded.
        local = mode == 'experimental' and not images and is_noise(prompt)
        ledger = UsageLedger(lambda tokens: self.user_model.registrar_tokens_usados(
            uid, tokens, dia=usuario.get('reservation_day')))
        historico = [item for mensagem in mensagens_anteriores for item in (
            {"role": "user", "content": mensagem["prompt"]},
            {"role": "assistant", "content": mensagem["resposta"]},
        )]
        if request.accept_mimetypes.best == "text/event-stream":
            return self._transmitir(uid, conversa_id, prompt, historico, usuario, ledger, local, mode, **attachment_options)
        try:
            resultado = obter_resposta(prompt, historico, ledger=ledger, mode=mode, **attachment_options)
            texto_resposta, tokens_gastos = resultado
        except RuntimeError as exc:
            self._finalizar(uid, usuario, ledger.attempted)
            falha = operational_error(exc)
            return jsonify(code=falha.code, message=falha.message, error=falha.message), 502
        self._finalizar(uid, usuario, not local)
        veredito = getattr(resultado, 'verdict', None) or separar_veredito(texto_resposta)[1]
        try:
            chat_salvo = self.chat_model.save_mensagem(uid, conversa_id, prompt, texto_resposta,
                                                      veredito, audit=getattr(resultado, 'audit', None))
            if not ledger.total and tokens_gastos:
                self.user_model.registrar_tokens_usados(uid, tokens_gastos)
        except (RuntimeError, PyMongoError):
            return jsonify(code="database_unavailable", message="Banco de dados indisponível. Tente novamente.", error="Banco de dados indisponível."), 503
        return jsonify({
            "resposta": texto_resposta,
            "resposta_formatada": formatar_resposta_ia(texto_resposta),
            "veredito": veredito,
            "chat": chat_salvo,
        }), 200

    def _finalizar(self, uid, reserva, sucesso):
        try:
            self.user_model.finalizar_reserva(uid, reserva, sucesso)
        except (RuntimeError, PyMongoError):
            logging.getLogger(__name__).error('quota_finalize_failed success=%s', sucesso)

    def _transmitir(self, uid, conversa_id, prompt, historico, reserva, ledger, local=False, mode='standard', *, images=()):
        def serializar(evento):
            return f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"

        def gerar():
            options = {'images': images} if images else {}
            resposta = transmitir_resposta(prompt, historico, ledger=ledger, mode=mode, **options)
            texto_parcial = ""
            concluido = False
            inicio = perf_counter()
            try:
                for evento in resposta:
                    if evento["type"] == "delta":
                        texto_parcial += evento["text"]
                        # Mesmo renderizador seguro durante e depois da geração.
                        yield serializar({**evento, "html": renderizar_markdown(texto_parcial)})
                        continue
                    if evento["type"] != "result":
                        yield serializar(evento)
                        continue
                    concluido = True
                    texto = evento["text"]
                    veredito = evento.get('veredito') or separar_veredito(texto)[1]
                    if veredito.get('version') != 2:
                        corpo, _ = separar_veredito(texto)
                        texto = f"{corpo}\n\n**Veredicto:** {veredito['code']}"
                    yield serializar({"type": "verdict", "veredito": veredito})
                    yield serializar(etapa("saving", "Salvando a conversa..."))
                    salvo = self.chat_model.save_mensagem(uid, conversa_id, prompt, texto, veredito,
                                                          audit=evento.get('audit'))
                    if not ledger.total and evento['tokens']:
                        self.user_model.registrar_tokens_usados(uid, evento["tokens"])
                    yield serializar({"type": "done", "resposta": texto,
                                      "resposta_formatada": formatar_resposta_ia(texto),
                                      "veredito": veredito, "chat": salvo})
            except Exception as exc:
                logging.getLogger(__name__).error("chat_stream_failed request_id=%s", getattr(g, "request_id", "unknown"))
                falha = operational_error(exc)
                yield serializar({'type': 'error', 'code': falha.code,
                                  'message': falha.message,
                                  'request_id': getattr(g, 'request_id', 'unknown')})
            finally:
                resposta.close()
                self._finalizar(uid, reserva, not local and (concluido or ledger.attempted))
                logging.getLogger(__name__).info('phase=stream duration_ms=%.1f request_id=%s', (perf_counter()-inicio)*1000, getattr(g, 'request_id', 'unknown'))

        response = Response(stream_with_context(gerar()), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
        })
        # Covers a response closed before the generator starts. The reservation
        # ID makes this a no-op after normal finalization.
        response.call_on_close(lambda: self._finalizar(uid, reserva, ledger.attempted and not local))
        return response

    @staticmethod
    def _pagina() -> Paginacao:
        return {'limit': int(request.args.get('limit', 100)), 'offset': int(request.args.get('offset', 0))}

    def get_conversas(self):
        uid, erro = self._usuario_autorizado()
        if uid is None:
            assert erro is not None
            return erro
        try:
            conversas = self.chat_model.get_conversas_por_usuario(uid, **self._pagina())
        except (RuntimeError, PyMongoError):
            return jsonify(code="database_unavailable", message="Banco de dados indisponível. Tente novamente.", error="Banco de dados indisponível."), 503
        return jsonify({"prompts": conversas, "pagination": {**self._pagina(), "has_more": len(conversas) == self._pagina()["limit"]}}), 200

    def pesquisar_conversas(self):
        uid, erro = self._usuario_autorizado()
        if uid is None:
            assert erro is not None
            return erro
        termo = request.args.get("q", "").strip()
        if not termo:
            return jsonify({"error": "Informe um termo de busca."}), 400
        try:
            conversas = self.chat_model.pesquisar_conversas(uid, termo, **self._pagina())
        except (RuntimeError, PyMongoError):
            return jsonify(code="database_unavailable", message="Banco de dados indisponível. Tente novamente.", error="Banco de dados indisponível."), 503
        return jsonify({"prompts": conversas, "pagination": {**self._pagina(), "has_more": len(conversas) == self._pagina()["limit"]}}), 200

    def apagar_conversa(self, conversa_id):
        uid, erro = self._usuario_autorizado()
        if uid is None:
            assert erro is not None
            return erro
        try:
            apagadas = self.chat_model.apagar_conversa(uid, conversa_id)
        except (RuntimeError, PyMongoError):
            return jsonify(code="database_unavailable", message="Banco de dados indisponível. Tente novamente.", error="Banco de dados indisponível."), 503
        if apagadas == 0:
            return jsonify({"error": "Conversa não encontrada."}), 404
        return jsonify({"apagadas": apagadas}), 200

    def get_mensagens_por_conversa(self, conversa_id):
        uid, erro = self._usuario_autorizado()
        if uid is None:
            assert erro is not None
            return erro
        try:
            mensagens = self.chat_model.get_mensagens_por_conversa(uid, conversa_id, **self._pagina())
        except (RuntimeError, PyMongoError):
            return jsonify(code="database_unavailable", message="Banco de dados indisponível. Tente novamente.", error="Banco de dados indisponível."), 503
        for mensagem in mensagens:
            mensagem["resposta_formatada"] = formatar_resposta_ia(mensagem["resposta"])
            salvo = mensagem.get("veredito")
            # Corrige também históricos afetados pelo parser antigo sem perder métricas.
            mensagem["veredito"] = salvo if salvo and (salvo.get('version') == 2 or salvo.get("metrics") or salvo.get('mode') == 'standard') else separar_veredito(mensagem["resposta"])[1]
        return jsonify({"mensagens": mensagens, "pagination": {**self._pagina(), "has_more": len(mensagens) == self._pagina()["limit"]}}), 200
