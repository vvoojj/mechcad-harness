from collections.abc import Mapping
from math import inf, nan

import pytest
from pydantic import ValidationError

from mechcad_harness.materials import MaterialDataAuthority
from mechcad_harness.dependency import DependencyGraph
from mechcad_harness.models.structural import (
    AcceptanceMaterialAuthorityPolicy,
    MaximumDisplacementCriterion,
    StructuralAnalysisDefinition,
    StructuralAnalysisKind,
    StructuralBodyAcceleration,
    StructuralCoordinateFrame,
    StructuralDof,
    StructuralFixedSupport,
    StructuralLoadCase,
    StructuralPropertyAuthorityRule,
    StructuralRegionDefinition,
    StructuralMaterialAssignment,
    StructuralMaterialAuthorityDecision,
    StructuralMaterialConversionProvenance,
    StructuralMaterialPropertyName,
    StructuralMaterialPropertySnapshot,
    StructuralPhysicalAssumptions,
    StructuralResultantForce,
    StructuralResultField,
    StructuralSurfacePressure,
    YieldSafetyFactorCriterion,
    evaluate_material_authority_policy,
    structural_definition_hash,
)


def make_snapshot(
    property_name: StructuralMaterialPropertyName,
    *,
    value: float = 1.0,
    normalized_unit: str | None = None,
    source_identity: str = "source:material",
    authority: MaterialDataAuthority = MaterialDataAuthority.MEASURED,
    conversion_provenance: StructuralMaterialConversionProvenance | None = None,
) -> StructuralMaterialPropertySnapshot:
    units = {
        StructuralMaterialPropertyName.ELASTIC_MODULUS: "MPa",
        StructuralMaterialPropertyName.POISSON_RATIO: "ratio",
        StructuralMaterialPropertyName.DENSITY: "kg/m^3",
        StructuralMaterialPropertyName.YIELD_STRENGTH: "MPa",
    }
    return StructuralMaterialPropertySnapshot(
        property_name=property_name,
        value=value,
        normalized_unit=normalized_unit or units[property_name],
        source_identity=source_identity,
        authority=authority,
        conversion_provenance=conversion_provenance
        or StructuralMaterialConversionProvenance(
            source_unit=units[property_name],
            normalization_rule="already_normalized",
            conversion_version="units@1.0",
        ),
    )


def make_structural_assignment_with(
    *,
    elastic_modulus_authority: MaterialDataAuthority = MaterialDataAuthority.MEASURED,
    poisson_ratio_authority: MaterialDataAuthority = MaterialDataAuthority.MEASURED,
    yield_strength_authority: MaterialDataAuthority = MaterialDataAuthority.MEASURED,
) -> StructuralMaterialAssignment:
    return StructuralMaterialAssignment(
        assignment_id="assignment-1",
        target_body_id="body-1",
        material_identity="material:6061-t6",
        assignment_context="room-temperature T6",
        property_snapshot=(
            make_snapshot(
                StructuralMaterialPropertyName.ELASTIC_MODULUS,
                value=69000.0,
                normalized_unit="MPa",
                authority=elastic_modulus_authority,
            ),
            make_snapshot(
                StructuralMaterialPropertyName.POISSON_RATIO,
                value=0.33,
                normalized_unit="ratio",
                authority=poisson_ratio_authority,
            ),
            make_snapshot(
                StructuralMaterialPropertyName.YIELD_STRENGTH,
                value=276.0,
                normalized_unit="MPa",
                authority=yield_strength_authority,
            ),
        ),
    )


def test_property_snapshot_preserves_mixed_authority_and_provenance():
    snapshot = StructuralMaterialPropertySnapshot(
        property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
        value=69000.0,
        normalized_unit="MPa",
        source_identity="supplier:datasheet:6061-t6",
        authority=MaterialDataAuthority.SUPPLIER_DATASHEET,
        context="room-temperature T6",
        conversion_provenance=StructuralMaterialConversionProvenance(
            source_unit="GPa",
            normalization_rule="gpa_to_mpa_x1000",
            conversion_version="units@1.0",
        ),
    )

    assert snapshot.authority is MaterialDataAuthority.SUPPLIER_DATASHEET
    assert snapshot.normalized_unit == "MPa"
    assert snapshot.conversion_provenance.source_unit == "GPa"


