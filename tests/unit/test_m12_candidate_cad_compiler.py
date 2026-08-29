from __future__ import annotations

import hashlib

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.cad_compilation import MountingPlateDesignSpec, compile_mounting_plate
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealizationRequest,
    CandidateCadStageReason,
    CandidateCadStageStatus,
    CandidateDesignVariable,
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
from mechcad_harness.candidates.cad_realization import (
    CandidateCadIntegrityError,
    CandidateCadRealizationService,
)
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager, state_hash


def _state() -> DesignState:
    return DesignState(
        id="DES-M12-4",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def _source(state: DesignState, project_id: str = "PRJ-M12-4") -> CandidateSourceBinding:
    return CandidateSourceBinding(
        project_id=project_id,
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


def _plate_properties(length: float = 40.0, width: float = 30.0, thickness: float = 5.0):
    return tuple(
        ComponentPropertySnapshot(
            key=key,
            availability=ComponentPropertyAvailability.AVAILABLE,
            normalized_value=value,
            canonical_unit="mm",
            source_identity="candidate:plate-dimensions@1",
            authority=ComponentPropertyAuthority.USER_DECLARED,
        )
        for key, value in (
            ("geometry.length_mm", length),
            ("geometry.width_mm", width),
            ("geometry.thickness_mm", thickness),
        )
    )


def _candidate(
    state: DesignState,
    *,
    specification: ComponentSpecificationSnapshot,
    instance_id: str = "mount",
    role: PhysicalComponentRole = PhysicalComponentRole.MOUNT_OR_SUPPORT,
):
    source = _source(state)
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    synthesis_policy = CandidateSynthesisPolicy()
    instance = PhysicalComponentInstance(
        instance_id=instance_id,
        specification_hash=specification.specification_hash,
        role=role,
        interfaces=specification.interfaces,
    )
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=(specification,),
        realization=PhysicalMechanismRealization(components=(instance,)),
        generator_identity="m12-4-test-generator",
        generator_version="1",
    )
    return candidate, synthesis_request, synthesis_policy


def _origin() -> CandidatePlacementOrigin:
    transform = CadRigidTransform()
    return CandidatePlacementOrigin(
        authority="deterministic_derived_relation",
        input_identities=("candidate:/realization/components/mount",),
        derivation="fixed-home-placement@1",
        transform=transform,
    )


def _generated_request(candidate: MechanicalDesignCandidate, specification: ComponentSpecificationSnapshot):
    spec = MountingPlateDesignSpec(
        part_id="cad_mount",
        plate_length_mm=specification.properties[0].normalized_value,
        plate_width_mm=specification.properties[1].normalized_value,
        plate_thickness_mm=specification.properties[2].normalized_value,
    )
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="mount",
        cad_instance_id="cad_mount",
        fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        representation_identity=cad_program_hash(compile_mounting_plate(spec)),
        geometry_definition_identities=tuple(property.property_hash for property in specification.properties),
        placement=CadRigidTransform(),
        placement_origin=_origin(),
    )
    return CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("mount",),
        mappings=(mapping,),
    )


def _service(tmp_path, manager: StateManager) -> CandidateCadRealizationService:
    return CandidateCadRealizationService(
        workspace=tmp_path,
        project_id="PRJ-M12-4",
        state_manager=manager,
    )


def test_candidate_integrity_and_currentness_are_gates_before_cad_construction(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    request = _generated_request(candidate, specification)

    forged = candidate.model_copy(update={"candidate_hash": "sha256:" + "0" * 64})
    with pytest.raises(CandidateCadIntegrityError):
        _service(tmp_path, manager).realize(forged, synthesis_request, synthesis_policy, request)

    manager.create_revision("PRJ-M12-4", state.model_copy(update={"id": "DES-CHANGED"}))
    with pytest.raises(CandidateCadIntegrityError):
        _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)


def test_generated_plate_uses_only_candidate_bound_dimensions_and_no_placeholder(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(41.0, 31.0, 6.0),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    request = _generated_request(candidate, specification)

    outcome = _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)

    assert outcome.status is CandidateCadStageStatus.SUCCESS
    assert outcome.realization is not None
    assert len(outcome.realization.assembly.parts) == 1
    base = outcome.realization.assembly.parts[0].operations[0]
    assert (base.length_mm, base.width_mm, base.thickness_mm) == (41.0, 31.0, 6.0)
    assert not outcome.realization.assembly.imported_components
    assert all(instance.part_id != "placeholder" for instance in outcome.realization.assembly.instances)


