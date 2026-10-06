from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.models.common import Model
from mechcad_harness.state.hashing import canonical_json

from .comparison import (
    CandidateComparisonRequest,
    CandidateComparisonRequestV2,
    CandidateComparisonResult,
    CandidateComparisonResultV2,
    candidate_comparison_policy_hash,
    candidate_comparison_request_hash,
    candidate_comparison_request_hash_v2,
    candidate_comparison_result_hash,
    candidate_comparison_result_hash_v2,
)
from .evaluation import (
    CandidateEvaluation,
    CandidateEvaluationOutcome,
    CandidateEvaluationV2,
)
from .models import (
    CandidateSynthesisRequest,
    MechanicalDesignCandidate,
    candidate_hash,
    candidate_hash_v2,
)


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


class CandidateSelection(Model):
    """An explicit, immutable selection that is not canonical design state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-selection@1"] = "candidate-selection@1"
    candidate_hash: str
    evaluation_hash: str
    source_binding_hash: str
    evaluation_scope_hash: str
    selector_identity: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    comparison_used: bool = False
    comparison_result_hash: str | None = None
    selection_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash",
        "evaluation_hash",
        "source_binding_hash",
        "evaluation_scope_hash",
    )(_require_hash)

    @field_validator("comparison_result_hash")
    @classmethod
    def _valid_comparison_hash(cls, value: str | None) -> str | None:
        return None if value is None else _require_hash(value)

    @field_validator("selection_hash")
    @classmethod
    def _valid_selection_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @field_validator("selector_identity", "rationale")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("selection identity and rationale must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_selection(self) -> "CandidateSelection":
        if self.comparison_used and self.comparison_result_hash is None:
            raise ValueError("selection using comparison requires a comparison result identity")
        if not self.comparison_used and self.comparison_result_hash is not None:
            raise ValueError("selection without comparison cannot carry a comparison result identity")
        expected = _hash(self, "selection_hash")
        if self.selection_hash == "pending":
            object.__setattr__(self, "selection_hash", expected)
        elif self.selection_hash != expected:
            raise ValueError("candidate selection hash mismatch")
        return self


class CandidateSelectionV2(Model):
    """An explicit, immutable selection bound to semantic candidate identities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["candidate-selection@2"] = "candidate-selection@2"
    candidate_hash: str
    evaluation_hash: str
    source_binding_hash: str
    evaluation_scope_hash: str
    selector_identity: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    comparison_used: bool = False
    comparison_result_hash: str | None = None
    selection_hash: str = "pending"

    _validate_hashes = field_validator(
        "candidate_hash",
        "evaluation_hash",
        "source_binding_hash",
        "evaluation_scope_hash",
    )(_require_hash)

    @field_validator("comparison_result_hash")
    @classmethod
    def _valid_comparison_hash(cls, value: str | None) -> str | None:
        return None if value is None else _require_hash(value)

    @field_validator("selection_hash")
    @classmethod
    def _valid_selection_hash(cls, value: str) -> str:
        return value if value == "pending" else _require_hash(value)

    @field_validator("selector_identity", "rationale")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("selection identity and rationale must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_selection_v2(self) -> "CandidateSelectionV2":
        if self.comparison_used and self.comparison_result_hash is None:
            raise ValueError("selection using comparison requires a comparison result identity")
        if not self.comparison_used and self.comparison_result_hash is not None:
            raise ValueError("selection without comparison cannot carry a comparison result identity")
        expected = candidate_selection_hash_v2(self)
        if self.selection_hash == "pending":
            object.__setattr__(self, "selection_hash", expected)
        elif self.selection_hash != expected:
            raise ValueError("candidate selection hash mismatch")
        return self


def candidate_selection_hash_v2(selection: CandidateSelectionV2) -> str:
    return _hash(selection, "selection_hash")


class CandidateSelectionService:
    """Validate and record a noncanonical choice without applying it."""

    def __init__(self, *, project_id: str, currentness_verifier=None):
        if not project_id.strip():
            raise ValueError("candidate selection requires a non-empty project binding")
        if currentness_verifier is None:
            raise ValueError("candidate selection requires a currentness verifier")
        self.project_id = project_id
        self.currentness_verifier = currentness_verifier

    @staticmethod
    def selection_hash(
        selection: CandidateSelection | CandidateSelectionV2,
    ) -> str:
        if isinstance(selection, CandidateSelectionV2):
            return candidate_selection_hash_v2(selection)
        return _hash(selection, "selection_hash")

    def _verify_current(
        self,
        evaluation: CandidateEvaluation | CandidateEvaluationV2,
        candidate: MechanicalDesignCandidate,
        synthesis_request=None,
        exact_source_artifacts=None,
    ) -> None:
        try:
            if synthesis_request is None:
                current = self.currentness_verifier.verify_current(evaluation, candidate)
            else:
                current = self.currentness_verifier.verify_current(
                    evaluation,
                    candidate,
                    synthesis_request=synthesis_request,
                    exact_source_artifacts=exact_source_artifacts,
                )
        except Exception as exc:
            raise ValueError(f"candidate selection currentness verification failed: {exc}") from exc
        if current is not True:
            raise ValueError("candidate selection requires a current candidate evaluation")

    @staticmethod
    def _validate_candidate_evaluation(
        candidate: MechanicalDesignCandidate,
        evaluation: CandidateEvaluation,
    ) -> tuple[MechanicalDesignCandidate, CandidateEvaluation, str]:
        try:
            candidate = MechanicalDesignCandidate.model_validate(candidate.model_dump(mode="json"))
            evaluation = CandidateEvaluation.model_validate(evaluation.model_dump(mode="json"))
        except Exception as exc:
            raise ValueError(f"candidate selection input integrity failure: {exc}") from exc

        expected_candidate_hash = (
            candidate_hash_v2(candidate)
            if candidate.schema_version == "mechanical-design-candidate@2"
            else candidate_hash(candidate)
        )
        if candidate.candidate_hash != expected_candidate_hash:
            raise ValueError("candidate selection candidate hash mismatch")
        if evaluation.candidate_hash != candidate.candidate_hash:
            raise ValueError("candidate selection candidate/evaluation identity mismatch")
        if evaluation.synthesis_request_hash != candidate.synthesis_request_hash:
            raise ValueError("candidate selection synthesis request binding mismatch")
        if evaluation.synthesis_policy_hash != candidate.synthesis_policy_hash:
            raise ValueError("candidate selection synthesis policy binding mismatch")

        source_binding_hash = _hash(candidate.source_binding)
        if evaluation.source_binding_hash != source_binding_hash:
            raise ValueError("candidate selection source binding mismatch")
        if evaluation.outcome is not CandidateEvaluationOutcome.FEASIBLE:
            raise ValueError("candidate selection requires a FEASIBLE evaluation")
        if evaluation.unresolved_findings:
            raise ValueError("candidate selection cannot use an evaluation with unresolved findings")
        return candidate, evaluation, source_binding_hash

    @staticmethod
    def _validate_candidate_evaluation_v2(
        candidate: MechanicalDesignCandidate,
        evaluation: CandidateEvaluationV2,
    ) -> tuple[MechanicalDesignCandidate, CandidateEvaluationV2, str]:
        try:
            candidate = MechanicalDesignCandidate.model_validate(
                candidate.model_dump(mode="json")
            )
            evaluation = CandidateEvaluationV2.model_validate(
                evaluation.model_dump(mode="json")
            )
        except Exception as exc:
            raise ValueError(f"candidate selection input integrity failure: {exc}") from exc
        if candidate.schema_version != "mechanical-design-candidate@2":
            raise ValueError("candidate-selection@2 rejects mixed candidate versions")
        if candidate.candidate_hash != candidate_hash_v2(candidate):
            raise ValueError("candidate selection candidate hash mismatch")
        if evaluation.candidate_hash != candidate.candidate_hash:
            raise ValueError("candidate selection candidate/evaluation identity mismatch")
        if evaluation.source_binding_hash != candidate.semantic_source_binding_hash:
            raise ValueError("candidate selection semantic source binding mismatch")
        if evaluation.synthesis_request_hash != candidate.synthesis_request_hash:
            raise ValueError("candidate selection synthesis request binding mismatch")
        if evaluation.synthesis_policy_hash != candidate.synthesis_policy_hash:
            raise ValueError("candidate selection synthesis policy binding mismatch")
        if evaluation.outcome is not CandidateEvaluationOutcome.FEASIBLE:
            raise ValueError("candidate selection requires a FEASIBLE evaluation")
        if evaluation.unresolved_findings:
            raise ValueError("candidate selection cannot use an evaluation with unresolved findings")
        return candidate, evaluation, candidate.semantic_source_binding_hash

    def _select_v2(
        self,
        candidate: MechanicalDesignCandidate,
        evaluation: CandidateEvaluationV2,
        selector_identity: str,
        rationale: str,
        comparison: CandidateComparisonResultV2 | None,
        comparison_entries,
        *,
        synthesis_request: CandidateSynthesisRequest | None,
        synthesis_requests_by_candidate_hash,
        exact_source_artifacts=None,
        exact_source_artifacts_by_candidate_hash=None,
    ) -> CandidateSelectionV2:
        if not isinstance(evaluation, CandidateEvaluationV2):
            raise ValueError("candidate@2 selection identity mismatch: evaluation@2 required")
        candidate, evaluation, source_binding_hash = self._validate_candidate_evaluation_v2(
            candidate, evaluation
        )
        if candidate.source_binding.project_id != self.project_id:
            raise ValueError("candidate selection project binding mismatch")
        if synthesis_request is None:
            raise ValueError("candidate@2 selection requires synthesis request@2")
        try:
            synthesis_request = CandidateSynthesisRequest.model_validate(
                synthesis_request.model_dump(mode="json")
            )
        except Exception as exc:
            raise ValueError(f"candidate selection request@2 integrity failure: {exc}") from exc
        if synthesis_request.schema_version != "candidate-synthesis-request@2":
            raise ValueError("candidate@2 selection requires synthesis request@2")
        if (
            candidate.synthesis_request_hash != synthesis_request.request_hash
            or candidate.source_binding != synthesis_request.source_binding
            or candidate.semantic_source_binding_hash
            != synthesis_request.semantic_source_binding_hash
        ):
            raise ValueError("candidate selection request@2 semantic binding mismatch")

        comparison_result_hash: str | None = None
        if comparison is None:
            if comparison_entries is not None:
                raise ValueError("candidate selection without comparison cannot carry comparison entries")
            if synthesis_requests_by_candidate_hash is not None:
                raise ValueError("candidate selection without comparison cannot carry request mappings")
            self._verify_current(
                evaluation,
                candidate,
                synthesis_request,
                exact_source_artifacts=exact_source_artifacts,
            )
        else:
            if not isinstance(comparison, CandidateComparisonResultV2):
                raise ValueError("candidate-selection@2 requires comparison result@2")
            if comparison_entries is None:
                raise ValueError("candidate selection comparison entries are required")
            try:
                comparison = CandidateComparisonResultV2.model_validate(
                    comparison.model_dump(mode="json")
                )
            except Exception as exc:
                raise ValueError(
                    f"candidate selection comparison integrity failure: {exc}"
                ) from exc
            if comparison.result_hash != candidate_comparison_result_hash_v2(comparison):
                raise ValueError("candidate selection comparison result identity mismatch")
            if comparison.policy_hash != candidate_comparison_policy_hash(comparison.policy):
                raise ValueError("candidate selection comparison policy identity mismatch")
            comparison_request = CandidateComparisonRequestV2(
                project_id=comparison.project_id,
                source_binding_hash=comparison.source_binding_hash,
                evaluation_scope_hash=comparison.evaluation_scope_hash,
                policy_hash=comparison.policy_hash,
                candidate_evaluation_pairs=comparison.candidate_evaluation_pairs,
                request_hash=comparison.request_hash,
            )
            if comparison.request_hash != candidate_comparison_request_hash_v2(
                comparison_request
            ):
                raise ValueError("candidate selection comparison request identity mismatch")
            if comparison.project_id != candidate.source_binding.project_id:
                raise ValueError("candidate selection comparison project binding mismatch")
            if comparison.project_id != self.project_id:
                raise ValueError("candidate selection project binding mismatch")
            if comparison.source_binding_hash != source_binding_hash:
                raise ValueError("candidate selection comparison source binding mismatch")
            if comparison.evaluation_scope_hash != evaluation.evaluation_scope_hash:
                raise ValueError("candidate selection comparison scope binding mismatch")
            selected_pair = (candidate.candidate_hash, evaluation.evaluation_hash)
            if selected_pair not in comparison.candidate_evaluation_pairs:
                raise ValueError("candidate selection comparison does not contain selected candidate")
            expected_candidate_ids = {
                candidate_id for candidate_id, _ in comparison.candidate_evaluation_pairs
            }
            if synthesis_requests_by_candidate_hash is None or set(
                synthesis_requests_by_candidate_hash
            ) != expected_candidate_ids:
                raise ValueError("candidate selection requires an exact request@2 mapping")
            selected_request = synthesis_requests_by_candidate_hash.get(candidate.candidate_hash)
            if selected_request is None:
                raise ValueError("candidate selection request@2 mapping is missing")
            selected_request = CandidateSynthesisRequest.model_validate(
                selected_request.model_dump(mode="json")
            )
            if selected_request != synthesis_request:
                raise ValueError("candidate selection request@2 mapping differs from selected request")

            try:
                entries = tuple(comparison_entries)
            except Exception as exc:
                raise ValueError("candidate selection comparison entries are invalid") from exc
            normalized_pairs: list[tuple[str, str]] = []
            metric_values = dict(comparison.metric_values)
            for entry in entries:
                if not isinstance(entry, tuple) or len(entry) != 2:
                    raise ValueError(
                        "candidate selection comparison entry must contain candidate and evaluation"
                    )
                member_candidate, member_evaluation, member_source_hash = (
                    self._validate_candidate_evaluation_v2(entry[0], entry[1])
                )
                if member_candidate.source_binding.project_id != comparison.project_id:
                    raise ValueError("candidate selection comparison project binding mismatch")
                if member_source_hash != comparison.source_binding_hash:
                    raise ValueError("candidate selection comparison source binding mismatch")
                if member_evaluation.evaluation_scope_hash != comparison.evaluation_scope_hash:
                    raise ValueError("candidate selection comparison scope binding mismatch")
                member_request = synthesis_requests_by_candidate_hash.get(
                    member_candidate.candidate_hash
                )
                if member_request is None:
                    raise ValueError("candidate selection request@2 mapping is missing")
                member_request = CandidateSynthesisRequest.model_validate(
                    member_request.model_dump(mode="json")
                )
                if member_request.schema_version != "candidate-synthesis-request@2":
                    raise ValueError("candidate selection request@2 mapping is missing or mixed")
                self._verify_current(
                    member_evaluation,
                    member_candidate,
                    member_request,
                    exact_source_artifacts=(
                        None
                        if exact_source_artifacts_by_candidate_hash is None
                        else exact_source_artifacts_by_candidate_hash.get(
                            member_candidate.candidate_hash
                        )
                    ),
                )
                member_pair = (
                    member_candidate.candidate_hash,
                    member_evaluation.evaluation_hash,
                )
                comparison_value = metric_values.get(member_candidate.candidate_hash)
                evaluation_metrics = tuple(
                    metric
                    for metric in member_evaluation.metrics
                    if metric.key in comparison.policy.metric_keys
                )
                if (
                    comparison_value is None
                    or len(evaluation_metrics) != 1
                    or evaluation_metrics[0].unit != comparison.policy.expected_units[0]
                    or evaluation_metrics[0].value != comparison_value
                ):
                    raise ValueError(
                        "candidate selection comparison metric does not match evaluation"
                    )
                normalized_pairs.append(member_pair)
            if tuple(normalized_pairs) != comparison.candidate_evaluation_pairs:
                raise ValueError(
                    "candidate selection comparison entries do not match exact candidate/evaluation pairs"
                )
            comparison_result_hash = comparison.result_hash

        return CandidateSelectionV2(
            candidate_hash=candidate.candidate_hash,
            evaluation_hash=evaluation.evaluation_hash,
            source_binding_hash=source_binding_hash,
            evaluation_scope_hash=evaluation.evaluation_scope_hash,
            selector_identity=selector_identity,
            rationale=rationale,
            comparison_used=comparison is not None,
            comparison_result_hash=comparison_result_hash,
        )

    def select(
        self,
        candidate: MechanicalDesignCandidate,
        evaluation: CandidateEvaluation | CandidateEvaluationV2,
        selector_identity: str,
        rationale: str,
        comparison: CandidateComparisonResult | CandidateComparisonResultV2 | None = None,
        comparison_entries: tuple[
            tuple[MechanicalDesignCandidate, CandidateEvaluation | CandidateEvaluationV2], ...
        ]
        | list[
            tuple[MechanicalDesignCandidate, CandidateEvaluation | CandidateEvaluationV2]
        ]
        | None = None,
        *,
        synthesis_request=None,
        synthesis_requests_by_candidate_hash=None,
        exact_source_artifacts=None,
        exact_source_artifacts_by_candidate_hash=None,
    ) -> CandidateSelection | CandidateSelectionV2:
        if (
            candidate.schema_version == "mechanical-design-candidate@2"
            or evaluation.schema_version == "candidate-evaluation@2"
        ):
            return self._select_v2(
                candidate,
                evaluation,
                selector_identity,
                rationale,
                comparison,
                comparison_entries,
                synthesis_request=synthesis_request,
                synthesis_requests_by_candidate_hash=synthesis_requests_by_candidate_hash,
                exact_source_artifacts=exact_source_artifacts,
                exact_source_artifacts_by_candidate_hash=exact_source_artifacts_by_candidate_hash,
            )
        candidate, evaluation, source_binding_hash = self._validate_candidate_evaluation(
            candidate, evaluation
        )
        if candidate.source_binding.project_id != self.project_id:
            raise ValueError("candidate selection project binding mismatch")
        if candidate.schema_version == "mechanical-design-candidate@2":
            if (
                synthesis_request is None
                or synthesis_request.schema_version != "candidate-synthesis-request@2"
            ):
                raise ValueError("candidate@2 selection requires synthesis request@2")
        elif synthesis_request is not None and synthesis_request.schema_version == "candidate-synthesis-request@2":
            raise ValueError("legacy candidate selection cannot carry request@2")

        comparison_result_hash: str | None = None
        comparison_used = comparison is not None
        if comparison is not None:
            if comparison_entries is None:
                raise ValueError("candidate selection comparison entries are required")
            try:
                comparison = CandidateComparisonResult.model_validate(
                    comparison.model_dump(mode="json")
                )
            except Exception as exc:
                raise ValueError(f"candidate selection comparison integrity failure: {exc}") from exc
            if comparison.result_hash != candidate_comparison_result_hash(comparison):
                raise ValueError("candidate selection comparison result identity mismatch")
            if comparison.policy_hash != candidate_comparison_policy_hash(comparison.policy):
                raise ValueError("candidate selection comparison policy identity mismatch")
            request = CandidateComparisonRequest(
                project_id=comparison.project_id,
                source_binding_hash=comparison.source_binding_hash,
                evaluation_scope_hash=comparison.evaluation_scope_hash,
                policy_hash=comparison.policy_hash,
                candidate_evaluation_pairs=comparison.candidate_evaluation_pairs,
                request_hash=comparison.request_hash,
            )
            if comparison.request_hash != candidate_comparison_request_hash(request):
                raise ValueError("candidate selection comparison request identity mismatch")
            ranked_pairs = tuple(
                zip(comparison.ranked_candidate_hashes, comparison.ranked_evaluation_hashes)
            )
            if set(ranked_pairs) != set(comparison.candidate_evaluation_pairs):
                raise ValueError("candidate selection comparison result membership mismatch")
            metric_values = dict(comparison.metric_values)
            if set(metric_values) != {
                candidate_id for candidate_id, _ in comparison.candidate_evaluation_pairs
            }:
                raise ValueError("candidate selection comparison metric membership mismatch")
            if comparison.project_id != candidate.source_binding.project_id:
                raise ValueError("candidate selection comparison project binding mismatch")
            if comparison.project_id != self.project_id:
                raise ValueError("candidate selection project binding mismatch")
            if comparison.source_binding_hash != source_binding_hash:
                raise ValueError("candidate selection comparison source binding mismatch")
            if comparison.evaluation_scope_hash != evaluation.evaluation_scope_hash:
                raise ValueError("candidate selection comparison scope binding mismatch")
            selected_pair = (candidate.candidate_hash, evaluation.evaluation_hash)
            if selected_pair not in comparison.candidate_evaluation_pairs:
                raise ValueError("candidate selection comparison does not contain the selected candidate")

            try:
                entries = tuple(comparison_entries)
            except Exception as exc:
                raise ValueError("candidate selection comparison entries are invalid") from exc
            normalized_entries = []
            for entry in entries:
                if not isinstance(entry, tuple) or len(entry) != 2:
                    raise ValueError("candidate selection comparison entry must contain candidate and evaluation")
                member_candidate, member_evaluation, member_source_binding_hash = (
                    self._validate_candidate_evaluation(entry[0], entry[1])
                )
                if member_candidate.source_binding.project_id != comparison.project_id:
                    raise ValueError("candidate selection comparison project binding mismatch")
                if member_source_binding_hash != comparison.source_binding_hash:
                    raise ValueError("candidate selection comparison source binding mismatch")
                if member_evaluation.evaluation_scope_hash != comparison.evaluation_scope_hash:
                    raise ValueError("candidate selection comparison scope binding mismatch")
                member_request = synthesis_request if member_candidate.candidate_hash == candidate.candidate_hash else None
                if member_candidate.schema_version == "mechanical-design-candidate@2":
                    if synthesis_requests_by_candidate_hash is None:
                        raise ValueError("comparison requires request@2 mapping for candidate@2")
                    member_request = synthesis_requests_by_candidate_hash.get(
                        member_candidate.candidate_hash
                    )
                    if (
                        member_request is None
                        or member_request.schema_version != "candidate-synthesis-request@2"
                    ):
                        raise ValueError("comparison request@2 mapping is missing or mixed")
                elif (
                    synthesis_requests_by_candidate_hash is not None
                    and member_candidate.candidate_hash in synthesis_requests_by_candidate_hash
                ):
                    raise ValueError("legacy comparison candidate cannot use request@2 mapping")
                self._verify_current(
                    member_evaluation,
                    member_candidate,
                    member_request,
                    exact_source_artifacts=(
                        None
                        if exact_source_artifacts_by_candidate_hash is None
                        else exact_source_artifacts_by_candidate_hash.get(
                            member_candidate.candidate_hash
                        )
                    ),
                )

                member_pair = (member_candidate.candidate_hash, member_evaluation.evaluation_hash)
                comparison_value = metric_values.get(member_candidate.candidate_hash)
                evaluation_metrics = tuple(
                    metric
                    for metric in member_evaluation.metrics
                    if metric.key in comparison.policy.metric_keys
                )
                if (
                    comparison_value is None
                    or len(evaluation_metrics) != 1
                    or evaluation_metrics[0].unit != comparison.policy.expected_units[0]
                    or evaluation_metrics[0].value != comparison_value
                ):
                    raise ValueError("candidate selection comparison metric does not match evaluation")
                normalized_entries.append(member_pair)

            if tuple(normalized_entries) != comparison.candidate_evaluation_pairs:
                raise ValueError("candidate selection comparison entries do not match exact candidate/evaluation pairs")
            comparison_result_hash = comparison.result_hash
        else:
            if comparison_entries is not None:
                raise ValueError("candidate selection without comparison cannot carry comparison entries")
            self._verify_current(
                evaluation,
                candidate,
                synthesis_request,
                exact_source_artifacts=exact_source_artifacts,
            )

        return CandidateSelection(
            candidate_hash=candidate.candidate_hash,
            evaluation_hash=evaluation.evaluation_hash,
            source_binding_hash=source_binding_hash,
            evaluation_scope_hash=evaluation.evaluation_scope_hash,
            selector_identity=selector_identity,
            rationale=rationale,
            comparison_used=comparison_used,
            comparison_result_hash=comparison_result_hash,
        )


def candidate_selection_hash(selection: CandidateSelection) -> str:
    return _hash(selection, "selection_hash")


__all__ = [
    "CandidateSelection",
    "CandidateSelectionV2",
    "CandidateSelectionService",
    "candidate_selection_hash",
    "candidate_selection_hash_v2",
]
