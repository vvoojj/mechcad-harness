from __future__ import annotations

import mechcad_harness.candidates.m10_evaluation as candidate_m10
import mechcad_harness.revolute_drive.models as revolute_drive_models
import pytest

from mechcad_harness.continuous_proof import CONTINUOUS_PROOF_ALGORITHM_VERSION
from mechcad_harness.candidates.models import CandidateDesignVariable, CandidateSynthesisRequest
from mechcad_harness.candidates.cad_realization import CandidateCadRealizationService
from mechcad_harness.multi_joint_kinematics import KinematicModel, RevoluteJointModel
from mechcad_harness.semantic_m10_kinematics import semantic_single_joint_kinematic_model_hash
from mechcad_harness.revolute_drive.service import RevoluteDriveRealizationService
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.state import StateManager

from task6_provenance_fixtures import make_home_result, make_proof_result
from test_candidate_cad_realization_v2 import _realization_at2
from test_candidate_cad_request_v3 import (
    _INSTANCE_SLOTS,
    _mapping_at2,
    _request_at3,
)
from test_candidate_trusted_semantic_verification import _at2_chain, _at2_setup


def _new_m10_records(candidate, synthesis_request, cad_realization, *, include_home=False):
    disposition_type = getattr(candidate_m10, "CandidateM10ConstituentDispositionV2")
    binding_type = getattr(candidate_m10, "CandidateM10BindingV2")
    scope_type = candidate_m10.CandidateM10EvaluationScope
    requirement_type = candidate_m10.CandidateM10PairScopeRequirement
    classification_type = getattr(candidate_m10, "CandidateCollisionPairClassificationV2")
    inventory_type = getattr(candidate_m10, "CandidateCollisionPairInventoryV2")
    request_type = getattr(candidate_m10, "CandidateM10EvaluationRequestV2")

    disposition_by_instance = {
        "drive-motor": (
            "internal_motion_unmodeled" if include_home else "fixed",
            None,
        ),
        "output-shaft": ("output_rigid", "J-1"),
        "bearing-a": ("fixed", None),
        "bearing-b": ("fixed", None),
        "output-hub": ("output_rigid", "J-1"),
        "motor-mount": ("fixed", None),
        "payload-body": ("output_rigid", "J-1"),
    }
    mapping_by_physical = {
        item.physical_instance_id: item for item in cad_realization.mappings
    }
    dispositions = tuple(
        disposition_type(
            schema_version="candidate-m10-constituent-disposition@2",
            physical_instance_id=physical_id,
            cad_instance_id=mapping_by_physical[physical_id].cad_instance_id,
            constituent_key=physical_id,
            disposition=disposition,
            output_transform_group=group,
        )
        for physical_id, (disposition, group) in disposition_by_instance.items()
    )
    parent_cad_instance = next(
        item
        for item in cad_realization.assembly.instances
        if item.instance_id == "cad-motor-mount"
    )
    output_axis_x_mm = 20.0
    model = KinematicModel(
        model_id="m12-output-model-at2",
        joints=(
            RevoluteJointModel(
                joint_id="J-1",
                parent_instance_id="cad-motor-mount",
                child_instance_id="cad-output-shaft",
                axis_origin_x_mm=output_axis_x_mm - parent_cad_instance.placement.x_mm,
                axis_direction_z=1.0,
            ),
        ),
    )
    binding = binding_type(
        schema_version="candidate-m10-binding@2",
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=cad_realization.realization_hash,
        model=model,
        semantic_single_joint_kinematic_model_hash=(
            semantic_single_joint_kinematic_model_hash(model)
        ),
        output_joint_id="J-1",
        driver_gear_constituent_key=None,
        output_axis=RevoluteAxis(
            origin_x_mm=output_axis_x_mm,
            origin_y_mm=0.0,
            origin_z_mm=0.0,
            direction_x=0.0,
            direction_y=0.0,
            direction_z=1.0,
            frame_id="joint:J-1",
        ),
        constituent_dispositions=dispositions,
    )
    scope_requirements = [
        requirement_type(
            requirement_key="bearing-hub-clearance",
            first_constituent_key="bearing-a",
            second_constituent_key="output-hub",
            required_classification="check_clearance",
        ),
    ]
    if include_home:
        scope_requirements.append(
            requirement_type(
                requirement_key="motor-home-check",
                first_constituent_key="drive-motor",
                second_constituent_key="bearing-a",
                required_classification="unmodeled_motion_out_of_scope",
                requires_home_exact_check=True,
            )
        )
    scope = scope_type(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=tuple(scope_requirements),
        fidelity_requirements=(),
        required_home_check_semantics=(),
        proof_service_version="m10-single-axis-continuous-proof@1",
    )
    inventory = inventory_type.complete_for(
        cad_realization, binding, scope
    )
    request = request_type(
        schema_version="candidate-m10-evaluation-request@2",
        candidate_hash=candidate.candidate_hash,
        cad_realization_hash=cad_realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        semantic_single_joint_kinematic_model_hash=(
            binding.semantic_single_joint_kinematic_model_hash
        ),
        mapping_hashes=tuple(sorted(item.mapping_hash for item in cad_realization.mappings)),
        inventory=inventory,
    )
    return binding, scope, request


