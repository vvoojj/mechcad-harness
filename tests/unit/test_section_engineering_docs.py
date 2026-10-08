from pathlib import Path


def test_c3a_boundaries_are_documented():
    capability_matrix = Path("docs/architecture/MECHCAD_CAPABILITY_MATRIX.md").read_text(
        encoding="utf-8"
    )
    system_contract = Path("docs/architecture/MECHCAD_SYSTEM_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    capability_reference = Path(
        "docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md"
    ).read_text(encoding="utf-8")
    system_contract = " ".join(system_contract.split())

    for phrase in (
        "M5.5C-3A",
        "persisted material/section results",
        "mass/stiffness ranges",
        "source hashes/units/authority preservation",
    ):
        assert phrase in capability_matrix
    assert "analysis.section" in system_contract
    assert "not general structural approval" in capability_reference
    assert "not structural-FEA authority" in system_contract
