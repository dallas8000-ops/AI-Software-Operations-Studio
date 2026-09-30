from django.test import SimpleTestCase

from config.settings import database_config_error

PG = "django.db.backends.postgresql"
SQLITE = "django.db.backends.sqlite3"


class DatabaseConfigGuardTests(SimpleTestCase):
    def test_blank_database_url_is_rejected(self):
        err = database_config_error({"DATABASE_URL": "   "}, SQLITE, on_railway=True, running_tests=False)
        self.assertIn("set but empty", err)

    def test_blank_database_url_rejected_even_off_railway(self):
        err = database_config_error({"DATABASE_URL": ""}, SQLITE, on_railway=False, running_tests=False)
        self.assertIsNotNone(err)

    def test_sqlite_on_railway_is_rejected(self):
        err = database_config_error({}, SQLITE, on_railway=True, running_tests=False)
        self.assertIn("SQLite", err)

    def test_postgres_on_railway_is_allowed(self):
        env = {"DATABASE_URL": "postgresql://u:p@db.railway.internal:5432/railway"}
        self.assertIsNone(database_config_error(env, PG, on_railway=True, running_tests=False))

    def test_local_sqlite_without_database_url_is_allowed(self):
        self.assertIsNone(database_config_error({}, SQLITE, on_railway=False, running_tests=False))

    def test_tests_are_never_blocked(self):
        self.assertIsNone(database_config_error({"DATABASE_URL": ""}, SQLITE, on_railway=True, running_tests=True))