def _policy_requirements():
    scalar = revolute_drive_models.SourceBoundScalar
    provenance = revolute_drive_models.InputProvenanceKind.POLICY_ASSUMPTION
    bound = lambda value, unit: scalar(value=value, unit=unit, provenance=provenance)
    return revolute_drive_models.RevoluteDriveEngineeringRequirements(
        required_output_speed=bound(100.0, "rpm"),
        design_load_case=revolute_drive_models.StaticOutputShaftDesignLoadCase(
            design_torque=bound(10.0, "N*m"),
            transverse_force_y=bound(0.0, "N"),
            transverse_force_z=bound(0.0, "N"),
        ),
        required_voltage=bound(24.0, "V"),
        safety_factor=bound(2.0, "1"),
        shaft_yield_strength=bound(250.0, "MPa"),
        shaft_support_geometry=revolute_drive_models.ShaftSupportGeometry(
            support_a_x=bound(0.0, "mm"),
            support_b_x=bound(100.0, "mm"),
            load_plane_x=bound(50.0, "mm"),
        ),
        trusted_source_scalar_bindings=(),
    )


def test_request_v2_candidate_v2_admissibility_v2_and_candidate_m10_v2_restart(tmp_path):
    _, _, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
    assert synthesis_request.schema_version == "candidate-synthesis-request@2"
    assert candidate.schema_version == "mechanical-design-candidate@2"
    assert candidate.source_binding == synthesis_request.source_binding
    assert candidate.semantic_source_binding_hash == synthesis_request.semantic_source_binding_hash

    admissibility = RevoluteDriveRealizationService().evaluate(
        candidate,
        synthesis_request,
        policy,
        _policy_requirements(),
    )
    assert admissibility.schema_version == "revolute-drive-admissibility@2"
    assert admissibility.candidate_hash == candidate.candidate_hash
    assert admissibility.source_binding_hash == synthesis_request.semantic_source_binding_hash
    assert admissibility.synthesis_request_hash == synthesis_request.request_hash
    assert (
        revolute_drive_models.admissibility_result_hash(admissibility)
        == admissibility.result_hash
    )

    cad_request = _request_at3(
        candidate, synthesis_request.semantic_source_binding_hash
    )
    cad_realization = _realization_at2(candidate, cad_request)
    binding, scope, m10_request = _new_m10_records(
        candidate, synthesis_request, cad_realization
    )
    proof_calls = []

    def prove(**kwargs):
        proof_calls.append(kwargs)
        return make_proof_result(kwargs)

    stage = candidate_m10.CandidateM10EvaluationService(
        prove,
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("no home exact check is declared")
        ),
        scope=scope,
    ).evaluate(
        synthesis_request.source_binding.source_revision,
        synthesis_request.source_binding.source_state_hash,
        cad_realization,
        binding,
        m10_request,
    )
    assert stage.schema_version == "candidate-m10-stage-outcome@2"
    assert len(proof_calls) == 1
    assert len(stage.pair_proofs) == 1
    proof = stage.pair_proofs[0]
    assert set(type(proof).model_fields) == {
        "schema_version", "pair", "moving_instance_id", "stationary_instance_id",
        "request", "result", "request_hash", "result_hash",
        "semantic_assembly_hash", "proof_hash",
    }
    assert "semantic_proof_request_hash" not in proof.model_dump(mode="json")
    assert "semantic_proof_result_hash" not in proof.model_dump(mode="json")
    raw_identity_substitution = proof.model_copy(
        update={
            "request_hash": "sha256:" + "a" * 64,
            "result_hash": "sha256:" + "b" * 64,
        }
    )
    assert candidate_m10.candidate_m10_pair_proof_hash_v2(
        raw_identity_substitution
    ) == proof.proof_hash
    with pytest.raises(ValueError, match="raw replay identities"):
        candidate_m10.CandidateM10PairProofV2.model_validate(
            raw_identity_substitution.model_dump(mode="json")
        )

    # Persisted @2 wrappers re-derive P1/P2 and the stage hash without invoking M10.
    restarted = candidate_m10.CandidateM10StageOutcomeV2.model_validate(
        stage.model_dump(mode="json")
    )
    assert restarted == stage
    restarted.validate_against(
        candidate,
        synthesis_request,
        admissibility,
        cad_realization,
        binding,
        m10_request,
        scope,
    )
    assert len(proof_calls) == 1
    assert {
        "revolute-drive-admissibility@2": admissibility.result_hash,
        "candidate-m10-constituent-disposition@2": binding.constituent_dispositions[0].disposition_hash,
        "candidate-m10-collision-pair-classification@2": m10_request.inventory.classifications[0].classification_hash,
        "candidate-m10-binding@2": binding.binding_hash,
        "candidate-m10-collision-pair-inventory@2": m10_request.inventory.inventory_hash,
        "candidate-m10-evaluation-request@2": m10_request.request_hash,
        "candidate-m10-pair-proof@2": proof.proof_hash,
        "candidate-m10-stage-outcome@2": stage.outcome_hash,
    } == {
        "revolute-drive-admissibility@2": "sha256:365cfe398a7501a70bb7f8bd143f8de4b0f7185e1eb06df5d4f1d83f92ce0980",
        "candidate-m10-constituent-disposition@2": "sha256:f336b53ec988b92ba73821043523736e5a04c41a12c9dde6e276a4879b73c38a",
        "candidate-m10-collision-pair-classification@2": "sha256:ae42d03305b867a8d22b67c3059cda84f4239866cbbb21402a5e6cb368ef1bd9",
        "candidate-m10-binding@2": "sha256:fe7f4aea5b9d6146673768f7544ef0b36dd773d3b8c28057665e5bd0dd0e0ce4",
        "candidate-m10-collision-pair-inventory@2": "sha256:0c6e60e6e432899d0029c18808b68dd49bfd37a144028eaec7c4f452dc322db5",
        "candidate-m10-evaluation-request@2": "sha256:1e89c37c0e26ca11c6f16bb95407adccac83bb65cbf1c1776b48fe9256c8df33",
        "candidate-m10-pair-proof@2": "sha256:0068619305e9fa2aab475dd52a9b5a68898023a702fb676e80f70739b707b889",
        "candidate-m10-stage-outcome@2": "sha256:c1276c7eddb1892692be87f3e47cf050e80f52c7dc47bf94b9193cda7edee8f2",
    }
    coordinate_only = candidate_m10.CandidateM10StageOutcomeV2.model_validate(
        stage.model_dump(mode="json")
        | {
            "source_revision": stage.source_revision + 1,
            "source_state_hash": "sha256:" + "f" * 64,
            "outcome_hash": "pending",
        }
    )
    assert coordinate_only.outcome_hash == stage.outcome_hash


