"""Schemas shared by every listing endpoint (RF02, RF07)."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class Pagination:
    """Which slice of a listing the client asked for."""

    page: int = DEFAULT_PAGE
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        """Number of rows to skip before the requested page."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Maximum number of rows in the requested page."""
        return self.page_size


class Page[ItemT](BaseModel):
    """One page of a listing, with the total number of matching rows."""

    items: list[ItemT]
    page: int
    page_size: int
    total: int


def build_page[ItemT](
    items: Sequence[ItemT], pagination: Pagination, total: int
) -> Page[ItemT]:
    """Wrap ``items`` and the request's pagination into a response page."""
    return Page[ItemT](
        items=list(items),
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
    )
