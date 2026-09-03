from __future__ import annotations

import hashlib
import json

import pytest

from mechcad_harness.candidates import (
    CandidateCadRealizationRequest,
    CandidateCadRealization,
    CandidateCadStageOutcome,
    CandidateCadStageReason,
    CandidateCadStageStatus,
    CandidateGeometryFidelity,
    CandidateEvaluation,
    CandidateEvaluationCurrentnessService,
    CandidateEvaluationOutcome,
    CandidateEvaluationPolicy,
    CandidateEvaluationService,
    CandidateCurrentness,
    CandidateMetricKey,
    CandidateM10StageOutcome,
    CandidateM10StageStatus,
    CandidateM10EvaluationRequest,
    CandidateIntegrityError,
)
from mechcad_harness.cad_assembly import assembly_hash
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.candidates.m10_evaluation import CandidateM10StageReason
from mechcad_harness.candidates.models import (
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalMechanismRealization,
    PhysicalComponentRole,
)
from mechcad_harness.revolute_drive import (
    DriveAdmissibility,
    EngineeringCheck,
    EngineeringCheckStatus,
    RevoluteDriveAdmissibilityResult,
    admissibility_result_hash,
)
from mechcad_harness.state import StateManager
from mechcad_harness.state.hashing import canonical_json

from test_m12_candidate_foundation import _candidate, _state, _source
from test_m12_candidate_m10_binding import _binding, _realization, _scope
from test_m12_candidate_m10_service import _request, _continuous_result, _home_result
from mechcad_harness.candidates import CandidateM10EvaluationService
from mechcad_harness.continuous_proof import ContinuousCollisionWitness, ContinuousSingleAxisProofStatus


class _CurrentnessVerifier:
    def evaluate(self, candidate, synthesis_request, synthesis_policy):
        return CandidateCurrentness.CURRENT


def _evaluation_service():
    return CandidateEvaluationService(currentness_verifier=_CurrentnessVerifier())


