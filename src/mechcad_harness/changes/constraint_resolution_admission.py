import ast
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.agents.constraint_requests import (
    ConstraintRequestMaterializer,
    ConstraintRequestStore,
    ConstraintRequestLifecycle,
)
from mechcad_harness.agents.constraint_resolution import (
    ConstraintResolutionBatchCommand,
    ConstraintResolutionRecord,
    ConstraintResolutionStore,
    canonical_record_equivalent,
    canonical_value_for_answer,
    parameter_id,
    resolution_id,
)
from mechcad_harness.engineering.keys import SupportedConstraintKey
from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter
from mechcad_harness.models.proposal import ChangeProposal, ProposalStatus
from mechcad_harness.changes.operations import ChangeOperation, OperationType
from mechcad_harness.models.common import Model
from mechcad_harness.runs.models import RunEvent
from mechcad_harness.runs.persistence import RunStore
from mechcad_harness.state.hashing import state_hash


def _nonempty(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty")
    return value


class ConstraintResolutionAdmissionRule(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resolver_type: str = Field(min_length=1)
    resolver_id: str = Field(min_length=1)
    engineering_scope_id: str = Field(min_length=1)
    allowed_keys: tuple[SupportedConstraintKey, ...] = Field(min_length=1)

    @field_validator("resolver_type", "resolver_id", "engineering_scope_id")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        return _nonempty(value)

    @model_validator(mode="after")
    def reject_duplicate_keys(self):
        if len(self.allowed_keys) != len(set(self.allowed_keys)):
            raise ValueError("admission rule contains duplicate keys")
        return self


class ConstraintResolutionAdmissionPolicy(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str = Field(min_length=1)
    rules: tuple[ConstraintResolutionAdmissionRule, ...] = ()

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return _nonempty(value)

    @model_validator(mode="after")
    def reject_duplicate_rule_identities(self):
        identities = [
            (rule.resolver_type, rule.resolver_id, rule.engineering_scope_id)
            for rule in self.rules
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("admission policy contains duplicate rule identities")
        return self

    @classmethod
    def deny_all(cls, project_id: str) -> "ConstraintResolutionAdmissionPolicy":
        return cls(project_id=project_id, rules=())

    def for_project(self, project_id: str) -> "ConstraintResolutionAdmissionPolicy":
        if project_id != self.project_id:
            raise ValueError("constraint resolution admission policy project mismatch")
        return self

    def allows(
        self,
        *,
        resolver_type: str,
        resolver_id: str,
        engineering_scope_id: str,
        keys: tuple[SupportedConstraintKey | str, ...],
    ) -> bool:
        try:
            requested = {SupportedConstraintKey(key) for key in keys}
        except (TypeError, ValueError):
            return False
        for rule in self.rules:
            if (
                rule.resolver_type == resolver_type
                and rule.resolver_id == resolver_id
                and rule.engineering_scope_id == engineering_scope_id
                and requested
                and requested.issubset(set(rule.allowed_keys))
            ):
                return True
        return False

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        project_id: str,
    ) -> "ConstraintResolutionAdmissionPolicy":
        payload = _read_policy_file(path)
        if payload.get("project_id") != project_id:
            raise ValueError("constraint resolution admission policy project mismatch")
        try:
            return cls.model_validate(payload).for_project(project_id)
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc):
                raise
            raise ValueError("invalid constraint resolution admission policy") from exc


def _read_policy_file(path: str | Path) -> dict:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("unable to read constraint resolution admission policy") from exc
    try:
        if text.lstrip().startswith("{"):
            payload = json.loads(text)
        else:
            payload = _parse_simple_yaml(text)
    except (SyntaxError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid constraint resolution admission policy") from exc
    if not isinstance(payload, dict) or set(payload) - {"project_id", "rules"}:
        raise ValueError("invalid constraint resolution admission policy fields")
    if not isinstance(payload.get("rules", ()), list):
        raise ValueError("admission policy rules must be a list")
    return payload


def _parse_simple_yaml(text: str) -> dict:
    result: dict = {}
    rules: list[dict] = []
    current: dict | None = None
    in_rules = False
    in_allowed_keys = False
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "rules:":
            in_rules = True
            in_allowed_keys = False
            continue
        if not in_rules:
            if ":" not in stripped:
                raise ValueError("invalid policy field")
            key, value = stripped.split(":", 1)
            result[key.strip()] = _yaml_scalar(value.strip())
            continue
        if stripped.startswith("- ") and ":" in stripped:
            key, value = stripped[2:].split(":", 1)
            if key.strip() in {"resolver_type", "resolver_id", "engineering_scope_id"}:
                current = {}
                rules.append(current)
                in_allowed_keys = False
                current[key.strip()] = _yaml_scalar(value.strip())
            elif key.strip() == "allowed_keys" and current is not None:
                current["allowed_keys"] = _yaml_scalar(value.strip())
                in_allowed_keys = True
            else:
                raise ValueError("invalid admission rule")
            continue
        if stripped.startswith("- ") and in_allowed_keys and current is not None:
            current.setdefault("allowed_keys", []).append(_yaml_scalar(stripped[2:].strip()))
            continue
        if ":" not in stripped or current is None:
            raise ValueError("invalid admission rule")
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key == "allowed_keys":
            current[key] = _yaml_scalar(value.strip())
            in_allowed_keys = True
        elif key in {"resolver_type", "resolver_id", "engineering_scope_id"}:
            current[key] = _yaml_scalar(value.strip())
            in_allowed_keys = False
        else:
            raise ValueError("invalid admission rule field")
    result["rules"] = rules
    return result


def _yaml_scalar(value: str):
    if not value:
        return None
    if value.startswith("["):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
    return value.strip("\"'")


AUTHORITY_ACTOR = "mechcad-authority-admission"


@dataclass(frozen=True)
class ConstraintResolutionCompilationResult:
    proposal: ChangeProposal
    changeset_id: str
    resolution_ids: tuple[str, ...]
    parameter_ids: tuple[str, ...]
    parameters: tuple[AuthoritativeParameter, ...]


@dataclass(frozen=True)
class ConstraintResolutionAdmissionResult:
    replayed: bool
    revision: int
    state_hash: str
    proposal: ChangeProposal
    changeset_id: str
    resolution_ids: tuple[str, ...]
    parameter_ids: tuple[str, ...]


class ConstraintResolutionAdmissionService:
    def __init__(self, *, project_id, state_manager, run_controller, policy):
        self.project_id = project_id
        self.state_manager = state_manager
        self.run_controller = run_controller
        self.policy = policy.for_project(project_id)
        self.run_store = RunStore(state_manager.workspace)
        self.request_store = ConstraintRequestStore(state_manager.workspace)
        self.resolution_store = ConstraintResolutionStore(state_manager.workspace)

    def compile_batch(
        self, resolution_run_id: str, command_id: str, *, allow_replay: bool = False
    ) -> ConstraintResolutionCompilationResult:
        command, run, source = self._load_source(
            command_run_id=resolution_run_id,
            command_id=command_id,
            require_current=not allow_replay,
        )
        expected = {
            resolution_id(
                project_id=self.project_id,
                source_request_id=answer.request_id,
                source_revision=command.source_revision,
                source_state_hash=command.source_state_hash,
                answer=answer.answer,
            ): answer
            for answer in command.answers
        }
        records = self.resolution_store.load_command_scoped_resolutions(
            self.project_id, resolution_run_id, command.command_id
        )
        if len(records) != len({record.resolution_id for record in records}):
            raise ValueError("duplicate command-scoped resolution records")
        if {record.resolution_id for record in records} != set(expected):
            raise ValueError("command-scoped resolution set does not match command")
        by_id = {record.resolution_id: record for record in records}
        validated: list[tuple[ConstraintResolutionRecord, AuthoritativeParameter]] = []
        for expected_id, answer in expected.items():
            record = by_id[expected_id]
            self._validate_record(command, resolution_run_id, answer.request_id, answer, record)
            request = self.request_store.load(self.project_id, resolution_run_id, answer.request_id)
            self._validate_request_and_task(
                command, resolution_run_id, answer.request_id, request, record.key
            )
            self._validate_project_provenance(record)
            anchor_kind, anchor_id = ConstraintRequestMaterializer.anchor_for(record.key)
            collection = source.requirements if anchor_kind == "requirement" else source.constraints
            anchors = [item for item in collection if item.id == anchor_id]
            if len(anchors) != 1:
                raise ValueError("canonical source anchor is missing or duplicated")
            target_id = parameter_id(
                project_id=self.project_id,
                scope_id=command.engineering_scope_id,
                anchor_kind=anchor_kind,
                anchor_id=anchor_id,
                key=record.key,
            )
            parameter = AuthoritativeParameter(
                id=target_id,
                anchor=AuthoritativeAnchor(kind=anchor_kind, id=anchor_id),
                scope_id=command.engineering_scope_id,
                key=record.key,
                value=record.canonical_value,
                source_resolution_id=record.resolution_id,
            )
            validated.append((record, parameter))

        if not self.policy.allows(
            resolver_type=command.resolver_type,
            resolver_id=command.resolver_id,
            engineering_scope_id=command.engineering_scope_id,
            keys=tuple(record.key for record, _ in validated),
        ):
            raise ValueError("constraint resolution batch is not authorized")
        parameter_ids = [parameter.id for _, parameter in validated]
        if len(parameter_ids) != len(set(parameter_ids)):
            raise ValueError("duplicate authoritative parameter targets")
        occupied_ids = {item.id for item in source.authoritative_parameters}
        if any(parameter_id_value in occupied_ids for parameter_id_value in parameter_ids):
            raise ValueError("authoritative parameter target is already occupied")

        ordered = sorted(validated, key=lambda item: item[1].id)
        pairs = tuple((record.resolution_id, parameter.id) for record, parameter in ordered)
        proposal_id_value, changeset_id_value = deterministic_admission_ids(
            project_id=self.project_id,
            resolution_run_id=resolution_run_id,
            command_id=command.command_id,
            source_revision=command.source_revision,
            source_state_hash=command.source_state_hash,
            pairs=pairs,
        )
        operations = [
            ChangeOperation(
                operation=OperationType.ADD,
                path=f"/authoritative_parameters/{parameter.id}",
                value=parameter.model_dump(mode="json"),
            )
            for _, parameter in ordered
        ]
        proposal = ChangeProposal(
            id=proposal_id_value,
            title="Admit constraint resolution batch",
            status=ProposalStatus.ACCEPTED,
            base_revision=command.source_revision,
            base_state_hash=command.source_state_hash,
            actor=AUTHORITY_ACTOR,
            operations=operations,
        )
        return ConstraintResolutionCompilationResult(
            proposal=proposal,
            changeset_id=changeset_id_value,
            resolution_ids=tuple(record.resolution_id for record, _ in ordered),
            parameter_ids=tuple(parameter.id for _, parameter in ordered),
            parameters=tuple(parameter for _, parameter in ordered),
        )

    def admit_batch(
        self, resolution_run_id: str, command_id: str
    ) -> ConstraintResolutionAdmissionResult:
        with self.state_manager.project_lock(self.project_id):
            command = self.resolution_store.load_command(
                self.project_id, resolution_run_id, command_id
            )
            current = self.state_manager.load_current_pointer(self.project_id)
            if (
                current["revision"] == command.source_revision
                and current["state_hash"] == command.source_state_hash
            ):
                compiled = self.compile_batch(resolution_run_id, command_id)
                payload = self._prepared_payload(
                    resolution_run_id, command, compiled
                )
                self._ensure_prepared_event(
                    resolution_run_id, command_id, payload, append=True
                )
                updated = self.run_controller.apply_approved_proposal(
                    resolution_run_id,
                    compiled.proposal,
                    changeset_id=compiled.changeset_id,
                )
                return ConstraintResolutionAdmissionResult(
                    replayed=False,
                    revision=updated.active_revision,
                    state_hash=updated.active_state_hash,
                    proposal=compiled.proposal,
                    changeset_id=compiled.changeset_id,
                    resolution_ids=compiled.resolution_ids,
                    parameter_ids=compiled.parameter_ids,
                )
            return self._replay_batch(resolution_run_id, command_id)

    def _load_source(self, *, command_run_id: str, command_id: str, require_current: bool):
        command = self.resolution_store.load_command(self.project_id, command_run_id, command_id)
        if command.project_id != self.project_id or command.command_id != command_id:
            raise ValueError("constraint resolution command identity mismatch")
        run = self.run_controller.get_run(command_run_id, self.project_id)
        manifest = self.run_store.load_manifest(self.project_id, command_run_id)
        if (
            manifest.run_id != command_run_id
            or manifest.project_id != self.project_id
            or run.run_id != command_run_id
            or run.project_id != self.project_id
            or manifest.initial_revision != run.initial_revision
            or manifest.initial_state_hash != run.initial_state_hash
        ):
            raise ValueError("invalid constraint resolution source run provenance")
        current = self.state_manager.load_current_pointer(self.project_id)
        if require_current and (
            run.active_revision != command.source_revision
            or run.active_state_hash != command.source_state_hash
            or current["revision"] != command.source_revision
            or current["state_hash"] != command.source_state_hash
        ):
            raise ValueError("constraint resolution source is stale")
        source = self.state_manager._read_snapshot(self.project_id, command.source_revision)
        if source.state_hash != command.source_state_hash:
            raise ValueError("constraint resolution source snapshot hash mismatch")
        return command, run, source.state

    @staticmethod
    def _prepared_payload(resolution_run_id, command, compiled):
        return {
            "resolution_run_id": resolution_run_id,
            "command_id": command.command_id,
            "resolution_ids": list(compiled.resolution_ids),
            "parameter_ids": list(compiled.parameter_ids),
            "proposal_id": compiled.proposal.id,
            "changeset_id": compiled.changeset_id,
            "base_revision": command.source_revision,
            "base_state_hash": command.source_state_hash,
        }

    def _ensure_prepared_event(
        self, resolution_run_id: str, command_id: str, payload: dict, *, append: bool
    ) -> RunEvent:
        events_dir = self.run_store.run_dir(self.project_id, resolution_run_id) / "events"
        matches = []
        if events_dir.exists():
            for path in sorted(events_dir.glob("EVT-*.json"), key=lambda item: item.name):
                try:
                    event = self.run_store._read(path, RunEvent)
                except Exception as exc:
                    raise ValueError("malformed source run event") from exc
                if event.event_type != "CONSTRAINT_RESOLUTION_BATCH_PREPARED":
                    continue
                if event.payload.get("resolution_run_id") != resolution_run_id:
                    continue
                if event.payload.get("command_id") != command_id:
                    continue
                if event.payload != payload:
                    raise ValueError("conflicting prepared constraint resolution event")
                matches.append(event)
        if len(matches) > 1:
            raise ValueError("multiple prepared constraint resolution events")
        if matches:
            return matches[0]
        if not append:
            raise ValueError("prepared constraint resolution event is missing")
        return self.run_store.append_event(
            self.project_id,
            resolution_run_id,
            "CONSTRAINT_RESOLUTION_BATCH_PREPARED",
            payload,
        )

    def _replay_batch(self, resolution_run_id: str, command_id: str):
        compiled = self.compile_batch(
            resolution_run_id, command_id, allow_replay=True
        )
        command = self.resolution_store.load_command(
            self.project_id, resolution_run_id, command_id
        )
        prepared_payload = self._prepared_payload(
            resolution_run_id, command, compiled
        )
        self._ensure_prepared_event(
            resolution_run_id, command_id, prepared_payload, append=False
        )
        target_revision = command.source_revision + 1
        expected_state = self.state_manager.load_revision(
            self.project_id, command.source_revision
        ).model_copy(
            update={
                "revision": target_revision,
                "authoritative_parameters": [
                    *self.state_manager.load_revision(
                        self.project_id, command.source_revision
                    ).authoritative_parameters,
                    *compiled.parameters,
                ],
            }
        )
        expected_hash = state_hash(expected_state)
        current = self.state_manager.load_current_pointer(self.project_id)
        if current["revision"] != target_revision or current["state_hash"] != expected_hash:
            raise ValueError("canonical replay state does not match expected N+1")
        snapshot = self.state_manager._read_snapshot(self.project_id, target_revision)
        if snapshot.state_hash != expected_hash or snapshot.state != expected_state:
            raise ValueError("canonical replay snapshot mismatch")
        run = self.run_controller.get_run(resolution_run_id, self.project_id)
        if (
            run.active_revision != target_revision
            or run.active_state_hash != expected_hash
            or expected_hash not in run.state_hash_history
            or command.source_state_hash not in run.state_hash_history
        ):
            raise ValueError("source run replay state history is incomplete")
        revision_event = self._find_revision_advanced_event(
            resolution_run_id, target_revision
        )
        if revision_event is None:
            raise ValueError("revision advancement evidence is missing")
        invalidation = self.run_controller.evidence.load_invalidation(
            self.project_id, target_revision
        )
        expected_paths = tuple(operation.path for operation in compiled.proposal.operations)
        expected_impact = self.run_controller.evidence.build_invalidation(
            self.project_id,
            target_revision,
            command.source_revision,
            expected_paths,
            compiled.changeset_id,
        )
        if (
            invalidation.project_id != expected_impact.project_id
            or invalidation.revision != expected_impact.revision
            or invalidation.parent_revision != expected_impact.parent_revision
            or invalidation.changeset_id != expected_impact.changeset_id
            or invalidation.changed_paths != expected_impact.changed_paths
            or invalidation.directly_invalidated_nodes != expected_impact.directly_invalidated_nodes
            or invalidation.transitively_invalidated_nodes != expected_impact.transitively_invalidated_nodes
        ):
            raise ValueError("canonical replay invalidation provenance mismatch")
        return ConstraintResolutionAdmissionResult(
            replayed=True,
            revision=target_revision,
            state_hash=expected_hash,
            proposal=compiled.proposal,
            changeset_id=compiled.changeset_id,
            resolution_ids=compiled.resolution_ids,
            parameter_ids=compiled.parameter_ids,
        )

    def _find_revision_advanced_event(self, run_id: str, revision: int):
        events_dir = self.run_store.run_dir(self.project_id, run_id) / "events"
        if not events_dir.exists():
            return None
        for path in sorted(events_dir.glob("EVT-*.json"), key=lambda item: item.name):
            try:
                event = self.run_store._read(path, RunEvent)
            except Exception as exc:
                raise ValueError("malformed source run event") from exc
            if event.event_type == "REVISION_ADVANCED" and event.payload == {"revision": revision}:
                return event
        return None

    def _validate_record(self, command, run_id, request_id, answer, record):
        if record.status.value != "accepted":
            raise ValueError("constraint resolution record is not accepted")
        if (
            record.source_command_id != command.command_id
            or record.source_constraint_request_id != request_id
            or record.project_id != command.project_id
            or record.engineering_scope_id != command.engineering_scope_id
            or record.source_revision != command.source_revision
            or record.source_state_hash != command.source_state_hash
            or record.resolver_type != command.resolver_type
            or record.resolver_id != command.resolver_id
            or record.source_answer != answer.answer
            or record.key.value != answer.answer.kind
        ):
            raise ValueError("constraint resolution record binding mismatch")
        if canonical_value_for_answer(record.key, record.source_answer) != record.canonical_value:
            raise ValueError("canonical value does not match source answer")

    def _validate_request_and_task(self, command, run_id, request_id, request, key):
        if (
            request.project_id != self.project_id
            or request.run_id != run_id
            or request.request.id != request_id
            or request.engineering_scope_id != command.engineering_scope_id
            or request.request.revision != command.source_revision
            or request.request.state_hash != command.source_state_hash
            or request.key is not key
            or request.lifecycle is not ConstraintRequestLifecycle.DISCOVERED
        ):
            raise ValueError("constraint request binding mismatch")
        definition = self.run_store.load_task_definition(self.project_id, run_id, request.task_id)
        state = self.run_store.load_task_state(self.project_id, run_id, request.task_id)
        if (
            definition.run_id != run_id
            or definition.bound_revision != command.source_revision
            or definition.bound_state_hash != command.source_state_hash
            or state.task_id != request.task_id
            or state.bound_revision != definition.bound_revision
            or state.bound_state_hash != definition.bound_state_hash
        ):
            raise ValueError("constraint request task binding mismatch")

    def _validate_project_provenance(self, record):
        matches = self.resolution_store.load_unique_project_resolution(
            self.project_id, record.resolution_id
        )
        if not canonical_record_equivalent(matches, record):
            raise ValueError("project-wide resolution provenance mismatch")
        request_matches = self.resolution_store.load_project_resolutions_by_source_request(
            self.project_id, record.source_constraint_request_id
        )
        if len(request_matches) != 1 or not canonical_record_equivalent(request_matches[0], record):
            raise ValueError("conflicting project-wide source request resolution")


def deterministic_admission_ids(
    *,
    project_id: str,
    resolution_run_id: str,
    command_id: str,
    source_revision: int,
    source_state_hash: str,
    pairs: tuple[tuple[str, str], ...],
) -> tuple[str, str]:
    identity = json.dumps(
        {
            "project_id": project_id,
            "resolution_run_id": resolution_run_id,
            "command_id": command_id,
            "source_revision": source_revision,
            "source_state_hash": source_state_hash,
            "pairs": sorted(pairs),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    value = uuid5(NAMESPACE_URL, identity)
    return f"CRPROP-{value}", f"CRCS-{value}"
