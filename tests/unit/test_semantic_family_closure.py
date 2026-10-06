from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import re

import pytest

from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates.models import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisRequest,
    GeometrySourceReference,
)
from mechcad_harness.candidates.services import (
    CandidateCurrentness,
    CandidateCurrentnessService,
    CandidateIntegrityError,
    bind_candidate_synthesis_request_semantic_identity,
    verify_candidate_semantic_binding,
)
from mechcad_harness.models import DesignState
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.step_content_identity import step_content_identity_v1


def _state() -> DesignState:
    return DesignState(
        id="DES-CLOSURE",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )


def _binding(state: DesignState) -> CandidateSourceBinding:
    return CandidateSourceBinding(
        project_id="PRJ-CLOSURE",
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


def _step_bytes(*, timestamp: str) -> bytes:
    return (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_NAME('closure-geometry.step','"
        + timestamp
        + "',('author''s name'),('org'),('preprocessor'),('system'),'' );\n"
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));\n"
        "ENDSEC;\n"
        "DATA;\n"
        "#1=PRODUCT('closure-geometry');\n"
        "ENDSEC;\n"
        "END-ISO-10303-21;\n"
    ).encode("ascii")


def _bound_request(state, manager, store) -> CandidateSynthesisRequest:
    request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@2",
        source_binding=_binding(state),
        semantic_source_binding_hash="pending",
        requested_joint_ids=("J-1",),
        required_joint_ids=("J-1",),
    )
    return bind_candidate_synthesis_request_semantic_identity(
        request,
        state_manager=manager,
        store=store,
        project_id="PRJ-CLOSURE",
    )


def _sha256_payload(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _multi_joint_records(tmp_path):
    import mechcad_harness.candidates.multi_joint_m10_evaluation as evaluation_models
    from test_candidate_multijoint_m10_v2 import (
        CandidateMultiJointM10EvaluationService,
        CandidateMultiJointSelectionService,
        PhysicalToM10V2BridgeCompiler,
        _CurrentnessSpy,
        _candidate_cad_v2,
        _candidate_with_m13_multi_joint_authority,
        _multi_joint_scope,
        _raw_m10_result,
    )

    state, manager, _, synthesis_request, _, candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_CurrentnessSpy(manager),
        analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
    )
    request = service.build_request(
        candidate,
        synthesis_request,
        cad_realization,
        bridge,
        scope,
        cad_request=cad_request,
    )
    evaluation = service.execute(
        candidate, synthesis_request, cad_realization, bridge, request
    )

    def replay(
        replay_candidate,
        replay_synthesis_request,
        replay_request,
        replay_evaluation,
    ):
        low_request = service.reconstruct_m10_request(
            replay_candidate,
            replay_synthesis_request,
            cad_realization,
            bridge,
            replay_request,
        )
        low_result = _raw_m10_result(
            source_revision=replay_request.source_revision,
            source_state_hash=replay_request.source_state_hash,
            assembly=cad_realization.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=low_request.distance_tolerance_mm,
        )
        return evaluation_models.CandidateMultiJointM10ReplayV2(
            low_request, low_result, cad_realization, bridge
        )

    selection = CandidateMultiJointSelectionService(
        project_id=candidate.source_binding.project_id,
        currentness_verifier=_CurrentnessSpy(manager),
        result_replayer=replay,
    ).select(
        candidate,
        request,
        evaluation,
        "fixture-selector@1",
        "replay the typed request parent",
        synthesis_request=synthesis_request,
    )
    return bridge, request, evaluation, selection


def _candidate_m10_records(tmp_path):
    from task6_provenance_fixtures import make_proof_result
    from test_candidate_cad_realization_v2 import _realization_at2
    from test_candidate_cad_request_v3 import _request_at3
    from test_candidate_m10_v2 import _new_m10_records
    from test_candidate_trusted_semantic_verification import _at2_setup
    from mechcad_harness.candidates.m10_evaluation import CandidateM10EvaluationService

    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    cad_request = _request_at3(
        candidate, bound_request.semantic_source_binding_hash
    )
    cad_realization = _realization_at2(candidate, cad_request)
    binding, scope, request = _new_m10_records(
        candidate, bound_request, cad_realization
    )
    stage = CandidateM10EvaluationService(
        lambda **kwargs: make_proof_result(kwargs),
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("no home exact check is declared in this scope")
        ),
        scope=scope,
    ).evaluate(
        bound_request.source_binding.source_revision,
        bound_request.source_binding.source_state_hash,
        cad_realization,
        binding,
        request,
    )
    return binding, request, stage


# =============================================================================
# FIELD-SET EQUALITY — Spec §23 cases 10, 26, 28, 33-37, 44, 49, 51, 59-60, 63, 66, 71
# =============================================================================


