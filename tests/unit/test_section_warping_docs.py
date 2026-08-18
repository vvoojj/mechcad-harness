from pathlib import Path


def test_c2b_policy_and_boundaries_are_documented():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "M5.5C-2B" in text
    assert "calculate_warping_properties" in text
    assert "solver_type = `direct`" in text
    assert "coarse" in text and "fine" in text
    assert "disconnected" in text
    assert "C-3" in text
    assert "bd_materials" in text
    assert "stress" in text
