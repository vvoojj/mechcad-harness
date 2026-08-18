from enum import StrEnum
from typing import Protocol

from pydantic import Field, field_validator

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BackendHealthStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class BackendIdentity(Model):
    name: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    library_name: str = Field(min_length=1)
    library_version: str | None = None
    library_source: str | None = None
    library_revision: str | None = None
    capabilities: tuple[str, ...] = Field(min_length=1)

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("capabilities must be non-empty")
        if len(set(values)) != len(values):
            raise ValueError("capabilities must be unique")
        return values


class BackendProvenance(Model):
    backend_name: str = Field(min_length=1)
    backend_adapter_version: str = Field(min_length=1)
    library_name: str | None = None
    library_version: str | None = None
    library_source: str | None = None
    library_revision: str | None = None


class BackendHealth(Model):
    backend_name: str = Field(min_length=1)
    status: BackendHealthStatus
    detected_version: str | None = None
    message: str | None = None


class EngineeringBackend(Protocol):
    identity: BackendIdentity

    def healthcheck(self) -> BackendHealth:
        ...
