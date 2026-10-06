from __future__ import annotations

import pytest

from mechcad_harness.candidates.m11_handoff import (
    CanonicalM11HandoffRequest,
    CanonicalM11HandoffResult,
    CanonicalM11HandoffRequestV2,
    CanonicalM11HandoffV2,
    build_handoff_v2,
    verify_m11_handoff_request_v2_linkage,
)
from mechcad_harness.candidates.promotion_artifacts import (
    SelectedCandidateDecisionManifest,
    SelectedCandidateDecisionManifestV2,
)
from mechcad_harness.candidates.promotion_models import (
    CandidateCanonicalInstanceMappingV3,
    CandidatePromotionPolicyV2,
    PrePromotionM10ScopeProjectionV2,
    PromotableMechanismProjectionV2,
    PromotionDecisionInputReferenceV2,
    PromotionPhysicalPairRequirement,
    PostPromotionM11TargetIntent,
    PromotionValueClassification,
)
from mechcad_harness.revolute_drive import InputProvenanceKind

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64
HASH_D = "sha256:" + "d" * 64


def _mapping_for(candidate_instance_id, canonical_instance_id):
    return CandidateCanonicalInstanceMappingV3(
        candidate_instance_id=candidate_instance_id,
        canonical_instance_id=canonical_instance_id,
        canonical_path=f"/physical_mechanisms/mech-1/components/{canonical_instance_id}",
        classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
        source_identity=f"s-{candidate_instance_id}",
        source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
    )


def _mapping():
    return (_mapping_for("c1", "k1"),)


def _intent(scope="single_component"):
    if scope == "single_component":
        return PostPromotionM11TargetIntent(
            target_scope="single_component", candidate_instance_id="c1"
        )
    return PostPromotionM11TargetIntent(target_scope="whole_mechanism")


def _request_v2(scope="single_component", mapping=None, semantic_decision_hash=HASH_C):
    mapping = _mapping() if mapping is None else mapping
    if scope == "single_component":
        return CanonicalM11HandoffRequestV2(
            project_id="p1",
            promoted_revision=2,
            promoted_state_hash=HASH_A,
            canonical_mechanism_id="mech-1",
            canonical_mechanism_hash=HASH_B,
            target_scope="single_component",
            target_instance_id=mapping[0].canonical_instance_id,
            target_geometry_artifact_id="GEO-1",
            target_geometry_artifact_hash=HASH_C,
            target_geometry_bound_revision=2,
            target_geometry_bound_state_hash=HASH_A,
            target_geometry_content_identity=HASH_D,
            target_geometry_content_identity_algorithm="step-content-identity@1",
            intent=_intent("single_component"),
            promotion_result_artifact_id="RES-1",
            promotion_result_hash=HASH_A,
            decision_artifact_id="DEC-1",
            decision_artifact_hash=HASH_B,
            semantic_decision_hash=semantic_decision_hash,
            promotion_proposal_hash=HASH_D,
            mapping_hashes=tuple(item.mapping_hash for item in mapping),
            mapping=mapping,
        )
    return CanonicalM11HandoffRequestV2(
        project_id="p1",
        promoted_revision=2,
        promoted_state_hash=HASH_A,
        canonical_mechanism_id="mech-1",
        canonical_mechanism_hash=HASH_B,
        target_scope="whole_mechanism",
        target_instance_id="mech-1",
        target_geometry_content_identity=None,
        target_geometry_content_identity_algorithm=None,
        intent=_intent("whole_mechanism"),
        promotion_result_artifact_id="RES-1",
        promotion_result_hash=HASH_A,
        decision_artifact_id="DEC-1",
        decision_artifact_hash=HASH_B,
        semantic_decision_hash=semantic_decision_hash,
        promotion_proposal_hash=HASH_D,
        mapping_hashes=tuple(item.mapping_hash for item in mapping),
        mapping=mapping,
    )


def test_exact_27_field_partition():
    assert len(CanonicalM11HandoffRequestV2.model_fields) == 27
    included = {
        "schema_version", "project_id", "canonical_mechanism_id", "canonical_mechanism_hash",
        "target_scope", "target_instance_id", "analysis_category", "eligibility_scope",
        "eligibility_scope_version", "promotion_result_hash", "semantic_decision_hash",
        "promotion_proposal_hash", "mapping_hashes",
        "target_geometry_content_identity", "target_geometry_content_identity_algorithm",
    }
    transformed = {"intent", "mapping"}
    excluded = {
        "promoted_revision", "promoted_state_hash",
        "target_geometry_artifact_id", "target_geometry_artifact_hash",
        "target_geometry_bound_revision", "target_geometry_bound_state_hash",
        "promotion_result_artifact_id", "decision_artifact_id", "decision_artifact_hash",
        "request_hash",
    }
    assert set(CanonicalM11HandoffRequestV2.model_fields.keys()) == included | transformed | excluded
    assert len(included) == 15
    assert len(transformed) == 2
    assert len(excluded) == 10


