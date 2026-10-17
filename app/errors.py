"""Domain errors raised by the business rules (RT14).

Each error carries the HTTP status it maps to as a plain integer, so the
service layer stays free of web framework imports (RT02). The web layer turns
them into RFC 9457 Problem Details responses.
"""

from typing import ClassVar


class DomainError(Exception):
    """Base class for errors raised when a business rule is violated."""

    status_code: ClassVar[int] = 500
    title: ClassVar[str] = "Internal Server Error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    """The requested resource does not exist."""

    status_code = 404
    title = "Not Found"


class ConflictError(DomainError):
    """The request conflicts with the current state of a resource."""

    status_code = 409
    title = "Conflict"


class InvalidReferenceError(DomainError):
    """The request points to a related resource that does not exist."""

    status_code = 422
    title = "Validation Error"
