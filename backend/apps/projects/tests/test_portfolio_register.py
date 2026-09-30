from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.projects.models import Project
from apps.stripe_core.portfolio_catalog import HUB_SLUG
from apps.stripe_core.portfolio_register import registrable_entries


@patch.dict("os.environ", {"PORTFOLIO_OWNER_EMAIL": "owner@example.com"})
class PortfolioRegisterTests(APITestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(email="owner@example.com", password="test-pass-123")
        self.other = users.create_user(email="someone@example.com", password="test-pass-123")

    def _list(self, user):
        self.client.force_authenticate(user)
        return self.client.get("/api/v1/projects/?include_portfolio=true", secure=True)

    def test_owner_gets_every_live_portfolio_app(self):
        response = self._list(self.owner)

        self.assertEqual(response.status_code, 200)
        slugs = {row["slug"] for row in response.data}
        expected = {e["projectSlug"] for e in registrable_entries()}
        self.assertEqual(slugs, expected)
        self.assertNotIn(HUB_SLUG, slugs)
        kistie = Project.objects.get(owner=self.owner, slug="kistie-store")
        self.assertEqual(kistie.scan_data["productionUrl"], "https://kistie-store-production.up.railway.app")

    def test_registration_is_idempotent_and_reuses_hand_added_apps(self):
        Project.objects.create(owner=self.owner, name="Kistie Store", slug="kistie-store-1")

        self._list(self.owner)
        self._list(self.owner)

        self.assertFalse(Project.objects.filter(owner=self.owner, slug="kistie-store").exists())
        self.assertEqual(
            Project.objects.filter(owner=self.owner).count(), len(registrable_entries())
        )

    def test_other_users_do_not_receive_portfolio(self):
        response = self._list(self.other)

        self.assertEqual(response.data, [])
