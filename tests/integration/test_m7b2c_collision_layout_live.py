import importlib.util

import pytest

from mechcad_harness.analysis_service import CadAssemblyAnalysisService
from mechcad_harness.assembly_service import CadAssemblyGenerationService
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend
from mechcad_harness.cad_analysis import CadAssemblyAnalysisPlan, CadInterferenceCheck, CadMinimumClearanceCheck
from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
from mechcad_harness.yagi_carrier_packaging import collision_resolved_yagi_carrier_assembly
from mechcad_harness.yagi_collision_layout import YagiCollisionLayoutSpec, YagiCollisionLayoutSynthesisService
from mechcad_harness.yagi_sliding_interface import select_yagi_carrier_sliding_interface


FREECAD_AVAILABLE = discover_freecad().available and importlib.util.find_spec("mechcad_harness") is not None


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_post_application_representative_collision_layout_has_expected_exact_pair_semantics(tmp_path):
    from tests.unit.test_m7b2c_canonical_layout import _canonical_carrier
    from tests.unit.test_m7b2b_yagi_carrier import state_with_authority
    from mechcad_harness.yagi_carrier import YagiCarrierDesignSpec

    manager = state_with_authority(tmp_path)
    _canonical_carrier(manager)
    before = manager._read_current("PRJ-CARRIER")
    synthesis = YagiCollisionLayoutSynthesisService().synthesize(
        manager.load_current_state("PRJ-CARRIER"),
        source_revision=before["revision"],
        source_state_hash=before["state_hash"],
        project_id="PRJ-CARRIER",
        selected_envelope_ids=("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200"),
    )
    applied = ChangeEngine(manager, OwnershipPolicy.from_file("config/ownership.yaml")).apply_proposal("PRJ-CARRIER", synthesis.proposal)
    pointer = manager._read_current("PRJ-CARRIER")
    post = manager.load_revision("PRJ-CARRIER", applied.snapshot.revision)
    carrier = YagiCarrierDesignSpec.model_validate(post.yagi_carriers[0])
    layout = YagiCollisionLayoutSpec.model_validate(post.yagi_collision_layouts[0])
    assembly = collision_resolved_yagi_carrier_assembly(carrier, select_yagi_carrier_sliding_interface(), layout)
    generation = CadAssemblyGenerationService(manager, FreeCADAssemblyBackend()).generate_assembly("PRJ-CARRIER", "RUN-M7B2C", pointer["revision"], pointer["state_hash"], assembly, tmp_path)
    assert generation.fcstd_verification.solid_count == 4
    plan = CadAssemblyAnalysisPlan(analysis_id="resolved_yagi_envelope_collision", checks=(
        CadInterferenceCheck(check_id="0400-0600", instance_a="antenna_0400", instance_b="antenna_0600"),
        CadInterferenceCheck(check_id="0600-1200", instance_a="antenna_0600", instance_b="antenna_1200"),
        CadInterferenceCheck(check_id="0400-1200", instance_a="antenna_0400", instance_b="antenna_1200"),
        CadMinimumClearanceCheck(check_id="distance-0400-0600", instance_a="antenna_0400", instance_b="antenna_0600"),
        CadMinimumClearanceCheck(check_id="distance-0600-1200", instance_a="antenna_0600", instance_b="antenna_1200"),
        CadMinimumClearanceCheck(check_id="distance-0400-1200", instance_a="antenna_0400", instance_b="antenna_1200"),
    ))
    analysis = CadAssemblyAnalysisService(manager, FreeCADAssemblyBackend()).analyze("PRJ-CARRIER", "RUN-M7B2C", pointer["revision"], pointer["state_hash"], assembly, plan, tmp_path)
    by_id = {item.check_id: item for item in analysis.interference}
    assert by_id["0400-0600"].interference_volume_mm3 == pytest.approx(0)
    assert by_id["0600-1200"].interference_volume_mm3 == pytest.approx(0)
    assert by_id["0400-1200"].interference_volume_mm3 == pytest.approx(0)
    by_distance_id = {item.check_id: item for item in analysis.clearance}
    assert by_distance_id["distance-0400-0600"].measured_clearance_mm == pytest.approx(0)
    assert by_distance_id["distance-0600-1200"].measured_clearance_mm == pytest.approx(0)
    assert by_distance_id["distance-0400-1200"].measured_clearance_mm == pytest.approx(25)
    assert analysis.passed is True
