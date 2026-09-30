from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run AI Software Operations Studio MCP server on stdio (set STRIPE_INSTALLER_USER)"

    def handle(self, *args, **options):
        from apps.mcp_server.server import run_stdio_server

        self.stdout.write("AI Software Operations Studio MCP server starting on stdio…")
        run_stdio_server()
