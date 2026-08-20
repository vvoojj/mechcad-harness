from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from mechcad_harness.models.common import Model


YAGI_CARRIER_LAYOUT_SYNTHESIS_VERSION = "yagi-carrier-layout-synthesis@1.0"
YAGI_CARRIER_FRAME = "carrier-center origin; +X boom/fore-aft; +Y lateral spacing; +Z right-handed"
YAGI_CARRIER_PART_ID = "preliminary_yagi_carrier"
YAGI_CARRIER_OWNER = "mechcad-yagi-carrier"


class YagiCarrierStatus(StrEnum):
    NOT_READY = "not_ready"
    INFEASIBLE = "infeasible"
    SUCCESS = "success"


class NominalLayoutStatus(StrEnum):
    CLEAR = "nominal_layout_clear"
    COLLIDES = "nominal_layout_collides"


class YagiCarrierSlidingInterfaceSection(Model):
    architecture: Literal["native_extrusion_t_slot"]
    continuous_lateral_travel_required: Literal[True]
    clamp_attachment_interface: Literal["t_nut_or_equivalent"]
    exact_extrusion_profile_status: Literal["unresolved"]
    exact_native_t_slot_geometry_status: Literal["unresolved"]
    compatible_t_nut_interface_status: Literal["unresolved"]
    structural_status: Literal["not_verified"]
    manufacturing_status: Literal["preliminary_packaging_geometry_only"]
    selection_version: str = Field(min_length=1)
    selection_hash: str = Field(min_length=1)

    @classmethod
    def from_selection(cls, selection):
        return cls(
            architecture=selection.architecture.value,
            continuous_lateral_travel_required=selection.continuous_lateral_travel_required,
            clamp_attachment_interface=selection.compatible_clamp_attachment,
            exact_extrusion_profile_status=selection.exact_extrusion_profile,
            exact_native_t_slot_geometry_status="unresolved",
            compatible_t_nut_interface_status="unresolved",
            structural_status=selection.structural_verification,
            manufacturing_status=selection.manufacturing_status,
            selection_version=selection.selection_version,
            selection_hash=selection.selection_hash,
        )


class YagiCarrierDesignSpec(Model):
    carrier_id: str = Field(min_length=1)
    carrier_length_mm: float = Field(gt=0)
    carrier_frame: Literal[YAGI_CARRIER_FRAME] = YAGI_CARRIER_FRAME
    lateral_adjustment_min_y_mm: float
    lateral_adjustment_max_y_mm: float
    adjustable_mounting: Literal["continuous_lateral_travel_region"] = "continuous_lateral_travel_region"
    nominal_two_antenna_y_mm: tuple[float, float]
    nominal_three_antenna_y_mm: tuple[float, float, float]
    required_fore_aft_travel_mm: float = Field(gt=0)
    preferred_fore_aft_travel_mm: float = Field(gt=0)
    final_antenna_x_positions_selected: Literal[False] = False
    clamp_architecture: Literal["interchangeable_adjustable_clamps"] = "interchangeable_adjustable_clamps"
    profile_structural_status: Literal["not_structurally_selected"] = "not_structurally_selected"
    structural_verification: Literal["not_verified"] = "not_verified"
    sliding_interface: YagiCarrierSlidingInterfaceSection | None = None
    provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_geometry(self):
        if self.lateral_adjustment_min_y_mm >= self.lateral_adjustment_max_y_mm:
            raise ValueError("lateral adjustment range must be increasing")
        if self.required_fore_aft_travel_mm > self.preferred_fore_aft_travel_mm:
            raise ValueError("preferred fore/aft travel must meet required travel")
        if not math.isfinite(self.carrier_length_mm):
            raise ValueError("carrier length must be finite")
        return self


class YagiCarrierSynthesisResult(Model):
    status: YagiCarrierStatus
    authority_hash: str
    synthesis_version: str = YAGI_CARRIER_LAYOUT_SYNTHESIS_VERSION
    design_variables: dict[str, float] = {}
    minimum_required_carrier_length_mm: float | None = None
    maximum_antenna_element_span_mm: float | None = None
    nominal_layout_status: NominalLayoutStatus | None = None
    nominal_colliding_pairs: tuple[tuple[str, str], ...] = ()
    lateral_adjustment_available: bool = False
    two_antenna_lateral_resolution_possible: bool = False
    three_antenna_lateral_resolution_possible: bool = False
    required_three_antenna_lateral_span_mm: float | None = None
    collision_resolution_strategies_available: tuple[str, ...] = ()
    collision_resolution_strategies_selected: tuple[str, ...] = ()
    structural_verification: Literal["not_verified"] = "not_verified"
    spec: YagiCarrierDesignSpec | None = None
    domain_spec_hash: str | None = None
    synthesis_hash: str
    missing_authority: str | None = None
    infeasibility: str | None = None
    proposal: object | None = None


