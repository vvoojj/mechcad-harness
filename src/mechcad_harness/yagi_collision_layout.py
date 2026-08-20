from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from mechcad_harness.models.common import Model
from mechcad_harness.yagi_carrier import YagiCarrierDesignSpec, carrier_authority_hash, carrier_spec_hash


YAGI_COLLISION_LAYOUT_SYNTHESIS_VERSION = "yagi-collision-layout-synthesis@1.0"


class YagiCollisionLayoutStatus(StrEnum):
    NOT_READY = "not_ready"
    INFEASIBLE = "infeasible"
    SUCCESS = "success"


class CollisionLayoutClassification(StrEnum):
    INTERFERENCE = "interference"
    NO_INTERFERENCE_TOUCHING = "no_interference_touching"
    POSITIVE_CLEARANCE = "positive_clearance"


class YagiEnvelopePlacement(Model):
    envelope_id: str = Field(min_length=1)
    lane: Literal["left", "center", "right", "lateral_negative", "lateral_positive"]
    center_y_mm: float
    relative_z_offset_mm: float
    reference_fixture_x_center_mm: None = None


class YagiCollisionPairResult(Model):
    first_envelope_id: str = Field(min_length=1)
    second_envelope_id: str = Field(min_length=1)
    common_volume_mm3: float = Field(ge=0)
    exact_distance_mm: float = Field(ge=0)
    classification: CollisionLayoutClassification


class YagiCollisionLayoutSpec(Model):
    layout_id: str = Field(min_length=1)
    selected_envelope_ids: tuple[str, ...]
    placements: tuple[YagiEnvelopePlacement, ...]
    strategies: tuple[Literal["nominal", "lateral_adjustment", "vertical_stagger"], ...]
    classification: CollisionLayoutClassification
    minimum_pair_clearance_mm: float = Field(ge=0)
    touching_pairs: tuple[tuple[str, str], ...] = ()
    pair_results: tuple[YagiCollisionPairResult, ...]
    final_antenna_x_positions_selected: Literal[False] = False
    com_verification: Literal["not_ready"] = "not_ready"
    structural_verification: Literal["not_verified"] = "not_verified"
    manufacturing_clearance_status: Literal["not_specified"] = "not_specified"
    vertical_stagger_mechanical_embodiment: Literal["not_designed", "not_required"]
    authority_hash: str = Field(min_length=1)
    carrier_design_hash: str = Field(min_length=1)
    synthesis_version: str = YAGI_COLLISION_LAYOUT_SYNTHESIS_VERSION
    synthesis_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_layout(self):
        if len(self.selected_envelope_ids) not in (2, 3):
            raise ValueError("selected envelopes must contain 2 or 3 identities")
        if len(set(self.selected_envelope_ids)) != len(self.selected_envelope_ids):
            raise ValueError("selected envelope identities must be unique")
        if {placement.envelope_id for placement in self.placements} != set(self.selected_envelope_ids):
            raise ValueError("placements must exactly cover selected envelopes")
        if len({placement.envelope_id for placement in self.placements}) != len(self.placements):
            raise ValueError("placement identities must be unique")
        return self


class YagiCollisionLayoutSynthesisResult(Model):
    status: YagiCollisionLayoutStatus
    authority_hash: str
    carrier_design_hash: str
    source_revision: int | None = None
    source_state_hash: str | None = None
    synthesis_version: str = YAGI_COLLISION_LAYOUT_SYNTHESIS_VERSION
    spec: YagiCollisionLayoutSpec | None = None
    synthesis_hash: str
    infeasibility: str | None = None
    proposal: object | None = None


def _hash_payload(payload) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()}"


