"""Testes sem chamadas externas: python -m unittest discover -s tests -v."""

import json
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from src.controller.chatController import ChatController
from src.services.chat_events import FiltroVeredito, separar_veredito
from src.services.markdown_service import formatar_resposta_ia
from src.services.openai_services import transmitir_resposta


TEXTO = "**Análise:** Uma análise.\n\n**Fontes consultadas:** [Fonte](https://example.org)\n\n**Veredicto:** FALSO"


class StreamingTests(unittest.TestCase):
    def test_marcador_dividido_em_qualquer_posicao(self):
        for i in range(len(TEXTO)):
            filtro = FiltroVeredito()
            saida = filtro.adicionar(TEXTO[:i]) + filtro.adicionar(TEXTO[i:]) + filtro.finalizar()
            self.assertEqual(saida, TEXTO.split("**Veredicto:**")[0])

    def test_fallback_e_markdown_seguro(self):
        self.assertEqual(separar_veredito("Olá")[1]["code"], "INCONCLUSIVO")
        self.assertEqual(separar_veredito("**Veredicto:** inventado")[1]["code"], "INCONCLUSIVO")
        formatado = formatar_resposta_ia(TEXTO)
        self.assertNotIn("Veredicto", formatado["fontes_html"])
        self.assertNotIn("<script>", formatar_resposta_ia("<script>alert(1)</script>")["analise_html"])

    def test_variantes_de_veredito_e_fragmentacao(self):
        variantes = ["Veredicto: falso", "**Veredicto:** FALSO", "**Veredicto**: **Falso**.",
                     "**Veredicto: FALSO**", "### Veredito: Falso.", "Veredito:\n**FALSO**",
                     "Veredicto: FALSO — a afirmação não procede."]
        for variante in variantes:
            texto = "Uma **análise**.\n\n" + variante
            with self.subTest(variante=variante):
                corpo, veredito = separar_veredito(texto)
                self.assertEqual(veredito["code"], "FALSO")
                self.assertEqual(corpo, "Uma **análise**.")
                for tamanho in range(1, len(texto) + 1):
                    filtro = FiltroVeredito()
                    saida = "".join(filtro.adicionar(texto[i:i+tamanho]) for i in range(0, len(texto), tamanho))
                    saida += filtro.finalizar()
                    self.assertEqual(saida.strip(), corpo)

    def test_veredito_no_inicio_nao_esconde_analise(self):
        filtro = FiltroVeredito()
        texto = "**Veredicto:** FALSO\n\nAnálise continua **visível**."
        saida = "".join(filtro.adicionar(c) for c in texto) + filtro.finalizar()
        self.assertEqual(saida.strip(), "Análise continua **visível**.")

    def test_historico_com_fallback_duplicado(self):
        texto = "Análise\nVeredicto: falso\n\n**Veredicto:** INCONCLUSIVO"
        corpo, veredito = separar_veredito(texto)
        self.assertEqual(veredito["code"], "FALSO")
        self.assertEqual(corpo, "Análise")

    def test_corpo_completo_preserva_negrito_antes_e_depois_das_secoes(self):
        texto = "**Termo inicial**\n\n**Análise:** Outro **termo importante**.\n\n**Fontes consultadas:** **Fonte**\n\n**Veredicto:** FALSO"
        html = formatar_resposta_ia(texto)["corpo_html"]
        self.assertIn("<strong>Termo inicial</strong>", html)
        self.assertIn("<strong>termo importante</strong>", html)
        self.assertIn("<strong>Fonte</strong>", html)
        self.assertNotIn("Veredicto", html)
        filtro = FiltroVeredito()
        parcial = "".join(filtro.adicionar(c) for c in texto) + filtro.finalizar()
        from src.services.markdown_service import renderizar_markdown
        self.assertEqual(renderizar_markdown(parcial.strip()), html)

    @patch("src.services.openai_services.client")
    def test_eventos_sdk_e_tokens(self, client):
        eventos = [Obj(type="response.web_search_call.searching"),
                   Obj(type="response.web_search_call.completed")]
        eventos += [Obj(type="response.output_text.delta", delta=c) for c in TEXTO]
        eventos += [Obj(type="response.completed", response=Obj(output_text=TEXTO, usage=Obj(total_tokens=42)))]
        client.responses.create.return_value.__enter__.return_value = iter(eventos)
        resultado = list(transmitir_resposta("teste"))
        self.assertEqual(resultado[-1]["tokens"], 42)
        self.assertNotIn("Veredicto", "".join(e["text"] for e in resultado if e["type"] == "delta"))
        self.assertIn("searching", [e["stage"] for e in resultado if e["type"] == "stage"])
        self.assertTrue(client.responses.create.call_args.kwargs["stream"])

    @patch("src.services.openai_services.client")
    def test_stream_incompleto_nao_e_sucesso(self, client):
        client.responses.create.return_value.__enter__.return_value = iter([])
        with self.assertRaises(RuntimeError):
            list(transmitir_resposta("teste"))

    def criar_cliente(self):
        controller = ChatController.__new__(ChatController)
        controller.chat_model = MagicMock()
        controller.user_model = MagicMock()
        controller.chat_model.get_mensagens_por_conversa.return_value = []
        controller.chat_model.save_mensagem.return_value = {"_id": "1"}
        controller.user_model.verificar_e_incrementar_uso.return_value = (True, {})
        controller._usuario_autorizado = lambda: ("uid", None)
        app = Flask(__name__)
        app.add_url_rule("/mensagem", view_func=controller.enviar_mensagem, methods=["POST"])
        return app.test_client(), controller

    def test_endpoint_incremental_persistencia_e_veredito(self):
        client, controller = self.criar_cliente()
        eventos = iter([{"type": "delta", "text": "Uma **análise**"},
                        {"type": "result", "text": TEXTO, "tokens": 42}])
        with patch("src.controller.chatController.transmitir_resposta", return_value=(e for e in eventos)):
            res = client.post("/mensagem", json={"prompt": "teste", "conversa_id": "c"},
                              headers={"Accept": "text/event-stream"}, buffered=False)
            partes = iter(res.response)
            primeiro = next(partes).decode()
            self.assertIn('"delta"', primeiro)
            self.assertIn("<strong>análise</strong>", primeiro)
            controller.chat_model.save_mensagem.assert_not_called()
            resto = b"".join(partes).decode()
        self.assertLess(resto.index('"verdict"'), resto.index('"done"'))
        controller.user_model.registrar_tokens_usados.assert_called_once_with("uid", 42)
        self.assertEqual(controller.chat_model.save_mensagem.call_args.args[-1]["code"], "FALSO")

    def test_limite_permanece_json(self):
        client, controller = self.criar_cliente()
        controller.user_model.verificar_e_incrementar_uso.return_value = (False, {})
        res = client.post("/mensagem", json={"prompt": "teste", "conversa_id": "c"},
                          headers={"Accept": "text/event-stream"})
        self.assertEqual(res.status_code, 429)
        self.assertTrue(res.is_json)

    def test_cliente_antigo_continua_recebendo_json(self):
        client, _ = self.criar_cliente()
        with patch("src.controller.chatController.obter_resposta", return_value=(TEXTO, 42)):
            res = client.post("/mensagem", json={"prompt": "teste", "conversa_id": "c"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["veredito"]["code"], "FALSO")

    def test_veredito_simples_chega_ao_frontend_sem_duplicar(self):
        client, controller = self.criar_cliente()
        texto = "**Análise:** Afirmação falsa.\n\nVeredicto: falso"
        eventos = ({"type": "result", "text": texto, "tokens": 10} for _ in range(1))
        with patch("src.controller.chatController.transmitir_resposta", return_value=eventos):
            res = client.post("/mensagem", json={"prompt": "teste", "conversa_id": "c"},
                              headers={"Accept": "text/event-stream"})
            quadros = [json.loads(p.removeprefix("data: ")) for p in res.text.strip().split("\n\n")]
        final = quadros[-1]
        self.assertEqual(final["veredito"]["code"], "FALSO")
        self.assertEqual(final["resposta"].lower().count("veredicto"), 1)
        self.assertNotIn("Veredicto", final["resposta_formatada"]["analise_html"])
        self.assertEqual(controller.chat_model.save_mensagem.call_args.args[-1]["code"], "FALSO")

    def test_falha_ao_salvar_nao_envia_done(self):
        client, controller = self.criar_cliente()
        controller.chat_model.save_mensagem.side_effect = RuntimeError("Mongo indisponível")
        eventos = ({"type": "result", "text": TEXTO, "tokens": 42} for _ in range(1))
        with patch("src.controller.chatController.transmitir_resposta", return_value=eventos):
            with self.assertLogs("src.controller.chatController", level="ERROR"):
                res = client.post("/mensagem", json={"prompt": "teste", "conversa_id": "c"},
                                  headers={"Accept": "text/event-stream"})
                texto = res.text
        self.assertIn('"verdict"', texto)
        self.assertIn('"error"', texto)
        self.assertNotIn('"done"', texto)

    def test_falha_emite_erro_e_fallback(self):
        client, _ = self.criar_cliente()
        def falhar(*args):
            yield {"type": "delta", "text": "Parcial"}
            raise RuntimeError("falha simulada")
        with patch("src.controller.chatController.transmitir_resposta", side_effect=falhar):
            with self.assertLogs("src.controller.chatController", level="ERROR"):
                res = client.post("/mensagem", json={"prompt": "teste", "conversa_id": "c"},
                                  headers={"Accept": "text/event-stream"})
                eventos = [json.loads(p.removeprefix("data: ")) for p in res.text.strip().split("\n\n")]
        self.assertEqual(eventos[-1]["type"], "error")
        self.assertEqual(eventos[-1]["veredito"]["code"], "INCONCLUSIVO")


if __name__ == "__main__":
    unittest.main()