def test_assignment_does_not_have_assignment_level_authority():
    assignment = make_structural_assignment_with(
        elastic_modulus_authority=MaterialDataAuthority.SUPPLIER_DATASHEET,
        poisson_ratio_authority=MaterialDataAuthority.TYPICAL_REFERENCE,
        yield_strength_authority=MaterialDataAuthority.MEASURED,
    )

    assert assignment.property_snapshot[0].authority is not None
    assert "authority" not in StructuralMaterialAssignment.model_fields
    with pytest.raises(ValidationError):
        StructuralMaterialAssignment(
            **assignment.model_dump(),
            authority=MaterialDataAuthority.MEASURED,
        )


@pytest.mark.parametrize(
    ("property_name", "value", "normalized_unit"),
    [
        (StructuralMaterialPropertyName.ELASTIC_MODULUS, 69000.0, "MPa"),
        (StructuralMaterialPropertyName.POISSON_RATIO, 0.3, "ratio"),
        (StructuralMaterialPropertyName.DENSITY, 2700.0, "kg/m^3"),
        (StructuralMaterialPropertyName.YIELD_STRENGTH, 276.0, "MPa"),
    ],
)
def test_valid_structural_property_snapshot_values(
    property_name: StructuralMaterialPropertyName,
    value: float,
    normalized_unit: str,
):
    snapshot = make_snapshot(
        property_name,
        value=value,
        normalized_unit=normalized_unit,
    )

    assert snapshot.property_name is property_name
    assert snapshot.value == value


@pytest.mark.parametrize(
    ("property_name", "value", "normalized_unit"),
    [
        (StructuralMaterialPropertyName.POISSON_RATIO, 0.3, "MPa"),
        (StructuralMaterialPropertyName.ELASTIC_MODULUS, 0.0, "MPa"),
        (StructuralMaterialPropertyName.DENSITY, 0.0, "kg/m^3"),
        (StructuralMaterialPropertyName.YIELD_STRENGTH, 0.0, "MPa"),
        (StructuralMaterialPropertyName.POISSON_RATIO, -1.0, "ratio"),
        (StructuralMaterialPropertyName.POISSON_RATIO, 0.5, "ratio"),
        (StructuralMaterialPropertyName.ELASTIC_MODULUS, inf, "MPa"),
        (StructuralMaterialPropertyName.DENSITY, nan, "kg/m^3"),
    ],
)
def test_invalid_structural_property_units_and_values_fail_closed(
    property_name: StructuralMaterialPropertyName,
    value: float,
    normalized_unit: str,
):
    with pytest.raises(ValidationError):
        make_snapshot(
            property_name,
            value=value,
            normalized_unit=normalized_unit,
        )


@pytest.mark.parametrize(
    "field_values",
    [
        {"source_identity": ""},
        {"normalized_unit": ""},
        {"conversion_provenance": {"source_unit": "", "normalization_rule": "rule", "conversion_version": "v1"}},
        {"conversion_provenance": {"source_unit": "GPa", "normalization_rule": "", "conversion_version": "v1"}},
        {"conversion_provenance": {"source_unit": "GPa", "normalization_rule": "rule", "conversion_version": ""}},
    ],
)
def test_structural_property_snapshot_requires_nonempty_provenance_fields(field_values):
    values = {
        "property_name": StructuralMaterialPropertyName.ELASTIC_MODULUS,
        "value": 69000.0,
        "normalized_unit": "MPa",
        "source_identity": "source:material",
        "authority": MaterialDataAuthority.MEASURED,
        "conversion_provenance": {
            "source_unit": "GPa",
            "normalization_rule": "gpa_to_mpa_x1000",
            "conversion_version": "units@1.0",
        },
    }
    values.update(field_values)

    with pytest.raises(ValidationError):
        StructuralMaterialPropertySnapshot(**values)


def test_structural_property_snapshot_requires_value():
    with pytest.raises(ValidationError):
        StructuralMaterialPropertySnapshot(
            property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
            normalized_unit="MPa",
            source_identity="source:material",
            authority=MaterialDataAuthority.MEASURED,
            conversion_provenance={
                "source_unit": "GPa",
                "normalization_rule": "gpa_to_mpa_x1000",
                "conversion_version": "units@1.0",
            },
        )


def test_assignment_requires_nonempty_unique_property_snapshots():
    with pytest.raises(ValidationError):
        StructuralMaterialAssignment(
            assignment_id="assignment-1",
            target_body_id="body-1",
            material_identity="material:6061-t6",
            assignment_context="room-temperature T6",
            property_snapshot=(),
        )

    elastic = make_snapshot(StructuralMaterialPropertyName.ELASTIC_MODULUS, value=69000.0)
    with pytest.raises(ValidationError):
        StructuralMaterialAssignment(
            assignment_id="assignment-1",
            target_body_id="body-1",
            material_identity="material:6061-t6",
            assignment_context="room-temperature T6",
            property_snapshot=(elastic, elastic),
        )


