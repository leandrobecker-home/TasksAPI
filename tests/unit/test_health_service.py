"""Unit tests for the health check service (RF14)."""

from pathlib import Path

from sqlmodel import Session

from app.db import create_db_engine
from app.services.health import check_database


def test_database_is_healthy_when_it_answers(session: Session) -> None:
    assert check_database(session) is True


def test_database_is_unhealthy_when_it_cannot_be_opened(tmp_path: Path) -> None:
    """SQLite cannot create a file inside a directory that does not exist."""
    unreachable = tmp_path / "missing-directory" / "tasks.db"
    engine = create_db_engine(f"sqlite:///{unreachable}")

    with Session(engine) as broken_session:
        healthy = check_database(broken_session)

    engine.dispose()
    assert healthy is False
