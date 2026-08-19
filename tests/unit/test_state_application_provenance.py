from datetime import datetime, timezone

import pytest


def test_application_identity_is_deterministic():
    from mechcad_harness.changes.provenance import application_id

    operations = ({"operation": "add", "path": "/authoritative_parameters/PARAM-1", "value": {"id": "PARAM-1"}},)
    assert application_id(project_id="PRJ", source_command_id="CMD-1", proposal_id="CP-1", base_revision=1, base_state_hash="sha256:state", operations=operations) == application_id(project_id="PRJ", source_command_id="CMD-1", proposal_id="CP-1", base_revision=1, base_state_hash="sha256:state", operations=operations)


def test_preparation_and_receipt_roundtrip_and_immutable_conflict(tmp_path):
    from mechcad_harness.changes.provenance import StateApplicationPreparationRecord, StateApplicationReceiptRecord, StateApplicationStore, operations_hash

    store = StateApplicationStore(tmp_path)
    operations = ({"operation": "add", "path": "/authoritative_parameters/PARAM-1", "value": {"id": "PARAM-1"}},)
    preparation = StateApplicationPreparationRecord(application_id="APP-1", project_id="PRJ", run_id="RUN", source_command_id="CMD-1", source_resolution_ids=("CRRES-1",), proposal_id="CP-1", changeset_id="CS-1", actor="mechcad-resolution", base_revision=1, base_state_hash="sha256:old", operations=operations, operations_hash=operations_hash(operations), target_revision=2, target_state_hash="sha256:new")
    receipt = StateApplicationReceiptRecord(application_id="APP-1", preparation_id="APP-1", project_id="PRJ", run_id="RUN", source_command_id="CMD-1", source_resolution_ids=("CRRES-1",), proposal_id="CP-1", changeset_id="CS-1", actor="mechcad-resolution", base_revision=1, base_state_hash="sha256:old", new_revision=2, new_state_hash="sha256:new", operations_hash=operations_hash(operations), outcome="applied")
    store.write_preparation("RUN", preparation)
    store.write_receipt("RUN", receipt)
    assert store.load_preparation("PRJ", "RUN", "APP-1") == preparation
    assert store.load_receipt("PRJ", "RUN", "APP-1") == receipt
    with pytest.raises(Exception):
        store.write_preparation("RUN", preparation.model_copy(update={"target_state_hash": "sha256:other"}))
    with pytest.raises(Exception):
        store.write_receipt("RUN", receipt.model_copy(update={"new_state_hash": "sha256:other"}))


def test_application_result_exposes_provenance_ids(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.state import StateManager
    from tests.unit.test_constraint_resolution_application import _setup

    manager, requests, command, materialized = _setup(tmp_path)
    result = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests).apply_batch(materialized, run_id="RUN")
    assert result.application_id
    assert result.preparation_id
    assert result.receipt_id


def test_application_provenance_uses_exact_run_scope(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.changes.provenance import StateApplicationStore
    from tests.unit.test_constraint_resolution_application import _setup

    manager, requests, command, materialized = _setup(tmp_path)
    from mechcad_harness.agents.constraint_resolution import ConstraintResolutionMaterializer, ConstraintResolutionStore
    request = requests.load("PRJ", "RUN", "CRREQ-1")
    requests.write(request.model_copy(update={"run_id": "RUN-EXACT"}))
    materialized = ConstraintResolutionMaterializer(requests, ConstraintResolutionStore(tmp_path)).materialize_batch(command, run_id="RUN-EXACT")
    result = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests).apply_batch(materialized, run_id="RUN-EXACT")
    store = StateApplicationStore(tmp_path)
    assert store.load_preparation("PRJ", "RUN-EXACT", result.application_id).application_id == result.application_id
    with pytest.raises(Exception):
        store.load_preparation("PRJ", "OTHER", result.application_id)


def test_preparation_failure_prevents_revision(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.changes.provenance import StateApplicationStore
    from tests.unit.test_constraint_resolution_application import _setup

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    service.application_store.write_preparation = lambda *args: (_ for _ in ()).throw(RuntimeError("preparation failure"))
    with pytest.raises(RuntimeError):
        service.apply_batch(materialized, run_id="RUN")
    assert manager._read_current("PRJ")["revision"] == 1
    assert not list((tmp_path / "projects" / "PRJ" / "revisions").glob("REV-000002.json"))


def test_completed_receipt_replay_reuses_application_without_new_revision(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from tests.unit.test_constraint_resolution_application import _setup

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    first = service.apply_batch(materialized, run_id="RUN")
    second = service.apply_batch(materialized, run_id="RUN")
    assert second.application_id == first.application_id
    assert second.receipt_id == first.receipt_id
    assert manager._read_current("PRJ")["revision"] == 2


def test_revision_without_receipt_recovers_exact_provenance(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.changes.provenance import StateApplicationStore
    from tests.unit.test_constraint_resolution_application import _setup

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    first = service.apply_batch(materialized, run_id="RUN")
    receipt_path = StateApplicationStore(tmp_path)._path("PRJ", "RUN", "receipts", first.application_id)
    receipt_path.unlink()
    second = service.recover_application("PRJ", "RUN", first.application_id)
    assert second.application_id == first.application_id
    assert second.proposal_id == first.proposal_id
    assert second.changeset_id == first.changeset_id
    assert second.new_revision == 2
    assert manager._read_current("PRJ")["revision"] == 2


def test_preparation_without_revision_recovers_exact_prepared_application(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.changes.provenance import StateApplicationStore
    from tests.unit.test_constraint_resolution_application import _setup

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    first = service.apply_batch(materialized, run_id="RUN")
    StateApplicationStore(tmp_path)._path("PRJ", "RUN", "receipts", first.application_id).unlink()
    manager._revision_path("PRJ", 2).unlink()
    manager._write_atomic(manager._current_path("PRJ"), {"project_id": "PRJ", "revision": 1, "state_hash": first.old_state_hash})
    recovered = service.recover_application("PRJ", "RUN", first.application_id)
    assert recovered.application_id == first.application_id
    assert recovered.proposal_id == first.proposal_id
    assert recovered.changeset_id == first.changeset_id
    assert recovered.new_revision == 2
    assert manager._read_current("PRJ")["revision"] == 2
    assert len(list((tmp_path / "projects" / "PRJ" / "revisions").glob("REV-*.json"))) == 2


def test_orphan_target_revision_hash_conflict_is_rejected(tmp_path):
    from mechcad_harness.agents.constraint_resolution_application import ConstraintResolutionApplicationService
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.changes.provenance import StateApplicationStore
    from tests.unit.test_constraint_resolution_application import _setup

    manager, requests, command, materialized = _setup(tmp_path)
    service = ConstraintResolutionApplicationService(manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/authoritative_parameters", "owner": "mechcad-resolution"}])), requests)
    first = service.apply_batch(materialized, run_id="RUN")
    receipt_path = StateApplicationStore(tmp_path)._path("PRJ", "RUN", "receipts", first.application_id)
    receipt_path.unlink()
    target_path = manager._revision_path("PRJ", 2)
    target_path.write_text(target_path.read_text(encoding="utf-8").replace(first.new_state_hash, "sha256:wrong"), encoding="utf-8")
    with pytest.raises(Exception):
        service.recover_application("PRJ", "RUN", first.application_id)