def test_shared_structural_enums_are_restricted():
    assert StructuralAnalysisKind.LINEAR_STATIC_SOLID.value == "linear_static_solid"
    assert StructuralCoordinateFrame.COMPONENT_LOCAL.value == "component_local"
    assert StructuralCoordinateFrame.ASSEMBLY_WORLD.value == "assembly_world"
    assert tuple(dof.value for dof in StructuralDof) == ("ux", "uy", "uz")
    assert tuple(field.value for field in StructuralResultField) == (
        "displacement",
        "von_mises_stress",
        "reactions",
    )


def test_structural_physical_assumptions_are_fixed():
    assumptions = StructuralPhysicalAssumptions()

    assert assumptions.model_dump() == {
        "analysis_kind": "linear_static_solid",
        "deformation_model": "small_deformation",
        "material_model": "linear_elastic",
        "material_symmetry": "isotropic",
        "body_scope": "single_solid_body",
    }

    with pytest.raises(ValidationError):
        StructuralPhysicalAssumptions(deformation_model="large_deformation")


def test_structural_property_snapshot_is_immutable():
    snapshot = make_snapshot(StructuralMaterialPropertyName.ELASTIC_MODULUS, value=69000.0)

    with pytest.raises(ValidationError):
        snapshot.value = 70000.0


def test_structural_physical_assumptions_are_immutable():
    assumptions = StructuralPhysicalAssumptions()

    with pytest.raises(ValidationError):
        assumptions.material_model = "linear_elastic"


def test_assignment_and_nested_structural_records_are_immutable():
    assignment = make_structural_assignment_with()

    with pytest.raises(ValidationError):
        assignment.target_body_id = "body-2"
    with pytest.raises(ValidationError):
        assignment.property_snapshot[0].conversion_provenance.source_unit = "MPa"


def make_structural_assignment_without(
    property_name: StructuralMaterialPropertyName,
) -> StructuralMaterialAssignment:
    assignment = make_structural_assignment_with()
    return StructuralMaterialAssignment(
        **{
            **assignment.model_dump(),
            "property_snapshot": tuple(
                snapshot
                for snapshot in assignment.property_snapshot
                if snapshot.property_name is not property_name
            ),
        }
    )


def make_region(
    region_id: str = "fixed-end",
    *,
    target_body_id: str = "body-1",
) -> StructuralRegionDefinition:
    return StructuralRegionDefinition(
        region_id=region_id,
        target_body_id=target_body_id,
        source_feature_id=f"feature:{region_id}",
        semantic_role=region_id,
        geometry_kind="face",
        selector_kind="semantic_feature_boundary",
        selector_parameters={"boundary": "outer"},
        expected_cardinality=1,
        resolver_version="region-resolver@1.0",
    )


def make_force(load_id: str = "force-1", target_region_id: str = "free-end"):
    return StructuralResultantForce(
        load_id=load_id,
        target_region_id=target_region_id,
        magnitude_n=100.0,
        direction_xyz=(1.0, 0.0, 0.0),
        frame=StructuralCoordinateFrame.COMPONENT_LOCAL,
        distribution="uniform_surface_traction_equivalent",
    )


def make_case(case_id: str = "case-1", *, loads=None, active: bool = True):
    return {
        "id": case_id,
        "name": case_id,
        "active": active,
        "loads": tuple(loads or (make_force(),)),
    }


def make_policy(
    *,
    yield_authorities=(
        MaterialDataAuthority.MEASURED,
        MaterialDataAuthority.SUPPLIER_DATASHEET,
    ),
) -> AcceptanceMaterialAuthorityPolicy:
    return AcceptanceMaterialAuthorityPolicy(
        allowed_authorities_by_property=(
            StructuralPropertyAuthorityRule(
                property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
                allowed_authorities=(
                    MaterialDataAuthority.MEASURED,
                    MaterialDataAuthority.SUPPLIER_DATASHEET,
                ),
            ),
            StructuralPropertyAuthorityRule(
                property_name=StructuralMaterialPropertyName.POISSON_RATIO,
                allowed_authorities=(
                    MaterialDataAuthority.MEASURED,
                    MaterialDataAuthority.TYPICAL_REFERENCE,
                ),
            ),
            StructuralPropertyAuthorityRule(
                property_name=StructuralMaterialPropertyName.YIELD_STRENGTH,
                allowed_authorities=yield_authorities,
            ),
        )
    )