def test_candidate_cad_rejects_foreign_manifest_identities(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(),
        interfaces=("mount",),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    baseline = _generated_request(candidate, specification)

    for field, identity in (
        ("design_variable_identities", "candidate:design-variable:foreign"),
        ("component_interface_identities", "candidate:component-interface:mount:foreign"),
    ):
        request = CandidateCadRealizationRequest(
            **baseline.model_dump(mode="python")
            | {field: (identity,), "request_hash": "pending"}
        )
        with pytest.raises(CandidateCadIntegrityError, match="identity"):
            _service(tmp_path, manager).realize(
                candidate, synthesis_request, synthesis_policy, request
            )


def test_candidate_cad_rejects_candidate_owned_but_unused_manifest_identities(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(),
        interfaces=("mount",),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    candidate = MechanicalDesignCandidate(
        **candidate.model_dump(mode="python")
        | {
            "design_variables": (CandidateDesignVariable(name="unused", value=1.0),),
            "candidate_hash": "pending",
        }
    )
    baseline = _generated_request(candidate, specification)
    for field, identity in (
        ("design_variable_identities", "candidate:design-variable:unused"),
        ("component_interface_identities", "candidate:component-interface:mount:mount"),
    ):
        request = CandidateCadRealizationRequest(
            **baseline.model_dump(mode="python")
            | {field: (identity,), "request_hash": "pending"}
        )
        with pytest.raises(CandidateCadIntegrityError, match="declared realization inputs"):
            _service(tmp_path, manager).realize(
                candidate, synthesis_request, synthesis_policy, request
            )


def test_candidate_cad_rejects_candidate_owned_placement_identity_for_another_mapping(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    candidate = MechanicalDesignCandidate(
        **candidate.model_dump(mode="python")
        | {
            "design_variables": (CandidateDesignVariable(name="other.placement.x_mm", value=0.0),),
            "candidate_hash": "pending",
        }
    )
    baseline = _generated_request(candidate, specification)
    mapping = baseline.mappings[0].model_copy(
        update={
            "placement_origin": CandidatePlacementOrigin(
                authority="candidate_design_variable",
                input_identities=("candidate:design-variable:other.placement.x_mm",),
                derivation="foreign-component-placement@1",
                transform=CadRigidTransform(),
            ),
            "mapping_hash": "pending",
        }
    )
    request = CandidateCadRealizationRequest.model_validate(
        baseline.model_dump(mode="json")
        | {
            "mappings": (mapping,),
            "design_variable_identities": ("candidate:design-variable:other.placement.x_mm",),
            "request_hash": "pending",
        }
    )

    with pytest.raises(CandidateCadIntegrityError, match="placement|identity|mapping"):
        _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)


def test_missing_supported_geometry_is_unresolved_without_fabricated_realization(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("mount",),
        mappings=(
            CandidateCadInstanceMapping(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id="mount",
                cad_instance_id="cad_mount",
                fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
                representation_identity="sha256:" + "1" * 64,
                geometry_definition_identities=("candidate:/missing-geometry",),
                placement=CadRigidTransform(),
                placement_origin=_origin(),
            ),
        ),
    )

    outcome = _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)

    assert outcome.status is CandidateCadStageStatus.UNRESOLVED
    assert CandidateCadStageReason.GEOMETRY_UNAVAILABLE in outcome.reasons
    assert outcome.realization is None
    assert outcome.realization_hash is None


def test_changed_request_placement_is_rejected_without_candidate_change(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    baseline = _generated_request(candidate, specification)
    changed_mapping = baseline.mappings[0].model_copy(
        update={
            "placement": CadRigidTransform(x_mm=12.0),
            "placement_origin": CandidatePlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=("candidate:/realization/components/mount",),
                derivation="fixed-home-placement@1",
                transform=CadRigidTransform(x_mm=12.0),
            ),
            "mapping_hash": "pending",
        }
    )
    request = baseline.model_copy(update={"mappings": (changed_mapping,), "request_hash": "pending"})

    outcome = _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)
    assert outcome.status is CandidateCadStageStatus.UNRESOLVED
    assert outcome.reasons == (CandidateCadStageReason.INVALID_PLACEMENT_PROVENANCE,)


def test_foreign_placement_provenance_is_rejected_even_when_transform_matches(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    baseline = _generated_request(candidate, specification)
    foreign_mapping = baseline.mappings[0].model_copy(
        update={
            "placement_origin": CandidatePlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=("candidate:placement:foreign",),
                derivation="fixed-home-placement@1",
                transform=CadRigidTransform(),
            ),
            "mapping_hash": "pending",
        }
    )
    request = CandidateCadRealizationRequest.model_validate(
        baseline.model_dump(mode="python")
        | {"mappings": (foreign_mapping,), "request_hash": "pending"}
    )

    with pytest.raises(CandidateCadIntegrityError, match="placement"):
        _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)


