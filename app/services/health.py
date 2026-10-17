"""Health check business logic (RF14)."""

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from app.repositories import health as health_repository


def check_database(session: Session) -> bool:
    """Return whether the database answers a trivial query."""
    try:
        health_repository.ping(session)
    except SQLAlchemyError:
        return False
    return True
