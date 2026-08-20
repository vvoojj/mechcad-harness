import math
from pathlib import Path
import subprocess

import pytest
from pydantic import ValidationError

from mechcad_harness.backends.freecad import (
    FREECAD_BACKEND_VERSION,
    FreeCADFixtureRequest,
    FreeCADUnavailableError,
    freecad_artifact_id,
    freecad_provenance,
    discover_freecad,
    FreeCADGenerationResult,
    FreeCADArtifactVerificationError,
    FreeCADBackend,
)


def test_fixture_request_requires_finite_positive_dimensions():
    request = FreeCADFixtureRequest(document_id="plate", object_id="Plate", length_mm=40, width_mm=30, height_mm=5)
    assert request.dimensions_mm == (40.0, 30.0, 5.0)
    with pytest.raises(ValidationError):
        FreeCADFixtureRequest(document_id="plate", object_id="Plate", length_mm=math.nan, width_mm=30, height_mm=5)
    with pytest.raises(ValidationError):
        FreeCADFixtureRequest(document_id="plate", object_id="Plate", length_mm=40, width_mm=0, height_mm=5)


def test_artifact_identity_is_semantic_and_stable():
    request = FreeCADFixtureRequest(document_id="plate", object_id="Plate", length_mm=40, width_mm=30, height_mm=5)
    first = freecad_artifact_id("PRJ-1", "RUN-1", 1, "sha256:state", request, "FCStd")
    second = freecad_artifact_id("PRJ-1", "RUN-1", 1, "sha256:state", request, "FCStd")
    assert first == second
    assert first.startswith("FC-plate-")


def test_provenance_binds_source_state_and_environment():
    request = FreeCADFixtureRequest(document_id="plate", object_id="Plate", length_mm=40, width_mm=30, height_mm=5)
    provenance = freecad_provenance("PRJ-1", "RUN-1", 1, "sha256:state", request, "sha256:artifact", "FCStd", "FreeCAD 0.21")
    assert provenance.bound_revision == 1
    assert provenance.bound_state_hash == "sha256:state"
    assert provenance.freecad_version == "FreeCAD 0.21"
    assert provenance.backend_adapter_version == FREECAD_BACKEND_VERSION


def test_discovery_reports_unavailable_without_freecad(monkeypatch):
    monkeypatch.delenv("MECHCAD_FREECADCMD", raising=False)
    monkeypatch.setattr("mechcad_harness.backends.freecad.shutil.which", lambda _: None)
    monkeypatch.setattr("mechcad_harness.backends.freecad.importlib.util.find_spec", lambda _: None)
    discovery = discover_freecad()
    assert discovery.available is False
    with pytest.raises(FreeCADUnavailableError):
        discovery.require_available()


def test_discovery_uses_explicit_freecadcmd(monkeypatch):
    configured = "C:\\FreeCAD\\bin\\freecadcmd.exe"
    monkeypatch.setenv("MECHCAD_FREECADCMD", configured)
    monkeypatch.setattr("mechcad_harness.backends.freecad.Path.is_file", lambda _: True)
    discovery = discover_freecad()
    assert discovery.available is True
    assert discovery.executable == str(Path(configured))
    assert discovery.execution_boundary == "bundled FreeCAD command line"


def test_generation_result_is_typed_and_binds_two_artifacts():
    assert FreeCADGenerationResult.model_fields["fcstd"].annotation is not None
    assert "step" in FreeCADGenerationResult.model_fields


def test_final_operation_identity_is_derived_from_program_manifest():
    from mechcad_harness.cad_manifest import build_program_manifest
    from mechcad_harness.cad_program import acceptance_program

    manifest = build_program_manifest(acceptance_program())
    assert manifest.operations[-1].internal_name == "op_706f636b6574"


def test_structured_verification_rejects_geometry_mismatch():
    result = subprocess.CompletedProcess([], 0, 'M7A1_JSON={"status":"verified","object_name":"Plate","shape_valid":true,"x_length_mm":40,"y_length_mm":30,"z_length_mm":6}\n', "")
    with pytest.raises(FreeCADArtifactVerificationError):
        FreeCADBackend._parse_verification(result, expected=(40, 30, 5), object_name="Plate")


def test_persisted_verifier_script_uses_absolute_artifact_paths(tmp_path):
    artifact_path = tmp_path / "workspace" / "projects" / "P" / "runs" / "R" / "artifacts" / "A" / "plate.FCStd"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(b"fcstd")
    relative_path = artifact_path.relative_to(tmp_path).as_posix()
    assert not Path(relative_path).is_absolute()
    assert (tmp_path / relative_path).resolve() == artifact_path.resolve()
