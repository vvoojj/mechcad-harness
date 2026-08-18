from pathlib import Path


def test_m6a1_boundaries_are_documented():
    text = Path("README.md").read_text(encoding="utf-8")
    for phrase in (
        "M6A-1",
        "AgentGateway",
        "FakeAgentAdapter",
        "agents/",
        "STALE",
        "ChangeProposal",
        "not Evidence",
        "M6A-2",
        "mechcad-transmission",
        "C-3B",
        "OpenCode",
        "AgentEvidenceSummary",
        "Evidence IDs",
        "RESPONSE_BINDING_MISMATCH",
        "CURRENT",
    ):
        assert phrase in text
