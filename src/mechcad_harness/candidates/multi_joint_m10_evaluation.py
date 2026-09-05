from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_serializer, model_validator

from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.candidates.cad_realization import (
    CandidateCadRealization,
    CandidateGeometryFidelity,
)
from mechcad_harness.candidates.models import MechanicalDesignCandidate
from mechcad_harness.models.common import Model
from mechcad_harness.models.generated_placement import (
    GeneratedPlacementDerivation,
    placement_derivations_hash,
)
from mechcad_harness.models.multi_joint_verification import (
    MultiJointVerificationConfigurationSet,
)
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
    MultiJointCollisionSweepRequestV2,
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModelV2,
    joint_configuration_hash,
    revalidate_v2_kinematic_model,
)
from mechcad_harness.multi_joint_pair_scope import (
    canonical_exact_pair_scope,
)

from .multi_joint_m10_bridge import (
    PhysicalToM10V2Bridge,
    validate_physical_to_m10_v2_bridge,
)
from .services import CandidateCurrentness, CandidateCurrentnessService


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_hash(value: str) -> str:
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError("must be a sha256 hash")
    return value


def _require_hash_or_pending(value: str) -> str:
    return value if value == "pending" else _require_hash(value)


def _require_nonblank(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _hash_model(value: Model, identity_field: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(identity_field, None)
    return _digest(payload)


def _revalidate(value, expected_type, label):
    if type(value) is not expected_type:
        raise ValueError(f"{label} must be a typed {expected_type.__name__}")
    try:
        return expected_type.model_validate(value.model_dump(mode="json"))
    except Exception as exc:
        raise ValueError(f"{label} failed integrity validation: {exc}") from exc


def _sorted_hashes(values, label: str) -> tuple[str, ...]:
    result = tuple(values)
    if any(not isinstance(value, str) for value in result):
        raise ValueError(f"{label} must contain hashes")
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must be unique")
    for value in result:
        _require_hash(value)
    if result != tuple(sorted(result)):
        raise ValueError(f"{label} must be lexically sorted")
    return result


def _configuration_model(model_or_bridge) -> KinematicModelV2:
    if type(model_or_bridge) is PhysicalToM10V2Bridge:
        bridge = _revalidate(model_or_bridge, PhysicalToM10V2Bridge, "bridge")
        return revalidate_v2_kinematic_model(bridge.model)
    return revalidate_v2_kinematic_model(
        _revalidate(model_or_bridge, KinematicModelV2, "M10 v2 model")
    )


def validate_multi_joint_verification_configurations(
    configurations, model_or_bridge
) -> tuple[JointConfiguration, ...]:
    """Validate explicit M13-3 commands against one trusted bridge model."""
    model = _configuration_model(model_or_bridge)
    configurations = tuple(
        _revalidate(configuration, JointConfiguration, "joint configuration")
        for configuration in configurations
    )
    if not configurations:
        raise ValueError("at least one multi-joint verification configuration is required")

    joint_by_id = {joint.joint_id: joint for joint in model.joints}
    expected_ids = set(joint_by_id)
    for configuration in configurations:
        if configuration.model_id != model.model_id:
            raise ValueError("configuration model ID does not match the trusted bridge model")
        if set(configuration.positions) != expected_ids:
            raise ValueError("configuration joint keys do not match the emitted physical joint IDs")
        for joint_id, value in configuration.positions.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("joint configuration values must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError("joint configuration values must be finite")
            joint = joint_by_id[joint_id]
            if any(
                limit is not None and not math.isfinite(float(limit))
                for limit in (joint.min_angle_deg, joint.max_angle_deg)
            ):
                raise ValueError("joint limits must be finite")
            if joint.min_angle_deg is not None and value < joint.min_angle_deg:
                raise ValueError("joint configuration value is below its inclusive limit")
            if joint.max_angle_deg is not None and value > joint.max_angle_deg:
                raise ValueError("joint configuration value is above its inclusive limit")
    return configurations


class CandidateMultiJointM10EvaluationScope(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-multi-joint-m10-evaluation-scope@1"] = (
        "candidate-multi-joint-m10-evaluation-scope@1"
    )
    configuration_set: MultiJointVerificationConfigurationSet
    volume_tolerance_mm3: float
    distance_tolerance_mm: float
    scope_identity: str = Field(min_length=1)
    scope_hash: str = "pending"

    _validate_scope_identity = field_validator("scope_identity")(_require_nonblank)
    _validate_scope_hash = field_validator("scope_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_scope(self) -> "CandidateMultiJointM10EvaluationScope":
        if not all(
            math.isfinite(value) and value >= 0
            for value in (self.volume_tolerance_mm3, self.distance_tolerance_mm)
        ):
            raise ValueError("M10 v2 tolerances must be finite and non-negative")
        expected = candidate_multi_joint_m10_scope_hash(self)
        if self.scope_hash == "pending":
            object.__setattr__(self, "scope_hash", expected)
        elif self.scope_hash != expected:
            raise ValueError("candidate multi-joint M10 scope hash mismatch")
        return self


def candidate_multi_joint_m10_scope_hash(
    scope: CandidateMultiJointM10EvaluationScope,
) -> str:
    return _hash_model(scope, "scope_hash")


class CandidateMultiJointM10EvaluationRequest(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-multi-joint-m10-evaluation-request@1"] = (
        "candidate-multi-joint-m10-evaluation-request@1"
    )
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str
    source_binding_hash: str
    candidate_hash: str
    physical_mechanism_hash: str
    physical_body_binding_hashes: tuple[str, ...] = Field(min_length=1)
    physical_joint_binding_hashes: tuple[str, ...] = ()
    kinematic_root_binding_hash: str
    physical_pair_classification_set_hash: str
    physical_to_m10_bridge_hash: str
    cad_realization_hash: str
    cad_mapping_hashes: tuple[str, ...] = Field(min_length=1)
    m10_model_hash: str
    inventory_hash: str
    exact_pair_scope_hash: str
    scope: CandidateMultiJointM10EvaluationScope
    scope_hash: str
    configuration_set_hash: str
    configuration_hashes: tuple[str, ...] = Field(min_length=1)
    m10_v2_request_hash: str
    placement_derivations: tuple[GeneratedPlacementDerivation, ...] = ()
    placement_derivations_hash: str | None = None
    request_hash: str = "pending"

    _validate_text = field_validator("project_id")(_require_nonblank)
    _validate_hashes = field_validator(
        "source_state_hash",
        "source_binding_hash",
        "candidate_hash",
        "physical_mechanism_hash",
        "kinematic_root_binding_hash",
        "physical_pair_classification_set_hash",
        "physical_to_m10_bridge_hash",
        "cad_realization_hash",
        "m10_model_hash",
        "inventory_hash",
        "exact_pair_scope_hash",
        "scope_hash",
        "configuration_set_hash",
        "m10_v2_request_hash",
    )(_require_hash)

    _validate_request_hash = field_validator("request_hash")(_require_hash_or_pending)

    @field_validator("placement_derivations_hash")
    @classmethod
    def _validate_placement_derivations_hash(cls, value):
        return None if value is None else _require_hash(value)

    @field_validator(
        "physical_body_binding_hashes",
        "physical_joint_binding_hashes",
        "cad_mapping_hashes",
    )
    @classmethod
    def _validate_sorted_hash_collections(cls, values):
        return _sorted_hashes(values, "request identity collection")

    @field_validator("configuration_hashes")
    @classmethod
    def _validate_configuration_hashes(cls, values):
        return tuple(_require_hash(value) for value in values)

    @model_serializer(mode="wrap")
    def serialize_request(self, handler):
        payload = handler(self)
        if not self.placement_derivations:
            payload.pop("placement_derivations", None)
            payload.pop("placement_derivations_hash", None)
        return payload

    @model_validator(mode="after")
    def validate_request(self) -> "CandidateMultiJointM10EvaluationRequest":
        scope = CandidateMultiJointM10EvaluationScope.model_validate(
            self.scope.model_dump(mode="json")
        )
        if scope != self.scope:
            object.__setattr__(self, "scope", scope)
        if self.scope_hash != scope.scope_hash:
            raise ValueError("request scope hash does not match embedded scope")
        configuration_set = scope.configuration_set
        if self.configuration_set_hash != configuration_set.configuration_set_hash:
            raise ValueError("request configuration-set hash does not match embedded scope")
        if self.configuration_hashes != configuration_set.configuration_hashes:
            raise ValueError("request configuration hashes do not match embedded commands")
        if len(self.configuration_hashes) != len(configuration_set.configurations):
            raise ValueError("request configuration hash count does not match commands")
        derivations = tuple(sorted(self.placement_derivations, key=lambda item: item.derivation_id))
        if derivations != self.placement_derivations:
            object.__setattr__(self, "placement_derivations", derivations)
        if derivations:
            expected_derivations_hash = placement_derivations_hash(derivations)
            if self.placement_derivations_hash != expected_derivations_hash:
                raise ValueError("request placement derivation hash does not match derivations")
        elif self.placement_derivations_hash is not None:
            raise ValueError("request placement derivation hash requires derivations")
        expected = _hash_model(self, "request_hash")
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("candidate multi-joint M10 request hash mismatch")
        return self


def candidate_multi_joint_m10_request_hash(
    request: CandidateMultiJointM10EvaluationRequest,
) -> str:
    return _hash_model(request, "request_hash")


class CandidateMultiJointM10Evaluation(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-multi-joint-m10-evaluation@1"] = (
        "candidate-multi-joint-m10-evaluation@1"
    )
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str
    source_binding_hash: str
    candidate_hash: str
    candidate_request_hash: str
    m10_v2_request_hash: str
    m10_v2_result_hash: str
    physical_to_m10_bridge_hash: str
    m10_model_hash: str
    physical_pair_classification_set_hash: str
    inventory_hash: str
    exact_pair_scope_hash: str
    scope_hash: str
    configuration_set_hash: str
    evaluation_hash: str = "pending"

    _validate_project_id = field_validator("project_id")(_require_nonblank)
    _validate_hashes = field_validator(
        "source_state_hash",
        "source_binding_hash",
        "candidate_hash",
        "candidate_request_hash",
        "m10_v2_request_hash",
        "m10_v2_result_hash",
        "physical_to_m10_bridge_hash",
        "m10_model_hash",
        "physical_pair_classification_set_hash",
        "inventory_hash",
        "exact_pair_scope_hash",
        "scope_hash",
        "configuration_set_hash",
    )(_require_hash)
    _validate_evaluation_hash = field_validator("evaluation_hash")(
        _require_hash_or_pending
    )

    @model_validator(mode="after")
    def validate_evaluation(self) -> "CandidateMultiJointM10Evaluation":
        expected = candidate_multi_joint_m10_evaluation_hash(self)
        if self.evaluation_hash == "pending":
            object.__setattr__(self, "evaluation_hash", expected)
        elif self.evaluation_hash != expected:
            raise ValueError("candidate multi-joint M10 evaluation hash mismatch")
        return self


def candidate_multi_joint_m10_evaluation_hash(
    evaluation: CandidateMultiJointM10Evaluation,
) -> str:
    return _hash_model(evaluation, "evaluation_hash")


class CandidateMultiJointM10EvaluationService:
    """Build candidate M10-3 authority without accepting a caller M10 request."""

    def __init__(
        self,
        state_manager=None,
        *,
        currentness_verifier=None,
        analyze_multi_joint_collision_sweep_v2=None,
    ):
        if (
            analyze_multi_joint_collision_sweep_v2 is None
            and currentness_verifier is not None
            and callable(state_manager)
        ):
            analyze_multi_joint_collision_sweep_v2 = state_manager
            state_manager = None
        self.analyze_multi_joint_collision_sweep_v2 = (
            analyze_multi_joint_collision_sweep_v2
        )
        if state_manager is None and currentness_verifier is None:
            raise ValueError(
                "candidate multi-joint M10 request requires a currentness verifier or state manager"
            )
        if state_manager is not None and currentness_verifier is not None:
            raise ValueError(
                "candidate multi-joint M10 request accepts either a currentness verifier or state manager"
            )
        self.currentness_verifier = currentness_verifier or CandidateCurrentnessService(state_manager)

    def build_request(
        self,
        candidate: MechanicalDesignCandidate,
        cad_realization: CandidateCadRealization,
        bridge: PhysicalToM10V2Bridge,
        scope: CandidateMultiJointM10EvaluationScope,
        *,
        placement_derivations=(),
        cad_request=None,
        source_assembly: CadAssemblyProgram | None = None,
    ) -> CandidateMultiJointM10EvaluationRequest:
        candidate = _revalidate(candidate, MechanicalDesignCandidate, "candidate")
        cad_realization = _revalidate(
            cad_realization, CandidateCadRealization, "candidate CAD realization"
        )
        bridge = _revalidate(bridge, PhysicalToM10V2Bridge, "physical-to-M10 bridge")
        scope = _revalidate(
            scope, CandidateMultiJointM10EvaluationScope, "candidate M10 scope"
        )
        if cad_request is not None:
            placement_derivations = getattr(cad_request, "placement_derivations", ())
        placement_derivations = tuple(
            sorted(placement_derivations, key=lambda item: item.derivation_id)
        )
        derivations_hash = (
            None if not placement_derivations else placement_derivations_hash(placement_derivations)
        )
        if cad_realization.placement_derivations_hash != derivations_hash:
            raise ValueError("candidate CAD realization placement derivation binding mismatch")
        generated_instance_ids = {
            mapping.physical_instance_id
            for mapping in cad_realization.mappings
            if mapping.fidelity is CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY
        }
        if {
            item.target_physical_instance_id for item in placement_derivations
        } != generated_instance_ids:
            raise ValueError("placement derivation targets do not match generated CAD mappings")
        currentness = self.currentness_verifier.evaluate_source_binding(candidate)
        if currentness is not CandidateCurrentness.CURRENT:
            raise ValueError(f"candidate is not current: {currentness.value}")
        if cad_realization.candidate_hash != candidate.candidate_hash:
            raise ValueError("candidate CAD realization does not bind the candidate")
        if source_assembly is not None:
            source_assembly = _revalidate(source_assembly, CadAssemblyProgram, "source assembly")
            if source_assembly != cad_realization.assembly:
                raise ValueError("source assembly does not match trusted candidate CAD realization")

        validate_physical_to_m10_v2_bridge(
            bridge,
            physical_mechanism_hash=candidate.realization.realization_hash,
            root_physical_body_id=candidate.realization.kinematic_root_physical_body_id,
            model=bridge.model,
            bodies=candidate.realization.physical_rigid_body_bindings,
            joints=candidate.realization.physical_revolute_joint_bindings,
            components=candidate.realization.components,
            connections=candidate.realization.connections,
            mappings=cad_realization.mappings,
            assembly=cad_realization.assembly,
            cad_realization_hash=cad_realization.realization_hash,
            pair_bindings=candidate.realization.physical_pair_classification_bindings,
        )
        configurations = validate_multi_joint_verification_configurations(
            scope.configuration_set.configurations, bridge
        )
        if configurations != scope.configuration_set.configurations:
            raise ValueError("scope configurations failed trusted bridge validation")

        m10_request = self._reconstruct_m10_request(bridge, cad_realization, scope)
        return CandidateMultiJointM10EvaluationRequest(
            project_id=candidate.source_binding.project_id,
            source_revision=candidate.source_binding.source_revision,
            source_state_hash=candidate.source_binding.source_state_hash,
            source_binding_hash=_digest(candidate.source_binding.model_dump(mode="json")),
            candidate_hash=candidate.candidate_hash,
            physical_mechanism_hash=bridge.physical_mechanism_hash,
            physical_body_binding_hashes=tuple(sorted(bridge.physical_body_binding_hashes)),
            physical_joint_binding_hashes=tuple(sorted(bridge.physical_joint_binding_hashes)),
            kinematic_root_binding_hash=bridge.kinematic_root_binding_hash,
            physical_pair_classification_set_hash=bridge.physical_pair_classification_set_hash,
            physical_to_m10_bridge_hash=bridge.physical_to_m10_bridge_hash,
            cad_realization_hash=cad_realization.realization_hash,
            cad_mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in cad_realization.mappings)),
            placement_derivations=placement_derivations,
            placement_derivations_hash=derivations_hash,
            m10_model_hash=bridge.m10_model_hash,
            inventory_hash=bridge.inventory_hash,
            exact_pair_scope_hash=bridge.exact_pair_scope_hash,
            scope=scope,
            scope_hash=scope.scope_hash,
            configuration_set_hash=scope.configuration_set.configuration_set_hash,
            configuration_hashes=tuple(joint_configuration_hash(item) for item in configurations),
            m10_v2_request_hash=m10_request.request_hash,
        )

    @staticmethod
    def _reconstruct_m10_request(
        bridge: PhysicalToM10V2Bridge,
        cad_realization: CandidateCadRealization,
        scope: CandidateMultiJointM10EvaluationScope,
    ) -> MultiJointCollisionSweepRequestV2:
        return MultiJointCollisionSweepRequestV2(
            schema_version="multi-joint-collision-sweep-request@2",
            source_assembly_id=cad_realization.assembly.assembly_id,
            source_assembly_hash=assembly_hash(cad_realization.assembly),
            model=revalidate_v2_kinematic_model(bridge.model),
            configurations=scope.configuration_set.configurations,
            exact_pair_scope=canonical_exact_pair_scope(bridge.exact_pair_scope),
            volume_tolerance_mm3=scope.volume_tolerance_mm3,
            distance_tolerance_mm=scope.distance_tolerance_mm,
            evaluator_version=MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
        )

    def reconstruct_m10_request(
        self,
        candidate: MechanicalDesignCandidate,
        cad_realization: CandidateCadRealization,
        bridge: PhysicalToM10V2Bridge,
        request: CandidateMultiJointM10EvaluationRequest,
        *,
        placement_derivations=(),
        cad_request=None,
    ) -> MultiJointCollisionSweepRequestV2:
        request = _revalidate(request, CandidateMultiJointM10EvaluationRequest, "candidate M10 request")
        expected = self.build_request(
            candidate,
            cad_realization,
            bridge,
            request.scope,
            placement_derivations=(
                request.placement_derivations
                if not placement_derivations and cad_request is None
                else placement_derivations
            ),
            cad_request=cad_request,
        )
        if expected != request:
            raise ValueError("candidate M10 request does not match trusted source inputs")
        reconstructed = self._reconstruct_m10_request(bridge, cad_realization, request.scope)
        if reconstructed.request_hash != request.m10_v2_request_hash:
            raise ValueError("stored M10 v2 request hash does not match reconstruction")
        return reconstructed

    def execute(
        self,
        candidate: MechanicalDesignCandidate,
        cad_realization: CandidateCadRealization,
        bridge: PhysicalToM10V2Bridge,
        request: CandidateMultiJointM10EvaluationRequest,
        *,
        evaluation_configuration_set_hash: str | None = None,
    ) -> CandidateMultiJointM10Evaluation:
        if self.analyze_multi_joint_collision_sweep_v2 is None:
            raise ValueError("candidate multi-joint M10 execution requires a v2 production method")

        candidate = _revalidate(candidate, MechanicalDesignCandidate, "candidate")
        cad_realization = _revalidate(
            cad_realization, CandidateCadRealization, "candidate CAD realization"
        )
        bridge = _revalidate(bridge, PhysicalToM10V2Bridge, "physical-to-M10 bridge")
        request = _revalidate(
            request,
            CandidateMultiJointM10EvaluationRequest,
            "candidate multi-joint M10 request",
        )
        scope = _revalidate(
            request.scope,
            CandidateMultiJointM10EvaluationScope,
            "candidate multi-joint M10 scope",
        )
        configuration_set = _revalidate(
            scope.configuration_set,
            MultiJointVerificationConfigurationSet,
            "candidate multi-joint M10 configuration set",
        )
        if request.scope != scope or scope.configuration_set != configuration_set:
            raise ValueError("candidate multi-joint M10 scope reconstruction mismatch")
        authoritative_configuration_set_hash = configuration_set.configuration_set_hash
        if request.configuration_set_hash != authoritative_configuration_set_hash:
            raise ValueError("candidate M10 request configuration-set binding mismatch")
        if request.configuration_hashes != configuration_set.configuration_hashes:
            raise ValueError("candidate M10 request configuration identities mismatch")
        if evaluation_configuration_set_hash is not None:
            _require_hash(evaluation_configuration_set_hash)
            if evaluation_configuration_set_hash != authoritative_configuration_set_hash:
                raise ValueError("candidate M10 evaluation configuration-set binding mismatch")
        m10_request = self.reconstruct_m10_request(
            candidate, cad_realization, bridge, request
        )
        if m10_request.request_hash != request.m10_v2_request_hash:
            raise ValueError("candidate M10 request hash does not match reconstruction")

        raw_result = self.analyze_multi_joint_collision_sweep_v2(
            source_revision=request.source_revision,
            source_state_hash=request.source_state_hash,
            assembly=cad_realization.assembly,
            model=m10_request.model,
            configurations=m10_request.configurations,
            exact_pair_scope=m10_request.exact_pair_scope,
            volume_tolerance_mm3=m10_request.volume_tolerance_mm3,
            distance_tolerance_mm=m10_request.distance_tolerance_mm,
        )
        result = _revalidate(
            raw_result, MultiJointCollisionSweepResultV2, "M10 v2 result"
        )
        if result.request_hash != m10_request.request_hash:
            raise ValueError("M10 v2 result is bound to a different request")
        if result.source_assembly_hash != m10_request.source_assembly_hash:
            raise ValueError("M10 v2 result source assembly binding mismatch")
        if result.model_hash != m10_request.model_hash:
            raise ValueError("M10 v2 result model binding mismatch")
        if result.evaluator_version != m10_request.evaluator_version:
            raise ValueError("M10 v2 result evaluator binding mismatch")
        if result.result_hash != multi_joint_collision_sweep_result_v2_hash(result):
            raise ValueError("M10 v2 result hash mismatch")

        evaluation = CandidateMultiJointM10Evaluation(
            project_id=request.project_id,
            source_revision=request.source_revision,
            source_state_hash=request.source_state_hash,
            source_binding_hash=request.source_binding_hash,
            candidate_hash=request.candidate_hash,
            candidate_request_hash=request.request_hash,
            m10_v2_request_hash=m10_request.request_hash,
            m10_v2_result_hash=result.result_hash,
            physical_to_m10_bridge_hash=request.physical_to_m10_bridge_hash,
            m10_model_hash=request.m10_model_hash,
            physical_pair_classification_set_hash=request.physical_pair_classification_set_hash,
            inventory_hash=request.inventory_hash,
            exact_pair_scope_hash=request.exact_pair_scope_hash,
            scope_hash=request.scope_hash,
            configuration_set_hash=authoritative_configuration_set_hash,
        )
        if authoritative_configuration_set_hash != evaluation.configuration_set_hash:
            raise ValueError("candidate M10 evaluation configuration-set binding mismatch")
        return evaluation


__all__ = [
    "CandidateMultiJointM10Evaluation",
    "CandidateMultiJointM10EvaluationRequest",
    "CandidateMultiJointM10EvaluationScope",
    "CandidateMultiJointM10EvaluationService",
    "candidate_multi_joint_m10_evaluation_hash",
    "candidate_multi_joint_m10_request_hash",
    "candidate_multi_joint_m10_scope_hash",
    "validate_multi_joint_verification_configurations",
]
