"""Response schema of the health check (RF14)."""

from typing import Literal

from pydantic import BaseModel

HealthState = Literal["ok", "error"]


class HealthResponse(BaseModel):
    """Overall status and the status of the database connection."""

    status: HealthState
    database: HealthState