def make_displacement_criterion(
    criterion_id: str = "criterion-displacement",
) -> MaximumDisplacementCriterion:
    return MaximumDisplacementCriterion(
        criterion_id=criterion_id,
        load_case_id="case-1",
        assessment_region_id="free-end",
        sampling="nodal_displacement_magnitude_on_region",
        maximum_allowed_displacement_mm=1.0,
    )


def make_yield_criterion(
    criterion_id: str = "criterion-yield",
) -> YieldSafetyFactorCriterion:
    return YieldSafetyFactorCriterion(
        criterion_id=criterion_id,
        load_case_id="case-1",
        assessment_region_id="free-end",
        stress_sampling="element_integration_point",
        minimum_yield_safety_factor=2.0,
        zero_stress_tolerance_mpa=0.001,
    )


def make_definition(
    definition_id: str = "definition-1",
    *,
    material_assignment: StructuralMaterialAssignment | None = None,
    regions=None,
    load_cases=None,
    boundary_conditions=None,
    acceptance_criteria=None,
    policy: AcceptanceMaterialAuthorityPolicy | None = None,
) -> StructuralAnalysisDefinition:
    return StructuralAnalysisDefinition(
        id=definition_id,
        name="Static structural definition",
        analysis_kind=StructuralAnalysisKind.LINEAR_STATIC_SOLID,
        target_body_id="body-1",
        regions=tuple(regions or (make_region("fixed-end"), make_region("free-end"))),
        material_assignment=material_assignment or make_structural_assignment_with(),
        load_cases=tuple(load_cases or (make_case(),)),
        boundary_conditions=tuple(
            boundary_conditions
            or (
                StructuralFixedSupport(
                    support_id="support-1",
                    target_region_id="fixed-end",
                    applies_to_load_case_ids=("case-1",),
                    frame=StructuralCoordinateFrame.COMPONENT_LOCAL,
                    constrained_dofs=("ux", "uy", "uz"),
                ),
            )
        ),
        acceptance_criteria=tuple(
            acceptance_criteria or (make_displacement_criterion(),)
        ),
        material_authority_policy=policy or make_policy(),
        physical_assumptions=StructuralPhysicalAssumptions(),
    )


def test_raw_face_selector_is_not_a_canonical_region():
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            region_id="fixed-end",
            target_body_id="body-1",
            semantic_role="base_end",
            geometry_kind="face",
            selector_kind="raw_topology_index",
            selector_parameters={"face": "Face7"},
            expected_cardinality=1,
            resolver_version="region-resolver@1.0",
        )


def test_selector_parameters_are_immutable_and_hash_stable():
    first = StructuralRegionDefinition(
        region_id="fixed-end",
        target_body_id="body-1",
        source_feature_id="feature:fixed-end",
        semantic_role="base_end",
        geometry_kind="face",
        selector_kind="semantic_feature_boundary",
        selector_parameters={"axis": "x", "boundary": "outer"},
        expected_cardinality=1,
        resolver_version="region-resolver@1.0",
    )
    equivalent = StructuralRegionDefinition(
        region_id="fixed-end",
        target_body_id="body-1",
        source_feature_id="feature:fixed-end",
        semantic_role="base_end",
        geometry_kind="face",
        selector_kind="semantic_feature_boundary",
        selector_parameters={"boundary": "outer", "axis": "x"},
        expected_cardinality=1,
        resolver_version="region-resolver@1.0",
    )

    assert hash(first) == hash(equivalent)
    assert first.selector_parameters == {
        "axis": "x",
        "boundary": "outer",
    }
    assert first.model_dump(mode="json")["selector_parameters"] == {
        "axis": "x",
        "boundary": "outer",
    }
    original_hash = structural_definition_hash(
        StructuralAnalysisDefinition(
            id="definition-1",
            name="Static structural definition",
            target_body_id="body-1",
            regions=(first, make_region("free-end")),
            material_assignment=make_structural_assignment_with(),
            load_cases=(make_case(),),
            material_authority_policy=make_policy(),
        )
    )
    with pytest.raises(TypeError):
        first.selector_parameters["axis"] = "y"
    with pytest.raises(TypeError):
        first.selector_parameters.update(axis="y")
    with pytest.raises(AttributeError):
        first.selector_parameters._items = ()

    assert structural_definition_hash(
        StructuralAnalysisDefinition(
            id="definition-1",
            name="Static structural definition",
            target_body_id="body-1",
            regions=(first, make_region("free-end")),
            material_assignment=make_structural_assignment_with(),
            load_cases=(make_case(),),
            material_authority_policy=make_policy(),
        )
    ) == original_hash


