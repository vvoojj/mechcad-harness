"""M9-1: FreeCAD runtime preflight + live generic backend verification.

This test enters through the EXISTING production boundary
``CadGenerationService`` -> ``FreeCADBackend`` and proves the generic
FreeCAD backend executes on a real FreeCAD runtime, persists FCStd/STEP
through ``ArtifactStore``, and passes fresh-reload verification.

No new CAD primitives, no domain (Yagi/AZ/EL/gear/imported) semantics, and
no DesignState/ChangeProposal/ChangeSet mutation are introduced or required.

The live tests are runtime-marked: they run only when FreeCAD is discoverable
through the supported harness override ``MECHCAD_FREECADCMD`` (or on PATH).
"""

import os

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import (
    FreeCADBackend,
    FreeCADBackendError,
    discover_freecad,
    freecad_program_artifact_id,
)
from mechcad_harness.cad_manifest import build_program_manifest
from mechcad_harness.cad_program import (
    BasePlateOperation,
    CadPartProgram,
    ThroughHoleOperation,
    cad_program_hash,
)
from mechcad_harness.cad_service import CadGenerationService
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager, state_hash as canonical_state_hash

# Supported harness runtime override. The verification session sets this to the
# real local FreeCAD command runtime. We fall back to the known local candidate
# only so the test can locate a runtime when the env var is unset.
CANDIDATE = r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe"


def _resolved_executable():
    return os.environ.get("MECHCAD_FREECADCMD") or CANDIDATE


FREECAD_AVAILABLE = discover_freecad().available


def generic_mounting_plate_program():
    """Smallest generic deterministic part: base plate + one through hole.

    Contains NO domain/engineering semantics beyond generic CAD primitives.
    """
    return CadPartProgram(
        part_id="M9A1GenericPlate",
        operations=(
            BasePlateOperation(operation_id="base", length_mm=60, width_mm=40, thickness_mm=6),
            ThroughHoleOperation(operation_id="hole1", x_mm=15, y_mm=20, diameter_mm=8),
        ),
    )


# ---------------------------------------------------------------------------
# A / B: discovery contract (no real FreeCAD execution required)
# ---------------------------------------------------------------------------

def test_discovery_finds_configured_runtime(monkeypatch):
    exe = _resolved_executable()
    monkeypatch.setenv("MECHCAD_FREECADCMD", exe)
    discovery = discover_freecad()
    assert discovery.available is True
    assert discovery.executable == exe
    assert discovery.execution_boundary == "bundled FreeCAD command line"


