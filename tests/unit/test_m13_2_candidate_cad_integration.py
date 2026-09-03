from __future__ import annotations

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import CadAssemblyProgram, CadComponentInstance, CadRigidTransform, assembly_hash
from mechcad_harness.cad_program import acceptance_program, cad_program_hash
from mechcad_harness.generated_part_cad import compile_generated_part
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealization,
    CandidateCadRealizationRequest,
    CandidateCadStageOutcome,
    CandidateCadStageReason,
    CandidateCadStageStatus,
    CandidateDesignVariable,
    CandidateGeometryFidelity,
    CandidatePlacementOrigin,
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
    ComponentPropertySnapshot,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
    ComponentSpecificationSnapshot,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.candidates.cad_realization import (
    CandidateCadIntegrityError,
    CandidateCadRealizationService,
)
from mechcad_harness.candidates.evaluation import _validate_cad_inputs
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.models import (
    CylindricalHubSpecification,
    GeneratedPlacementDerivation,
    GeneratedAuthorityInput,
    GeneratedAuthorityView,
    GeneratedPartFieldBinding,
    compose_poses,
    place_generated_target,
    pose_from_interface,
    SolidCircularShaftSpecification,
    DesignState,
    generated_geometry_definition_identities,
    placement_derivations_hash,
    selection_hash,
    value_hash,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    RotationalShaftInterface,
    SuppliedComponentInterfaceDefinition,
    SuppliedInterfaceTransformRole,
)
from mechcad_harness.state import StateManager, state_hash
from test_m13_geometry_materialization import _interface_fact


def _state() -> DesignState:
    return DesignState(
        id="DES-M13-2-T7",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def _source(state: DesignState) -> CandidateSourceBinding:
    return CandidateSourceBinding(
        project_id="PRJ-M13-2-T7",
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


def _selection_input(input_id: str, value: float) -> GeneratedAuthorityInput:
    return GeneratedAuthorityInput(
        input_id=input_id,
        role="dimension",
        source_kind="design_selection",
        locator={
            "name_form": "component_scoped",
            "selection_key": input_id,
            "selection_hash": selection_hash("component_scoped", input_id, value),
        },
        value=value,
        value_hash=value_hash(value),
    )


def _direct(slot: str, input_id: str, value: float) -> GeneratedPartFieldBinding:
    return GeneratedPartFieldBinding(
        field_slot=slot,
        source={"input_id": input_id},
        field_value_hash=value_hash(value),
    )


def _shaft_spec() -> ComponentSpecificationSnapshot:
    shaft = SolidCircularShaftSpecification(
        generated_part_id="shaft-definition",
        diameter_mm=12.5,
        length_mm=40.0,
        inputs=(_selection_input("diameter", 12.5), _selection_input("length", 40.0)),
        field_bindings=(
            _direct("shaft.diameter_mm", "diameter", 12.5),
            _direct("shaft.length_mm", "length", 40.0),
        ),
    )
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@3",
        component_type="shaft",
        source_identity="generated:shaft-definition",
        generated_part=shaft,
        interfaces=shaft.active_interface_ids,
    )


def _property_shaft_spec(specification_id: str, diameter: float, length: float) -> ComponentSpecificationSnapshot:
    diameter_property = ComponentPropertySnapshot(
        key="shaft-diameter",
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_value=diameter,
        canonical_unit="mm",
        source_identity=f"property:{specification_id}:diameter",
        authority=ComponentPropertyAuthority.MEASURED_LOCAL,
    )
    length_property = ComponentPropertySnapshot(
        key="shaft-length",
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_value=length,
        canonical_unit="mm",
        source_identity=f"property:{specification_id}:length",
        authority=ComponentPropertyAuthority.MEASURED_LOCAL,
    )
    generated = SolidCircularShaftSpecification(
        generated_part_id=specification_id,
        diameter_mm=diameter,
        length_mm=length,
        inputs=(
            GeneratedAuthorityInput(
                input_id="diameter",
                role="dimension",
                source_kind="component_property",
                locator={"property_key": "shaft-diameter"},
                value=diameter,
                value_hash=value_hash(diameter),
            ),
            GeneratedAuthorityInput(
                input_id="length",
                role="dimension",
                source_kind="component_property",
                locator={"property_key": "shaft-length"},
                value=length,
                value_hash=value_hash(length),
            ),
        ),
        field_bindings=(
            _direct("shaft.diameter_mm", "diameter", diameter),
            _direct("shaft.length_mm", "length", length),
        ),
    )
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@3",
        component_type="shaft",
        source_identity=f"generated:{specification_id}",
        properties=(diameter_property, length_property),
        generated_part=generated,
        interfaces=generated.active_interface_ids,
    )
def _candidate(
    state: DesignState,
    specification: ComponentSpecificationSnapshot,
    instance_ids: tuple[str, ...] = ("shaft-a",),
):
    source = _source(state)
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    synthesis_policy = CandidateSynthesisPolicy()
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=(specification,),
        realization=PhysicalMechanismRealization(
            components=tuple(
                PhysicalComponentInstance(
                    instance_id=instance_id,
                    specification_hash=specification.specification_hash,
                    role=PhysicalComponentRole.SHAFT,
                    interfaces=specification.interfaces,
                )
                for instance_id in instance_ids
            )
        ),
        design_variables=(
            CandidateDesignVariable(name="diameter", value=12.5),
            CandidateDesignVariable(name="length", value=40.0),
        ),
        generator_identity="m13-2-task-7-test-generator",
        generator_version="1",
    )
    return candidate, synthesis_request, synthesis_policy


def _origin(instance_id: str) -> CandidatePlacementOrigin:
    return CandidatePlacementOrigin(
        authority="deterministic_derived_relation",
        input_identities=(f"candidate:/realization/components/{instance_id}",),
        derivation="fixed-home-placement@1",
        transform=CadRigidTransform(),
    )


def _request(candidate, specification, *, fidelity="exact_generated_geometry"):
    from mechcad_harness.generated_part_cad import compile_generated_part

    generated = specification.generated_part
    assert generated is not None
    compiled = compile_generated_part(
        generated,
        GeneratedAuthorityView(design_selections=tuple(candidate.design_variables)),
    )
    identities = generated_geometry_definition_identities(generated)
    mappings = tuple(
        CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id=instance_id,
            cad_instance_id=f"cad-{instance_id}",
            fidelity=fidelity,
            representation_identity=cad_program_hash(compiled.program),
            geometry_definition_identities=identities,
            placement=CadRigidTransform(),
            placement_origin=_origin(instance_id),
        )
        for instance_id in (
            component.instance_id for component in candidate.realization.components
        )
    )
    return CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=tuple(
            component.instance_id for component in candidate.realization.components
        ),
        mappings=mappings,
    )