def _pair_result(first, second, first_placement, second_placement) -> YagiCollisionPairResult:
    dimensions_a = (first.length_mm, first.span_mm, first.depth_mm)
    dimensions_b = (second.length_mm, second.span_mm, second.depth_mm)
    centers_a = (0.0, first_placement.center_y_mm, first_placement.relative_z_offset_mm)
    centers_b = (0.0, second_placement.center_y_mm, second_placement.relative_z_offset_mm)
    overlaps = []
    gaps = []
    for center_a, center_b, dimension_a, dimension_b in zip(centers_a, centers_b, dimensions_a, dimensions_b, strict=True):
        separation = abs(center_a - center_b)
        half_sum = (dimension_a + dimension_b) / 2
        overlaps.append(max(0.0, half_sum - separation))
        gaps.append(max(0.0, separation - half_sum))
    common_volume = overlaps[0] * overlaps[1] * overlaps[2]
    distance = (sum(gap * gap for gap in gaps)) ** 0.5
    classification = CollisionLayoutClassification.INTERFERENCE if common_volume > 0 else (CollisionLayoutClassification.POSITIVE_CLEARANCE if distance > 0 else CollisionLayoutClassification.NO_INTERFERENCE_TOUCHING)
    return YagiCollisionPairResult(
        first_envelope_id=min(first.semantic_id, second.semantic_id),
        second_envelope_id=max(first.semantic_id, second.semantic_id),
        common_volume_mm3=common_volume,
        exact_distance_mm=distance,
        classification=classification,
    )


def _pair_results(envelopes, placements):
    by_id = {placement.envelope_id: placement for placement in placements}
    results = []
    for index, first in enumerate(envelopes):
        for second in envelopes[index + 1:]:
            results.append(_pair_result(first, second, by_id[first.semantic_id], by_id[second.semantic_id]))
    return tuple(sorted(results, key=lambda result: (result.first_envelope_id, result.second_envelope_id)))


def _classification(pair_results):
    if any(result.classification is CollisionLayoutClassification.INTERFERENCE for result in pair_results):
        return CollisionLayoutClassification.INTERFERENCE
    if any(result.classification is CollisionLayoutClassification.NO_INTERFERENCE_TOUCHING for result in pair_results):
        return CollisionLayoutClassification.NO_INTERFERENCE_TOUCHING
    return CollisionLayoutClassification.POSITIVE_CLEARANCE


def _synthesis_hash(*, authority_hash, carrier_design_hash, source_revision, source_state_hash, selected_envelope_ids, placements, strategies, classification):
    return _hash_payload(
        {
            "authority_hash": authority_hash,
            "carrier_design_hash": carrier_design_hash,
            "source_revision": source_revision,
            "source_state_hash": source_state_hash,
            "selected_envelope_ids": selected_envelope_ids,
            "placements": [placement.model_dump(mode="json") for placement in placements],
            "strategies": strategies,
            "classification": classification.value,
            "synthesis_version": YAGI_COLLISION_LAYOUT_SYNTHESIS_VERSION,
        }
    )


