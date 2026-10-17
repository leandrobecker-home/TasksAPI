"""RFC 9457 Problem Details schema (RT14)."""

from pydantic import BaseModel

PROBLEM_MEDIA_TYPE = "application/problem+json"


class ProblemDetails(BaseModel):
    """Body of every error response."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
