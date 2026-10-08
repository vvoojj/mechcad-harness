from pathlib import Path


def test_structural_extra_and_axis_contract_are_documented():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    system_contract = Path("docs/architecture/MECHCAD_SYSTEM_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    capability_reference = Path(
        "docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md"
    ).read_text(encoding="utf-8")
    assert "structural = [" in text
    assert '"sectionproperties==3.10.2"' in text
    assert '"numpy>=2,<2.4"' in text
    assert "Section geometry and warping" in system_contract
    assert "direct solver" in system_contract
    assert "coarse/fine convergence" in system_contract
    assert "analytic oracles" in system_contract
    assert "analysis.section" in capability_reference
