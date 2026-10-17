"""Base class for request bodies (RN08)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

# Set by the server only. A client that sends them is not told off: they are
# dropped. Any other unknown field is an error.
GENERATED_FIELDS = frozenset({"id", "created_at", "updated_at", "completed_at"})


class InputModel(BaseModel):
    """Request body that ignores generated fields and rejects unknown ones."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_generated_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                key: value for key, value in data.items() if key not in GENERATED_FIELDS
            }
        return data
