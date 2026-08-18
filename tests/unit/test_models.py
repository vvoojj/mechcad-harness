import pytest
from pydantic import ValidationError

from mechcad_harness.models import (
    ChangeProposal,
    Component,
    DesignState,
    Evidence,
    ProposalStatus,
)


def test_basic_models_construct():
    component = Component(id="PRT-part", name="Bracket")
    state = DesignState(id="REV-revision", revision=1, components=[component])

    assert state.components[0].name == "Bracket"


def test_invalid_values_are_rejected():
    with pytest.raises(ValidationError):
        Component(id="PRT-part", name="")
    with pytest.raises(ValidationError):
        DesignState(id="REV-revision", revision=0)


def test_proposal_and_evidence_bind_to_revision_and_hash():
    proposal = ChangeProposal(
        id="CP-proposal",
        title="Add bracket",
        status=ProposalStatus.DRAFT,
        revision=3,
        state_hash="sha256:abc",
    )
    evidence = Evidence(
        id="EVD-proof",
        kind="calculation",
        summary="Checked",
        revision=3,
        state_hash="sha256:abc",
    )

    assert proposal.revision == evidence.revision == 3
    assert proposal.state_hash == evidence.state_hash


def test_design_state_does_not_contain_evidence_or_results():
    assert "evidence" not in DesignState.model_fields
    assert "results" not in DesignState.model_fields
