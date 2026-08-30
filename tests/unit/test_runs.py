import json
from pathlib import Path

import pytest

from mechcad_harness.changes import ChangeEngine, ChangeOperation, OwnershipPolicy
from mechcad_harness.dependency import DependencyGraph, EvidenceFreshness, EvidenceStore
from mechcad_harness.models import ChangeProposal, Component, DesignState, Evidence, ProposalStatus
from mechcad_harness.runs import (
    ConvergenceError,
    FakeTaskExecutor,
    InvalidRunTransitionError,
    PostApplyInvalidationError,
    PostApplyRunTransitionError,
    RunController,
    RunStatus,
    StaleTaskResultError,
    TaskDependencyCycleError,
    TaskDependencyError,
    TaskDefinition,
    TaskStatus,
    TaskExecutionResult,
)
from mechcad_harness.runs.models import SourceBinding
from mechcad_harness.runs.errors import RunIntegrityError
from mechcad_harness.state import RevisionNotFoundError, StateManager


def make_state(name="Bracket", revision=1):
    return DesignState(id="DES-1", revision=revision, components=[Component(id="PRT-1", name=name)])


def dependency_file(tmp_path, *, rules=None):
    path = tmp_path / "dependencies.json"
    path.write_text(json.dumps({"rules": rules or [
        {"when": ["/components/*/name"], "invalidates": ["analysis.materials"]},
        {"when": ["/components/*/description"], "invalidates": ["analysis.packaging"]},
    ], "edges": []}), encoding="utf-8")
    return path


def make_controller(tmp_path, *, rules=None):
    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path, rules=rules))
    evidence = EvidenceStore(tmp_path, manager, graph)
    engine = ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}]))
    return RunController(tmp_path, manager, engine, evidence), snapshot


def task(controller, run, task_id, *, depends_on=(), produces=(), required=()):
    return controller.add_task(run.run_id, TaskDefinition(
        task_id=task_id,
        run_id=run.run_id,
        task_type="fake",
        objective=task_id,
        bound_revision=run.active_revision,
        bound_state_hash=run.active_state_hash,
        depends_on=tuple(depends_on),
        required_nodes=tuple(required),
        produces_nodes=tuple(produces),
    ))


def test_run_binds_exact_canonical_revision_and_manifest_is_immutable(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1", max_iterations=3)
    assert (run.initial_revision, run.initial_state_hash) == (snapshot.revision, snapshot.state_hash)
    manifest = tmp_path / "projects/PRJ-1/runs" / run.run_id / "manifest.json"
    original = manifest.read_bytes()
    with pytest.raises(Exception):
        controller.store.create_manifest(run.model_copy(update={"initial_revision": 9}))
    assert manifest.read_bytes() == original


def test_create_run_accepts_matching_expected_source_and_preserves_legacy_callers(tmp_path):
    controller, snapshot = make_controller(tmp_path)

    expected = SourceBinding(project_id="PRJ-1", revision=1, state_hash=snapshot.state_hash)
    bound = controller.create_run("PRJ-1", expected_source=expected)
    legacy = controller.create_run("PRJ-1")

    assert (bound.initial_revision, bound.initial_state_hash) == (1, snapshot.state_hash)
    assert (legacy.initial_revision, legacy.initial_state_hash) == (1, snapshot.state_hash)


def test_fail_run_persists_generic_failed_terminal_state(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1", expected_source=SourceBinding(
        project_id="PRJ-1", revision=snapshot.revision, state_hash=snapshot.state_hash
    ))

    failed = controller.fail_run(run.run_id, error="promotion decision publication failed")

    assert failed.status is RunStatus.FAILED
    assert failed.active_revision == snapshot.revision
    assert failed.active_state_hash == snapshot.state_hash
    assert controller.get_run(run.run_id).status is RunStatus.FAILED
    events = sorted((tmp_path / "projects/PRJ-1/runs" / run.run_id / "events").glob("*.json"))
    assert json.loads(events[-1].read_text(encoding="utf-8"))["event_type"] == "RUN_FAILED"


def test_create_run_missing_project_does_not_create_project_directory(tmp_path):
    controller, _ = make_controller(tmp_path)
    missing_project = "PRJ-missing"

    with pytest.raises(RevisionNotFoundError):
        controller.create_run(missing_project)

    assert not (tmp_path / "projects" / missing_project).exists()


