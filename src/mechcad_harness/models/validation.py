from enum import StrEnum

from pydantic import Field

from .common import StateBinding


class ValidationStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class ValidationResult(StateBinding):
    id: str = Field(min_length=1)
    status: ValidationStatus
    summary: str = Field(min_length=1)
