from __future__ import annotations

import json
import hashlib
import math
import os
import shutil
from types import SimpleNamespace
from pathlib import Path

import pytest
from pydantic import ValidationError

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.analysis_provenance import (
    TRANSIENT_MEASUREMENT_EXECUTION_MODE,
    TRANSIENT_MEASUREMENT_PROVIDER_NAME,
)
from mechcad_harness.backends.freecad import FreeCADBackend
from mechcad_harness.candidates import (
    CandidateCadStageStatus,
    CandidateIntegrityError,
    CandidateGeometryFidelity,
    CandidateMultiJointPromotionApplicationResult,
    PromotionApplicationStatus,
    CandidateMultiJointPromotionRequest,
    CandidatePromotionCompilation,
    MultiJointPromotionReadiness,
    compile_canonical,
    compare_candidate_canonical_multi_joint_semantics,
)
from mechcad_harness.candidates.cad_realization import CandidateCadIntegrityError
from mechcad_harness.candidates.canonical_cad import CanonicalCadIntegrityError
from mechcad_harness.changes.operations import ChangeOperation, OperationType
from mechcad_harness.models import ChangeProposal, ProposalStatus
from mechcad_harness.multi_joint_collision_sweep import (
    CollisionClassification,
)
from mechcad_harness.multi_joint_continuous_clearance import (
    MultiJointContinuousClearanceProofResultV2,
    MultiJointContinuousProofStatus,
)
from mechcad_harness.multi_joint_continuous_path import MultiJointPath
from mechcad_harness.multi_joint_kinematics import JointConfiguration
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
from mechcad_harness.runs.models import SourceBinding
from mechcad_harness.dependency.models import EvidenceFreshness
from mechcad_harness.state import state_hash
from mechcad_harness.structural.runtime import discover_freecad

from m13_4_acceptance_fixtures import (
    PROJECT_ID,
    build_m134_application_at,
    build_m134_fixture,
    build_m134_multi_joint_request,
    build_m134_promotion_request,
)


M11_STATUS = "UNRESOLVED"
M11_ELIGIBLE = False


def test_m13_4_exact_pair_coverage_rejects_duplicate_for_omitted_pair():
    expected_scope = (
        ExactConstituentPair(first_instance_id="cad-a", second_instance_id="cad-b"),
        ExactConstituentPair(first_instance_id="cad-a", second_instance_id="cad-c"),
    )
    configuration = SimpleNamespace(
        pair_results=(
            SimpleNamespace(first_instance_id="cad-a", second_instance_id="cad-b"),
            SimpleNamespace(first_instance_id="cad-a", second_instance_id="cad-b"),
        )
    )
    with pytest.raises(AssertionError, match="duplicate"):
        _assert_exact_pair_coverage(expected_scope, (configuration,))


def _normalized_pair_identity(pair):
    first = pair.first_instance_id
    second = pair.second_instance_id
    assert isinstance(first, str) and first.strip(), "pair first identity must be nonempty"
    assert isinstance(second, str) and second.strip(), "pair second identity must be nonempty"
    assert first != second, "pair identities must be distinct"
    return tuple(sorted((first, second)))


def _assert_exact_pair_coverage(exact_pair_scope, configuration_results):
    expected_pairs = tuple(
        _normalized_pair_identity(pair) for pair in exact_pair_scope
    )
    expected_pair_set = set(expected_pairs)
    assert len(expected_pairs) == len(expected_pair_set), (
        "exact pair scope contains duplicate identities"
    )
    for configuration in configuration_results:
        actual_pairs = tuple(
            _normalized_pair_identity(pair)
            for pair in configuration.pair_results
        )
        assert len(actual_pairs) == len(expected_pairs), (
            "measured pair count does not match exact pair scope"
        )
        assert len(actual_pairs) == len(set(actual_pairs)), (
            "measured pair results contain a duplicate identity"
        )
        assert set(actual_pairs) == expected_pair_set, (
            "measured pair identities do not exactly match exact pair scope"
        )


def _assert_m10_result(
    result,
    expected_configuration_count: int,
    expected_pair_count: int,
    exact_pair_scope,
):
    assert result.evaluator_version == "multi-joint-exact-collision-sweep@2.0"
    assert result.continuous_path_verified is False
    assert len(result.configuration_results) == expected_configuration_count
    assert [len(configuration.pair_results) for configuration in result.configuration_results] == [
        expected_pair_count
    ] * expected_configuration_count, result.model_dump(mode="json")
    _assert_exact_pair_coverage(exact_pair_scope, result.configuration_results)
    assert all(
        pair.classification
        in (
            CollisionClassification.POSITIVE_CLEARANCE,
            CollisionClassification.TOUCHING,
            CollisionClassification.INTERFERENCE,
        )
        for configuration in result.configuration_results
        for pair in configuration.pair_results
    )
    assert all(
        len(configuration.instance_world_transforms) == 6
        for configuration in result.configuration_results
    )


def _assert_durable_canonical_m10_evidence(
    application, reconstruction, canonical_cad, canonical_bridge, canonical_m10
):
    evidence = application.get_multi_joint_collision_sweep_evidence(
        canonical_m10.result.result_hash
    )
    assert evidence is not None
    reloaded = application.evidence_store.load_evidence(application.project_id, evidence.id)
    assert reloaded == evidence
    assert application.project_id == canonical_cad.project_id == reconstruction.project_id
    assert reloaded.revision == reconstruction.revision
    assert reloaded.state_hash == reconstruction.state_hash
    assert reloaded.producer_result_id == canonical_m10.result.result_hash
    assert reloaded.input_hash == canonical_m10.request.request_hash
    assert reloaded.output_hash == canonical_m10.result.result_hash
    provenance = reloaded.analysis_execution_provenance
    assert provenance is not None
    assert provenance.request_hash == canonical_m10.request.request_hash
    assert provenance.result_hash == canonical_m10.result.result_hash
    assert provenance.source_assembly_hash == canonical_cad.assembly_hash
    assert provenance.model_hash == canonical_bridge.m10_model_hash
    assert canonical_m10.request.model_hash == canonical_bridge.m10_model_hash
    obligation = reconstruction.canonical_mechanism.multi_joint_verification_obligations[0]
    assert canonical_m10.request.configurations == obligation.configuration_set.configurations
    assert canonical_m10.request.exact_pair_scope == canonical_bridge.exact_pair_scope
    assert canonical_m10.request.volume_tolerance_mm3 == obligation.volume_tolerance_mm3
    assert canonical_m10.request.distance_tolerance_mm == obligation.distance_tolerance_mm
    assert canonical_bridge.inventory.inventory_hash == canonical_bridge.inventory_hash
    assert provenance.provider_name == TRANSIENT_MEASUREMENT_PROVIDER_NAME
    assert provenance.execution_mode == TRANSIENT_MEASUREMENT_EXECUTION_MODE
    assert provenance.backend_provenance is not None
    assert provenance.backend_provenance.backend_name == "freecad"
    assert provenance.backend_provenance.library_version == "1.1.3"
    assert (
        application.evidence_store.get_evidence_freshness(
            application.project_id, reloaded.id
        )
        is EvidenceFreshness.CURRENT
    )
    return reloaded


