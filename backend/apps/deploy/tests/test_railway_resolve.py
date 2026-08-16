from unittest.mock import patch

from django.test import SimpleTestCase

from apps.deploy.railway_resolve import ensure_railway_public_domain, preset_for_project, _name_matches


class RailwayResolveTests(SimpleTestCase):
    def test_preset_for_silverfox_and_kistie(self):
        class P:
            def __init__(self, slug):
                self.slug = slug

        self.assertEqual(preset_for_project(P("silverfox")), "silverfox")
        self.assertEqual(preset_for_project(P("kistie-store")), "kistie-store")
        self.assertEqual(preset_for_project(P("agripay-logistics-ai")), "agripay-logistics-ai")
        self.assertIsNone(preset_for_project(P("elite-fintech-systems")))

    def test_name_matches_ignores_spaces_and_case(self):
        self.assertTrue(_name_matches("SilverFox", "silverfox"))
        self.assertTrue(_name_matches("Kistie Store", "kistie-store"))
        self.assertFalse(_name_matches("Postgres", "SilverFox"))

    @patch("apps.deploy.railway_resolve.update_project_scan_data")
    @patch("apps.deploy.railway_resolve._railway_gql")
    @patch("apps.deploy.railway_resolve._service_public_hosts", return_value=set())
    def test_ensure_public_domain_creates_and_persists_url(
        self, mock_hosts, mock_gql, mock_update
    ):
        mock_gql.return_value = {
            "serviceDomainCreate": {"domain": "ai-memory-engine-production.up.railway.app"}
        }

        url = ensure_railway_public_domain(
            object(), "token", "project-id", "service-id", "environment-id"
        )

        self.assertEqual(url, "https://ai-memory-engine-production.up.railway.app")
        mock_gql.assert_called_once()
        mock_update.assert_called_once_with(
            object=object
        ) if False else mock_update.assert_called_once_with(
            mock_update.call_args.args[0],
            {
                "productionUrl": url,
                "production_url": url,
            },
        )

    @patch("apps.deploy.railway_resolve.update_project_scan_data")
    @patch(
        "apps.deploy.railway_resolve._service_public_hosts",
        return_value={"existing.up.railway.app"},
    )
    def test_ensure_public_domain_reuses_existing_host(self, mock_hosts, mock_update):
        project = object()

        url = ensure_railway_public_domain(project, "token", "project-id", "service-id")

        self.assertEqual(url, "https://existing.up.railway.app")
        mock_update.assert_called_once_with(
            project,
            {"productionUrl": url, "production_url": url},
        )
