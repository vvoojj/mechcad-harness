"""Project-bound trusted joint authority admission.

A policy-authorized issuer states a :class:`JointAuthorityDeclaration`; a distinct
policy-authorized approver approves its exact content hash; the trusted admission
service compiles one ``ChangeProposal`` and applies it through the existing
``RunController -> ChangeEngine`` path under the project lock.  Candidate
CAD/M10/evaluation/solver output is never an authority source.

The trust root is a trusted, out-of-band, project-bound
:class:`JointAuthorityAdmissionPolicy` (deny-all by default).  There is no
cryptographic authentication; issuer/approver are governance assertions
validated against the policy.  Synthetic fixture origin is strictly scoped to the
authorized project and denied by default elsewhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.changes.operations import ChangeOperation, OperationType
from mechcad_harness.models import ChangeProposal, DesignState, ProposalStatus
from mechcad_harness.models.common import Model
from mechcad_harness.models.joint_authority import (
    AuthorityOriginKind,
    ComponentReferenceKind,
    JointAuthorityAdmissionProvenance,
    JointAuthorityDeclaration,
)
from mechcad_harness.runs.models import RunEvent
from mechcad_harness.runs.persistence import RunStore
from mechcad_harness.state.hashing import state_hash

AUTHORITY_ACTOR = "mechcad-joint-authority-admission"

# Accepted policy-file envelope: the trusted out-of-band project-bound policy may
# carry optional metadata (`schema`/`version`/`policy_id`). Only `project_id`,
# `rules`, and the optional `policy_id` are semantically consumed; `schema` and
# `version` are tolerated as inert metadata so an approved policy artifact loads
# through the production loader without weakening the deny-by-default rule set.
_POLICY_FILE_KEYS = frozenset({"schema", "version", "project_id", "policy_id", "rules"})


def _nonempty(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty")
    return value


class JointAuthorityApproval(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    authority_kind: str = Field(min_length=1)
    issuer_id: str = Field(min_length=1)
    approver_id: str = Field(min_length=1)
    content_hash: str
    declared_approval_policy_id: str | None = None

    _validate_text = field_validator(
        "project_id", "authority_kind", "issuer_id", "approver_id"
    )(_nonempty)
    _validate_policy = field_validator("declared_approval_policy_id")(
        lambda cls, value: None if value is None else _nonempty(value)
    )


class JointAuthorityAdmissionRule(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    authority_kind: str = Field(min_length=1)
    authorized_issuers: tuple[str, ...] = Field(min_length=1)
    authorized_approvers: tuple[str, ...] = Field(min_length=1)
    issuer_origin_kinds_allowed: tuple[AuthorityOriginKind, ...] = Field(min_length=1)
    allow_self_approval: bool = False
    required_bounded_limitation_kinds: tuple[str, ...] = ()
    synthetic_scope_project_ids: tuple[str, ...] = ()

    _validate_kind = field_validator("authority_kind")(_nonempty)

    @model_validator(mode="after")
    def validate_rule(self) -> "JointAuthorityAdmissionRule":
        if not self.authorized_issuers or not self.authorized_approvers:
            raise ValueError("admission rule requires issuers and approvers")
        if len(set(self.authorized_issuers)) != len(self.authorized_issuers):
            raise ValueError("admission rule issuers must be unique")
        if len(set(self.authorized_approvers)) != len(self.authorized_approvers):
            raise ValueError("admission rule approvers must be unique")
        return self


class JointAuthorityAdmissionPolicy(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    policy_id: str = "joint-authority-admission-policy@1"
    rules: tuple[JointAuthorityAdmissionRule, ...] = ()

    _validate_project = field_validator("project_id", "policy_id")(_nonempty)

    @classmethod
    def deny_all(cls, project_id: str) -> "JointAuthorityAdmissionPolicy":
        return cls(project_id=project_id, rules=())

    def for_project(self, project_id: str) -> "JointAuthorityAdmissionPolicy":
        if project_id != self.project_id:
            raise ValueError("joint authority admission policy project mismatch")
        return self

    def authorize(
        self,
        *,
        authority_kind: str,
        issuer_id: str,
        approver_id: str,
        origin_kind: AuthorityOriginKind,
        scope_project_id: str | None,
    ) -> bool:
        for rule in self.rules:
            if rule.authority_kind != authority_kind:
                continue
            if issuer_id not in rule.authorized_issuers:
                continue
            if approver_id not in rule.authorized_approvers:
                continue
            if origin_kind not in rule.issuer_origin_kinds_allowed:
                continue
            if origin_kind is AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE:
                if self.project_id not in rule.synthetic_scope_project_ids:
                    continue
                if scope_project_id != self.project_id:
                    continue
            if issuer_id == approver_id and not rule.allow_self_approval:
                continue
            return True
        return False

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        project_id: str,
    ) -> "JointAuthorityAdmissionPolicy":
        payload = _read_policy_file(path)
        if payload.get("project_id") != project_id:
            raise ValueError("joint authority admission policy project mismatch")
        rules = payload.get("rules", ())
        if not isinstance(rules, list):
            raise ValueError("joint authority admission policy rules must be a list")
        parsed: list[JointAuthorityAdmissionRule] = []
        for entry in rules:
            if not isinstance(entry, dict):
                raise ValueError("joint authority admission rule must be a mapping")
            parsed.append(_rule_from_mapping(entry))
        policy_id = payload.get("policy_id")
        if policy_id is not None and (
            not isinstance(policy_id, str) or not policy_id.strip()
        ):
            raise ValueError("joint authority admission policy id must not be empty")
        return cls(
            project_id=project_id,
            policy_id=policy_id or "joint-authority-admission-policy@1",
            rules=tuple(parsed),
        ).for_project(project_id)


def _rule_from_mapping(entry: dict) -> JointAuthorityAdmissionRule:
    required = {
        "authority_kind",
        "authorized_issuers",
        "authorized_approvers",
        "issuer_origin_kinds_allowed",
    }
    missing = required - set(entry)
    if missing:
        raise ValueError(f"joint authority admission rule missing fields: {sorted(missing)}")
    origin_kinds = entry["issuer_origin_kinds_allowed"]
    if not isinstance(origin_kinds, list) or not origin_kinds:
        raise ValueError("issuer_origin_kinds_allowed must be a non-empty list")
    return JointAuthorityAdmissionRule(
        authority_kind=_nonempty(str(entry["authority_kind"])),
        authorized_issuers=tuple(_nonempty(str(item)) for item in entry["authorized_issuers"]),
        authorized_approvers=tuple(_nonempty(str(item)) for item in entry["authorized_approvers"]),
        issuer_origin_kinds_allowed=tuple(
            AuthorityOriginKind(str(item)) for item in origin_kinds
        ),
        allow_self_approval=bool(entry.get("allow_self_approval", False)),
        required_bounded_limitation_kinds=tuple(
            _nonempty(str(item)) for item in entry.get("required_bounded_limitation_kinds", ())
        ),
        synthetic_scope_project_ids=tuple(
            _nonempty(str(item)) for item in entry.get("synthetic_scope_project_ids", ())
        ),
    )


def _read_policy_file(path: str | Path) -> dict:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("unable to read joint authority admission policy") from exc
    try:
        if text.lstrip().startswith("{"):
            payload = json.loads(text)
        else:
            payload = _parse_simple_yaml(text)
    except (SyntaxError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid joint authority admission policy") from exc
    if not isinstance(payload, dict) or set(payload) - _POLICY_FILE_KEYS:
        raise ValueError("invalid joint authority admission policy fields")
    return payload


def _parse_simple_yaml(text: str) -> dict:
    result: dict = {}
    rules: list[dict] = []
    current: dict | None = None
    in_rules = False
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "rules:":
            in_rules = True
            continue
        if not in_rules:
            if ":" not in stripped:
                raise ValueError("invalid policy field")
            key, value = stripped.split(":", 1)
            result[key.strip()] = _yaml_value(value.strip())
            continue
        if stripped.startswith("- "):
            current = {}
            rules.append(current)
            stripped = stripped[2:]
            if ":" not in stripped:
                raise ValueError("invalid admission rule")
        if ":" not in stripped:
            raise ValueError("invalid admission rule")
        key, value = stripped.split(":", 1)
        if current is None:
            raise ValueError("invalid admission rule")
        current[key.strip()] = _yaml_value(value.strip())
    result["rules"] = rules
    return result


def _yaml_value(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]
    if value == "[]":
        return []
    return value.strip("\"'")


@dataclass(frozen=True)
class JointAuthorityAdmissionResult:
    replayed: bool
    revision: int
    state_hash: str
    proposal: ChangeProposal
    changeset_id: str


def deterministic_joint_authority_ids(
    *,
    project_id: str,
    authority_kind: str,
    declaration_id: str,
    declaration_hash: str,
    base_revision: int,
    base_state_hash: str,
) -> tuple[str, str]:
    identity = json.dumps(
        {
            "project_id": project_id,
            "authority_kind": authority_kind,
            "declaration_id": declaration_id,
            "declaration_hash": declaration_hash,
            "base_revision": base_revision,
            "base_state_hash": base_state_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    value = uuid5(NAMESPACE_URL, identity)
    return f"JA-PROP-{value}", f"JA-CS-{value}"


@dataclass(frozen=True)
class _Compiled:
    proposal: ChangeProposal
    changeset_id: str
    expected_state: DesignState
    expected_state_hash: str


class JointAuthorityAdmissionService:
    def __init__(self, *, project_id, state_manager, run_controller, policy):
        self.project_id = project_id
        self.state_manager = state_manager
        self.run_controller = run_controller
        self.policy = policy.for_project(project_id)
        self.run_store = RunStore(state_manager.workspace)

    def admit(
        self,
        declaration: JointAuthorityDeclaration,
        approval: JointAuthorityApproval,
        *,
        admission_run_id: str,
        source_revision: int,
        source_state_hash: str,
    ) -> JointAuthorityAdmissionResult:
        with self.state_manager.project_lock(self.project_id):
            if approval.project_id != self.project_id:
                raise ValueError("joint authority approval project mismatch")
            if declaration.project_id != self.project_id:
                raise ValueError("joint authority declaration project mismatch")
            if approval.authority_kind != declaration.authority_kind:
                raise ValueError("joint authority approval kind mismatch")
            if not self.policy.authorize(
                authority_kind=declaration.authority_kind,
                issuer_id=approval.issuer_id,
                approver_id=approval.approver_id,
                origin_kind=declaration.authority_origin.origin_kind,
                scope_project_id=declaration.authority_origin.scope_project_id,
            ):
                raise ValueError("joint authority declaration is not authorized")
            if approval.content_hash != declaration.declaration_hash:
                raise ValueError("joint authority approval content hash mismatch")
            origin = declaration.authority_origin
            if (
                origin.origin_kind is AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE
                and origin.scope_project_id != self.project_id
            ):
                raise ValueError(
                    "approved_synthetic_fixture origin is outside its authorized project scope"
                )
            required = self._required_limitation_kinds(declaration.authority_kind)
            present = {
                item.limitation_key
                for item in declaration.verification.bounded_limitations
            }
            if required - present:
                raise ValueError(
                    "joint authority declaration is missing required bounded limitations"
                )

            current = self.state_manager.load_current_pointer(self.project_id)
            if (
                current["revision"] == source_revision
                and current["state_hash"] == source_state_hash
            ):
                self._load_source(admission_run_id, source_revision, source_state_hash)
                compiled = self._compile(
                    declaration, approval, admission_run_id, source_revision, source_state_hash
                )
                updated = self.run_controller.apply_approved_proposal(
                    admission_run_id,
                    compiled.proposal,
                    changeset_id=compiled.changeset_id,
                )
                return JointAuthorityAdmissionResult(
                    replayed=False,
                    revision=updated.active_revision,
                    state_hash=updated.active_state_hash,
                    proposal=compiled.proposal,
                    changeset_id=compiled.changeset_id,
                )
            compiled = self._compile(
                declaration, approval, admission_run_id, source_revision, source_state_hash
            )
            return self._replay(
                admission_run_id,
                source_revision,
                source_state_hash,
                compiled.expected_state,
                compiled.expected_state_hash,
                compiled.proposal,
                compiled.changeset_id,
            )

    def _compile(
        self,
        declaration: JointAuthorityDeclaration,
        approval: JointAuthorityApproval,
        admission_run_id: str,
        source_revision: int,
        source_state_hash: str,
    ) -> "_Compiled":
        provenance = JointAuthorityAdmissionProvenance(
            admission_source_revision=source_revision,
            admission_source_state_hash=source_state_hash,
            admission_run_id=admission_run_id,
            admission_policy_id=self.policy.policy_id,
            admission_policy_hash=self._policy_hash(),
            issuer_id=approval.issuer_id,
            approver_id=approval.approver_id,
            approval_content_hash=approval.content_hash,
            admitted_at_revision=source_revision + 1,
        )
        record = declaration.model_copy(update={"provenance": provenance})
        proposal_id, changeset_id = deterministic_joint_authority_ids(
            project_id=self.project_id,
            authority_kind=declaration.authority_kind,
            declaration_id=declaration.id,
            declaration_hash=declaration.declaration_hash,
            base_revision=source_revision,
            base_state_hash=source_state_hash,
        )
        operation = ChangeOperation(
            operation=OperationType.ADD,
            path=f"/joint_authority_declarations/{declaration.id}",
            value=record.model_dump(mode="json"),
        )
        proposal = ChangeProposal(
            id=proposal_id,
            title="Admit joint authority declaration",
            status=ProposalStatus.ACCEPTED,
            base_revision=source_revision,
            base_state_hash=source_state_hash,
            actor=AUTHORITY_ACTOR,
            operations=(operation,),
        )
        source_state = self.state_manager._read_snapshot(self.project_id, source_revision).state
        self._validate_canonical_references(source_state, declaration)
        expected_state = source_state.model_copy(
            update={
                "revision": source_revision + 1,
                "joint_authority_declarations": [
                    *source_state.joint_authority_declarations,
                    record,
                ],
            }
        )
        return _Compiled(
            proposal=proposal,
            changeset_id=changeset_id,
            expected_state=expected_state,
            expected_state_hash=state_hash(expected_state),
        )

    def _replay(
        self,
        admission_run_id,
        source_revision,
        source_state_hash,
        expected_state,
        expected_state_hash,
        proposal,
        changeset_id,
    ) -> JointAuthorityAdmissionResult:
        current = self.state_manager.load_current_pointer(self.project_id)
        if (
            current["revision"] != source_revision + 1
            or current["state_hash"] != expected_state_hash
        ):
            raise ValueError("canonical replay state does not match expected N+1")
        snapshot = self.state_manager._read_snapshot(
            self.project_id, source_revision + 1
        )
        if snapshot.state_hash != expected_state_hash or snapshot.state != expected_state:
            raise ValueError("canonical replay snapshot mismatch")
        run = self.run_controller.get_run(admission_run_id, self.project_id)
        if (
            run.active_revision != source_revision + 1
            or run.active_state_hash != expected_state_hash
            or expected_state_hash not in run.state_hash_history
            or source_state_hash not in run.state_hash_history
        ):
            raise ValueError("admission run replay state history is incomplete")
        revision_event = self._find_revision_advanced_event(
            admission_run_id, source_revision + 1
        )
        if revision_event is None:
            raise ValueError("revision advancement evidence is missing")
        invalidation = self.run_controller.evidence.load_invalidation(
            self.project_id, source_revision + 1
        )
        expected_paths = (proposal.operations[0].path,)
        expected_impact = self.run_controller.evidence.build_invalidation(
            self.project_id,
            source_revision + 1,
            source_revision,
            expected_paths,
            changeset_id,
        )
        if (
            invalidation.project_id != expected_impact.project_id
            or invalidation.revision != expected_impact.revision
            or invalidation.parent_revision != expected_impact.parent_revision
            or invalidation.changeset_id != expected_impact.changeset_id
            or invalidation.changed_paths != expected_impact.changed_paths
            or invalidation.directly_invalidated_nodes
            != expected_impact.directly_invalidated_nodes
            or invalidation.transitively_invalidated_nodes
            != expected_impact.transitively_invalidated_nodes
        ):
            raise ValueError("canonical replay invalidation provenance mismatch")
        return JointAuthorityAdmissionResult(
            replayed=True,
            revision=source_revision + 1,
            state_hash=expected_state_hash,
            proposal=proposal,
            changeset_id=changeset_id,
        )

    def _load_source(
        self,
        admission_run_id: str,
        source_revision: int,
        source_state_hash: str,
    ) -> dict:
        run = self.run_controller.get_run(admission_run_id, self.project_id)
        manifest = self.run_store.load_manifest(self.project_id, admission_run_id)
        current = self.state_manager.load_current_pointer(self.project_id)
        if (
            manifest.run_id != admission_run_id
            or manifest.project_id != self.project_id
            or run.run_id != admission_run_id
            or run.project_id != self.project_id
            or manifest.initial_revision != run.initial_revision
            or manifest.initial_state_hash != run.initial_state_hash
            or run.initial_revision != source_revision
            or run.initial_state_hash != source_state_hash
        ):
            raise ValueError("invalid admission run provenance")
        if (
            current["revision"] != source_revision
            or current["state_hash"] != source_state_hash
        ):
            raise ValueError("admission source is stale")
        snapshot = self.state_manager._read_snapshot(self.project_id, source_revision)
        if snapshot.state_hash != source_state_hash:
            raise ValueError("admission source snapshot hash mismatch")
        return {"revision": source_revision, "state_hash": source_state_hash}

    def _required_limitation_kinds(self, authority_kind: str) -> set[str]:
        required: set[str] = set()
        for rule in self.policy.rules:
            if rule.authority_kind == authority_kind:
                required.update(rule.required_bounded_limitation_kinds)
        return required

    def _validate_canonical_references(
        self, source_state: DesignState, declaration: JointAuthorityDeclaration
    ) -> None:
        """Fail closed on any ``canonical_component_identity`` ref that does not
        resolve to a canonical component or specification present in the source
        state at the admission revision. Self-contained and synthetic references
        require only declaration-internal consistency (already validated by the
        model)."""
        resolvable: set[str] = set()
        for mechanism in source_state.physical_mechanisms:
            resolvable.update(
                component.instance_id for component in mechanism.components
            )
            resolvable.update(
                specification.specification_hash
                for specification in mechanism.component_specifications
            )
        for constituent in declaration.constituents:
            reference = constituent.component_ref
            if reference.ref_kind is ComponentReferenceKind.CANONICAL_COMPONENT_IDENTITY:
                if reference.canonical_component_id not in resolvable:
                    raise ValueError(
                        "joint authority canonical component reference does not "
                        "resolve in the source state"
                    )

    def _policy_hash(self) -> str:
        from mechcad_harness.core.canonical import canonical_json_bytes

        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.policy.model_dump(mode="json"))
        ).hexdigest()

    def _find_revision_advanced_event(self, run_id: str, revision: int) -> RunEvent | None:
        events_dir = self.run_store.run_dir(self.project_id, run_id) / "events"
        if not events_dir.exists():
            return None
        for path in sorted(events_dir.glob("EVT-*.json"), key=lambda item: item.name):
            try:
                event = self.run_store._read(path, RunEvent)
            except Exception as exc:
                raise ValueError("malformed admission run event") from exc
            if event.event_type == "REVISION_ADVANCED" and event.payload == {"revision": revision}:
                return event
        return None
