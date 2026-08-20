import importlib.util

import pytest

from mechcad_harness.analysis_service import CadAssemblyAnalysisService
from mechcad_harness.assembly_service import CadAssemblyGenerationService
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend
from mechcad_harness.cad_analysis import CadAssemblyAnalysisPlan, CadInterferenceCheck
from mechcad_harness.cad_service import CadGenerationService
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.yagi_carrier import YagiCarrierSynthesisService, build_yagi_carrier_proposal
from mechcad_harness.yagi_carrier_packaging import compile_yagi_carrier_packaging_geometry, representative_yagi_carrier_assembly
from mechcad_harness.yagi_sliding_interface import select_yagi_carrier_sliding_interface


FREECAD_AVAILABLE = discover_freecad().available and importlib.util.find_spec("mechcad_harness") is not None


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_canonical_carrier_packaging_cad_and_nominal_collision_analysis(tmp_path):
    from tests.unit.test_m7b2b_yagi_carrier import state_with_authority

    manager = state_with_authority(tmp_path)
    project_id, run_id = "PRJ-CARRIER", "RUN-R4"
    before = manager._read_current(project_id)
    state = manager.load_current_state(project_id)
    synthesis = YagiCarrierSynthesisService().synthesize(state, source_revision=before["revision"], source_state_hash=before["state_hash"], project_id=project_id)
    proposal = build_yagi_carrier_proposal(synthesis, project_id=project_id, source_revision=before["revision"], source_state_hash=before["state_hash"], sliding_interface=select_yagi_carrier_sliding_interface())
    applied = ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")).apply_proposal(project_id, proposal)
    post = manager.load_revision(project_id, applied.snapshot.revision)
    pointer = manager._read_current(project_id)
    carrier = post.yagi_carriers[0]
    from mechcad_harness.yagi_carrier import YagiCarrierDesignSpec

    canonical_spec = YagiCarrierDesignSpec.model_validate(carrier)
    interface = select_yagi_carrier_sliding_interface()
    program = compile_yagi_carrier_packaging_geometry(canonical_spec, interface)
    cad = CadGenerationService(manager, FreeCADBackend())
    first = cad.generate_program(project_id, run_id, pointer["revision"], pointer["state_hash"], program, tmp_path)
    replay = cad.generate_program(project_id, run_id, pointer["revision"], pointer["state_hash"], program, tmp_path)
    assert first.fcstd == replay.fcstd
    assert first.step == replay.step
    assert (first.fcstd_verification.x_length_mm, first.fcstd_verification.y_length_mm, first.fcstd_verification.z_length_mm) == pytest.approx((40, 500, 40), abs=1e-6)
    assert first.fcstd_verification.volume_mm3 == pytest.approx(800000, abs=1e-6)
    assert first.step_verification.volume_mm3 == pytest.approx(800000, abs=1e-6)
    assembly = representative_yagi_carrier_assembly(canonical_spec, interface)
    assembly_result = CadAssemblyGenerationService(manager, FreeCADAssemblyBackend()).generate_assembly(project_id, run_id, pointer["revision"], pointer["state_hash"], assembly, tmp_path)
    assert assembly_result.fcstd_verification.solid_count == 4
    plan = CadAssemblyAnalysisPlan(analysis_id="nominal_yagi_envelope_collision", checks=(
        CadInterferenceCheck(check_id="0400-0600", instance_a="antenna_0400", instance_b="antenna_0600"),
        CadInterferenceCheck(check_id="0600-1200", instance_a="antenna_0600", instance_b="antenna_1200"),
        CadInterferenceCheck(check_id="0400-1200", instance_a="antenna_0400", instance_b="antenna_1200"),
    ))
    analysis = CadAssemblyAnalysisService(manager, FreeCADAssemblyBackend()).analyze(project_id, run_id, pointer["revision"], pointer["state_hash"], assembly, plan, tmp_path)
    by_id = {item.check_id: item for item in analysis.interference}
    assert by_id["0400-0600"].interference_volume_mm3 == pytest.approx(8820000)
    assert by_id["0600-1200"].interference_volume_mm3 == pytest.approx(3060000)
    assert by_id["0400-1200"].interference_volume_mm3 == pytest.approx(0)
    assert analysis.passed is False
