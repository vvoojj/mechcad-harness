from __future__ import annotations

import hashlib
import itertools
import math
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.cad_assembly import (
    M10_EXECUTION_SEMANTICS_VERSION,
    CadAssemblyProgram,
    _require_semantic_fields,
    assembly_hash,
    verified_semantic_assembly_hash,
)
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.candidates.cad_realization import (
    CandidateCadRealization,
    CandidateCadRealizationV2,
    CandidateCadStageOutcome,
    CandidateCadStageOutcomeV2,
    CandidateCadStageStatus,
    CandidateGeometryFidelity,
)
from mechcad_harness.candidates.m10_result_validation import (
    ContinuousM10ResultValidationContract,
    HomeM10ResultValidationContract,
)
from mechcad_harness.candidates.models import (
    MechanicalConnectionKind,
    MechanicalDesignCandidate,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
    semantic_candidate_realization_payload,
)
from mechcad_harness.continuous_proof import (
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    semantic_proof_request_hash,
    semantic_proof_result_hash,
    _semantic_proof_request_hash_from_assembly_identity,
    _semantic_proof_result_hash_from_assembly_identity,
)
from mechcad_harness.kinematic_sweep import (
    RIGID_BODY_COLLISION_SWEEP_VERSION,
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CollisionClassification,
    RevoluteAxis,
    semantic_sweep_request_hash,
    semantic_sweep_result_hash,
    _semantic_sweep_request_hash_from_assembly_identity,
    _semantic_sweep_result_hash_from_assembly_identity,
)
from mechcad_harness.models.common import Model
from mechcad_harness.models.physical_pair_policy import PhysicalPairClassification
from mechcad_harness.multi_joint_kinematics import (
    KinematicModel,
    kinematic_model_hash,
    transform_apply,
)
from mechcad_harness.semantic_m10_kinematics import semantic_single_joint_kinematic_model_hash
from mechcad_harness.state.hashing import canonical_json