def _placement_derivation(
    derivation_id="place-shaft",
    target_physical_instance_id="shaft-a",
    source_interface_id="motor-output",
    source_physical_instance_id="shaft-a",
    source_interface_hash=None,
    source_placement_ref=None,
    target_generated_interface_ref=None,
    inputs=(),
):
    return GeneratedPlacementDerivation(
        derivation_id=derivation_id,
        rule_id="coaxial-generated-placement@1",
        source_physical_instance_id=source_physical_instance_id,
        source_interface_ref={
            "interface_id": source_interface_id,
            "interface_hash": source_interface_hash or "sha256:" + "a" * 64,
        },
        source_placement_ref=source_placement_ref or {"kind": "design_variable_placement"},
        target_physical_instance_id=target_physical_instance_id,
        target_generated_interface_ref=target_generated_interface_ref or {
            "interface_id": f"{target_physical_instance_id}:shaft",
            "interface_hash": "sha256:" + "b" * 64,
        },
        inputs=inputs,
    )


_UNSET = object()


def _request_with_derivations(candidate, specification, derivations, derivations_hash=_UNSET):
    baseline = _request(candidate, specification)
    return CandidateCadRealizationRequest.model_validate(
        baseline.model_dump(mode="python")
        | {
            "schema_version": "candidate-cad-realization-request@2",
            "placement_derivations": derivations,
            "placement_derivations_hash": (
                placement_derivations_hash(derivations)
                if derivations_hash is _UNSET
                else derivations_hash
            ),
            "request_hash": "pending",
        }
    )


def _service(tmp_path, manager):
    return CandidateCadRealizationService(
        workspace=tmp_path,
        project_id="PRJ-M13-2-T7",
        state_manager=manager,
    )


def test_candidate_cad_request_v2_round_trips_and_binds_derivation_set():
    state = _state()
    specification = _shaft_spec()
    candidate, _, _ = _candidate(state, specification)
    derivation = _placement_derivation()
    request = _request_with_derivations(candidate, specification, (derivation,))

    assert request.placement_derivations_hash == placement_derivations_hash((derivation,))
    payload = request.model_dump(mode="json")
    assert payload["placement_derivations"] == [derivation.model_dump(mode="json")]
    assert CandidateCadRealizationRequest.model_validate(payload) == request


def test_candidate_cad_request_v1_rejects_derivations_and_omits_derived_fields():
    state = _state()
    specification = _shaft_spec()
    candidate, _, _ = _candidate(state, specification)
    derivation = _placement_derivation()
    request = _request(candidate, specification)

    payload = request.model_dump(mode="json")
    assert "placement_derivations" not in payload
    assert "placement_derivations_hash" not in payload
    assert CandidateCadRealizationRequest.model_validate(payload) == request

    with pytest.raises(ValueError):
        CandidateCadRealizationRequest.model_validate(
            request.model_dump(mode="python")
            | {"placement_derivations": (derivation,), "request_hash": "pending"}
        )
    with pytest.raises(ValueError):
        CandidateCadRealizationRequest.model_validate(
            request.model_dump(mode="python")
            | {
                "placement_derivations_hash": placement_derivations_hash(()),
                "request_hash": "pending",
            }
        )


def test_derivation_set_content_and_tuple_order_are_bound_to_request_identity():
    state = _state()
    specification = _shaft_spec()
    candidate, _, _ = _candidate(state, specification, ("shaft-a", "shaft-b"))
    first = _placement_derivation("place-a", "shaft-a")
    second = _placement_derivation("place-b", "shaft-b")
    ordered = _request_with_derivations(candidate, specification, (first, second))
    reversed_order = _request_with_derivations(candidate, specification, (second, first))
    substituted = _request_with_derivations(
        candidate,
        specification,
        (_placement_derivation("place-a", "shaft-a", "motor-other"), second),
    )

    assert ordered.placement_derivations_hash == reversed_order.placement_derivations_hash
    assert ordered.request_hash != reversed_order.request_hash
    assert ordered.placement_derivations_hash != substituted.placement_derivations_hash
    assert ordered.request_hash != substituted.request_hash


def test_candidate_cad_request_v2_requires_set_hash_and_unique_derivation_targets():
    state = _state()
    specification = _shaft_spec()
    candidate, _, _ = _candidate(state, specification, ("shaft-a", "shaft-b"))
    first = _placement_derivation("place-a", "shaft-a")

    with pytest.raises(ValueError, match="hash"):
        _request_with_derivations(
            candidate,
            specification,
            (first,),
            derivations_hash="sha256:" + "f" * 64,
        )
    with pytest.raises(ValueError, match="hash"):
        _request_with_derivations(
            candidate, specification, (first,), derivations_hash=None
        )

    duplicate_target = _placement_derivation("place-b", "shaft-a")
    with pytest.raises(ValueError, match="targets.*unique"):
        _request_with_derivations(
            candidate, specification, (first, duplicate_target)
        )

    duplicate_id = _placement_derivation("place-a", "shaft-b")
    with pytest.raises(ValueError, match="IDs.*unique"):
        _request_with_derivations(
            candidate,
            specification,
            (first, duplicate_id),
            derivations_hash=placement_derivations_hash(
                (first, _placement_derivation("place-b", "shaft-b"))
            ),
        )


def test_candidate_cad_request_v2_rejects_generated_mapping_without_derivation():
    state = _state()
    specification = _shaft_spec()
    candidate, _, _ = _candidate(state, specification)
    baseline = _request(candidate, specification)

    with pytest.raises(ValueError, match="derivation"):
        CandidateCadRealizationRequest.model_validate(
            baseline.model_dump(mode="python")
            | {
                "schema_version": "candidate-cad-realization-request@2",
                "placement_derivations": (),
                "placement_derivations_hash": placement_derivations_hash(()),
                "request_hash": "pending",
            }
        )


def test_candidate_cad_request_v2_rejects_ghost_derivation_endpoints():
    state = _state()
    specification = _shaft_spec()
    candidate, _, _ = _candidate(state, specification)

    for field, value in (
        ("source_physical_instance_id", "missing-source"),
        ("target_physical_instance_id", "missing-target"),
    ):
        derivation = _placement_derivation(**{field: value})
        with pytest.raises(ValueError, match="candidate instance|mapped physical"):
            _request_with_derivations(candidate, specification, (derivation,))


