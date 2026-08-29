from __future__ import annotations

import pytest
from pydantic import ValidationError

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import acceptance_program, cad_program_hash
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealization,
    CandidateCadRealizationRequest,
    CandidateCadStageOutcome,
    CandidateCadStageReason,
    CandidateCadStageStatus,
    CandidateGeometryFidelity,
    CandidatePlacementOrigin,
)
from mechcad_harness.candidates.models import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.models import DesignState
from mechcad_harness.state import state_hash
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash


def _candidate(candidate_id: str = "candidate-a") -> MechanicalDesignCandidate:
    state = DesignState(
        id="DES-M12-4",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )
    source = CandidateSourceBinding(
        project_id="PRJ-M12-4",
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
    specification = ComponentSpecificationSnapshot(
        component_type="fixture",
        source_identity="local:fixture@1",
        interfaces=("mount",),
    )
    instance = PhysicalComponentInstance(
        instance_id=candidate_id,
        specification_hash=specification.specification_hash,
        role=PhysicalComponentRole.MOUNT_OR_SUPPORT,
        interfaces=("mount",),
    )
    realization = PhysicalMechanismRealization(components=(instance,))
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    synthesis_policy = CandidateSynthesisPolicy()
    return MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=(specification,),
        realization=realization,
        generator_identity="test-generator",
        generator_version="1",
    )


def _origin(transform: CadRigidTransform, input_id: str = "candidate:/mount") -> CandidatePlacementOrigin:
    return CandidatePlacementOrigin(
        authority="candidate_design_variable",
        input_identities=(input_id,),
        derivation="mount-frame@1",
        transform=transform,
    )


def _mapping(
    candidate: MechanicalDesignCandidate,
    *,
    cad_instance_id: str = "cad-mount",
    fidelity: CandidateGeometryFidelity = CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
    origin: CandidatePlacementOrigin | None = None,
) -> CandidateCadInstanceMapping:
    transform = CadRigidTransform(x_mm=12.0)
    imported = ImportedCadComponent(
        component_id=cad_instance_id,
        artifact_id="ART-source",
        artifact_hash="sha256:" + "2" * 64,
        source_revision=1,
        source_state_hash=candidate.source_binding.source_state_hash,
    )
    return CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id=candidate.realization.components[0].instance_id,
        cad_instance_id=cad_instance_id,
        fidelity=fidelity,
        representation_identity=(
            imported_component_hash(imported)
            if fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
            else cad_program_hash(acceptance_program())
        ),
        source_geometry_identity=(
            "sha256:" + "2" * 64
            if fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
            else None
        ),
        geometry_definition_identities=("candidate:/mount-size",),
        placement=transform,
        placement_origin=origin or _origin(transform),
    )


def _request(candidate: MechanicalDesignCandidate, mapping=None) -> CandidateCadRealizationRequest:
    return CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=tuple(
            instance.instance_id for instance in candidate.realization.components
        ),
        mappings=(mapping or _mapping(candidate),),
        design_variable_identities=("candidate:/mount-size",),
        component_interface_identities=("candidate:/mount-interface",),
    )


def _realization(
    candidate: MechanicalDesignCandidate,
    request: CandidateCadRealizationRequest,
    *,
    assembly: CadAssemblyProgram | None = None,
    mappings=None,
    verified_source_content_identities=(),
):
    if assembly is None:
        if request.mappings[0].fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY:
            imported = ImportedCadComponent(
                component_id="cad-mount",
                artifact_id="ART-source",
                artifact_hash="sha256:" + "2" * 64,
                source_revision=1,
                source_state_hash=candidate.source_binding.source_state_hash,
            )
            assembly = CadAssemblyProgram(
                assembly_id="candidate-assembly",
                imported_components=(imported,),
                instances=(
                    CadComponentInstance(
                        instance_id="cad-mount",
                        part_id="cad-mount",
                        placement=CadRigidTransform(x_mm=12.0),
                    ),
                ),
            )
        else:
            assembly = CadAssemblyProgram(
                assembly_id="candidate-assembly",
                parts=(acceptance_program(),),
                instances=(
                    CadComponentInstance(
                        instance_id="cad-mount",
                        part_id="M7A2ABracket",
                        placement=CadRigidTransform(x_mm=12.0),
                    ),
                ),
            )
    return CandidateCadRealization(
        candidate_hash=candidate.candidate_hash,
        request_hash=request.request_hash,
        mappings=mappings or request.mappings,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        verified_source_content_identities=verified_source_content_identities,
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        provider_identity="transient-freecad@1",
    )