def _hash(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _m12_result(candidate, status: EngineeringCheckStatus = EngineeringCheckStatus.SATISFIED):
    result = RevoluteDriveAdmissibilityResult(
        candidate_hash=candidate.candidate_hash,
        source_binding_hash=_hash(candidate.source_binding.model_dump(mode="json")),
        synthesis_request_hash=candidate.synthesis_request_hash,
        synthesis_policy_hash=candidate.synthesis_policy_hash,
        requirements_hash="sha256:" + "a" * 64,
        checks=(EngineeringCheck(check_id="required-drive", status=status, reason="fixture" if status is not EngineeringCheckStatus.SATISFIED else None),),
    )
    return RevoluteDriveAdmissibilityResult.model_validate(result.model_dump(mode="json"))


def _evaluation_candidate(state=None):
    base, _, synthesis_policy = _candidate(state)
    specifications = {spec.source_identity: spec for spec in base.component_specifications}
    motor = specifications["datasheet:example:MTR-24-100@1"]
    bearing = specifications["catalog:bearing@1"]
    components = (
        PhysicalComponentInstance(instance_id="motor", specification_hash=motor.specification_hash, role=PhysicalComponentRole.ACTUATOR, interfaces=motor.interfaces),
        PhysicalComponentInstance(instance_id="driver", specification_hash=motor.specification_hash, role=PhysicalComponentRole.TRANSMISSION, interfaces=motor.interfaces),
        PhysicalComponentInstance(instance_id="shaft", specification_hash=specifications["custom:shaft@1"].specification_hash, role=PhysicalComponentRole.SHAFT, interfaces=specifications["custom:shaft@1"].interfaces),
        PhysicalComponentInstance(instance_id="bearing", specification_hash=bearing.specification_hash, role=PhysicalComponentRole.BEARING, interfaces=bearing.interfaces),
        PhysicalComponentInstance(instance_id="hub", specification_hash=specifications["custom:hub@1"].specification_hash, role=PhysicalComponentRole.HUB_OR_COUPLING, interfaces=specifications["custom:hub@1"].interfaces),
        PhysicalComponentInstance(instance_id="mount", specification_hash=specifications["custom:mount@1"].specification_hash, role=PhysicalComponentRole.MOUNT_OR_SUPPORT, interfaces=specifications["custom:mount@1"].interfaces),
        PhysicalComponentInstance(instance_id="body", specification_hash=specifications["custom:body@1"].specification_hash, role=PhysicalComponentRole.DRIVEN_BODY, interfaces=specifications["custom:body@1"].interfaces),
    )
    realization = PhysicalMechanismRealization(components=components)
    synthesis_request = type(_candidate(state)[1])(source_binding=base.source_binding)
    candidate = MechanicalDesignCandidate(
        source_binding=base.source_binding,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=synthesis_policy.policy_hash,
        component_specifications=base.component_specifications,
        realization=realization,
        generator_identity=base.generator_identity,
        generator_version=base.generator_version,
    )
    return candidate, synthesis_request, synthesis_policy


def _bound_m10_inputs(candidate, *, trusted_source_artifact=None):
    base_realization = _realization()
    mappings = tuple(
        mapping.model_copy(update={"candidate_hash": candidate.candidate_hash, "mapping_hash": "pending"})
        for mapping in base_realization.mappings
    )
    realization = base_realization.model_copy(update={
        "candidate_hash": candidate.candidate_hash,
        "mappings": mappings,
        "realization_hash": "pending",
    })
    if trusted_source_artifact is not None:
        specifications = {
            specification.specification_hash: specification
            for specification in candidate.component_specifications
        }
        components = {
            component.instance_id: component for component in candidate.realization.components
        }
        imported_components = []
        trusted_part_ids = set()
        trusted_mappings = []
        for mapping in realization.mappings:
            specification = specifications[components[mapping.physical_instance_id].specification_hash]
            source = specification.geometry_source
            if source is None:
                trusted_mappings.append(mapping)
                continue
            if (source.artifact_id, source.artifact_hash) != (
                trusted_source_artifact.artifact_id,
                trusted_source_artifact.sha256,
            ):
                raise AssertionError("trusted fixture artifact does not match source geometry")
            part_id = next(
                instance.part_id
                for instance in realization.assembly.instances
                if instance.instance_id == mapping.cad_instance_id
            )
            imported = ImportedCadComponent(
                component_id=part_id,
                artifact_id=trusted_source_artifact.artifact_id,
                artifact_hash=trusted_source_artifact.sha256,
                source_revision=trusted_source_artifact.bound_revision,
                source_state_hash=trusted_source_artifact.bound_state_hash,
            )
            imported_components.append(imported)
            trusted_part_ids.add(part_id)
            trusted_mappings.append(
                mapping.model_copy(
                    update={
                        "fidelity": CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
                        "representation_identity": imported_component_hash(imported),
                        "source_geometry_identity": trusted_source_artifact.sha256,
                        "geometry_definition_identities": (trusted_source_artifact.artifact_id,),
                        "mapping_hash": "pending",
                    }
                )
            )
        assembly = realization.assembly.model_copy(
            update={
                "parts": tuple(
                    part
                    for part in realization.assembly.parts
                    if part.part_id not in trusted_part_ids
                ),
                "imported_components": tuple(imported_components),
            }
        )
        realization = realization.model_copy(
            update={
                "mappings": tuple(trusted_mappings),
                "assembly": assembly,
                "assembly_hash": assembly_hash(assembly),
                "realization_hash": "pending",
            }
        )
    from mechcad_harness.candidates.cad_realization import CandidateCadRealization

    cad_request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-evaluation-fixture@1",
        compiler_identity="fixture",
        compiler_version="1",
        candidate_instance_ids=tuple(mapping.physical_instance_id for mapping in realization.mappings),
        mappings=realization.mappings,
    )
    cad_realization = CandidateCadRealization(
        candidate_hash=candidate.candidate_hash,
        request_hash=cad_request.request_hash,
        mappings=realization.mappings,
        assembly=realization.assembly,
        assembly_hash=realization.assembly_hash,
        verified_source_content_identities=(
            (trusted_source_artifact.sha256,)
            if trusted_source_artifact is not None
            else ()
        ),
        compiler_identity="fixture",
        compiler_version="1",
        provider_identity="fixture",
    )
    binding = _binding(cad_realization, driver_gear_constituent_key=None)
    base_scope = _scope()
    scope = type(base_scope).model_validate(base_scope.model_dump(mode="python") | {
        "pair_scope_requirements": (_scope().pair_scope_requirements[0],),
        "scope_hash": "pending",
    })
    request = _request(cad_realization, binding, scope)
    m10 = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs),
        lambda **kwargs: pytest.fail("home check not required"),
        scope=scope,
    ).evaluate(1, candidate.source_binding.source_state_hash, cad_realization, binding, request)
    cad = CandidateCadStageOutcome(status=CandidateCadStageStatus.SUCCESS, realization=cad_realization)
    return cad, m10, scope, binding, request, cad_request