def _hash_payload(value) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()}"


def carrier_authority_hash(requirements) -> str:
    return _hash_payload(requirements.model_dump(mode="json"))


def carrier_spec_hash(spec: YagiCarrierDesignSpec) -> str:
    return _hash_payload(spec.model_dump(mode="json"))


def envelope_pair_interference(first_center, first_size, second_center, second_size) -> bool:
    for axis in range(3):
        separation = abs(first_center[axis] - second_center[axis])
        if separation >= (first_size[axis] + second_size[axis]) / 2:
            return False
    return True


def _representative_envelopes(requirements):
    wanted = ("ANTENNA_ENVELOPE_0400", "ANTENNA_ENVELOPE_0600", "ANTENNA_ENVELOPE_1200")
    by_id = {envelope.semantic_id: envelope for envelope in requirements.envelopes}
    return tuple(by_id[identity] for identity in wanted if identity in by_id)


def synthesize_yagi_carrier_layout(requirements, *, carrier_id: str = YAGI_CARRIER_PART_ID) -> YagiCarrierSynthesisResult:
    authority_hash = carrier_authority_hash(requirements)
    lateral = requirements.recommended_lateral_adjustment_mm
    minimum_required_length = 2 * lateral
    carrier_length = max(minimum_required_length, requirements.preferred_carrier_length_mm)
    spec = YagiCarrierDesignSpec(
        carrier_id=carrier_id,
        carrier_length_mm=carrier_length,
        lateral_adjustment_min_y_mm=-lateral,
        lateral_adjustment_max_y_mm=lateral,
        nominal_two_antenna_y_mm=(-requirements.nominal_spacing_mm / 2, requirements.nominal_spacing_mm / 2),
        nominal_three_antenna_y_mm=(-requirements.nominal_spacing_mm, 0.0, requirements.nominal_spacing_mm),
        required_fore_aft_travel_mm=requirements.required_fore_aft_travel_mm,
        preferred_fore_aft_travel_mm=requirements.preferred_fore_aft_travel_mm,
        provenance=requirements.provenance,
    )
    representative = _representative_envelopes(requirements)
    placements = tuple(zip(spec.nominal_three_antenna_y_mm, representative))
    colliding = []
    for index, (first_y, first) in enumerate(placements):
        for second_y, second in placements[index + 1:]:
            if envelope_pair_interference(
                (0.0, first_y, 0.0),
                (first.length_mm, first.span_mm, first.depth_mm),
                (0.0, second_y, 0.0),
                (second.length_mm, second.span_mm, second.depth_mm),
            ):
                colliding.append(tuple(sorted((first.semantic_id, second.semantic_id))))
    spans = [envelope.span_mm for envelope in representative]
    required_three_span = sum(spans) - (spans[0] + spans[-1]) / 2 if len(spans) == 3 else 0.0
    two_antenna_pair = representative[:2]
    required_two_span = (two_antenna_pair[0].span_mm + two_antenna_pair[1].span_mm) / 2 if len(two_antenna_pair) == 2 else 0.0
    design_variables = {
        "carrier_length_mm": spec.carrier_length_mm,
        "lateral_adjustment_min_y_mm": spec.lateral_adjustment_min_y_mm,
        "lateral_adjustment_max_y_mm": spec.lateral_adjustment_max_y_mm,
    }
    result = YagiCarrierSynthesisResult(
        status=YagiCarrierStatus.SUCCESS,
        authority_hash=authority_hash,
        design_variables=design_variables,
        minimum_required_carrier_length_mm=minimum_required_length,
        maximum_antenna_element_span_mm=max(envelope.span_mm for envelope in requirements.envelopes),
        nominal_layout_status=NominalLayoutStatus.COLLIDES if colliding else NominalLayoutStatus.CLEAR,
        nominal_colliding_pairs=tuple(sorted(set(colliding))),
        lateral_adjustment_available=True,
        two_antenna_lateral_resolution_possible=required_two_span <= 2 * lateral,
        three_antenna_lateral_resolution_possible=required_three_span <= 2 * lateral,
        required_three_antenna_lateral_span_mm=required_three_span,
        collision_resolution_strategies_available=tuple(requirements.collision_resolution_strategies),
        spec=spec,
        domain_spec_hash=carrier_spec_hash(spec),
        synthesis_hash="pending",
    )
    return result.model_copy(update={"synthesis_hash": _synthesis_hash(result)})


def _synthesis_hash(result: YagiCarrierSynthesisResult) -> str:
    return _hash_payload(
        {
            "authority_hash": result.authority_hash,
            "synthesis_version": result.synthesis_version,
            "design_variables": result.design_variables,
            "domain_spec_hash": result.domain_spec_hash,
        }
    )


