"""A incorporação permanece restrita às extensões explicitamente autorizadas."""
import os
import unittest
from unittest.mock import patch
from flask import Flask
from src.utils.api import configure_api


class ExtensionHeadersTests(unittest.TestCase):
    def policy(self, ids):
        app = Flask(__name__)
        configure_api(app)
        app.add_url_rule('/chat', view_func=lambda: 'chat')
        with patch.dict(os.environ, {'CHROME_EXTENSION_IDS': ids}):
            return app.test_client().get('/chat').headers['Content-Security-Policy']

    def test_default_denies_external_frames(self):
        self.assertTrue(self.policy('').endswith("frame-ancestors 'self'"))

    def test_only_valid_explicit_extension_origins(self):
        extension_id = 'abcdefghijklmnop' * 2
        policy = self.policy(f' {extension_id},*,https://evil.example,invalid; frame-ancestors *')
        self.assertEqual(policy, "object-src 'none'; base-uri 'self'; frame-ancestors 'self' "
                         f'chrome-extension://{extension_id}')


if __name__ == '__main__':
    unittest.main()