def test_admissible_candidate_with_clear_cad_and_verified_m10_is_feasible_and_uses_certificate_metric():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    policy = CandidateEvaluationPolicy()

    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        m10,
        policy,
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )

    assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert evaluation.metrics[0].key is CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM
    assert evaluation.metrics[0].unit == "mm"
    assert evaluation.metrics[0].value == pytest.approx(9.9)
    assert evaluation.m10_stage_outcome_hash == m10.outcome_hash
    assert evaluation.evaluation_scope_hash == scope.scope_hash


def test_not_proven_is_unresolved_and_exact_stage_identity_is_retained():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    proof = m10.pair_proofs[0].result
    not_proven = proof.model_copy(update={
        "status": ContinuousSingleAxisProofStatus.NOT_PROVEN,
        "certified_leaf_certificates": (),
        "unresolved_intervals": ((proof.start_angle_deg, proof.end_angle_deg),),
    })
    payload = not_proven.model_dump(mode="json", exclude={"result_hash"})
    not_proven = not_proven.model_copy(update={
        "result_hash": "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    })
    m10 = m10.model_copy(update={
        "pair_proofs": (m10.pair_proofs[0].model_copy(update={"result": not_proven, "result_hash": not_proven.result_hash, "proof_hash": "pending"}),),
        "outcome_hash": "pending",
    })
    m10 = CandidateM10StageOutcome.model_validate(m10.model_dump(mode="json"))
    evaluation = _evaluation_service().evaluate(
        candidate, synthesis_request, synthesis_policy, _m12_result(candidate), cad, m10, CandidateEvaluationPolicy(),
        cad_request=cad_request, m10_request=m10_request, m10_scope=scope, m10_binding=binding,
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert evaluation.metrics == ()
    assert evaluation.m10_stage_outcome_hash == m10.outcome_hash


def test_unresolved_cad_does_not_fabricate_cad_or_m10_realization_identities():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.UNRESOLVED,
        reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
    )
    m10 = CandidateM10StageOutcome(
        status=CandidateM10StageStatus.NOT_REACHED,
        candidate_hash=candidate.candidate_hash,
        source_revision=1,
        source_state_hash=candidate.source_binding.source_state_hash,
        reasons=(CandidateM10StageReason.PRIOR_STAGE_FAILED,),
    )
    evaluation = _evaluation_service().evaluate(
        candidate, synthesis_request, synthesis_policy, _m12_result(candidate), cad, m10, CandidateEvaluationPolicy()
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert evaluation.cad_realization_hash is None
    assert evaluation.m10_request_hashes == ()
    assert evaluation.m10_result_hashes == ()


def test_not_reached_evaluation_rejects_arbitrary_m10_stage_identities():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.UNRESOLVED,
        reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
    )
    with pytest.raises(ValueError, match="identity|context|not-reached"):
        CandidateM10StageOutcome(
            status=CandidateM10StageStatus.NOT_REACHED,
            candidate_hash=candidate.candidate_hash,
            binding_hash="sha256:" + "b" * 64,
            scope_hash="sha256:" + "c" * 64,
            evaluation_request_hash="sha256:" + "d" * 64,
            source_revision=1,
            source_state_hash=candidate.source_binding.source_state_hash,
            reasons=(CandidateM10StageReason.PRIOR_STAGE_FAILED,),
        )


def test_hard_m12_witness_precedes_unresolved_later_stages():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad = CandidateCadStageOutcome(status=CandidateCadStageStatus.NOT_REACHED, reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,))
    m10 = CandidateM10StageOutcome(
        status=CandidateM10StageStatus.NOT_REACHED,
        candidate_hash=candidate.candidate_hash,
        source_revision=1,
        source_state_hash=candidate.source_binding.source_state_hash,
        reasons=(CandidateM10StageReason.PRIOR_STAGE_FAILED,),
    )
    evaluation = _evaluation_service().evaluate(
        candidate, synthesis_request, synthesis_policy, _m12_result(candidate, EngineeringCheckStatus.VIOLATED), cad, m10, CandidateEvaluationPolicy()
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.INFEASIBLE


def test_metric_cannot_be_forged_from_discrete_clearance_or_wrong_unit():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    policy = CandidateEvaluationPolicy()
    evaluation = _evaluation_service().evaluate(
        candidate, synthesis_request, synthesis_policy, _m12_result(candidate), cad, m10, policy,
        cad_request=cad_request, m10_request=m10_request, m10_scope=scope, m10_binding=binding,
    )
    forged_metric = evaluation.metrics[0].model_copy(update={"unit": "cm", "value": 123.0, "metric_hash": "pending"})
    with pytest.raises(ValueError, match="metric|unit|certificate"):
        CandidateEvaluation.model_validate(evaluation.model_dump(mode="json") | {"metrics": (forged_metric,), "evaluation_hash": "pending"})


def test_currentness_rejects_changed_source_and_forged_result(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation = _evaluation_service().evaluate(
        candidate, synthesis_request, synthesis_policy, _m12_result(candidate), cad, m10, CandidateEvaluationPolicy(),
        cad_request=cad_request, m10_request=m10_request, m10_scope=scope, m10_binding=binding,
    )
    assert CandidateEvaluationCurrentnessService(
        manager, cad_replay_verifier=lambda *args: None
    ).verify_current(
        evaluation, candidate, synthesis_request, synthesis_policy
    ) is True
    manager.create_revision("PRJ-M12", state.model_copy(update={"id": "changed"}))
    with pytest.raises(ValueError, match="current|source|stale"):
        CandidateEvaluationCurrentnessService(
            manager, cad_replay_verifier=lambda *args: None
        ).verify_current(
            evaluation, candidate, synthesis_request, synthesis_policy
        )


def test_evaluation_rejects_stale_candidate_before_aggregation(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    manager.create_revision("PRJ-M12", state.model_copy(update={"id": "changed"}))

    with pytest.raises(CandidateIntegrityError, match="current|stale|source"):
        CandidateEvaluationService(manager).evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            cad,
            m10,
            CandidateEvaluationPolicy(),
        )


def test_evaluation_rejects_forged_m10_stage_request_reference():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    forged_stage = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {"evaluation_request_hash": "sha256:" + "f" * 64, "outcome_hash": "pending"}
    )

    with pytest.raises(ValueError, match="request|M10"):
        _evaluation_service().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            cad,
            forged_stage,
            CandidateEvaluationPolicy(),
            cad_request=cad_request,
            m10_request=m10_request,
            m10_scope=scope,
            m10_binding=binding,
        )


def test_evaluation_rejects_omitted_required_m10_pair_proof():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    forged_stage = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json") | {"pair_proofs": (), "outcome_hash": "pending"}
    )

    with pytest.raises(ValueError, match="proof|pair"):
        _evaluation_service().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            cad,
            forged_stage,
            CandidateEvaluationPolicy(),
            cad_request=cad_request,
            m10_request=m10_request,
            m10_scope=scope,
            m10_binding=binding,
        )


