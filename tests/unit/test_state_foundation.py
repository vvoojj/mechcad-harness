import json

import pytest
from pydantic import ValidationError

from mechcad_harness.changes import ChangeEngine, ChangeOperation, OwnershipPolicy
from mechcad_harness.models import (
    CanonicalComponentSpecification,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    ChangeProposal,
    Component,
    DesignState,
    Evidence,
    ProposalStatus,
    StructuralAnalysisDefinition,
)
from mechcad_harness.state import (
    StateIntegrityError,
    StateManager,
    canonical_json,
    state_hash,
)


def make_state(
    name: str = "Bracket",
    *,
    structural_analysis_definitions=None,
    physical_mechanisms=None,
) -> DesignState:
    return DesignState(
        id="REV-state",
        revision=1,
        components=[Component(id="PRT-bracket", name=name)],
        structural_analysis_definitions=structural_analysis_definitions or [],
        physical_mechanisms=physical_mechanisms or [],
    )


def make_definition(definition_id: str = "definition-1") -> StructuralAnalysisDefinition:
    return StructuralAnalysisDefinition.model_validate(
        {
            "id": definition_id,
            "name": "Static structural definition",
            "target_body_id": "body-1",
            "regions": [
                {
                    "region_id": "fixed-end",
                    "target_body_id": "body-1",
                    "source_feature_id": "feature:fixed-end",
                    "semantic_role": "fixed_end",
                    "geometry_kind": "face",
                    "selector_kind": "semantic_feature_boundary",
                    "selector_parameters": {"boundary": "outer"},
                    "expected_cardinality": 1,
                    "resolver_version": "region-resolver@1.0",
                },
                {
                    "region_id": "free-end",
                    "target_body_id": "body-1",
                    "source_feature_id": "feature:free-end",
                    "semantic_role": "free_end",
                    "geometry_kind": "face",
                    "selector_kind": "semantic_feature_boundary",
                    "selector_parameters": {"boundary": "outer"},
                    "expected_cardinality": 1,
                    "resolver_version": "region-resolver@1.0",
                },
            ],
            "material_assignment": {
                "assignment_id": "assignment-1",
                "target_body_id": "body-1",
                "material_identity": "material:6061-t6",
                "assignment_context": "room-temperature T6",
                "property_snapshot": [
                    {
                        "property_name": "elastic_modulus",
                        "value": 69000.0,
                        "normalized_unit": "MPa",
                        "source_identity": "source:material",
                        "authority": "measured",
                        "conversion_provenance": {
                            "source_unit": "MPa",
                            "normalization_rule": "already_normalized",
                            "conversion_version": "units@1.0",
                        },
                    },
                    {
                        "property_name": "poisson_ratio",
                        "value": 0.33,
                        "normalized_unit": "ratio",
                        "source_identity": "source:material",
                        "authority": "measured",
                        "conversion_provenance": {
                            "source_unit": "ratio",
                            "normalization_rule": "already_normalized",
                            "conversion_version": "units@1.0",
                        },
                    },
                ],
            },
            "load_cases": [
                {
                    "id": "case-1",
                    "name": "Case 1",
                    "loads": [
                        {
                            "kind": "resultant_force",
                            "load_id": "force-1",
                            "target_region_id": "free-end",
                            "magnitude_n": 100.0,
                            "direction_xyz": [1.0, 0.0, 0.0],
                            "frame": "component_local",
                            "distribution": "uniform_surface_traction_equivalent",
                        }
                    ],
                }
            ],
            "boundary_conditions": [
                {
                    "support_id": "support-1",
                    "target_region_id": "fixed-end",
                    "applies_to_load_case_ids": ["case-1"],
                    "frame": "component_local",
                    "constrained_dofs": ["ux", "uy", "uz"],
                }
            ],
            "acceptance_criteria": [
                {
                    "kind": "maximum_displacement",
                    "criterion_id": "criterion-displacement",
                    "load_case_id": "case-1",
                    "assessment_region_id": "free-end",
                    "maximum_allowed_displacement_mm": 1.0,
                }
            ],
            "material_authority_policy": {
                "allowed_authorities_by_property": [
                    {
                        "property_name": "elastic_modulus",
                        "allowed_authorities": ["measured"],
                    },
                    {
                        "property_name": "poisson_ratio",
                        "allowed_authorities": ["measured"],
                    },
                ]
            },
        }
    )


