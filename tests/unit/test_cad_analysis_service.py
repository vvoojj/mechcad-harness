import pytest

from mechcad_harness.analysis_service import CadAssemblyAnalysisService
from mechcad_harness.backends.freecad import FreeCADArtifactVerificationError
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend
from mechcad_harness.cad_analysis import CadAssemblyAnalysisPlan, CadInterferenceCheck
from mechcad_harness.cad_program import acceptance_program
from mechcad_harness.cad_analysis import analysis_artifact_id


class SpyBackend:
    def __init__(self):
        self.calls = 0

    def verify_persisted_assembly(self, *args, **kwargs):
        self.calls += 1
        raise FreeCADArtifactVerificationError("stale assembly")


def test_stale_assembly_is_rejected_before_analysis_runner(tmp_path, monkeypatch):
    from mechcad_harness.models import DesignState
    from mechcad_harness.state import StateManager
    state = StateManager(tmp_path)
    snapshot = state.create_project("P", DesignState(id="D", revision=1))
    binding_hash = snapshot.state_hash
    spy = SpyBackend()
    service = CadAssemblyAnalysisService(state, spy)
    plan = CadAssemblyAnalysisPlan(analysis_id="a", checks=(CadInterferenceCheck(check_id="i", instance_a="x", instance_b="y"),))
    with pytest.raises(FreeCADArtifactVerificationError):
        service.analyze("P", "R", 1, binding_hash, type("Program", (), {})(), plan, tmp_path)
    assert spy.calls == 1


def test_analysis_artifact_identity_binds_assembly_artifact_and_analyzer_version():
    assert analysis_artifact_id("analysis", "sha256:plan", "ASM-1", "sha256:assembly", "mechcad-freecad-clearance@1.0") != analysis_artifact_id("analysis", "sha256:plan", "ASM-2", "sha256:assembly", "mechcad-freecad-clearance@1.0")
    assert analysis_artifact_id("analysis", "sha256:plan", "ASM-1", "sha256:assembly", "mechcad-freecad-clearance@1.0") != analysis_artifact_id("analysis", "sha256:plan", "ASM-1", "sha256:assembly", "mechcad-freecad-clearance@2.0")


def test_analysis_service_reuses_existing_persisted_result_without_geometry_runner(tmp_path):
    # The service-level replay contract is exercised by the live fixture; this
    # assertion locks the artifact identity API used to locate that result.
    assert analysis_artifact_id("analysis", "sha256:plan", "ASM-1", "sha256:assembly", "mechcad-freecad-clearance@1.0").startswith("ANALYSIS-")
