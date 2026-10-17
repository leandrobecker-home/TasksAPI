"""FastAPI dependencies shared by the routers."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session


def get_session(request: Request) -> Iterator[Session]:
    """Open a database session on the application's engine for one request."""
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