def _hash(value: object, identity_field: str | None = None) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, Model) else value
    payload = dict(payload)
    if identity_field is not None:
        payload.pop(identity_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _semantic_m10_hash(payload: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _legacy_continuous_result_hash(result: ContinuousSingleAxisProofResult) -> str:
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _legacy_sweep_result_hash(result: CadKinematicSweepResult) -> str:
    payload = result.model_dump(mode="json", exclude={"result_hash"})
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


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


def _optional_hash(value: str | None) -> str | None:
    return None if value is None else _require_hash(value)


def _nonblank(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _canonical_pair(pair: tuple[str, str]) -> tuple[str, str]:
    if len(pair) != 2:
        raise ValueError("collision pair must contain exactly two CAD instance IDs")
    first, second = pair
    if not first.strip() or not second.strip():
        raise ValueError("collision pair instance IDs must not be empty")
    if first == second:
        raise ValueError("collision pair must contain two distinct CAD instances")
    return tuple(sorted((first, second)))


class CandidateM10Model(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CandidateM10BodyDisposition(StrEnum):
    FIXED = "fixed"
    OUTPUT_RIGID = "output_rigid"
    INTERNAL_MOTION_UNMODELED = "internal_motion_unmodeled"


CandidateM10PairClassification = PhysicalPairClassification


class CandidateM10ConstituentDisposition(CandidateM10Model):
    """Candidate-specific disposition for one realized CAD constituent."""

    schema_version: str = "candidate-m10-constituent-disposition@1"
    physical_instance_id: str = Field(min_length=1)
    cad_instance_id: str = Field(min_length=1)
    constituent_key: str = Field(min_length=1)
    disposition: CandidateM10BodyDisposition
    output_transform_group: str | None = None
    disposition_hash: str = "pending"

    _validate_ids = field_validator(
        "physical_instance_id", "cad_instance_id", "constituent_key", "output_transform_group"
    )(_nonblank)
    _validate_hash = field_validator("disposition_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_disposition(self) -> "CandidateM10ConstituentDisposition":
        if self.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID:
            if self.output_transform_group is not None and not self.output_transform_group.strip():
                raise ValueError("output-rigid transform group must not be empty")
        elif self.output_transform_group is not None:
            raise ValueError("only output-rigid constituents may declare a transform group")
        expected = _hash(self, "disposition_hash")
        if self.disposition_hash == "pending":
            object.__setattr__(self, "disposition_hash", expected)
        elif self.disposition_hash != expected:
            raise ValueError("candidate M10 constituent disposition hash mismatch")
        return self


class CandidateM10ConstituentDispositionV2(CandidateM10Model):
    schema_version: Literal["candidate-m10-constituent-disposition@2"] = (
        "candidate-m10-constituent-disposition@2"
    )
    physical_instance_id: str = Field(min_length=1)
    cad_instance_id: str = Field(min_length=1)
    constituent_key: str = Field(min_length=1)
    disposition: CandidateM10BodyDisposition
    output_transform_group: str | None = None
    disposition_hash: str = "pending"

    _validate_ids = field_validator(
        "physical_instance_id", "cad_instance_id", "constituent_key",
        "output_transform_group",
    )(_nonblank)
    _validate_hash = field_validator("disposition_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_semantic_disposition(self):
        if self.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID:
            if self.output_transform_group is not None and not self.output_transform_group.strip():
                raise ValueError("output-rigid transform group must not be empty")
        elif self.output_transform_group is not None:
            raise ValueError("only output-rigid constituents may declare a transform group")
        expected = candidate_m10_constituent_disposition_hash_v2(self)
        if self.disposition_hash == "pending":
            object.__setattr__(self, "disposition_hash", expected)
        elif self.disposition_hash != expected:
            raise ValueError("candidate M10 constituent disposition@2 hash mismatch")
        return self


def candidate_m10_constituent_disposition_hash_v2(
    disposition: CandidateM10ConstituentDispositionV2,
) -> str:
    _require_semantic_fields(
        disposition,
        CandidateM10ConstituentDispositionV2,
        {
            "schema_version", "physical_instance_id", "cad_instance_id",
            "constituent_key", "disposition", "output_transform_group",
            "disposition_hash",
        },
        "CandidateM10ConstituentDispositionV2",
    )
    return _semantic_m10_hash(
        {
            "schema_version": disposition.schema_version,
            "physical_instance_id": disposition.physical_instance_id,
            "cad_instance_id": disposition.cad_instance_id,
            "constituent_key": disposition.constituent_key,
            "disposition": disposition.disposition.value,
            "output_transform_group": disposition.output_transform_group,
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        }
    )


class CandidateM10PairScopeRequirement(CandidateM10Model):
    """Candidate-independent semantic requirement for one constituent pair."""

    schema_version: str = "candidate-m10-pair-scope-requirement@1"
    requirement_key: str = Field(min_length=1)
    first_constituent_key: str = Field(min_length=1)
    second_constituent_key: str = Field(min_length=1)
    required_classification: CandidateM10PairClassification
    requires_home_exact_check: bool = False

    _validate_keys = field_validator(
        "requirement_key", "first_constituent_key", "second_constituent_key"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_pair(self) -> "CandidateM10PairScopeRequirement":
        if self.first_constituent_key == self.second_constituent_key:
            raise ValueError("pair scope requirement must contain two distinct constituents")
        return self

    @property
    def constituent_key_pair(self) -> tuple[str, str]:
        return tuple(sorted((self.first_constituent_key, self.second_constituent_key)))


class CandidateM10EvaluationScope(CandidateM10Model):
    """The comparable, candidate-independent part of an M10 evaluation."""

    schema_version: str = "candidate-m10-evaluation-scope@1"
    output_joint_semantic_key: str = Field(min_length=1)
    angle_interval_deg: tuple[float, float]
    required_clearance_mm: float = Field(ge=0)
    pair_scope_requirements: tuple[CandidateM10PairScopeRequirement, ...] = Field(min_length=1)
    fidelity_requirements: tuple[tuple[str, CandidateGeometryFidelity], ...] = ()
    required_home_check_semantics: tuple[str, ...] = ()
    proof_service_version: str = Field(min_length=1)
    policy_assumptions: tuple[str, ...] = ()
    scope_hash: str = "pending"

    _validate_joint_key = field_validator("output_joint_semantic_key", "proof_service_version")(_nonblank)
    _validate_hash = field_validator("scope_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_scope(self) -> "CandidateM10EvaluationScope":
        start, end = self.angle_interval_deg
        if not all(math.isfinite(value) for value in (start, end)) or start > end:
            raise ValueError("M10 angle interval must be finite and ordered")
        requirement_keys = [requirement.requirement_key for requirement in self.pair_scope_requirements]
        if len(set(requirement_keys)) != len(requirement_keys):
            raise ValueError("M10 pair scope requirement keys must be unique")
        fidelity_keys = [key for key, _ in self.fidelity_requirements]
        if any(not key.strip() for key in fidelity_keys) or len(set(fidelity_keys)) != len(fidelity_keys):
            raise ValueError("M10 fidelity requirement keys must be unique and non-empty")
        if any(not value.strip() for value in self.required_home_check_semantics + self.policy_assumptions):
            raise ValueError("M10 scope semantic assumptions must not be empty")
        if self.proof_service_version != "m10-single-axis-continuous-proof@1":
            raise ValueError("unsupported M10 continuous proof service version")
        expected = candidate_m10_scope_hash(self)
        if self.scope_hash == "pending":
            object.__setattr__(self, "scope_hash", expected)
        elif self.scope_hash != expected:
            raise ValueError("candidate M10 evaluation scope hash mismatch")
        return self


def candidate_m10_scope_hash(scope: CandidateM10EvaluationScope) -> str:
    return _hash(scope, "scope_hash")


class CandidateM10Binding(CandidateM10Model):
    """Candidate-specific mapping onto one existing M10 output joint."""

    schema_version: str = "candidate-m10-binding@1"
    candidate_hash: str
    cad_realization_hash: str
    model: KinematicModel
    model_hash: str = "pending"
    output_joint_id: str = Field(min_length=1)
    driver_gear_constituent_key: str | None = None
    output_axis: RevoluteAxis
    constituent_dispositions: tuple[CandidateM10ConstituentDisposition, ...] = Field(min_length=1)
    binding_hash: str = "pending"

    _validate_hashes = field_validator("candidate_hash", "cad_realization_hash")(_require_hash)
    _validate_derived_hashes = field_validator("model_hash", "binding_hash")(_require_hash_or_pending)
    _validate_ids = field_validator("output_joint_id", "driver_gear_constituent_key")(_nonblank)

    @model_validator(mode="after")
    def validate_binding(self) -> "CandidateM10Binding":
        expected_model_hash = kinematic_model_hash(self.model)
        if self.model_hash == "pending":
            object.__setattr__(self, "model_hash", expected_model_hash)
        elif self.model_hash != expected_model_hash:
            raise ValueError("candidate M10 model hash mismatch")

        joint = next((joint for joint in self.model.joints if joint.joint_id == self.output_joint_id), None)
        if joint is None:
            raise ValueError("candidate M10 output joint is missing from the model")
        if self.output_axis.frame_id != f"joint:{self.output_joint_id}":
            raise ValueError("candidate M10 output axis frame does not match output joint")

        physical_ids = [entry.physical_instance_id for entry in self.constituent_dispositions]
        cad_ids = [entry.cad_instance_id for entry in self.constituent_dispositions]
        keys = [entry.constituent_key for entry in self.constituent_dispositions]
        if len(set(physical_ids)) != len(physical_ids):
            raise ValueError("candidate M10 physical constituent IDs must be unique")
        if len(set(cad_ids)) != len(cad_ids):
            raise ValueError("candidate M10 CAD constituent IDs must be unique")
        if len(set(keys)) != len(keys):
            raise ValueError("candidate M10 constituent keys must be unique")
        if self.driver_gear_constituent_key is not None:
            driver_gear = next(
                (
                    entry
                    for entry in self.constituent_dispositions
                    if entry.constituent_key == self.driver_gear_constituent_key
                ),
                None,
            )
            if driver_gear is None:
                raise ValueError("candidate M10 driver gear constituent is missing")
            if driver_gear.disposition is CandidateM10BodyDisposition.FIXED:
                raise ValueError("driver gear cannot be fixed in the candidate M10 binding")
            if driver_gear.disposition is not CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED:
                raise ValueError("driver gear must be internal motion unmodeled in the candidate M10 binding")
        for entry in self.constituent_dispositions:
            if entry.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID:
                if entry.output_transform_group not in (None, self.output_joint_id):
                    raise ValueError("output-rigid constituent has a different output transform")
            elif entry.output_transform_group is not None:
                raise ValueError("fixed or unmodeled constituent cannot share an output transform")

        child_cad_id = joint.child_instance_id
        child = next((entry for entry in self.constituent_dispositions if entry.cad_instance_id == child_cad_id), None)
        if child is None or child.disposition is not CandidateM10BodyDisposition.OUTPUT_RIGID:
            raise ValueError("output joint child must be output-rigid")

        expected = _hash(self, "binding_hash")
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected)
        elif self.binding_hash != expected:
            raise ValueError("candidate M10 binding hash mismatch")
        return self

    def validate_against(
        self,
        realization: CandidateCadRealization,
        physical_realization: PhysicalMechanismRealization | None = None,
    ) -> None:
        realization = CandidateCadRealization.model_validate(realization.model_dump(mode="json"))
        if self.candidate_hash != realization.candidate_hash:
            raise ValueError("candidate M10 binding candidate hash mismatch")
        if self.cad_realization_hash != realization.realization_hash:
            raise ValueError("candidate M10 binding realization hash mismatch")
        joint = next(joint for joint in self.model.joints if joint.joint_id == self.output_joint_id)
        parent = next(
            (
                instance
                for instance in realization.assembly.instances
                if instance.instance_id == joint.parent_instance_id
            ),
            None,
        )
        if parent is None:
            raise ValueError("candidate M10 joint parent is missing from the exact CAD realization")
        if not _axis_matches_transformed_joint(self.output_axis, joint, parent.placement):
            raise ValueError("candidate M10 world output axis does not match the parent-local joint axis")
        if physical_realization is not None:
            self.validate_physical_realization(physical_realization)
        CandidateM10Binding.model_validate(self.model_dump(mode="json"))

    def validate_physical_realization(
        self, physical_realization: PhysicalMechanismRealization
    ) -> None:
        physical_realization = PhysicalMechanismRealization.model_validate(
            physical_realization.model_dump(mode="json")
        )
        _validate_single_joint_driver_topology(
            self.constituent_dispositions,
            self.driver_gear_constituent_key,
            physical_realization,
        )

    @property
    def cad_instance_ids(self) -> tuple[str, ...]:
        return tuple(sorted(entry.cad_instance_id for entry in self.constituent_dispositions))

    @property
    def output_rigid_cad_instance_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                entry.cad_instance_id
                for entry in self.constituent_dispositions
                if entry.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID
            )
        )

    def disposition_for(self, cad_instance_id: str) -> CandidateM10ConstituentDisposition:
        try:
            return next(
                entry for entry in self.constituent_dispositions if entry.cad_instance_id == cad_instance_id
            )
        except StopIteration:
            raise ValueError(f"candidate M10 CAD constituent is missing: {cad_instance_id}") from None


def _validate_single_joint_driver_topology(
    constituent_dispositions: tuple[CandidateM10ConstituentDisposition, ...]
    | tuple[CandidateM10ConstituentDispositionV2, ...],
    driver_gear_constituent_key: str | None,
    physical_realization: PhysicalMechanismRealization,
) -> None:
    """Check external-spur driver topology shared by legacy and @2 single-joint bindings."""
    dispositions = {
        entry.physical_instance_id: entry for entry in constituent_dispositions
    }
    components = {
        component.instance_id: component for component in physical_realization.components
    }
    gear_drivers = []
    for connection in physical_realization.connections:
        if connection.kind is not MechanicalConnectionKind.GEAR_MESH:
            continue
        driver = components.get(connection.from_instance_id)
        disposition = dispositions.get(connection.from_instance_id)
        if driver is None or disposition is None:
            raise ValueError("external-spur driver is missing from the candidate M10 binding")
        if driver.role is not PhysicalComponentRole.TRANSMISSION:
            raise ValueError("external-spur gear driver must have transmission role")
        if disposition.disposition is not CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED:
            raise ValueError("external-spur driver motion cannot be fixed or output-rigid")
        gear_drivers.append(disposition.constituent_key)
    if gear_drivers:
        if driver_gear_constituent_key is None:
            raise ValueError("external-spur driver gear marker is required")
        if any(key != driver_gear_constituent_key for key in gear_drivers):
            raise ValueError("candidate M10 driver gear marker does not match candidate topology")


def _axis_matches_transformed_joint(axis: RevoluteAxis, joint, parent_placement) -> bool:
    local_origin = joint.axis_origin
    local_direction = joint.axis_direction
    world_origin = transform_apply(parent_placement, local_origin)
    world_direction_point = transform_apply(
        parent_placement,
        tuple(origin + direction for origin, direction in zip(local_origin, local_direction)),
    )
    world_direction = tuple(
        point - origin for point, origin in zip(world_direction_point, world_origin)
    )
    return all(
        math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9)
        for actual, expected in zip(
            (axis.origin_x_mm, axis.origin_y_mm, axis.origin_z_mm, *axis.direction),
            (*world_origin, *world_direction),
        )
    )


class CandidateM10BindingV2(CandidateM10Model):
    schema_version: Literal["candidate-m10-binding@2"] = "candidate-m10-binding@2"
    candidate_hash: str
    cad_realization_hash: str
    model: KinematicModel
    semantic_single_joint_kinematic_model_hash: str
    output_joint_id: str = Field(min_length=1)
    driver_gear_constituent_key: str | None = None
    output_axis: RevoluteAxis
    constituent_dispositions: tuple[CandidateM10ConstituentDispositionV2, ...] = Field(min_length=1)
    binding_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash", "cad_realization_hash",
        "semantic_single_joint_kinematic_model_hash",
    )(_require_hash)
    _validate_binding_hash = field_validator("binding_hash")(_require_hash_or_pending)
    _validate_ids = field_validator("output_joint_id", "driver_gear_constituent_key")(_nonblank)

    @model_validator(mode="after")
    def validate_binding_v2(self):
        model = KinematicModel.model_validate(self.model.model_dump(mode="json"))
        expected_model_hash = semantic_single_joint_kinematic_model_hash(model)
        if self.semantic_single_joint_kinematic_model_hash != expected_model_hash:
            raise ValueError("candidate M10 semantic single-joint model hash mismatch")
        object.__setattr__(self, "model", model)
        joint = next(
            (joint for joint in model.joints if joint.joint_id == self.output_joint_id),
            None,
        )
        if joint is None:
            raise ValueError("candidate M10 output joint is missing from the model")
        if self.output_axis.frame_id != f"joint:{self.output_joint_id}":
            raise ValueError("candidate M10 output axis frame does not match output joint")

        dispositions = tuple(
            CandidateM10ConstituentDispositionV2.model_validate(
                item.model_dump(mode="json")
            )
            for item in self.constituent_dispositions
        )
        by_key = {}
        for item in dispositions:
            key = (item.physical_instance_id, item.cad_instance_id, item.constituent_key)
            if key in by_key:
                raise ValueError("candidate M10 constituent disposition identities must be unique")
            by_key[key] = item
        dispositions = tuple(by_key[key] for key in sorted(by_key))
        object.__setattr__(self, "constituent_dispositions", dispositions)
        if len({item.physical_instance_id for item in dispositions}) != len(dispositions):
            raise ValueError("candidate M10 physical constituent IDs must be unique")
        if len({item.cad_instance_id for item in dispositions}) != len(dispositions):
            raise ValueError("candidate M10 CAD constituent IDs must be unique")
        if len({item.constituent_key for item in dispositions}) != len(dispositions):
            raise ValueError("candidate M10 constituent keys must be unique")
        if self.driver_gear_constituent_key is not None:
            driver = next(
                (item for item in dispositions if item.constituent_key == self.driver_gear_constituent_key),
                None,
            )
            if driver is None or driver.disposition is not CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED:
                raise ValueError("candidate M10 driver gear must be internal motion unmodeled")
        for item in dispositions:
            if item.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID:
                if item.output_transform_group not in (None, self.output_joint_id):
                    raise ValueError("output-rigid constituent has a different output transform")
            elif item.output_transform_group is not None:
                raise ValueError("fixed or unmodeled constituent cannot share an output transform")
        child = next(
            (item for item in dispositions if item.cad_instance_id == joint.child_instance_id),
            None,
        )
        if child is None or child.disposition is not CandidateM10BodyDisposition.OUTPUT_RIGID:
            raise ValueError("output joint child must be output-rigid")

        expected = candidate_m10_binding_hash_v2(self)
        if self.binding_hash == "pending":
            object.__setattr__(self, "binding_hash", expected)
        elif self.binding_hash != expected:
            raise ValueError("candidate M10 binding@2 hash mismatch")
        return self

    def validate_against(
        self,
        realization: CandidateCadRealizationV2,
        physical_realization: PhysicalMechanismRealization | None = None,
    ) -> None:
        realization = CandidateCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
        )
        if self.candidate_hash != realization.candidate_hash:
            raise ValueError("candidate M10 binding candidate@2 hash mismatch")
        if self.cad_realization_hash != realization.realization_hash:
            raise ValueError("candidate M10 binding CAD realization@2 hash mismatch")
        if semantic_single_joint_kinematic_model_hash(self.model) != self.semantic_single_joint_kinematic_model_hash:
            raise ValueError("candidate M10 binding semantic model identity mismatch")
        mappings = {item.physical_instance_id: item for item in realization.mappings}
        dispositions = {item.physical_instance_id: item for item in self.constituent_dispositions}
        if set(mappings) != set(dispositions):
            raise ValueError("candidate M10 binding must cover the complete CAD realization")
        if any(
            mappings[physical_id].cad_instance_id != item.cad_instance_id
            for physical_id, item in dispositions.items()
        ):
            raise ValueError("candidate M10 physical-to-CAD mapping mismatch")
        joint = next(item for item in self.model.joints if item.joint_id == self.output_joint_id)
        parent = next(
            (item for item in realization.assembly.instances if item.instance_id == joint.parent_instance_id),
            None,
        )
        if parent is None or not _axis_matches_transformed_joint(self.output_axis, joint, parent.placement):
            raise ValueError("candidate M10 world output axis does not match the semantic joint")
        if physical_realization is not None:
            self.validate_physical_realization(physical_realization)

    def validate_physical_realization(
        self, physical_realization: PhysicalMechanismRealization
    ) -> None:
        """Admit a validated realization@1/@2 on the single-joint candidate M10@2 path.

        Case 92 requires candidate@2 / PhysicalMechanismRealization@1 lineage
        through single-joint candidate M10@2. The @2 semantic binding only needs
        common realization semantics via the shared schema-dispatched
        projection; the realization@2-only bridge / multi-joint mechanism path
        (semantic_candidate_mechanism_hash) is untouched.
        """
        validated = PhysicalMechanismRealization.model_validate(
            physical_realization.model_dump(mode="json")
        )
        if validated.schema_version not in (
            "physical-mechanism-realization@1",
            "physical-mechanism-realization@2",
        ):
            raise ValueError(
                "candidate M10 @2 requires physical-mechanism-realization@1 or @2"
            )
        semantic_candidate_realization_payload(validated)
        _validate_single_joint_driver_topology(
            self.constituent_dispositions,
            self.driver_gear_constituent_key,
            validated,
        )

    @property
    def cad_instance_ids(self) -> tuple[str, ...]:
        return tuple(sorted(item.cad_instance_id for item in self.constituent_dispositions))

    @property
    def output_rigid_cad_instance_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.cad_instance_id
                for item in self.constituent_dispositions
                if item.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID
            )
        )