def synthesize_yagi_collision_layout(requirements, carrier: YagiCarrierDesignSpec, selected_envelope_ids, *, source_revision: int | None = None, source_state_hash: str | None = None, layout_id: str = "preliminary_yagi_collision_layout") -> YagiCollisionLayoutSynthesisResult:
    selected_ids = tuple(selected_envelope_ids)
    if len(selected_ids) not in (2, 3):
        raise ValueError("select exactly 2 or 3 envelope IDs")
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("duplicate envelope IDs are not allowed")
    by_id = {envelope.semantic_id: envelope for envelope in requirements.envelopes}
    unknown = tuple(identity for identity in selected_ids if identity not in by_id)
    if unknown:
        raise ValueError(f"unknown envelope IDs: {unknown}")
    envelopes = tuple(by_id[identity] for identity in selected_ids)
    authority_hash = carrier_authority_hash(requirements)
    design_hash = carrier_spec_hash(carrier)
    if len(envelopes) == 2:
        required_separation = (envelopes[0].span_mm + envelopes[1].span_mm) / 2
        target_separation = max(requirements.nominal_spacing_mm, required_separation)
        placements = tuple(
            YagiEnvelopePlacement(envelope_id=envelope.semantic_id, lane=lane, center_y_mm=center_y, relative_z_offset_mm=0.0)
            for envelope, lane, center_y in zip(envelopes, ("lateral_negative", "lateral_positive"), (-target_separation / 2, target_separation / 2), strict=True)
        )
        strategies = ("lateral_adjustment",)
    else:
        ordered = tuple(sorted(envelopes, key=lambda envelope: (-envelope.span_mm, envelope.semantic_id)))
        placements = tuple(
            YagiEnvelopePlacement(envelope_id=envelope.semantic_id, lane=lane, center_y_mm=center_y, relative_z_offset_mm=0.0)
            for envelope, lane, center_y in zip(ordered, ("left", "center", "right"), carrier.nominal_three_antenna_y_mm, strict=True)
        )
        initial_pairs = _pair_results(ordered, placements)
        center = ordered[1]
        colliding_neighbors = [
            next(envelope for envelope in ordered if envelope.semantic_id == (pair.second_envelope_id if pair.first_envelope_id == center.semantic_id else pair.first_envelope_id))
            for pair in initial_pairs
            if pair.classification is CollisionLayoutClassification.INTERFERENCE and center.semantic_id in (pair.first_envelope_id, pair.second_envelope_id)
        ]
        strategies = ("nominal",)
        if colliding_neighbors:
            required_z = max((center.depth_mm + neighbor.depth_mm) / 2 for neighbor in colliding_neighbors)
            placements = tuple(placement.model_copy(update={"relative_z_offset_mm": required_z}) if placement.envelope_id == center.semantic_id else placement for placement in placements)
            strategies += ("vertical_stagger",)
    if any(placement.center_y_mm < carrier.lateral_adjustment_min_y_mm or placement.center_y_mm > carrier.lateral_adjustment_max_y_mm for placement in placements):
        return YagiCollisionLayoutSynthesisResult(
            status=YagiCollisionLayoutStatus.INFEASIBLE,
            authority_hash=authority_hash,
            carrier_design_hash=design_hash,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            synthesis_hash=_hash_payload({"status": "infeasible", "selected": selected_ids, "synthesis_version": YAGI_COLLISION_LAYOUT_SYNTHESIS_VERSION}),
            infeasibility="authoritative lateral center range exceeded",
        )
    pairs = _pair_results(envelopes, placements)
    classification = _classification(pairs)
    synthesis_hash = _synthesis_hash(
        authority_hash=authority_hash,
        carrier_design_hash=design_hash,
        source_revision=source_revision,
        source_state_hash=source_state_hash,
        selected_envelope_ids=selected_ids,
        placements=placements,
        strategies=strategies,
        classification=classification,
    )
    spec = YagiCollisionLayoutSpec(
        layout_id=layout_id,
        selected_envelope_ids=selected_ids,
        placements=placements,
        strategies=strategies,
        classification=classification,
        minimum_pair_clearance_mm=min(pair.exact_distance_mm for pair in pairs),
        touching_pairs=tuple((pair.first_envelope_id, pair.second_envelope_id) for pair in pairs if pair.classification is CollisionLayoutClassification.NO_INTERFERENCE_TOUCHING),
        pair_results=pairs,
        vertical_stagger_mechanical_embodiment="not_designed" if any(placement.relative_z_offset_mm for placement in placements) else "not_required",
        authority_hash=authority_hash,
        carrier_design_hash=design_hash,
        synthesis_hash=synthesis_hash,
    )
    return YagiCollisionLayoutSynthesisResult(
        status=YagiCollisionLayoutStatus.SUCCESS if classification is not CollisionLayoutClassification.INTERFERENCE else YagiCollisionLayoutStatus.INFEASIBLE,
        authority_hash=authority_hash,
        carrier_design_hash=design_hash,
        source_revision=source_revision,
        source_state_hash=source_state_hash,
        spec=spec,
        synthesis_hash=synthesis_hash,
        infeasibility="allowed Y + Z strategies cannot resolve this combination" if classification is CollisionLayoutClassification.INTERFERENCE else None,
    )


