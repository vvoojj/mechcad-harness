from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from mechcad_harness.cad_assembly import assembly_hash
from mechcad_harness.candidates import PrePromotionM10ScopeProjection
from mechcad_harness.candidates.canonical_cad import (
    CanonicalCadRealization,
    CanonicalPhysicalCadCompiler,
)
from mechcad_harness.candidates.canonical_mechanism import CanonicalMechanismReconstruction
from mechcad_harness.candidates import PromotableMechanismProjection
from mechcad_harness.candidates.promotion_models import PromotionPhysicalPairRequirement
from mechcad_harness.candidates.canonical_m10 import (
    CanonicalM10HomeExactCheck,
    CanonicalM10PairProof,
    CanonicalM10ScopeEquivalenceService,
    CanonicalM10ScopeEquivalenceResult,
    CanonicalM10VerificationService,
    CanonicalM10VerificationStatus,
    DerivedCanonicalM10Scope,
)
from mechcad_harness.continuous_proof import (
    ContinuousCollisionWitness,
    ContinuousIntervalCertificate,
    ContinuousPairCertificate,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
)
from mechcad_harness.kinematic_sweep import (
    CadKinematicCollisionPairResult,
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CadKinematicSweepSample,
    CollisionClassification,
    RevoluteAxis,
    SweepAggregateClassification,
    transformed_assembly_program,
)
from mechcad_harness.models import (
    CanonicalConnectionMeaning,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    CanonicalPhysicalPairRequirement,
)
from mechcad_harness.state.hashing import canonical_json

from test_m12_canonical_cad import _fixture


def _joint_semantic_hash(binding) -> str:
    payload = {
        "joint_id": binding.joint_id,
        "joint_kind": "revolute",
        "parent_instance_id": binding.expected_parent_instance_id,
        "child_instance_id": binding.expected_child_instance_id,
        "axis_origin": [
            binding.axis_origin_x_mm,
            binding.axis_origin_y_mm,
            binding.axis_origin_z_mm,
        ],
        "axis_direction": [
            binding.axis_direction_x,
            binding.axis_direction_y,
            binding.axis_direction_z,
        ],
        "semantic_version": binding.semantic_version,
    }
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _canonical_inputs(tmp_path, *, requires_home=False):
    _, _, mechanism, _, reconstruction, resolver = _fixture(tmp_path)
    binding = reconstruction.mechanism.joint_bindings[0]
    binding = binding.model_copy(
        update={"semantic_hash": _joint_semantic_hash(binding), "binding_hash": "pending"}
    )
    base_obligation = reconstruction.mechanism.m10_obligations[0]
    obligation = type(base_obligation).model_validate(
        base_obligation.model_dump(mode="python")
        | {
            "physical_pair_requirements": tuple(
                type(item).model_validate(
                    item.model_dump(mode="python")
                    | {
                        "requires_home_exact_check": requires_home,
                        "requirement_hash": "pending",
                    }
                )
                for item in base_obligation.physical_pair_requirements
            ),
            "obligation_hash": "pending",
        }
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        reconstruction.mechanism.model_dump(mode="python")
        | {
            "joint_bindings": (binding,),
            "m10_obligations": (obligation,),
            "mechanism_hash": "pending",
        }
    )
    projection = PromotableMechanismProjection(
        canonical_target_mechanism_id=mechanism.id,
        canonical_instance_ids=tuple(item.instance_id for item in mechanism.components),
        component_specifications=mechanism.component_specifications,
        components=mechanism.components,
        accepted_design_choices=mechanism.accepted_design_choices,
        placements=mechanism.placements,
        connections=mechanism.connections,
        joint_bindings=mechanism.joint_bindings,
        m10_obligations=mechanism.m10_obligations,
        mapping_identities=tuple(item.instance_id for item in mechanism.components),
    )
    reconstruction = CanonicalMechanismReconstruction.model_validate(
        reconstruction.model_dump(mode="python")
        | {
            "canonical_mechanism": mechanism,
            "normalized_projection_hash": projection.projection_hash,
        }
    )
    cad = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
    return reconstruction, cad


def _topology_registry_mechanism(mechanism):
    base_specification = mechanism.component_specifications[1]
    topology_specification = type(base_specification).model_validate(
        base_specification.model_dump(mode="python")
        | {
            "interfaces": (*base_specification.interfaces, "gear", "output", "rotor"),
            "specification_hash": "pending",
        }
    )
    components = tuple(
        component.model_copy(
            update={
                "specification_hash": topology_specification.specification_hash,
                "component_hash": "pending",
            }
        )
        if component.specification_hash == base_specification.specification_hash
        else component
        for component in mechanism.components
    )
    return CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="python")
        | {
            "component_specifications": (
                mechanism.component_specifications[0],
                topology_specification,
            ),
            "components": components,
            "mechanism_hash": "pending",
        }
    )


