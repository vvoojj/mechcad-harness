from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from typing import Literal, Mapping

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.models.common import Model
from mechcad_harness.state.hashing import canonical_json

from .evaluation import (
    CandidateEvaluation,
    CandidateEvaluationOutcome,
    CandidateMetricKey,
)
from .models import MechanicalDesignCandidate, candidate_hash


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


class CandidateComparisonModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CandidateComparisonDirection(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class CandidateComparisonPolicy(CandidateComparisonModel):
    schema_version: Literal["candidate-comparison-policy@1"] = "candidate-comparison-policy@1"
    metric_keys: tuple[CandidateMetricKey, ...] = (
        CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,
    )
    directions: tuple[CandidateComparisonDirection, ...] = (
        CandidateComparisonDirection.MAXIMIZE,
    )
    expected_units: tuple[Literal["mm"], ...] = ("mm",)
    required_outcome: Literal[CandidateEvaluationOutcome.FEASIBLE] = CandidateEvaluationOutcome.FEASIBLE
    missing_metric_behavior: Literal["reject"] = "reject"
    tie_semantics: Literal["equal_metric_values_are_ties"] = "equal_metric_values_are_ties"
    comparator_version: str = "candidate-comparison@1"
    policy_hash: str = "pending"

    @field_validator("policy_hash")
    @classmethod
    def _valid_policy_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @field_validator("comparator_version")
    @classmethod
    def _nonblank_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("comparison comparator version must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_policy(self) -> "CandidateComparisonPolicy":
        if not self.metric_keys:
            raise ValueError("comparison policy requires at least one metric")
        if len(self.metric_keys) != len(self.directions) or len(self.metric_keys) != len(self.expected_units):
            raise ValueError("comparison metric keys, directions, and units must have equal lengths")
        if len(set(self.metric_keys)) != len(self.metric_keys):
            raise ValueError("comparison metric keys must be unique")
        if self.metric_keys != (CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,):
            raise ValueError("unsupported comparison metric")
        if self.expected_units != ("mm",):
            raise ValueError("verified clearance comparison metric requires unit mm")
        expected = _hash(self, "policy_hash")
        if self.policy_hash == "pending":
            object.__setattr__(self, "policy_hash", expected)
        elif self.policy_hash != expected:
            raise ValueError("candidate comparison policy hash mismatch")
        return self

    @property
    def metric_order(self) -> tuple[CandidateMetricKey, ...]:
        return self.metric_keys


class CandidateComparisonRequest(CandidateComparisonModel):
    schema_version: Literal["candidate-comparison-request@1"] = "candidate-comparison-request@1"
    project_id: str = Field(min_length=1)
    source_binding_hash: str
    evaluation_scope_hash: str
    policy_hash: str
    candidate_evaluation_pairs: tuple[tuple[str, str], ...] = Field(min_length=1)
    request_hash: str = "pending"

    _validate_hashes = field_validator(
        "source_binding_hash", "evaluation_scope_hash", "policy_hash"
    )(_require_hash)

    @field_validator("request_hash")
    @classmethod
    def _valid_request_hash(cls, value: str) -> str:
        return _require_hash_or_pending(value)

    @model_validator(mode="after")
    def _validate_request(self) -> "CandidateComparisonRequest":
        if not self.project_id.strip():
            raise ValueError("comparison project ID must not be empty")
        pairs = self.candidate_evaluation_pairs
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError("comparison candidate/evaluation pair must contain two hashes")
        for candidate_id, evaluation_id in pairs:
            _require_hash(candidate_id)
            _require_hash(evaluation_id)
        if len({candidate_id for candidate_id, _ in pairs}) != len(pairs):
            raise ValueError("comparison candidates must be unique")
        if len({evaluation_id for _, evaluation_id in pairs}) != len(pairs):
            raise ValueError("comparison evaluations must be unique")
        expected = _hash(self, "request_hash")
        if self.request_hash == "pending":
            object.__setattr__(self, "request_hash", expected)
        elif self.request_hash != expected:
            raise ValueError("candidate comparison request hash mismatch")
        return self


def candidate_comparison_policy_hash(policy: CandidateComparisonPolicy) -> str:
    return _hash(policy, "policy_hash")


def candidate_comparison_request_hash(request: CandidateComparisonRequest) -> str:
    return _hash(request, "request_hash")


class CandidateComparisonResult(CandidateComparisonModel):
    schema_version: Literal["candidate-comparison-result@1"] = "candidate-comparison-result@1"
    project_id: str = Field(min_length=1)
    source_binding_hash: str
    evaluation_scope_hash: str
    policy: CandidateComparisonPolicy
    policy_hash: str
    request_hash: str
    candidate_evaluation_pairs: tuple[tuple[str, str], ...] = Field(min_length=1)
    ranked_candidate_hashes: tuple[str, ...] = Field(min_length=1)
    ranked_evaluation_hashes: tuple[str, ...] = Field(min_length=1)
    metric_values: tuple[tuple[str, float], ...] = Field(min_length=1)
    ties: tuple[tuple[str, ...], ...] = ()
    comparator_identity: str = "candidate-comparison"
    comparator_version: str = Field(min_length=1)
    result_hash: str = "pending"

    _validate_hashes = field_validator(
        "source_binding_hash", "evaluation_scope_hash", "policy_hash", "request_hash"
    )(_require_hash)

    @field_validator("result_hash")
    @classmethod
    def _valid_result_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @field_validator("comparator_version")
    @classmethod
    def _nonblank_comparator_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("comparison comparator version must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_result(self) -> "CandidateComparisonResult":
        if not self.project_id.strip() or not self.comparator_identity.strip():
            raise ValueError("comparison result identities must not be empty")
        if self.policy_hash != self.policy.policy_hash:
            raise ValueError("comparison result policy binding mismatch")
        if self.comparator_version != self.policy.comparator_version:
            raise ValueError("comparison result comparator binding mismatch")
        CandidateComparisonRequest(
            project_id=self.project_id,
            source_binding_hash=self.source_binding_hash,
            evaluation_scope_hash=self.evaluation_scope_hash,
            policy_hash=self.policy_hash,
            candidate_evaluation_pairs=self.candidate_evaluation_pairs,
            request_hash=self.request_hash,
        )
        if len(self.candidate_evaluation_pairs) != len(self.ranked_candidate_hashes):
            raise ValueError("comparison result ranking is incomplete")
        if len(self.ranked_candidate_hashes) != len(self.ranked_evaluation_hashes):
            raise ValueError("comparison result candidate/evaluation ranking is inconsistent")
        if len(set(self.candidate_evaluation_pairs)) != len(self.candidate_evaluation_pairs):
            raise ValueError("comparison result candidate/evaluation pairs must be unique")
        for candidate_id, evaluation_id in self.candidate_evaluation_pairs:
            _require_hash(candidate_id)
            _require_hash(evaluation_id)
        for candidate_id in self.ranked_candidate_hashes:
            _require_hash(candidate_id)
        for evaluation_id in self.ranked_evaluation_hashes:
            _require_hash(evaluation_id)
        if len(set(self.ranked_candidate_hashes)) != len(self.ranked_candidate_hashes):
            raise ValueError("comparison result ranked candidates must be unique")
        if len(set(self.ranked_evaluation_hashes)) != len(self.ranked_evaluation_hashes):
            raise ValueError("comparison result ranked evaluations must be unique")
        requested_candidates = {candidate_id for candidate_id, _ in self.candidate_evaluation_pairs}
        ranked_pairs = set(zip(self.ranked_candidate_hashes, self.ranked_evaluation_hashes))
        if set(self.ranked_candidate_hashes) != requested_candidates:
            raise ValueError("comparison result ranking does not match the requested candidate set")
        if ranked_pairs != set(self.candidate_evaluation_pairs):
            raise ValueError("comparison result ranking has an inconsistent candidate/evaluation pairing")
        if len(self.metric_values) != len(requested_candidates):
            raise ValueError("comparison result metric coverage is incomplete")
        metric_candidates = tuple(candidate_id for candidate_id, _ in self.metric_values)
        if len(set(metric_candidates)) != len(metric_candidates) or set(metric_candidates) != requested_candidates:
            raise ValueError("comparison result metric coverage does not match the requested candidates")
        for candidate_id, value in self.metric_values:
            _require_hash(candidate_id)
            if not math.isfinite(value):
                raise ValueError("comparison metric values must be finite")
        values = dict(self.metric_values)
        maximize = self.policy.directions[0] is CandidateComparisonDirection.MAXIMIZE
        for previous, current in zip(self.ranked_candidate_hashes, self.ranked_candidate_hashes[1:]):
            if (maximize and values[previous] < values[current]) or (
                not maximize and values[previous] > values[current]
            ):
                raise ValueError("comparison result ranking order does not match policy metric direction")
        expected_ties: list[tuple[str, ...]] = []
        index = 0
        while index < len(self.ranked_candidate_hashes):
            end = index + 1
            while (
                end < len(self.ranked_candidate_hashes)
                and values[self.ranked_candidate_hashes[end]] == values[self.ranked_candidate_hashes[index]]
            ):
                end += 1
            if end - index > 1:
                expected_ties.append(tuple(self.ranked_candidate_hashes[index:end]))
            index = end
        tie_candidates: list[str] = []
        for group in self.ties:
            if len(group) < 2:
                raise ValueError("comparison ties must contain at least two candidates")
            for candidate_id in group:
                _require_hash(candidate_id)
                tie_candidates.append(candidate_id)
        if len(set(tie_candidates)) != len(tie_candidates) or tuple(self.ties) != tuple(expected_ties):
            raise ValueError("comparison ties do not match equal metric values")
        expected = _hash(self, "result_hash")
        if self.result_hash == "pending":
            object.__setattr__(self, "result_hash", expected)
        elif self.result_hash != expected:
            raise ValueError("candidate comparison result hash mismatch")
        return self


class CandidateComparisonService:
    def __init__(
        self,
        policy: CandidateComparisonPolicy,
        *,
        project_id: str | None = None,
        currentness_verifier=None,
    ):
        if currentness_verifier is None:
            raise ValueError("candidate comparison requires a currentness verifier")
        self.policy = CandidateComparisonPolicy.model_validate(policy.model_dump(mode="json"))
        self.project_id = project_id
        self.currentness_verifier = currentness_verifier

    @staticmethod
    def result_hash(result: CandidateComparisonResult) -> str:
        return _hash(result, "result_hash")

    def compare(
        self,
        request: CandidateComparisonRequest,
        evaluations: Mapping[str, CandidateEvaluation] | tuple[object, ...] | list[object],
    ) -> CandidateComparisonResult:
        request = CandidateComparisonRequest.model_validate(request.model_dump(mode="json"))
        if request.policy_hash != self.policy.policy_hash:
            raise ValueError("comparison request policy binding mismatch")
        if self.project_id is not None and request.project_id != self.project_id:
            raise ValueError("comparison project binding mismatch")

        if isinstance(evaluations, Mapping):
            entries = tuple(evaluations.values())
            mapped_candidate_ids = tuple(evaluations)
        else:
            entries = tuple(evaluations)
            mapped_candidate_ids = ()
        normalized: dict[str, tuple[MechanicalDesignCandidate | None, CandidateEvaluation]] = {}
        for index, entry in enumerate(entries):
            candidate: MechanicalDesignCandidate | None = None
            evaluation = entry
            if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], MechanicalDesignCandidate):
                candidate, evaluation = entry
                candidate = MechanicalDesignCandidate.model_validate(candidate.model_dump(mode="json"))
                if candidate.candidate_hash != candidate_hash(candidate):
                    raise ValueError("comparison candidate hash mismatch")
                if candidate.source_binding.project_id != request.project_id:
                    raise ValueError("comparison project binding mismatch")
                if _hash(candidate.source_binding) != request.source_binding_hash:
                    raise ValueError("comparison source binding mismatch")
            evaluation = CandidateEvaluation.model_validate(evaluation.model_dump(mode="json"))
            if candidate is not None and candidate.candidate_hash != evaluation.candidate_hash:
                raise ValueError("comparison candidate/evaluation identity mismatch")
            if mapped_candidate_ids and mapped_candidate_ids[index] != evaluation.candidate_hash:
                raise ValueError("comparison mapping candidate identity mismatch")
            if evaluation.outcome is not self.policy.required_outcome:
                raise ValueError("comparison requires current FEASIBLE evaluations")
            if evaluation.source_binding_hash != request.source_binding_hash:
                raise ValueError("comparison source binding mismatch")
            if evaluation.evaluation_scope_hash != request.evaluation_scope_hash:
                raise ValueError("comparison evaluation scope mismatch")
            if candidate is None:
                raise ValueError("comparison currentness verification requires the candidate")
            try:
                current = self.currentness_verifier.verify_current(evaluation, candidate)
            except Exception as exc:
                raise ValueError(f"candidate evaluation currentness verification failed: {exc}") from exc
            if current is not True:
                raise ValueError("candidate evaluation is not current")
            if evaluation.candidate_hash in normalized:
                raise ValueError("comparison candidates must be unique")
            normalized[evaluation.candidate_hash] = (candidate, evaluation)

        expected_pairs = request.candidate_evaluation_pairs
        actual_pairs = tuple(
            (candidate_id, normalized[candidate_id][1].evaluation_hash)
            for candidate_id, _ in expected_pairs
            if candidate_id in normalized
        )
        if actual_pairs != expected_pairs:
            raise ValueError("comparison request does not match exact candidate/evaluation pairs")
        if len(normalized) != len(expected_pairs):
            raise ValueError("comparison contains an unexpected evaluation")

        values: dict[str, float] = {}
        for candidate_id, _ in expected_pairs:
            evaluation = normalized[candidate_id][1]
            metrics = tuple(
                metric for metric in evaluation.metrics if metric.key in self.policy.metric_keys
            )
            if len(metrics) != 1 or metrics[0].unit != self.policy.expected_units[0]:
                raise ValueError("comparison required metric is missing or has an incompatible unit")
            values[candidate_id] = metrics[0].value

        reverse = self.policy.directions[0] is CandidateComparisonDirection.MAXIMIZE
        ranked = tuple(sorted(expected_pairs, key=lambda pair: values[pair[0]], reverse=reverse))
        ties: list[tuple[str, ...]] = []
        index = 0
        while index < len(ranked):
            end = index + 1
            while end < len(ranked) and values[ranked[end][0]] == values[ranked[index][0]]:
                end += 1
            if end - index > 1:
                ties.append(tuple(candidate_id for candidate_id, _ in ranked[index:end]))
            index = end

        result = CandidateComparisonResult(
            project_id=request.project_id,
            source_binding_hash=request.source_binding_hash,
            evaluation_scope_hash=request.evaluation_scope_hash,
            policy=self.policy,
            policy_hash=request.policy_hash,
            request_hash=request.request_hash,
            candidate_evaluation_pairs=expected_pairs,
            ranked_candidate_hashes=tuple(candidate_id for candidate_id, _ in ranked),
            ranked_evaluation_hashes=tuple(evaluation_id for _, evaluation_id in ranked),
            metric_values=tuple((candidate_id, values[candidate_id]) for candidate_id, _ in ranked),
            ties=tuple(ties),
            comparator_version=self.policy.comparator_version,
        )
        return CandidateComparisonResult.model_validate(result.model_dump(mode="json"))


def candidate_comparison_result_hash(result: CandidateComparisonResult) -> str:
    return _hash(result, "result_hash")


__all__ = [
    "CandidateComparisonDirection",
    "CandidateComparisonPolicy",
    "CandidateComparisonRequest",
    "CandidateComparisonResult",
    "CandidateComparisonService",
    "candidate_comparison_policy_hash",
    "candidate_comparison_request_hash",
    "candidate_comparison_result_hash",
]
