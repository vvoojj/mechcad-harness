from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.cad_assembly import assembly_hash
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
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CadKinematicSweepSample,
    CollisionClassification,
    transformed_assembly_program,
)
from mechcad_harness.candidates import (
    CandidateGeometryFidelity,
    CandidateM10PairClassification,
    CandidateM10PairScopeRequirement,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationService,
    CandidateM10StageOutcome,
    CandidateM10StageStatus,
)
from mechcad_harness.candidates.m10_evaluation import (
    CandidateCollisionPairInventory,
)

from test_m12_candidate_m10_binding import _binding, _inventory, _realization, _scope


def _continuous_result(kwargs, status=ContinuousSingleAxisProofStatus.VERIFIED_CLEAR):
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
    certificates = ()
    if status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR:
        pair = ContinuousPairCertificate(
            moving_instance_id=kwargs["moving_instance_ids"][0],
            stationary_instance_id=kwargs["stationary_instance_ids"][0],
            exact_distance_mm=10.0,
            radial_bound_mm=1.0,
            angular_motion_bound_mm=0.1,
            certified_lower_clearance_mm=9.9,
        )
        certificates = (ContinuousIntervalCertificate(
            interval_start_deg=request.start_angle_deg,
            interval_end_deg=request.end_angle_deg,
            reference_angle_deg=0.0,
            pair_certificates=(pair,),
            minimum_certified_lower_clearance_mm=9.9,
        ),)
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
        certified_leaf_certificates=certificates,
        unresolved_intervals=() if certificates else ((request.start_angle_deg, request.end_angle_deg),),
        exact_evaluations_count=1,
        maximum_depth_reached=0,
    )
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    return result.model_copy(update={
        "result_hash": "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    })


def _home_result(kwargs, *, collision=False):
    request = CadKinematicSweepRequest(
        source_assembly_id=kwargs["assembly"].assembly_id,
        source_assembly_hash=assembly_hash(kwargs["assembly"]),
        axis=kwargs["axis"],
        sample_angles_deg=(0.0,),
        moving_instance_ids=kwargs["moving_instance_ids"],
        stationary_instance_ids=kwargs["stationary_instance_ids"],
    )
    classification = CollisionClassification.INTERFERENCE if collision else CollisionClassification.POSITIVE_CLEARANCE
    # Build the pair result without relying on a provider implementation.
    from mechcad_harness.kinematic_sweep import CadKinematicCollisionPairResult
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
        pair_results=(CadKinematicCollisionPairResult(
            moving_instance_id=request.moving_instance_ids[0],
            stationary_instance_id=request.stationary_instance_ids[0],
            interference_volume_mm3=1.0 if collision else 0.0,
            exact_distance_mm=0.0 if collision else 5.0,
            classification=classification,
        ),),
        maximum_interference_volume_mm3=1.0 if collision else 0.0,
        minimum_exact_distance_mm=0.0 if collision else 5.0,
        classification=classification,
    )
    return CadKinematicSweepResult.from_samples(request, (sample,))


def _request(realization, binding, scope):
    inventory = _inventory(realization, binding, scope)
    return CandidateM10EvaluationRequest(
        candidate_hash=realization.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization.mappings)),
        inventory=inventory,
    )


