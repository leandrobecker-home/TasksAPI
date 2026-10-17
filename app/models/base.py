"""Helpers shared by the table models."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current moment as a timezone-aware UTC datetime (RT05)."""
    return datetime.now(UTC)
