from __future__ import annotations

import hashlib
import json
from typing import Literal, NamedTuple

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.models.common import Model
from mechcad_harness.models.multi_joint_verification import (
    MultiJointVerificationConfigurationSet,
)
from mechcad_harness.models.physical_pair_policy import (
    physical_pair_classification_set_hash,
)
from mechcad_harness.multi_joint_collision_sweep import (
    MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION,
    MultiJointCollisionSweepRequestV2,
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.multi_joint_kinematics import joint_configuration_hash
from mechcad_harness.multi_joint_pair_scope import exact_pair_scope_hash

from .models import MechanicalDesignCandidate, candidate_hash
from .multi_joint_m10_evaluation import (
    CandidateMultiJointM10Evaluation,
    CandidateMultiJointM10EvaluationRequest,
)
from .services import CandidateCurrentness


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


def _require_nonblank(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _revalidate(value, expected_type, label):
    if type(value) is not expected_type:
        raise ValueError(f"{label} must be a typed {expected_type.__name__}")
    try:
        return expected_type.model_validate(value.model_dump(mode="json"))
    except Exception as exc:
        raise ValueError(f"{label} failed integrity validation: {exc}") from exc


def _hash_model(value: Model, identity_field: str) -> str:
    payload = value.model_dump(mode="json")
    payload.pop(identity_field, None)
    return _digest(payload)


class CandidateMultiJointSelection(Model):
    """An immutable candidate multi-joint M10 selection, not canonical state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-multi-joint-selection@1"] = (
        "candidate-multi-joint-selection@1"
    )
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str
    source_binding_hash: str
    candidate_hash: str
    evaluation_hash: str
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
    selector_identity: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    selection_hash: str = "pending"

    _validate_project_id = field_validator("project_id")(_require_nonblank)
    _validate_hashes = field_validator(
        "source_state_hash",
        "source_binding_hash",
        "candidate_hash",
        "evaluation_hash",
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
    _validate_selection_text = field_validator(
        "selector_identity", "rationale"
    )(_require_nonblank)
    _validate_selection_hash = field_validator("selection_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_selection(self) -> "CandidateMultiJointSelection":
        expected = candidate_multi_joint_selection_hash(self)
        if self.selection_hash == "pending":
            object.__setattr__(self, "selection_hash", expected)
        elif self.selection_hash != expected:
            raise ValueError("candidate multi-joint selection hash mismatch")
        return self


def candidate_multi_joint_selection_hash(
    selection: CandidateMultiJointSelection,
) -> str:
    return _hash_model(selection, "selection_hash")


class CandidateMultiJointM10Replay(NamedTuple):
    """Transient trusted replay output; neither member enters selection state."""

    request: MultiJointCollisionSweepRequestV2
    result: MultiJointCollisionSweepResultV2


class CandidateMultiJointSelectionService:
    """Validate one complete candidate M10-3 chain before recording selection.

    ``result_replayer`` is a trusted adapter over candidate CAD and bridge
    inputs. It must reconstruct the v2 request and return it with its typed
    result; selection validates both members independently.
    """

    def __init__(
        self,
        *,
        project_id: str,
        currentness_verifier=None,
        result_replayer=None,
    ):
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("candidate multi-joint selection requires a non-empty project binding")
        if currentness_verifier is None:
            raise ValueError(
                "candidate multi-joint selection requires a currentness verifier"
            )
        if not callable(result_replayer):
            raise ValueError(
                "candidate multi-joint selection requires a trusted result replayer"
            )
        self.project_id = project_id
        self.currentness_verifier = currentness_verifier
        self.result_replayer = result_replayer

    @staticmethod
    def selection_hash(selection: CandidateMultiJointSelection) -> str:
        return candidate_multi_joint_selection_hash(selection)

    @staticmethod
    def _validate_chain(
        candidate: MechanicalDesignCandidate,
        request: CandidateMultiJointM10EvaluationRequest,
        evaluation: CandidateMultiJointM10Evaluation,
    ) -> tuple[
        MechanicalDesignCandidate,
        CandidateMultiJointM10EvaluationRequest,
        CandidateMultiJointM10Evaluation,
    ]:
        candidate = _revalidate(candidate, MechanicalDesignCandidate, "candidate")
        request = _revalidate(
            request,
            CandidateMultiJointM10EvaluationRequest,
            "candidate multi-joint M10 request",
        )
        evaluation = _revalidate(
            evaluation,
            CandidateMultiJointM10Evaluation,
            "candidate multi-joint M10 evaluation",
        )

        if candidate.candidate_hash != candidate_hash(candidate):
            raise ValueError("candidate multi-joint selection candidate hash mismatch")
        source_binding_hash = _digest(candidate.source_binding.model_dump(mode="json"))
        source = candidate.source_binding
        if request.project_id != source.project_id:
            raise ValueError("candidate multi-joint selection project binding mismatch")
        if request.source_revision != source.source_revision:
            raise ValueError("candidate multi-joint selection source revision mismatch")
        if request.source_state_hash != source.source_state_hash:
            raise ValueError("candidate multi-joint selection source state hash mismatch")
        if request.source_binding_hash != source_binding_hash:
            raise ValueError("candidate multi-joint selection source binding mismatch")
        if request.candidate_hash != candidate.candidate_hash:
            raise ValueError("candidate multi-joint selection candidate binding mismatch")
        realization = candidate.realization
        if request.physical_mechanism_hash != realization.realization_hash:
            raise ValueError(
                "candidate multi-joint selection physical mechanism binding mismatch"
            )
        expected_body_hashes = tuple(
            sorted(binding.binding_hash for binding in realization.physical_rigid_body_bindings)
        )
        if request.physical_body_binding_hashes != expected_body_hashes:
            raise ValueError(
                "candidate multi-joint selection physical body binding mismatch"
            )
        expected_joint_hashes = tuple(
            sorted(binding.binding_hash for binding in realization.physical_revolute_joint_bindings)
        )
        if request.physical_joint_binding_hashes != expected_joint_hashes:
            raise ValueError(
                "candidate multi-joint selection physical joint binding mismatch"
            )
        if request.kinematic_root_binding_hash != realization.kinematic_root_binding_hash:
            raise ValueError(
                "candidate multi-joint selection kinematic root binding mismatch"
            )
        expected_pair_hash = physical_pair_classification_set_hash(
            realization.physical_pair_classification_bindings
        )
        if request.physical_pair_classification_set_hash != expected_pair_hash:
            raise ValueError(
                "candidate multi-joint selection physical pair policy binding mismatch"
            )

        scope = request.scope
        configuration_set = MultiJointVerificationConfigurationSet.model_validate(
            scope.configuration_set.model_dump(mode="json")
        )
        if scope.configuration_set != configuration_set:
            raise ValueError("candidate multi-joint selection configuration set replay mismatch")
        if request.scope_hash != scope.scope_hash:
            raise ValueError("candidate multi-joint selection scope binding mismatch")
        if request.configuration_set_hash != configuration_set.configuration_set_hash:
            raise ValueError(
                "candidate multi-joint selection configuration-set binding mismatch"
            )
        if request.configuration_hashes != configuration_set.configuration_hashes:
            raise ValueError(
                "candidate multi-joint selection configuration identities mismatch"
            )

        request_fields = (
            "project_id",
            "source_revision",
            "source_state_hash",
            "source_binding_hash",
            "candidate_hash",
            "m10_v2_request_hash",
            "physical_to_m10_bridge_hash",
            "m10_model_hash",
            "physical_pair_classification_set_hash",
            "inventory_hash",
            "exact_pair_scope_hash",
            "scope_hash",
            "configuration_set_hash",
        )
        for field in request_fields:
            if getattr(evaluation, field) != getattr(request, field):
                raise ValueError(
                    f"candidate multi-joint selection evaluation {field} binding mismatch"
                )
        if evaluation.candidate_request_hash != request.request_hash:
            raise ValueError(
                "candidate multi-joint selection evaluation request binding mismatch"
            )

        return candidate, request, evaluation

    def select(
        self,
        candidate: MechanicalDesignCandidate,
        request: CandidateMultiJointM10EvaluationRequest,
        evaluation: CandidateMultiJointM10Evaluation,
        selector_identity: str,
        rationale: str,
    ) -> CandidateMultiJointSelection:
        candidate, request, evaluation = self._validate_chain(
            candidate, request, evaluation
        )
        if request.project_id != self.project_id:
            raise ValueError("candidate multi-joint selection project binding mismatch")
        try:
            currentness = self.currentness_verifier.evaluate_source_binding(candidate)
        except Exception as exc:
            raise ValueError(
                f"candidate multi-joint selection currentness verification failed: {exc}"
            ) from exc
        if currentness is not CandidateCurrentness.CURRENT:
            value = getattr(currentness, "value", currentness)
            raise ValueError(f"candidate multi-joint selection requires current source: {value}")

        try:
            replay = self.result_replayer(candidate, request, evaluation)
        except Exception as exc:
            raise ValueError(
                f"candidate multi-joint selection trusted M10 replay failed: {exc}"
            ) from exc
        if type(replay) is not CandidateMultiJointM10Replay:
            raise ValueError(
                "candidate multi-joint selection replay must contain a typed request and result"
            )
        replayed_request = _revalidate(
            replay.request,
            MultiJointCollisionSweepRequestV2,
            "replayed M10 v2 request",
        )
        result = _revalidate(
            replay.result,
            MultiJointCollisionSweepResultV2,
            "replayed M10 v2 result",
        )
        if replayed_request.request_hash != request.m10_v2_request_hash:
            raise ValueError(
                "candidate multi-joint selection replay request identity mismatch"
            )
        if replayed_request.model_hash != request.m10_model_hash:
            raise ValueError(
                "candidate multi-joint selection replay request model binding mismatch"
            )
        if replayed_request.evaluator_version != MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION:
            raise ValueError(
                "candidate multi-joint selection replay request evaluator binding mismatch"
            )
        if replayed_request.configurations != request.scope.configuration_set.configurations:
            raise ValueError(
                "candidate multi-joint selection replay request configuration binding mismatch"
            )
        if replayed_request.volume_tolerance_mm3 != request.scope.volume_tolerance_mm3:
            raise ValueError(
                "candidate multi-joint selection replay request volume tolerance mismatch"
            )
        if replayed_request.distance_tolerance_mm != request.scope.distance_tolerance_mm:
            raise ValueError(
                "candidate multi-joint selection replay request distance tolerance mismatch"
            )
        if exact_pair_scope_hash(replayed_request.exact_pair_scope) != request.exact_pair_scope_hash:
            raise ValueError(
                "candidate multi-joint selection replay request pair scope mismatch"
            )
        if result.request_hash != replayed_request.request_hash:
            raise ValueError(
                "candidate multi-joint selection replay result request binding mismatch"
            )
        if result.model_hash != replayed_request.model_hash:
            raise ValueError(
                "candidate multi-joint selection replay result model binding mismatch"
            )
        if result.source_assembly_hash != replayed_request.source_assembly_hash:
            raise ValueError(
                "candidate multi-joint selection replay result assembly binding mismatch"
            )
        if result.evaluator_version != replayed_request.evaluator_version:
            raise ValueError(
                "candidate multi-joint selection replay result evaluator binding mismatch"
            )
        _require_hash(replayed_request.source_assembly_hash)
        expected_configuration_hashes = tuple(
            joint_configuration_hash(configuration)
            for configuration in replayed_request.configurations
        )
        actual_configuration_hashes = tuple(
            item.configuration_hash for item in result.configuration_results
        )
        if actual_configuration_hashes != expected_configuration_hashes:
            raise ValueError(
                "candidate multi-joint selection replay result configuration binding mismatch"
            )
        if result.result_hash != multi_joint_collision_sweep_result_v2_hash(result):
            raise ValueError("candidate multi-joint selection replay result hash mismatch")
        if result.result_hash != evaluation.m10_v2_result_hash:
            raise ValueError(
                "candidate multi-joint selection replay result does not match evaluation"
            )

        return CandidateMultiJointSelection(
            project_id=request.project_id,
            source_revision=request.source_revision,
            source_state_hash=request.source_state_hash,
            source_binding_hash=request.source_binding_hash,
            candidate_hash=request.candidate_hash,
            evaluation_hash=evaluation.evaluation_hash,
            candidate_request_hash=request.request_hash,
            m10_v2_request_hash=request.m10_v2_request_hash,
            m10_v2_result_hash=evaluation.m10_v2_result_hash,
            physical_to_m10_bridge_hash=request.physical_to_m10_bridge_hash,
            m10_model_hash=request.m10_model_hash,
            physical_pair_classification_set_hash=request.physical_pair_classification_set_hash,
            inventory_hash=request.inventory_hash,
            exact_pair_scope_hash=request.exact_pair_scope_hash,
            scope_hash=request.scope_hash,
            configuration_set_hash=request.configuration_set_hash,
            selector_identity=selector_identity,
            rationale=rationale,
        )


__all__ = [
    "CandidateMultiJointM10Replay",
    "CandidateMultiJointSelection",
    "CandidateMultiJointSelectionService",
    "candidate_multi_joint_selection_hash",
]
