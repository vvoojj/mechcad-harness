from pathlib import Path


def test_c2b_policy_and_boundaries_are_documented():
    system_contract = Path("docs/architecture/MECHCAD_SYSTEM_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    capability_matrix = Path("docs/architecture/MECHCAD_CAPABILITY_MATRIX.md").read_text(
        encoding="utf-8"
    )
    capability_reference = Path(
        "docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md"
    ).read_text(encoding="utf-8")
    system_contract = " ".join(system_contract.split())

    assert "Section geometry and warping" in system_contract
    assert "direct solver" in system_contract
    assert "coarse/fine convergence" in system_contract
    assert "analytic oracles" in system_contract
    assert "section geometry/warping" in capability_matrix
    assert "EXISTS_UNWIRED" in capability_reference
    assert "not general structural approval" in capability_reference
    assert "not structural-FEA authority" in system_contract
