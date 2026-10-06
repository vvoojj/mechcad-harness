from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates import (
    CandidateCadRealizationService,
    CandidateComparisonService,
    CandidateCurrentnessService,
    CandidateEvaluation,
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationPolicy,
    CandidateEvaluationService,
    CandidateIntegrityVerifier,
    CandidateMultiJointM10EvaluationService,
    CandidatePromotionCompiler,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    CandidatePublicationService,
    CandidateSelection,
    CandidateSelectionService,
)
from mechcad_harness.candidates.models import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisRequest,
    GeometrySourceReference,
)
from mechcad_harness.candidates.services import (
    bind_candidate_synthesis_request_semantic_identity,
    CandidateIntegrityError,
    compute_verified_semantic_binding,
    verify_candidate_semantic_binding,
)
from mechcad_harness.models import DesignState
from mechcad_harness.models.semantic_component import (
    bind_component_specification_semantic_identity,
)
from mechcad_harness.revolute_drive import DriveArchitecture, admissibility_result_hash
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.state.hashing import canonical_json
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_m12_candidate_comparison import (
    _policy as _comparison_policy,
    _request as _comparison_request,
)
from test_m12_candidate_evaluation import (
    _bound_m10_inputs,
    _evaluation_candidate,
    _evaluation_service,
    _m12_result,
)
from test_m12_candidate_foundation import (
    _source as _foundation_binding,
    _state as _foundation_state,
)
from test_m12_revolute_drive_service import (
    _SERVICE as _REVOLUTE_SERVICE,
    bearing_specification,
    body_specification,
    hub_specification,
    motor_specification,
    mount_specification,
    policy_for,
    shaft_specification,
    template,
)
from test_m13_3_candidate_evaluation import _request as _mj_request


def _state() -> DesignState:
    return DesignState(
        id="DES-TRUSTED",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def _binding(state: DesignState) -> CandidateSourceBinding:
    return CandidateSourceBinding(
        project_id="PRJ-TRUSTED",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
        ),
    ).bound_to(state)


def test_shared_core_recomputes_the_semantic_binding_from_the_exact_state(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-TRUSTED", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-TRUSTED", run_id="TRUSTED")
    binding = _binding(state)

    geometry_bindings, semantic_hash = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id="PRJ-TRUSTED",
    )

    assert geometry_bindings == {}
    assert semantic_hash.startswith("sha256:")


def test_shared_core_rejects_a_binding_for_the_wrong_revision(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-TRUSTED", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-TRUSTED", run_id="TRUSTED")
    binding = _binding(state).model_copy(update={"source_state_hash": "sha256:" + "f" * 64})

    with pytest.raises((CandidateIntegrityError, ValueError)):
        compute_verified_semantic_binding(
            binding,
            state=state,
            store=store,
            project_id="PRJ-TRUSTED",
        )


def test_request_binder_fills_semantic_identity_and_request_hash(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-TRUSTED", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-TRUSTED", run_id="TRUSTED")
    request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@2",
        source_binding=_binding(state),
        semantic_source_binding_hash="pending",
    )

    bound = bind_candidate_synthesis_request_semantic_identity(
        request,
        state_manager=manager,
        store=store,
        project_id="PRJ-TRUSTED",
    )

    assert bound.semantic_source_binding_hash != "pending"
    assert bound.request_hash != "pending"


def test_request_binder_rejects_a_forged_concrete_request_hash(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-TRUSTED", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-TRUSTED", run_id="TRUSTED")
    request = bind_candidate_synthesis_request_semantic_identity(
        CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@2",
            source_binding=_binding(state),
            semantic_source_binding_hash="pending",
        ),
        state_manager=manager,
        store=store,
        project_id="PRJ-TRUSTED",
    )
    forged = request.model_copy(update={"request_hash": "sha256:" + "f" * 64})

    with pytest.raises(CandidateIntegrityError):
        bind_candidate_synthesis_request_semantic_identity(
            forged,
            state_manager=manager,
            store=store,
            project_id="PRJ-TRUSTED",
        )


