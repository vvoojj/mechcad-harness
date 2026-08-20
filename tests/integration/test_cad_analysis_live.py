import importlib.util

import pytest

from mechcad_harness.analysis_service import CadAssemblyAnalysisService
from mechcad_harness.assembly_service import CadAssemblyGenerationService
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend
from mechcad_harness.cad_analysis import CadAssemblyAnalysisPlan, CadInterferenceCheck, CadMinimumClearanceCheck
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import acceptance_program
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager


FREECAD_AVAILABLE = importlib.util.find_spec("mechcad_harness") is not None


def fixture(name, x):
    return CadAssemblyProgram(assembly_id=name, parts=(acceptance_program(),), instances=(
        CadComponentInstance(instance_id="bracket_A", part_id="M7A2ABracket"),
        CadComponentInstance(instance_id="bracket_B", part_id="M7A2ABracket", placement=CadRigidTransform(x_mm=x)),
    ))


def plan(name, required=0):
    return CadAssemblyAnalysisPlan(analysis_id=name, checks=(
        CadInterferenceCheck(check_id="interference", instance_a="bracket_A", instance_b="bracket_B"),
        CadMinimumClearanceCheck(check_id="clearance", instance_a="bracket_A", instance_b="bracket_B", required_clearance_mm=required),
    ))


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
@pytest.mark.parametrize("x, expected_clearance, expected_interference", [(100, 20, 0), (80, 0, 0)])
def test_persisted_assembly_analysis_separated_and_touching(tmp_path, monkeypatch, x, expected_clearance, expected_interference):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M7A2C", DesignState(id="DES-M7A2C", revision=1))
    program = fixture(f"M7A2C-{x}", x)
    CadAssemblyGenerationService(manager, FreeCADAssemblyBackend()).generate_assembly("PRJ-M7A2C", f"RUN-{x}", 1, snapshot.state_hash, program, tmp_path)
    result = CadAssemblyAnalysisService(manager, FreeCADAssemblyBackend()).analyze("PRJ-M7A2C", f"RUN-{x}", 1, snapshot.state_hash, program, plan(f"analysis-{x}"), tmp_path)
    assert result.interference[0].interference_volume_mm3 == pytest.approx(expected_interference, abs=1e-6)
    assert result.clearance[0].measured_clearance_mm == pytest.approx(expected_clearance, abs=1e-6)


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
def test_persisted_assembly_analysis_interference_and_exact_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M7A2C-INTERFERE", DesignState(id="DES-M7A2C-INTERFERE", revision=1))
    program = fixture("M7A2C-70", 70)
    CadAssemblyGenerationService(manager, FreeCADAssemblyBackend()).generate_assembly("PRJ-M7A2C-INTERFERE", "RUN", 1, snapshot.state_hash, program, tmp_path)
    service = CadAssemblyAnalysisService(manager, FreeCADAssemblyBackend())
    result = service.analyze("PRJ-M7A2C-INTERFERE", "RUN", 1, snapshot.state_hash, program, plan("analysis", 1), tmp_path)
    replay = service.analyze("PRJ-M7A2C-INTERFERE", "RUN", 1, snapshot.state_hash, program, plan("analysis", 1), tmp_path)
    assert result.interference[0].interference_volume_mm3 > 1e-9
    assert result.clearance[0].measured_clearance_mm == 0
    assert not result.clearance[0].passed
    assert replay == result


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCAD runtime unavailable")
def test_analysis_is_placement_sensitive(tmp_path, monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", r"C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe")
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-M7A2C-SENSITIVE", DesignState(id="DES-M7A2C-SENSITIVE", revision=1))
    first = fixture("M7A2C-A", 100)
    second = fixture("M7A2C-B", 110)
    service = CadAssemblyGenerationService(manager, FreeCADAssemblyBackend())
    service.generate_assembly("PRJ-M7A2C-SENSITIVE", "RUN-A", 1, snapshot.state_hash, first, tmp_path)
    service.generate_assembly("PRJ-M7A2C-SENSITIVE", "RUN-B", 1, snapshot.state_hash, second, tmp_path)
    analyzer = CadAssemblyAnalysisService(manager, FreeCADAssemblyBackend())
    first_result = analyzer.analyze("PRJ-M7A2C-SENSITIVE", "RUN-A", 1, snapshot.state_hash, first, plan("analysis-a"), tmp_path)
    second_result = analyzer.analyze("PRJ-M7A2C-SENSITIVE", "RUN-B", 1, snapshot.state_hash, second, plan("analysis-b"), tmp_path)
    assert assembly_hash(first) != assembly_hash(second)
    assert first_result.clearance[0].measured_clearance_mm != second_result.clearance[0].measured_clearance_mm