def test_evaluation_rejects_certificate_requirement_replay_against_original_request():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    proof = m10.pair_proofs[0]
    changed_request = proof.request.model_copy(
        update={"required_clearance_mm": proof.request.required_clearance_mm + 1.0, "request_hash": "pending"}
    )
    changed_result = proof.result.model_copy(
        update={
            "request_hash": changed_request.request_hash,
            "required_clearance_mm": changed_request.required_clearance_mm,
            "result_hash": "pending",
        }
    )
    result_payload = changed_result.model_dump(mode="json", exclude={"result_hash"})
    changed_result = changed_result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(result_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )
    changed_proof = proof.model_copy(
        update={
            "request": changed_request,
            "result": changed_result,
            "request_hash": changed_request.request_hash,
            "result_hash": changed_result.result_hash,
            "proof_hash": "pending",
        }
    )
    forged_stage = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {"pair_proofs": (changed_proof,), "outcome_hash": "pending"}
    )

    with pytest.raises(ValueError, match="request|clearance|scope"):
        _evaluation_service().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            cad,
            forged_stage,
            CandidateEvaluationPolicy(),
            cad_request=cad_request,
            m10_request=m10_request,
            m10_scope=scope,
            m10_binding=binding,
        )


def test_currentness_revalidates_supplied_policy_nested_hashes(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation_policy = CandidateEvaluationPolicy()
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        m10,
        evaluation_policy,
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    forged_policy = evaluation_policy.model_copy(
        update={"required_check_keys": ("candidate_cad_realization",)}
    )

    with pytest.raises(ValueError, match="policy|hash"):
        CandidateEvaluationCurrentnessService(
            manager, cad_replay_verifier=lambda *args: None
        ).verify_current(
            evaluation,
            candidate,
            synthesis_request,
            synthesis_policy,
            policy=forged_policy,
        )


def test_currentness_revalidates_nested_policy_inside_forged_evaluation(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    forged_policy = evaluation.policy.model_copy(
        update={"required_check_keys": ("candidate_cad_realization",)}
    )
    forged_evaluation = evaluation.model_copy(update={"policy": forged_policy})

    with pytest.raises(ValueError, match="policy|hash"):
        CandidateEvaluationCurrentnessService(
            manager, cad_replay_verifier=lambda *args: None
        ).verify_current(
            forged_evaluation,
            candidate,
            synthesis_request,
            synthesis_policy,
        )


def test_currentness_replays_candidate_cad_before_accepting_it(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )

    def reject_replay(*args):
        raise ValueError("stale CAD source bytes")

    with pytest.raises(ValueError, match="stale CAD source"):
        CandidateEvaluationCurrentnessService(
            manager, cad_replay_verifier=reject_replay
        ).verify_current(evaluation, candidate)


def test_currentness_requires_cad_replay_verifier(tmp_path):
    manager = StateManager(tmp_path)

    with pytest.raises(CandidateIntegrityError, match="CAD replay|replay verifier"):
        CandidateEvaluationCurrentnessService(manager)


def test_verified_clear_requires_a_lower_bound_above_original_clearance_and_guard():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    proof = m10.pair_proofs[0]
    original_certificate = proof.result.certified_leaf_certificates[0]
    threshold = proof.request.required_clearance_mm + proof.request.proof_guard_mm
    threshold_pair = original_certificate.pair_certificates[0].model_copy(
        update={"certified_lower_clearance_mm": threshold}
    )
    threshold_certificate = original_certificate.model_copy(
        update={
            "pair_certificates": (threshold_pair,),
            "minimum_certified_lower_clearance_mm": threshold,
        }
    )
    threshold_result = proof.result.model_copy(
        update={"certified_leaf_certificates": (threshold_certificate,), "result_hash": "pending"}
    )
    payload = threshold_result.model_dump(mode="json", exclude={"result_hash"})
    threshold_result = threshold_result.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )
    threshold_stage = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {
            "pair_proofs": (
                proof.model_copy(
                    update={
                        "result": threshold_result,
                        "result_hash": threshold_result.result_hash,
                        "proof_hash": "pending",
                    }
                ),
            ),
            "outcome_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="clearance|threshold|guard"):
        _evaluation_service().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            cad,
            threshold_stage,
            CandidateEvaluationPolicy(),
            cad_request=cad_request,
            m10_request=m10_request,
            m10_scope=scope,
            m10_binding=binding,
        )


def test_evaluation_rejects_foreign_cad_mapping_input_even_when_stage_hashes_are_replayed():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    foreign_mapping = cad_request.mappings[0].model_copy(
        update={"geometry_definition_identities": ("candidate:foreign-geometry",), "mapping_hash": "pending"}
    )
    foreign_request = CandidateCadRealizationRequest.model_validate(
        cad_request.model_dump(mode="json")
        | {"mappings": (foreign_mapping, *cad_request.mappings[1:]), "request_hash": "pending"}
    )
    foreign_realization = CandidateCadRealization.model_validate(
        cad.realization.model_dump(mode="json")
        | {
            "request_hash": foreign_request.request_hash,
            "mappings": (foreign_mapping, *cad.realization.mappings[1:]),
            "realization_hash": "pending",
        }
    )
    foreign_cad = CandidateCadStageOutcome(
        status=CandidateCadStageStatus.SUCCESS, realization=foreign_realization
    )
    foreign_m10 = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {"cad_realization_hash": foreign_realization.realization_hash, "outcome_hash": "pending"}
    )

    with pytest.raises(ValueError, match="foreign|geometry|input"):
        _evaluation_service().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            foreign_cad,
            foreign_m10,
            CandidateEvaluationPolicy(),
            cad_request=foreign_request,
            m10_request=m10_request,
            m10_scope=scope,
            m10_binding=binding,
        )