def make_mechanism(mechanism_id: str = "PM-1") -> CanonicalPhysicalMechanism:
    specification = CanonicalComponentSpecification(
        component_type="shaft",
        source_identity="drawing:shaft@1",
    )
    component = CanonicalPhysicalComponent(
        instance_id="shaft-1",
        specification_hash=specification.specification_hash,
        role="shaft",
    )
    return CanonicalPhysicalMechanism(
        id=mechanism_id,
        name="rotary output",
        component_specifications=(specification,),
        components=(component,),
    )


def test_equivalent_states_have_same_canonical_hash():
    first = make_state()
    second = DesignState.model_validate(json.loads(first.model_dump_json()))
    assert canonical_json(first) == canonical_json(second)
    assert state_hash(first) == state_hash(second)


def test_hash_ignores_mapping_order_but_changes_with_state():
    first = make_state()
    reordered = DesignState.model_validate(
        {
            "load_cases": [],
            "constraints": [],
            "interfaces": [],
            "materials": [],
            "assemblies": [],
            "components": [{"created_at": first.components[0].created_at, "name": "Bracket", "id": "PRT-bracket"}],
            "requirements": [],
            "created_at": first.created_at,
            "revision": 1,
            "id": "REV-state",
        }
    )
    assert state_hash(first) == state_hash(reordered)
    assert state_hash(first) != state_hash(make_state("Changed"))


def test_structural_definition_is_canonical_state_and_affects_hash():
    first = make_state()
    second = first.model_copy(
        update={"structural_analysis_definitions": [make_definition()]}
    )

    assert "structural_analysis_definitions" in DesignState.model_fields
    assert second.created_at == first.created_at
    assert state_hash(first) != state_hash(second)


def test_duplicate_structural_definition_ids_fail_closed():
    with pytest.raises(ValidationError):
        make_state(
            structural_analysis_definitions=[
                make_definition("DEF-1"),
                make_definition("DEF-1"),
            ]
        )


def test_physical_mechanism_is_canonical_state_and_affects_hash():
    first = make_state()
    second = first.model_copy(update={"physical_mechanisms": [make_mechanism()]})

    assert "physical_mechanisms" in DesignState.model_fields
    assert second.created_at == first.created_at
    assert state_hash(first) != state_hash(second)


def test_duplicate_physical_mechanism_ids_fail_closed():
    with pytest.raises(ValidationError):
        make_state(
            physical_mechanisms=[
                make_mechanism("PM-1"),
                make_mechanism("PM-1"),
            ]
        )


def test_partial_physical_mechanism_values_fail_pydantic_validation():
    with pytest.raises(ValidationError):
        DesignState(
            id="REV-state",
            revision=1,
            physical_mechanisms=[{"id": "PM-1"}],
        )


def test_structural_definition_survives_state_json_round_trip():
    state = make_state(structural_analysis_definitions=[make_definition()])
    reloaded = DesignState.model_validate(json.loads(state.model_dump_json()))

    assert reloaded.structural_analysis_definitions == state.structural_analysis_definitions
    assert state_hash(reloaded) == state_hash(state)


def test_physical_mechanism_survives_state_json_round_trip():
    state = make_state(physical_mechanisms=[make_mechanism()])
    reloaded = DesignState.model_validate(json.loads(state.model_dump_json()))

    assert reloaded.physical_mechanisms == state.physical_mechanisms
    assert state_hash(reloaded) == state_hash(state)