def test_realization_echoes_and_revalidates_v2_derivation_set_hash(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    request = _mixed_request(candidate, specifications, artifact)

    outcome = _service(tmp_path, manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.realization is not None
    realization = outcome.realization
    assert realization.placement_derivations_hash == request.placement_derivations_hash
    assert "placement_derivations_hash" in realization.model_dump(mode="json")
    assert CandidateCadRealization.model_validate(
        realization.model_dump(mode="json")
    ) == realization

    tampered = realization.model_copy(
        update={
            "placement_derivations_hash": "sha256:" + "f" * 64,
            "realization_hash": "pending",
        }
    )
    with pytest.raises(CandidateCadIntegrityError, match="replay mismatch"):
        _service(tmp_path, manager).validate_realization(candidate, request, tampered)


def test_generated_part_routes_to_generated_compiler_with_exact_fidelity(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    specification = _shaft_spec()
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification)
    request = _request(candidate, specification)

    outcome = _service(tmp_path, manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.status is CandidateCadStageStatus.SUCCESS
    assert outcome.realization is not None
    mapping = outcome.realization.mappings[0]
    assert mapping.fidelity.value == "exact_generated_geometry"
    assert mapping.source_geometry_identity is None
    assert mapping.representation_identity == cad_program_hash(
        outcome.realization.assembly.parts[0]
    )
    assert mapping.geometry_definition_identities == generated_geometry_definition_identities(
        specification.generated_part
    )


def test_generated_compiler_scopes_component_properties_to_target_specification():
    state = _state()
    target = _property_shaft_spec("target-shaft", 12.5, 40.0)
    foreign = _property_shaft_spec("foreign-shaft", 25.0, 80.0)
    candidate, _, _ = _candidate(state, target)
    candidate = candidate.model_copy(update={"component_specifications": (foreign, target)})
    service = CandidateCadRealizationService(
        workspace=".", project_id="PRJ-M13-2-T7", state_manager=None
    )

    view = service._candidate_authority_view(candidate, target)

    assert view.component_properties == target.properties
    assert tuple(view.design_selections) == tuple(candidate.design_variables)
    from mechcad_harness.generated_part_cad import compile_generated_part

    compilation = compile_generated_part(target.generated_part, view)
    assert compilation.program.operations[0].diameter_mm == 12.5


def test_generated_part_rejects_legacy_bounded_fidelity(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    specification = _shaft_spec()
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification)
    request = _request(
        candidate,
        specification,
        fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
    )

    outcome = _service(tmp_path, manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.status is CandidateCadStageStatus.UNRESOLVED
    assert outcome.reasons == (CandidateCadStageReason.UNSUPPORTED_REPRESENTATION,)


def test_evaluation_accepts_exact_generated_definition_identities(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    specification = _shaft_spec()
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification)
    request = _request(candidate, specification)
    outcome = _service(tmp_path, manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    _validate_cad_inputs(candidate, request, outcome)


def test_generated_mapping_requires_exact_shared_definition_identity_order(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    specification = _shaft_spec()
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification)
    baseline = _request(candidate, specification)
    mapping = CandidateCadInstanceMapping.model_validate(
        baseline.mappings[0].model_dump(mode="json")
        | {
            "geometry_definition_identities": tuple(
                reversed(baseline.mappings[0].geometry_definition_identities)
            ),
            "mapping_hash": "pending",
        }
    )
    request = CandidateCadRealizationRequest.model_validate(
        baseline.model_dump(mode="json")
        | {"mappings": (mapping.model_dump(mode="json"),), "request_hash": "pending"}
    )

    with pytest.raises(CandidateCadIntegrityError, match="definition identities"):
        _service(tmp_path, manager).realize(
            candidate, synthesis_request, synthesis_policy, request
        )


def test_same_generated_definition_is_reused_by_two_instances(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    specification = _shaft_spec()
    candidate, synthesis_request, synthesis_policy = _candidate(
        state, specification, ("shaft-a", "shaft-b")
    )
    request = _request(candidate, specification)

    outcome = _service(tmp_path, manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.status is CandidateCadStageStatus.SUCCESS
    assert outcome.realization is not None
    assert len(outcome.realization.assembly.parts) == 1
    instances = outcome.realization.assembly.instances
    assert tuple(instance.instance_id for instance in instances) == (
        "cad-shaft-a",
        "cad-shaft-b",
    )
    assert instances[0].part_id == instances[1].part_id
    assert instances[0].instance_id != instances[1].instance_id


def test_imported_geometry_source_precedes_generated_compiler(monkeypatch, tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M13-2-T7", run_id="INPUT")
    artifact = store.publish(
        "ART-MOTOR",
        ArtifactType.STEP,
        "motor.step",
        b"trusted motor",
        "test",
        "1",
        state.revision,
        state_hash(state),
    )
    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="vendor:motor",
        geometry_source=GeometrySourceReference(
            artifact_id=artifact.artifact_id,
            artifact_hash=artifact.sha256,
            source_identity="vendor:motor",
        ),
        interfaces=("output",),
    )
    candidate, synthesis_request, synthesis_policy = _candidate(state, specification)
    imported = ImportedCadComponent(
        component_id="cad-shaft-a",
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
    )
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="shaft-a",
        cad_instance_id="cad-shaft-a",
        fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
        representation_identity=imported_component_hash(imported),
        source_geometry_identity=artifact.sha256,
        geometry_definition_identities=(artifact.artifact_id,),
        placement=CadRigidTransform(),
        placement_origin=_origin("shaft-a"),
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("shaft-a",),
        mappings=(mapping,),
    )

    import mechcad_harness.candidates.cad_realization as cad_realization

    monkeypatch.setattr(
        cad_realization,
        "compile_generated_part",
        lambda *args, **kwargs: pytest.fail("imported source entered generated compiler"),
        raising=False,
    )
    outcome = _service(tmp_path, manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.status is CandidateCadStageStatus.SUCCESS
    assert outcome.realization is not None
    assert outcome.realization.assembly.imported_components == (imported,)


@pytest.mark.parametrize(
    "fidelity",
    (
        CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
    ),
)
def test_evaluation_rejects_nontrusted_mapping_for_source_backed_specification(tmp_path, fidelity):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M13-2-T7", run_id="INPUT")
    artifact = store.publish(
        "ART-MOTOR",
        ArtifactType.STEP,
        "motor.step",
        b"trusted motor",
        "test",
        "1",
        state.revision,
        state_hash(state),
    )
    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="vendor:motor",
        geometry_source=GeometrySourceReference(
            artifact_id=artifact.artifact_id,
            artifact_hash=artifact.sha256,
            source_identity="vendor:motor",
        ),
        interfaces=("output",),
    )
    candidate, _, _ = _candidate(state, specification)
    generated = acceptance_program()
    mapping = CandidateCadInstanceMapping(
        candidate_hash=candidate.candidate_hash,
        physical_instance_id="shaft-a",
        cad_instance_id="cad-shaft-a",
        fidelity=fidelity,
        representation_identity=cad_program_hash(generated),
        geometry_definition_identities=(artifact.artifact_id,),
        placement=CadRigidTransform(),
        placement_origin=_origin("shaft-a"),
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("shaft-a",),
        mappings=(mapping,),
    )
    assembly = CadAssemblyProgram(
        assembly_id="candidate-cad-source-stand-in",
        parts=(generated,),
        instances=(
            CadComponentInstance(
                instance_id="cad-shaft-a",
                part_id=generated.part_id,
                placement=CadRigidTransform(),
            ),
        ),
    )
    realization = CandidateCadRealization(
        candidate_hash=candidate.candidate_hash,
        request_hash=request.request_hash,
        mappings=(mapping,),
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        provider_identity="fixture",
    )
    stage = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.SUCCESS,
        realization=realization,
    )

    with pytest.raises(ValueError, match="trusted source|source-backed"):
        _validate_cad_inputs(candidate, request, stage)


def test_geometry_definition_identities_distinguish_binding_graphs():
    inputs = (
        _selection_input("outer", 30.0),
        _selection_input("length", 50.0),
        GeneratedAuthorityInput(
            input_id="supplied",
            role="supplied_diameter",
            source_kind="design_selection",
            locator={
                "name_form": "component_scoped",
                "selection_key": "supplied",
                "selection_hash": selection_hash("component_scoped", "supplied", 10.0),
            },
            value=10.0,
            value_hash=value_hash(10.0),
        ),
        GeneratedAuthorityInput(
            input_id="clearance",
            role="clearance",
            source_kind="design_selection",
            locator={
                "name_form": "component_scoped",
                "selection_key": "clearance",
                "selection_hash": selection_hash("component_scoped", "clearance", 0.5),
            },
            value=0.5,
            value_hash=value_hash(0.5),
        ),
        _selection_input("start", 5.0),
        _selection_input("depth", 20.0),
    )
    common_bindings = (
        _direct("hub.outer_diameter_mm", "outer", 30.0),
        _direct("hub.length_mm", "length", 50.0),
        _direct("hub.bore:input.start_z_mm", "start", 5.0),
        _direct("hub.bore:input.depth_mm", "depth", 20.0),
    )
    direct = CylindricalHubSpecification(
        generated_part_id="hub",
        outer_diameter_mm=30.0,
        length_mm=50.0,
        bores=({"bore_id": "input", "diameter_mm": 10.0, "start_z_mm": 5.0, "depth_mm": 20.0},),
        inputs=inputs,
        field_bindings=common_bindings + (_direct("hub.bore:input.diameter_mm", "supplied", 10.0),),
    )
    related = CylindricalHubSpecification(
        generated_part_id="hub",
        outer_diameter_mm=30.0,
        length_mm=50.0,
        bores=({"bore_id": "input", "diameter_mm": 10.5, "start_z_mm": 5.0, "depth_mm": 20.0},),
        inputs=inputs,
        field_bindings=common_bindings
        + (
            GeneratedPartFieldBinding(
                field_slot="hub.bore:input.diameter_mm",
                source={
                    "rule_id": "hub-bore-from-supplied-shaft-with-clearance@1",
                    "input_ids": ("supplied", "clearance"),
                },
                field_value_hash=value_hash(10.5),
            ),
        ),
    )

    assert set(direct.inputs) == set(related.inputs)
    assert generated_geometry_definition_identities(direct) != generated_geometry_definition_identities(
        related
    )


def _hub_spec() -> ComponentSpecificationSnapshot:
    inputs = (
        _selection_input("hub_outer", 30.0),
        _selection_input("hub_length", 50.0),
        _selection_input("hub_bore_diameter", 10.0),
        _selection_input("hub_bore_start", 0.0),
        _selection_input("hub_bore_depth", 50.0),
    )
    hub = CylindricalHubSpecification(
        generated_part_id="hub-definition",
        outer_diameter_mm=30.0,
        length_mm=50.0,
        bores=({
            "bore_id": "input",
            "diameter_mm": 10.0,
            "start_z_mm": 0.0,
            "depth_mm": 50.0,
        },),
        inputs=inputs,
        field_bindings=(
            _direct("hub.outer_diameter_mm", "hub_outer", 30.0),
            _direct("hub.length_mm", "hub_length", 50.0),
            _direct("hub.bore:input.diameter_mm", "hub_bore_diameter", 10.0),
            _direct("hub.bore:input.start_z_mm", "hub_bore_start", 0.0),
            _direct("hub.bore:input.depth_mm", "hub_bore_depth", 50.0),
        ),
    )
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@3",
        component_type="hub",
        source_identity="generated:hub-definition",
        generated_part=hub,
        interfaces=hub.active_interface_ids,
    )


def _supplied_motor_spec(artifact) -> ComponentSpecificationSnapshot:
    geometry = GeometryArtifactIdentity(
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_identity="vendor:motor",
        coordinate_system_id="motor-local-mm",
    )
    geometry_reference = GeometrySourceReference(
        artifact_id=geometry.artifact_id,
        artifact_hash=geometry.artifact_hash,
        source_identity=geometry.source_identity,
        coordinate_system_id="motor-local-mm",
    )
    interface = RotationalShaftInterface(
        interface_id="output-shaft",
        geometry_reference_hash=geometry_reference.reference_hash,
        geometry=geometry,
        axis_point=_interface_fact(
            "motor-axis-point",
            SuppliedInterfaceTransformRole.POINT_MM,
            (1.0, 2.0, 3.0),
        ),
        axis_direction=_interface_fact(
            "motor-axis-direction",
            SuppliedInterfaceTransformRole.DIRECTION_UNIT,
            (0.0, 0.0, 1.0),
        ),
        nominal_shaft_diameter=_interface_fact(
            "motor-shaft-diameter",
            SuppliedInterfaceTransformRole.LENGTH_MM,
            10.0,
        ),
        usable_axial_engagement_length=_interface_fact(
            "motor-engagement",
            SuppliedInterfaceTransformRole.LENGTH_MM,
            20.0,
        ),
    )
    definition = SuppliedComponentInterfaceDefinition(
        interface_id=interface.interface_id,
        geometry_reference_hash=geometry_reference.reference_hash,
        geometry=geometry,
        shaft=interface,
    )
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="vendor:motor",
        geometry_source=geometry_reference,
        interfaces=(interface.interface_id,),
        supplied_interface_definitions=(definition,),
    )


def _mixed_fixture(tmp_path, *, motor_instance_ids=("motor-a",)):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M13-2-T7", state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M13-2-T7", run_id="INPUT")
    artifact = store.publish(
        "ART-MOTOR",
        ArtifactType.STEP,
        "motor.step",
        b"trusted motor",
        "test",
        "1",
        state.revision,
        state_hash(state),
    )
    motor = _supplied_motor_spec(artifact)
    shaft = _shaft_spec()
    hub = _hub_spec()
    specifications = (motor, shaft, hub)
    source = _source(state)
    synthesis_request = CandidateSynthesisRequest(source_binding=source)
    synthesis_policy = CandidateSynthesisPolicy()
    components = tuple(
        PhysicalComponentInstance(
            instance_id=instance_id,
            specification_hash=motor.specification_hash,
            role=PhysicalComponentRole.ACTUATOR,
            interfaces=motor.interfaces,
        )
        for instance_id in motor_instance_ids
    ) + (
        PhysicalComponentInstance(
            instance_id="shaft-a",
            specification_hash=shaft.specification_hash,
            role=PhysicalComponentRole.SHAFT,
            interfaces=shaft.interfaces,
        ),
        PhysicalComponentInstance(
            instance_id="hub-a",
            specification_hash=hub.specification_hash,
            role=PhysicalComponentRole.HUB_OR_COUPLING,
            interfaces=hub.interfaces,
        ),
    )
    candidate = MechanicalDesignCandidate(
        source_binding=source,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=specifications,
        realization=PhysicalMechanismRealization(components=components),
        design_variables=(
            CandidateDesignVariable(name="motor-a.placement.x_mm", value=10.0),
            CandidateDesignVariable(name="motor-a.placement.y_mm", value=20.0),
            CandidateDesignVariable(name="motor-a.placement.z_mm", value=30.0),
            CandidateDesignVariable(name="motor-b.placement.x_mm", value=100.0),
            CandidateDesignVariable(name="motor-b.placement.y_mm", value=200.0),
            CandidateDesignVariable(name="motor-b.placement.z_mm", value=300.0),
            CandidateDesignVariable(name="hub_outer", value=30.0),
            CandidateDesignVariable(name="hub_length", value=50.0),
            CandidateDesignVariable(name="hub_bore_diameter", value=10.0),
            CandidateDesignVariable(name="hub_bore_start", value=0.0),
            CandidateDesignVariable(name="hub_bore_depth", value=50.0),
            CandidateDesignVariable(name="diameter", value=12.5),
            CandidateDesignVariable(name="length", value=40.0),
            CandidateDesignVariable(name="shaft-a.placement.axial_offset_mm", value=4.0),
            CandidateDesignVariable(name="hub-a.placement.axial_offset_mm", value=2.0),
        ),
        generator_identity="m13-2-task-9-test-generator",
        generator_version="1",
    )
    return manager, candidate, synthesis_request, synthesis_policy, specifications, artifact


def _mixed_request(candidate, specifications, artifact, *, source_instance_id="motor-a"):
    motor, shaft, hub = specifications
    shaft_program = compile_generated_part(
        shaft.generated_part,
        GeneratedAuthorityView(design_selections=tuple(candidate.design_variables)),
    ).program
    hub_program = compile_generated_part(
        hub.generated_part,
        GeneratedAuthorityView(design_selections=tuple(candidate.design_variables)),
    ).program
    source_placement = {
        "motor-a": CadRigidTransform(x_mm=10.0, y_mm=20.0, z_mm=30.0),
        "motor-b": CadRigidTransform(x_mm=100.0, y_mm=200.0, z_mm=300.0),
    }[source_instance_id]
    source_local = CadRigidTransform(x_mm=1.0, y_mm=2.0, z_mm=3.0)
    shaft_local = pose_from_interface(shaft.generated_part.interfaces[0])
    hub_local = pose_from_interface(hub.generated_part.interfaces[0])
    first = place_generated_target(
        "coaxial-generated-placement@1",
        compose_poses(source_placement, source_local),
        shaft_local,
        None,
        None,
    )
    second = place_generated_target(
        "coaxial-generated-placement@1",
        compose_poses(first, shaft_local),
        hub_local,
        2.0,
        None,
    )
    motor_origin = lambda instance_id, transform: CandidatePlacementOrigin(
        authority="candidate_design_variable",
        input_identities=tuple(
            f"candidate:design-variable:{instance_id}.placement.{axis}"
            for axis in ("x_mm", "y_mm", "z_mm")
        ),
        derivation="accepted-design-variable-placement@1",
        transform=transform,
    )
    source_mappings = []
    for component in candidate.realization.components:
        if component.specification_hash != motor.specification_hash:
            continue
        instance_id = component.instance_id
        transform = {
            "motor-a": CadRigidTransform(x_mm=10.0, y_mm=20.0, z_mm=30.0),
            "motor-b": CadRigidTransform(x_mm=100.0, y_mm=200.0, z_mm=300.0),
        }[instance_id]
        imported = ImportedCadComponent(
            component_id=f"cad-{instance_id}",
            artifact_id=artifact.artifact_id,
            artifact_hash=artifact.sha256,
            source_revision=1,
            source_state_hash=candidate.source_binding.source_state_hash,
        )
        source_mappings.append(CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id=instance_id,
            cad_instance_id=f"cad-{instance_id}",
            fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            representation_identity=imported_component_hash(imported),
            source_geometry_identity=artifact.sha256,
            geometry_definition_identities=(artifact.artifact_id,),
            placement=transform,
            placement_origin=motor_origin(instance_id, transform),
        ))
    derivations = (
        _placement_derivation(
            derivation_id="place-shaft",
            source_physical_instance_id=source_instance_id,
            target_physical_instance_id="shaft-a",
            source_interface_id="output-shaft",
            source_interface_hash=motor.supplied_interface_definitions[0].interface_hash,
            target_generated_interface_ref={
                "interface_id": shaft.generated_part.interfaces[0].interface_id,
                "interface_hash": shaft.generated_part.interfaces[0].interface_hash,
            },
        ),
        _placement_derivation(
            derivation_id="place-hub",
            source_physical_instance_id="shaft-a",
            source_interface_id=shaft.generated_part.interfaces[0].interface_id,
            source_interface_hash=shaft.generated_part.interfaces[0].interface_hash,
            source_placement_ref={"kind": "derivation", "derivation_id": "place-shaft"},
            target_physical_instance_id="hub-a",
            target_generated_interface_ref={
                "interface_id": hub.generated_part.interfaces[0].interface_id,
                "interface_hash": hub.generated_part.interfaces[0].interface_hash,
            },
            inputs=(
                GeneratedAuthorityInput(
                    input_id="offset",
                    role="axial_offset",
                    source_kind="design_selection",
                    locator={
                        "name_form": "instance_scoped",
                        "selection_key": "placement.axial_offset_mm",
                        "selection_hash": selection_hash(
                            "instance_scoped", "placement.axial_offset_mm", 2.0
                        ),
                    },
                    value=2.0,
                    value_hash=value_hash(2.0),
                ),
            ),
        ),
    )
    def derived_mapping(instance_id, cad_id, program, generated_part, transform, derivation_id, source_hash, target_hash, input_hashes=()):
        origin = CandidatePlacementOrigin(
            authority="deterministic_derived_relation",
            input_identities=(
                f"candidate:generated-placement:{derivation_id}",
                source_hash,
                target_hash,
                *sorted(input_hashes),
            ),
            derivation="coaxial-generated-placement@1",
            transform=transform,
        )
        return CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id=instance_id,
            cad_instance_id=cad_id,
            fidelity=CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
            representation_identity=cad_program_hash(program),
            geometry_definition_identities=generated_geometry_definition_identities(generated_part),
            placement=transform,
            placement_origin=origin,
        )
    shaft_mapping = derived_mapping(
        "shaft-a", "cad-shaft-a", shaft_program, shaft.generated_part, first, "place-shaft",
        motor.supplied_interface_definitions[0].interface_hash,
        shaft.generated_part.interfaces[0].interface_hash,
    )
    hub_mapping = derived_mapping(
        "hub-a", "cad-hub-a", hub_program, hub.generated_part, second, "place-hub",
        shaft.generated_part.interfaces[0].interface_hash,
        hub.generated_part.interfaces[0].interface_hash,
        (derivations[1].inputs[0].input_hash,),
    )
    return CandidateCadRealizationRequest(
        schema_version="candidate-cad-realization-request@2",
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=tuple(component.instance_id for component in candidate.realization.components),
        mappings=tuple(source_mappings) + (shaft_mapping, hub_mapping),
        placement_derivations=derivations,
        placement_derivations_hash=placement_derivations_hash(derivations),
        design_variable_identities=tuple(
            f"candidate:design-variable:{variable.name}"
            for variable in candidate.design_variables
            if any(
                variable.name == f"{component.instance_id}.placement.{axis}"
                for component in candidate.realization.components
                for axis in ("x_mm", "y_mm", "z_mm")
            )
        ),
    )


