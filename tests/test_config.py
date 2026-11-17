"""Local env conflicts must be visible without overriding production or leaking keys."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from src.config import load_environment


class ConfigTests(unittest.TestCase):
    def test_inherited_values_win_but_conflict_is_logged_without_secrets(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/'.env'
            path.write_text('OPENAI_API_KEY=secret-file\nOPENAI_MODEL=file-model\n')
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'secret-export', 'OPENAI_MODEL': 'export-model'}, clear=True):
                with self.assertLogs('src.config', level='WARNING') as logs:
                    load_environment(path)
                self.assertEqual(os.environ['OPENAI_API_KEY'], 'secret-export')
                self.assertEqual(os.environ['OPENAI_MODEL'], 'export-model')
                output = '\n'.join(logs.output)
                self.assertIn('OPENAI_API_KEY', output)
                self.assertIn('OPENAI_MODEL', output)
                self.assertNotIn('secret-file', output)
                self.assertNotIn('secret-export', output)

    def test_clean_process_reads_file(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/'.env'
            path.write_text('OPENAI_API_KEY=secret-file\nOPENAI_MODEL=file-model\n')
            with patch.dict(os.environ, {}, clear=True):
                load_environment(path)
                self.assertEqual(os.environ['OPENAI_API_KEY'], 'secret-file')
                self.assertEqual(os.environ['OPENAI_MODEL'], 'file-model')
