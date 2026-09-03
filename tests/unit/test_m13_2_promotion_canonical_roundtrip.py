from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.cad_assembly import CadRigidTransform, assembly_hash
from mechcad_harness.candidates import (
    CandidateCadRealizationService,
    CandidateCadStageOutcome,
    CandidateCurrentness,
    CandidateCollisionPairInventory,
    CandidateEvaluationPolicy,
    CandidateEvaluationService,
    CandidateM10Binding,
    CandidateM10BodyDisposition,
    CandidateM10ConstituentDisposition,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationScope,
    CandidateGeometryFidelity,
    CandidateM10PairClassification,
    CandidateM10PairScopeRequirement,
    CandidateM10EvaluationService,
    CandidatePromotionRequest,
    CandidateSelection,
    JointPhysicalRealizationBinding,
)
from mechcad_harness.candidates.canonical_mechanism import _projection_from_mechanism
import mechcad_harness.candidates.canonical_mechanism as canonical_mechanism
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalPhysicalMechanismCompiler,
    ProjectArtifactResolver,
)
from mechcad_harness.candidates.evaluation import _stage_outcome_hash
from mechcad_harness.candidates.promotion import CandidatePromotionCompiler
from mechcad_harness.candidates.promotion_models import PromotableMechanismProjection
from mechcad_harness.candidates.models import ComponentSpecificationSnapshot
from mechcad_harness.candidates.promotion_models import (
    CandidatePromotionPolicy,
    PromotionClassification,
    PromotionValueClassification,
)
from mechcad_harness.models import (
    CanonicalAcceptedDesignChoice,
    CanonicalGeneratedPlacementDerivation,
    CanonicalGeometryFidelity,
    CanonicalPhysicalMechanism,
    CanonicalDesignChoiceOrigin,
    CanonicalPlacement,
    CanonicalPlacementOrigin,
    placement_derivations_hash,
    selection_hash,
    value_hash,
)
from mechcad_harness.generated_part_cad import generated_cad_definition_id
from mechcad_harness.candidates.canonical_cad import (
    CanonicalCadIntegrityError,
    CanonicalPhysicalCadCompiler,
)
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.multi_joint_kinematics import KinematicModel, RevoluteJointModel
from mechcad_harness.state import StateManager, state_hash

from test_m13_2_legacy_goldens import (
    GOLDEN_CANONICAL_MECHANISM_HASH,
    GOLDEN_CANONICAL_MECHANISM_JSON,
    _canonical_mechanism,
)
from test_m13_2_generated_part_models import _shaft
from test_m13_2_candidate_cad_integration import (
    _mixed_fixture,
    _mixed_request,
    _placement_derivation,
)
from test_m13_geometry_materialization import _interface_fact
from mechcad_harness.models.supplied_component_interface import (
    SuppliedComponentReferenceFrame,
    SuppliedInterfaceTransformRole,
)
from test_m12_candidate_evaluation import _m12_result, _evaluation_service
from test_m12_candidate_m10_service import _continuous_result


HASH = "sha256:" + "a" * 64


def _canonical_derivation() -> CanonicalGeneratedPlacementDerivation:
    return CanonicalGeneratedPlacementDerivation(
        derivation_id="place-shaft",
        rule_id="coaxial-generated-placement@1",
        source_canonical_instance_id="mount-1",
        source_interface_id="mount:output-frame",
        source_interface_hash=HASH,
        source_placement_ref={"kind": "design_variable_placement"},
        target_canonical_instance_id="shaft-1",
        target_generated_interface_id="shaft-1:shaft",
        target_generated_interface_hash=HASH,
        inputs=(),
    )


def _mechanism_v2(*, derivations=()):
    return CanonicalPhysicalMechanism.model_validate(
        _canonical_mechanism().model_dump(mode="python")
        | {
            "schema_version": "canonical-physical-mechanism@2",
            "generated_placement_derivations": derivations,
            "mechanism_hash": "pending",
        }
    )


def _projection(mechanism: CanonicalPhysicalMechanism, *, derivations=()):
    return PromotableMechanismProjection(
        canonical_target_mechanism_id=mechanism.id,
        canonical_instance_ids=tuple(component.instance_id for component in mechanism.components),
        component_specifications=mechanism.component_specifications,
        components=mechanism.components,
        accepted_design_choices=mechanism.accepted_design_choices,
        placements=mechanism.placements,
        connections=mechanism.connections,
        joint_bindings=mechanism.joint_bindings,
        m10_obligations=mechanism.m10_obligations,
        generated_placement_derivations=derivations,
        mapping_identities=tuple(component.instance_id for component in mechanism.components),
    )


def test_canonical_mechanism_v1_golden_round_trip_remains_byte_stable():
    mechanism = CanonicalPhysicalMechanism.model_validate_json(GOLDEN_CANONICAL_MECHANISM_JSON)

    assert mechanism.model_dump_json() == GOLDEN_CANONICAL_MECHANISM_JSON
    assert mechanism.mechanism_hash == GOLDEN_CANONICAL_MECHANISM_HASH
    assert "generated_placement_derivations" not in mechanism.model_dump(mode="json")


def test_canonical_mechanism_v2_round_trips_and_hashes_derivations_deterministically():
    derivation = _canonical_derivation()
    mechanism = _mechanism_v2(derivations=(derivation,))
    reloaded = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="json")
    )
    empty = _mechanism_v2()

    assert reloaded == mechanism
    assert reloaded.mechanism_hash == mechanism.mechanism_hash
    assert reloaded.generated_placement_derivations == (derivation,)
    assert mechanism.mechanism_hash != empty.mechanism_hash
    assert json.loads(mechanism.model_dump_json())["generated_placement_derivations"]


def test_nonempty_generated_placement_derivations_require_mechanism_v2():
    with pytest.raises(ValidationError, match="canonical-physical-mechanism@1"):
        CanonicalPhysicalMechanism(
            **_canonical_mechanism().model_dump(mode="python"),
            generated_placement_derivations=(_canonical_derivation(),),
        )


def test_empty_projection_derivations_are_omitted_without_changing_legacy_hash():
    mechanism = _canonical_mechanism()
    projection = _projection(mechanism)

    assert projection.projection_hash == (
        "sha256:b515bbeebbce691066cc6b959f1bb9c5ccfe44593dfcc8df5fa317c525ece66e"
    )
    assert "generated_placement_derivations" not in projection.model_dump(mode="json")