def test_candidate_cad_service_v2_output_is_consumed_by_candidate_m10_v2(tmp_path):
    _, manager, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
    mappings = tuple(
        _mapping_at2(candidate.candidate_hash, instance_id, slot)
        for instance_id, slot in _INSTANCE_SLOTS
    )
    cad_request = _request_at3(
        candidate,
        synthesis_request.semantic_source_binding_hash,
        mappings=mappings,
    )
    cad_stage = CandidateCadRealizationService(
        tmp_path, "PRJ-M12", manager
    ).realize(candidate, synthesis_request, policy, cad_request)
    assert cad_stage.schema_version == "candidate-cad-stage-outcome@2"
    assert cad_stage.status.value == "success"
    cad_realization = cad_stage.realization
    assert cad_realization is not None

    binding, scope, m10_request = _new_m10_records(
        candidate, synthesis_request, cad_realization
    )
    proof_calls = []

    def prove(**kwargs):
        proof_calls.append(kwargs)
        return make_proof_result(kwargs)

    m10_stage = candidate_m10.CandidateM10EvaluationService(
        prove,
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("no home exact check is declared")
        ),
        scope=scope,
    ).evaluate(
        synthesis_request.source_binding.source_revision,
        synthesis_request.source_binding.source_state_hash,
        cad_realization,
        binding,
        m10_request,
    )
    assert m10_stage.schema_version == "candidate-m10-stage-outcome@2"
    assert len(proof_calls) == 1
    m10_stage.validate_against(
        candidate,
        synthesis_request,
        RevoluteDriveRealizationService().evaluate(
            candidate, synthesis_request, policy, _policy_requirements()
        ),
        cad_realization,
        binding,
        m10_request,
        scope,
    )
    assert len(proof_calls) == 1


