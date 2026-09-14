from __future__ import annotations

import pytest
from pydantic import ValidationError
import sys
from pathlib import Path

from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    TrustedSourceArtifact,
    _projection_from_mechanism,
)
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    CandidateCanonicalMultiJointEquivalence,
    CanonicalMultiJointM10Verification,
    CanonicalMultiJointM10VerificationService,
    compare_candidate_canonical_multi_joint_semantics,
    compile_canonical,
)
from mechcad_harness.candidates.promotion_models import CandidateMultiJointPromotionRequest
from test_m13_3_fresh_canonical_bridge import _canonical_reconstruction
from test_m13_3_promotion import _promotion_chain


def _fresh_canonical_verification(tmp_path):
    integration_path = str(Path(__file__).parents[1] / "integration")
    if integration_path not in sys.path:
        sys.path.insert(0, integration_path)
    from test_m13_3_candidate_m10_production import _application

    reconstruction = _canonical_reconstruction(tmp_path)
    store = ArtifactStore(
        tmp_path,
        project_id=reconstruction.project_id,
        run_id="f12-identity-test",
    )
    cad = CanonicalPhysicalCadCompiler(store).realize(reconstruction)
    application = _application(
        tmp_path,
        [],
        project_id=reconstruction.project_id,
        create_state=False,
    )
    return reconstruction, cad, application.canonical_multi_joint_m10_verification_service.execute(
        reconstruction, cad
    )


def test_task_16_public_symbols_exist():
    assert CandidateCanonicalMultiJointEquivalence is not None
    assert callable(compare_candidate_canonical_multi_joint_semantics)
    assert CanonicalMultiJointM10VerificationService is not None


def test_canonical_m10_verification_exposes_canonical_identity(tmp_path):
    reconstruction, cad, verification = _fresh_canonical_verification(tmp_path)
    mechanism = reconstruction.canonical_mechanism

    assert isinstance(verification, CanonicalMultiJointM10Verification)
    assert verification.project_id == reconstruction.project_id
    assert verification.revision == reconstruction.revision
    assert verification.state_hash == reconstruction.state_hash
    assert verification.mechanism_id == mechanism.id
    assert verification.mechanism_hash == mechanism.mechanism_hash
    assert verification.canonical_cad_realization_hash == cad.realization_hash
    assert verification.normalized_projection_hash == reconstruction.normalized_projection_hash
    assert verification.result.request_hash == verification.request.request_hash


@pytest.mark.parametrize(
    "field",
    (
        "project_id",
        "state_hash",
        "mechanism_id",
        "mechanism_hash",
        "canonical_cad_realization_hash",
        "normalized_projection_hash",
    ),
)
def test_canonical_m10_verification_rejects_blank_identity(field, tmp_path):
    _, _, verification = _fresh_canonical_verification(tmp_path)

    with pytest.raises(ValidationError):
        CanonicalMultiJointM10Verification.model_validate(
            verification.model_dump(mode="json") | {field: "   "}
        )


@pytest.mark.parametrize(
    "field",
    (
        "state_hash",
        "mechanism_hash",
        "canonical_cad_realization_hash",
        "normalized_projection_hash",
    ),
)
def test_canonical_m10_verification_rejects_malformed_identity_hash(field, tmp_path):
    _, _, verification = _fresh_canonical_verification(tmp_path)

    with pytest.raises(ValidationError):
        CanonicalMultiJointM10Verification.model_validate(
            verification.model_dump(mode="json") | {field: "sha256:not-a-hash"}
        )


def test_canonical_m10_verification_rejects_nonpositive_revision(tmp_path):
    _, _, verification = _fresh_canonical_verification(tmp_path)

    with pytest.raises(ValidationError):
        CanonicalMultiJointM10Verification.model_validate(
            verification.model_dump(mode="json") | {"revision": 0}
        )


def test_canonical_m10_verification_rejects_result_request_mismatch(tmp_path):
    _, _, verification = _fresh_canonical_verification(tmp_path)
    result = verification.result.model_copy(
        update={"request_hash": "sha256:" + "0" * 64}
    )

    with pytest.raises(ValidationError, match="request hash"):
        CanonicalMultiJointM10Verification(
            project_id=verification.project_id,
            revision=verification.revision,
            state_hash=verification.state_hash,
            mechanism_id=verification.mechanism_id,
            mechanism_hash=verification.mechanism_hash,
            canonical_cad_realization_hash=verification.canonical_cad_realization_hash,
            normalized_projection_hash=verification.normalized_projection_hash,
            request=verification.request,
            result=result,
        )


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
