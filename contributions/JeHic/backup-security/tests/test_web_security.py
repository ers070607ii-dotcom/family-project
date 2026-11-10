"""Runs without importing Flask or touching the real database."""
from datetime import timedelta
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hardening = load_module("web_security", ROOT / "security" / "web_security.py")
patcher = load_module("apply_security_phase1", ROOT / "scripts" / "apply_security_phase1.py")


class FakeApp:
    def __init__(self):
        self.config = {}
        self.secret_key = None
        self.after_request_callback = None

    def after_request(self, callback):
        self.after_request_callback = callback
        return callback


class ConfigurationTests(unittest.TestCase):
    def test_missing_secret_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                hardening.configure_security(FakeApp())

    def test_short_secret_rejected(self):
        with patch.dict(os.environ, {"SECRET_KEY": "too-short"}, clear=True):
            with self.assertRaises(RuntimeError):
                hardening.configure_security(FakeApp())

    def test_secure_defaults_for_local_dev(self):
        with patch.dict(os.environ, {"SECRET_KEY": "a" * 64}, clear=True):
            app = FakeApp()
            hardening.configure_security(app)
        self.assertEqual(app.secret_key, "a" * 64)
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertFalse(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(app.config["PERMANENT_SESSION_LIFETIME"], timedelta(hours=8))
        self.assertIsNotNone(app.after_request_callback)

    def test_https_cookie_flag(self):
        with patch.dict(os.environ, {"SECRET_KEY": "b" * 64, "COOKIE_SECURE": "1"}, clear=True):
            app = FakeApp()
            hardening.configure_security(app)
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])


class PatcherTests(unittest.TestCase):
    def test_exact_patch_and_idempotence(self):
        before = '\n'.join((
            patcher.OLD_IMPORT,
            'app = Flask(__name__)',
            patcher.OLD_SECRET,
            'def register():',
            patcher.OLD_REGISTER,
            'def login():',
            patcher.OLD_LOGIN,
            'if __name__ == "__main__":',
            '    ' + patcher.OLD_DEBUG,
        ))
        once = patcher.patch_text(before)
        twice = patcher.patch_text(once)
        self.assertEqual(once, twice)
        self.assertIn(patcher.NEW_SECRET, once)
        self.assertIn(patcher.NEW_DEBUG, once)
        self.assertIn(patcher.NEW_IMPORT, once)
        self.assertIn(patcher.NEW_LOGIN, once)
        self.assertIn(patcher.NEW_REGISTER, once)
        self.assertNotIn(patcher.OLD_SECRET, once)

    def test_unexpected_source_rejected(self):
        with self.assertRaises(RuntimeError):
            patcher.patch_text("# unrelated app")


if __name__ == "__main__":
    unittest.main()