def test_selector_parameters_reject_base_dict_mutation_and_preserve_hash():
    region = StructuralRegionDefinition(
        region_id="fixed-end",
        target_body_id="body-1",
        source_feature_id="feature:fixed-end",
        semantic_role="base_end",
        geometry_kind="face",
        selector_kind="semantic_feature_boundary",
        selector_parameters={"axis": "x", "boundary": "outer"},
        expected_cardinality=1,
        resolver_version="region-resolver@1.0",
    )
    definition = StructuralAnalysisDefinition(
        id="definition-1",
        name="Static structural definition",
        target_body_id="body-1",
        regions=(region, make_region("free-end")),
        material_assignment=make_structural_assignment_with(),
        load_cases=(make_case(),),
        material_authority_policy=make_policy(),
    )
    original_parameters = dict(region.selector_parameters)
    original_model_hash = hash(region)
    original_definition_hash = structural_definition_hash(definition)

    assert isinstance(region.selector_parameters, Mapping)
    assert not isinstance(region.selector_parameters, dict)
    assert tuple(region.selector_parameters.items()) == (
        ("axis", "x"),
        ("boundary", "outer"),
    )
    with pytest.raises(TypeError):
        dict.__setitem__(region.selector_parameters, "axis", "y")
    with pytest.raises(TypeError):
        dict.clear(region.selector_parameters)

    assert dict(region.selector_parameters) == original_parameters
    assert hash(region) == original_model_hash
    assert structural_definition_hash(definition) == original_definition_hash


def test_structural_region_schema_supports_selector_parameters():
    schema = StructuralRegionDefinition.model_json_schema()

    assert "selector_parameters" in schema["properties"]
    assert schema["properties"]["selector_parameters"]["type"] == "object"
    assert StructuralRegionDefinition(
        region_id="fixed-end",
        target_body_id="body-1",
        source_feature_id="feature:fixed-end",
        semantic_role="base_end",
        geometry_kind="face",
        selector_kind="semantic_feature_boundary",
        selector_parameters={"boundary": "outer"},
        expected_cardinality=1,
        resolver_version="region-resolver@1.0",
    ).model_dump(mode="json")["selector_parameters"] == {"boundary": "outer"}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("face", "Face7"),
        ("edge", "Edge2"),
        ("vertex", "Vertex3"),
        ("mesh_node_id", 7),
        ("gmsh_entity_id", 11),
        ("calculix_set_name", "SET-1"),
        ("semantic_label", "Face7"),
        ("semantic_label", "mesh-node-7"),
        ("semantic_label", "Gmsh:11"),
        ("semantic_label", "CalculiX:SET-1"),
        ("semantic_label", "FaceN"),
        ("semantic_label", "Edge2"),
        ("semantic_label", "Vertex3"),
        ("semantic_label", "MeshNode7"),
        ("semantic_label", "GmshEntity11"),
        ("semantic_label", "CalculiXSet1"),
    ],
)
def test_semantic_region_rejects_raw_topology_identity_parameters(key, value):
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            region_id="fixed-end",
            target_body_id="body-1",
            source_feature_id="feature:fixed-end",
            semantic_role="base_end",
            geometry_kind="face",
            selector_kind="semantic_feature_boundary",
            selector_parameters={key: value},
            expected_cardinality=1,
            resolver_version="region-resolver@1.0",
        )


@pytest.mark.parametrize(
    ("selector_kind", "key", "value"),
    [
        ("semantic_feature_boundary", "topology_id", 7),
        ("semantic_feature_boundary", "topology_index", 7),
        ("semantic_feature_boundary", "raw_topology_index", 7),
        ("semantic_feature_boundary", "selector", "topology:7"),
        ("semantic_feature_boundary", "Face", "Face7"),
        ("semantic_feature_boundary", "Edge", "Edge2"),
        ("semantic_feature_boundary", "Vertex", "Vertex3"),
        ("semantic_feature_boundary", "mesh_node_id", 7),
        ("semantic_feature_boundary", "Gmsh_entity_id", 11),
        ("semantic_feature_boundary", "CalculiX_set_name", "SET-1"),
        ("topology", "label", "topology:7"),
        ("mesh-node", "label", "mesh-node-7"),
        ("Gmsh-entity", "label", "Gmsh:11"),
        ("CalculiX-set", "label", "CalculiX:SET-1"),
    ],
)
def test_raw_topology_and_solver_identity_is_rejected_for_all_selector_kinds(
    selector_kind: str,
    key: str,
    value,
):
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            region_id="fixed-end",
            target_body_id="body-1",
            source_feature_id="feature:fixed-end",
            semantic_role="base_end",
            geometry_kind="face",
            selector_kind=selector_kind,
            selector_parameters={key: value},
            expected_cardinality=1,
            resolver_version="region-resolver@1.0",
        )


