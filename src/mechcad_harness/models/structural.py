import json
import re
from collections.abc import Mapping
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from ..materials import MaterialDataAuthority
from .common import Model


_SelectorParameter = str | int | float | bool


class _ImmutableSelectorParameters(Mapping[str, _SelectorParameter]):
    __slots__ = ("_items", "_hash")

    def __init__(self, items: Mapping[str, _SelectorParameter]):
        object.__setattr__(self, "_items", tuple(sorted(items.items(), key=lambda item: item[0])))
        object.__setattr__(self, "_hash", hash(self._items))

    def __setattr__(self, name, value):
        raise AttributeError("selector parameters are immutable")

    def __delattr__(self, name):
        raise AttributeError("selector parameters are immutable")

    def __getitem__(self, key: str) -> _SelectorParameter:
        for item_key, item_value in self._items:
            if item_key == key:
                return item_value
        raise KeyError(key)

    def __iter__(self):
        for key, _ in self._items:
            yield key

    def __len__(self):
        return len(self._items)

    def __setitem__(self, key, value):
        raise TypeError("selector parameters are immutable")

    def __delitem__(self, key):
        raise TypeError("selector parameters are immutable")

    def clear(self):
        raise TypeError("selector parameters are immutable")

    def pop(self, key, default=None):
        raise TypeError("selector parameters are immutable")

    def popitem(self):
        raise TypeError("selector parameters are immutable")

    def setdefault(self, key, default=None):
        raise TypeError("selector parameters are immutable")

    def update(self, *args, **kwargs):
        raise TypeError("selector parameters are immutable")

    def __ior__(self, other):
        raise TypeError("selector parameters are immutable")

    def __hash__(self):
        return self._hash


def _coerce_selector_parameters(value: object) -> object:
    if isinstance(value, Mapping):
        return dict(value.items())
    return value


def _serialize_selector_parameters(
    value: Mapping[str, _SelectorParameter],
) -> dict[str, _SelectorParameter]:
    return dict(value.items())


_SelectorParameters = Annotated[
    Mapping[str, _SelectorParameter],
    BeforeValidator(_coerce_selector_parameters),
    PlainSerializer(
        _serialize_selector_parameters,
        return_type=dict[str, _SelectorParameter],
    ),
    WithJsonSchema(
        {
            "type": "object",
            "additionalProperties": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "integer"},
                    {"type": "number"},
                    {"type": "boolean"},
                ]
            },
        },
        mode="validation",
    ),
]


_RAW_IDENTITY_PREFIXES = ("face", "edge", "vertex", "topology", "raw_topology", "mesh", "gmsh", "calculix")


def _normalized_selector_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _is_raw_identity_key(value: str) -> bool:
    normalized = _normalized_selector_token(value)
    return any(normalized.startswith(prefix) for prefix in _RAW_IDENTITY_PREFIXES)


def _is_raw_identity_value(value: str) -> bool:
    normalized = _normalized_selector_token(value)
    if re.fullmatch(r"(?:face|edge|vertex)_?\d*", normalized):
        return True
    compact = normalized.replace("_", "")
    if re.fullmatch(r"(?:face|edge|vertex|meshnode|gmshentity|calculixset)[a-z0-9]*", compact):
        return True
    return bool(
        re.match(
            r"^(?:raw_)?topology(?:_|\d|$)|(?:mesh|gmsh|calculix)(?:_|\d|$)",
            normalized,
        )
    )


class StructuralMaterialPropertyName(StrEnum):
    ELASTIC_MODULUS = "elastic_modulus"
    POISSON_RATIO = "poisson_ratio"
    DENSITY = "density"
    YIELD_STRENGTH = "yield_strength"


