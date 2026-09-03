from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Iterator, Literal, Mapping, TypeAlias, Union

from pydantic import ConfigDict, Field, field_validator, model_validator

from .common import Model
from .quaternion import normalize_direction, normalize_quaternion

if TYPE_CHECKING:
    from .supplied_component_interface import (
        SuppliedComponentInterfaceDefinition,
        SuppliedComponentReferenceFrame,
    )


_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def _canonical_json(value: Any) -> bytes:
    # Defer the state package import so generated models can be loaded while
    # the canonical physical model is still initializing.
    from mechcad_harness.state.hashing import canonical_json

    return canonical_json(value)


def _require_hash(value: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ValueError("must be a sha256 hash")
    return value


def _hash_or_pending(value: str) -> str:
    if value == "pending":
        return value
    return _require_hash(value)


def _safe_id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID_RE.fullmatch(value):
        raise ValueError("must be a SAFE_ID")
    return value


def _nonblank(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _finite_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("must be a scalar number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("must be finite")
    return value


def _strict_finite_float(value: Any) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("must be a finite float")
    return value


def value_hash(value: float) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(float(value))).hexdigest()


class GeneratedAuthoritySourceKind(StrEnum):
    COMPONENT_PROPERTY = "component_property"
    DESIGN_SELECTION = "design_selection"
    M13_1_INTERFACE_FACT = "m13_1_interface_fact"


class GeneratedAuthorityRole(StrEnum):
    DIMENSION = "dimension"
    SELECTED_DIAMETER = "selected_diameter"
    SUPPLIED_DIAMETER = "supplied_diameter"
    CLEARANCE = "clearance"
    AXIAL_OFFSET = "axial_offset"
    CLOCKING_ANGLE = "clocking_angle"


class GeneratedSelectionNameForm(StrEnum):
    COMPONENT_SCOPED = "component_scoped"
    INSTANCE_SCOPED = "instance_scoped"


GENERATED_AUTHORITY_SOURCE_KINDS = tuple(item.value for item in GeneratedAuthoritySourceKind)
GENERATED_AUTHORITY_ROLES = tuple(item.value for item in GeneratedAuthorityRole)
GENERATED_SELECTION_NAME_FORMS = tuple(item.value for item in GeneratedSelectionNameForm)

GENERATED_PART_RULES = (
    "hub-bore-from-supplied-shaft@1",
    "hub-bore-from-supplied-shaft-with-clearance@1",
)
GENERATED_INTERFACE_RULES = (
    "generated-shaft-interface@1",
    "generated-hub-interface@1",
    "generated-frame-faces@1",
)

FIELD_SLOTS = (
    "shaft.diameter_mm",
    "shaft.length_mm",
    "hub.outer_diameter_mm",
    "hub.length_mm",
    "frame.length_mm",
    "frame.width_mm",
    "frame.height_mm",
)

# Public aliases keep the closed vocabulary discoverable without introducing a
# second taxonomy for authority or interface semantics.
GENERATED_AUTHORITY_INPUT_SOURCE_KINDS = GENERATED_AUTHORITY_SOURCE_KINDS
GENERATED_AUTHORITY_INPUT_ROLES = GENERATED_AUTHORITY_ROLES
GENERATED_FIELD_SLOTS = FIELD_SLOTS
GENERATED_PART_FIELD_SLOTS = FIELD_SLOTS
GENERATED_FIELD_BINDING_RULES = GENERATED_PART_RULES
GENERATED_INTERFACE_DERIVATION_RULES = GENERATED_INTERFACE_RULES

_INSTANCE_RELATIVE_SELECTION_RE = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9_-]*|geometry\.[A-Za-z][A-Za-z0-9_-]*|placement\.axial_offset_mm)"
)
_COMPONENT_RAW_SELECTION_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


def selection_hash(
    name_form: str | Mapping[str, Any], selection_key: str | None = None, value: float | None = None
) -> str:
    if isinstance(name_form, Mapping):
        payload = dict(name_form)
    else:
        if selection_key is None or value is None:
            raise ValueError("selection hash requires a name form, key, and value")
        payload = {
            "name_form": str(name_form),
            "selection_key": selection_key,
            "value": float(value),
        }
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def _self_hash(model: Model, hash_field: str) -> str:
    payload = model.model_dump(mode="json")
    payload.pop(hash_field, None)
    return "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()


