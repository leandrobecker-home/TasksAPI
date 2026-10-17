"""Unit tests for the pagination types (RF02, RF07)."""

import dataclasses

import pytest
from pydantic import BaseModel

from app.schemas.common import (
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
    Pagination,
    build_page,
)


class Item(BaseModel):
    name: str


def test_defaults_match_the_scope() -> None:
    pagination = Pagination()

    assert (DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE) == (1, 20, 100)
    assert (pagination.page, pagination.page_size) == (1, 20)


@pytest.mark.parametrize(
    ("page", "page_size", "offset"),
    [(1, 20, 0), (2, 20, 20), (3, 20, 40), (1, 100, 0), (5, 10, 40), (2, 1, 1)],
)
def test_offset_skips_the_previous_pages(
    page: int, page_size: int, offset: int
) -> None:
    pagination = Pagination(page=page, page_size=page_size)

    assert pagination.offset == offset
    assert pagination.limit == page_size


def test_pagination_is_immutable() -> None:
    pagination = Pagination()

    with pytest.raises(dataclasses.FrozenInstanceError):
        pagination.page = 2  # type: ignore[misc]


def test_page_has_exactly_the_members_of_the_listing_format() -> None:
    page = build_page([Item(name="a")], Pagination(page=2, page_size=10), total=11)

    assert page.model_dump() == {
        "items": [{"name": "a"}],
        "page": 2,
        "page_size": 10,
        "total": 11,
    }


def test_empty_listing_has_no_items_and_zero_total() -> None:
    no_items: list[Item] = []
    page = build_page(no_items, Pagination(), total=0)

    assert page.model_dump() == {"items": [], "page": 1, "page_size": 20, "total": 0}


def test_build_page_accepts_any_sequence() -> None:
    page = build_page((Item(name="a"), Item(name="b")), Pagination(), total=2)

    assert [item.name for item in page.items] == ["a", "b"]


def test_page_is_generic_over_its_items() -> None:
    page = Page[Item].model_validate(
        {"items": [{"name": "a"}], "page": 1, "page_size": 20, "total": 1}
    )

    assert isinstance(page.items[0], Item)
    with pytest.raises(ValueError, match="name"):
        Page[Item].model_validate(
            {"items": [{"nome": "a"}], "page": 1, "page_size": 20, "total": 1}
        )
