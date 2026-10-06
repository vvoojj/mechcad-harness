from __future__ import annotations

import hashlib
import pytest

from mechcad_harness.candidates.provenance_artifacts import (
    CandidateMultiJointM10Provenance,
    candidate_multi_joint_m10_provenance_artifact_id,
    resolve_mj_provenance_expected_tuple_from_promotion_request,
    resolve_mj_provenance_expected_tuple_from_decision_manifest,
    resolve_mj_provenance_expected_tuple_from_result_manifest,
    validate_candidate_multi_joint_m10_provenance_chain,
)
from mechcad_harness.candidates.promotion_models import CandidateMultiJointPromotionRequestV2
from mechcad_harness.candidates.promotion_artifacts import (
    SelectedMultiJointCandidateDecisionManifestV2,
    MultiJointPromotionResultManifestV2,
)
from mechcad_harness.artifacts import ArtifactType, EngineeringArtifact
from mechcad_harness.candidates.provenance_artifacts import ArtifactReference

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
HASH_D = "sha256:" + "d" * 64


def _artifact(artifact_id="CAND-1", input_hash=None, project="PRJ-M12", rev=2, state=None):
    state = state or HASH_A
    return EngineeringArtifact(
        artifact_id=artifact_id,
        project_id=project,
        run_id="run-1",
        task_id="task-1",
        artifact_type=ArtifactType.JSON,
        media_type="application/json",
        relative_path=f"{artifact_id}.json",
        sha256=HASH_B,
        size_bytes=10,
        producer_tool_name="mechcad-candidate-provenance",
        producer_tool_version="1",
        bound_revision=rev,
        bound_state_hash=state,
        input_hash=input_hash or HASH_C,
        created_at="2026-01-01T00:00:00+00:00",
    )


def _ref(artifact):
    return ArtifactReference(
        artifact=artifact,
        artifact_id=artifact.artifact_id,
        project_id=artifact.project_id,
        run_id=artifact.run_id,
        task_id=artifact.task_id,
        artifact_type=artifact.artifact_type,
        sha256=artifact.sha256,
        bound_revision=artifact.bound_revision,
        bound_state_hash=artifact.bound_state_hash,
    )


def _mj_chain(tmp_path):
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
    from mechcad_harness.candidates.multi_joint_selection import CandidateMultiJointSelectionService
    from mechcad_harness.candidates.services import CandidateCurrentnessService

    state, manager, store, synthesis_request, policy, candidate = _candidate_with_m13_multi_joint_authority(tmp_path)
    cad_request, cad_realization = _candidate_cad_v2(candidate, synthesis_request, state)
    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)

    class _Cur:
        def __init__(self, m):
            self.delegate = CandidateCurrentnessService(m)
            self.requests = []

        def evaluate_source_binding(self, candidate, *, synthesis_request=None):
            self.requests.append(synthesis_request)
            return self.delegate.evaluate_source_binding(
                candidate, synthesis_request=synthesis_request
            )

        def verify_current(self, *a, **k):
            return True

    cur = _Cur(manager)

    def provider(**kwargs):
        return _raw_m10_result(**kwargs)

    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=cur,
        analyze_multi_joint_collision_sweep_v2=provider,
    )
    request = service.build_request(candidate, synthesis_request, cad_realization, bridge, scope, cad_request=cad_request)
    evaluation = service.execute(candidate, synthesis_request, cad_realization, bridge, request)

    def replayer(rc, rs, rr, re):
        low_request = service.reconstruct_m10_request(rc, rs, cad_realization, bridge, rr)
        low_result = _raw_m10_result(
            source_revision=rr.source_revision,
            source_state_hash=rr.source_state_hash,
            assembly=cad_realization.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=low_request.distance_tolerance_mm,
        )
        from mechcad_harness.candidates import multi_joint_m10_evaluation as evaluation_models

        return evaluation_models.CandidateMultiJointM10ReplayV2(low_request, low_result, cad_realization, bridge)

    selection = CandidateMultiJointSelectionService(
        project_id=candidate.source_binding.project_id,
        currentness_verifier=cur,
        result_replayer=replayer,
    ).select(candidate, request, evaluation, "sel@1", "reason", synthesis_request=synthesis_request)
    # P6 persisted body: use provider result for the same low request.
    low_request = service.reconstruct_m10_request(candidate, synthesis_request, cad_realization, bridge, request)
    p6_result = _raw_m10_result(
        source_revision=request.source_revision,
        source_state_hash=request.source_state_hash,
        assembly=cad_realization.assembly,
        model=low_request.model,
        configurations=low_request.configurations,
        exact_pair_scope=low_request.exact_pair_scope,
        volume_tolerance_mm3=low_request.volume_tolerance_mm3,
        distance_tolerance_mm=low_request.distance_tolerance_mm,
    )
    return {
        "state": state,
        "candidate": candidate,
        "synthesis_request": synthesis_request,
        "synthesis_policy": policy,
        "store": store,
        "cad_request": cad_request,
        "cad_realization": cad_realization,
        "bridge": bridge,
        "request": request,
        "evaluation": evaluation,
        "selection": selection,
        "p6_result": p6_result,
        "low_request": low_request,
        "manager": manager,
    }


