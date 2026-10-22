"""Stable credential evidence and secure entry contracts. No database access."""
import contextlib
import io
import json
import os
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from scripts import management_preview_account as account


class StableAccountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_ai_copilot.settings")
        cls.password = secrets.token_urlsafe(24)
        cls.password_hash = make_password(cls.password, hasher="pbkdf2_sha256")

    def test_hash_only_roundtrip_and_tamper_rejection(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "uat"
            with patch("scripts.management_preview.protect", side_effect=lambda path: path.mkdir()):
                account.write_stable(self.password_hash, directory=directory)
            value = account.read_stable(directory=directory)
            self.assertEqual(value["username"], "manager")
            self.assertEqual(value["password_hash"], self.password_hash)
            self.assertNotIn(self.password, (directory / "manager.json").read_text())
            envelope = json.loads((directory / "manager.json").read_text())
            envelope["account"]["is_superuser"] = True
            (directory / "manager.json").write_text(json.dumps(envelope))
            with self.assertRaises(RuntimeError):
                account.read_stable(directory=directory)
            with self.assertRaises(RuntimeError):
                account.write_stable(self.password_hash, directory=directory)

    def test_missing_evidence_not_silently_recreated(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "missing"
            self.assertIsNone(account.read_stable(required=False, directory=directory))
            with self.assertRaises(FileNotFoundError):
                account.read_stable(directory=directory)

    def test_unusable_hash_rejected_before_storage(self):
        value = dict(version=1, scope="MANAGEMENT_TEST_PREVIEW_V1", username="manager", password_hash="!unusable",
                     is_active=True, is_staff=True, is_superuser=False)
        with self.assertRaises((RuntimeError, ValueError, AssertionError)):
            account.validate_stable(value)

    def test_reset_refuses_noninteractive_entry(self):
        with patch("sys.stdin.isatty", return_value=False), patch("getpass.getpass") as prompt:
            with self.assertRaises(RuntimeError):
                account.prompt_password(None)
            prompt.assert_not_called()

    def test_secure_prompt_confirms_and_validates_without_output(self):
        output = io.StringIO()
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", side_effect=[self.password]*2) as prompt, \
             patch("django.contrib.auth.password_validation.validate_password") as validate, contextlib.redirect_stdout(output):
            self.assertEqual(account.prompt_password(None), self.password)
            self.assertEqual(prompt.call_count, 2)
            validate.assert_called_once_with(self.password, user=None)
        self.assertNotIn(self.password, output.getvalue())

    def test_mismatched_confirmation_rejected(self):
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", side_effect=[self.password, "different"]), \
             patch("django.contrib.auth.password_validation.validate_password") as validate:
            with self.assertRaises(RuntimeError):
                account.prompt_password(None)
            validate.assert_not_called()

    def test_legacy_local_recovery_and_hash_only_login_prompt(self):
        self.assertEqual(account.login_credentials({"username": "manager", "password": self.password}),
                         {"username": "manager", "password": self.password})
        with patch("sys.stdin.isatty", return_value=False), self.assertRaises(RuntimeError):
            account.login_credentials({"username": "manager"})


if __name__ == "__main__":
    unittest.main()
