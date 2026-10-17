"""Unit tests for the domain errors and the Problem Details schema (RT14)."""

import pytest
from pydantic import ValidationError

from app.errors import ConflictError, DomainError, InvalidReferenceError, NotFoundError
from app.schemas.problem import PROBLEM_MEDIA_TYPE, ProblemDetails


@pytest.mark.parametrize(
    ("error_class", "status_code", "title"),
    [
        (NotFoundError, 404, "Not Found"),
        (ConflictError, 409, "Conflict"),
        (InvalidReferenceError, 422, "Validation Error"),
    ],
)
def test_domain_errors_map_to_their_http_status(
    error_class: type[DomainError], status_code: int, title: str
) -> None:
    error = error_class("something went wrong")

    assert isinstance(error, DomainError)
    assert error.status_code == status_code
    assert error.title == title
    assert error.detail == "something went wrong"
    assert str(error) == "something went wrong"


def test_problem_details_defaults_the_type_to_about_blank() -> None:
    problem = ProblemDetails(title="Not Found", status=404, detail="x", instance="/y")

    assert problem.type == "about:blank"


def test_problem_details_requires_every_other_member() -> None:
    with pytest.raises(ValidationError):
        ProblemDetails.model_validate({"title": "Not Found", "status": 404})


def test_problem_media_type_is_rfc_9457() -> None:
    assert PROBLEM_MEDIA_TYPE == "application/problem+json"