def test_evaluation_rejects_foreign_m10_binding_reference_even_when_stage_hashes_are_replayed():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    foreign_binding_hash = "sha256:" + "f" * 64
    foreign_inventory = m10_request.inventory.model_copy(
        update={"binding_hash": foreign_binding_hash, "inventory_hash": "pending"}
    )
    foreign_request = CandidateM10EvaluationRequest.model_validate(
        m10_request.model_dump(mode="json")
        | {
            "binding_hash": foreign_binding_hash,
            "inventory": foreign_inventory,
            "request_hash": "pending",
        }
    )
    foreign_m10 = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {
            "binding_hash": foreign_binding_hash,
            "evaluation_request_hash": foreign_request.request_hash,
            "outcome_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="binding|M10|request"):
        _evaluation_service().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            cad,
            foreign_m10,
            CandidateEvaluationPolicy(),
            cad_request=cad_request,
            m10_request=foreign_request,
            m10_scope=scope,
            m10_binding=binding,
        )


def test_collision_witness_remains_a_hard_evaluation_outcome():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    proof = m10.pair_proofs[0]
    collision = proof.result.model_copy(
        update={
            "status": ContinuousSingleAxisProofStatus.COLLISION_WITNESS,
            "certified_leaf_certificates": (),
            "unresolved_intervals": (),
            "collision_witness": ContinuousCollisionWitness(
                witness_angle_deg=0.0,
                moving_instance_id=proof.moving_instance_id,
                stationary_instance_id=proof.stationary_instance_id,
                interference_volume_mm3=1.0,
                exact_distance_mm=0.0,
                classification="interference",
            ),
            "result_hash": "pending",
        }
    )
    payload = collision.model_dump(mode="json", exclude={"result_hash"})
    collision = collision.model_copy(
        update={
            "result_hash": "sha256:" + hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        }
    )
    collision_stage = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {
            "pair_proofs": (
                proof.model_copy(
                    update={"result": collision, "result_hash": collision.result_hash, "proof_hash": "pending"}
                ),
            ),
            "outcome_hash": "pending",
        }
    )
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        collision_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.INFEASIBLE