@pytest.mark.parametrize(
    "raw_value",
    ["FaceN", "Edge2", "Vertex3", "MeshNode7", "GmshEntity11", "CalculiXSet1"],
)
@pytest.mark.parametrize(
    "selector_kind",
    ["semantic_feature_boundary", "topology", "mesh-node", "Gmsh-entity", "CalculiX-set"],
)
def test_exact_raw_identity_values_are_rejected_for_every_selector_kind(
    raw_value: str,
    selector_kind: str,
):
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            region_id="fixed-end",
            target_body_id="body-1",
            source_feature_id="feature:fixed-end",
            semantic_role="base_end",
            geometry_kind="face",
            selector_kind=selector_kind,
            selector_parameters={"label": raw_value},
            expected_cardinality=1,
            resolver_version="region-resolver@1.0",
        )


@pytest.mark.parametrize("selector_kind", ["mesh-node", "Gmsh-entity", "CalculiX-set"])
def test_solver_selector_names_and_nonfinite_parameters_are_not_canonical(
    selector_kind: str,
):
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            region_id="fixed-end",
            target_body_id="body-1",
            source_feature_id="feature:fixed-end",
            semantic_role="base_end",
            geometry_kind="face",
            selector_kind=selector_kind,
            selector_parameters={},
            expected_cardinality=1,
            resolver_version="region-resolver@1.0",
        )
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            region_id="fixed-end",
            target_body_id="body-1",
            source_feature_id="feature:fixed-end",
            semantic_role="base_end",
            geometry_kind="face",
            selector_kind="semantic_feature_boundary",
            selector_parameters={"offset": nan},
            expected_cardinality=1,
            resolver_version="region-resolver@1.0",
        )


def test_region_requires_exactly_one_source_identity_and_positive_cardinality():
    values = {
        "region_id": "fixed-end",
        "target_body_id": "body-1",
        "semantic_role": "base_end",
        "geometry_kind": "face",
        "selector_kind": "semantic_feature_boundary",
        "selector_parameters": {"boundary": "outer"},
        "expected_cardinality": 1,
        "resolver_version": "region-resolver@1.0",
    }
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(**values)
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            **values,
            source_feature_id="feature:base",
            source_primitive_id="primitive:base",
        )
    with pytest.raises(ValidationError):
        StructuralRegionDefinition(
            **{**values, "expected_cardinality": 0},
            source_feature_id="feature:base",
        )


def test_resultant_force_requires_explicit_distribution_and_frame():
    with pytest.raises(ValidationError):
        StructuralResultantForce(
            load_id="force-1",
            target_region_id="free-end",
            magnitude_n=100.0,
            direction_xyz=(1.0, 0.0, 0.0),
            frame="component_local",
            distribution="point_force",
        )


def test_load_primitives_validate_vectors_and_preserve_case_order():
    with pytest.raises(ValidationError):
        StructuralResultantForce(
            load_id="force-1",
            target_region_id="free-end",
            magnitude_n=100.0,
            direction_xyz=(0.0, 0.0, 0.0),
            frame="component_local",
            distribution="uniform_surface_traction_equivalent",
        )
    with pytest.raises(ValidationError):
        StructuralResultantForce(
            load_id="force-1",
            target_region_id="free-end",
            magnitude_n=0.0,
            direction_xyz=(1.0, 0.0, 0.0),
            frame="component_local",
            distribution="uniform_surface_traction_equivalent",
        )

    pressure = StructuralSurfacePressure(
        load_id="pressure-1",
        target_region_id="free-end",
        pressure_mpa=-0.5,
        signed_normal_convention="inward_positive",
        frame="assembly_world",
    )
    acceleration = StructuralBodyAcceleration(
        load_id="acceleration-1",
        target_body_id="body-1",
        acceleration_xyz=(0.0, -9810.0, 0.0),
        acceleration_unit="mm/s^2",
        frame="component_local",
    )
    first = StructuralLoadCase(**make_case("case-1", loads=(pressure,)))
    second = StructuralLoadCase(**make_case("case-2", loads=(acceleration,)))
    assert (first.id, second.id) == ("case-1", "case-2")
    assert first.loads[0].kind == "surface_pressure"
    assert second.loads[0].kind == "body_acceleration"


