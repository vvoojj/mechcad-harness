from __future__ import annotations

import hashlib

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import CandidateIntegrityError
from mechcad_harness.candidates.models import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
)
from mechcad_harness.candidates.services import compute_verified_semantic_binding
from mechcad_harness.models import DesignState
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.state import StateManager, state_hash

from test_candidate_trusted_semantic_verification import _P2_STEP_VARIANTS

_PROJECT_ID = "PRJ-SUPP"
_STATE_ARTIFACT = "ART-STATE"
_SUPP_ARTIFACT = "ART-SUPP"


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _identity(artifact_id, digest, source_identity):
    return GeometryArtifactIdentity.from_fields(
        artifact_id, digest, source_identity, "step", None
    )


def _setup(tmp_path):
    content = _P2_STEP_VARIANTS["A"]
    digest = _digest(content)
    state = DesignState(
        id="DES-SUPP",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )
    payload = state.model_dump(mode="json")
    payload["yagi_payload_carrier_requirements"] = [
        {
            "artifact_id": _STATE_ARTIFACT,
            "artifact_hash": digest,
            "source_identity": "supplier:state:slot@1",
            "format": "step",
        }
    ]
    state = DesignState.model_validate(payload)
    manager = StateManager(tmp_path)
    manager.create_project(_PROJECT_ID, state)
    store = ArtifactStore(tmp_path, project_id=_PROJECT_ID, run_id="SUPP")
    state_artifact = store.publish(
        _STATE_ARTIFACT,
        ArtifactType.STEP,
        "state.step",
        content,
        "supp-test",
        "1",
        state.revision,
        state_hash(state),
    )
    binding = CandidateSourceBinding(
        project_id=_PROJECT_ID,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/yagi_payload_carrier_requirements/0",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    ).bound_to(state)
    return state, store, binding, state_artifact


def _publish_supp(store, state, content):
    return store.publish(
        _SUPP_ARTIFACT,
        ArtifactType.STEP,
        "supp.step",
        content,
        "supp-test",
        "1",
        state.revision,
        state_hash(state),
    )


def _state_key(artifact):
    return (_STATE_ARTIFACT, artifact.sha256, "supplier:state:slot@1", "step", None)


def _supp_key(artifact):
    return (_SUPP_ARTIFACT, artifact.sha256, "supplier:supp:slot@1", "step", None)


def test_A_state_only_context_unchanged(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    context, semantic_hash = compute_verified_semantic_binding(
        binding, state=state, store=store, project_id=_PROJECT_ID
    )
    assert set(context) == {_state_key(state_artifact)}

    context_empty, semantic_hash_empty = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id=_PROJECT_ID,
        required_source_identities={},
    )
    assert context_empty == context
    assert semantic_hash_empty == semantic_hash


def test_B_candidate_exact_source_supplemented(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    supp_artifact = _publish_supp(store, state, _P2_STEP_VARIANTS["B"])
    identity = _identity(_SUPP_ARTIFACT, supp_artifact.sha256, "supplier:supp:slot@1")
    context, _ = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id=_PROJECT_ID,
        required_source_identities={_SUPP_ARTIFACT: identity},
    )
    assert _supp_key(supp_artifact) in context
    assert _state_key(state_artifact) in context


def test_C_mixed_context_state_and_supplemental(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    supp_artifact = _publish_supp(store, state, _P2_STEP_VARIANTS["B"])
    identity = _identity(_SUPP_ARTIFACT, supp_artifact.sha256, "supplier:supp:slot@1")
    context, _ = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id=_PROJECT_ID,
        required_source_identities={_SUPP_ARTIFACT: identity},
    )
    assert set(context) == {_state_key(state_artifact), _supp_key(supp_artifact)}


def test_D_wrong_exact_artifact_fails(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    supp_artifact = _publish_supp(store, state, _P2_STEP_VARIANTS["B"])
    identity = _identity(_SUPP_ARTIFACT, supp_artifact.sha256, "supplier:supp:slot@1")
    with pytest.raises(CandidateIntegrityError):
        compute_verified_semantic_binding(
            binding,
            state=state,
            store=store,
            project_id=_PROJECT_ID,
            exact_source_artifacts=(state_artifact,),
            required_source_identities={_SUPP_ARTIFACT: identity},
        )


def test_E_missing_required_exact_artifact_fails(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    identity = _identity(_SUPP_ARTIFACT, "sha256:" + "0" * 64, "supplier:supp:slot@1")
    with pytest.raises(CandidateIntegrityError):
        compute_verified_semantic_binding(
            binding,
            state=state,
            store=store,
            project_id=_PROJECT_ID,
            required_source_identities={_SUPP_ARTIFACT: identity},
        )


def test_G_duplicate_exact_artifact_id_fails(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    with pytest.raises(CandidateIntegrityError):
        compute_verified_semantic_binding(
            binding,
            state=state,
            store=store,
            project_id=_PROJECT_ID,
            exact_source_artifacts=(state_artifact, state_artifact),
        )


def test_I_extra_artifact_not_declared_gains_no_authority(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    supp_artifact = _publish_supp(store, state, _P2_STEP_VARIANTS["B"])
    extra_artifact = store.publish(
        "ART-EXTRA",
        ArtifactType.STEP,
        "extra.step",
        _P2_STEP_VARIANTS["A"],
        "supp-test",
        "1",
        state.revision,
        state_hash(state),
    )
    identity = _identity(_SUPP_ARTIFACT, supp_artifact.sha256, "supplier:supp:slot@1")
    context, _ = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id=_PROJECT_ID,
        exact_source_artifacts=(state_artifact, supp_artifact, extra_artifact),
        required_source_identities={_SUPP_ARTIFACT: identity},
    )
    assert ("ART-EXTRA", extra_artifact.sha256, "supplier:supp:slot@1", "step", None) not in context
    assert not any(key[0] == "ART-EXTRA" for key in context)


def test_J_supplemental_does_not_change_source_binding_hash(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    _, base_hash = compute_verified_semantic_binding(
        binding, state=state, store=store, project_id=_PROJECT_ID
    )
    supp_artifact = _publish_supp(store, state, _P2_STEP_VARIANTS["B"])
    identity = _identity(_SUPP_ARTIFACT, supp_artifact.sha256, "supplier:supp:slot@1")
    _, supp_hash = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id=_PROJECT_ID,
        required_source_identities={_SUPP_ARTIFACT: identity},
    )
    assert supp_hash == base_hash


def test_K_candidate_a_artifact_cannot_satisfy_b_identity(tmp_path):
    state, store, binding, state_artifact = _setup(tmp_path)
    supp_artifact = _publish_supp(store, state, _P2_STEP_VARIANTS["B"])
    # Identity claims a different (wrong) hash for the required artifact id.
    identity = _identity(_SUPP_ARTIFACT, _digest(_P2_STEP_VARIANTS["A"]), "supplier:supp:slot@1")
    with pytest.raises(CandidateIntegrityError):
        compute_verified_semantic_binding(
            binding,
            state=state,
            store=store,
            project_id=_PROJECT_ID,
            required_source_identities={_SUPP_ARTIFACT: identity},
        )


def test_L_supplemental_same_key_does_not_override_state_binding(tmp_path):
    # Same artifact_id + same hash + same source_identity => same semantic key => no override.
    state, store, binding, state_artifact = _setup(tmp_path)
    same = _identity(_STATE_ARTIFACT, state_artifact.sha256, "supplier:state:slot@1")
    context, _ = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id=_PROJECT_ID,
        required_source_identities={_STATE_ARTIFACT: same},
    )
    assert set(context) == {_state_key(state_artifact)}


def test_M_conflicting_artifact_id_hash_fails(tmp_path):
    # Same artifact_id with a conflicting hash must fail closed.
    state, store, binding, state_artifact = _setup(tmp_path)
    conflicting = _identity(_STATE_ARTIFACT, "sha256:" + "1" * 64, "supplier:state:slot@1")
    with pytest.raises(CandidateIntegrityError):
        compute_verified_semantic_binding(
            binding,
            state=state,
            store=store,
            project_id=_PROJECT_ID,
            required_source_identities={_STATE_ARTIFACT: conflicting},
        )
