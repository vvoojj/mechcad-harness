from datetime import datetime, timezone
import json

import pytest

from mechcad_harness.dependency import (
    DependencyCycleError,
    DependencyGraph,
    EvidenceIntegrityError,
    EvidenceConflictError,
    EvidenceFreshness,
    EvidenceStore,
    InvalidationError,
)
from mechcad_harness.models import DesignState, Evidence
from mechcad_harness.state import StateManager, state_hash


def dependency_file(tmp_path, *, rules=None, edges=None):
    path = tmp_path / "dependencies.yaml"
    rules = rules or [{"when": ["/materials/*"], "invalidates": ["analysis.materials"]}]
    edges = edges or []
    path.write_text(json.dumps({"rules": rules, "edges": [{"from": a, "to": b} for a, b in edges]}), encoding="utf-8")
    return path


def test_dependency_prefix_and_wildcard_match(tmp_path):
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path, rules=[
        {"when": ["/materials/*"], "invalidates": ["analysis.materials"]},
        {"when": ["/components/*/transmission"], "invalidates": ["analysis.transmission"]},
    ]))
    impact = graph.impact(["/materials/MAT-001/material", "/components/PRT-001/transmission/module"])
    assert impact.direct_nodes == ("analysis.materials", "analysis.transmission")


def test_unrelated_path_has_no_impact(tmp_path):
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path))
    assert graph.impact(["/components/PRT-001/description"]).all_nodes == ()


def test_transitive_nodes_are_sorted_and_deduplicated(tmp_path):
    graph = DependencyGraph.from_yaml(dependency_file(
        tmp_path,
        rules=[{"when": ["/requirements/*"], "invalidates": ["analysis.loads", "analysis.structural"]}],
        edges=[("analysis.loads", "analysis.structural"), ("analysis.structural", "validation.structural")],
    ))
    impact = graph.impact(["/requirements/R-1/description", "/requirements/R-2/description"])
    assert impact.all_nodes == ("analysis.loads", "analysis.structural", "validation.structural")


def test_dependency_graph_rejects_cycles(tmp_path):
    with pytest.raises(DependencyCycleError):
        DependencyGraph.from_yaml(dependency_file(tmp_path, edges=[("analysis.a", "analysis.b"), ("analysis.b", "analysis.a")]))


def make_state(revision=1):
    return DesignState(id="DES-1", revision=revision)


def make_evidence(manager, project_id, *, evidence_id="EVD-1", node="analysis.materials", revision=None, hash_value=None):
    revision = revision or manager._read_current(project_id)["revision"]
    hash_value = hash_value or manager._read_current(project_id)["state_hash"]
    return Evidence(
        id=evidence_id,
        kind=node,
        summary="deterministic evidence",
        revision=revision,
        state_hash=hash_value,
    )


def test_invalidation_and_evidence_records_are_immutable(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path))
    store = EvidenceStore(tmp_path, manager, graph)
    record = store.build_invalidation("PRJ-1", 2, 1, ("/materials/MAT-1/material",), None)
    store.record_invalidation(record)
    path = tmp_path / "projects" / "PRJ-1" / "invalidations" / "REV-000002.json"
    original = path.read_bytes()
    with pytest.raises(InvalidationError):
        store.record_invalidation(record)
    assert path.read_bytes() == original
    evidence = make_evidence(manager, "PRJ-1")
    store.write_evidence("PRJ-1", evidence)
    with pytest.raises(EvidenceConflictError):
        store.write_evidence("PRJ-1", evidence)


def test_freshness_requires_complete_history_and_valid_provenance(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path))
    store = EvidenceStore(tmp_path, manager, graph)
    evidence = make_evidence(manager, "PRJ-1")
    store.write_evidence("PRJ-1", evidence)
    manager.create_revision("PRJ-1", make_state())
    assert store.get_evidence_freshness("PRJ-1", "EVD-1") is EvidenceFreshness.UNKNOWN
    manager.create_revision("PRJ-1", make_state())
    assert store.get_evidence_freshness("PRJ-1", "EVD-1") is EvidenceFreshness.UNKNOWN


