"""Default single-generation path and explicit experimental opt-in."""
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace as Obj
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError
from src.services.openai_services import transmitir_resposta, obter_resposta
from src.services.analysis_service import UsageLedger
from src.services.standard_prompt import SYSTEM_PROMPT
from src.services.prompt_images import IMAGE_ONLY_PROMPT
from src.core.contracts import Extraction
import test_streaming
from test_streaming import json_response


TEXT = '**Análise:** Texto **verificado**.\n\n**Veredicto:** FALSO'
IMAGE = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jf1sAAAAASUVORK5CYII='


def stream_client(client):
    result = Obj(status='completed', output_text=TEXT,
                 usage=Obj(total_tokens=42, input_tokens=30, output_tokens=12))
    events = [Obj(type='response.output_text.delta', delta=TEXT[:25]),
              Obj(type='response.output_text.delta', delta=TEXT[25:]),
              Obj(type='response.completed', response=result)]
    client.responses.create.return_value.__enter__.return_value = iter(events)


class ModeTests(unittest.TestCase):
    @patch('src.services.openai_services.client')
    def test_image_only_prompt_passes_multimodal_content_on_both_transports(self, provider):
        for accept in ('application/json', 'text/event-stream'):
            with self.subTest(accept=accept):
                stream_client(provider)
                client, controller = test_streaming.StreamingTests().criar_cliente()
                res = client.post('/mensagem', json={'prompt': '', 'conversa_id': 'c', 'images': [IMAGE]},
                                  headers={'Accept': accept})
                self.assertEqual(res.status_code, 200)
                res.get_data()
                content = provider.responses.create.call_args.kwargs['input'][-1]['content']
                self.assertEqual(content, [{'type': 'input_text', 'text': IMAGE_ONLY_PROMPT},
                                           {'type': 'input_image', 'image_url': IMAGE, 'detail': 'high'}])
                self.assertEqual(controller.chat_model.save_mensagem.call_args.args[2], IMAGE_ONLY_PROMPT)

    def test_invalid_images_are_rejected_before_quota(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        for images in ([IMAGE] * 4, [IMAGE.replace('image/png', 'image/jpeg')], ['https://example.org/image.png']):
            res = client.post('/mensagem', json={'prompt': 'Verifique isto', 'conversa_id': 'c', 'images': images})
            self.assertEqual(res.status_code, 400)
            self.assertEqual(json_response(res)['code'], 'invalid_images')
        controller.user_model.verificar_e_incrementar_uso.assert_not_called()

    @patch('src.services.openai_services.client')
    @patch('src.services.analysis_service._structured')
    def test_experimental_passes_image_observations_to_extraction(self, extract, provider):
        observations = 'A imagem menciona a eleição de 2026.'
        provider.responses.create.return_value = Obj(status='completed', output_text=observations,
                                                      usage=Obj(total_tokens=42, input_tokens=30, output_tokens=12))
        extract.return_value = Extraction(kind='NEEDS_CONTEXT', claims=[], omitted_material=False,
                                          decomposition_complete=True)
        with patch('src.services.analysis_service.ZoneInfo', side_effect=ZoneInfoNotFoundError), \
             patch('src.services.analysis_service.datetime', wraps=datetime) as clock:
            utc_now = datetime(2026, 11, 19, 1, tzinfo=timezone.utc)
            clock.now.side_effect = utc_now.astimezone
            result = list(transmitir_resposta('Isso é verdade?', mode='experimental', images=[IMAGE]))[-1]
        self.assertEqual(provider.responses.create.call_args.kwargs['input'][0]['content'][1]['image_url'], IMAGE)
        self.assertEqual(extract.call_args.args[-1]['image_observations'], observations)
        self.assertEqual(extract.call_args.args[-1]['input'], 'Isso é verdade?')
        self.assertEqual(extract.call_args.args[-1]['today'], '2026-11-18')
        assert result['type'] == 'result'
        self.assertEqual(result['tokens'], 42)

    @patch('src.services.openai_services.client')
    @patch('src.services.openai_services.analyze')
    def test_default_uses_one_original_prompt_call_without_experimental_pipeline(self, analyze, client):
        stream_client(client)
        calls = []
        ledger = UsageLedger(calls.append)
        events = list(transmitir_resposta('Uma afirmação factual.', ledger=ledger))
        analyze.assert_not_called()
        self.assertEqual(client.responses.create.call_count, 1)
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs['input'][0], {'role': 'system', 'content': SYSTEM_PROMPT})
        self.assertTrue(kwargs['stream'])
        self.assertNotIn('text', kwargs)
        self.assertFalse(kwargs['store'])
        result = events[-1]
        assert result['type'] == 'result'
        self.assertEqual(result['veredito']['mode'], 'standard')
        self.assertEqual(result['veredito']['metrics'], [])
        self.assertIsNone(result['audit'])
        self.assertEqual(calls, [42])
        self.assertNotIn('Veredicto', ''.join(e['text'] for e in events if e['type'] == 'delta'))

    @patch('src.services.openai_services.client')
    def test_fast_mode_prioritizes_titles_in_colloquial_world_cup_question(self, client):
        stream_client(client)
        question = 'os EUA tem copa do mundo?'
        list(transmitir_resposta(question))
        system, user = client.responses.create.call_args.kwargs['input']
        self.assertEqual(user['content'], question)
        self.assertIn('Pesquise títulos da seleção', system['content'])
        self.assertIn('sede como assunto principal quando', system['content'])

    @patch('src.services.openai_services.client')
    @patch('src.services.openai_services.analyze')
    def test_only_explicit_experimental_mode_uses_pipeline(self, analyze, client):
        analyze.return_value = iter([{'type': 'result', 'text': 'Resultado', 'tokens': 0,
            'veredito': {'version': 2, 'metrics': []}, 'audit': {'method_version': 'test'}}])
        result = list(transmitir_resposta('Afirmação', mode='experimental'))[-1]
        analyze.assert_called_once()
        client.responses.create.assert_not_called()
        assert result['type'] == 'result'
        self.assertEqual(result['veredito']['mode'], 'experimental')

    @patch('src.services.openai_services.client')
    def test_default_json_and_sse_preserve_mode_and_legacy_verdict(self, provider):
        for accept in ('application/json', 'text/event-stream'):
            with self.subTest(accept=accept):
                stream_client(provider)
                client, controller = test_streaming.StreamingTests().criar_cliente()
                res = client.post('/mensagem', json={'prompt': 'Uma afirmação factual.', 'conversa_id': 'c'},
                                  headers={'Accept': accept})
                data = json_response(res) if accept == 'application/json' else json.loads(res.text.strip().split('\n\n')[-1].removeprefix('data: '))
                self.assertEqual(data['veredito']['mode'], 'standard')
                self.assertEqual(data['veredito']['metrics'], [])
                self.assertEqual(data['veredito']['code'], 'FALSO')
                saved = controller.chat_model.save_mensagem.call_args
                self.assertEqual(saved.args[4]['mode'], 'standard')
                self.assertIsNone(saved.kwargs['audit'])

    def test_invalid_modes_are_rejected_before_quota_or_provider(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        for mode in ('', 'TRUE', True, None, {}, ['experimental']):
            res = client.post('/mensagem', json={'prompt': 'Uma afirmação.', 'conversa_id': 'c', 'mode': mode})
            self.assertEqual(res.status_code, 400)
        controller.user_model.verificar_e_incrementar_uso.assert_not_called()

    @patch('src.services.openai_services.analyze')
    def test_endpoint_requires_explicit_opt_in_and_saves_experimental_mode(self, analyze):
        analyze.return_value = iter([{'type': 'result', 'text': 'Conclusão experimental', 'tokens': 0,
            'veredito': {'version': 2, 'code': 'INCONCLUSIVE', 'metrics': []},
            'audit': {'method_version': 'test'}}])
        client, controller = test_streaming.StreamingTests().criar_cliente()
        res = client.post('/mensagem', json={'prompt': 'Uma afirmação factual.', 'conversa_id': 'c',
                                           'mode': 'experimental'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json_response(res)['veredito']['mode'], 'experimental')
        self.assertEqual(controller.chat_model.save_mensagem.call_args.kwargs['audit']['method_version'], 'test')
        analyze.assert_called_once()

    def test_standard_history_does_not_turn_into_experimental_or_unknown_version(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        controller.chat_model.get_mensagens_por_conversa.return_value = [dict(prompt='p', resposta=TEXT,
            veredito={'version': 1, 'code': 'FALSO', 'metrics': [], 'mode': 'standard'})]
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context('/'):
            result = json_response(controller.get_mensagens_por_conversa('c')[0])
        self.assertEqual(result['mensagens'][0]['veredito']['mode'], 'standard')


if __name__ == '__main__':
    unittest.main()
