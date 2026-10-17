"""Run the API with the configured host, port and log level.

Usage: ``uv run python -m app``. Configuration comes from the ``TASKS_*``
environment variables (see ``.env.example``).
"""

import uvicorn

from app.config import get_settings


def main() -> None:
    """Start the HTTP server using the application settings."""
    settings = get_settings()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