def test_mixed_candidate_realization_recomputes_generated_placements_from_semantics(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    request = _mixed_request(candidate, specifications, artifact)

    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.status is CandidateCadStageStatus.SUCCESS
    assert outcome.realization is not None
    assert outcome.realization.assembly.imported_components
    assert outcome.realization.mappings[1].placement == request.mappings[1].placement
    assert outcome.realization.mappings[2].placement == request.mappings[2].placement
    assert outcome.realization.mappings[1].placement_origin.authority == "deterministic_derived_relation"


def test_derived_placement_uses_the_referenced_identical_source_instance(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(
        tmp_path, motor_instance_ids=("motor-a", "motor-b")
    )
    request = _mixed_request(candidate, specifications, artifact, source_instance_id="motor-b")

    service = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager)
    specifications_by_hash = {
        specification.specification_hash: specification for specification in specifications
    }
    shaft_mapping = next(
        mapping for mapping in request.mappings if mapping.physical_instance_id == "shaft-a"
    )

    assert service._derived_placement(
        request, shaft_mapping, specifications_by_hash, candidate
    ).x_mm == 101.0


def test_frame_derived_placement_deduplicates_shared_generated_reference_frames(tmp_path):
    state = _state()
    specification = _shaft_spec()
    base_candidate, synthesis_request, synthesis_policy = _candidate(
        state, specification, ("shaft-a", "shaft-b")
    )
    candidate = MechanicalDesignCandidate.model_validate(
        base_candidate.model_dump(mode="python")
        | {
            "design_variables": (
                *base_candidate.design_variables,
                CandidateDesignVariable(name="clocking", value=0.0),
                CandidateDesignVariable(name="shaft-a.placement.x_mm", value=3.0),
                CandidateDesignVariable(name="shaft-a.placement.y_mm", value=4.0),
                CandidateDesignVariable(name="shaft-a.placement.z_mm", value=5.0),
            ),
            "candidate_hash": "pending",
        }
    )
    generated = specification.generated_part
    assert generated is not None
    interface = generated.interfaces[0]
    frame = generated.reference_frame
    derivation_payload = {
        "rule_id": "frame-generated-placement@1",
        "source_interface_ref": {
            "interface_id": interface.interface_id,
            "interface_hash": interface.interface_hash,
        },
        "source_frame_ref": {
            "frame_id": frame.frame_id,
            "frame_hash": frame.frame_hash,
        },
        "source_placement_ref": {"kind": "design_variable_placement"},
        "target_generated_frame_ref": {
            "frame_id": frame.frame_id,
            "frame_hash": frame.frame_hash,
        },
        "rotation": {
            "rotation_id": "clocking",
            "axis_ref": {"frame_role": "target", "axis": "+z"},
            "angle_degrees": 0.0,
            "provenance": {
                "name_form": "component_scoped",
                "selection_key": "clocking",
                "selection_hash": selection_hash(
                    "component_scoped", "clocking", 0.0
                ),
            },
            "value_hash": value_hash(0.0),
        },
    }
    source_derivation = GeneratedPlacementDerivation.model_validate(
        {
            **derivation_payload,
            "derivation_id": "place-frame-source",
            "source_physical_instance_id": "shaft-a",
            "target_physical_instance_id": "shaft-a",
        }
    )
    derivation = GeneratedPlacementDerivation.model_validate(
        {
            **derivation_payload,
            "derivation_id": "place-frame-target",
            "source_physical_instance_id": "shaft-a",
            "target_physical_instance_id": "shaft-b",
        }
    )
    request = _request_with_derivations(
        candidate, specification, (source_derivation, derivation)
    )
    target_mapping = next(
        mapping
        for mapping in request.mappings
        if mapping.physical_instance_id == "shaft-b"
    )
    target_mapping = CandidateCadInstanceMapping.model_validate(
        target_mapping.model_dump(mode="python")
        | {
            "placement": CadRigidTransform(x_mm=3.0, y_mm=4.0, z_mm=5.0),
            "placement_origin": CandidatePlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=(
                    "candidate:generated-placement:place-frame-target",
                    interface.interface_hash,
                    frame.frame_hash,
                    derivation.rotation.input_hash,
                ),
                derivation="frame-generated-placement@1",
                transform=CadRigidTransform(x_mm=3.0, y_mm=4.0, z_mm=5.0),
            ),
            "mapping_hash": "pending",
        }
    )

    placement = _service(tmp_path, StateManager(tmp_path))._derived_placement(
        request,
        target_mapping,
        {specification.specification_hash: specification},
        candidate,
    )

    assert placement.x_mm == pytest.approx(3.0)
    assert placement.y_mm == pytest.approx(4.0)
    assert placement.z_mm == pytest.approx(5.0)