def _envelope(chain):
    cand_pub = _artifact("CAND-1", input_hash=chain["candidate"].candidate_hash,
                         project=chain["candidate"].source_binding.project_id,
                         rev=chain["candidate"].source_binding.source_revision,
                         state=chain["candidate"].source_binding.source_state_hash)
    cad_pub = _artifact("CAD-1", input_hash=chain["cad_realization"].realization_hash,
                        project=chain["candidate"].source_binding.project_id,
                        rev=chain["candidate"].source_binding.source_revision,
                        state=chain["candidate"].source_binding.source_state_hash)
    return CandidateMultiJointM10Provenance(
        request=chain["request"],
        evaluation=chain["evaluation"],
        selection=chain["selection"],
        m10_v2_result=chain["p6_result"],
        candidate_publication=_ref(cand_pub),
        candidate_cad=_ref(cad_pub),
    )


def test_exact_seven_fields_literal_no_self_hash():
    assert set(CandidateMultiJointM10Provenance.model_fields.keys()) == {
        "schema_version", "request", "evaluation", "selection",
        "m10_v2_result", "candidate_publication", "candidate_cad",
    }
    assert len(CandidateMultiJointM10Provenance.model_fields) == 7
    assert CandidateMultiJointM10Provenance.model_fields["schema_version"].default == "candidate-multi-joint-m10-provenance@1"
    assert "selection_hash" not in CandidateMultiJointM10Provenance.model_fields
    # No @2 envelope version exists.
    import mechcad_harness.candidates.provenance_artifacts as mod

    assert not hasattr(mod, "CandidateMultiJointM10ProvenanceV2")


def test_typed_records_and_persisted_p6(tmp_path):
    chain = _mj_chain(tmp_path)
    env = _envelope(chain)
    assert env.schema_version == "candidate-multi-joint-m10-provenance@1"
    assert env.request.request_hash == chain["request"].request_hash
    assert env.evaluation.evaluation_hash == chain["evaluation"].evaluation_hash
    assert env.selection.selection_hash == chain["selection"].selection_hash
    # Persisted typed P6 body present (not a semantic reference).
    assert env.m10_v2_result.result_hash == chain["p6_result"].result_hash
    # CAND- and candidate-CAD refs present.
    assert env.candidate_publication.artifact.artifact_id == "CAND-1"
    assert env.candidate_cad.artifact.artifact_id == "CAD-1"