def test_semantic_records_have_deterministic_sha256_identities_and_round_trip():
    candidate = _candidate()
    first = _request(candidate)
    second = _request(candidate)
    assert first.request_hash == second.request_hash

    realization = _realization(candidate, first)
    outcome = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.SUCCESS,
        realization=realization,
    )
    assert realization.realization_hash.startswith("sha256:")
    assert outcome.outcome_hash.startswith("sha256:")
    assert CandidateCadRealizationRequest.model_validate(first.model_dump(mode="json")) == first
    assert CandidateCadRealization.model_validate(realization.model_dump(mode="json")) == realization
    assert CandidateCadStageOutcome.model_validate(outcome.model_dump(mode="json")) == outcome


def test_candidate_mapping_inputs_and_placement_provenance_change_identity():
    candidate = _candidate()
    baseline = _request(candidate)
    changed_candidate_hash = "sha256:" + "3" * 64
    changed_candidate_mapping = _mapping(candidate).model_copy(
        update={"candidate_hash": changed_candidate_hash, "mapping_hash": "pending"}
    )
    changed_candidate = CandidateCadRealizationRequest(
        **baseline.model_dump(mode="python")
        | {
            "candidate_hash": changed_candidate_hash,
            "mappings": (changed_candidate_mapping,),
            "request_hash": "pending",
        }
    )
    changed_mapping = _request(
        candidate,
        _mapping(candidate, origin=_origin(CadRigidTransform(x_mm=12.0), "candidate:/other")),
    )
    changed_fidelity = _request(
        candidate,
        _mapping(candidate, fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),
    )
    assert changed_candidate.request_hash != baseline.request_hash
    assert changed_mapping.request_hash != baseline.request_hash
    assert changed_fidelity.request_hash != baseline.request_hash


def test_realization_requires_assembly_instances_to_match_cad_mappings():
    candidate = _candidate()
    request = _request(candidate, _mapping(candidate, cad_instance_id="cad-other"))
    with pytest.raises(ValueError, match="assembly.*mapping"):
        _realization(candidate, request)


def test_realization_rejects_mapping_representation_that_does_not_match_assembly_component():
    candidate = _candidate()
    request = _request(candidate)
    mapping = request.mappings[0].model_copy(
        update={"representation_identity": "sha256:" + "9" * 64, "mapping_hash": "pending"}
    )
    with pytest.raises(ValueError, match="representation"):
        CandidateCadRealization.model_validate(
            _realization(candidate, request).model_dump(mode="python")
            | {"mappings": (mapping,), "realization_hash": "pending"}
        )


def test_trusted_realization_requires_verified_source_content_identity():
    candidate = _candidate()
    mapping = _mapping(candidate, fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY)
    request = _request(candidate, mapping)
    with pytest.raises(ValueError, match="verified source content"):
        _realization(candidate, request)
    with pytest.raises(ValueError, match="source geometry identity"):
        _realization(
            candidate,
            request,
            verified_source_content_identities=("sha256:" + "3" * 64,),
        )
    realization = _realization(
        candidate,
        request,
        verified_source_content_identities=("sha256:" + "2" * 64,),
    )
    assert realization.verified_source_content_identities == ("sha256:" + "2" * 64,)