def test_derived_placement_rejects_an_unresolvable_instance_placement_pair(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    baseline = _mixed_request(candidate, specifications, artifact)
    request = baseline.model_copy(
        update={
            "placement_derivations": (
                _placement_derivation(
                    derivation_id="place-shaft",
                    source_physical_instance_id="missing-motor",
                    target_physical_instance_id="shaft-a",
                    source_interface_id="output-shaft",
                    source_interface_hash=specifications[0].supplied_interface_definitions[0].interface_hash,
                    target_generated_interface_ref={
                        "interface_id": specifications[1].generated_part.interfaces[0].interface_id,
                        "interface_hash": specifications[1].generated_part.interfaces[0].interface_hash,
                    },
                ),
                baseline.placement_derivations[1],
            ),
            "placement_derivations_hash": placement_derivations_hash((
                _placement_derivation(
                    derivation_id="place-shaft",
                    source_physical_instance_id="missing-motor",
                    target_physical_instance_id="shaft-a",
                    source_interface_id="output-shaft",
                    source_interface_hash=specifications[0].supplied_interface_definitions[0].interface_hash,
                    target_generated_interface_ref={
                        "interface_id": specifications[1].generated_part.interfaces[0].interface_id,
                        "interface_hash": specifications[1].generated_part.interfaces[0].interface_hash,
                    },
                ),
                baseline.placement_derivations[1],
            )),
            "request_hash": "pending",
        }
    )

    with pytest.raises(CandidateCadIntegrityError, match="candidate instance|source"):
        CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
            candidate, synthesis_request, synthesis_policy, request
        )


