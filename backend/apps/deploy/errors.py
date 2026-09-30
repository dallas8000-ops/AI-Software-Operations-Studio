"""User-facing errors for setup/deploy runs."""

from rest_framework import status
from rest_framework.response import Response


def workspace_missing_response(exc: Exception) -> Response:
    """Setup reads and writes the app's folder on disk; the hosted Studio can't see a PC's C:\\ drive.

    Previously this surfaced as an unhandled 500, which the UI rendered as a
    misleading 'Backend error on port 8000' hint.
    """
    return Response(
        {
            "error": (
                f"{exc} Full setup works on the app's folder on disk, so it must run from the "
                "Studio on the computer that has that folder."
            ),
            "code": "workspace_missing",
        },
        status=status.HTTP_409_CONFLICT,
    )