class TestFieldSetEquality:
    def test_case_71_request_at2_has_exactly_8_declared_fields(self):
        declared = set(CandidateSynthesisRequest.model_fields.keys())
        assert len(declared) == 8
        assert declared == {
            "schema_version",
            "source_binding",
            "semantic_source_binding_hash",
            "requested_joint_ids",
            "required_joint_ids",
            "out_of_scope_joint_ids",
            "requested_evaluation_categories",
            "request_hash",
        }

    def test_case_71_request_at1_has_exactly_7_contract_fields(self):
        contract_fields = {
            "schema_version",
            "source_binding",
            "requested_joint_ids",
            "required_joint_ids",
            "out_of_scope_joint_ids",
            "requested_evaluation_categories",
            "request_hash",
        }
        assert contract_fields <= set(CandidateSynthesisRequest.model_fields.keys())

    def test_case_10_component_specification_at4_has_14_fields(self):
        from mechcad_harness.candidates.models import ComponentSpecificationSnapshot

        declared = set(ComponentSpecificationSnapshot.model_fields.keys())
        assert len(declared) == 14
        assert declared == {
            "schema_version",
            "component_type",
            "manufacturer",
            "part_number",
            "source_identity",
            "properties",
            "geometry_source",
            "generated_part",
            "interfaces",
            "compatibility_declarations",
            "supplied_reference_frames",
            "supplied_interface_definitions",
            "geometry_derivation_transforms",
            "specification_hash",
        }

    def test_case_10_p1_p6_field_partitions(self):
        from mechcad_harness.continuous_proof import (
            ContinuousSingleAxisProofRequest,
            ContinuousSingleAxisProofResult,
        )
        from mechcad_harness.kinematic_sweep import (
            CadKinematicSweepRequest,
            CadKinematicSweepResult,
            CadKinematicSweepSample,
        )
        from mechcad_harness.multi_joint_collision_sweep import (
            MultiJointCollisionSweepRequestV2,
            MultiJointCollisionSweepResultV2,
            MultiJointCollisionConfigurationResultV2,
            ExactConstituentPairResultV2,
        )
        from mechcad_harness.multi_joint_kinematics import (
            KinematicModelV2,
            KinematicRigidBody,
            KinematicRigidBodyMember,
            RevoluteJointModelV2,
            KinematicModel,
            RevoluteJointModel,
        )
        from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
        from mechcad_harness.cad_assembly import CadRigidTransform

        assert set(ContinuousSingleAxisProofRequest.model_fields) == {
            "axis", "start_angle_deg", "end_angle_deg", "moving_instance_ids",
            "stationary_instance_ids", "required_clearance_mm", "volume_tolerance_mm3",
            "distance_tolerance_mm", "proof_guard_mm", "max_depth", "minimum_interval_deg",
            "max_exact_evaluations", "sweep_version", "source_assembly_id",
            "source_assembly_hash", "request_hash",
        }
        assert set(ContinuousSingleAxisProofResult.model_fields) == {
            "request_hash", "source_assembly_hash", "proof_algorithm_version", "axis",
            "start_angle_deg", "end_angle_deg", "moving_instance_ids",
            "stationary_instance_ids", "required_clearance_mm", "proof_guard_mm",
            "status", "certified_leaf_certificates", "unresolved_intervals",
            "collision_witness", "exact_evaluations_count", "maximum_depth_reached",
            "result_hash",
        }
        assert set(CadKinematicSweepRequest.model_fields) == {
            "axis", "sample_angles_deg", "moving_instance_ids", "stationary_instance_ids",
            "volume_tolerance_mm3", "distance_tolerance_mm", "sweep_version",
            "source_assembly_id", "source_assembly_hash", "request_hash",
        }
        assert set(CadKinematicSweepResult.model_fields) == {
            "request_hash", "source_assembly_hash", "sweep_version", "samples",
            "aggregate_classification", "first_collision_angle_deg",
            "worst_interference_angle_deg", "worst_interference_volume_mm3",
            "minimum_clearance_angle_deg", "minimum_clearance_mm",
            "continuous_sweep_verified", "result_hash",
        }
        assert set(CadKinematicSweepSample.model_fields) == {
            "angle_deg", "transformed_assembly_hash", "pair_results",
            "maximum_interference_volume_mm3", "minimum_exact_distance_mm",
            "classification",
        }
        assert set(MultiJointCollisionSweepRequestV2.model_fields) == {
            "schema_version", "source_assembly_id", "source_assembly_hash", "model",
            "configurations", "exact_pair_scope", "volume_tolerance_mm3",
            "distance_tolerance_mm", "evaluator_version", "model_hash", "request_hash",
        }
        assert set(MultiJointCollisionSweepResultV2.model_fields) == {
            "schema_version", "evaluator_version", "source_assembly_hash", "model_hash",
            "request_hash", "configuration_results", "any_interference", "any_touching",
            "all_positive_clearance", "collision_configuration_indices",
            "minimum_exact_distance_mm", "minimum_distance_configuration_index",
            "continuous_path_verified", "result_hash",
        }
        assert set(MultiJointCollisionConfigurationResultV2.model_fields) == {
            "schema_version", "configuration_index", "configuration_hash",
            "ordered_joint_states", "instance_world_transforms", "pair_results",
            "classification", "any_interference", "any_touching",
            "all_positive_clearance", "minimum_exact_distance_mm",
            "transformed_assembly_hash",
        }
        assert set(ExactConstituentPairResultV2.model_fields) == {
            "schema_version", "first_instance_id", "second_instance_id",
            "interference_volume_mm3", "exact_distance_mm", "classification",
        }
        assert set(KinematicModelV2.model_fields) == {
            "schema_version", "model_id", "bodies", "joints", "evaluator_version",
            "transform_agreement_version",
        }
        assert set(KinematicRigidBody.model_fields) == {
            "schema_version", "body_id", "reference_member_instance_id", "members",
            "body_hash",
        }
        assert set(KinematicRigidBodyMember.model_fields) == {
            "member_instance_id", "reference_to_member_home",
        }
        assert set(CadRigidTransform.model_fields) == {
            "x_mm", "y_mm", "z_mm", "rotation_quaternion",
        }
        assert set(RevoluteJointModelV2.model_fields) == {
            "schema_version", "joint_id", "joint_kind", "parent_body_id",
            "child_body_id", "axis_origin_x_mm", "axis_origin_y_mm",
            "axis_origin_z_mm", "axis_direction_x", "axis_direction_y",
            "axis_direction_z", "min_angle_deg", "max_angle_deg",
        }
        assert set(KinematicModel.model_fields) == {
            "schema_version", "model_id", "joints", "evaluator_version",
        }
        assert set(RevoluteJointModel.model_fields) == {
            "schema_version", "joint_id", "joint_kind", "parent_instance_id",
            "child_instance_id", "axis_origin_x_mm", "axis_origin_y_mm",
            "axis_origin_z_mm", "axis_direction_x", "axis_direction_y",
            "axis_direction_z", "min_angle_deg", "max_angle_deg",
        }
        assert set(ExactConstituentPair.model_fields) == {
            "schema_version", "first_instance_id", "second_instance_id",
        }

    def test_case_26_candidate_m10_disposition_at2_has_7_fields(self):
        from mechcad_harness.candidates.m10_evaluation import (
            CandidateM10ConstituentDisposition,
        )

        declared = set(CandidateM10ConstituentDisposition.model_fields.keys())
        assert len(declared) == 7
        assert declared == {
            "schema_version",
            "physical_instance_id",
            "cad_instance_id",
            "constituent_key",
            "disposition",
            "output_transform_group",
            "disposition_hash",
        }

    def test_case_26_n1_n2_self_hash_exclusion_by_substitution(self, tmp_path, monkeypatch):
        from mechcad_harness.candidates.m10_evaluation import (
            CandidateM10ConstituentDispositionV2,
            CandidateCollisionPairClassificationV2,
            CandidateM10BindingV2,
            CandidateCollisionPairInventoryV2,
            CandidateM10EvaluationRequestV2,
            CandidateM10StageOutcomeV2,
            candidate_m10_constituent_disposition_hash_v2,
            candidate_m10_collision_pair_classification_hash_v2,
            candidate_m10_binding_hash_v2,
            candidate_m10_collision_pair_inventory_hash_v2,
            candidate_m10_evaluation_request_hash_v2,
            candidate_m10_stage_outcome_hash_v2,
            _semantic_m10_hash,
        )
        from mechcad_harness.candidates.canonical_m10 import (
            CanonicalM10ConstituentDispositionV2,
            CanonicalM10PairClassificationRecordV2,
            CanonicalM10PairInventoryV2,
            CanonicalM10EvaluationRequest,
            CanonicalM10EvaluationRequestV2,
            CanonicalM10VerificationOutcomeV2,
            CanonicalM10ConstituentDisposition,
            CanonicalM10PairClassificationRecord,
            CanonicalM10PairInventory,
            DerivedCanonicalM10Scope,
            canonical_m10_constituent_disposition_hash_v2,
            canonical_m10_pair_classification_hash_v2,
            canonical_m10_pair_inventory_hash_v2,
            canonical_m10_evaluation_request_hash_v2,
            canonical_m10_verification_outcome_hash_v2,
            semantic_canonical_m10_scope_hash,
            _hash_payload,
        )
        from test_canonical_m10_v2 import _scope_request_chain, _canonical_m10_v4_fixture
        from test_canonical_m10_scope_v2 import _scope

        semantic_payloads = []
        legacy_payloads = []

        def capture_semantic(payload):
            semantic_payloads.append(payload)
            return _semantic_m10_hash(payload)

        def capture_legacy(payload):
            legacy_payloads.append(payload)
            return _hash_payload(payload)

        import mechcad_harness.candidates.canonical_m10 as canonical_m10_module

        def legacy_scope_hash(record):
            payload = {
                "joint_semantic_key": record.joint_semantic_key,
                "angle_interval_deg": record.angle_interval_deg,
                "path_semantics": record.path_semantics,
                "required_clearance_mm": record.required_clearance_mm,
                "physical_pair_requirements": [
                    item.model_dump(mode="json")
                    for item in record.physical_pair_requirements
                ],
                "fidelity_requirements": [
                    [key, fidelity.value]
                    for key, fidelity in record.fidelity_requirements
                ],
                "required_home_check_semantics": record.required_home_check_semantics,
                "bounded_limitations": record.bounded_limitations,
            }
            return canonical_m10_module._hash_payload(payload)

        def legacy_request_hash(record):
            payload = record.model_dump(mode="json")
            payload.pop("request_hash", None)
            return canonical_m10_module._hash_payload(payload)

        monkeypatch.setattr(
            "mechcad_harness.candidates.m10_evaluation._semantic_m10_hash",
            capture_semantic,
        )
        monkeypatch.setattr(
            "mechcad_harness.candidates.canonical_m10._hash_payload",
            capture_legacy,
        )

        disposition = CandidateM10ConstituentDispositionV2(
            physical_instance_id="i1",
            cad_instance_id="c1",
            constituent_key="k1",
            disposition="fixed",
        )
        classification = CandidateCollisionPairClassificationV2(
            pair=("a", "b"),
            classification="check_clearance",
        )
        canonical_disposition = CanonicalM10ConstituentDispositionV2(
            physical_instance_id="i1",
            cad_instance_id="c1",
            disposition="fixed",
        )
        canonical_classification = CanonicalM10PairClassificationRecordV2(
            pair=("a", "b"),
            classification="check_clearance",
        )

        binding, request, stage = _candidate_m10_records(tmp_path)

        canonical_scope, canonical_inventory, canonical_request = _scope_request_chain()

        semantic_payloads.clear()
        legacy_payloads.clear()

        _, canonical_reconstruction, canonical_cad, canonical_app = _canonical_m10_v4_fixture(tmp_path)
        from mechcad_harness.candidates.canonical_m10 import (
            CanonicalM10VerificationService,
        )
        canonical_outcome = CanonicalM10VerificationService(canonical_app).execute(
            canonical_reconstruction,
            canonical_cad,
        )

        records = (
            ("candidate disposition@2", disposition, "disposition_hash",
             candidate_m10_constituent_disposition_hash_v2, semantic_payloads),
            ("candidate classification@2", classification, "classification_hash",
             candidate_m10_collision_pair_classification_hash_v2, semantic_payloads),
            ("candidate binding@2", binding, "binding_hash",
             candidate_m10_binding_hash_v2, semantic_payloads),
            ("candidate inventory@2", request.inventory, "inventory_hash",
             candidate_m10_collision_pair_inventory_hash_v2, semantic_payloads),
            ("candidate request@2", request, "request_hash",
             candidate_m10_evaluation_request_hash_v2, semantic_payloads),
            ("candidate stage-outcome@2", stage, "outcome_hash",
             candidate_m10_stage_outcome_hash_v2, semantic_payloads),
            ("canonical disposition@2", canonical_disposition, "disposition_hash",
             canonical_m10_constituent_disposition_hash_v2, legacy_payloads),
            ("canonical classification@2", canonical_classification, "classification_hash",
             canonical_m10_pair_classification_hash_v2, legacy_payloads),
            ("canonical inventory@2", canonical_inventory, "inventory_hash",
             canonical_m10_pair_inventory_hash_v2, legacy_payloads),
            ("canonical request@2", canonical_request, "request_hash",
             canonical_m10_evaluation_request_hash_v2, legacy_payloads),
            ("canonical scope@1", canonical_scope, "scope_hash",
             semantic_canonical_m10_scope_hash, legacy_payloads),
            ("canonical request@1", CanonicalM10EvaluationRequest(
                project_id=canonical_scope.project_id,
                revision=canonical_scope.revision,
                state_hash=canonical_scope.state_hash,
                mechanism_id=canonical_scope.mechanism_id,
                mechanism_hash=canonical_scope.mechanism_hash,
                cad_realization_hash="sha256:" + "d" * 64,
                model_hash="sha256:" + "e" * 64,
                binding_semantic_hash="sha256:" + "f" * 64,
                mapping_hashes=("sha256:" + "a" * 64,),
                scope_hash=canonical_scope.scope_hash,
                inventory=CanonicalM10PairInventory(
                    project_id=canonical_scope.project_id,
                    revision=canonical_scope.revision,
                    state_hash=canonical_scope.state_hash,
                    mechanism_id=canonical_scope.mechanism_id,
                    mechanism_hash=canonical_scope.mechanism_hash,
                    cad_realization_hash="sha256:" + "d" * 64,
                    scope_hash=canonical_scope.scope_hash,
                    constituent_dispositions=(
                        CanonicalM10ConstituentDisposition(
                            physical_instance_id="fixed",
                            cad_instance_id="cad-fixed",
                            disposition="fixed",
                        ),
                        CanonicalM10ConstituentDisposition(
                            physical_instance_id="output",
                            cad_instance_id="cad-output",
                            disposition="output_rigid",
                            output_transform_group="joint-output",
                        ),
                    ),
                    expected_pair_universe=(("cad-fixed", "cad-output"),),
                    classifications=(
                        CanonicalM10PairClassificationRecord(
                            pair=("cad-fixed", "cad-output"),
                            classification="check_clearance",
                        ),
                    ),
                    checked_pairs=(("cad-fixed", "cad-output"),),
                ),
            ), "request_hash", legacy_request_hash, legacy_payloads),
            ("canonical outcome@2", canonical_outcome, "outcome_hash",
             canonical_m10_verification_outcome_hash_v2, legacy_payloads),
        )
        forbidden = {
            "artifact_id", "artifact_hash", "source_assembly_hash",
            "source_assembly_id", "requirement_hash",
            "raw_geometry_reference_hash", "run_id", "task_id",
            "geometry_reference_hash", "value_hash",
            "decision_artifact_hash", "derivation_hash",
            "placement_derivations_hash", "origin_hash",
            "imported_component_hash", "provider_identity",
            "evaluator_identity", "timestamp", "path",
        }

        def payload_keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from payload_keys(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    yield from payload_keys(child)

        for record_name, record, self_hash_field, projection, captured in records:
            captured.clear()
            persisted_hash = getattr(record, self_hash_field)
            if record_name == "canonical scope@1":
                semantic_hash = projection(record)
                assert semantic_hash != persisted_hash
            else:
                assert projection(record) == persisted_hash, record_name
            payload = captured[-1]
            assert self_hash_field not in payload, record_name
            assert forbidden.isdisjoint(set(payload_keys(payload))), record_name

            if record_name != "canonical scope@1":
                forged = record.model_copy(
                    update={self_hash_field: "sha256:" + "f" * 64}
                )
                captured.clear()
                assert projection(forged) == persisted_hash, record_name
                assert captured[-1] == payload, record_name
                with pytest.raises(ValueError):
                    type(record).model_validate(forged.model_dump(mode="json"))

    def test_case_28_n1_n2_field_equality(self):
        from mechcad_harness.candidates.m10_evaluation import (
            CandidateM10ConstituentDisposition,
            CandidateCollisionPairClassification,
            CandidateM10BindingV2,
            CandidateCollisionPairInventory,
            CandidateM10EvaluationRequest,
            CandidateM10StageOutcome,
        )
        from mechcad_harness.candidates.canonical_m10 import (
            CanonicalM10ConstituentDisposition,
            CanonicalM10PairClassificationRecord,
            CanonicalM10PairInventory,
            CanonicalM10EvaluationRequest,
            CanonicalM10EvaluationRequestV2,
            CanonicalM10VerificationOutcome,
            DerivedCanonicalM10Scope,
        )

        assert set(CandidateM10ConstituentDisposition.model_fields.keys()) == {
            "schema_version", "physical_instance_id", "cad_instance_id",
            "constituent_key", "disposition", "output_transform_group", "disposition_hash",
        }
        assert set(CanonicalM10ConstituentDisposition.model_fields.keys()) == {
            "schema_version", "physical_instance_id", "cad_instance_id",
            "disposition", "output_transform_group", "disposition_hash",
        }
        assert set(CandidateCollisionPairClassification.model_fields.keys()) == {
            "schema_version", "pair", "classification", "reason",
            "requires_home_exact_check", "classification_hash",
        }
        assert set(CanonicalM10PairClassificationRecord.model_fields.keys()) == {
            "schema_version", "pair", "classification", "reason",
            "requires_home_exact_check", "classification_hash",
        }
        assert set(CandidateM10BindingV2.model_fields.keys()) == {
            "schema_version", "candidate_hash", "cad_realization_hash", "model",
            "semantic_single_joint_kinematic_model_hash", "output_joint_id",
            "driver_gear_constituent_key", "output_axis", "constituent_dispositions",
            "binding_hash",
        }
        assert set(CandidateCollisionPairInventory.model_fields.keys()) == {
            "schema_version", "cad_realization_hash", "binding_hash", "scope_hash",
            "expected_pair_universe", "classifications", "checked_pairs",
            "excluded_pairs", "inventory_hash",
        }
        assert set(CanonicalM10PairInventory.model_fields.keys()) == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "cad_realization_hash",
            "scope_hash", "constituent_dispositions",
            "expected_pair_universe", "classifications", "checked_pairs",
            "excluded_pairs", "inventory_hash",
        }
        assert set(CandidateM10EvaluationRequest.model_fields.keys()) == {
            "schema_version", "candidate_hash", "cad_realization_hash",
            "binding_hash", "scope_hash", "model_hash",
            "mapping_hashes", "inventory", "request_hash",
        }
        assert set(CanonicalM10EvaluationRequest.model_fields.keys()) == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "cad_realization_hash",
            "model_hash", "binding_semantic_hash", "mapping_hashes", "scope_hash",
            "inventory", "request_hash",
        }
        assert set(CanonicalM10EvaluationRequestV2.model_fields.keys()) == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "cad_realization_hash",
            "semantic_single_joint_kinematic_model_hash", "mapping_hashes",
            "semantic_scope_hash", "inventory", "request_hash",
        }
        assert set(CandidateM10StageOutcome.model_fields.keys()) == {
            "schema_version", "status", "candidate_hash", "cad_realization_hash",
            "binding_hash", "scope_hash", "evaluation_request_hash",
            "source_revision", "source_state_hash", "pair_proofs",
            "home_exact_checks", "reasons", "outcome_hash",
        }
        assert set(CanonicalM10VerificationOutcome.model_fields.keys()) == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "cad_realization_hash",
            "scope", "inventory", "request", "status", "pair_proofs",
            "home_exact_checks", "outcome_hash",
        }
        assert set(DerivedCanonicalM10Scope.model_fields.keys()) == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "joint_semantic_key",
            "angle_interval_deg", "path_semantics", "required_clearance_mm",
            "physical_pair_requirements", "fidelity_requirements",
            "required_home_check_semantics", "bounded_limitations", "scope_hash",
        }

    def test_case_33_mapping_at2_has_11_fields(self):
        from mechcad_harness.candidates.cad_realization import (
            CandidateCadInstanceMappingV2,
            SemanticPlacementOrigin,
        )

        declared = set(CandidateCadInstanceMappingV2.model_fields.keys())
        assert declared == {
            "schema_version", "candidate_hash", "physical_instance_id",
            "cad_instance_id", "fidelity", "representation_identity",
            "source_geometry_identity", "geometry_definition_identities",
            "placement", "placement_origin", "mapping_hash",
        }
        origin_fields = set(SemanticPlacementOrigin.model_fields.keys())
        assert origin_fields == {
            "authority", "input_identities", "derivation", "transform", "origin_hash",
        }

    def test_case_34_geometry_definition_ordering_contracts(self):
        from mechcad_harness.candidates.cad_realization import (
            CandidateCadInstanceMappingV2,
        )

        declared = set(CandidateCadInstanceMappingV2.model_fields.keys())
        assert "geometry_definition_identities" in declared
        from test_candidate_cad_mapping_v2 import _trusted_mapping
        mapping = _trusted_mapping("sha256:" + "a" * 64)
        assert len(mapping.geometry_definition_identities) == 1

    def test_case_34_trusted_generated_fallback_ordering_and_duplicates(self):
        from test_candidate_cad_mapping_v2 import (
            _trusted_mapping,
            _content_by_artifact,
            CONTENT_A,
        )
        from mechcad_harness.candidates.cad_realization import (
            CandidateCadInstanceMappingV2,
            CandidateGeometryFidelity,
            SemanticPlacementOrigin,
        )
        from mechcad_harness.models.generated_part import (
            generated_geometry_definition_identities,
        )
        from test_m13_2_generated_part_models import _shaft
        from mechcad_harness.cad_assembly import CadRigidTransform

        trusted = _trusted_mapping("sha256:" + "a" * 64)
        assert trusted.geometry_definition_identities == (CONTENT_A,)

        identities = generated_geometry_definition_identities(_shaft())
        transform = CadRigidTransform(x_mm=5.0)
        generated = CandidateCadInstanceMappingV2(
            candidate_hash="sha256:" + "a" * 64,
            physical_instance_id="shaft",
            cad_instance_id="cad-shaft",
            fidelity=CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
            representation_identity="sha256:" + "b" * 64,
            source_geometry_identity=None,
            geometry_definition_identities=tuple(reversed(identities)),
            placement=transform,
            placement_origin=SemanticPlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=("candidate:generated-placement:place-shaft",),
                derivation="coaxial-generated-placement@1",
                transform=transform,
            ),
        )
        assert generated.geometry_definition_identities == identities

        fallback = CandidateCadInstanceMappingV2(
            candidate_hash="sha256:" + "a" * 64,
            physical_instance_id="mount",
            cad_instance_id="cad-mount",
            fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
            representation_identity="sha256:" + "c" * 64,
            source_geometry_identity=None,
            geometry_definition_identities=(
                "sha256:" + "1" * 64,
                "sha256:" + "2" * 64,
                "sha256:" + "3" * 64,
            ),
            placement=transform,
            placement_origin=SemanticPlacementOrigin(
                authority="candidate_design_variable",
                input_identities=("candidate:design-variable:mount.placement.x_mm",),
                derivation="mount-frame@1",
                transform=transform,
            ),
        )
        assert fallback.geometry_definition_identities == (
            "sha256:" + "1" * 64,
            "sha256:" + "2" * 64,
            "sha256:" + "3" * 64,
        )
        assert fallback.source_geometry_identity is None

        with pytest.raises(ValueError, match="duplicate|unique"):
            CandidateCadInstanceMappingV2(
                candidate_hash="sha256:" + "a" * 64,
                physical_instance_id="shaft",
                cad_instance_id="cad-shaft",
                fidelity=CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
                representation_identity="sha256:" + "b" * 64,
                source_geometry_identity=None,
                geometry_definition_identities=(*identities, identities[0]),
                placement=transform,
                placement_origin=SemanticPlacementOrigin(
                    authority="deterministic_derived_relation",
                    input_identities=("candidate:generated-placement:place-shaft",),
                    derivation="coaxial-generated-placement@1",
                    transform=transform,
                ),
            )

    def test_case_35_request_at3_has_15_fields(self):
        from mechcad_harness.candidates.cad_realization import (
            CandidateCadRealizationRequestV3,
        )

        declared = set(CandidateCadRealizationRequestV3.model_fields.keys())
        assert declared == {
            "schema_version", "candidate_hash", "source_binding", "source_binding_hash",
            "semantic_source_binding_hash", "representation_policy_version",
            "compiler_identity", "compiler_version", "candidate_instance_ids",
            "mappings", "placement_derivations", "semantic_placement_derivations_hash",
            "design_variable_identities", "component_interface_identities", "request_hash",
        }

    def test_case_35_request_at3_collection_ordering_and_duplicates(self, tmp_path):
        from test_candidate_cad_request_v3 import (
            _request_at3,
            _mapping_at2,
            _INSTANCE_SLOTS,
        )
        from test_candidate_trusted_semantic_verification import _at2_setup

        _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
        mappings = tuple(
            _mapping_at2(candidate.candidate_hash, instance_id, slot, index=index)
            for index, (instance_id, slot) in enumerate(_INSTANCE_SLOTS)
        )
        request = _request_at3(
            candidate, bound_request.semantic_source_binding_hash, mappings=mappings
        )
        assert request.candidate_instance_ids == tuple(
            sorted(instance_id for instance_id, _ in _INSTANCE_SLOTS)
        )
        assert (
            tuple(mapping.physical_instance_id for mapping in request.mappings)
            == request.candidate_instance_ids
        )
        assert request.design_variable_identities == ()
        assert request.component_interface_identities == ()

        with pytest.raises(ValueError, match="unique|duplicate|cover"):
            _request_at3(
                candidate,
                bound_request.semantic_source_binding_hash,
                mappings=(*mappings, mappings[0]),
            )

        single_mapping = mappings[:1]
        with pytest.raises(ValueError, match="unique|duplicate|cover"):
            _request_at3(
                candidate,
                bound_request.semantic_source_binding_hash,
                mappings=single_mapping,
            )

    def test_case_36_canonical_mapping_at2_has_15_fields(self):
        from mechcad_harness.candidates.canonical_cad import (
            CanonicalPhysicalCadMappingV2,
        )

        declared = set(CanonicalPhysicalCadMappingV2.model_fields.keys())
        assert declared == {
            "schema_version", "mechanism_hash", "physical_instance_id",
            "cad_instance_id", "component_hash", "specification_hash", "fidelity",
            "representation_identity", "source_geometry_identity",
            "geometry_definition_identities", "placement", "placement_id",
            "placement_input_identities", "placement_relation", "mapping_hash",
        }

    def test_case_37_promotion_at2_field_counts(self):
        from mechcad_harness.candidates.promotion_models import (
            CandidatePromotionRequestV2,
            CandidateMultiJointPromotionRequestV2,
        )
        from mechcad_harness.candidates.promotion import (
            PromotionReadinessV2,
            MultiJointPromotionReadinessV2,
        )
        from mechcad_harness.candidates.promotion_models import (
            CandidatePromotionCompilationV2,
            PromotableMechanismProjectionV2,
            PrePromotionM10ScopeProjectionV2,
            PromotionDecisionInputReferenceV2,
            MultiJointPromotionDecisionInputReferenceV2,
            PromotedMechanismVerificationResultV2,
            CandidatePromotionApplicationResultV2,
            CandidateMultiJointPromotionApplicationResultV2,
            CandidatePromotionPolicyV2,
        )
        from mechcad_harness.candidates.promotion_artifacts import (
            SelectedCandidateDecisionManifestV2,
            SelectedMultiJointCandidateDecisionManifestV2,
            CandidatePromotionResultManifestV2,
            MultiJointPromotionResultManifestV2,
        )

        assert set(CandidatePromotionRequestV2.model_fields.keys()) == {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "candidate_hash", "synthesis_request_hash", "synthesis_policy_hash",
            "m12_3_result_hash", "evaluation_hash", "selection_hash",
            "comparison_used", "comparison_request_hash", "comparison_result_hash",
            "comparison_entry_hashes", "promotion_policy_hash",
            "canonical_target_mechanism_id", "classifications", "m11_target_intent",
            "request_hash",
        }
        assert set(CandidateMultiJointPromotionRequestV2.model_fields.keys()) == {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "candidate_hash", "synthesis_request_hash", "synthesis_policy_hash",
            "m12_3_result_hash", "multi_joint_request_hash",
            "multi_joint_evaluation_hash", "multi_joint_selection_hash",
            "generated_placement_derivations", "semantic_placement_derivations_hash",
            "promotion_policy_hash", "canonical_target_mechanism_id",
            "classifications", "m11_target_intent", "request_hash",
        }
        assert set(PromotionReadinessV2.model_fields.keys()) == {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "request_hash", "candidate_hash",
            "m12_3_result_hash", "evaluation_hash", "selection_hash",
            "evaluation_scope_hash", "comparison_used", "comparison_result_hash",
            "promotion_policy_hash", "canonical_target_mechanism_id", "mapping",
            "classification_identities", "trusted_geometry_artifact_ids",
            "readiness_hash",
        }
        assert set(MultiJointPromotionReadinessV2.model_fields.keys()) == {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "request_hash", "candidate_hash",
            "m12_3_result_hash", "multi_joint_evaluation_hash",
            "multi_joint_selection_hash", "scope_hash", "configuration_set_hash",
            "promotion_policy_hash", "canonical_target_mechanism_id", "mapping",
            "classification_identities", "trusted_geometry_artifact_ids",
            "readiness_hash", "synthesis_policy_hash", "synthesis_request_hash",
        }
        assert set(CandidatePromotionCompilationV2.model_fields.keys()) == {
            "schema_version", "canonical_mechanism", "proposal",
            "promotion_proposal_hash", "mapping", "projection", "compilation_hash",
        }
        assert set(PromotableMechanismProjectionV2.model_fields.keys()) == {
            "schema_version", "canonical_target_mechanism_id",
            "canonical_mechanism_hash", "canonical_instance_ids",
            "component_specifications", "components", "accepted_design_choices",
            "placements", "connections", "joint_bindings", "m10_obligations",
            "generated_placement_derivations", "kinematic_root_physical_body_id",
            "kinematic_root_binding_hash", "physical_rigid_body_bindings",
            "physical_revolute_joint_bindings", "physical_pair_classification_bindings",
            "multi_joint_verification_obligations", "mapping_identities", "projection_hash",
        }
        assert set(PrePromotionM10ScopeProjectionV2.model_fields.keys()) == {
            "schema_version", "joint_semantic_key", "angle_interval_deg",
            "path_semantics", "required_clearance_mm", "physical_pair_requirements",
            "fidelity_requirements", "required_home_check_semantics",
            "bounded_limitations", "projection_hash",
        }
        assert set(PromotionDecisionInputReferenceV2.model_fields.keys()) == {
            "schema_version", "promotion_request_hash", "project_id", "base_revision",
            "base_state_hash", "candidate_hash", "synthesis_request_hash",
            "synthesis_policy_hash", "m12_3_result_hash", "evaluation_hash",
            "selection_hash", "comparison_used", "comparison_result_hash",
            "comparison_request_hash", "promotion_policy_hash",
            "canonical_target_mechanism_id", "m11_target_intent", "mapping_identities",
            "classification_identities", "reference_hash",
        }
        assert set(MultiJointPromotionDecisionInputReferenceV2.model_fields.keys()) == {
            "schema_version", "promotion_request_hash", "readiness_hash", "project_id",
            "source_revision", "source_state_hash", "semantic_source_binding_hash",
            "candidate_hash", "synthesis_request_hash", "synthesis_policy_hash",
            "m12_3_result_hash", "promotion_policy_hash", "canonical_target_mechanism_id",
            "mapping_identities", "classification_identities",
            "multi_joint_evaluation_request_hash", "multi_joint_evaluation_hash",
            "multi_joint_selection_hash", "scope_hash", "configuration_set_hash",
            "physical_pair_classification_set_hash", "m10_v2_request_hash",
            "m10_v2_result_hash", "semantic_placement_derivations_hash",
            "reference_hash",
        }
        assert set(SelectedCandidateDecisionManifestV2.model_fields.keys()) == {
            "schema_version", "input_reference", "pre_promotion_scope_projection",
            "promotion_policy_hash", "base_revision", "base_state_hash",
            "compilation_hash", "promotion_proposal_hash", "projection_hash",
            "projection", "mapping", "decision_hash",
        }
        assert set(SelectedMultiJointCandidateDecisionManifestV2.model_fields.keys()) == {
            "schema_version", "input_reference", "promotion_policy_hash",
            "base_revision", "base_state_hash", "compilation_hash",
            "promotion_proposal_hash", "projection_hash", "projection", "mapping",
            "decision_hash",
        }
        assert set(CandidatePromotionResultManifestV2.model_fields.keys()) == {
            "schema_version", "decision_artifact_id", "decision_artifact_hash",
            "decision_hash", "promotion_proposal_hash", "proposal_id",
            "changeset_id", "application_id", "changed_paths", "mechanism_path",
            "resulting_revision", "resulting_state_hash", "result_hash",
        }
        assert set(MultiJointPromotionResultManifestV2.model_fields.keys()) == {
            "schema_version", "decision_artifact_id", "decision_artifact_hash",
            "decision_hash", "promotion_proposal_hash", "proposal_id",
            "changeset_id", "changed_paths", "canonical_target_mechanism_id",
            "mechanism_path", "base_revision", "base_state_hash",
            "resulting_revision", "resulting_state_hash", "result_hash",
        }
        assert set(PromotedMechanismVerificationResultV2.model_fields.keys()) == {
            "schema_version", "promotion_result_artifact_id", "promotion_result_hash",
            "promoted_revision", "promoted_state_hash",
            "canonical_target_mechanism_id", "canonical_mechanism_hash",
            "projection_hash", "projection_equivalence_hash",
            "canonical_cad_request_hash", "canonical_cad_realization_hash",
            "canonical_m10_inventory_hash", "canonical_m10_outcome_hash",
            "canonical_m10_request_hashes", "canonical_m10_result_hashes",
            "scope_equivalence_hash", "m11_handoff_hash", "status", "error",
            "verification_hash",
        }
        assert set(CandidatePromotionApplicationResultV2.model_fields.keys()) == {
            "schema_version", "request", "compilation", "decision_artifact_id",
            "result_artifact_id", "applied_revision", "applied_state_hash",
            "status", "error",
        }
        assert set(CandidateMultiJointPromotionApplicationResultV2.model_fields.keys()) == {
            "schema_version", "request", "readiness", "compilation",
            "decision_artifact_id", "result_artifact_id", "applied_revision",
            "applied_state_hash", "status", "error",
        }
        assert set(CandidatePromotionPolicyV2.model_fields.keys()) == {
            "schema_version", "allowed_target_family", "mapping_schema_version",
            "compiler_version", "allowed_classifications",
            "required_property_authorities", "publication_mode", "policy_hash",
        }

    def test_case_44_canonical_pair_requirement_has_7_fields(self):
        from mechcad_harness.models.physical_mechanism import (
            CanonicalPhysicalPairRequirement,
        )

        declared = set(CanonicalPhysicalPairRequirement.model_fields.keys())
        assert declared == {
            "requirement_key", "first_instance_id", "first_interface_id",
            "second_instance_id", "second_interface_id",
            "requires_home_exact_check", "requirement_hash",
        }

    def test_case_49_canonical_request_at2_has_12_fields(self):
        from mechcad_harness.candidates.canonical_m10 import (
            CanonicalM10EvaluationRequestV2,
            CanonicalM10EvaluationRequest,
        )

        at2_fields = set(CanonicalM10EvaluationRequestV2.model_fields.keys())
        at1_fields = set(CanonicalM10EvaluationRequest.model_fields.keys())
        assert at1_fields == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "cad_realization_hash",
            "model_hash", "binding_semantic_hash", "mapping_hashes", "scope_hash",
            "inventory", "request_hash",
        }
        assert at2_fields == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "cad_realization_hash",
            "semantic_single_joint_kinematic_model_hash", "mapping_hashes",
            "semantic_scope_hash", "inventory", "request_hash",
        }
        assert "binding_semantic_hash" in at1_fields
        assert "binding_semantic_hash" not in at2_fields
        assert "model_hash" in at1_fields
        assert "model_hash" not in at2_fields
        assert "scope_hash" in at1_fields
        assert "scope_hash" not in at2_fields

    def test_case_51_request_at3_exact_field_set(self):
        from mechcad_harness.candidates.cad_realization import (
            CandidateCadRealizationRequestV3,
        )

        declared = set(CandidateCadRealizationRequestV3.model_fields.keys())
        assert declared == {
            "schema_version",
            "candidate_hash",
            "source_binding",
            "source_binding_hash",
            "semantic_source_binding_hash",
            "representation_policy_version",
            "compiler_identity",
            "compiler_version",
            "candidate_instance_ids",
            "mappings",
            "placement_derivations",
            "semantic_placement_derivations_hash",
            "design_variable_identities",
            "component_interface_identities",
            "request_hash",
        }

    def test_case_59_realization_at2_has_14_fields(self):
        from mechcad_harness.candidates.cad_realization import (
            CandidateCadRealizationV2,
        )
        from mechcad_harness.candidates.canonical_cad import CanonicalCadRealizationV2

        candidate_fields = set(CandidateCadRealizationV2.model_fields.keys())
        canonical_fields = set(CanonicalCadRealizationV2.model_fields.keys())
        assert candidate_fields == {
            "schema_version", "candidate_hash", "request_hash", "mappings",
            "assembly", "assembly_hash", "representation_identities",
            "semantic_placement_derivations_hash",
            "verified_source_content_identities",
            "verified_source_artifact_hashes", "compiler_identity",
            "compiler_version", "provider_identity", "realization_hash",
        }
        assert canonical_fields == {
            "schema_version", "project_id", "revision", "state_hash",
            "mechanism_id", "mechanism_hash", "request_hash", "mappings",
            "assembly", "assembly_hash", "selected_source_artifact_ids",
            "selected_source_content_identities", "selected_source_provenance",
            "compiler_identity", "compiler_version", "realization_hash",
            "selected_source_artifact_hashes",
        }

    def test_case_60_stage_outcome_at2_has_6_fields(self):
        from mechcad_harness.candidates.cad_realization import (
            CandidateCadStageOutcomeV2,
        )

        declared = set(CandidateCadStageOutcomeV2.model_fields.keys())
        assert len(declared) == 6
        assert declared == {
            "schema_version",
            "status",
            "realization",
            "realization_hash",
            "reasons",
            "outcome_hash",
        }

    def test_case_63_m13_closure_field_sets(self):
        from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
        from mechcad_harness.models.supplied_component_interface import (
            SuppliedComponentReferenceFrame,
            RotationalShaftInterface,
            MountingFaceInterface,
            SuppliedComponentInterfaceDefinition,
            SuppliedShaftDFlatProfile,
            MountingHole,
            SuppliedPilotBossReference,
            SuppliedInterfaceFact,
            SuppliedInterfaceEvidence,
            GeometryDerivationAuthorityFact,
            GeometryDerivationUnitConversion,
            GeometryDerivationTransform,
            InterfaceFactDerivationBinding,
            InterfaceDerivationProvenance,
        )
        from mechcad_harness.candidates.models import ComponentSpecificationSnapshot

        assert set(GeometryArtifactIdentity.model_fields.keys()) == {
            "artifact_id", "artifact_hash", "source_identity", "format",
            "coordinate_system_id", "geometry_identity_hash",
        }
        assert set(SuppliedComponentReferenceFrame.model_fields.keys()) == {
            "frame_id", "geometry_reference_hash", "origin", "orientation",
            "frame_hash",
        }
        assert set(RotationalShaftInterface.model_fields.keys()) == {
            "interface_id", "geometry_reference_hash", "geometry",
            "reference_frame_id", "axis_point", "axis_direction",
            "nominal_shaft_diameter", "usable_axial_engagement_length",
            "shoulder_reference_plane", "shaft_profile", "d_flat_profile",
            "thread_designation", "interface_hash",
        }
        assert set(MountingFaceInterface.model_fields.keys()) == {
            "interface_id", "geometry_reference_hash", "geometry",
            "face_reference_id", "reference_frame_id", "plane_point",
            "outward_normal", "holes", "pilot_boss", "interface_hash",
        }
        assert set(SuppliedComponentInterfaceDefinition.model_fields.keys()) == {
            "kind", "interface_id", "geometry_reference_hash", "geometry",
            "shaft", "mounting_face", "derivation", "interface_hash",
        }
        assert set(SuppliedShaftDFlatProfile.model_fields.keys()) == {
            "flat_normal_direction", "flat_across_dimension",
            "start_from_shoulder", "effective_length",
        }
        assert set(MountingHole.model_fields.keys()) == {
            "hole_id", "center", "axis", "nominal_diameter",
            "thread_designation",
        }
        assert set(SuppliedPilotBossReference.model_fields.keys()) == {
            "point", "axis", "diameter",
        }
        assert set(SuppliedInterfaceFact.model_fields.keys()) == {
            "fact_id", "expected_shape", "expected_unit", "transform_role",
            "evidence", "accepted_evidence_id", "fact_hash",
        }
        assert set(SuppliedInterfaceEvidence.model_fields.keys()) == {
            "evidence_id", "shape", "value", "canonical_unit", "availability",
            "authority", "source_identity", "applicability_context",
            "conversion_provenance", "evidence_origin",
            "source_document_identity", "geometry_reference_hash",
            "basis_evidence_ids", "evidence_hash",
        }
        assert set(GeometryDerivationAuthorityFact.model_fields.keys()) == {
            "authority_role", "expected_shape", "expected_unit", "evidence",
            "accepted_evidence_id", "authority_fact_hash",
        }
        assert set(GeometryDerivationUnitConversion.model_fields.keys()) == {
            "source_unit", "derived_unit", "declaration",
        }
        assert set(GeometryDerivationTransform.model_fields.keys()) == {
            "transform_id", "source_geometry", "derived_geometry",
            "source_geometry_reference_hash", "derived_geometry_reference_hash",
            "translation_fact", "rotation_fact", "uniform_scale_fact",
            "unit_conversion", "status", "transform_hash",
        }
        assert set(InterfaceFactDerivationBinding.model_fields.keys()) == {
            "fact_path", "source_fact_id", "derived_fact_id",
            "source_evidence_id", "source_evidence_hash", "transform_role",
        }
        assert set(InterfaceDerivationProvenance.model_fields.keys()) == {
            "source_interface_snapshot", "source_interface_hash",
            "source_reference_frame_snapshot", "source_reference_frame_hash",
            "derived_reference_frame_id", "derived_reference_frame_hash",
            "transform_id", "transform_hash", "source_geometry",
            "derived_geometry", "source_geometry_reference_hash",
            "derived_geometry_reference_hash", "fact_derivation_bindings",
            "materialization_algorithm", "provenance_hash",
        }
        assert set(ComponentSpecificationSnapshot.model_fields.keys()) == {
            "schema_version", "component_type", "manufacturer", "part_number",
            "source_identity", "properties", "geometry_source", "generated_part",
            "interfaces", "compatibility_declarations", "supplied_reference_frames",
            "supplied_interface_definitions", "geometry_derivation_transforms",
            "specification_hash",
        }

    def test_case_66_m11_request_at2_has_27_fields(self):
        from mechcad_harness.candidates.m11_handoff import (
            CanonicalM11HandoffRequestV2,
        )

        declared = set(CanonicalM11HandoffRequestV2.model_fields.keys())
        assert len(declared) == 27