def test_derived_placement_rejects_foreign_provenance_identity(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    request = _mixed_request(candidate, specifications, artifact)
    mapping = request.mappings[1].model_copy(
        update={
            "placement_origin": request.mappings[1].placement_origin.model_copy(
                update={"input_identities": request.mappings[1].placement_origin.input_identities + ("foreign",), "origin_hash": "pending"}
            ),
            "mapping_hash": "pending",
        }
    )
    request = request.model_copy(
        update={"mappings": (request.mappings[0], mapping, *request.mappings[2:]), "request_hash": "pending"}
    )

    with pytest.raises(CandidateCadIntegrityError, match="foreign or irrelevant"):
        CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
            candidate, synthesis_request, synthesis_policy, request
        )


def test_two_trusted_instances_can_reuse_one_verified_step_artifact(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(
        tmp_path, motor_instance_ids=("motor-a", "motor-b")
    )
    request = _mixed_request(candidate, specifications, artifact)

    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.status is CandidateCadStageStatus.SUCCESS
    assert outcome.realization is not None
    assert outcome.realization.verified_source_content_identities == (artifact.sha256,)
    assert tuple(
        instance.part_id for instance in outcome.realization.assembly.instances[:2]
    ) == ("cad-motor-a", "cad-motor-b")


def test_cad_input_validation_independently_binds_placement_derivations_hash(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    request = _mixed_request(candidate, specifications, artifact)
    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )
    assert outcome.realization is not None
    tampered_realization = outcome.realization.model_copy(
        update={
            "placement_derivations_hash": placement_derivations_hash(()),
            "realization_hash": "pending",
        }
    )
    tampered_stage = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.SUCCESS,
        realization=tampered_realization,
    )

    with pytest.raises(ValueError, match="placement derivations"):
        _validate_cad_inputs(candidate, request, tampered_stage)