@pytest.mark.parametrize("expected, error", [
    (SourceBinding(project_id="PRJ-1", revision=1, state_hash="sha256:" + "0" * 64), RunIntegrityError),
    (SourceBinding(project_id="PRJ-1", revision=2, state_hash="sha256:missing"), RevisionNotFoundError),
    (SourceBinding(project_id="OTHER", revision=1, state_hash="sha256:wrong"), RunIntegrityError),
])
def test_create_run_rejects_mismatched_expected_source(tmp_path, expected, error):
    controller, snapshot = make_controller(tmp_path)

    with pytest.raises(error):
        controller.create_run("PRJ-1", expected_source=expected)


def test_source_binding_rejects_blank_or_non_positive_values_and_is_frozen():
    with pytest.raises(ValueError):
        SourceBinding(project_id=" ", revision=1, state_hash="sha256:ok")
    with pytest.raises(ValueError):
        SourceBinding(project_id="PRJ-1", revision=0, state_hash="sha256:ok")
    with pytest.raises(ValueError):
        SourceBinding(project_id="PRJ-1", revision=1, state_hash=" ")

    binding = SourceBinding(project_id="PRJ-1", revision=1, state_hash="sha256:ok")
    with pytest.raises((TypeError, ValueError)):
        binding.revision = 2


