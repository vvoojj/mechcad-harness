from __future__ import annotations

import hashlib
import itertools
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Literal, TypeAlias

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, CadRigidTransform, assembly_hash
from mechcad_harness.candidates.cad_realization import (
    CandidateCadInstanceMapping,
    CandidateCadRealization,
)
from mechcad_harness.candidates.canonical_cad import (
    CanonicalCadRealization,
    CanonicalPhysicalCadMapping,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
)
from mechcad_harness.candidates.generated_authority import (
    _fact_value,
    build_candidate_view,
    build_canonical_view,
    candidate_placement_design_variables,
    m13_local_pose,
)
from mechcad_harness.candidates.models import (
    ComponentSpecificationSnapshot,
    GeneratedReferenceFrameAxisSource,
    GeneratedRotationalInterfaceAxisSource,
    MechanicalConnection,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalMechanismRealization,
    PhysicalRevoluteJointBinding,
    PhysicalRigidBodyBinding,
    SuppliedReferenceFrameAxisSource,
    SuppliedRotationalInterfaceAxisSource,
    physical_kinematic_root_hash,
)
from mechcad_harness.models.physical_mechanism import (
    CanonicalPhysicalPairClassificationBinding,
    CanonicalPhysicalRigidBodyBinding,
    CanonicalPhysicalComponent,
    CanonicalPhysicalMechanism,
    CanonicalPhysicalRevoluteJointBinding,
    CanonicalMechanicalConnection,
    CanonicalMechanicalConnectionKind,
    CanonicalConnectionMeaning,
    CanonicalPlacementOrigin,
    CanonicalSuppliedRotationalInterfaceAxisSource,
    CanonicalSuppliedReferenceFrameAxisSource,
    CanonicalGeneratedRotationalInterfaceAxisSource,
    CanonicalGeneratedReferenceFrameAxisSource,
)
from mechcad_harness.models.generated_placement import (
    CanonicalGeneratedPlacementDerivation,
    GeneratedPlacementDerivation,
    _resolve_rotation_input,
    compose_poses,
    place_generated_target,
    pose_from_interface,
    placement_derivations_hash,
    resolve_placement_inputs,
)
from mechcad_harness.models.supplied_component_interface import (
    RotationalShaftInterface,
    SuppliedComponentReferenceFrame,
)
from mechcad_harness.models.generated_part import GeneratedRotationalInterface
from mechcad_harness.models.generated_part import GeneratedReferenceFrame
from mechcad_harness.models.physical_pair_policy import (
    PhysicalPairClassification,
    PhysicalPairClassificationBinding,
    physical_pair_classification_set_hash,
)
from mechcad_harness.models.quaternion import normalize_direction, rotate_vector
from mechcad_harness.models.common import Model
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicJointKind,
    KinematicModelV2,
    KinematicRigidBody,
    KinematicRigidBodyMember,
    MultiJointKinematicsService,
    RevoluteJointModelV2,
    RIGID_TRANSFORM_AGREEMENT_VERSION,
    kinematic_model_hash,
    revalidate_v2_kinematic_model,
    rigid_transform_agrees,
    transform_apply,
    transform_compose,
    transform_inverse,
    validate_v2_body_assembly_agreement,
)
from mechcad_harness.multi_joint_pair_scope import (
    ExactConstituentPair,
    canonical_exact_pair_scope,
    exact_pair_scope_hash,
)
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
    MultiJointCollisionSweepRequestV2,
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)


_CadMapping: TypeAlias = CandidateCadInstanceMapping | CanonicalPhysicalCadMapping
_BodyBinding: TypeAlias = PhysicalRigidBodyBinding | CanonicalPhysicalRigidBodyBinding
_PairBinding: TypeAlias = (
    PhysicalPairClassificationBinding | CanonicalPhysicalPairClassificationBinding
)
_JointBinding: TypeAlias = (
    PhysicalRevoluteJointBinding | CanonicalPhysicalRevoluteJointBinding
)
_Connection: TypeAlias = MechanicalConnection | CanonicalMechanicalConnection
_AxisSource: TypeAlias = (
    SuppliedRotationalInterfaceAxisSource
    | SuppliedReferenceFrameAxisSource
    | GeneratedRotationalInterfaceAxisSource
    | GeneratedReferenceFrameAxisSource
    | CanonicalSuppliedRotationalInterfaceAxisSource
    | CanonicalSuppliedReferenceFrameAxisSource
    | CanonicalGeneratedRotationalInterfaceAxisSource
    | CanonicalGeneratedReferenceFrameAxisSource
)
_SemanticAxisPose: TypeAlias = tuple[
    tuple[float, float, float], tuple[float, float, float]
]


class CandidateCanonicalMultiJointEquivalence(Model):
    """Semantic agreement result for candidate and fresh canonical bridges."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_bridge_hash: str
    canonical_bridge_hash: str
    equivalent: bool
    differences: tuple[str, ...] = ()


def compare_candidate_canonical_multi_joint_semantics(
    candidate_bridge: "PhysicalToM10V2Bridge",
    canonical_bridge: "PhysicalToM10V2Bridge",
    *,
    candidate_cad: CandidateCadRealization | None = None,
    canonical_cad: CanonicalCadRealization | None = None,
    instance_mapping: Mapping[str, str] | None = None,
    candidate_pair_bindings: Sequence[_PairBinding] | None = None,
    canonical_pair_bindings: Sequence[_PairBinding] | None = None,
    candidate_configurations: Sequence[JointConfiguration] | None = None,
    canonical_configurations: Sequence[JointConfiguration] | None = None,
    candidate_volume_tolerance_mm3: float | None = None,
    canonical_volume_tolerance_mm3: float | None = None,
    candidate_distance_tolerance_mm: float | None = None,
    canonical_distance_tolerance_mm: float | None = None,
    candidate_placement_derivations: Sequence[GeneratedPlacementDerivation] | None = None,
    canonical_placement_derivations: Sequence[CanonicalGeneratedPlacementDerivation] | None = None,
) -> CandidateCanonicalMultiJointEquivalence:
    """Compare bridge semantics while allowing fresh CAD identities to differ."""
    if type(candidate_bridge) is not PhysicalToM10V2Bridge:
        raise TypeError("candidate bridge must be a PhysicalToM10V2Bridge")
    if type(canonical_bridge) is not PhysicalToM10V2Bridge:
        raise TypeError("canonical bridge must be a PhysicalToM10V2Bridge")
    differences: list[str] = []
    if candidate_bridge.model.model_id != canonical_bridge.model.model_id:
        differences.append("semantic_model_id")
    if (
        candidate_bridge.model.evaluator_version != canonical_bridge.model.evaluator_version
        or candidate_bridge.model.transform_agreement_version
        != canonical_bridge.model.transform_agreement_version
    ):
        differences.append("model_versions")
    if candidate_bridge.ordered_body_ids != canonical_bridge.ordered_body_ids:
        differences.append("body_ids")
    if candidate_bridge.ordered_joint_ids != canonical_bridge.ordered_joint_ids:
        differences.append("joint_ids")

    def candidate_to_canonical(instance_id: str) -> str:
        if instance_mapping is not None:
            return instance_mapping.get(instance_id, instance_id)
        return instance_id

    if candidate_pair_bindings is not None and canonical_pair_bindings is not None:
        candidate_pairs = tuple(
            sorted(
                (
                    tuple(
                        sorted(
                            (
                                candidate_to_canonical(item.first_physical_instance_id),
                                candidate_to_canonical(item.second_physical_instance_id),
                            )
                        )
                    ),
                    item.classification.value,
                    item.exclusion_reason,
                )
                for item in candidate_pair_bindings
            )
        )
        canonical_pairs = tuple(
            sorted(
                (
                    tuple(
                        sorted(
                            (
                                item.first_physical_instance_id,
                                item.second_physical_instance_id,
                            )
                        )
                    ),
                    item.classification.value,
                    item.exclusion_reason,
                )
                for item in canonical_pair_bindings
            )
        )
        if candidate_pairs != canonical_pairs:
            differences.append("pair_policy")
    elif candidate_cad is None or canonical_cad is None:
        if candidate_bridge.physical_pair_classification_set_hash != canonical_bridge.physical_pair_classification_set_hash:
            differences.append("pair_policy")
    def physical_by_cad(cad):
        return {
            item.cad_instance_id: item.physical_instance_id
            for item in cad.mappings
        }

    candidate_physical_by_cad = (
        physical_by_cad(candidate_cad) if candidate_cad is not None else {}
    )
    canonical_physical_by_cad = (
        physical_by_cad(canonical_cad) if canonical_cad is not None else {}
    )

    def model_semantics(bridge, cad, physical_by_cad, normalize_instance):
        bodies = tuple(
            (
                body.body_id,
                normalize_instance(
                    physical_by_cad.get(body.reference_member_instance_id,
                                        body.reference_member_instance_id)
                ),
                tuple(
                    sorted(
                        [
                            (
                                normalize_instance(
                                    physical_by_cad.get(
                                        member.member_instance_id,
                                        member.member_instance_id,
                                    )
                                ),
                                member.reference_to_member_home.model_dump(mode="json"),
                            )
                            for member in body.members
                        ],
                        key=lambda value: value[0],
                    )
                ),
            )
            for body in bridge.model.bodies
        )
        joints = tuple(
            (
                joint.joint_id,
                joint.joint_kind.value,
                joint.parent_body_id,
                joint.child_body_id,
                joint.axis_origin,
                joint.axis_direction,
                joint.min_angle_deg,
                joint.max_angle_deg,
            )
            for joint in bridge.model.joints
        )
        return bodies, joints

    if model_semantics(
        candidate_bridge,
        candidate_cad,
        candidate_physical_by_cad,
        candidate_to_canonical,
    ) != model_semantics(
        canonical_bridge,
        canonical_cad,
        canonical_physical_by_cad,
        lambda value: value,
    ):
        differences.append("lowered_model")

    def pair_semantics(bridge, cad, physical_by_cad, normalize_instance):
        return tuple(
            sorted(
                (
                    tuple(
                        sorted(
                            (
                                normalize_instance(
                                    physical_by_cad.get(
                                        entry.first_instance_id,
                                        entry.first_instance_id,
                                    )
                                ),
                                normalize_instance(
                                    physical_by_cad.get(
                                        entry.second_instance_id,
                                        entry.second_instance_id,
                                    )
                                ),
                            )
                        )
                    ),
                    entry.classification.value,
                    entry.exclusion_reason,
                )
                for entry in bridge.inventory.entries
            )
        )

    if candidate_cad is not None and canonical_cad is not None:
        if pair_semantics(
            candidate_bridge,
            candidate_cad,
            candidate_physical_by_cad,
            candidate_to_canonical,
        ) != pair_semantics(
            canonical_bridge,
            canonical_cad,
            canonical_physical_by_cad,
            lambda value: value,
        ):
            differences.append("inventory")

    if (candidate_configurations is None) != (canonical_configurations is None):
        differences.append("configurations")
    elif candidate_configurations is not None and canonical_configurations is not None:
        candidate_configuration_semantics = tuple(
            (item.model_id, tuple(sorted(item.positions.items())))
            for item in candidate_configurations
        )
        canonical_configuration_semantics = tuple(
            (item.model_id, tuple(sorted(item.positions.items())))
            for item in canonical_configurations
        )
        if candidate_configuration_semantics != canonical_configuration_semantics:
            differences.append("configurations")

    for name, candidate_value, canonical_value in (
        ("volume_tolerance", candidate_volume_tolerance_mm3, canonical_volume_tolerance_mm3),
        ("distance_tolerance", candidate_distance_tolerance_mm, canonical_distance_tolerance_mm),
    ):
        if (candidate_value is None) != (canonical_value is None):
            differences.append(name)
        elif candidate_value is not None and candidate_value != canonical_value:
            differences.append(name)

    def placement_semantics(derivations, canonical):
        values = []
        for derivation in derivations:
            if canonical:
                values.append(
                    (
                        derivation.derivation_id,
                        derivation.rule_id,
                        derivation.source_canonical_instance_id,
                        derivation.source_interface_id,
                        derivation.source_interface_hash,
                        derivation.source_frame_id,
                        derivation.source_frame_hash,
                        derivation.source_placement_ref.model_dump(mode="json"),
                        derivation.target_canonical_instance_id,
                        derivation.target_generated_interface_id,
                        derivation.target_generated_interface_hash,
                        derivation.target_generated_frame_id,
                        derivation.target_generated_frame_hash,
                        tuple(item.model_dump(mode="json") for item in derivation.inputs),
                        None if derivation.rotation is None else derivation.rotation.model_dump(mode="json"),
                    )
                )
            else:
                values.append(
                    (
                        derivation.derivation_id,
                        derivation.rule_id,
                        candidate_to_canonical(derivation.source_physical_instance_id),
                        derivation.source_interface_ref.interface_id,
                        derivation.source_interface_ref.interface_hash,
                        None if derivation.source_frame_ref is None else derivation.source_frame_ref.frame_id,
                        None if derivation.source_frame_ref is None else derivation.source_frame_ref.frame_hash,
                        derivation.source_placement_ref.model_dump(mode="json"),
                        candidate_to_canonical(derivation.target_physical_instance_id),
                        None if derivation.target_generated_interface_ref is None else derivation.target_generated_interface_ref.interface_id,
                        None if derivation.target_generated_interface_ref is None else derivation.target_generated_interface_ref.interface_hash,
                        None if derivation.target_generated_frame_ref is None else derivation.target_generated_frame_ref.frame_id,
                        None if derivation.target_generated_frame_ref is None else derivation.target_generated_frame_ref.frame_hash,
                        tuple(item.model_dump(mode="json") for item in derivation.inputs),
                        None if derivation.rotation is None else derivation.rotation.model_dump(mode="json"),
                    )
                )
        return tuple(values)

    if (candidate_placement_derivations is None) != (
        canonical_placement_derivations is None
    ):
        differences.append("placement_derivations")
    elif candidate_placement_derivations is not None and canonical_placement_derivations is not None:
        if placement_semantics(candidate_placement_derivations, False) != placement_semantics(
            canonical_placement_derivations, True
        ):
            differences.append("placement_derivations")
    if candidate_cad is None or canonical_cad is None:
        if candidate_bridge.exact_pair_scope != canonical_bridge.exact_pair_scope:
            differences.append("exact_pair_scope")
    else:
        candidate_by_physical = {
            item.physical_instance_id: item.cad_instance_id for item in candidate_cad.mappings
        }
        canonical_by_physical = {
            item.physical_instance_id: item.cad_instance_id for item in canonical_cad.mappings
        }
        candidate_physical_by_cad = {value: key for key, value in candidate_by_physical.items()}
        canonical_physical_by_cad = {value: key for key, value in canonical_by_physical.items()}
        candidate_scope = tuple(
            sorted(
                (candidate_physical_by_cad[p.first_instance_id], candidate_physical_by_cad[p.second_instance_id])
                for p in candidate_bridge.exact_pair_scope
            )
        )
        canonical_scope = tuple(
            sorted(
                (canonical_physical_by_cad[p.first_instance_id], canonical_physical_by_cad[p.second_instance_id])
                for p in canonical_bridge.exact_pair_scope
            )
        )
        if instance_mapping is not None:
            candidate_scope = tuple(
                sorted(
                    (instance_mapping[first], instance_mapping[second])
                    for first, second in candidate_scope
                )
            )
        if candidate_scope != canonical_scope:
            differences.append("exact_pair_scope")
    return CandidateCanonicalMultiJointEquivalence(
        candidate_bridge_hash=candidate_bridge.physical_to_m10_bridge_hash,
        canonical_bridge_hash=canonical_bridge.physical_to_m10_bridge_hash,
        equivalent=not differences,
        differences=tuple(differences),
    )


class CanonicalMultiJointM10Verification(Model):
    """Transient fresh canonical M10 request/result pair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request: MultiJointCollisionSweepRequestV2
    result: MultiJointCollisionSweepResultV2