# P2 staged-admission boundary proofs (accepted Plan T-P2.6): request@2 and
# candidate@2 trusted behavior works positively through binding, construction,
# publication, and currentness; every reachable P3/P5/P7 admission boundary
# stays reject-only until its owner phase creates the required records.


def _step_bytes(*, timestamp):
    return (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_NAME('p2-geometry.step','"
        + timestamp
        + "',('author''s name'),('org'),('preprocessor'),('system'),'' );\n"
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));\n"
        "ENDSEC;\n"
        "DATA;\n"
        "#1=PRODUCT('p2-geometry');\n"
        "ENDSEC;\n"
        "END-ISO-10303-21;\n"
    ).encode("utf-8")


_P2_GEOMETRY_SLOTS = ("motor", "shaft", "bearing", "hub", "mount", "body")

_P2_STEP_VARIANTS = {
    "A": _step_bytes(timestamp="2026-09-22T12:34:56"),
    "B": _step_bytes(timestamp="2027-01-02T03:04:05"),
}


def _geometry_identity(artifact_id, artifact_hash, slot):
    return {
        "artifact_id": artifact_id,
        "artifact_hash": artifact_hash,
        "source_identity": f"supplier:m12:{slot}@1",
        "format": "step",
    }


def _at2_chain(tmp_path, manager, store, *, variant="A", project_id="PRJ-M12"):
    """Build one fully bound request@2/candidate@2 pair with dual-bound geometry.

    The STEP geometry is published to the store AND carried as consumed
    authority values in the state, so the trusted verifier rebuilds the exact
    semantic geometry context from bytes. Variants A/B share content with
    rotated raw timestamps/identifiers.
    """
    from mechcad_harness.artifacts import ArtifactType

    step_bytes = _P2_STEP_VARIANTS[variant]
    artifact_hash = "sha256:" + hashlib.sha256(step_bytes).hexdigest()
    content_hash = step_content_identity_v1(step_bytes).content_hash
    base_state = _foundation_state()
    identities = [
        _geometry_identity(f"ART-P2-{slot}-{variant}", artifact_hash, slot)
        for slot in _P2_GEOMETRY_SLOTS
    ]
    state = base_state.model_copy(
        update={"yagi_payload_carrier_requirements": identities}
    )
    try:
        manager.create_project(project_id, state)
        stored = manager.load_revision(project_id, 1)
    except Exception:
        stored = manager.load_revision(
            project_id, manager.create_revision(project_id, state).revision
        )
    binding = CandidateSourceBinding(
        project_id=project_id,
        source_revision=stored.revision,
        source_state_hash=state_hash(stored),
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
            *(
                CandidateSourceReference(
                    path=f"/yagi_payload_carrier_requirements/{index}",
                    value_hash="pending",
                    authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
                )
                for index in range(len(identities))
            ),
        ),
    ).bound_to(stored)
    for identity in identities:
        store.publish(
            identity["artifact_id"],
            ArtifactType.STEP,
            f"p2-{identity['artifact_id'].lower()}.step",
            step_bytes,
            "fixture-step-producer",
            "1",
            binding.source_revision,
            binding.source_state_hash,
        )
    context = {
        (
            identity["artifact_id"],
            artifact_hash,
            identity["source_identity"],
            "step",
            None,
        ): {
            "algorithm": "step-content-identity@1",
            "content_hash": content_hash,
        }
        for identity in identities
    }
    base_specs = {
        "motor": motor_specification(),
        "shaft": shaft_specification(),
        "bearing": bearing_specification(),
        "hub": hub_specification(),
        "mount": mount_specification(),
        "body": body_specification(),
    }
    bound_specs = {}
    for slot, base_spec in base_specs.items():
        identity = next(
            item for item in identities if item["source_identity"] == f"supplier:m12:{slot}@1"
        )
        pending_spec = base_spec.model_copy(
            update={
                "schema_version": "component-specification@4",
                "geometry_source": GeometrySourceReference(
                    artifact_id=identity["artifact_id"],
                    artifact_hash=identity["artifact_hash"],
                    source_identity=identity["source_identity"],
                    content_identity="pending",
                    content_identity_algorithm="step-content-identity@1",
                ),
                "specification_hash": "pending",
            }
        )
        bound_specs[slot] = bind_component_specification_semantic_identity(
            pending_spec, context
        )
    pending_request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@2",
        source_binding=binding,
        semantic_source_binding_hash="pending",
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )
    bound_request = bind_candidate_synthesis_request_semantic_identity(
        pending_request,
        state_manager=manager,
        store=store,
        project_id=project_id,
    )
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    candidate = _REVOLUTE_SERVICE.construct_candidate(
        bound_request,
        policy,
        template(
            DriveArchitecture.DIRECT_DRIVE,
            motor_specification=bound_specs["motor"],
            shaft_specification=bound_specs["shaft"],
            bearing_a_specification=bound_specs["bearing"],
            bearing_b_specification=bound_specs["bearing"],
            hub_specification=bound_specs["hub"],
            mount_specification=bound_specs["mount"],
            driven_body_specification=bound_specs["body"],
        ),
    ).candidate
    assert candidate is not None
    return state, binding, bound_request, policy, candidate


