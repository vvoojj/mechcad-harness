import importlib.util
import math
import json
from hashlib import sha256

import pytest

from mechcad_harness.cad_program import acceptance_program, cad_program_hash
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.backends.freecad import freecad_object_name, freecad_program_artifact_id
from mechcad_harness.backends.freecad import FreeCADArtifactVerificationError
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.cad_service import CadGenerationService
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager


FREECAD_AVAILABLE = discover_freecad().available and importlib.util.find_spec("mechcad_harness") is not None


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_typed_parametric_program_publishes_and_verifies_one_mechanical_solid(tmp_path):
    program = acceptance_program()
    backend = FreeCADBackend()
    result = backend.generate_program(program, tmp_path, project_id="PRJ-M7A2A", run_id="RUN-M7A2A", revision=1, state_hash="sha256:m7a2a-state")
    replay = backend.generate_program(program, tmp_path, project_id="PRJ-M7A2A", run_id="RUN-M7A2A", revision=1, state_hash="sha256:m7a2a-state")
    assert replay.fcstd == result.fcstd
    assert replay.step == result.step
    expected_volume = 80 * 60 * 8 - 2 * math.pi * 3**2 * 8 - 30 * 20 * 3
    for verification in (result.fcstd_verification, result.step_verification):
        assert (verification.x_length_mm, verification.y_length_mm, verification.z_length_mm) == pytest.approx((80, 60, 8), abs=1e-6)
        assert verification.solid_count == 1
        assert verification.shape_valid is True
        assert verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert result.fcstd_verification.feature_probes == {"hole_hole1": True, "hole_hole2": True, "pocket_pocket": True}
    assert cad_program_hash(program).startswith("sha256:")
    for artifact in (result.fcstd, result.step):
        path = tmp_path / artifact.relative_path
        assert path.is_file()
        assert artifact.sha256 == f"sha256:{sha256(path.read_bytes()).hexdigest()}"
        assert artifact.input_hash == cad_program_hash(program)


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_partial_replay_reuses_fcstd_and_completes_missing_step(tmp_path):
    program = acceptance_program()
    backend = FreeCADBackend()
    first = backend.generate_program(program, tmp_path, project_id="PRJ-PARTIAL", run_id="RUN-PARTIAL", revision=1, state_hash="sha256:s")
    step_dir = tmp_path / "projects" / "PRJ-PARTIAL" / "runs" / "RUN-PARTIAL" / "artifacts" / freecad_program_artifact_id("PRJ-PARTIAL", "RUN-PARTIAL", 1, "sha256:s", program, "STEP")
    for path in step_dir.iterdir():
        path.unlink()
    step_dir.rmdir()
    fcstd_path = tmp_path / first.fcstd.relative_path
    before = fcstd_path.read_bytes()
    recovered = backend.generate_program(program, tmp_path, project_id="PRJ-PARTIAL", run_id="RUN-PARTIAL", revision=1, state_hash="sha256:s")
    assert recovered.fcstd.artifact_id == first.fcstd.artifact_id
    assert recovered.fcstd.sha256 == first.fcstd.sha256
    assert fcstd_path.read_bytes() == before
    assert recovered.step.artifact_id == first.step.artifact_id
    assert (tmp_path / recovered.step.relative_path).is_file()


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_real_freecad_preserves_encoded_final_name(tmp_path):
    program = acceptance_program()
    result = FreeCADBackend().generate_program(program, tmp_path, project_id="PRJ-NAME", run_id="RUN-NAME", revision=1, state_hash="sha256:s")
    assert result.fcstd_verification.object_name == freecad_object_name("pocket")


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_cad_generation_service_binds_authoritative_state(tmp_path):
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-SERVICE", DesignState(id="DES-SERVICE", revision=1))
    result = CadGenerationService(manager, FreeCADBackend()).generate_program("PRJ-SERVICE", "RUN-SERVICE", snapshot.revision, snapshot.state_hash, acceptance_program(), tmp_path)
    assert result.bound_revision == snapshot.revision
    assert result.bound_state_hash == snapshot.state_hash
    assert result.fcstd.bound_revision == snapshot.revision
    assert result.fcstd.bound_state_hash == snapshot.state_hash


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_tampered_fcstd_manifest_fails_reload_verification(tmp_path):
    program = acceptance_program()
    backend = FreeCADBackend()
    result = backend.generate_program(program, tmp_path, project_id="PRJ-TAMPER", run_id="RUN-TAMPER", revision=1, state_hash="sha256:s")
    path = tmp_path / result.fcstd.relative_path
    script = """import FreeCAD, json
doc = FreeCAD.openDocument(%r)
manifest = doc.getObject('program_manifest')
payload = json.loads(manifest.ManifestJson)
payload['program_hash'] = 'sha256:tampered'
manifest.ManifestJson = json.dumps(payload, sort_keys=True, separators=(',', ':'))
doc.save()
FreeCAD.closeDocument(doc.Name)
""" % str(path)
    backend._run(discover_freecad().executable, script, cwd=tmp_path)
    with pytest.raises((FreeCADArtifactVerificationError, FileExistsError)):
        backend.generate_program(program, tmp_path, project_id="PRJ-TAMPER", run_id="RUN-TAMPER", revision=1, state_hash="sha256:s")
