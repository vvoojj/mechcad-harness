from pathlib import Path


def test_m6a1_boundaries_are_documented():
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

    for phrase in (
        "AgentGateway",
        "FakeAgentAdapter",
        "mechcad-transmission",
        "OpenCode",
    ):
        assert phrase in system_contract
    assert "| AgentGateway |" in capability_matrix
    assert "context hash, stale and response checks" in capability_matrix
    assert "FakeAgentAdapter" in system_contract
    assert "A test agent is testing-only" in system_contract
    assert "cannot choose trusted revision IDs, state hashes, Evidence IDs" in system_contract
    assert "reasoning-only and does not automatically mutate canonical state" in capability_reference
