import math
import subprocess

import pytest

from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend, FreeCADArtifactVerificationError
from mechcad_harness.cad_assembly import CadRigidTransform


def test_freecad_placement_comparison_accepts_canonical_quaternion_sign():
    actual = {"base": (160.0, 0.0, 0.0), "quaternion": (-math.sqrt(0.5), 0, 0, -math.sqrt(0.5))}
    expected = CadRigidTransform(x_mm=160, rotation_quaternion=(math.sqrt(0.5), 0, 0, math.sqrt(0.5)))
    assert FreeCADAssemblyBackend.placement_matches(actual, expected)


def test_freecad_placement_comparison_rejects_tamper():
    actual = {"base": (159.0, 0.0, 0.0), "quaternion": (math.sqrt(0.5), 0, 0, math.sqrt(0.5))}
    expected = CadRigidTransform(x_mm=160, rotation_quaternion=(math.sqrt(0.5), 0, 0, math.sqrt(0.5)))
    assert not FreeCADAssemblyBackend.placement_matches(actual, expected)


def test_component_preflight_rejects_invalid_artifact_before_assembly_runner(tmp_path):
    backend = FreeCADAssemblyBackend()
    with pytest.raises(FreeCADArtifactVerificationError):
        backend.verify_component_artifact(None, tmp_path, expected_part_hash="sha256:part", expected_artifact_id="FC-PART")


def test_assembly_compile_source_paths_are_absolute(tmp_path):
    source = (tmp_path / "projects" / "P" / "runs" / "R" / "artifacts" / "part" / "plate.FCStd").resolve()
    assert source.is_absolute()
    assert str(source).startswith(str(tmp_path.resolve()))
