from mechcad_harness.state.hashing import state_hash
from mechcad_harness.dependency.models import EvidenceFreshness

from .models import AgentContext, AgentEvidenceSummary


class ContextBuilder:
    def __init__(self, controller):
        self.controller = controller

    def build(self, run_id: str, task_id: str, *, selected_evidence_ids: tuple[str, ...] = (), selected_requirement_ids: tuple[str, ...] = (), selected_constraint_ids: tuple[str, ...] = ()) -> AgentContext:
        run = self.controller.get_run(run_id)
        definition = self.controller.store.load_task_definition(run.project_id, run_id, task_id)
        state = self.controller.state_manager.load_revision(run.project_id, definition.bound_revision)
        if definition.run_id != run_id or definition.bound_revision != run.active_revision or definition.bound_state_hash != run.active_state_hash:
            raise ValueError("agent task binding is stale")
        if state_hash(state) != definition.bound_state_hash:
            raise ValueError("agent context state hash mismatch")
        evidence_summaries = []
        for evidence_id in selected_evidence_ids:
            evidence = self.controller.evidence.load_evidence(run.project_id, evidence_id)
            if evidence.revision != definition.bound_revision or evidence.state_hash != definition.bound_state_hash:
                raise ValueError("evidence binding mismatch")
            freshness = self.controller.evidence.get_evidence_freshness(run.project_id, evidence_id)
            if freshness is not EvidenceFreshness.CURRENT:
                raise ValueError(f"evidence is not current: {evidence_id}")
            evidence_summaries.append(AgentEvidenceSummary(evidence_id=evidence.id, dependency_node=evidence.kind, bound_revision=evidence.revision, bound_state_hash=evidence.state_hash, freshness=freshness.value, summary=evidence.summary, source_tool_name=evidence.producer_name, source_tool_version=evidence.producer_version, source_result_id=evidence.producer_result_id))
        requirements = []
        for requirement_id in selected_requirement_ids:
            match = next((item for item in state.requirements if item.id == requirement_id), None)
            if match is None:
                raise ValueError(f"requirement not found: {requirement_id}")
            requirements.append(match.description)
        constraints = []
        for constraint_id in selected_constraint_ids:
            match = next((item for item in state.constraints if item.id == constraint_id), None)
            if match is None:
                raise ValueError(f"constraint not found: {constraint_id}")
            constraints.append(match.expression)
        return AgentContext(project_id=run.project_id, run_id=run_id, task_id=task_id, revision=definition.bound_revision, state_hash=definition.bound_state_hash, design_state=state.model_copy(deep=True), task_objective=definition.objective, task_instructions=definition.objective, requirements=tuple(requirements), constraints=tuple(constraints), evidence_summaries=tuple(evidence_summaries))