def _proof_result(kwargs, status=ContinuousSingleAxisProofStatus.VERIFIED_CLEAR):
    request = ContinuousSingleAxisProofRequest(
        source_assembly_id=kwargs["assembly"].assembly_id,
        source_assembly_hash=assembly_hash(kwargs["assembly"]),
        axis=kwargs["axis"],
        start_angle_deg=kwargs["start_angle_deg"],
        end_angle_deg=kwargs["end_angle_deg"],
        moving_instance_ids=kwargs["moving_instance_ids"],
        stationary_instance_ids=kwargs["stationary_instance_ids"],
        required_clearance_mm=kwargs["required_clearance_mm"],
        proof_guard_mm=kwargs["proof_guard_mm"],
        max_depth=kwargs["max_depth"],
        minimum_interval_deg=kwargs["minimum_interval_deg"],
        max_exact_evaluations=kwargs["max_exact_evaluations"],
    )

    certificate = ContinuousIntervalCertificate(
        interval_start_deg=request.start_angle_deg,
        interval_end_deg=request.end_angle_deg,
        reference_angle_deg=request.start_angle_deg,
        pair_certificates=(
            ContinuousPairCertificate(
                moving_instance_id=request.moving_instance_ids[0],
                stationary_instance_id=request.stationary_instance_ids[0],
                exact_distance_mm=10.0,
                radial_bound_mm=1.0,
                angular_motion_bound_mm=0.1,
                certified_lower_clearance_mm=9.9,
            ),
        ),
        minimum_certified_lower_clearance_mm=9.9,
    )
    result = ContinuousSingleAxisProofResult(
        request_hash=request.request_hash,
        source_assembly_hash=request.source_assembly_hash,
        proof_algorithm_version=CONTINUOUS_PROOF_ALGORITHM_VERSION,
        axis=request.axis,
        start_angle_deg=request.start_angle_deg,
        end_angle_deg=request.end_angle_deg,
        moving_instance_ids=request.moving_instance_ids,
        stationary_instance_ids=request.stationary_instance_ids,
        required_clearance_mm=request.required_clearance_mm,
        proof_guard_mm=request.proof_guard_mm,
        status=status,
        certified_leaf_certificates=(certificate,) if status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR else (),
        unresolved_intervals=() if status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR else ((request.start_angle_deg, request.end_angle_deg),),
        exact_evaluations_count=1,
        maximum_depth_reached=0,
    )
    if status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS:
        result = result.model_copy(update={
            "collision_witness": ContinuousCollisionWitness(
                witness_angle_deg=request.start_angle_deg,
                moving_instance_id=request.moving_instance_ids[0],
                stationary_instance_id=request.stationary_instance_ids[0],
                interference_volume_mm3=1.0,
                exact_distance_mm=0.0,
                classification="interference",
            )
        })
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    return result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )


def _home_result(kwargs, *, collision=False):
    request = CadKinematicSweepRequest(
        source_assembly_id=kwargs["assembly"].assembly_id,
        source_assembly_hash=assembly_hash(kwargs["assembly"]),
        axis=kwargs["axis"],
        sample_angles_deg=(0.0,),
        moving_instance_ids=kwargs["moving_instance_ids"],
        stationary_instance_ids=kwargs["stationary_instance_ids"],
    )
    classification = (
        CollisionClassification.INTERFERENCE
        if collision
        else CollisionClassification.POSITIVE_CLEARANCE
    )
    pair = CadKinematicCollisionPairResult(
        moving_instance_id=request.moving_instance_ids[0],
        stationary_instance_id=request.stationary_instance_ids[0],
        interference_volume_mm3=1.0 if collision else 0.0,
        exact_distance_mm=0.0 if collision else 5.0,
        classification=classification,
    )
    sample = CadKinematicSweepSample(
        angle_deg=0.0,
        transformed_assembly_hash=assembly_hash(
            transformed_assembly_program(
                kwargs["assembly"],
                kwargs["axis"],
                0.0,
                kwargs["moving_instance_ids"],
                kwargs["stationary_instance_ids"],
            )
        ),
        pair_results=(pair,),
        maximum_interference_volume_mm3=pair.interference_volume_mm3,
        minimum_exact_distance_mm=pair.exact_distance_mm,
        classification=classification,
    )
    return CadKinematicSweepResult.from_samples(request, (sample,))