class CanonicalMultiJointM10VerificationService:
    """Execute the sole canonical multi-joint obligation against fresh inputs."""

    def __init__(self, application):
        self.application = application

    def execute(
        self,
        reconstruction: CanonicalMechanismReconstruction,
        cad: CanonicalCadRealization,
    ) -> CanonicalMultiJointM10Verification:
        if type(reconstruction) is not CanonicalMechanismReconstruction:
            raise ValueError("canonical multi-joint verification requires reconstruction")
        if type(cad) is not CanonicalCadRealization:
            raise ValueError("canonical multi-joint verification requires canonical CAD")
        reconstruction = CanonicalMechanismReconstruction.model_validate(
            reconstruction.model_dump(mode="json")
        )
        cad = cad.validated_canonical_copy()
        mechanism = reconstruction.canonical_mechanism
        obligations = mechanism.multi_joint_verification_obligations
        if len(obligations) != 1:
            raise ValueError("canonical multi-joint verification requires exactly one obligation")
        from mechcad_harness.candidates.multi_joint_m10_evaluation import (
            validate_multi_joint_verification_configurations,
        )

        bridge = PhysicalToM10V2BridgeCompiler().compile_canonical(reconstruction, cad)
        obligation = obligations[0]
        configurations = tuple(obligation.configuration_set.configurations)
        emitted_joint_ids = tuple(joint.joint_id for joint in bridge.model.joints)
        if tuple(sorted(emitted_joint_ids)) != tuple(
            sorted(configuration_key for configuration_key in configurations[0].positions)
        ):
            raise ValueError("canonical obligation joint keys do not match fresh bridge model")
        for configuration in configurations:
            validate_multi_joint_verification_configurations(
                (configuration,), bridge
            )
        request = MultiJointCollisionSweepRequestV2(
            schema_version="multi-joint-collision-sweep-request@2",
            source_assembly_id=cad.assembly.assembly_id,
            source_assembly_hash=assembly_hash(cad.assembly),
            model=revalidate_v2_kinematic_model(bridge.model),
            configurations=configurations,
            exact_pair_scope=canonical_exact_pair_scope(bridge.exact_pair_scope),
            volume_tolerance_mm3=obligation.volume_tolerance_mm3,
            distance_tolerance_mm=obligation.distance_tolerance_mm,
            evaluator_version=MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
        )
        executor = getattr(self.application, "_execute_candidate_v2_sweep", None)
        if not callable(executor):
            raise ValueError("application does not expose the trusted v2 tolerance adapter")
        raw_result = executor(
            source_revision=reconstruction.revision,
            source_state_hash=reconstruction.state_hash,
            assembly=cad.assembly,
            model=request.model,
            configurations=request.configurations,
            exact_pair_scope=request.exact_pair_scope,
            volume_tolerance_mm3=request.volume_tolerance_mm3,
            distance_tolerance_mm=request.distance_tolerance_mm,
        )
        result = MultiJointCollisionSweepResultV2.model_validate(
            raw_result.model_dump(mode="json")
        )
        if (
            result.request_hash != request.request_hash
            or result.source_assembly_hash != request.source_assembly_hash
            or result.model_hash != request.model_hash
            or result.evaluator_version != request.evaluator_version
            or result.result_hash != multi_joint_collision_sweep_result_v2_hash(result)
        ):
            raise ValueError("fresh canonical M10 result binding mismatch")
        return CanonicalMultiJointM10Verification(request=request, result=result)


def _require_final_hash(value: str) -> str:
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError("must be a sha256 hash")
    return value


def _require_hash_or_pending(value: str) -> str:
    if value == "pending":
        return value
    return _require_final_hash(value)


def _inventory_hash_payload(inventory: "MultiJointCollisionPairInventory") -> dict[str, object]:
    payload = inventory.model_dump(mode="json")
    payload.pop("inventory_hash", None)
    return payload