def test_projection_population_preserves_canonical_derivations():
    mechanism = _mechanism_v2(derivations=(_canonical_derivation(),))

    projections = (
        CandidatePromotionCompiler._projection(mechanism),
        _projection_from_mechanism(mechanism),
    )

    assert all(
        projection.generated_placement_derivations
        == mechanism.generated_placement_derivations
        for projection in projections
    )


def _generated_specification():
    generated = _shaft()
    return ComponentSpecificationSnapshot(
        schema_version="component-specification@3",
        component_type="shaft",
        source_identity="generated:shaft",
        interfaces=generated.active_interface_ids,
        generated_part=generated,
    )


def _generated_promotion_fixture(tmp_path, *, classifications=True):
    manager, candidate, synthesis_request, synthesis_policy, specifications, artifact = _mixed_fixture(
        tmp_path
    )
    realization = candidate.realization.model_copy(
        update={
            "joint_bindings": (
                JointPhysicalRealizationBinding(
                    joint_id="output-joint",
                    driven_instance_id="shaft-a",
                    realization_component_ids=("motor-a", "shaft-a", "hub-a"),
                    axis_frame_reference="joint:output-joint",
                    load_path_metadata_available=False,
                ),
            ),
            "realization_hash": "pending",
        }
    )
    candidate = type(candidate).model_validate(
        candidate.model_dump(mode="python")
        | {"realization": realization, "candidate_hash": "pending"}
    )
    cad_request = _mixed_request(candidate, specifications, artifact)
    cad_stage = CandidateCadRealizationService(
        workspace=tmp_path,
        project_id="PRJ-M13-2-T7",
        state_manager=manager,
    ).realize(candidate, synthesis_request, synthesis_policy, cad_request)
    assert cad_stage.realization is not None
    realization = cad_stage.realization

    scope = CandidateM10EvaluationScope(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            CandidateM10PairScopeRequirement(
                requirement_key="motor-shaft-clearance",
                first_constituent_key="motor",
                second_constituent_key="shaft",
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
        ),
        fidelity_requirements=(("shaft", CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY),),
        proof_service_version="m10-single-axis-continuous-proof@1",
    )
    binding = CandidateM10Binding(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        model=KinematicModel(
            model_id="generated-promotion-model",
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
    inventory = CandidateCollisionPairInventory.complete_for(realization, binding, scope)
    m10_request = CandidateM10EvaluationRequest(
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization.mappings)),
        inventory=inventory,
    )
    m10_stage = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs),
        lambda **kwargs: pytest.fail("home check not required"),
        scope=scope,
    ).evaluate(
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
        realization,
        binding,
        m10_request,
    )
    m12_result = _m12_result(candidate).model_copy(
        update={"design_variables": candidate.design_variables, "result_hash": "pending"}
    )
    m12_result = type(m12_result).model_validate(m12_result.model_dump(mode="json"))
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        cad_stage,
        m10_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    selection = CandidateSelection(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity="fixture-selector",
        rationale="fixture selection",
    )
    request = CandidatePromotionRequest(
        project_id=candidate.source_binding.project_id,
        source_revision=candidate.source_binding.source_revision,
        source_state_hash=candidate.source_binding.source_state_hash,
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_3_result=m12_result,
        evaluation=evaluation,
        selection=selection,
        promotion_policy=CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
        canonical_target_mechanism_id="PM-generated",
        classifications=(),
    )
    if classifications:
        expected = CandidatePromotionCompiler._expected_classifications(request)
        complete = tuple(
            PromotionClassification(
                source_identity=identity,
                classification=(
                    expected_value.required_classification
                    or (
                        PromotionValueClassification.ACCEPTED_DESIGN_CHOICE
                        if identity.startswith("candidate:design-variable:")
                        else PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
                    )
                ),
                source_value=expected_value.source_value if expected_value.has_source_value else None,
            )
            for identity, expected_value in expected.items()
        )
        request = request.model_copy(update={"classifications": complete, "request_hash": "pending"})
        request = CandidatePromotionRequest.model_validate(request.model_dump(mode="json"))
    compiler = CandidatePromotionCompiler(
        manager,
        lambda project_id: ArtifactStore(tmp_path, project_id=project_id, run_id="promotion-lookup"),
        cad_replay_verifier=lambda *args: None,
    )
    return manager, compiler, request, cad_request


def _assert_rejected_by_readiness_and_compile(manager, compiler, request, match):
    with pytest.raises(ValueError, match=match):
        compiler.validate_readiness(request)
    with pytest.raises(ValueError, match=match):
        compiler.compile(manager.load_current_state(request.project_id), request)


def test_generated_promotion_accepts_exact_evaluated_derivation_set_a(tmp_path):
    manager, compiler, request, _ = _generated_promotion_fixture(tmp_path)
    cad_request = request.evaluation.cad_request
    assert cad_request is not None

    readiness = compiler.validate_readiness(request)
    compilation = compiler.compile(manager.load_current_state(request.project_id), request)

    assert readiness.mapping == compilation.mapping
    assert tuple(
        derivation.derivation_id for derivation in cad_request.placement_derivations
    ) == tuple(
        derivation.derivation_id
        for derivation in compilation.canonical_mechanism.generated_placement_derivations
    )
    assert compilation.canonical_mechanism.schema_version == "canonical-physical-mechanism@2"
    assert tuple(
        specification.schema_version
        for specification in compilation.canonical_mechanism.component_specifications
        if specification.generated_part is not None
    ) == ("canonical-component-specification@3", "canonical-component-specification@3")
    assert compilation.canonical_mechanism.generated_placement_derivations
    assert compilation.proposal.operations[0].path == "/physical_mechanisms/PM-generated"


@pytest.mark.parametrize(
    ("identity_kind", "expected_identity"),
    [
        ("generated_part", "candidate:generated-part:{part_hash}:shaft-definition"),
        ("generated_placement", "candidate:generated-placement:place-shaft"),
    ],
)
def test_generated_promotion_rejects_missing_required_classification(
    tmp_path, identity_kind, expected_identity
):
    manager, compiler, request, _ = _generated_promotion_fixture(tmp_path)
    generated = request.candidate.component_specifications[1].generated_part
    assert generated is not None
    identity = expected_identity.format(part_hash=request.candidate.component_specifications[1].specification_hash)
    classifications = tuple(
        item for item in request.classifications if item.source_identity != identity
    )

    _assert_rejected_by_readiness_and_compile(
        manager,
        compiler,
        request.model_copy(update={"classifications": classifications, "request_hash": "pending"}),
        rf"promotion classification is missing: {identity}",
    )