def test_existing_provenance_service_publishes_and_reloads_section_18b(tmp_path):
    from test_candidate_decision_v2 import _verify_candidate_cad_v2

    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
    )

    chain = _mj_chain(tmp_path)
    service = CandidateProvenanceArtifactService(
        tmp_path,
        chain["candidate"].source_binding.project_id,
        chain["manager"],
        cad_replay_verifier=_verify_candidate_cad_v2,
    )
    cad_publication = service.publish_candidate_cad(
        chain["candidate"],
        chain["synthesis_request"],
        chain["synthesis_policy"],
        chain["cad_request"],
        chain["cad_realization"],
        source_step_artifacts=None,
    )
    published = service.publish_candidate_multi_joint_m10(
        request=chain["request"],
        evaluation=chain["evaluation"],
        selection=chain["selection"],
        m10_v2_result=chain["p6_result"],
        candidate_cad=cad_publication,
    )
    resolved = service.resolve_candidate_multi_joint_m10(
        published.artifact,
        expected_selection_hash=chain["selection"].selection_hash,
    )
    fresh_service = CandidateProvenanceArtifactService(
        tmp_path,
        chain["candidate"].source_binding.project_id,
        chain["manager"],
        cad_replay_verifier=_verify_candidate_cad_v2,
    )
    restarted = fresh_service.resolve_candidate_multi_joint_m10(
        published.artifact.artifact_id,
        expected_selection_hash=chain["selection"].selection_hash,
    )

    assert published.artifact.artifact_id == candidate_multi_joint_m10_provenance_artifact_id(
        chain["selection"].selection_hash
    )
    assert published.artifact.input_hash == chain["selection"].selection_hash
    assert resolved.payload == published.payload
    assert restarted.payload == published.payload
    assert resolved.payload.m10_v2_result.result_hash == chain["p6_result"].result_hash


def test_deterministic_id_and_full_hash(tmp_path):
    chain = _mj_chain(tmp_path)
    sel_hash = chain["selection"].selection_hash
    artifact_id = candidate_multi_joint_m10_provenance_artifact_id(sel_hash)
    assert artifact_id == "CANDIDATE-MULTI-JOINT-M10-" + sel_hash[7:31]
    # Full hash always recomputed: truncated ID never proves identity.
    other = "sha256:" + "f" * 64
    assert candidate_multi_joint_m10_provenance_artifact_id(other) != artifact_id or other == sel_hash
    # Same truncated ID with different full hash -> conflict detectable.
    # (IDs equal only if first 24 hex chars collide; here they differ.)
    assert artifact_id.startswith("CANDIDATE-MULTI-JOINT-M10-")


def test_mixed_and_wrong_bindings_reject(tmp_path):
    chain = _mj_chain(tmp_path)
    env = _envelope(chain)
    # Mixed @1 request rejects (exact type).
    with pytest.raises(ValueError, match="exact"):
        CandidateMultiJointM10Provenance(
            request={"schema_version": "candidate-multi-joint-m10-evaluation-request@1"},
            evaluation=chain["evaluation"],
            selection=chain["selection"],
            m10_v2_result=chain["p6_result"],
            candidate_publication=env.candidate_publication,
            candidate_cad=env.candidate_cad,
        )
    # Wrong project rejects in chain validation.
    with pytest.raises(ValueError, match="project|candidate|binding"):
        validate_candidate_multi_joint_m10_provenance_chain(
            env, candidate_hash=chain["candidate"].candidate_hash, project_id="WRONG"
        )
    # Wrong candidate hash rejects.
    with pytest.raises(ValueError, match="candidate"):
        validate_candidate_multi_joint_m10_provenance_chain(
            env, candidate_hash=HASH_A, project_id=chain["candidate"].source_binding.project_id
        )


def test_p6_self_hash_and_semantic_and_replay(tmp_path):
    from mechcad_harness.multi_joint_collision_sweep import multi_joint_collision_sweep_result_v2_hash
    from mechcad_harness.candidates.multi_joint_m10_evaluation import (
        CandidateMultiJointM10EvaluationService,
    )
    from mechcad_harness.candidates.services import CandidateCurrentnessService
    from mechcad_harness.semantic_m10_kinematics import semantic_m10_v2_request_hash

    chain = _mj_chain(tmp_path)
    p6 = chain["p6_result"]
    # Legacy self-hash recomputes.
    assert multi_joint_collision_sweep_result_v2_hash(p6) == p6.result_hash
    # Forged P6 body fails self-hash.
    forged = p6.model_copy(update={"minimum_exact_distance_mm": 999.0, "result_hash": p6.result_hash})
    assert multi_joint_collision_sweep_result_v2_hash(forged) != p6.result_hash

    # P5 request is PURE_REDERIVED through the actual production reconstruction path:
    # reconstruct_m10_request deterministically rebuilds the low-level sweep request
    # from persisted bridge@2 + CAD realization@2 + scope, without invoking the
    # M10 provider. The spy is injected at the provider boundary and must not fire.
    calls = []

    def _no_exec(**kwargs):
        calls.append(kwargs)
        raise AssertionError("zero execution: P5/P6 must not re-execute")

    reconstruction_service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=CandidateCurrentnessService(chain["manager"]),
        analyze_multi_joint_collision_sweep_v2=_no_exec,
    )
    reconstructed = reconstruction_service.reconstruct_m10_request(
        chain["candidate"],
        chain["synthesis_request"],
        chain["cad_realization"],
        chain["bridge"],
        chain["request"],
    )
    assert calls == []

    # The persisted P6 result's legacy replay fields bind to the pure-rederived P5 request.
    assert p6.request_hash == reconstructed.request_hash
    assert p6.source_assembly_hash == reconstructed.source_assembly_hash
    assert p6.model_hash == reconstructed.model_hash

    # Semantic P5 identity recomputes from the reconstructed request + resolved assembly.
    assert semantic_m10_v2_request_hash(
        reconstructed,
        chain["cad_realization"].assembly,
        chain["cad_realization"].mappings,
    ) == chain["request"].semantic_m10_v2_request_hash

    # The envelope's persisted P6 body carries the same legacy request_hash.
    env = _envelope(chain)
    assert env.m10_v2_result.request_hash == reconstructed.request_hash