def test_scope_equivalence_is_pure_and_reports_semantic_match():
    frozen = PrePromotionM10ScopeProjection(
        joint_semantic_key="joint-output",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        physical_pair_requirements=(
            {
                "requirement_key": "shaft-mount",
                "first_instance_id": "shaft-1",
                "first_interface_id": "output",
                "second_instance_id": "mount-1",
                "second_interface_id": "frame",
            },
        ),
        fidelity_requirements=(("shaft-1", "trusted_source_geometry"),),
        required_home_check_semantics=("home-check",),
        bounded_limitations=("internal motion is outside scope",),
    )
    derived = DerivedCanonicalM10Scope(
        project_id="PRJ-CAD",
        revision=2,
        state_hash="sha256:" + "a" * 64,
        mechanism_id="PM-1",
        mechanism_hash="sha256:" + "b" * 64,
        joint_semantic_key="joint-output",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        physical_pair_requirements=tuple(
            CanonicalPhysicalPairRequirement.model_validate(item.model_dump(mode="json"))
            for item in frozen.physical_pair_requirements
        ),
        fidelity_requirements=frozen.fidelity_requirements,
        required_home_check_semantics=frozen.required_home_check_semantics,
        bounded_limitations=frozen.bounded_limitations,
    )

    result = CanonicalM10ScopeEquivalenceService.compare(frozen, derived)

    assert result.equivalent is True
    assert result.revision == 2
    assert result.state_hash == derived.state_hash
    assert result.differences == ()


def test_execute_derives_fresh_canonical_pair_and_request_without_scope(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)
    calls = []

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            calls.append(kwargs)
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)

    assert outcome.status is CanonicalM10VerificationStatus.VERIFIED_CLEAR
    assert len(calls) == 1
    assert calls[0]["source_revision"] == reconstruction.revision
    assert calls[0]["source_state_hash"] == reconstruction.state_hash
    assert calls[0]["moving_instance_ids"] == (cad.mappings[0].cad_instance_id,)
    assert calls[0]["stationary_instance_ids"] == (cad.mappings[1].cad_instance_id,)
    assert outcome.inventory.expected_pair_universe == (
        tuple(sorted(mapping.cad_instance_id for mapping in cad.mappings)),
    )
    assert outcome.inventory.checked_pairs == (
        tuple(sorted(mapping.cad_instance_id for mapping in cad.mappings)),
    )
    assert outcome.request.request_hash != "sha256:" + "b" * 64
    assert outcome.request.revision == reconstruction.revision


@pytest.mark.parametrize(
    "status",
    (ContinuousSingleAxisProofStatus.COLLISION_WITNESS, ContinuousSingleAxisProofStatus.NOT_PROVEN),
)
def test_execute_preserves_collision_and_not_proven_statuses(tmp_path, status):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs, status)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)

    assert outcome.status.value == status.value
    assert outcome.pair_proofs[0].result.status is status


@pytest.mark.parametrize("collision", (False, True))
def test_execute_calls_home_entrypoint_and_binds_exact_home_result(tmp_path, collision):
    reconstruction, cad = _canonical_inputs(tmp_path, requires_home=True)
    calls = []

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

        def analyze_assembly_kinematics(self, **kwargs):
            calls.append(kwargs)
            return _home_result(kwargs, collision=collision)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)

    assert len(calls) == 1
    assert outcome.home_exact_checks[0].request.sample_angles_deg == (0.0,)
    assert outcome.home_exact_checks[0].request_hash == outcome.home_exact_checks[0].request.request_hash
    assert outcome.home_exact_checks[0].result_hash == outcome.home_exact_checks[0].result.result_hash
    assert outcome.status is (
        CanonicalM10VerificationStatus.COLLISION_WITNESS
        if collision
        else CanonicalM10VerificationStatus.VERIFIED_CLEAR
    )

    missing_home = outcome.model_dump(mode="json")
    missing_home["home_exact_checks"] = []
    missing_home["outcome_hash"] = "pending"
    with pytest.raises(ValueError, match="home checks"):
        type(outcome).model_validate(missing_home)