def test_fresh_trusted_step_resolution_binds_exact_content_and_preserves_imported_component(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    content = b"trusted multi-shape STEP bytes"
    store = ArtifactStore(tmp_path, project_id="PRJ-M12-4", run_id="INPUT")
    artifact = store.publish(
        "ART-source",
        ArtifactType.STEP,
        "source.step",
        content,
        "test-source",
        "1",
        state.revision,
        state_hash(state),
    )
    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="trusted:motor@1",
        geometry_source={
            "artifact_id": artifact.artifact_id,
            "artifact_hash": artifact.sha256,
            "source_identity": "trusted:motor@1",
        },
    )
    candidate, synthesis_request, synthesis_policy = _candidate(
        state,
        specification=specification,
        instance_id="motor",
        role=PhysicalComponentRole.ACTUATOR,
    )
    imported = ImportedCadComponent(
        component_id="cad_motor",
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
    )
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="motor",
        cad_instance_id="cad_motor",
        fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
        representation_identity=imported_component_hash(imported),
        source_geometry_identity=artifact.sha256,
        geometry_definition_identities=(artifact.artifact_id,),
        placement=CadRigidTransform(),
        placement_origin=CandidatePlacementOrigin(
            authority="deterministic_derived_relation",
            input_identities=(artifact.artifact_id,),
            derivation="fixed-home-placement@1",
            transform=CadRigidTransform(),
        ),
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("motor",),
        mappings=(mapping,),
    )

    outcome = _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)

    assert outcome.status is CandidateCadStageStatus.SUCCESS
    assert outcome.realization is not None
    assert outcome.realization.verified_source_content_identities == (artifact.sha256,)
    assert outcome.realization.assembly.imported_components[0].artifact_id == artifact.artifact_id
    assert outcome.realization.assembly.imported_components[0].artifact_hash == artifact.sha256
    assert outcome.realization.assembly.parts == ()
    assert outcome.realization.assembly.imported_components == (imported,)


def test_trusted_mapping_rejects_unused_geometry_identity_for_the_component(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12-4", run_id="INPUT")
    artifact = store.publish(
        "ART-source",
        ArtifactType.STEP,
        "source.step",
        b"trusted geometry",
        "test-source",
        "1",
        state.revision,
        state_hash(state),
    )
    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="trusted:motor@1",
        geometry_source={
            "artifact_id": artifact.artifact_id,
            "artifact_hash": artifact.sha256,
            "source_identity": "trusted:motor@1",
        },
    )
    candidate, synthesis_request, synthesis_policy = _candidate(
        state,
        specification=specification,
        instance_id="motor",
        role=PhysicalComponentRole.ACTUATOR,
    )
    imported = ImportedCadComponent(
        component_id="cad_motor",
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
    )
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="motor",
        cad_instance_id="cad_motor",
        fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
        representation_identity=imported_component_hash(imported),
        source_geometry_identity=artifact.sha256,
        geometry_definition_identities=(artifact.artifact_id, "candidate:geometry:foreign"),
        placement=CadRigidTransform(),
        placement_origin=CandidatePlacementOrigin(
            authority="deterministic_derived_relation",
            input_identities=(artifact.artifact_id,),
            derivation="fixed-home-placement@1",
            transform=CadRigidTransform(),
        ),
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("motor",),
        mappings=(mapping,),
    )

    with pytest.raises(CandidateCadIntegrityError, match="geometry|identity"):
        _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)


def test_trusted_source_never_automatically_downgrades_to_bounded_geometry(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12-4", run_id="INPUT")
    artifact = store.publish(
        "ART-source",
        ArtifactType.STEP,
        "source.step",
        b"trusted source",
        "test-source",
        "1",
        1,
        state_hash(state),
    )
    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="trusted:motor@1",
        geometry_source={
            "artifact_id": artifact.artifact_id,
            "artifact_hash": artifact.sha256,
            "source_identity": "trusted:motor@1",
        },
    )
    candidate, synthesis_request, synthesis_policy = _candidate(
        state, specification=specification, instance_id="motor", role=PhysicalComponentRole.ACTUATOR
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("motor",),
        mappings=(
            CandidateCadInstanceMapping(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id="motor",
                cad_instance_id="cad_motor",
                fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
                representation_identity="sha256:" + "1" * 64,
                geometry_definition_identities=(artifact.artifact_id,),
                placement=CadRigidTransform(),
                placement_origin=CandidatePlacementOrigin(
                    authority="deterministic_derived_relation",
                    input_identities=(artifact.artifact_id,),
                    derivation="fixed-home-placement@1",
                    transform=CadRigidTransform(),
                ),
            ),
        ),
    )

    outcome = _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)

    assert outcome.status is CandidateCadStageStatus.UNRESOLVED
    assert outcome.reasons == (CandidateCadStageReason.UNSUPPORTED_REPRESENTATION,)
    assert outcome.realization is None


