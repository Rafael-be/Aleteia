"""Operational failures must never masquerade as fact-checking decisions."""
import json
import unittest
from unittest.mock import patch
import httpx
from openai import AuthenticationError
from src.services.analysis_errors import operational_error
import test_streaming
from test_streaming import json_response


class OperationalErrorTests(unittest.TestCase):
    def auth_error(self):
        return AuthenticationError('secret credential and user content',
            response=httpx.Response(401, request=httpx.Request('POST', 'https://api.openai.com/v1/responses')),
            body={'error': {'code': 'invalid_api_key', 'message': 'secret credential'}})

    def test_upstream_auth_failure_does_not_expose_secret(self):
        error = operational_error(self.auth_error())
        self.assertEqual(error.code, 'provider_authentication_failed')
        self.assertNotIn('secret', error.message)

    def test_json_reports_configuration_failure_without_verdict(self):
        client, _ = test_streaming.StreamingTests().criar_cliente()
        with patch('src.services.openai_services.client.responses.create', side_effect=self.auth_error()):
            result = client.post('/mensagem', json={'prompt': 'A água ferve a 100 graus ao nível do mar.', 'conversa_id': 'c'})
        self.assertEqual(result.status_code, 502)
        data = json_response(result)
        self.assertEqual(data['code'], 'provider_authentication_failed')
        self.assertNotIn('veredito', data)
        self.assertNotIn('secret', result.text)

    def test_stream_reports_failure_without_inventing_legacy_analysis(self):
        client, controller = test_streaming.StreamingTests().criar_cliente()
        with patch('src.services.openai_services.client.responses.create', side_effect=self.auth_error()):
            result = client.post('/mensagem', json={'prompt': 'A água ferve a 100 graus ao nível do mar.', 'conversa_id': 'c'},
                                 headers={'Accept': 'text/event-stream'})
            frames = [json.loads(f.removeprefix('data: ')) for f in result.text.strip().split('\n\n')]
        self.assertEqual(frames[-1]['type'], 'error')
        self.assertEqual(frames[-1]['code'], 'provider_authentication_failed')
        self.assertNotIn('veredito', frames[-1])
        self.assertFalse(any(f['type'] == 'done' for f in frames))
        controller.chat_model.save_mensagem.assert_not_called()


if __name__ == '__main__':
    unittest.main()
