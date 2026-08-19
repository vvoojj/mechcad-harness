from uuid import uuid5, NAMESPACE_URL

from .persistence import AgentStore
from .tool_mediation import AgentToolMediationMode
from mechcad_harness.tools.evidence import ToolEvidenceMaterializer


class TransmissionToolRoundTripResult:
    def __init__(self, status, *, failure_kind=None, evidence_id=None):
        self.status = status
        self.failure_kind = failure_kind
        self.evidence_id = evidence_id


class TransmissionToolRoundTripCoordinator:
    def __init__(self, controller, gateway, registry):
        self.controller = controller
        self.gateway = gateway
        self.registry = registry

    def run(self, run_id, task_id, agent_name, agent_version, *, selected_requirement_ids=(), selected_constraint_ids=()):
        run = self.controller.get_run(run_id)
        definition = self.controller.store.load_task_definition(run.project_id, run_id, task_id)
        workflow_id = f"RTR-{uuid5(NAMESPACE_URL, f'mechcad:roundtrip:{run.project_id}:{run_id}:{task_id}:{agent_name}:{agent_version}') }"
        self._write_transition(run.project_id, run_id, workflow_id, "00_started", {"workflow_id": workflow_id, "project_id": run.project_id, "run_id": run_id, "task_id": task_id, "bound_revision": definition.bound_revision, "bound_state_hash": definition.bound_state_hash})
        result_a = self.gateway.invoke(run_id, task_id, agent_name, agent_version, selected_requirement_ids=selected_requirement_ids, selected_constraint_ids=selected_constraint_ids, mediation_mode=AgentToolMediationMode.ENABLED)
        if result_a.status.value != "succeeded":
            invocation_a = AgentStore(self.controller.workspace).load_invocation(run.project_id, run_id, result_a.invocation_id)
            self._write_transition(run.project_id, run_id, workflow_id, "10_invocation_a_failure", {
                "workflow_id": workflow_id,
                "failure_kind": "INVOCATION_A_FAILED",
                "invocation_a_id": result_a.invocation_id,
                "agent_result_a_id": result_a.result_id,
                "response_contract": invocation_a.request.response_contract.value,
                "response_schema_hash": invocation_a.request.response_schema_hash,
                "bound_revision": definition.bound_revision,
                "bound_state_hash": definition.bound_state_hash,
            })
            return TransmissionToolRoundTripResult("failed", failure_kind="INVOCATION_A_FAILED")
        store = AgentStore(self.controller.workspace)
        observation_a = store.load_tool_request_observation(run.project_id, run_id, result_a.invocation_id)
        if len(observation_a.tool_requests) != 1:
            return TransmissionToolRoundTripResult("failed", failure_kind="NO_TOOL_REQUEST" if not observation_a.tool_requests else "TOO_MANY_TOOL_REQUESTS")
        self._write_transition(run.project_id, run_id, workflow_id, "10_invocation_a", {"workflow_id": workflow_id, "invocation_a_id": result_a.invocation_id, "agent_result_a_id": result_a.result_id, "observation_id": observation_a.observation_id})
        mediation = self._load_mediation_for_invocation(run.project_id, run_id, result_a.invocation_id)
        if mediation is None or mediation.status != "succeeded" or not mediation.tool_result_id:
            return TransmissionToolRoundTripResult("failed", failure_kind="MEDIATED_TOOL_FAILED")
        tool_result = self._load_tool_result(run.project_id, run_id, mediation.tool_result_id)
        self._write_transition(run.project_id, run_id, workflow_id, "20_tool_result", {
            "workflow_id": workflow_id,
            "invocation_a_id": result_a.invocation_id,
            "agent_result_a_id": result_a.result_id,
            "observation_id": observation_a.observation_id,
            "mediation_id": mediation.mediation_id,
            "tool_call_id": mediation.tool_call_id,
            "tool_result_id": tool_result.result_id,
            "bound_revision": definition.bound_revision,
            "bound_state_hash": definition.bound_state_hash,
        })
        if not self._binding_current(run_id, task_id, definition.bound_revision, definition.bound_state_hash):
            return TransmissionToolRoundTripResult("failed", failure_kind="STALE_BEFORE_EVIDENCE")
        evidence = ToolEvidenceMaterializer(self.controller, self.gateway.tool_mediator.broker.registry).materialize_from_result(run.project_id, run_id, task_id, mediation.tool_result_id, "analysis.transmission.torque", definition.bound_revision, definition.bound_state_hash)
        if not self._binding_current(run_id, task_id, definition.bound_revision, definition.bound_state_hash) or not self.controller.evidence.is_evidence_fresh(run.project_id, evidence.id):
            return TransmissionToolRoundTripResult("failed", failure_kind="EVIDENCE_NOT_CURRENT")
        self._write_transition(run.project_id, run_id, workflow_id, "30_evidence", {"workflow_id": workflow_id, "evidence_id": evidence.id, "mediation_id": mediation.mediation_id, "tool_result_id": mediation.tool_result_id})
        result_b = self.gateway.invoke(run_id, task_id, agent_name, agent_version, selected_evidence_ids=(evidence.id,), selected_requirement_ids=selected_requirement_ids, selected_constraint_ids=selected_constraint_ids, mediation_mode=AgentToolMediationMode.DISABLED)
        if result_b.invocation_id == result_a.invocation_id:
            raise RuntimeError("gateway did not create a fresh Invocation B")
        if result_b.status.value != "succeeded":
            invocation_b = store.load_invocation(run.project_id, run_id, result_b.invocation_id)
            self._write_transition(run.project_id, run_id, workflow_id, "40_invocation_b_failure", {
                "workflow_id": workflow_id,
                "failure_kind": "INVOCATION_B_FAILED",
                "invocation_b_id": result_b.invocation_id,
                "agent_result_b_id": result_b.result_id,
                "evidence_id": evidence.id,
                "mediation_id": mediation.mediation_id,
                "tool_call_id": mediation.tool_call_id,
                "tool_result_id": mediation.tool_result_id,
                "response_contract": invocation_b.request.response_contract.value,
                "response_schema_hash": invocation_b.request.response_schema_hash,
                "bound_revision": definition.bound_revision,
                "bound_state_hash": definition.bound_state_hash,
            })
            return TransmissionToolRoundTripResult("failed", failure_kind="INVOCATION_B_FAILED", evidence_id=evidence.id)
        observation_b = store.load_tool_request_observation(run.project_id, run_id, result_b.invocation_id)
        self._write_transition(run.project_id, run_id, workflow_id, "40_invocation_b", {"workflow_id": workflow_id, "invocation_b_id": result_b.invocation_id, "agent_result_b_id": result_b.result_id, "observation_id": observation_b.observation_id})
        if observation_b.tool_requests:
            self._write_transition(run.project_id, run_id, workflow_id, "40_invocation_b_failure", {
                "workflow_id": workflow_id,
                "failure_kind": "SECOND_TOOL_REQUEST",
                "invocation_b_id": result_b.invocation_id,
                "agent_result_b_id": result_b.result_id,
                "observation_id": observation_b.observation_id,
                "evidence_id": evidence.id,
                "mediation_id": mediation.mediation_id,
                "tool_call_id": mediation.tool_call_id,
                "tool_result_id": mediation.tool_result_id,
                "bound_revision": definition.bound_revision,
                "bound_state_hash": definition.bound_state_hash,
            })
            return TransmissionToolRoundTripResult("failed", failure_kind="SECOND_TOOL_REQUEST", evidence_id=evidence.id)
        if result_b.status.value != "succeeded":
            return TransmissionToolRoundTripResult("failed", failure_kind="INVOCATION_B_FAILED", evidence_id=evidence.id)
        self._write_transition(run.project_id, run_id, workflow_id, "50_complete", {"workflow_id": workflow_id, "evidence_id": evidence.id, "agent_result_b_id": result_b.result_id})
        return TransmissionToolRoundTripResult("complete", evidence_id=evidence.id)

    def _binding_current(self, run_id, task_id, revision, state_hash):
        run = self.controller.get_run(run_id)
        definition = self.controller.store.load_task_definition(run.project_id, run_id, task_id)
        return run.active_revision == revision and run.active_state_hash == state_hash and definition.bound_revision == revision and definition.bound_state_hash == state_hash

    def _load_mediation(self, project_id, run_id, mediation_id):
        from .tool_mediation import ToolMediationRecord
        path = self.controller.workspace / "projects" / project_id / "runs" / run_id / "agents" / "tool_mediation" / mediation_id / "final.json"
        if not path.exists():
            return None
        return ToolMediationRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def _load_mediation_for_invocation(self, project_id, run_id, invocation_id):
        root = self.controller.workspace / "projects" / project_id / "runs" / run_id / "agents" / "tool_mediation"
        matches = []
        for path in root.glob("*/final.json"):
            from .tool_mediation import ToolMediationRecord
            record = ToolMediationRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if record.invocation_id == invocation_id:
                matches.append(record)
        return matches[0] if len(matches) == 1 else None

    def _load_tool_result(self, project_id, run_id, result_id):
        from mechcad_harness.tools.persistence import ToolStore
        return ToolStore(self.controller.workspace).load_result(project_id, run_id, result_id)

    def resume(self, run_id, task_id, agent_name, agent_version):
        import json
        run = self.controller.get_run(run_id)
        workflow_id = f"RTR-{uuid5(NAMESPACE_URL, f'mechcad:roundtrip:{run.project_id}:{run_id}:{task_id}:{agent_name}:{agent_version}') }"
        directory = self.controller.workspace / "projects" / run.project_id / "runs" / run_id / "agents" / "roundtrips" / workflow_id
        failure_path = directory / "40_invocation_b_failure.json"
        if failure_path.exists():
            payload = json.loads(failure_path.read_text(encoding="utf-8"))
            return TransmissionToolRoundTripResult("failed", failure_kind=payload["failure_kind"], evidence_id=payload.get("evidence_id"))
        failure_path = directory / "10_invocation_a_failure.json"
        if failure_path.exists():
            payload = json.loads(failure_path.read_text(encoding="utf-8"))
            return TransmissionToolRoundTripResult("failed", failure_kind=payload["failure_kind"])
        complete_path = directory / "50_complete.json"
        if complete_path.exists():
            payload = json.loads(complete_path.read_text(encoding="utf-8"))
            return TransmissionToolRoundTripResult("complete", evidence_id=payload["evidence_id"])
        raise ValueError("round-trip recovery is only defined for terminal workflows")

    def _write_transition(self, project_id, run_id, workflow_id, name, payload):
        path = self.controller.workspace / "projects" / project_id / "runs" / run_id / "agents" / "roundtrips" / workflow_id / f"{name}.json"
        self.controller.store._write(path, payload, exclusive=True)
