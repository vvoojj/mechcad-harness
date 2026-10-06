from __future__ import annotations

import hashlib
from typing import Literal, NamedTuple

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.cad_assembly import M10_EXECUTION_SEMANTICS_VERSION, _require_semantic_fields
from mechcad_harness.candidates.cad_realization import CandidateCadRealizationV2
from mechcad_harness.candidates.models import (
    CandidateSynthesisRequest,
    candidate_hash_v2,
    candidate_synthesis_request_hash_v2,
    physical_kinematic_root_hash,
    semantic_candidate_mechanism_hash,
)
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    PhysicalToM10V2BridgeV2,
    semantic_physical_revolute_joint_binding_hash_v2,
    validate_physical_to_m10_v2_bridge_v2,
)
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
from mechcad_harness.semantic_m10_kinematics import (
    semantic_m10_v2_request_hash,
    semantic_m10_v2_result_hash,
)

from .models import MechanicalDesignCandidate, candidate_hash
from .multi_joint_m10_evaluation import (
    CandidateMultiJointM10Evaluation,
    CandidateMultiJointM10EvaluationV2,
    CandidateMultiJointM10EvaluationRequest,
    CandidateMultiJointM10EvaluationRequestV2,
    CandidateMultiJointM10EvaluationScope,
    CandidateMultiJointM10EvaluationService,
    CandidateMultiJointM10ReplayV2,
    candidate_multi_joint_m10_evaluation_hash_v2,
)
from .services import CandidateCurrentness


def _digest(payload: object) -> str:
    encoded = canonical_json_bytes(payload)
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


class CandidateMultiJointSelectionV2(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-multi-joint-selection@2"] = (
        "candidate-multi-joint-selection@2"
    )
    project_id: str = Field(min_length=1)
    source_revision: int = Field(gt=0)
    source_state_hash: str
    semantic_source_binding_hash: str
    candidate_hash: str
    evaluation_hash: str
    candidate_request_hash: str
    semantic_m10_v2_request_hash: str
    semantic_m10_v2_result_hash: str
    physical_to_m10_bridge_hash: str
    semantic_kinematic_model_hash: str
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
        "source_state_hash", "semantic_source_binding_hash", "candidate_hash",
        "evaluation_hash", "candidate_request_hash", "semantic_m10_v2_request_hash",
        "semantic_m10_v2_result_hash", "physical_to_m10_bridge_hash",
        "semantic_kinematic_model_hash", "physical_pair_classification_set_hash",
        "inventory_hash", "exact_pair_scope_hash", "scope_hash",
        "configuration_set_hash",
    )(_require_hash)
    _validate_selection_text = field_validator(
        "selector_identity", "rationale"
    )(_require_nonblank)
    _validate_selection_hash = field_validator("selection_hash")(
        lambda value: value if value == "pending" else _require_hash(value)
    )

    @model_validator(mode="after")
    def validate_selection_v2(self):
        expected = candidate_multi_joint_selection_hash_v2(self)
        if self.selection_hash == "pending":
            object.__setattr__(self, "selection_hash", expected)
        elif self.selection_hash != expected:
            raise ValueError("candidate multi-joint selection@2 hash mismatch")
        return self