def test_verified_source_content_identities_bind_one_to_one_to_trusted_mappings():
    candidate = _candidate()
    request = _request(
        candidate,
        _mapping(candidate, fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),
    )
    with pytest.raises(ValueError, match="one-to-one"):
        _realization(
            candidate,
            request,
            verified_source_content_identities=(
                "sha256:" + "2" * 64,
                "sha256:" + "2" * 64,
            ),
        )


def test_bounded_realization_cannot_claim_verified_source_content():
    candidate = _candidate()
    request = _request(candidate)
    with pytest.raises(ValueError, match="bounded"):
        _realization(
            candidate,
            request,
            verified_source_content_identities=("sha256:" + "2" * 64,),
        )


def test_explicit_pending_origin_hash_is_resolved_deterministically():
    transform = CadRigidTransform(x_mm=12.0)
    origin = CandidatePlacementOrigin(
        authority="candidate_design_variable",
        input_identities=("candidate:/mount",),
        derivation="mount-frame@1",
        transform=transform,
        origin_hash="pending",
    )
    assert origin.origin_hash == _origin(transform).origin_hash


def test_cad_stage_reason_must_match_stage_status():
    with pytest.raises(ValueError, match="prior stage"):
        CandidateCadStageOutcome(
            status=CandidateCadStageStatus.UNRESOLVED,
            reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,),
        )
    with pytest.raises(ValueError, match="prior-stage reason"):
        CandidateCadStageOutcome(
            status=CandidateCadStageStatus.NOT_REACHED,
            reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
        )
    with pytest.raises(ValueError, match="prior-stage reason"):
        CandidateCadStageOutcome(
            status=CandidateCadStageStatus.NOT_REACHED,
            reasons=(
                CandidateCadStageReason.PRIOR_STAGE_FAILED,
                CandidateCadStageReason.UNSUPPORTED_REPRESENTATION,
            ),
        )


def test_required_cad_strings_reject_whitespace_only_values():
    candidate = _candidate()
    with pytest.raises(ValidationError):
        CandidatePlacementOrigin(
            authority="candidate_design_variable",
            input_identities=("candidate:/mount",),
            derivation=" ",
            transform=CadRigidTransform(x_mm=12.0),
        )

    mapping_data = _mapping(candidate).model_dump(mode="python")
    mapping_data.update(physical_instance_id=" ", mapping_hash="pending")
    with pytest.raises(ValidationError):
        CandidateCadInstanceMapping(**mapping_data)

    request_data = _request(candidate).model_dump(mode="python")
    request_data.update(representation_policy_version=" ", request_hash="pending")
    with pytest.raises(ValidationError):
        CandidateCadRealizationRequest(**request_data)

    realization_data = _realization(candidate, _request(candidate)).model_dump(mode="python")
    realization_data.update(provider_identity=" ", realization_hash="pending")
    with pytest.raises(ValidationError):
        CandidateCadRealization(**realization_data)


def test_realization_rejects_duplicate_cad_instance_ids():
    candidate = _candidate()
    first = _mapping(candidate)
    second = first.model_copy(
        update={
            "physical_instance_id": "physical-other",
            "mapping_hash": "pending",
        }
    )
    request = _request(candidate)
    with pytest.raises(ValueError, match="CAD instance mappings must be unique"):
        _realization(candidate, request, mappings=(first, second))


def test_realization_rejects_changed_assembly_placement():
    candidate = _candidate()
    request = _request(candidate)
    changed_assembly = CadAssemblyProgram(
        assembly_id="candidate-assembly",
        parts=(acceptance_program(),),
        instances=(
            CadComponentInstance(
                instance_id="cad-mount",
                part_id="M7A2ABracket",
                placement=CadRigidTransform(x_mm=13.0),
            ),
        ),
    )
    with pytest.raises(ValueError, match="placement"):
        _realization(candidate, request, assembly=changed_assembly)