def _at2_setup(tmp_path):
    """Build the primary fully bound request@2/candidate@2 pair."""
    manager = StateManager(tmp_path)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12", run_id="TRUSTED-AT2")
    state, binding, bound_request, policy, candidate = _at2_chain(
        tmp_path, manager, store, variant="A"
    )
    return state, manager, store, binding, bound_request, policy, candidate


def _legacy_request_for(binding):
    return CandidateSynthesisRequest(
        source_binding=binding,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )


class _NeverCalled:
    def __call__(self, *args, **kwargs):
        raise AssertionError("verifier must not be invoked past the boundary")

    def verify_current(self, *args, **kwargs):
        raise AssertionError("verifier must not be invoked past the boundary")

    def evaluate(self, *args, **kwargs):
        raise AssertionError("verifier must not be invoked past the boundary")

    def evaluate_source_binding(self, *args, **kwargs):
        raise AssertionError("verifier must not be invoked past the boundary")


def test_p2_integrity_rejects_candidate_at2_with_request_at1(tmp_path):
    _, _, _, _, _, policy, candidate = _at2_setup(tmp_path)

    with pytest.raises(CandidateIntegrityError, match="famil"):
        CandidateIntegrityVerifier().verify(
            candidate, _legacy_request_for(candidate.source_binding), policy
        )


def test_p2_source_only_currentness_cannot_establish_current_for_at2(tmp_path):
    _, manager, _, _, _, _, candidate = _at2_setup(tmp_path)
    service = CandidateCurrentnessService(manager)

    with pytest.raises(CandidateIntegrityError, match="request@2"):
        service.evaluate_source_binding(candidate)
    with pytest.raises(CandidateIntegrityError, match="@2"):
        service.evaluate_source_binding(
            candidate,
            synthesis_request=_legacy_request_for(candidate.source_binding),
        )


def test_p2_contextual_verifier_rejects_forged_request_binding(tmp_path):
    _, manager, store, _, bound_request, _, candidate = _at2_setup(tmp_path)
    forged_request = bound_request.model_copy(
        update={"semantic_source_binding_hash": "sha256:" + "e" * 64}
    )

    with pytest.raises(CandidateIntegrityError, match="semantic"):
        verify_candidate_semantic_binding(
            candidate,
            forged_request,
            state_manager=manager,
            store=store,
            project_id="PRJ-M12",
        )


