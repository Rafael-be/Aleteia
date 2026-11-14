import os
import unittest
from unittest.mock import patch

from flask import Flask
from src.utils.observability import _scrub, configure_sentry


class ObservabilityTests(unittest.TestCase):
    def test_sentry_is_disabled_without_dsn(self):
        app = Flask(__name__)
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(configure_sentry(app))

    def test_sensitive_event_fields_are_filtered(self):
        event = _scrub({"prompt": "privado", "token": "segredo", "nested": {"password": "x"}})
        self.assertEqual(event["prompt"], "[Filtered]")
        self.assertEqual(event["token"], "[Filtered]")
        self.assertEqual(event["nested"]["password"], "[Filtered]")


if __name__ == "__main__":
    unittest.main()
