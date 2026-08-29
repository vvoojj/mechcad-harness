from __future__ import annotations

import pytest

from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealizationRequest,
    CandidateGeometryFidelity,
    CandidatePlacementOrigin,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
    ComponentPropertySnapshot,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.candidates.cad_realization import CandidateCadRealizationService
from mechcad_harness.candidates.cad_realization import CandidateCadIntegrityError
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager, state_hash


def _fixture(tmp_path):
    state = DesignState(id="DES-M12-4", revision=1, requirements=[], constraints=[], interfaces=[], authoritative_parameters=[])
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    source = CandidateSourceBinding(
        project_id="PRJ-M12-4",
        source_revision=1,
        source_state_hash=state_hash(state),
        consumed_authority=(CandidateSourceReference(path="/id", value_hash="pending", authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT),),
    ).bound_to(state)
    properties = tuple(
        ComponentPropertySnapshot(
            key=key,
            availability=ComponentPropertyAvailability.AVAILABLE,
            normalized_value=value,
            canonical_unit="mm",
            source_identity="candidate:plate-dimensions@1",
            authority=ComponentPropertyAuthority.USER_DECLARED,
        )
        for key, value in (("geometry.length_mm", 40.0), ("geometry.width_mm", 30.0), ("geometry.thickness_mm", 5.0))
    )
    specification = ComponentSpecificationSnapshot(component_type="mount", source_identity="candidate:mount@1", properties=properties)
    physical = PhysicalComponentInstance(instance_id="mount", specification_hash=specification.specification_hash, role=PhysicalComponentRole.MOUNT_OR_SUPPORT)
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    synthesis_policy = CandidateSynthesisPolicy()
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=(specification,),
        realization=PhysicalMechanismRealization(components=(physical,)),
        generator_identity="m12-4-test-generator",
        generator_version="1",
    )
    plate = MountingPlateDesignSpec(part_id="cad_mount", plate_length_mm=40.0, plate_width_mm=30.0, plate_thickness_mm=5.0)
    origin = CandidatePlacementOrigin(
        authority="deterministic_derived_relation",
        input_identities=("candidate:/realization/components/mount",),
        derivation="fixed-home-placement@1",
        transform={"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
    )
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="mount",
        cad_instance_id="cad_mount",
        fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        representation_identity=cad_program_hash(compile_mounting_plate(plate)),
        geometry_definition_identities=tuple(property.property_hash for property in properties),
        placement=origin.transform,
        placement_origin=origin,
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=source,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("mount",),
        mappings=(mapping,),
    )
    service = CandidateCadRealizationService(workspace=tmp_path, project_id="PRJ-M12-4", state_manager=manager)
    return service, candidate, synthesis_request, synthesis_policy, request


def test_semantically_identical_candidate_cad_replays_have_identical_realization_identity(tmp_path):
    service, candidate, synthesis_request, synthesis_policy, request = _fixture(tmp_path)

    first = service.realize(candidate, synthesis_request, synthesis_policy, request)
    second = service.realize(candidate, synthesis_request, synthesis_policy, request)

    assert first == second
    assert first.realization is not None
    assert first.realization.realization_hash == second.realization.realization_hash
    assert first.outcome_hash == second.outcome_hash


def test_replay_does_not_accept_a_mapping_for_a_different_candidate(tmp_path):
    service, candidate, synthesis_request, synthesis_policy, request = _fixture(tmp_path)
    other = candidate.model_copy(update={"candidate_hash": "sha256:" + "1" * 64})
    forged_request = request.model_copy(update={"candidate_hash": other.candidate_hash, "request_hash": "pending"})

    from pytest import raises
    from mechcad_harness.candidates.cad_realization import CandidateCadIntegrityError

    with raises(CandidateCadIntegrityError):
        service.realize(other, synthesis_request, synthesis_policy, forged_request)


def test_candidate_cad_replay_rejects_tampered_placement_realization(tmp_path):
    service, candidate, synthesis_request, synthesis_policy, request = _fixture(tmp_path)
    baseline = service.realize(candidate, synthesis_request, synthesis_policy, request)
    assert baseline.realization is not None
    tampered_mapping = baseline.realization.mappings[0].model_copy(
        update={"placement": CadRigidTransform(x_mm=99.0), "mapping_hash": "pending"}
    )
    tampered = baseline.realization.model_copy(
        update={"mappings": (tampered_mapping,), "realization_hash": "pending"}
    )

    with pytest.raises(CandidateCadIntegrityError, match="placement"):
        service.validate_realization(candidate, request, tampered)
