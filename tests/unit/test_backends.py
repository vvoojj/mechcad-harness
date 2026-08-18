import json

import pytest

from mechcad_harness.backends import (
    BackendHealth,
    BackendHealthStatus,
    BackendIdentity,
    BackendProvenance,
    BackendRegistry,
    BackendRegistrationError,
    BackendNotFoundError,
    inspect_distribution,
)
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.models import Component, DesignState
from mechcad_harness.runs import RunController
from mechcad_harness.state import StateManager
from mechcad_harness.tools import ToolResult, ToolResultStatus


class FakeBackend:
    def __init__(self, name, capabilities=(), health=None):
        capabilities = capabilities or ("test.health",)
        self.identity = BackendIdentity(
            name=name,
            adapter_version="0.1.0",
            library_name=name.replace("-", "_"),
            capabilities=tuple(capabilities),
        )
        self._health = health or BackendHealth(backend_name=name, status=BackendHealthStatus.AVAILABLE)

    def healthcheck(self):
        return self._health


def test_backend_identity_and_structured_provenance():
    identity = BackendIdentity(name="py-gearworks", adapter_version="0.1.0", library_name="py_gearworks", capabilities=("gear.geometry.spur",))
    assert identity.library_version is None
    provenance = BackendProvenance(backend_name=identity.name, backend_adapter_version=identity.adapter_version, library_name=identity.library_name)
    assert provenance.model_dump()["backend_name"] == "py-gearworks"
    with pytest.raises(Exception):
        BackendIdentity(name="", adapter_version="0.1.0", library_name="lib", capabilities=("x",))


def test_registry_is_deterministic_and_rejects_duplicates():
    registry = BackendRegistry([FakeBackend("zeta"), FakeBackend("alpha", ("gear.geometry.spur",))])
    assert [item.identity.name for item in registry.list()] == ["alpha", "zeta"]
    assert registry.find_by_capability("gear.geometry.spur")[0].identity.name == "alpha"
    with pytest.raises(BackendRegistrationError):
        BackendRegistry([FakeBackend("alpha"), FakeBackend("alpha")])
    with pytest.raises(BackendNotFoundError):
        registry.get("missing")


def test_health_is_detected_runtime_data_not_identity():
    backend = FakeBackend("missing", health=BackendHealth(backend_name="missing", status=BackendHealthStatus.UNAVAILABLE, message="not installed"))
    original = backend.identity
    assert backend.healthcheck().status is BackendHealthStatus.UNAVAILABLE
    assert backend.identity == original


def test_package_inspection_uses_trusted_distribution_mapping():
    available = inspect_distribution("setuptools")
    assert available.status is BackendHealthStatus.AVAILABLE
    assert available.detected_version
    missing = inspect_distribution("py_gearworks")
    assert missing.status is BackendHealthStatus.UNAVAILABLE
    with pytest.raises(Exception):
        inspect_distribution("arbitrary.module.path")


def test_backend_provenance_is_optional_and_tool_result_serializes():
    result = ToolResult(result_id="TOOLRES-1", call_id="CALL-1", tool_name="tool", tool_version="1.0", project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", bound_revision=1, bound_state_hash="sha256:a", status=ToolResultStatus.SUCCEEDED, input_hash="sha256:i")
    assert "backend_provenance" not in result.model_dump(exclude_none=True)
    result = result.model_copy(update={"backend_provenance": BackendProvenance(backend_name="backend", backend_adapter_version="0.1.0")})
    assert result.model_dump(mode="json")["backend_provenance"]["backend_name"] == "backend"
    with pytest.raises(Exception):
        ToolResult(**result.model_dump(mode="python") | {"backend_provenance": {"backend_name": "backend", "backend_adapter_version": "0.1.0", "object": object()}})


def test_backend_checks_do_not_change_canonical_revision(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Part")]))
    revision = tmp_path / "projects/PRJ-1/revisions/REV-000001.json"
    before = revision.read_bytes()
    registry = BackendRegistry([FakeBackend("alpha")])
    registry.get("alpha").healthcheck()
    inspect_distribution("setuptools")
    assert revision.read_bytes() == before