def test_m12_3_v2_rejects_legacy_request_identity_and_binding_mismatch(tmp_path):
    _, _, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
    service = RevoluteDriveRealizationService()
    legacy_request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@1",
        source_binding=synthesis_request.source_binding,
        requested_joint_ids=synthesis_request.requested_joint_ids,
        required_joint_ids=synthesis_request.required_joint_ids,
    )
    with pytest.raises(ValueError, match="candidate@2 requires candidate-synthesis-request@2"):
        service.evaluate(candidate, legacy_request, policy, _policy_requirements())
    legacy_hash_candidate = type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "synthesis_request_hash": legacy_request.request_hash,
            "candidate_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="candidate synthesis request@2 identity mismatch"):
        service.evaluate(
            legacy_hash_candidate,
            synthesis_request,
            policy,
            _policy_requirements(),
        )

    mismatched = type(candidate).model_validate(
        candidate.model_dump(mode="json")
        | {
            "semantic_source_binding_hash": "sha256:" + "f" * 64,
            "candidate_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="semantic source binding"):
        service.evaluate(mismatched, synthesis_request, policy, _policy_requirements())


def test_candidate_m10_v2_record_field_counts_are_exact():
    expected = {
        "CandidateM10ConstituentDispositionV2": {
            "schema_version", "physical_instance_id", "cad_instance_id",
            "constituent_key", "disposition", "output_transform_group",
            "disposition_hash",
        },
        "CandidateCollisionPairClassificationV2": {
            "schema_version", "pair", "classification", "reason",
            "requires_home_exact_check", "classification_hash",
        },
        "CandidateM10BindingV2": {
            "schema_version", "candidate_hash", "cad_realization_hash", "model",
            "semantic_single_joint_kinematic_model_hash", "output_joint_id",
            "driver_gear_constituent_key", "output_axis", "constituent_dispositions",
            "binding_hash",
        },
        "CandidateCollisionPairInventoryV2": {
            "schema_version", "cad_realization_hash", "binding_hash", "scope_hash",
            "expected_pair_universe", "classifications", "checked_pairs",
            "excluded_pairs", "inventory_hash",
        },
        "CandidateM10EvaluationRequestV2": {
            "schema_version", "candidate_hash", "cad_realization_hash", "binding_hash",
            "scope_hash", "semantic_single_joint_kinematic_model_hash",
            "mapping_hashes", "inventory", "request_hash",
        },
        "CandidateM10PairProofV2": {
            "schema_version", "pair", "moving_instance_id", "stationary_instance_id",
            "request", "result", "request_hash", "result_hash",
            "semantic_assembly_hash", "proof_hash",
        },
        "CandidateHomeExactCheckV2": {
            "schema_version", "pair", "moving_instance_id", "stationary_instance_id",
            "request", "result", "request_hash", "result_hash",
            "semantic_assembly_hash", "check_hash",
        },
        "CandidateM10StageOutcomeV2": {
            "schema_version", "status", "candidate_hash", "cad_realization_hash",
            "binding_hash", "scope_hash", "evaluation_request_hash",
            "source_revision", "source_state_hash", "pair_proofs", "home_exact_checks",
            "reasons", "outcome_hash",
        },
    }
    for name, fields in expected.items():
        record_type = getattr(candidate_m10, name)
        assert set(record_type.model_fields) == fields


def test_raw_only_timestamp_and_artifact_id_rotation_preserves_m12_and_candidate_m10_v2(tmp_path):
    manager = StateManager(tmp_path)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12", run_id="P5-2-ROTATION")
    state_a, _, request_a, policy_a, candidate_a = _at2_chain(
        tmp_path, manager, store, variant="A"
    )
    state_b, _, request_b, policy_b, candidate_b = _at2_chain(
        tmp_path, manager, store, variant="B"
    )
    assert request_a.request_hash == request_b.request_hash
    assert request_a.semantic_source_binding_hash == request_b.semantic_source_binding_hash
    assert candidate_a.candidate_hash == candidate_b.candidate_hash

    requirements_a, requirements_b = _policy_requirements(), _policy_requirements()
    m12_service = RevoluteDriveRealizationService()
    admissibility_a = m12_service.evaluate(
        candidate_a, request_a, policy_a, requirements_a, source_state=state_a
    )
    admissibility_b = m12_service.evaluate(
        candidate_b, request_b, policy_b, requirements_b, source_state=state_b
    )
    assert admissibility_a.schema_version == "revolute-drive-admissibility@2"
    assert admissibility_a.result_hash == admissibility_b.result_hash

    cad_request_a = _request_at3(candidate_a, request_a.semantic_source_binding_hash)
    cad_request_b = _request_at3(candidate_b, request_b.semantic_source_binding_hash)
    cad_a = _realization_at2(candidate_a, cad_request_a)
    cad_b = _realization_at2(candidate_b, cad_request_b)
    assert cad_a.assembly_hash != cad_b.assembly_hash
    assert cad_a.realization_hash == cad_b.realization_hash

    binding_a, scope_a, m10_request_a = _new_m10_records(candidate_a, request_a, cad_a)
    binding_b, scope_b, m10_request_b = _new_m10_records(candidate_b, request_b, cad_b)
    assert binding_a.binding_hash == binding_b.binding_hash
    assert m10_request_a.request_hash == m10_request_b.request_hash

    evaluator_changed_binding = binding_a.model_copy(
        update={
            "model": binding_a.model.model_copy(
                update={"evaluator_version": "multi-joint-forward-kinematics@other"}
            )
        }
    )
    assert candidate_m10.candidate_m10_binding_hash_v2(
        evaluator_changed_binding
    ) == binding_a.binding_hash

    def evaluate(realization, binding, request, scope, source_binding):
        calls = []

        def prove(**kwargs):
            calls.append(kwargs)
            return make_proof_result(kwargs)

        stage = candidate_m10.CandidateM10EvaluationService(
            prove,
            lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("home exact check is not part of this scope")
            ),
            scope=scope,
        ).evaluate(
            source_binding.source_revision,
            source_binding.source_state_hash,
            realization,
            binding,
            request,
        )
        return stage, calls

    stage_a, calls_a = evaluate(
        cad_a, binding_a, m10_request_a, scope_a, request_a.source_binding
    )
    stage_b, calls_b = evaluate(
        cad_b, binding_b, m10_request_b, scope_b, request_b.source_binding
    )
    assert len(calls_a) == len(calls_b) == 1
    assert stage_a.outcome_hash == stage_b.outcome_hash
    assert stage_a.pair_proofs[0].request_hash != stage_b.pair_proofs[0].request_hash
    assert stage_a.pair_proofs[0].result_hash != stage_b.pair_proofs[0].result_hash
    assert stage_a.pair_proofs[0].proof_hash == stage_b.pair_proofs[0].proof_hash


def test_candidate_home_exact_check_v2_replays_without_execution(tmp_path):
    _, _, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
    admissibility = RevoluteDriveRealizationService().evaluate(
        candidate, synthesis_request, policy, _policy_requirements()
    )
    cad_request = _request_at3(
        candidate, synthesis_request.semantic_source_binding_hash
    )
    cad_realization = _realization_at2(candidate, cad_request)
    binding, scope, m10_request = _new_m10_records(
        candidate, synthesis_request, cad_realization, include_home=True
    )
    calls = []

    def analyze(**kwargs):
        calls.append(kwargs)
        return make_home_result(kwargs)

    stage = candidate_m10.CandidateM10EvaluationService(
        lambda **kwargs: make_proof_result(kwargs),
        analyze,
        scope=scope,
    ).evaluate(
        synthesis_request.source_binding.source_revision,
        synthesis_request.source_binding.source_state_hash,
        cad_realization,
        binding,
        m10_request,
    )
    assert stage.schema_version == "candidate-m10-stage-outcome@2"
    assert len(stage.home_exact_checks) == 1
    check = stage.home_exact_checks[0]
    assert set(type(check).model_fields) == {
        "schema_version", "pair", "moving_instance_id", "stationary_instance_id",
        "request", "result", "request_hash", "result_hash",
        "semantic_assembly_hash", "check_hash",
    }
    assert "semantic_sweep_request_hash" not in check.model_dump(mode="json")
    assert "semantic_sweep_result_hash" not in check.model_dump(mode="json")

    restarted = candidate_m10.CandidateM10StageOutcomeV2.model_validate(
        stage.model_dump(mode="json")
    )
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
    assert {
        "candidate-home-exact-check@2": check.check_hash,
        "candidate-m10-stage-outcome@2-home": stage.outcome_hash,
    } == {
        "candidate-home-exact-check@2": "sha256:77f22b9af42e084e31f05c9b30e23e94824c3740577c383c4f537f6d5f07620d",
        "candidate-m10-stage-outcome@2-home": "sha256:6f2c595ba6c19a68984cf10ad6fd6b48e2531f15ff6f2ed9b9e7fb9a67fd38c7",
    }


def test_m12_admissibility_v2_preserves_the_legacy_declared_field_count():
    result_type = revolute_drive_models.RevoluteDriveAdmissibilityResult
    assert set(result_type.model_fields) == {
        "schema_version", "candidate_hash", "source_binding_hash",
        "synthesis_request_hash", "synthesis_policy_hash", "requirements_hash",
        "design_variables", "consumed_property_bindings", "calculation_id",
        "calculation_version", "checks", "status", "result_hash",
    }
    assert result_type.model_fields["schema_version"].default == (
        "revolute-drive-admissibility@1"
    )


def test_admissibility_at2_hash_sorts_variables_without_mutating_the_stored_tuple(tmp_path):
    _, _, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
    result = RevoluteDriveRealizationService().evaluate(
        candidate, synthesis_request, policy, _policy_requirements()
    )
    variables = (
        CandidateDesignVariable(name="z-variable", value=2.0),
        CandidateDesignVariable(name="a-variable", value=1.0),
    )

    def rebuilt(schema_version, ordered_variables):
        return type(result).model_validate(
            result.model_dump(mode="json")
            | {
                "schema_version": schema_version,
                "design_variables": [item.model_dump(mode="json") for item in ordered_variables],
                "result_hash": "pending",
            }
        )

    forward = rebuilt("revolute-drive-admissibility@2", variables)
    reverse = rebuilt("revolute-drive-admissibility@2", tuple(reversed(variables)))
    assert forward.design_variables == variables
    assert reverse.design_variables == tuple(reversed(variables))
    assert forward.result_hash == reverse.result_hash
    assert revolute_drive_models.admissibility_result_hash(forward) == forward.result_hash

    legacy_forward = rebuilt("revolute-drive-admissibility@1", variables)
    legacy_reverse = rebuilt("revolute-drive-admissibility@1", tuple(reversed(variables)))
    assert legacy_forward.result_hash != legacy_reverse.result_hash


_UNSET_REALIZATION = object()


class TestSingleJointM10V2RealizationAdmission:
    """Case-92 admission: single-joint candidate M10@2 accepts realization@1/@2.

    The single-joint @2 binding only needs common realization semantics via the
    shared schema-dispatched projection. The realization@2-only bridge /
    multi-joint mechanism path stays reject-only for realization@1.
    """

    def _at1_chain(self, tmp_path):
        _, _, _, _, synthesis_request, policy, candidate = _at2_setup(tmp_path)
        assert candidate.schema_version == "mechanical-design-candidate@2"
        assert candidate.realization.schema_version == "physical-mechanism-realization@1"
        admissibility = RevoluteDriveRealizationService().evaluate(
            candidate,
            synthesis_request,
            policy,
            _policy_requirements(),
        )
        assert admissibility.schema_version == "revolute-drive-admissibility@2"
        cad_request = _request_at3(
            candidate, synthesis_request.semantic_source_binding_hash
        )
        cad_realization = _realization_at2(candidate, cad_request)
        binding, scope, m10_request = _new_m10_records(
            candidate, synthesis_request, cad_realization
        )
        return {
            "synthesis_request": synthesis_request,
            "candidate": candidate,
            "admissibility": admissibility,
            "cad_request": cad_request,
            "cad_realization": cad_realization,
            "binding": binding,
            "scope": scope,
            "m10_request": m10_request,
        }

    def _evaluate(self, chain, physical_realization=_UNSET_REALIZATION):
        from task6_provenance_fixtures import make_proof_result as _prove_factory

        if physical_realization is _UNSET_REALIZATION:
            physical_realization = chain["candidate"].realization

        def prove(**kwargs):
            return _prove_factory(kwargs)

        return candidate_m10.CandidateM10EvaluationService(
            prove,
            lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("no home exact check is declared in this scope")
            ),
            scope=chain["scope"],
        ).evaluate(
            chain["synthesis_request"].source_binding.source_revision,
            chain["synthesis_request"].source_binding.source_state_hash,
            chain["cad_realization"],
            chain["binding"],
            chain["m10_request"],
            scope=chain["scope"],
            physical_realization=physical_realization,
        )

    def test_a_realization_at1_accepted_through_m10_v2_evaluation(self, tmp_path):
        chain = self._at1_chain(tmp_path)
        chain["binding"].validate_against(
            chain["cad_realization"], chain["candidate"].realization
        )
        stage = self._evaluate(chain)
        assert stage.schema_version == "candidate-m10-stage-outcome@2"
        unbound = self._evaluate(chain, physical_realization=None)
        assert stage.outcome_hash == unbound.outcome_hash

    def test_b_set_semantic_reorder_of_realization_at1_preserves_m10_v2_identity(
        self, tmp_path
    ):
        from test_candidate_decision_v2 import _realization_order_candidate

        chain = self._at1_chain(tmp_path)
        reordered_candidate = _realization_order_candidate(chain["candidate"])
        assert (
            reordered_candidate.realization.schema_version
            == "physical-mechanism-realization@1"
        )
        assert reordered_candidate.candidate_hash == chain["candidate"].candidate_hash
        reordered_request = _request_at3(
            reordered_candidate,
            chain["synthesis_request"].semantic_source_binding_hash,
        )
        assert reordered_request.request_hash == chain["cad_request"].request_hash
        reordered_realization = _realization_at2(
            reordered_candidate, reordered_request
        )
        assert (
            reordered_realization.realization_hash
            == chain["cad_realization"].realization_hash
        )
        reordered_binding, _, reordered_request_m10 = _new_m10_records(
            reordered_candidate,
            chain["synthesis_request"],
            reordered_realization,
        )
        assert reordered_binding.binding_hash == chain["binding"].binding_hash
        assert reordered_request_m10.request_hash == chain["m10_request"].request_hash
        reordered_chain = dict(
            chain,
            candidate=reordered_candidate,
            cad_request=reordered_request,
            cad_realization=reordered_realization,
            binding=reordered_binding,
            m10_request=reordered_request_m10,
        )
        assert (
            self._evaluate(reordered_chain).outcome_hash
            == self._evaluate(chain).outcome_hash
        )

    def test_c_engineering_change_in_realization_at1_changes_identity(self, tmp_path):
        from test_candidate_decision_v2 import _support_order_candidate

        chain = self._at1_chain(tmp_path)
        changed = _support_order_candidate(chain["candidate"])
        assert changed.candidate_hash != chain["candidate"].candidate_hash

    def test_d_invalid_realization_at1_binding_rejected(self, tmp_path):
        from mechcad_harness.candidates.models import MechanicalConnection

        chain = self._at1_chain(tmp_path)
        payload = chain["candidate"].realization.model_dump(mode="json")
        payload["connections"] = [
            *payload["connections"],
            MechanicalConnection(
                connection_id="gear-mesh-invalid",
                kind="gear_mesh",
                from_instance_id="drive-motor",
                from_interface_id="output-shaft",
                to_instance_id="output-shaft",
                to_interface_id="motor-side",
            ).model_dump(mode="json"),
        ]
        payload["realization_hash"] = "pending"
        forged = type(chain["candidate"].realization).model_validate(payload)
        assert forged.schema_version == "physical-mechanism-realization@1"
        with pytest.raises(ValueError, match="transmission role"):
            chain["binding"].validate_physical_realization(forged)
        with pytest.raises(ValueError, match="transmission role"):
            chain["binding"].validate_against(chain["cad_realization"], forged)

    def test_e_unknown_realization_schema_rejected(self, tmp_path):
        chain = self._at1_chain(tmp_path)
        forged = chain["candidate"].realization.model_copy(
            update={"schema_version": "physical-mechanism-realization@9"}
        )
        with pytest.raises(ValueError, match="physical-mechanism-realization"):
            chain["binding"].validate_physical_realization(forged)
        with pytest.raises(ValueError, match="physical-mechanism-realization"):
            chain["binding"].validate_against(chain["cad_realization"], forged)

    def test_f_realization_at2_positive_path_unchanged(self, tmp_path):
        from test_candidate_decision_v2 import _decision_evaluation

        records = _decision_evaluation(tmp_path / "at2-positive")
        candidate = records["candidate"]
        assert candidate.realization.schema_version == "physical-mechanism-realization@2"
        records["binding"].validate_against(
            records["cad_realization"], candidate.realization
        )
        assert (
            records["m10_stage"].schema_version == "candidate-m10-stage-outcome@2"
        )

    def test_g_bridge_path_still_rejects_realization_at1(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import _candidate_cad_v2
        from mechcad_harness.candidates.multi_joint_m10_bridge import (
            PhysicalToM10V2BridgeCompiler,
        )

        state, _, _, _, synthesis_request, _, candidate = _at2_setup(tmp_path)
        assert candidate.realization.schema_version == "physical-mechanism-realization@1"
        _, cad_realization = _candidate_cad_v2(candidate, synthesis_request, state)
        with pytest.raises(ValueError, match="physical-mechanism-realization@2"):
            PhysicalToM10V2BridgeCompiler().compile_candidate(
                candidate, cad_realization
            )

    def test_h_mechanism_hash_remains_realization_at2_only(self, tmp_path):
        from test_candidate_multijoint_m10_v2 import (
            _candidate_with_m13_multi_joint_authority,
        )
        from mechcad_harness.candidates.models import (
            semantic_candidate_mechanism_hash,
        )

        _, _, _, _, _, _, at1_candidate = _at2_setup(tmp_path)
        with pytest.raises(ValueError, match="realization@2"):
            semantic_candidate_mechanism_hash(at1_candidate.realization)
        _, _, _, _, _, at2_candidate = _candidate_with_m13_multi_joint_authority(
            tmp_path / "at2-mechanism"
        )
        assert at2_candidate.realization.schema_version == (
            "physical-mechanism-realization@2"
        )
        mechanism_hash = semantic_candidate_mechanism_hash(at2_candidate.realization)
        assert mechanism_hash.startswith("sha256:")
        assert mechanism_hash == semantic_candidate_mechanism_hash(
            at2_candidate.realization
        )

    def test_i_legacy_m10_physical_admission_unchanged(self, tmp_path):
        from test_m12_candidate_m10_binding import _binding as _legacy_binding
        from test_m12_candidate_m10_binding import _realization as _legacy_realization

        _, _, _, _, _, _, candidate = _at2_setup(tmp_path)
        legacy_binding = _legacy_binding(_legacy_realization())
        legacy_binding.validate_physical_realization(candidate.realization)