def _semantic_snapshot(
    bridge,
    cad_realization,
    physical_realization,
    pair_bindings,
    configurations,
    *,
    exact_pair_scope,
    volume_tolerance_mm3,
    distance_tolerance_mm,
    placement_derivations,
):
    def normalized_id(value):
        return value.rsplit(":", 1)[-1]

    def enum_value(value):
        return getattr(value, "value", value)

    def transform_values(transform):
        return tuple(
            round(value, 9)
            for value in (
                transform.x_mm,
                transform.y_mm,
                transform.z_mm,
                *transform.rotation_quaternion,
            )
        )

    def derivation_values(derivation):
        source_member = (
            derivation.source_physical_instance_id
            if hasattr(derivation, "source_physical_instance_id")
            else derivation.source_canonical_instance_id
        )
        target_member = (
            derivation.target_physical_instance_id
            if hasattr(derivation, "target_physical_instance_id")
            else derivation.target_canonical_instance_id
        )
        source_frame = getattr(derivation, "source_frame_ref", None)
        target_interface = getattr(derivation, "target_generated_interface_ref", None)
        target_frame = getattr(derivation, "target_generated_frame_ref", None)
        return {
            "derivation_id": derivation.derivation_id,
            "rule_id": derivation.rule_id,
            "source_member": normalized_id(source_member),
            "source_interface": {
                "id": derivation.source_interface_ref.interface_id
                if hasattr(derivation, "source_interface_ref")
                else derivation.source_interface_id,
                "hash": derivation.source_interface_ref.interface_hash
                if hasattr(derivation, "source_interface_ref")
                else derivation.source_interface_hash,
            },
            "source_frame": None
            if source_frame is None
            and (
                not hasattr(derivation, "source_frame_id")
                or derivation.source_frame_id is None
            )
            else {
                "id": source_frame.frame_id
                if source_frame is not None
                else derivation.source_frame_id,
                "hash": source_frame.frame_hash
                if source_frame is not None
                else derivation.source_frame_hash,
            },
            "source_placement_ref": derivation.source_placement_ref.model_dump(mode="json"),
            "target_member": normalized_id(target_member),
            "target_interface": None
            if target_interface is None
            and (
                not hasattr(derivation, "target_generated_interface_id")
                or derivation.target_generated_interface_id is None
            )
            else {
                "id": target_interface.interface_id
                if target_interface is not None
                else derivation.target_generated_interface_id,
                "hash": target_interface.interface_hash
                if target_interface is not None
                else derivation.target_generated_interface_hash,
            },
            "target_frame": None
            if target_frame is None
            and (
                not hasattr(derivation, "target_generated_frame_id")
                or derivation.target_generated_frame_id is None
            )
            else {
                "id": target_frame.frame_id
                if target_frame is not None
                else derivation.target_generated_frame_id,
                "hash": target_frame.frame_hash
                if target_frame is not None
                else derivation.target_generated_frame_hash,
            },
            "inputs": tuple(item.model_dump(mode="json") for item in derivation.inputs),
            "rotation": None
            if derivation.rotation is None
            else derivation.rotation.model_dump(mode="json"),
        }

    mapping_by_physical = {
        item.physical_instance_id: item for item in cad_realization.mappings
    }
    physical_by_cad = {
        item.cad_instance_id: normalized_id(item.physical_instance_id)
        for item in cad_realization.mappings
    }

    def member_id(value):
        return physical_by_cad.get(value, normalized_id(value))
    return {
        "bodies": tuple(
            (
                normalized_id(body.physical_body_id),
                tuple(normalized_id(item) for item in body.member_physical_instance_ids),
                normalized_id(body.reference_physical_instance_id),
            )
            for body in physical_realization.physical_rigid_body_bindings
        ),
        "root_body": normalized_id(physical_realization.kinematic_root_physical_body_id),
        "joints": tuple(
            (
                normalized_id(joint.physical_joint_id),
                normalized_id(joint.parent_physical_body_id),
                normalized_id(joint.child_physical_body_id),
                normalized_id(joint.connection_id),
                normalized_id(joint.parent_physical_instance_id),
                normalized_id(joint.parent_interface_id),
                normalized_id(joint.child_physical_instance_id),
                normalized_id(joint.child_interface_id),
                enum_value(joint.axis_owner_endpoint),
                joint.axis_sign,
                enum_value(joint.motion_mode),
                joint.min_angle_deg,
                joint.max_angle_deg,
                joint.zero_reference_semantics,
            )
            for joint in physical_realization.physical_revolute_joint_bindings
        ),
        "pairs": tuple(
            (
                normalized_id(pair.first_physical_instance_id),
                normalized_id(pair.second_physical_instance_id),
                enum_value(pair.classification),
                pair.exclusion_reason,
            )
            for pair in pair_bindings
        ),
        "configurations": tuple(
            (
                configuration.model_id,
                tuple(
                    (normalized_id(key), value)
                    for key, value in sorted(configuration.positions.items())
                ),
            )
            for configuration in configurations
        ),
        "placements": tuple(
            (
                normalized_id(physical_id),
                transform_values(mapping_by_physical[physical_id].placement),
            )
            for physical_id in sorted(mapping_by_physical)
        ),
        "member_body_offsets": tuple(
            (
                normalized_id(body.body_id),
                member_id(body.reference_member_instance_id),
                tuple(
                    (
                        member_id(member.member_instance_id),
                        transform_values(member.reference_to_member_home),
                    )
                    for member in body.members
                ),
            )
            for body in sorted(bridge.model.bodies, key=lambda item: item.body_id)
        ),
        "placement_derivations": tuple(
            derivation_values(derivation)
            for derivation in sorted(
                placement_derivations, key=lambda item: item.derivation_id
            )
        ),
        "exact_checked_pair_scope": tuple(
            (
                member_id(pair.first_instance_id),
                member_id(pair.second_instance_id),
            )
            for pair in exact_pair_scope
        ),
        "volume_tolerance_mm3": volume_tolerance_mm3,
        "distance_tolerance_mm": distance_tolerance_mm,
        "cad_inventory": tuple(
            (
                next(
                    normalized_id(physical_id)
                    for physical_id, mapping in mapping_by_physical.items()
                    if mapping.cad_instance_id == item.first_instance_id
                ),
                next(
                    normalized_id(physical_id)
                    for physical_id, mapping in mapping_by_physical.items()
                    if mapping.cad_instance_id == item.second_instance_id
                ),
            )
            for item in bridge.inventory.entries
        ),
        "cad_representations": tuple(
            (
                normalized_id(mapping.physical_instance_id),
                enum_value(mapping.fidelity),
            )
            for mapping in sorted(
                cad_realization.mappings,
                key=lambda item: item.physical_instance_id,
            )
        ),
    }


def _apply_n_plus_one_name_change(application, source, mechanism):
    run = application.run_controller.create_run(
        application.project_id,
        expected_source=SourceBinding(
            project_id=application.project_id,
            revision=source.revision,
            state_hash=source.state_hash,
        ),
    )
    changed = mechanism.model_copy(
        update={"name": "M13-4 T16 N+1 state", "mechanism_hash": "pending"}
    )
    proposal = ChangeProposal(
        id="CP-M13-4-T16-NPLUS1",
        title="M13-4 representative N+1 source advance",
        status=ProposalStatus.ACCEPTED,
        base_revision=source.revision,
        base_state_hash=source.state_hash,
        actor="mechcad-physical-mechanism",
        operations=[
            ChangeOperation(
                operation=OperationType.REPLACE,
                path=f"/physical_mechanisms/{mechanism.id}",
                value=changed.model_dump(mode="json"),
            )
        ],
    )
    return application.run_controller.apply_approved_proposal(run.run_id, proposal)