def test_design_variable_source_keeps_named_identity_orientation_contract(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(tmp_path)
    request = _mixed_request(candidate, specifications, artifact)
    mapping = request.mappings[0].model_copy(
        update={
            "placement": CadRigidTransform(
                x_mm=10.0,
                y_mm=20.0,
                z_mm=30.0,
                rotation_quaternion=(0.0, 1.0, 0.0, 0.0),
            ),
            "placement_origin": request.mappings[0].placement_origin.model_copy(
                update={
                    "transform": CadRigidTransform(
                        x_mm=10.0,
                        y_mm=20.0,
                        z_mm=30.0,
                        rotation_quaternion=(0.0, 1.0, 0.0, 0.0),
                    ),
                    "origin_hash": "pending",
                }
            ),
            "mapping_hash": "pending",
        }
    )
    request = request.model_copy(
        update={"mappings": (mapping, *request.mappings[1:]), "request_hash": "pending"}
    )

    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )

    assert outcome.status is CandidateCadStageStatus.UNRESOLVED
    assert outcome.reasons == (CandidateCadStageReason.INVALID_PLACEMENT_PROVENANCE,)


# ---------------------------------------------------------------------------
# M10 integration section (Task 14): generated candidates traverse the
# existing M10 path unchanged.
# ---------------------------------------------------------------------------


def _m10_binding(realization):
    from mechcad_harness.candidates import (
        CandidateM10Binding,
        CandidateM10BodyDisposition,
        CandidateM10ConstituentDisposition,
    )
    from mechcad_harness.kinematic_sweep import RevoluteAxis
    from mechcad_harness.multi_joint_kinematics import KinematicModel, RevoluteJointModel

    return CandidateM10Binding(
        candidate_hash=realization.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        model=KinematicModel(
            model_id="m13-2-m10-model",
            joints=(
                RevoluteJointModel(
                    joint_id="output-joint",
                    parent_instance_id="cad-motor-a",
                    child_instance_id="cad-shaft-a",
                    axis_origin_x_mm=0.0,
                    axis_direction_z=1.0,
                ),
            ),
        ),
        output_joint_id="output-joint",
        output_axis=RevoluteAxis(
            origin_x_mm=10.0,
            origin_y_mm=20.0,
            origin_z_mm=30.0,
            direction_x=0.0,
            direction_y=0.0,
            direction_z=1.0,
            frame_id="joint:output-joint",
        ),
        constituent_dispositions=(
            CandidateM10ConstituentDisposition(
                physical_instance_id="motor-a",
                cad_instance_id="cad-motor-a",
                constituent_key="motor",
                disposition=CandidateM10BodyDisposition.FIXED,
            ),
            CandidateM10ConstituentDisposition(
                physical_instance_id="shaft-a",
                cad_instance_id="cad-shaft-a",
                constituent_key="shaft",
                disposition=CandidateM10BodyDisposition.OUTPUT_RIGID,
                output_transform_group="output-joint",
            ),
            CandidateM10ConstituentDisposition(
                physical_instance_id="hub-a",
                cad_instance_id="cad-hub-a",
                constituent_key="hub",
                disposition=CandidateM10BodyDisposition.OUTPUT_RIGID,
                output_transform_group="output-joint",
            ),
        ),
    )


