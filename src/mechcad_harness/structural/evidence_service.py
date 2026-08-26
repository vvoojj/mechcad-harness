from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

from mechcad_harness.artifacts.models import ArtifactType
from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactVerificationError
from mechcad_harness.dependency.storage import EvidenceStore
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.models.structural import structural_definition_hash
from mechcad_harness.state.hashing import state_hash
from mechcad_harness.state.manager import StateManager
from mechcad_harness.backends.provenance import provenance_from_identity
from mechcad_harness.structural.evidence import (
    FREE_END_TRANSVERSE_DISPLACEMENT,
    EvidenceSubject,
    StructuralEvidenceCurrentness,
    StructuralEvidencePayload,
    StructuralEvidenceVerification,
    StructuralMeshConvergenceLevel,
    StructuralMeshConvergenceResult,
    StructuralMeshConvergenceStatus,
    StructuralMeshConvergenceStudy,
    StructuralRepeatabilityComparison,
    StructuralRepeatabilityPolicy,
    StructuralRepeatabilityResult,
    StructuralRepeatabilityStatus,
    StructuralPipelineProvenance,
    structural_evidence_hash,
    structural_mesh_convergence_result_hash,
    structural_mesh_convergence_study_hash,
    structural_mesh_specification_hash,
    structural_repeatability_policy_hash,
)
from mechcad_harness.structural.models import (
    CALCULIX_PROVIDER_IDENTITY,
    DECK_BUILDER_IDENTITY,
    GMSH_PROVIDER_IDENTITY,
    REGION_RESOLVER_IDENTITY,
    REGION_RESOLVER_VERSION,
    StructuralExecutionManifest,
    StructuralExecutionStatus,
    StructuralResultParserProvenance,
    StructuralCriterionStatus,
    execution_manifest_hash,
    structural_result_hash,
    structural_verification_hash,
)
from mechcad_harness.structural.deck import DECK_BUILDER_VERSION
from mechcad_harness.structural.results import (
    CalculiXDatResultParser,
    CalculiXFrdResultParser,
    StructuralResultIntegrityError,
    StructuralResultInterpreter,
    StructuralVerificationService,
)
from mechcad_harness.structural.runtime import CALCULIX_IDENTITY, FREECAD_IDENTITY, GMSH_IDENTITY
from mechcad_harness.structural.validation import reconstruct_analytical_validation
from mechcad_harness.structural_request import StructuralAnalysisRequest, structural_request_hash


class StructuralEvidenceIntegrityError(ValueError):
    """Raised when durable structural evidence cannot be independently trusted."""


def structural_evidence_id(payload: StructuralEvidencePayload) -> str:
    """Return the immutable identity for one complete structural conclusion."""
    return "EVD-STRUCTURAL-" + hashlib.sha256(payload.semantic_hash.encode("utf-8")).hexdigest()[:24]


class StructuralRepeatabilityService:
    """Compare only declared semantic summaries from independently verified Evidence."""

    def __init__(self, verifier: "StructuralEvidenceVerifier"):
        self.verifier = verifier

    def compare(
        self,
        *,
        policy: StructuralRepeatabilityPolicy,
        first_evidence_id: str,
        second_evidence_id: str,
    ) -> StructuralRepeatabilityResult:
        if first_evidence_id == second_evidence_id:
            return _repeatability_integrity_failure(
                policy, first_evidence_id, second_evidence_id, "evidence_ids_must_be_distinct"
            )
        try:
            _validate_repeatability_policy(policy)
            first = self.verifier.verify(first_evidence_id)
            second = self.verifier.verify(second_evidence_id)
            if first.evidence_id != first_evidence_id or second.evidence_id != second_evidence_id:
                raise StructuralEvidenceIntegrityError("repeatability verifier ID binding mismatch")
            _require_verified_evidence(policy, first)
            _require_verified_evidence(policy, second)
            _require_repeatability_identity(policy, first.payload, second.payload)
            comparisons = tuple(
                _compare_summary_field(policy, field_id, first.payload, second.payload)
                for field_id in policy.semantic_summary_fields
            )
            return StructuralRepeatabilityResult(
                policy=policy,
                first_evidence_id=first_evidence_id,
                second_evidence_id=second_evidence_id,
                status=(
                    StructuralRepeatabilityStatus.REPEATABLE
                    if all(item.within_tolerance for item in comparisons)
                    else StructuralRepeatabilityStatus.NOT_REPEATABLE
                ),
                comparisons=comparisons,
            )
        except Exception:
            return _repeatability_integrity_failure(
                policy, first_evidence_id, second_evidence_id, "evidence_verification_or_identity_failure"
            )