def test_create_run_rejects_expected_source_when_current_pointer_advances(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    controller.state_manager.create_revision("PRJ-1", make_state(name="New"))
    expected = SourceBinding(project_id="PRJ-1", revision=1, state_hash=snapshot.state_hash)

    with pytest.raises(RunIntegrityError):
        controller.create_run("PRJ-1", expected_source=expected)


@pytest.mark.parametrize("current_contents", ["not-json\n", "[]\n", '{"project_id": "PRJ-1"}\n'])
def test_create_run_normalizes_malformed_expected_source_current_pointer(tmp_path, current_contents):
    controller, snapshot = make_controller(tmp_path)
    current = tmp_path / "projects/PRJ-1/current.json"
    current.write_text(current_contents, encoding="utf-8")
    expected = SourceBinding(project_id="PRJ-1", revision=1, state_hash=snapshot.state_hash)

    with pytest.raises(RunIntegrityError):
        controller.create_run("PRJ-1", expected_source=expected)


def test_manifest_contains_only_immutable_provenance(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1", max_iterations=3)
    manifest_path = tmp_path / "projects/PRJ-1/runs" / run.run_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert set(manifest) == {"created_at", "initial_revision", "initial_state_hash", "max_iterations", "project_id", "run_id", "schema_version"}
    assert not {"active_revision", "active_state_hash", "status", "iteration", "state_hash_history", "updated_at"}.intersection(manifest)


def test_manifest_stays_unchanged_while_mutable_state_advances(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", produces=("analysis.materials",))
    manifest_path = tmp_path / "projects/PRJ-1/runs" / run.run_id / "manifest.json"
    original = manifest_path.read_bytes()
    controller.create_plan(run.run_id)
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    controller.apply_approved_proposal(run.run_id, proposal)
    assert manifest_path.read_bytes() == original
    state = json.loads((manifest_path.parent / "state.json").read_text(encoding="utf-8"))
    assert state["active_revision"] == 2
    assert state["iteration"] == 1


def test_resume_uses_state_not_mutable_manifest_fields(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    controller.apply_approved_proposal(run.run_id, proposal)
    manifest_path = tmp_path / "projects/PRJ-1/runs" / run.run_id / "manifest.json"
    original = manifest_path.read_bytes()
    resumed = controller.resume_run("PRJ-1", run.run_id)
    assert resumed.active_revision == 2
    assert resumed.iteration == 1
    assert manifest_path.read_bytes() == original


def test_task_definition_is_immutable_and_state_is_separate(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    created = task(controller, run, "TASK-A")
    definition = tmp_path / "projects/PRJ-1/runs" / run.run_id / "tasks/TASK-A/definition.json"
    state = tmp_path / "projects/PRJ-1/runs" / run.run_id / "tasks/TASK-A/state.json"
    assert definition.exists() and state.exists()
    before = definition.read_bytes()
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    assert definition.read_bytes() == before
    assert controller.get_task(run.run_id, created.task_id).status is TaskStatus.SUCCEEDED


def test_scheduler_orders_tasks_and_blocks_failed_dependents(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-B", depends_on=("TASK-A",))
    task(controller, run, "TASK-A")
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor(failing_task_ids={"TASK-A"}))
    assert controller.get_task(run.run_id, "TASK-A").status is TaskStatus.FAILED
    assert controller.get_task(run.run_id, "TASK-B").status is TaskStatus.BLOCKED


def test_scheduler_rejects_unknown_dependencies_and_cycles(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", depends_on=("MISSING",))
    with pytest.raises(TaskDependencyError):
        controller.create_plan(run.run_id)

    controller, _ = make_controller(tmp_path / "cycle")
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", depends_on=("TASK-B",))
    task(controller, run, "TASK-B", depends_on=("TASK-A",))
    with pytest.raises(TaskDependencyCycleError):
        controller.create_plan(run.run_id)


def test_result_binding_mismatch_fails_closed(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A")
    result = TaskExecutionResult(task_id="WRONG", result_id="RES-1", bound_revision=1, bound_state_hash=run.active_state_hash)
    with pytest.raises(StaleTaskResultError):
        controller.accept_result(run.run_id, "TASK-A", result)


def test_completion_requires_current_evidence_and_old_unrelated_evidence_reuses(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", produces=("analysis.materials",))
    controller.create_plan(run.run_id, required_evidence_nodes=("analysis.materials",))
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    assert controller.evaluate_completion(run.run_id) is True

    proposal = ChangeProposal(
        id="CP-1", title="description", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/description", value="new")],
    )
    controller.apply_approved_proposal(run.run_id, proposal)
    assert controller.evaluate_completion(run.run_id) is True
    assert controller.evidence.get_evidence_freshness("PRJ-1", "RES-TASK-A-analysis.materials") is EvidenceFreshness.CURRENT


def test_revision_advancement_stales_pending_task_without_rebinding(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", produces=("analysis.materials",))
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    controller.apply_approved_proposal(run.run_id, proposal)
    stale = controller.get_task(run.run_id, "TASK-A")
    assert stale.status is TaskStatus.STALE
    assert stale.bound_revision == 1
    assert controller.get_run(run.run_id).active_revision == 2


def test_m3_failure_follows_canonical_revision_and_blocks_without_guessing_impact(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", produces=("analysis.materials",))
    controller.evidence.record_invalidation = lambda record: (_ for _ in ()).throw(RuntimeError("disk failure"))
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    with pytest.raises(PostApplyInvalidationError) as error:
        controller.apply_approved_proposal(run.run_id, proposal)
    assert error.value.applied.snapshot.revision == 2
    assert error.value.applied.changeset_id.startswith("CS-")
    assert error.value.blocked.run_id == run.run_id
    assert error.value.blocked.status is RunStatus.BLOCKED
    assert controller.state_manager.load_revision("PRJ-1", 2).revision == 2
    current = controller.get_run(run.run_id)
    assert current.status is RunStatus.BLOCKED
    assert current.active_revision == 2
    assert current.iteration == 1
    assert controller.get_task(run.run_id, "TASK-A").status is TaskStatus.PENDING


def test_convergence_failure_after_revision_has_post_apply_receipt(tmp_path, monkeypatch):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )

    def fail_convergence(*_args):
        raise ConvergenceError("convergence bookkeeping failed")

    monkeypatch.setattr(
        "mechcad_harness.runs.controller.ConvergenceTracker.record_revision",
        fail_convergence,
    )

    with pytest.raises(PostApplyRunTransitionError) as error:
        controller.apply_approved_proposal(run.run_id, proposal)

    assert error.value.applied.snapshot.revision == 2
    assert error.value.current.active_revision == 2
    assert error.value.current.status is RunStatus.BLOCKED
    assert controller.state_manager.load_current_pointer("PRJ-1")["revision"] == 2


def test_run_state_persistence_failure_after_revision_has_post_apply_receipt(tmp_path, monkeypatch):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    monkeypatch.setattr(controller, "_save", lambda _run: (_ for _ in ()).throw(OSError("state disk failure")))

    with pytest.raises(PostApplyRunTransitionError) as error:
        controller.apply_approved_proposal(run.run_id, proposal)

    assert error.value.applied.snapshot.revision == 2
    assert error.value.current.active_revision == 2
    assert controller.state_manager.load_current_pointer("PRJ-1")["revision"] == 2


def test_run_event_persistence_failure_after_revision_has_post_apply_receipt(tmp_path, monkeypatch):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    append_event = controller.store.append_event

    def fail_revision_event(project_id, run_id, event_type, payload=None):
        if event_type == "REVISION_ADVANCED":
            raise OSError("event disk failure")
        return append_event(project_id, run_id, event_type, payload)

    monkeypatch.setattr(controller.store, "append_event", fail_revision_event)

    with pytest.raises(PostApplyRunTransitionError) as error:
        controller.apply_approved_proposal(run.run_id, proposal)

    assert error.value.applied.snapshot.revision == 2
    assert error.value.current.active_revision == 2
    assert controller.state_manager.load_current_pointer("PRJ-1")["revision"] == 2


def test_convergence_rejects_same_hash_progression(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1", max_iterations=2)
    with pytest.raises(ConvergenceError):
        controller.record_convergence_revision(run.run_id, run.active_revision, run.active_state_hash)
    assert controller.get_run(run.run_id).status is RunStatus.BLOCKED


def test_resume_verifies_active_revision_and_state_hash(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A")
    resumed = controller.resume_run("PRJ-1", run.run_id)
    assert resumed.run_id == run.run_id
    state = tmp_path / "projects/PRJ-1/runs" / run.run_id / "state.json"
    payload = json.loads(state.read_text())
    payload["active_state_hash"] = "sha256:wrong"
    state.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Exception):
        controller.resume_run("PRJ-1", run.run_id)


def test_rerun_requires_new_task_and_result_identity(tmp_path):
    controller, _ = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", produces=("analysis.materials",))
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    with pytest.raises(Exception):
        controller.accept_result(run.run_id, "TASK-A", TaskExecutionResult(
            result_id="RES-REPLACEMENT", task_id="TASK-A", bound_revision=1,
            bound_state_hash=run.active_state_hash,
        ))


def test_unaffected_pending_task_remains_pending_after_invalidation(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-A", produces=("analysis.materials",))
    task(controller, run, "TASK-B", produces=("analysis.packaging",))
    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="Plate")],
    )
    controller.apply_approved_proposal(run.run_id, proposal)
    assert controller.get_task(run.run_id, "TASK-A").status is TaskStatus.STALE
    assert controller.get_task(run.run_id, "TASK-B").status is TaskStatus.PENDING


def test_convergence_detects_cycle_and_iteration_limit(tmp_path):
    controller, snapshot = make_controller(tmp_path)
    run = controller.create_run("PRJ-1", max_iterations=1)
    first = controller.record_convergence_revision(run.run_id, 2, "sha256:first")
    assert first.iteration == 1
    with pytest.raises(ConvergenceError):
        controller.record_convergence_revision(run.run_id, 3, "sha256:first")
    assert controller.get_run(run.run_id).status is RunStatus.BLOCKED


def test_end_to_end_fake_executor_revision_replacement(tmp_path):
    controller, snapshot = make_controller(tmp_path, rules=[
        {"when": ["/components/*/name"], "invalidates": ["analysis.materials", "analysis.transmission"]},
        {"when": ["/components/*/description"], "invalidates": ["analysis.packaging"]},
    ])
    run = controller.create_run("PRJ-1")
    task(controller, run, "TASK-1", produces=("analysis.materials",))
    task(controller, run, "TASK-2", depends_on=("TASK-1",), produces=("analysis.transmission",))
    task(controller, run, "TASK-3", depends_on=("TASK-2",), produces=("analysis.packaging",))
    controller.create_plan(run.run_id, required_evidence_nodes=("analysis.materials", "analysis.transmission", "analysis.packaging"))
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    assert controller.evaluate_completion(run.run_id) is True

    proposal = ChangeProposal(
        id="CP-1", title="material", status=ProposalStatus.DRAFT,
        base_revision=1, base_state_hash=snapshot.state_hash, actor="actor",
        operations=[ChangeOperation(operation="replace", path="/components/PRT-1/name", value="PA12")],
    )
    controller.apply_approved_proposal(run.run_id, proposal)
    assert controller.evaluate_completion(run.run_id) is False
    current = controller.get_run(run.run_id)
    task(controller, current, "TASK-4", produces=("analysis.materials",))
    task(controller, current, "TASK-5", depends_on=("TASK-4",), produces=("analysis.transmission",))
    task(controller, current, "TASK-6", depends_on=("TASK-5",), produces=("analysis.packaging",))
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    controller.execute_ready_tasks(run.run_id, FakeTaskExecutor())
    assert controller.evaluate_completion(run.run_id) is True