def test_frozen_scope_comparison_cannot_change_canonical_execution_or_reexecution(
    tmp_path, monkeypatch
):
    reconstruction, cad = _canonical_inputs(tmp_path)
    calls = []

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            calls.append(kwargs)
            return _proof_result(kwargs)

    service = CanonicalM10VerificationService(FakeApplication())
    first = service.execute(reconstruction, cad)
    frozen = PrePromotionM10ScopeProjection.model_validate({
        "joint_semantic_key": first.scope.joint_semantic_key,
        "angle_interval_deg": first.scope.angle_interval_deg,
        "path_semantics": first.scope.path_semantics,
        "required_clearance_mm": first.scope.required_clearance_mm,
        "physical_pair_requirements": [
            item.model_dump(mode="json") for item in first.scope.physical_pair_requirements
        ],
        "fidelity_requirements": [
            [key, fidelity.value] for key, fidelity in first.scope.fidelity_requirements
        ],
        "required_home_check_semantics": first.scope.required_home_check_semantics,
        "bounded_limitations": first.scope.bounded_limitations,
    })
    changed = frozen.model_copy(
        update={"required_clearance_mm": 99.0, "projection_hash": "pending"}
    )
    assert CanonicalM10ScopeEquivalenceService.compare(frozen, first.scope).equivalent
    assert not CanonicalM10ScopeEquivalenceService.compare(changed, first.scope).equivalent

    from test_m12_candidate_m10_binding import _binding, _realization, _scope
    from test_m12_candidate_m10_service import _request

    candidate_realization = _realization()
    candidate_binding = _binding(candidate_realization)
    candidate_request = _request(candidate_realization, candidate_binding, _scope())

    def forbidden_compare(*args, **kwargs):
        raise AssertionError("canonical reexecution must not compare pre-promotion scope")

    monkeypatch.setattr(
        CanonicalM10ScopeEquivalenceService,
        "compare",
        staticmethod(forbidden_compare),
    )
    del candidate_request, candidate_binding, candidate_realization, frozen, changed

    second = service.execute(reconstruction, cad)

    assert second.request == first.request
    assert second.inventory == first.inventory
    assert calls[0]["required_clearance_mm"] == calls[1]["required_clearance_mm"] == 1.0