class StructuralMeshConvergenceService:
    """Evaluate a declared mesh sequence from independently verified Evidence."""

    def __init__(self, verifier: "StructuralEvidenceVerifier"):
        self.verifier = verifier

    def evaluate(
        self,
        *,
        study: StructuralMeshConvergenceStudy,
        level_evidence_ids: tuple[str, ...],
    ) -> StructuralMeshConvergenceResult:
        study, study_error = self._validated_study(study)
        if study_error is not None:
            return _convergence_integrity_failure(study, study_error)
        try:
            if len(level_evidence_ids) != len(study.mesh_specifications):
                raise StructuralEvidenceIntegrityError("level_count_mismatch")
            if len(set(level_evidence_ids)) != len(level_evidence_ids):
                raise StructuralEvidenceIntegrityError("level_evidence_ids_must_be_unique")

            verified = tuple(self.verifier.verify(evidence_id) for evidence_id in level_evidence_ids)
            payloads = tuple(
                self._require_level(evidence_id, item)
                for evidence_id, item in zip(level_evidence_ids, verified, strict=True)
            )
            self._require_shared_identity(study, payloads)
            previous_response = None
            levels = []
            metric_unavailable = False
            for index, (evidence_id, payload) in enumerate(
                zip(level_evidence_ids, payloads, strict=True), start=1
            ):
                level = self._level(
                    study,
                    index,
                    evidence_id,
                    payload,
                    previous_response=previous_response,
                )
                levels.append(level)
                if level.status is StructuralMeshConvergenceStatus.NOT_EVALUABLE:
                    metric_unavailable = True
                previous_response = level.response_value
            concrete_levels = tuple(levels)
            return StructuralMeshConvergenceResult(
                study=study,
                status=(
                    StructuralMeshConvergenceStatus.NOT_EVALUABLE
                    if metric_unavailable
                    else StructuralMeshConvergenceStatus.CONVERGED
                    if all(
                        level.previous_relative_change is None
                        or level.previous_relative_change <= study.relative_change_threshold
                        for level in concrete_levels
                    )
                    else StructuralMeshConvergenceStatus.NOT_CONVERGED
                ),
                levels=concrete_levels,
                reason="response_metric_unavailable" if metric_unavailable else "",
            )
        except Exception as exc:
            return _convergence_integrity_failure(
                study, str(exc) or "mesh convergence integrity failure"
            )

    def publish(
        self,
        *,
        study: StructuralMeshConvergenceStudy,
        level_evidence_ids: tuple[str, ...],
    ) -> Evidence:
        """Persist a convergence-only Evidence record after independent evaluation."""
        result = self.evaluate(study=study, level_evidence_ids=level_evidence_ids)
        if result.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE:
            raise StructuralEvidenceIntegrityError(result.reason)
        if not result.levels or len(result.levels) != len(study.mesh_specifications):
            raise StructuralEvidenceIntegrityError(
                "convergence study does not have complete verified level bindings to publish"
            )

        first = self.verifier.verify(result.levels[0].evidence_id)
        first_payload = self._require_level(result.levels[0].evidence_id, first)
        payload = StructuralEvidencePayload(
            subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
            mesh_convergence_status=result.status,
            convergence=result,
        )
        evidence = Evidence(
            id=structural_evidence_id(payload),
            kind=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY.value,
            subject=EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY,
            summary=f"Structural mesh convergence study: {result.status.value}",
            revision=first_payload.request.source_binding.source_revision,
            state_hash=first_payload.request.source_binding.source_state_hash,
            producer_type="structural_mesh_convergence",
            producer_name="mechcad-structural-convergence@1",
            producer_version="1",
            producer_result_id=result.result_hash,
            input_hash=result.study.study_hash,
            output_hash=payload.semantic_hash,
            structural_evidence_payload=payload,
        )
        store = getattr(self.verifier, "evidence_store", None)
        project_id = getattr(self.verifier, "project_id", None)
        if store is None or not project_id:
            raise StructuralEvidenceIntegrityError(
                "convergence publication requires the existing EvidenceStore"
            )
        store.write_evidence(project_id, evidence)
        self._fresh_verifier().verify(evidence.id)
        return evidence

    def _fresh_verifier(self):
        if not isinstance(self.verifier, StructuralEvidenceVerifier):
            return self.verifier
        manager = StateManager(self.verifier.workspace)
        return StructuralEvidenceVerifier(
            workspace=self.verifier.workspace,
            project_id=self.verifier.project_id,
            state_manager=manager,
            artifact_store=ArtifactStore(
                self.verifier.workspace,
                project_id=self.verifier.project_id,
                run_id="PUBLISH",
            ),
            evidence_store=EvidenceStore(
                self.verifier.workspace,
                manager,
                self.verifier.evidence_store.graph,
            ),
        )

    @staticmethod
    def _validated_study(study):
        if not isinstance(study, StructuralMeshConvergenceStudy):
            raise StructuralEvidenceIntegrityError("mesh convergence study is not typed")
        if study.response_semantics != "magnitude":
            raise StructuralEvidenceIntegrityError("mesh convergence response semantics are not magnitude")
        values = study.model_dump(mode="python")
        supplied_hash = values["study_hash"]
        values["study_hash"] = (
            supplied_hash
            if supplied_hash == structural_mesh_convergence_study_hash(study)
            else "pending"
        )
        try:
            canonical = StructuralMeshConvergenceStudy.model_validate(values)
        except Exception as exc:
            raise StructuralEvidenceIntegrityError("mesh convergence study cannot be canonicalized") from exc
        if supplied_hash != canonical.study_hash:
            return canonical, "study_hash_mismatch"
        return canonical, None

    @staticmethod
    def _require_level(evidence_id: str, verified: StructuralEvidenceVerification) -> StructuralEvidencePayload:
        if (
            not isinstance(verified, StructuralEvidenceVerification)
            or not verified.valid
            or verified.evidence_id != evidence_id
            or not isinstance(verified.payload, StructuralEvidencePayload)
            or verified.payload.subject is not EvidenceSubject.STRUCTURAL_ANALYSIS
            or verified.payload.mesh_convergence_status is not StructuralMeshConvergenceStatus.NOT_EVALUATED
            or verified.payload.semantic_hash != structural_evidence_hash(verified.payload)
            or structural_evidence_id(verified.payload) != evidence_id
            or verified.request_hash != verified.payload.request.request_hash
            or verified.result_hash != verified.payload.result.result_hash
            or verified.verification_hash != verified.payload.verification.verification_hash
        ):
            raise StructuralEvidenceIntegrityError("level evidence verification or identity failure")
        return verified.payload

    @classmethod
    def _require_shared_identity(
        cls,
        study: StructuralMeshConvergenceStudy,
        payloads: tuple[StructuralEvidencePayload, ...],
    ) -> None:
        first = payloads[0]
        first_request = first.request
        first_manifest = first.execution_manifest
        first_source = first_request.source_binding
        first_request_semantics = cls._request_semantics(first_request)
        first_runtime = cls._runtime_semantics(first)
        for index, payload in enumerate(payloads):
            request = payload.request
            manifest = payload.execution_manifest
            source = request.source_binding
            expected_mesh_hash = study.mesh_specification_hashes[index]
            if (
                source.project_id,
                source.source_revision,
                source.source_state_hash,
                source.definition_id,
                source.definition_hash,
                source.target_body_id,
                source.source_program_hash,
                source.geometry_identity,
                source.geometry_artifact_id,
                source.geometry_artifact_hash,
            ) != (
                first_source.project_id,
                first_source.source_revision,
                first_source.source_state_hash,
                first_source.definition_id,
                first_source.definition_hash,
                first_source.target_body_id,
                first_source.source_program_hash,
                first_source.geometry_identity,
                first_source.geometry_artifact_id,
                first_source.geometry_artifact_hash,
            ):
                raise StructuralEvidenceIntegrityError("source identity mismatch")
            if cls._request_semantics(request) != first_request_semantics:
                raise StructuralEvidenceIntegrityError("request semantics mismatch")
            if (
                request.selected_load_case_ids != (study.load_case_id,)
                or manifest.selected_load_case_ids != (study.load_case_id,)
                or tuple(case.load_case_id for case in manifest.case_manifests) != (study.load_case_id,)
                or tuple(case.load_case_id for case in payload.result.load_case_results) != (study.load_case_id,)
            ):
                raise StructuralEvidenceIntegrityError("load case identity mismatch")
            if cls._runtime_semantics(payload) != first_runtime:
                raise StructuralEvidenceIntegrityError("runtime/provider semantics mismatch")
            if not set(study.required_runtime_identities).issubset(_persisted_identity_tokens(payload)):
                raise StructuralEvidenceIntegrityError("required runtime identity is missing")
            if structural_mesh_specification_hash(request.mesh_specification) != expected_mesh_hash:
                raise StructuralEvidenceIntegrityError("request mesh specification order mismatch")
            mesh_manifest = manifest.mesh_manifest
            if (
                manifest.execution_status is not StructuralExecutionStatus.SUCCEEDED
                or any(
                    case.execution_status is not StructuralExecutionStatus.SUCCEEDED
                    for case in manifest.case_manifests
                )
                or payload.result.load_case_results[0].load_case_id != study.load_case_id
                or manifest.mesh_specification_hash != expected_mesh_hash
                or mesh_manifest is None
                or mesh_manifest.mesh_specification_hash != expected_mesh_hash
                or manifest.mesh_artifact_hash != mesh_manifest.mesh_hash
                or payload.result.mesh_hash != manifest.mesh_artifact_hash
                or payload.result.load_case_results[0].mesh_hash != manifest.mesh_artifact_hash
            ):
                raise StructuralEvidenceIntegrityError("mesh identity mismatch")
            if first_manifest is None:
                raise StructuralEvidenceIntegrityError("execution manifest is missing")

    @staticmethod
    def _request_semantics(request: StructuralAnalysisRequest) -> str:
        values = request.model_dump(mode="json")
        values.pop("request_hash", None)
        values.pop("mesh_specification", None)
        values.pop("analytical_policy_hash", None)
        return json.dumps(values, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _runtime_semantics(payload: StructuralEvidencePayload) -> str:
        manifest = payload.execution_manifest
        values = {
            "aggregate": payload.aggregate_provenance.model_dump(mode="json"),
            "manifest": {
                "geometry_provider_provenance": manifest.geometry_provider_provenance.model_dump(mode="json"),
                "resolver_identity": manifest.resolver_identity,
                "resolver_version": manifest.resolver_version,
                "gmsh_identity": manifest.gmsh_identity,
                "gmsh_version": manifest.gmsh_version,
                "deck_builder_identity": manifest.deck_builder_identity,
                "deck_builder_version": manifest.deck_builder_version,
                "calculix_identity": manifest.calculix_identity,
                "calculix_version": manifest.calculix_version,
                "mesh_provider": (
                    manifest.mesh_manifest.gmsh_identity,
                    manifest.mesh_manifest.gmsh_version,
                ) if manifest.mesh_manifest is not None else None,
                "case_deck_providers": tuple(
                    (case.deck_builder_identity, case.deck_builder_version)
                    for case in manifest.case_manifests
                ),
                "case_solver_providers": tuple(
                    (
                        case.solver_manifest.calculix_identity,
                        case.solver_manifest.calculix_version,
                    ) if case.solver_manifest is not None else None
                    for case in manifest.case_manifests
                ),
                "solver_provenance": tuple(
                    case.solver_manifest.backend_provenance.model_dump(mode="json")
                    if case.solver_manifest is not None and case.solver_manifest.backend_provenance is not None
                    else None
                    for case in manifest.case_manifests
                ),
            },
        }
        return json.dumps(values, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _level(
        study: StructuralMeshConvergenceStudy,
        level_index: int,
        evidence_id: str,
        payload: StructuralEvidencePayload,
        *,
        previous_response: float | None,
    ) -> StructuralMeshConvergenceLevel:
        validation = payload.analytical_validation
        check = (
            next((item for item in validation.checks if item.check_id == "tip_displacement"), None)
            if validation is not None
            else None
        )
        if (
            validation is None
            or validation.policy.tip_displacement_metric != study.response_metric
            or validation.policy.free_end_region_id != "free"
            or study.response_domain != "free-end"
            or check is None
            or not isinstance(check.observed_value, (int, float))
            or isinstance(check.observed_value, bool)
            or not math.isfinite(float(check.observed_value))
        ):
            return StructuralMeshConvergenceLevel(
                level_index=level_index,
                evidence_id=evidence_id,
                evidence_hash=payload.semantic_hash,
                mesh_specification_hash=study.mesh_specification_hashes[level_index - 1],
                node_count=payload.execution_manifest.mesh_manifest.node_count,
                volume_element_count=payload.execution_manifest.mesh_manifest.volume_element_count,
                response_value=None,
                status=StructuralMeshConvergenceStatus.NOT_EVALUABLE,
                reason="response_metric_unavailable",
                previous_relative_change=None,
            )
        response_value = abs(float(check.observed_value))
        previous_relative_change = None
        if previous_response is not None:
            previous_relative_change = abs(response_value - previous_response) / max(
                abs(response_value), study.epsilon
            )
        check_reference = (
            abs(float(check.expected_value))
            if isinstance(check.expected_value, (int, float)) and not isinstance(check.expected_value, bool)
            else None
        )
        check_error = abs(float(check.relative_error)) if check.relative_error is not None else None
        return StructuralMeshConvergenceLevel(
            level_index=level_index,
            evidence_id=evidence_id,
            evidence_hash=payload.semantic_hash,
            mesh_specification_hash=study.mesh_specification_hashes[level_index - 1],
            node_count=payload.execution_manifest.mesh_manifest.node_count,
            volume_element_count=payload.execution_manifest.mesh_manifest.volume_element_count,
            response_value=response_value,
            status=StructuralMeshConvergenceStatus.CONVERGED,
            analytical_reference=(float(check_reference) if check_reference is not None else None),
            analytical_error=(float(check_error) if check_error is not None else None),
            previous_relative_change=previous_relative_change,
        )


def _repeatability_integrity_failure(policy, first_evidence_id, second_evidence_id, reason):
    if isinstance(policy, StructuralRepeatabilityPolicy) and policy.policy_hash != structural_repeatability_policy_hash(policy):
        policy_values = policy.model_dump(mode="python")
        policy_values["policy_hash"] = "pending"
        policy = StructuralRepeatabilityPolicy.model_validate(policy_values)
    return StructuralRepeatabilityResult(
        policy=policy,
        first_evidence_id=first_evidence_id,
        second_evidence_id=second_evidence_id,
        status=StructuralRepeatabilityStatus.INTEGRITY_FAILURE,
        comparisons=(),
        reason=reason,
    )


def _convergence_integrity_failure(
    study: StructuralMeshConvergenceStudy,
    reason: str,
) -> StructuralMeshConvergenceResult:
    return StructuralMeshConvergenceResult(
        study=study,
        status=StructuralMeshConvergenceStatus.INTEGRITY_FAILURE,
        levels=(),
        reason=reason,
    )


def _validate_repeatability_policy(policy: StructuralRepeatabilityPolicy) -> None:
    if not isinstance(policy, StructuralRepeatabilityPolicy):
        raise StructuralEvidenceIntegrityError("repeatability policy is not typed")
    if policy.policy_hash != structural_repeatability_policy_hash(policy):
        raise StructuralEvidenceIntegrityError("repeatability policy hash mismatch")


def _require_verified_evidence(policy, verified: StructuralEvidenceVerification) -> None:
    if not isinstance(verified, StructuralEvidenceVerification) or not verified.valid:
        raise StructuralEvidenceIntegrityError("evidence verification did not produce valid Evidence")
    payload = verified.payload
    if payload.subject is not EvidenceSubject.STRUCTURAL_ANALYSIS:
        raise StructuralEvidenceIntegrityError("repeatability requires ordinary structural Evidence")
    if policy.source_project_id is not None and payload.request.source_binding.project_id != policy.source_project_id:
        raise StructuralEvidenceIntegrityError("repeatability project identity mismatch")
    if policy.source_definition_id is not None and payload.request.source_binding.definition_id != policy.source_definition_id:
        raise StructuralEvidenceIntegrityError("repeatability definition identity mismatch")
    if policy.source_definition_hash is not None and payload.request.source_binding.definition_hash != policy.source_definition_hash:
        raise StructuralEvidenceIntegrityError("repeatability definition hash mismatch")
    if policy.source_request_hash is not None and payload.request.request_hash != policy.source_request_hash:
        raise StructuralEvidenceIntegrityError("repeatability request identity mismatch")
    tokens = _persisted_identity_tokens(payload)
    if not set(policy.required_provider_identities).issubset(tokens):
        raise StructuralEvidenceIntegrityError("repeatability provider identity requirement is missing")
    if not set(policy.required_runtime_identities).issubset(tokens):
        raise StructuralEvidenceIntegrityError("repeatability runtime identity requirement is missing")


def _require_repeatability_identity(policy, first: StructuralEvidencePayload, second: StructuralEvidencePayload) -> None:
    first_binding = first.request.source_binding
    second_binding = second.request.source_binding
    if (
        first_binding.project_id,
        first_binding.source_revision,
        first_binding.source_state_hash,
        first_binding.definition_id,
        first_binding.definition_hash,
        first_binding.target_body_id,
        first.request.request_hash,
    ) != (
        second_binding.project_id,
        second_binding.source_revision,
        second_binding.source_state_hash,
        second_binding.definition_id,
        second_binding.definition_hash,
        second_binding.target_body_id,
        second.request.request_hash,
    ):
        raise StructuralEvidenceIntegrityError("repeatability source identity mismatch")


def _persisted_identity_tokens(payload: StructuralEvidencePayload) -> set[str]:
    tokens: set[str] = set()
    manifest = payload.execution_manifest
    for value in (
        payload.aggregate_provenance.pipeline_identity,
        manifest.resolver_identity,
        manifest.gmsh_identity,
        manifest.deck_builder_identity,
        manifest.calculix_identity,
        manifest.gmsh_version,
        manifest.calculix_version,
    ):
        tokens.add(value)
    for provenance in (
        payload.aggregate_provenance.geometry_provenance,
        payload.aggregate_provenance.mesh_provenance,
        payload.aggregate_provenance.solver_provenance,
    ):
        for value in (
            provenance.backend_name,
            provenance.backend_adapter_version,
            provenance.library_revision,
        ):
            if value:
                tokens.add(value)
        if provenance.library_name and provenance.library_version:
            tokens.add(f"{provenance.library_name}@{provenance.library_version}")
            tokens.add(f"{provenance.backend_name}@{provenance.library_version}")
    parser = payload.aggregate_provenance.parser_provenance
    tokens.update(
        value
        for value in (
            parser.frd_parser_identity,
            parser.dat_parser_identity,
            parser.interpreter_identity,
        )
        if value
    )
    return tokens


def _compare_summary_field(policy, field_id, first, second):
    first_value = _semantic_summary(first, field_id)
    second_value = _semantic_summary(second, field_id)
    if _summary_is_unavailable(first_value) or _summary_is_unavailable(second_value):
        raise StructuralEvidenceIntegrityError("declared repeatability summary is unavailable")
    absolute_tolerance = dict(policy.absolute_tolerances).get(field_id, 0.0)
    relative_tolerance = dict(policy.relative_tolerances).get(field_id, 0.0)
    structure_first = _summary_structure(first_value)
    structure_second = _summary_structure(second_value)
    if structure_first != structure_second:
        return StructuralRepeatabilityComparison(
            field_id=field_id,
            first_value=first_value,
            second_value=second_value,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
            within_tolerance=False,
        )
    first_numbers = _summary_numbers(first_value)
    second_numbers = _summary_numbers(second_value)
    if not first_numbers:
        within = first_value == second_value
        absolute_difference = relative_difference = None
    else:
        differences = tuple(
            abs(left - right) for left, right in zip(first_numbers, second_numbers, strict=True)
        )
        scales = tuple(max(abs(left), abs(right), 1e-30) for left, right in zip(first_numbers, second_numbers, strict=True))
        absolute_difference = sum(difference * difference for difference in differences) ** 0.5
        relative_difference = max(difference / scale for difference, scale in zip(differences, scales, strict=True))
        within = all(
            difference <= absolute_tolerance + relative_tolerance * scale
            for difference, scale in zip(differences, scales, strict=True)
        )
    return StructuralRepeatabilityComparison(
        field_id=field_id,
        first_value=first_value,
        second_value=second_value,
        absolute_difference=absolute_difference,
        relative_difference=relative_difference,
        absolute_tolerance=absolute_tolerance,
        relative_tolerance=relative_tolerance,
        within_tolerance=within,
    )


def _semantic_summary(payload: StructuralEvidencePayload, field_id: str):
    result = payload.result
    cases = result.load_case_results
    if field_id == "free_end_transverse_displacement_mm":
        validation = payload.analytical_validation
        if validation is None:
            return None
        check = next((item for item in validation.checks if item.check_id == "tip_displacement"), None)
        return (
            None
            if check is None
            else {"metric": validation.policy.tip_displacement_metric, "value": check.observed_value}
        )
    if field_id == "maximum_displacement_mm":
        values = tuple(case.maximum_displacement_mm for case in cases)
        return values[0] if len(values) == 1 else values
    if field_id == "maximum_von_mises_stress_mpa":
        samples = [sample for case in cases for sample in case.stress_samples]
        representations = {sample.representation.value for sample in samples}
        if len(representations) != 1:
            return None
        maximum = max((case.maximum_von_mises_stress_mpa for case in cases if case.maximum_von_mises_stress_mpa is not None), default=None)
        return {"representation": next(iter(representations)), "value": maximum}
    if field_id in {"total_reaction_force_n", "total_reaction_moment_n_mm"}:
        values = tuple(getattr(case, field_id) for case in cases)
        return values[0] if len(values) == 1 else values
    if field_id == "criterion_results":
        return tuple(
            item.model_dump(mode="json")
            for item in sorted(payload.verification.criterion_results, key=lambda item: item.criterion_id)
        )
    if field_id == "analytical_validation":
        validation = payload.analytical_validation
        if validation is None:
            return None
        return {
            "policy_id": validation.policy.policy_id,
            "policy_hash": validation.policy_hash,
            "status": validation.status,
            "checks": tuple(
                {
                    "check_id": check.check_id,
                    "expected_value": check.expected_value,
                    "observed_value": check.observed_value,
                    "tolerance": check.tolerance,
                    "status": check.status,
                    "reason": check.reason,
                }
                for check in sorted(validation.checks, key=lambda item: item.check_id)
            ),
        }
    raise StructuralEvidenceIntegrityError("unsupported repeatability semantic summary")


def _summary_is_unavailable(value) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return "value" in value and value["value"] is None
    if isinstance(value, (tuple, list)):
        return any(child is None for child in value)
    return False


def _summary_structure(value):
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        return "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else type(value).__name__
    if isinstance(value, tuple):
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return ("mapping", tuple((item[0], _summary_structure(item[1])) for item in value))
        return ("sequence", tuple(_summary_structure(item) for item in value))
    if isinstance(value, dict):
        return ("mapping", tuple((key, _summary_structure(value[key])) for key in sorted(value)))
    if isinstance(value, list):
        return ("sequence", tuple(_summary_structure(item) for item in value))
    raise StructuralEvidenceIntegrityError("unsupported repeatability summary value")


def _summary_numbers(value):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return ()
    if isinstance(value, (int, float)):
        return (float(value),)
    if isinstance(value, tuple):
        return tuple(number for item in value for number in _summary_numbers(item))
    if isinstance(value, dict):
        return tuple(number for key in sorted(value) for number in _summary_numbers(value[key]))
    if isinstance(value, list):
        return tuple(number for item in value for number in _summary_numbers(item))
    raise StructuralEvidenceIntegrityError("unsupported repeatability summary value")


class StructuralEvidencePublisher:
    """Publish structural Evidence reconstructed from durable M11-4 authority."""

    def __init__(
        self,
        *,
        workspace: str | Path,
        project_id: str,
        state_manager: StateManager,
        artifact_store: ArtifactStore,
        evidence_store: EvidenceStore,
        request_resolver: Callable[[str], StructuralAnalysisRequest | None] | None = None,
        analytical_validation_factory: Callable[..., tuple[Any, Any, Any]] | None = None,
    ):
        self.workspace = Path(workspace)
        self.project_id = project_id
        self.state_manager = state_manager
        self.artifact_store = artifact_store
        self.evidence_store = evidence_store
        self.request_resolver = request_resolver
        self.analytical_validation_factory = analytical_validation_factory
        self._composed_analytical_validation_factory = analytical_validation_factory

    def publish(
        self,
        *,
        execution_manifest,
        request: StructuralAnalysisRequest | None = None,
        analytical_policy=None,
        execution_manifest_artifact_id: str | None = None,
        execution_manifest_artifact_hash: str | None = None,
    ) -> Evidence:
        try:
            verifier = self._verifier()
            request = self._resolve_request(execution_manifest, request)
            definition = verifier._load_bound_definition(request)
            request.validate_against(definition)
            manifest, store, _manifest_bytes, manifest_artifact = verifier._load_durable_manifest_for_publication(
                execution_manifest,
                request,
                execution_manifest_artifact_id,
                execution_manifest_artifact_hash,
            )
            verifier._verify_direct_manifest_provenance(manifest)
            verified_bytes = verifier._verify_all_artifacts(store, request, definition, manifest)
            result = verifier._reconstruct_result(request, definition, manifest)
            verification = StructuralVerificationService().evaluate(result, definition)

            geometry_observation = None
            material_observation = None
            analytical_validation = None
            if analytical_policy is not None:
                if (
                    self.analytical_validation_factory
                    is not self._composed_analytical_validation_factory
                ):
                    raise StructuralEvidenceIntegrityError(
                        "composed analytical validation factory is untrusted"
                    )
                if self.analytical_validation_factory is None:
                    raise StructuralEvidenceIntegrityError(
                        "trusted analytical validation reconstruction is unavailable"
                    )
                analytical_validation, geometry_observation, material_observation = (
                    self.analytical_validation_factory(
                        execution_manifest=manifest,
                        request=request,
                        definition=definition,
                        result=result,
                        verification=verification,
                        analytical_policy=analytical_policy,
                        mesh_artifact_bytes=verified_bytes["msh"],
                    )
                )

            aggregate = StructuralPipelineProvenance(
                pipeline_identity="mechcad-structural-pipeline@1",
                geometry_provenance=manifest.geometry_provider_provenance,
                mesh_provenance=provenance_from_identity(GMSH_IDENTITY),
                solver_provenance=provenance_from_identity(CALCULIX_IDENTITY),
                parser_provenance=result.parser_provenance,
            )
            payload = StructuralEvidencePayload(
                request=request,
                execution_manifest_artifact_id=manifest_artifact.artifact_id,
                execution_manifest_artifact_hash=manifest_artifact.sha256,
                execution_manifest=manifest,
                result=result,
                verification=verification,
                analytical_validation=analytical_validation,
                analytical_geometry_observation=geometry_observation,
                analytical_material_observation=material_observation,
                aggregate_provenance=aggregate,
            )
            verifier._verify_result_and_criteria(payload, request, manifest, result, verification)
            verifier._verify_analytical_validation(
                payload,
                request,
                definition,
                manifest,
                result,
                verified_bytes["msh"],
            )
            verifier._verify_pipeline_provenance(payload, manifest, result)
            evidence = Evidence(
                id=structural_evidence_id(payload),
                kind=EvidenceSubject.STRUCTURAL_ANALYSIS.value,
                subject=EvidenceSubject.STRUCTURAL_ANALYSIS,
                summary=(
                    f"Structural analysis evidence: {verification.overall_status.value} "
                    f"for {request.source_binding.definition_id}"
                ),
                revision=request.source_binding.source_revision,
                state_hash=request.source_binding.source_state_hash,
                producer_type="structural_evidence",
                producer_name="mechcad-structural-evidence@1",
                producer_version="1",
                producer_result_id=result.result_hash,
                input_hash=request.request_hash,
                output_hash=payload.semantic_hash,
                structural_evidence_payload=payload,
            )
            self.evidence_store.write_evidence(self.project_id, evidence)
            self._fresh_verifier(manifest.run_id).verify(evidence.id)
            return evidence
        except StructuralEvidenceIntegrityError:
            raise
        except Exception as exc:
            raise StructuralEvidenceIntegrityError(str(exc) or "structural evidence integrity failure") from exc

    def _resolve_request(self, execution_manifest, request):
        request_hash = getattr(execution_manifest, "request_hash", None)
        resolved = self.request_resolver(request_hash) if request is None and self.request_resolver else None
        resolved = resolved or request
        if not isinstance(resolved, StructuralAnalysisRequest):
            raise StructuralEvidenceIntegrityError("the bound structural request is unavailable")
        if resolved.request_hash != request_hash:
            raise StructuralEvidenceIntegrityError("structural request/manifest binding mismatch")
        return StructuralAnalysisRequest.model_validate(resolved.model_dump(mode="json"))

    def _verifier(self) -> "StructuralEvidenceVerifier":
        return StructuralEvidenceVerifier(
            workspace=self.workspace,
            project_id=self.project_id,
            state_manager=self.state_manager,
            artifact_store=self.artifact_store,
            evidence_store=self.evidence_store,
        )

    def _fresh_verifier(self, run_id: str) -> "StructuralEvidenceVerifier":
        fresh_state_manager = StateManager(self.workspace)
        return StructuralEvidenceVerifier(
            workspace=self.workspace,
            project_id=self.project_id,
            state_manager=fresh_state_manager,
            artifact_store=ArtifactStore(self.workspace, project_id=self.project_id, run_id=run_id),
            evidence_store=EvidenceStore(self.workspace, fresh_state_manager, self.evidence_store.graph),
        )


class StructuralEvidenceVerifier:
    """Reload and verify structural evidence without discovering runtimes."""

    def __init__(
        self,
        *,
        workspace: str | Path,
        project_id: str,
        state_manager: StateManager,
        artifact_store: ArtifactStore,
        evidence_store: EvidenceStore,
    ):
        self.workspace = Path(workspace)
        self.project_id = project_id
        self.state_manager = state_manager
        self.artifact_store = artifact_store
        self.evidence_store = evidence_store

    def verify(self, evidence_id: str) -> StructuralEvidenceVerification:
        try:
            evidence = self.evidence_store.load_evidence(self.project_id, evidence_id)
            if evidence.id != evidence_id:
                raise StructuralEvidenceIntegrityError("Evidence ID binding mismatch")
            payload = self._require_payload(evidence)
            self._verify_evidence_binding(evidence, payload)
            if payload.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY:
                return self._verify_convergence_evidence(evidence, payload)
            request = self._reconstruct_request(payload)
            definition = self._load_bound_definition(request)
            request.validate_against(definition)
            manifest, store, manifest_bytes = self._load_verified_manifest(payload, request)
            self._verify_direct_provenance(payload, manifest)
            verified_bytes = self._verify_all_artifacts(store, request, definition, manifest)
            result = self._reconstruct_result(request, definition, manifest)
            verification = StructuralVerificationService().evaluate(result, definition)
            self._verify_result_and_criteria(payload, request, manifest, result, verification)
            self._verify_analytical_validation(
                payload, request, definition, manifest, result, verified_bytes["msh"]
            )
            self._verify_pipeline_provenance(payload, manifest, result)
            return StructuralEvidenceVerification(
                evidence_id=evidence.id,
                payload=payload,
                valid=True,
                engineering_status=verification.overall_status,
                request_hash=request.request_hash,
                result_hash=result.result_hash,
                verification_hash=verification.verification_hash,
            )
        except StructuralEvidenceIntegrityError:
            raise
        except Exception as exc:
            raise StructuralEvidenceIntegrityError(str(exc) or "structural evidence integrity failure") from exc

    def currentness(self, evidence_id: str) -> StructuralEvidenceCurrentness:
        try:
            evidence = self.evidence_store.load_evidence(self.project_id, evidence_id)
            if evidence.id != evidence_id:
                raise StructuralEvidenceIntegrityError("Evidence ID binding mismatch")
            payload = self._require_payload(evidence)
            self._verify_evidence_binding(evidence, payload)
        except StructuralEvidenceIntegrityError:
            raise
        except Exception as exc:
            raise StructuralEvidenceIntegrityError(str(exc) or "structural evidence integrity failure") from exc
        if payload.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY:
            convergence = payload.convergence
            if convergence is None or not convergence.levels:
                raise StructuralEvidenceIntegrityError("convergence level evidence bindings are missing")
            level_ids = tuple(level.evidence_id for level in convergence.levels)
            if len(set(level_ids)) != len(level_ids):
                raise StructuralEvidenceIntegrityError("convergence level evidence IDs are not unique")
            level_payloads = []
            for level in convergence.levels:
                try:
                    level_evidence = self.evidence_store.load_evidence(self.project_id, level.evidence_id)
                    if level_evidence.id != level.evidence_id:
                        raise StructuralEvidenceIntegrityError("convergence level Evidence ID binding mismatch")
                    level_payload = self._require_payload(level_evidence)
                    self._verify_evidence_binding(level_evidence, level_payload)
                except StructuralEvidenceIntegrityError:
                    raise
                except Exception as exc:
                    raise StructuralEvidenceIntegrityError(
                        "convergence level Evidence is unavailable or malformed"
                    ) from exc
                if (
                    level_payload.subject is not EvidenceSubject.STRUCTURAL_ANALYSIS
                    or level.evidence_hash != level_payload.semantic_hash
                ):
                    raise StructuralEvidenceIntegrityError("convergence level Evidence binding mismatch")
                level_payloads.append(level_payload)
            first_source = level_payloads[0].request.source_binding
            for level_payload in level_payloads[1:]:
                source = level_payload.request.source_binding
                if (
                    source.project_id,
                    source.source_revision,
                    source.source_state_hash,
                ) != (
                    first_source.project_id,
                    first_source.source_revision,
                    first_source.source_state_hash,
                ):
                    raise StructuralEvidenceIntegrityError("convergence level source binding mismatch")
            if (
                evidence.revision != first_source.source_revision
                or evidence.state_hash != first_source.source_state_hash
            ):
                raise StructuralEvidenceIntegrityError("convergence source binding mismatch")
            binding = first_source
        else:
            binding = payload.request.source_binding
        try:
            current = self.state_manager.load_current_pointer(self.project_id)
        except Exception:
            return StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE
        if (
            not isinstance(current, dict)
            or current.get("project_id") != self.project_id
            or not isinstance(current.get("revision"), int)
            or isinstance(current.get("revision"), bool)
            or current.get("revision") <= 0
            or not isinstance(current.get("state_hash"), str)
            or not current.get("state_hash")
        ):
            return StructuralEvidenceCurrentness.CURRENTNESS_UNAVAILABLE
        if (current.get("revision"), current.get("state_hash")) == (
            binding.source_revision,
            binding.source_state_hash,
        ):
            return StructuralEvidenceCurrentness.CURRENT
        return StructuralEvidenceCurrentness.STALE_RELATIVE_TO_CURRENT_STATE

    @staticmethod
    def _require_payload(evidence: Evidence) -> StructuralEvidencePayload:
        if not isinstance(evidence, Evidence):
            raise StructuralEvidenceIntegrityError("evidence record is not typed")
        payload = evidence.structural_evidence_payload
        if not isinstance(payload, StructuralEvidencePayload) or payload.schema_version != "structural-evidence@1":
            raise StructuralEvidenceIntegrityError("evidence is not a supported structural analysis record")
        if evidence.kind != payload.subject.value or evidence.subject is not payload.subject:
            raise StructuralEvidenceIntegrityError("structural evidence discriminator mismatch")
        expected = structural_evidence_hash(payload)
        if payload.semantic_hash != expected:
            raise StructuralEvidenceIntegrityError("structural evidence semantic hash mismatch")
        return payload

    def _verify_evidence_binding(self, evidence: Evidence, payload: StructuralEvidencePayload) -> None:
        if evidence.id != structural_evidence_id(payload):
            raise StructuralEvidenceIntegrityError("Evidence deterministic identity mismatch")
        if payload.subject is EvidenceSubject.STRUCTURAL_CONVERGENCE_STUDY:
            self._verify_convergence_generic_binding(evidence, payload)
            return
        request = payload.request
        if evidence.revision != request.source_binding.source_revision:
            raise StructuralEvidenceIntegrityError("Evidence source revision binding mismatch")
        if evidence.state_hash != request.source_binding.source_state_hash:
            raise StructuralEvidenceIntegrityError("Evidence source state binding mismatch")
        if evidence.input_hash != request.request_hash:
            raise StructuralEvidenceIntegrityError("Evidence request binding mismatch")
        if evidence.output_hash != payload.semantic_hash:
            raise StructuralEvidenceIntegrityError("Evidence payload output hash mismatch")
        if evidence.producer_result_id != payload.result.result_hash:
            raise StructuralEvidenceIntegrityError("Evidence result binding mismatch")
        if (
            evidence.producer_type != "structural_evidence"
            or evidence.producer_name != "mechcad-structural-evidence@1"
            or evidence.producer_version != "1"
        ):
            raise StructuralEvidenceIntegrityError("Evidence producer binding mismatch")

    def _verify_convergence_generic_binding(
        self, evidence: Evidence, payload: StructuralEvidencePayload
    ) -> None:
        convergence = payload.convergence
        if convergence is None:
            raise StructuralEvidenceIntegrityError("convergence result is missing")
        if evidence.producer_type != "structural_mesh_convergence":
            raise StructuralEvidenceIntegrityError("convergence Evidence producer binding mismatch")
        if (
            evidence.producer_name != "mechcad-structural-convergence@1"
            or evidence.producer_version != "1"
            or evidence.input_hash != convergence.study_hash
            or evidence.output_hash != payload.semantic_hash
            or evidence.producer_result_id != convergence.result_hash
        ):
            raise StructuralEvidenceIntegrityError("convergence Evidence generic binding mismatch")

    def _verify_convergence_evidence(
        self, evidence: Evidence, payload: StructuralEvidencePayload
    ) -> StructuralEvidenceVerification:
        convergence = payload.convergence
        if convergence is None:
            raise StructuralEvidenceIntegrityError("convergence result is missing")
        study = convergence.study
        if study.study_hash != structural_mesh_convergence_study_hash(study):
            raise StructuralEvidenceIntegrityError("mesh convergence study hash mismatch")
        if convergence.study_hash != study.study_hash:
            raise StructuralEvidenceIntegrityError("mesh convergence result study hash mismatch")
        if convergence.result_hash != structural_mesh_convergence_result_hash(convergence):
            raise StructuralEvidenceIntegrityError("mesh convergence result hash mismatch")

        level_ids = tuple(level.evidence_id for level in convergence.levels)
        if len(set(level_ids)) != len(level_ids):
            raise StructuralEvidenceIntegrityError("convergence level evidence IDs are not unique")
        if not level_ids:
            raise StructuralEvidenceIntegrityError("convergence level evidence bindings are missing")
        verified_levels = tuple(self.verify(level_id) for level_id in level_ids)
        level_payloads = tuple(
            StructuralMeshConvergenceService._require_level(level_id, verified)
            for level_id, verified in zip(level_ids, verified_levels, strict=True)
        )
        for level, level_payload in zip(convergence.levels, level_payloads, strict=True):
            if level.evidence_hash != level_payload.semantic_hash:
                raise StructuralEvidenceIntegrityError("convergence level evidence hash mismatch")

        first_source = level_payloads[0].request.source_binding
        if (
            evidence.revision != first_source.source_revision
            or evidence.state_hash != first_source.source_state_hash
        ):
            raise StructuralEvidenceIntegrityError("convergence source binding mismatch")
        recomputed = StructuralMeshConvergenceService(self).evaluate(
            study=study,
            level_evidence_ids=level_ids,
        )
        if recomputed.status is StructuralMeshConvergenceStatus.INTEGRITY_FAILURE:
            raise StructuralEvidenceIntegrityError(recomputed.reason)
        if recomputed != convergence:
            raise StructuralEvidenceIntegrityError("convergence result recomputation mismatch")
        return StructuralEvidenceVerification(
            evidence_id=evidence.id,
            payload=payload,
            valid=True,
            engineering_status=None,
            result_hash=convergence.result_hash,
        )

    def _reconstruct_request(self, payload: StructuralEvidencePayload) -> StructuralAnalysisRequest:
        request = StructuralAnalysisRequest.model_validate(payload.request.model_dump(mode="json"))
        if request.request_hash != structural_request_hash(request):
            raise StructuralEvidenceIntegrityError("structural request hash mismatch")
        if request.source_binding.project_id != self.project_id:
            raise StructuralEvidenceIntegrityError("structural request project binding mismatch")
        return request

    def _load_bound_definition(self, request: StructuralAnalysisRequest):
        try:
            state = self.state_manager.load_revision(
                request.source_binding.project_id,
                request.source_binding.source_revision,
            )
        except Exception as exc:
            raise StructuralEvidenceIntegrityError("bound source revision is unavailable") from exc
        if state_hash(state) != request.source_binding.source_state_hash:
            raise StructuralEvidenceIntegrityError("bound source revision state hash mismatch")
        definitions = tuple(
            definition
            for definition in state.structural_analysis_definitions
            if definition.id == request.source_binding.definition_id
        )
        if len(definitions) != 1:
            raise StructuralEvidenceIntegrityError("canonical structural definition is unavailable")
        definition = definitions[0]
        if structural_definition_hash(definition) != request.source_binding.definition_hash:
            raise StructuralEvidenceIntegrityError("canonical structural definition hash mismatch")
        if definition.target_body_id != request.source_binding.target_body_id:
            raise StructuralEvidenceIntegrityError("structural target body binding mismatch")
        return definition

    def _run_store(self, run_id: str) -> ArtifactStore:
        if (
            getattr(self.artifact_store, "project_id", None) == self.project_id
            and getattr(self.artifact_store, "run_id", None) == run_id
        ):
            return self.artifact_store
        return ArtifactStore(self.workspace, project_id=self.project_id, run_id=run_id)

    def _load_verified_manifest(self, payload, request):
        manifest_from_payload = payload.execution_manifest
        if manifest_from_payload.run_id is None:
            raise StructuralEvidenceIntegrityError("execution manifest run identity is missing")
        store = self._run_store(manifest_from_payload.run_id)
        try:
            verified = store.read_verified_strict(
                payload.execution_manifest_artifact_id,
                expected_type=ArtifactType.JSON,
                expected_hash=payload.execution_manifest_artifact_hash,
            )
        except ArtifactVerificationError as exc:
            raise StructuralEvidenceIntegrityError("execution manifest artifact is not trusted") from exc
        artifact, content = verified
        self._verify_artifact_metadata(
            artifact,
            manifest_from_payload,
            ArtifactType.JSON,
            expected_producer=manifest_from_payload.deck_builder_identity,
            expected_version=manifest_from_payload.deck_builder_version,
            expected_input_hash=request.request_hash,
        )
        try:
            durable_manifest = StructuralExecutionManifest.model_validate_json(content)
        except Exception as exc:
            raise StructuralEvidenceIntegrityError("execution manifest JSON is invalid") from exc
        if durable_manifest != manifest_from_payload:
            raise StructuralEvidenceIntegrityError("execution manifest content binding mismatch")
        if durable_manifest.project_id != request.source_binding.project_id:
            raise StructuralEvidenceIntegrityError("execution manifest project binding mismatch")
        if execution_manifest_hash(durable_manifest) != execution_manifest_hash(manifest_from_payload):
            raise StructuralEvidenceIntegrityError("execution manifest hash binding mismatch")
        return durable_manifest, store, content

    def _load_durable_manifest_for_publication(
        self,
        supplied_manifest,
        request,
        manifest_artifact_id,
        manifest_artifact_hash,
    ):
        if not isinstance(supplied_manifest, StructuralExecutionManifest):
            raise StructuralEvidenceIntegrityError("structural execution manifest is required")
        if supplied_manifest.run_id is None:
            raise StructuralEvidenceIntegrityError("execution manifest run identity is missing")
        if not manifest_artifact_id or not manifest_artifact_hash:
            raise StructuralEvidenceIntegrityError("explicit execution manifest artifact binding is required")
        store = self._run_store(supplied_manifest.run_id)
        try:
            artifact, content = store.read_verified_strict(
                manifest_artifact_id,
                expected_type=ArtifactType.JSON,
                expected_hash=manifest_artifact_hash,
            )
        except ArtifactVerificationError as exc:
            raise StructuralEvidenceIntegrityError("execution manifest artifact is not trusted")
        self._verify_artifact_metadata(
            artifact,
            supplied_manifest,
            ArtifactType.JSON,
            expected_producer=supplied_manifest.deck_builder_identity,
            expected_version=supplied_manifest.deck_builder_version,
            expected_input_hash=request.request_hash,
        )
        try:
            durable_manifest = StructuralExecutionManifest.model_validate_json(content)
        except Exception as exc:
            raise StructuralEvidenceIntegrityError("execution manifest JSON is invalid") from exc
        if durable_manifest != supplied_manifest:
            raise StructuralEvidenceIntegrityError("execution manifest content binding mismatch")
        if durable_manifest.request_hash != request.request_hash:
            raise StructuralEvidenceIntegrityError("execution manifest request binding mismatch")
        return durable_manifest, store, content, artifact

    def _verify_all_artifacts(self, store, request, definition, manifest):
        interpreter = StructuralResultInterpreter(
            workspace=self.workspace,
            project_id=self.project_id,
            request=request,
            definition=definition,
        )
        try:
            interpreter._verify_manifest_binding(manifest, request, definition)
        except Exception as exc:
            raise StructuralEvidenceIntegrityError(str(exc)) from exc

        try:
            source_verified = store.read_verified_in_project(
                request.source_binding.geometry_artifact_id,
                expected_type=ArtifactType.STEP,
                expected_hash=request.source_binding.geometry_artifact_hash,
            )
        except ArtifactVerificationError as exc:
            raise StructuralEvidenceIntegrityError("STEP artifact is not trusted") from exc
        if source_verified is None:
            raise StructuralEvidenceIntegrityError("STEP artifact is not trusted")
        source_artifact, source_bytes = source_verified
        self._verify_artifact_metadata(
            source_artifact,
            manifest,
            ArtifactType.STEP,
            expected_producer="mechcad-freecad",
            expected_version=manifest.geometry_provider_provenance.backend_adapter_version,
            expected_input_hash=request.source_binding.source_program_hash,
            expected_backend=manifest.geometry_provider_provenance,
            require_manifest_ref=True,
            allow_different_run=True,
        )
        if not self._is_trusted_freecad_provenance(source_artifact.backend_provenance):
            raise StructuralEvidenceIntegrityError("source STEP producer provenance is not trusted")
        mesh_input = self._mesh_input_hash(request, manifest)
        mesh_artifact, mesh_bytes = self._read_artifact(
            store,
            manifest.mesh_artifact_id,
            manifest.mesh_artifact_hash,
            ArtifactType.MSH,
            manifest,
            expected_producer=manifest.gmsh_identity,
            expected_version=manifest.gmsh_version,
            expected_input_hash=mesh_input,
            expected_backend=provenance_from_identity(GMSH_IDENTITY),
            require_manifest_ref=True,
        )
        cases: dict[str, dict[str, bytes]] = {}
        for case in manifest.case_manifests:
            solver = case.solver_manifest
            if solver is None:
                raise StructuralEvidenceIntegrityError("case solver provenance is missing")
            case_bytes: dict[str, bytes] = {}
            deck_artifact, case_bytes["inp"] = self._read_artifact(
                store, case.deck_artifact_id, case.deck_artifact_hash, ArtifactType.INP, manifest,
                expected_producer=case.deck_builder_identity or manifest.deck_builder_identity,
                expected_version=case.deck_builder_version or manifest.deck_builder_version,
                expected_input_hash=manifest.mesh_artifact_hash,
                require_manifest_ref=True,
            )
            if case.deck_semantic_hash != self._sha256(case_bytes["inp"]):
                raise StructuralEvidenceIntegrityError("INP deck semantic hash mismatch")
            for name, artifact_id, artifact_hash, artifact_type in (
                ("frd", case.frd_artifact_id, case.frd_artifact_hash, ArtifactType.FRD),
                ("dat", case.dat_artifact_id, case.dat_artifact_hash, ArtifactType.DAT),
                ("log", case.log_artifact_id, case.log_artifact_hash, ArtifactType.LOG),
            ):
                _artifact, case_bytes[name] = self._read_artifact(
                    store, artifact_id, artifact_hash, artifact_type, manifest,
                    expected_producer=solver.calculix_identity,
                    expected_version=solver.calculix_version,
                    expected_input_hash=case.deck_artifact_hash,
                    expected_backend=provenance_from_identity(CALCULIX_IDENTITY),
                    require_manifest_ref=True,
                )
            cases[case.load_case_id] = case_bytes
        return {"step": source_bytes, "msh": mesh_bytes, "cases": cases}

    def _read_artifact(
        self,
        store,
        artifact_id,
        artifact_hash,
        artifact_type,
        manifest,
        *,
        expected_producer=None,
        expected_version=None,
        expected_input_hash=None,
        expected_backend=None,
        require_manifest_ref=False,
    ):
        if not artifact_id or not artifact_hash:
            raise StructuralEvidenceIntegrityError(f"{artifact_type.value.upper()} artifact binding is incomplete")
        try:
            verified = store.read_verified_strict(
                artifact_id, expected_type=artifact_type, expected_hash=artifact_hash
            )
        except ArtifactVerificationError as exc:
            raise StructuralEvidenceIntegrityError(f"{artifact_type.value.upper()} artifact is not trusted") from exc
        artifact, content = verified
        self._verify_artifact_metadata(
            artifact,
            manifest,
            artifact_type,
            expected_producer=expected_producer,
            expected_version=expected_version,
            expected_input_hash=expected_input_hash,
            expected_backend=expected_backend,
            require_manifest_ref=require_manifest_ref,
        )
        return artifact, content

    @staticmethod
    def _verify_artifact_metadata(
        artifact,
        manifest,
        expected_type,
        *,
        expected_producer=None,
        expected_version=None,
        expected_input_hash=None,
        expected_backend=None,
        require_manifest_ref=False,
        allow_different_run=False,
    ):
        if (
            artifact.artifact_type is not expected_type
            or artifact.project_id != manifest.project_id
            or (not allow_different_run and artifact.run_id != manifest.run_id)
            or artifact.bound_revision != manifest.revision
            or artifact.bound_state_hash != manifest.state_hash
        ):
            raise StructuralEvidenceIntegrityError(f"{expected_type.value.upper()} artifact binding mismatch")
        if expected_producer is not None and artifact.producer_tool_name != expected_producer:
            raise StructuralEvidenceIntegrityError(f"{expected_type.value.upper()} artifact producer mismatch")
        if expected_version is not None and artifact.producer_tool_version != expected_version:
            raise StructuralEvidenceIntegrityError(f"{expected_type.value.upper()} artifact producer version mismatch")
        if expected_input_hash is not None and artifact.input_hash != expected_input_hash:
            raise StructuralEvidenceIntegrityError(f"{expected_type.value.upper()} artifact input binding mismatch")
        if expected_backend is not None and artifact.backend_provenance != expected_backend:
            raise StructuralEvidenceIntegrityError(f"{expected_type.value.upper()} artifact backend provenance mismatch")
        ref = next((item for item in manifest.artifacts if item.artifact_id == artifact.artifact_id), None)
        if require_manifest_ref and ref is None:
            raise StructuralEvidenceIntegrityError(f"{expected_type.value.upper()} artifact manifest reference is missing")
        if ref is not None and (
            ref.artifact_type != expected_type.value
            or ref.sha256 != artifact.sha256
            or ref.producer_identity != artifact.producer_tool_name
            or ref.producer_version != artifact.producer_tool_version
        ):
            raise StructuralEvidenceIntegrityError(f"{expected_type.value.upper()} artifact manifest reference mismatch")

    def _reconstruct_result(self, request, definition, manifest):
        try:
            return StructuralResultInterpreter(
                workspace=self.workspace,
                project_id=self.project_id,
                request=request,
                definition=definition,
                frd_parser=CalculiXFrdResultParser(),
                dat_parser=CalculiXDatResultParser(),
            ).interpret(manifest, request=request, definition=definition)
        except Exception as exc:
            raise StructuralEvidenceIntegrityError("trusted structural result reconstruction failed") from exc

    def _verify_result_and_criteria(self, payload, request, manifest, result, verification):
        if structural_result_hash(payload.result) != payload.result.result_hash:
            raise StructuralEvidenceIntegrityError("persisted structural result hash mismatch")
        if result.result_hash != payload.result.result_hash:
            raise StructuralEvidenceIntegrityError("reconstructed structural result hash mismatch")
        if result != payload.result.model_copy(update={"run_id": result.run_id}):
            raise StructuralEvidenceIntegrityError("persisted structural result content mismatch")
        if result.execution_manifest_hash != execution_manifest_hash(manifest):
            raise StructuralEvidenceIntegrityError("structural result execution binding mismatch")
        if structural_verification_hash(payload.verification) != payload.verification.verification_hash:
            raise StructuralEvidenceIntegrityError("persisted structural verification hash mismatch")
        if verification != payload.verification:
            raise StructuralEvidenceIntegrityError("reconstructed structural verification findings mismatch")
        if verification.overall_status not in {
            StructuralCriterionStatus.PASS,
            StructuralCriterionStatus.FAIL,
            StructuralCriterionStatus.NOT_EVALUABLE,
        }:
            raise StructuralEvidenceIntegrityError("unsupported structural engineering status")

    def _verify_analytical_validation(self, payload, request, definition, manifest, result, mesh_bytes):
        validation = payload.analytical_validation
        observations = (
            payload.analytical_geometry_observation,
            payload.analytical_material_observation,
        )
        if validation is None:
            if any(observation is not None for observation in observations):
                raise StructuralEvidenceIntegrityError("analytical observations are incomplete")
            return
        if any(observation is None for observation in observations):
            raise StructuralEvidenceIntegrityError("analytical validation observations are incomplete")
        try:
            reconstructed = reconstruct_analytical_validation(
                result,
                validation,
                request=request,
                execution_manifest=manifest,
                mesh_artifact_bytes=mesh_bytes,
                geometry_observation=observations[0],
                material_observation=observations[1],
                definition=definition,
            )
        except Exception as exc:
            raise StructuralEvidenceIntegrityError("analytical validation reconstruction failed") from exc
        if reconstructed != validation:
            raise StructuralEvidenceIntegrityError("analytical validation findings mismatch")

    @staticmethod
    def _verify_direct_provenance(payload, manifest):
        StructuralEvidenceVerifier._verify_direct_manifest_provenance(manifest)
        aggregate = payload.aggregate_provenance
        if (
            aggregate.pipeline_identity != "mechcad-structural-pipeline@1"
            or aggregate.pipeline_version != "1"
        ):
            raise StructuralEvidenceIntegrityError("aggregate pipeline provenance is untrusted")
        if aggregate.geometry_provenance != manifest.geometry_provider_provenance:
            raise StructuralEvidenceIntegrityError("aggregate geometry provenance does not match direct provenance")
        if aggregate.mesh_provenance != provenance_from_identity(GMSH_IDENTITY):
            raise StructuralEvidenceIntegrityError("aggregate mesh provenance is untrusted")
        if aggregate.solver_provenance != provenance_from_identity(CALCULIX_IDENTITY):
            raise StructuralEvidenceIntegrityError("aggregate solver provenance is untrusted")

    @staticmethod
    def _verify_direct_manifest_provenance(manifest):
        if not StructuralEvidenceVerifier._is_trusted_freecad_provenance(manifest.geometry_provider_provenance):
            raise StructuralEvidenceIntegrityError("direct geometry producer provenance is untrusted")
        if (
            manifest.resolver_identity != REGION_RESOLVER_IDENTITY
            or manifest.resolver_version != REGION_RESOLVER_VERSION
            or manifest.gmsh_identity != GMSH_PROVIDER_IDENTITY
            or manifest.gmsh_version != GMSH_IDENTITY.library_version
            or manifest.deck_builder_identity != DECK_BUILDER_IDENTITY
            or manifest.deck_builder_version != DECK_BUILDER_VERSION
            or manifest.calculix_identity != CALCULIX_PROVIDER_IDENTITY
            or manifest.calculix_version != CALCULIX_IDENTITY.library_version
        ):
            raise StructuralEvidenceIntegrityError("direct mesh or solver producer identity is untrusted")
        for case in manifest.case_manifests:
            solver = case.solver_manifest
            if solver is None or solver.backend_provenance != provenance_from_identity(CALCULIX_IDENTITY):
                raise StructuralEvidenceIntegrityError("direct solver producer provenance is untrusted")

    @staticmethod
    def _verify_pipeline_provenance(payload, manifest, result):
        expected = StructuralResultParserProvenance()
        if payload.aggregate_provenance.parser_provenance != expected:
            raise StructuralEvidenceIntegrityError("parser provenance is untrusted")
        if result.parser_provenance != expected:
            raise StructuralEvidenceIntegrityError("result parser provenance is untrusted")

    @staticmethod
    def _is_trusted_freecad_provenance(provenance) -> bool:
        return provenance is not None and provenance == provenance_from_identity(FREECAD_IDENTITY)

    @staticmethod
    def _mesh_input_hash(request, manifest) -> str:
        payload = {
            "source_geometry_hash": request.source_binding.geometry_artifact_hash,
            "mesh_specification_hash": manifest.mesh_specification_hash,
            "region_map_hash": manifest.region_map_hash,
            "gmsh_identity": manifest.gmsh_identity,
            "gmsh_version": manifest.gmsh_version,
        }
        return "sha256:" + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _sha256(content: bytes) -> str:
        return "sha256:" + hashlib.sha256(content).hexdigest()