def test_structural_load_case_requires_nonempty_loads():
    with pytest.raises(ValidationError):
        StructuralLoadCase(id="case-1", name="Case", loads=())


def test_fixed_support_requires_all_solid_translation_dofs_and_case_ids():
    with pytest.raises(ValidationError):
        StructuralFixedSupport(
            support_id="support-1",
            target_region_id="fixed-end",
            applies_to_load_case_ids=(),
            frame="component_local",
            constrained_dofs=("ux", "uy"),
        )
    with pytest.raises(ValidationError):
        StructuralFixedSupport(
            support_id="support-1",
            target_region_id="fixed-end",
            applies_to_load_case_ids=("case-1", "case-1"),
            frame="component_local",
            constrained_dofs=("ux", "uy", "uz"),
        )
    support = StructuralFixedSupport(
        support_id="support-1",
        target_region_id="fixed-end",
        applies_to_load_case_ids=("case-1",),
        frame="assembly_world",
        constrained_dofs=("ux", "uy", "uz"),
    )
    assert support.constrained_dofs == (
        StructuralDof.UX,
        StructuralDof.UY,
        StructuralDof.UZ,
    )


def test_authority_policy_is_property_specific_and_unique():
    with pytest.raises(ValidationError):
        AcceptanceMaterialAuthorityPolicy(
            allowed_authorities_by_property=(
                StructuralPropertyAuthorityRule(
                    property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
                    allowed_authorities=(),
                ),
            )
        )
    with pytest.raises(ValidationError):
        AcceptanceMaterialAuthorityPolicy(
            allowed_authorities_by_property=(
                StructuralPropertyAuthorityRule(
                    property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
                    allowed_authorities=(MaterialDataAuthority.MEASURED,),
                ),
                StructuralPropertyAuthorityRule(
                    property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
                    allowed_authorities=(MaterialDataAuthority.MEASURED,),
                ),
            )
        )


def test_authority_evaluator_accepts_mixed_allowed_authorities():
    assignment = make_structural_assignment_with(
        elastic_modulus_authority=MaterialDataAuthority.SUPPLIER_DATASHEET,
        poisson_ratio_authority=MaterialDataAuthority.TYPICAL_REFERENCE,
        yield_strength_authority=MaterialDataAuthority.MEASURED,
    )
    decision = evaluate_material_authority_policy(
        make_yield_criterion(), assignment, make_policy()
    )
    assert decision == StructuralMaterialAuthorityDecision(
        status="eligible",
        consumed_property_names=(
            StructuralMaterialPropertyName.ELASTIC_MODULUS,
            StructuralMaterialPropertyName.POISSON_RATIO,
            StructuralMaterialPropertyName.YIELD_STRENGTH,
        ),
    )


def test_missing_yield_only_blocks_yield_criterion():
    assignment = make_structural_assignment_without(
        StructuralMaterialPropertyName.YIELD_STRENGTH
    )
    displacement = evaluate_material_authority_policy(
        make_displacement_criterion(), assignment, make_policy()
    )
    yield_check = evaluate_material_authority_policy(
        make_yield_criterion(), assignment, make_policy()
    )
    assert displacement.status == "eligible"
    assert yield_check.status == "not_evaluable"
    assert (
        yield_check.rejection_reasons[0].property_name
        is StructuralMaterialPropertyName.YIELD_STRENGTH
    )
    assert yield_check.rejection_reasons[0].reason == "missing_snapshot"


def test_authority_evaluator_rejects_disallowed_authority_and_missing_provenance():
    assignment = make_structural_assignment_with(
        yield_strength_authority=MaterialDataAuthority.TYPICAL_REFERENCE
    )
    decision = evaluate_material_authority_policy(
        make_yield_criterion(), assignment, make_policy()
    )
    assert decision.status == "not_evaluable"
    assert decision.rejection_reasons[0].reason == "disallowed_authority"

    snapshot = make_snapshot(StructuralMaterialPropertyName.ELASTIC_MODULUS)
    invalid_snapshot = StructuralMaterialPropertySnapshot.model_construct(
        **{
            **snapshot.model_dump(),
            "conversion_provenance": None,
        }
    )
    assignment_values = make_structural_assignment_with().model_dump()
    assignment_values["property_snapshot"] = (
        invalid_snapshot,
        *make_structural_assignment_with().property_snapshot[1:],
    )
    invalid_assignment = StructuralMaterialAssignment.model_construct(
        **assignment_values
    )
    invalid_decision = evaluate_material_authority_policy(
        make_displacement_criterion(), invalid_assignment, make_policy()
    )
    assert invalid_decision.status == "not_evaluable"
    assert invalid_decision.rejection_reasons[0].reason == "missing_conversion_provenance"