class ComponentPropertyLocator(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    property_key: str = Field(min_length=1)

    _validate_key = field_validator("property_key")(_nonblank)


class DesignSelectionLocator(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name_form: GeneratedSelectionNameForm
    selection_key: str = Field(min_length=1)
    selection_hash: str

    _validate_key = field_validator("selection_key")(_nonblank)
    _validate_hash = field_validator("selection_hash")(_require_hash)

    @model_validator(mode="after")
    def validate_selection_key(self) -> "DesignSelectionLocator":
        if self.name_form is GeneratedSelectionNameForm.COMPONENT_SCOPED:
            if not _COMPONENT_RAW_SELECTION_RE.fullmatch(self.selection_key):
                raise ValueError("component-scoped selection key must be a raw semantic key")
        elif not _INSTANCE_RELATIVE_SELECTION_RE.fullmatch(self.selection_key):
            raise ValueError("instance-scoped selection key must be a relative alias")
        return self


class M13_1InterfaceFactLocator(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_hash: str
    fact_id: str = Field(min_length=1)
    accepted_evidence_id: str = Field(min_length=1)
    value_hash: str

    _validate_hashes = field_validator("interface_hash", "value_hash")(_require_hash)
    _validate_ids = field_validator("fact_id", "accepted_evidence_id")(_nonblank)


AuthorityLocator: TypeAlias = Union[
    ComponentPropertyLocator, DesignSelectionLocator, M13_1InterfaceFactLocator
]


class GeneratedAuthorityInput(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_id: str = Field(min_length=1)
    role: GeneratedAuthorityRole
    source_kind: GeneratedAuthoritySourceKind
    locator: AuthorityLocator
    value: float
    value_hash: str = "pending"
    input_hash: str = "pending"

    _validate_id = field_validator("input_id")(_safe_id)
    _validate_value = field_validator("value", mode="before")(_strict_finite_float)
    _validate_hashes = field_validator("value_hash", "input_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_input(self) -> "GeneratedAuthorityInput":
        expected_value_hash = value_hash(self.value)
        if self.value_hash == "pending":
            object.__setattr__(self, "value_hash", expected_value_hash)
        elif self.value_hash != expected_value_hash:
            raise ValueError("generated authority input value hash mismatch")

        if self.source_kind is GeneratedAuthoritySourceKind.COMPONENT_PROPERTY:
            if not isinstance(self.locator, ComponentPropertyLocator):
                raise ValueError("component property input has an invalid locator")
        elif self.source_kind is GeneratedAuthoritySourceKind.DESIGN_SELECTION:
            if not isinstance(self.locator, DesignSelectionLocator):
                raise ValueError("design selection input has an invalid locator")
            expected_selection_hash = selection_hash(
                self.locator.name_form.value, self.locator.selection_key, self.value
            )
            if self.locator.selection_hash != expected_selection_hash:
                raise ValueError("design selection hash mismatch")
        elif not isinstance(self.locator, M13_1InterfaceFactLocator):
            raise ValueError("M13-1 interface input has an invalid locator")
        elif self.locator.value_hash != expected_value_hash:
            raise ValueError("M13-1 interface locator value hash mismatch")

        expected = _self_hash(self, "input_hash")
        if self.input_hash == "pending":
            object.__setattr__(self, "input_hash", expected)
        elif self.input_hash != expected:
            raise ValueError("generated authority input hash mismatch")
        return self


class DirectGeneratedFieldSource(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_id: str = Field(min_length=1)

    _validate_id = field_validator("input_id")(_safe_id)


class RelationGeneratedFieldSource(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    input_ids: tuple[str, ...]

    _validate_rule = field_validator("rule_id")(_nonblank)

    @field_validator("input_ids")
    @classmethod
    def validate_input_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _SAFE_ID_RE.fullmatch(value) for value in values):
            raise ValueError("relation input IDs must be SAFE_IDs")
        if len(set(values)) != len(values):
            raise ValueError("relation input IDs must be unique")
        return values


FieldBindingSource: TypeAlias = Union[DirectGeneratedFieldSource, RelationGeneratedFieldSource]


class GeneratedPartFieldBinding(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    field_slot: str
    source: FieldBindingSource
    field_value_hash: str
    binding_hash: str = "pending"

    _validate_field_hash = field_validator("field_value_hash")(_require_hash)
    _validate_hash = field_validator("binding_hash")(_hash_or_pending)

    @model_validator(mode="after")
    def validate_binding(self) -> "GeneratedPartFieldBinding":
        if not _valid_field_slot(self.field_slot):
            raise ValueError("field slot is outside the closed generated-part vocabulary")
        if isinstance(self.source, RelationGeneratedFieldSource):
            rule = _RULES.get(self.source.rule_id)
            if rule is None:
                raise ValueError("unknown generated field rule")
            if len(self.source.input_ids) != len(rule[0]):
                raise ValueError("generated field rule arity mismatch")
            if not self.field_slot.startswith("hub.bore:") or not self.field_slot.endswith(
                ".diameter_mm"
            ):
                raise ValueError("generated field relation targets a bore diameter only")
        expected = _self_hash(self, "binding_hash")
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected)
        elif self.binding_hash != expected:
            raise ValueError("generated field binding hash mismatch")
        return self


class GeneratedInterfaceDerivation(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: str
    source_slots: tuple[str, ...]

    @field_validator("rule")
    @classmethod
    def validate_rule(cls, value: str) -> str:
        if value not in GENERATED_INTERFACE_RULES:
            raise ValueError("unknown generated interface derivation rule")
        return value

    @field_validator("source_slots")
    @classmethod
    def validate_slots(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values or any(not _valid_field_slot(value) for value in values):
            raise ValueError("generated interface source slots are invalid")
        if len(set(values)) != len(values):
            raise ValueError("generated interface source slots must be unique")
        return values

    @model_validator(mode="after")
    def validate_rule_source_slots(self) -> "GeneratedInterfaceDerivation":
        if not _valid_derivation_source_slots(self.rule, self.source_slots):
            raise ValueError("generated interface source slots do not match its rule")
        return self


def _vector(value: Any, size: int) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)) or len(value) != size:
        raise ValueError(f"expected a vector of length {size}")
    result = tuple(_finite_float(item) for item in value)
    return result


class GeneratedRotationalInterface(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_id: str = Field(min_length=1)
    axis_point: tuple[float, float, float]
    axis_direction: tuple[float, float, float]
    nominal_diameter_mm: float
    usable_engagement_length_mm: float
    derivation: GeneratedInterfaceDerivation
    interface_hash: str = "pending"

    _validate_id = field_validator("interface_id")(_nonblank)
    _validate_hash = field_validator("interface_hash")(_hash_or_pending)
    _validate_point = field_validator("axis_point", mode="before")(
        lambda value: _vector(value, 3)
    )
    _validate_direction = field_validator("axis_direction", mode="before")(
        lambda value: normalize_direction(_vector(value, 3))
    )
    _validate_dims = field_validator("nominal_diameter_mm", "usable_engagement_length_mm", mode="before")(
        _finite_float
    )

    @model_validator(mode="after")
    def validate_interface(self) -> "GeneratedRotationalInterface":
        if self.nominal_diameter_mm <= 0 or self.usable_engagement_length_mm <= 0:
            raise ValueError("generated rotational interface dimensions must be positive")
        if self.derivation.rule == "generated-shaft-interface@1":
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*:shaft", self.interface_id):
                raise ValueError("generated shaft interface ID is invalid")
            if self.axis_point != (0.0, 0.0, 0.0) or self.axis_direction != (0.0, 0.0, 1.0):
                raise ValueError("generated shaft interface axis is invalid")
        elif self.derivation.rule == "generated-hub-interface@1":
            match = re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_.-]*:bore:([A-Za-z][A-Za-z0-9_.-]*):(near|far)",
                self.interface_id,
            )
            if match is None:
                raise ValueError("generated hub interface ID is invalid")
            bore_id, side = match.groups()
            expected_slots = (
                f"hub.bore:{bore_id}.diameter_mm",
                f"hub.bore:{bore_id}.depth_mm",
            )
            if self.derivation.source_slots != expected_slots:
                raise ValueError("generated hub interface source slots do not match its bore")
            expected_direction = (0.0, 0.0, 1.0 if side == "near" else -1.0)
            if self.axis_direction != expected_direction:
                raise ValueError("generated hub interface mouth direction is invalid")
            if side == "near" and self.axis_point != (0.0, 0.0, 0.0):
                raise ValueError("generated near mouth point is invalid")
            if side == "far" and (
                self.axis_point[0] != 0.0
                or self.axis_point[1] != 0.0
                or self.axis_point[2] <= 0.0
            ):
                raise ValueError("generated far mouth point is invalid")
        else:
            raise ValueError("generated rotational interface rule is invalid")
        expected = _self_hash(self, "interface_hash")
        if self.interface_hash == "pending":
            object.__setattr__(self, "interface_hash", expected)
        elif self.interface_hash != expected:
            raise ValueError("generated rotational interface hash mismatch")
        return self


class GeneratedAttachmentFaceInterface(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    interface_id: str = Field(min_length=1)
    plane_point: tuple[float, float, float]
    outward_normal: tuple[float, float, float]
    derivation: GeneratedInterfaceDerivation
    interface_hash: str = "pending"

    _validate_id = field_validator("interface_id")(_nonblank)
    _validate_hash = field_validator("interface_hash")(_hash_or_pending)
    _validate_point = field_validator("plane_point", mode="before")(
        lambda value: _vector(value, 3)
    )
    _validate_normal = field_validator("outward_normal", mode="before")(
        lambda value: normalize_direction(_vector(value, 3))
    )

    @model_validator(mode="after")
    def validate_interface(self) -> "GeneratedAttachmentFaceInterface":
        if self.derivation.rule != "generated-frame-faces@1":
            raise ValueError("generated attachment interface rule is invalid")
        match = re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_.-]*:face:([+-][xyz])", self.interface_id
        )
        if match is None:
            raise ValueError("generated attachment interface ID is invalid")
        side = match.group(1)
        expected_normal = {
            "-x": (-1.0, 0.0, 0.0),
            "+x": (1.0, 0.0, 0.0),
            "-y": (0.0, -1.0, 0.0),
            "+y": (0.0, 1.0, 0.0),
            "-z": (0.0, 0.0, -1.0),
            "+z": (0.0, 0.0, 1.0),
        }[side]
        if self.outward_normal != expected_normal:
            raise ValueError("generated attachment interface normal is invalid")
        axis = "xyz".index(side[1])
        if (side[0] == "-" and self.plane_point[axis] != 0.0) or (
            side[0] == "+" and self.plane_point[axis] <= 0.0
        ):
            raise ValueError("generated attachment interface plane is invalid")
        if any(value <= 0.0 for index, value in enumerate(self.plane_point) if index != axis):
            raise ValueError("generated attachment interface point is invalid")
        expected = _self_hash(self, "interface_hash")
        if self.interface_hash == "pending":
            object.__setattr__(self, "interface_hash", expected)
        elif self.interface_hash != expected:
            raise ValueError("generated attachment interface hash mismatch")
        return self


class GeneratedReferenceFrame(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_id: str = Field(min_length=1)
    origin: tuple[float, float, float]
    orientation: tuple[float, float, float, float]
    derivation: GeneratedInterfaceDerivation
    frame_hash: str = "pending"

    _validate_id = field_validator("frame_id")(_nonblank)
    _validate_hash = field_validator("frame_hash")(_hash_or_pending)
    _validate_origin = field_validator("origin", mode="before")(
        lambda value: _vector(value, 3)
    )
    _validate_orientation = field_validator("orientation", mode="before")(
        lambda value: normalize_quaternion(_vector(value, 4))
    )

    @model_validator(mode="after")
    def validate_frame(self) -> "GeneratedReferenceFrame":
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*:frame", self.frame_id):
            raise ValueError("generated reference frame ID is invalid")
        if self.origin != (0.0, 0.0, 0.0) or self.orientation != (1.0, 0.0, 0.0, 0.0):
            raise ValueError("generated reference frame pose is invalid")
        expected = _self_hash(self, "frame_hash")
        if self.frame_hash == "pending":
            object.__setattr__(self, "frame_hash", expected)
        elif self.frame_hash != expected:
            raise ValueError("generated reference frame hash mismatch")
        return self


class HubBoreSegment(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bore_id: str = Field(min_length=1)
    diameter_mm: float
    start_z_mm: float
    depth_mm: float

    _validate_id = field_validator("bore_id")(_safe_id)
    _validate_numbers = field_validator(
        "diameter_mm", "start_z_mm", "depth_mm", mode="before"
    )(_finite_float)

    @model_validator(mode="after")
    def validate_bore(self) -> "HubBoreSegment":
        if self.diameter_mm <= 0 or self.depth_mm <= 0 or self.start_z_mm < 0:
            raise ValueError("hub bore dimensions are invalid")
        return self


def _valid_field_slot(slot: str) -> bool:
    if slot in FIELD_SLOTS:
        return True
    match = re.fullmatch(r"hub\.bore:([A-Za-z][A-Za-z0-9_.-]*)\.(diameter_mm|start_z_mm|depth_mm)", slot)
    return match is not None


def _valid_derivation_source_slots(rule: str, slots: tuple[str, ...]) -> bool:
    if rule == "generated-shaft-interface@1":
        return slots == ("shaft.diameter_mm", "shaft.length_mm")
    if rule == "generated-frame-faces@1":
        return slots == ("frame.length_mm", "frame.width_mm", "frame.height_mm")
    if rule == "generated-hub-interface@1":
        if len(slots) < 2 or len(slots) % 2:
            return False
        bore_ids = []
        for diameter_slot, depth_slot in zip(slots[::2], slots[1::2]):
            diameter_match = re.fullmatch(
                r"hub\.bore:([A-Za-z][A-Za-z0-9_.-]*)\.diameter_mm", diameter_slot
            )
            depth_match = re.fullmatch(
                r"hub\.bore:([A-Za-z][A-Za-z0-9_.-]*)\.depth_mm", depth_slot
            )
            if (
                diameter_match is None
                or depth_match is None
                or diameter_match.group(1) != depth_match.group(1)
            ):
                return False
            bore_ids.append(diameter_match.group(1))
        return len(set(bore_ids)) == len(bore_ids)
    return False


_RULES = {
    "hub-bore-from-supplied-shaft@1": (("supplied_diameter",), lambda values: values[0]),
    "hub-bore-from-supplied-shaft-with-clearance@1": (
        ("supplied_diameter", "clearance"),
        lambda values: values[0] + values[1],
    ),
}


def evaluate_generated_field_rule(
    binding_or_rule: GeneratedPartFieldBinding | str,
    values: Mapping[str, float],
) -> float:
    if isinstance(binding_or_rule, GeneratedPartFieldBinding):
        source = binding_or_rule.source
        if isinstance(source, DirectGeneratedFieldSource):
            input_ids = (source.input_id,)
            rule = None
        else:
            input_ids = source.input_ids
            rule = _RULES.get(source.rule_id)
            if rule is None:
                raise GeneratedAuthorityError("unknown generated field rule")
    else:
        rule = _RULES.get(binding_or_rule)
        if rule is None:
            raise GeneratedAuthorityError("unknown generated field rule")
        input_ids = tuple(values)
    try:
        resolved = tuple(float(values[input_id]) for input_id in input_ids)
    except (KeyError, TypeError, ValueError) as exc:
        raise GeneratedAuthorityError("generated field relation input is missing") from exc
    if rule is None:
        result = resolved[0]
    else:
        expected_roles, evaluator = rule
        if len(resolved) != len(expected_roles):
            raise GeneratedAuthorityError("generated field rule arity mismatch")
        result = evaluator(resolved)
    if not math.isfinite(result):
        raise GeneratedAuthorityError("generated field relation result is not finite")
    if isinstance(binding_or_rule, GeneratedPartFieldBinding) and value_hash(result) != binding_or_rule.field_value_hash:
        raise GeneratedAuthorityError("generated field value hash mismatch")
    return result


class GeneratedAuthorityError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedAuthorityView:
    component_properties: Mapping[str, Any] | tuple[Any, ...] = field(default_factory=dict)
    design_selections: Mapping[str, Any] | tuple[Any, ...] = field(default_factory=dict)
    interface_definitions: (
        Mapping[str, "SuppliedComponentInterfaceDefinition"]
        | tuple["SuppliedComponentInterfaceDefinition", ...]
    ) = ()
    supplied_interfaces: (
        Mapping[str, "SuppliedComponentInterfaceDefinition"]
        | tuple["SuppliedComponentInterfaceDefinition", ...]
    ) = ()
    reference_frames: (
        Mapping[str, "SuppliedComponentReferenceFrame"]
        | tuple["SuppliedComponentReferenceFrame", ...]
    ) = ()
    generated_interfaces: (
        Mapping[str, GeneratedRotationalInterface]
        | tuple[GeneratedRotationalInterface, ...]
    ) = ()


def _view_value(record: Any, key: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(key)
    return getattr(record, key, None)


def _iter_typed_model_facts(value: Any) -> Iterator[Any]:
    from .supplied_component_interface import SuppliedInterfaceFact

    if isinstance(value, SuppliedInterfaceFact):
        yield value
        return
    if isinstance(value, Model):
        for field_name in type(value).model_fields:
            yield from _iter_typed_model_facts(getattr(value, field_name))
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_typed_model_facts(nested)
    elif isinstance(value, (tuple, list)):
        for nested in value:
            yield from _iter_typed_model_facts(nested)


def _lookup(records: Mapping[str, Any] | tuple[Any, ...], key: str, *names: str) -> Any:
    if isinstance(records, Mapping):
        record = records.get(key)
    else:
        record = next(
            (
                candidate
                for candidate in records
                if any(_view_value(candidate, name) == key for name in names)
            ),
            None,
        )
    return record


def _resolve_selection(view: GeneratedAuthorityView, locator: DesignSelectionLocator, owner: str | None) -> Any:
    if locator.name_form is GeneratedSelectionNameForm.INSTANCE_SCOPED and not _INSTANCE_RELATIVE_SELECTION_RE.fullmatch(
        locator.selection_key
    ):
        raise GeneratedAuthorityError("instance-scoped selection key must be a relative alias")
    if locator.name_form is GeneratedSelectionNameForm.COMPONENT_SCOPED:
        key = locator.selection_key
    else:
        if owner is None or not owner.strip():
            raise GeneratedAuthorityError("instance-scoped selection requires an owning instance")
        key = f"{owner}.{locator.selection_key}"
    record = _lookup(view.design_selections, key, "name", "key", "selection_key")
    if record is None:
        raise GeneratedAuthorityError("design selection cannot be resolved")
    if isinstance(record, (int, float, bool)):
        return record
    if isinstance(record, Mapping):
        identities = [record[name] for name in ("name", "key", "selection_key") if name in record]
    else:
        identities = [
            getattr(record, name)
            for name in ("name", "key", "selection_key")
            if hasattr(record, name)
        ]
    if not identities or any(identity != key for identity in identities):
        raise GeneratedAuthorityError("design selection record identity does not match its key")
    return _view_value(record, "value")


def _resolve_interface_fact(
    view: GeneratedAuthorityView, locator: M13_1InterfaceFactLocator
) -> Any:
    from .supplied_component_interface import (
        SuppliedComponentInterfaceDefinition,
        SuppliedComponentReferenceFrame,
        require_authoritatively_consumable_interface,
        require_authoritative_fact,
    )

    def resolve_active_frame(
        definition: SuppliedComponentInterfaceDefinition,
    ) -> SuppliedComponentReferenceFrame | None:
        if definition.kind != "materialized":
            return None
        variant = definition.shaft if definition.shaft is not None else definition.mounting_face
        assert variant is not None
        frame_id = getattr(variant, "reference_frame_id", None)
        if frame_id is None:
            return None
        provenance = definition.derivation
        frame_hash = None if provenance is None else provenance.derived_reference_frame_hash
        if frame_hash is None:
            raise GeneratedAuthorityError("M13-1 active reference frame hash is missing")
        records = view.reference_frames
        if isinstance(records, Mapping):
            candidate = records.get(frame_id)
            candidates = () if candidate is None else (candidate,)
        else:
            candidates = tuple(records)
        matches = []
        for candidate in candidates:
            if not isinstance(candidate, SuppliedComponentReferenceFrame):
                continue
            try:
                frame = SuppliedComponentReferenceFrame.model_validate(
                    candidate.model_dump(mode="json")
                )
            except Exception:
                continue
            if frame.frame_id == frame_id and frame.frame_hash == frame_hash:
                matches.append(frame)
        if len(matches) != 1:
            raise GeneratedAuthorityError("M13-1 active reference frame cannot be resolved")
        return matches[0]

    definitions = view.interface_definitions or view.supplied_interfaces
    if isinstance(definitions, Mapping):
        candidate = definitions.get(locator.interface_hash)
        candidates = () if candidate is None else (candidate,)
    else:
        candidates = tuple(definitions)
    matches = []
    for candidate in candidates:
        if not isinstance(candidate, SuppliedComponentInterfaceDefinition):
            continue
        try:
            definition = SuppliedComponentInterfaceDefinition.model_validate(
                candidate.model_dump(mode="json")
            )
        except Exception:
            continue
        if definition.interface_hash == locator.interface_hash:
            matches.append(definition)
    if not matches:
        raise GeneratedAuthorityError("M13-1 interface cannot be resolved")
    resolved_values = []
    for definition in matches:
        try:
            reference_frame = resolve_active_frame(definition)
            require_authoritatively_consumable_interface(definition, reference_frame)
            variants = (getattr(definition, "shaft", None), getattr(definition, "mounting_face", None))
            facts = tuple(
                fact
                for variant in variants
                if variant is not None
                for fact in _iter_typed_model_facts(variant)
                if getattr(fact, "fact_id", None) == locator.fact_id
            )
            if len(facts) != 1:
                raise ValueError("fact is missing or ambiguous in the interface")
            fact = facts[0]
            if definition.kind == "direct":
                evidence = require_authoritative_fact(fact, fact_name=locator.fact_id)
            else:
                evidence = next(
                    (
                        record
                        for record in fact.evidence
                        if record.evidence_id == fact.accepted_evidence_id
                    ),
                    None,
                )
                if evidence is None:
                    raise ValueError("accepted evidence is missing")
            if evidence.evidence_id != locator.accepted_evidence_id:
                raise ValueError("accepted evidence does not match")
            if value_hash(evidence.value) != locator.value_hash:
                raise ValueError("accepted evidence value hash does not match")
            resolved_values.append(evidence.value)
        except Exception as exc:
            raise GeneratedAuthorityError("M13-1 interface fact is not authoritative") from exc
    if not resolved_values or any(value != resolved_values[0] for value in resolved_values):
        raise GeneratedAuthorityError("M13-1 interface fact is ambiguous")
    return resolved_values[0]


def resolve_generated_inputs(
    inputs: tuple[GeneratedAuthorityInput, ...],
    view: GeneratedAuthorityView | None = None,
    owning_instance_context: str | None = None,
) -> dict[str, float]:
    view = view or GeneratedAuthorityView()
    input_ids = tuple(record.input_id for record in inputs)
    if len(set(input_ids)) != len(input_ids):
        raise GeneratedAuthorityError("generated authority input IDs must be unique")
    resolved: dict[str, float] = {}
    for record in inputs:
        try:
            if record.source_kind is GeneratedAuthoritySourceKind.COMPONENT_PROPERTY:
                property_record = _lookup(
                    view.component_properties, record.locator.property_key, "key", "property_key"
                )  # type: ignore[union-attr]
                value = _resolve_component_property(property_record, record.locator.property_key)  # type: ignore[union-attr]
            elif record.source_kind is GeneratedAuthoritySourceKind.DESIGN_SELECTION:
                value = _resolve_selection(view, record.locator, owning_instance_context)  # type: ignore[arg-type]
            else:
                value = _resolve_interface_fact(view, record.locator)  # type: ignore[arg-type]
        except GeneratedAuthorityError:
            raise
        except Exception as exc:
            raise GeneratedAuthorityError("generated authority input cannot be resolved") from exc
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise GeneratedAuthorityError("resolved authority input is not a finite scalar")
        value = float(value)
        if value != record.value or value_hash(value) != record.value_hash:
            raise GeneratedAuthorityError("resolved authority input does not match its bound value")
        resolved[record.input_id] = value
    return resolved


def _record_payload(record: Any) -> dict[str, Any] | None:
    if isinstance(record, Mapping):
        return dict(record)
    model_dump = getattr(record, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        return dict(payload) if isinstance(payload, Mapping) else None
    try:
        return dict(vars(record))
    except (TypeError, ValueError):
        return None


def _resolve_component_property(record: Any, property_key: str) -> Any:
    required_fields = (
        "key",
        "availability",
        "normalized_value",
        "normalized_range",
        "canonical_unit",
        "property_hash",
    )
    payload = _record_payload(record)
    if payload is None or any(name not in payload for name in required_fields):
        raise GeneratedAuthorityError("component property authority metadata is incomplete")
    if payload["key"] != property_key:
        raise GeneratedAuthorityError("component property key does not match its locator")
    availability = getattr(payload["availability"], "value", payload["availability"])
    if availability != "available":
        raise GeneratedAuthorityError("component property is not available")
    if payload["canonical_unit"] != "mm":
        raise GeneratedAuthorityError("component property is not in mm")
    if payload["normalized_range"] is not None:
        raise GeneratedAuthorityError("component property must have one normalized value")
    value = payload["normalized_value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise GeneratedAuthorityError("component property normalized value is not a finite scalar")
    expected_hash = payload.pop("property_hash")
    actual_hash = "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()
    if expected_hash != actual_hash:
        raise GeneratedAuthorityError("component property hash mismatch")
    return value


def _required_slots(part_kind: str, bores: tuple[HubBoreSegment, ...] = ()) -> tuple[str, ...]:
    if part_kind == "solid_circular_shaft":
        return ("shaft.diameter_mm", "shaft.length_mm")
    if part_kind == "rectangular_frame_member":
        return ("frame.length_mm", "frame.width_mm", "frame.height_mm")
    return (
        "hub.outer_diameter_mm",
        "hub.length_mm",
        *(f"hub.bore:{bore.bore_id}.{name}" for bore in bores for name in ("diameter_mm", "start_z_mm", "depth_mm")),
    )


def _validate_authority_bindings(
    inputs: tuple[GeneratedAuthorityInput, ...],
    bindings: tuple[GeneratedPartFieldBinding, ...],
    fields: Mapping[str, float],
    part_kind: str,
    bores: tuple[HubBoreSegment, ...] = (),
) -> None:
    inputs_by_id = {record.input_id: record for record in inputs}
    if len(inputs_by_id) != len(inputs):
        raise ValueError("generated authority input IDs must be unique")
    bindings_by_slot = {binding.field_slot: binding for binding in bindings}
    if len(bindings_by_slot) != len(bindings):
        raise ValueError("generated field slots must have exactly one binding")
    required = set(_required_slots(part_kind, bores))
    if set(bindings_by_slot) != required:
        raise ValueError("every generated geometry field requires exactly one binding")
    resolved_values = {record.input_id: record.value for record in inputs}
    for slot, binding in bindings_by_slot.items():
        if isinstance(binding.source, DirectGeneratedFieldSource):
            record = inputs_by_id.get(binding.source.input_id)
            if record is None:
                raise ValueError("field binding references a missing input")
            result = record.value
        else:
            records = [inputs_by_id.get(input_id) for input_id in binding.source.input_ids]
            if any(record is None for record in records):
                raise ValueError("field relation references a missing input")
            expected_roles, _ = _RULES[binding.source.rule_id]
            if tuple(record.role.value for record in records if record is not None) != expected_roles:
                raise ValueError("field relation input roles are invalid")
            result = evaluate_generated_field_rule(binding, resolved_values)
        if result != fields[slot] or value_hash(fields[slot]) != binding.field_value_hash:
            raise ValueError("generated field binding does not match its field value")


def _derived_frame(part_id: str, rule: str, slots: tuple[str, ...], origin=(0.0, 0.0, 0.0)) -> GeneratedReferenceFrame:
    return GeneratedReferenceFrame(
        frame_id=f"{part_id}:frame",
        origin=origin,
        orientation=(1.0, 0.0, 0.0, 0.0),
        derivation=GeneratedInterfaceDerivation(rule=rule, source_slots=slots),
    )


def derive_shaft_interfaces(spec: "SolidCircularShaftSpecification") -> tuple[GeneratedRotationalInterface, ...]:
    return (
        GeneratedRotationalInterface(
            interface_id=f"{spec.generated_part_id}:shaft",
            axis_point=(0.0, 0.0, 0.0),
            axis_direction=(0.0, 0.0, 1.0),
            nominal_diameter_mm=spec.diameter_mm,
            usable_engagement_length_mm=spec.length_mm,
            derivation=GeneratedInterfaceDerivation(
                rule="generated-shaft-interface@1",
                source_slots=("shaft.diameter_mm", "shaft.length_mm"),
            ),
        ),
    )


def derive_hub_interfaces(spec: "CylindricalHubSpecification") -> tuple[GeneratedRotationalInterface, ...]:
    result = []
    for bore in spec.bores:
        if bore.start_z_mm == 0:
            result.append(
                GeneratedRotationalInterface(
                    interface_id=f"{spec.generated_part_id}:bore:{bore.bore_id}:near",
                    axis_point=(0.0, 0.0, 0.0),
                    axis_direction=(0.0, 0.0, 1.0),
                    nominal_diameter_mm=bore.diameter_mm,
                    usable_engagement_length_mm=bore.depth_mm,
                    derivation=GeneratedInterfaceDerivation(
                        rule="generated-hub-interface@1",
                        source_slots=(
                            f"hub.bore:{bore.bore_id}.diameter_mm",
                            f"hub.bore:{bore.bore_id}.depth_mm",
                        ),
                    ),
                )
            )
        if bore.start_z_mm + bore.depth_mm == spec.length_mm:
            result.append(
                GeneratedRotationalInterface(
                    interface_id=f"{spec.generated_part_id}:bore:{bore.bore_id}:far",
                    axis_point=(0.0, 0.0, spec.length_mm),
                    axis_direction=(0.0, 0.0, -1.0),
                    nominal_diameter_mm=bore.diameter_mm,
                    usable_engagement_length_mm=bore.depth_mm,
                    derivation=GeneratedInterfaceDerivation(
                        rule="generated-hub-interface@1",
                        source_slots=(
                            f"hub.bore:{bore.bore_id}.diameter_mm",
                            f"hub.bore:{bore.bore_id}.depth_mm",
                        ),
                    ),
                )
            )
    return tuple(result)


def derive_frame_interfaces(spec: "RectangularFrameMemberSpecification") -> tuple[GeneratedAttachmentFaceInterface, ...]:
    L, W, H = spec.length_mm, spec.width_mm, spec.height_mm
    faces = (
        ("-x", (0.0, W / 2, H / 2), (-1.0, 0.0, 0.0)),
        ("+x", (L, W / 2, H / 2), (1.0, 0.0, 0.0)),
        ("-y", (L / 2, 0.0, H / 2), (0.0, -1.0, 0.0)),
        ("+y", (L / 2, W, H / 2), (0.0, 1.0, 0.0)),
        ("-z", (L / 2, W / 2, 0.0), (0.0, 0.0, -1.0)),
        ("+z", (L / 2, W / 2, H), (0.0, 0.0, 1.0)),
    )
    slots = ("frame.length_mm", "frame.width_mm", "frame.height_mm")
    return tuple(
        GeneratedAttachmentFaceInterface(
            interface_id=f"{spec.generated_part_id}:face:{side}",
            plane_point=point,
            outward_normal=normal,
            derivation=GeneratedInterfaceDerivation(
                rule="generated-frame-faces@1", source_slots=slots
            ),
        )
        for side, point, normal in faces
    )


class _GeneratedPartBase(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    generated_part_id: str = Field(min_length=1)
    inputs: tuple[GeneratedAuthorityInput, ...]
    field_bindings: tuple[GeneratedPartFieldBinding, ...]
    interfaces: tuple[GeneratedRotationalInterface | GeneratedAttachmentFaceInterface, ...] = ()
    reference_frames: tuple[GeneratedReferenceFrame, ...] = ()
    generated_part_hash: str = "pending"

    _validate_id = field_validator("generated_part_id")(_safe_id)
    _validate_hash = field_validator("generated_part_hash")(_hash_or_pending)

    @field_validator("inputs")
    @classmethod
    def sort_inputs(cls, values: tuple[GeneratedAuthorityInput, ...]) -> tuple[GeneratedAuthorityInput, ...]:
        return tuple(sorted(values, key=lambda record: record.input_id))

    @field_validator("field_bindings")
    @classmethod
    def sort_bindings(cls, values: tuple[GeneratedPartFieldBinding, ...]) -> tuple[GeneratedPartFieldBinding, ...]:
        return tuple(sorted(values, key=lambda record: record.field_slot))

    @property
    def active_interface_ids(self) -> tuple[str, ...]:
        return tuple(interface.interface_id for interface in self.interfaces)

    @property
    def reference_frame(self) -> GeneratedReferenceFrame:
        if len(self.reference_frames) != 1:
            raise GeneratedAuthorityError("generated part does not have exactly one reference frame")
        return self.reference_frames[0]


class SolidCircularShaftSpecification(_GeneratedPartBase):
    part_kind: Literal["solid_circular_shaft"] = "solid_circular_shaft"
    diameter_mm: float
    length_mm: float

    _validate_dimensions = field_validator("diameter_mm", "length_mm", mode="before")(_finite_float)

    @model_validator(mode="after")
    def validate_shaft(self) -> "SolidCircularShaftSpecification":
        if self.diameter_mm <= 0 or self.length_mm <= 0:
            raise ValueError("shaft dimensions must be positive")
        _validate_authority_bindings(
            self.inputs,
            self.field_bindings,
            {"shaft.diameter_mm": self.diameter_mm, "shaft.length_mm": self.length_mm},
            self.part_kind,
        )
        interfaces = derive_shaft_interfaces(self)
        frames = (_derived_frame(self.generated_part_id, "generated-shaft-interface@1", ("shaft.diameter_mm", "shaft.length_mm")),)
        _set_derived_records(self, interfaces, frames)
        return self


class CylindricalHubSpecification(_GeneratedPartBase):
    part_kind: Literal["cylindrical_hub"] = "cylindrical_hub"
    outer_diameter_mm: float
    length_mm: float
    bores: tuple[HubBoreSegment, ...] = Field(min_length=1, max_length=4)

    _validate_dimensions = field_validator("outer_diameter_mm", "length_mm", mode="before")(_finite_float)

    @model_validator(mode="after")
    def validate_hub(self) -> "CylindricalHubSpecification":
        if self.outer_diameter_mm <= 0 or self.length_mm <= 0:
            raise ValueError("hub dimensions must be positive")
        bores = tuple(sorted(self.bores, key=lambda bore: bore.bore_id))
        if len({bore.bore_id for bore in bores}) != len(bores):
            raise ValueError("hub bore IDs must be unique")
        for index, bore in enumerate(bores):
            if bore.diameter_mm >= self.outer_diameter_mm:
                raise ValueError("hub bore diameter must be smaller than stock")
            if bore.start_z_mm + bore.depth_mm > self.length_mm:
                raise ValueError("hub bore is outside the stock extent")
            if any(
                bore.start_z_mm < other.start_z_mm + other.depth_mm
                and other.start_z_mm < bore.start_z_mm + bore.depth_mm
                for other in bores[index + 1 :]
            ):
                raise ValueError("hub bore segments must not overlap")
        object.__setattr__(self, "bores", bores)
        fields = {"hub.outer_diameter_mm": self.outer_diameter_mm, "hub.length_mm": self.length_mm}
        fields.update(
            {
                f"hub.bore:{bore.bore_id}.{name}": getattr(bore, name)
                for bore in bores
                for name in ("diameter_mm", "start_z_mm", "depth_mm")
            }
        )
        _validate_authority_bindings(self.inputs, self.field_bindings, fields, self.part_kind, bores)
        interfaces = derive_hub_interfaces(self)
        slots = tuple(
            slot
            for bore in bores
            for slot in (
                f"hub.bore:{bore.bore_id}.diameter_mm",
                f"hub.bore:{bore.bore_id}.depth_mm",
            )
        )
        frames = (_derived_frame(self.generated_part_id, "generated-hub-interface@1", slots),)
        _set_derived_records(self, interfaces, frames)
        return self


class RectangularFrameMemberSpecification(_GeneratedPartBase):
    part_kind: Literal["rectangular_frame_member"] = "rectangular_frame_member"
    length_mm: float
    width_mm: float
    height_mm: float

    _validate_dimensions = field_validator(
        "length_mm", "width_mm", "height_mm", mode="before"
    )(_finite_float)

    @model_validator(mode="after")
    def validate_frame_member(self) -> "RectangularFrameMemberSpecification":
        if min(self.length_mm, self.width_mm, self.height_mm) <= 0:
            raise ValueError("frame dimensions must be positive")
        _validate_authority_bindings(
            self.inputs,
            self.field_bindings,
            {
                "frame.length_mm": self.length_mm,
                "frame.width_mm": self.width_mm,
                "frame.height_mm": self.height_mm,
            },
            self.part_kind,
        )
        interfaces = derive_frame_interfaces(self)
        frames = (_derived_frame(self.generated_part_id, "generated-frame-faces@1", ("frame.length_mm", "frame.width_mm", "frame.height_mm")),)
        _set_derived_records(self, interfaces, frames)
        return self


def _set_derived_records(part: _GeneratedPartBase, interfaces: tuple[Any, ...], frames: tuple[GeneratedReferenceFrame, ...]) -> None:
    if part.interfaces and tuple(part.interfaces) != interfaces:
        raise ValueError("generated interfaces do not match pure derivation")
    if part.reference_frames and tuple(part.reference_frames) != frames:
        raise ValueError("generated reference frames do not match pure derivation")
    object.__setattr__(part, "interfaces", interfaces)
    object.__setattr__(part, "reference_frames", frames)
    expected = _self_hash(part, "generated_part_hash")
    if part.generated_part_hash == "pending":
        object.__setattr__(part, "generated_part_hash", expected)
    elif part.generated_part_hash != expected:
        raise ValueError("generated part hash mismatch")


GeneratedPartSpecification: TypeAlias = Annotated[
    Union[
        SolidCircularShaftSpecification,
        CylindricalHubSpecification,
        RectangularFrameMemberSpecification,
    ],
    Field(discriminator="part_kind"),
]


def generated_part_hash(spec: GeneratedPartSpecification) -> str:
    return _self_hash(spec, "generated_part_hash")


def input_hash(record: GeneratedAuthorityInput) -> str:
    return _self_hash(record, "input_hash")


def binding_hash(record: GeneratedPartFieldBinding) -> str:
    return _self_hash(record, "binding_hash")


def interface_hash(record: GeneratedRotationalInterface | GeneratedAttachmentFaceInterface) -> str:
    return _self_hash(record, "interface_hash")


def frame_hash(record: GeneratedReferenceFrame) -> str:
    return _self_hash(record, "frame_hash")


def generated_geometry_definition_identities(spec: GeneratedPartSpecification) -> tuple[str, ...]:
    return tuple(
        sorted({record.input_hash for record in spec.inputs} | {binding.binding_hash for binding in spec.field_bindings})
    )


def validate_generated_interface_registry(
    spec: GeneratedPartSpecification, registered_interface_ids: tuple[str, ...]
) -> tuple[str, ...]:
    """Require the enclosing active-interface registry to match this part exactly."""
    expected = spec.active_interface_ids
    if len(set(registered_interface_ids)) != len(registered_interface_ids):
        raise ValueError("generated interface IDs must be unique")
    if tuple(sorted(registered_interface_ids)) != tuple(sorted(expected)):
        raise ValueError("generated interface registry does not match derived interfaces")
    if any(frame.frame_id in registered_interface_ids for frame in spec.reference_frames):
        raise ValueError("generated reference frames are not interface endpoints")
    return expected


__all__ = [
    "AuthorityLocator",
    "ComponentPropertyLocator",
    "CylindricalHubSpecification",
    "DirectGeneratedFieldSource",
    "DesignSelectionLocator",
    "FIELD_SLOTS",
    "GENERATED_AUTHORITY_ROLES",
    "GENERATED_AUTHORITY_SOURCE_KINDS",
    "GENERATED_AUTHORITY_INPUT_ROLES",
    "GENERATED_AUTHORITY_INPUT_SOURCE_KINDS",
    "GENERATED_FIELD_BINDING_RULES",
    "GENERATED_FIELD_SLOTS",
    "GENERATED_INTERFACE_RULES",
    "GENERATED_INTERFACE_DERIVATION_RULES",
    "GENERATED_PART_RULES",
    "GENERATED_PART_FIELD_SLOTS",
    "GENERATED_SELECTION_NAME_FORMS",
    "GeneratedAttachmentFaceInterface",
    "GeneratedAuthorityError",
    "GeneratedAuthorityInput",
    "GeneratedAuthorityRole",
    "GeneratedAuthoritySourceKind",
    "GeneratedAuthorityView",
    "GeneratedInterfaceDerivation",
    "GeneratedPartFieldBinding",
    "GeneratedPartSpecification",
    "GeneratedReferenceFrame",
    "GeneratedRotationalInterface",
    "GeneratedSelectionNameForm",
    "HubBoreSegment",
    "M13_1InterfaceFactLocator",
    "RectangularFrameMemberSpecification",
    "RelationGeneratedFieldSource",
    "SolidCircularShaftSpecification",
    "derive_frame_interfaces",
    "derive_hub_interfaces",
    "derive_shaft_interfaces",
    "evaluate_generated_field_rule",
    "generated_geometry_definition_identities",
    "generated_part_hash",
    "input_hash",
    "binding_hash",
    "interface_hash",
    "frame_hash",
    "resolve_generated_inputs",
    "selection_hash",
    "validate_generated_interface_registry",
    "value_hash",
]