def candidate_m10_binding_hash_v2(binding: CandidateM10BindingV2) -> str:
    _require_semantic_fields(
        binding,
        CandidateM10BindingV2,
        {
            "schema_version", "candidate_hash", "cad_realization_hash", "model",
            "semantic_single_joint_kinematic_model_hash", "output_joint_id",
            "driver_gear_constituent_key", "output_axis", "constituent_dispositions",
            "binding_hash",
        },
        "CandidateM10BindingV2",
    )
    dispositions = tuple(
        sorted(
            (
                CandidateM10ConstituentDispositionV2.model_validate(item.model_dump(mode="json"))
                for item in binding.constituent_dispositions
            ),
            key=lambda item: (
                item.physical_instance_id, item.cad_instance_id, item.constituent_key
            ),
        )
    )
    return _semantic_m10_hash(
        {
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
            "schema_version": binding.schema_version,
            "candidate_hash": binding.candidate_hash,
            "cad_realization_hash": binding.cad_realization_hash,
            "semantic_single_joint_kinematic_model_hash": binding.semantic_single_joint_kinematic_model_hash,
            "output_joint_id": binding.output_joint_id,
            "driver_gear_constituent_key": binding.driver_gear_constituent_key,
            "output_axis": binding.output_axis.model_dump(mode="json"),
            "constituent_disposition_hashes": [
                candidate_m10_constituent_disposition_hash_v2(item)
                for item in dispositions
            ],
        }
    )


class CandidateCollisionPairClassification(CandidateM10Model):
    schema_version: str = "candidate-m10-collision-pair-classification@1"
    pair: tuple[str, str]
    classification: CandidateM10PairClassification
    reason: str | None = None
    requires_home_exact_check: bool = False
    classification_hash: str = "pending"

    _validate_hash = field_validator("classification_hash")(_require_hash_or_pending)
    _validate_reason = field_validator("reason")(_nonblank)

    @model_validator(mode="after")
    def validate_classification(self) -> "CandidateCollisionPairClassification":
        canonical_pair = _canonical_pair(self.pair)
        if canonical_pair != self.pair:
            object.__setattr__(self, "pair", canonical_pair)
        if self.classification is CandidateM10PairClassification.CHECK_CLEARANCE:
            if self.reason is not None:
                raise ValueError("checked collision pairs cannot carry an exclusion reason")
            if self.requires_home_exact_check:
                raise ValueError("checked collision pairs cannot require a home-only check")
        elif self.reason is None:
            raise ValueError("excluded collision pairs require an explicit reason")
        if self.requires_home_exact_check and self.classification is not CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE:
            raise ValueError("home exact checks are only valid for unmodeled motion pairs")
        expected = _hash(self, "classification_hash")
        if self.classification_hash == "pending":
            object.__setattr__(self, "classification_hash", expected)
        elif self.classification_hash != expected:
            raise ValueError("candidate M10 collision pair classification hash mismatch")
        return self


class CandidateCollisionPairClassificationV2(CandidateM10Model):
    schema_version: Literal["candidate-m10-collision-pair-classification@2"] = (
        "candidate-m10-collision-pair-classification@2"
    )
    pair: tuple[str, str]
    classification: CandidateM10PairClassification
    reason: str | None = None
    requires_home_exact_check: bool = False
    classification_hash: str = "pending"

    _validate_hash = field_validator("classification_hash")(_require_hash_or_pending)
    _validate_reason = field_validator("reason")(_nonblank)

    @model_validator(mode="after")
    def validate_semantic_classification(self):
        canonical_pair = _canonical_pair(self.pair)
        if canonical_pair != self.pair:
            object.__setattr__(self, "pair", canonical_pair)
        if self.classification is CandidateM10PairClassification.CHECK_CLEARANCE:
            if self.reason is not None:
                raise ValueError("checked collision pairs cannot carry an exclusion reason")
            if self.requires_home_exact_check:
                raise ValueError("checked collision pairs cannot require a home-only check")
        elif self.reason is None:
            raise ValueError("excluded collision pairs require an explicit reason")
        if self.requires_home_exact_check and self.classification is not CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE:
            raise ValueError("home exact checks are only valid for unmodeled motion pairs")
        expected = candidate_m10_collision_pair_classification_hash_v2(self)
        if self.classification_hash == "pending":
            object.__setattr__(self, "classification_hash", expected)
        elif self.classification_hash != expected:
            raise ValueError("candidate M10 collision pair classification@2 hash mismatch")
        return self


def candidate_m10_collision_pair_classification_hash_v2(
    classification: CandidateCollisionPairClassificationV2,
) -> str:
    _require_semantic_fields(
        classification,
        CandidateCollisionPairClassificationV2,
        {
            "schema_version", "pair", "classification", "reason",
            "requires_home_exact_check", "classification_hash",
        },
        "CandidateCollisionPairClassificationV2",
    )
    return _semantic_m10_hash(
        {
            "schema_version": classification.schema_version,
            "pair": list(classification.pair),
            "classification": classification.classification.value,
            "reason": classification.reason,
            "requires_home_exact_check": classification.requires_home_exact_check,
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        }
    )