def _not_ready(missing: str) -> YagiCarrierSynthesisResult:
    payload = {"status": YagiCarrierStatus.NOT_READY.value, "missing_authority": missing, "synthesis_version": YAGI_CARRIER_LAYOUT_SYNTHESIS_VERSION}
    return YagiCarrierSynthesisResult(status=YagiCarrierStatus.NOT_READY, authority_hash="unbound", missing_authority=missing, synthesis_hash=_hash_payload(payload))


class CarrierCadCapabilityAudit(Model):
    supported: bool
    available_operations: tuple[str, ...]
    required_operations: tuple[str, ...]
    missing_capability: str | None = None
    pocket_substitution_allowed: Literal[False] = False
    rationale: str = Field(min_length=1)
    marker: str | None = None


def carrier_cad_capability_audit() -> CarrierCadCapabilityAudit:
    from mechcad_harness.cad_program import BasePlateOperation, RectangularPocketOperation, ThroughHoleOperation

    available = tuple(sorted(operation.model_fields["operation_type"].default for operation in (BasePlateOperation, ThroughHoleOperation, RectangularPocketOperation)))
    required = ("base_plate", "through_slot")
    missing = tuple(name for name in required if name not in available)
    return CarrierCadCapabilityAudit(
        supported=not missing,
        available_operations=available,
        required_operations=required,
        missing_capability=missing[0] if missing else None,
        rationale=(
            "The carrier's adjustable mounting is a continuous lateral travel region, which requires a "
            "through_slot (elongated full-depth opening). RectangularPocketOperation is validated as blind "
            "(depth strictly less than thickness), so substituting it would change the physical meaning of the "
            "clamp travel region from an open slot to a closed recess."
        ),
        marker="M7B2B_CAD_OPERATION_CAPABILITY_REQUIRED" if missing else None,
    )


def compile_preliminary_yagi_carrier(spec: YagiCarrierDesignSpec):
    audit = carrier_cad_capability_audit()
    if not audit.supported:
        raise ValueError(f"{audit.marker}: missing {audit.missing_capability} operation; {audit.rationale}")
    raise ValueError("M7B2B_CAD_OPERATION_CAPABILITY_REQUIRED: carrier CAD compilation is not accepted yet")


def build_yagi_carrier_proposal(result: YagiCarrierSynthesisResult, *, project_id: str, source_revision: int, source_state_hash: str, sliding_interface=None):
    from uuid import NAMESPACE_URL, uuid5

    from mechcad_harness.changes import ChangeOperation, OperationType
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    if result.status is not YagiCarrierStatus.SUCCESS or result.spec is None:
        raise ValueError("only successful carrier synthesis can produce a proposal")
    spec = result.spec.model_copy(update={"sliding_interface": YagiCarrierSlidingInterfaceSection.from_selection(sliding_interface)}) if sliding_interface is not None else result.spec
    operation = ChangeOperation(operation=OperationType.ADD, path=f"/yagi_carriers/{spec.carrier_id}", value=spec.model_dump(mode="json"))
    identity = _hash_payload(
        {
            "project_id": project_id,
            "source_revision": source_revision,
            "source_state_hash": source_state_hash,
            "authority_hash": result.authority_hash,
            "synthesis_version": result.synthesis_version,
            "synthesis_hash": result.synthesis_hash,
            "domain_spec_hash": result.domain_spec_hash,
        }
    )
    return ChangeProposal(
        id=f"CP-{uuid5(NAMESPACE_URL, identity)}",
        title="Synthesize preliminary Yagi carrier layout",
        status=ProposalStatus.DRAFT,
        base_revision=source_revision,
        base_state_hash=source_state_hash,
        actor=YAGI_CARRIER_OWNER,
        operations=[operation],
    )


class YagiCarrierSynthesisService:
    def synthesize(self, state, *, source_revision: int, source_state_hash: str, project_id: str = "unbound") -> YagiCarrierSynthesisResult:
        from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer
        from mechcad_harness.engineering.keys import SupportedConstraintKey

        key = SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS
        if state.revision != source_revision or not source_state_hash:
            return _not_ready("invalid source state binding")
        try:
            satisfied = ConstraintRequestMaterializer().is_satisfied(key, state, engineering_scope_id="yagi-carrier")
        except ValueError as exc:
            return _not_ready(str(exc))
        if not satisfied:
            return _not_ready(key.value)
        requirements = next(parameter.value for parameter in state.authoritative_parameters if parameter.key is key)
        result = synthesize_yagi_carrier_layout(requirements)
        if result.status is not YagiCarrierStatus.SUCCESS:
            return result
        proposal = build_yagi_carrier_proposal(result, project_id=project_id, source_revision=source_revision, source_state_hash=source_state_hash)
        return result.model_copy(update={"proposal": proposal})