def test_m13_4_representative_canonical_m10_full_stack_capstone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    discovery = discover_freecad()
    assert discovery.available is True
    assert discovery.executable == os.environ.get("MECHCAD_FREECADCMD")
    backend_provenance = FreeCADBackend().provenance()
    assert backend_provenance.backend_name == "freecad"
    assert backend_provenance.library_version == "1.1.3"

    fixture = build_m134_fixture(tmp_path)
    application = fixture.application
    source_before = application.load_state()
    assert M11_STATUS == "UNRESOLVED"
    assert M11_ELIGIBLE is False
    assert {item.id for item in source_before.state.requirements} == {
        "REQ-M13-4-GENERATED-GEOMETRY",
    }
    assert {item.id for item in source_before.state.constraints} == {
        "CON-TRANSMISSION-OUTPUT-INTERFACE",
        "CON-TRANSMISSION-PACKAGING-ENVELOPE",
    }
    assert {
        parameter.key.value for parameter in source_before.state.authoritative_parameters
    } == {
        "transmission.output_interface",
        "transmission.packaging_envelope",
    }
    assert source_before.state.structural_analysis_definitions == []
    assert source_before.state.materials == []
    assert source_before.state.load_cases == []
    assert fixture.candidate.source_binding.project_id == application.project_id
    assert fixture.candidate.source_binding.source_revision == source_before.revision
    assert fixture.candidate.source_binding.source_state_hash == source_before.state_hash
    assert all(reference.value_hash.startswith("sha256:") for reference in fixture.candidate.source_binding.consumed_authority)
    assert {
        reference.path for reference in fixture.candidate.source_binding.consumed_authority
    } >= {"/requirements", "/constraints", "/authoritative_parameters"}
    supplied_specification = fixture.specifications[0]
    assert supplied_specification.component_type == "support-plate"
    assert supplied_specification.supplied_interface_definitions[0].shaft is None
    assert supplied_specification.supplied_interface_definitions[0].mounting_face is not None
    assert all(
        specification.generated_part is not None
        or not specification.supplied_interface_definitions[0].shaft
        for specification in fixture.specifications
    )
    reloaded_supplied_artifact = type(fixture.supplied_artifact).model_validate_json(
        json.dumps(fixture.supplied_artifact.model_dump(mode="json"), sort_keys=True)
    )
    assert reloaded_supplied_artifact == fixture.supplied_artifact
    assert {item.instance_id for item in fixture.candidate.realization.components} == {
        "motor-r",
        "frame-r",
        "shaft-a",
        "hub-a",
        "shaft-b",
        "hub-b",
    }

    cad_stage = application.realize_candidate_cad(
        fixture.candidate,
        fixture.synthesis_request,
        fixture.synthesis_policy,
        fixture.cad_request,
    )
    assert cad_stage.status is CandidateCadStageStatus.SUCCESS
    assert cad_stage.realization is not None
    assert len(cad_stage.realization.mappings) == 6
    assert {mapping.physical_instance_id for mapping in cad_stage.realization.mappings} == {
        "motor-r",
        "frame-r",
        "shaft-a",
        "hub-a",
        "shaft-b",
        "hub-b",
    }
    assert sum(
        mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
        for mapping in cad_stage.realization.mappings
    ) == 1
    assert sum(
        mapping.fidelity is CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY
        for mapping in cad_stage.realization.mappings
    ) == 5
    reloaded_cad_realization = type(cad_stage.realization).model_validate_json(
        json.dumps(cad_stage.realization.model_dump(mode="json"), sort_keys=True)
    )
    assert reloaded_cad_realization.realization_hash == cad_stage.realization.realization_hash
    assert reloaded_cad_realization.assembly_hash == cad_stage.realization.assembly_hash
    trusted_mapping = next(
        mapping
        for mapping in cad_stage.realization.mappings
        if mapping.fidelity is CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
    )
    assert trusted_mapping.source_geometry_identity == fixture.supplied_artifact.sha256
    assert cad_stage.realization.verified_source_content_identities == (
        fixture.supplied_artifact.sha256,
    )

    from mechcad_harness.candidates.multi_joint_m10_bridge import PhysicalToM10V2BridgeCompiler

    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        fixture.candidate,
        cad_stage.realization,
        fixture.cad_request.placement_derivations,
    )
    multi_joint_request = build_m134_multi_joint_request(
        fixture, cad_stage.realization, bridge
    )
    assert len(bridge.model.bodies) == 3
    assert len(bridge.model.joints) == 2
    assert len(bridge.inventory.entries) == 15
    assert len(fixture.candidate.realization.physical_pair_classification_bindings) == 15
    assert len(multi_joint_request.scope.configuration_set.configurations) == 4
    configurations = multi_joint_request.scope.configuration_set.configurations
    assert [configuration.positions for configuration in configurations] == [
        {"J1": 0.0, "J2": 0.0},
        {"J1": 15.0, "J2": 0.0},
        {"J1": 0.0, "J2": 15.0},
        {"J1": 15.0, "J2": 45.0},
    ]
    assert (
        fixture.candidate.realization.physical_revolute_joint_bindings[0]
        .axis_source.source_kind
        == "generated_rotational_interface"
    )
    assert fixture.candidate.realization.physical_revolute_joint_bindings[0].axis_owner_endpoint.value == "child"

    observed_candidate_results = []
    m10_service = application.candidate_multi_joint_m10_evaluation_service
    original_m10_analyzer = m10_service.analyze_multi_joint_collision_sweep_v2

    def observe_candidate_m10(**kwargs):
        result = original_m10_analyzer(**kwargs)
        observed_candidate_results.append(result)
        return result

    monkeypatch.setattr(
        m10_service,
        "analyze_multi_joint_collision_sweep_v2",
        observe_candidate_m10,
    )
    evaluation = application.evaluate_candidate_multi_joint_m10(
        fixture.candidate,
        cad_stage.realization,
        bridge,
        multi_joint_request,
    )
    assert len(observed_candidate_results) == 1
    request = m10_service.reconstruct_m10_request(
        fixture.candidate,
        cad_stage.realization,
        bridge,
        multi_joint_request,
    )
    candidate_result = observed_candidate_results[0]
    candidate_result = type(candidate_result).model_validate_json(
        json.dumps(candidate_result.model_dump(mode="json"), sort_keys=True)
    )
    assert evaluation.m10_v2_request_hash == request.request_hash
    assert evaluation.m10_v2_result_hash == candidate_result.result_hash
    candidate_mapping_by_physical = {
        item.physical_instance_id: item.cad_instance_id
        for item in cad_stage.realization.mappings
    }
    assert len(request.exact_pair_scope) == 11
    assert frozenset({
        candidate_mapping_by_physical["motor-r"],
        candidate_mapping_by_physical["shaft-a"],
    }) in {
        frozenset({pair.first_instance_id, pair.second_instance_id})
        for pair in request.exact_pair_scope
    }
    assert all(
        frozenset({
            candidate_mapping_by_physical["motor-r"],
            candidate_mapping_by_physical["shaft-a"],
        })
        in {
            frozenset({pair.first_instance_id, pair.second_instance_id})
            for pair in configuration.pair_results
        }
        for configuration in candidate_result.configuration_results
    )
    _assert_m10_result(candidate_result, 4, 11, request.exact_pair_scope)
    assert candidate_result.request_hash == request.request_hash
    assert candidate_result.source_assembly_hash == request.source_assembly_hash
    assert candidate_result.model_hash == request.model_hash
    assert all(
        math.isfinite(pair.interference_volume_mm3)
        and math.isfinite(pair.exact_distance_mm)
        for configuration in candidate_result.configuration_results
        for pair in configuration.pair_results
    )
    def candidate_transform(configuration_index, physical_instance_id):
        transforms = {
            item.instance_id: item.transform
            for item in candidate_result.configuration_results[
                configuration_index
            ].instance_world_transforms
        }
        return transforms[candidate_mapping_by_physical[physical_instance_id]]

    assert candidate_transform(0, "motor-r") == candidate_transform(1, "motor-r")
    assert candidate_transform(0, "shaft-a") != candidate_transform(1, "shaft-a")
    assert candidate_transform(0, "shaft-b") != candidate_transform(2, "shaft-b")
    assert candidate_transform(1, "shaft-b") != candidate_transform(3, "shaft-b")
    candidate_m10_evidence = application.get_multi_joint_collision_sweep_evidence(
        candidate_result.result_hash
    )
    assert candidate_m10_evidence is not None
    candidate_provenance = candidate_m10_evidence.analysis_execution_provenance
    assert candidate_provenance is not None
    assert candidate_provenance.request_hash == request.request_hash
    assert candidate_provenance.result_hash == candidate_result.result_hash
    assert candidate_provenance.source_assembly_hash == request.source_assembly_hash
    assert candidate_provenance.model_hash == request.model_hash
    assert candidate_provenance.provider_name == TRANSIENT_MEASUREMENT_PROVIDER_NAME
    assert candidate_provenance.execution_mode == TRANSIENT_MEASUREMENT_EXECUTION_MODE
    assert candidate_provenance.backend_provenance is not None
    assert candidate_provenance.backend_provenance.backend_name == "freecad"
    assert candidate_provenance.backend_provenance.library_version == "1.1.3"

    selection = application.select_candidate_multi_joint(
        fixture.candidate,
        cad_stage.realization,
        bridge,
        multi_joint_request,
        evaluation,
        "m13-4-t16-selector",
        "Selected the exact generic six-constituent candidate chain.",
    )
    selection = type(selection).model_validate_json(
        json.dumps(selection.model_dump(mode="json"), sort_keys=True)
    )
    evaluation = type(evaluation).model_validate_json(
        json.dumps(evaluation.model_dump(mode="json"), sort_keys=True)
    )
    promotion_request = build_m134_promotion_request(
        fixture,
        multi_joint_request,
        evaluation,
        selection,
    )
    with pytest.raises(ValidationError, match="CandidatePromotionRequest"):
        application.promote_selected_candidate(promotion_request)

    observed_compilations = []
    original_compiler = application.candidate_promotion_compiler.compile_multi_joint

    def observe_promotion_compilation(state, request):
        compilation = original_compiler(state, request)
        observed_compilations.append(compilation)
        return compilation

    monkeypatch.setattr(
        application.candidate_promotion_compiler,
        "compile_multi_joint",
        observe_promotion_compilation,
    )
    receipt = application.promote_selected_multi_joint_candidate(promotion_request)
    assert len(observed_compilations) == 1
    compilation = observed_compilations[0]
    assert receipt.compilation == compilation
    assert receipt.compilation.compilation_hash == compilation.compilation_hash
    assert receipt.compilation.projection == compilation.projection
    assert receipt.compilation.projection.projection_hash == compilation.projection.projection_hash
    assert receipt.compilation.mapping == compilation.mapping
    assert compilation.canonical_mechanism.id == "PM-M13-4-T16"
    assert len(compilation.canonical_mechanism.components) == 6
    assert len(compilation.canonical_mechanism.physical_revolute_joint_bindings) == 2
    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED
    assert receipt.applied_revision == source_before.revision + 1
    assert receipt.applied_state_hash == state_hash(
        application.state_manager.load_revision(
            application.project_id, receipt.applied_revision
        )
    )
    receipt_payload = json.loads(
        json.dumps(receipt.model_dump(mode="json"), sort_keys=True)
    )
    receipt_payload["request"] = CandidateMultiJointPromotionRequest.model_validate(
        receipt_payload["request"]
    )
    receipt_payload["readiness"] = MultiJointPromotionReadiness.model_validate(
        receipt_payload["readiness"]
    )
    receipt_payload["compilation"] = CandidatePromotionCompilation.model_validate(
        receipt_payload["compilation"]
    )
    receipt_locator = type(receipt).model_validate(receipt_payload)
    application.verify_multi_joint_promotion_application(receipt_locator)
    assert receipt.decision_artifact_id is not None
    assert receipt.result_artifact_id is not None
    for artifact_id in (receipt.decision_artifact_id, receipt.result_artifact_id):
        assert ArtifactStore(
            application.state_manager.workspace,
            project_id=application.project_id,
            run_id="locator",
            ).read_verified_in_project(artifact_id, expected_type=ArtifactType.JSON)
    decision_artifact, _ = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id="locator",
    ).read_verified_in_project(receipt.decision_artifact_id, expected_type=ArtifactType.JSON)
    assert decision_artifact is not None
    promotion_run = application.run_controller.get_run(
        decision_artifact.run_id, application.project_id
    )
    assert promotion_run.initial_revision == source_before.revision
    event_dir = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "runs"
        / decision_artifact.run_id
        / "events"
    )
    event_types = {
        json.loads(path.read_text(encoding="utf-8"))["event_type"]
        for path in event_dir.glob("EVT-*.json")
    }
    assert {"RUN_CREATED", "REVISION_ADVANCED"} <= event_types
    assert promotion_run.active_revision == receipt.applied_revision
    assert promotion_run.active_state_hash == receipt.applied_state_hash
    promotion_store = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id=promotion_run.run_id,
    )
    promotion_manifest = application.promotion_manifest_service.resolve_multi_joint_result(
        promotion_store, receipt.result_artifact_id
    )
    assert promotion_manifest.changeset_id
    assert promotion_manifest.changed_paths == (
        "/physical_mechanisms/PM-M13-4-T16",
    )
    promotion_invalidation = application.evidence_store.load_invalidation(
        application.project_id, receipt.applied_revision
    )
    assert promotion_invalidation.changeset_id == promotion_manifest.changeset_id
    assert promotion_invalidation.changed_paths == promotion_manifest.changed_paths

    promoted_reconstruction = application.reconstruct_promoted_mechanism(
        revision=receipt.applied_revision,
        state_hash=receipt.applied_state_hash,
        mechanism_id=receipt.request.canonical_target_mechanism_id,
    )
    assert compilation.canonical_mechanism == promoted_reconstruction.mechanism
    assert compilation.canonical_mechanism.mechanism_hash == promoted_reconstruction.mechanism.mechanism_hash
    assert compilation.projection.projection_hash == promoted_reconstruction.normalized_projection_hash

    old_reconstruction = application.reconstruct_promoted_mechanism(
        revision=receipt.applied_revision,
        state_hash=receipt.applied_state_hash,
        mechanism_id=receipt.request.canonical_target_mechanism_id,
    )
    fresh_application = build_m134_application_at(
        application.state_manager.workspace,
        tmp_path / "fresh-configuration",
        application.project_id,
    )
    fresh_reconstruction = fresh_application.reconstruct_promoted_mechanism(
        revision=receipt.applied_revision,
        state_hash=receipt.applied_state_hash,
        mechanism_id=receipt.request.canonical_target_mechanism_id,
    )
    fresh_cad = fresh_application.canonical_cad_compiler.realize(fresh_reconstruction)
    canonical_bridge = compile_canonical(fresh_reconstruction, fresh_cad)
    canonical_m10 = fresh_application.canonical_multi_joint_m10_verification_service.execute(
        fresh_reconstruction, fresh_cad
    )
    assert canonical_m10.request.source_assembly_hash == fresh_cad.assembly_hash
    assert canonical_m10.request.model_hash == canonical_bridge.m10_model_hash
    assert canonical_m10.result.source_assembly_hash == fresh_cad.assembly_hash
    assert canonical_m10.result.model_hash == canonical_bridge.m10_model_hash
    assert canonical_m10.result.request_hash == canonical_m10.request.request_hash
    assert len(canonical_m10.request.exact_pair_scope) == 11
    _assert_m10_result(
        canonical_m10.result, 4, 11, canonical_m10.request.exact_pair_scope
    )
    canonical_evidence = _assert_durable_canonical_m10_evidence(
        fresh_application,
        fresh_reconstruction,
        fresh_cad,
        canonical_bridge,
        canonical_m10,
    )

    candidate_semantics = _semantic_snapshot(
        bridge,
        cad_stage.realization,
        fixture.candidate.realization,
        fixture.candidate.realization.physical_pair_classification_bindings,
        multi_joint_request.scope.configuration_set.configurations,
        exact_pair_scope=request.exact_pair_scope,
        volume_tolerance_mm3=request.volume_tolerance_mm3,
        distance_tolerance_mm=request.distance_tolerance_mm,
        placement_derivations=multi_joint_request.placement_derivations,
    )
    canonical_obligation = fresh_reconstruction.canonical_mechanism.multi_joint_verification_obligations[0]
    canonical_semantics = _semantic_snapshot(
        canonical_bridge,
        fresh_cad,
        fresh_reconstruction.canonical_mechanism,
        fresh_reconstruction.canonical_mechanism.physical_pair_classification_bindings,
        canonical_obligation.configuration_set.configurations,
        exact_pair_scope=canonical_m10.request.exact_pair_scope,
        volume_tolerance_mm3=canonical_m10.request.volume_tolerance_mm3,
        distance_tolerance_mm=canonical_m10.request.distance_tolerance_mm,
        placement_derivations=fresh_reconstruction.canonical_mechanism.generated_placement_derivations,
    )
    assert candidate_semantics == canonical_semantics
    canonical_payload = json.dumps(
        fresh_reconstruction.model_dump(mode="json"), sort_keys=True
    )
    assert fixture.candidate.candidate_hash not in canonical_payload
    assert evaluation.m10_v2_result_hash not in canonical_payload
    equivalence = compare_candidate_canonical_multi_joint_semantics(
        bridge,
        canonical_bridge,
        candidate_cad=cad_stage.realization,
        canonical_cad=fresh_cad,
        candidate_pair_bindings=fixture.candidate.realization.physical_pair_classification_bindings,
        canonical_pair_bindings=fresh_reconstruction.canonical_mechanism.physical_pair_classification_bindings,
        instance_mapping={
            candidate_mapping.physical_instance_id: canonical_mapping.physical_instance_id
            for candidate_mapping in cad_stage.realization.mappings
            for canonical_mapping in fresh_cad.mappings
            if canonical_mapping.physical_instance_id.endswith(
                candidate_mapping.physical_instance_id
            )
        },
        candidate_configurations=multi_joint_request.scope.configuration_set.configurations,
        canonical_configurations=canonical_obligation.configuration_set.configurations,
        candidate_volume_tolerance_mm3=multi_joint_request.scope.volume_tolerance_mm3,
        canonical_volume_tolerance_mm3=canonical_obligation.volume_tolerance_mm3,
        candidate_distance_tolerance_mm=multi_joint_request.scope.distance_tolerance_mm,
        canonical_distance_tolerance_mm=canonical_obligation.distance_tolerance_mm,
        candidate_placement_derivations=multi_joint_request.placement_derivations,
        canonical_placement_derivations=fresh_reconstruction.canonical_mechanism.generated_placement_derivations,
    )
    assert equivalence.equivalent, equivalence.differences

    foreign_candidate = fixture.candidate.model_copy(
        update={
            "source_binding": fixture.candidate.source_binding.model_copy(
                update={"project_id": "PRJ-FOREIGN-M13-4"}
            )
        }
    )
    with pytest.raises(CandidateIntegrityError, match="project binding"):
        application.select_candidate_multi_joint(
            foreign_candidate,
            cad_stage.realization,
            bridge,
            multi_joint_request,
            evaluation,
            "m13-4-foreign-selector",
            "foreign project must be rejected",
        )

    candidate_pair_scope = tuple(
        pair
        for pair in request.exact_pair_scope
        if {
            pair.first_instance_id,
            pair.second_instance_id,
        }
        in (
            {
                candidate_mapping_by_physical["motor-r"],
                candidate_mapping_by_physical["hub-a"],
            },
            {
                candidate_mapping_by_physical["shaft-a"],
                candidate_mapping_by_physical["hub-b"],
            },
        )
    )
    assert len(candidate_pair_scope) == 2
    candidate_q0 = multi_joint_request.scope.configuration_set.configurations[0]
    candidate_q1 = JointConfiguration(
        model_id=bridge.model.model_id,
        positions={joint_id: 1.0 for joint_id in candidate_q0.positions},
    )
    path = MultiJointPath(
        model_id=bridge.model.model_id,
        waypoints=(candidate_q0, candidate_q1),
    )
    candidate_continuous = application.prove_continuous_multi_joint_path_clearance_v2(
        source_revision=source_before.revision,
        source_state_hash=source_before.state_hash,
        assembly=cad_stage.realization.assembly,
        model=bridge.model,
        path=path,
        exact_pair_scope=candidate_pair_scope,
        required_clearance_mm=0.0,
        max_depth=8,
        max_exact_evaluations=512,
    )
    assert isinstance(candidate_continuous, MultiJointContinuousClearanceProofResultV2)
    assert candidate_continuous.status in {
        MultiJointContinuousProofStatus.VERIFIED_CLEAR,
        MultiJointContinuousProofStatus.COLLISION_WITNESS,
    }
    assert candidate_continuous.result_hash
    candidate_continuous_evidence = application.get_multi_joint_continuous_proof_evidence(
        candidate_continuous.result_hash
    )
    assert candidate_continuous_evidence is not None
    assert candidate_continuous_evidence.continuous_proof_execution_provenance is not None
    assert candidate_continuous_evidence.continuous_proof_execution_provenance.backend_provenance is not None

    canonical_mapping_by_physical = {
        item.physical_instance_id.rsplit(":", 1)[-1]: item.cad_instance_id
        for item in fresh_cad.mappings
    }
    canonical_pair_scope = tuple(
        pair
        for pair in canonical_m10.request.exact_pair_scope
        if {
            pair.first_instance_id,
            pair.second_instance_id,
        }
        in (
            {
                canonical_mapping_by_physical["motor-r"],
                canonical_mapping_by_physical["hub-a"],
            },
            {
                canonical_mapping_by_physical["shaft-a"],
                canonical_mapping_by_physical["hub-b"],
            },
        )
    )
    assert len(canonical_pair_scope) == 2
    canonical_q0 = canonical_obligation.configuration_set.configurations[0]
    canonical_q1 = JointConfiguration(
        model_id=canonical_bridge.model.model_id,
        positions={joint_id: 1.0 for joint_id in canonical_q0.positions},
    )
    canonical_path = MultiJointPath(
        model_id=canonical_bridge.model.model_id,
        waypoints=(canonical_q0, canonical_q1),
    )
    canonical_continuous = fresh_application.prove_continuous_multi_joint_path_clearance_v2(
        source_revision=receipt.applied_revision,
        source_state_hash=receipt.applied_state_hash,
        assembly=fresh_cad.assembly,
        model=canonical_bridge.model,
        path=canonical_path,
        exact_pair_scope=canonical_pair_scope,
        required_clearance_mm=0.0,
        max_depth=8,
        max_exact_evaluations=512,
    )
    assert canonical_continuous.status in {
        MultiJointContinuousProofStatus.VERIFIED_CLEAR,
        MultiJointContinuousProofStatus.COLLISION_WITNESS,
    }
    assert canonical_continuous.status is candidate_continuous.status
    canonical_continuous_evidence = fresh_application.get_multi_joint_continuous_proof_evidence(
        canonical_continuous.result_hash
    )
    assert canonical_continuous_evidence is not None
    assert canonical_continuous_evidence.continuous_proof_execution_provenance is not None
    assert canonical_continuous_evidence.continuous_proof_execution_provenance.backend_provenance is not None

    # Verify actual persisted source bytes, not only an in-memory hash mutation.
    tampered_workspace = tmp_path / "tampered-workspace"
    shutil.copytree(application.state_manager.workspace, tampered_workspace)
    source_reference = fresh_reconstruction.trusted_source_references[0]
    tampered_source_path = tampered_workspace / source_reference.relative_path
    tampered_source_path.write_bytes(tampered_source_path.read_bytes() + b"tampered")
    tampered_application = build_m134_application_at(
        tampered_workspace,
        tmp_path / "tampered-configuration",
        application.project_id,
    )
    with pytest.raises((CanonicalCadIntegrityError, ValueError), match="source|tampered|missing"):
        tampered_reconstruction = tampered_application.reconstruct_promoted_mechanism(
            revision=receipt.applied_revision,
            state_hash=receipt.applied_state_hash,
            mechanism_id=receipt.request.canonical_target_mechanism_id,
        )
        tampered_application.canonical_cad_compiler.realize(tampered_reconstruction)

    source_after_promotion = application.load_state()
    mechanism = source_after_promotion.state.physical_mechanisms[0]
    advanced = _apply_n_plus_one_name_change(
        application, source_after_promotion, mechanism
    )
    assert advanced.active_revision == source_after_promotion.revision + 1
    assert advanced.active_state_hash != source_after_promotion.state_hash
    invalidation = application.evidence_store.load_invalidation(
        application.project_id, advanced.active_revision
    )
    assert invalidation.changeset_id
    assert invalidation.changed_paths == (f"/physical_mechanisms/{mechanism.id}",)
    assert f"/physical_mechanisms/{mechanism.id}" in invalidation.changed_paths
    if "M134_REPORT_VALUES" in __import__("os").environ:
        print(f"M134_NPLUS1={advanced.active_revision}:{advanced.active_state_hash}")
    with pytest.raises(CandidateCadIntegrityError, match="not current"):
        application.realize_candidate_cad(
            fixture.candidate,
            fixture.synthesis_request,
            fixture.synthesis_policy,
            fixture.cad_request,
        )
    with pytest.raises((CandidateIntegrityError, ValueError), match="current|stale"):
        application.select_candidate_multi_joint(
            fixture.candidate,
            cad_stage.realization,
            bridge,
            multi_joint_request,
            evaluation,
            "m13-4-stale-selector",
            "stale candidate must be rejected",
        )
    stale_source = old_reconstruction.trusted_source_references[0].model_copy(
        update={"sha256": "sha256:" + "0" * 64}
    )
    stale_reconstruction = old_reconstruction.model_copy(
        update={"trusted_source_references": (stale_source,)}
    )
    with pytest.raises(
        (CanonicalCadIntegrityError, ValueError), match="source|tampered|missing"
    ):
        fresh_application.canonical_cad_compiler.realize(stale_reconstruction)

    reloaded = build_m134_application_at(
        application.state_manager.workspace,
        tmp_path / "post-n-plus-one-reload",
        application.project_id,
    ).load_state()
    assert reloaded.revision == advanced.active_revision
    assert reloaded.state_hash == advanced.active_state_hash
    assert application.evidence_store.get_evidence_freshness(
        application.project_id, candidate_m10_evidence.id
    ).value != "current"
    if "M134_REPORT_VALUES" in os.environ:
        report_values = {
            "runtime": {
                "available": discovery.available,
                "executable": discovery.executable,
                "version": discovery.version,
                "provenance": (
                    None
                    if discovery.provenance is None
                    else discovery.provenance.model_dump(mode="json")
                ),
                "backend": backend_provenance.model_dump(mode="json"),
            },
            "source": {
                "project_id": source_before.project_id,
                "revision": source_before.revision,
                "state_hash": source_before.state_hash,
                "artifact_id": fixture.supplied_artifact.artifact_id,
                "artifact_hash": fixture.supplied_artifact.sha256,
            },
            "candidate": {
                "candidate_hash": fixture.candidate.candidate_hash,
                "cad_request_hash": fixture.cad_request.request_hash,
                "cad_realization_hash": cad_stage.realization.realization_hash,
                "assembly_hash": cad_stage.realization.assembly_hash,
                "bridge_hash": bridge.physical_to_m10_bridge_hash,
                "m10_model_hash": bridge.m10_model_hash,
                "inventory_hash": bridge.inventory_hash,
                "pair_scope_hash": bridge.exact_pair_scope_hash,
                "evaluation_hash": evaluation.evaluation_hash,
                "selection_hash": selection.selection_hash,
                "m10_request_hash": request.request_hash,
                "m10_result_hash": candidate_result.result_hash,
                "m10_evidence_id": candidate_m10_evidence.id,
                "minimum_exact_distance_mm": candidate_result.minimum_exact_distance_mm,
            },
            "promotion": {
                "decision_artifact_id": receipt.decision_artifact_id,
                "result_artifact_id": receipt.result_artifact_id,
                "applied_revision": receipt.applied_revision,
                "applied_state_hash": receipt.applied_state_hash,
                "changeset_id": invalidation.changeset_id,
            },
            "canonical": {
                "mechanism_id": fresh_reconstruction.mechanism.id,
                "projection_hash": fresh_reconstruction.normalized_projection_hash,
                "cad_request_hash": fresh_cad.request_hash,
                "cad_realization_hash": fresh_cad.realization_hash,
                "assembly_hash": fresh_cad.assembly_hash,
                "bridge_hash": canonical_bridge.physical_to_m10_bridge_hash,
                "m10_request_hash": canonical_m10.request.request_hash,
                "m10_result_hash": canonical_m10.result.result_hash,
                "m10_evidence_id": canonical_evidence.id,
            },
            "continuous": {
                "candidate_status": candidate_continuous.status.value,
                "candidate_result_hash": candidate_continuous.result_hash,
                "candidate_evidence_id": candidate_continuous_evidence.id,
                "candidate_minimum_certified_lower_clearance_mm": candidate_continuous.minimum_certified_lower_clearance_mm,
                "canonical_status": canonical_continuous.status.value,
                "canonical_result_hash": canonical_continuous.result_hash,
                "canonical_evidence_id": canonical_continuous_evidence.id,
                "canonical_minimum_certified_lower_clearance_mm": canonical_continuous.minimum_certified_lower_clearance_mm,
            },
            "m11": {"status": M11_STATUS, "eligible": M11_ELIGIBLE},
            "n_plus_one": {
                "revision": advanced.active_revision,
                "state_hash": advanced.active_state_hash,
                "evidence_freshness": application.evidence_store.get_evidence_freshness(
                    application.project_id, candidate_m10_evidence.id
                ).value,
            },
        }
        print("M134_REPORT_VALUES=" + json.dumps(report_values, sort_keys=True))