def test_canonical_request_identity_is_fresh_even_when_candidate_scope_is_equivalent(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    canonical = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    from test_m12_candidate_m10_binding import _binding, _realization, _scope
    from test_m12_candidate_m10_service import _request

    realization = _realization()
    candidate_request = _request(realization, _binding(realization), _scope())

    candidate_scope = _scope()
    frozen_pairs = tuple(
        PromotionPhysicalPairRequirement(
            requirement_key=item.requirement_key,
            first_instance_id=item.first_constituent_key,
            first_interface_id="interface",
            second_instance_id=item.second_constituent_key,
            second_interface_id="interface",
            requires_home_exact_check=item.requires_home_exact_check,
        )
        for item in candidate_scope.pair_scope_requirements
        if item.required_classification.value == "check_clearance"
    )
    normalized_pairs = tuple(
        CanonicalPhysicalPairRequirement(
            requirement_key=item.requirement_key,
            first_instance_id=item.first_constituent_key,
            first_interface_id="interface",
            second_instance_id=item.second_constituent_key,
            second_interface_id="interface",
            requires_home_exact_check=item.requires_home_exact_check,
        )
        for item in candidate_scope.pair_scope_requirements
        if item.required_classification.value == "check_clearance"
    )
    frozen = PrePromotionM10ScopeProjection(
        joint_semantic_key=candidate_scope.output_joint_semantic_key,
        angle_interval_deg=candidate_scope.angle_interval_deg,
        required_clearance_mm=candidate_scope.required_clearance_mm,
        physical_pair_requirements=frozen_pairs,
        fidelity_requirements=tuple(
            (key, fidelity.value) for key, fidelity in candidate_scope.fidelity_requirements
        ),
        required_home_check_semantics=candidate_scope.required_home_check_semantics,
    )
    equivalent_scope = DerivedCanonicalM10Scope(
        project_id=reconstruction.project_id,
        revision=reconstruction.revision,
        state_hash=reconstruction.state_hash,
        mechanism_id=reconstruction.mechanism.id,
        mechanism_hash=reconstruction.mechanism.mechanism_hash,
        joint_semantic_key=frozen.joint_semantic_key,
        angle_interval_deg=frozen.angle_interval_deg,
        required_clearance_mm=frozen.required_clearance_mm,
        physical_pair_requirements=normalized_pairs,
        fidelity_requirements=tuple(
            (key, fidelity.value) for key, fidelity in candidate_scope.fidelity_requirements
        ),
        required_home_check_semantics=frozen.required_home_check_semantics,
    )

    assert CanonicalM10ScopeEquivalenceService.compare(frozen, equivalent_scope).equivalent
    assert canonical.request.request_hash != candidate_request.request_hash


def test_required_canonical_m10_hashes_reject_pending_and_mapping_hashes_are_validated(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    request_payload = outcome.request.model_dump(mode="json")
    request_payload["state_hash"] = "pending"
    request_payload["inventory"]["state_hash"] = "pending"
    request_payload["inventory"]["inventory_hash"] = "pending"
    request_payload["request_hash"] = "pending"
    with pytest.raises(ValueError, match="sha256"):
        type(outcome.request).model_validate(request_payload)

    mapping_payload = outcome.request.model_dump(mode="json")
    mapping_payload["mapping_hashes"] = ["not-a-hash"]
    mapping_payload["request_hash"] = "pending"
    with pytest.raises(ValueError, match="sha256"):
        type(outcome.request).model_validate(mapping_payload)


def test_outcome_requires_exact_nested_coverage_and_consistent_status(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)

    missing_proof = outcome.model_dump(mode="json")
    missing_proof["pair_proofs"] = []
    missing_proof["outcome_hash"] = "pending"
    with pytest.raises(ValueError, match="proof"):
        type(outcome).model_validate(missing_proof)

    inconsistent_status = outcome.model_dump(mode="json")
    inconsistent_status["status"] = ContinuousSingleAxisProofStatus.NOT_PROVEN.value
    inconsistent_status["outcome_hash"] = "pending"
    with pytest.raises(ValueError, match="status"):
        type(outcome).model_validate(inconsistent_status)


def test_outcome_binds_nested_mechanism_identity(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    payload = outcome.model_dump(mode="json")
    payload["scope"]["mechanism_id"] = "different-mechanism"
    payload["scope"]["scope_hash"] = "pending"
    payload["outcome_hash"] = "pending"
    with pytest.raises(ValueError, match="mechanism"):
        type(outcome).model_validate(payload)


def test_pair_proof_rejects_recomputed_embedded_request_partition_mismatch(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    proof = outcome.pair_proofs[0]
    request = ContinuousSingleAxisProofRequest.model_validate(
        proof.request.model_dump(mode="json")
        | {
            "moving_instance_ids": (proof.stationary_instance_id,),
            "stationary_instance_ids": (proof.moving_instance_id,),
            "request_hash": "pending",
        }
    )
    result = proof.result.model_copy(
        update={
            "request_hash": request.request_hash,
            "moving_instance_ids": request.moving_instance_ids,
            "stationary_instance_ids": request.stationary_instance_ids,
            "result_hash": "pending",
        }
    )
    result = result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(
                    result.model_dump(mode="json", exclude={"result_hash"}),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        }
    )

    with pytest.raises(ValueError, match="partition"):
        CanonicalM10PairProof(
            pair=proof.pair,
            moving_instance_id=proof.moving_instance_id,
            stationary_instance_id=proof.stationary_instance_id,
            request=request,
            result=result,
            request_hash=request.request_hash,
            result_hash=result.result_hash,
        )


def test_pair_proof_rejects_recomputed_embedded_result_partition_mismatch(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    proof = outcome.pair_proofs[0]
    result = proof.result.model_copy(
        update={
            "moving_instance_ids": proof.result.stationary_instance_ids,
            "stationary_instance_ids": proof.result.moving_instance_ids,
            "result_hash": "pending",
        }
    )
    result = result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(
                    result.model_dump(mode="json", exclude={"result_hash"}),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        }
    )

    with pytest.raises(ValueError, match="partition"):
        CanonicalM10PairProof(
            pair=proof.pair,
            moving_instance_id=proof.moving_instance_id,
            stationary_instance_id=proof.stationary_instance_id,
            request=proof.request,
            result=result,
            request_hash=proof.request_hash,
            result_hash=result.result_hash,
        )


def test_home_check_rejects_recomputed_embedded_partitions(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path, requires_home=True)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

        def analyze_assembly_kinematics(self, **kwargs):
            return _home_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    check = outcome.home_exact_checks[0]
    request = CadKinematicSweepRequest.model_validate(
        check.request.model_dump(mode="json")
        | {
            "moving_instance_ids": (check.stationary_instance_id,),
            "stationary_instance_ids": (check.moving_instance_id,),
            "request_hash": "pending",
        }
    )
    result = check.result.model_copy(
        update={
            "request_hash": request.request_hash,
            "samples": check.result.samples,
            "sweep_version": request.sweep_version,
            "result_hash": "pending",
        }
    )
    result = result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(
                    result.model_dump(mode="json", exclude={"result_hash"}),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        }
    )

    with pytest.raises(ValueError, match="partition"):
        CanonicalM10HomeExactCheck(
            pair=check.pair,
            moving_instance_id=check.moving_instance_id,
            stationary_instance_id=check.stationary_instance_id,
            request=request,
            result=result,
            request_hash=request.request_hash,
            result_hash=result.result_hash,
        )


def test_home_check_rejects_recomputed_embedded_result_partition_mismatch(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path, requires_home=True)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

        def analyze_assembly_kinematics(self, **kwargs):
            return _home_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    check = outcome.home_exact_checks[0]
    pair_result = check.result.samples[0].pair_results[0].model_copy(
        update={
            "moving_instance_id": check.stationary_instance_id,
            "stationary_instance_id": check.moving_instance_id,
        }
    )
    sample = check.result.samples[0].model_copy(update={"pair_results": (pair_result,)})
    result = check.result.model_copy(update={"samples": (sample,), "result_hash": "pending"})
    result = result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(
                    result.model_dump(mode="json", exclude={"result_hash"}),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        }
    )

    with pytest.raises(ValueError, match="partition"):
        CanonicalM10HomeExactCheck(
            pair=check.pair,
            moving_instance_id=check.moving_instance_id,
            stationary_instance_id=check.stationary_instance_id,
            request=check.request,
            result=result,
            request_hash=check.request_hash,
            result_hash=result.result_hash,
        )


def test_home_check_rejects_request_result_sweep_version_mismatch(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path, requires_home=True)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

        def analyze_assembly_kinematics(self, **kwargs):
            return _home_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    check = outcome.home_exact_checks[0]
    result = check.result.model_copy(
        update={"sweep_version": "foreign-sweep@9", "result_hash": "pending"}
    )
    result = result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(
                    result.model_dump(mode="json", exclude={"result_hash"}),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        }
    )

    with pytest.raises(ValueError, match="sweep version"):
        CanonicalM10HomeExactCheck(
            pair=check.pair,
            moving_instance_id=check.moving_instance_id,
            stationary_instance_id=check.stationary_instance_id,
            request=check.request,
            result=result,
            request_hash=check.request_hash,
            result_hash=result.result_hash,
        )


