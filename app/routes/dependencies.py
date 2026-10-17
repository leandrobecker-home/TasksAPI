"""FastAPI dependencies shared by the routers."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlmodel import Session

from app.schemas.common import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Pagination,
)


def get_session(request: Request) -> Iterator[Session]:
    """Open a database session on the application's engine for one request."""
    with Session(request.app.state.engine) as session:
        yield session


def get_pagination(
    page: Annotated[int, Query(ge=1, description="Page number, starting at 1.")] = (
        DEFAULT_PAGE
    ),
    page_size: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Number of items per page."),
    ] = DEFAULT_PAGE_SIZE,
) -> Pagination:
    """Read and validate the ``page`` and ``page_size`` query parameters."""
    return Pagination(page=page, page_size=page_size)


SessionDep = Annotated[Session, Depends(get_session)]
PaginationDep = Annotated[Pagination, Depends(get_pagination)]
