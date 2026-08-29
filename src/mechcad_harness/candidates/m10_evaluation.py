from __future__ import annotations

import hashlib
import itertools
import json
import math
from enum import StrEnum

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    assembly_hash,
)
from mechcad_harness.candidates.cad_realization import (
    CandidateCadRealization,
    CandidateCadStageOutcome,
    CandidateCadStageStatus,
    CandidateGeometryFidelity,
)
from mechcad_harness.continuous_proof import (
    CONTINUOUS_PROOF_ALGORITHM_VERSION,
    ContinuousSingleAxisProofRequest,
    ContinuousSingleAxisProofResult,
    ContinuousSingleAxisProofStatus,
)
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.kinematic_sweep import (
    CadKinematicSweepRequest,
    CadKinematicSweepResult,
    CollisionClassification,
    SweepAggregateClassification,
)
from mechcad_harness.models.common import Model
from mechcad_harness.multi_joint_kinematics import (
    KinematicModel,
    kinematic_model_hash,
    transform_apply,
)
from mechcad_harness.candidates.models import (
    MechanicalConnectionKind,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.state.hashing import canonical_json


def _hash(value: object, identity_field: str | None = None) -> str:
    payload = value.model_dump(mode="json") if isinstance(value, Model) else value
    payload = dict(payload)
    if identity_field is not None:
        payload.pop(identity_field, None)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


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


class CandidateM10PairClassification(StrEnum):
    CHECK_CLEARANCE = "check_clearance"
    INTENDED_CONTACT_EXCLUDED = "intended_contact_excluded"
    SAME_RIGID_GROUP_EXCLUDED = "same_rigid_group_excluded"
    UNMODELED_MOTION_OUT_OF_SCOPE = "unmodeled_motion_out_of_scope"
    OTHER_EXPLICIT_OUT_OF_SCOPE = "other_explicit_out_of_scope"


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
        dispositions = {
            entry.physical_instance_id: entry for entry in self.constituent_dispositions
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
            if self.driver_gear_constituent_key is None:
                raise ValueError("external-spur driver gear marker is required")
            if any(key != self.driver_gear_constituent_key for key in gear_drivers):
                raise ValueError("candidate M10 driver gear marker does not match candidate topology")

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


class CandidateM10StageStatus(StrEnum):
    SUCCESS = "success"
    UNRESOLVED = "unresolved"
    NOT_REACHED = "not_reached"


class CandidateM10StageReason(StrEnum):
    UNMODELED_CONTINUOUS_MOTION = "unmodeled_continuous_motion"
    PRIOR_STAGE_FAILED = "prior_stage_failed"


def _result_hash(result: object) -> str:
    if isinstance(result, Model):
        payload = result.model_dump(mode="json", exclude={"result_hash"})
    else:
        payload = dict(result)
    # Match the hash construction used by the accepted M10 result models.
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


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

    def evaluate(
        self,
        source_revision: int,
        source_state_hash: str,
        realization: CandidateCadRealization | CandidateCadStageOutcome,
        binding: CandidateM10Binding,
        request: CandidateM10EvaluationRequest,
        *,
        scope: CandidateM10EvaluationScope | None = None,
        physical_realization: PhysicalMechanismRealization | None = None,
    ) -> CandidateM10StageOutcome:
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
        if assembly is not None and request.source_assembly_hash != assembly_hash(assembly):
            raise ValueError("M10 continuous source assembly does not match induced assembly")
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
                raise ValueError(f"M10 continuous result {label} mismatch")
        expected_pairs = tuple(
            (moving, stationary)
            for moving in request.moving_instance_ids
            for stationary in request.stationary_instance_ids
        )
        for certificate in result.certified_leaf_certificates:
            certificate_pairs = tuple(
                (pair.moving_instance_id, pair.stationary_instance_id)
                for pair in certificate.pair_certificates
            )
            if certificate_pairs != expected_pairs:
                raise ValueError("M10 continuous certificate pair mismatch")
        if result.status is ContinuousSingleAxisProofStatus.COLLISION_WITNESS:
            if result.collision_witness is None:
                raise ValueError("M10 collision-witness result requires a witness")
        elif result.collision_witness is not None:
            raise ValueError("M10 non-collision result cannot carry a collision witness")
        if result.status is ContinuousSingleAxisProofStatus.VERIFIED_CLEAR and not result.certified_leaf_certificates:
            raise ValueError("M10 verified-clear result requires certificates")
        if result.collision_witness is not None:
            witness_pair = (
                result.collision_witness.moving_instance_id,
                result.collision_witness.stationary_instance_id,
            )
            if witness_pair not in expected_pairs:
                raise ValueError("M10 collision witness pair mismatch")
            if result.collision_witness.classification not in (
                CollisionClassification.INTERFERENCE,
                CollisionClassification.TOUCHING,
            ):
                raise ValueError("M10 collision witness classification mismatch")
        if result.result_hash != _result_hash(result):
            raise ValueError("M10 continuous result hash mismatch")

    @staticmethod
    def _validate_home_result(request, result, assembly: CadAssemblyProgram | None = None) -> None:
        if request.sample_angles_deg != (0.0,):
            raise ValueError("M10 home request must use exactly the zero-angle sample")
        from mechcad_harness.kinematic_sweep import RIGID_BODY_COLLISION_SWEEP_VERSION

        if request.sweep_version != RIGID_BODY_COLLISION_SWEEP_VERSION:
            raise ValueError("M10 home request uses an unsupported discrete sweep service")
        if result.sweep_version != RIGID_BODY_COLLISION_SWEEP_VERSION:
            raise ValueError("M10 home result uses an unsupported discrete sweep service")
        if result.request_hash != request.request_hash:
            raise ValueError("M10 home result request identity mismatch")
        if result.source_assembly_hash != request.source_assembly_hash:
            raise ValueError("M10 home result source assembly mismatch")
        if assembly is not None:
            from mechcad_harness.kinematic_sweep import transformed_assembly_program

            expected_transformed = assembly_hash(
                transformed_assembly_program(
                    assembly,
                    request.axis,
                    0.0,
                    request.moving_instance_ids,
                    request.stationary_instance_ids,
                )
            )
            if result.samples[0].transformed_assembly_hash != expected_transformed:
                raise ValueError("M10 home transformed assembly hash mismatch")
        if tuple(sample.angle_deg for sample in result.samples) != (0.0,):
            raise ValueError("M10 home result must contain exactly the zero-angle sample")
        expected_pairs = tuple(
            (moving, stationary)
            for moving in request.moving_instance_ids
            for stationary in request.stationary_instance_ids
        )
        sample = result.samples[0]
        actual_pairs = tuple(
            (pair.moving_instance_id, pair.stationary_instance_id)
            for pair in sample.pair_results
        )
        if actual_pairs != expected_pairs:
            raise ValueError("M10 home result pair mismatch")
        precedence = {
            CollisionClassification.POSITIVE_CLEARANCE: 0,
            CollisionClassification.TOUCHING: 1,
            CollisionClassification.INTERFERENCE: 2,
        }
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
            raise ValueError("M10 home result pair classification mismatch")
        expected_sample_classification = max(expected_pair_classifications, key=precedence.__getitem__)
        if sample.classification is not expected_sample_classification:
            raise ValueError("M10 home result sample classification mismatch")
        expected_aggregate = (
            SweepAggregateClassification.COLLISION_PRESENT
            if CollisionClassification.INTERFERENCE in expected_pair_classifications
            else SweepAggregateClassification.TOUCHING_PRESENT
            if CollisionClassification.TOUCHING in expected_pair_classifications
            else SweepAggregateClassification.COLLISION_FREE
        )
        if result.aggregate_classification is not expected_aggregate:
            raise ValueError("M10 home result aggregate classification mismatch")
        if result.result_hash != _result_hash(result):
            raise ValueError("M10 home result hash mismatch")


def _is_hash(value: str) -> bool:
    try:
        _require_hash(value)
    except (TypeError, ValueError):
        return False
    return True