def test_change_engine_mutates_structural_definition_collection_items(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-structural", make_state())
    engine = ChangeEngine(
        manager,
        OwnershipPolicy.from_file("config/ownership.yaml"),
    )

    def make_proposal(operation: ChangeOperation) -> ChangeProposal:
        current = manager._read_current("PRJ-structural")
        return ChangeProposal(
            id="CP-structural",
            title="change structural definition",
            status=ProposalStatus.DRAFT,
            base_revision=current["revision"],
            base_state_hash=current["state_hash"],
            actor="mechcad-structural",
            operations=[operation],
        )

    definition = make_definition("DEF-1")
    engine.apply_proposal(
        "PRJ-structural",
        make_proposal(
            ChangeOperation(
                operation="add",
                path="/structural_analysis_definitions/DEF-1",
                value=definition.model_dump(mode="json"),
            )
        ),
    )
    assert manager.load_current_state("PRJ-structural").structural_analysis_definitions[0].id == "DEF-1"

    replacement = definition.model_copy(update={"name": "Replaced definition"})
    engine.apply_proposal(
        "PRJ-structural",
        make_proposal(
            ChangeOperation(
                operation="replace",
                path="/structural_analysis_definitions/DEF-1",
                value=replacement.model_dump(mode="json"),
            )
        ),
    )
    assert manager.load_current_state("PRJ-structural").structural_analysis_definitions[0].name == "Replaced definition"

    engine.apply_proposal(
        "PRJ-structural",
        make_proposal(
            ChangeOperation(
                operation="remove",
                path="/structural_analysis_definitions/DEF-1",
            )
        ),
    )
    assert manager.load_current_state("PRJ-structural").structural_analysis_definitions == []


def test_change_engine_mutates_physical_mechanism_collection_items(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-physical", make_state())
    engine = ChangeEngine(
        manager,
        OwnershipPolicy([{"path": "/physical_mechanisms/*", "owner": "mechcad-physical"}]),
    )

    def make_proposal(operation: ChangeOperation) -> ChangeProposal:
        current = manager._read_current("PRJ-physical")
        return ChangeProposal(
            id="CP-physical",
            title="change physical mechanism",
            status=ProposalStatus.DRAFT,
            base_revision=current["revision"],
            base_state_hash=current["state_hash"],
            actor="mechcad-physical",
            operations=[operation],
        )

    mechanism = make_mechanism()
    engine.apply_proposal(
        "PRJ-physical",
        make_proposal(
            ChangeOperation(
                operation="add",
                path="/physical_mechanisms/PM-1",
                value=mechanism.model_dump(mode="json"),
            )
        ),
    )
    assert manager.load_current_state("PRJ-physical").physical_mechanisms[0].id == "PM-1"

    replacement = mechanism.model_copy(update={"name": "replaced output", "mechanism_hash": "pending"})
    engine.apply_proposal(
        "PRJ-physical",
        make_proposal(
            ChangeOperation(
                operation="replace",
                path="/physical_mechanisms/PM-1",
                value=replacement.model_dump(mode="json"),
            )
        ),
    )
    assert manager.load_current_state("PRJ-physical").physical_mechanisms[0].name == "replaced output"

    engine.apply_proposal(
        "PRJ-physical",
        make_proposal(
            ChangeOperation(
                operation="remove",
                path="/physical_mechanisms/PM-1",
            )
        ),
    )
    assert manager.load_current_state("PRJ-physical").physical_mechanisms == []


def test_project_revisions_are_immutable_and_current_points_to_latest(tmp_path):
    manager = StateManager(tmp_path)
    project_id = "PRJ-test"
    first = manager.create_project(project_id, make_state())
    first_path = tmp_path / "projects" / project_id / "revisions" / "REV-000001.json"
    first_bytes = first_path.read_bytes()

    second = manager.create_revision(project_id, make_state("Updated"))

    assert first.revision == 1
    assert second.revision == 2
    assert first_path.read_bytes() == first_bytes
    assert manager.load_current_state(project_id).components[0].name == "Updated"
    assert manager.load_revision(project_id, 1).components[0].name == "Bracket"


def test_existing_revision_cannot_be_overwritten(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-test", make_state())
    with pytest.raises(Exception):
        manager.create_revision("PRJ-test", make_state(), revision=1)


def test_tampered_snapshot_is_detected(tmp_path):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-test", make_state())
    path = tmp_path / "projects" / "PRJ-test" / "revisions" / "REV-000001.json"
    payload = json.loads(path.read_text())
    payload["state"]["components"][0]["name"] = "Tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(StateIntegrityError):
        manager.verify_revision("PRJ-test", 1)


def test_current_pointer_is_unchanged_when_snapshot_persistence_fails(tmp_path, monkeypatch):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-test", make_state())
    current_path = tmp_path / "projects" / "PRJ-test" / "current.json"
    current_bytes = current_path.read_bytes()

    def fail_write(*args, **kwargs):
        raise OSError("persistence failed")

    monkeypatch.setattr(manager, "_write_snapshot", fail_write)
    with pytest.raises(OSError):
        manager.create_revision("PRJ-test", make_state("Updated"))
    assert current_path.read_bytes() == current_bytes


def test_evidence_is_not_part_of_design_state():
    state = make_state()
    Evidence(id="EVD-test", kind="note", summary="separate", revision=1, state_hash="sha256:test")
    assert "evidence" not in DesignState.model_fields
