import importlib.util
import math
from hashlib import sha256

import pytest

from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.cad_program import AxialBoreOperation, CadPartProgram, CylindricalStockOperation, cad_program_hash


FREECAD_AVAILABLE = discover_freecad().available and importlib.util.find_spec("mechcad_harness") is not None


def _assert_generated_geometry(program, tmp_path, *, project_id, run_id, expected_bbox, expected_volume, expected_probes):
    backend = FreeCADBackend()
    first = backend.generate_program(
        program,
        tmp_path,
        project_id=project_id,
        run_id=run_id,
        revision=1,
        state_hash="sha256:m13-2-state",
    )
    # A second call verifies the persisted files in a new FreeCAD subprocess.
    second = backend.generate_program(
        program,
        tmp_path,
        project_id=project_id,
        run_id=run_id,
        revision=1,
        state_hash="sha256:m13-2-state",
    )

    program_hash = cad_program_hash(program)
    assert first.fcstd.artifact_id == second.fcstd.artifact_id
    assert first.step.artifact_id == second.step.artifact_id
    for artifact in (first.fcstd, first.step):
        path = tmp_path / artifact.relative_path
        assert path.is_file()
        assert artifact.input_hash == program_hash
        assert artifact.sha256 == f"sha256:{sha256(path.read_bytes()).hexdigest()}"
        assert artifact.backend_provenance.backend_name == "freecad"
        assert artifact.backend_provenance.library_version

    for verification in (first.fcstd_verification, first.step_verification):
        assert verification.status == "verified"
        assert verification.shape_valid is True
        assert (verification.x_length_mm, verification.y_length_mm, verification.z_length_mm) == pytest.approx(expected_bbox, abs=1e-6)
        assert verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
        assert verification.solid_count == 1
        assert verification.feature_probes == expected_probes

    store = ArtifactStore(tmp_path, project_id=project_id, run_id=run_id)
    assert store.existing(first.fcstd.artifact_id) is not None
    assert store.existing(first.step.artifact_id) is not None
    assert second.fcstd_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)
    assert second.step_verification.volume_mm3 == pytest.approx(expected_volume, rel=1e-6)


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_live_generated_shaft_publishes_exact_single_cylindrical_solid(tmp_path):
    diameter_mm = 20.0
    length_mm = 50.0
    program = CadPartProgram(
        part_id="m13-2-shaft",
        coordinate_system="base-center; +Z cylinder-axis",
        operations=(CylindricalStockOperation(operation_id="stock", diameter_mm=diameter_mm, length_mm=length_mm),),
    )

    _assert_generated_geometry(
        program,
        tmp_path,
        project_id="PRJ-M13-2-SHAFT",
        run_id="RUN-M13-2-SHAFT",
        expected_bbox=(diameter_mm, diameter_mm, length_mm),
        expected_volume=math.pi * (diameter_mm / 2) ** 2 * length_mm,
        expected_probes={},
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_live_generated_hub_cuts_a_concentric_bore_and_reloads(tmp_path):
    program = CadPartProgram(
        part_id="m13-2-hub",
        coordinate_system="base-center; +Z cylinder-axis",
        operations=(
            CylindricalStockOperation(operation_id="stock", diameter_mm=40, length_mm=30),
            AxialBoreOperation(operation_id="bore", diameter_mm=20, start_z_mm=0, depth_mm=30),
        ),
    )

    _assert_generated_geometry(
        program,
        tmp_path,
        project_id="PRJ-M13-2-HUB",
        run_id="RUN-M13-2-HUB",
        expected_bbox=(40, 40, 30),
        expected_volume=math.pi * (20**2 - 10**2) * 30,
        expected_probes={"bore_bore": True},
    )


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_live_generated_hub_supports_a_two_segment_stepped_bore(tmp_path):
    program = CadPartProgram(
        part_id="m13-2-stepped-hub",
        coordinate_system="base-center; +Z cylinder-axis",
        operations=(
            CylindricalStockOperation(operation_id="stock", diameter_mm=40, length_mm=30),
            AxialBoreOperation(operation_id="bore-near", diameter_mm=20, start_z_mm=0, depth_mm=10),
            AxialBoreOperation(operation_id="bore-far", diameter_mm=30, start_z_mm=10, depth_mm=20),
        ),
    )

    _assert_generated_geometry(
        program,
        tmp_path,
        project_id="PRJ-M13-2-STEPPED",
        run_id="RUN-M13-2-STEPPED",
        expected_bbox=(40, 40, 30),
        expected_volume=math.pi * 20**2 * 30 - math.pi * (10**2 * 10 + 15**2 * 20),
        expected_probes={"bore_bore-near": True, "bore_bore-far": True},
    )