def _m10_scope(**updates):
    from mechcad_harness.candidates import (
        CandidateM10EvaluationScope,
        CandidateM10PairClassification,
        CandidateM10PairScopeRequirement,
    )

    payload = {
        "output_joint_semantic_key": "primary-output-revolute",
        "angle_interval_deg": (-45.0, 45.0),
        "required_clearance_mm": 1.0,
        "pair_scope_requirements": (
            CandidateM10PairScopeRequirement(
                requirement_key="motor-shaft-clearance",
                first_constituent_key="motor",
                second_constituent_key="shaft",
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
        ),
        "fidelity_requirements": (
            ("motor", CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY),
            ("shaft", CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY),
            ("hub", CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY),
        ),
        "proof_service_version": "m10-single-axis-continuous-proof@1",
    } | updates
    return CandidateM10EvaluationScope(**payload)


def _m10_realization(tmp_path):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = (
        _mixed_fixture(tmp_path)
    )
    request = _mixed_request(candidate, specifications, artifact)
    outcome = CandidateCadRealizationService(tmp_path, "PRJ-M13-2-T7", manager).realize(
        candidate, synthesis_request, synthesis_policy, request
    )
    assert outcome.realization is not None
    return candidate, request, outcome.realization


def test_generated_candidate_m10_evaluation_runs_complete_pair_universe(tmp_path):
    import itertools

    from mechcad_harness.candidates import (
        CandidateCollisionPairInventory,
        CandidateM10EvaluationRequest,
        CandidateM10EvaluationService,
        CandidateM10PairClassification,
        CandidateM10StageStatus,
    )
    from test_m12_candidate_m10_service import _continuous_result

    candidate, _, realization = _m10_realization(tmp_path)
    binding = _m10_binding(realization)
    scope = _m10_scope()

    inventory = CandidateCollisionPairInventory.complete_for(realization, binding, scope)
    cad_ids = tuple(sorted(mapping.cad_instance_id for mapping in realization.mappings))
    assert inventory.expected_pair_universe == tuple(itertools.combinations(cad_ids, 2))
    assert tuple(item.pair for item in inventory.classifications) == inventory.expected_pair_universe
    checked = next(
        item for item in inventory.classifications if item.pair == ("cad-motor-a", "cad-shaft-a")
    )
    assert checked.classification is CandidateM10PairClassification.CHECK_CLEARANCE
    fidelity_by_key = dict(scope.fidelity_requirements)
    mapping_by_cad = {mapping.cad_instance_id: mapping for mapping in realization.mappings}
    for entry in binding.constituent_dispositions:
        assert mapping_by_cad[entry.cad_instance_id].fidelity is fidelity_by_key[entry.constituent_key]

    m10_request = CandidateM10EvaluationRequest(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization.mappings)),
        inventory=inventory,
    )
    calls = []

    def prove(**kwargs):
        calls.append(kwargs)
        return _continuous_result(kwargs)

    stage = CandidateM10EvaluationService(
        prove,
        lambda **kwargs: pytest.fail("home check not required"),
        scope=scope,
    ).evaluate(
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
        realization,
        binding,
        m10_request,
    )

    assert stage.status is CandidateM10StageStatus.SUCCESS
    assert len(calls) == 1
    assert calls[0]["moving_instance_ids"] == ("cad-shaft-a",)
    assert calls[0]["stationary_instance_ids"] == ("cad-motor-a",)
    assert {instance.instance_id for instance in calls[0]["assembly"].instances} == {
        "cad-motor-a",
        "cad-shaft-a",
    }
    assert stage.cad_realization_hash == realization.realization_hash
    assert stage.evaluation_request_hash == m10_request.request_hash
    assert stage.pair_proofs[0].pair == ("cad-motor-a", "cad-shaft-a")


def test_candidate_m10_binding_binds_derivation_set_realization_and_enforces_fidelity(tmp_path):
    from mechcad_harness.candidates import CandidateCollisionPairInventory

    candidate, request, realization = _m10_realization(tmp_path)
    binding = _m10_binding(realization)
    scope = _m10_scope()

    assert binding.cad_realization_hash == realization.realization_hash
    assert realization.placement_derivations_hash == request.placement_derivations_hash
    assert request.placement_derivations
    assert realization.request_hash == request.request_hash

    forged = binding.model_copy(update={"cad_realization_hash": "sha256:" + "f" * 64})
    with pytest.raises(ValueError, match="realization"):
        forged.validate_against(realization)

    wrong_fidelity_scope = _m10_scope(
        fidelity_requirements=(
            ("shaft", CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
        ),
    )
    with pytest.raises(ValueError, match="fidelity"):
        CandidateCollisionPairInventory.complete_for(realization, binding, wrong_fidelity_scope)

    CandidateCollisionPairInventory.complete_for(realization, binding, scope)


def test_canonical_m10_verification_mirrors_generated_exact_fidelity(tmp_path):
    import itertools

    from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
    from mechcad_harness.candidates.canonical_m10 import (
        CanonicalM10VerificationService,
        CanonicalM10VerificationStatus,
    )
    from mechcad_harness.models import CanonicalGeometryFidelity
    from test_m12_canonical_m10 import _proof_result
    from test_m13_2_promotion_canonical_roundtrip import _persist_generated_canonical_fixture

    _, _, _, _, _, _, reconstruction, resolver = _persist_generated_canonical_fixture(tmp_path)
    cad = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
    mechanism = reconstruction.mechanism
    obligation = mechanism.m10_obligations[0]
    shaft_canonical_id = f"{mechanism.id}:shaft-a"

    assert (
        shaft_canonical_id,
        CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY,
    ) in obligation.fidelity_requirements
    shaft_mapping = next(
        mapping for mapping in cad.mappings if mapping.physical_instance_id == shaft_canonical_id
    )
    assert shaft_mapping.fidelity is CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY

    calls = []

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            calls.append(kwargs)
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)

    assert outcome.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR
    assert len(calls) == 1
    cad_ids = tuple(sorted(mapping.cad_instance_id for mapping in cad.mappings))
    assert outcome.inventory.expected_pair_universe == tuple(itertools.combinations(cad_ids, 2))
    assert outcome.scope.fidelity_requirements == obligation.fidelity_requirements
    assert outcome.cad_realization_hash == cad.realization_hash


def test_canonical_m10_verification_rejects_obligation_fidelity_mismatch(tmp_path):
    from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
    from mechcad_harness.candidates.canonical_m10 import CanonicalM10VerificationService
    from mechcad_harness.candidates.canonical_mechanism import CanonicalPhysicalMechanismCompiler
    from mechcad_harness.models import CanonicalGeometryFidelity
    from test_m12_canonical_m10 import _proof_result
    from test_m13_2_promotion_canonical_roundtrip import _persist_generated_canonical_fixture

    manager, _, request, _, _, _, reconstruction, resolver = (
        _persist_generated_canonical_fixture(tmp_path)
    )
    mechanism = reconstruction.mechanism
    obligation = mechanism.m10_obligations[0]
    shaft_canonical_id = f"{mechanism.id}:shaft-a"
    tampered_obligation = type(obligation).model_validate(
        obligation.model_dump(mode="python")
        | {
            "fidelity_requirements": tuple(
                (
                    instance_id,
                    CanonicalGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
                )
                if instance_id == shaft_canonical_id
                else (instance_id, fidelity)
                for instance_id, fidelity in obligation.fidelity_requirements
            ),
            "obligation_hash": "pending",
        }
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "m10_obligations": (tampered_obligation,),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)
    tampered_reconstruction = CanonicalPhysicalMechanismCompiler(
        manager, lambda project_id: resolver
    ).reconstruct(
        request.project_id,
        snapshot.revision,
        snapshot.state_hash,
        tampered_mechanism.id,
    )
    cad = CanonicalPhysicalCadCompiler(resolver).realize(tampered_reconstruction)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    with pytest.raises(ValueError, match="fidelity"):
        CanonicalM10VerificationService(FakeApplication()).execute(
            tampered_reconstruction, cad
        )