def test_criteria_declare_ordered_consumed_properties_and_reject_invalid_values():
    assert MaximumDisplacementCriterion.model_fields["consumed_material_properties"].default == (
        StructuralMaterialPropertyName.ELASTIC_MODULUS,
        StructuralMaterialPropertyName.POISSON_RATIO,
    )
    assert YieldSafetyFactorCriterion.model_fields["consumed_material_properties"].default == (
        StructuralMaterialPropertyName.ELASTIC_MODULUS,
        StructuralMaterialPropertyName.POISSON_RATIO,
        StructuralMaterialPropertyName.YIELD_STRENGTH,
    )
    with pytest.raises(ValidationError):
        MaximumDisplacementCriterion(
            criterion_id="criterion-1",
            load_case_id="case-1",
            assessment_region_id="free-end",
            sampling="nodal_displacement_magnitude_on_region",
            maximum_allowed_displacement_mm=0.0,
            consumed_material_properties=(
                StructuralMaterialPropertyName.ELASTIC_MODULUS,
                StructuralMaterialPropertyName.ELASTIC_MODULUS,
            ),
        )
    with pytest.raises(ValidationError):
        YieldSafetyFactorCriterion(
            criterion_id="criterion-1",
            load_case_id="case-1",
            assessment_region_id="free-end",
            stress_sampling="node_averaged",
            minimum_yield_safety_factor=-1.0,
            zero_stress_tolerance_mpa=0.0,
        )


def test_definition_cross_validation_requires_active_cases_and_references():
    valid = make_definition()
    assert valid.id == "definition-1"
    assert "mesh_specification" not in StructuralAnalysisDefinition.model_fields
    assert structural_definition_hash(valid) == structural_definition_hash(
        StructuralAnalysisDefinition.model_validate(valid.model_dump())
    )

    with pytest.raises(ValidationError):
        make_definition(load_cases=(make_case(active=False),))
    with pytest.raises(ValidationError):
        make_definition(
            acceptance_criteria=(
                make_displacement_criterion().model_copy(
                    update={"load_case_id": "missing-case"}
                ),
            )
        )
    with pytest.raises(ValidationError):
        make_definition(
            material_assignment=make_structural_assignment_without(
                StructuralMaterialPropertyName.ELASTIC_MODULUS
            )
        )


def test_definition_requires_density_for_body_acceleration_but_not_yield():
    base_assignment = make_structural_assignment_with()
    assignment = StructuralMaterialAssignment(
        **{
            **base_assignment.model_dump(),
            "property_snapshot": (
                *base_assignment.property_snapshot[:2],
                make_snapshot(
                    StructuralMaterialPropertyName.DENSITY,
                    value=2700.0,
                    normalized_unit="kg/m^3",
                ),
            ),
        }
    )
    definition = make_definition(
        material_assignment=assignment,
        load_cases=(
            make_case(
                loads=(
                    StructuralBodyAcceleration(
                        load_id="acceleration-1",
                        target_body_id="body-1",
                        acceleration_xyz=(0.0, 0.0, -9810.0),
                        frame="assembly_world",
                    ),
                )
            ),
        ),
        acceptance_criteria=(make_displacement_criterion(),),
    )
    assert definition.material_assignment.property_snapshot

    no_density = make_structural_assignment_without(
        StructuralMaterialPropertyName.DENSITY
    )
    with pytest.raises(ValidationError):
        make_definition(
            material_assignment=no_density,
            load_cases=(
                make_case(
                    loads=(
                        StructuralBodyAcceleration(
                            load_id="acceleration-1",
                            target_body_id="body-1",
                            acceleration_xyz=(0.0, 0.0, -9810.0),
                            frame="assembly_world",
                        ),
                    )
                ),
            ),
        )


def test_definition_hash_is_order_sensitive_for_semantic_tuples():
    first = make_definition()
    second = make_definition(
        load_cases=(
            make_case("case-2", loads=(make_force("force-2"),)),
            make_case("case-1", loads=(make_force("force-1"),)),
        ),
    )
    assert structural_definition_hash(first) != structural_definition_hash(second)


def test_structural_definition_change_invalidates_structural_analysis(tmp_path):
    graph = DependencyGraph.from_yaml("config/dependencies.yaml")
    impact = graph.impact(("/structural_analysis_definitions/DEF-1",))
    assert "analysis.structural" in impact.direct_nodes
    assert "validation.structural" not in impact.direct_nodes
    assert "validation.structural" in impact.all_nodes
