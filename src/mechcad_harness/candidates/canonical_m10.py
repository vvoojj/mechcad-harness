from __future__ import annotations

import hashlib
import itertools
import json
import math
from enum import StrEnum
from typing import Literal

from pydantic import (
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.candidates.canonical_cad import CanonicalCadRealization
from mechcad_harness.candidates.canonical_mechanism import CanonicalMechanismReconstruction
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
)
from mechcad_harness.kinematic_sweep import (
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CollisionClassification,
    RevoluteAxis,
    SweepAggregateClassification,
    transformed_assembly_program,
)
from mechcad_harness.models import (
    CanonicalConnectionMeaning,
    CanonicalGeometryFidelity,
    CanonicalMechanicalConnectionKind,
    CanonicalPhysicalComponentRole,
    CanonicalPhysicalPairRequirement,
)
from mechcad_harness.models.common import Model
from mechcad_harness.multi_joint_kinematics import (
    KinematicModel,
    RevoluteJointModel,
    kinematic_model_hash,
    transform_apply,
)
from mechcad_harness.state.hashing import canonical_json

from .promotion_models import PrePromotionM10ScopeProjection


def _hash_payload(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def _require_hash(value: str) -> str:
    if value == "pending":
        raise ValueError("must be a sha256 hash")
    if (
        len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError("must be a sha256 hash")
    return value


def _require_hash_or_pending(value: str) -> str:
    return value if value == "pending" else _require_hash(value)


def _hash_model(value: Model, identity_field: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(identity_field, None)
    return _hash_payload(payload)


def _result_hash(value: Model) -> str:
    payload = value.model_dump(mode="json", exclude={"result_hash"})
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _canonical_pair(pair: tuple[str, str]) -> tuple[str, str]:
    if len(pair) != 2 or pair[0] == pair[1] or any(not item.strip() for item in pair):
        raise ValueError("canonical M10 pair must contain two distinct instance IDs")
    return tuple(sorted(pair))


class CanonicalM10Model(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


# Canonical execution deliberately retains the accepted M10 proof statuses.
CanonicalM10VerificationStatus = ContinuousSingleAxisProofStatus


class CanonicalM10BodyDisposition(StrEnum):
    FIXED = "fixed"
    OUTPUT_RIGID = "output_rigid"
    INTERNAL_MOTION_UNMODELED = "internal_motion_unmodeled"


class CanonicalM10PairClassification(StrEnum):
    CHECK_CLEARANCE = "check_clearance"
    INTENDED_CONTACT_EXCLUDED = "intended_contact_excluded"
    SAME_RIGID_GROUP_EXCLUDED = "same_rigid_group_excluded"
    UNMODELED_MOTION_OUT_OF_SCOPE = "unmodeled_motion_out_of_scope"
    OTHER_EXPLICIT_OUT_OF_SCOPE = "other_explicit_out_of_scope"


class CanonicalM10ConstituentDisposition(CanonicalM10Model):
    schema_version: Literal["canonical-m10-constituent-disposition@1"] = (
        "canonical-m10-constituent-disposition@1"
    )
    physical_instance_id: StrictStr = Field(min_length=1)
    cad_instance_id: StrictStr = Field(min_length=1)
    disposition: CanonicalM10BodyDisposition
    output_transform_group: StrictStr | None = None
    disposition_hash: StrictStr = "pending"

    _validate_hash = field_validator("disposition_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_disposition(self) -> "CanonicalM10ConstituentDisposition":
        if self.disposition is CanonicalM10BodyDisposition.OUTPUT_RIGID:
            if self.output_transform_group is not None and not self.output_transform_group.strip():
                raise ValueError("canonical output transform group must not be empty")
        elif self.output_transform_group is not None:
            raise ValueError("only output-rigid canonical constituents may declare a transform group")
        expected = _hash_model(self, "disposition_hash")
        if self.disposition_hash == "pending":
            object.__setattr__(self, "disposition_hash", expected)
        elif self.disposition_hash != expected:
            raise ValueError("canonical M10 constituent disposition hash mismatch")
        return self


class CanonicalM10PairClassificationRecord(CanonicalM10Model):
    schema_version: Literal["canonical-m10-pair-classification@1"] = (
        "canonical-m10-pair-classification@1"
    )
    pair: tuple[StrictStr, StrictStr]
    classification: CanonicalM10PairClassification
    reason: StrictStr | None = None
    requires_home_exact_check: StrictBool = False
    classification_hash: StrictStr = "pending"

    _validate_hash = field_validator("classification_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_classification(self) -> "CanonicalM10PairClassificationRecord":
        pair = _canonical_pair(self.pair)
        if pair != self.pair:
            object.__setattr__(self, "pair", pair)
        if self.classification is CanonicalM10PairClassification.CHECK_CLEARANCE:
            if self.reason is not None:
                raise ValueError("checked canonical M10 pairs cannot carry an exclusion reason")
        elif self.reason is None or not self.reason.strip():
            raise ValueError("excluded canonical M10 pairs require an explicit reason")
        expected = _hash_model(self, "classification_hash")
        if self.classification_hash == "pending":
            object.__setattr__(self, "classification_hash", expected)
        elif self.classification_hash != expected:
            raise ValueError("canonical M10 pair classification hash mismatch")
        return self


class CanonicalM10PairInventory(CanonicalM10Model):
    schema_version: Literal["canonical-m10-pair-inventory@1"] = (
        "canonical-m10-pair-inventory@1"
    )
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    mechanism_id: StrictStr = Field(min_length=1)
    mechanism_hash: StrictStr
    cad_realization_hash: StrictStr
    scope_hash: StrictStr
    constituent_dispositions: tuple[CanonicalM10ConstituentDisposition, ...] = Field(min_length=1)
    expected_pair_universe: tuple[tuple[StrictStr, StrictStr], ...] = Field(min_length=1)
    classifications: tuple[CanonicalM10PairClassificationRecord, ...] = Field(min_length=1)
    checked_pairs: tuple[tuple[StrictStr, StrictStr], ...] = ()
    excluded_pairs: tuple[tuple[StrictStr, StrictStr], ...] = ()
    inventory_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "state_hash",
        "mechanism_hash",
        "cad_realization_hash",
        "scope_hash",
    )(_require_hash)
    _validate_inventory_hash = field_validator("inventory_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_inventory(self) -> "CanonicalM10PairInventory":
        expected_pairs = tuple(itertools.combinations(
            sorted(item.cad_instance_id for item in self.constituent_dispositions), 2
        ))
        if self.expected_pair_universe != expected_pairs:
            raise ValueError("canonical M10 pair universe is incomplete or unordered")
        actual_pairs = tuple(item.pair for item in self.classifications)
        if tuple(sorted(actual_pairs)) != expected_pairs or len(set(actual_pairs)) != len(actual_pairs):
            raise ValueError("canonical M10 pair inventory is incomplete")
        checked = tuple(sorted(
            item.pair
            for item in self.classifications
            if item.classification is CanonicalM10PairClassification.CHECK_CLEARANCE
        ))
        excluded = tuple(sorted(
            item.pair
            for item in self.classifications
            if item.classification is not CanonicalM10PairClassification.CHECK_CLEARANCE
        ))
        if self.checked_pairs != checked:
            raise ValueError("canonical M10 checked pair inventory mismatch")
        if self.excluded_pairs != excluded:
            raise ValueError("canonical M10 excluded pair inventory mismatch")
        expected = _hash_model(self, "inventory_hash")
        if self.inventory_hash == "pending":
            object.__setattr__(self, "inventory_hash", expected)
        elif self.inventory_hash != expected:
            raise ValueError("canonical M10 pair inventory hash mismatch")
        return self


class CanonicalM10EvaluationRequest(CanonicalM10Model):
    schema_version: Literal["canonical-m10-evaluation-request@1"] = (
        "canonical-m10-evaluation-request@1"
    )
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    mechanism_id: StrictStr = Field(min_length=1)
    mechanism_hash: StrictStr
    cad_realization_hash: StrictStr
    binding_semantic_hash: StrictStr
    model_hash: StrictStr
    mapping_hashes: tuple[StrictStr, ...] = Field(min_length=1)
    scope_hash: StrictStr
    inventory: CanonicalM10PairInventory
    request_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "state_hash",
        "mechanism_hash",
        "cad_realization_hash",
        "binding_semantic_hash",
        "model_hash",
        "scope_hash",
    )(_require_hash)
    _validate_request_hash = field_validator("request_hash")(_require_hash_or_pending)
    _validate_mapping_hashes = field_validator("mapping_hashes")(
        lambda values: tuple(_require_hash(value) for value in values)
    )

    @model_validator(mode="after")
    def validate_request(self) -> "CanonicalM10EvaluationRequest":
        if self.inventory.project_id != self.project_id or self.inventory.revision != self.revision:
            raise ValueError("canonical M10 request inventory revision binding mismatch")
        if self.inventory.state_hash != self.state_hash:
            raise ValueError("canonical M10 request inventory state binding mismatch")
        if self.inventory.mechanism_id != self.mechanism_id:
            raise ValueError("canonical M10 request inventory mechanism binding mismatch")
        if self.inventory.mechanism_hash != self.mechanism_hash:
            raise ValueError("canonical M10 request inventory mechanism hash mismatch")
        if self.inventory.cad_realization_hash != self.cad_realization_hash:
            raise ValueError("canonical M10 request CAD binding mismatch")
        if self.inventory.scope_hash != self.scope_hash:
            raise ValueError("canonical M10 request scope binding mismatch")
        expected = _hash_model(self, "request_hash")
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("canonical M10 evaluation request hash mismatch")
        return self


class CanonicalM10PairProof(CanonicalM10Model):
    schema_version: Literal["canonical-m10-pair-proof@1"] = "canonical-m10-pair-proof@1"
    pair: tuple[StrictStr, StrictStr]
    moving_instance_id: StrictStr = Field(min_length=1)
    stationary_instance_id: StrictStr = Field(min_length=1)
    request: ContinuousSingleAxisProofRequest
    result: ContinuousSingleAxisProofResult
    request_hash: StrictStr
    result_hash: StrictStr
    proof_hash: StrictStr = "pending"

    _validate_hashes = field_validator("request_hash", "result_hash")(_require_hash)
    _validate_proof_hash = field_validator("proof_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_proof(self) -> "CanonicalM10PairProof":
        pair = _canonical_pair(self.pair)
        if pair != self.pair or {self.moving_instance_id, self.stationary_instance_id} != set(pair):
            raise ValueError("canonical M10 proof pair does not match its partitions")
        if (
            self.request.moving_instance_ids != (self.moving_instance_id,)
            or self.request.stationary_instance_ids != (self.stationary_instance_id,)
            or self.result.moving_instance_ids != (self.moving_instance_id,)
            or self.result.stationary_instance_ids != (self.stationary_instance_id,)
        ):
            raise ValueError("canonical M10 proof embedded partitions do not match its pair")
        if self.request.request_hash != self.request_hash or self.result.request_hash != self.request_hash:
            raise ValueError("canonical M10 proof request identity mismatch")
        if self.result.result_hash != self.result_hash:
            raise ValueError("canonical M10 proof result identity mismatch")
        if self.result.result_hash != _result_hash(self.result):
            raise ValueError("canonical M10 proof result hash mismatch")
        expected = _hash_model(self, "proof_hash")
        if self.proof_hash == "pending":
            object.__setattr__(self, "proof_hash", expected)
        elif self.proof_hash != expected:
            raise ValueError("canonical M10 proof hash mismatch")
        return self


class CanonicalM10HomeExactCheck(CanonicalM10Model):
    schema_version: Literal["canonical-m10-home-exact-check@1"] = "canonical-m10-home-exact-check@1"
    pair: tuple[StrictStr, StrictStr]
    moving_instance_id: StrictStr = Field(min_length=1)
    stationary_instance_id: StrictStr = Field(min_length=1)
    request: CadKinematicSweepRequest
    result: CadKinematicSweepResult
    request_hash: StrictStr
    result_hash: StrictStr
    check_hash: StrictStr = "pending"

    _validate_hashes = field_validator("request_hash", "result_hash")(_require_hash)
    _validate_check_hash = field_validator("check_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_check(self) -> "CanonicalM10HomeExactCheck":
        pair = _canonical_pair(self.pair)
        if pair != self.pair or {self.moving_instance_id, self.stationary_instance_id} != set(pair):
            raise ValueError("canonical M10 home pair does not match its partitions")
        if (
            self.request.moving_instance_ids != (self.moving_instance_id,)
            or self.request.stationary_instance_ids != (self.stationary_instance_id,)
            or any(
                pair_result.moving_instance_id != self.moving_instance_id
                or pair_result.stationary_instance_id != self.stationary_instance_id
                for sample in self.result.samples
                for pair_result in sample.pair_results
            )
        ):
            raise ValueError("canonical M10 home embedded partitions do not match its pair")
        if self.request.sample_angles_deg != (0.0,):
            raise ValueError("canonical M10 home check must use the zero-angle sample")
        if self.result.sweep_version != self.request.sweep_version:
            raise ValueError("canonical M10 home request/result sweep version mismatch")
        if self.request.request_hash != self.request_hash or self.result.request_hash != self.request_hash:
            raise ValueError("canonical M10 home request identity mismatch")
        if self.result.result_hash != self.result_hash:
            raise ValueError("canonical M10 home result identity mismatch")
        if self.result.result_hash != _result_hash(self.result):
            raise ValueError("canonical M10 home result hash mismatch")
        expected = _hash_model(self, "check_hash")
        if self.check_hash == "pending":
            object.__setattr__(self, "check_hash", expected)
        elif self.check_hash != expected:
            raise ValueError("canonical M10 home check hash mismatch")
        return self


def _aggregate_status(proof_statuses, home_aggregates):
    if (
        ContinuousSingleAxisProofStatus.COLLISION_WITNESS in proof_statuses
        or any(
            aggregate is not SweepAggregateClassification.COLLISION_FREE
            for aggregate in home_aggregates
        )
    ):
        return CanonicalM10VerificationStatus.COLLISION_WITNESS
    if ContinuousSingleAxisProofStatus.NOT_PROVEN in proof_statuses:
        return CanonicalM10VerificationStatus.NOT_PROVEN
    return CanonicalM10VerificationStatus.VERIFIED_CLEAR


class DerivedCanonicalM10Scope(CanonicalM10Model):
    schema_version: Literal["derived-canonical-m10-scope@1"] = "derived-canonical-m10-scope@1"
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    mechanism_id: StrictStr = Field(min_length=1)
    mechanism_hash: StrictStr
    joint_semantic_key: StrictStr = Field(min_length=1)
    angle_interval_deg: tuple[float, float]
    path_semantics: StrictStr = "single_axis_interval"
    required_clearance_mm: float = Field(ge=0)
    physical_pair_requirements: tuple[CanonicalPhysicalPairRequirement, ...] = Field(min_length=1)
    fidelity_requirements: tuple[tuple[StrictStr, CanonicalGeometryFidelity], ...] = ()
    required_home_check_semantics: tuple[StrictStr, ...] = ()
    bounded_limitations: tuple[StrictStr, ...] = ()
    scope_hash: StrictStr = "pending"

    _validate_hashes = field_validator("state_hash", "mechanism_hash")(_require_hash)
    _validate_scope_hash = field_validator("scope_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_scope(self) -> "DerivedCanonicalM10Scope":
        if not all(math.isfinite(value) for value in self.angle_interval_deg):
            raise ValueError("canonical M10 interval must be finite")
        if self.angle_interval_deg[0] > self.angle_interval_deg[1]:
            raise ValueError("canonical M10 interval must be ordered")
        if any(not value.strip() for value in self.required_home_check_semantics + self.bounded_limitations):
            raise ValueError("canonical M10 scope semantic text must not be empty")
        keys = tuple(key for key, _ in self.fidelity_requirements)
        if len(set(keys)) != len(keys) or any(not key.strip() for key in keys):
            raise ValueError("canonical M10 fidelity keys must be unique and non-empty")
        semantic_payload = {
            "joint_semantic_key": self.joint_semantic_key,
            "angle_interval_deg": self.angle_interval_deg,
            "path_semantics": self.path_semantics,
            "required_clearance_mm": self.required_clearance_mm,
            "physical_pair_requirements": [
                item.model_dump(mode="json") for item in self.physical_pair_requirements
            ],
            "fidelity_requirements": [
                [key, fidelity.value] for key, fidelity in self.fidelity_requirements
            ],
            "required_home_check_semantics": self.required_home_check_semantics,
            "bounded_limitations": self.bounded_limitations,
        }
        expected = _hash_payload(semantic_payload)
        if self.scope_hash == "pending":
            object.__setattr__(self, "scope_hash", expected)
        elif self.scope_hash != expected:
            raise ValueError("canonical M10 scope hash mismatch")
        return self


class CanonicalM10ScopeEquivalenceResult(CanonicalM10Model):
    schema_version: Literal["canonical-m10-scope-equivalence-result@1"] = (
        "canonical-m10-scope-equivalence-result@1"
    )
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    frozen_projection_hash: StrictStr
    derived_scope_hash: StrictStr
    equivalent: StrictBool
    differences: tuple[StrictStr, ...] = ()
    result_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "state_hash", "frozen_projection_hash", "derived_scope_hash"
    )(_require_hash)
    _validate_result_hash = field_validator("result_hash")(_require_hash_or_pending)

    @model_validator(mode="after")
    def validate_result(self) -> "CanonicalM10ScopeEquivalenceResult":
        if self.equivalent != (not self.differences):
            raise ValueError("canonical M10 scope equivalence flag does not match differences")
        expected = _hash_model(self, "result_hash")
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected)
        elif self.result_hash != expected:
            raise ValueError("canonical M10 scope equivalence result hash mismatch")
        return self


class CanonicalM10VerificationOutcome(CanonicalM10Model):
    schema_version: Literal["canonical-m10-verification-outcome@1"] = (
        "canonical-m10-verification-outcome@1"
    )
    project_id: StrictStr = Field(min_length=1)
    revision: StrictInt = Field(gt=0)
    state_hash: StrictStr
    mechanism_id: StrictStr = Field(min_length=1)
    mechanism_hash: StrictStr
    cad_realization_hash: StrictStr
    scope: DerivedCanonicalM10Scope
    inventory: CanonicalM10PairInventory
    request: CanonicalM10EvaluationRequest
    status: CanonicalM10VerificationStatus
    pair_proofs: tuple[CanonicalM10PairProof, ...] = ()
    home_exact_checks: tuple[CanonicalM10HomeExactCheck, ...] = ()
    outcome_hash: StrictStr = "pending"

    _validate_hashes = field_validator(
        "state_hash", "mechanism_hash", "cad_realization_hash"
    )(_require_hash)
    _validate_outcome_hash = field_validator("outcome_hash")(_require_hash_or_pending)

    @property
    def evaluation_request(self) -> CanonicalM10EvaluationRequest:
        return self.request

    @model_validator(mode="after")
    def validate_outcome(self) -> "CanonicalM10VerificationOutcome":
        if self.scope.project_id != self.project_id or self.scope.revision != self.revision:
            raise ValueError("canonical M10 outcome scope binding mismatch")
        if self.scope.mechanism_id != self.mechanism_id:
            raise ValueError("canonical M10 outcome scope mechanism binding mismatch")
        if (
            self.inventory.project_id != self.project_id
            or self.inventory.revision != self.revision
            or self.scope.state_hash != self.state_hash
            or self.inventory.mechanism_id != self.mechanism_id
            or self.scope.mechanism_hash != self.mechanism_hash
            or self.inventory.state_hash != self.state_hash
            or self.inventory.mechanism_hash != self.mechanism_hash
            or self.request.project_id != self.project_id
            or self.request.revision != self.revision
            or self.request.state_hash != self.state_hash
            or self.request.mechanism_id != self.mechanism_id
            or self.request.mechanism_hash != self.mechanism_hash
            or self.request.cad_realization_hash != self.cad_realization_hash
            or self.inventory.cad_realization_hash != self.cad_realization_hash
            or self.request.scope_hash != self.scope.scope_hash
            or self.request.inventory != self.inventory
        ):
            raise ValueError("canonical M10 outcome execution binding mismatch")
        expected_proof_pairs = set(self.inventory.checked_pairs)
        actual_proof_pairs = tuple(proof.pair for proof in self.pair_proofs)
        if (
            len(actual_proof_pairs) != len(set(actual_proof_pairs))
            or set(actual_proof_pairs) != expected_proof_pairs
        ):
            raise ValueError("canonical M10 pair proofs do not exactly cover checked pairs")
        expected_home_pairs = {
            item.pair
            for item in self.inventory.classifications
            if item.requires_home_exact_check
        }
        actual_home_pairs = tuple(check.pair for check in self.home_exact_checks)
        if (
            len(actual_home_pairs) != len(set(actual_home_pairs))
            or set(actual_home_pairs) != expected_home_pairs
        ):
            raise ValueError("canonical M10 home checks do not exactly cover required pairs")
        for proof in self.pair_proofs:
            if (
                {proof.moving_instance_id, proof.stationary_instance_id} != set(proof.pair)
                or
                proof.request.moving_instance_ids != (proof.moving_instance_id,)
                or proof.request.stationary_instance_ids != (proof.stationary_instance_id,)
                or proof.result.moving_instance_ids != (proof.moving_instance_id,)
                or proof.result.stationary_instance_ids != (proof.stationary_instance_id,)
            ):
                raise ValueError("canonical M10 proof embedded partitions do not match its pair")
        for check in self.home_exact_checks:
            if (
                {check.moving_instance_id, check.stationary_instance_id} != set(check.pair)
                or
                check.request.moving_instance_ids != (check.moving_instance_id,)
                or check.request.stationary_instance_ids != (check.stationary_instance_id,)
                or any(
                    pair_result.moving_instance_id != check.moving_instance_id
                    or pair_result.stationary_instance_id != check.stationary_instance_id
                    for sample in check.result.samples
                    for pair_result in sample.pair_results
                )
            ):
                raise ValueError("canonical M10 home embedded partitions do not match its pair")
            if check.result.sweep_version != check.request.sweep_version:
                raise ValueError("canonical M10 home request/result sweep version mismatch")
        expected_status = _aggregate_status(
            [proof.result.status for proof in self.pair_proofs],
            [check.result.aggregate_classification for check in self.home_exact_checks],
        )
        if self.status is not expected_status:
            raise ValueError("canonical M10 outcome status is inconsistent with contained results")
        expected = _hash_model(self, "outcome_hash")
        if self.outcome_hash == "pending":
            object.__setattr__(self, "outcome_hash", expected)
        elif self.outcome_hash != expected:
            raise ValueError("canonical M10 outcome hash mismatch")
        return self


class CanonicalM10ScopeEquivalenceService:
    """Compare the frozen pre-promotion scope without participating in execution."""

    @staticmethod
    def compare(
        frozen_pre_promotion_scope_projection: PrePromotionM10ScopeProjection,
        derived_canonical_scope: DerivedCanonicalM10Scope,
    ) -> CanonicalM10ScopeEquivalenceResult:
        frozen = PrePromotionM10ScopeProjection.model_validate(
            frozen_pre_promotion_scope_projection.model_dump(mode="json")
        )
        derived = DerivedCanonicalM10Scope.model_validate(
            derived_canonical_scope.model_dump(mode="json")
        )
        differences: list[str] = []

        if frozen.joint_semantic_key != derived.joint_semantic_key:
            differences.append("joint_semantic_key")
        if frozen.angle_interval_deg != derived.angle_interval_deg:
            differences.append("angle_interval_deg")
        if frozen.path_semantics != derived.path_semantics:
            differences.append("path_semantics")
        if frozen.required_clearance_mm != derived.required_clearance_mm:
            differences.append("required_clearance_mm")

        canonical_prefix = f"{derived.mechanism_id}:"

        def normalized_instance_id(instance_id: str) -> str:
            return instance_id.removeprefix(canonical_prefix)

        frozen_pairs = tuple(
            (
                item.requirement_key,
                normalized_instance_id(item.first_instance_id),
                item.first_interface_id,
                normalized_instance_id(item.second_instance_id),
                item.second_interface_id,
                item.requires_home_exact_check,
            )
            for item in frozen.physical_pair_requirements
        )
        derived_pairs = tuple(
            (
                item.requirement_key,
                normalized_instance_id(item.first_instance_id),
                item.first_interface_id,
                normalized_instance_id(item.second_instance_id),
                item.second_interface_id,
                item.requires_home_exact_check,
            )
            for item in derived.physical_pair_requirements
        )
        if frozen_pairs != derived_pairs:
            differences.append("physical_pair_requirements")
        if tuple(
            (normalized_instance_id(key), fidelity.value)
            for key, fidelity in frozen.fidelity_requirements
        ) != tuple(
            (normalized_instance_id(key), fidelity.value)
            for key, fidelity in derived.fidelity_requirements
        ):
            differences.append("fidelity_requirements")
        if frozen.required_home_check_semantics != derived.required_home_check_semantics:
            differences.append("required_home_check_semantics")
        if frozen.bounded_limitations != derived.bounded_limitations:
            differences.append("bounded_limitations")

        return CanonicalM10ScopeEquivalenceResult(
            project_id=derived.project_id,
            revision=derived.revision,
            state_hash=derived.state_hash,
            frozen_projection_hash=frozen.projection_hash,
            derived_scope_hash=derived.scope_hash,
            equivalent=not differences,
            differences=tuple(differences),
        )


class CanonicalM10VerificationService:
    """Execute fresh M10 checks from canonical reconstruction and CAD only."""

    def __init__(
        self,
        application,
        *,
        proof_guard_mm: float = 1e-6,
        max_depth: int = 16,
        minimum_interval_deg: float = 1e-6,
        max_exact_evaluations: int = 4096,
    ) -> None:
        self.application = application
        self.proof_guard_mm = proof_guard_mm
        self.max_depth = max_depth
        self.minimum_interval_deg = minimum_interval_deg
        self.max_exact_evaluations = max_exact_evaluations

    def execute(
        self,
        reconstruction: CanonicalMechanismReconstruction,
        cad: CanonicalCadRealization,
    ) -> CanonicalM10VerificationOutcome:
        reconstruction = CanonicalMechanismReconstruction.model_validate(
            reconstruction.model_dump(mode="json")
        )
        cad = cad.validated_canonical_copy()
        mechanism = reconstruction.mechanism
        obligation, binding, model, axis, dispositions, scope = self._derive_canonical_inputs(
            reconstruction, cad
        )
        self._validate_cad_binding(reconstruction, cad)
        inventory = self._derive_inventory(reconstruction, cad, obligation, dispositions, scope)
        request = CanonicalM10EvaluationRequest(
            project_id=reconstruction.project_id,
            revision=reconstruction.revision,
            state_hash=reconstruction.state_hash,
            mechanism_id=mechanism.id,
            mechanism_hash=mechanism.mechanism_hash,
            cad_realization_hash=cad.realization_hash,
            binding_semantic_hash=binding.semantic_hash,
            model_hash=kinematic_model_hash(model),
            mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in cad.mappings)),
            scope_hash=scope.scope_hash,
            inventory=inventory,
        )

        proofs: list[CanonicalM10PairProof] = []
        home_checks: list[CanonicalM10HomeExactCheck] = []
        disposition_by_cad = {item.cad_instance_id: item for item in dispositions}
        for item in inventory.classifications:
            first, second = item.pair
            first_disposition = disposition_by_cad[first]
            second_disposition = disposition_by_cad[second]
            if item.classification is CanonicalM10PairClassification.CHECK_CLEARANCE:
                moving, stationary = self._directional_pair(first_disposition, second_disposition)
                pair_assembly = self._induced_pair_assembly(cad.assembly, moving, stationary)
                kwargs = {
                    "source_revision": reconstruction.revision,
                    "source_state_hash": reconstruction.state_hash,
                    "assembly": pair_assembly,
                    "axis": axis,
                    "moving_instance_ids": (moving,),
                    "stationary_instance_ids": (stationary,),
                    "start_angle_deg": scope.angle_interval_deg[0],
                    "end_angle_deg": scope.angle_interval_deg[1],
                    "required_clearance_mm": scope.required_clearance_mm,
                    "proof_guard_mm": self.proof_guard_mm,
                    "max_depth": self.max_depth,
                    "minimum_interval_deg": self.minimum_interval_deg,
                    "max_exact_evaluations": self.max_exact_evaluations,
                }
                raw_result = self.application.prove_continuous_single_axis_clearance(**kwargs)
                proof_request = ContinuousSingleAxisProofRequest(
                    source_assembly_id=pair_assembly.assembly_id,
                    source_assembly_hash=assembly_hash(pair_assembly),
                    axis=axis,
                    start_angle_deg=scope.angle_interval_deg[0],
                    end_angle_deg=scope.angle_interval_deg[1],
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                    required_clearance_mm=scope.required_clearance_mm,
                    proof_guard_mm=self.proof_guard_mm,
                    max_depth=self.max_depth,
                    minimum_interval_deg=self.minimum_interval_deg,
                    max_exact_evaluations=self.max_exact_evaluations,
                )
                result = ContinuousSingleAxisProofResult.model_validate(
                    raw_result.model_dump(mode="json")
                )
                self._validate_continuous_result(proof_request, result, pair_assembly)
                proofs.append(CanonicalM10PairProof(
                    pair=item.pair,
                    moving_instance_id=moving,
                    stationary_instance_id=stationary,
                    request=proof_request,
                    result=result,
                    request_hash=proof_request.request_hash,
                    result_hash=result.result_hash,
                ))

            if item.requires_home_exact_check:
                moving, stationary = self._home_directional_pair(
                    first_disposition, second_disposition
                )
                pair_assembly = self._induced_pair_assembly(cad.assembly, moving, stationary)
                home_request = CadKinematicSweepRequest(
                    source_assembly_id=pair_assembly.assembly_id,
                    source_assembly_hash=assembly_hash(pair_assembly),
                    axis=axis,
                    sample_angles_deg=(0.0,),
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                )
                raw_result = self.application.analyze_assembly_kinematics(
                    source_revision=reconstruction.revision,
                    source_state_hash=reconstruction.state_hash,
                    assembly=pair_assembly,
                    axis=axis,
                    moving_instance_ids=(moving,),
                    stationary_instance_ids=(stationary,),
                    sample_angles_deg=(0.0,),
                )
                result = CadKinematicSweepResult.model_validate(
                    raw_result.model_dump(mode="json")
                )
                self._validate_home_result(home_request, result, pair_assembly)
                home_checks.append(CanonicalM10HomeExactCheck(
                    pair=item.pair,
                    moving_instance_id=moving,
                    stationary_instance_id=stationary,
                    request=home_request,
                    result=result,
                    request_hash=home_request.request_hash,
                    result_hash=result.result_hash,
                ))
        status = _aggregate_status(
            [proof.result.status for proof in proofs],
            [check.result.aggregate_classification for check in home_checks],
        )
        return CanonicalM10VerificationOutcome(
            project_id=reconstruction.project_id,
            revision=reconstruction.revision,
            state_hash=reconstruction.state_hash,
            mechanism_id=mechanism.id,
            mechanism_hash=mechanism.mechanism_hash,
            cad_realization_hash=cad.realization_hash,
            scope=scope,
            inventory=inventory,
            request=request,
            status=status,
            pair_proofs=tuple(proofs),
            home_exact_checks=tuple(home_checks),
        )

    @staticmethod
    def _validate_cad_binding(
        reconstruction: CanonicalMechanismReconstruction,
        cad: CanonicalCadRealization,
    ) -> None:
        if (
            cad.project_id != reconstruction.project_id
            or cad.revision != reconstruction.revision
            or cad.state_hash != reconstruction.state_hash
            or cad.mechanism_id != reconstruction.mechanism.id
            or cad.mechanism_hash != reconstruction.mechanism.mechanism_hash
        ):
            raise ValueError("canonical M10 CAD does not match canonical reconstruction")
        physical_ids = {component.instance_id for component in reconstruction.mechanism.components}
        mapped_ids = {mapping.physical_instance_id for mapping in cad.mappings}
        if mapped_ids != physical_ids:
            raise ValueError("canonical M10 CAD mappings do not cover canonical components")

    def _derive_canonical_inputs(self, reconstruction, cad):
        mechanism = reconstruction.mechanism
        if len(mechanism.m10_obligations) != 1:
            raise ValueError("canonical M10 requires exactly one verification obligation")
        obligation = mechanism.m10_obligations[0]
        bindings = tuple(
            binding for binding in mechanism.joint_bindings
            if binding.joint_id == obligation.joint_semantic_key
        )
        if len(bindings) != 1:
            raise ValueError("canonical M10 joint binding is missing or ambiguous")
        binding = bindings[0]
        expected_semantic_hash = self._joint_semantic_hash(binding)
        if binding.semantic_hash != expected_semantic_hash:
            raise ValueError("canonical M10 joint semantic hash does not match canonical meaning")

        mapping_by_physical = {mapping.physical_instance_id: mapping for mapping in cad.mappings}
        parent_mapping = mapping_by_physical.get(binding.expected_parent_instance_id)
        child_mapping = mapping_by_physical.get(binding.expected_child_instance_id)
        if parent_mapping is None or child_mapping is None:
            raise ValueError("canonical M10 joint parent or child is missing from CAD")
        axis = self._world_axis(binding, parent_mapping.placement)
        joint = RevoluteJointModel(
            joint_id=binding.joint_id,
            parent_instance_id=parent_mapping.cad_instance_id,
            child_instance_id=child_mapping.cad_instance_id,
            axis_origin_x_mm=binding.axis_origin_x_mm,
            axis_origin_y_mm=binding.axis_origin_y_mm,
            axis_origin_z_mm=binding.axis_origin_z_mm,
            axis_direction_x=binding.axis_direction_x,
            axis_direction_y=binding.axis_direction_y,
            axis_direction_z=binding.axis_direction_z,
        )
        model = KinematicModel(
            model_id=f"canonical-m10-{mechanism.id}-{binding.joint_id}",
            joints=(joint,),
        )

        dispositions = self._derive_dispositions(
            mechanism,
            binding,
            {physical_id: mapping.cad_instance_id for physical_id, mapping in mapping_by_physical.items()},
        )

        scope = DerivedCanonicalM10Scope(
            project_id=reconstruction.project_id,
            revision=reconstruction.revision,
            state_hash=reconstruction.state_hash,
            mechanism_id=mechanism.id,
            mechanism_hash=mechanism.mechanism_hash,
            joint_semantic_key=obligation.joint_semantic_key,
            angle_interval_deg=obligation.angle_interval_deg,
            required_clearance_mm=obligation.required_clearance_mm,
            physical_pair_requirements=obligation.physical_pair_requirements,
            fidelity_requirements=obligation.fidelity_requirements,
            required_home_check_semantics=obligation.required_home_check_semantics,
            bounded_limitations=obligation.bounded_limitations,
        )
        for physical_id, fidelity in obligation.fidelity_requirements:
            mapping = mapping_by_physical.get(physical_id)
            if mapping is None or mapping.fidelity is not fidelity:
                raise ValueError("canonical M10 CAD fidelity does not satisfy the obligation")
        return obligation, binding, model, axis, tuple(dispositions), scope

    @staticmethod
    def _derive_dispositions(mechanism, binding, cad_instance_by_physical=None):
        cad_instance_by_physical = cad_instance_by_physical or {}
        component_by_id = {component.instance_id: component for component in mechanism.components}
        gear_driver_ids = {
            connection.from_instance_id
            for connection in mechanism.connections
            if connection.kind is CanonicalMechanicalConnectionKind.GEAR_MESH
            and component_by_id[connection.from_instance_id].role
            is CanonicalPhysicalComponentRole.TRANSMISSION
        }
        reachable = {binding.expected_child_instance_id}
        frontier = [binding.expected_child_instance_id]
        while frontier:
            current = frontier.pop()
            for connection in mechanism.connections:
                if connection.kind is CanonicalMechanicalConnectionKind.GEAR_MESH:
                    continue
                if CanonicalConnectionMeaning.KINEMATIC_REALIZATION_INTENT not in connection.meanings:
                    continue
                if connection.from_instance_id == current:
                    neighbor = connection.to_instance_id
                elif connection.to_instance_id == current:
                    neighbor = connection.from_instance_id
                else:
                    continue
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    frontier.append(neighbor)

        fixed_roles = {
            CanonicalPhysicalComponentRole.ACTUATOR,
            CanonicalPhysicalComponentRole.BEARING,
            CanonicalPhysicalComponentRole.MOUNT_OR_SUPPORT,
        }
        output_ids = {
            instance_id
            for instance_id in reachable
            if instance_id == binding.expected_child_instance_id
            or component_by_id[instance_id].role not in fixed_roles
        }
        return tuple(
            CanonicalM10ConstituentDisposition(
                physical_instance_id=component.instance_id,
                cad_instance_id=cad_instance_by_physical.get(
                    component.instance_id, component.instance_id
                ),
                disposition=(
                    CanonicalM10BodyDisposition.INTERNAL_MOTION_UNMODELED
                    if component.instance_id in gear_driver_ids
                    else CanonicalM10BodyDisposition.OUTPUT_RIGID
                    if component.instance_id in output_ids
                    else CanonicalM10BodyDisposition.FIXED
                ),
                output_transform_group=(
                    binding.joint_id
                    if component.instance_id in output_ids and component.instance_id not in gear_driver_ids
                    else None
                ),
            )
            for component in mechanism.components
        )

    @staticmethod
    def _joint_semantic_hash(binding) -> str:
        return _hash_payload({
            "joint_id": binding.joint_id,
            "joint_kind": "revolute",
            "parent_instance_id": binding.expected_parent_instance_id,
            "child_instance_id": binding.expected_child_instance_id,
            "axis_origin": [
                binding.axis_origin_x_mm,
                binding.axis_origin_y_mm,
                binding.axis_origin_z_mm,
            ],
            "axis_direction": [
                binding.axis_direction_x,
                binding.axis_direction_y,
                binding.axis_direction_z,
            ],
            "semantic_version": binding.semantic_version,
        })

    @staticmethod
    def _world_axis(binding, parent_placement) -> RevoluteAxis:
        origin = transform_apply(
            parent_placement,
            (binding.axis_origin_x_mm, binding.axis_origin_y_mm, binding.axis_origin_z_mm),
        )
        direction_point = transform_apply(
            parent_placement,
            (
                binding.axis_origin_x_mm + binding.axis_direction_x,
                binding.axis_origin_y_mm + binding.axis_direction_y,
                binding.axis_origin_z_mm + binding.axis_direction_z,
            ),
        )
        return RevoluteAxis(
            origin_x_mm=origin[0],
            origin_y_mm=origin[1],
            origin_z_mm=origin[2],
            direction_x=direction_point[0] - origin[0],
            direction_y=direction_point[1] - origin[1],
            direction_z=direction_point[2] - origin[2],
            frame_id=f"joint:{binding.joint_id}",
        )

    @staticmethod
    def _derive_inventory(reconstruction, cad, obligation, dispositions, scope):
        mechanism = reconstruction.mechanism
        mapping_by_physical = {mapping.physical_instance_id: mapping for mapping in cad.mappings}
        disposition_by_physical = {item.physical_instance_id: item for item in dispositions}
        requirement_by_pair = {}
        for requirement in obligation.physical_pair_requirements:
            key = tuple(sorted((requirement.first_instance_id, requirement.second_instance_id)))
            if key in requirement_by_pair:
                raise ValueError("canonical M10 pair requirements must identify unique physical pairs")
            requirement_by_pair[key] = requirement
        gear_pairs = {
            tuple(sorted((connection.from_instance_id, connection.to_instance_id)))
            for connection in mechanism.connections
            if connection.kind is CanonicalMechanicalConnectionKind.GEAR_MESH
        }
        component_by_id = {component.instance_id: component for component in mechanism.components}
        classifications = []
        cad_ids = tuple(sorted(mapping.cad_instance_id for mapping in cad.mappings))
        for first, second in itertools.combinations(cad_ids, 2):
            first_physical = next(
                mapping.physical_instance_id for mapping in cad.mappings if mapping.cad_instance_id == first
            )
            second_physical = next(
                mapping.physical_instance_id for mapping in cad.mappings if mapping.cad_instance_id == second
            )
            physical_pair = tuple(sorted((first_physical, second_physical)))
            requirement = requirement_by_pair.get(physical_pair)
            if physical_pair in gear_pairs:
                if requirement is not None:
                    raise ValueError("canonical M10 cannot require clearance across a gear mesh")
                record = CanonicalM10PairClassificationRecord(
                    pair=(first, second),
                    classification=CanonicalM10PairClassification.INTENDED_CONTACT_EXCLUDED,
                    reason="declared gear mesh interface is outside M10 scope",
                )
            elif requirement is not None:
                first_disposition = disposition_by_physical[first_physical]
                second_disposition = disposition_by_physical[second_physical]
                if {first_disposition.disposition, second_disposition.disposition} != {
                    CanonicalM10BodyDisposition.FIXED,
                    CanonicalM10BodyDisposition.OUTPUT_RIGID,
                }:
                    raise ValueError("canonical M10 clearance pair must contain one fixed and one output-rigid body")
                record = CanonicalM10PairClassificationRecord(
                    pair=(first, second),
                    classification=CanonicalM10PairClassification.CHECK_CLEARANCE,
                    requires_home_exact_check=requirement.requires_home_exact_check,
                )
            elif any(
                item.disposition is CanonicalM10BodyDisposition.INTERNAL_MOTION_UNMODELED
                for item in (
                    disposition_by_physical[first_physical],
                    disposition_by_physical[second_physical],
                )
            ):
                record = CanonicalM10PairClassificationRecord(
                    pair=(first, second),
                    classification=CanonicalM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE,
                    reason="internal driver motion is outside M10 scope",
                )
            elif all(
                item.disposition is CanonicalM10BodyDisposition.OUTPUT_RIGID
                and item.output_transform_group == scope.joint_semantic_key
                for item in (
                    disposition_by_physical[first_physical],
                    disposition_by_physical[second_physical],
                )
            ):
                record = CanonicalM10PairClassificationRecord(
                    pair=(first, second),
                    classification=CanonicalM10PairClassification.SAME_RIGID_GROUP_EXCLUDED,
                    reason="both constituents share the accepted output rigid transform",
                )
            else:
                record = CanonicalM10PairClassificationRecord(
                    pair=(first, second),
                    classification=CanonicalM10PairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE,
                    reason="not required by the canonical M10 engineering obligation",
                )
            classifications.append(record)
        expected_pairs = tuple(itertools.combinations(cad_ids, 2))
        return CanonicalM10PairInventory(
            project_id=reconstruction.project_id,
            revision=reconstruction.revision,
            state_hash=reconstruction.state_hash,
            mechanism_id=mechanism.id,
            mechanism_hash=mechanism.mechanism_hash,
            cad_realization_hash=cad.realization_hash,
            scope_hash=scope.scope_hash,
            constituent_dispositions=dispositions,
            expected_pair_universe=expected_pairs,
            classifications=tuple(classifications),
            checked_pairs=tuple(sorted(
                item.pair for item in classifications
                if item.classification is CanonicalM10PairClassification.CHECK_CLEARANCE
            )),
            excluded_pairs=tuple(sorted(
                item.pair for item in classifications
                if item.classification is not CanonicalM10PairClassification.CHECK_CLEARANCE
            )),
        )

    @staticmethod
    def _directional_pair(first, second) -> tuple[str, str]:
        if first.disposition is CanonicalM10BodyDisposition.OUTPUT_RIGID and second.disposition is CanonicalM10BodyDisposition.FIXED:
            return first.cad_instance_id, second.cad_instance_id
        if second.disposition is CanonicalM10BodyDisposition.OUTPUT_RIGID and first.disposition is CanonicalM10BodyDisposition.FIXED:
            return second.cad_instance_id, first.cad_instance_id
        raise ValueError("canonical M10 clearance pair has no unique moving/stationary direction")

    @staticmethod
    def _home_directional_pair(first, second) -> tuple[str, str]:
        if first.disposition is CanonicalM10BodyDisposition.INTERNAL_MOTION_UNMODELED:
            return first.cad_instance_id, second.cad_instance_id
        if second.disposition is CanonicalM10BodyDisposition.INTERNAL_MOTION_UNMODELED:
            return second.cad_instance_id, first.cad_instance_id
        return CanonicalM10VerificationService._directional_pair(first, second)

    @staticmethod
    def _induced_pair_assembly(assembly: CadAssemblyProgram, moving: str, stationary: str):
        selected_ids = (moving, stationary)
        instances_by_id = {instance.instance_id: instance for instance in assembly.instances}
        if any(instance_id not in instances_by_id for instance_id in selected_ids):
            raise ValueError("canonical M10 pair references an unknown CAD instance")
        selected = tuple(instances_by_id[instance_id] for instance_id in selected_ids)
        component_ids = {instance.part_id for instance in selected}
        pair_identity = _hash_payload({"assembly": assembly_hash(assembly), "pair": selected_ids})[7:27]
        return CadAssemblyProgram(
            assembly_id=f"{assembly.assembly_id}-canonical-m10-pair-{pair_identity}",
            parts=tuple(part for part in assembly.parts if part.part_id in component_ids),
            imported_components=tuple(
                component for component in assembly.imported_components
                if component.component_id in component_ids
            ),
            instances=selected,
        )

    @staticmethod
    def _validate_continuous_result(request, result, assembly):
        if request.source_assembly_id != assembly.assembly_id or request.source_assembly_hash != assembly_hash(assembly):
            raise ValueError("canonical M10 continuous source assembly mismatch")
        comparisons = (
            (result.request_hash, request.request_hash, "request"),
            (result.source_assembly_hash, request.source_assembly_hash, "source assembly"),
            (result.axis, request.axis, "axis"),
            (result.start_angle_deg, request.start_angle_deg, "path"),
            (result.end_angle_deg, request.end_angle_deg, "path"),
            (result.moving_instance_ids, request.moving_instance_ids, "moving partition"),
            (result.stationary_instance_ids, request.stationary_instance_ids, "stationary partition"),
            (result.required_clearance_mm, request.required_clearance_mm, "clearance"),
            (result.proof_guard_mm, request.proof_guard_mm, "proof guard"),
            (result.proof_algorithm_version, CONTINUOUS_PROOF_ALGORITHM_VERSION, "algorithm version"),
        )
        for actual, expected, label in comparisons:
            if actual != expected:
                raise ValueError(f"canonical M10 continuous result {label} mismatch")
        expected_pairs = tuple(
            (moving, stationary)
            for moving in request.moving_instance_ids
            for stationary in request.stationary_instance_ids
        )
        for certificate in result.certified_leaf_certificates:
            actual_pairs = tuple(
                (pair.moving_instance_id, pair.stationary_instance_id)
                for pair in certificate.pair_certificates
            )
            if actual_pairs != expected_pairs:
                raise ValueError("canonical M10 continuous certificate pair mismatch")
        if result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS:
            if result.collision_witness is None:
                raise ValueError("canonical M10 collision witness is missing")
            witness_pair = (
                result.collision_witness.moving_instance_id,
                result.collision_witness.stationary_instance_id,
            )
            if witness_pair not in expected_pairs:
                raise ValueError("canonical M10 collision witness pair mismatch")
        elif result.collision_witness is not None:
            raise ValueError("canonical M10 non-collision result carries a witness")
        if result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR and not result.certified_leaf_certificates:
            raise ValueError("canonical M10 verified-clear result requires certificates")
        if result.result_hash != _result_hash(result):
            raise ValueError("canonical M10 continuous result hash mismatch")

    @staticmethod
    def _validate_home_result(request, result, assembly):
        if request.sample_angles_deg != (0.0,):
            raise ValueError("canonical M10 home request must use exactly zero angle")
        if result.request_hash != request.request_hash or result.source_assembly_hash != request.source_assembly_hash:
            raise ValueError("canonical M10 home result identity mismatch")
        if tuple(sample.angle_deg for sample in result.samples) != (0.0,):
            raise ValueError("canonical M10 home result must contain one zero-angle sample")
        expected_transformed = assembly_hash(
            transformed_assembly_program(
                assembly, request.axis, 0.0, request.moving_instance_ids, request.stationary_instance_ids
            )
        )
        sample = result.samples[0]
        if sample.transformed_assembly_hash != expected_transformed:
            raise ValueError("canonical M10 home transformed assembly mismatch")
        expected_pairs = tuple(
            (moving, stationary)
            for moving in request.moving_instance_ids
            for stationary in request.stationary_instance_ids
        )
        actual_pairs = tuple(
            (pair.moving_instance_id, pair.stationary_instance_id)
            for pair in sample.pair_results
        )
        if actual_pairs != expected_pairs:
            raise ValueError("canonical M10 home result pair mismatch")
        expected_pair_classifications = tuple(
            CollisionClassification.from_measurement(
                pair.interference_volume_mm3,
                pair.exact_distance_mm,
                volume_tolerance_mm3=request.volume_tolerance_mm3,
                distance_tolerance_mm=request.distance_tolerance_mm,
            )
            for pair in sample.pair_results
        )
        if tuple(pair.classification for pair in sample.pair_results) != expected_pair_classifications:
            raise ValueError("canonical M10 home pair classification mismatch")
        precedence = {
            CollisionClassification.POSITIVE_CLEARANCE: 0,
            CollisionClassification.TOUCHING: 1,
            CollisionClassification.INTERFERENCE: 2,
        }
        if sample.classification is not max(expected_pair_classifications, key=precedence.__getitem__):
            raise ValueError("canonical M10 home sample classification mismatch")
        expected_aggregate = (
            SweepAggregateClassification.COLLISION_PRESENT
            if CollisionClassification.INTERFERENCE in expected_pair_classifications
            else SweepAggregateClassification.TOUCHING_PRESENT
            if CollisionClassification.TOUCHING in expected_pair_classifications
            else SweepAggregateClassification.COLLISION_FREE
        )
        if result.aggregate_classification is not expected_aggregate:
            raise ValueError("canonical M10 home aggregate classification mismatch")
        if result.result_hash != _result_hash(result):
            raise ValueError("canonical M10 home result hash mismatch")

__all__ = [
    "CanonicalM10BodyDisposition",
    "CanonicalM10ConstituentDisposition",
    "CanonicalM10EvaluationRequest",
    "CanonicalM10HomeExactCheck",
    "CanonicalM10PairClassification",
    "CanonicalM10PairClassificationRecord",
    "CanonicalM10PairInventory",
    "CanonicalM10PairProof",
    "CanonicalM10ScopeEquivalenceResult",
    "CanonicalM10ScopeEquivalenceService",
    "CanonicalM10VerificationOutcome",
    "CanonicalM10VerificationService",
    "CanonicalM10VerificationStatus",
    "DerivedCanonicalM10Scope",
]
