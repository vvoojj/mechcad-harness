"""Focused unit tests for the H1-B joint authority admission service (B2/B3/B4)."""

from __future__ import annotations

import pytest

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
from mechcad_harness.dependency import DependencyGraph, EvidenceStore
from mechcad_harness.state import StateManager, state_hash, state_hash_v1
from mechcad_harness.runs import RunController
from mechcad_harness.changes import ChangeConflictError, ChangeEngine, OwnershipPolicy
from mechcad_harness.changes.joint_authority_admission import (
    JointAuthorityAdmissionPolicy,
    JointAuthorityAdmissionRule,
    JointAuthorityAdmissionService,
    JointAuthorityApproval,
)

PROJECT_ID = "MINI_ROTARY_FIXTURE"
AUTHORITY_KIND = "single-joint-verification-requirement@1"


def _declaration(declaration_id: str = "DECL-1", **overrides) -> JointAuthorityDeclaration:
    data = {
        "project_id": PROJECT_ID,
        "id": declaration_id,
        "authority_kind": AUTHORITY_KIND,
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
    data.update(overrides)
    return JointAuthorityDeclaration.model_validate(data)


def _rule(**overrides) -> JointAuthorityAdmissionRule:
    data = {
        "authority_kind": AUTHORITY_KIND,
        "authorized_issuers": ("fixture-issuer",),
        "authorized_approvers": ("fixture-approver",),
        "issuer_origin_kinds_allowed": (
            AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
            AuthorityOriginKind.TRUSTED_ENGINEERING_DECLARATION,
        ),
        "synthetic_scope_project_ids": (PROJECT_ID,),
    }
    data.update(overrides)
    return JointAuthorityAdmissionRule.model_validate(data)


def _approval(declaration, *, issuer="fixture-issuer", approver="fixture-approver"):
    return JointAuthorityApproval(
        project_id=PROJECT_ID,
        authority_kind=declaration.authority_kind,
        issuer_id=issuer,
        approver_id=approver,
        content_hash=declaration.declaration_hash,
    )


def _admit(harness, declaration, approval):
    return harness["service"].admit(
        declaration,
        approval,
        admission_run_id=harness["run"].run_id,
        source_revision=harness["base_revision"],
        source_state_hash=harness["base_state_hash"],
    )


@pytest.fixture()
def harness(tmp_path):
    workspace = tmp_path / "workspace"
    state_manager = StateManager(workspace)
    state_manager.create_project(PROJECT_ID, DesignState(id="DES-1", revision=1))
    evidence = EvidenceStore(workspace, state_manager, DependencyGraph([], []))
    controller = RunController(
        workspace,
        state_manager,
        ChangeEngine(
            state_manager,
            OwnershipPolicy(
                [{"path": "/joint_authority_declarations/*", "owner": "mechcad-joint-authority-admission"}]
            ),
        ),
        evidence,
    )
    run = controller.create_run(PROJECT_ID)
    policy = JointAuthorityAdmissionPolicy(project_id=PROJECT_ID, rules=(_rule(),))
    service = JointAuthorityAdmissionService(
        project_id=PROJECT_ID,
        state_manager=state_manager,
        run_controller=controller,
        policy=policy,
    )
    return {
        "state_manager": state_manager,
        "controller": controller,
        "run": run,
        "base_revision": run.initial_revision,
        "base_state_hash": run.initial_state_hash,
        "policy": policy,
        "service": service,
    }


def test_admit_creates_revision_and_persists(harness):
    declaration = _declaration()
    result = _admit(harness, declaration, _approval(declaration))
    assert result.replayed is False
    assert result.revision == 2
    state = harness["state_manager"].load_current_state(PROJECT_ID)
    assert len(state.joint_authority_declarations) == 1
    stored = state.joint_authority_declarations[0]
    assert stored.id == "DECL-1"
    assert stored.provenance is not None
    assert stored.provenance.admission_source_revision == 1
    assert stored.provenance.admitted_at_revision == 2
    assert stored.provenance.approval_content_hash == declaration.declaration_hash


def test_admit_replays_without_new_revision(harness):
    declaration = _declaration()
    _admit(harness, declaration, _approval(declaration))
    result = _admit(harness, declaration, _approval(declaration))
    assert result.replayed is True
    assert result.revision == 2


def test_nonempty_collection_enters_hash(harness):
    declaration = _declaration()
    _admit(harness, declaration, _approval(declaration))
    state = harness["state_manager"].load_current_state(PROJECT_ID)
    assert state_hash(state) != state_hash_v1(state)


def test_unauthorized_issuer_rejected(harness):
    declaration = _declaration()
    with pytest.raises(ValueError):
        _admit(harness, declaration, _approval(declaration, issuer="evil"))


def test_content_hash_mismatch_rejected(harness):
    declaration = _declaration()
    approval = _approval(declaration)
    object.__setattr__(approval, "content_hash", "sha256:" + "0" * 64)
    with pytest.raises(ValueError):
        _admit(harness, declaration, approval)


def test_self_approval_rejected(harness):
    declaration = _declaration()
    with pytest.raises(ValueError):
        _admit(
            harness,
            declaration,
            _approval(declaration, issuer="fixture-issuer", approver="fixture-issuer"),
        )


def test_synthetic_origin_outside_scope_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    state_manager = StateManager(workspace)
    state_manager.create_project("OTHER-PROJECT", DesignState(id="DES-2", revision=1))
    evidence = EvidenceStore(workspace, state_manager, DependencyGraph([], []))
    controller = RunController(
        workspace,
        state_manager,
        ChangeEngine(
            state_manager,
            OwnershipPolicy([{"path": "/joint_authority_declarations/*", "owner": "mechcad-joint-authority-admission"}]),
        ),
        evidence,
    )
    run = controller.create_run("OTHER-PROJECT")
    policy = JointAuthorityAdmissionPolicy(project_id="OTHER-PROJECT", rules=(_rule(),))
    service = JointAuthorityAdmissionService(
        project_id="OTHER-PROJECT", state_manager=state_manager, run_controller=controller, policy=policy
    )
    declaration = _declaration()
    with pytest.raises(ValueError):
        service.admit(
            declaration,
            _approval(declaration),
            admission_run_id=run.run_id,
            source_revision=run.initial_revision,
            source_state_hash=run.initial_state_hash,
        )


def test_missing_required_limitation_rejected(harness):
    rule = _rule(required_bounded_limitation_kinds=("internal_motion_unmodeled@1",))
    policy = JointAuthorityAdmissionPolicy(project_id=PROJECT_ID, rules=(rule,))
    service = JointAuthorityAdmissionService(
        project_id=PROJECT_ID,
        state_manager=harness["state_manager"],
        run_controller=harness["controller"],
        policy=policy,
    )
    data = _declaration().model_dump(mode="json")
    data["verification"]["bounded_limitations"] = []
    data["declaration_hash"] = "pending"
    declaration = JointAuthorityDeclaration.model_validate(data)
    with pytest.raises(ValueError):
        service.admit(
            declaration,
            _approval(declaration),
            admission_run_id=harness["run"].run_id,
            source_revision=harness["base_revision"],
            source_state_hash=harness["base_state_hash"],
        )


def test_duplicate_declaration_id_rejected(harness):
    declaration = _declaration()
    _admit(harness, declaration, _approval(declaration))
    data = _declaration().model_dump(mode="json")
    data["joint_semantic_key"] = "a-different-joint"
    data["verification"]["joint_semantic_key"] = "a-different-joint"
    data["declaration_hash"] = "pending"
    conflicting = JointAuthorityDeclaration.model_validate(data)
    with pytest.raises(ValueError):
        _admit(harness, conflicting, _approval(conflicting))


def test_policy_from_file(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(
        "project_id: MINI_ROTARY_FIXTURE\n"
        "rules:\n"
        "  - authority_kind: single-joint-verification-requirement@1\n"
        "    authorized_issuers: [fixture-issuer]\n"
        "    authorized_approvers: [fixture-approver]\n"
        "    issuer_origin_kinds_allowed: [approved_synthetic_fixture]\n"
        "    synthetic_scope_project_ids: [MINI_ROTARY_FIXTURE]\n",
        encoding="utf-8",
    )
    policy = JointAuthorityAdmissionPolicy.from_file(path, project_id=PROJECT_ID)
    assert policy.authorize(
        authority_kind=AUTHORITY_KIND,
        issuer_id="fixture-issuer",
        approver_id="fixture-approver",
        origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
        scope_project_id=PROJECT_ID,
    )


def test_deny_all_policy_rejects(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text("project_id: MINI_ROTARY_FIXTURE\nrules: []\n", encoding="utf-8")
    policy = JointAuthorityAdmissionPolicy.from_file(path, project_id=PROJECT_ID)
    assert not policy.authorize(
        authority_kind=AUTHORITY_KIND,
        issuer_id="fixture-issuer",
        approver_id="fixture-approver",
        origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
        scope_project_id=PROJECT_ID,
    )


def _declaration_with_canonical_ref(canonical_component_id: str) -> JointAuthorityDeclaration:
    data = _declaration().model_dump(mode="json")
    data["constituents"][0]["component_ref"] = {
        "ref_kind": "canonical_component_identity",
        "canonical_component_id": canonical_component_id,
    }
    data["declaration_hash"] = "pending"
    return JointAuthorityDeclaration.model_validate(data)


def test_cross_project_declaration_rejected(harness):
    declaration = _declaration(project_id="OTHER-PROJECT")
    with pytest.raises(ValueError, match="declaration project mismatch"):
        _admit(harness, declaration, _approval(declaration))


def test_unresolved_canonical_component_reference_rejected(harness):
    declaration = _declaration_with_canonical_ref("CMP-DOES-NOT-EXIST")
    with pytest.raises(ValueError, match="canonical component reference"):
        _admit(harness, declaration, _approval(declaration))


def test_canonical_reference_resolution_unit(tmp_path):
    from types import SimpleNamespace

    service = JointAuthorityAdmissionService(
        project_id=PROJECT_ID,
        state_manager=SimpleNamespace(workspace=tmp_path),
        run_controller=None,
        policy=JointAuthorityAdmissionPolicy.deny_all(PROJECT_ID),
    )
    source = SimpleNamespace(
        physical_mechanisms=[
            SimpleNamespace(
                components=[SimpleNamespace(instance_id="CMP-1")],
                component_specifications=[
                    SimpleNamespace(specification_hash="sha256:" + "a" * 64)
                ],
            )
        ]
    )
    service._validate_canonical_references(
        source, _declaration_with_canonical_ref("CMP-1")
    )
    service._validate_canonical_references(
        source, _declaration_with_canonical_ref("sha256:" + "a" * 64)
    )
    with pytest.raises(ValueError):
        service._validate_canonical_references(
            source, _declaration_with_canonical_ref("CMP-MISSING")
        )


def test_policy_file_with_metadata_envelope_loads(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(
        "schema: mechcad-harness\n"
        "version: 1\n"
        "project_id: MINI_ROTARY_FIXTURE\n"
        "policy_id: mini-joint-authority-policy@1\n"
        "rules:\n"
        "  - authority_kind: single-joint-verification-requirement@1\n"
        "    authorized_issuers: [mini-fixture-issuer]\n"
        "    authorized_approvers: [mini-fixture-approver]\n"
        "    issuer_origin_kinds_allowed: [approved_synthetic_fixture]\n"
        "    synthetic_scope_project_ids: [MINI_ROTARY_FIXTURE]\n"
        "    required_bounded_limitation_kinds: [internal_motion_unmodeled@1]\n",
        encoding="utf-8",
    )
    policy = JointAuthorityAdmissionPolicy.from_file(path, project_id=PROJECT_ID)
    assert policy.policy_id == "mini-joint-authority-policy@1"
    assert policy.authorize(
        authority_kind=AUTHORITY_KIND,
        issuer_id="mini-fixture-issuer",
        approver_id="mini-fixture-approver",
        origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
        scope_project_id=PROJECT_ID,
    )


def test_policy_file_metadata_envelope_preserves_deny_all(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(
        "schema: mechcad-harness\n"
        "version: 1\n"
        "project_id: MINI_ROTARY_FIXTURE\n"
        "rules: []\n",
        encoding="utf-8",
    )
    policy = JointAuthorityAdmissionPolicy.from_file(path, project_id=PROJECT_ID)
    assert not policy.authorize(
        authority_kind=AUTHORITY_KIND,
        issuer_id="mini-fixture-issuer",
        approver_id="mini-fixture-approver",
        origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
        scope_project_id=PROJECT_ID,
    )


def test_approved_mini_fixture_policy_file_loads():
    from pathlib import Path

    mini_policy = (
        Path(__file__).resolve().parents[2]
        / "projects"
        / "mini_rotary_fixture"
        / "joint_authority_policy.yaml"
    )
    if not mini_policy.exists():
        pytest.skip("local MINI fixture policy not present")
    policy = JointAuthorityAdmissionPolicy.from_file(
        mini_policy, project_id="MINI_ROTARY_FIXTURE"
    )
    assert policy.policy_id == "mini-joint-authority-policy@1"
    assert policy.authorize(
        authority_kind=AUTHORITY_KIND,
        issuer_id="mini-fixture-issuer",
        approver_id="mini-fixture-approver",
        origin_kind=AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE,
        scope_project_id="MINI_ROTARY_FIXTURE",
    )
