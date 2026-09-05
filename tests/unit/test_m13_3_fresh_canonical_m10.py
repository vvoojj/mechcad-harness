from __future__ import annotations

import pytest

from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    TrustedSourceArtifact,
    _projection_from_mechanism,
)
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    CandidateCanonicalMultiJointEquivalence,
    CanonicalMultiJointM10VerificationService,
    compare_candidate_canonical_multi_joint_semantics,
    compile_canonical,
)
from mechcad_harness.candidates.promotion_models import CandidateMultiJointPromotionRequest
from test_m13_3_fresh_canonical_bridge import _canonical_reconstruction
from test_m13_3_promotion import _promotion_chain


def test_task_16_public_symbols_exist():
    assert CandidateCanonicalMultiJointEquivalence is not None
    assert callable(compare_candidate_canonical_multi_joint_semantics)
    assert CanonicalMultiJointM10VerificationService is not None


def test_equivalence_rejects_non_bridge_inputs():
    with pytest.raises((TypeError, ValueError)):
        compare_candidate_canonical_multi_joint_semantics(object(), object())


def test_multi_joint_promotion_preserves_generated_placement_authority(tmp_path):
    _, _, candidate_bridge, _, _, request, _, compiler = _promotion_chain(tmp_path)
    state = compiler.state_manager.load_current_state(request.project_id)
    compilation = compiler.compile_multi_joint(state, request)
    mechanism = compilation.canonical_mechanism

    assert mechanism.generated_placement_derivations
    assert {
        derivation.target_canonical_instance_id
        for derivation in mechanism.generated_placement_derivations
    } == {"PM-M13-3:shaft-a", "PM-M13-3:hub-a"}
    candidate_hub = next(
        body for body in candidate_bridge.model.bodies if body.body_id == "physical-link"
    )
    assert next(
        member.reference_to_member_home.z_mm
        for member in candidate_hub.members
        if member.member_instance_id == "cad-hub-a"
    ) == 2.0
    assert request.placement_derivations_hash == request.multi_joint_request.placement_derivations_hash


def test_fresh_canonical_bridge_replays_generated_placement_offset(tmp_path):
    reconstruction = _canonical_reconstruction(tmp_path)
    store = ArtifactStore(
        tmp_path,
        project_id=reconstruction.project_id,
        run_id="task-16-placement-replay",
    )
    trusted_sources = tuple(
        TrustedSourceArtifact.from_artifact(
            store.read_verified_in_project(
                specification.geometry_source.artifact_id,
                expected_hash=specification.geometry_source.artifact_hash,
            )[0]
        )
        for specification in reconstruction.canonical_mechanism.component_specifications
        if specification.geometry_source is not None
    )
    fresh_reconstruction = CanonicalMechanismReconstruction(
        project_id=reconstruction.project_id,
        revision=reconstruction.revision,
        state_hash=reconstruction.state_hash,
        canonical_mechanism=reconstruction.canonical_mechanism,
        trusted_source_references=trusted_sources,
        normalized_projection_hash=_projection_from_mechanism(
            reconstruction.canonical_mechanism
        ).projection_hash,
    )
    fresh = CanonicalPhysicalCadCompiler(store).realize(fresh_reconstruction)
    bridge = compile_canonical(fresh_reconstruction, fresh)

    hub = next(
        body for body in bridge.model.bodies if body.body_id == "physical-link"
    )
    hub_offset = next(
        member.reference_to_member_home.z_mm
        for member in hub.members
        if member.member_instance_id.endswith("hub-a-664fc5912ebd")
    )
    assert hub_offset == 2.0


def test_multi_joint_promotion_rejects_substituted_placement_derivation_set(tmp_path):
    _, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)
    original = next(
        derivation
        for derivation in request.generated_placement_derivations
        if derivation.derivation_id == "place-hub"
    )
    changed_input = original.inputs[0].model_copy(
        update={"value": 3.0, "value_hash": "pending", "input_hash": "pending"}
    )
    changed = original.model_copy(
        update={"inputs": (changed_input,), "derivation_hash": "pending"}
    )
    forged = request.model_copy(
        update={
            "generated_placement_derivations": tuple(
                changed
                if derivation.derivation_id == "place-hub"
                else derivation
                for derivation in request.generated_placement_derivations
            ),
            "placement_derivations_hash": "pending",
            "request_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="derivation|CAD|binding"):
        compiler.compile_multi_joint(
            compiler.state_manager.load_current_state(forged.project_id), forged
        )