@pytest.mark.parametrize(
    ("identity_prefix", "update", "message"),
    [
        (
            "candidate:generated-part:",
            {"source_value": "sha256:" + "f" * 64},
            "promotion classification value substitution",
        ),
        (
            "candidate:generated-placement:",
            {"classification": PromotionValueClassification.DO_NOT_PROMOTE},
            "promotion classification omits canonical input",
        ),
    ],
)
def test_generated_promotion_rejects_substituted_or_unsupported_classification(
    tmp_path, identity_prefix, update, message
):
    manager, compiler, request, _ = _generated_promotion_fixture(tmp_path)
    target = next(
        item for item in request.classifications if item.source_identity.startswith(identity_prefix)
    )
    changed = target.model_copy(update=update | {"classification_hash": "pending"})
    classifications = tuple(
        changed if item.source_identity == target.source_identity else item
        for item in request.classifications
    )

    _assert_rejected_by_readiness_and_compile(
        manager,
        compiler,
        request.model_copy(update={"classifications": classifications, "request_hash": "pending"}),
        message,
    )


@pytest.mark.parametrize("mismatch", ["input", "binding"])
def test_generated_promotion_rejects_canonical_input_or_binding_survival_mismatch(
    tmp_path, monkeypatch, mismatch
):
    manager, compiler, request, _ = _generated_promotion_fixture(tmp_path)
    if mismatch == "input":
        original = compiler._canonical_choice

        def substituted(variable, classifications, canonical_by_candidate):
            choice = original(variable, classifications, canonical_by_candidate)
            if variable.name == "diameter":
                return choice.model_copy(update={"value": 999.0})
            return choice

        monkeypatch.setattr(compiler, "_canonical_choice", substituted)
        message = "generated authority input or binding did not survive promotion"
    else:
        original = compiler._canonical_specification

        def substituted(specification):
            canonical = original(specification)
            if canonical.generated_part is None:
                return canonical
            binding = canonical.generated_part.field_bindings[0].model_copy(
                update={"field_value_hash": value_hash(999.0)}
            )
            generated = canonical.generated_part.model_copy(
                update={"field_bindings": (binding, *canonical.generated_part.field_bindings[1:])}
            )
            return canonical.model_copy(update={"generated_part": generated})

        monkeypatch.setattr(compiler, "_canonical_specification", substituted)
        message = "generated specification semantic substitution"

    _assert_rejected_by_readiness_and_compile(manager, compiler, request, message)


def test_generated_promotion_rejects_evaluated_set_a_with_request_set_b(tmp_path):
    manager, compiler, request, _ = _generated_promotion_fixture(tmp_path)
    cad_request = request.evaluation.cad_request
    assert cad_request is not None
    changed = _placement_derivation(
        derivation_id="place-shaft",
        source_physical_instance_id="motor-a",
        target_physical_instance_id="shaft-a",
        source_interface_id="substituted-output",
        target_generated_interface_ref={
            "interface_id": request.candidate.component_specifications[1].generated_part.interfaces[0].interface_id,
            "interface_hash": request.candidate.component_specifications[1].generated_part.interfaces[0].interface_hash,
        },
    )
    derivations = (changed, cad_request.placement_derivations[1])
    request_set_b = type(cad_request).model_validate(
        cad_request.model_dump(mode="python")
        | {
            "placement_derivations": derivations,
            "placement_derivations_hash": placement_derivations_hash(derivations),
            "request_hash": "pending",
            }
    )
    realization_set_a = request.evaluation.cad_stage_outcome.realization
    assert realization_set_a is not None
    realization_set_b = type(realization_set_a).model_validate(
        realization_set_a.model_dump(mode="python")
        | {
            "request_hash": request_set_b.request_hash,
            "realization_hash": "pending",
        }
    )
    cad_stage_set_b = CandidateCadStageOutcome(
        status=request.evaluation.cad_stage_outcome.status,
        realization=realization_set_b,
    )
    m10_stage_set_b = request.evaluation.m10_stage_outcome.model_copy(
        update={
            "cad_realization_hash": realization_set_b.realization_hash,
            "outcome_hash": "pending",
        }
    )
    evaluation_set_b = request.evaluation.model_copy(
        update={
            "cad_request": request_set_b,
            "cad_stage_outcome": cad_stage_set_b,
            "cad_stage_outcome_hash": _stage_outcome_hash(cad_stage_set_b),
            "m10_stage_outcome": m10_stage_set_b,
            "m10_stage_outcome_hash": _stage_outcome_hash(m10_stage_set_b),
            "evaluation_hash": "pending",
        }
    )
    request_set_b = request.model_copy(
        update={"evaluation": evaluation_set_b, "request_hash": "pending"}
    )

    _assert_rejected_by_readiness_and_compile(
        manager,
        compiler,
        request_set_b,
        r"(?s)promotion request integrity failure: .*candidate evaluation placement derivations identity mismatch",
    )