def test_home_collision_witness_remains_hard_while_continuous_internal_motion_is_unresolved():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, _, _, binding, _, cad_request = _bound_m10_inputs(candidate)
    scope = _scope()
    m10_request = _request(cad.realization, binding, scope)
    m10 = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs),
        lambda **kwargs: _home_result(kwargs, collision=True),
        scope=scope,
    ).evaluate(
        1,
        candidate.source_binding.source_state_hash,
        cad.realization,
        binding,
        m10_request,
    )
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.INFEASIBLE
    assert any(item.startswith("m10_home_collision:") for item in evaluation.hard_witnesses)
    assert "m10_continuous_clearance" in evaluation.unresolved_findings


def test_evaluation_requires_source_state_currentness_verification():
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate()
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)

    with pytest.raises(CandidateIntegrityError, match="currentness"):
        CandidateEvaluationService().evaluate(
            candidate,
            synthesis_request,
            synthesis_policy,
            _m12_result(candidate),
            cad,
            m10,
            CandidateEvaluationPolicy(),
            cad_request=cad_request,
            m10_request=m10_request,
            m10_scope=scope,
            m10_binding=binding,
        )


def test_rehashed_clear_home_stage_cannot_omit_required_internal_motion_finding(tmp_path):
    state = _state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
    cad, _, _, binding, _, cad_request = _bound_m10_inputs(candidate)
    scope = _scope()
    m10_request = _request(cad.realization, binding, scope)
    m10 = CandidateM10EvaluationService(
        lambda **kwargs: _continuous_result(kwargs),
        lambda **kwargs: _home_result(kwargs),
        scope=scope,
    ).evaluate(
        1,
        candidate.source_binding.source_state_hash,
        cad.realization,
        binding,
        m10_request,
    )
    forged_stage = CandidateM10StageOutcome.model_validate(
        m10.model_dump(mode="json")
        | {
            "status": CandidateM10StageStatus.SUCCESS,
            "reasons": (),
            "outcome_hash": "pending",
        }
    )

    evaluation = CandidateEvaluationService(manager).evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        _m12_result(candidate),
        cad,
        forged_stage,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )

    assert evaluation.outcome is CandidateEvaluationOutcome.UNRESOLVED
    assert "m10_internal_motion_unmodeled" in evaluation.unresolved_findings
    assert evaluation.m10_stage_outcome.home_exact_checks[0].result_hash == m10.home_exact_checks[0].result_hash
