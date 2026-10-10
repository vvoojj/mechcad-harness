"""Focused unit tests for the H1-B promotion-consumption validation helper (B9)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mechcad_harness.candidates.joint_authority_promotion import (
    JointAuthorityPromotionValidator,
)
from mechcad_harness.models.joint_authority import (
    AuthorityOrigin,
    AuthorityOriginKind,
    ComponentAuthorityReference,
    ComponentReferenceKind,
    JointAuthorityAdmissionProvenance,
    JointAuthorityDeclaration,
    JointAxisDeclaration,
    JointBoundedLimitation,
    JointConstituent,
    JointFrameReference,
    JointMotionDeclaration,
    JointPairRequirement,
    JointVerificationRequirement,
)
from mechcad_harness.models.physical_mechanism import (
    CanonicalPhysicalComponentRole as Role,
)

PROJECT_ID = "MINI_ROTARY_FIXTURE"


def _declaration() -> JointAuthorityDeclaration:
    declaration = JointAuthorityDeclaration.model_validate(
        {
            "project_id": PROJECT_ID,
            "id": "DECL-V",
            "authority_kind": "single-joint-verification-requirement@1",
            "semantic_version": "h1b-joint-semantics@1",
            "authority_origin": AuthorityOrigin(
                origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
                issuer_id="fixture-issuer",
                scope_project_id=PROJECT_ID,
                provenance_note="fixture",
            ),
            "constituents": (
                JointConstituent(
                    constituent_key="mount",
                    component_ref=ComponentAuthorityReference(
                        ref_kind=ComponentReferenceKind.SYNTHETIC_FIXTURE_IDENTITY,
                        source_identity="fixture:mount",
                    ),
                    role=Role.MOUNT_OR_SUPPORT,
                    interface_refs=("mount-face",),
                ),
                JointConstituent(
                    constituent_key="shaft",
                    component_ref=ComponentAuthorityReference(
                        ref_kind=ComponentReferenceKind.SYNTHETIC_FIXTURE_IDENTITY,
                        source_identity="fixture:shaft",
                    ),
                    role=Role.ROTATING_MEMBER,
                    interface_refs=("shaft-journal",),
                ),
            ),
            "parent_constituent_key": "mount",
            "child_constituent_key": "shaft",
            "joint_semantic_key": "primary-output-revolute",
            "motion": JointMotionDeclaration(),
            "axis": JointAxisDeclaration(
                frame_reference=JointFrameReference(
                    frame_id="f1", supplied_by_constituent_key="mount", interface_id="mount-face"
                ),
                coordinate_system_id="cs@1",
                axis_sign_rule="rule@1",
                axis_owner_constituent_key="mount",
            ),
            "verification": JointVerificationRequirement(
                joint_semantic_key="primary-output-revolute",
                angle_interval_deg=(-45.0, 45.0),
                required_clearance_mm=1.0,
                required_pairs=(
                    JointPairRequirement(
                        requirement_key="hub-mount-clearance",
                        first_constituent_key="shaft",
                        first_interface_id="shaft-journal",
                        second_constituent_key="mount",
                        second_interface_id="mount-face",
                    ),
                ),
                bounded_limitations=(
                    JointBoundedLimitation(
                        limitation_key="internal_motion_unmodeled@1",
                        statement="Internal driver motion is not modeled.",
                        scope_constituent_keys=("shaft",),
                    ),
                ),
                verification_semantics_version="m10-single-axis-continuous-proof@1",
            ),
        }
    )
    provenance = JointAuthorityAdmissionProvenance(
        admission_source_revision=1,
        admission_source_state_hash="sha256:" + "a" * 64,
        admission_run_id="RUN-1",
        admission_policy_id="policy-1",
        admission_policy_hash="sha256:" + "b" * 64,
        issuer_id="fixture-issuer",
        approver_id="fixture-approver",
        approval_content_hash=declaration.declaration_hash,
        admitted_at_revision=2,
    )
    object.__setattr__(declaration, "provenance", provenance)
    return declaration


def _request(**overrides) -> SimpleNamespace:
    scope = SimpleNamespace(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            SimpleNamespace(
                requirement_key="hub-mount-clearance",
                requires_home_exact_check=False,
            ),
        ),
    )
    joint_binding = SimpleNamespace(axis_frame_reference="f1")
    realization = SimpleNamespace(joint_bindings=(joint_binding,))
    candidate = SimpleNamespace(realization=realization)
    evaluation = SimpleNamespace(m10_scope=scope)
    data = {
        "source_revision": 1,
        "source_state_hash": "sha256:" + "a" * 64,
        "candidate": candidate,
        "evaluation": evaluation,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_valid_request_passes():
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=_declaration(), request=_request()
    )
    assert result.ok, result.failures


def test_wrong_joint_key_fails():
    request = _request()
    request.evaluation.m10_scope.output_joint_semantic_key = "other-joint"
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=_declaration(), request=request
    )
    assert not result.ok


def test_wrong_interval_fails():
    request = _request()
    request.evaluation.m10_scope.angle_interval_deg = (0.0, 90.0)
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=_declaration(), request=request
    )
    assert not result.ok


def test_wrong_clearance_fails():
    request = _request()
    request.evaluation.m10_scope.required_clearance_mm = 2.0
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=_declaration(), request=request
    )
    assert not result.ok


def test_wrong_pairs_fails():
    request = _request()
    request.evaluation.m10_scope.pair_scope_requirements = ()
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=_declaration(), request=request
    )
    assert not result.ok


def test_wrong_frame_fails():
    request = _request()
    request.candidate.realization.joint_bindings = (SimpleNamespace(axis_frame_reference="other"),)
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=_declaration(), request=request
    )
    assert not result.ok


def test_unadmitted_declaration_fails():
    declaration = _declaration()
    data = declaration.model_dump(mode="json")
    data["provenance"] = None
    data["declaration_hash"] = "pending"
    unadmitted = JointAuthorityDeclaration.model_validate(data)
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=unadmitted, request=_request()
    )
    assert not result.ok


def test_synthetic_outside_scope_fails():
    declaration = _declaration()
    data = declaration.model_dump(mode="json")
    data["authority_origin"]["scope_project_id"] = "OTHER"
    data["declaration_hash"] = "pending"
    out = JointAuthorityDeclaration.model_validate(data)
    result = JointAuthorityPromotionValidator().validate(
        project_id=PROJECT_ID, declaration=out, request=_request()
    )
    assert not result.ok