def test_generated_promotion_rejects_cad_mapping_placement_inconsistent_with_derivation(tmp_path):
    manager, compiler, request, _ = _generated_promotion_fixture(tmp_path)
    cad_request = request.evaluation.cad_request
    cad_realization = request.evaluation.cad_stage_outcome.realization
    binding = request.evaluation.m10_binding
    scope = request.evaluation.m10_scope
    assert cad_request is not None
    assert cad_realization is not None
    assert binding is not None
    assert scope is not None

    target_mapping = next(
        item for item in cad_request.mappings if item.physical_instance_id == "shaft-a"
    )
    wrong_placement = CadRigidTransform(
        x_mm=target_mapping.placement.x_mm + 1.0,
        y_mm=target_mapping.placement.y_mm,
        z_mm=target_mapping.placement.z_mm,
    )
    wrong_origin = type(target_mapping.placement_origin).model_validate(
        target_mapping.placement_origin.model_dump(mode="python")
        | {"transform": wrong_placement, "origin_hash": "pending"}
    )
    wrong_mapping = type(target_mapping).model_validate(
        target_mapping.model_dump(mode="python")
        | {
            "placement": wrong_placement,
            "placement_origin": wrong_origin,
            "mapping_hash": "pending",
        }
    )
    mappings = tuple(
        wrong_mapping if item.physical_instance_id == "shaft-a" else item
        for item in cad_request.mappings
    )
    request_b = type(cad_request).model_validate(
        cad_request.model_dump(mode="python")
        | {"mappings": mappings, "request_hash": "pending"}
    )
    mappings = request_b.mappings
    assembly = cad_realization.assembly.model_copy(
        update={
            "instances": tuple(
                instance.model_copy(update={"placement": wrong_placement})
                if instance.instance_id == "cad-shaft-a"
                else instance
                for instance in cad_realization.assembly.instances
            )
        }
    )
    realization_b = type(cad_realization).model_validate(
        cad_realization.model_dump(mode="python")
        | {
            "request_hash": request_b.request_hash,
            "mappings": mappings,
            "assembly": assembly,
            "assembly_hash": assembly_hash(assembly),
            "realization_hash": "pending",
        }
    )
    binding_b = type(binding).model_validate(
        binding.model_dump(mode="python")
        | {"cad_realization_hash": realization_b.realization_hash, "binding_hash": "pending"}
    )
    inventory = CandidateCollisionPairInventory.complete_for(realization_b, binding_b, scope)
    m10_request_b = CandidateM10EvaluationRequest(
        candidate_hash=request.candidate.candidate_hash,
        cad_realization_hash=realization_b.realization_hash,
        binding_hash=binding_b.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding_b.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization_b.mappings)),
        inventory=inventory,
    )
    m10_stage_b = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs),
        lambda **kwargs: pytest.fail("home check not required"),
        scope=scope,
    ).evaluate(
        request.candidate.source_binding.source_revision,
        request.candidate.source_binding.source_state_hash,
        realization_b,
        binding_b,
        m10_request_b,
    )
    cad_stage_b = CandidateCadStageOutcome(
        status=request.evaluation.cad_stage_outcome.status,
        realization=realization_b,
    )
    class _CurrentnessVerifier:
        def evaluate(self, *args, **kwargs):
            return CandidateCurrentness.CURRENT

    evaluation_b = CandidateEvaluationService(
        currentness_verifier=_CurrentnessVerifier()
    ).evaluate(
        request.candidate,
        request.synthesis_request,
        request.synthesis_policy,
        request.m12_3_result,
        cad_stage_b,
        m10_stage_b,
        CandidateEvaluationPolicy(),
        cad_request=request_b,
        m10_request=m10_request_b,
        m10_scope=scope,
        m10_binding=binding_b,
    )
    selection_b = CandidateSelection(
        candidate_hash=request.candidate.candidate_hash,
        evaluation_hash=evaluation_b.evaluation_hash,
        source_binding_hash=evaluation_b.source_binding_hash,
        evaluation_scope_hash=evaluation_b.evaluation_scope_hash,
        selector_identity="fixture-selector",
        rationale="fixture selection",
    )
    request_b = request.model_copy(
        update={
            "evaluation": evaluation_b,
            "selection": selection_b,
            "request_hash": "pending",
        }
    )

    _assert_rejected_by_readiness_and_compile(
        manager,
        compiler,
        request_b,
        "promotion candidate CAD placement does not match semantic derivation",
    )


def test_generated_specification_promotes_as_canonical_v3_without_losing_semantics():
    specification = _generated_specification()

    canonical = CandidatePromotionCompiler._canonical_specification(specification)

    assert canonical.schema_version == "canonical-component-specification@3"
    assert canonical.generated_part is not None
    assert canonical.generated_part.model_dump_json() == specification.generated_part.model_dump_json()
    assert canonical.specification_hash != specification.specification_hash


def test_generated_specification_triggers_mapping_v2_and_requires_exact_classification():
    specification = _generated_specification()
    candidate = type("Candidate", (), {
        "component_specifications": (specification,),
        "design_variables": (),
        "realization": type("Realization", (), {
            "components": (),
            "connections": (),
            "joint_bindings": (),
        })(),
    })()
    request = type("Request", (), {"candidate": candidate})()
    compiler = object.__new__(CandidatePromotionCompiler)

    compiler._verify_policy(
        CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
        candidate,
    )
    expected = compiler._expected_classifications(request)

    identity = f"candidate:generated-part:{specification.specification_hash}:{specification.generated_part.generated_part_id}"
    assert expected[identity].required_classification is PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
    assert expected[identity].source_value == specification.generated_part.generated_part_hash


def test_generated_placement_classification_is_bound_to_the_derivation_hash(tmp_path):
    _, candidate, _, _, specifications, artifact = _mixed_fixture(tmp_path)
    cad_request = _mixed_request(candidate, specifications, artifact)
    request = type("Request", (), {
        "candidate": candidate,
        "evaluation": type("Evaluation", (), {"cad_request": cad_request})(),
    })()

    expected = CandidatePromotionCompiler._expected_classifications(request)
    derivation = cad_request.placement_derivations[0]
    identity = f"candidate:generated-placement:{derivation.derivation_id}"

    assert expected[identity].required_classification is PromotionValueClassification.CANONICAL_REDERIVATION_INPUT
    assert expected[identity].source_value == derivation.derivation_hash


def test_generated_placement_projection_preserves_source_instance_and_placement_reference(tmp_path):
    _, candidate, _, _, specifications, artifact = _mixed_fixture(
        tmp_path, motor_instance_ids=("motor-a", "motor-b")
    )
    cad_request = _mixed_request(candidate, specifications, artifact, source_instance_id="motor-b")
    request = type("Request", (), {
        "candidate": candidate,
        "evaluation": type("Evaluation", (), {"cad_request": cad_request})(),
    })()
    canonical_by_candidate = {
        component.instance_id: f"PM-1:{component.instance_id}"
        for component in candidate.realization.components
    }

    projected = CandidatePromotionCompiler._canonical_generated_placement_derivations(
        request, canonical_by_candidate
    )
    first = projected[0]

    assert first.source_canonical_instance_id == "PM-1:motor-b"
    assert first.source_placement_ref == cad_request.placement_derivations[0].source_placement_ref