def test_p2_contextual_verifier_rejects_forged_candidate_request_hash(tmp_path):
    _, manager, store, _, bound_request, _, candidate = _at2_setup(tmp_path)
    forged_candidate = candidate.model_copy(
        update={"synthesis_request_hash": "sha256:" + "e" * 64}
    )

    with pytest.raises(CandidateIntegrityError, match="synthesis request hash"):
        verify_candidate_semantic_binding(
            forged_candidate,
            bound_request,
            state_manager=manager,
            store=store,
            project_id="PRJ-M12",
        )


def test_p2_request_binder_rejects_request_at1_without_upgrade(tmp_path):
    state = _foundation_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12", run_id="TRUSTED-AT2")

    with pytest.raises(CandidateIntegrityError, match="@2"):
        bind_candidate_synthesis_request_semantic_identity(
            _legacy_request_for(_foundation_binding(state)),
            state_manager=manager,
            store=store,
            project_id="PRJ-M12",
        )


def test_p2_evaluation_boundary_requires_admissibility_at2(tmp_path):
    _, manager, _, _, bound_request, policy, candidate = _at2_setup(tmp_path)
    service = CandidateEvaluationService(
        currentness_verifier=CandidateCurrentnessService(manager)
    )

    with pytest.raises(CandidateIntegrityError, match="admissibility@2"):
        service.evaluate(
            candidate,
            bound_request,
            policy,
            _m12_result(candidate),
            None,
            None,
            CandidateEvaluationPolicy(),
        )


def test_p2_multi_joint_m10_boundary_rejects_at2_before_construction(tmp_path):
    _, _, _, _, _, _, candidate = _at2_setup(tmp_path)
    _, mj_realization, mj_bridge, mj_request = _mj_request(tmp_path)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=CandidateCurrentnessService(StateManager(tmp_path))
    )

    with pytest.raises(ValueError, match="synthesis request@2"):
        service.build_request(
            candidate,
            mj_realization,
            mj_bridge,
            mj_request.scope,
            placement_derivations=mj_request.placement_derivations,
            synthesis_request=None,
        )


