"""Data access for the health check (RT02, RT03)."""

from sqlalchemy import text
from sqlmodel import Session


def ping(session: Session) -> None:
    """Run the cheapest possible query; raises if the database is unreachable."""
    session.connection().execute(text("SELECT 1"))