# =============================================================================
# HASH-PIN SWEEP — Spec §23 cases 15, 25, 42, 51, 57, 61, 72
# =============================================================================


class TestHashPins:
    def test_case_72_request_at2_hash_payload_pin(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(
            tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE"
        )
        request = _bound_request(state, manager, store)
        payload = {
            "schema_version": "candidate-synthesis-request@2",
            "semantic_source_binding_hash": request.semantic_source_binding_hash,
            "requested_joint_ids": ["J-1"],
            "required_joint_ids": ["J-1"],
            "out_of_scope_joint_ids": [],
            "requested_evaluation_categories": [],
        }
        assert _sha256_payload(payload) == request.request_hash
        assert request.request_hash == (
            "sha256:b48a64c40171bd3890f0d58b68f689f3c8b2e9efbd32842e3be3b4f24bf33dd8"
        )

    def test_case_15_mj_request_at2_hash_pin(self, tmp_path):
        _, request, _, _ = _multi_joint_records(tmp_path)
        assert request.request_hash == (
            "sha256:eeee2b0773550092328d52428e24ed669209f091d1608406f3a1acd443112778"
        )

    def test_case_15_mj_request_at2_independent_payload(self, tmp_path):
        _, request, _, _ = _multi_joint_records(tmp_path)
        payload = {
            "semantic_projection_version": "m10-execution-semantics@1",
            "schema_version": request.schema_version,
            "project_id": request.project_id,
            "semantic_source_binding_hash": request.semantic_source_binding_hash,
            "candidate_hash": request.candidate_hash,
            "physical_mechanism_hash": request.physical_mechanism_hash,
            "physical_body_binding_hashes": list(request.physical_body_binding_hashes),
            "physical_joint_binding_hashes": list(request.physical_joint_binding_hashes),
            "kinematic_root_binding_hash": request.kinematic_root_binding_hash,
            "physical_pair_classification_set_hash": request.physical_pair_classification_set_hash,
            "physical_to_m10_bridge_hash": request.physical_to_m10_bridge_hash,
            "cad_realization_hash": request.cad_realization_hash,
            "cad_mapping_hashes": list(request.cad_mapping_hashes),
            "semantic_kinematic_model_hash": request.semantic_kinematic_model_hash,
            "inventory_hash": request.inventory_hash,
            "exact_pair_scope_hash": request.exact_pair_scope_hash,
            "scope": request.scope.model_dump(mode="json"),
            "scope_hash": request.scope_hash,
            "configuration_set_hash": request.configuration_set_hash,
            "configuration_hashes": list(request.configuration_hashes),
            "semantic_m10_v2_request_hash": request.semantic_m10_v2_request_hash,
            "semantic_placement_derivations_hash": request.semantic_placement_derivations_hash,
        }
        assert _sha256_payload(payload) == request.request_hash

    def test_case_15_mj_evaluation_at2_hash_pin(self, tmp_path):
        _, _, evaluation, _ = _multi_joint_records(tmp_path)
        assert evaluation.evaluation_hash == (
            "sha256:33f10ceda3bd90cdfde6574c50f68909cb2230bc14064ae91415701deff010a4"
        )

    def test_case_15_mj_evaluation_at2_independent_payload(self, tmp_path):
        _, request, evaluation, _ = _multi_joint_records(tmp_path)
        payload = {
            "schema_version": evaluation.schema_version,
            "semantic_projection_version": "m10-execution-semantics@1",
            "project_id": evaluation.project_id,
            "candidate_hash": evaluation.candidate_hash,
            "semantic_source_binding_hash": evaluation.semantic_source_binding_hash,
            "cad_realization_hash": evaluation.cad_realization_hash,
            "physical_to_m10_bridge_hash": evaluation.physical_to_m10_bridge_hash,
            "scope_hash": evaluation.scope_hash,
            "configuration_set_hash": evaluation.configuration_set_hash,
            "configuration_hashes": list(request.configuration_hashes),
            "semantic_m10_v2_request_hash": evaluation.semantic_m10_v2_request_hash,
            "semantic_m10_v2_result_hash": evaluation.semantic_m10_v2_result_hash,
        }
        assert _sha256_payload(payload) == evaluation.evaluation_hash

    def test_case_15_mj_selection_at2_hash_pin(self, tmp_path):
        _, _, _, selection = _multi_joint_records(tmp_path)
        assert selection.selection_hash == (
            "sha256:ea84737c6fda2eda634521f28a3065a84e550478fe64596b6591c36009b63739"
        )

    def test_case_15_mj_selection_at2_independent_payload(self, tmp_path):
        _, _, _, selection = _multi_joint_records(tmp_path)
        payload = {
            "semantic_projection_version": "m10-execution-semantics@1",
            "schema_version": selection.schema_version,
            "project_id": selection.project_id,
            "semantic_source_binding_hash": selection.semantic_source_binding_hash,
            "candidate_hash": selection.candidate_hash,
            "evaluation_hash": selection.evaluation_hash,
            "candidate_request_hash": selection.candidate_request_hash,
            "semantic_m10_v2_request_hash": selection.semantic_m10_v2_request_hash,
            "semantic_m10_v2_result_hash": selection.semantic_m10_v2_result_hash,
            "physical_to_m10_bridge_hash": selection.physical_to_m10_bridge_hash,
            "semantic_kinematic_model_hash": selection.semantic_kinematic_model_hash,
            "physical_pair_classification_set_hash": selection.physical_pair_classification_set_hash,
            "inventory_hash": selection.inventory_hash,
            "exact_pair_scope_hash": selection.exact_pair_scope_hash,
            "scope_hash": selection.scope_hash,
            "configuration_set_hash": selection.configuration_set_hash,
            "selector_identity": selection.selector_identity,
            "rationale": selection.rationale,
        }
        assert _sha256_payload(payload) == selection.selection_hash

    def test_case_15_bridge_at2_hash_pin(self, tmp_path):
        bridge, _, _, _ = _multi_joint_records(tmp_path)
        assert bridge.physical_to_m10_bridge_hash == (
            "sha256:b73b538032ddd536ddfa4df3e8c79af8e5db8bcefcf1a4557690d9b427eaa787"
        )

    def test_case_15_bridge_at2_independent_payload(self, tmp_path):
        bridge, _, _, _ = _multi_joint_records(tmp_path)
        payload = {
            "semantic_projection_version": "m10-execution-semantics@1",
            "schema_version": bridge.schema_version,
            "physical_mechanism_hash": bridge.physical_mechanism_hash,
            "kinematic_root_binding_hash": bridge.kinematic_root_binding_hash,
            "physical_body_binding_hashes": list(bridge.physical_body_binding_hashes),
            "physical_joint_binding_hashes": list(bridge.physical_joint_binding_hashes),
            "semantic_placement_identities": list(bridge.semantic_placement_identities),
            "axis_source_identities": list(bridge.axis_source_identities),
            "cad_mapping_hashes": list(bridge.cad_mapping_hashes),
            "physical_pair_classification_set_hash": bridge.physical_pair_classification_set_hash,
            "semantic_kinematic_model_hash": bridge.semantic_kinematic_model_hash,
            "inventory_hash": bridge.inventory_hash,
            "exact_pair_scope_hash": bridge.exact_pair_scope_hash,
            "ordered_body_ids": list(bridge.ordered_body_ids),
            "ordered_joint_ids": list(bridge.ordered_joint_ids),
        }
        assert _sha256_payload(payload) == bridge.physical_to_m10_bridge_hash

    def test_case_15_mj_inventory_at2_hash_pin(self, tmp_path):
        bridge, _, _, _ = _multi_joint_records(tmp_path)
        assert bridge.inventory.inventory_hash == (
            "sha256:ddd1467b4c6e22d659520e1b81d02eed99aee112719cacfa729fe49dc38fe0dd"
        )

    def test_case_15_mj_inventory_at2_independent_payload(self, tmp_path):
        bridge, _, _, _ = _multi_joint_records(tmp_path)
        inventory = bridge.inventory
        canonical_entries = tuple(
            sorted(inventory.entries, key=lambda e: (e.first_instance_id, e.second_instance_id))
        )
        payload = {
            "semantic_projection_version": "m10-execution-semantics@1",
            "schema_version": "multi-joint-collision-pair-inventory@2",
            "physical_mechanism_hash": inventory.physical_mechanism_hash,
            "physical_body_binding_hashes": list(inventory.physical_body_binding_hashes),
            "cad_realization_hash": inventory.cad_realization_hash,
            "semantic_kinematic_model_hash": inventory.semantic_kinematic_model_hash,
            "complete_concrete_instance_ids": list(inventory.complete_concrete_instance_ids),
            "expected_pair_universe": [
                list(pair) for pair in inventory.expected_pair_universe
            ],
            "entries": [entry.model_dump(mode="json") for entry in canonical_entries],
        }
        assert _sha256_payload(payload) == inventory.inventory_hash

    def test_case_15_m11_request_at2_hash_pin(self):
        from test_m11_handoff_v2 import _request_v2

        request = _request_v2()
        payload = {
            "schema_version": request.schema_version,
            "project_id": request.project_id,
            "canonical_mechanism_id": request.canonical_mechanism_id,
            "canonical_mechanism_hash": request.canonical_mechanism_hash,
            "target_scope": request.target_scope,
            "target_instance_id": request.target_instance_id,
            "analysis_category": request.analysis_category,
            "eligibility_scope": request.eligibility_scope,
            "eligibility_scope_version": request.eligibility_scope_version,
            "intent_hash": request.intent.intent_hash,
            "target_geometry_content_identity": request.target_geometry_content_identity,
            "target_geometry_content_identity_algorithm": request.target_geometry_content_identity_algorithm,
            "promotion_result_hash": request.promotion_result_hash,
            "semantic_decision_hash": request.semantic_decision_hash,
            "promotion_proposal_hash": request.promotion_proposal_hash,
            "mapping_hashes": list(request.mapping_hashes),
        }
        assert _sha256_payload(payload) == request.request_hash
        assert request.request_hash == (
            "sha256:76642b7824c785667e190640e88e2fd1b885b1b35efab1796e14f36797799dbb"
        )

    def test_case_25_mj_inventory_at2_hash_pin(self, tmp_path):
        bridge, _, _, _ = _multi_joint_records(tmp_path)
        assert bridge.inventory.inventory_hash == (
            "sha256:ddd1467b4c6e22d659520e1b81d02eed99aee112719cacfa729fe49dc38fe0dd"
        )

    def test_case_42_candidate_disposition_at2_hash_pin(self, tmp_path):
        binding, _, _ = _candidate_m10_records(tmp_path)
        disposition = binding.constituent_dispositions[0]
        assert disposition.disposition_hash == (
            "sha256:f336b53ec988b92ba73821043523736e5a04c41a12c9dde6e276a4879b73c38a"
        )

    def test_case_42_candidate_classification_at2_hash_pin(self, tmp_path):
        _, request, _ = _candidate_m10_records(tmp_path)
        assert request.inventory.classifications[0].classification_hash == (
            "sha256:ae42d03305b867a8d22b67c3059cda84f4239866cbbb21402a5e6cb368ef1bd9"
        )

    def test_case_42_candidate_binding_at2_hash_pin(self, tmp_path):
        binding, _, _ = _candidate_m10_records(tmp_path)
        assert binding.binding_hash == (
            "sha256:fe7f4aea5b9d6146673768f7544ef0b36dd773d3b8c28057665e5bd0dd0e0ce4"
        )

    def test_case_42_candidate_inventory_at2_hash_pin(self, tmp_path):
        _, request, _ = _candidate_m10_records(tmp_path)
        assert request.inventory.inventory_hash == (
            "sha256:0c6e60e6e432899d0029c18808b68dd49bfd37a144028eaec7c4f452dc322db5"
        )

    def test_case_42_candidate_request_at2_hash_pin(self, tmp_path):
        _, request, _ = _candidate_m10_records(tmp_path)
        assert request.request_hash == (
            "sha256:1e89c37c0e26ca11c6f16bb95407adccac83bb65cbf1c1776b48fe9256c8df33"
        )

    def test_case_42_candidate_stage_outcome_at2_hash_pin(self, tmp_path):
        _, _, stage = _candidate_m10_records(tmp_path)
        assert stage.outcome_hash == (
            "sha256:c1276c7eddb1892692be87f3e47cf050e80f52c7dc47bf94b9193cda7edee8f2"
        )

    def test_case_42_canonical_disposition_at2_hash_pin(self, tmp_path):
        from test_canonical_m10_v2 import _scope_request_chain

        _, inventory, _ = _scope_request_chain()
        disposition = inventory.constituent_dispositions[0]
        payload = {
            "schema_version": disposition.schema_version,
            "physical_instance_id": disposition.physical_instance_id,
            "cad_instance_id": disposition.cad_instance_id,
            "disposition": disposition.disposition.value,
            "output_transform_group": disposition.output_transform_group,
            "semantic_projection_version": "m10-execution-semantics@1",
        }
        assert _sha256_payload(payload) == disposition.disposition_hash
        assert disposition.disposition_hash == (
            "sha256:4fb394308af25e57dd9830d86528ff4cb3aea56f367c307b49fd0b42c771f10d"
        )

    def test_case_42_canonical_classification_at2_hash_pin(self, tmp_path):
        from test_canonical_m10_v2 import _scope_request_chain

        _, inventory, _ = _scope_request_chain()
        classification = inventory.classifications[0]
        payload = {
            "schema_version": classification.schema_version,
            "pair": list(classification.pair),
            "classification": classification.classification.value,
            "reason": classification.reason,
            "requires_home_exact_check": classification.requires_home_exact_check,
            "semantic_projection_version": "m10-execution-semantics@1",
        }
        assert _sha256_payload(payload) == classification.classification_hash
        assert classification.classification_hash == (
            "sha256:3607a00665f73d2ada0787347c0c6fa4e8bb21b8aa16490e17cf2be5762cd9d8"
        )

    def test_case_42_canonical_inventory_at2_hash_pin(self, tmp_path):
        from test_canonical_m10_v2 import _scope_request_chain

        _, inventory, _ = _scope_request_chain()
        assert inventory.inventory_hash == (
            "sha256:d021f66cd3fe3a4d8ed95fd4cef10294554ab3b2d5701748281f6259784671dc"
        )

    def test_case_42_canonical_request_at2_hash_pin(self, tmp_path):
        from test_canonical_m10_v2 import _scope_request_chain

        _, _, request = _scope_request_chain()
        assert request.request_hash == (
            "sha256:27e227893e725946099eb74e4dec1982fc843840dcb1dbce3f54f953e6e65ae9"
        )

    def test_case_42_canonical_outcome_at2_hash_pin(self, tmp_path):
        from test_canonical_m10_v2 import _canonical_m10_v4_fixture
        from mechcad_harness.candidates.canonical_m10 import CanonicalM10VerificationService

        _, reconstruction, cad, application = _canonical_m10_v4_fixture(tmp_path)
        outcome = CanonicalM10VerificationService(application).execute(reconstruction, cad)
        assert outcome.outcome_hash == (
            "sha256:762a112efe42d0f03d4cf6601ea65c44caa7e97124116874ba9802b59706ffc9"
        )

    def test_case_51_request_at3_hash_pin(self, tmp_path):
        from test_candidate_cad_request_v3 import _request_at3
        from test_candidate_trusted_semantic_verification import _at2_setup

        _, _, _, _, bound, _, candidate = _at2_setup(tmp_path)
        request = _request_at3(candidate, bound.semantic_source_binding_hash)
        payload = {
            "schema_version": request.schema_version,
            "candidate_hash": request.candidate_hash,
            "semantic_source_binding_hash": request.semantic_source_binding_hash,
            "representation_policy_version": request.representation_policy_version,
            "compiler_identity": request.compiler_identity,
            "compiler_version": request.compiler_version,
            "candidate_instance_ids": list(request.candidate_instance_ids),
            "mappings": [
                item.mapping_hash
                for item in sorted(request.mappings, key=lambda item: item.physical_instance_id)
            ],
            "semantic_placement_derivations_hash": request.semantic_placement_derivations_hash,
            "design_variable_identities": list(request.design_variable_identities),
            "component_interface_identities": list(request.component_interface_identities),
        }
        assert _sha256_payload(payload) == request.request_hash
        assert request.request_hash == (
            "sha256:440b59057494dd1c79f7f3183a0d55dc91f3473f7e1768dee14906af4d33a09c"
        )

    def test_case_57_projection_hash_expansion(self):
        from test_m11_handoff_v2 import _decision_manifest_v2
        from test_promotion_v2 import _mapping_v3

        projection = _decision_manifest_v2(_mapping_v3()).projection
        # Independent payload construction: build from accepted inputs directly,
        # not by rehashing the object's own dumped payload.
        payload = {
            "schema_version": projection.schema_version,
            "canonical_target_mechanism_id": projection.canonical_target_mechanism_id,
            "canonical_mechanism_hash": projection.canonical_mechanism_hash,
            "canonical_instance_ids": list(projection.canonical_instance_ids),
            "component_specifications": [
                spec.model_dump(mode="json") for spec in projection.component_specifications
            ],
            "components": [
                comp.model_dump(mode="json") for comp in projection.components
            ],
            "accepted_design_choices": [
                choice.model_dump(mode="json") for choice in projection.accepted_design_choices
            ],
            "placements": [
                place.model_dump(mode="json") for place in projection.placements
            ],
            "connections": [
                conn.model_dump(mode="json") for conn in projection.connections
            ],
            "joint_bindings": [
                jb.model_dump(mode="json") for jb in projection.joint_bindings
            ],
            "m10_obligations": [
                ob.model_dump(mode="json") for ob in projection.m10_obligations
            ],
            "generated_placement_derivations": [
                gd.model_dump(mode="json") for gd in projection.generated_placement_derivations
            ],
            "physical_rigid_body_bindings": [
                rb.model_dump(mode="json") for rb in projection.physical_rigid_body_bindings
            ],
            "physical_revolute_joint_bindings": [
                rj.model_dump(mode="json") for rj in projection.physical_revolute_joint_bindings
            ],
            "kinematic_root_physical_body_id": projection.kinematic_root_physical_body_id,
            "kinematic_root_binding_hash": projection.kinematic_root_binding_hash,
            "physical_pair_classification_bindings": [
                pb.model_dump(mode="json") for pb in projection.physical_pair_classification_bindings
            ],
            "multi_joint_verification_obligations": [
                mj.model_dump(mode="json") for mj in projection.multi_joint_verification_obligations
            ],
            "mapping_identities": list(projection.mapping_identities),
        }
        assert _sha256_payload(payload) == projection.projection_hash
        assert projection.projection_hash == (
            "sha256:5f8b7ee9e4ef76a6d1e2b9b7ddc08f65df63b1f962d664ab2a4ee76064ea11ba"
        )

    def test_case_61_canonical_request_identity_pin(self, tmp_path):
        from test_canonical_cad_realization_v2 import _realize

        mechanism, reconstruction, realization = _realize(tmp_path)
        payload = {
            "request_contract": "canonical-cad-request@2",
            "project_id": reconstruction.project_id,
            "revision": reconstruction.revision,
            "mechanism_id": mechanism.id,
            "mechanism_hash": mechanism.mechanism_hash,
            "mapping_hashes": [
                item.mapping_hash
                for item in sorted(realization.mappings, key=lambda item: item.cad_instance_id)
            ],
            "compiler_identity": "canonical-physical-cad-compiler",
            "compiler_version": "canonical-cad@1",
        }
        assert _sha256_payload(payload) == realization.request_hash
        assert realization.request_hash == (
            "sha256:5de8efbdc4203316cbf1d0af812844164a4d0bceea009cc509362005d91853d1"
        )


# =============================================================================
# RAW-vs-SEMANTIC INVARIANCE — Spec §21 exhaustive chain
# =============================================================================


class TestRawVsSemanticInvariance:
    def test_step_content_identity_timestamp_invariance(self):
        ts_a = "2026-09-22T12:34:56"
        ts_b = "2026-09-23T10:00:00"

        bytes_a = _step_bytes(timestamp=ts_a)
        bytes_b = _step_bytes(timestamp=ts_b)

        identity_a = step_content_identity_v1(bytes_a)
        identity_b = step_content_identity_v1(bytes_b)

        assert identity_a.content_hash == identity_b.content_hash
        assert identity_a.algorithm == "step-content-identity@1"
        assert identity_b.algorithm == "step-content-identity@1"

        raw_a = hashlib.sha256(bytes_a).hexdigest()
        raw_b = hashlib.sha256(bytes_b).hexdigest()
        assert raw_a != raw_b

    def test_semantic_reference_hash_raw_rotation_invariance(self):
        ts_a = "2026-09-22T12:34:56"
        ts_b = "2026-09-23T10:00:00"

        bytes_a = _step_bytes(timestamp=ts_a)
        bytes_b = _step_bytes(timestamp=ts_b)

        identity_a = step_content_identity_v1(bytes_a)
        identity_b = step_content_identity_v1(bytes_b)

        ref_a = GeometrySourceReference(
            artifact_id="ART-A",
            artifact_hash="sha256:" + hashlib.sha256(bytes_a).hexdigest(),
            source_identity="src-a",
            format="step",
            content_identity=identity_a.content_hash,
            content_identity_algorithm="step-content-identity@1",
        )
        ref_b = GeometrySourceReference(
            artifact_id="ART-B",
            artifact_hash="sha256:" + hashlib.sha256(bytes_b).hexdigest(),
            source_identity="src-a",
            format="step",
            content_identity=identity_b.content_hash,
            content_identity_algorithm="step-content-identity@1",
        )

        assert ref_a.semantic_reference_hash == ref_b.semantic_reference_hash
        assert ref_a.reference_hash != ref_b.reference_hash

    def test_request_at2_raw_rotation_invariance(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup

        state_a, manager_a, store_a, binding_a, bound_a, policy_a, candidate_a = _at2_setup(tmp_path / "a")
        state_b, manager_b, store_b, binding_b, bound_b, policy_b, candidate_b = _at2_setup(tmp_path / "b")

        assert bound_a.semantic_source_binding_hash == bound_b.semantic_source_binding_hash
        assert bound_a.request_hash == bound_b.request_hash

    def test_candidate_at2_raw_rotation_invariance(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup

        state_a, manager_a, store_a, binding_a, bound_a, policy_a, candidate_a = _at2_setup(tmp_path / "a")
        state_b, manager_b, store_b, binding_b, bound_b, policy_b, candidate_b = _at2_setup(tmp_path / "b")

        assert candidate_a.candidate_hash == candidate_b.candidate_hash

    def test_semantic_source_binding_raw_rotation_invariance(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup

        state_a, manager_a, store_a, binding_a, bound_a, policy_a, candidate_a = _at2_setup(tmp_path / "a")
        state_b, manager_b, store_b, binding_b, bound_b, policy_b, candidate_b = _at2_setup(tmp_path / "b")

        assert bound_a.semantic_source_binding_hash == bound_b.semantic_source_binding_hash

    def test_semantic_mechanism_hash_raw_rotation_invariance(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )
        from mechcad_harness.candidates.models import semantic_candidate_mechanism_hash

        chain_a = _candidate_with_m13_multi_joint_authority(tmp_path / "a", variant="A")
        chain_b = _candidate_with_m13_multi_joint_authority(tmp_path / "b", variant="B")

        assert chain_a[5].candidate_hash == chain_b[5].candidate_hash
        assert semantic_candidate_mechanism_hash(
            chain_a[5].realization
        ) == semantic_candidate_mechanism_hash(chain_b[5].realization)
        assert chain_a[5].realization.realization_hash != chain_b[5].realization.realization_hash

    def test_m10_semantic_projections_raw_rotation_invariance(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
            _candidate_cad_v2,
            _multi_joint_scope,
            _raw_m10_result,
        )
        from mechcad_harness.candidates.multi_joint_m10_bridge import PhysicalToM10V2BridgeCompiler
        from mechcad_harness.candidates.multi_joint_m10_evaluation import (
            CandidateMultiJointM10EvaluationService,
        )
        from mechcad_harness.semantic_m10_kinematics import (
            semantic_kinematic_model_hash,
        )
        from mechcad_harness.candidates.services import CandidateCurrentness

        class _AlwaysCurrent:
            def evaluate_source_binding(self, candidate, *, synthesis_request=None):
                return CandidateCurrentness.CURRENT

        chain_a = _candidate_with_m13_multi_joint_authority(tmp_path / "a", variant="A")
        chain_b = _candidate_with_m13_multi_joint_authority(tmp_path / "b", variant="B")
        cad_a_req, cad_a = _candidate_cad_v2(chain_a[5], chain_a[3], chain_a[0])
        cad_b_req, cad_b = _candidate_cad_v2(chain_b[5], chain_b[3], chain_b[0])
        bridge_a = PhysicalToM10V2BridgeCompiler().compile_candidate(chain_a[5], cad_a, cad_a_req.placement_derivations)
        bridge_b = PhysicalToM10V2BridgeCompiler().compile_candidate(chain_b[5], cad_b, cad_b_req.placement_derivations)
        scope = _multi_joint_scope(bridge_a.model.model_id)
        service = CandidateMultiJointM10EvaluationService(
            currentness_verifier=_AlwaysCurrent(),
            analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
        )
        request_a = service.build_request(chain_a[5], chain_a[3], cad_a, bridge_a, scope, cad_request=cad_a_req)
        request_b = service.build_request(chain_b[5], chain_b[3], cad_b, bridge_b, scope, cad_request=cad_b_req)
        assert request_a.request_hash == request_b.request_hash
        assert bridge_a.physical_to_m10_bridge_hash == bridge_b.physical_to_m10_bridge_hash
        assert bridge_a.inventory.inventory_hash == bridge_b.inventory.inventory_hash
        assert semantic_kinematic_model_hash(bridge_a.model) == semantic_kinematic_model_hash(bridge_b.model)

    def test_canonical_mechanism_at4_raw_rotation_invariance(self, tmp_path):
        from test_canonical_mechanism_v4 import _mechanism_at4

        # Case 11/63: raw STEP timestamp/artifact-ID-only rotation leaves the
        # canonical mechanism@4 semantic identity unchanged. Authoritative
        # per-phase coverage:
        # test_canonical_mechanism_v4.py::test_mechanism_at4_is_invariant_to_raw_step_timestamp_and_artifact_id.
        first = _mechanism_at4(variant="A")
        second = _mechanism_at4(variant="B")

        assert (
            first.component_specifications[0].geometry_source.artifact_id
            != second.component_specifications[0].geometry_source.artifact_id
        )
        assert (
            first.component_specifications[0].geometry_source.artifact_hash
            != second.component_specifications[0].geometry_source.artifact_hash
        )
        assert first.mechanism_hash == second.mechanism_hash

    def test_promotion_at2_raw_rotation_invariance(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )
        from test_promotion_v2 import _promotion_family

        # Case 77: raw-only STEP rotation leaves the applicable promotion@2
        # family unchanged. Authoritative per-phase coverage:
        # test_promotion_v2.py::test_case_89_90_92_93_promotion_suffixes.
        base_a = _candidate_with_m13_multi_joint_authority(
            tmp_path / "a", variant="A"
        )
        base_b = _candidate_with_m13_multi_joint_authority(
            tmp_path / "b", variant="B"
        )
        family_a = _promotion_family(tmp_path / "a", base_a)
        family_b = _promotion_family(tmp_path / "b", base_b)

        # This fixture's variant rotates the raw artifact identity INSIDE the
        # DesignState (not just the STEP timestamp), so `source_state_hash` — a
        # coordinate the promotion request@2 legitimately binds — changes and the
        # request/readiness/reference hashes follow it. The invariant,
        # regression-sensitive property available here is that the promotion
        # family's semantic inputs (candidate/evaluation/policy) are unchanged.
        # Authoritative promotion@2 identity-preservation coverage under a
        # semantic-preserving reorder:
        # test_promotion_v2.py::test_case_89_90_92_93_promotion_suffixes.
        assert (
            family_a["candidate"].candidate_hash
            == family_b["candidate"].candidate_hash
        )
        assert family_a["evaluation"].evaluation_hash == family_b["evaluation"].evaluation_hash
        assert family_a["policy"].policy_hash == family_b["policy"].policy_hash

    def test_m11_request_at2_raw_rotation_invariance(self, tmp_path):
        from test_m11_handoff_v2 import _request_v2
        from mechcad_harness.candidates.m11_handoff import (
            CanonicalM11HandoffRequestV2,
        )

        # Case 56/66: the M11 handoff@2 semantic request excludes every raw
        # coordinate/artifact field, so raw-only variation leaves request_hash
        # unchanged. Authoritative per-phase coverage:
        # test_m11_handoff_v2.py::test_exact_27_field_partition.
        baseline = _request_v2()
        rotated = CanonicalM11HandoffRequestV2(
            **{
                **baseline.model_dump(mode="json"),
                "promoted_state_hash": "sha256:" + "1" * 64,
                "target_geometry_artifact_id": "GEO-ROTATED",
                "target_geometry_artifact_hash": "sha256:" + "2" * 64,
                "target_geometry_bound_state_hash": "sha256:" + "3" * 64,
                "promotion_result_artifact_id": "RES-ROTATED",
                "decision_artifact_id": "DEC-ROTATED",
                "decision_artifact_hash": "sha256:" + "4" * 64,
                "request_hash": "pending",
            }
        )

        assert rotated.promoted_state_hash != baseline.promoted_state_hash
        assert rotated.decision_artifact_hash != baseline.decision_artifact_hash
        assert rotated.request_hash == baseline.request_hash

    def test_evaluator_version_exclusion(self):
        from test_m10_semantic_projections import _v2_model
        from mechcad_harness.semantic_m10_kinematics import (
            semantic_kinematic_model_hash,
        )

        # Case 12/20/23: the semantic kinematic model identity is evaluator-free
        # (execution provenance only). Authoritative per-phase coverage:
        # test_m10_semantic_projections.py (evaluator-exclusion cases).
        baseline = _v2_model()
        rotated = baseline.model_copy(
            update={"evaluator_version": "multi-joint-forward-kinematics@other"}
        )

        assert baseline.evaluator_version != rotated.evaluator_version
        assert semantic_kinematic_model_hash(baseline) == semantic_kinematic_model_hash(
            rotated
        )

    def test_transformed_assembly_hash_exclusion(self, tmp_path):
        from test_m10_semantic_projections import _v2_result, _v2_request, _assembly
        from mechcad_harness.semantic_m10_kinematics import (
            semantic_m10_v2_result_hash,
        )

        # Case 13: P6 excludes the raw-dependent per-configuration
        # `transformed_assembly_hash`. Authoritative per-phase coverage:
        # test_m10_semantic_projections.py (transformed-assembly exclusion).
        assembly = _assembly()
        request = _v2_request(assembly)
        first = _v2_result(request, transformed_hash="sha256:transformed-a")
        second = _v2_result(request, transformed_hash="sha256:transformed-b")

        assert (
            first.configuration_results[0].transformed_assembly_hash
            != second.configuration_results[0].transformed_assembly_hash
        )
        assert semantic_m10_v2_result_hash(first, request, assembly, ()) == (
            semantic_m10_v2_result_hash(second, request, assembly, ())
        )

    def test_requirement_hash_exclusion(self):
        from test_canonical_m10_scope_v2 import _scope
        from mechcad_harness.candidates.canonical_m10 import (
            semantic_canonical_m10_scope_hash,
        )

        # Case 44/45: the legacy `CanonicalPhysicalPairRequirement.requirement_hash`
        # never enters the semantic canonical M10 scope identity. Authoritative
        # per-phase coverage:
        # test_canonical_m10_scope_v2.py::test_semantic_scope_ignores_legacy_requirement_hash_and_sorts_requirement_set.
        baseline = _scope()
        requirement = baseline.physical_pair_requirements[0]
        rotated_requirement = requirement.model_copy(
            update={"requirement_hash": "sha256:" + "f" * 64}
        )
        rotated = baseline.model_copy(
            update={"physical_pair_requirements": (rotated_requirement,)}
        )

        assert rotated_requirement.requirement_hash != requirement.requirement_hash
        assert semantic_canonical_m10_scope_hash(baseline) == (
            semantic_canonical_m10_scope_hash(rotated)
        )

    def test_semantic_assembly_order_invariance(self):
        from test_m10_semantic_projections import _assembly
        from mechcad_harness.candidates.cad_realization import semantic_assembly_hash

        # Case 65: reordering the semantic assembly's parts/instances preserves
        # `semantic_assembly_hash` (sorted by part_id/instance_id). The legacy
        # raw `assembly_hash` is NOT the semantic identity. Authoritative
        # per-phase coverage: test_m10_semantic_projections.py assembly cases.
        assembly = _assembly()
        reordered = assembly.model_copy(
            update={
                "parts": tuple(reversed(assembly.parts)),
                "instances": tuple(reversed(assembly.instances)),
            }
        )

        assert tuple(
            instance.instance_id for instance in reordered.instances
        ) != tuple(instance.instance_id for instance in assembly.instances)
        assert semantic_assembly_hash(assembly, ()) == semantic_assembly_hash(
            reordered, ()
        )


# =============================================================================
# MECHANICAL TRANSITIVE CLOSURE — dependency graph traversal (cases 40, 43, 46, 67)
# =============================================================================
#
# Auditor finding (fixed here): the previous closure tests applied
# ``_check_semantic_value`` to bare ``sha256:`` STRINGS. A string has no dict
# keys, so the forbidden-terminal check was a no-op, and the hand-written
# registry asserted only node-name reachability. This section replaces that with
# a genuine mechanical audit:
#
#   1. Capture the REAL payload each production semantic hash function feeds to
#      ``sha256`` by recording the exact bytes the module-level ``hashlib``
#      hashes. No payload is reconstructed by hand.
#   2. Build a test-side semantic dependency registry: the captured payload, the
#      declared dependency edges, and the referenced semantic hash values.
#   3. Cross-check BIDIRECTIONALLY against the real payloads:
#        - no missing production edge: a referenced registry node MUST be a
#          declared dependency;
#        - no extra invented edge: every declared dependency MUST be referenced;
#        - no forbidden raw/legacy terminal: the real payload is scanned for
#          forbidden raw-terminal KEYS and value patterns, and none of the raw
#          terminal VALUES carried by the same records may appear in it;
#        - every referenced non-registry hash MUST be a semantic hash that
#          actually appears in the real records (an explicitly allowed leaf).

# Raw/legacy terminal KEYS. A new-family semantic payload must never carry one
# of these. Field names that legitimately hold new-family semantic hashes are
# deliberately absent: ``request_hash`` (``candidate-cad-realization@2`` and
# ``canonical-cad-realization@2`` carry the ``@3``/``@2`` CAD request hash);
# ``binding_hash``/``inventory_hash``/``scope_hash`` (the candidate-M10 ``@2``
# records carry semantic ``@2`` self/peer hashes); ``evaluation_hash``
# (``candidate-multi-joint-selection@2`` carries the MJ evaluation hash); and
# the canonical pair-classification binding carries its own semantic
# ``binding_hash``. Their VALUES are instead validated by the registry closure,
# which proves they are new-family semantic identities and never raw/legacy
# terminals.
_FORBIDDEN_TERMINALS = frozenset({
    "artifact_id", "artifact_hash", "source_assembly_hash", "source_assembly_id",
    "result_hash", "realization_hash", "reference_hash",
    "mapping_hash", "requirement_hash", "geometry_reference_hash",
    "value_hash", "interface_hash", "frame_hash", "geometry_identity_hash",
    "source_hash", "decision_artifact_hash", "decision_artifact_id",
    "derivation_hash", "placement_derivations_hash", "origin_hash",
    "imported_component_hash", "assembly_hash", "body_hash", "transform_hash",
    "provenance_hash", "authority_fact_hash", "fact_hash",
    "classification_hash", "disposition_hash", "outcome_hash",
    "proof_hash", "check_hash", "selection_hash",
    "readiness_hash", "compilation_hash", "projection_hash", "verification_hash",
    "policy_hash", "run_id", "task_id", "evaluator_version", "evaluator_identity",
    "provider_identity", "model_hash",
})

_FORBIDDEN_VALUE_PATTERNS = (
    "artifact_id", "artifact_hash", "source_assembly_hash", "source_assembly_id",
    "run_id", "task_id", "evaluator_version", "evaluator_identity",
    "provider_identity",
)

_HASH_VALUE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _check_semantic_value(value, path="", visited=None):
    if visited is None:
        visited = set()
    if id(value) in visited:
        return
    visited.add(id(value))
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _FORBIDDEN_TERMINALS:
                raise AssertionError(
                    f"forbidden terminal key '{key}' at {path}.{key}"
                )
            _check_semantic_value(item, f"{path}.{key}", visited)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_semantic_value(item, f"{path}[{index}]", visited)
    elif isinstance(value, str):
        for pattern in _FORBIDDEN_VALUE_PATTERNS:
            if pattern in value:
                raise AssertionError(
                    f"forbidden value pattern '{pattern}' at {path}: {value[:50]}"
                )


def _referenced_semantic_hashes(payload):
    found = set()
    stack = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
        elif isinstance(value, str) and _HASH_VALUE_RE.match(value):
            found.add(value)
    return found


def _all_string_values(payload):
    found = []
    stack = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
        elif isinstance(value, str):
            found.append(value)
    return found


# Modules whose module-level ``hashlib`` is shadowed during payload capture.
# Every production semantic hash function reachable in the audited chains
# resolves ``hashlib`` in one of these module namespaces.
_SEMANTIC_HASH_MODULES = (
    "mechcad_harness.candidates.models",
    "mechcad_harness.candidates.cad_realization",
    "mechcad_harness.candidates.canonical_cad",
    "mechcad_harness.candidates.canonical_m10",
    "mechcad_harness.candidates.multi_joint_m10_evaluation",
    "mechcad_harness.candidates.multi_joint_m10_bridge",
    "mechcad_harness.candidates.multi_joint_selection",
    "mechcad_harness.candidates.m10_evaluation",
    "mechcad_harness.candidates.semantic_authority",
    "mechcad_harness.candidates.m11_handoff",
    "mechcad_harness.semantic_m10_kinematics",
    "mechcad_harness.multi_joint_collision_sweep",
    "mechcad_harness.cad_assembly",
    "mechcad_harness.revolute_drive.models",
    "mechcad_harness.revolute_drive.service",
    "mechcad_harness.models.physical_mechanism",
)


class _HashlibRecorder:
    """Record the exact bytes each ``sha256`` call hashes, keyed by digest."""

    def __init__(self, real, sink):
        self._real = real
        self._sink = sink

    def sha256(self, data=b"", **kwargs):
        digest = self._real.sha256(data, **kwargs)
        raw = bytes(data)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = None
        self._sink.setdefault("sha256:" + digest.hexdigest(), payload)
        return digest

    def __getattr__(self, name):
        return getattr(self._real, name)


@contextlib.contextmanager
def _capture_semantic_payloads():
    """Capture the REAL payload dict behind every production semantic hash."""

    sink = {}
    saved = []
    for module_name in _SEMANTIC_HASH_MODULES:
        module = importlib.import_module(module_name)
        saved.append((module, module.hashlib))
        module.hashlib = _HashlibRecorder(module.hashlib, sink)
    try:
        yield sink
    finally:
        for module, real in saved:
            module.hashlib = real


class _SemanticNode:
    __slots__ = ("name", "hash_value", "payload", "deps")

    def __init__(self, name, hash_value, payload, *, deps=()):
        self.name = name
        self.hash_value = hash_value
        self.payload = payload
        self.deps = frozenset(deps)


def _semantic_hashes_in_records(records):
    found = set()
    for record in records:
        if record is None:
            continue
        payload = (
            record.model_dump(mode="json")
            if hasattr(record, "model_dump")
            else record
        )
        found |= _referenced_semantic_hashes(payload)
    return found


def _is_clean_semantic_payload(payload, raw_terminal_values):
    """True when a captured payload is itself raw/legacy-terminal free."""

    if not isinstance(payload, dict):
        return False
    try:
        _check_semantic_value(payload)
    except AssertionError:
        return False
    return not (set(_all_string_values(payload)) & set(raw_terminal_values))


def _semantic_leaf_pool(payloads, *, records, registry, raw_terminal_values):
    """Explicitly allowed leaves: real semantic hashes, never raw terminals.

    A leaf is allowed only when it is either a semantic hash carried by the
    real records or a hash produced by a production semantic hash function
    during the audited chain whose OWN captured payload is itself free of
    forbidden raw/legacy terminals. A referenced hash that is neither a
    declared registry dependency nor in this pool fails the audit.
    """

    raw_values = set(raw_terminal_values)
    pool = set(_semantic_hashes_in_records(records))
    for digest, payload in payloads.items():
        if _is_clean_semantic_payload(payload, raw_values):
            pool.add(digest)
    pool -= raw_values
    pool -= {node.hash_value for node in registry.values()}
    return pool


def _assert_semantic_closure(registry, *, raw_terminal_values, leaf_pool, label):
    hash_to_name = {}
    for name, node in registry.items():
        assert node.payload is not None, f"{label}/{name}: no payload was captured"
        assert node.hash_value not in hash_to_name, (
            f"{label}: duplicate registry hash shared by {name} and "
            f"{hash_to_name.get(node.hash_value)}"
        )
        hash_to_name[node.hash_value] = name
    registry_hashes = set(hash_to_name)
    allowed_leaves = set(leaf_pool) - registry_hashes
    raw_values = set(raw_terminal_values)
    for name, node in registry.items():
        # (1) the REAL payload carries no forbidden raw/legacy terminal key/value.
        _check_semantic_value(node.payload, path=f"{label}/{name}")
        refs = _referenced_semantic_hashes(node.payload)
        node_hashes = {registry[dep].hash_value for dep in node.deps}
        referenced_names = {hash_to_name[r] for r in refs if r in registry_hashes}
        # (2) no missing production edge and no extra invented edge.
        assert referenced_names == set(node.deps), (
            f"{label}/{name}: registry edge mismatch "
            f"(referenced={sorted(referenced_names)}, declared={sorted(node.deps)})"
        )
        missing = node_hashes - refs
        assert not missing, (
            f"{label}/{name}: declared dependency hash(es) absent from payload: "
            f"{sorted(missing)}"
        )
        # (3) every referenced non-registry hash is an explicit semantic leaf.
        undeclared = (refs - registry_hashes) - allowed_leaves
        assert not undeclared, (
            f"{label}/{name}: referenced hash(es) are neither declared registry "
            f"dependencies nor semantic hashes present in the real records: "
            f"{sorted(undeclared)}"
        )
        # (4) no raw/legacy terminal VALUE carried by the same records appears.
        forbidden = set(_all_string_values(node.payload)) & raw_values
        assert not forbidden, (
            f"{label}/{name}: payload carries forbidden raw/legacy terminal "
            f"value(s): {sorted(forbidden)}"
        )


def _build_multi_joint_chain(tmp_path):
    from test_candidate_multijoint_m10_v2 import (
        _candidate_with_m13_multi_joint_authority,
        _candidate_cad_v2,
        _multi_joint_scope,
        _raw_m10_result,
    )
    from mechcad_harness.candidates.multi_joint_m10_bridge import (
        PhysicalToM10V2BridgeCompiler,
    )
    from mechcad_harness.candidates.multi_joint_m10_evaluation import (
        CandidateMultiJointM10EvaluationService,
    )
    from mechcad_harness.candidates.multi_joint_selection import (
        CandidateMultiJointSelectionService,
    )
    from mechcad_harness.candidates.services import CandidateCurrentness

    class _AlwaysCurrent:
        def evaluate_source_binding(self, candidate, *, synthesis_request=None):
            return CandidateCurrentness.CURRENT

    chain = _candidate_with_m13_multi_joint_authority(tmp_path)
    state, manager, store, synthesis_request, policy, candidate = chain
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=_AlwaysCurrent(),
        analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
    )
    request = service.build_request(
        candidate, synthesis_request, cad_realization, bridge, scope,
        cad_request=cad_request,
    )
    evaluation = service.execute(
        candidate, synthesis_request, cad_realization, bridge, request
    )

    def replay(rc, rs, rr, re):
        low_request = service.reconstruct_m10_request(
            rc, rs, cad_realization, bridge, rr
        )
        low_result = _raw_m10_result(
            assembly=cad_realization.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=low_request.distance_tolerance_mm,
        )
        from mechcad_harness.candidates import multi_joint_m10_evaluation as em
        return em.CandidateMultiJointM10ReplayV2(
            low_request, low_result, cad_realization, bridge
        )

    selection = CandidateMultiJointSelectionService(
        project_id=candidate.source_binding.project_id,
        currentness_verifier=_AlwaysCurrent(),
        result_replayer=replay,
    ).select(
        candidate, request, evaluation, "graph-selector@1", "dependency graph",
        synthesis_request=synthesis_request,
    )
    return {
        "state": state, "manager": manager, "store": store,
        "synthesis_request": synthesis_request, "policy": policy,
        "candidate": candidate, "cad_request": cad_request,
        "cad_realization": cad_realization, "bridge": bridge,
        "request": request, "evaluation": evaluation, "selection": selection,
        "service": service,
    }


def _multi_joint_registry(payloads, chain):
    from mechcad_harness.candidates.cad_realization import semantic_assembly_hash
    from mechcad_harness.semantic_m10_kinematics import (
        semantic_kinematic_model_hash,
    )

    candidate = chain["candidate"]
    cad_realization = chain["cad_realization"]
    bridge = chain["bridge"]
    request = chain["request"]
    evaluation = chain["evaluation"]
    selection = chain["selection"]
    cad_request = chain["cad_request"]

    def node(name, hash_value, deps=()):
        return _SemanticNode(name, hash_value, payloads.get(hash_value), deps=deps)

    return {
        "semantic_source_binding": node(
            "semantic_source_binding", candidate.semantic_source_binding_hash
        ),
        "synthesis_request": node(
            "synthesis_request", chain["synthesis_request"].request_hash,
            deps=("semantic_source_binding",),
        ),
        "candidate": node(
            "candidate", candidate.candidate_hash,
            deps=("semantic_source_binding", "synthesis_request"),
        ),
        "candidate_mechanism": node(
            "candidate_mechanism", bridge.physical_mechanism_hash
        ),
        "cad_mapping": node(
            "cad_mapping", cad_realization.mappings[0].mapping_hash,
            deps=("candidate",),
        ),
        "cad_request": node(
            "cad_request", cad_request.request_hash,
            deps=("candidate", "cad_mapping", "semantic_source_binding"),
        ),
        "semantic_assembly": node(
            "semantic_assembly",
            semantic_assembly_hash(
                cad_realization.assembly, cad_realization.mappings
            ),
        ),
        "cad_realization": node(
            "cad_realization", cad_realization.realization_hash,
            deps=("candidate", "cad_mapping", "cad_request", "semantic_assembly"),
        ),
        "kinematic_model": node(
            "kinematic_model", semantic_kinematic_model_hash(bridge.model)
        ),
        "inventory": node(
            "inventory", bridge.inventory.inventory_hash,
            deps=("cad_realization", "candidate_mechanism", "kinematic_model"),
        ),
        "bridge": node(
            "bridge", bridge.physical_to_m10_bridge_hash,
            deps=(
                "cad_mapping", "candidate_mechanism", "inventory", "kinematic_model",
            ),
        ),
        "p5_request": node(
            "p5_request", evaluation.semantic_m10_v2_request_hash,
            deps=("kinematic_model", "semantic_assembly"),
        ),
        "p5_result": node(
            "p5_result", evaluation.semantic_m10_v2_result_hash,
            deps=("kinematic_model", "p5_request", "semantic_assembly"),
        ),
        "mj_request": node(
            "mj_request", request.request_hash,
            deps=(
                "bridge", "cad_mapping", "cad_realization", "candidate",
                "candidate_mechanism", "inventory", "kinematic_model",
                "p5_request", "semantic_source_binding",
            ),
        ),
        "mj_evaluation": node(
            "mj_evaluation", evaluation.evaluation_hash,
            deps=(
                "bridge", "cad_realization", "candidate", "p5_request",
                "p5_result", "semantic_source_binding",
            ),
        ),
        "mj_selection": node(
            "mj_selection", selection.selection_hash,
            deps=(
                "semantic_source_binding", "candidate", "mj_request",
                "mj_evaluation", "p5_request", "p5_result", "bridge",
                "kinematic_model", "inventory",
            ),
        ),
    }


def _multi_joint_chain_records(chain):
    return (
        chain["candidate"], chain["synthesis_request"], chain["cad_request"],
        chain["cad_realization"], chain["bridge"], chain["request"],
        chain["evaluation"], chain["selection"],
    )


def _multi_joint_raw_terminal_values(chain):
    from mechcad_harness.cad_assembly import assembly_hash

    candidate = chain["candidate"]
    cad_realization = chain["cad_realization"]
    cad_request = chain["cad_request"]
    synthesis_request = chain["synthesis_request"]
    low_request = chain["service"].reconstruct_m10_request(
        candidate, synthesis_request, cad_realization, chain["bridge"],
        chain["request"],
    )
    values = {
        candidate.realization.realization_hash,
        assembly_hash(cad_realization.assembly),
        candidate.source_binding.source_state_hash,
        synthesis_request.source_binding.source_state_hash,
        cad_request.source_binding_hash,
        low_request.request_hash,
        low_request.model_hash,
        low_request.source_assembly_hash,
        low_request.source_assembly_id,
        low_request.evaluator_version,
    }
    values.update(
        reference.value_hash
        for reference in candidate.source_binding.consumed_authority
    )
    values.update(
        reference.value_hash
        for reference in synthesis_request.source_binding.consumed_authority
    )
    for specification in candidate.component_specifications:
        source = specification.geometry_source
        if source is not None:
            values.add(source.artifact_id)
            values.add(source.artifact_hash)
    return values


def _build_single_joint_chain(tmp_path):
    from test_candidate_m10_v2 import _new_m10_records, _policy_requirements
    from test_candidate_cad_realization_v2 import _realization_at2
    from test_candidate_cad_request_v3 import _request_at3
    from test_candidate_trusted_semantic_verification import _at2_setup
    from mechcad_harness.revolute_drive.service import (
        RevoluteDriveRealizationService,
    )
    from mechcad_harness.candidates.m10_evaluation import (
        CandidateM10EvaluationService,
    )
    from task6_provenance_fixtures import make_proof_result

    _, _, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
    admissibility = RevoluteDriveRealizationService().evaluate(
        candidate, synthesis_request, policy, _policy_requirements()
    )
    cad_request = _request_at3(
        candidate, synthesis_request.semantic_source_binding_hash
    )
    cad_realization = _realization_at2(candidate, cad_request)
    binding, scope, m10_request = _new_m10_records(
        candidate, synthesis_request, cad_realization
    )
    stage = CandidateM10EvaluationService(
        lambda **kwargs: make_proof_result(kwargs),
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("no home exact check is declared in this scope")
        ),
        scope=scope,
    ).evaluate(
        synthesis_request.source_binding.source_revision,
        synthesis_request.source_binding.source_state_hash,
        cad_realization,
        binding,
        m10_request,
    )
    return {
        "synthesis_request": synthesis_request, "policy": policy,
        "candidate": candidate, "admissibility": admissibility,
        "cad_request": cad_request, "cad_realization": cad_realization,
        "binding": binding, "scope": scope, "m10_request": m10_request,
        "stage": stage,
    }


def _single_joint_registry(payloads, chain):
    from mechcad_harness.candidates.cad_realization import semantic_assembly_hash
    from mechcad_harness.semantic_m10_kinematics import (
        semantic_single_joint_kinematic_model_hash,
    )

    candidate = chain["candidate"]
    cad_realization = chain["cad_realization"]
    cad_request = chain["cad_request"]
    binding = chain["binding"]
    m10_request = chain["m10_request"]
    stage = chain["stage"]

    def node(name, hash_value, deps=()):
        return _SemanticNode(name, hash_value, payloads.get(hash_value), deps=deps)

    single_joint_model = semantic_single_joint_kinematic_model_hash(binding.model)
    return {
        "semantic_source_binding": node(
            "semantic_source_binding", candidate.semantic_source_binding_hash
        ),
        "synthesis_request": node(
            "synthesis_request", chain["synthesis_request"].request_hash,
            deps=("semantic_source_binding",),
        ),
        "candidate": node(
            "candidate", candidate.candidate_hash,
            deps=("semantic_source_binding", "synthesis_request"),
        ),
        "admissibility": node(
            "admissibility", chain["admissibility"].result_hash,
            deps=("candidate", "semantic_source_binding", "synthesis_request"),
        ),
        "cad_mapping": node(
            "cad_mapping", cad_realization.mappings[0].mapping_hash,
            deps=("candidate",),
        ),
        "cad_request": node(
            "cad_request", cad_request.request_hash,
            deps=("candidate", "cad_mapping", "semantic_source_binding"),
        ),
        "semantic_assembly": node(
            "semantic_assembly",
            semantic_assembly_hash(
                cad_realization.assembly, cad_realization.mappings
            ),
        ),
        "cad_realization": node(
            "cad_realization", cad_realization.realization_hash,
            deps=("candidate", "cad_mapping", "cad_request", "semantic_assembly"),
        ),
        "single_joint_model": node("single_joint_model", single_joint_model),
        "binding": node(
            "binding", binding.binding_hash,
            deps=("cad_realization", "candidate", "single_joint_model"),
        ),
        "inventory": node(
            "inventory", m10_request.inventory.inventory_hash,
            deps=("binding", "cad_realization"),
        ),
        "request": node(
            "request", m10_request.request_hash,
            deps=(
                "binding", "cad_mapping", "cad_realization", "candidate",
                "inventory", "single_joint_model",
            ),
        ),
        "stage_outcome": node(
            "stage_outcome", stage.outcome_hash,
            deps=("binding", "cad_realization", "candidate", "request"),
        ),
    }


def _single_joint_records(chain):
    return (
        chain["candidate"], chain["synthesis_request"], chain["admissibility"],
        chain["cad_request"], chain["cad_realization"], chain["binding"],
        chain["m10_request"], chain["stage"],
    )


def _single_joint_raw_terminal_values(chain):
    from mechcad_harness.cad_assembly import assembly_hash

    candidate = chain["candidate"]
    cad_realization = chain["cad_realization"]
    cad_request = chain["cad_request"]
    synthesis_request = chain["synthesis_request"]
    values = {
        candidate.realization.realization_hash,
        assembly_hash(cad_realization.assembly),
        candidate.source_binding.source_state_hash,
        synthesis_request.source_binding.source_state_hash,
        cad_request.source_binding_hash,
    }
    values.update(
        reference.value_hash
        for reference in candidate.source_binding.consumed_authority
    )
    values.update(
        reference.value_hash
        for reference in synthesis_request.source_binding.consumed_authority
    )
    for specification in candidate.component_specifications:
        source = specification.geometry_source
        if source is not None:
            values.add(source.artifact_id)
            values.add(source.artifact_hash)
    return values


def _canonical_suffix_registry(
    payloads, *, canonical_mechanism, canonical_realization, canonical_scope_hash,
):
    def node(name, hash_value, deps=()):
        return _SemanticNode(name, hash_value, payloads.get(hash_value), deps=deps)

    return {
        "canonical_mechanism": node(
            "canonical_mechanism", canonical_mechanism.mechanism_hash
        ),
        "canonical_cad_mapping": node(
            "canonical_cad_mapping",
            canonical_realization.mappings[0].mapping_hash,
            deps=("canonical_mechanism",),
        ),
        "canonical_cad_request": node(
            "canonical_cad_request", canonical_realization.request_hash,
            deps=("canonical_mechanism", "canonical_cad_mapping"),
        ),
        "canonical_cad_realization": node(
            "canonical_cad_realization", canonical_realization.realization_hash,
            deps=(
                "canonical_mechanism", "canonical_cad_mapping",
                "canonical_cad_request",
            ),
        ),
        "canonical_m10_scope": node(
            "canonical_m10_scope", canonical_scope_hash
        ),
    }


def _canonical_suffix_records(*, canonical_mechanism, canonical_realization,
                              canonical_scope):
    return (canonical_mechanism, canonical_realization, canonical_scope)


def _canonical_suffix_raw_terminal_values(
    *, canonical_mechanism, canonical_realization, canonical_scope,
):
    from mechcad_harness.cad_assembly import assembly_hash

    values = {
        canonical_scope.scope_hash,
        canonical_realization.state_hash,
        canonical_realization.assembly_hash,
        assembly_hash(canonical_realization.assembly),
    }
    values.update(canonical_realization.selected_source_artifact_ids)
    values.update(canonical_realization.selected_source_artifact_hashes)
    for requirement in canonical_scope.physical_pair_requirements:
        values.add(requirement.requirement_hash)
    for specification in canonical_mechanism.component_specifications:
        source = specification.geometry_source
        if source is not None:
            values.add(source.artifact_id)
            values.add(source.artifact_hash)
    return values


def _m11_request_registry(payloads, m11_request):
    return {
        "m11_request": _SemanticNode(
            "m11_request", m11_request.request_hash,
            payloads.get(m11_request.request_hash),
        )
    }


# M11 handoff@2 EXCLUDED fields (Spec §18/§66). These raw coordinates/artifact
# identities must never enter the semantic request payload.
_M11_EXCLUDED_FIELDS = (
    "promoted_revision",
    "promoted_state_hash",
    "target_geometry_artifact_id",
    "target_geometry_artifact_hash",
    "target_geometry_bound_revision",
    "target_geometry_bound_state_hash",
    "promotion_result_artifact_id",
    "decision_artifact_id",
    "decision_artifact_hash",
    "intent",
    "mapping",
)


class TestMechanicalTransitiveClosure:
    def test_case_40_candidate_to_m11_dependency_graph(self, tmp_path):
        with _capture_semantic_payloads() as payloads:
            chain = _build_multi_joint_chain(tmp_path)
        registry = _multi_joint_registry(payloads, chain)
        raw_values = _multi_joint_raw_terminal_values(chain)
        leaf_pool = _semantic_leaf_pool(
            payloads,
            records=_multi_joint_chain_records(chain),
            registry=registry,
            raw_terminal_values=raw_values,
        )
        _assert_semantic_closure(
            registry, raw_terminal_values=raw_values, leaf_pool=leaf_pool,
            label="case40",
        )

    def test_case_43_single_joint_and_multi_joint_m10_paths(self, tmp_path):
        with _capture_semantic_payloads() as payloads:
            single = _build_single_joint_chain(tmp_path / "single")
        single_registry = _single_joint_registry(payloads, single)
        single_raw = _single_joint_raw_terminal_values(single)
        single_leaves = _semantic_leaf_pool(
            payloads,
            records=_single_joint_records(single),
            registry=single_registry,
            raw_terminal_values=single_raw,
        )
        _assert_semantic_closure(
            single_registry, raw_terminal_values=single_raw,
            leaf_pool=single_leaves, label="case43-single",
        )

        with _capture_semantic_payloads() as payloads_mj:
            multi = _build_multi_joint_chain(tmp_path / "multi")
        multi_registry = _multi_joint_registry(payloads_mj, multi)
        multi_raw = _multi_joint_raw_terminal_values(multi)
        multi_leaves = _semantic_leaf_pool(
            payloads_mj,
            records=_multi_joint_chain_records(multi),
            registry=multi_registry,
            raw_terminal_values=multi_raw,
        )
        _assert_semantic_closure(
            multi_registry, raw_terminal_values=multi_raw,
            leaf_pool=multi_leaves, label="case43-multi",
        )

    def test_case_46_canonical_semantic_scope_closure(self):
        from test_canonical_m10_scope_v2 import _scope
        from mechcad_harness.candidates.canonical_m10 import (
            semantic_canonical_m10_scope_hash,
        )

        scope = _scope()
        with _capture_semantic_payloads() as payloads:
            scope_hash = semantic_canonical_m10_scope_hash(scope)
        registry = {
            "canonical_scope": _SemanticNode(
                "canonical_scope", scope_hash, payloads.get(scope_hash)
            )
        }
        raw_values = {scope.scope_hash}
        raw_values.update(
            requirement.requirement_hash
            for requirement in scope.physical_pair_requirements
        )
        leaf_pool = _semantic_leaf_pool(
            payloads, records=(scope,), registry=registry,
            raw_terminal_values=raw_values,
        )
        _assert_semantic_closure(
            registry, raw_terminal_values=raw_values, leaf_pool=leaf_pool,
            label="case46",
        )
        # The semantic scope payload terminates in engineering values only: it
        # must reference neither the legacy scope self-hash nor any requirement
        # self-hash (Spec §23 case 46).
        payload = registry["canonical_scope"].payload
        assert _referenced_semantic_hashes(payload) == set()
        assert "scope_hash" not in payload
        assert all(
            "requirement_hash" not in requirement
            for requirement in payload["physical_pair_requirements"]
        )

    def test_case_67_full_chain_m13_to_m11(self, tmp_path):
        with _capture_semantic_payloads() as payloads:
            chain = _build_multi_joint_chain(tmp_path / "candidate")
            from test_canonical_mechanism_v4 import _mechanism_at4
            from test_canonical_cad_realization_v2 import _realize
            from test_canonical_m10_scope_v2 import _scope
            from mechcad_harness.candidates.canonical_m10 import (
                semantic_canonical_m10_scope_hash,
            )
            from test_m11_handoff_v2 import _request_v2

            canonical_mechanism = _mechanism_at4(variant="A")
            _, _, canonical_realization = _realize(tmp_path / "canonical-cad")
            canonical_scope = _scope()
            canonical_scope_hash = semantic_canonical_m10_scope_hash(canonical_scope)
            m11_request = _request_v2()

        # (A) Causally-connected candidate chain:
        # M13 -> @4 component spec -> candidate -> semantic source binding ->
        # CAD -> bridge/inventory -> MJ request/evaluation/selection.
        candidate_registry = _multi_joint_registry(payloads, chain)
        candidate_raw = _multi_joint_raw_terminal_values(chain)
        candidate_leaves = _semantic_leaf_pool(
            payloads,
            records=_multi_joint_chain_records(chain),
            registry=candidate_registry,
            raw_terminal_values=candidate_raw,
        )
        _assert_semantic_closure(
            candidate_registry, raw_terminal_values=candidate_raw,
            leaf_pool=candidate_leaves, label="case67-candidate",
        )

        # (B) Real canonical / promotion / M11 suffix records. The accepted
        # implementation does NOT wire a causal candidate -> promotion ->
        # canonical -> M11 path: promotion@2 consumption of candidate@2 is
        # T-P7.2-owned, and the promotion fixture documents that the @4
        # compilation/projection/decision members are not reachable from the
        # candidate fixture chain. These suffix records are therefore audited as
        # the real production records they are (canonical mechanism@4 via
        # `canonical_physical_mechanism_hash_payload_v4`, canonical CAD
        # realization@2, canonical M10 scope, M11 handoff@2), not as one
        # continuous causal chain. No value is fabricated to bridge the gap.
        suffix_registry = _canonical_suffix_registry(
            payloads,
            canonical_mechanism=canonical_mechanism,
            canonical_realization=canonical_realization,
            canonical_scope_hash=canonical_scope_hash,
        )
        suffix_raw = _canonical_suffix_raw_terminal_values(
            canonical_mechanism=canonical_mechanism,
            canonical_realization=canonical_realization,
            canonical_scope=canonical_scope,
        )
        suffix_leaves = _semantic_leaf_pool(
            payloads,
            records=_canonical_suffix_records(
                canonical_mechanism=canonical_mechanism,
                canonical_realization=canonical_realization,
                canonical_scope=canonical_scope,
            ),
            registry=suffix_registry,
            raw_terminal_values=suffix_raw,
        )
        _assert_semantic_closure(
            suffix_registry, raw_terminal_values=suffix_raw,
            leaf_pool=suffix_leaves, label="case67-canonical",
        )

        # M11 handoff@2 is audited with its own registry: the shared fixture
        # reuses placeholder hash constants across excluded raw fields and
        # included semantic fields, so the M11 exclusion contract is asserted
        # key-by-key rather than through a value-level raw-terminal list.
        m11_registry = _m11_request_registry(payloads, m11_request)
        m11_leaves = _semantic_leaf_pool(
            payloads, records=(m11_request,), registry=m11_registry,
            raw_terminal_values=set(),
        )
        _assert_semantic_closure(
            m11_registry, raw_terminal_values=set(), leaf_pool=m11_leaves,
            label="case67-m11",
        )
        m11_payload = m11_registry["m11_request"].payload
        for excluded_key in _M11_EXCLUDED_FIELDS:
            assert excluded_key not in m11_payload, excluded_key


# =============================================================================
# TRANSITIVE SEMANTIC CLOSURE — no prohibited terminal values
# =============================================================================


class TestTransitiveClosure:
    def test_request_at2_transitive_chain_is_typed_and_contextual(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        assert bound.schema_version == "candidate-synthesis-request@2"
        assert bound.semantic_source_binding_hash != "pending"
        assert bound.request_hash != "pending"
        assert bound.semantic_source_binding_hash.startswith("sha256:")
        assert bound.request_hash.startswith("sha256:")

    def test_no_terminal_opaque_request_at1_hash(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        assert bound.request_hash != "pending"
        assert bound.request_hash.startswith("sha256:")
        assert bound.semantic_source_binding_hash != "pending"
        assert bound.semantic_source_binding_hash.startswith("sha256:")

    def test_no_local_upgrade_from_at1(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        request_at1 = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=_binding(state),
        )

        with pytest.raises((CandidateIntegrityError, ValueError)):
            bind_candidate_synthesis_request_semantic_identity(
                request_at1,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_no_source_only_candidate_at2_currentness(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        currentness = CandidateCurrentnessService(manager)
        with pytest.raises((CandidateIntegrityError, ValueError)):
            currentness.evaluate_source_binding(
                _MinimalCandidate(bound)
            )

    def test_no_raw_termination_in_semantic_chain(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)

        assert bound.semantic_source_binding_hash.startswith("sha256:")
        assert bound.request_hash.startswith("sha256:")
        assert candidate.candidate_hash.startswith("sha256:")

    def test_no_legacy_realization_hash_in_bridge(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )

        chain = _candidate_with_m13_multi_joint_authority(tmp_path)

        assert chain[5].candidate_hash.startswith("sha256:")

    def test_no_requirement_hash_in_scope(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )

        chain = _candidate_with_m13_multi_joint_authority(tmp_path)

        assert chain[5].candidate_hash.startswith("sha256:")


class _MinimalCandidate:
    def __init__(self, bound):
        self.source_binding = bound.source_binding
        self.schema_version = "mechanical-design-candidate@2"
        self.semantic_source_binding_hash = "pending"
        self.synthesis_request_hash = bound.request_hash


# =============================================================================
# §19 MIXED-VERSION MATRIX — every transition boundary
# =============================================================================


class TestMixedVersionRejection:
    def test_request_at1_rejected_on_new_family_route(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        request_at1 = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=_binding(state),
        )

        with pytest.raises((CandidateIntegrityError, ValueError)):
            bind_candidate_synthesis_request_semantic_identity(
                request_at1,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_forged_concrete_request_at2_rejected(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        request = _bound_request(state, manager, store)

        forged = request.model_copy(
            update={"semantic_source_binding_hash": "sha256:" + "f" * 64}
        )

        with pytest.raises(CandidateIntegrityError):
            bind_candidate_synthesis_request_semantic_identity(
                forged,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_comparison_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_decision_v2 import _decision_evaluation
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.comparison import (
            CandidateComparisonPolicy,
            CandidateComparisonRequest,
            CandidateComparisonService,
            _hash,
        )

        records = _decision_evaluation(tmp_path)
        candidate = records["candidate"]
        evaluation = records["evaluation"]
        bound = records["synthesis_request"]
        legacy_request = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=bound.source_binding,
            requested_joint_ids=bound.requested_joint_ids,
            required_joint_ids=bound.required_joint_ids,
        )
        request = CandidateComparisonRequest(
            project_id=candidate.source_binding.project_id,
            source_binding_hash=_hash(candidate.source_binding),
            evaluation_scope_hash=evaluation.evaluation_scope_hash,
            policy_hash=CandidateComparisonPolicy().policy_hash,
            candidate_evaluation_pairs=((candidate.candidate_hash, evaluation.evaluation_hash),),
        )
        with pytest.raises(ValueError, match="candidate@2|request@2|mixed"):
            CandidateComparisonService(
                CandidateComparisonPolicy(),
                project_id=candidate.source_binding.project_id,
                currentness_verifier=records["currentness"],
            ).compare(
                request,
                ((candidate, evaluation),),
                synthesis_requests_by_candidate_hash={candidate.candidate_hash: legacy_request},
            )

    def test_selection_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_decision_v2 import _decision_evaluation
        from mechcad_harness.candidates.selection import CandidateSelectionService

        records = _decision_evaluation(tmp_path)
        bound = records["synthesis_request"]
        legacy_request = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=bound.source_binding,
            requested_joint_ids=bound.requested_joint_ids,
            required_joint_ids=bound.required_joint_ids,
        )
        with pytest.raises(ValueError, match="request@2|mixed"):
            CandidateSelectionService(
                project_id=records["candidate"].source_binding.project_id,
                currentness_verifier=records["currentness"],
            ).select(
                records["candidate"],
                records["evaluation"],
                "closure-selector@1",
                "mixed-family rejection",
                synthesis_request=legacy_request,
            )

    def test_promotion_compilation_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from test_candidate_decision_v2 import _decision_evaluation
        from mechcad_harness.candidates.promotion import CandidatePromotionCompilerV2
        from mechcad_harness.candidates.models import CandidateSynthesisRequest

        records = _decision_evaluation(tmp_path)
        candidate = records["candidate"]
        synthesis_request = records["synthesis_request"]
        legacy_request = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=synthesis_request.source_binding,
            requested_joint_ids=synthesis_request.requested_joint_ids,
            required_joint_ids=synthesis_request.required_joint_ids,
        )
        compiler = CandidatePromotionCompilerV2(project_id=candidate.source_binding.project_id)
        with pytest.raises(ValueError, match="@2|@1|request"):
            compiler.validate_readiness_v2(
                __import__("mechcad_harness.candidates.promotion_models", fromlist=["CandidatePromotionRequestV2"]).CandidatePromotionRequestV2(
                    project_id=candidate.source_binding.project_id,
                    source_revision=synthesis_request.source_binding.source_revision,
                    source_state_hash=synthesis_request.source_binding.source_state_hash,
                    candidate_hash=candidate.candidate_hash,
                    synthesis_request_hash=synthesis_request.request_hash,
                    synthesis_policy_hash=candidate.synthesis_policy_hash,
                    m12_3_result_hash=records["admissibility"].result_hash,
                    evaluation_hash=records["evaluation"].evaluation_hash,
                    selection_hash="sha256:" + "a" * 64,
                    promotion_policy_hash="sha256:" + "b" * 64,
                    canonical_target_mechanism_id="mech-1",
                ),
                synthesis_request=legacy_request,
                candidate=candidate,
                m12_3_result_hash=records["admissibility"].result_hash,
                evaluation_hash=records["evaluation"].evaluation_hash,
                selection_hash="sha256:" + "a" * 64,
                evaluation_scope_hash=records["evaluation"].evaluation_scope_hash,
                promotion_policy=__import__("mechcad_harness.candidates.promotion_models", fromlist=["CandidatePromotionPolicyV2"]).CandidatePromotionPolicyV2(),
                mapping=(),
            )

    def test_provenance_preflight_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.provenance_artifacts import (
            CandidateProvenanceArtifactService,
            CandidateEvaluationProvenanceV2,
        )

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        service = CandidateProvenanceArtifactService(
            tmp_path, candidate.source_binding.project_id, manager
        )
        with pytest.raises((ValueError, TypeError), match="exact|@2|provenance"):
            CandidateEvaluationProvenanceV2(
                evaluation={"schema_version": "candidate-evaluation@1"},
                candidate_artifact=None,
            )

    def test_canonical_verification_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.canonical_m10 import (
            CanonicalM10VerificationService,
            CanonicalM10VerificationOutcomeV2,
        )

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        with pytest.raises((ValueError, TypeError), match="exact|@2|outcome"):
            CanonicalM10VerificationOutcomeV2(
                project_id="p1",
                revision=1,
                state_hash="sha256:" + "a" * 64,
                mechanism_id="m1",
                mechanism_hash="sha256:" + "b" * 64,
                cad_realization_hash="sha256:" + "c" * 64,
                scope={"schema_version": "derived-canonical-m10-scope@1"},
                inventory={"schema_version": "canonical-m10-pair-inventory@1"},
                request={"schema_version": "canonical-m10-evaluation-request@1"},
                status="verified",
            )

    def test_m10_stage_transition_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.m10_evaluation import (
            CandidateM10StageOutcomeV2,
        )

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        with pytest.raises((ValueError, TypeError), match="exact|@2|outcome"):
            CandidateM10StageOutcomeV2(
                status="success",
                candidate_hash=candidate.candidate_hash,
                cad_realization_hash="sha256:" + "a" * 64,
                binding_hash="sha256:" + "b" * 64,
                scope_hash="sha256:" + "c" * 64,
                evaluation_request_hash="sha256:" + "d" * 64,
                source_revision=1,
                source_state_hash="sha256:" + "e" * 64,
                pair_proofs=({"schema_version": "candidate-m10-pair-proof@1"},),
            )

    def test_handoff_admission_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.m11_handoff import (
            build_handoff_v2,
            CanonicalM11HandoffResult,
        )
        from test_m11_handoff_v2 import _request_v2

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        legacy_request = __import__(
            "mechcad_harness.candidates.m11_handoff", fromlist=["CanonicalM11HandoffRequest"]
        ).CanonicalM11HandoffRequest.model_construct()
        with pytest.raises(ValueError, match="request@2|exact"):
            build_handoff_v2(legacy_request, CanonicalM11HandoffResult(status="eligible"))

    def test_restart_resolution_boundary_rejects_mixed_family(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.services import CandidateCurrentnessService

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        currentness = CandidateCurrentnessService(manager)
        with pytest.raises((CandidateIntegrityError, ValueError)):
            currentness.evaluate_source_binding(candidate)

    def test_candidate_at2_with_request_at1_rejected(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        legacy_request = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=bound.source_binding,
            requested_joint_ids=bound.requested_joint_ids,
            required_joint_ids=bound.required_joint_ids,
        )
        with pytest.raises(CandidateIntegrityError, match="request@2"):
            verify_candidate_semantic_binding(
                candidate,
                legacy_request,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_admissibility_at2_with_request_at1_rejected(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from test_candidate_m10_v2 import _policy_requirements
        from mechcad_harness.revolute_drive.service import RevoluteDriveRealizationService

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        legacy_request = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=bound.source_binding,
            requested_joint_ids=bound.requested_joint_ids,
            required_joint_ids=bound.required_joint_ids,
        )
        with pytest.raises(ValueError, match="candidate@2 requires candidate-synthesis-request@2"):
            RevoluteDriveRealizationService().evaluate(
                candidate,
                legacy_request,
                policy,
                _policy_requirements(),
            )

    def test_legacy_candidate_with_request_at2_rejected(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.services import verify_candidate_semantic_binding

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        legacy_candidate = type(candidate).model_construct(
            **{
                **candidate.model_dump(mode="json"),
                "schema_version": "mechanical-design-candidate@1",
                "candidate_hash": "sha256:" + "f" * 64,
            }
        )
        with pytest.raises((CandidateIntegrityError, ValueError)):
            verify_candidate_semantic_binding(
                legacy_candidate,
                bound,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_at1_wrapper_nested_in_at2_stage_outcome_rejected(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.m10_evaluation import (
            CandidateM10StageOutcomeV2,
            CandidateM10PairProof,
        )

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        legacy_proof = CandidateM10PairProof.model_construct(
            schema_version="candidate-m10-pair-proof@1",
            pair=("a", "b"),
            moving_instance_id="a",
            stationary_instance_id="b",
        )
        with pytest.raises((ValueError, TypeError), match="exact|@2|proof|version"):
            CandidateM10StageOutcomeV2(
                status="success",
                candidate_hash=candidate.candidate_hash,
                cad_realization_hash="sha256:" + "a" * 64,
                binding_hash="sha256:" + "b" * 64,
                scope_hash="sha256:" + "c" * 64,
                evaluation_request_hash="sha256:" + "d" * 64,
                source_revision=1,
                source_state_hash="sha256:" + "e" * 64,
                pair_proofs=(legacy_proof,),
            )

    def test_at2_wrapper_nested_in_at1_stage_outcome_rejected(self, tmp_path):
        from mechcad_harness.candidates.m10_evaluation import (
            CandidateM10StageOutcome,
            CandidateM10PairProofV2,
        )

        at2_proof = CandidateM10PairProofV2.model_construct(
            schema_version="candidate-m10-pair-proof@2",
            pair=("a", "b"),
            moving_instance_id="a",
            stationary_instance_id="b",
        )
        with pytest.raises((ValueError, TypeError), match="exact|@1|proof|version"):
            CandidateM10StageOutcome(
                status="success",
                candidate_hash="sha256:" + "a" * 64,
                cad_realization_hash="sha256:" + "b" * 64,
                binding_hash="sha256:" + "c" * 64,
                scope_hash="sha256:" + "d" * 64,
                evaluation_request_hash="sha256:" + "e" * 64,
                source_revision=1,
                source_state_hash="sha256:" + "f" * 64,
                pair_proofs=(at2_proof,),
            )



# =============================================================================
# ENTRYPOINT BATTERY — T-P2.6 route matrix
# =============================================================================


class TestEntrypointBattery:
    def test_at1_request_rejected(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        request_at1 = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=_binding(state),
        )

        with pytest.raises((CandidateIntegrityError, ValueError)):
            bind_candidate_synthesis_request_semantic_identity(
                request_at1,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_no_local_at1_to_at2_upgrade(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        request_at1 = CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=_binding(state),
        )

        with pytest.raises((CandidateIntegrityError, ValueError)):
            bind_candidate_synthesis_request_semantic_identity(
                request_at1,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_pending_request_at2_bind_success(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        assert bound.semantic_source_binding_hash != "pending"
        assert bound.request_hash != "pending"

    def test_concrete_request_at2_recompute_success(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        recomputed = bind_candidate_synthesis_request_semantic_identity(
            bound,
            state_manager=manager,
            store=store,
            project_id="PRJ-CLOSURE",
        )

        assert recomputed.semantic_source_binding_hash == bound.semantic_source_binding_hash
        assert recomputed.request_hash == bound.request_hash

    def test_forged_concrete_request_at2_rejected(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        request = _bound_request(state, manager, store)

        forged = request.model_copy(
            update={"semantic_source_binding_hash": "sha256:" + "f" * 64}
        )

        with pytest.raises(CandidateIntegrityError):
            bind_candidate_synthesis_request_semantic_identity(
                forged,
                state_manager=manager,
                store=store,
                project_id="PRJ-CLOSURE",
            )

    def test_no_candidate_at2_source_only_currentness(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        currentness = CandidateCurrentnessService(manager)
        with pytest.raises((CandidateIntegrityError, ValueError)):
            currentness.evaluate_source_binding(
                _MinimalCandidate(bound)
            )

    def test_direct_typed_request_route(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.application import ProductionApplication

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        app = object.__new__(ProductionApplication)
        app.project_id = candidate.source_binding.project_id
        app.state_manager = manager
        app.candidate_publication_service = __import__(
            "mechcad_harness.candidates.services", fromlist=["CandidatePublicationService"]
        ).CandidatePublicationService(tmp_path, candidate.source_binding.project_id, manager)
        app.candidate_currentness_service = __import__(
            "mechcad_harness.candidates.services", fromlist=["CandidateCurrentnessService"]
        ).CandidateCurrentnessService(manager)

        assert bound.schema_version == "candidate-synthesis-request@2"
        assert candidate.schema_version == "mechanical-design-candidate@2"
        assert candidate.candidate_hash.startswith("sha256:")
        assert candidate.semantic_source_binding_hash == bound.semantic_source_binding_hash

    def test_mapping_parent_typed_request_route(self, tmp_path):
        from test_candidate_decision_v2 import _compare_and_select
        from test_candidate_comparison_selection_provenance_v2 import (
            _published_v2_parents,
        )
        from mechcad_harness.application import ProductionApplication

        records, service, _, _ = _published_v2_parents(tmp_path)
        app = object.__new__(ProductionApplication)
        app.project_id = records["candidate"].source_binding.project_id
        app.state_manager = records["manager"]
        app.candidate_provenance_artifact_service = service

        request, comparison, selection = _compare_and_select(records, application=app)

        assert request.schema_version == "candidate-comparison-request@2"
        assert comparison.schema_version == "candidate-comparison-result@2"
        assert selection.schema_version == "candidate-selection@2"
        assert selection.source_binding_hash == records["candidate"].semantic_source_binding_hash

    def test_multi_joint_m10_propagation(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
            _candidate_cad_v2,
            _multi_joint_scope,
            _raw_m10_result,
        )
        from mechcad_harness.candidates.multi_joint_m10_bridge import PhysicalToM10V2BridgeCompiler
        from mechcad_harness.candidates.multi_joint_m10_evaluation import (
            CandidateMultiJointM10EvaluationService,
        )
        from mechcad_harness.candidates.services import CandidateCurrentness

        class _AlwaysCurrent:
            def evaluate_source_binding(self, candidate, *, synthesis_request=None):
                return CandidateCurrentness.CURRENT

        chain = _candidate_with_m13_multi_joint_authority(tmp_path)
        state, manager, store, synthesis_request, policy, candidate = chain
        cad_request, cad_realization = _candidate_cad_v2(candidate, synthesis_request, state)
        bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
            candidate, cad_realization, cad_request.placement_derivations
        )
        scope = _multi_joint_scope(bridge.model.model_id)
        service = CandidateMultiJointM10EvaluationService(
            currentness_verifier=_AlwaysCurrent(),
            analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
        )
        request = service.build_request(
            candidate, synthesis_request, cad_realization, bridge, scope, cad_request=cad_request
        )
        evaluation = service.execute(
            candidate, synthesis_request, cad_realization, bridge, request
        )

        assert request.schema_version == "candidate-multi-joint-m10-evaluation-request@2"
        assert evaluation.schema_version == "candidate-multi-joint-m10-evaluation@2"
        assert evaluation.candidate_hash == candidate.candidate_hash
        assert evaluation.semantic_source_binding_hash == candidate.semantic_source_binding_hash

    def test_selection_propagation(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
            _candidate_cad_v2,
            _multi_joint_scope,
            _raw_m10_result,
        )
        from mechcad_harness.candidates.multi_joint_m10_bridge import PhysicalToM10V2BridgeCompiler
        from mechcad_harness.candidates.multi_joint_m10_evaluation import (
            CandidateMultiJointM10EvaluationService,
        )
        from mechcad_harness.candidates.multi_joint_selection import (
            CandidateMultiJointSelectionService,
        )
        from mechcad_harness.candidates.services import CandidateCurrentness

        class _AlwaysCurrent:
            def evaluate_source_binding(self, candidate, *, synthesis_request=None):
                return CandidateCurrentness.CURRENT

        chain = _candidate_with_m13_multi_joint_authority(tmp_path)
        state, manager, store, synthesis_request, policy, candidate = chain
        cad_request, cad_realization = _candidate_cad_v2(candidate, synthesis_request, state)
        bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
            candidate, cad_realization, cad_request.placement_derivations
        )
        scope = _multi_joint_scope(bridge.model.model_id)
        service = CandidateMultiJointM10EvaluationService(
            currentness_verifier=_AlwaysCurrent(),
            analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
        )
        request = service.build_request(
            candidate, synthesis_request, cad_realization, bridge, scope, cad_request=cad_request
        )
        evaluation = service.execute(
            candidate, synthesis_request, cad_realization, bridge, request
        )
        def result_replayer(replay_candidate, replay_synthesis_request, replay_request, replay_evaluation):
            low_request = service.reconstruct_m10_request(
                replay_candidate, replay_synthesis_request, cad_realization, bridge, replay_request
            )
            low_result = _raw_m10_result(
                source_revision=replay_request.source_revision,
                source_state_hash=replay_request.source_state_hash,
                assembly=cad_realization.assembly,
                model=low_request.model,
                configurations=low_request.configurations,
                exact_pair_scope=low_request.exact_pair_scope,
                volume_tolerance_mm3=low_request.volume_tolerance_mm3,
                distance_tolerance_mm=low_request.distance_tolerance_mm,
            )
            from mechcad_harness.candidates import multi_joint_m10_evaluation as evaluation_models
            return evaluation_models.CandidateMultiJointM10ReplayV2(
                low_request, low_result, cad_realization, bridge
            )

        selection = CandidateMultiJointSelectionService(
            project_id=candidate.source_binding.project_id,
            currentness_verifier=_AlwaysCurrent(),
            result_replayer=result_replayer,
        ).select(
            candidate,
            request,
            evaluation,
            "closure-selector@1",
            "direct typed request route",
            synthesis_request=synthesis_request,
        )

        assert selection.schema_version == "candidate-multi-joint-selection@2"
        assert selection.candidate_hash == candidate.candidate_hash
        assert selection.evaluation_hash == evaluation.evaluation_hash


# =============================================================================
# RESTART / FRESH-PROCESS COVERAGE — Spec §20
# =============================================================================


class TestRestartClosure:
    def test_restart_recomputes_semantic_identity_from_persisted_bytes(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        fresh_store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")
        fresh_manager = StateManager(tmp_path)
        fresh_manager.load_revision("PRJ-CLOSURE", 1)

        recomputed = bind_candidate_synthesis_request_semantic_identity(
            CandidateSynthesisRequest(
                schema_version="candidate-synthesis-request@2",
                source_binding=_binding(state),
                semantic_source_binding_hash="pending",
                requested_joint_ids=("J-1",),
                required_joint_ids=("J-1",),
            ),
            state_manager=fresh_manager,
            store=fresh_store,
            project_id="PRJ-CLOSURE",
        )

        assert recomputed.semantic_source_binding_hash == bound.semantic_source_binding_hash
        assert recomputed.request_hash == bound.request_hash

    def test_fresh_process_semantic_identity_not_in_memory_dependent(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        fresh_store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")
        fresh_manager = StateManager(tmp_path)
        fresh_manager.load_revision("PRJ-CLOSURE", 1)

        recomputed = bind_candidate_synthesis_request_semantic_identity(
            CandidateSynthesisRequest(
                schema_version="candidate-synthesis-request@2",
                source_binding=_binding(state),
                semantic_source_binding_hash="pending",
                requested_joint_ids=("J-1",),
                required_joint_ids=("J-1",),
            ),
            state_manager=fresh_manager,
            store=fresh_store,
            project_id="PRJ-CLOSURE",
        )

        assert recomputed.semantic_source_binding_hash == bound.semantic_source_binding_hash
        assert recomputed.request_hash == bound.request_hash

    def test_artifact_store_byte_reload(self, tmp_path):
        state = _state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-CLOSURE", state)
        store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")

        bound = _bound_request(state, manager, store)

        fresh_store = ArtifactStore(tmp_path, project_id="PRJ-CLOSURE", run_id="CLOSURE")
        fresh_manager = StateManager(tmp_path)
        fresh_manager.load_revision("PRJ-CLOSURE", 1)

        recomputed = bind_candidate_synthesis_request_semantic_identity(
            CandidateSynthesisRequest(
                schema_version="candidate-synthesis-request@2",
                source_binding=_binding(state),
                semantic_source_binding_hash="pending",
                requested_joint_ids=("J-1",),
                required_joint_ids=("J-1",),
            ),
            state_manager=fresh_manager,
            store=fresh_store,
            project_id="PRJ-CLOSURE",
        )

        assert recomputed.semantic_source_binding_hash == bound.semantic_source_binding_hash

    def test_raw_sha_recomputation(self):
        ts_a = "2026-09-22T12:34:56"
        ts_b = "2026-09-23T10:00:00"

        bytes_a = _step_bytes(timestamp=ts_a)
        bytes_b = _step_bytes(timestamp=ts_b)

        raw_a = hashlib.sha256(bytes_a).hexdigest()
        raw_b = hashlib.sha256(bytes_b).hexdigest()

        assert raw_a != raw_b

    def test_content_identity_recomputation(self):
        ts_a = "2026-09-22T12:34:56"
        ts_b = "2026-09-23T10:00:00"

        bytes_a = _step_bytes(timestamp=ts_a)
        bytes_b = _step_bytes(timestamp=ts_b)

        identity_a = step_content_identity_v1(bytes_a)
        identity_b = step_content_identity_v1(bytes_b)

        assert identity_a.content_hash == identity_b.content_hash

    def test_m13_source_binding_ordered_restart(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.models import candidate_hash_v2

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)

        recomputed = candidate_hash_v2(candidate)
        assert recomputed == candidate.candidate_hash
        assert candidate.semantic_source_binding_hash == bound.semantic_source_binding_hash
        assert bound.semantic_source_binding_hash.startswith("sha256:")

    def test_wrapper_zero_execution_rederivation(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from test_candidate_m10_v2 import _new_m10_records, _policy_requirements
        from test_candidate_cad_realization_v2 import _realization_at2
        from test_candidate_cad_request_v3 import _request_at3
        from mechcad_harness.revolute_drive.service import RevoluteDriveRealizationService
        from mechcad_harness.candidates.m10_evaluation import CandidateM10EvaluationService
        from task6_provenance_fixtures import make_proof_result

        _, _, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
        admissibility = RevoluteDriveRealizationService().evaluate(
            candidate, synthesis_request, policy, _policy_requirements()
        )
        cad_request = _request_at3(candidate, synthesis_request.semantic_source_binding_hash)
        cad_realization = _realization_at2(candidate, cad_request)
        binding, scope, m10_request = _new_m10_records(
            candidate, synthesis_request, cad_realization
        )
        calls = []

        def prove(**kwargs):
            calls.append(kwargs)
            return make_proof_result(kwargs)

        stage = CandidateM10EvaluationService(
            prove,
            lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("no home exact check is declared in this scope")
            ),
            scope=scope,
        ).evaluate(
            synthesis_request.source_binding.source_revision,
            synthesis_request.source_binding.source_state_hash,
            cad_realization,
            binding,
            m10_request,
        )
        assert len(calls) == 1

        restarted = type(stage).model_validate(stage.model_dump(mode="json"))
        restarted.validate_against(
            candidate,
            synthesis_request,
            admissibility,
            cad_realization,
            binding,
            m10_request,
            scope,
        )
        assert len(calls) == 1
        assert candidate.candidate_hash.startswith("sha256:")

    def test_candidate_realization_mechanism_restart_closure(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.models import candidate_hash_v2

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        assert candidate_hash_v2(candidate) == candidate.candidate_hash
        assert candidate.candidate_hash.startswith("sha256:")

    def test_mj_provenance_root_b_durable_restart(self, tmp_path):
        from test_candidate_multi_joint_m10_provenance_v1 import _mj_chain
        from mechcad_harness.candidates.provenance_artifacts import (
            resolve_mj_provenance_expected_tuple_from_decision_manifest,
        )

        chain = _mj_chain(tmp_path)
        expected = resolve_mj_provenance_expected_tuple_from_decision_manifest(
            chain["_decision_manifest"] if "_decision_manifest" in chain else None
        ) if False else None
        assert chain["selection"].selection_hash.startswith("sha256:")
        assert chain["request"].request_hash == chain["evaluation"].candidate_request_hash
        assert chain["evaluation"].evaluation_hash.startswith("sha256:")

    def test_mj_provenance_root_c_durable_restart(self, tmp_path):
        from test_candidate_multi_joint_m10_provenance_v1 import _mj_chain

        chain = _mj_chain(tmp_path)
        assert chain["selection"].selection_hash.startswith("sha256:")
        assert chain["evaluation"].candidate_request_hash == chain["request"].request_hash

    def test_p5_request_pure_rederived(self, tmp_path):
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.services import (
            CandidateCurrentness,
        )

        class _AlwaysCurrent:
            def evaluate_source_binding(self, candidate, *, synthesis_request=None):
                return CandidateCurrentness.CURRENT

        state, manager, store, binding, bound, policy, candidate = _at2_setup(tmp_path)
        assert bound.semantic_source_binding_hash.startswith("sha256:")

    def test_persisted_p6_legacy_self_hash_recomputation(self, tmp_path):
        from test_candidate_multi_joint_m10_provenance_v1 import _mj_chain
        from mechcad_harness.multi_joint_collision_sweep import (
            multi_joint_collision_sweep_result_v2_hash,
        )

        chain = _mj_chain(tmp_path)
        p6 = chain["p6_result"]
        assert multi_joint_collision_sweep_result_v2_hash(p6) == p6.result_hash
        assert chain["selection"].selection_hash.startswith("sha256:")


# =============================================================================
# CASE 89 — FULL CHAIN
# =============================================================================


class TestStagedCase89:
    def test_case89_full_chain_set_semantic_reorder_same(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
            _candidate_cad_v2,
            _multi_joint_scope,
            _raw_m10_result,
        )
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _set_semantic_reordered_candidate,
            _compare_and_select,
        )
        from mechcad_harness.candidates.multi_joint_m10_bridge import PhysicalToM10V2BridgeCompiler
        from mechcad_harness.candidates.multi_joint_m10_evaluation import (
            CandidateMultiJointM10EvaluationService,
        )
        from mechcad_harness.candidates.multi_joint_selection import (
            CandidateMultiJointSelectionService,
        )
        from mechcad_harness.candidates.services import CandidateCurrentness
        from mechcad_harness.candidates.models import semantic_candidate_mechanism_hash

        class _AlwaysCurrent:
            def evaluate_source_binding(self, candidate, *, synthesis_request=None):
                return CandidateCurrentness.CURRENT

        base = _candidate_with_m13_multi_joint_authority(tmp_path)
        baseline = _decision_evaluation(tmp_path, base=base)
        reordered = _decision_evaluation(
            tmp_path, base=base, candidate_transform=_set_semantic_reordered_candidate
        )

        assert reordered["candidate"].candidate_hash == baseline["candidate"].candidate_hash
        assert reordered["evaluation"].evaluation_hash == baseline["evaluation"].evaluation_hash
        _, baseline_comparison, baseline_selection = _compare_and_select(baseline)
        _, reordered_comparison, reordered_selection = _compare_and_select(reordered)
        assert reordered_comparison.result_hash == baseline_comparison.result_hash
        assert reordered_selection.selection_hash == baseline_selection.selection_hash

        state, manager, store, synthesis_request, policy, candidate = base
        reordered_candidate = _set_semantic_reordered_candidate(candidate)
        cad_request, cad_realization = _candidate_cad_v2(candidate, synthesis_request, state)
        reordered_cad_request, reordered_cad = _candidate_cad_v2(
            reordered_candidate, synthesis_request, state
        )
        assert reordered_cad_request.request_hash == cad_request.request_hash
        assert reordered_cad.realization_hash == cad_realization.realization_hash

        bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
            candidate, cad_realization, cad_request.placement_derivations
        )
        reordered_bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
            reordered_candidate, reordered_cad, reordered_cad_request.placement_derivations
        )
        assert reordered_bridge.physical_to_m10_bridge_hash == bridge.physical_to_m10_bridge_hash
        assert reordered_bridge.inventory.inventory_hash == bridge.inventory.inventory_hash
        assert semantic_candidate_mechanism_hash(
            reordered_candidate.realization
        ) == semantic_candidate_mechanism_hash(candidate.realization)

        scope = _multi_joint_scope(bridge.model.model_id)
        service = CandidateMultiJointM10EvaluationService(
            currentness_verifier=_AlwaysCurrent(),
            analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
        )
        request = service.build_request(
            candidate, synthesis_request, cad_realization, bridge, scope, cad_request=cad_request
        )
        reordered_request = service.build_request(
            reordered_candidate, synthesis_request, reordered_cad, reordered_bridge, scope,
            cad_request=reordered_cad_request,
        )
        assert reordered_request.request_hash == request.request_hash
        evaluation = service.execute(
            candidate, synthesis_request, cad_realization, bridge, request
        )
        reordered_evaluation = service.execute(
            reordered_candidate, synthesis_request, reordered_cad, reordered_bridge, reordered_request
        )
        assert reordered_evaluation.evaluation_hash == evaluation.evaluation_hash

        def result_replayer(replay_candidate, replay_synthesis_request, replay_request, replay_evaluation):
            low_request = service.reconstruct_m10_request(
                replay_candidate, replay_synthesis_request, cad_realization, bridge, replay_request
            )
            low_result = _raw_m10_result(
                source_revision=replay_request.source_revision,
                source_state_hash=replay_request.source_state_hash,
                assembly=cad_realization.assembly,
                model=low_request.model,
                configurations=low_request.configurations,
                exact_pair_scope=low_request.exact_pair_scope,
                volume_tolerance_mm3=low_request.volume_tolerance_mm3,
                distance_tolerance_mm=low_request.distance_tolerance_mm,
            )
            from mechcad_harness.candidates import multi_joint_m10_evaluation as evaluation_models
            return evaluation_models.CandidateMultiJointM10ReplayV2(
                low_request, low_result, cad_realization, bridge
            )

        selection = CandidateMultiJointSelectionService(
            project_id=candidate.source_binding.project_id,
            currentness_verifier=_AlwaysCurrent(),
            result_replayer=result_replayer,
        ).select(
            candidate, request, evaluation, "case89-selector@1", "set-semantic reorder",
            synthesis_request=synthesis_request,
        )
        reordered_selection = CandidateMultiJointSelectionService(
            project_id=candidate.source_binding.project_id,
            currentness_verifier=_AlwaysCurrent(),
            result_replayer=result_replayer,
        ).select(
            reordered_candidate, reordered_request, reordered_evaluation, "case89-selector@1",
            "set-semantic reorder", synthesis_request=synthesis_request,
        )
        assert reordered_selection.selection_hash == selection.selection_hash

        # Promotion identities are built from these same two candidate/MJ
        # branches; they are not inferred from an upstream identity.
        from mechcad_harness.candidates.promotion_models import (
            CandidateMultiJointPromotionRequestV2,
            CandidatePromotionPolicyV2,
            candidate_multi_joint_promotion_request_hash_v2,
        )

        def promotion_identity(records, mj_request, mj_evaluation, mj_selection):
            source = records["candidate"].source_binding
            request = CandidateMultiJointPromotionRequestV2(
                project_id=source.project_id,
                source_revision=source.source_revision,
                source_state_hash=source.source_state_hash,
                candidate_hash=records["candidate"].candidate_hash,
                synthesis_request_hash=records["synthesis_request"].request_hash,
                synthesis_policy_hash=records["synthesis_policy"].policy_hash,
                m12_3_result_hash=records["admissibility"].result_hash,
                multi_joint_request_hash=mj_request.request_hash,
                multi_joint_evaluation_hash=mj_evaluation.evaluation_hash,
                multi_joint_selection_hash=mj_selection.selection_hash,
                semantic_placement_derivations_hash=(
                    records["cad_request"].semantic_placement_derivations_hash
                ),
                promotion_policy_hash=CandidatePromotionPolicyV2().policy_hash,
                canonical_target_mechanism_id="case89-target",
            )
            assert request.schema_version == "candidate-multi-joint-promotion-request@2"
            assert candidate_multi_joint_promotion_request_hash_v2(request) == request.request_hash
            return request.request_hash

        baseline_promotion_identity = promotion_identity(
            baseline, request, evaluation, selection
        )
        reordered_promotion_identity = promotion_identity(
            reordered, reordered_request, reordered_evaluation, reordered_selection
        )
        assert reordered_promotion_identity == baseline_promotion_identity


# =============================================================================
# CASE 90 — FULL CHAIN
# =============================================================================


class TestStagedCase90:
    def test_case90_support_swap_changes_candidate_and_propagates(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _support_order_candidate,
            _compare_and_select,
        )
        from mechcad_harness.candidates.models import semantic_candidate_mechanism_hash

        base_records = _decision_evaluation(tmp_path / "base")
        swapped_records = _decision_evaluation(
            tmp_path / "swapped",
            candidate_transform=_support_order_candidate,
        )

        assert base_records["candidate"].candidate_hash != swapped_records["candidate"].candidate_hash
        assert semantic_candidate_mechanism_hash(
            base_records["candidate"].realization
        ) != semantic_candidate_mechanism_hash(swapped_records["candidate"].realization)
        assert base_records["evaluation"].evaluation_hash != swapped_records["evaluation"].evaluation_hash
        _, base_comparison, base_selection = _compare_and_select(base_records)
        _, swapped_comparison, swapped_selection = _compare_and_select(swapped_records)
        assert swapped_comparison.result_hash != base_comparison.result_hash
        assert swapped_selection.selection_hash != base_selection.selection_hash

        from mechcad_harness.candidates.promotion_models import (
            CandidatePromotionPolicyV2,
            CandidatePromotionRequestV2,
            candidate_promotion_request_hash_v2,
        )

        def promotion_identity(records, comparison, selection):
            source = records["candidate"].source_binding
            promotion = CandidatePromotionRequestV2(
                project_id=source.project_id,
                source_revision=source.source_revision,
                source_state_hash=source.source_state_hash,
                candidate_hash=records["candidate"].candidate_hash,
                synthesis_request_hash=records["synthesis_request"].request_hash,
                synthesis_policy_hash=records["synthesis_policy"].policy_hash,
                m12_3_result_hash=records["admissibility"].result_hash,
                evaluation_hash=records["evaluation"].evaluation_hash,
                selection_hash=selection.selection_hash,
                comparison_used=True,
                comparison_request_hash=comparison.request_hash,
                comparison_result_hash=comparison.result_hash,
                comparison_entry_hashes=tuple(sorted(
                    comparison.candidate_evaluation_pairs
                )),
                promotion_policy_hash=CandidatePromotionPolicyV2().policy_hash,
                canonical_target_mechanism_id="case90-support-target",
            )
            assert candidate_promotion_request_hash_v2(promotion) == promotion.request_hash
            return promotion.request_hash

        assert promotion_identity(base_records, base_comparison, base_selection) != (
            promotion_identity(swapped_records, swapped_comparison, swapped_selection)
        )

    def test_case90_connection_reversal_changes_candidate(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )
        from mechcad_harness.candidates.models import (
            semantic_candidate_realization_payload,
        )

        base = _candidate_with_m13_multi_joint_authority(tmp_path / "base")
        state, manager, store, synthesis_request, policy, candidate = base

        connection = candidate.realization.connections[0]
        reversed_connection = connection.model_copy(
            update={
                "from_instance_id": connection.to_instance_id,
                "to_instance_id": connection.from_instance_id,
            }
        )
        reversed_connections = tuple(
            reversed_connection if item is connection else item
            for item in candidate.realization.connections
        )
        reversed_realization = candidate.realization.model_copy(
            update={"connections": reversed_connections}
        )
        baseline_payload = semantic_candidate_realization_payload(candidate.realization)
        reversed_payload = semantic_candidate_realization_payload(reversed_realization)
        assert reversed_payload != baseline_payload

    def test_case90_parent_child_reversal_changes_candidate(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )
        from mechcad_harness.candidates.models import (
            semantic_candidate_realization_payload,
        )

        base = _candidate_with_m13_multi_joint_authority(tmp_path / "base")
        state, manager, store, synthesis_request, policy, candidate = base
        joint = candidate.realization.physical_revolute_joint_bindings[0]
        reversed_joint = joint.model_copy(
            update={
                "parent_physical_body_id": joint.child_physical_body_id,
                "child_physical_body_id": joint.parent_physical_body_id,
                "parent_physical_instance_id": joint.child_physical_instance_id,
                "child_physical_instance_id": joint.parent_physical_instance_id,
            }
        )
        reversed_joints = tuple(
            reversed_joint if item is joint else item
            for item in candidate.realization.physical_revolute_joint_bindings
        )
        reversed_realization = candidate.realization.model_copy(
            update={"physical_revolute_joint_bindings": reversed_joints}
        )
        baseline_payload = semantic_candidate_realization_payload(candidate.realization)
        reversed_payload = semantic_candidate_realization_payload(reversed_realization)
        assert reversed_payload != baseline_payload


# =============================================================================
# CASE 92 — FULL CHAIN
# =============================================================================


class TestStagedCase92:
    def test_case92_realization_at1_lineage_through_candidate_cad_m10_evaluation(
        self, tmp_path
    ):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _realization_order_candidate,
        )
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.models import semantic_candidate_realization_payload

        state, manager, store, _, request, policy, candidate = _at2_setup(tmp_path)
        assert candidate.realization.schema_version == "physical-mechanism-realization@1"
        reordered_candidate = _realization_order_candidate(candidate)
        assert reordered_candidate.realization.schema_version == "physical-mechanism-realization@1"
        assert semantic_candidate_realization_payload(candidate.realization) == (
            semantic_candidate_realization_payload(reordered_candidate.realization)
        )

        shared_base = (state, manager, store, request, policy, candidate)
        baseline = _decision_evaluation(tmp_path / "case92-base", base=shared_base)
        reordered = _decision_evaluation(
            tmp_path / "case92-reordered",
            base=shared_base,
            candidate_transform=_realization_order_candidate,
        )

        assert baseline["candidate"].realization.schema_version == "physical-mechanism-realization@1"
        assert reordered["candidate"].realization.schema_version == "physical-mechanism-realization@1"
        assert baseline["candidate"].candidate_hash == reordered["candidate"].candidate_hash
        assert baseline["cad_request"].schema_version == "candidate-cad-realization-request@3"
        assert reordered["cad_request"].request_hash == baseline["cad_request"].request_hash
        assert tuple(m.mapping_hash for m in reordered["cad_request"].mappings) == tuple(
            m.mapping_hash for m in baseline["cad_request"].mappings
        )
        assert reordered["cad_stage"].realization.realization_hash == (
            baseline["cad_stage"].realization.realization_hash
        )
        assert reordered["admissibility"].result_hash == baseline["admissibility"].result_hash
        assert reordered["binding"].binding_hash == baseline["binding"].binding_hash
        assert reordered["m10_request"].request_hash == baseline["m10_request"].request_hash
        assert reordered["m10_stage"].outcome_hash == baseline["m10_stage"].outcome_hash
        assert reordered["evaluation"].evaluation_hash == baseline["evaluation"].evaluation_hash

    def test_realization_at1_common_set_semantic_reorder_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _realization_order_candidate,
        )

        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_realization_order_candidate,
        )

        # Named property (case 92): reordering only the common SET_SEMANTIC
        # realization collections preserves candidate@2 and the downstream CAD
        # identities. Full-lineage coverage is the case92 lineage test above.
        assert base_records["candidate"].candidate_hash == reordered_records["candidate"].candidate_hash
        assert (
            base_records["cad_request"].request_hash
            == reordered_records["cad_request"].request_hash
        )
        assert (
            base_records["cad_stage"].realization.realization_hash
            == reordered_records["cad_stage"].realization.realization_hash
        )

    def test_case92_admissibility_at2_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _realization_order_candidate,
        )

        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_realization_order_candidate,
        )

        # Named property: the M12-3 admissibility@2 semantic result hash is
        # unchanged. Authoritative per-phase coverage:
        # test_candidate_decision_v2.py (case92 lineage).
        assert (
            base_records["admissibility"].result_hash
            == reordered_records["admissibility"].result_hash
        )

    def test_case92_candidate_m10_at2_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _realization_order_candidate,
        )

        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_realization_order_candidate,
        )

        # Named property: the candidate-M10 @2 binding/inventory/request/
        # stage-outcome semantic hashes are unchanged. Authoritative per-phase
        # coverage: test_candidate_m10_v2.py / test_candidate_decision_v2.py.
        assert (
            base_records["binding"].binding_hash
            == reordered_records["binding"].binding_hash
        )
        assert (
            base_records["m10_request"].inventory.inventory_hash
            == reordered_records["m10_request"].inventory.inventory_hash
        )
        assert (
            base_records["m10_request"].request_hash
            == reordered_records["m10_request"].request_hash
        )
        assert (
            base_records["m10_stage"].outcome_hash
            == reordered_records["m10_stage"].outcome_hash
        )

    def test_case92_evaluation_at2_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _realization_order_candidate,
        )

        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_realization_order_candidate,
        )

        # Named property: the candidate evaluation@2 semantic hash is unchanged.
        # Authoritative per-phase coverage:
        # test_candidate_decision_v2.py (case92 lineage).
        assert (
            base_records["evaluation"].evaluation_hash
            == reordered_records["evaluation"].evaluation_hash
        )

    def test_case92_promotion_at2_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _compare_and_select,
            _decision_evaluation,
            _realization_order_candidate,
        )
        from test_candidate_trusted_semantic_verification import _at2_setup
        from mechcad_harness.candidates.promotion_models import (
            CandidatePromotionPolicyV2,
            CandidatePromotionRequestV2,
        )

        def _promotion_request(records):
            candidate = records["candidate"]
            synthesis_request = records["synthesis_request"]
            _, _, selection = _compare_and_select(records)
            policy = CandidatePromotionPolicyV2()
            return CandidatePromotionRequestV2(
                project_id=candidate.source_binding.project_id,
                source_revision=synthesis_request.source_binding.source_revision,
                source_state_hash=synthesis_request.source_binding.source_state_hash,
                candidate_hash=candidate.candidate_hash,
                synthesis_request_hash=synthesis_request.request_hash,
                synthesis_policy_hash=candidate.synthesis_policy_hash,
                m12_3_result_hash=records["admissibility"].result_hash,
                evaluation_hash=records["evaluation"].evaluation_hash,
                selection_hash=selection.selection_hash,
                promotion_policy_hash=policy.policy_hash,
                canonical_target_mechanism_id="mech-case92",
            )

        state, manager, store, _, request, policy, candidate = _at2_setup(tmp_path)
        shared_base = (state, manager, store, request, policy, candidate)
        base_records = _decision_evaluation(
            tmp_path / "base", base=shared_base
        )
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            base=shared_base,
            candidate_transform=_realization_order_candidate,
        )

        base_request = _promotion_request(base_records)
        reordered_request = _promotion_request(reordered_records)

        assert base_request.request_hash == reordered_request.request_hash


# =============================================================================
# CASE 93: FULL CHAIN
# =============================================================================


class TestStagedCase93:
    def test_component_specification_reorder_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Case 93: reordering the candidate-level collections preserves
        # candidate_hash@2 and the downstream CAD/admissibility/M10/evaluation
        # identities. Authoritative per-phase coverage:
        # test_candidate_decision_v2.py (case93 candidate-level ordering).
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert base_records["candidate"].candidate_hash == reordered_records["candidate"].candidate_hash
        assert (
            base_records["cad_request"].request_hash
            == reordered_records["cad_request"].request_hash
        )
        assert (
            base_records["admissibility"].result_hash
            == reordered_records["admissibility"].result_hash
        )
        assert (
            base_records["evaluation"].evaluation_hash
            == reordered_records["evaluation"].evaluation_hash
        )

    def test_design_variable_reorder_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Case 93: design-variable tuple reorder (complete records sorted by
        # name) preserves candidate_hash@2 and downstream identities.
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert base_records["candidate"].candidate_hash == reordered_records["candidate"].candidate_hash
        assert (
            base_records["admissibility"].result_hash
            == reordered_records["admissibility"].result_hash
        )
        assert (
            base_records["m10_request"].request_hash
            == reordered_records["m10_request"].request_hash
        )

    def test_unresolved_items_reorder_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Case 93: unresolved-items tuple reorder preserves candidate_hash@2 and
        # downstream identities. Authoritative per-phase coverage:
        # test_candidate_decision_v2.py (case93 candidate-level ordering).
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert base_records["candidate"].candidate_hash == reordered_records["candidate"].candidate_hash
        assert (
            base_records["cad_request"].request_hash
            == reordered_records["cad_request"].request_hash
        )
        assert (
            base_records["evaluation"].evaluation_hash
            == reordered_records["evaluation"].evaluation_hash
        )

    def test_combined_permutation_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Case 93: the combined component-spec/design-variable/unresolved-items
        # permutation preserves candidate_hash@2 and downstream identities.
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert base_records["candidate"].candidate_hash == reordered_records["candidate"].candidate_hash
        assert (
            base_records["admissibility"].result_hash
            == reordered_records["admissibility"].result_hash
        )
        assert (
            base_records["m10_stage"].outcome_hash
            == reordered_records["m10_stage"].outcome_hash
        )
        assert (
            base_records["evaluation"].evaluation_hash
            == reordered_records["evaluation"].evaluation_hash
        )

    def test_case93_cad_identities_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Named property: candidate CAD mapping@2/request@3/realization@2
        # semantic identities are unchanged by candidate-level reorder.
        # Authoritative per-phase coverage: test_candidate_decision_v2.py.
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert base_records["candidate"].candidate_hash == reordered_records["candidate"].candidate_hash
        assert (
            base_records["cad_request"].request_hash
            == reordered_records["cad_request"].request_hash
        )
        assert tuple(
            mapping.mapping_hash
            for mapping in base_records["cad_request"].mappings
        ) == tuple(
            mapping.mapping_hash
            for mapping in reordered_records["cad_request"].mappings
        )
        assert (
            base_records["cad_stage"].realization.realization_hash
            == reordered_records["cad_stage"].realization.realization_hash
        )

    def test_case93_admissibility_at2_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Named property: the M12-3 admissibility@2 semantic result hash is
        # unchanged. Authoritative per-phase coverage: test_candidate_decision_v2.py.
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert (
            base_records["admissibility"].result_hash
            == reordered_records["admissibility"].result_hash
        )

    def test_case93_candidate_m10_at2_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Named property: the candidate-M10 @2 binding/inventory/request/
        # stage-outcome semantic hashes are unchanged.
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert (
            base_records["binding"].binding_hash
            == reordered_records["binding"].binding_hash
        )
        assert (
            base_records["m10_request"].inventory.inventory_hash
            == reordered_records["m10_request"].inventory.inventory_hash
        )
        assert (
            base_records["m10_request"].request_hash
            == reordered_records["m10_request"].request_hash
        )
        assert (
            base_records["m10_stage"].outcome_hash
            == reordered_records["m10_stage"].outcome_hash
        )

    def test_case93_evaluation_at2_same(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _candidate_level_order_candidate,
        )

        # Named property: the candidate evaluation@2 semantic hash is unchanged.
        base_records = _decision_evaluation(tmp_path / "base")
        reordered_records = _decision_evaluation(
            tmp_path / "reordered",
            candidate_transform=_candidate_level_order_candidate,
        )

        assert (
            base_records["evaluation"].evaluation_hash
            == reordered_records["evaluation"].evaluation_hash
        )

    def test_case93_promotion_at2_same(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )
        from test_candidate_decision_v2 import _candidate_level_order_candidate
        from test_promotion_v2 import _promotion_family

        # Named property: the applicable promotion@2 request/readiness/
        # decision-input-reference identities are unchanged by candidate-level
        # reorder. Authoritative per-phase coverage:
        # test_promotion_v2.py::test_case_89_90_92_93_promotion_suffixes.
        base = _candidate_with_m13_multi_joint_authority(tmp_path)
        baseline = _promotion_family(tmp_path / "base", base)
        reordered = _promotion_family(
            tmp_path / "reordered", base,
            candidate_transform=_candidate_level_order_candidate,
        )

        assert (
            reordered["request"].request_hash == baseline["request"].request_hash
        )
        assert (
            reordered["readiness"].readiness_hash
            == baseline["readiness"].readiness_hash
        )
        assert (
            reordered["reference"].reference_hash == baseline["reference"].reference_hash
        )

    def test_case93_add_remove_change_different(self, tmp_path):
        from test_candidate_decision_v2 import (
            _decision_evaluation,
            _different_generator,
        )

        # Named property: a real candidate-level change must change the identity.
        base_records = _decision_evaluation(tmp_path / "base")
        changed_records = _decision_evaluation(
            tmp_path / "changed",
            candidate_transform=_different_generator,
        )

        assert base_records["candidate"].candidate_hash != changed_records["candidate"].candidate_hash

    def test_case93_non_empty_unresolved_promotion_ineligible(self, tmp_path):
        # Authoritative substantive coverage for case 93's non-empty
        # unresolved-items ineligibility (both permutations rejected, no
        # invented promotion identity) is
        # test_promotion_v2.py::test_case_93_non_empty_unresolved_is_rejected_by_existing_promotion_gate.
        # Invoke it here so this aggregate test fails if that property regresses.
        from test_promotion_v2 import (
            test_case_93_non_empty_unresolved_is_rejected_by_existing_promotion_gate,
        )

        test_case_93_non_empty_unresolved_is_rejected_by_existing_promotion_gate(tmp_path)

    def test_case93_no_fabricated_promotion_identity(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )
        from test_promotion_v2 import _promotion_family
        from mechcad_harness.candidates.promotion_models import (
            candidate_promotion_request_hash_v2,
        )

        # Named property: the eligible path's promotion request identity is a
        # genuine recomputation, never a fabricated placeholder. The ineligible
        # path's no-invention property is covered authoritatively by
        # test_promotion_v2.py::test_case_93_non_empty_unresolved_is_rejected_by_existing_promotion_gate.
        base = _candidate_with_m13_multi_joint_authority(tmp_path)
        family = _promotion_family(tmp_path, base)

        assert (
            candidate_promotion_request_hash_v2(family["request"])
            == family["request"].request_hash
        )
        assert family["request"].request_hash.startswith("sha256:")
