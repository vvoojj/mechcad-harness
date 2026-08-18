from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from mechcad_harness.models import Model


class OperationType(StrEnum):
    ADD = "add"
    REPLACE = "replace"
    REMOVE = "remove"


class ChangeOperation(Model):
    operation: OperationType
    path: str = Field(min_length=2)
    value: Any = None
    expected: Any = None

    @model_validator(mode="after")
    def validate_value(self) -> "ChangeOperation":
        if self.operation is OperationType.ADD and self.value is None:
            raise ValueError("add operations require value")
        if self.operation is OperationType.REPLACE and self.value is None:
            raise ValueError("replace operations require value")
        if self.operation is OperationType.REMOVE and self.value is not None:
            raise ValueError("remove operations cannot include value")
        return self