class StructuralMaterialConversionProvenance(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_unit: str = Field(min_length=1)
    normalization_rule: str = Field(min_length=1)
    conversion_version: str = Field(min_length=1)


class StructuralMaterialPropertySnapshot(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    property_name: StructuralMaterialPropertyName
    value: float
    normalized_unit: str = Field(min_length=1)
    source_identity: str = Field(min_length=1)
    authority: MaterialDataAuthority
    context: str | None = None
    conversion_provenance: StructuralMaterialConversionProvenance

    @model_validator(mode="after")
    def validate_normalized_value(self):
        expected_units = {
            StructuralMaterialPropertyName.ELASTIC_MODULUS: "MPa",
            StructuralMaterialPropertyName.POISSON_RATIO: "ratio",
            StructuralMaterialPropertyName.DENSITY: "kg/m^3",
            StructuralMaterialPropertyName.YIELD_STRENGTH: "MPa",
        }
        if self.normalized_unit != expected_units[self.property_name]:
            raise ValueError(
                f"{self.property_name.value} must use normalized unit "
                f"{expected_units[self.property_name]}"
            )
        if not isfinite(self.value):
            raise ValueError("structural material property value must be finite")
        if self.property_name is StructuralMaterialPropertyName.POISSON_RATIO:
            if not -1 < self.value < 0.5:
                raise ValueError("poisson_ratio must be greater than -1 and less than 0.5")
        elif self.value <= 0:
            raise ValueError("structural material property value must be positive")
        return self


class StructuralMaterialAssignment(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assignment_id: str = Field(min_length=1)
    target_body_id: str = Field(min_length=1)
    material_identity: str = Field(min_length=1)
    assignment_context: str = Field(min_length=1)
    property_snapshot: tuple[StructuralMaterialPropertySnapshot, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_properties(self):
        property_names = [snapshot.property_name for snapshot in self.property_snapshot]
        if len(set(property_names)) != len(property_names):
            raise ValueError("structural material property names must be unique")
        return self


class StructuralPhysicalAssumptions(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_kind: Literal["linear_static_solid"] = "linear_static_solid"
    deformation_model: Literal["small_deformation"] = "small_deformation"
    material_model: Literal["linear_elastic"] = "linear_elastic"
    material_symmetry: Literal["isotropic"] = "isotropic"
    body_scope: Literal["single_solid_body"] = "single_solid_body"


class StructuralAnalysisKind(StrEnum):
    LINEAR_STATIC_SOLID = "linear_static_solid"


class StructuralCoordinateFrame(StrEnum):
    COMPONENT_LOCAL = "component_local"
    ASSEMBLY_WORLD = "assembly_world"


class StructuralDof(StrEnum):
    UX = "ux"
    UY = "uy"
    UZ = "uz"


class StructuralResultField(StrEnum):
    DISPLACEMENT = "displacement"
    VON_MISES_STRESS = "von_mises_stress"
    REACTIONS = "reactions"


class StructuralRegionDefinition(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    region_id: str = Field(min_length=1)
    target_body_id: str = Field(min_length=1)
    source_feature_id: str | None = None
    source_primitive_id: str | None = None
    semantic_role: str = Field(min_length=1)
    geometry_kind: Literal["face", "edge", "volume"]
    selector_kind: str = Field(min_length=1)
    selector_parameters: _SelectorParameters
    expected_cardinality: int = Field(gt=0)
    resolver_version: str = Field(min_length=1)

    @field_validator("selector_parameters", mode="after")
    @classmethod
    def freeze_selector_parameters(cls, value: _SelectorParameters):
        return _ImmutableSelectorParameters(value)

    @model_validator(mode="after")
    def validate_semantic_identity(self):
        if bool(self.source_feature_id) == bool(self.source_primitive_id):
            raise ValueError(
                "exactly one nonempty structural region source identity is required"
            )
        if _is_raw_identity_key(self.selector_kind):
            raise ValueError("raw solver or topology selectors are not canonical regions")
        for key, value in self.selector_parameters.items():
            if _is_raw_identity_key(key):
                raise ValueError("raw topology or solver identity parameters are not canonical regions")
            if isinstance(value, str) and _is_raw_identity_value(value):
                raise ValueError("raw topology or solver identity values are not canonical regions")
            if isinstance(value, float) and not isfinite(value):
                raise ValueError("structural region selector parameters must be finite")
        return self


class StructuralResultantForce(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["resultant_force"] = "resultant_force"
    load_id: str = Field(min_length=1)
    target_region_id: str = Field(min_length=1)
    magnitude_n: float
    direction_xyz: tuple[float, float, float]
    frame: StructuralCoordinateFrame
    distribution: Literal["uniform_surface_traction_equivalent"]

    @model_validator(mode="after")
    def validate_force(self):
        if not isfinite(self.magnitude_n) or self.magnitude_n <= 0:
            raise ValueError("resultant force magnitude must be finite and positive")
        if not all(isfinite(component) for component in self.direction_xyz):
            raise ValueError("resultant force direction must be finite")
        if all(component == 0 for component in self.direction_xyz):
            raise ValueError("resultant force direction must be nonzero")
        return self


class StructuralSurfacePressure(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["surface_pressure"] = "surface_pressure"
    load_id: str = Field(min_length=1)
    target_region_id: str = Field(min_length=1)
    pressure_mpa: float
    signed_normal_convention: Literal["outward_positive", "inward_positive"]
    frame: StructuralCoordinateFrame

    @model_validator(mode="after")
    def validate_pressure(self):
        if not isfinite(self.pressure_mpa):
            raise ValueError("surface pressure must be finite")
        return self


class StructuralBodyAcceleration(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["body_acceleration"] = "body_acceleration"
    load_id: str = Field(min_length=1)
    target_body_id: str = Field(min_length=1)
    acceleration_xyz: tuple[float, float, float]
    acceleration_unit: Literal["mm/s^2"] = "mm/s^2"
    frame: StructuralCoordinateFrame

    @model_validator(mode="after")
    def validate_acceleration(self):
        if not all(isfinite(component) for component in self.acceleration_xyz):
            raise ValueError("body acceleration must be finite")
        return self


StructuralLoad = Annotated[
    StructuralResultantForce | StructuralSurfacePressure | StructuralBodyAcceleration,
    Field(discriminator="kind"),
]


class StructuralLoadCase(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    active: bool = True
    loads: tuple[StructuralLoad, ...] = Field(min_length=1)


class StructuralFixedSupport(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    support_id: str = Field(min_length=1)
    target_region_id: str = Field(min_length=1)
    applies_to_load_case_ids: tuple[str, ...] = Field(min_length=1)
    frame: StructuralCoordinateFrame
    constrained_dofs: tuple[StructuralDof, ...]

    @model_validator(mode="after")
    def validate_fixed_translation(self):
        if len(set(self.applies_to_load_case_ids)) != len(self.applies_to_load_case_ids):
            raise ValueError("fixed support load-case IDs must be unique")
        if self.constrained_dofs != (
            StructuralDof.UX,
            StructuralDof.UY,
            StructuralDof.UZ,
        ):
            raise ValueError("fixed support must constrain ux, uy, and uz in canonical order")
        return self


class StructuralPropertyAuthorityRule(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    property_name: StructuralMaterialPropertyName
    allowed_authorities: tuple[MaterialDataAuthority, ...] = Field(min_length=1)


class AcceptanceMaterialAuthorityPolicy(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_authorities_by_property: tuple[StructuralPropertyAuthorityRule, ...]

    @model_validator(mode="after")
    def validate_unique_properties(self):
        property_names = [
            rule.property_name for rule in self.allowed_authorities_by_property
        ]
        if len(set(property_names)) != len(property_names):
            raise ValueError("material authority policy property names must be unique")
        return self


class MaximumDisplacementCriterion(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["maximum_displacement"] = "maximum_displacement"
    criterion_id: str = Field(min_length=1)
    load_case_id: str = Field(min_length=1)
    assessment_region_id: str = Field(min_length=1)
    sampling: Literal["nodal_displacement_magnitude_on_region"] = (
        "nodal_displacement_magnitude_on_region"
    )
    consumed_material_properties: tuple[StructuralMaterialPropertyName, ...] = (
        StructuralMaterialPropertyName.ELASTIC_MODULUS,
        StructuralMaterialPropertyName.POISSON_RATIO,
    )
    maximum_allowed_displacement_mm: float

    @model_validator(mode="after")
    def validate_criterion(self):
        _validate_consumed_properties(self.consumed_material_properties)
        if (
            not isfinite(self.maximum_allowed_displacement_mm)
            or self.maximum_allowed_displacement_mm <= 0
        ):
            raise ValueError("maximum allowed displacement must be finite and positive")
        return self


class YieldSafetyFactorCriterion(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["yield_safety_factor"] = "yield_safety_factor"
    criterion_id: str = Field(min_length=1)
    load_case_id: str = Field(min_length=1)
    assessment_region_id: str = Field(min_length=1)
    stress_sampling: Literal[
        "element_integration_point",
        "element_nodal_extrapolated",
        "node_averaged",
    ] = "element_integration_point"
    consumed_material_properties: tuple[StructuralMaterialPropertyName, ...] = (
        StructuralMaterialPropertyName.ELASTIC_MODULUS,
        StructuralMaterialPropertyName.POISSON_RATIO,
        StructuralMaterialPropertyName.YIELD_STRENGTH,
    )
    minimum_yield_safety_factor: float
    zero_stress_tolerance_mpa: float

    @model_validator(mode="after")
    def validate_criterion(self):
        _validate_consumed_properties(self.consumed_material_properties)
        if (
            not isfinite(self.minimum_yield_safety_factor)
            or self.minimum_yield_safety_factor <= 0
        ):
            raise ValueError("minimum yield safety factor must be finite and positive")
        if (
            not isfinite(self.zero_stress_tolerance_mpa)
            or self.zero_stress_tolerance_mpa <= 0
        ):
            raise ValueError("zero stress tolerance must be finite and positive")
        return self


StructuralCriterion = Annotated[
    MaximumDisplacementCriterion | YieldSafetyFactorCriterion,
    Field(discriminator="kind"),
]


class StructuralMaterialAuthorityRejection(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    property_name: StructuralMaterialPropertyName
    reason: Literal[
        "missing_snapshot",
        "disallowed_authority",
        "invalid_unit",
        "missing_conversion_provenance",
    ]


class StructuralMaterialAuthorityDecision(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["eligible", "not_evaluable"]
    consumed_property_names: tuple[StructuralMaterialPropertyName, ...]
    rejection_reasons: tuple[StructuralMaterialAuthorityRejection, ...] = ()


class StructuralAnalysisDefinition(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    analysis_kind: StructuralAnalysisKind = StructuralAnalysisKind.LINEAR_STATIC_SOLID
    target_body_id: str = Field(min_length=1)
    regions: tuple[StructuralRegionDefinition, ...]
    material_assignment: StructuralMaterialAssignment
    load_cases: tuple[StructuralLoadCase, ...] = Field(min_length=1)
    boundary_conditions: tuple[StructuralFixedSupport, ...] = ()
    acceptance_criteria: tuple[StructuralCriterion, ...] = ()
    material_authority_policy: AcceptanceMaterialAuthorityPolicy
    physical_assumptions: StructuralPhysicalAssumptions = Field(
        default_factory=StructuralPhysicalAssumptions
    )

    @model_validator(mode="after")
    def validate_definition(self):
        if self.analysis_kind is not StructuralAnalysisKind.LINEAR_STATIC_SOLID:
            raise ValueError("unsupported structural analysis kind")
        if self.material_assignment.target_body_id != self.target_body_id:
            raise ValueError("material assignment target body does not match definition")

        active_cases = {case.id: case for case in self.load_cases if case.active}
        load_case_ids = {case.id for case in self.load_cases}
        if not active_cases:
            raise ValueError("structural definition requires an active load case")
        if len(load_case_ids) != len(self.load_cases):
            raise ValueError("structural load-case IDs must be unique")

        region_ids = {region.region_id for region in self.regions}
        if len(region_ids) != len(self.regions):
            raise ValueError("structural region IDs must be unique")
        if any(region.target_body_id != self.target_body_id for region in self.regions):
            raise ValueError("structural region target body does not match definition")

        loads = tuple(load for case in self.load_cases for load in case.loads)
        load_ids = {load.load_id for load in loads}
        if len(load_ids) != len(loads):
            raise ValueError("structural load IDs must be unique")
        for load in loads:
            if isinstance(load, (StructuralResultantForce, StructuralSurfacePressure)):
                if load.target_region_id not in region_ids:
                    raise ValueError("load references an unknown structural region")
            elif load.target_body_id != self.target_body_id:
                raise ValueError("body acceleration target body does not match definition")

        support_ids = {support.support_id for support in self.boundary_conditions}
        if len(support_ids) != len(self.boundary_conditions):
            raise ValueError("structural support IDs must be unique")
        for support in self.boundary_conditions:
            if support.target_region_id not in region_ids:
                raise ValueError("support references an unknown structural region")
            if any(
                case_id not in active_cases
                for case_id in support.applies_to_load_case_ids
            ):
                raise ValueError("support must reference defined active load cases")

        criterion_ids = {
            criterion.criterion_id for criterion in self.acceptance_criteria
        }
        if len(criterion_ids) != len(self.acceptance_criteria):
            raise ValueError("structural criterion IDs must be unique")
        policy_names = {
            rule.property_name
            for rule in self.material_authority_policy.allowed_authorities_by_property
        }
        for criterion in self.acceptance_criteria:
            if criterion.load_case_id not in active_cases:
                raise ValueError("criterion must reference an active load case")
            if criterion.assessment_region_id not in region_ids:
                raise ValueError("criterion references an unknown structural region")
            if any(
                property_name not in policy_names
                for property_name in criterion.consumed_material_properties
            ):
                raise ValueError("criterion property is missing from authority policy")

        snapshots = {
            snapshot.property_name: snapshot
            for snapshot in self.material_assignment.property_snapshot
        }
        required_properties = {
            StructuralMaterialPropertyName.ELASTIC_MODULUS,
            StructuralMaterialPropertyName.POISSON_RATIO,
        }
        if any(isinstance(load, StructuralBodyAcceleration) for load in loads):
            required_properties.add(StructuralMaterialPropertyName.DENSITY)
        missing_properties = required_properties.difference(snapshots)
        if missing_properties:
            raise ValueError(
                "structural definition is missing required material properties: "
                + ", ".join(sorted(property_name.value for property_name in missing_properties))
            )
        return self


def _validate_consumed_properties(
    property_names: tuple[StructuralMaterialPropertyName, ...],
) -> None:
    if not property_names:
        raise ValueError("criterion must consume at least one material property")
    if len(set(property_names)) != len(property_names):
        raise ValueError("criterion material properties must be unique")


def evaluate_material_authority_policy(
    criterion: StructuralCriterion,
    assignment: StructuralMaterialAssignment,
    policy: AcceptanceMaterialAuthorityPolicy,
) -> StructuralMaterialAuthorityDecision:
    consumed = criterion.consumed_material_properties
    snapshots = {
        snapshot.property_name: snapshot for snapshot in assignment.property_snapshot
    }
    rules = {
        rule.property_name: rule
        for rule in policy.allowed_authorities_by_property
    }
    expected_units = {
        StructuralMaterialPropertyName.ELASTIC_MODULUS: "MPa",
        StructuralMaterialPropertyName.POISSON_RATIO: "ratio",
        StructuralMaterialPropertyName.DENSITY: "kg/m^3",
        StructuralMaterialPropertyName.YIELD_STRENGTH: "MPa",
    }
    rejections: list[StructuralMaterialAuthorityRejection] = []
    for property_name in consumed:
        snapshot = snapshots.get(property_name)
        if snapshot is None:
            rejections.append(
                StructuralMaterialAuthorityRejection(
                    property_name=property_name, reason="missing_snapshot"
                )
            )
            continue
        rule = rules.get(property_name)
        if rule is None or snapshot.authority not in rule.allowed_authorities:
            rejections.append(
                StructuralMaterialAuthorityRejection(
                    property_name=property_name, reason="disallowed_authority"
                )
            )
            continue
        if snapshot.normalized_unit != expected_units[property_name]:
            rejections.append(
                StructuralMaterialAuthorityRejection(
                    property_name=property_name, reason="invalid_unit"
                )
            )
            continue
        provenance = snapshot.conversion_provenance
        if provenance is None or not all(
            (provenance.source_unit, provenance.normalization_rule, provenance.conversion_version)
        ):
            rejections.append(
                StructuralMaterialAuthorityRejection(
                    property_name=property_name,
                    reason="missing_conversion_provenance",
                )
            )
    return StructuralMaterialAuthorityDecision(
        status="not_evaluable" if rejections else "eligible",
        consumed_property_names=consumed,
        rejection_reasons=tuple(rejections),
    )


def structural_definition_hash(definition: StructuralAnalysisDefinition) -> str:
    payload = json.dumps(
        definition.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()