def _persist_generated_canonical_fixture(tmp_path, *, duplicate_generated=False):
    manager, compiler, request, cad_request = _generated_promotion_fixture(tmp_path)
    state = manager.load_current_state(request.project_id)
    compilation = compiler.compile(state, request)
    mechanism = compilation.canonical_mechanism
    if duplicate_generated:
        shaft = next(
            component
            for component in mechanism.components
            if component.instance_id.endswith(":shaft-a")
        )
        mechanism = type(mechanism).model_validate(
            mechanism.model_dump(mode="python")
            | {
                "components": (
                    *mechanism.components,
                    shaft.model_copy(
                        update={
                            "instance_id": "PM-generated:shaft-b",
                            "placement_id": None,
                            "component_hash": "pending",
                        }
                    ),
                ),
                "mechanism_hash": "pending",
            }
        )
    canonical_state = state.model_copy(
        update={"physical_mechanisms": [mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, canonical_state)
    resolver = ProjectArtifactResolver(
        ArtifactStore(tmp_path, project_id=request.project_id, run_id="canonical-lookup")
    )
    reconstruction = CanonicalPhysicalMechanismCompiler(
        manager, lambda project_id: resolver
    ).reconstruct(
        request.project_id,
        snapshot.revision,
        snapshot.state_hash,
        compilation.canonical_mechanism.id,
    )
    return manager, compiler, request, cad_request, compilation, snapshot, reconstruction, resolver


def test_canonical_generated_cad_regenerates_exact_geometry_and_deduplicates_definitions(tmp_path):
    (
        _,
        _,
        request,
        cad_request,
        compilation,
        _,
        reconstruction,
        resolver,
    ) = _persist_generated_canonical_fixture(tmp_path, duplicate_generated=True)

    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
    generated_specs = {
        specification.specification_hash: specification.generated_part
        for specification in reconstruction.mechanism.component_specifications
        if specification.generated_part is not None
    }
    generated_mappings = tuple(
        mapping
        for mapping in realization.mappings
        if mapping.specification_hash in generated_specs
    )

    assert generated_mappings
    assert all(
        mapping.fidelity is CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY
        for mapping in generated_mappings
    )
    candidate_instance_ids = {
        mapping.physical_instance_id for mapping in cad_request.mappings
    }
    for mapping in generated_mappings:
        physical_instance_id = mapping.physical_instance_id.rsplit(":", 1)[-1]
        if physical_instance_id in candidate_instance_ids:
            candidate_mapping = next(
                item
                for item in cad_request.mappings
                if item.physical_instance_id == physical_instance_id
            )
            assert mapping.representation_identity == candidate_mapping.representation_identity

    generated_parts = tuple(
        part for part in realization.assembly.parts if part.part_id.startswith("generated-part-")
    )
    assert len(generated_parts) == len({part.part_id for part in generated_parts})
    assert tuple(
        instance.part_id
        for instance in realization.assembly.instances
        if instance.instance_id in {mapping.cad_instance_id for mapping in generated_mappings}
    ) == tuple(
        generated_cad_definition_id(generated_specs[mapping.specification_hash])
        for mapping in generated_mappings
    )
    assert len({mapping.cad_instance_id for mapping in generated_mappings}) == len(generated_mappings)
    shaft_instances = tuple(
        instance
        for instance in realization.assembly.instances
        if instance.instance_id
        in {
            mapping.cad_instance_id
            for mapping in generated_mappings
            if mapping.physical_instance_id.endswith(":shaft-a")
            or mapping.physical_instance_id.endswith(":shaft-b")
        }
    )
    assert len(shaft_instances) == 2
    assert shaft_instances[0].part_id == shaft_instances[1].part_id


def test_canonical_reconstruction_replays_from_canonical_records_without_candidate_state(
    tmp_path, monkeypatch
):
    manager, _, request, _, compilation, snapshot, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )

    def fail_if_candidate_is_consulted(*args, **kwargs):
        raise AssertionError("candidate state must not be consulted")

    monkeypatch.setattr(
        "mechcad_harness.candidates.generated_authority.build_candidate_view",
        fail_if_candidate_is_consulted,
    )
    monkeypatch.setattr(
        "mechcad_harness.candidates.cad_realization.CandidateCadRealizationService._derived_placement",
        fail_if_candidate_is_consulted,
    )

    reconstruction = CanonicalPhysicalMechanismCompiler(
        manager, lambda project_id: resolver
    ).reconstruct(
        request.project_id,
        snapshot.revision,
        snapshot.state_hash,
        compilation.canonical_mechanism.id,
    )

    assert reconstruction.mechanism == compilation.canonical_mechanism


def test_canonical_reconstruction_rejects_tampered_generated_placement_derivation(tmp_path):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    original = mechanism.generated_placement_derivations[0]
    tampered_derivation = original.model_copy(
        update={"source_interface_hash": "sha256:" + "f" * 64, "derivation_hash": "pending"}
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "generated_placement_derivations": (
                tampered_derivation,
                *mechanism.generated_placement_derivations[1:],
            ),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="canonical|placement|derivation"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_reconstruction_rejects_generated_relation_without_derivation(tmp_path):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    assert mechanism.generated_placement_derivations
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "generated_placement_derivations": (),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="generated placement|derivation"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_reconstruction_rejects_valid_but_unrelated_source_frame(tmp_path):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    motor_specification = next(
        specification
        for specification in mechanism.component_specifications
        if specification.component_type == "motor"
    )
    geometry = motor_specification.geometry_source
    assert geometry is not None
    frame_kwargs = {
        "geometry_reference_hash": geometry.reference_hash,
        "origin": _interface_fact(
            "canonical-frame-origin",
            SuppliedInterfaceTransformRole.POINT_MM,
            (1.0, 2.0, 3.0),
        ),
        "orientation": _interface_fact(
            "canonical-frame-orientation",
            SuppliedInterfaceTransformRole.ORIENTATION,
            (1.0, 0.0, 0.0, 0.0),
        ),
    }
    declared_frame = SuppliedComponentReferenceFrame(
        frame_id="declared-frame", **frame_kwargs
    )
    unrelated_frame = SuppliedComponentReferenceFrame(
        frame_id="unrelated-frame", **frame_kwargs
    )
    source_definition = motor_specification.supplied_interface_definitions[0]
    source_payload = source_definition.model_dump(mode="python")
    source_payload["shaft"] = source_definition.shaft.model_dump(mode="python") | {
        "reference_frame_id": declared_frame.frame_id,
        "interface_hash": "pending",
    }
    source_payload["interface_hash"] = "pending"
    source_definition = type(source_definition).model_validate(source_payload)
    specification_payload = motor_specification.model_dump(mode="python") | {
        "supplied_reference_frames": (declared_frame, unrelated_frame),
        "supplied_interface_definitions": (source_definition,),
        "specification_hash": "pending",
    }
    motor_specification = type(motor_specification).model_validate(specification_payload)
    specifications = tuple(
        motor_specification
        if specification.component_type == "motor"
        else specification
        for specification in mechanism.component_specifications
    )
    components = tuple(
        component.model_copy(
            update={
                "specification_hash": motor_specification.specification_hash,
                "component_hash": "pending",
            }
        )
        if component.specification_hash != motor_specification.specification_hash
        and component.instance_id.endswith("motor-a")
        else component
        for component in mechanism.components
    )
    original = mechanism.generated_placement_derivations[0]
    shaft_specification = next(
        specification
        for specification in mechanism.component_specifications
        if specification.generated_part is not None
        and specification.component_type == "shaft"
    )
    shaft_frame = shaft_specification.generated_part.reference_frame
    rotation = {
        "rotation_id": "clocking",
        "axis_ref": {"frame_role": "target", "axis": "+z"},
        "angle_degrees": 0.0,
        "provenance": {
            "name_form": "component_scoped",
            "selection_key": "clocking",
            "selection_hash": selection_hash("component_scoped", "clocking", 0.0),
        },
        "value_hash": value_hash(0.0),
    }
    tampered_derivation = type(original).model_validate(
        original.model_dump(mode="python")
        | {
            "rule_id": "frame-generated-placement@1",
            "source_frame_id": unrelated_frame.frame_id,
            "source_frame_hash": unrelated_frame.frame_hash,
            "target_generated_interface_id": None,
            "target_generated_interface_hash": None,
            "target_generated_frame_id": shaft_frame.frame_id,
            "target_generated_frame_hash": shaft_frame.frame_hash,
            "rotation": rotation,
            "derivation_hash": "pending",
        }
    )
    original_placement = next(
        placement
        for placement in mechanism.placements
        if placement.instance_id.endswith("shaft-a")
    )
    tampered_placement = type(original_placement).model_validate(
        original_placement.model_dump(mode="python")
        | {
            "relation": tampered_derivation.rule_id,
            "input_identities": (
                tampered_derivation.source_interface_hash,
                tampered_derivation.target_generated_frame_hash,
                tampered_derivation.rotation.input_hash,
            ),
            "placement_hash": "pending",
        }
    )
    choice = CanonicalAcceptedDesignChoice(
        key="clocking",
        value=0.0,
        origin=CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION,
        provenance="task-13-integrity-test",
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "component_specifications": specifications,
            "components": components,
            "accepted_design_choices": (*mechanism.accepted_design_choices, choice),
            "placements": tuple(
                tampered_placement if placement.instance_id.endswith("shaft-a") else placement
                for placement in mechanism.placements
            ),
            "generated_placement_derivations": (
                tampered_derivation,
                *mechanism.generated_placement_derivations[1:],
            ),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="source frame|canonical"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


@pytest.mark.parametrize("missing_endpoint", ["source", "target"])
def test_canonical_reconstruction_rejects_missing_generated_endpoint_declarations(
    tmp_path, missing_endpoint
):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    component_id = (
        next(
            derivation.source_canonical_instance_id
            for derivation in mechanism.generated_placement_derivations[1:]
        )
        if missing_endpoint == "source"
        else mechanism.generated_placement_derivations[1].target_canonical_instance_id
    )
    component = next(
        component for component in mechanism.components if component.instance_id == component_id
    )
    interface_id = next(
        derivation.source_interface_id
        for derivation in mechanism.generated_placement_derivations[1:]
    ) if missing_endpoint == "source" else mechanism.generated_placement_derivations[1].target_generated_interface_id
    tampered_component = component.model_copy(
        update={
            "interfaces": tuple(
                interface for interface in component.interfaces if interface != interface_id
            ),
            "component_hash": "pending",
        }
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "components": tuple(
                tampered_component if item.instance_id == component_id else item
                for item in mechanism.components
            ),
            "m10_obligations": (),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="interface|canonical"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_reconstruction_rejects_source_interface_missing_from_physical_registry(
    tmp_path,
):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    derivation = next(
        derivation
        for derivation in mechanism.generated_placement_derivations
        if next(
            component
            for component in mechanism.components
            if component.instance_id == derivation.source_canonical_instance_id
        ).specification_hash
        == next(
            specification.specification_hash
            for specification in mechanism.component_specifications
            if specification.generated_part is None
        )
    )
    source_component = next(
        component
        for component in mechanism.components
        if component.instance_id == derivation.source_canonical_instance_id
    )
    assert derivation.source_interface_id in source_component.interfaces
    tampered_component = source_component.model_copy(
        update={
            "interfaces": tuple(
                interface
                for interface in source_component.interfaces
                if interface != derivation.source_interface_id
            ),
            "component_hash": "pending",
        }
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "components": tuple(
                tampered_component
                if component.instance_id == source_component.instance_id
                else component
                for component in mechanism.components
            ),
            "m10_obligations": (),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="interface|canonical"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


@pytest.mark.parametrize(
    "source_placement_update",
    [
        {"origin": CanonicalPlacementOrigin.ACCEPTED_INTERFACE},
        {"relation": "forged-source-placement@1"},
        {"rotation_quaternion": (0.0, 0.0, 0.0, 1.0)},
    ],
)
def test_canonical_reconstruction_rejects_non_design_variable_source_placement_authority(
    tmp_path, source_placement_update
):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    derivation = mechanism.generated_placement_derivations[0]
    source_placement = next(
        placement
        for placement in mechanism.placements
        if placement.instance_id == derivation.source_canonical_instance_id
    )
    tampered_placement = type(source_placement).model_validate(
        source_placement.model_dump(mode="python")
        | source_placement_update
        | {"placement_hash": "pending"}
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "placements": tuple(
                tampered_placement
                if placement.placement_id == source_placement.placement_id
                else placement
                for placement in mechanism.placements
            ),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="source placement"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_reconstruction_rejects_missing_design_variable_source_placement(tmp_path):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    derivation = mechanism.generated_placement_derivations[0]
    source_component = next(
        component
        for component in mechanism.components
        if component.instance_id == derivation.source_canonical_instance_id
    )
    source_placement = next(
        placement
        for placement in mechanism.placements
        if placement.instance_id == source_component.instance_id
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "components": tuple(
                component.model_copy(
                    update={"placement_id": None, "component_hash": "pending"}
                )
                if component.instance_id == source_component.instance_id
                else component
                for component in mechanism.components
            ),
            "placements": tuple(
                placement
                for placement in mechanism.placements
                if placement.placement_id != source_placement.placement_id
            ),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="source placement"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_reconstruction_rejects_duplicate_generated_placement_targets(tmp_path):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    original = mechanism.generated_placement_derivations[0]
    duplicate = type(original).model_validate(
        original.model_dump(mode="python")
        | {"derivation_id": "duplicate-place-shaft", "derivation_hash": "pending"}
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "generated_placement_derivations": (
                original,
                duplicate,
                *mechanism.generated_placement_derivations[1:],
            ),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="target instance IDs"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_cad_replays_mechanism_placement_before_emitting_cad(tmp_path):
    manager, _, request, _, compilation, _, reconstruction, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    derivation = mechanism.generated_placement_derivations[0]
    target_placement = next(
        placement
        for placement in mechanism.placements
        if placement.instance_id == derivation.target_canonical_instance_id
    )
    tampered_placement = target_placement.model_copy(
        update={
            "x_mm": target_placement.x_mm + 1.0,
            "placement_hash": "pending",
        }
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "placements": tuple(
                tampered_placement
                if placement.placement_id == target_placement.placement_id
                else placement
                for placement in mechanism.placements
            ),
            "mechanism_hash": "pending",
        }
    )
    caller_constructed = reconstruction.model_copy(
        update={
            "canonical_mechanism": tampered_mechanism,
            "normalized_projection_hash": _projection_from_mechanism(
                tampered_mechanism
            ).projection_hash,
        }
    )

    with pytest.raises(CanonicalCadIntegrityError, match="placement|derivation|canonical"):
        CanonicalPhysicalCadCompiler(resolver).realize(caller_constructed)


def _frame_generated_mechanism(mechanism):
    source_specification = next(
        specification
        for specification in mechanism.component_specifications
        if specification.generated_part is None
    )
    source_geometry = source_specification.geometry_source
    assert source_geometry is not None
    original_source_specification_hash = source_specification.specification_hash
    source_frame = SuppliedComponentReferenceFrame(
        frame_id="source-frame",
        geometry_reference_hash=source_geometry.reference_hash,
        origin=_interface_fact(
            "source-frame-origin",
            SuppliedInterfaceTransformRole.POINT_MM,
            (1.0, 2.0, 3.0),
        ),
        orientation=_interface_fact(
            "source-frame-orientation",
            SuppliedInterfaceTransformRole.ORIENTATION,
            (1.0, 0.0, 0.0, 0.0),
        ),
    )
    source_definition = source_specification.supplied_interface_definitions[0]
    source_payload = source_definition.model_dump(mode="python")
    source_payload["shaft"] = source_definition.shaft.model_dump(mode="python") | {
        "reference_frame_id": source_frame.frame_id,
        "interface_hash": "pending",
    }
    source_payload["interface_hash"] = "pending"
    source_definition = type(source_definition).model_validate(source_payload)
    source_specification = type(source_specification).model_validate(
        source_specification.model_dump(mode="python")
        | {
            "supplied_reference_frames": (source_frame,),
            "supplied_interface_definitions": (source_definition,),
            "specification_hash": "pending",
        }
    )
    components = tuple(
        component.model_copy(
            update={
                "specification_hash": source_specification.specification_hash,
                "component_hash": "pending",
            }
        )
        if component.specification_hash == original_source_specification_hash
        else component
        for component in mechanism.components
    )
    original = mechanism.generated_placement_derivations[0]
    target_specification = next(
        specification
        for specification in mechanism.component_specifications
        if specification.generated_part is not None
        and specification.component_type == "shaft"
    )
    target_frame = target_specification.generated_part.reference_frame
    rotation = {
        "rotation_id": "clocking",
        "axis_ref": {"frame_role": "target", "axis": "+z"},
        "angle_degrees": 0.0,
        "provenance": {
            "name_form": "component_scoped",
            "selection_key": "clocking",
            "selection_hash": selection_hash("component_scoped", "clocking", 0.0),
        },
        "value_hash": value_hash(0.0),
    }
    derivation = type(original).model_validate(
        original.model_dump(mode="python")
        | {
            "rule_id": "frame-generated-placement@1",
            "source_interface_hash": source_definition.interface_hash,
            "source_frame_id": source_frame.frame_id,
            "source_frame_hash": source_frame.frame_hash,
            "target_generated_interface_id": None,
            "target_generated_interface_hash": None,
            "target_generated_frame_id": target_frame.frame_id,
            "target_generated_frame_hash": target_frame.frame_hash,
            "rotation": rotation,
            "derivation_hash": "pending",
        }
    )
    accepted_choice = CanonicalAcceptedDesignChoice(
        key="clocking",
        value=0.0,
        origin=CanonicalDesignChoiceOrigin.EXPLICIT_POLICY_ASSUMPTION,
        provenance="task-13-frame-replay-test",
    )
    target_placement_id = next(
        placement.placement_id
        for placement in mechanism.placements
        if placement.instance_id == original.target_canonical_instance_id
    )
    placements = tuple(
        type(placement).model_validate(
            placement.model_dump(mode="python")
            | {
                "relation": derivation.rule_id,
                "input_identities": (
                    source_definition.interface_hash,
                    target_frame.frame_hash,
                    derivation.rotation.input_hash,
                ),
                "placement_hash": "pending",
            }
        )
        if placement.placement_id == target_placement_id
        else placement
        for placement in mechanism.placements
    )
    return type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "component_specifications": tuple(
                source_specification
                if specification.component_type == source_specification.component_type
                else specification
                for specification in mechanism.component_specifications
            ),
            "components": components,
            "accepted_design_choices": (*mechanism.accepted_design_choices, accepted_choice),
            "placements": placements,
            "generated_placement_derivations": (
                derivation,
                *mechanism.generated_placement_derivations[1:],
            ),
            "mechanism_hash": "pending",
        }
    )


def test_canonical_frame_replay_explicitly_gates_exact_supplied_source_frame(
    tmp_path, monkeypatch
):
    _, _, _, _, compilation, _, _, _ = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = _frame_generated_mechanism(compilation.canonical_mechanism)
    calls = []
    from mechcad_harness.models import supplied_component_interface as m13

    original_gate = m13.require_authoritatively_consumable_interface

    def record_gate(definition, active_frame=None):
        calls.append((definition, active_frame))
        return original_gate(definition, active_frame)

    monkeypatch.setattr(
        m13,
        "require_authoritatively_consumable_interface",
        record_gate,
    )

    validated = CanonicalPhysicalMechanismCompiler._validate_mechanism(mechanism)

    source_specification = next(
        specification
        for specification in validated.component_specifications
        if specification.generated_part is None
    )
    assert calls == [
        (
            source_specification.supplied_interface_definitions[0],
            source_specification.supplied_reference_frames[0],
        )
    ]


def test_canonical_reconstruction_rejects_any_generated_placement_without_derivation(
    tmp_path,
):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    generated_specifications = {
        specification.specification_hash
        for specification in mechanism.component_specifications
        if specification.generated_part is not None
    }
    accepted_placements = tuple(
        type(placement).model_validate(
            placement.model_dump(mode="python")
            | {
                "origin": CanonicalPlacementOrigin.ACCEPTED_DESIGN_CHOICE,
                "relation": "accepted-design-variable-placement@1",
                "rotation_quaternion": (1.0, 0.0, 0.0, 0.0),
                "placement_hash": "pending",
            }
        )
        if next(
            component
            for component in mechanism.components
            if component.instance_id == placement.instance_id
        ).specification_hash in generated_specifications
        else placement
        for placement in mechanism.placements
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "placements": accepted_placements,
            "generated_placement_derivations": (),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="generated placement|derivation"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


@pytest.mark.parametrize("tamper", ["coordinates", "identities", "choice"])
def test_canonical_design_variable_source_placement_replays_exact_accepted_choices(
    tmp_path, tamper
):
    manager, _, request, _, compilation, _, _, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = compilation.canonical_mechanism
    derivation = mechanism.generated_placement_derivations[0]
    source_id = derivation.source_canonical_instance_id
    source_placement = next(
        placement for placement in mechanism.placements if placement.instance_id == source_id
    )
    axes = ("x_mm", "y_mm", "z_mm")
    choices = tuple(
        next(
            choice
            for choice in mechanism.accepted_design_choices
            if choice.key == f"{source_id}.placement.{axis}"
        )
        for axis in axes
    )
    expected_identities = tuple(
        identity for choice in choices for identity in choice.source_identities
    )
    assert source_placement.input_identities == expected_identities

    placement = source_placement
    placement_updates = {source_placement.placement_id: source_placement}
    accepted_choices = mechanism.accepted_design_choices
    if tamper == "coordinates":
        placement = source_placement.model_copy(
            update={"x_mm": source_placement.x_mm + 1.0, "placement_hash": "pending"}
        )
        placement_updates[source_placement.placement_id] = placement
        for target_derivation in mechanism.generated_placement_derivations:
            target_placement = next(
                item
                for item in mechanism.placements
                if item.instance_id == target_derivation.target_canonical_instance_id
            )
            placement_updates[target_placement.placement_id] = target_placement.model_copy(
                update={"x_mm": target_placement.x_mm + 1.0, "placement_hash": "pending"}
            )
    elif tamper == "identities":
        placement = source_placement.model_copy(
            update={
                "input_identities": ("forged-source-identity", *expected_identities[1:]),
                "placement_hash": "pending",
            }
        )
        placement_updates[source_placement.placement_id] = placement
    else:
        changed_choice = choices[0].model_copy(
            update={"value": choices[0].value + 1.0, "choice_hash": "pending"}
        )
        accepted_choices = tuple(
            changed_choice if choice.key == changed_choice.key else choice
            for choice in mechanism.accepted_design_choices
        )

    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "accepted_design_choices": accepted_choices,
            "placements": tuple(
                placement_updates.get(item.placement_id, item)
                for item in mechanism.placements
            ),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="source placement|design choice|canonical"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_reconstruction_rejects_extra_generated_accepted_placement_without_target_derivation(
    tmp_path,
):
    manager, _, request, _, _, _, reconstruction, resolver = _persist_generated_canonical_fixture(
        tmp_path, duplicate_generated=True
    )
    mechanism = reconstruction.mechanism
    extra_component = next(
        component
        for component in mechanism.components
        if component.instance_id.endswith(":shaft-b")
    )
    extra_placement = CanonicalPlacement(
        placement_id=f"{extra_component.instance_id}:placement",
        instance_id=extra_component.instance_id,
        origin=CanonicalPlacementOrigin.ACCEPTED_DESIGN_CHOICE,
        input_identities=("canonical:extra-placement",),
        relation="accepted-design-variable-placement@1",
        x_mm=7.0,
        y_mm=8.0,
        z_mm=9.0,
    )
    tampered_component = extra_component.model_copy(
        update={"placement_id": extra_placement.placement_id, "component_hash": "pending"}
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "components": tuple(
                tampered_component if item.instance_id == extra_component.instance_id else item
                for item in mechanism.components
            ),
            "placements": (*mechanism.placements, extra_placement),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="generated placement|derivation"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


def test_canonical_reconstruction_rejects_duplicate_generated_placement_records(
    tmp_path,
):
    manager, _, request, _, _, _, reconstruction, resolver = _persist_generated_canonical_fixture(
        tmp_path
    )
    mechanism = reconstruction.mechanism
    target_id = mechanism.generated_placement_derivations[0].target_canonical_instance_id
    target_placement = next(
        placement for placement in mechanism.placements if placement.instance_id == target_id
    )
    duplicate_placement = type(target_placement).model_validate(
        target_placement.model_dump(mode="python")
        | {
            "placement_id": f"{target_id}:duplicate-placement",
            "placement_hash": "pending",
        }
    )
    tampered_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "placements": (*mechanism.placements, duplicate_placement),
            "mechanism_hash": "pending",
        }
    )
    state = manager.load_current_state(request.project_id).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    snapshot = manager.create_revision(request.project_id, state)

    with pytest.raises(ValueError, match="generated placement|derivation"):
        CanonicalPhysicalMechanismCompiler(
            manager, lambda project_id: resolver
        ).reconstruct(
            request.project_id,
            snapshot.revision,
            snapshot.state_hash,
            tampered_mechanism.id,
        )


@pytest.mark.parametrize("generated", [False, True])
def test_canonical_mechanism_rejects_component_endpoint_outside_specification_registry(
    tmp_path, generated
):
    _, _, request, _, compilation, _, _, _ = _persist_generated_canonical_fixture(tmp_path)
    mechanism = compilation.canonical_mechanism
    component = next(
        component
        for component in mechanism.components
        if (
            next(
                specification
                for specification in mechanism.component_specifications
                if specification.specification_hash == component.specification_hash
            ).generated_part
            is not None
        )
        is generated
    )
    tampered_component = component.model_copy(
        update={
            "interfaces": (*component.interfaces, "undeclared-endpoint"),
            "component_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="declared|interface|registry"):
        CanonicalPhysicalMechanism.model_validate(
            mechanism.model_dump(mode="python")
            | {
                "components": tuple(
                    tampered_component if item.instance_id == component.instance_id else item
                    for item in mechanism.components
                ),
                "mechanism_hash": "pending",
            }
        )


def test_canonical_generated_reference_frames_remain_non_endpoint_declarations(tmp_path):
    _, _, _, _, compilation, _, _, _ = _persist_generated_canonical_fixture(tmp_path)
    mechanism = compilation.canonical_mechanism
    generated = next(
        specification
        for specification in mechanism.component_specifications
        if specification.generated_part is not None
    )
    assert generated.generated_part is not None
    assert generated.generated_part.reference_frame.frame_id not in generated.interfaces
    assert CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="json")
    ) == mechanism
