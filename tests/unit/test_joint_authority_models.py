"""Focused unit tests for the H1-B joint authority declaration models (B1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mechcad_harness.models.joint_authority import (
    AuthorityOrigin,
    AuthorityOriginKind,
    ComponentAuthorityReference,
    ComponentReferenceKind,
    JointAuthorityDeclaration,
    JointAuthorityAdmissionProvenance,
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


def _declaration(**overrides) -> JointAuthorityDeclaration:
    constituents = (
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
    )
    data = {
        "project_id": "MINI_ROTARY_FIXTURE",
        "id": "DECL-1",
        "authority_kind": "single-joint-verification-requirement@1",
        "semantic_version": "h1b-joint-semantics@1",
        "authority_origin": AuthorityOrigin(
            origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
            issuer_id="fixture-issuer",
            scope_project_id="MINI_ROTARY_FIXTURE",
            provenance_note="fixture origin",
        ),
        "constituents": constituents,
        "parent_constituent_key": "mount",
        "child_constituent_key": "shaft",
        "joint_semantic_key": "primary-output-revolute",
        "motion": JointMotionDeclaration(supports_internal_motion=True),
        "axis": JointAxisDeclaration(
            frame_reference=JointFrameReference(
                frame_id="f1",
                supplied_by_constituent_key="mount",
                interface_id="mount-face",
            ),
            direction_z=2.0,
            coordinate_system_id="cs-mount@1",
            axis_sign_rule="right-hand-point-parent-to-child@1",
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
    data.update(overrides)
    return JointAuthorityDeclaration.model_validate(data)


def _provenance() -> JointAuthorityAdmissionProvenance:
    return JointAuthorityAdmissionProvenance(
        admission_source_revision=3,
        admission_source_state_hash="sha256:" + "a" * 64,
        admission_run_id="RUN-1",
        admission_policy_id="policy-1",
        admission_policy_hash="sha256:" + "b" * 64,
        issuer_id="issuer",
        approver_id="approver",
        approval_content_hash="sha256:" + "c" * 64,
        admitted_at_revision=4,
    )


def test_hash_computed_and_stable() -> None:
    declaration = _declaration()
    assert declaration.declaration_hash.startswith("sha256:")
    assert len(declaration.declaration_hash) == 71
    assert declaration.model_dump(mode="json")["declaration_hash"] == declaration.declaration_hash


def test_hash_mismatch_rejected() -> None:
    declaration = _declaration()
    payload = declaration.model_dump(mode="json")
    payload["declaration_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError):
        JointAuthorityDeclaration.model_validate(payload)


def test_direction_normalized() -> None:
    assert _declaration().axis.direction_z == pytest.approx(1.0)


def test_parent_child_must_differ() -> None:
    with pytest.raises(ValidationError):
        _declaration(parent_constituent_key="mount", child_constituent_key="mount")


def test_duplicate_constituent_keys_rejected() -> None:
    constituents = (
        JointConstituent(
            constituent_key="mount",
            component_ref=ComponentAuthorityReference(
                ref_kind=ComponentReferenceKind.SYNTHETIC_FIXTURE_IDENTITY,
                source_identity="fixture:mount",
            ),
            role=Role.MOUNT_OR_SUPPORT,
        ),
        JointConstituent(
            constituent_key="mount",
            component_ref=ComponentAuthorityReference(
                ref_kind=ComponentReferenceKind.SYNTHETIC_FIXTURE_IDENTITY,
                source_identity="fixture:mount2",
            ),
            role=Role.ROTATING_MEMBER,
        ),
    )
    with pytest.raises(ValidationError):
        _declaration(constituents=constituents)


def test_pair_requires_declared_interface() -> None:
    pair = JointPairRequirement(
        requirement_key="p",
        first_constituent_key="shaft",
        first_interface_id="not-declared",
        second_constituent_key="mount",
        second_interface_id="mount-face",
    )
    with pytest.raises(ValidationError):
        _declaration(
            verification=JointVerificationRequirement(
                joint_semantic_key="primary-output-revolute",
                angle_interval_deg=(-45.0, 45.0),
                required_clearance_mm=1.0,
                required_pairs=(pair,),
                verification_semantics_version="m10-single-axis-continuous-proof@1",
            )
        )


def test_axis_owner_must_match_frame_owner() -> None:
    with pytest.raises(ValidationError):
        _declaration(
            axis=JointAxisDeclaration(
                frame_reference=JointFrameReference(
                    frame_id="f1", supplied_by_constituent_key="mount"
                ),
                coordinate_system_id="cs@1",
                axis_sign_rule="rule@1",
                axis_owner_constituent_key="shaft",
            )
        )


def test_synthetic_origin_requires_scope_project() -> None:
    with pytest.raises(ValidationError):
        _declaration(
            authority_origin=AuthorityOrigin(
                origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
                issuer_id="fixture-issuer",
                provenance_note="n",
            )
        )


def test_component_reference_single_identity() -> None:
    with pytest.raises(ValidationError):
        ComponentAuthorityReference(
            ref_kind=ComponentReferenceKind.CANONICAL_COMPONENT_IDENTITY,
            canonical_component_id="CMP-1",
            source_identity="fixture:x",
        )
    with pytest.raises(ValidationError):
        ComponentAuthorityReference(
            ref_kind=ComponentReferenceKind.ENGINEERING_SOURCE_IDENTITY
        )


def test_provenance_excluded_from_semantic_hash() -> None:
    base = _declaration()
    with_provenance = base.model_copy(update={"provenance": _provenance()})
    assert with_provenance.declaration_hash == base.declaration_hash


def test_frozen_and_extra_forbidden() -> None:
    declaration = _declaration()
    payload = declaration.model_dump(mode="json")
    payload["unexpected"] = 1
    with pytest.raises(ValidationError):
        JointAuthorityDeclaration.model_validate(payload)


def test_frame_owner_must_be_declared_constituent() -> None:
    with pytest.raises(ValidationError):
        _declaration(
            axis=JointAxisDeclaration(
                frame_reference=JointFrameReference(
                    frame_id="f1",
                    supplied_by_constituent_key="ghost",
                    interface_id="mount-face",
                ),
                coordinate_system_id="cs@1",
                axis_sign_rule="rule@1",
                axis_owner_constituent_key="ghost",
            )
        )


def test_frame_interface_must_be_declared_on_owner() -> None:
    with pytest.raises(ValidationError):
        _declaration(
            axis=JointAxisDeclaration(
                frame_reference=JointFrameReference(
                    frame_id="f1",
                    supplied_by_constituent_key="mount",
                    interface_id="not-declared",
                ),
                coordinate_system_id="cs@1",
                axis_sign_rule="rule@1",
                axis_owner_constituent_key="mount",
            )
        )


def test_frame_reference_must_be_grounded_in_declared_interface() -> None:
    with pytest.raises(ValidationError):
        _declaration(
            axis=JointAxisDeclaration(
                frame_reference=JointFrameReference(
                    frame_id="frame-that-does-not-exist",
                    supplied_by_constituent_key="mount",
                ),
                coordinate_system_id="cs@1",
                axis_sign_rule="rule@1",
                axis_owner_constituent_key="mount",
            )
        )


def test_synthetic_fixture_ref_requires_synthetic_origin() -> None:
    with pytest.raises(ValidationError):
        _declaration(
            authority_origin=AuthorityOrigin(
                origin_kind=AuthorityOriginKind.TRUSTED_ENGINEERING_DECLARATION,
                issuer_id="eng-issuer",
                provenance_note="trusted engineering declaration",
            )
        )