def _inventory_hash(inventory: "MultiJointCollisionPairInventory") -> str:
    encoded = json.dumps(
        _inventory_hash_payload(inventory), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class MultiJointCollisionPairEntry(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["multi-joint-collision-pair-entry@1"] = (
        "multi-joint-collision-pair-entry@1"
    )
    first_instance_id: str = Field(min_length=1)
    second_instance_id: str = Field(min_length=1)
    classification: PhysicalPairClassification
    exclusion_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _canonicalize_concrete_pair(cls, data):
        data = dict(data)
        first = data.get("first_instance_id")
        second = data.get("second_instance_id")
        if isinstance(first, str) and isinstance(second, str):
            data["first_instance_id"], data["second_instance_id"] = sorted(
                (first, second)
            )
        return data

    @field_validator("first_instance_id", "second_instance_id")
    @classmethod
    def _require_concrete_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("concrete instance IDs must not be blank")
        return value

    @field_validator("exclusion_reason")
    @classmethod
    def _require_exclusion_reason_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("exclusion reason must not be blank")
        return value

    @model_validator(mode="after")
    def _validate_entry(self) -> "MultiJointCollisionPairEntry":
        if self.first_instance_id >= self.second_instance_id:
            raise ValueError("concrete pair IDs must be strictly ordered")
        if self.classification is PhysicalPairClassification.CHECK_CLEARANCE:
            if self.exclusion_reason is not None:
                raise ValueError("checked concrete pairs cannot carry an exclusion reason")
        elif self.exclusion_reason is None:
            raise ValueError("excluded concrete pairs require an explicit reason")
        return self


class MultiJointCollisionPairInventory(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["multi-joint-collision-pair-inventory@1"] = (
        "multi-joint-collision-pair-inventory@1"
    )
    physical_mechanism_hash: str
    physical_body_binding_hashes: tuple[str, ...] = Field(min_length=1)
    cad_realization_hash: str
    m10_model_hash: str
    complete_concrete_instance_ids: tuple[str, ...] = Field(min_length=1)
    expected_pair_universe: tuple[tuple[str, str], ...] = Field(min_length=1)
    entries: tuple[MultiJointCollisionPairEntry, ...] = Field(min_length=1)
    inventory_hash: str = "pending"

    _validate_hashes = field_validator(
        "physical_mechanism_hash",
        "cad_realization_hash",
        "m10_model_hash",
    )(_require_final_hash)
    _validate_inventory_hash = field_validator("inventory_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def _validate_inventory(self) -> "MultiJointCollisionPairInventory":
        body_hashes = tuple(sorted(self.physical_body_binding_hashes))
        if body_hashes != self.physical_body_binding_hashes:
            object.__setattr__(self, "physical_body_binding_hashes", body_hashes)
        if len(set(body_hashes)) != len(body_hashes):
            raise ValueError("physical body binding hashes must be unique")
        for value in body_hashes:
            _require_final_hash(value)

        concrete_ids = tuple(sorted(self.complete_concrete_instance_ids))
        if any(not value.strip() for value in concrete_ids):
            raise ValueError("complete concrete instance IDs must not be blank")
        if len(set(concrete_ids)) != len(concrete_ids):
            raise ValueError("complete concrete instance IDs must be unique")
        if concrete_ids != self.complete_concrete_instance_ids:
            object.__setattr__(self, "complete_concrete_instance_ids", concrete_ids)

        expected_pairs = tuple(itertools.combinations(concrete_ids, 2))
        normalized_expected = tuple(
            sorted(tuple(sorted(pair)) for pair in self.expected_pair_universe)
        )
        if normalized_expected != expected_pairs:
            raise ValueError("concrete pair universe is incomplete or contains unsupported pairs")
        if normalized_expected != self.expected_pair_universe:
            object.__setattr__(self, "expected_pair_universe", normalized_expected)

        entries = tuple(
            MultiJointCollisionPairEntry.model_validate(entry.model_dump(mode="json"))
            for entry in self.entries
        )
        entries = tuple(
            sorted(entries, key=lambda entry: (entry.first_instance_id, entry.second_instance_id))
        )
        entry_pairs = tuple(
            (entry.first_instance_id, entry.second_instance_id) for entry in entries
        )
        if len(set(entry_pairs)) != len(entry_pairs) or entry_pairs != expected_pairs:
            raise ValueError("concrete pair inventory is incomplete or contains unsupported pairs")
        if entries != self.entries:
            object.__setattr__(self, "entries", entries)

        expected_hash = _inventory_hash(self)
        if self.inventory_hash == "pending":
            if "inventory_hash" in self.model_fields_set:
                raise ValueError("multi-joint collision pair inventory hash must be finalized")
            object.__setattr__(self, "inventory_hash", expected_hash)
        elif self.inventory_hash != expected_hash:
            raise ValueError("multi-joint collision pair inventory hash mismatch")
        return self


def _lookup_one(records, predicate, message):
    matches = tuple(record for record in records if predicate(record))
    if len(matches) != 1:
        raise ValueError(message)
    return matches[0]


def _candidate_context(candidate, instance_id):
    candidate = _validated(candidate, MechanicalDesignCandidate, "candidate")
    component = _lookup_one(
        candidate.realization.components,
        lambda item: item.instance_id == instance_id,
        "candidate source instance cannot be resolved",
    )
    specification = _lookup_one(
        candidate.component_specifications,
        lambda item: item.specification_hash == component.specification_hash,
        "candidate source specification cannot be resolved",
    )
    return candidate, component, _validated(
        specification, ComponentSpecificationSnapshot, "candidate specification"
    )


def _canonical_context(mechanism, instance_id):
    mechanism = _validated(mechanism, CanonicalPhysicalMechanism, "canonical mechanism")
    component = _lookup_one(
        mechanism.components,
        lambda item: item.instance_id == instance_id,
        "canonical source instance cannot be resolved",
    )
    specification = _lookup_one(
        mechanism.component_specifications,
        lambda item: item.specification_hash == component.specification_hash,
        "canonical source specification cannot be resolved",
    )
    return mechanism, component, specification


def _supplied_frame(specification, frame_id, frame_hash=None):
    return _lookup_one(
        specification.supplied_reference_frames,
        lambda frame: frame.frame_id == frame_id
        and (frame_hash is None or frame.frame_hash == frame_hash),
        "supplied reference frame cannot be resolved by exact ID and hash",
    )


def _supplied_interface(specification, interface_id, interface_hash):
    definition = _lookup_one(
        specification.supplied_interface_definitions,
        lambda item: item.interface_id == interface_id
        and item.interface_hash == interface_hash,
        "supplied interface cannot be resolved by exact ID and hash",
    )
    variant = definition.shaft or definition.mounting_face
    if variant is None:
        raise ValueError("supplied interface has no semantic variant")
    frame_id = getattr(variant, "reference_frame_id", None)
    frame = None if frame_id is None else _supplied_frame(specification, frame_id)
    if specification.geometry_source is None:
        raise ValueError("supplied source specification has no geometry authority")
    if definition.geometry_reference_hash != specification.geometry_source.reference_hash:
        raise ValueError("supplied interface geometry authority does not match specification")
    from mechcad_harness.models import supplied_component_interface as m13

    m13.require_authoritatively_consumable_interface(definition, frame)
    return definition, variant, frame


def _supplied_frame_authority(specification, component, frame_id, frame_hash):
    frame = _supplied_frame(specification, frame_id, frame_hash)
    definitions = tuple(
        definition
        for definition in specification.supplied_interface_definitions
        if getattr(definition.shaft or definition.mounting_face, "reference_frame_id", None)
        == frame_id
    )
    if len(definitions) != 1:
        raise ValueError("supplied reference frame must resolve one active interface")
    definition = definitions[0]
    if definition.interface_id not in component.interfaces:
        raise ValueError("supplied reference frame interface is not declared by its instance")
    _, _, active_frame = _supplied_interface(
        specification, definition.interface_id, definition.interface_hash
    )
    if active_frame is None or active_frame.frame_hash != frame_hash:
        raise ValueError("supplied reference frame is not the exact active interface frame")
    return frame


def _generated_interface(specification, interface_id, interface_hash, label):
    generated = specification.generated_part
    if generated is None:
        raise ValueError(f"{label} requires a generated specification")
    if interface_id not in specification.interfaces:
        raise ValueError(f"{label} is not declared by its component")
    interface = _lookup_one(
        generated.interfaces,
        lambda item: item.interface_id == interface_id
        and item.interface_hash == interface_hash,
        f"{label} cannot be resolved by exact ID and hash",
    )
    if not isinstance(interface, GeneratedRotationalInterface):
        raise ValueError(f"{label} is not a generated rotational interface")
    return interface


def _generated_frame(specification, frame_id, frame_hash, label):
    generated = specification.generated_part
    if generated is None:
        raise ValueError(f"{label} requires a generated specification")
    return _lookup_one(
        generated.reference_frames,
        lambda item: item.frame_id == frame_id and item.frame_hash == frame_hash,
        f"{label} cannot be resolved by exact ID and hash",
    )


def resolve_candidate_axis_source(candidate, source: _AxisSource):
    """Resolve one candidate physical axis from M13-1 or M13-2 authority."""
    source = _validated(
        source,
        (
            SuppliedRotationalInterfaceAxisSource,
            SuppliedReferenceFrameAxisSource,
            GeneratedRotationalInterfaceAxisSource,
            GeneratedReferenceFrameAxisSource,
        ),
        "candidate axis source",
    )
    candidate, component, specification = _candidate_context(
        candidate, source.source_physical_instance_id
    )
    if isinstance(source, (SuppliedRotationalInterfaceAxisSource, SuppliedReferenceFrameAxisSource)):
        if source.specification_hash != component.specification_hash:
            raise ValueError("candidate supplied axis source specification identity mismatch")
        if (
            specification.geometry_source is None
            or source.geometry_reference_hash != specification.geometry_source.reference_hash
        ):
            raise ValueError("candidate supplied axis source geometry identity mismatch")
        if isinstance(source, SuppliedRotationalInterfaceAxisSource):
            if source.interface_id not in component.interfaces:
                raise ValueError("candidate supplied axis interface is not declared by its instance")
            _, variant, _ = _supplied_interface(
                specification, source.interface_id, source.interface_hash
            )
            if not isinstance(variant, RotationalShaftInterface):
                raise ValueError("candidate supplied rotational axis is not a shaft interface")
            return variant
        frame = _supplied_frame_authority(
            specification, component, source.frame_id, source.frame_hash
        )
        m13_local_pose(frame)
        return frame
    if source.generated_specification_hash != component.specification_hash:
        raise ValueError("candidate generated axis source specification identity mismatch")
    if isinstance(source, GeneratedRotationalInterfaceAxisSource):
        if source.interface_id not in component.interfaces:
            raise ValueError("candidate generated axis interface is not declared by its instance")
        return _generated_interface(
            specification, source.interface_id, source.interface_hash,
            "candidate generated interface",
        )
    return _generated_frame(
        specification, source.frame_id, source.frame_hash,
        "candidate generated frame",
    )


def resolve_canonical_axis_source(mechanism, source: _AxisSource):
    """Resolve one canonical physical axis from M13-1 or M13-2 authority."""
    source = _validated(
        source,
        (
            CanonicalSuppliedRotationalInterfaceAxisSource,
            CanonicalSuppliedReferenceFrameAxisSource,
            CanonicalGeneratedRotationalInterfaceAxisSource,
            CanonicalGeneratedReferenceFrameAxisSource,
        ),
        "canonical axis source",
    )
    mechanism, component, specification = _canonical_context(
        mechanism, source.source_physical_instance_id
    )
    if isinstance(source, (CanonicalSuppliedRotationalInterfaceAxisSource, CanonicalSuppliedReferenceFrameAxisSource)):
        if source.specification_hash != component.specification_hash:
            raise ValueError("canonical supplied axis source specification identity mismatch")
        if (
            specification.geometry_source is None
            or source.geometry_reference_hash != specification.geometry_source.reference_hash
        ):
            raise ValueError("canonical supplied axis source geometry identity mismatch")
        if isinstance(source, CanonicalSuppliedRotationalInterfaceAxisSource):
            if source.interface_id not in component.interfaces:
                raise ValueError("canonical supplied axis interface is not declared by its instance")
            _, variant, _ = _supplied_interface(
                specification, source.interface_id, source.interface_hash
            )
            if not isinstance(variant, RotationalShaftInterface):
                raise ValueError("canonical supplied rotational axis is not a shaft interface")
            return variant
        frame = _supplied_frame_authority(
            specification, component, source.frame_id, source.frame_hash
        )
        m13_local_pose(frame)
        return frame
    if source.generated_specification_hash != component.specification_hash:
        raise ValueError("canonical generated axis source specification identity mismatch")
    if isinstance(source, CanonicalGeneratedRotationalInterfaceAxisSource):
        if source.interface_id not in component.interfaces:
            raise ValueError("canonical generated axis interface is not declared by its instance")
        return _generated_interface(
            specification, source.interface_id, source.interface_hash,
            "canonical generated interface",
        )
    return _generated_frame(
        specification, source.frame_id, source.frame_hash,
        "canonical generated frame",
    )


def _candidate_view_for_placement(candidate, specification_hash):
    view = build_candidate_view(candidate, specification_hash)
    frames = list(view.reference_frames)
    known = {(frame.frame_id, frame.frame_hash) for frame in frames}
    for specification in candidate.component_specifications:
        generated = specification.generated_part
        if generated is None:
            continue
        for frame in generated.reference_frames:
            if (frame.frame_id, frame.frame_hash) not in known:
                frames.append(frame)
                known.add((frame.frame_id, frame.frame_hash))
    return replace(view, reference_frames=tuple(frames))


def _canonical_view_for_placement(mechanism, specification_hash):
    view = build_canonical_view(mechanism, specification_hash)
    frames = list(view.reference_frames)
    known = {(frame.frame_id, frame.frame_hash) for frame in frames}
    for specification in mechanism.component_specifications:
        generated = specification.generated_part
        if generated is None:
            continue
        for frame in generated.reference_frames:
            if (frame.frame_id, frame.frame_hash) not in known:
                frames.append(frame)
                known.add((frame.frame_id, frame.frame_hash))
    return replace(view, reference_frames=tuple(frames))


def _candidate_source_local_pose(candidate, specification, derivation):
    reference = derivation.source_interface_ref
    if specification.generated_part is not None:
        interface = _generated_interface(
            specification,
            reference.interface_id,
            reference.interface_hash,
            "candidate generated source interface",
        )
        if derivation.rule_id == "frame-generated-placement@1":
            frame_ref = derivation.source_frame_ref
            if frame_ref is None:
                raise ValueError("candidate source frame is missing")
            return pose_from_interface(
                _generated_frame(
                    specification,
                    frame_ref.frame_id,
                    frame_ref.frame_hash,
                    "candidate generated source frame",
                )
            )
        return pose_from_interface(interface)

    definition, variant, active_frame = _supplied_interface(
        specification, reference.interface_id, reference.interface_hash
    )
    if derivation.rule_id == "frame-generated-placement@1":
        frame_ref = derivation.source_frame_ref
        if (
            frame_ref is None
            or active_frame is None
            or active_frame.frame_id != frame_ref.frame_id
            or active_frame.frame_hash != frame_ref.frame_hash
        ):
            raise ValueError(
                "candidate source frame is not the exact frame declared by the source interface"
            )
        return m13_local_pose(active_frame)
    return m13_local_pose(definition, active_frame)


def _candidate_target_local_pose(specification, derivation):
    if specification.generated_part is None:
        raise ValueError("candidate generated placement target is not generated")
    if derivation.rule_id == "coaxial-generated-placement@1":
        reference = derivation.target_generated_interface_ref
        if reference is None:
            raise ValueError("candidate target generated interface is missing")
        return pose_from_interface(
            _generated_interface(
                specification,
                reference.interface_id,
                reference.interface_hash,
                "candidate target generated interface",
            )
        )
    reference = derivation.target_generated_frame_ref
    if reference is None:
        raise ValueError("candidate target generated frame is missing")
    return pose_from_interface(
        _generated_frame(
            specification,
            reference.frame_id,
            reference.frame_hash,
            "candidate target generated frame",
        )
    )


def resolve_candidate_placement(candidate, instance_id: str, derivations=()):
    """Resolve a candidate placement from accepted choices or M13-2 replay."""
    candidate, _, _ = _candidate_context(candidate, instance_id)
    records = tuple(
        _validated(item, GeneratedPlacementDerivation, "candidate placement derivation")
        for item in derivations
    )
    by_id = {item.derivation_id: item for item in records}
    by_target = {item.target_physical_instance_id: item for item in records}
    if len(by_id) != len(records) or len(by_target) != len(records):
        raise ValueError("candidate placement derivation identities must be unique")
    resolving: set[str] = set()
    resolved: dict[str, CadRigidTransform] = {}

    def derive(target_id: str) -> CadRigidTransform:
        if target_id in resolved:
            return resolved[target_id]
        if target_id in resolving:
            raise ValueError("candidate placement derivation set must be acyclic")
        derivation = by_target.get(target_id)
        if derivation is None:
            _, _, target_specification = _candidate_context(candidate, target_id)
            if target_specification.generated_part is not None:
                raise ValueError("candidate generated placement derivation is missing")
            return CadRigidTransform(**candidate_placement_design_variables(candidate, target_id))
        resolving.add(target_id)
        _, source_component, source_specification = _candidate_context(
            candidate, derivation.source_physical_instance_id
        )
        if derivation.source_placement_ref.kind == "design_variable_placement":
            source_world = derive(derivation.source_physical_instance_id)
        else:
            dependency = by_id.get(derivation.source_placement_ref.derivation_id)
            if (
                dependency is None
                or dependency.target_physical_instance_id
                != derivation.source_physical_instance_id
            ):
                raise ValueError("candidate source placement reference does not resolve")
            source_world = derive(dependency.target_physical_instance_id)
        source_pose = compose_poses(
            source_world,
            _candidate_source_local_pose(candidate, source_specification, derivation),
        )
        _, _, target_specification = _candidate_context(candidate, target_id)
        view = _candidate_view_for_placement(
            candidate, target_specification.specification_hash
        )
        inputs = resolve_placement_inputs(derivation, view)
        if len(inputs) > 1:
            raise ValueError("candidate generated placement has more than one axial offset")
        rotation = (
            _resolve_rotation_input(derivation, view)
            if derivation.rotation is not None
            else None
        )
        result = place_generated_target(
            derivation.rule_id,
            source_pose,
            _candidate_target_local_pose(target_specification, derivation),
            next(iter(inputs.values()), None),
            rotation,
        )
        resolving.remove(target_id)
        resolved[target_id] = result
        return result

    return derive(instance_id)


def _canonical_source_local_pose(mechanism, specification, derivation):
    if specification.generated_part is not None:
        interface = _generated_interface(
            specification,
            derivation.source_interface_id,
            derivation.source_interface_hash,
            "canonical generated source interface",
        )
        if derivation.rule_id == "frame-generated-placement@1":
            if derivation.source_frame_id is None or derivation.source_frame_hash is None:
                raise ValueError("canonical source frame is missing")
            return pose_from_interface(
                _generated_frame(
                    specification,
                    derivation.source_frame_id,
                    derivation.source_frame_hash,
                    "canonical generated source frame",
                )
            )
        return pose_from_interface(interface)

    definition, _, active_frame = _supplied_interface(
        specification, derivation.source_interface_id, derivation.source_interface_hash
    )
    if derivation.rule_id == "frame-generated-placement@1":
        if (
            active_frame is None
            or derivation.source_frame_id != active_frame.frame_id
            or derivation.source_frame_hash != active_frame.frame_hash
        ):
            raise ValueError(
                "canonical source frame is not the exact frame declared by the source interface"
            )
        return m13_local_pose(active_frame)
    return m13_local_pose(definition, active_frame)


def _canonical_target_local_pose(specification, derivation):
    if specification.generated_part is None:
        raise ValueError("canonical generated placement target is not generated")
    if derivation.rule_id == "coaxial-generated-placement@1":
        if (
            derivation.target_generated_interface_id is None
            or derivation.target_generated_interface_hash is None
        ):
            raise ValueError("canonical target generated interface is missing")
        return pose_from_interface(
            _generated_interface(
                specification,
                derivation.target_generated_interface_id,
                derivation.target_generated_interface_hash,
                "canonical target generated interface",
            )
        )
    if (
        derivation.target_generated_frame_id is None
        or derivation.target_generated_frame_hash is None
    ):
        raise ValueError("canonical target generated frame is missing")
    return pose_from_interface(
        _generated_frame(
            specification,
            derivation.target_generated_frame_id,
            derivation.target_generated_frame_hash,
            "canonical target generated frame",
        )
    )


def _canonical_design_placement(mechanism, instance_id: str):
    placement = _lookup_one(
        mechanism.placements,
        lambda item: item.instance_id == instance_id,
        "canonical source placement record is missing",
    )
    if (
        placement.origin is not CanonicalPlacementOrigin.ACCEPTED_DESIGN_CHOICE
        or placement.relation != "accepted-design-variable-placement@1"
        or placement.rotation_quaternion != (1.0, 0.0, 0.0, 0.0)
    ):
        raise ValueError("canonical source placement authority is invalid")
    choices = tuple(
        _lookup_one(
            mechanism.accepted_design_choices,
            lambda choice: choice.key == f"{instance_id}.{axis}",
            "canonical source placement design choices are missing",
        )
        for axis in ("placement.x_mm", "placement.y_mm", "placement.z_mm")
    )
    if any(isinstance(choice.value, bool) or not isinstance(choice.value, (int, float)) for choice in choices):
        raise ValueError("canonical source placement design choices are not numeric")
    expected_inputs = tuple(
        identity for choice in choices for identity in choice.source_identities
    )
    expected_coordinates = tuple(float(choice.value) for choice in choices)
    if (
        placement.input_identities != expected_inputs
        or (placement.x_mm, placement.y_mm, placement.z_mm) != expected_coordinates
    ):
        raise ValueError("canonical source placement design choice binding mismatch")
    return CadRigidTransform(
        x_mm=placement.x_mm,
        y_mm=placement.y_mm,
        z_mm=placement.z_mm,
        rotation_quaternion=placement.rotation_quaternion,
    )


def resolve_canonical_placement(mechanism, instance_id: str, derivations=None):
    """Resolve a canonical placement from accepted choices or M13-2 replay."""
    mechanism, _, _ = _canonical_context(mechanism, instance_id)
    records = tuple(
        _validated(item, CanonicalGeneratedPlacementDerivation, "canonical placement derivation")
        for item in (
            mechanism.generated_placement_derivations
            if derivations is None
            else derivations
        )
    )
    by_id = {item.derivation_id: item for item in records}
    by_target = {item.target_canonical_instance_id: item for item in records}
    if len(by_id) != len(records) or len(by_target) != len(records):
        raise ValueError("canonical placement derivation identities must be unique")
    resolving: set[str] = set()
    resolved: dict[str, CadRigidTransform] = {}

    def derive(target_id: str) -> CadRigidTransform:
        if target_id in resolved:
            return resolved[target_id]
        if target_id in resolving:
            raise ValueError("canonical placement derivation set must be acyclic")
        derivation = by_target.get(target_id)
        if derivation is None:
            _, _, target_specification = _canonical_context(mechanism, target_id)
            if target_specification.generated_part is not None:
                raise ValueError("canonical generated placement derivation is missing")
            return _canonical_design_placement(mechanism, target_id)
        resolving.add(target_id)
        _, _, source_specification = _canonical_context(
            mechanism, derivation.source_canonical_instance_id
        )
        if derivation.source_placement_ref.kind == "design_variable_placement":
            source_world = derive(derivation.source_canonical_instance_id)
        else:
            dependency = by_id.get(derivation.source_placement_ref.derivation_id)
            if (
                dependency is None
                or dependency.target_canonical_instance_id
                != derivation.source_canonical_instance_id
            ):
                raise ValueError("canonical source placement reference does not resolve")
            source_world = derive(dependency.target_canonical_instance_id)
        source_pose = compose_poses(
            source_world,
            _canonical_source_local_pose(mechanism, source_specification, derivation),
        )
        _, _, target_specification = _canonical_context(mechanism, target_id)
        view = _canonical_view_for_placement(
            mechanism, target_specification.specification_hash
        )
        inputs = resolve_placement_inputs(derivation, view)
        if len(inputs) > 1:
            raise ValueError("canonical generated placement has more than one axial offset")
        rotation = (
            _resolve_rotation_input(derivation, view)
            if derivation.rotation is not None
            else None
        )
        result = place_generated_target(
            derivation.rule_id,
            source_pose,
            _canonical_target_local_pose(target_specification, derivation),
            next(iter(inputs.values()), None),
            rotation,
        )
        resolving.remove(target_id)
        resolved[target_id] = result
        return result

    return derive(instance_id)


def _joint_connection_inputs(joints_or_realization, connections, components):
    if isinstance(
        joints_or_realization,
        (PhysicalMechanismRealization, CanonicalPhysicalMechanism),
    ):
        realization = joints_or_realization
        return (
            realization.physical_revolute_joint_bindings,
            realization.connections,
            realization.components,
        )
    joints = tuple(joints_or_realization)
    connections = tuple(connections or ())
    # Accept the same collection order used by the M10 bridge call sites.
    if joints and isinstance(joints[0], (MechanicalConnection, CanonicalMechanicalConnection)):
        joints, connections = connections, joints
    return joints, connections, components


def validate_physical_revolute_connections(
    joints_or_realization,
    connections: Sequence[_Connection] | None = None,
    components=None,
) -> Mapping[str, _Connection]:
    """Validate exact directed rotational connections for physical joints."""
    joints, connections, components = _joint_connection_inputs(
        joints_or_realization, connections, components
    )
    joints = tuple(
        _validated(
            item,
            (PhysicalRevoluteJointBinding, CanonicalPhysicalRevoluteJointBinding),
            "physical revolute joint",
        )
        for item in joints
    )
    connections = tuple(
        _validated(
            item,
            (MechanicalConnection, CanonicalMechanicalConnection),
            "mechanical connection",
        )
        for item in connections
    )
    joint_layer = _require_single_layer(
        joints,
        PhysicalRevoluteJointBinding,
        CanonicalPhysicalRevoluteJointBinding,
        "physical revolute joints",
    )
    connection_layer = _require_single_layer(
        connections,
        MechanicalConnection,
        CanonicalMechanicalConnection,
        "mechanical connections",
    )
    if joint_layer != connection_layer:
        raise ValueError(
            "physical joints and mechanical connections must not mix candidate and canonical layers"
        )
    if len({item.physical_joint_id for item in joints}) != len(joints):
        raise ValueError("physical revolute joint IDs must be unique")
    if len({item.connection_id for item in connections}) != len(connections):
        raise ValueError("mechanical connection IDs must be unique")
    component_map = {}
    if components is not None:
        components = tuple(
            _validated(
                item,
                (PhysicalComponentInstance, CanonicalPhysicalComponent),
                "physical component",
            )
            for item in components
        )
        component_layer = _require_single_layer(
            components,
            PhysicalComponentInstance,
            CanonicalPhysicalComponent,
            "physical components",
        )
        if component_layer != joint_layer:
            raise ValueError("physical joints and components must use one layer")
        component_map = {item.instance_id: item for item in components}
        if len(component_map) != len(components):
            raise ValueError("physical component IDs must be unique")

    result = {}
    for joint in joints:
        connection = _lookup_one(
            connections,
            lambda item: item.connection_id == joint.connection_id,
            "physical revolute joint connection must resolve exactly once",
        )
        if connection.kind.value != CanonicalMechanicalConnectionKind.ROTATIONAL_DRIVE.value:
            raise ValueError("physical revolute joint connection must be ROTATIONAL_DRIVE")
        if not any(
            meaning.value == CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT.value
            for meaning in connection.meanings
        ):
            raise ValueError(
                "physical revolute joint connection requires kinematic realization meaning"
            )
        expected = (
            joint.parent_physical_instance_id,
            joint.parent_interface_id,
            joint.child_physical_instance_id,
            joint.child_interface_id,
        )
        actual = (
            connection.from_instance_id,
            connection.from_interface_id,
            connection.to_instance_id,
            connection.to_interface_id,
        )
        if actual != expected:
            raise ValueError(
                "physical revolute joint connection endpoint direction or identity mismatch"
            )
        for instance_id, interface_id in (
            (joint.parent_physical_instance_id, joint.parent_interface_id),
            (joint.child_physical_instance_id, joint.child_interface_id),
        ):
            component = component_map.get(instance_id)
            if component is not None and interface_id not in component.interfaces:
                raise ValueError("physical revolute joint endpoint interface is missing")
        result[joint.physical_joint_id] = connection
    return MappingProxyType({key: result[key] for key in sorted(result)})


def validate_physical_kinematic_tree(
    bodies_or_realization,
    joints: Sequence[_JointBinding] | None = None,
    root_physical_body_id: str | None = None,
) -> Mapping[str, str]:
    """Validate a connected, acyclic, single-root physical body tree."""
    if isinstance(
        bodies_or_realization,
        (PhysicalMechanismRealization, CanonicalPhysicalMechanism),
    ):
        realization = bodies_or_realization
        bodies = realization.physical_rigid_body_bindings
        joints = realization.physical_revolute_joint_bindings
        root_physical_body_id = realization.kinematic_root_physical_body_id
    else:
        bodies = tuple(bodies_or_realization)
        joints = tuple(joints or ())
    bodies = tuple(
        _validated(
            item,
            (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
            "physical rigid body",
        )
        for item in bodies
    )
    joints = tuple(
        _validated(
            item,
            (PhysicalRevoluteJointBinding, CanonicalPhysicalRevoluteJointBinding),
            "physical revolute joint",
        )
        for item in joints
    )
    body_layer = _require_single_layer(
        bodies,
        PhysicalRigidBodyBinding,
        CanonicalPhysicalRigidBodyBinding,
        "physical rigid bodies",
    )
    joint_layer = (
        _require_single_layer(
            joints,
            PhysicalRevoluteJointBinding,
            CanonicalPhysicalRevoluteJointBinding,
            "physical revolute joints",
        )
        if joints
        else body_layer
    )
    if body_layer != joint_layer:
        raise ValueError("physical rigid bodies and joints must use one layer")
    body_ids = tuple(item.physical_body_id for item in bodies)
    if len(set(body_ids)) != len(body_ids):
        raise ValueError("physical rigid body IDs must be unique")
    if (
        not isinstance(root_physical_body_id, str)
        or not root_physical_body_id.strip()
        or root_physical_body_id not in set(body_ids)
    ):
        raise ValueError("kinematic root physical body is missing")
    member_owner = {}
    for body in bodies:
        for instance_id in body.member_physical_instance_ids:
            if instance_id in member_owner:
                raise ValueError("physical body member belongs to multiple bodies")
            member_owner[instance_id] = body.physical_body_id

    parent_by_child: dict[str, str] = {}
    for joint in joints:
        if (
            joint.parent_physical_body_id not in body_ids
            or joint.child_physical_body_id not in body_ids
        ):
            raise ValueError("physical revolute joint body is missing")
        if member_owner.get(joint.parent_physical_instance_id) != joint.parent_physical_body_id:
            raise ValueError("physical revolute joint parent endpoint has no matching body owner")
        if member_owner.get(joint.child_physical_instance_id) != joint.child_physical_body_id:
            raise ValueError("physical revolute joint child endpoint has no matching body owner")
        if joint.child_physical_body_id in parent_by_child:
            raise ValueError("physical kinematic tree has multiple parents")
        parent_by_child[joint.child_physical_body_id] = joint.parent_physical_body_id

    state: dict[str, int] = {}

    def visit(body_id: str) -> None:
        state[body_id] = 1
        for child, parent in parent_by_child.items():
            if parent != body_id:
                continue
            if state.get(child) == 1:
                raise ValueError("physical kinematic tree contains a cycle")
            if state.get(child) != 2:
                visit(child)
        state[body_id] = 2

    for body_id in body_ids:
        if state.get(body_id) is None:
            visit(body_id)
    roots = set(body_ids) - set(parent_by_child)
    if roots != {root_physical_body_id}:
        raise ValueError("physical kinematic tree is disconnected or does not have one root")

    reachable = set()
    stack = [root_physical_body_id]
    while stack:
        body_id = stack.pop()
        if body_id in reachable:
            continue
        reachable.add(body_id)
        stack.extend(
            child for child, parent in parent_by_child.items() if parent == body_id
        )
    if reachable != set(body_ids):
        raise ValueError("physical kinematic tree is disconnected")
    return MappingProxyType({key: parent_by_child[key] for key in sorted(parent_by_child)})


def _validated(value, expected_type, label):
    if not isinstance(value, expected_type):
        expected_name = getattr(expected_type, "__name__", "record")
        raise ValueError(f"{label} must be a typed {expected_name}")
    try:
        return type(value).model_validate(value.model_dump(mode="json"))
    except Exception as exc:
        raise ValueError(f"{label} failed integrity validation: {exc}") from exc


def _validated_sequence(values, expected_type, label):
    result = tuple(
        _validated(value, expected_type, f"{label} entry") for value in values
    )
    if not result:
        raise ValueError(f"{label} must not be empty")
    return result


def _require_single_layer(values, candidate_type, canonical_type, label):
    has_candidate = any(isinstance(value, candidate_type) for value in values)
    has_canonical = any(isinstance(value, canonical_type) for value in values)
    if has_candidate and has_canonical:
        raise ValueError(f"{label} must not mix candidate and canonical records")
    return "candidate" if has_candidate else "canonical"


def _pair_key(binding: _PairBinding) -> tuple[str, str]:
    return (binding.first_physical_instance_id, binding.second_physical_instance_id)


def _normalized_pair_map(
    bindings: Iterable[_PairBinding], physical_instance_ids: Iterable[str]
):
    ids = tuple(physical_instance_ids)
    if not ids or any(not isinstance(value, str) or not value.strip() for value in ids):
        raise ValueError("physical instance universe must contain nonblank IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("physical instance universe must be unique")

    validated = _validated_sequence(
        tuple(bindings),
        (PhysicalPairClassificationBinding, CanonicalPhysicalPairClassificationBinding),
        "physical pair classification bindings",
    )
    _require_single_layer(
        validated,
        PhysicalPairClassificationBinding,
        CanonicalPhysicalPairClassificationBinding,
        "physical pair classification bindings",
    )
    pair_map: dict[tuple[str, str], _PairBinding] = {}
    known_ids = set(ids)
    for binding in validated:
        key = _pair_key(binding)
        if key[0] == key[1]:
            raise ValueError("physical pair policy contains a self pair")
        if key[0] not in known_ids or key[1] not in known_ids:
            raise ValueError("physical pair policy contains an unknown pair member")
        if key in pair_map:
            raise ValueError(f"duplicate physical pair policy: {key!r}")
        pair_map[key] = binding

    expected = {
        (first, second)
        for index, first in enumerate(sorted(ids))
        for second in sorted(ids)[index + 1 :]
    }
    actual = set(pair_map)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"physical pair policy universe mismatch; missing={missing!r}, extra={extra!r}"
        )
    return MappingProxyType({key: pair_map[key] for key in sorted(pair_map)})


def validate_physical_cad_universe(
    mappings: Sequence[_CadMapping],
    assembly: CadAssemblyProgram,
    physical_body_bindings: Sequence[_BodyBinding],
) -> Mapping[str, _CadMapping]:
    """Validate the complete physical-to-CAD and physical-body universe."""
    if not isinstance(assembly, CadAssemblyProgram):
        raise ValueError("CAD assembly must be a typed CadAssemblyProgram")
    try:
        validated_assembly = CadAssemblyProgram.model_validate(
            assembly.model_dump(mode="json")
        )
    except Exception as exc:
        raise ValueError(f"CAD assembly failed integrity validation: {exc}") from exc

    validated_mappings = _validated_sequence(
        mappings,
        (CandidateCadInstanceMapping, CanonicalPhysicalCadMapping),
        "CAD mappings",
    )
    validated_bodies = _validated_sequence(
        physical_body_bindings,
        (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
        "physical rigid body bindings",
    )
    mapping_layer = _require_single_layer(
        validated_mappings,
        CandidateCadInstanceMapping,
        CanonicalPhysicalCadMapping,
        "CAD mappings",
    )
    body_layer = _require_single_layer(
        validated_bodies,
        PhysicalRigidBodyBinding,
        CanonicalPhysicalRigidBodyBinding,
        "physical rigid body bindings",
    )
    if mapping_layer != body_layer:
        raise ValueError("CAD mappings and physical rigid body bindings must use one layer")

    by_physical: dict[str, _CadMapping] = {}
    by_cad: dict[str, _CadMapping] = {}
    for mapping in validated_mappings:
        if mapping.physical_instance_id in by_physical:
            raise ValueError("duplicate physical CAD mapping")
        if mapping.cad_instance_id in by_cad:
            raise ValueError("duplicate CAD instance mapping")
        by_physical[mapping.physical_instance_id] = mapping
        by_cad[mapping.cad_instance_id] = mapping

    assembly_ids = {instance.instance_id for instance in validated_assembly.instances}
    if set(by_cad) != assembly_ids:
        raise ValueError("CAD mapping and assembly membership universe mismatch")
    assembly_by_id = {
        instance.instance_id: instance for instance in validated_assembly.instances
    }
    if any(
        assembly_by_id[mapping.cad_instance_id].placement != mapping.placement
        for mapping in validated_mappings
    ):
        raise ValueError("CAD mapping and assembly placement mismatch")

    body_ids: set[str] = set()
    member_owner: dict[str, str] = {}
    for body in validated_bodies:
        if body.physical_body_id in body_ids:
            raise ValueError("duplicate physical body binding")
        body_ids.add(body.physical_body_id)
        for member_id in body.member_physical_instance_ids:
            if member_id not in by_physical:
                raise ValueError("physical body member universe is not mapped to CAD")
            if member_id in member_owner:
                raise ValueError("physical body member belongs to multiple bodies")
            member_owner[member_id] = body.physical_body_id

    if set(member_owner) != set(by_physical):
        raise ValueError("physical body member universe does not match CAD mappings")

    return MappingProxyType({key: by_physical[key] for key in sorted(by_physical)})


def validate_complete_physical_pair_policy(
    pair_bindings: Sequence[_PairBinding],
    physical_instance_ids: Iterable[str],
) -> Mapping[tuple[str, str], _PairBinding]:
    """Validate and canonically index the complete unordered physical pair set."""
    return _normalized_pair_map(pair_bindings, physical_instance_ids)


def validate_physical_body_pair_consistency(
    physical_body_bindings: Sequence[_BodyBinding],
    pair_bindings: Mapping[tuple[str, str], _PairBinding] | Sequence[_PairBinding],
) -> Mapping[str, str]:
    """Validate body ownership and the classification required by each pair."""
    validated_bodies = _validated_sequence(
        physical_body_bindings,
        (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
        "physical rigid body bindings",
    )
    body_layer = _require_single_layer(
        validated_bodies,
        PhysicalRigidBodyBinding,
        CanonicalPhysicalRigidBodyBinding,
        "physical rigid body bindings",
    )
    owner: dict[str, str] = {}
    body_ids: set[str] = set()
    for body in validated_bodies:
        if body.physical_body_id in body_ids:
            raise ValueError("duplicate physical body binding")
        body_ids.add(body.physical_body_id)
        for member_id in body.member_physical_instance_ids:
            if member_id in owner:
                raise ValueError("physical body member belongs to multiple bodies")
            owner[member_id] = body.physical_body_id

    if isinstance(pair_bindings, Mapping):
        raw_pairs = tuple(pair_bindings.values())
        for key, binding in pair_bindings.items():
            if not isinstance(key, tuple) or key != _pair_key(binding):
                raise ValueError("physical pair map key does not match its binding")
    else:
        raw_pairs = tuple(pair_bindings)
    pair_layer = _require_single_layer(
        raw_pairs,
        PhysicalPairClassificationBinding,
        CanonicalPhysicalPairClassificationBinding,
        "physical pair classification bindings",
    )
    if body_layer != pair_layer:
        raise ValueError(
            "physical rigid body bindings and pair classifications must use one layer"
        )
    pairs = _normalized_pair_map(raw_pairs, owner)

    for key, binding in pairs.items():
        same_body = owner[key[0]] == owner[key[1]]
        if same_body and binding.classification is not PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED:
            raise ValueError("same physical body pair must be SAME_RIGID_GROUP_EXCLUDED")
        if not same_body and binding.classification is PhysicalPairClassification.SAME_RIGID_GROUP_EXCLUDED:
            raise ValueError("cross-body pair cannot be SAME_RIGID_GROUP_EXCLUDED")

    return MappingProxyType({key: owner[key] for key in sorted(owner)})


def derive_multi_joint_collision_pair_inventory(
    physical_mechanism_hash: str,
    cad_realization_hash: str,
    model: KinematicModelV2,
    mappings: Sequence[_CadMapping],
    assembly: CadAssemblyProgram,
    physical_body_bindings: Sequence[_BodyBinding],
    pair_bindings: Sequence[_PairBinding],
) -> MultiJointCollisionPairInventory:
    """Derive the complete concrete pair inventory from physical policy."""
    physical_mechanism_hash = _require_final_hash(physical_mechanism_hash)
    cad_realization_hash = _require_final_hash(cad_realization_hash)
    assembly = _validated(assembly, CadAssemblyProgram, "CAD assembly")
    model = revalidate_v2_kinematic_model(model)
    physical_body_bindings = _validated_sequence(
        physical_body_bindings,
        (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
        "physical rigid body bindings",
    )

    mappings_by_physical = validate_physical_cad_universe(
        mappings, assembly, physical_body_bindings
    )
    member_to_body = validate_v2_body_assembly_agreement(assembly, model)
    concrete_ids = tuple(sorted(mapping.cad_instance_id for mapping in mappings_by_physical.values()))
    model_member_ids = tuple(sorted(member_to_body))
    assembly_instance_ids = tuple(sorted(instance.instance_id for instance in assembly.instances))
    if not (
        concrete_ids == model_member_ids == assembly_instance_ids
    ):
        raise ValueError(
            "concrete instance universe must match the CAD assembly and v2 body members"
        )

    physical_instance_ids = tuple(sorted(mappings_by_physical))
    physical_pair_map = validate_complete_physical_pair_policy(
        pair_bindings, physical_instance_ids
    )
    physical_owner_by_instance = validate_physical_body_pair_consistency(
        physical_body_bindings, physical_pair_map
    )
    if set(physical_owner_by_instance) != set(physical_instance_ids):
        raise ValueError("physical body and CAD mapping universes do not match")
    for physical_instance_id, mapping in mappings_by_physical.items():
        cad_instance_id = mapping.cad_instance_id
        v2_body = member_to_body.get(cad_instance_id)
        if v2_body is None or v2_body.body_id != physical_owner_by_instance[physical_instance_id]:
            raise ValueError("physical body ownership disagrees with v2 body membership")

    entries_by_pair: dict[tuple[str, str], MultiJointCollisionPairEntry] = {}
    for physical_pair, binding in physical_pair_map.items():
        concrete_pair = tuple(
            sorted(
                (
                    mappings_by_physical[physical_pair[0]].cad_instance_id,
                    mappings_by_physical[physical_pair[1]].cad_instance_id,
                )
            )
        )
        if concrete_pair in entries_by_pair:
            raise ValueError("physical-to-CAD pair mapping is not one-to-one")
        entries_by_pair[concrete_pair] = MultiJointCollisionPairEntry(
            first_instance_id=concrete_pair[0],
            second_instance_id=concrete_pair[1],
            classification=binding.classification,
            exclusion_reason=binding.exclusion_reason,
        )

    expected_pairs = tuple(itertools.combinations(concrete_ids, 2))
    if tuple(sorted(entries_by_pair)) != expected_pairs:
        raise ValueError("derived concrete pair inventory is incomplete")

    return MultiJointCollisionPairInventory(
        physical_mechanism_hash=physical_mechanism_hash,
        physical_body_binding_hashes=tuple(
            sorted(binding.binding_hash for binding in physical_body_bindings)
        ),
        cad_realization_hash=cad_realization_hash,
        m10_model_hash=kinematic_model_hash(model),
        complete_concrete_instance_ids=concrete_ids,
        expected_pair_universe=expected_pairs,
        entries=tuple(entries_by_pair[pair] for pair in expected_pairs),
    )


def exact_scope_from_inventory(
    inventory: MultiJointCollisionPairInventory,
    *,
    model: KinematicModelV2,
    mappings: Sequence[_CadMapping],
    assembly: CadAssemblyProgram,
    physical_body_bindings: Sequence[_BodyBinding],
    pair_bindings: Sequence[_PairBinding],
) -> tuple[ExactConstituentPair, ...]:
    """Validate trusted inputs before projecting checked concrete pairs."""
    try:
        inventory = MultiJointCollisionPairInventory.model_validate(
            inventory.model_dump(mode="json")
        )
    except Exception as exc:
        raise ValueError("multi-joint collision pair inventory is not finalized") from exc

    expected_inventory = derive_multi_joint_collision_pair_inventory(
        physical_mechanism_hash=inventory.physical_mechanism_hash,
        cad_realization_hash=inventory.cad_realization_hash,
        model=model,
        mappings=mappings,
        assembly=assembly,
        physical_body_bindings=physical_body_bindings,
        pair_bindings=pair_bindings,
    )
    if expected_inventory != inventory:
        raise ValueError("inventory does not match trusted physical inputs")

    pairs = tuple(
        ExactConstituentPair(
            first_instance_id=entry.first_instance_id,
            second_instance_id=entry.second_instance_id,
        )
        for entry in inventory.entries
        if entry.classification is PhysicalPairClassification.CHECK_CLEARANCE
    )
    return canonical_exact_pair_scope(pairs)


def lower_physical_axis_to_parent_body_reference(
    source_axis_origin: tuple[float, float, float],
    source_axis_direction: tuple[float, float, float],
    source_instance_home: CadRigidTransform,
    parent_reference_home: CadRigidTransform,
    axis_sign: int,
) -> _SemanticAxisPose:
    """Lower a resolved semantic axis into its parent body's reference frame."""
    if type(axis_sign) is not int or axis_sign not in (1, -1):
        raise ValueError("physical joint axis sign must be exactly 1 or -1")
    if not isinstance(source_instance_home, CadRigidTransform):
        raise ValueError("source instance home must be a CadRigidTransform")
    if not isinstance(parent_reference_home, CadRigidTransform):
        raise ValueError("parent reference home must be a CadRigidTransform")

    source_axis_tip = tuple(
        origin + direction
        for origin, direction in zip(source_axis_origin, source_axis_direction)
    )
    world_origin = transform_apply(
        source_instance_home, source_axis_origin
    )
    world_tip = transform_apply(source_instance_home, source_axis_tip)
    parent_reference_inverse = transform_inverse(parent_reference_home)
    parent_origin = transform_apply(parent_reference_inverse, world_origin)
    parent_tip = transform_apply(parent_reference_inverse, world_tip)
    direction = normalize_direction(
        tuple(
            axis_sign * (tip - origin)
            for tip, origin in zip(parent_tip, parent_origin)
        )
    )
    return parent_origin, direction


def derive_body_member_offsets(
    body: _BodyBinding,
    semantic_placements: Mapping[str, CadRigidTransform],
) -> tuple[KinematicRigidBodyMember, ...]:
    """Derive full-precision body-reference offsets from semantic home poses."""
    body = _validated(
        body,
        (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
        "physical rigid body",
    )
    reference_home = semantic_placements.get(body.reference_physical_instance_id)
    if not isinstance(reference_home, CadRigidTransform):
        raise ValueError("physical body reference semantic placement is missing")

    offsets = []
    for physical_instance_id in sorted(body.member_physical_instance_ids):
        member_home = semantic_placements.get(physical_instance_id)
        if not isinstance(member_home, CadRigidTransform):
            raise ValueError("physical body member semantic placement is missing")
        offset = (
            CadRigidTransform()
            if physical_instance_id == body.reference_physical_instance_id
            else transform_compose(transform_inverse(reference_home), member_home)
        )
        offsets.append(
            KinematicRigidBodyMember(
                member_instance_id=physical_instance_id,
                reference_to_member_home=offset,
            )
        )
    return tuple(offsets)


def compile_kinematic_model_v2(
    assembly: CadAssemblyProgram,
    body_bindings: Sequence[_BodyBinding],
    joint_bindings: Sequence[_JointBinding],
    semantic_placements: Mapping[str, CadRigidTransform],
    physical_to_cad_instance_ids: Mapping[str, str],
    semantic_axis_poses: Mapping[str, _SemanticAxisPose],
    model_id: str,
) -> KinematicModelV2:
    """Compile resolved physical semantics into a checked M10 v2 model."""
    if not isinstance(assembly, CadAssemblyProgram):
        raise ValueError("CAD assembly must be a typed CadAssemblyProgram")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("kinematic model ID must not be blank")

    bodies = _validated_sequence(
        body_bindings,
        (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
        "physical rigid body bindings",
    )
    joints = tuple(
        _validated(
            joint,
            (PhysicalRevoluteJointBinding, CanonicalPhysicalRevoluteJointBinding),
            "physical revolute joint",
        )
        for joint in joint_bindings
    )
    if joints:
        _require_single_layer(
            joints,
            PhysicalRevoluteJointBinding,
            CanonicalPhysicalRevoluteJointBinding,
            "physical revolute joints",
        )

    physical_ids = tuple(
        member_id
        for body in bodies
        for member_id in body.member_physical_instance_ids
    )
    if len(set(physical_ids)) != len(physical_ids):
        raise ValueError("physical body member IDs must be unique across bodies")
    if set(semantic_placements) != set(physical_ids):
        raise ValueError("semantic placement universe does not match body members")
    if set(physical_to_cad_instance_ids) != set(physical_ids):
        raise ValueError("physical-to-CAD instance universe does not match body members")
    cad_ids = tuple(physical_to_cad_instance_ids[physical_id] for physical_id in physical_ids)
    if any(not isinstance(cad_id, str) or not cad_id.strip() for cad_id in cad_ids):
        raise ValueError("physical-to-CAD instance IDs must not be blank")
    if len(set(cad_ids)) != len(cad_ids):
        raise ValueError("physical-to-CAD instance IDs must be unique")
    assembly_by_id = {instance.instance_id: instance for instance in assembly.instances}
    if set(cad_ids) != set(assembly_by_id):
        raise ValueError("physical-to-CAD instance universe does not match assembly")
    for physical_id, cad_id in physical_to_cad_instance_ids.items():
        if not rigid_transform_agrees(
            semantic_placements[physical_id],
            assembly_by_id[cad_id].placement,
            RIGID_TRANSFORM_AGREEMENT_VERSION,
        ):
            raise ValueError("semantic placement disagrees with CAD assembly placement")

    body_by_id = {body.physical_body_id: body for body in bodies}
    if len(body_by_id) != len(bodies):
        raise ValueError("physical body IDs must be unique")
    emitted_bodies = []
    for body in bodies:
        offsets = derive_body_member_offsets(body, semantic_placements)
        emitted_members = tuple(
            member.model_copy(
                update={
                    "member_instance_id": physical_to_cad_instance_ids[
                        member.member_instance_id
                    ]
                }
            )
            for member in offsets
        )
        emitted_bodies.append(
            KinematicRigidBody(
                body_id=body.physical_body_id,
                reference_member_instance_id=physical_to_cad_instance_ids[
                    body.reference_physical_instance_id
                ],
                members=emitted_members,
            )
        )

    joint_ids = tuple(joint.physical_joint_id for joint in joints)
    if len(set(joint_ids)) != len(joint_ids):
        raise ValueError("physical revolute joint IDs must be unique")
    if set(semantic_axis_poses) != set(joint_ids):
        raise ValueError("semantic axis pose universe does not match physical joints")

    emitted_joints = []
    for joint in joints:
        parent_body = body_by_id.get(joint.parent_physical_body_id)
        if parent_body is None:
            raise ValueError("physical revolute joint parent body is missing")
        source_home = semantic_placements.get(
            joint.axis_source.source_physical_instance_id
        )
        if not isinstance(source_home, CadRigidTransform):
            raise ValueError("physical joint axis source semantic placement is missing")
        parent_home = semantic_placements[parent_body.reference_physical_instance_id]
        source_origin, source_direction = semantic_axis_poses[joint.physical_joint_id]
        axis_origin, axis_direction = lower_physical_axis_to_parent_body_reference(
            source_origin,
            source_direction,
            source_home,
            parent_home,
            joint.axis_sign,
        )
        emitted_joints.append(
            RevoluteJointModelV2(
                joint_id=joint.physical_joint_id,
                joint_kind=KinematicJointKind.REVOLUTE,
                parent_body_id=joint.parent_physical_body_id,
                child_body_id=joint.child_physical_body_id,
                axis_origin_x_mm=axis_origin[0],
                axis_origin_y_mm=axis_origin[1],
                axis_origin_z_mm=axis_origin[2],
                axis_direction_x=axis_direction[0],
                axis_direction_y=axis_direction[1],
                axis_direction_z=axis_direction[2],
                min_angle_deg=joint.min_angle_deg,
                max_angle_deg=joint.max_angle_deg,
            )
        )

    model = revalidate_v2_kinematic_model(
        KinematicModelV2(
            model_id=model_id,
            bodies=tuple(emitted_bodies),
            joints=tuple(emitted_joints),
        )
    )
    validate_v2_body_assembly_agreement(assembly, model)
    MultiJointKinematicsService().evaluate(
        assembly,
        model,
        JointConfiguration(
            model_id=model.model_id,
            positions={joint.joint_id: 0.0 for joint in model.joints},
        ),
    )
    return model


def _stable_physical_ids(
    values, attribute: str, label: str, *, allow_empty: bool = False
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{label} must be an iterable of IDs")
    try:
        ids = tuple(
            value if isinstance(value, str) else getattr(value, attribute, None)
            for value in values
        )
    except TypeError as exc:
        raise ValueError(f"{label} must be an iterable of IDs") from exc
    if (not allow_empty and not ids) or any(
        not isinstance(value, str) or not value.strip() for value in ids
    ):
        raise ValueError(f"{label} must contain nonblank IDs")
    if len(set(ids)) != len(ids):
        raise ValueError(f"{label} must contain unique IDs")
    return tuple(sorted(ids))


def physical_to_m10_v2_model_id(
    physical_body_ids,
    physical_joint_ids,
) -> str:
    """Derive the bridge-local model identity from stable physical topology IDs."""
    body_ids = _stable_physical_ids(
        physical_body_ids, "physical_body_id", "physical body IDs"
    )
    joint_ids = _stable_physical_ids(
        physical_joint_ids,
        "physical_joint_id",
        "physical joint IDs",
        allow_empty=True,
    )
    payload = {
        "schema_version": "physical-to-m10-v2-model-id@1",
        "physical_body_ids": list(body_ids),
        "physical_joint_ids": list(joint_ids),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "physical-to-m10-v2-model@1:" + hashlib.sha256(encoded).hexdigest()


def _trusted_scope_from_inventory(
    inventory: MultiJointCollisionPairInventory,
) -> tuple[ExactConstituentPair, ...]:
    return canonical_exact_pair_scope(
        tuple(
            ExactConstituentPair(
                first_instance_id=entry.first_instance_id,
                second_instance_id=entry.second_instance_id,
            )
            for entry in inventory.entries
            if entry.classification is PhysicalPairClassification.CHECK_CLEARANCE
        )
    )


class PhysicalToM10V2Bridge(Model):
    """Frozen, derived binding of physical authority to M10 v2 analysis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["physical-to-m10-v2-bridge@1"] = (
        "physical-to-m10-v2-bridge@1"
    )
    physical_mechanism_hash: str
    kinematic_root_binding_hash: str
    physical_body_binding_hashes: tuple[str, ...] = Field(min_length=1)
    physical_joint_binding_hashes: tuple[str, ...] = ()
    semantic_placement_identities: tuple[str, ...] = Field(min_length=1)
    axis_source_identities: tuple[str, ...] = ()
    cad_mapping_hashes: tuple[str, ...] = Field(min_length=1)
    physical_pair_classification_set_hash: str
    model: KinematicModelV2
    m10_model_hash: str
    inventory: MultiJointCollisionPairInventory
    inventory_hash: str
    exact_pair_scope: tuple[ExactConstituentPair, ...] = Field(min_length=1)
    exact_pair_scope_hash: str
    ordered_body_ids: tuple[str, ...] = Field(min_length=1)
    ordered_joint_ids: tuple[str, ...] = ()
    physical_to_m10_bridge_hash: str = "pending"

    _validate_hashes = field_validator(
        "physical_mechanism_hash",
        "kinematic_root_binding_hash",
        "physical_pair_classification_set_hash",
        "m10_model_hash",
        "inventory_hash",
        "exact_pair_scope_hash",
    )(_require_final_hash)

    @field_validator(
        "physical_body_binding_hashes",
        "physical_joint_binding_hashes",
        "semantic_placement_identities",
        "axis_source_identities",
        "cad_mapping_hashes",
    )
    @classmethod
    def _validate_identity_hashes(cls, values):
        values = tuple(values)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("bridge identity projections must not be blank")
        for value in values:
            _require_final_hash(value)
        return values

    @model_validator(mode="after")
    def validate_bridge(self) -> "PhysicalToM10V2Bridge":
        try:
            model = revalidate_v2_kinematic_model(self.model)
            inventory = MultiJointCollisionPairInventory.model_validate(
                self.inventory.model_dump(mode="json")
            )
            scope = canonical_exact_pair_scope(
                tuple(
                    ExactConstituentPair.model_validate(pair.model_dump(mode="json"))
                    for pair in self.exact_pair_scope
                )
            )
        except Exception as exc:
            raise ValueError(f"bridge nested M10 input integrity failure: {exc}") from exc

        if model != self.model:
            object.__setattr__(self, "model", model)
        if inventory != self.inventory:
            object.__setattr__(self, "inventory", inventory)
        if scope != self.exact_pair_scope:
            object.__setattr__(self, "exact_pair_scope", scope)
        if self.m10_model_hash != kinematic_model_hash(model):
            raise ValueError("bridge M10 model hash mismatch")
        if self.inventory_hash != inventory.inventory_hash:
            raise ValueError("bridge inventory hash mismatch")
        if inventory.m10_model_hash != self.m10_model_hash:
            raise ValueError("bridge inventory model hash mismatch")
        if inventory.physical_mechanism_hash != self.physical_mechanism_hash:
            raise ValueError("bridge inventory physical mechanism binding mismatch")
        if inventory.physical_body_binding_hashes != self.physical_body_binding_hashes:
            raise ValueError("bridge inventory physical body binding mismatch")
        model_member_ids = tuple(
            sorted(member.member_instance_id for body in model.bodies for member in body.members)
        )
        if inventory.complete_concrete_instance_ids != model_member_ids:
            raise ValueError("bridge inventory concrete instance binding mismatch")
        if scope != _trusted_scope_from_inventory(inventory):
            raise ValueError("bridge scope does not match trusted CHECK_CLEARANCE scope")
        if self.exact_pair_scope_hash != exact_pair_scope_hash(scope):
            raise ValueError("bridge exact pair scope hash mismatch")
        if self.ordered_body_ids != tuple(body.body_id for body in model.bodies):
            raise ValueError("bridge ordered body IDs mismatch")
        if self.ordered_joint_ids != tuple(joint.joint_id for joint in model.joints):
            raise ValueError("bridge ordered joint IDs mismatch")
        expected_model_id = physical_to_m10_v2_model_id(
            self.ordered_body_ids, self.ordered_joint_ids
        )
        if model.model_id != expected_model_id:
            raise ValueError("bridge model ID is not the frozen physical topology identity")
        expected = physical_to_m10_bridge_hash(self)
        if self.physical_to_m10_bridge_hash != expected:
            if (
                self.physical_to_m10_bridge_hash == "pending"
                and "physical_to_m10_bridge_hash" not in self.model_fields_set
            ):
                object.__setattr__(self, "physical_to_m10_bridge_hash", expected)
                return self
            raise ValueError("physical-to-M10 bridge hash mismatch")
        return self


def physical_to_m10_bridge_hash(bridge: PhysicalToM10V2Bridge) -> str:
    """Hash a finalized bridge without introducing a model/inventory cycle."""
    if type(bridge) is not PhysicalToM10V2Bridge:
        raise TypeError("bridge hash requires a PhysicalToM10V2Bridge")
    model = revalidate_v2_kinematic_model(bridge.model)
    inventory = MultiJointCollisionPairInventory.model_validate(
        bridge.inventory.model_dump(mode="json")
    )
    scope = canonical_exact_pair_scope(
        tuple(
            ExactConstituentPair.model_validate(pair.model_dump(mode="json"))
            for pair in bridge.exact_pair_scope
        )
    )
    if bridge.m10_model_hash != kinematic_model_hash(model):
        raise ValueError("bridge M10 model hash mismatch")
    if bridge.inventory_hash != inventory.inventory_hash:
        raise ValueError("bridge inventory hash mismatch")
    if inventory.physical_mechanism_hash != bridge.physical_mechanism_hash:
        raise ValueError("bridge inventory physical mechanism binding mismatch")
    if inventory.physical_body_binding_hashes != bridge.physical_body_binding_hashes:
        raise ValueError("bridge inventory physical body binding mismatch")
    model_member_ids = tuple(
        sorted(member.member_instance_id for body in model.bodies for member in body.members)
    )
    if inventory.complete_concrete_instance_ids != model_member_ids:
        raise ValueError("bridge inventory concrete instance binding mismatch")
    if scope != _trusted_scope_from_inventory(inventory):
        raise ValueError("bridge scope does not match trusted CHECK_CLEARANCE scope")
    if bridge.exact_pair_scope_hash != exact_pair_scope_hash(scope):
        raise ValueError("bridge exact pair scope hash mismatch")
    payload = bridge.model_dump(mode="json")
    payload.pop("model", None)
    payload.pop("inventory", None)
    payload.pop("physical_to_m10_bridge_hash", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def validate_physical_to_m10_v2_bridge(
    bridge: PhysicalToM10V2Bridge,
    *,
    physical_mechanism_hash: str,
    root_physical_body_id: str,
    model: KinematicModelV2,
    bodies,
    joints,
    components,
    connections,
    mappings,
    assembly: CadAssemblyProgram,
    cad_realization_hash: str,
    pair_bindings,
) -> PhysicalToM10V2Bridge:
    """Accept a bridge only after rederiving it from trusted physical/CAD inputs."""
    bridge = _validated(bridge, PhysicalToM10V2Bridge, "physical-to-M10 bridge")
    physical_mechanism_hash = _require_final_hash(physical_mechanism_hash)
    cad_realization_hash = _require_final_hash(cad_realization_hash)
    model = revalidate_v2_kinematic_model(model)
    bodies = _validated_sequence(
        bodies,
        (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
        "trusted physical rigid body bindings",
    )
    joints = tuple(
        _validated(
            joint,
            (PhysicalRevoluteJointBinding, CanonicalPhysicalRevoluteJointBinding),
            "trusted physical revolute joint",
        )
        for joint in joints
    )
    pairs = _validated_sequence(
        pair_bindings,
        (PhysicalPairClassificationBinding, CanonicalPhysicalPairClassificationBinding),
        "trusted physical pair classifications",
    )
    components = _validated_sequence(
        components,
        (PhysicalComponentInstance, CanonicalPhysicalComponent),
        "trusted physical components",
    )
    assembly = _validated(assembly, CadAssemblyProgram, "trusted CAD assembly")
    mappings = tuple(
        _validated(
            mapping,
            (CandidateCadInstanceMapping, CanonicalPhysicalCadMapping),
            "trusted CAD mapping",
        )
        for mapping in mappings
    )

    validate_physical_kinematic_tree(bodies, joints, root_physical_body_id)
    validate_physical_revolute_connections(joints, connections, components)
    mapping_by_physical = validate_physical_cad_universe(mappings, assembly, bodies)
    expected_inventory = derive_multi_joint_collision_pair_inventory(
        physical_mechanism_hash=physical_mechanism_hash,
        cad_realization_hash=cad_realization_hash,
        model=model,
        mappings=tuple(mapping_by_physical.values()),
        assembly=assembly,
        physical_body_bindings=bodies,
        pair_bindings=pairs,
    )
    expected_scope = exact_scope_from_inventory(
        expected_inventory,
        model=model,
        mappings=tuple(mapping_by_physical.values()),
        assembly=assembly,
        physical_body_bindings=bodies,
        pair_bindings=pairs,
    )
    expected_body_hashes = tuple(sorted(body.binding_hash for body in bodies))
    expected_joint_hashes = tuple(
        joint.binding_hash
        for joint in sorted(joints, key=lambda item: item.physical_joint_id)
    )
    expected_placement_identities = tuple(
        sorted(
            (
                mapping.placement_origin.origin_hash
                if isinstance(mapping, CandidateCadInstanceMapping)
                else mapping.placement_hash or mapping.component_hash
            )
            for mapping in mapping_by_physical.values()
        )
    )
    expected_axis_source_identities = tuple(
        joint.axis_source.source_hash
        for joint in sorted(joints, key=lambda item: item.physical_joint_id)
    )
    expected_model_hash = kinematic_model_hash(model)
    expected_model_id = physical_to_m10_v2_model_id(
        (body.physical_body_id for body in bodies),
        (joint.physical_joint_id for joint in joints),
    )
    checks = (
        (bridge.physical_mechanism_hash == physical_mechanism_hash, "physical mechanism"),
        (
            bridge.kinematic_root_binding_hash
            == physical_kinematic_root_hash(root_physical_body_id),
            "kinematic root",
        ),
        (bridge.physical_body_binding_hashes == expected_body_hashes, "physical body binding"),
        (bridge.physical_joint_binding_hashes == expected_joint_hashes, "physical joint binding"),
        (
            bridge.semantic_placement_identities == expected_placement_identities,
            "semantic placement",
        ),
        (bridge.axis_source_identities == expected_axis_source_identities, "axis source"),
        (
            bridge.cad_mapping_hashes
            == tuple(sorted(mapping.mapping_hash for mapping in mapping_by_physical.values())),
            "CAD mapping",
        ),
        (
            bridge.physical_pair_classification_set_hash
            == physical_pair_classification_set_hash(pairs),
            "physical pair classification",
        ),
        (bridge.model == model, "M10 model"),
        (bridge.model.model_id == expected_model_id, "M10 model ID"),
        (bridge.m10_model_hash == expected_model_hash, "M10 model hash"),
        (bridge.inventory == expected_inventory, "inventory"),
        (bridge.inventory_hash == expected_inventory.inventory_hash, "inventory hash"),
        (bridge.exact_pair_scope == expected_scope, "exact pair scope"),
        (bridge.exact_pair_scope_hash == exact_pair_scope_hash(expected_scope), "scope hash"),
    )
    for matches, identity in checks:
        if not matches:
            raise ValueError(f"bridge {identity} does not match trusted physical inputs")
    if bridge.physical_to_m10_bridge_hash != physical_to_m10_bridge_hash(bridge):
        raise ValueError("bridge hash does not match trusted physical inputs")
    return bridge


def _axis_pose_from_resolved_source(source) -> _SemanticAxisPose:
    if isinstance(source, RotationalShaftInterface):
        return (
            tuple(_fact_value(source.axis_point, "shaft axis point")),
            normalize_direction(_fact_value(source.axis_direction, "shaft axis direction")),
        )
    if isinstance(source, GeneratedRotationalInterface):
        return source.axis_point, normalize_direction(source.axis_direction)
    if isinstance(source, (GeneratedReferenceFrame,)):
        origin = source.origin
        direction = rotate_vector((0.0, 0.0, 1.0), source.orientation)
        return origin, normalize_direction(direction)
    if isinstance(source, SuppliedComponentReferenceFrame):
        pose = m13_local_pose(source)
        origin = (pose.x_mm, pose.y_mm, pose.z_mm)
        direction = transform_apply(pose, (0.0, 0.0, 1.0))
        return origin, normalize_direction(tuple(b - a for a, b in zip(origin, direction)))
    raise ValueError("resolved physical axis source has no supported semantic axis")


def _candidate_semantic_placements(candidate, mappings, derivations):
    records = tuple(
        _validated(item, GeneratedPlacementDerivation, "candidate placement derivation")
        for item in derivations
    )
    return {
        mapping.physical_instance_id: resolve_candidate_placement(
            candidate, mapping.physical_instance_id, records
        )
        for mapping in mappings
    }, tuple(mapping.placement_origin.origin_hash for mapping in mappings)


def _canonical_semantic_placements(mechanism, mappings):
    return {
        mapping.physical_instance_id: (
            CadRigidTransform()
            if next(
                component
                for component in mechanism.components
                if component.instance_id == mapping.physical_instance_id
            ).placement_id is None
            else resolve_canonical_placement(mechanism, mapping.physical_instance_id)
        )
        for mapping in mappings
    }, tuple(
        mapping.placement_hash or mapping.component_hash for mapping in mappings
    )


def _compile_physical_to_m10_core(
    *,
    physical_mechanism_hash: str,
    root_physical_body_id: str,
    bodies,
    joints,
    components,
    connections,
    mappings,
    assembly: CadAssemblyProgram,
    cad_realization_hash: str,
    pair_bindings,
    semantic_placements,
    semantic_placement_identities,
    axis_poses,
) -> PhysicalToM10V2Bridge:
    physical_mechanism_hash = _require_final_hash(physical_mechanism_hash)
    assembly = _validated(assembly, CadAssemblyProgram, "CAD assembly")
    bodies = _validated_sequence(
        bodies,
        (PhysicalRigidBodyBinding, CanonicalPhysicalRigidBodyBinding),
        "physical rigid body bindings",
    )
    joints = tuple(
        _validated(
            joint,
            (PhysicalRevoluteJointBinding, CanonicalPhysicalRevoluteJointBinding),
            "physical revolute joint",
        )
        for joint in joints
    )
    pairs = _validated_sequence(
        pair_bindings,
        (PhysicalPairClassificationBinding, CanonicalPhysicalPairClassificationBinding),
        "physical pair classification bindings",
    )
    validate_physical_kinematic_tree(bodies, joints, root_physical_body_id)
    components = _validated_sequence(
        components,
        (PhysicalComponentInstance, CanonicalPhysicalComponent),
        "physical components",
    )
    validate_physical_revolute_connections(joints, connections, components)
    mapping_by_physical = validate_physical_cad_universe(mappings, assembly, bodies)
    physical_ids = tuple(sorted(mapping_by_physical))
    if set(semantic_placements) != set(physical_ids):
        raise ValueError("semantic placement universe does not match physical CAD universe")
    if set(axis_poses) != {joint.physical_joint_id for joint in joints}:
        raise ValueError("semantic axis pose universe does not match physical joints")
    model_id = physical_to_m10_v2_model_id(
        (body.physical_body_id for body in bodies),
        (joint.physical_joint_id for joint in joints),
    )
    model = compile_kinematic_model_v2(
        assembly,
        bodies,
        joints,
        semantic_placements,
        {physical_id: mapping.cad_instance_id for physical_id, mapping in mapping_by_physical.items()},
        axis_poses,
        model_id,
    )
    inventory = derive_multi_joint_collision_pair_inventory(
        physical_mechanism_hash=physical_mechanism_hash,
        cad_realization_hash=_require_final_hash(cad_realization_hash),
        model=model,
        mappings=tuple(mapping_by_physical.values()),
        assembly=assembly,
        physical_body_bindings=bodies,
        pair_bindings=pairs,
    )
    scope = exact_scope_from_inventory(
        inventory,
        model=model,
        mappings=tuple(mapping_by_physical.values()),
        assembly=assembly,
        physical_body_bindings=bodies,
        pair_bindings=pairs,
    )
    bridge = PhysicalToM10V2Bridge(
        physical_mechanism_hash=physical_mechanism_hash,
        kinematic_root_binding_hash=physical_kinematic_root_hash(root_physical_body_id),
        physical_body_binding_hashes=tuple(
            sorted(body.binding_hash for body in bodies)
        ),
        physical_joint_binding_hashes=tuple(
            joint.binding_hash for joint in sorted(joints, key=lambda item: item.physical_joint_id)
        ),
        semantic_placement_identities=tuple(sorted(semantic_placement_identities)),
        axis_source_identities=tuple(
            joint.axis_source.source_hash
            for joint in sorted(joints, key=lambda item: item.physical_joint_id)
        ),
        cad_mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in mapping_by_physical.values())),
        physical_pair_classification_set_hash=physical_pair_classification_set_hash(pairs),
        model=model,
        m10_model_hash=kinematic_model_hash(model),
        inventory=inventory,
        inventory_hash=inventory.inventory_hash,
        exact_pair_scope=scope,
        exact_pair_scope_hash=exact_pair_scope_hash(scope),
        ordered_body_ids=tuple(body.body_id for body in model.bodies),
        ordered_joint_ids=tuple(joint.joint_id for joint in model.joints),
    )
    return validate_physical_to_m10_v2_bridge(
        bridge,
        physical_mechanism_hash=physical_mechanism_hash,
        root_physical_body_id=root_physical_body_id,
        model=model,
        bodies=bodies,
        joints=joints,
        components=components,
        connections=connections,
        mappings=tuple(mapping_by_physical.values()),
        assembly=assembly,
        cad_realization_hash=cad_realization_hash,
        pair_bindings=pairs,
    )


class PhysicalToM10V2BridgeCompiler:
    """Compile candidate or canonical physical authority through one pure core."""

    def compile_candidate(
        self,
        candidate: MechanicalDesignCandidate,
        cad_realization: CandidateCadRealization,
        placement_derivations=(),
    ) -> PhysicalToM10V2Bridge:
        if type(candidate) is not MechanicalDesignCandidate:
            raise ValueError("candidate bridge input must be a typed MechanicalDesignCandidate")
        if type(cad_realization) is not CandidateCadRealization:
            raise ValueError("candidate bridge CAD input must be CandidateCadRealization")
        candidate = _validated(candidate, MechanicalDesignCandidate, "candidate")
        cad_realization = _validated(cad_realization, CandidateCadRealization, "candidate CAD realization")
        if cad_realization.candidate_hash != candidate.candidate_hash:
            raise ValueError("candidate CAD realization does not bind the candidate")
        realization = _validated(
            candidate.realization, PhysicalMechanismRealization, "candidate physical realization"
        )
        if realization.schema_version != "physical-mechanism-realization@2":
            raise ValueError("candidate bridge requires physical-mechanism-realization@2")
        mappings = tuple(
            _validated(item, CandidateCadInstanceMapping, "candidate CAD mapping")
            for item in cad_realization.mappings
        )
        placement_derivations = tuple(
            _validated(item, GeneratedPlacementDerivation, "candidate placement derivation")
            for item in placement_derivations
        )
        if cad_realization.placement_derivations_hash is None:
            if placement_derivations:
                raise ValueError("candidate placement derivations are not bound by the CAD realization")
        elif placement_derivations_hash(placement_derivations) != cad_realization.placement_derivations_hash:
            raise ValueError("candidate placement derivation identity mismatch")
        placements, identities = _candidate_semantic_placements(
            candidate, mappings, placement_derivations
        )
        axis_poses = {
            joint.physical_joint_id: _axis_pose_from_resolved_source(
                resolve_candidate_axis_source(candidate, joint.axis_source)
            )
            for joint in realization.physical_revolute_joint_bindings
        }
        return _compile_physical_to_m10_core(
            physical_mechanism_hash=realization.realization_hash,
            root_physical_body_id=realization.kinematic_root_physical_body_id,
            bodies=realization.physical_rigid_body_bindings,
            joints=realization.physical_revolute_joint_bindings,
            components=realization.components,
            connections=realization.connections,
            mappings=mappings,
            assembly=cad_realization.assembly,
            cad_realization_hash=cad_realization.realization_hash,
            pair_bindings=realization.physical_pair_classification_bindings,
            semantic_placements=placements,
            semantic_placement_identities=identities,
            axis_poses=axis_poses,
        )

    def compile_canonical(
        self,
        reconstruction: CanonicalMechanismReconstruction,
        cad_realization: CanonicalCadRealization,
    ) -> PhysicalToM10V2Bridge:
        if type(cad_realization) is not CanonicalCadRealization:
            raise ValueError("canonical bridge CAD input must be CanonicalCadRealization")
        if type(reconstruction) is not CanonicalMechanismReconstruction:
            raise ValueError(
                "canonical bridge reconstruction input must be a typed "
                "CanonicalMechanismReconstruction"
            )
        reconstruction = _validated(
            reconstruction,
            CanonicalMechanismReconstruction,
            "canonical mechanism reconstruction",
        )
        mechanism = reconstruction.canonical_mechanism
        if len(mechanism.multi_joint_verification_obligations) != 1:
            raise ValueError(
                "canonical bridge requires exactly one multi-joint verification obligation"
            )
        cad_realization = _validated(cad_realization, CanonicalCadRealization, "canonical CAD realization")
        if (
            cad_realization.project_id != reconstruction.project_id
            or cad_realization.revision != reconstruction.revision
            or cad_realization.state_hash != reconstruction.state_hash
            or cad_realization.mechanism_id != mechanism.id
            or cad_realization.mechanism_hash != mechanism.mechanism_hash
        ):
            raise ValueError("canonical CAD realization does not bind the reconstruction")
        if mechanism.schema_version != "canonical-physical-mechanism@3":
            raise ValueError("canonical bridge requires canonical-physical-mechanism@3")
        mappings = tuple(
            _validated(item, CanonicalPhysicalCadMapping, "canonical CAD mapping")
            for item in cad_realization.mappings
        )
        placements, identities = _canonical_semantic_placements(mechanism, mappings)
        axis_poses = {
            joint.physical_joint_id: _axis_pose_from_resolved_source(
                resolve_canonical_axis_source(mechanism, joint.axis_source)
            )
            for joint in mechanism.physical_revolute_joint_bindings
        }
        return _compile_physical_to_m10_core(
            physical_mechanism_hash=mechanism.mechanism_hash,
            root_physical_body_id=mechanism.kinematic_root_physical_body_id,
            bodies=mechanism.physical_rigid_body_bindings,
            joints=mechanism.physical_revolute_joint_bindings,
            components=mechanism.components,
            connections=mechanism.connections,
            mappings=mappings,
            assembly=cad_realization.assembly,
            cad_realization_hash=cad_realization.realization_hash,
            pair_bindings=mechanism.physical_pair_classification_bindings,
            semantic_placements=placements,
            semantic_placement_identities=identities,
            axis_poses=axis_poses,
        )


def compile_candidate(
    candidate: MechanicalDesignCandidate,
    cad_realization: CandidateCadRealization,
    placement_derivations=(),
) -> PhysicalToM10V2Bridge:
    return PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, cad_realization, placement_derivations
    )


def compile_canonical(
    reconstruction: CanonicalMechanismReconstruction,
    cad_realization: CanonicalCadRealization,
) -> PhysicalToM10V2Bridge:
    return PhysicalToM10V2BridgeCompiler().compile_canonical(
        reconstruction, cad_realization
    )


__all__ = [
    "CandidateCanonicalMultiJointEquivalence",
    "CanonicalMultiJointM10Verification",
    "CanonicalMultiJointM10VerificationService",
    "compare_candidate_canonical_multi_joint_semantics",
    "resolve_candidate_axis_source",
    "resolve_candidate_placement",
    "resolve_canonical_axis_source",
    "resolve_canonical_placement",
    "validate_physical_revolute_connections",
    "validate_physical_kinematic_tree",
    "validate_physical_cad_universe",
    "validate_complete_physical_pair_policy",
    "validate_physical_body_pair_consistency",
    "MultiJointCollisionPairEntry",
    "MultiJointCollisionPairInventory",
    "derive_multi_joint_collision_pair_inventory",
    "exact_scope_from_inventory",
    "lower_physical_axis_to_parent_body_reference",
    "derive_body_member_offsets",
    "compile_kinematic_model_v2",
    "PhysicalToM10V2Bridge",
    "PhysicalToM10V2BridgeCompiler",
    "compile_candidate",
    "compile_canonical",
    "physical_to_m10_v2_model_id",
    "physical_to_m10_bridge_hash",
    "validate_physical_to_m10_v2_bridge",
]