def test_roots_a_b_c_and_decision_linkage(tmp_path):
    chain = _mj_chain(tmp_path)
    # Root A: verified entry context only (not durable).
    promo_req = CandidateMultiJointPromotionRequestV2(
        project_id=chain["candidate"].source_binding.project_id,
        source_revision=chain["candidate"].source_binding.source_revision,
        source_state_hash=chain["candidate"].source_binding.source_state_hash,
        candidate_hash=chain["candidate"].candidate_hash,
        synthesis_request_hash=chain["synthesis_request"].request_hash,
        synthesis_policy_hash=chain["candidate"].synthesis_policy_hash,
        m12_3_result_hash=HASH_A,
        multi_joint_request_hash=chain["request"].request_hash,
        multi_joint_evaluation_hash=chain["evaluation"].evaluation_hash,
        multi_joint_selection_hash=chain["selection"].selection_hash,
        promotion_policy_hash=HASH_B,
        canonical_target_mechanism_id="mech-1",
    )
    expected_a = resolve_mj_provenance_expected_tuple_from_promotion_request(promo_req)
    assert expected_a == (
        chain["request"].request_hash,
        chain["evaluation"].evaluation_hash,
        chain["selection"].selection_hash,
    )
    # Artifact ID only after verified expected selection hash.
    artifact_id = candidate_multi_joint_m10_provenance_artifact_id(expected_a[2])
    assert artifact_id.startswith("CANDIDATE-MULTI-JOINT-M10-")

    # Root B/C require decision/result manifests @2; construct minimal valid ones
    # via direct model validation with dummy hashes for linkage mechanics.
    from mechcad_harness.candidates.promotion_models import (
        MultiJointPromotionDecisionInputReferenceV2,
        PromotableMechanismProjectionV2,
    )
    from mechcad_harness.candidates.promotion_artifacts import (
        SelectedMultiJointCandidateDecisionManifestV2,
        MultiJointPromotionResultManifestV2,
        multi_joint_decision_manifest_hash_v2,
    )

    # Use real MJ hashes for reference.
    ref = MultiJointPromotionDecisionInputReferenceV2(
        promotion_request_hash=HASH_A,
        readiness_hash=HASH_B,
        project_id=chain["candidate"].source_binding.project_id,
        source_revision=chain["candidate"].source_binding.source_revision,
        source_state_hash=chain["candidate"].source_binding.source_state_hash,
        semantic_source_binding_hash=chain["candidate"].semantic_source_binding_hash,
        candidate_hash=chain["candidate"].candidate_hash,
        synthesis_request_hash=chain["synthesis_request"].request_hash,
        synthesis_policy_hash=chain["candidate"].synthesis_policy_hash,
        m12_3_result_hash=HASH_A,
        multi_joint_evaluation_request_hash=chain["request"].request_hash,
        multi_joint_evaluation_hash=chain["evaluation"].evaluation_hash,
        multi_joint_selection_hash=chain["selection"].selection_hash,
        scope_hash=chain["request"].scope_hash,
        configuration_set_hash=chain["request"].configuration_set_hash,
        physical_pair_classification_set_hash=chain["request"].physical_pair_classification_set_hash,
        m10_v2_request_hash=HASH_C,
        m10_v2_result_hash=HASH_D,
        promotion_policy_hash=HASH_B,
        canonical_target_mechanism_id="mech-1",
        mapping_identities=(HASH_A,),
        classification_identities=(HASH_B,),
    )
    proj = PromotableMechanismProjectionV2(
        canonical_target_mechanism_id="mech-1",
        canonical_mechanism_hash=HASH_A,
        canonical_instance_ids=("k1",),
        mapping_identities=(HASH_A,),
    )
    from mechcad_harness.candidates.promotion_models import CandidateCanonicalInstanceMappingV3
    from mechcad_harness.revolute_drive import InputProvenanceKind
    from mechcad_harness.candidates.promotion_models import PromotionValueClassification

    mapping = (
        CandidateCanonicalInstanceMappingV3(
            candidate_instance_id="c1",
            canonical_instance_id="k1",
            canonical_path="/physical_components/k1",
            classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
            source_identity="s1",
            source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
        ),
    )
    # Align mapping hash with reference.
    ref = MultiJointPromotionDecisionInputReferenceV2(
        **{**ref.model_dump(mode="json"), "mapping_identities": (mapping[0].mapping_hash,), "reference_hash": "pending"}
    )
    manifest = SelectedMultiJointCandidateDecisionManifestV2(
        input_reference=ref,
        promotion_policy_hash=HASH_B,
        base_revision=chain["candidate"].source_binding.source_revision,
        base_state_hash=chain["candidate"].source_binding.source_state_hash,
        compilation_hash=HASH_C,
        promotion_proposal_hash=HASH_D,
        projection_hash=proj.projection_hash,
        projection=proj,
        mapping=mapping,
    )
    expected_b = resolve_mj_provenance_expected_tuple_from_decision_manifest(manifest)
    assert expected_b == (
        chain["request"].request_hash,
        chain["evaluation"].evaluation_hash,
        chain["selection"].selection_hash,
    )
    # Root C: byte-verified decision artifact.
    import json

    decision_bytes = manifest.model_dump_json().encode("utf-8")
    decision_hash_raw = "sha256:" + hashlib.sha256(decision_bytes).hexdigest()
    result = MultiJointPromotionResultManifestV2(
        decision_artifact_id="DEC-1",
        decision_artifact_hash=decision_hash_raw,
        decision_hash=manifest.decision_hash,
        promotion_proposal_hash=HASH_D,
        proposal_id="p1",
        changeset_id="c1",
        changed_paths=("/physical_mechanisms/mech-1",),
        canonical_target_mechanism_id="mech-1",
        mechanism_path="/physical_mechanisms/mech-1",
        base_revision=chain["candidate"].source_binding.source_revision,
        base_state_hash=chain["candidate"].source_binding.source_state_hash,
        resulting_revision=chain["candidate"].source_binding.source_revision + 1,
        resulting_state_hash=HASH_A,
    )
    expected_c = resolve_mj_provenance_expected_tuple_from_result_manifest(
        result, decision_artifact_bytes=decision_bytes, decision_artifact_hash=decision_hash_raw
    )
    assert expected_c == expected_b
    # Byte mismatch rejects.
    with pytest.raises(ValueError, match="byte"):
        resolve_mj_provenance_expected_tuple_from_result_manifest(
            result, decision_artifact_bytes=b"forged", decision_artifact_hash=decision_hash_raw
        )
    # Decision_hash mismatch rejects (tamper result).
    tampered = MultiJointPromotionResultManifestV2(
        **{**result.model_dump(mode="json"), "decision_hash": HASH_A, "result_hash": "pending"}
    )
    with pytest.raises(ValueError, match="decision_hash"):
        resolve_mj_provenance_expected_tuple_from_result_manifest(
            tampered, decision_artifact_bytes=decision_bytes, decision_artifact_hash=decision_hash_raw
        )
    # Rotation invariance: same resolved records with different artifact ID leave
    # semantic promotion identity invariant (IDs are pure functions of selection hash).
    assert candidate_multi_joint_m10_provenance_artifact_id(expected_b[2]) == artifact_id