def _rehash_result(result):
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    return result.model_copy(update={
        "result_hash": "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    })


def test_evaluate_calls_continuous_m10_once_per_checked_pair_with_induced_assembly():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)
    continuous_calls = []
    home_calls = []
    continuous_results = []
    home_results = []

    def prove(**kwargs):
        continuous_calls.append(kwargs)
        result = _continuous_result(kwargs)
        continuous_results.append(result)
        return result

    def home(**kwargs):
        home_calls.append(kwargs)
        result = _home_result(kwargs)
        home_results.append(result)
        return result

    outcome = CandidateM10EvaluationService(
        prove_continuous_single_axis_clearance=prove,
        analyze_assembly_kinematics=home,
        scope=scope,
    ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)

    assert outcome.status is CandidateM10StageStatus.UNRESOLVED
    assert len(continuous_calls) == 1
    assert len(home_calls) == 1
    assert len(continuous_calls[0]["assembly"].instances) == 2
    assert {item.instance_id for item in continuous_calls[0]["assembly"].instances} == {"cad-hub", "cad-mount"}
    assert [item.placement for item in continuous_calls[0]["assembly"].instances] == [
        item.placement for item in realization.assembly.instances if item.instance_id in {"cad-hub", "cad-mount"}
    ]
    assert len(outcome.pair_proofs) == 1
    assert outcome.pair_proofs[0].request_hash == continuous_results[0].request_hash
    assert outcome.pair_proofs[0].result_hash == outcome.pair_proofs[0].result.result_hash
    assert outcome.home_exact_checks[0].result_hash == home_results[0].result_hash
    assert outcome.home_exact_checks[0].result.aggregate_classification.value == "collision_free"


def test_not_proven_is_successful_m10_execution_and_is_retained_exactly():
    realization = _realization()
    binding = _binding(realization, driver_gear_constituent_key=None)
    scope = type(_scope()).model_validate(_scope().model_dump(mode="python") | {
        "pair_scope_requirements": (_scope().pair_scope_requirements[0],),
        "scope_hash": "pending",
    })
    request = _request(realization, binding, scope)

    def prove(**kwargs):
        return _continuous_result(kwargs, ContinuousSingleAxisProofStatus.NOT_PROVEN)

    outcome = CandidateM10EvaluationService(prove, lambda **kwargs: pytest.fail("home check not required"), scope=scope).evaluate(
        1, "sha256:" + "a" * 64, realization, binding, request
    )

    assert outcome.status is CandidateM10StageStatus.SUCCESS
    assert outcome.pair_proofs[0].result.status is ContinuousSingleAxisProofStatus.NOT_PROVEN


def test_continuous_result_axis_and_certificate_pairs_are_revalidated():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    def prove(**kwargs):
        result = _continuous_result(kwargs)
        certificate = result.certified_leaf_certificates[0]
        pair = certificate.pair_certificates[0].model_copy(
            update={"moving_instance_id": "cad-not-in-request"}
        )
        return _rehash_result(result.model_copy(update={
            "axis": kwargs["axis"].model_copy(update={"origin_x_mm": 21.0}),
            "certified_leaf_certificates": (
                certificate.model_copy(update={"pair_certificates": (pair,)}),
            ),
        }))

    with pytest.raises(ValueError, match="axis|certificate|pair"):
        CandidateM10EvaluationService(prove, lambda **kwargs: _home_result(kwargs), scope=scope).evaluate(
            1, "sha256:" + "a" * 64, realization, binding, request
        )


def test_scope_rejects_untrusted_continuous_proof_service_version():
    base = _scope()
    with pytest.raises(ValueError, match="proof.*version|service"):
        type(base).model_validate(
            base.model_dump(mode="python")
            | {"proof_service_version": "untrusted-proof-service@99", "scope_hash": "pending"}
        )


def test_continuous_result_algorithm_version_must_match_declared_m10_scope():
    realization = _realization()
    binding = _binding(realization, driver_gear_constituent_key=None)
    base_scope = _scope()
    scope = type(base_scope).model_validate(
        base_scope.model_dump(mode="python")
        | {"pair_scope_requirements": (base_scope.pair_scope_requirements[0],), "scope_hash": "pending"}
    )
    request = _request(realization, binding, scope)

    def prove(**kwargs):
        return _rehash_result(_continuous_result(kwargs).model_copy(
            update={"proof_algorithm_version": "untrusted-proof-algorithm@99"}
        ))

    with pytest.raises(ValueError, match="algorithm"):
        CandidateM10EvaluationService(
            prove, lambda **kwargs: pytest.fail("home check not required"), scope=scope
        ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)


def test_home_result_zero_angle_hash_must_match_induced_transformed_assembly():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    def home(**kwargs):
        result = _home_result(kwargs)
        sample = result.samples[0].model_copy(
            update={"transformed_assembly_hash": "sha256:" + "f" * 64}
        )
        return _rehash_result(result.model_copy(update={"samples": (sample,)}))

    with pytest.raises(ValueError, match="transformed.*assembly|assembly"):
        CandidateM10EvaluationService(
            lambda **kwargs: _continuous_result(kwargs), home, scope=scope
        ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)


def test_home_result_requires_the_accepted_discrete_sweep_identity():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    def home(**kwargs):
        result = _home_result(kwargs)
        return _rehash_result(result.model_copy(update={"sweep_version": "foreign-sweep@9"}))

    with pytest.raises(ValueError, match="sweep|service|version"):
        CandidateM10EvaluationService(
            lambda **kwargs: _continuous_result(kwargs), home, scope=scope
        ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)


@pytest.mark.parametrize("field", ("start_angle_deg", "end_angle_deg", "required_clearance_mm", "moving_instance_ids"))
def test_continuous_result_rejects_path_clearance_and_pair_replay(field):
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    def prove(**kwargs):
        result = _continuous_result(kwargs)
        replacement = {
            "start_angle_deg": kwargs["start_angle_deg"] + 1.0,
            "end_angle_deg": kwargs["end_angle_deg"] - 1.0,
            "required_clearance_mm": kwargs["required_clearance_mm"] + 1.0,
            "moving_instance_ids": ("cad-not-in-request",),
        }[field]
        return _rehash_result(result.model_copy(update={field: replacement}))

    with pytest.raises(ValueError, match="path|clearance|partition|moving"):
        CandidateM10EvaluationService(prove, lambda **kwargs: _home_result(kwargs), scope=scope).evaluate(
            1, "sha256:" + "a" * 64, realization, binding, request
        )


def test_collision_witness_must_bind_to_one_requested_pair():
    realization = _realization()
    binding = _binding(realization, driver_gear_constituent_key=None)
    scope = type(_scope()).model_validate(_scope().model_dump(mode="python") | {
        "pair_scope_requirements": (_scope().pair_scope_requirements[0],),
        "scope_hash": "pending",
    })
    request = _request(realization, binding, scope)

    def prove(**kwargs):
        result = _continuous_result(kwargs, ContinuousSingleAxisProofStatus.COLLISION_WITNESS)
        return _rehash_result(result.model_copy(update={
            "collision_witness": ContinuousCollisionWitness(
                witness_angle_deg=0.0,
                moving_instance_id="cad-not-in-request",
                stationary_instance_id=kwargs["stationary_instance_ids"][0],
                interference_volume_mm3=1.0,
                exact_distance_mm=0.0,
                classification="interference",
            ),
        }))

    with pytest.raises(ValueError, match="witness|pair|instance"):
        CandidateM10EvaluationService(prove, lambda **kwargs: pytest.fail("home check not required"), scope=scope).evaluate(
            1, "sha256:" + "a" * 64, realization, binding, request
        )


def test_exact_home_collision_is_retained_and_classified():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    outcome = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs),
        lambda **kwargs: _home_result(kwargs, collision=True),
        scope=scope,
    ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)

    assert outcome.status is CandidateM10StageStatus.UNRESOLVED
    assert outcome.home_exact_checks[0].result.aggregate_classification.value == "collision_present"
    assert outcome.home_exact_checks[0].result.samples[0].pair_results[0].classification.value == "interference"


