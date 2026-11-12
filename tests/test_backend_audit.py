"""Offline regressions for the backend audit; no external credentials/cost."""
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask, g
from pymongo.errors import AutoReconnect
from src.controller.chatController import ChatController
from src.controller.authController import AuthController
from src.models.chatModel import ChatModel
from src.database import MongoDatabaseProvider
from src.services.markdown_service import renderizar_markdown
from src.utils.api import configure_api
from src.utils.auth import obter_uid_do_token_firebase
import test_streaming
from test_streaming import TEXTO


class AuditTests(unittest.TestCase):
    def client(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        configure_api(client.application)
        return client, controller

    def test_invalid_payloads_never_reserve_or_call_ai(self):
        client, controller = self.client()
        with patch('src.controller.chatController.obter_resposta') as ai:
            for payload in [[], 1, None, {}, {'prompt': [], 'conversa_id': 'c'},
                            {'prompt': 'x', 'conversa_id': 1},
                            {'prompt': 'x'*12001, 'conversa_id': 'c'},
                            {'prompt': 'x', 'conversa_id': 'c'*129}]:
                with self.subTest(payload_type=type(payload).__name__):
                    response = client.post('/mensagem', json=payload)
                    self.assertEqual(response.status_code, 400)
            ai.assert_not_called()
            controller.user_model.verificar_e_incrementar_uso.assert_not_called()

    def test_provision_before_reservation_and_failure_refund(self):
        client, controller = self.client()
        reservation = {'reservation_id': 'r', 'reservation_day': '2026-11-02'}
        controller.user_model.verificar_e_incrementar_uso.return_value = (True, reservation)
        with patch('src.controller.chatController.obter_resposta', side_effect=RuntimeError('secret')):
            response = client.post('/mensagem', json={'prompt':'x', 'conversa_id':'c'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('secret', response.text)
        controller.user_model.sincronizar_usuario_firebase.assert_called_once()
        controller.user_model.finalizar_reserva.assert_called_once_with('uid', reservation, False)

    def test_stream_disconnect_refunds_and_closes(self):
        client, controller = self.client()
        def events(*args):
            yield {'type':'delta', 'text':'partial'}
            yield {'type':'result', 'text':TEXTO, 'tokens':42}
        with patch('src.controller.chatController.transmitir_resposta', side_effect=events):
            response = client.post('/mensagem', json={'prompt':'x','conversa_id':'c'}, headers={'Accept':'text/event-stream'}, buffered=False)
            next(iter(response.response))
            response.close()
        self.assertFalse(controller.user_model.finalizar_reserva.call_args.args[-1])

    def test_missing_profile_is_not_quota(self):
        client, controller = self.client()
        controller.user_model.verificar_e_incrementar_uso.return_value = (False, None)
        self.assertEqual(client.post('/mensagem', json={'prompt':'x','conversa_id':'c'}).status_code, 503)

    def test_syntax_email_needs_no_external_service(self):
        app = Flask(__name__)
        controller = AuthController(MagicMock())
        app.add_url_rule('/email', view_func=controller.validar_email, methods=['POST'])
        with app.test_client() as client:
            self.assertFalse(client.post('/email', json={'email':'user@example.org'}).json['checagem_disponivel'])
            for payload in [[], {'email':[]}, {'email':'bad'}, {'email':'a@b\n.c'}]:
                self.assertEqual(client.post('/email', json=payload).status_code, 400)

    def test_mongo_client_reused_without_ping(self):
        with patch('src.database.MongoClient') as constructor:
            provider = MongoDatabaseProvider('mongodb://localhost', 'test')
            provider.get_database()
            provider.get_database()
            constructor.assert_called_once()
            constructor.return_value.admin.command.assert_not_called()

    def test_token_claims_verified_once_and_anonymous_denied(self):
        app = Flask(__name__)
        with app.test_request_context(headers={'Authorization':'Bearer test'}):
            with patch('src.utils.auth.firebase_auth.verify_id_token', return_value={'uid':'a','email_verified':True}) as verify:
                self.assertEqual(obter_uid_do_token_firebase(), ('a', True))
                obter_uid_do_token_firebase()
                verify.assert_called_once()
        with app.test_request_context():
            self.assertEqual(ChatController._usuario_autorizado()[1][1], 401)

    def test_mongo_failure_is_json_and_secret_free(self):
        app = Flask(__name__)
        configure_api(app)
        @app.route('/api/test')
        def fail():
            raise AutoReconnect('mongodb://user:secret@internal')
        response = app.test_client().get('/api/test')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', response.text)
        self.assertIn('request_id', response.json)
        self.assertEqual(app.test_client().get('/api/test?limit=no').status_code, 400)

    def test_uid_isolation_in_history_and_delete(self):
        db = MagicMock()
        model = ChatModel(db)
        model.collection = MagicMock()
        model.db_available = True
        model.get_mensagens_por_conversa('user-a', 'shared-id')
        self.assertEqual(model.collection.find.call_args.args[0], {'firebase_uid':'user-a', 'conversa_id':'shared-id'})
        model.apagar_conversa('user-b', 'shared-id')
        model.collection.delete_many.assert_called_once_with({'firebase_uid':'user-b', 'conversa_id':'shared-id'})

    def test_hostile_markdown(self):
        for text in ['<script>alert(1)</script>', '<svg onload=alert(1)>',
                     '[x](javascript:alert(1))', '[x](vbscript:alert(1))',
                     '[x](data:text/html;base64,PHNjcmlwdD4=)', '![x](data:image/png;base64,eA==)', '[x](https://[invalid)']:
            html = renderizar_markdown(text)
            self.assertNotIn('<script', html)
            self.assertNotIn('<svg', html)
            for scheme in ['javascript:', 'vbscript:', 'data:']:
                self.assertNotIn('href="'+scheme, html)
                self.assertNotIn('src="'+scheme, html)

    def test_body_limit_and_pagination(self):
        app = Flask(__name__)
        configure_api(app)
        @app.route('/api/body', methods=['POST'])
        def body():
            return {'data': __import__('flask').request.get_json()}
        client = app.test_client()
        self.assertEqual(client.post('/api/body', json={'x':'x'*65536}).status_code, 413)
        for query in ['limit=0', 'limit=101', 'offset=-1', 'offset=10001', 'offset='+'1'*5000, 'q='+'x'*201]:
            self.assertEqual(client.post('/api/body?'+query, json={}).status_code, 400)

    def test_application_pages_and_anonymous_api(self):
        import firebase_admin
        import importlib
        with patch.dict(firebase_admin._apps, {'audit-test': object()}):
            application = importlib.import_module('app').app
        client = application.test_client()
        for page in ['/', '/chat', '/login', '/cadastro']:
            self.assertEqual(client.get(page).status_code, 200)
        for method, path in [('get','/api/chat/conversas'), ('get','/api/chat/pesquisar?q=x'),
                             ('get','/api/chat/conversas/c'), ('delete','/api/chat/conversas/c'),
                             ('post','/api/chat/mensagem'), ('post','/api/auth/sincronizar')]:
            response = getattr(client, method)(path)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json['code'], 'unauthorized')


if __name__ == '__main__':
    unittest.main()
