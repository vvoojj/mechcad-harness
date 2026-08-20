import importlib.util
from hashlib import sha256

import pytest

from mechcad_harness.backends.freecad import FreeCADBackend, FreeCADFixtureRequest, discover_freecad


FREECAD_AVAILABLE = discover_freecad().available and importlib.util.find_spec("mechcad_harness") is not None


@pytest.mark.skipif(not FREECAD_AVAILABLE, reason="FreeCADCmd is not available")
def test_freecad_plate_publishes_and_verifies_run_scoped_artifacts(tmp_path):
    request = FreeCADFixtureRequest(document_id="M7A1Plate", object_id="Plate", length_mm=40, width_mm=30, height_mm=5)
    backend = FreeCADBackend()
    first = backend.generate_plate(request, tmp_path, project_id="PRJ-M7A1", run_id="RUN-M7A1", revision=1, state_hash="sha256:state")
    second = backend.generate_plate(request, tmp_path, project_id="PRJ-M7A1", run_id="RUN-M7A1", revision=1, state_hash="sha256:state")
    assert first.fcstd == second.fcstd
    assert first.step == second.step
    assert first.fcstd_verification.x_length_mm == pytest.approx(40, abs=1e-6)
    assert first.fcstd_verification.y_length_mm == pytest.approx(30, abs=1e-6)
    assert first.fcstd_verification.z_length_mm == pytest.approx(5, abs=1e-6)
    assert first.step_verification.x_length_mm == pytest.approx(40, abs=1e-6)
    assert first.step_verification.y_length_mm == pytest.approx(30, abs=1e-6)
    assert first.step_verification.z_length_mm == pytest.approx(5, abs=1e-6)
    for artifact in (first.fcstd, first.step):
        path = tmp_path / artifact.relative_path
        assert path.is_file()
        assert artifact.sha256 == f"sha256:{sha256(path.read_bytes()).hexdigest()}"
        assert artifact.bound_revision == 1
        assert artifact.bound_state_hash == "sha256:state"
        assert artifact.backend_provenance.backend_name == "freecad"
        assert artifact.backend_provenance.library_version