def test_evidence_at_revision_is_not_invalidated_by_own_record(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path))
    store = EvidenceStore(tmp_path, manager, graph)
    manager.create_revision("PRJ-1", make_state())
    current = manager._read_current("PRJ-1")
    evidence = make_evidence(manager, "PRJ-1", revision=2, hash_value=current["state_hash"])
    store.write_evidence("PRJ-1", evidence)
    record = store.build_invalidation("PRJ-1", 2, 1, ("/materials/MAT-1/material",), None)
    store.record_invalidation(record)
    assert store.get_evidence_freshness("PRJ-1", "EVD-1") is EvidenceFreshness.CURRENT


def test_matching_later_invalidation_is_stale_and_unknown_is_not_fresh(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path))
    store = EvidenceStore(tmp_path, manager, graph)
    evidence = make_evidence(manager, "PRJ-1")
    store.write_evidence("PRJ-1", evidence)
    manager.create_revision("PRJ-1", make_state())
    record = store.build_invalidation("PRJ-1", 2, 1, ("/materials/MAT-1/material",), None)
    store.record_invalidation(record)
    assert store.get_evidence_freshness("PRJ-1", "EVD-1") is EvidenceFreshness.STALE
    assert not store.is_evidence_fresh("PRJ-1", "EVD-1")


def test_wrong_hash_and_unknown_node_are_unknown(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path))
    store = EvidenceStore(tmp_path, manager, graph)
    store.write_evidence("PRJ-1", make_evidence(manager, "PRJ-1", hash_value="sha256:wrong"))
    assert store.get_evidence_freshness("PRJ-1", "EVD-1") is EvidenceFreshness.UNKNOWN
    unknown = make_evidence(manager, "PRJ-1", evidence_id="EVD-2", node="analysis.unknown")
    with pytest.raises(EvidenceIntegrityError):
        store.write_evidence("PRJ-1", unknown)


def test_end_to_end_unrelated_then_material_change_and_replacement(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-1", make_state())
    graph = DependencyGraph.from_yaml(dependency_file(tmp_path, rules=[
        {"when": ["/materials/*"], "invalidates": ["analysis.materials"]},
        {"when": ["/components/*/description"], "invalidates": ["analysis.packaging"]},
    ]))
    store = EvidenceStore(tmp_path, manager, graph)
    material = make_evidence(manager, "PRJ-1", evidence_id="EVD-M", node="analysis.materials")
    packaging = make_evidence(manager, "PRJ-1", evidence_id="EVD-P", node="analysis.packaging")
    store.write_evidence("PRJ-1", material)
    store.write_evidence("PRJ-1", packaging)

    manager.create_revision("PRJ-1", make_state())
    store.record_invalidation(store.build_invalidation("PRJ-1", 2, 1, ("/description",), "CS-2"))
    assert store.get_evidence_freshness("PRJ-1", "EVD-M") is EvidenceFreshness.CURRENT
    assert store.get_evidence_freshness("PRJ-1", "EVD-P") is EvidenceFreshness.CURRENT

    manager.create_revision("PRJ-1", make_state())
    store.record_invalidation(store.build_invalidation("PRJ-1", 3, 2, ("/materials/MAT-1/material",), "CS-3"))
    assert store.get_evidence_freshness("PRJ-1", "EVD-M") is EvidenceFreshness.STALE
    assert store.get_evidence_freshness("PRJ-1", "EVD-P") is EvidenceFreshness.CURRENT

    replacement = make_evidence(manager, "PRJ-1", evidence_id="EVD-M-3", node="analysis.materials", revision=3, hash_value=manager._read_current("PRJ-1")["state_hash"])
    store.write_evidence("PRJ-1", replacement)
    assert store.get_evidence_freshness("PRJ-1", "EVD-M-3") is EvidenceFreshness.CURRENT