def test_request_requires_complete_unique_candidate_and_cad_instance_mapping():
    candidate = _candidate()
    mapping = _mapping(candidate)
    with pytest.raises(ValueError, match="candidate physical instance"):
        CandidateCadRealizationRequest(
            candidate_hash=candidate.candidate_hash,
            source_binding=candidate.source_binding,
            representation_policy_version="candidate-cad-policy@1",
            compiler_identity="candidate-cad-compiler",
            compiler_version="1",
            candidate_instance_ids=("different-instance",),
            mappings=(mapping,),
            design_variable_identities=("candidate:/mount-size",),
            component_interface_identities=("candidate:/mount-interface",),
        )

    with pytest.raises(ValueError, match="unique"):
        CandidateCadRealizationRequest(
            **_request(candidate).model_dump(mode="python")
            | {"mappings": (mapping, mapping), "request_hash": "pending"}
        )


def test_mapping_cannot_bind_a_different_candidate_and_direct_transform_is_unproven():
    candidate_a = _candidate("physical-a")
    candidate_b = _candidate("physical-b")
    foreign_mapping = _mapping(candidate_b)
    with pytest.raises(ValueError, match="candidate"):
        CandidateCadRealizationRequest(
            candidate_hash=candidate_a.candidate_hash,
            source_binding=candidate_a.source_binding,
            representation_policy_version="candidate-cad-policy@1",
            compiler_identity="candidate-cad-compiler",
            compiler_version="1",
            candidate_instance_ids=("physical-a",),
            mappings=(foreign_mapping,),
            design_variable_identities=("candidate:/mount-size",),
            component_interface_identities=("candidate:/mount-interface",),
        )

    with pytest.raises(ValueError, match="input_identities"):
        CandidateCadInstanceMapping(
            candidate_hash=candidate_a.candidate_hash,
            physical_instance_id="physical-a",
            cad_instance_id="cad-mount",
            fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
            representation_identity="sha256:" + "1" * 64,
            geometry_definition_identities=("candidate:/mount-size",),
            placement=CadRigidTransform(x_mm=12.0),
            placement_origin=CandidatePlacementOrigin(
                authority="candidate_design_variable",
                input_identities=(),
                derivation="mount-frame@1",
                transform=CadRigidTransform(x_mm=12.0),
            ),
        )


def test_source_geometry_and_bounded_representation_are_explicitly_distinct():
    candidate = _candidate()
    bounded = _mapping(candidate)
    trusted = _mapping(candidate, fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY)
    assert bounded.fidelity is not trusted.fidelity
    assert bounded.source_geometry_identity is None
    assert trusted.source_geometry_identity is not None


def test_stage_outcomes_require_exactly_one_realization_only_for_success():
    candidate = _candidate()
    request = _request(candidate)
    realization = _realization(candidate, request)
    success = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.SUCCESS,
        realization=realization,
    )
    assert success.realization_hash == realization.realization_hash

    unresolved = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.UNRESOLVED,
        reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
    )
    not_reached = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.NOT_REACHED,
        reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,),
    )
    assert unresolved.realization is None
    assert unresolved.realization_hash is None
    assert not_reached.realization is None
    assert not_reached.realization_hash is None
    with pytest.raises(ValueError, match="realization"):
        CandidateCadStageOutcome(
            status=CandidateCadStageStatus.SUCCESS,
            reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
        )
    with pytest.raises(ValueError, match="reason"):
        CandidateCadStageOutcome(status=CandidateCadStageStatus.UNRESOLVED)


def test_frozen_extra_forbid_and_fake_hashes_reject():
    candidate = _candidate()
    request = _request(candidate)
    with pytest.raises(ValidationError):
        CandidateCadRealizationRequest(
            **request.model_dump(mode="python") | {"unexpected": "field"}
        )
    with pytest.raises(ValidationError):
        CandidateCadRealizationRequest(
            **request.model_dump(mode="python") | {"request_hash": "sha256:" + "0" * 64}
        )
    with pytest.raises(ValidationError):
        request.compiler_version = "forged"
