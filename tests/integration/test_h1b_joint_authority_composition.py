"""Composition test: H1-B joint authority admission via ProductionApplication (B5/B7)."""

from __future__ import annotations

import json

import pytest

from mechcad_harness.application import ProductionApplication
from mechcad_harness.models import DesignState
from mechcad_harness.models.joint_authority import (
    AuthorityOrigin,
    AuthorityOriginKind,
    ComponentAuthorityReference,
    ComponentReferenceKind,
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
from mechcad_harness.changes.joint_authority_admission import JointAuthorityApproval

PROJECT_ID = "MINI_ROTARY_FIXTURE"


class Adapter:
    identity = object()

    def invoke(self, request):
        raise AssertionError("not called")


def _declaration() -> JointAuthorityDeclaration:
    return JointAuthorityDeclaration.model_validate(
        {
            "project_id": PROJECT_ID,
            "id": "DECL-COMP-1",
            "authority_kind": "single-joint-verification-requirement@1",
            "semantic_version": "h1b-joint-semantics@1",
            "authority_origin": AuthorityOrigin(
                origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
                issuer_id="mini-fixture-issuer",
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
            "motion": JointMotionDeclaration(supports_internal_motion=True),
            "axis": JointAxisDeclaration(
                frame_reference=JointFrameReference(
                    frame_id="f1", supplied_by_constituent_key="mount", interface_id="mount-face"
                ),
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
    )


@pytest.fixture()
def app(tmp_path):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    ownership.write_text(
        "ownership:\n"
        "  - path: /joint_authority_declarations/*\n"
        "    owner: mechcad-joint-authority-admission\n",
        encoding="utf-8",
    )
    dependencies = tmp_path / "dependencies.yaml"
    dependencies.write_text(json.dumps({"rules": [], "edges": []}), encoding="utf-8")
    policy = tmp_path / "joint_authority_policy.yaml"
    policy.write_text(
        "project_id: MINI_ROTARY_FIXTURE\n"
        "rules:\n"
        "  - authority_kind: single-joint-verification-requirement@1\n"
        "    authorized_issuers: [mini-fixture-issuer]\n"
        "    authorized_approvers: [mini-fixture-approver]\n"
        "    issuer_origin_kinds_allowed: [approved_synthetic_fixture]\n"
        "    synthetic_scope_project_ids: [MINI_ROTARY_FIXTURE]\n",
        encoding="utf-8",
    )
    from mechcad_harness.state import StateManager

    StateManager(workspace).create_project(PROJECT_ID, DesignState(id="DES-1", revision=1))
    application = ProductionApplication.create(
        workspace,
        PROJECT_ID,
        Adapter(),
        ownership_path=ownership,
        dependency_path=dependencies,
        joint_authority_policy_path=policy,
    )
    return application


def test_composition_admits_and_replays(app):
    run = app.create_run().run
    base = app.state_manager._read_current(PROJECT_ID)
    declaration = _declaration()
    approval = JointAuthorityApproval(
        project_id=PROJECT_ID,
        authority_kind=declaration.authority_kind,
        issuer_id="mini-fixture-issuer",
        approver_id="mini-fixture-approver",
        content_hash=declaration.declaration_hash,
    )
    result = app.admit_joint_authority_declaration(
        declaration,
        approval,
        admission_run_id=run.run_id,
        source_revision=base["revision"],
        source_state_hash=base["state_hash"],
    )
    assert result.replayed is False
    assert result.revision == 2
    replay = app.admit_joint_authority_declaration(
        declaration,
        approval,
        admission_run_id=run.run_id,
        source_revision=base["revision"],
        source_state_hash=base["state_hash"],
    )
    assert replay.replayed is True
    assert replay.revision == 2