def test_home_result_requires_one_zero_angle_sample_and_exact_pair_ids():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    def home(**kwargs):
        result = _home_result(kwargs)
        sample = result.samples[0]
        forged_pair = sample.pair_results[0].model_copy(update={"moving_instance_id": "cad-not-in-request"})
        forged_sample = sample.model_copy(update={"pair_results": (forged_pair,)})
        return _rehash_result(result.model_copy(update={
            "samples": (sample, forged_sample.model_copy(update={"angle_deg": 1.0})),
        }))

    with pytest.raises(ValueError, match="home|sample|pair"):
        CandidateM10EvaluationService(
            lambda **kwargs: _continuous_result(kwargs), home, scope=scope
        ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)


def test_home_result_rejects_replayed_collision_classification():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)

    def home(**kwargs):
        result = _home_result(kwargs, collision=True)
        sample = result.samples[0]
        forged_pair = sample.pair_results[0].model_copy(
            update={"classification": CollisionClassification.POSITIVE_CLEARANCE}
        )
        return _rehash_result(result.model_copy(update={
            "samples": (sample.model_copy(update={"pair_results": (forged_pair,)}),),
        }))

    with pytest.raises(ValueError, match="classification"):
        CandidateM10EvaluationService(
            lambda **kwargs: _continuous_result(kwargs), home, scope=scope
        ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)