class _UninvokedM134Agent(FakeAgentAdapter):
    def invoke(self, request):
        raise AssertionError("phase B must not invoke an agent adapter")


def _phase_a_m134_to_locator(tmp_path: Path) -> Path:
    fixture = build_m134_fixture(tmp_path)
    application = fixture.application
    source_before = application.load_state()
    cad_stage = application.realize_candidate_cad(
        fixture.candidate,
        fixture.synthesis_request,
        fixture.synthesis_policy,
        fixture.cad_request,
    )
    assert cad_stage.status is CandidateCadStageStatus.SUCCESS
    assert cad_stage.realization is not None

    from mechcad_harness.candidates.multi_joint_m10_bridge import PhysicalToM10V2BridgeCompiler

    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        fixture.candidate,
        cad_stage.realization,
        fixture.cad_request.placement_derivations,
    )
    multi_joint_request = build_m134_multi_joint_request(
        fixture, cad_stage.realization, bridge
    )
    candidate_m10_request = (
        application.candidate_multi_joint_m10_evaluation_service.reconstruct_m10_request(
            fixture.candidate,
            cad_stage.realization,
            bridge,
            multi_joint_request,
        )
    )
    evaluation = application.evaluate_candidate_multi_joint_m10(
        fixture.candidate,
        cad_stage.realization,
        bridge,
        multi_joint_request,
    )
    selection = application.select_candidate_multi_joint(
        fixture.candidate,
        cad_stage.realization,
        bridge,
        multi_joint_request,
        evaluation,
        "m13-4-phase-a-selector",
        "Phase A selected the representative candidate.",
    )
    promotion_request = build_m134_promotion_request(
        fixture,
        multi_joint_request,
        evaluation,
        selection,
    )
    receipt = application.promote_selected_multi_joint_candidate(promotion_request)
    assert receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED
    assert receipt.compilation is not None
    assert receipt.decision_artifact_id is not None
    assert receipt.result_artifact_id is not None
    assert receipt.applied_revision is not None
    assert receipt.applied_state_hash is not None

    lookup = ArtifactStore(
        application.state_manager.workspace,
        project_id=application.project_id,
        run_id="phase-a-lookup",
    )
    decision_meta = lookup.existing_in_project(receipt.decision_artifact_id)
    result_meta = lookup.existing_in_project(receipt.result_artifact_id)
    assert decision_meta is not None
    assert result_meta is not None
    promotion_run = application.run_controller.get_run(
        decision_meta.run_id, application.project_id
    )
    invalidation = application.evidence_store.load_invalidation(
        application.project_id, receipt.applied_revision
    )
    source_revision_path = application.state_manager._revision_path(
        application.project_id, source_before.revision
    )
    source_revision_bytes_sha256 = "sha256:" + hashlib.sha256(
        source_revision_path.read_bytes()
    ).hexdigest()

    semantic_snapshot = json.loads(
        json.dumps(
            _semantic_snapshot(
                bridge,
                cad_stage.realization,
                fixture.candidate.realization,
                fixture.candidate.realization.physical_pair_classification_bindings,
                multi_joint_request.scope.configuration_set.configurations,
                exact_pair_scope=candidate_m10_request.exact_pair_scope,
                volume_tolerance_mm3=candidate_m10_request.volume_tolerance_mm3,
                distance_tolerance_mm=candidate_m10_request.distance_tolerance_mm,
                placement_derivations=multi_joint_request.placement_derivations,
            ),
            sort_keys=True,
        )
    )
    assert {
        "bodies",
        "joints",
        "pairs",
        "configurations",
        "placements",
        "member_body_offsets",
        "placement_derivations",
        "exact_checked_pair_scope",
        "volume_tolerance_mm3",
        "distance_tolerance_mm",
        "cad_inventory",
        "cad_representations",
    } <= set(semantic_snapshot)
    semantic_snapshot_path = tmp_path / "m13-4-phase-a-semantic-snapshot.json"
    semantic_snapshot_path.write_text(
        json.dumps(semantic_snapshot, sort_keys=True),
        encoding="utf-8",
    )
    receipt_path = tmp_path / "m13-4-phase-a-receipt.json"
    receipt_path.write_text(
        receipt.model_dump_json(indent=2),
        encoding="utf-8",
    )
    locator_path = tmp_path / "m13-4-phase-a-locator.json"
    locator_path.write_text(
        json.dumps(
            {
                "workspace": str(application.state_manager.workspace),
                "project_id": application.project_id,
                "fresh_configuration_root": str(tmp_path / "phase-b-configuration"),
                "semantic_snapshot_path": str(semantic_snapshot_path),
                "receipt_path": str(receipt_path),
                "source_revision": source_before.revision,
                "source_state_hash": source_before.state_hash,
                "source_revision_bytes_sha256": source_revision_bytes_sha256,
                "promotion_run_id": promotion_run.run_id,
                "decision_artifact_id": receipt.decision_artifact_id,
                "decision_artifact_hash": decision_meta.sha256,
                "result_artifact_id": receipt.result_artifact_id,
                "result_artifact_hash": result_meta.sha256,
                "changeset_id": invalidation.changeset_id,
                "promoted_revision": receipt.applied_revision,
                "promoted_state_hash": receipt.applied_state_hash,
                "canonical_mechanism_id": receipt.request.canonical_target_mechanism_id,
                "canonical_mechanism_hash": receipt.compilation.canonical_mechanism.mechanism_hash,
                "compilation_hash": receipt.compilation.compilation_hash,
                "projection_hash": receipt.compilation.projection.projection_hash,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return locator_path


def _phase_b_verify_from_locator(locator_path: Path) -> None:
    locator = json.loads(locator_path.read_text(encoding="utf-8"))
    assert locator["project_id"] == PROJECT_ID
    workspace = Path(locator["workspace"])
    fresh_agent = _UninvokedM134Agent(
        AgentIdentity(
            agent_name="m13-4-restart-verifier",
            agent_version="1.0",
            role="m13-4-restart-verifier",
            protocol_version="1.0",
        ),
        scripted_responses=(),
    )
    fresh_application = build_m134_application_at(
        workspace,
        Path(locator["fresh_configuration_root"]),
        locator["project_id"],
        agent=fresh_agent,
    )
    assert fresh_agent.invocation_count == 0

    lookup = ArtifactStore(
        workspace,
        project_id=locator["project_id"],
        run_id="phase-b-lookup",
    )
    decision_meta = lookup.existing_in_project(locator["decision_artifact_id"])
    result_meta = lookup.existing_in_project(locator["result_artifact_id"])
    assert decision_meta is not None
    assert result_meta is not None
    assert decision_meta.sha256 == locator["decision_artifact_hash"]
    assert result_meta.sha256 == locator["result_artifact_hash"]
    assert decision_meta.run_id == locator["promotion_run_id"]
    assert result_meta.run_id == locator["promotion_run_id"]

    store = ArtifactStore(
        workspace,
        project_id=locator["project_id"],
        run_id=locator["promotion_run_id"],
    )
    decision = fresh_application.promotion_manifest_service.resolve_multi_joint_decision(
        store, locator["decision_artifact_id"]
    )
    result = fresh_application.promotion_manifest_service.resolve_multi_joint_result(
        store, locator["result_artifact_id"]
    )
    assert decision.compilation_hash == locator["compilation_hash"]
    assert decision.projection_hash == locator["projection_hash"]
    assert result.changeset_id == locator["changeset_id"]
    assert result.resulting_revision == locator["promoted_revision"]
    assert result.resulting_state_hash == locator["promoted_state_hash"]

    receipt_payload = json.loads(
        Path(locator["receipt_path"]).read_text(encoding="utf-8")
    )
    receipt_payload["request"] = CandidateMultiJointPromotionRequest.model_validate(
        receipt_payload["request"]
    )
    receipt_payload["readiness"] = MultiJointPromotionReadiness.model_validate(
        receipt_payload["readiness"]
    )
    receipt_payload["compilation"] = CandidatePromotionCompilation.model_validate(
        receipt_payload["compilation"]
    )
    receipt = CandidateMultiJointPromotionApplicationResult.model_validate(receipt_payload)
    fresh_application.verify_multi_joint_promotion_application(receipt)
    assert receipt.compilation is not None
    assert receipt.compilation.compilation_hash == locator["compilation_hash"]

    promoted_state = fresh_application.state_manager.load_revision(
        locator["project_id"], locator["promoted_revision"]
    )
    assert state_hash(promoted_state) == locator["promoted_state_hash"]
    run = fresh_application.run_controller.get_run(
        locator["promotion_run_id"], locator["project_id"]
    )
    assert (run.initial_revision, run.initial_state_hash) == (
        locator["source_revision"],
        locator["source_state_hash"],
    )
    assert (run.active_revision, run.active_state_hash) == (
        locator["promoted_revision"],
        locator["promoted_state_hash"],
    )
    event_dir = workspace / "projects" / locator["project_id"] / "runs" / locator["promotion_run_id"] / "events"
    event_types = {
        json.loads(path.read_text(encoding="utf-8"))["event_type"]
        for path in event_dir.glob("EVT-*.json")
    }
    assert {"RUN_CREATED", "REVISION_ADVANCED"} <= event_types

    invalidation = fresh_application.evidence_store.load_invalidation(
        locator["project_id"], locator["promoted_revision"]
    )
    assert invalidation.changeset_id == locator["changeset_id"]
    assert invalidation.changed_paths == (
        f"/physical_mechanisms/{locator['canonical_mechanism_id']}",
    )

    reconstruction = fresh_application.reconstruct_promoted_mechanism(
        revision=locator["promoted_revision"],
        state_hash=locator["promoted_state_hash"],
        mechanism_id=locator["canonical_mechanism_id"],
    )
    assert reconstruction.mechanism.mechanism_hash == locator["canonical_mechanism_hash"]
    canonical_cad = fresh_application.canonical_cad_compiler.realize(reconstruction)
    canonical_bridge = compile_canonical(reconstruction, canonical_cad)
    canonical_m10 = fresh_application.canonical_multi_joint_m10_verification_service.execute(
        reconstruction, canonical_cad
    )
    assert canonical_m10.request.source_assembly_hash == canonical_cad.assembly_hash
    assert canonical_m10.request.model_hash == canonical_bridge.m10_model_hash
    assert canonical_m10.result.source_assembly_hash == canonical_cad.assembly_hash
    assert canonical_m10.result.model_hash == canonical_bridge.m10_model_hash
    _assert_m10_result(
        canonical_m10.result, 4, 11, canonical_m10.request.exact_pair_scope
    )
    _assert_durable_canonical_m10_evidence(
        fresh_application,
        reconstruction,
        canonical_cad,
        canonical_bridge,
        canonical_m10,
    )

    canonical_obligation = reconstruction.canonical_mechanism.multi_joint_verification_obligations[0]
    stored_snapshot = json.loads(
        Path(locator["semantic_snapshot_path"]).read_text(encoding="utf-8")
    )
    canonical_snapshot = json.loads(
        json.dumps(
            _semantic_snapshot(
                canonical_bridge,
                canonical_cad,
                reconstruction.canonical_mechanism,
                reconstruction.canonical_mechanism.physical_pair_classification_bindings,
                canonical_obligation.configuration_set.configurations,
                exact_pair_scope=canonical_m10.request.exact_pair_scope,
                volume_tolerance_mm3=canonical_m10.request.volume_tolerance_mm3,
                distance_tolerance_mm=canonical_m10.request.distance_tolerance_mm,
                placement_derivations=reconstruction.canonical_mechanism.generated_placement_derivations,
            ),
            sort_keys=True,
        )
    )
    assert stored_snapshot == canonical_snapshot

    source_revision_path = fresh_application.state_manager._revision_path(
        locator["project_id"], locator["source_revision"]
    )
    assert "sha256:" + hashlib.sha256(source_revision_path.read_bytes()).hexdigest() == locator[
        "source_revision_bytes_sha256"
    ]


def test_m13_4_serialized_restart_canonical_restart_and_durable_reload(tmp_path: Path):
    locator_path = _phase_a_m134_to_locator(tmp_path)
    _phase_b_verify_from_locator(locator_path)


def test_m13_4_acceptance_fixture_has_no_new_production_surface():
    source = Path(__file__).parents[2] / "src" / "mechcad_harness"
    assert source.is_dir()
    assert not any(path.name.startswith("m13_4") for path in source.rglob("*"))