def test_component_bound_requires_identity():
    req = _request_v2("single_component")
    assert req.target_geometry_content_identity == HASH_D
    assert req.target_geometry_content_identity_algorithm == "step-content-identity@1"
    # Wrong algorithm rejects.
    with pytest.raises(ValueError, match="algorithm"):
        CanonicalM11HandoffRequestV2(
            **{**_request_v2("single_component").model_dump(mode="json"),
               "target_geometry_content_identity_algorithm": "other@1",
               "request_hash": "pending"}
        )


def test_whole_mechanism_null_pair():
    req = _request_v2("whole_mechanism")
    assert req.target_geometry_content_identity is None
    assert req.target_geometry_content_identity_algorithm is None
    # One-null/one-non-null rejects.
    with pytest.raises(ValueError, match="null"):
        CanonicalM11HandoffRequestV2(
            **{**req.model_dump(mode="json"),
               "target_geometry_content_identity": HASH_A,
               "request_hash": "pending"}
        )


def test_decision_linkage_and_raw_invariance():
    req = _request_v2("single_component")
    verify_m11_handoff_request_v2_linkage(
        req, decision_hash=HASH_C, promotion_result_hash=HASH_A
    )
    with pytest.raises(ValueError, match="decision"):
        verify_m11_handoff_request_v2_linkage(
            req, decision_hash=HASH_A, promotion_result_hash=HASH_A
        )
    # Raw-only decision variation invariance: changing raw artifact hash leaves
    # semantic request hash invariant? No: raw is excluded, so two requests differing
    # only in raw must have same request_hash.
    raw_variant = CanonicalM11HandoffRequestV2(
        **{
            **req.model_dump(mode="json"),
            "target_geometry_artifact_id": "GEO-2",
            "target_geometry_artifact_hash": HASH_D,
            "target_geometry_bound_revision": 3,
            "target_geometry_bound_state_hash": HASH_B,
            "decision_artifact_hash": HASH_D,
            "request_hash": "pending",
        }
    )
    assert raw_variant.request_hash == req.request_hash
    # Semantic decision variation changes request hash.
    sem_variant = CanonicalM11HandoffRequestV2(
        **{**req.model_dump(mode="json"), "semantic_decision_hash": HASH_A, "request_hash": "pending"}
    )
    assert sem_variant.request_hash != req.request_hash


def _decision_manifest_v2(mapping):
    pair = PromotionPhysicalPairRequirement(
        requirement_key="pair",
        first_instance_id="k1",
        first_interface_id="i1",
        second_instance_id="k2",
        second_interface_id="i2",
    )
    scope = PrePromotionM10ScopeProjectionV2(
        joint_semantic_key="joint",
        angle_interval_deg=(0.0, 1.0),
        required_clearance_mm=0.0,
        physical_pair_requirements=(pair,),
    )
    projection = PromotableMechanismProjectionV2(
        canonical_target_mechanism_id="mech-1",
        canonical_mechanism_hash=HASH_B,
        canonical_instance_ids=("k1",),
        mapping_identities=(mapping.mapping_hash,),
    )
    reference = PromotionDecisionInputReferenceV2(
        promotion_request_hash=HASH_A,
        project_id="p1",
        base_revision=1,
        base_state_hash=HASH_A,
        candidate_hash=HASH_A,
        synthesis_request_hash=HASH_B,
        synthesis_policy_hash=HASH_C,
        m12_3_result_hash=HASH_A,
        evaluation_hash=HASH_B,
        selection_hash=HASH_C,
        promotion_policy_hash=HASH_D,
        canonical_target_mechanism_id="mech-1",
        mapping_identities=(mapping.mapping_hash,),
    )
    return SelectedCandidateDecisionManifestV2(
        input_reference=reference,
        pre_promotion_scope_projection=scope,
        promotion_policy_hash=HASH_D,
        base_revision=1,
        base_state_hash=HASH_A,
        compilation_hash=HASH_A,
        promotion_proposal_hash=HASH_B,
        projection_hash=projection.projection_hash,
        projection=projection,
        mapping=(mapping,),
    )


def test_semantic_decision_hash_is_established_by_verified_decision_manifest():
    mapping = _mapping()[0]
    manifest = _decision_manifest_v2(mapping)
    request = _request_v2(semantic_decision_hash=manifest.decision_hash)
    verify_m11_handoff_request_v2_linkage(
        request,
        decision_manifest=manifest,
        promotion_result_hash=HASH_A,
    )