def _feasible_at1_evaluation(state):
    candidate1, request1, policy1 = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate1)
    evaluation = _evaluation_service().evaluate(
        candidate1,
        request1,
        policy1,
        _m12_result(candidate1),
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    return candidate1, evaluation


def test_p2_selection_boundary_rejects_mixed_candidate_at2_without_admission(tmp_path):
    # A coherent evaluation@1/candidate@2 pair is not constructible at P2: the
    # @2-specific selection branch requires P7 records. This proves the staged
    # boundary fail-closed behavior with honest fixtures: no selection@1 is
    # produced for candidate@2 and no bypass exists.
    state, manager, _, _, _, _, candidate = _at2_setup(tmp_path)
    _, evaluation = _feasible_at1_evaluation(state)
    service = CandidateSelectionService(
        project_id="PRJ-M12",
        currentness_verifier=CandidateEvaluationCurrentnessService(
            manager, cad_replay_verifier=lambda *args: None
        ),
    )

    with pytest.raises(ValueError, match="identity mismatch"):
        service.select(candidate, evaluation, "manual", "P2 boundary proof.")


def test_p2_comparison_boundary_requires_request_at2(tmp_path):
    state, _, _, _, _, _, candidate = _at2_setup(tmp_path)
    _, evaluation = _feasible_at1_evaluation(state)
    comparison_policy = _comparison_policy()
    request = _comparison_request(comparison_policy, ((candidate, evaluation),))
    service = CandidateComparisonService(
        comparison_policy,
        project_id="PRJ-M12",
        currentness_verifier=_NeverCalled(),
    )

    with pytest.raises(ValueError, match="request@2"):
        service.compare(request, ((candidate, evaluation),))


def test_p2_cad_boundary_requires_request_at3(tmp_path):
    state, manager, _, _, bound_request, policy, candidate = _at2_setup(tmp_path)
    candidate1, _, _ = _evaluation_candidate(state)
    cad_request = _bound_m10_inputs(candidate1)[5]
    service = CandidateCadRealizationService(tmp_path, "PRJ-M12", manager)

    with pytest.raises(CandidateIntegrityError, match="request@3"):
        service._verify_candidate(candidate, bound_request, policy, cad_request)


def test_p2_promotion_boundary_requires_canonical_at4_family(tmp_path):
    # The promotion-request envelope validation itself requires P7 @2 member
    # records, so this exercises the exact rejection point directly with real
    # candidate/request/policy objects (repo precedent: SimpleNamespace
    # request envelopes in promotion replay tests). Integrity and currentness
    # run for real; only the envelope container is stood in.
    from types import SimpleNamespace

    _, manager, _, _, bound_request, policy, candidate = _at2_setup(tmp_path)
    compiler = CandidatePromotionCompiler(
        manager,
        lambda project_id: ArtifactStore(
            tmp_path, project_id=project_id, run_id="promotion-lookup"
        ),
        cad_replay_verifier=lambda *args: None,
    )
    envelope = SimpleNamespace(
        synthesis_request=bound_request, synthesis_policy=policy
    )

    with pytest.raises(ValueError, match="canonical @4 promotion family"):
        compiler._verify_candidate(candidate, envelope)


def test_p2_revision_drift_with_equivalent_authority_stays_current(tmp_path):
    from mechcad_harness.candidates import CandidateCurrentness

    state, manager, _, _, bound_request, policy, candidate = _at2_setup(tmp_path)
    manager.create_revision("PRJ-M12", state)

    assert (
        CandidateCurrentnessService(manager).evaluate(candidate, bound_request, policy)
        is CandidateCurrentness.CURRENT
    )


def test_p2_raw_rotation_preserves_semantic_request_candidate_chain(tmp_path):
    _, manager, store, _, _, _, candidate_a = _at2_setup(tmp_path)
    semantic_a = candidate_a.semantic_source_binding_hash
    request_a = candidate_a.synthesis_request_hash
    candidate_hash_a = candidate_a.candidate_hash
    _, _, bound_request_b, _, candidate_b = _at2_chain(
        tmp_path, manager, store, variant="B"
    )

    raw_a = "sha256:" + hashlib.sha256(_P2_STEP_VARIANTS["A"]).hexdigest()
    raw_b = "sha256:" + hashlib.sha256(_P2_STEP_VARIANTS["B"]).hexdigest()
    assert raw_a != raw_b
    assert bound_request_b.semantic_source_binding_hash == semantic_a
    assert bound_request_b.request_hash == request_a
    assert candidate_b.candidate_hash == candidate_hash_a
    assert candidate_b.source_binding != candidate_a.source_binding


def test_p2_publication_resolve_verifies_without_repair(tmp_path):
    state, manager, _, _, bound_request, policy, candidate = _at2_setup(tmp_path)
    publisher = CandidatePublicationService(tmp_path, "PRJ-M12", manager)
    publication = publisher.publish(candidate, bound_request, policy)
    resolved = publisher.resolve(publication.artifact.artifact_id)

    assert resolved.candidate == candidate

    payload_path = tmp_path / publication.artifact.relative_path
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["candidate"]["candidate_hash"] = "sha256:" + "f" * 64
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    payload_path.write_bytes(content)
    metadata_path = payload_path.parent / "metadata.json"
    metadata = json.loads(metadata_path.read_bytes())
    metadata["sha256"] = "sha256:" + hashlib.sha256(content).hexdigest()
    metadata["size_bytes"] = len(content)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(CandidateIntegrityError):
        publisher.resolve(publication.artifact.artifact_id)


def test_p2_publication_rejects_pending_candidate_at2(tmp_path):
    _, manager, _, _, bound_request, policy, candidate = _at2_setup(tmp_path)
    pending_candidate = candidate.model_copy(
        update={
            "semantic_source_binding_hash": "pending",
            "candidate_hash": "pending",
        }
    )

    with pytest.raises(CandidateIntegrityError):
        CandidatePublicationService(tmp_path, "PRJ-M12", manager).publish(
            pending_candidate, bound_request, policy
        )
