import time
from unittest import mock

from django.test import SimpleTestCase

from apps.vault import railway_cli


class RailwayCliTokenTests(SimpleTestCase):
    def test_returns_valid_cli_token(self):
        with mock.patch.object(railway_cli, "_read_cli_token", return_value=("tok", time.time() + 3600)):
            self.assertEqual(railway_cli.railway_cli_token(), "tok")

    def test_missing_login_returns_none(self):
        with mock.patch.object(railway_cli, "_read_cli_token", return_value=("", 0.0)):
            self.assertIsNone(railway_cli.railway_cli_token())

    def test_expired_token_without_cli_is_still_returned(self):
        with mock.patch.object(railway_cli, "_read_cli_token", return_value=("tok", time.time() - 10)), \
             mock.patch.object(railway_cli.shutil, "which", return_value=None):
            self.assertEqual(railway_cli.railway_cli_token(), "tok")