def test_cross_rejection_and_mapping_alignment():
    from mechcad_harness.candidates.promotion_models import CandidateCanonicalInstanceMapping

    req = _request_v2("single_component")
    # @1 request type rejected where @2 required (exact-type check, no upgrade).
    with pytest.raises(ValueError, match="@2|exact|linkage"):
        verify_m11_handoff_request_v2_linkage(
            {"schema_version": "canonical-m11-handoff-request@1"},
            decision_hash=HASH_C,
            promotion_result_hash=HASH_A,
        )
    # @1 mapping objects rejected for @2 (must be exactly @3).
    legacy_mapping = CandidateCanonicalInstanceMapping(
        candidate_instance_id="c1",
        canonical_instance_id="k1",
        canonical_path="/physical_components/k1",
        classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
        source_identity="s1",
        source_provenance=InputProvenanceKind.SOURCE_AUTHORITY,
    )
    with pytest.raises(ValueError, match="@3|exact"):
        CanonicalM11HandoffRequestV2(
            **{**req.model_dump(mode="json"), "mapping": (legacy_mapping,), "request_hash": "pending"}
        )
    # Mapping cardinality/alignment enforced.
    with pytest.raises(ValueError, match="cardinality|alignment|min|short"):
        CanonicalM11HandoffRequestV2(
            **{**req.model_dump(mode="json"), "mapping_hashes": (), "request_hash": "pending"}
        )
    duplicate = _mapping_for("c1", "k1")
    with pytest.raises(ValueError, match="unique"):
        CanonicalM11HandoffRequestV2(
            **{
                **req.model_dump(mode="json"),
                "mapping": (duplicate, duplicate),
                "mapping_hashes": (duplicate.mapping_hash, duplicate.mapping_hash),
                "request_hash": "pending",
            }
        )
    wrong_path = CandidateCanonicalInstanceMappingV3(
        **{
            **req.mapping[0].model_dump(mode="json"),
            "canonical_path": "/physical_components/k1",
            "mapping_hash": "pending",
        }
    )
    with pytest.raises(ValueError, match="path|canonical mechanism"):
        CanonicalM11HandoffRequestV2(
            **{
                **req.model_dump(mode="json"),
                "mapping": (wrong_path,),
                "mapping_hashes": (wrong_path.mapping_hash,),
                "request_hash": "pending",
            }
        )


def test_mapping_hashes_follow_key_alignment_not_global_hash_order():
    mapping = (_mapping_for("c3", "k3"), _mapping_for("c4", "k4"))
    assert mapping[0].mapping_hash > mapping[1].mapping_hash
    request = _request_v2(mapping=mapping)
    assert request.mapping_hashes == tuple(item.mapping_hash for item in mapping)


def test_component_bound_requires_complete_raw_target_binding():
    with pytest.raises(ValueError, match="source|artifact|binding|complete"):
        request = _request_v2("single_component")
        CanonicalM11HandoffRequestV2(
            **{
                **request.model_dump(mode="json"),
                "target_geometry_artifact_id": None,
                "request_hash": "pending",
            }
        )


def test_whole_mechanism_target_is_bound_to_mechanism_identity():
    request = _request_v2("whole_mechanism")
    with pytest.raises(ValueError, match="whole-mechanism|mechanism"):
        CanonicalM11HandoffRequestV2(
            **{
                **request.model_dump(mode="json"),
                "target_instance_id": "component-1",
                "request_hash": "pending",
            }
        )


def test_envelope_by_hash_only():
    req = _request_v2("single_component")
    env = build_handoff_v2(
        req,
        CanonicalM11HandoffResult(status="eligible"),
    )
    assert env.schema_version == "canonical-m11-handoff@2"
    # Nested full request dump never enters (by-hash-only).
    assert "target_geometry_content_identity" not in env.model_dump(mode="json")


def test_envelope_requires_request_v2_and_result_v1():
    req = _request_v2("single_component")
    with pytest.raises(ValueError, match="request@2|result@1|exact"):
        build_handoff_v2(req, object())


def test_envelope_rejects_legacy_request_parent():
    legacy = CanonicalM11HandoffRequest.model_construct()
    with pytest.raises(ValueError, match="request@2|exact"):
        build_handoff_v2(legacy, CanonicalM11HandoffResult(status="eligible"))


def test_decision_linkage_rejects_unverified_parent_object():
    with pytest.raises(ValueError, match="verified decision manifest@2|exact"):
        verify_m11_handoff_request_v2_linkage(
            _request_v2(),
            decision_manifest=object(),
            promotion_result_hash=HASH_A,
        )


def test_decision_linkage_rejects_legacy_decision_parent():
    legacy = SelectedCandidateDecisionManifest.model_construct(decision_hash=HASH_C)
    with pytest.raises(ValueError, match="manifest@2|exact"):
        verify_m11_handoff_request_v2_linkage(
            _request_v2(),
            decision_manifest=legacy,
            promotion_result_hash=HASH_A,
        )


def test_new_family_compiler_override_is_rejected_by_pinned_parent_policy():
    with pytest.raises(ValueError, match="candidate-promotion@1|pinned"):
        CandidatePromotionPolicyV2(compiler_version="caller-override")


def test_v2_envelope_contains_no_structural_execution_payload():
    assert not {"structural_definition", "mesh", "solver", "evidence"}.intersection(
        CanonicalM11HandoffV2.model_fields
    )


def test_envelope_hash_is_by_hash_only_and_excludes_coordinates():
    request = _request_v2()
    envelope = build_handoff_v2(request, CanonicalM11HandoffResult(status="eligible"))
    coordinate_variant = CanonicalM11HandoffV2(
        **{
            **envelope.model_dump(mode="json"),
            "promoted_revision": 99,
            "promoted_state_hash": HASH_D,
            "handoff_hash": "pending",
        }
    )
    assert coordinate_variant.handoff_hash == envelope.handoff_hash