def test_outcome_rejects_recomputed_nested_pair_with_inner_partition_mismatch(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    proof = outcome.pair_proofs[0]
    request = ContinuousSingleAxisProofRequest.model_validate(
        proof.request.model_dump(mode="json")
        | {
            "moving_instance_ids": (proof.stationary_instance_id,),
            "stationary_instance_ids": (proof.moving_instance_id,),
            "request_hash": "pending",
        }
    )
    result = proof.result.model_copy(
        update={
            "request_hash": request.request_hash,
            "moving_instance_ids": request.moving_instance_ids,
            "stationary_instance_ids": request.stationary_instance_ids,
            "result_hash": "pending",
        }
    )
    result = result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(
                    result.model_dump(mode="json", exclude={"result_hash"}),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        }
    )
    payload = outcome.model_dump(mode="json")
    payload["pair_proofs"][0] = {
        **proof.model_dump(mode="json"),
        "request": request.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
        "request_hash": request.request_hash,
        "result_hash": result.result_hash,
        "proof_hash": "pending",
    }
    payload["outcome_hash"] = "pending"

    with pytest.raises(ValueError, match="partition"):
        type(outcome).model_validate(payload)


def test_outcome_rejects_preconstructed_nested_pair_partition_mismatch(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path, requires_home=True)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return _proof_result(kwargs)

        def analyze_assembly_kinematics(self, **kwargs):
            return _home_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(reconstruction, cad)
    proof = outcome.pair_proofs[0]
    forged_moving_id = "forged-moving-instance"
    forged_proof_request = proof.request.model_copy(
        update={"moving_instance_ids": (forged_moving_id,)}
    )
    forged_proof_result = proof.result.model_copy(
        update={"moving_instance_ids": (forged_moving_id,)}
    )
    forged_proof = CanonicalM10PairProof.model_construct(
        **{
            **proof.__dict__,
            "moving_instance_id": forged_moving_id,
            "request": forged_proof_request,
            "result": forged_proof_result,
        }
    )
    forged_proof_outcome = outcome.model_copy(
        update={"pair_proofs": (forged_proof,), "outcome_hash": "pending"}
    )
    with pytest.raises(ValueError, match="pair"):
        forged_proof_outcome.validate_outcome()

    check = outcome.home_exact_checks[0]
    forged_check_request = check.request.model_copy(
        update={"moving_instance_ids": (forged_moving_id,)}
    )
    forged_pair_result = check.result.samples[0].pair_results[0].model_copy(
        update={"moving_instance_id": forged_moving_id}
    )
    forged_sample = check.result.samples[0].model_copy(
        update={"pair_results": (forged_pair_result,)}
    )
    forged_check_result = check.result.model_copy(update={"samples": (forged_sample,)})
    forged_check = CanonicalM10HomeExactCheck.model_construct(
        **{
            **check.__dict__,
            "moving_instance_id": forged_moving_id,
            "request": forged_check_request,
            "result": forged_check_result,
        }
    )
    forged_check_outcome = outcome.model_copy(
        update={"home_exact_checks": (forged_check,), "outcome_hash": "pending"}
    )
    with pytest.raises(ValueError, match="pair"):
        forged_check_outcome.validate_outcome()