def test_multiple_checked_pairs_are_each_evaluated():
    realization = _realization()
    binding = _binding(realization)
    base_scope = _scope()
    scope = type(base_scope).model_validate(base_scope.model_dump(mode="python") | {
        "pair_scope_requirements": base_scope.pair_scope_requirements + (
            CandidateM10PairScopeRequirement(
                requirement_key="body-mount-clearance",
                first_constituent_key="body",
                second_constituent_key="mount",
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
        ),
        "fidelity_requirements": base_scope.fidelity_requirements + (
            ("body", CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
        ),
        "scope_hash": "pending",
    })
    request = _request(realization, binding, scope)
    calls = []

    def prove(**kwargs):
        calls.append(kwargs)
        return _continuous_result(kwargs)

    outcome = CandidateM10EvaluationService(
        prove, lambda **kwargs: _home_result(kwargs), scope=scope
    ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)

    assert outcome.status is CandidateM10StageStatus.UNRESOLVED
    assert len(calls) == 2
    assert {frozenset(instance.instance_id for instance in call["assembly"].instances) for call in calls} == {
        frozenset({"cad-hub", "cad-mount"}),
        frozenset({"cad-body", "cad-mount"}),
    }


def test_operational_m10_exception_propagates():
    realization = _realization()
    binding = _binding(realization, driver_gear_constituent_key=None)
    scope = type(_scope()).model_validate(_scope().model_dump(mode="python") | {
        "pair_scope_requirements": (_scope().pair_scope_requirements[0],),
        "scope_hash": "pending",
    })
    request = _request(realization, binding, scope)

    def prove(**kwargs):
        raise RuntimeError("CAD backend unavailable")

    with pytest.raises(RuntimeError, match="CAD backend unavailable"):
        CandidateM10EvaluationService(prove, lambda **kwargs: pytest.fail("home check not required"), scope=scope).evaluate(
            1, "sha256:" + "a" * 64, realization, binding, request
        )


def test_not_reached_requires_absent_cad_identity_and_m10_payloads():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    request = _request(realization, binding, scope)
    from mechcad_harness.candidates.cad_realization import CandidateCadStageOutcome as CadOutcome
    from mechcad_harness.candidates.cad_realization import CandidateCadStageReason, CandidateCadStageStatus

    prior = CadOutcome(status=CandidateCadStageStatus.NOT_REACHED, reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,))
    baseline = CandidateM10EvaluationService(lambda **kwargs: None, lambda **kwargs: None, scope=scope).evaluate(
        1, "sha256:" + "a" * 64, prior, binding, request
    )
    with pytest.raises(ValueError, match="realization|CAD"):
        CandidateM10StageOutcome.model_validate(
            baseline.model_dump(mode="python")
            | {"cad_realization_hash": realization.realization_hash, "outcome_hash": "pending"}
        )


def test_completed_m10_stage_requires_cad_identity():
    realization = _realization()
    binding = _binding(realization, driver_gear_constituent_key=None)
    base_scope = _scope()
    scope = type(base_scope).model_validate(base_scope.model_dump(mode="python") | {
        "pair_scope_requirements": (base_scope.pair_scope_requirements[0],),
        "scope_hash": "pending",
    })
    request = _request(realization, binding, scope)
    outcome = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs, ContinuousSingleAxisProofStatus.NOT_PROVEN),
        lambda **kwargs: pytest.fail("home check not required"),
        scope=scope,
    ).evaluate(1, "sha256:" + "a" * 64, realization, binding, request)

    with pytest.raises(ValueError, match="realization|CAD"):
        CandidateM10StageOutcome.model_validate(
            outcome.model_dump(mode="python")
            | {"cad_realization_hash": None, "outcome_hash": "pending"}
        )