def test_success_preserves_every_physical_and_cad_instance_identity_in_one_assembly(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    specification = ComponentSpecificationSnapshot(
        component_type="mount",
        source_identity="candidate:mount@1",
        properties=_plate_properties(),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification)
    request = _generated_request(candidate, specification)

    outcome = _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)

    assert outcome.realization is not None
    assert {
        mapping.physical_instance_id: mapping.cad_instance_id
        for mapping in outcome.realization.mappings
    } == {"mount": "cad_mount"}
    assert {
        instance.instance_id: instance.part_id
        for instance in outcome.realization.assembly.instances
    } == {"cad_mount": "cad_mount"}


def test_source_byte_mutation_and_artifact_substitution_fail_closed(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12-4", run_id="INPUT")
    artifact = store.publish(
        "ART-source",
        ArtifactType.STEP,
        "source.step",
        b"original",
        "test-source",
        "1",
        state.revision,
        state_hash(state),
    )
    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="trusted:motor@1",
        geometry_source={
            "artifact_id": artifact.artifact_id,
            "artifact_hash": artifact.sha256,
            "source_identity": "trusted:motor@1",
        },
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification=specification, instance_id="motor", role=PhysicalComponentRole.ACTUATOR)
    imported = ImportedCadComponent(component_id="cad_motor", artifact_id=artifact.artifact_id, artifact_hash=artifact.sha256, source_revision=1, source_state_hash=state_hash(state))
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="motor",
        cad_instance_id="cad_motor",
        fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
        representation_identity=imported_component_hash(imported),
        source_geometry_identity=artifact.sha256,
        geometry_definition_identities=(artifact.artifact_id,),
        placement=CadRigidTransform(),
        placement_origin=CandidatePlacementOrigin(
            authority="deterministic_derived_relation",
            input_identities=(artifact.artifact_id,),
            derivation="fixed-home-placement@1",
            transform=CadRigidTransform(),
        ),
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("motor",),
        mappings=(mapping,),
    )
    baseline = _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)
    assert baseline.realization is not None
    path = tmp_path / artifact.relative_path
    path.write_bytes(b"mutated")

    with pytest.raises(CandidateCadIntegrityError, match="artifact"):
        _service(tmp_path, manager).validate_realization(candidate, request, baseline.realization)

    assert hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256.removeprefix("sha256:")


def test_candidate_source_artifact_substitution_fails_closed(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12-4", run_id="INPUT")
    first = store.publish("ART-first", ArtifactType.STEP, "first.step", b"first", "test-source", "1", 1, state_hash(state))
    second = store.publish("ART-second", ArtifactType.STEP, "second.step", b"second", "test-source", "1", 1, state_hash(state))
    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="trusted:motor@1",
        geometry_source={
            "artifact_id": first.artifact_id,
            "artifact_hash": first.sha256,
            "source_identity": "trusted:motor@1",
        },
    )
    candidate, synthesis_request, synthesis_policy = _candidate(
        state, specification=specification, instance_id="motor", role=PhysicalComponentRole.ACTUATOR
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("motor",),
        mappings=(
            CandidateCadInstanceMapping(
                candidate_hash=candidate.candidate_hash,
                physical_instance_id="motor",
                cad_instance_id="cad_motor",
                fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                representation_identity="sha256:" + "2" * 64,
                source_geometry_identity=second.sha256,
                geometry_definition_identities=(second.artifact_id,),
                placement=CadRigidTransform(),
                placement_origin=CandidatePlacementOrigin(
                    authority="deterministic_derived_relation",
                    input_identities=(second.artifact_id,),
                    derivation="fixed-home-placement@1",
                    transform=CadRigidTransform(),
                ),
            ),
        ),
    )

    with pytest.raises(CandidateCadIntegrityError, match="source geometry identity"):
        _service(tmp_path, manager).realize(candidate, synthesis_request, synthesis_policy, request)
