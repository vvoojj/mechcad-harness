import json

from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend


def test_step_verification_accepts_three_or_more_valid_assembly_instances():
    payload = {
        "assembly_id": "assembly",
        "assembly_hash": "sha256:assembly",
        "instances": [
            {"instance_id": name, "object_name": name, "x_length_mm": 1, "y_length_mm": 1, "z_length_mm": 1, "x_min_mm": 0, "x_max_mm": 1, "y_min_mm": 0, "y_max_mm": 1, "z_min_mm": 0, "z_max_mm": 1, "volume_mm3": 1, "shape_valid": True}
            for name in ("one", "two", "three", "four")
        ],
        "overall_bounds_mm": [1, 1, 1],
        "total_volume_mm3": 4,
        "solid_count": 4,
        "shape_valid": True,
    }

    class Completed:
        returncode = 0
        stdout = "M7A2B_JSON=" + json.dumps(payload)
        stderr = ""

    parsed = FreeCADAssemblyBackend._parse(Completed(), expected_hash="sha256:assembly", require_names=False)
    assert parsed.solid_count == 4
