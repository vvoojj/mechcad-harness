from pathlib import Path


def test_structural_extra_and_axis_contract_are_documented():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "structural = [" in text
    assert '"sectionproperties==3.10.2"' in text
    assert '"numpy>=2,<2.4"' in text
    assert "x = horizontal" in readme
    assert "C-2A" in readme
    assert "warping" in readme
    assert "mesh_size_mm2" in readme
    assert "discretization_points" in readme