def candidate_multi_joint_selection_hash_v2(
    selection: CandidateMultiJointSelectionV2,
) -> str:
    _require_semantic_fields(
        selection,
        CandidateMultiJointSelectionV2,
        {
            "schema_version", "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "candidate_hash", "evaluation_hash",
            "candidate_request_hash", "semantic_m10_v2_request_hash",
            "semantic_m10_v2_result_hash", "physical_to_m10_bridge_hash",
            "semantic_kinematic_model_hash", "physical_pair_classification_set_hash",
            "inventory_hash", "exact_pair_scope_hash", "scope_hash",
            "configuration_set_hash", "selector_identity", "rationale", "selection_hash",
        },
        "CandidateMultiJointSelectionV2",
    )
    return _digest(
        {
            "semantic_projection_version": M10_EXECUTION_SEMANTICS_VERSION,
            "schema_version": selection.schema_version,
            "project_id": selection.project_id,
            "semantic_source_binding_hash": selection.semantic_source_binding_hash,
            "candidate_hash": selection.candidate_hash,
            "evaluation_hash": selection.evaluation_hash,
            "candidate_request_hash": selection.candidate_request_hash,
            "semantic_m10_v2_request_hash": selection.semantic_m10_v2_request_hash,
            "semantic_m10_v2_result_hash": selection.semantic_m10_v2_result_hash,
            "physical_to_m10_bridge_hash": selection.physical_to_m10_bridge_hash,
            "semantic_kinematic_model_hash": selection.semantic_kinematic_model_hash,
            "physical_pair_classification_set_hash": selection.physical_pair_classification_set_hash,
            "inventory_hash": selection.inventory_hash,
            "exact_pair_scope_hash": selection.exact_pair_scope_hash,
            "scope_hash": selection.scope_hash,
            "configuration_set_hash": selection.configuration_set_hash,
            "selector_identity": selection.selector_identity,
            "rationale": selection.rationale,
        }
    )


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

        if candidate.schema_version == "mechanical-design-candidate@2":
            raise ValueError("candidate@2 multi-joint selection requires selection@2")
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

    @staticmethod
    def _validate_chain_v2(
        candidate: MechanicalDesignCandidate,
        synthesis_request: CandidateSynthesisRequest,
        request: CandidateMultiJointM10EvaluationRequestV2,
        evaluation: CandidateMultiJointM10EvaluationV2,
    ):
        if type(candidate) is not MechanicalDesignCandidate:
            raise TypeError("candidate multi-joint @2 selection requires a typed candidate")
        if type(synthesis_request) is not CandidateSynthesisRequest:
            raise TypeError("candidate multi-joint @2 selection requires a typed synthesis request")
        if type(request) is not CandidateMultiJointM10EvaluationRequestV2:
            raise TypeError("candidate multi-joint @2 selection requires request@2")
        if type(evaluation) is not CandidateMultiJointM10EvaluationV2:
            raise TypeError("candidate multi-joint @2 selection requires evaluation@2")
        candidate = MechanicalDesignCandidate.model_validate(
            candidate.model_dump(mode="json")
        )
        validated_synthesis_request = CandidateSynthesisRequest.model_validate(
            synthesis_request.model_dump(mode="json")
        )
        request = CandidateMultiJointM10EvaluationRequestV2.model_validate(
            request.model_dump(mode="json")
        )
        evaluation = CandidateMultiJointM10EvaluationV2.model_validate(
            evaluation.model_dump(mode="json")
        )
        if candidate.schema_version != "mechanical-design-candidate@2":
            raise ValueError("candidate multi-joint @2 selection requires candidate@2")
        if synthesis_request.schema_version != "candidate-synthesis-request@2":
            raise ValueError("candidate multi-joint @2 selection requires request@2")
        if (
            candidate.source_binding != synthesis_request.source_binding
            or candidate.semantic_source_binding_hash
            != synthesis_request.semantic_source_binding_hash
            or candidate.synthesis_request_hash != synthesis_request.request_hash
        ):
            raise ValueError("candidate/request@2 binding mismatch")
        if candidate_hash_v2(candidate) != candidate.candidate_hash:
            raise ValueError("candidate@2 hash mismatch")
        if candidate_synthesis_request_hash_v2(synthesis_request) != synthesis_request.request_hash:
            raise ValueError("synthesis request@2 hash mismatch")
        source = candidate.source_binding
        if request.project_id != source.project_id:
            raise ValueError("candidate multi-joint @2 project binding mismatch")
        if request.source_revision != source.source_revision:
            raise ValueError("candidate multi-joint @2 source revision mismatch")
        if request.source_state_hash != source.source_state_hash:
            raise ValueError("candidate multi-joint @2 source state mismatch")
        if request.semantic_source_binding_hash != candidate.semantic_source_binding_hash:
            raise ValueError("candidate multi-joint @2 semantic source binding mismatch")
        realization = candidate.realization
        if realization.schema_version != "physical-mechanism-realization@2":
            raise ValueError("candidate multi-joint @2 requires physical realization@2")
        if request.candidate_hash != candidate.candidate_hash:
            raise ValueError("candidate multi-joint @2 candidate reference mismatch")
        if request.physical_mechanism_hash != semantic_candidate_mechanism_hash(realization):
            raise ValueError("candidate multi-joint @2 physical mechanism mismatch")
        expected_body_hashes = tuple(
            sorted(item.binding_hash for item in realization.physical_rigid_body_bindings)
        )
        if request.physical_body_binding_hashes != expected_body_hashes:
            raise ValueError("candidate multi-joint @2 physical body binding mismatch")
        expected_joint_hashes = tuple(
            semantic_physical_revolute_joint_binding_hash_v2(item)
            for item in sorted(
                realization.physical_revolute_joint_bindings,
                key=lambda item: item.physical_joint_id,
            )
        )
        if request.physical_joint_binding_hashes != expected_joint_hashes:
            raise ValueError("candidate multi-joint @2 physical joint binding mismatch")
        if request.kinematic_root_binding_hash != realization.kinematic_root_binding_hash:
            raise ValueError("candidate multi-joint @2 kinematic root mismatch")
        if request.physical_pair_classification_set_hash != physical_pair_classification_set_hash(
            realization.physical_pair_classification_bindings
        ):
            raise ValueError("candidate multi-joint @2 physical pair policy mismatch")

        scope = CandidateMultiJointM10EvaluationScope.model_validate(
            request.scope.model_dump(mode="json")
        )
        if request.configuration_set_hash != scope.configuration_set.configuration_set_hash:
            raise ValueError("candidate multi-joint @2 configuration-set mismatch")
        if request.configuration_hashes != scope.configuration_set.configuration_hashes:
            raise ValueError("candidate multi-joint @2 configuration order mismatch")
        request_evaluation_fields = (
            "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "candidate_hash", "candidate_request_hash",
            "semantic_m10_v2_request_hash", "cad_realization_hash",
            "physical_to_m10_bridge_hash", "semantic_kinematic_model_hash",
            "physical_pair_classification_set_hash", "inventory_hash",
            "exact_pair_scope_hash", "scope_hash", "configuration_set_hash",
        )
        for field in request_evaluation_fields:
            request_value = (
                request.request_hash
                if field == "candidate_request_hash"
                else getattr(request, field)
            )
            if getattr(evaluation, field) != request_value:
                raise ValueError(f"candidate multi-joint @2 evaluation {field} mismatch")
        if evaluation.candidate_request_hash != request.request_hash:
            raise ValueError("candidate multi-joint @2 evaluation request identity mismatch")
        evaluation.validate_against(request)
        return candidate, synthesis_request, request, evaluation

    def _select_v2(
        self,
        candidate,
        synthesis_request,
        request,
        evaluation,
        selector_identity,
        rationale,
    ) -> CandidateMultiJointSelectionV2:
        candidate, synthesis_request, request, evaluation = self._validate_chain_v2(
            candidate, synthesis_request, request, evaluation
        )
        if request.project_id != self.project_id:
            raise ValueError("candidate multi-joint @2 selection project mismatch")
        try:
            currentness = self.currentness_verifier.evaluate_source_binding(
                candidate, synthesis_request=synthesis_request
            )
        except Exception as exc:
            raise ValueError(
                f"candidate multi-joint @2 selection currentness verification failed: {exc}"
            ) from exc
        if currentness is not CandidateCurrentness.CURRENT:
            value = getattr(currentness, "value", currentness)
            raise ValueError(f"candidate multi-joint @2 selection requires current source: {value}")

        try:
            replay = self.result_replayer(
                candidate, synthesis_request, request, evaluation
            )
        except Exception as exc:
            raise ValueError(f"candidate multi-joint @2 trusted replay failed: {exc}") from exc
        if type(replay) is not CandidateMultiJointM10ReplayV2:
            raise ValueError("candidate multi-joint @2 replay must retain CAD and bridge context")
        cad_realization = CandidateCadRealizationV2.model_validate(
            replay.cad_realization.model_dump(mode="json")
        )
        bridge = PhysicalToM10V2BridgeV2.model_validate(
            replay.bridge.model_dump(mode="json")
        )
        placement_derivations = request.placement_derivations
        validate_physical_to_m10_v2_bridge_v2(
            bridge,
            candidate=candidate,
            cad_realization=cad_realization,
            placement_derivations=placement_derivations,
        )
        reconstructed = CandidateMultiJointM10EvaluationService._reconstruct_m10_request_v2(
            bridge, cad_realization, request.scope
        )
        if type(replay.request) is not MultiJointCollisionSweepRequestV2:
            raise ValueError("candidate multi-joint @2 replay request must be low-level request@2")
        replay_request = MultiJointCollisionSweepRequestV2.model_validate(
            replay.request.model_dump(mode="json")
        )
        result = MultiJointCollisionSweepResultV2.model_validate(
            replay.result.model_dump(mode="json")
        )
        if replay_request != reconstructed:
            raise ValueError("candidate multi-joint @2 replay request differs from reconstruction")
        if semantic_m10_v2_request_hash(
            replay_request, cad_realization.assembly, cad_realization.mappings
        ) != request.semantic_m10_v2_request_hash:
            raise ValueError("candidate multi-joint @2 replay P5 identity mismatch")
        semantic_result = semantic_m10_v2_result_hash(
            result,
            replay_request,
            cad_realization.assembly,
            cad_realization.mappings,
        )
        if semantic_result != evaluation.semantic_m10_v2_result_hash:
            raise ValueError("candidate multi-joint @2 replay P6 identity mismatch")
        if result.result_hash != multi_joint_collision_sweep_result_v2_hash(result):
            raise ValueError("candidate multi-joint @2 replay raw M10 result hash mismatch")

        return CandidateMultiJointSelectionV2(
            project_id=request.project_id,
            source_revision=request.source_revision,
            source_state_hash=request.source_state_hash,
            semantic_source_binding_hash=request.semantic_source_binding_hash,
            candidate_hash=candidate.candidate_hash,
            evaluation_hash=evaluation.evaluation_hash,
            candidate_request_hash=request.request_hash,
            semantic_m10_v2_request_hash=request.semantic_m10_v2_request_hash,
            semantic_m10_v2_result_hash=evaluation.semantic_m10_v2_result_hash,
            physical_to_m10_bridge_hash=request.physical_to_m10_bridge_hash,
            semantic_kinematic_model_hash=request.semantic_kinematic_model_hash,
            physical_pair_classification_set_hash=request.physical_pair_classification_set_hash,
            inventory_hash=request.inventory_hash,
            exact_pair_scope_hash=request.exact_pair_scope_hash,
            scope_hash=request.scope_hash,
            configuration_set_hash=request.configuration_set_hash,
            selector_identity=selector_identity,
            rationale=rationale,
        )

    @staticmethod
    def _validate_chain_v2(
        candidate,
        synthesis_request,
        request,
        evaluation,
    ):
        candidate = _revalidate(candidate, MechanicalDesignCandidate, "candidate")
        if candidate.schema_version != "mechanical-design-candidate@2":
            raise ValueError("candidate multi-joint M10 @2 requires candidate@2")
        if type(synthesis_request) is not CandidateSynthesisRequest:
            raise TypeError("candidate multi-joint M10 @2 requires typed synthesis request@2")
        validated_synthesis_request = CandidateSynthesisRequest.model_validate(
            synthesis_request.model_dump(mode="json")
        )
        if synthesis_request.schema_version != "candidate-synthesis-request@2":
            raise ValueError("candidate multi-joint M10 @2 rejects synthesis request@1")
        if validated_synthesis_request != synthesis_request:
            raise ValueError("candidate multi-joint M10 synthesis request@2 reconstruction mismatch")
        if candidate_hash_v2(candidate) != candidate.candidate_hash:
            raise ValueError("candidate@2 hash mismatch")
        if candidate_synthesis_request_hash_v2(synthesis_request) != synthesis_request.request_hash:
            raise ValueError("synthesis request@2 hash mismatch")
        if (
            candidate.source_binding != synthesis_request.source_binding
            or candidate.semantic_source_binding_hash
            != synthesis_request.semantic_source_binding_hash
            or candidate.synthesis_request_hash != synthesis_request.request_hash
        ):
            raise ValueError("candidate/request@2 semantic binding mismatch")
        request = _revalidate(
            request,
            CandidateMultiJointM10EvaluationRequestV2,
            "candidate multi-joint M10 request@2",
        )
        evaluation = _revalidate(
            evaluation,
            CandidateMultiJointM10EvaluationV2,
            "candidate multi-joint M10 evaluation@2",
        )
        realization = candidate.realization
        comparisons = (
            (request.project_id, synthesis_request.source_binding.project_id, "project"),
            (request.source_revision, synthesis_request.source_binding.source_revision, "source revision"),
            (request.source_state_hash, synthesis_request.source_binding.source_state_hash, "source state"),
            (request.semantic_source_binding_hash, candidate.semantic_source_binding_hash, "semantic source binding"),
            (request.candidate_hash, candidate.candidate_hash, "candidate"),
            (
                request.physical_mechanism_hash,
                semantic_candidate_mechanism_hash(realization),
                "physical mechanism",
            ),
            (
                request.physical_body_binding_hashes,
                tuple(sorted(item.binding_hash for item in realization.physical_rigid_body_bindings)),
                "physical body binding",
            ),
            (
                request.physical_joint_binding_hashes,
                tuple(
                    semantic_physical_revolute_joint_binding_hash_v2(item)
                    for item in sorted(
                        realization.physical_revolute_joint_bindings,
                        key=lambda item: item.physical_joint_id,
                    )
                ),
                "physical joint binding",
            ),
            (request.kinematic_root_binding_hash, realization.kinematic_root_binding_hash, "kinematic root"),
            (
                request.physical_pair_classification_set_hash,
                physical_pair_classification_set_hash(realization.physical_pair_classification_bindings),
                "physical pair policy",
            ),
        )
        for actual, expected, label in comparisons:
            if actual != expected:
                raise ValueError(f"candidate multi-joint @2 {label} binding mismatch")
        scope = CandidateMultiJointM10EvaluationScope.model_validate(
            request.scope.model_dump(mode="json")
        )
        config_set = MultiJointVerificationConfigurationSet.model_validate(
            scope.configuration_set.model_dump(mode="json")
        )
        if (
            request.scope_hash != scope.scope_hash
            or request.configuration_set_hash != config_set.configuration_set_hash
            or request.configuration_hashes != config_set.configuration_hashes
        ):
            raise ValueError("candidate multi-joint @2 scope/configuration binding mismatch")
        evaluation_fields = (
            "project_id", "source_revision", "source_state_hash",
            "semantic_source_binding_hash", "candidate_hash", "semantic_m10_v2_request_hash",
            "cad_realization_hash", "physical_to_m10_bridge_hash",
            "semantic_kinematic_model_hash", "physical_pair_classification_set_hash",
            "inventory_hash", "exact_pair_scope_hash", "scope_hash",
            "configuration_set_hash",
        )
        for field in evaluation_fields:
            if getattr(evaluation, field) != getattr(request, field):
                raise ValueError(f"candidate multi-joint @2 evaluation {field} mismatch")
        if evaluation.candidate_request_hash != request.request_hash:
            raise ValueError("candidate multi-joint @2 evaluation request hash mismatch")
        evaluation.validate_against(request)
        return candidate, synthesis_request, request, evaluation

    def select(
        self,
        candidate: MechanicalDesignCandidate,
        request: CandidateMultiJointM10EvaluationRequest,
        evaluation: CandidateMultiJointM10Evaluation,
        selector_identity: str,
        rationale: str,
        *,
        synthesis_request=None,
    ) -> CandidateMultiJointSelection | CandidateMultiJointSelectionV2:
        if (
            getattr(candidate, "schema_version", None) == "mechanical-design-candidate@2"
            or getattr(request, "schema_version", None)
            == "candidate-multi-joint-m10-evaluation-request@2"
        ):
            return self._select_v2(
                candidate,
                synthesis_request,
                request,
                evaluation,
                selector_identity,
                rationale,
            )
        if synthesis_request is not None:
            raise ValueError("legacy multi-joint selection cannot carry synthesis request@2")
        candidate, request, evaluation = self._validate_chain(
            candidate, request, evaluation
        )
        if request.project_id != self.project_id:
            raise ValueError("candidate multi-joint selection project binding mismatch")
        try:
            if candidate.schema_version == "mechanical-design-candidate@2":
                if (
                    synthesis_request is None
                    or synthesis_request.schema_version != "candidate-synthesis-request@2"
                ):
                    raise ValueError("candidate@2 selection requires synthesis request@2")
                currentness = self.currentness_verifier.evaluate_source_binding(
                    candidate, synthesis_request=synthesis_request
                )
            elif synthesis_request is not None:
                raise ValueError("legacy candidate selection cannot carry request@2")
            else:
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
