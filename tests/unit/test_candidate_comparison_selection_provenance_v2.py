from __future__ import annotations

import hashlib

from mechcad_harness.candidates import CandidateProvenanceArtifactService
from mechcad_harness.candidates.comparison import (
    CandidateComparisonPolicy,
    CandidateComparisonService,
)
from mechcad_harness.candidates.selection import CandidateSelectionService
from mechcad_harness.application import ProductionApplication
from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceArtifactService

from test_candidate_decision_v2 import (
    _comparison_request,
    _decision_evaluation,
    _verify_candidate_cad_v2,
)


def _published_v2_parents(tmp_path):
    records = _decision_evaluation(tmp_path)
    candidate = records["candidate"]
    service = CandidateProvenanceArtifactService(
        tmp_path,
        candidate.source_binding.project_id,
        records["manager"],
        cad_replay_verifier=_verify_candidate_cad_v2,
    )
    cad = service.publish_candidate_cad(
        candidate,
        records["synthesis_request"],
        records["synthesis_policy"],
        records["cad_request"],
        records["cad_realization"],
        source_step_artifacts=None,
    )
    from mechcad_harness.models.evidence import Evidence

    evidence_dir = (
        tmp_path
        / "projects"
        / candidate.source_binding.project_id
        / "evidence"
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for kind, prefix, items in (
        (
            "analysis.continuous_clearance_proof",
            "EVD-CPROOF-",
            records["evaluation"].m10_stage_outcome.pair_proofs,
        ),
        (
            "analysis.kinematic_sweep",
            "EVD-KSWEEP-",
            records["evaluation"].m10_stage_outcome.home_exact_checks,
        ),
    ):
        for item in items:
            evidence_id = prefix + hashlib.sha256(
                (item.request_hash + item.result_hash).encode()
            ).hexdigest()[:24]
            evidence = Evidence(
                id=evidence_id,
                kind=kind,
                summary="V2 provenance fixture evidence",
                revision=candidate.source_binding.source_revision,
                state_hash=candidate.source_binding.source_state_hash,
                producer_result_id=item.result_hash,
                input_hash=item.request_hash,
                output_hash=item.result_hash,
            )
            (evidence_dir / f"{evidence_id}.json").write_text(
                evidence.model_dump_json(), encoding="utf-8"
            )
    evaluation = service.publish_candidate_evaluation(
        cad, records["evaluation"]
    )
    return records, service, cad, evaluation


def test_comparison_provenance_v2_publishes_and_resolves_typed_parents(tmp_path):
    records, service, _, evaluation_artifact = _published_v2_parents(tmp_path)
    candidate = records["candidate"]
    evaluation = records["evaluation"]
    policy = CandidateComparisonPolicy()
    entries = ((candidate, evaluation),)
    request = _comparison_request((records,), policy)
    requests = {candidate.candidate_hash: records["synthesis_request"]}
    result = CandidateComparisonService(
        policy,
        project_id=candidate.source_binding.project_id,
        currentness_verifier=records["currentness"],
    ).compare(
        request,
        entries,
        synthesis_requests_by_candidate_hash=requests,
    )

    published = service.publish_candidate_comparison(
        request, result, (evaluation_artifact.artifact,)
    )
    fresh_service = CandidateProvenanceArtifactService(
        tmp_path,
        candidate.source_binding.project_id,
        records["manager"],
        cad_replay_verifier=_verify_candidate_cad_v2,
    )
    resolved = fresh_service.resolve_candidate_comparison(
        published.artifact.artifact_id
    )

    assert resolved.payload.schema_version == "candidate-comparison-provenance@2"
    assert set(type(resolved.payload).model_fields) == {
        "schema_version",
        "request",
        "result",
        "candidate_cad_artifacts",
        "candidate_evaluation_artifacts",
    }
    assert resolved.payload.request == request
    assert resolved.payload.result == result


def test_selection_provenance_v2_publishes_and_resolves_typed_parents(tmp_path):
    records, service, cad, evaluation_artifact = _published_v2_parents(tmp_path)
    candidate = records["candidate"]
    evaluation = records["evaluation"]
    synthesis_request = records["synthesis_request"]
    policy = CandidateComparisonPolicy()
    entries = ((candidate, evaluation),)
    requests = {candidate.candidate_hash: synthesis_request}
    comparison_request = _comparison_request((records,), policy)
    comparison = CandidateComparisonService(
        policy,
        project_id=candidate.source_binding.project_id,
        currentness_verifier=records["currentness"],
    ).compare(
        comparison_request,
        entries,
        synthesis_requests_by_candidate_hash=requests,
    )
    comparison_artifact = service.publish_candidate_comparison(
        comparison_request, comparison, (evaluation_artifact.artifact,)
    )
    selection = CandidateSelectionService(
        project_id=candidate.source_binding.project_id,
        currentness_verifier=records["currentness"],
    ).select(
        candidate,
        evaluation,
        "p7-provenance-test@1",
        "explicit semantic selection",
        comparison=comparison,
        comparison_entries=entries,
        synthesis_request=synthesis_request,
        synthesis_requests_by_candidate_hash=requests,
    )

    published = service.publish_candidate_selection(
        selection,
        cad.artifact,
        evaluation_artifact.artifact,
        comparison_artifact.artifact,
    )
    fresh_service = CandidateProvenanceArtifactService(
        tmp_path,
        candidate.source_binding.project_id,
        records["manager"],
        cad_replay_verifier=_verify_candidate_cad_v2,
    )
    resolved = fresh_service.resolve_candidate_selection(
        published.artifact.artifact_id
    )

    assert resolved.payload.schema_version == "candidate-selection-provenance@2"
    assert set(type(resolved.payload).model_fields) == {
        "schema_version",
        "selection",
        "candidate_cad",
        "evaluation",
        "comparison",
    }
    assert resolved.payload.selection == selection


def test_application_publishes_v2_comparison_and_selection(tmp_path):
    records, service, _, _ = _published_v2_parents(tmp_path)
    candidate = records["candidate"]
    evaluation = records["evaluation"]
    synthesis_request = records["synthesis_request"]
    policy = CandidateComparisonPolicy()
    entries = ((candidate, evaluation),)
    requests = {candidate.candidate_hash: synthesis_request}
    request = _comparison_request((records,), policy)
    application = object.__new__(ProductionApplication)
    application.project_id = candidate.source_binding.project_id
    application.state_manager = records["manager"]
    application.candidate_comparison_service = CandidateComparisonService(
        policy,
        project_id=application.project_id,
        currentness_verifier=records["currentness"],
    )
    application.candidate_selection_service = CandidateSelectionService(
        project_id=application.project_id,
        currentness_verifier=records["currentness"],
    )
    application.candidate_provenance_artifact_service = service

    comparison = application.compare_candidates(
        request, entries, synthesis_requests_by_candidate_hash=requests
    )

    comparison_artifact_id = application._candidate_provenance_artifact_id(
        "CANDIDATE-COMPARISON-", comparison.result_hash
    )
    resolved_comparison = service.resolve_candidate_comparison(
        comparison_artifact_id
    )
    selection = application.select_candidate(
        candidate,
        evaluation,
        "p7-provenance-test@1",
        "explicit semantic selection",
        comparison=comparison,
        comparison_entries=entries,
        synthesis_request=synthesis_request,
        synthesis_requests_by_candidate_hash=requests,
    )
    resolved_selection = service.resolve_candidate_selection(
        application._candidate_provenance_artifact_id(
            "CANDIDATE-SELECTION-", selection.selection_hash
        )
    )

    assert resolved_comparison.payload.result == comparison
    assert resolved_selection.payload.selection == selection