def test_scope_equivalence_result_requires_flag_to_match_differences():
    with pytest.raises(ValueError, match="equivalence flag"):
        CanonicalM10ScopeEquivalenceResult(
            project_id="PRJ",
            revision=1,
            state_hash="sha256:" + "a" * 64,
            frozen_projection_hash="sha256:" + "b" * 64,
            derived_scope_hash="sha256:" + "c" * 64,
            equivalent=True,
            differences=("required_clearance_mm",),
        )


def test_dispositions_follow_selected_topology_and_external_spur_boundary(tmp_path):
    reconstruction, _ = _canonical_inputs(tmp_path)
    mechanism = _topology_registry_mechanism(reconstruction.mechanism)
    specification_hash = mechanism.component_specifications[1].specification_hash
    components = (
        *mechanism.components,
        CanonicalPhysicalComponent(
            instance_id="driver-gear",
            specification_hash=specification_hash,
            role="transmission",
            interfaces=("gear",),
        ),
        CanonicalPhysicalComponent(
            instance_id="driven-gear",
            specification_hash=specification_hash,
            role="transmission",
            interfaces=("gear", "output"),
        ),
        CanonicalPhysicalComponent(
            instance_id="unrelated-rotor",
            specification_hash=specification_hash,
            role="rotating_member",
            interfaces=("rotor",),
        ),
    )
    connections = (
        *mechanism.connections,
        CanonicalMechanicalConnection(
            connection_id="gear-mesh",
            kind=CanonicalMechanicalConnectionKind.GEAR_MESH,
            from_instance_id="driver-gear",
            from_interface_id="gear",
            to_instance_id="driven-gear",
            to_interface_id="gear",
            meanings=(CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
        ),
        CanonicalMechanicalConnection(
            connection_id="gear-output",
            kind=CanonicalMechanicalConnectionKind.ROTATIONAL_DRIVE,
            from_instance_id="driven-gear",
            from_interface_id="output",
            to_instance_id="shaft-1",
            to_interface_id="output",
            meanings=(CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
        ),
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="python")
        | {"components": components, "connections": connections, "mechanism_hash": "pending"}
    )
    binding = mechanism.joint_bindings[0]
    dispositions = CanonicalM10VerificationService._derive_dispositions(mechanism, binding)
    by_id = {item.physical_instance_id: item for item in dispositions}

    assert by_id["shaft-1"].disposition.value == "output_rigid"
    assert by_id["driven-gear"].disposition.value == "output_rigid"
    assert by_id["driver-gear"].disposition.value == "internal_motion_unmodeled"
    assert by_id["unrelated-rotor"].disposition.value == "fixed"
    assert sum(
        connection.kind is CanonicalMechanicalConnectionKind.GEAR_MESH
        for connection in mechanism.connections
    ) == 1


def test_external_spur_gear_mesh_cannot_become_a_canonical_clearance_requirement(tmp_path):
    reconstruction, _ = _canonical_inputs(tmp_path)
    mechanism = _topology_registry_mechanism(reconstruction.mechanism)
    specification_hash = mechanism.component_specifications[1].specification_hash
    components = (
        *mechanism.components,
        CanonicalPhysicalComponent(
            instance_id="driver-gear",
            specification_hash=specification_hash,
            role="transmission",
            interfaces=("gear",),
        ),
        CanonicalPhysicalComponent(
            instance_id="driven-gear",
            specification_hash=specification_hash,
            role="transmission",
            interfaces=("gear", "output"),
        ),
    )
    gear_connections = (
        CanonicalMechanicalConnection(
            connection_id="gear-mesh",
            kind=CanonicalMechanicalConnectionKind.GEAR_MESH,
            from_instance_id="driver-gear",
            from_interface_id="gear",
            to_instance_id="driven-gear",
            to_interface_id="gear",
            meanings=(CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
        ),
        CanonicalMechanicalConnection(
            connection_id="gear-output",
            kind=CanonicalMechanicalConnectionKind.ROTATIONAL_DRIVE,
            from_instance_id="driven-gear",
            from_interface_id="output",
            to_instance_id="shaft-1",
            to_interface_id="output",
            meanings=(CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT,),
        ),
    )
    base_obligation = mechanism.m10_obligations[0]
    gear_requirement = CanonicalPhysicalPairRequirement(
        requirement_key="gear-clearance",
        first_instance_id="driver-gear",
        first_interface_id="gear",
        second_instance_id="driven-gear",
        second_interface_id="gear",
        requires_home_exact_check=True,
    )
    obligation = type(base_obligation).model_validate(
        base_obligation.model_dump(mode="python")
        | {
            "physical_pair_requirements": (
                *base_obligation.physical_pair_requirements,
                gear_requirement,
            ),
            "obligation_hash": "pending",
        }
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        mechanism.model_dump(mode="python")
        | {
            "components": components,
            "connections": (*mechanism.connections, *gear_connections),
            "m10_obligations": (obligation,),
            "mechanism_hash": "pending",
        }
    )
    binding = mechanism.joint_bindings[0]
    dispositions = CanonicalM10VerificationService._derive_dispositions(mechanism, binding)
    scope = DerivedCanonicalM10Scope(
        project_id=reconstruction.project_id,
        revision=reconstruction.revision,
        state_hash=reconstruction.state_hash,
        mechanism_id=mechanism.id,
        mechanism_hash=mechanism.mechanism_hash,
        joint_semantic_key=obligation.joint_semantic_key,
        angle_interval_deg=obligation.angle_interval_deg,
        required_clearance_mm=obligation.required_clearance_mm,
        physical_pair_requirements=obligation.physical_pair_requirements,
        fidelity_requirements=obligation.fidelity_requirements,
        required_home_check_semantics=obligation.required_home_check_semantics,
        bounded_limitations=obligation.bounded_limitations,
    )
    fake_reconstruction = SimpleNamespace(
        project_id=reconstruction.project_id,
        revision=reconstruction.revision,
        state_hash=reconstruction.state_hash,
        mechanism=mechanism,
    )
    fake_cad = SimpleNamespace(
        realization_hash="sha256:" + "d" * 64,
        mappings=tuple(
            SimpleNamespace(
                physical_instance_id=component.instance_id,
                cad_instance_id=f"cad-{component.instance_id}",
            )
            for component in mechanism.components
        ),
    )

    with pytest.raises(ValueError, match="gear mesh"):
        CanonicalM10VerificationService._derive_inventory(
            fake_reconstruction,
            fake_cad,
            obligation,
            dispositions,
            scope,
        )


def test_joint_semantic_drift_fails_before_m10_entrypoint(tmp_path):
    reconstruction, cad = _canonical_inputs(tmp_path)
    binding = reconstruction.mechanism.joint_bindings[0]
    drifted = binding.model_copy(
        update={
            "expected_parent_instance_id": "shaft-1",
            "expected_child_instance_id": "mount-1",
            "binding_hash": "pending",
        }
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        reconstruction.mechanism.model_dump(mode="python")
        | {"joint_bindings": (drifted,), "mechanism_hash": "pending"}
    )
    projection = PromotableMechanismProjection(
        canonical_target_mechanism_id=mechanism.id,
        canonical_instance_ids=tuple(item.instance_id for item in mechanism.components),
        component_specifications=mechanism.component_specifications,
        components=mechanism.components,
        accepted_design_choices=mechanism.accepted_design_choices,
        placements=mechanism.placements,
        connections=mechanism.connections,
        joint_bindings=mechanism.joint_bindings,
        m10_obligations=mechanism.m10_obligations,
        mapping_identities=tuple(item.instance_id for item in mechanism.components),
    )
    drifted_reconstruction = reconstruction.model_copy(
        update={"canonical_mechanism": mechanism, "normalized_projection_hash": projection.projection_hash}
    )
    with pytest.raises(ValueError, match="semantic|joint"):
        CanonicalM10VerificationService(object()).execute(drifted_reconstruction, cad)
