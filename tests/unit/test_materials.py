import importlib.util
import json
import math

import pytest

from mechcad_harness.materials import MaterialDataAuthority, MaterialPropertyStatus, TypicalMaterialPropertiesInput


MATERIALS_AVAILABLE = importlib.util.find_spec("bd_materials") is not None


def test_materials_optional_dependency_is_declared():
    pyproject = open("pyproject.toml", encoding="utf-8").read()
    assert "materials = [" in pyproject
    assert "bd-materials==0.2.4" in pyproject


def test_material_input_requires_explicit_identity():
    with pytest.raises(Exception):
        TypicalMaterialPropertiesInput(material_id="")
    assert TypicalMaterialPropertiesInput(material_id="Alu_G6061_T6").material_id == "Alu_G6061_T6"


def test_authority_and_status_are_explicit():
    assert MaterialDataAuthority.TYPICAL_REFERENCE.value == "typical_reference"
    assert MaterialPropertyStatus.MISSING.value == "missing"
    assert MaterialPropertyStatus.NOT_SUITABLE.value == "not_suitable"


@pytest.mark.skipif(not MATERIALS_AVAILABLE, reason="materials extra is not installed")
def test_catalog_result_preserves_range_and_density_semantics():
    from mechcad_harness.backends.bd_materials import BdMaterialsAdapter

    result = BdMaterialsAdapter().typical_properties(TypicalMaterialPropertiesInput(material_id="Alu_G7075_T6"))
    assert result.authority is MaterialDataAuthority.TYPICAL_REFERENCE
    assert result.canonical_name == "Alu_G7075_T6"
    modulus = result.properties["elastic_modulus"]
    assert modulus.min_value == 68
    assert modulus.max_value == 72
    assert modulus.representative_value is None
    assert result.density.representative_value == 2810
    assert result.density.value_semantics == "representative"


@pytest.mark.skipif(not MATERIALS_AVAILABLE, reason="materials extra is not installed")
def test_missing_and_not_suitable_are_not_numeric():
    from mechcad_harness.backends.bd_materials import BdMaterialsAdapter

    adapter = BdMaterialsAdapter()
    missing = adapter.typical_properties(TypicalMaterialPropertiesInput(material_id="Alu_G7075_T6"))
    assert missing.properties["elongation_at_break"].status is MaterialPropertyStatus.MISSING
    assert missing.properties["elongation_at_break"].min_value is None
    not_suitable = adapter.typical_properties(TypicalMaterialPropertiesInput(material_id="CFRP_PLATE"))
    prop = not_suitable.properties["yield_strength"]
    assert prop.status is MaterialPropertyStatus.NOT_SUITABLE
    assert prop.min_value is None
    assert not any(isinstance(value, float) and math.isnan(value) for value in prop.model_dump().values())


@pytest.mark.skipif(not MATERIALS_AVAILABLE, reason="materials extra is not installed")
def test_ambiguous_family_resolution_returns_canonical_identity():
    from mechcad_harness.backends.bd_materials import BdMaterialsAdapter

    result = BdMaterialsAdapter().typical_properties(TypicalMaterialPropertiesInput(material_id="aluminum"))
    assert result.canonical_name == "Alu_G6061_T6"
    assert result.warnings


@pytest.mark.skipif(not MATERIALS_AVAILABLE, reason="materials extra is not installed")
def test_mass_uses_representative_density_and_typical_authority():
    from mechcad_harness.backends.bd_materials import BdMaterialsAdapter

    result = BdMaterialsAdapter().mass(__import__("mechcad_harness.materials", fromlist=["MaterialMassInput"]).MaterialMassInput(volume_mm3=1000, material_id="Alu_G6061_T6"))
    assert result.mass_g == pytest.approx(2.7)
    assert result.authority is MaterialDataAuthority.TYPICAL_REFERENCE
    assert result.estimate is True


@pytest.mark.skipif(not MATERIALS_AVAILABLE, reason="materials extra is not installed")
def test_material_toolbroker_result_and_evidence_are_bound(tmp_path):
    from mechcad_harness.changes import ChangeEngine, OwnershipPolicy
    from mechcad_harness.dependency import DependencyGraph, EvidenceStore
    from mechcad_harness.models import Component, DesignState
    from mechcad_harness.runs import RunController, TaskDefinition
    from mechcad_harness.state import StateManager
    from mechcad_harness.tools import MaterialTools, ToolBroker, ToolRegistry, ToolResultStatus

    manager = StateManager(tmp_path)
    snapshot = manager.create_project("PRJ-1", DesignState(id="DES-1", revision=1, components=[Component(id="PRT-1", name="Part")]))
    graph_path = tmp_path / "dependencies.json"
    graph_path.write_text(json.dumps({"rules": [{"when": ["/components/*/name"], "invalidates": ["material.typical"]}], "edges": []}), encoding="utf-8")
    evidence = EvidenceStore(tmp_path, manager, DependencyGraph.from_yaml(graph_path))
    controller = RunController(tmp_path, manager, ChangeEngine(manager, OwnershipPolicy([{"path": "/components/*", "owner": "actor"}])), evidence)
    run = controller.create_run("PRJ-1")
    task = TaskDefinition(task_id="TASK-1", run_id=run.run_id, task_type="tool", objective="material", bound_revision=1, bound_state_hash=snapshot.state_hash, allowed_tools=("mechcad-material-typical-properties@1.0",))
    controller.add_task(run.run_id, task)
    result = ToolBroker(controller, ToolRegistry(MaterialTools.registrations())).execute(run.run_id, task.task_id, "mechcad-material-typical-properties", "1.0", {"material_id": "Alu_G7075_T6"}, evidence_node="material.typical")
    assert result.status is ToolResultStatus.SUCCEEDED
    assert result.output["authority"] == "typical_reference"
    assert result.backend_provenance.backend_name == "bd-materials"
    saved = controller.evidence.load_evidence("PRJ-1", result.evidence_id)
    assert saved.backend_provenance == result.backend_provenance