def test_discovery_reports_unavailable_for_nonexistent_config(monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\nonexistent\freecadcmd.exe")
    discovery = discover_freecad()
    assert discovery.available is False
    assert discovery.executable is None


def test_invalid_configured_executable_fails_clearly(monkeypatch, tmp_path):
    # A real, valid executable that is NOT FreeCAD must fail clearly rather
    # than silently producing geometry.
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Windows\System32\cmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M9B", DesignState(id="DES-M9B", revision=1))
    program = generic_mounting_plate_program()
    service = CadGenerationService(manager, FreeCADBackend())
    with pytest.raises(FreeCADBackendError):
        service.generate_program(
            "PRJ-M9B", "RUN-M9B", snapshot.revision, snapshot.state_hash, program, tmp_path
        )


# ---------------------------------------------------------------------------
# C-J: live generic backend path (requires real FreeCAD)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime not configured")
def test_live_backend_compiles_generic_program():
    program = generic_mounting_plate_program()
    script = FreeCADBackend.compile_program(program, "C:/tmp/plate.FCStd", "C:/tmp/plate.step")
    assert "makeBox" in script
    assert "makeCylinder" in script
    assert "doc.saveAs" in script
    assert "Part.export" in script


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime not configured")
def test_live_generic_part_persists_and_reloads(tmp_path):
    exe = _resolved_executable()
    os.environ["MECHCAD_FREECADCMD"] = exe

    program = generic_mounting_plate_program()
    expected_volume = 60 * 40 * 6 - (3.141592653589793 * (8 / 2) ** 2 * 6)

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M9A1", DesignState(id="DES-M9A1", revision=1))
    state_hash_before = snapshot.state_hash

    service = CadGenerationService(manager, FreeCADBackend())

    # C/D/E: real backend executes, compiles, and produces FCStd/STEP.
    first = service.generate_program(
        "PRJ-M9A1", "RUN-M9A1", snapshot.revision, snapshot.state_hash, program, tmp_path
    )

    # E: persisted artifact files exist.
    fcstd_path = (tmp_path / first.fcstd.relative_path).resolve()
    step_path = (tmp_path / first.step.relative_path).resolve()
    assert fcstd_path.is_file()
    assert step_path.is_file()
    assert fcstd_path.stat().st_size > 0
    assert step_path.stat().st_size > 0

    # F: ArtifactStore integrity (record + file + size + sha256 recompute).
    store = ArtifactStore(tmp_path, project_id="PRJ-M9A1", run_id="RUN-M9A1")
    fcstd_id = freecad_program_artifact_id(
        "PRJ-M9A1", "RUN-M9A1", snapshot.revision, snapshot.state_hash, program, "FCStd"
    )
    step_id = freecad_program_artifact_id(
        "PRJ-M9A1", "RUN-M9A1", snapshot.revision, snapshot.state_hash, program, "STEP"
    )
    fcstd_artifact = store.existing(fcstd_id)
    step_artifact = store.existing(step_id)
    assert fcstd_artifact is not None
    assert step_artifact is not None
    assert fcstd_artifact.size_bytes == fcstd_path.stat().st_size
    assert step_artifact.size_bytes == step_path.stat().st_size
    assert fcstd_artifact.sha256 == f"sha256:{_sha256(fcstd_path.read_bytes())}"
    assert fcstd_artifact.artifact_type == ArtifactType.FCSTD
    assert step_artifact.artifact_type == ArtifactType.STEP

    # G: fresh-reload verification (separate subprocess, post-generation).
    fcstd_v = first.fcstd_verification
    step_v = first.step_verification
    assert fcstd_v.status == "verified"
    assert fcstd_v.shape_valid is True
    assert fcstd_v.solid_count == 1
    assert (fcstd_v.x_length_mm, fcstd_v.y_length_mm, fcstd_v.z_length_mm) == pytest.approx((60, 40, 6), abs=1e-6)
    assert fcstd_v.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert step_v.status == "verified"
    assert step_v.shape_valid is True
    assert step_v.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    # Through-hole probe must report the removed material (hole present).
    assert fcstd_v.feature_probes.get("hole_hole1") is True

    # H: no DesignState mutation.
    reloaded = manager.load_revision("PRJ-M9A1", snapshot.revision)
    assert canonical_state_hash(reloaded) == state_hash_before

    # I: no ChangeProposal / ChangeSet created anywhere in the workspace.
    offending = [
        str(p)
        for p in tmp_path.rglob("*")
        if "proposal" in p.name.lower() or "changeset" in p.name.lower()
    ]
    assert offending == []

    # J: fixture is purely generic (no domain semantics).
    assert all(
        isinstance(op, (BasePlateOperation, ThroughHoleOperation)) for op in program.operations
    )
    manifest = build_program_manifest(program)
    assert {entry.operation_kind for entry in manifest.operations} == {"base_plate", "through_hole"}


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime not configured")
def test_live_generic_part_is_deterministic_and_reloadable(tmp_path):
    exe = _resolved_executable()
    os.environ["MECHCAD_FREECADCMD"] = exe

    program = generic_mounting_plate_program()
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M9A1D", DesignState(id="DES-M9A1D", revision=1))
    service = CadGenerationService(manager, FreeCADBackend())

    first = service.generate_program(
        "PRJ-M9A1D", "RUN-M9A1D", snapshot.revision, snapshot.state_hash, program, tmp_path
    )
    # Second call hits the persisted ArtifactStore path (proves persistence +
    # fresh reload), not in-memory caching of the result object.
    second = service.generate_program(
        "PRJ-M9A1D", "RUN-M9A1D", snapshot.revision, snapshot.state_hash, program, tmp_path
    )

    # Semantic/deterministic identity (NOT binary byte identity).
    assert first.fcstd.artifact_id == second.fcstd.artifact_id
    assert first.step.artifact_id == second.step.artifact_id
    assert first.fcstd.input_hash == cad_program_hash(program)
    assert second.fcstd.input_hash == cad_program_hash(program)
    assert first.fcstd_verification.volume_mm3 == pytest.approx(second.fcstd_verification.volume_mm3, rel=1e-9)
    assert first.fcstd.artifact_id.startswith("FC-M9A1GenericPlate-")


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime not configured")
def test_live_backend_runtime_identity():
    backend = FreeCADBackend()
    provenance = backend.provenance()
    assert provenance.backend_name == "freecad"
    assert provenance.backend_adapter_version == "mechcad-freecad@2.1"
    assert provenance.library_name == "FreeCAD"
    assert provenance.library_version and provenance.library_version != "unknown"
    assert provenance.library_source is not None


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