def build_yagi_collision_layout_proposal(result: YagiCollisionLayoutSynthesisResult, *, project_id: str, source_revision: int, source_state_hash: str):
    from uuid import NAMESPACE_URL, uuid5

    from mechcad_harness.changes import ChangeOperation, OperationType
    from mechcad_harness.models import ChangeProposal, ProposalStatus

    if result.status is not YagiCollisionLayoutStatus.SUCCESS or result.spec is None:
        raise ValueError("only successful collision layout synthesis can produce a proposal")
    if result.source_revision != source_revision or result.source_state_hash != source_state_hash:
        raise ValueError("collision layout synthesis is not bound to the requested source state")
    identity = _hash_payload(
        {
            "project_id": project_id,
            "source_revision": source_revision,
            "source_state_hash": source_state_hash,
            "authority_hash": result.authority_hash,
            "carrier_design_hash": result.carrier_design_hash,
            "synthesis_version": result.synthesis_version,
            "synthesis_hash": result.synthesis_hash,
        }
    )
    return ChangeProposal(
        id=f"CP-{uuid5(NAMESPACE_URL, identity)}",
        title="Synthesize preliminary Yagi collision layout",
        status=ProposalStatus.DRAFT,
        base_revision=source_revision,
        base_state_hash=source_state_hash,
        actor="mechcad-yagi-carrier",
        operations=[ChangeOperation(operation=OperationType.ADD, path=f"/yagi_collision_layouts/{result.spec.layout_id}", value=result.spec.model_dump(mode="json"))],
    )


class YagiCollisionLayoutSynthesisService:
    def synthesize(self, state, *, source_revision: int, source_state_hash: str, project_id: str, selected_envelope_ids):
        from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer
        from mechcad_harness.engineering.keys import SupportedConstraintKey
        from mechcad_harness.yagi_carrier import YagiCarrierDesignSpec

        key = SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS
        if state.revision != source_revision or not source_state_hash:
            return YagiCollisionLayoutSynthesisResult(
                status=YagiCollisionLayoutStatus.NOT_READY,
                authority_hash="unbound",
                carrier_design_hash="unbound",
                source_revision=source_revision,
                source_state_hash=source_state_hash,
                synthesis_hash=_hash_payload({"status": "not_ready", "reason": "invalid source state binding"}),
                infeasibility="invalid source state binding",
            )
        if not ConstraintRequestMaterializer().is_satisfied(key, state, engineering_scope_id="yagi-carrier"):
            return YagiCollisionLayoutSynthesisResult(
                status=YagiCollisionLayoutStatus.NOT_READY,
                authority_hash="unbound",
                carrier_design_hash="unbound",
                source_revision=source_revision,
                source_state_hash=source_state_hash,
                synthesis_hash=_hash_payload({"status": "not_ready", "reason": key.value}),
                infeasibility=key.value,
            )
        if len(state.yagi_carriers) != 1:
            return YagiCollisionLayoutSynthesisResult(
                status=YagiCollisionLayoutStatus.NOT_READY,
                authority_hash="unbound",
                carrier_design_hash="unbound",
                source_revision=source_revision,
                source_state_hash=source_state_hash,
                synthesis_hash=_hash_payload({"status": "not_ready", "reason": "canonical carrier design required"}),
                infeasibility="canonical carrier design required",
            )
        requirements = next(parameter.value for parameter in state.authoritative_parameters if parameter.key is key)
        carrier = YagiCarrierDesignSpec.model_validate(state.yagi_carriers[0])
        result = synthesize_yagi_collision_layout(requirements, carrier, selected_envelope_ids, source_revision=source_revision, source_state_hash=source_state_hash)
        if result.status is not YagiCollisionLayoutStatus.SUCCESS:
            return result
        proposal = build_yagi_collision_layout_proposal(result, project_id=project_id, source_revision=source_revision, source_state_hash=source_state_hash)
        return result.model_copy(update={"proposal": proposal})
