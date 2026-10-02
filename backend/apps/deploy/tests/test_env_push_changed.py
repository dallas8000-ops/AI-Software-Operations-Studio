from unittest import mock
from django.test import SimpleTestCase
from apps.deploy import env_push


class PushOnlyChangedTests(SimpleTestCase):
    def _push(self, existing, incoming):
        calls = []
        with mock.patch.object(env_push, "get_railway_env_vars", return_value=existing), \
             mock.patch.object(env_push, "_railway_gql", side_effect=lambda t, q, v: calls.append(v)):
            result = env_push.push_to_railway("t", "p", "s", incoming, "e")
        return result, calls

    def test_only_changed_keys_are_sent(self):
        existing = {"DATABASE_URL": "postgresql://resolved", "A": "1", "B": "2"}
        result, calls = self._push(existing, {"A": "9"})
        self.assertTrue(result["changed"])
        self.assertEqual(calls[0]["input"]["variables"], {"A": "9"})

    def test_no_write_when_nothing_differs(self):
        result, calls = self._push({"A": "1", "B": "2"}, {"A": "1"})
        self.assertFalse(result["changed"])
        self.assertEqual(calls, [])
