import importlib.util
import math
from hashlib import sha256

import pytest

from mechcad_harness.assembly_service import CadAssemblyGenerationService
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash, instance_object_name
from mechcad_harness.cad_program import acceptance_program, cad_program_hash
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager
from mechcad_harness.backends.freecad import FreeCADArtifactVerificationError
from mechcad_harness.backends.freecad_assembly import assembly_artifact_id


FREECAD_AVAILABLE = importlib.util.find_spec("mechcad_harness") is not None


def acceptance_assembly():
    return CadAssemblyProgram(assembly_id="M7A2BAssembly", parts=(acceptance_program(),), instances=(
        CadComponentInstance(instance_id="bracket_A", part_id="M7A2ABracket"),
        CadComponentInstance(instance_id="bracket_B", part_id="M7A2ABracket", placement=CadRigidTransform(x_mm=160, rotation_quaternion=(math.sqrt(0.5), 0, 0, math.sqrt(0.5)))),
    ))


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
def test_two_fixed_instances_produce_verified_self_contained_assembly(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M7A2B", DesignState(id="DES-M7A2B", revision=1))
    result = CadAssemblyGenerationService(manager, FreeCADAssemblyBackend()).generate_assembly("PRJ-M7A2B", "RUN-M7A2B", 1, snapshot.state_hash, acceptance_assembly(), tmp_path)
    assert result.manifest.assembly_hash == assembly_hash(acceptance_assembly())
    assert [item.instance_id for item in result.manifest.instances] == ["bracket_A", "bracket_B"]
    assert result.manifest.instances[0].part_id == result.manifest.instances[1].part_id
    assert result.manifest.parts[0].part_program_hash == cad_program_hash(acceptance_program())
    assert result.fcstd_verification.overall_bounds_mm == pytest.approx((160, 80, 8), abs=1e-6)
    assert result.step_verification.overall_bounds_mm == pytest.approx((160, 80, 8), abs=1e-6)
    assert [item.x_length_mm for item in result.fcstd_verification.instances] == pytest.approx([80, 60], abs=1e-6)
    assert [item.y_length_mm for item in result.fcstd_verification.instances] == pytest.approx([60, 80], abs=1e-6)
    assert result.fcstd_verification.total_volume_mm3 == pytest.approx(72295.22131576614, rel=1e-6)
    assert result.step_verification.total_volume_mm3 == pytest.approx(72295.22131576614, rel=1e-6)
    assert result.fcstd_verification.solid_count == 2
    assert result.step_verification.solid_count == 2
    assert (tmp_path / result.fcstd.relative_path).is_file()
    assert (tmp_path / result.step.relative_path).is_file()
    replay = CadAssemblyGenerationService(manager, FreeCADAssemblyBackend()).generate_assembly("PRJ-M7A2B", "RUN-M7A2B", 1, snapshot.state_hash, acceptance_assembly(), tmp_path)
    assert replay.fcstd == result.fcstd
    assert replay.step == result.step
    assert instance_object_name("bracket_A") != instance_object_name("bracket_B")


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
def test_assembly_partial_replay_preserves_fcstd_bytes_and_completes_step(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-PARTIAL-ASSEMBLY", DesignState(id="DES-PARTIAL-ASSEMBLY", revision=1))
    program = acceptance_assembly()
    backend = FreeCADAssemblyBackend()
    first = CadAssemblyGenerationService(manager, backend).generate_assembly("PRJ-PARTIAL-ASSEMBLY", "RUN-PARTIAL-ASSEMBLY", 1, snapshot.state_hash, program, tmp_path)
    fcstd_path = tmp_path / first.fcstd.relative_path
    before = fcstd_path.read_bytes()
    before_hash = sha256(before).hexdigest()
    step_dir = tmp_path / "projects" / "PRJ-PARTIAL-ASSEMBLY" / "runs" / "RUN-PARTIAL-ASSEMBLY" / "artifacts" / assembly_artifact_id("PRJ-PARTIAL-ASSEMBLY", "RUN-PARTIAL-ASSEMBLY", 1, snapshot.state_hash, program, "STEP")
    for path in step_dir.iterdir():
        path.unlink()
    step_dir.rmdir()
    recovered = CadAssemblyGenerationService(manager, FreeCADAssemblyBackend()).generate_assembly("PRJ-PARTIAL-ASSEMBLY", "RUN-PARTIAL-ASSEMBLY", 1, snapshot.state_hash, program, tmp_path)
    assert recovered.fcstd.artifact_id == first.fcstd.artifact_id
    assert recovered.fcstd.relative_path == first.fcstd.relative_path
    assert recovered.fcstd.sha256 == first.fcstd.sha256
    assert sha256(fcstd_path.read_bytes()).hexdigest() == before_hash
    assert fcstd_path.read_bytes() == before
    assert recovered.step.artifact_id == first.step.artifact_id


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
def test_actual_placement_tamper_fails_fcstd_verification(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-PLACEMENT-TAMPER", DesignState(id="DES-PLACEMENT-TAMPER", revision=1))
    program = acceptance_assembly()
    backend = FreeCADAssemblyBackend()
    result = CadAssemblyGenerationService(manager, backend).generate_assembly("PRJ-PLACEMENT-TAMPER", "RUN-PLACEMENT-TAMPER", 1, snapshot.state_hash, program, tmp_path)
    path = tmp_path / result.fcstd.relative_path
    script = """import FreeCAD
doc = FreeCAD.openDocument(%r)
obj = doc.getObject('inst_627261636b65745f42')
obj.Placement.Base.x = 159
doc.save()
FreeCAD.closeDocument(doc.Name)
""" % str(path)
    backend.part_backend._run(r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe", script, cwd=tmp_path)
    with pytest.raises(FreeCADArtifactVerificationError):
        backend._verify_persisted(program, tmp_path, "PRJ-PLACEMENT-TAMPER", "RUN-PLACEMENT-TAMPER", 1, snapshot.state_hash, __import__('mechcad_harness.backends.freecad').backends.freecad.discover_freecad(), result.fcstd, result.step, result.manifest)