class CandidateCollisionPairInventory(CandidateM10Model):
    schema_version: str = "candidate-m10-collision-pair-inventory@1"
    cad_realization_hash: str
    binding_hash: str
    scope_hash: str
    expected_pair_universe: tuple[tuple[str, str], ...] = Field(min_length=1)
    classifications: tuple[CandidateCollisionPairClassification, ...] = Field(min_length=1)
    checked_pairs: tuple[tuple[str, str], ...] = ()
    excluded_pairs: tuple[tuple[str, str], ...] = ()
    inventory_hash: str = "pending"

    _validate_hashes = field_validator(
        "cad_realization_hash", "binding_hash", "scope_hash"
    )(_require_hash)
    _validate_inventory_hash = field_validator("inventory_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_inventory(self) -> "CandidateCollisionPairInventory":
        expected = tuple(sorted(_canonical_pair(pair) for pair in self.expected_pair_universe))
        if expected != self.expected_pair_universe:
            object.__setattr__(self, "expected_pair_universe", expected)
        pairs = tuple(item.pair for item in self.classifications)
        if len(set(pairs)) != len(pairs):
            raise ValueError("collision pair classifications must be unique")
        if tuple(sorted(pairs)) != self.expected_pair_universe:
            raise ValueError("collision pair inventory is incomplete or contains unsupported pairs")
        checked = tuple(sorted(item.pair for item in self.classifications if item.classification is CandidateM10PairClassification.CHECK_CLEARANCE))
        excluded = tuple(sorted(item.pair for item in self.classifications if item.classification is not CandidateM10PairClassification.CHECK_CLEARANCE))
        if "checked_pairs" in self.model_fields_set and self.checked_pairs != checked:
            raise ValueError("checked collision pair inventory mismatch")
        if "excluded_pairs" in self.model_fields_set and self.excluded_pairs != excluded:
            raise ValueError("excluded collision pair inventory mismatch")
        if "checked_pairs" not in self.model_fields_set:
            object.__setattr__(self, "checked_pairs", checked)
        if "excluded_pairs" not in self.model_fields_set:
            object.__setattr__(self, "excluded_pairs", excluded)
        expected_hash = _hash(self, "inventory_hash")
        if self.inventory_hash == "pending":
            object.__setattr__(self, "inventory_hash", expected_hash)
        elif self.inventory_hash != expected_hash:
            raise ValueError("candidate M10 collision pair inventory hash mismatch")
        return self

    @classmethod
    def complete_for(
        cls,
        realization: CandidateCadRealization,
        binding: CandidateM10Binding,
        scope: CandidateM10EvaluationScope,
        classifications: tuple[CandidateCollisionPairClassification, ...] = (),
    ) -> "CandidateCollisionPairInventory":
        realization = CandidateCadRealization.model_validate(realization.model_dump(mode="json"))
        binding.validate_against(realization)
        mapping_by_cad = {mapping.cad_instance_id: mapping for mapping in realization.mappings}
        if set(mapping_by_cad) != set(binding.cad_instance_ids):
            raise ValueError("candidate M10 binding must cover every CAD realization constituent")
        mapping_by_physical = {
            mapping.physical_instance_id: mapping for mapping in realization.mappings
        }
        for entry in binding.constituent_dispositions:
            mapping = mapping_by_physical.get(entry.physical_instance_id)
            if mapping is None or mapping.cad_instance_id != entry.cad_instance_id:
                raise ValueError("candidate M10 physical-to-CAD mapping does not match realization")
        if any(mapping.candidate_hash != realization.candidate_hash for mapping in realization.mappings):
            raise ValueError("candidate CAD mapping identity mismatch")
        expected_pairs = tuple(itertools.combinations(sorted(mapping_by_cad), 2))
        entry_by_cad = {entry.cad_instance_id: entry for entry in binding.constituent_dispositions}
        binding_keys = {entry.constituent_key for entry in binding.constituent_dispositions}
        for requirement in scope.pair_scope_requirements:
            missing_keys = set((requirement.first_constituent_key, requirement.second_constituent_key)) - binding_keys
            if missing_keys:
                raise ValueError(
                    f"M10 scope requirement has no candidate constituent: {requirement.requirement_key}"
                )
        requirement_by_key_pair = {
            requirement.constituent_key_pair: requirement
            for requirement in scope.pair_scope_requirements
        }
        if len(requirement_by_key_pair) != len(scope.pair_scope_requirements):
            raise ValueError("M10 scope pair requirements must identify unique constituent pairs")
        if not classifications:
            derived_classifications = []
            for pair in expected_pairs:
                key_pair = tuple(
                    sorted(
                        (
                            entry_by_cad[pair[0]].constituent_key,
                            entry_by_cad[pair[1]].constituent_key,
                        )
                    )
                )
                requirement = requirement_by_key_pair.get(key_pair)
                classification = (
                    requirement.required_classification
                    if requirement is not None
                    else CandidateM10PairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE
                )
                derived_classifications.append(
                    CandidateCollisionPairClassification(
                        pair=pair,
                        classification=classification,
                        reason=(
                            None
                            if classification is CandidateM10PairClassification.CHECK_CLEARANCE
                            else "not required by the declared M10 engineering scope"
                        ),
                        requires_home_exact_check=(
                            requirement.requires_home_exact_check
                            if requirement is not None
                            else False
                        ),
                    )
                )
            classifications = tuple(derived_classifications)
        entries = tuple(
            item
            if isinstance(item, CandidateCollisionPairClassification)
            else CandidateCollisionPairClassification.model_validate(item)
            for item in classifications
        )
        actual_pairs = tuple(item.pair for item in entries)
        if len(set(actual_pairs)) != len(actual_pairs):
            raise ValueError("collision pair inventory contains duplicate classifications")
        if tuple(sorted(actual_pairs)) != expected_pairs:
            missing = sorted(set(expected_pairs) - set(actual_pairs))
            extra = sorted(set(actual_pairs) - set(expected_pairs))
            raise ValueError(f"collision pair inventory is incomplete: omitted={missing}, unsupported={extra}")

        key_pair_to_requirement = requirement_by_key_pair
        fidelity_by_key = dict(scope.fidelity_requirements)
        for key, fidelity in fidelity_by_key.items():
            matching = [entry for entry in binding.constituent_dispositions if entry.constituent_key == key]
            if len(matching) != 1:
                raise ValueError(f"M10 fidelity requirement has no candidate constituent: {key}")
            mapping = mapping_by_cad[matching[0].cad_instance_id]
            if mapping.fidelity is not fidelity:
                raise ValueError(f"candidate CAD fidelity does not satisfy M10 scope: {key}")

        for item in entries:
            first, second = (entry_by_cad[item.pair[0]], entry_by_cad[item.pair[1]])
            requirement = key_pair_to_requirement.get(
                tuple(sorted((first.constituent_key, second.constituent_key)))
            )
            if requirement is not None:
                if item.classification is not requirement.required_classification:
                    raise ValueError(
                        f"collision pair classification does not match scope requirement: {requirement.requirement_key}"
                    )
                if item.requires_home_exact_check != requirement.requires_home_exact_check:
                    raise ValueError(
                        f"collision pair home-check semantics do not match scope requirement: {requirement.requirement_key}"
                    )
            else:
                if item.requires_home_exact_check:
                    raise ValueError("home exact check is not declared in the M10 scope")
                if item.classification is CandidateM10PairClassification.CHECK_CLEARANCE:
                    raise ValueError("checked collision pair is not declared in the M10 scope")

            dispositions = {first.disposition, second.disposition}
            if item.classification is CandidateM10PairClassification.CHECK_CLEARANCE:
                if dispositions != {
                    CandidateM10BodyDisposition.FIXED,
                    CandidateM10BodyDisposition.OUTPUT_RIGID,
                }:
                    raise ValueError("M10 clearance checks require one fixed and one output-rigid constituent")
            elif item.classification is CandidateM10PairClassification.SAME_RIGID_GROUP_EXCLUDED:
                if (
                    first.output_transform_group is None
                    or first.output_transform_group != second.output_transform_group
                    or first.disposition is not CandidateM10BodyDisposition.OUTPUT_RIGID
                    or second.disposition is not CandidateM10BodyDisposition.OUTPUT_RIGID
                ):
                    raise ValueError("same-rigid-group exclusion requires one genuine shared output group")
            elif item.classification is CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE:
                if CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED not in dispositions:
                    raise ValueError("unmodeled-motion exclusion requires an unmodeled constituent")

        return cls(
            cad_realization_hash=realization.realization_hash,
            binding_hash=binding.binding_hash,
            scope_hash=scope.scope_hash,
            expected_pair_universe=expected_pairs,
            classifications=entries,
        )


class CandidateCollisionPairInventoryV2(CandidateM10Model):
    schema_version: Literal["candidate-m10-collision-pair-inventory@2"] = (
        "candidate-m10-collision-pair-inventory@2"
    )
    cad_realization_hash: str
    binding_hash: str
    scope_hash: str
    expected_pair_universe: tuple[tuple[str, str], ...] = Field(min_length=1)
    classifications: tuple[CandidateCollisionPairClassificationV2, ...] = Field(min_length=1)
    checked_pairs: tuple[tuple[str, str], ...] = ()
    excluded_pairs: tuple[tuple[str, str], ...] = ()
    inventory_hash: str = "pending"

    _validate_hashes = field_validator(
        "cad_realization_hash", "binding_hash", "scope_hash"
    )(_require_hash)
    _validate_inventory_hash = field_validator("inventory_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_inventory_v2(self):
        universe = tuple(sorted(_canonical_pair(pair) for pair in self.expected_pair_universe))
        if universe != self.expected_pair_universe:
            object.__setattr__(self, "expected_pair_universe", universe)
        entries = tuple(
            CandidateCollisionPairClassificationV2.model_validate(
                item.model_dump(mode="json")
            )
            for item in self.classifications
        )
        entries = tuple(sorted(entries, key=lambda item: item.pair))
        pairs = tuple(item.pair for item in entries)
        if len(set(pairs)) != len(pairs) or pairs != universe:
            raise ValueError("candidate M10 @2 pair inventory is incomplete or duplicated")
        if entries != self.classifications:
            object.__setattr__(self, "classifications", entries)
        checked = tuple(
            item.pair for item in entries
            if item.classification is CandidateM10PairClassification.CHECK_CLEARANCE
        )
        excluded = tuple(
            item.pair for item in entries
            if item.classification is not CandidateM10PairClassification.CHECK_CLEARANCE
        )
        if "checked_pairs" in self.model_fields_set and self.checked_pairs != checked:
            raise ValueError("candidate M10 @2 checked pair projection mismatch")
        if "excluded_pairs" in self.model_fields_set and self.excluded_pairs != excluded:
            raise ValueError("candidate M10 @2 excluded pair projection mismatch")
        if "checked_pairs" not in self.model_fields_set:
            object.__setattr__(self, "checked_pairs", checked)
        if "excluded_pairs" not in self.model_fields_set:
            object.__setattr__(self, "excluded_pairs", excluded)
        expected = candidate_m10_collision_pair_inventory_hash_v2(self)
        if self.inventory_hash == "pending":
            object.__setattr__(self, "inventory_hash", expected)
        elif self.inventory_hash != expected:
            raise ValueError("candidate M10 collision pair inventory@2 hash mismatch")
        return self

    @classmethod
    def complete_for(
        cls,
        realization: CandidateCadRealizationV2,
        binding: CandidateM10BindingV2,
        scope: CandidateM10EvaluationScope,
        classifications: tuple[CandidateCollisionPairClassificationV2, ...] = (),
    ) -> "CandidateCollisionPairInventoryV2":
        realization = CandidateCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
        )
        binding.validate_against(realization)
        scope = CandidateM10EvaluationScope.model_validate(scope.model_dump(mode="json"))
        mapping_by_physical = {
            item.physical_instance_id: item for item in realization.mappings
        }
        if set(mapping_by_physical) != {
            item.physical_instance_id for item in binding.constituent_dispositions
        }:
            raise ValueError("candidate M10 @2 mapping and disposition universes differ")
        mapping_by_cad = {
            item.cad_instance_id: item for item in realization.mappings
        }
        entry_by_cad = {
            item.cad_instance_id: item for item in binding.constituent_dispositions
        }
        expected_pairs = tuple(itertools.combinations(tuple(sorted(mapping_by_cad)), 2))
        requirements_by_key_pair = {
            requirement.constituent_key_pair: requirement
            for requirement in scope.pair_scope_requirements
        }
        if len(requirements_by_key_pair) != len(scope.pair_scope_requirements):
            raise ValueError("M10 scope pair requirements must identify unique constituent pairs")
        binding_keys = {item.constituent_key for item in binding.constituent_dispositions}
        for requirement in scope.pair_scope_requirements:
            if not {
                requirement.first_constituent_key,
                requirement.second_constituent_key,
            } <= binding_keys:
                raise ValueError("M10 scope requirement has no candidate constituent")
        for key, fidelity in scope.fidelity_requirements:
            matches = [item for item in binding.constituent_dispositions if item.constituent_key == key]
            if len(matches) != 1:
                raise ValueError(f"M10 fidelity requirement has no candidate constituent: {key}")
            mapping = mapping_by_physical[matches[0].physical_instance_id]
            if mapping.fidelity is not fidelity:
                raise ValueError(f"candidate CAD fidelity does not satisfy M10 scope: {key}")

        if not classifications:
            generated = []
            for pair in expected_pairs:
                first = entry_by_cad[pair[0]]
                second = entry_by_cad[pair[1]]
                requirement = requirements_by_key_pair.get(
                    tuple(sorted((first.constituent_key, second.constituent_key)))
                )
                classification = (
                    requirement.required_classification
                    if requirement is not None
                    else CandidateM10PairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE
                )
                generated.append(
                    CandidateCollisionPairClassificationV2(
                        pair=pair,
                        classification=classification,
                        reason=(
                            None
                            if classification is CandidateM10PairClassification.CHECK_CLEARANCE
                            else "not required by the declared M10 engineering scope"
                        ),
                        requires_home_exact_check=(
                            requirement.requires_home_exact_check
                            if requirement is not None
                            else False
                        ),
                    )
                )
            classifications = tuple(generated)
        entries = tuple(
            CandidateCollisionPairClassificationV2.model_validate(
                item.model_dump(mode="json")
            )
            for item in classifications
        )
        if tuple(sorted(item.pair for item in entries)) != expected_pairs:
            raise ValueError("candidate M10 @2 collision inventory is incomplete")
        for item in entries:
            first, second = (entry_by_cad[item.pair[0]], entry_by_cad[item.pair[1]])
            requirement = requirements_by_key_pair.get(
                tuple(sorted((first.constituent_key, second.constituent_key)))
            )
            if requirement is not None and (
                item.classification is not requirement.required_classification
                or item.requires_home_exact_check != requirement.requires_home_exact_check
            ):
                raise ValueError("candidate M10 @2 classification does not match scope")
            if requirement is None and (
                item.classification is CandidateM10PairClassification.CHECK_CLEARANCE
                or item.requires_home_exact_check
            ):
                raise ValueError("candidate M10 @2 inventory contains an undeclared check")
            dispositions = {first.disposition, second.disposition}
            if item.classification is CandidateM10PairClassification.CHECK_CLEARANCE and dispositions != {
                CandidateM10BodyDisposition.FIXED,
                CandidateM10BodyDisposition.OUTPUT_RIGID,
            }:
                raise ValueError("M10 clearance checks require one fixed and one output-rigid constituent")
            if item.classification is CandidateM10PairClassification.SAME_RIGID_GROUP_EXCLUDED and (
                first.output_transform_group is None
                or first.output_transform_group != second.output_transform_group
            ):
                raise ValueError("same-rigid-group exclusion requires a shared output group")
            if item.classification is CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE and (
                CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED not in dispositions
            ):
                raise ValueError("unmodeled-motion exclusion requires an unmodeled constituent")

        return cls(
            cad_realization_hash=realization.realization_hash,
            binding_hash=binding.binding_hash,
            scope_hash=scope.scope_hash,
            expected_pair_universe=expected_pairs,
            classifications=entries,
        )


def candidate_m10_collision_pair_inventory_hash_v2(
    inventory: CandidateCollisionPairInventoryV2,
) -> str:
    _require_semantic_fields(
        inventory,
        CandidateCollisionPairInventoryV2,
        {
            "schema_version", "cad_realization_hash", "binding_hash", "scope_hash",
            "expected_pair_universe", "classifications", "checked_pairs",
            "excluded_pairs", "inventory_hash",
        },
        "CandidateCollisionPairInventoryV2",
    )
    entries = tuple(
        CandidateCollisionPairClassificationV2.model_validate(
            item.model_dump(mode="json")
        )
        for item in inventory.classifications
    )
    entries = tuple(sorted(entries, key=lambda item: item.pair))
    return _semantic_m10_hash(
        {
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
            "schema_version": inventory.schema_version,
            "cad_realization_hash": inventory.cad_realization_hash,
            "binding_hash": inventory.binding_hash,
            "scope_hash": inventory.scope_hash,
            "expected_pair_universe": [list(pair) for pair in inventory.expected_pair_universe],
            "classification_hashes": [
                candidate_m10_collision_pair_classification_hash_v2(item)
                for item in entries
            ],
            "checked_pairs": [list(pair) for pair in inventory.checked_pairs],
            "excluded_pairs": [list(pair) for pair in inventory.excluded_pairs],
        }
    )


class CandidateM10EvaluationRequest(CandidateM10Model):
    schema_version: str = "candidate-m10-evaluation-request@1"
    candidate_hash: str
    cad_realization_hash: str
    binding_hash: str
    scope_hash: str
    model_hash: str
    mapping_hashes: tuple[str, ...] = Field(min_length=1)
    inventory: CandidateCollisionPairInventory
    request_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash", "cad_realization_hash", "binding_hash", "scope_hash", "model_hash"
    )(_require_hash)
    _validate_request_hash = field_validator("request_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_request(self) -> "CandidateM10EvaluationRequest":
        if self.inventory.cad_realization_hash != self.cad_realization_hash:
            raise ValueError("M10 request realization hash does not match inventory")
        if self.inventory.binding_hash != self.binding_hash:
            raise ValueError("M10 request binding hash does not match inventory")
        if self.inventory.scope_hash != self.scope_hash:
            raise ValueError("M10 request scope hash does not match inventory")
        if self.mapping_hashes and any(not _is_hash(value) for value in self.mapping_hashes):
            raise ValueError("M10 request mapping hashes must be sha256 identities")
        expected = _hash(self, "request_hash")
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("candidate M10 evaluation request hash mismatch")
        return self

    def validate_against(
        self,
        realization: CandidateCadRealization,
        binding: CandidateM10Binding,
        scope: CandidateM10EvaluationScope,
    ) -> None:
        binding.validate_against(realization)
        if self.candidate_hash != realization.candidate_hash:
            raise ValueError("M10 request candidate hash mismatch")
        if self.cad_realization_hash != realization.realization_hash:
            raise ValueError("M10 request realization hash mismatch")
        if self.binding_hash != binding.binding_hash:
            raise ValueError("M10 request binding hash mismatch")
        if self.scope_hash != scope.scope_hash:
            raise ValueError("M10 request scope hash mismatch")
        if self.model_hash != binding.model_hash:
            raise ValueError("M10 request model hash mismatch")
        expected_mapping_hashes = tuple(
            sorted(mapping.mapping_hash for mapping in realization.mappings)
        )
        if tuple(sorted(self.mapping_hashes)) != expected_mapping_hashes:
            raise ValueError("M10 request mapping inventory mismatch")
        expected_inventory = CandidateCollisionPairInventory.complete_for(
            realization, binding, scope, self.inventory.classifications
        )
        if expected_inventory != self.inventory:
            raise ValueError("M10 request pair inventory does not match scope")


class CandidateM10EvaluationRequestV2(CandidateM10Model):
    schema_version: Literal["candidate-m10-evaluation-request@2"] = (
        "candidate-m10-evaluation-request@2"
    )
    candidate_hash: str
    cad_realization_hash: str
    binding_hash: str
    scope_hash: str
    semantic_single_joint_kinematic_model_hash: str
    mapping_hashes: tuple[str, ...] = Field(min_length=1)
    inventory: CandidateCollisionPairInventoryV2
    request_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash", "cad_realization_hash", "binding_hash", "scope_hash",
        "semantic_single_joint_kinematic_model_hash",
    )(_require_hash)
    _validate_request_hash = field_validator("request_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_request_v2(self):
        if self.inventory.cad_realization_hash != self.cad_realization_hash:
            raise ValueError("M10 @2 request realization does not match inventory")
        if self.inventory.binding_hash != self.binding_hash:
            raise ValueError("M10 @2 request binding does not match inventory")
        if self.inventory.scope_hash != self.scope_hash:
            raise ValueError("M10 @2 request scope does not match inventory")
        mappings = tuple(self.mapping_hashes)
        if (
            mappings != tuple(sorted(mappings))
            or len(set(mappings)) != len(mappings)
            or any(not _is_hash(value) for value in mappings)
        ):
            raise ValueError("M10 @2 mapping hashes must be sorted, unique SHA-256 identities")
        expected = candidate_m10_evaluation_request_hash_v2(self)
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("candidate M10 evaluation request@2 hash mismatch")
        return self

    def validate_against(
        self,
        realization: CandidateCadRealizationV2,
        binding: CandidateM10BindingV2,
        scope: CandidateM10EvaluationScope,
    ) -> None:
        binding.validate_against(realization)
        scope = CandidateM10EvaluationScope.model_validate(scope.model_dump(mode="json"))
        comparisons = (
            (self.candidate_hash, realization.candidate_hash, "candidate"),
            (self.cad_realization_hash, realization.realization_hash, "CAD realization"),
            (self.binding_hash, binding.binding_hash, "binding"),
            (self.scope_hash, scope.scope_hash, "scope"),
            (
                self.semantic_single_joint_kinematic_model_hash,
                binding.semantic_single_joint_kinematic_model_hash,
                "semantic single-joint model",
            ),
        )
        for actual, expected, label in comparisons:
            if actual != expected:
                raise ValueError(f"M10 @2 request {label} mismatch")
        expected_mapping_hashes = tuple(
            sorted(mapping.mapping_hash for mapping in realization.mappings)
        )
        if self.mapping_hashes != expected_mapping_hashes:
            raise ValueError("M10 @2 request mapping inventory mismatch")
        expected_inventory = CandidateCollisionPairInventoryV2.complete_for(
            realization, binding, scope, self.inventory.classifications
        )
        if expected_inventory != self.inventory:
            raise ValueError("M10 @2 request pair inventory does not match scope")


def candidate_m10_evaluation_request_hash_v2(
    request: CandidateM10EvaluationRequestV2,
) -> str:
    _require_semantic_fields(
        request,
        CandidateM10EvaluationRequestV2,
        {
            "schema_version", "candidate_hash", "cad_realization_hash",
            "binding_hash", "scope_hash", "semantic_single_joint_kinematic_model_hash",
            "mapping_hashes", "inventory", "request_hash",
        },
        "CandidateM10EvaluationRequestV2",
    )
    inventory = CandidateCollisionPairInventoryV2.model_validate(
        request.inventory.model_dump(mode="json")
    )
    return _semantic_m10_hash(
        {
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
            "schema_version": request.schema_version,
            "candidate_hash": request.candidate_hash,
            "cad_realization_hash": request.cad_realization_hash,
            "binding_hash": request.binding_hash,
            "scope_hash": request.scope_hash,
            "semantic_single_joint_kinematic_model_hash": request.semantic_single_joint_kinematic_model_hash,
            "mapping_hashes": list(request.mapping_hashes),
            "inventory_hash": inventory.inventory_hash,
        }
    )


class CandidateM10StageStatus(StrEnum):
    SUCCESS = "success"
    UNRESOLVED = "unresolved"
    NOT_REACHED = "not_reached"


class CandidateM10StageReason(StrEnum):
    UNMODELED_CONTINUOUS_MOTION = "unmodeled_continuous_motion"
    PRIOR_STAGE_FAILED = "prior_stage_failed"


class CandidateM10PairProof(CandidateM10Model):
    """One exact continuous M10 proof and its reconstructed request."""

    schema_version: str = "candidate-m10-pair-proof@1"
    pair: tuple[str, str]
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    request: ContinuousSingleAxisProofRequest
    result: ContinuousSingleAxisProofResult
    request_hash: str
    result_hash: str
    proof_hash: str = "pending"

    _validate_hashes = field_validator("request_hash", "result_hash", "proof_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_pair_proof(self) -> "CandidateM10PairProof":
        if self.pair != tuple(sorted(self.pair)) or len(self.pair) != 2 or self.pair[0] == self.pair[1]:
            raise ValueError("M10 pair proof pair must be a sorted pair of distinct IDs")
        if (self.moving_instance_id, self.stationary_instance_id) != self.pair:
            if {self.moving_instance_id, self.stationary_instance_id} != set(self.pair):
                raise ValueError("M10 pair proof instance IDs do not match pair")
        if self.request.request_hash != self.request_hash:
            raise ValueError("M10 pair proof request identity mismatch")
        if self.result.request_hash != self.request_hash:
            raise ValueError("M10 pair proof result is bound to a different request")
        if self.result.result_hash != self.result_hash:
            raise ValueError("M10 pair proof result identity mismatch")
        if self.request.moving_instance_ids != (self.moving_instance_id,) or self.request.stationary_instance_ids != (self.stationary_instance_id,):
            raise ValueError("M10 pair proof request partition mismatch")
        if self.result.source_assembly_hash != self.request.source_assembly_hash:
            raise ValueError("M10 pair proof source assembly mismatch")
        expected = _hash(self, "proof_hash")
        if self.proof_hash == "pending":
            object.__setattr__(self, "proof_hash", expected)
        elif self.proof_hash != expected:
            raise ValueError("candidate M10 pair proof hash mismatch")
        return self


class CandidateHomeExactCheck(CandidateM10Model):
    """The exact home-state M10 sweep for an independently measurable pair."""

    schema_version: str = "candidate-home-exact-check@1"
    pair: tuple[str, str]
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    request: CadKinematicSweepRequest
    result: CadKinematicSweepResult
    request_hash: str
    result_hash: str
    check_hash: str = "pending"

    _validate_hashes = field_validator("request_hash", "result_hash", "check_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_home_check(self) -> "CandidateHomeExactCheck":
        if self.pair != tuple(sorted(self.pair)) or len(self.pair) != 2 or self.pair[0] == self.pair[1]:
            raise ValueError("home exact check pair must be a sorted pair of distinct IDs")
        if {self.moving_instance_id, self.stationary_instance_id} != set(self.pair):
            raise ValueError("home exact check instance IDs do not match pair")
        if self.request.request_hash != self.request_hash:
            raise ValueError("home exact check request identity mismatch")
        if self.result.request_hash != self.request_hash:
            raise ValueError("home exact check result is bound to a different request")
        if self.result.result_hash != self.result_hash:
            raise ValueError("home exact check result identity mismatch")
        if self.request.sample_angles_deg != (0.0,):
            raise ValueError("home exact check must use the zero-angle sample")
        if self.request.moving_instance_ids != (self.moving_instance_id,) or self.request.stationary_instance_ids != (self.stationary_instance_id,):
            raise ValueError("home exact check request partition mismatch")
        if self.result.source_assembly_hash != self.request.source_assembly_hash:
            raise ValueError("home exact check source assembly mismatch")
        expected = _hash(self, "check_hash")
        if self.check_hash == "pending":
            object.__setattr__(self, "check_hash", expected)
        elif self.check_hash != expected:
            raise ValueError("candidate home exact check hash mismatch")
        return self


class CandidateM10PairProofV2(CandidateM10Model):
    schema_version: Literal["candidate-m10-pair-proof@2"] = "candidate-m10-pair-proof@2"
    pair: tuple[str, str]
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    request: ContinuousSingleAxisProofRequest
    result: ContinuousSingleAxisProofResult
    request_hash: str
    result_hash: str
    semantic_assembly_hash: str
    proof_hash: str = "pending"

    _validate_hashes = field_validator(
        "request_hash", "result_hash", "semantic_assembly_hash", "proof_hash"
    )(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_pair_proof_v2(self):
        request = ContinuousSingleAxisProofRequest.model_validate(
            self.request.model_dump(mode="json")
        )
        result = ContinuousSingleAxisProofResult.model_validate(
            self.result.model_dump(mode="json")
        )
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "result", result)
        if self.pair != tuple(sorted(self.pair)) or len(self.pair) != 2 or self.pair[0] == self.pair[1]:
            raise ValueError("M10 @2 pair proof requires a sorted pair of distinct IDs")
        if {self.moving_instance_id, self.stationary_instance_id} != set(self.pair):
            raise ValueError("M10 @2 pair proof instance IDs do not match pair")
        if (
            self.request_hash != self.request.request_hash
            or self.result.request_hash != self.request_hash
            or self.result_hash != self.result.result_hash
        ):
            raise ValueError("M10 @2 pair proof raw replay identities do not bind")
        if self.request.moving_instance_ids != (self.moving_instance_id,) or self.request.stationary_instance_ids != (self.stationary_instance_id,):
            raise ValueError("M10 @2 pair proof request partition mismatch")
        if self.result.source_assembly_hash != self.request.source_assembly_hash:
            raise ValueError("M10 @2 pair proof source assembly mismatch")
        if self.result.result_hash != _legacy_continuous_result_hash(self.result):
            raise ValueError("M10 @2 pair proof raw result hash mismatch")
        expected = candidate_m10_pair_proof_hash_v2(self)
        if self.proof_hash == "pending":
            object.__setattr__(self, "proof_hash", expected)
        elif self.proof_hash != expected:
            raise ValueError("candidate M10 pair proof@2 hash mismatch")
        return self

    def validate_against(
        self,
        assembly: CadAssemblyProgram,
        mappings,
    ) -> None:
        semantic_assembly = verified_semantic_assembly_hash(
            assembly, mappings, self.request.source_assembly_hash
        )
        if semantic_assembly != self.semantic_assembly_hash:
            raise ValueError("M10 @2 pair proof semantic assembly binding mismatch")
        CandidateM10EvaluationService.CONTINUOUS_RESULT_VALIDATION.validate(
            self.request, self.result, assembly
        )
        if semantic_proof_request_hash(self.request, assembly, mappings) != (
            _semantic_proof_request_hash_from_assembly_identity(
                self.request, self.semantic_assembly_hash
            )
        ):
            raise ValueError("M10 @2 pair proof request projection mismatch")
        if semantic_proof_result_hash(self.result, self.request, assembly, mappings) != (
            _semantic_proof_result_hash_from_assembly_identity(
                self.result, self.request, self.semantic_assembly_hash
            )
        ):
            raise ValueError("M10 @2 pair proof result projection mismatch")


def candidate_m10_pair_proof_hash_v2(proof: CandidateM10PairProofV2) -> str:
    _require_semantic_fields(
        proof,
        CandidateM10PairProofV2,
        {
            "schema_version", "pair", "moving_instance_id", "stationary_instance_id",
            "request", "result", "request_hash", "result_hash",
            "semantic_assembly_hash", "proof_hash",
        },
        "CandidateM10PairProofV2",
    )
    payload = {
        "schema_version": proof.schema_version,
        "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
        "pair": list(proof.pair),
        "moving_instance_id": proof.moving_instance_id,
        "stationary_instance_id": proof.stationary_instance_id,
        "semantic_proof_request_hash": _semantic_proof_request_hash_from_assembly_identity(
            proof.request, proof.semantic_assembly_hash
        ),
        "semantic_proof_result_hash": _semantic_proof_result_hash_from_assembly_identity(
            proof.result, proof.request, proof.semantic_assembly_hash
        ),
        "semantic_assembly_hash": proof.semantic_assembly_hash,
    }
    return _semantic_m10_hash(payload)


class CandidateHomeExactCheckV2(CandidateM10Model):
    schema_version: Literal["candidate-home-exact-check@2"] = "candidate-home-exact-check@2"
    pair: tuple[str, str]
    moving_instance_id: str = Field(min_length=1)
    stationary_instance_id: str = Field(min_length=1)
    request: CadKinematicSweepRequest
    result: CadKinematicSweepResult
    request_hash: str
    result_hash: str
    semantic_assembly_hash: str
    check_hash: str = "pending"

    _validate_hashes = field_validator(
        "request_hash", "result_hash", "semantic_assembly_hash", "check_hash"
    )(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_home_check_v2(self):
        request = CadKinematicSweepRequest.model_validate(
            self.request.model_dump(mode="json")
        )
        result = CadKinematicSweepResult.model_validate(
            self.result.model_dump(mode="json")
        )
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "result", result)
        if self.pair != tuple(sorted(self.pair)) or len(self.pair) != 2 or self.pair[0] == self.pair[1]:
            raise ValueError("home exact check@2 requires a sorted pair of distinct IDs")
        if {self.moving_instance_id, self.stationary_instance_id} != set(self.pair):
            raise ValueError("home exact check@2 instance IDs do not match pair")
        if (
            self.request_hash != self.request.request_hash
            or self.result.request_hash != self.request_hash
            or self.result_hash != self.result.result_hash
        ):
            raise ValueError("home exact check@2 raw replay identities do not bind")
        if self.request.sample_angles_deg != (0.0,):
            raise ValueError("home exact check@2 must use the zero-angle sample")
        if self.request.moving_instance_ids != (self.moving_instance_id,) or self.request.stationary_instance_ids != (self.stationary_instance_id,):
            raise ValueError("home exact check@2 request partition mismatch")
        if self.result.source_assembly_hash != self.request.source_assembly_hash:
            raise ValueError("home exact check@2 source assembly mismatch")
        if self.result.result_hash != _legacy_sweep_result_hash(self.result):
            raise ValueError("home exact check@2 raw result hash mismatch")
        expected = candidate_home_exact_check_hash_v2(self)
        if self.check_hash == "pending":
            object.__setattr__(self, "check_hash", expected)
        elif self.check_hash != expected:
            raise ValueError("candidate home exact check@2 hash mismatch")
        return self

    def validate_against(self, assembly: CadAssemblyProgram, mappings) -> None:
        semantic_assembly = verified_semantic_assembly_hash(
            assembly, mappings, self.request.source_assembly_hash
        )
        if semantic_assembly != self.semantic_assembly_hash:
            raise ValueError("home exact check@2 semantic assembly binding mismatch")
        CandidateM10EvaluationService.HOME_RESULT_VALIDATION.validate(
            self.request, self.result, assembly
        )
        semantic_sweep_request_hash(self.request, assembly, mappings)
        semantic_sweep_result_hash(self.result, self.request, assembly, mappings)


def candidate_home_exact_check_hash_v2(check: CandidateHomeExactCheckV2) -> str:
    _require_semantic_fields(
        check,
        CandidateHomeExactCheckV2,
        {
            "schema_version", "pair", "moving_instance_id", "stationary_instance_id",
            "request", "result", "request_hash", "result_hash",
            "semantic_assembly_hash", "check_hash",
        },
        "CandidateHomeExactCheckV2",
    )
    return _semantic_m10_hash(
        {
            "schema_version": check.schema_version,
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
            "pair": list(check.pair),
            "moving_instance_id": check.moving_instance_id,
            "stationary_instance_id": check.stationary_instance_id,
            "semantic_sweep_request_hash": _semantic_sweep_request_hash_from_assembly_identity(
                check.request, check.semantic_assembly_hash
            ),
            "semantic_sweep_result_hash": _semantic_sweep_result_hash_from_assembly_identity(
                check.result, check.request, check.semantic_assembly_hash
            ),
            "semantic_assembly_hash": check.semantic_assembly_hash,
        }
    )


class CandidateM10StageOutcomeV2(CandidateM10Model):
    schema_version: Literal["candidate-m10-stage-outcome@2"] = "candidate-m10-stage-outcome@2"
    status: CandidateM10StageStatus
    candidate_hash: str
    cad_realization_hash: str | None = None
    binding_hash: str | None = None
    scope_hash: str | None = None
    evaluation_request_hash: str | None = None
    source_revision: int = Field(gt=0)
    source_state_hash: str
    pair_proofs: tuple[CandidateM10PairProofV2, ...] = ()
    home_exact_checks: tuple[CandidateHomeExactCheckV2, ...] = ()
    reasons: tuple[CandidateM10StageReason, ...] = ()
    outcome_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash", "binding_hash", "scope_hash", "evaluation_request_hash",
        "source_state_hash",
    )(_optional_hash)
    _validate_cad_hash = field_validator(
        "cad_realization_hash",
    )(lambda value: None if value is None else _require_hash(value))
    _validate_outcome_hash = field_validator("outcome_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_stage_outcome_v2(self):
        if self.status is CandidateM10StageStatus.SUCCESS and self.reasons:
            raise ValueError("successful M10 @2 stage cannot contain unresolved reasons")
        if self.status is CandidateM10StageStatus.UNRESOLVED and not self.reasons:
            raise ValueError("unresolved M10 @2 stage requires a typed reason")
        if self.status is CandidateM10StageStatus.NOT_REACHED:
            if self.cad_realization_hash is not None or any(
                value is not None
                for value in (self.binding_hash, self.scope_hash, self.evaluation_request_hash)
            ):
                raise ValueError("not-reached M10 @2 stage must be a reason-only record")
            if self.reasons != (CandidateM10StageReason.PRIOR_STAGE_FAILED,):
                raise ValueError("not-reached M10 @2 stage requires the prior-stage reason")
            if self.pair_proofs or self.home_exact_checks:
                raise ValueError("not-reached M10 @2 stage cannot contain M10 executions")
        elif self.cad_realization_hash is None or any(
            value is None for value in (self.binding_hash, self.scope_hash, self.evaluation_request_hash)
        ):
            raise ValueError("completed M10 @2 stage requires exact stage identities")
        pair_keys = tuple(item.pair for item in self.pair_proofs)
        home_keys = tuple(item.pair for item in self.home_exact_checks)
        if (
            pair_keys != tuple(sorted(pair_keys))
            or home_keys != tuple(sorted(home_keys))
            or len(set(pair_keys)) != len(pair_keys)
            or len(set(home_keys)) != len(home_keys)
        ):
            raise ValueError("M10 @2 execution pairs must be unique and canonically ordered")
        expected = candidate_m10_stage_outcome_hash_v2(self)
        if self.outcome_hash == "pending":
            object.__setattr__(self, "outcome_hash", expected)
        elif self.outcome_hash != expected:
            raise ValueError("candidate M10 stage outcome@2 hash mismatch")
        return self

    def validate_against(
        self,
        candidate: MechanicalDesignCandidate,
        synthesis_request,
        admissibility_result,
        realization: CandidateCadRealizationV2,
        binding: CandidateM10BindingV2,
        request: CandidateM10EvaluationRequestV2,
        scope: CandidateM10EvaluationScope,
    ) -> None:
        from mechcad_harness.revolute_drive.models import admissibility_result_hash

        candidate = MechanicalDesignCandidate.model_validate(
            candidate.model_dump(mode="json")
        )
        if (
            candidate.schema_version != "mechanical-design-candidate@2"
            or synthesis_request.schema_version != "candidate-synthesis-request@2"
            or admissibility_result.schema_version != "revolute-drive-admissibility@2"
        ):
            raise ValueError("candidate M10 @2 replay requires a homogeneous request/candidate/M12 chain")
        if (
            candidate.source_binding != synthesis_request.source_binding
            or candidate.semantic_source_binding_hash
            != synthesis_request.semantic_source_binding_hash
            or candidate.synthesis_request_hash != synthesis_request.request_hash
        ):
            raise ValueError("candidate M10 @2 synthesis request binding mismatch")
        if (
            admissibility_result.candidate_hash != candidate.candidate_hash
            or admissibility_result.synthesis_request_hash != synthesis_request.request_hash
            or admissibility_result.source_binding_hash
            != synthesis_request.semantic_source_binding_hash
            or admissibility_result.result_hash
            != admissibility_result_hash(admissibility_result)
        ):
            raise ValueError("candidate M10 @2 admissibility parent mismatch")
        realization = CandidateCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
        )
        binding.validate_against(realization)
        request.validate_against(realization, binding, scope)
        if (
            self.candidate_hash != candidate.candidate_hash
            or self.cad_realization_hash != realization.realization_hash
            or self.binding_hash != binding.binding_hash
            or self.scope_hash != scope.scope_hash
            or self.evaluation_request_hash != request.request_hash
            or self.source_revision != synthesis_request.source_binding.source_revision
            or self.source_state_hash != synthesis_request.source_binding.source_state_hash
        ):
            raise ValueError("candidate M10 @2 stage parent or source-coordinate mismatch")

        expected_proofs = tuple(
            item.pair
            for item in request.inventory.classifications
            if item.classification is CandidateM10PairClassification.CHECK_CLEARANCE
        )
        expected_home_checks = tuple(
            item.pair
            for item in request.inventory.classifications
            if item.requires_home_exact_check
        )
        if tuple(item.pair for item in self.pair_proofs) != expected_proofs:
            raise ValueError("candidate M10 @2 pair proofs do not match the request inventory")
        if tuple(item.pair for item in self.home_exact_checks) != expected_home_checks:
            raise ValueError("candidate M10 @2 home checks do not match the request inventory")

        for proof in self.pair_proofs:
            pair_assembly = CandidateM10EvaluationService._induced_pair_assembly(
                realization.assembly,
                proof.moving_instance_id,
                proof.stationary_instance_id,
            )
            pair_ids = {instance.instance_id for instance in pair_assembly.instances}
            pair_mappings = tuple(
                mapping for mapping in realization.mappings
                if mapping.cad_instance_id in pair_ids
            )
            proof.validate_against(pair_assembly, pair_mappings)
        for check in self.home_exact_checks:
            pair_assembly = CandidateM10EvaluationService._induced_pair_assembly(
                realization.assembly,
                check.moving_instance_id,
                check.stationary_instance_id,
            )
            pair_ids = {instance.instance_id for instance in pair_assembly.instances}
            pair_mappings = tuple(
                mapping for mapping in realization.mappings
                if mapping.cad_instance_id in pair_ids
            )
            check.validate_against(pair_assembly, pair_mappings)

    @property
    def m10_request_hashes(self) -> tuple[str, ...]:
        return tuple(proof.request_hash for proof in self.pair_proofs) + tuple(
            check.request_hash for check in self.home_exact_checks
        )

    @property
    def m10_result_hashes(self) -> tuple[str, ...]:
        return tuple(proof.result_hash for proof in self.pair_proofs) + tuple(
            check.result_hash for check in self.home_exact_checks
        )


def candidate_m10_stage_outcome_hash_v2(outcome: CandidateM10StageOutcomeV2) -> str:
    _require_semantic_fields(
        outcome,
        CandidateM10StageOutcomeV2,
        {
            "schema_version", "status", "candidate_hash", "cad_realization_hash",
            "binding_hash", "scope_hash", "evaluation_request_hash",
            "source_revision", "source_state_hash", "pair_proofs",
            "home_exact_checks", "reasons", "outcome_hash",
        },
        "CandidateM10StageOutcomeV2",
    )
    return _semantic_m10_hash(
        {
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
            "schema_version": outcome.schema_version,
            "status": outcome.status.value,
            "candidate_hash": outcome.candidate_hash,
            "cad_realization_hash": outcome.cad_realization_hash,
            "binding_hash": outcome.binding_hash,
            "scope_hash": outcome.scope_hash,
            "evaluation_request_hash": outcome.evaluation_request_hash,
            "pair_proof_hashes": [item.proof_hash for item in outcome.pair_proofs],
            "home_exact_check_hashes": [item.check_hash for item in outcome.home_exact_checks],
            "reasons": [item.value for item in outcome.reasons],
        }
    )


class CandidateM10StageOutcome(CandidateM10Model):
    """Immutable outcome of the candidate-to-M10 execution stage."""

    schema_version: str = "candidate-m10-stage-outcome@1"
    status: CandidateM10StageStatus
    candidate_hash: str
    cad_realization_hash: str | None = None
    binding_hash: str | None = None
    scope_hash: str | None = None
    evaluation_request_hash: str | None = None
    source_revision: int = Field(gt=0)
    source_state_hash: str
    pair_proofs: tuple[CandidateM10PairProof, ...] = ()
    home_exact_checks: tuple[CandidateHomeExactCheck, ...] = ()
    reasons: tuple[CandidateM10StageReason, ...] = ()
    outcome_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash", "binding_hash", "scope_hash", "evaluation_request_hash", "source_state_hash"
    )(_optional_hash)
    _validate_cad_hash = field_validator("cad_realization_hash")(
        lambda value: None if value is None else _require_hash(value)
    )
    _validate_outcome_hash = field_validator("outcome_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_stage_outcome(self) -> "CandidateM10StageOutcome":
        if self.status is CandidateM10StageStatus.SUCCESS and self.reasons:
            raise ValueError("successful M10 stage cannot contain unresolved reasons")
        if self.status is CandidateM10StageStatus.UNRESOLVED and not self.reasons:
            raise ValueError("unresolved M10 stage requires a typed reason")
        if self.status is CandidateM10StageStatus.NOT_REACHED:
            if self.cad_realization_hash is not None:
                raise ValueError("not-reached M10 stage cannot carry a CAD realization")
            if any(value is not None for value in (self.binding_hash, self.scope_hash, self.evaluation_request_hash)):
                raise ValueError("not-reached M10 stage must be a reason-only record")
            if self.reasons != (CandidateM10StageReason.PRIOR_STAGE_FAILED,):
                raise ValueError("not-reached M10 stage requires the prior-stage reason")
            if self.pair_proofs or self.home_exact_checks:
                raise ValueError("not-reached M10 stage cannot contain M10 executions")
        elif self.cad_realization_hash is None:
            raise ValueError("completed M10 stage requires a CAD realization")
        elif any(value is None for value in (self.binding_hash, self.scope_hash, self.evaluation_request_hash)):
            raise ValueError("completed M10 stage requires exact stage identities")
        pair_keys = tuple(proof.pair for proof in self.pair_proofs)
        home_keys = tuple(check.pair for check in self.home_exact_checks)
        if len(set(pair_keys)) != len(pair_keys) or len(set(home_keys)) != len(home_keys):
            raise ValueError("M10 stage execution pairs must be unique")
        expected = _hash(self, "outcome_hash")
        if self.outcome_hash == "pending":
            object.__setattr__(self, "outcome_hash", expected)
        elif self.outcome_hash != expected:
            raise ValueError("candidate M10 stage outcome hash mismatch")
        return self

    @property
    def m10_request_hashes(self) -> tuple[str, ...]:
        return tuple(proof.request_hash for proof in self.pair_proofs) + tuple(
            check.request_hash for check in self.home_exact_checks
        )

    @property
    def m10_result_hashes(self) -> tuple[str, ...]:
        return tuple(proof.result_hash for proof in self.pair_proofs) + tuple(
            check.result_hash for check in self.home_exact_checks
        )


class CandidateM10EvaluationService:
    """Invoke the accepted M10 public methods without reimplementing M10."""

    CONTINUOUS_RESULT_VALIDATION = ContinuousM10ResultValidationContract(
        require_source_assembly_id=False,
        allowed_collision_witness_classifications=frozenset(
            (CollisionClassification.INTERFERENCE, CollisionClassification.TOUCHING)
        ),
    )
    HOME_RESULT_VALIDATION = HomeM10ResultValidationContract(
        accepted_sweep_version=RIGID_BODY_COLLISION_SWEEP_VERSION
    )

    def __init__(
        self,
        prove_continuous_single_axis_clearance,
        analyze_assembly_kinematics,
        *,
        scope: CandidateM10EvaluationScope | None = None,
        proof_guard_mm: float = 1e-6,
        max_depth: int = 16,
        minimum_interval_deg: float = 1e-6,
        max_exact_evaluations: int = 4096,
    ):
        self.prove_continuous_single_axis_clearance = prove_continuous_single_axis_clearance
        self.analyze_assembly_kinematics = analyze_assembly_kinematics
        self.scope = scope
        self.proof_guard_mm = proof_guard_mm
        self.max_depth = max_depth
        self.minimum_interval_deg = minimum_interval_deg
        self.max_exact_evaluations = max_exact_evaluations

    def _evaluate_v2(
        self,
        source_revision: int,
        source_state_hash: str,
        realization: CandidateCadRealizationV2 | CandidateCadStageOutcomeV2,
        binding: CandidateM10BindingV2,
        request: CandidateM10EvaluationRequestV2,
        *,
        scope: CandidateM10EvaluationScope | None,
        physical_realization: PhysicalMechanismRealization | None,
    ) -> CandidateM10StageOutcomeV2:
        _require_hash(source_state_hash)
        request = CandidateM10EvaluationRequestV2.model_validate(
            request.model_dump(mode="json")
        )
        binding = CandidateM10BindingV2.model_validate(binding.model_dump(mode="json"))
        effective_scope = scope or self.scope
        if effective_scope is None:
            raise ValueError("candidate M10 evaluation scope is required")
        effective_scope = CandidateM10EvaluationScope.model_validate(
            effective_scope.model_dump(mode="json")
        )
        if isinstance(realization, CandidateCadStageOutcomeV2):
            realization = CandidateCadStageOutcomeV2.model_validate(
                realization.model_dump(mode="json")
            )
            if realization.status is not CandidateCadStageStatus.SUCCESS:
                if physical_realization is not None:
                    binding.validate_physical_realization(physical_realization)
                return CandidateM10StageOutcomeV2(
                    status=CandidateM10StageStatus.NOT_REACHED,
                    candidate_hash=request.candidate_hash,
                    source_revision=source_revision,
                    source_state_hash=source_state_hash,
                    reasons=(CandidateM10StageReason.PRIOR_STAGE_FAILED,),
                )
            if realization.realization is None:
                raise ValueError("successful candidate CAD @2 stage has no realization")
            realization = realization.realization
        if type(realization) is not CandidateCadRealizationV2:
            raise TypeError("candidate M10 @2 requires CandidateCadRealizationV2")
        realization = CandidateCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
        )
        binding.validate_against(realization, physical_realization)
        request.validate_against(realization, binding, effective_scope)
        if request.scope_hash != effective_scope.scope_hash:
            raise ValueError("candidate M10 @2 evaluation scope mismatch")

        disposition_by_cad = {
            item.cad_instance_id: item for item in binding.constituent_dispositions
        }
        mappings_by_cad = {item.cad_instance_id: item for item in realization.mappings}
        proofs: list[CandidateM10PairProofV2] = []
        home_checks: list[CandidateHomeExactCheckV2] = []
        unresolved: list[CandidateM10StageReason] = []
        for classification in request.inventory.classifications:
            first, second = classification.pair
            first_disposition = disposition_by_cad[first]
            second_disposition = disposition_by_cad[second]
            if classification.classification is CandidateM10PairClassification.CHECK_CLEARANCE:
                moving = next(
                    item.cad_instance_id
                    for item in (first_disposition, second_disposition)
                    if item.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID
                )
                stationary = next(
                    item.cad_instance_id
                    for item in (first_disposition, second_disposition)
                    if item.disposition is CandidateM10BodyDisposition.FIXED
                )
                pair_assembly = self._induced_pair_assembly(
                    realization.assembly, moving, stationary
                )
                pair_mappings = tuple(
                    mappings_by_cad[instance.instance_id]
                    for instance in pair_assembly.instances
                )
                pair_assembly_semantics = verified_semantic_assembly_hash(
                    pair_assembly, pair_mappings, assembly_hash(pair_assembly)
                )
                kwargs = {
                    "source_revision": source_revision,
                    "source_state_hash": source_state_hash,
                    "assembly": pair_assembly,
                    "axis": binding.output_axis,
                    "moving_instance_ids": (moving,),
                    "stationary_instance_ids": (stationary,),
                    "start_angle_deg": effective_scope.angle_interval_deg[0],
                    "end_angle_deg": effective_scope.angle_interval_deg[1],
                    "required_clearance_mm": effective_scope.required_clearance_mm,
                    "proof_guard_mm": self.proof_guard_mm,
                    "max_depth": self.max_depth,
                    "minimum_interval_deg": self.minimum_interval_deg,
                    "max_exact_evaluations": self.max_exact_evaluations,
                }
                result = self.prove_continuous_single_axis_clearance(**kwargs)
                proof_request = ContinuousSingleAxisProofRequest(
                    source_assembly_id=pair_assembly.assembly_id,
                    source_assembly_hash=assembly_hash(pair_assembly),
                    axis=binding.output_axis,
                    start_angle_deg=effective_scope.angle_interval_deg[0],
                    end_angle_deg=effective_scope.angle_interval_deg[1],
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                    required_clearance_mm=effective_scope.required_clearance_mm,
                    proof_guard_mm=self.proof_guard_mm,
                    max_depth=self.max_depth,
                    minimum_interval_deg=self.minimum_interval_deg,
                    max_exact_evaluations=self.max_exact_evaluations,
                )
                result = ContinuousSingleAxisProofResult.model_validate(
                    result.model_dump(mode="json")
                )
                self._validate_continuous_result(proof_request, result, pair_assembly)
                proofs.append(
                    CandidateM10PairProofV2(
                        pair=classification.pair,
                        moving_instance_id=moving,
                        stationary_instance_id=stationary,
                        request=proof_request,
                        result=result,
                        request_hash=proof_request.request_hash,
                        result_hash=result.result_hash,
                        semantic_assembly_hash=pair_assembly_semantics,
                    )
                )
            elif classification.requires_home_exact_check:
                moving = next(
                    item.cad_instance_id
                    for item in (first_disposition, second_disposition)
                    if item.disposition is CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED
                )
                stationary = second if moving == first else first
                pair_assembly = self._induced_pair_assembly(
                    realization.assembly, moving, stationary
                )
                pair_mappings = tuple(
                    mappings_by_cad[instance.instance_id]
                    for instance in pair_assembly.instances
                )
                pair_assembly_semantics = verified_semantic_assembly_hash(
                    pair_assembly, pair_mappings, assembly_hash(pair_assembly)
                )
                home_request = CadKinematicSweepRequest(
                    source_assembly_id=pair_assembly.assembly_id,
                    source_assembly_hash=assembly_hash(pair_assembly),
                    axis=binding.output_axis,
                    sample_angles_deg=(0.0,),
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                )
                result = self.analyze_assembly_kinematics(
                    source_revision=source_revision,
                    source_state_hash=source_state_hash,
                    assembly=pair_assembly,
                    axis=binding.output_axis,
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                    sample_angles_deg=(0.0,),
                )
                result = CadKinematicSweepResult.model_validate(
                    result.model_dump(mode="json")
                )
                self._validate_home_result(home_request, result, pair_assembly)
                home_checks.append(
                    CandidateHomeExactCheckV2(
                        pair=classification.pair,
                        moving_instance_id=moving,
                        stationary_instance_id=stationary,
                        request=home_request,
                        result=result,
                        request_hash=home_request.request_hash,
                        result_hash=result.result_hash,
                        semantic_assembly_hash=pair_assembly_semantics,
                    )
                )
                unresolved.append(CandidateM10StageReason.UNMODELED_CONTINUOUS_MOTION)
            elif classification.classification is CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE:
                unresolved.append(CandidateM10StageReason.UNMODELED_CONTINUOUS_MOTION)

        return CandidateM10StageOutcomeV2(
            status=(
                CandidateM10StageStatus.UNRESOLVED
                if unresolved
                else CandidateM10StageStatus.SUCCESS
            ),
            candidate_hash=realization.candidate_hash,
            cad_realization_hash=realization.realization_hash,
            binding_hash=binding.binding_hash,
            scope_hash=effective_scope.scope_hash,
            evaluation_request_hash=request.request_hash,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            pair_proofs=tuple(sorted(proofs, key=lambda item: item.pair)),
            home_exact_checks=tuple(sorted(home_checks, key=lambda item: item.pair)),
            reasons=tuple(dict.fromkeys(unresolved)),
        )

    def evaluate(
        self,
        source_revision: int,
        source_state_hash: str,
        realization: CandidateCadRealization | CandidateCadStageOutcome | CandidateCadRealizationV2 | CandidateCadStageOutcomeV2,
        binding: CandidateM10Binding | CandidateM10BindingV2,
        request: CandidateM10EvaluationRequest | CandidateM10EvaluationRequestV2,
        *,
        scope: CandidateM10EvaluationScope | None = None,
        physical_realization: PhysicalMechanismRealization | None = None,
    ) -> CandidateM10StageOutcome | CandidateM10StageOutcomeV2:
        if isinstance(request, CandidateM10EvaluationRequestV2):
            if not isinstance(binding, CandidateM10BindingV2):
                raise ValueError("candidate M10 request@2 cannot use binding@1")
            return self._evaluate_v2(
                source_revision,
                source_state_hash,
                realization,
                binding,
                request,
                scope=scope,
                physical_realization=physical_realization,
            )
        if getattr(request, "schema_version", None) == "candidate-m10-evaluation-request@2":
            raise TypeError("candidate M10 request@2 must be CandidateM10EvaluationRequestV2")
        _require_hash(source_state_hash)
        request = CandidateM10EvaluationRequest.model_validate(request.model_dump(mode="json"))
        effective_scope = scope or self.scope
        if effective_scope is None:
            raise ValueError("candidate M10 evaluation scope is required")
        effective_scope = CandidateM10EvaluationScope.model_validate(effective_scope.model_dump(mode="json"))

        binding = CandidateM10Binding.model_validate(binding.model_dump(mode="json"))
        self._validate_request_against_binding_scope(request, binding, effective_scope)

        if isinstance(realization, CandidateCadStageOutcome):
            realization = CandidateCadStageOutcome.model_validate(realization.model_dump(mode="json"))
            if realization.status is not CandidateCadStageStatus.SUCCESS:
                if physical_realization is not None:
                    binding.validate_physical_realization(physical_realization)
                return CandidateM10StageOutcome(
                    status=CandidateM10StageStatus.NOT_REACHED,
                    candidate_hash=request.candidate_hash,
                    source_revision=source_revision,
                    source_state_hash=source_state_hash,
                    reasons=(CandidateM10StageReason.PRIOR_STAGE_FAILED,),
                )
            if realization.realization is None:
                raise ValueError("successful CAD stage has no realization")
            realization = realization.realization

        realization = CandidateCadRealization.model_validate(realization.model_dump(mode="json"))
        binding.validate_against(realization, physical_realization)
        request.validate_against(realization, binding, effective_scope)
        if request.scope_hash != effective_scope.scope_hash:
            raise ValueError("candidate M10 evaluation scope mismatch")

        disposition_by_cad = {entry.cad_instance_id: entry for entry in binding.constituent_dispositions}
        proofs: list[CandidateM10PairProof] = []
        home_checks: list[CandidateHomeExactCheck] = []
        unresolved: list[CandidateM10StageReason] = []

        for classification in request.inventory.classifications:
            first, second = classification.pair
            first_disposition = disposition_by_cad[first]
            second_disposition = disposition_by_cad[second]

            if classification.classification is CandidateM10PairClassification.CHECK_CLEARANCE:
                moving = next(
                    entry.cad_instance_id
                    for entry in (first_disposition, second_disposition)
                    if entry.disposition is CandidateM10BodyDisposition.OUTPUT_RIGID
                )
                stationary = next(
                    entry.cad_instance_id
                    for entry in (first_disposition, second_disposition)
                    if entry.disposition is CandidateM10BodyDisposition.FIXED
                )
                pair_assembly = self._induced_pair_assembly(realization.assembly, moving, stationary)
                kwargs = {
                    "source_revision": source_revision,
                    "source_state_hash": source_state_hash,
                    "assembly": pair_assembly,
                    "axis": binding.output_axis,
                    "moving_instance_ids": (moving,),
                    "stationary_instance_ids": (stationary,),
                    "start_angle_deg": effective_scope.angle_interval_deg[0],
                    "end_angle_deg": effective_scope.angle_interval_deg[1],
                    "required_clearance_mm": effective_scope.required_clearance_mm,
                    "proof_guard_mm": self.proof_guard_mm,
                    "max_depth": self.max_depth,
                    "minimum_interval_deg": self.minimum_interval_deg,
                    "max_exact_evaluations": self.max_exact_evaluations,
                }
                result = self.prove_continuous_single_axis_clearance(**kwargs)
                proof_request = ContinuousSingleAxisProofRequest(
                    source_assembly_id=pair_assembly.assembly_id,
                    source_assembly_hash=assembly_hash(pair_assembly),
                    axis=binding.output_axis,
                    start_angle_deg=effective_scope.angle_interval_deg[0],
                    end_angle_deg=effective_scope.angle_interval_deg[1],
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                    required_clearance_mm=effective_scope.required_clearance_mm,
                    proof_guard_mm=self.proof_guard_mm,
                    max_depth=self.max_depth,
                    minimum_interval_deg=self.minimum_interval_deg,
                    max_exact_evaluations=self.max_exact_evaluations,
                )
                result = ContinuousSingleAxisProofResult.model_validate(result.model_dump(mode="json"))
                self._validate_continuous_result(proof_request, result, pair_assembly)
                proofs.append(CandidateM10PairProof(
                    pair=classification.pair,
                    moving_instance_id=moving,
                    stationary_instance_id=stationary,
                    request=proof_request,
                    result=result,
                    request_hash=proof_request.request_hash,
                    result_hash=result.result_hash,
                ))
            elif classification.requires_home_exact_check:
                moving = next(
                    entry.cad_instance_id
                    for entry in (first_disposition, second_disposition)
                    if entry.disposition is CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED
                )
                stationary = second if moving == first else first
                pair_assembly = self._induced_pair_assembly(realization.assembly, moving, stationary)
                home_request = CadKinematicSweepRequest(
                    source_assembly_id=pair_assembly.assembly_id,
                    source_assembly_hash=assembly_hash(pair_assembly),
                    axis=binding.output_axis,
                    sample_angles_deg=(0.0,),
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                )
                result = self.analyze_assembly_kinematics(
                    source_revision=source_revision,
                    source_state_hash=source_state_hash,
                    assembly=pair_assembly,
                    axis=binding.output_axis,
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                    sample_angles_deg=(0.0,),
                )
                result = CadKinematicSweepResult.model_validate(result.model_dump(mode="json"))
                self._validate_home_result(home_request, result, pair_assembly)
                home_checks.append(CandidateHomeExactCheck(
                    pair=classification.pair,
                    moving_instance_id=moving,
                    stationary_instance_id=stationary,
                    request=home_request,
                    result=result,
                    request_hash=home_request.request_hash,
                    result_hash=result.result_hash,
                ))
                unresolved.append(CandidateM10StageReason.UNMODELED_CONTINUOUS_MOTION)
            elif classification.classification is CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE:
                unresolved.append(CandidateM10StageReason.UNMODELED_CONTINUOUS_MOTION)

        return CandidateM10StageOutcome(
            status=CandidateM10StageStatus.UNRESOLVED if unresolved else CandidateM10StageStatus.SUCCESS,
            candidate_hash=realization.candidate_hash,
            cad_realization_hash=realization.realization_hash,
            binding_hash=binding.binding_hash,
            scope_hash=effective_scope.scope_hash,
            evaluation_request_hash=request.request_hash,
            source_revision=source_revision,
            source_state_hash=source_state_hash,
            pair_proofs=tuple(proofs),
            home_exact_checks=tuple(home_checks),
            reasons=tuple(dict.fromkeys(unresolved)),
        )

    @staticmethod
    def _induced_pair_assembly(assembly: CadAssemblyProgram, first: str, second: str) -> CadAssemblyProgram:
        selected_ids = (first, second)
        instances_by_id = {instance.instance_id: instance for instance in assembly.instances}
        if any(instance_id not in instances_by_id for instance_id in selected_ids):
            raise ValueError("candidate M10 pair references an unknown CAD instance")
        selected = tuple(instances_by_id[instance_id] for instance_id in selected_ids)
        component_ids = {instance.part_id for instance in selected}
        parts = tuple(part for part in assembly.parts if part.part_id in component_ids)
        imported = tuple(component for component in assembly.imported_components if component.component_id in component_ids)
        pair_identity = hashlib.sha256(canonical_json({"assembly": assembly_hash(assembly), "pair": selected_ids})).hexdigest()[:20]
        return CadAssemblyProgram(
            assembly_id=f"{assembly.assembly_id}-m10-pair-{pair_identity}",
            parts=parts,
            imported_components=imported,
            instances=selected,
        )

    @staticmethod
    def _validate_request_against_binding_scope(
        request: CandidateM10EvaluationRequest,
        binding: CandidateM10Binding,
        scope: CandidateM10EvaluationScope,
    ) -> None:
        comparisons = (
            (request.candidate_hash, binding.candidate_hash, "candidate"),
            (request.cad_realization_hash, binding.cad_realization_hash, "CAD realization"),
            (request.binding_hash, binding.binding_hash, "binding"),
            (request.scope_hash, scope.scope_hash, "scope"),
            (request.model_hash, binding.model_hash, "model"),
            (request.inventory.binding_hash, binding.binding_hash, "inventory binding"),
            (request.inventory.scope_hash, scope.scope_hash, "inventory scope"),
        )
        for actual, expected, label in comparisons:
            if actual != expected:
                raise ValueError(f"M10 request {label} mismatch")
        expected_pairs = tuple(itertools.combinations(binding.cad_instance_ids, 2))
        if request.inventory.expected_pair_universe != expected_pairs:
            raise ValueError("M10 request pair universe mismatch")
        entry_by_cad = {
            entry.cad_instance_id: entry for entry in binding.constituent_dispositions
        }
        requirement_by_key_pair = {
            requirement.constituent_key_pair: requirement
            for requirement in scope.pair_scope_requirements
        }
        if len(requirement_by_key_pair) != len(scope.pair_scope_requirements):
            raise ValueError("M10 scope pair requirements must identify unique constituent pairs")
        for requirement in scope.pair_scope_requirements:
            if not {
                requirement.first_constituent_key,
                requirement.second_constituent_key,
            } <= {
                entry.constituent_key for entry in binding.constituent_dispositions
            }:
                raise ValueError(
                    f"M10 scope requirement has no candidate constituent: {requirement.requirement_key}"
                )
        actual_pairs = tuple(item.pair for item in request.inventory.classifications)
        if tuple(sorted(actual_pairs)) != expected_pairs:
            raise ValueError("M10 request pair inventory is incomplete")
        for item in request.inventory.classifications:
            first, second = (entry_by_cad[item.pair[0]], entry_by_cad[item.pair[1]])
            requirement = requirement_by_key_pair.get(
                tuple(sorted((first.constituent_key, second.constituent_key)))
            )
            if requirement is not None:
                if item.classification is not requirement.required_classification:
                    raise ValueError(
                        f"M10 request pair classification does not match scope: {requirement.requirement_key}"
                    )
                if item.requires_home_exact_check != requirement.requires_home_exact_check:
                    raise ValueError(
                        f"M10 request home-check semantics do not match scope: {requirement.requirement_key}"
                    )
            elif item.requires_home_exact_check or item.classification is CandidateM10PairClassification.CHECK_CLEARANCE:
                raise ValueError("M10 request contains an unsupported scoped pair classification")

    @staticmethod
    def _validate_continuous_result(request, result, assembly: CadAssemblyProgram | None = None) -> None:
        CandidateM10EvaluationService.CONTINUOUS_RESULT_VALIDATION.validate(
            request, result, assembly
        )

    @staticmethod
    def _validate_home_result(request, result, assembly: CadAssemblyProgram | None = None) -> None:
        CandidateM10EvaluationService.HOME_RESULT_VALIDATION.validate(request, result, assembly)


def _is_hash(value: str) -> bool:
    try:
        _require_hash(value)
    except (TypeError, ValueError):
        return False
    return True
