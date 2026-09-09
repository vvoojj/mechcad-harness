from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from mechcad_harness.candidates import (
    CandidateMultiJointPromotionApplicationResult,
    MultiJointPromotionResultManifest,
    PromotionManifestService,
    multi_joint_result_manifest_hash,
    PromotionApplicationStatus,
    resolve_multi_joint_result,
)
from mechcad_harness.artifacts import ArtifactType
from mechcad_harness.changes.engine import AppliedChangeResult
from mechcad_harness.dependency.models import InvalidationRecord
from mechcad_harness.runs import RunStatus
from mechcad_harness.state import StateManager
from test_m13_4e_promotion_evidence import _decision_inputs


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
HASH_C = "sha256:" + "c" * 64


def _result(**updates):
    values = {
        "decision_artifact_id": "MULTI-JOINT-PROMOTION-DECISION-123456789012345678901234",
        "decision_artifact_hash": HASH_A,
        "decision_hash": HASH_B,
        "promotion_proposal_hash": HASH_C,
        "proposal_id": "promotion:PM-M13-3",
        "changeset_id": "changeset-1",
        "changed_paths": (
            "/physical_mechanisms/PM-M13-3",
            "/physical_mechanisms/PM-M13-3/metadata",
        ),
        "canonical_target_mechanism_id": "PM-M13-3",
        "mechanism_path": "/physical_mechanisms/PM-M13-3",
        "base_revision": 1,
        "base_state_hash": HASH_A,
        "resulting_revision": 2,
        "resulting_state_hash": HASH_B,
    }
    values.update(updates)
    return MultiJointPromotionResultManifest(**values)


def test_result_manifest_has_exact_frozen_fields_and_hash_payload():
    result = _result()

    assert set(result.model_dump(mode="json")) == {
        "schema_version",
        "decision_artifact_id",
        "decision_artifact_hash",
        "decision_hash",
        "promotion_proposal_hash",
        "proposal_id",
        "changeset_id",
        "changed_paths",
        "canonical_target_mechanism_id",
        "mechanism_path",
        "base_revision",
        "base_state_hash",
        "resulting_revision",
        "resulting_state_hash",
        "result_hash",
    }
    assert result.schema_version == "multi-joint-promotion-result-manifest@1"
    assert "application_id" not in result.model_dump(mode="json")
    payload = result.model_dump(mode="json")
    actual = payload.pop("result_hash")
    expected = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert actual == expected == multi_joint_result_manifest_hash(result)

    with pytest.raises(ValueError):
        result.result_hash = HASH_C


def test_application_result_verifier_is_exported_with_peer_public_verifiers():
    from mechcad_harness.candidates import promotion_artifacts
    import mechcad_harness.candidates as candidates

    assert "verify_multi_joint_promotion_application_result" in promotion_artifacts.__all__
    assert "verify_multi_joint_promotion_application_result" in candidates.__all__


@pytest.mark.parametrize(
    "updates",
    [
        {"decision_artifact_id": " "},
        {"proposal_id": " "},
        {"changeset_id": " "},
        {"changed_paths": ()},
        {"changed_paths": ("/one", "/one")},
        {"mechanism_path": "/missing"},
        {"resulting_revision": 1},
        {"base_revision": 0},
        {"resulting_state_hash": "not-a-hash"},
    ],
)
def test_result_manifest_rejects_invalid_structural_bindings(updates):
    with pytest.raises(ValueError):
        _result(**updates)


def test_result_manifest_preserves_ordered_changed_paths_without_sorting():
    result = _result(
        changed_paths=(
            "/physical_mechanisms/PM-M13-3/metadata",
            "/physical_mechanisms/PM-M13-3",
        ),
        mechanism_path="/physical_mechanisms/PM-M13-3",
    )

    assert result.changed_paths == (
        "/physical_mechanisms/PM-M13-3/metadata",
        "/physical_mechanisms/PM-M13-3",
    )


def _result_inputs(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()
    decision_artifact = service.publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )
    changed_paths = tuple(
        dict.fromkeys(operation.path for operation in compilation.proposal.operations)
    )
    state_manager = StateManager(tmp_path)
    snapshot = state_manager.create_revision(
        request.project_id, state_manager.load_current_state(request.project_id)
    )
    applied = AppliedChangeResult(
        snapshot=snapshot,
        changeset_id="CS-M13-4E",
        changed_paths=changed_paths,
    )
    invalidation = InvalidationRecord(
        project_id=request.project_id,
        revision=applied.snapshot.revision,
        parent_revision=run.initial_revision,
        changeset_id=applied.changeset_id,
        changed_paths=changed_paths,
        directly_invalidated_nodes=(),
        transitively_invalidated_nodes=(),
        created_at="2026-01-01T00:00:00+00:00",
    )
    final_run = run.model_copy(
        update={
            "active_revision": applied.snapshot.revision,
            "active_state_hash": applied.snapshot.state_hash,
        }
    )
    return (
        store,
        service,
        decision_artifact,
        request,
        readiness,
        compilation,
        applied,
        invalidation,
        final_run,
        state_manager,
    )


def test_result_publication_uses_decision_byte_hash_and_fresh_resolution(tmp_path):
    (
        store,
        service,
        decision_artifact,
        _,
        _,
        compilation,
        applied,
        invalidation,
        final_run,
        _,
    ) = _result_inputs(tmp_path)

    artifact = service.publish_multi_joint_result(
        store,
        decision_artifact=decision_artifact,
        compilation=compilation,
        proposal=compilation.proposal,
        applied=applied,
        invalidation=invalidation,
        final_run=final_run,
    )
    result = service.resolve_multi_joint_result(store, artifact.artifact_id)

    assert artifact.artifact_id == f"MULTI-JOINT-PROMOTION-RESULT-{result.result_hash[7:31]}"
    assert artifact.artifact_type is ArtifactType.JSON
    assert artifact.relative_path.endswith("/multi_joint_result.json")
    assert artifact.producer_tool_name == "mechcad-promotion-manifest"
    assert artifact.producer_tool_version == "1"
    assert artifact.bound_revision == applied.snapshot.revision
    assert artifact.bound_state_hash == applied.snapshot.state_hash
    assert artifact.input_hash == decision_artifact.sha256
    assert artifact.run_id == decision_artifact.run_id == final_run.run_id
    content = (tmp_path / artifact.relative_path).read_bytes()
    assert content.endswith(b"\n")
    assert artifact.sha256 == "sha256:" + hashlib.sha256(content).hexdigest()
    assert result.decision_artifact_hash == decision_artifact.sha256
    assert result.decision_hash != result.decision_artifact_hash
    assert result.changed_paths == applied.changed_paths


def test_result_publication_rejects_unresolved_decision_and_lifecycle_substitution(tmp_path):
    (
        store,
        service,
        decision_artifact,
        _,
        _,
        compilation,
        applied,
        invalidation,
        final_run,
        _,
    ) = _result_inputs(tmp_path)

    forged_decision = decision_artifact.model_copy(
        update={"artifact_id": "MULTI-JOINT-PROMOTION-DECISION-forged"}
    )
    with pytest.raises(ValueError, match="decision|artifact|missing"):
        service.publish_multi_joint_result(
            store,
            decision_artifact=forged_decision,
            compilation=compilation,
            proposal=compilation.proposal,
            applied=applied,
            invalidation=invalidation,
            final_run=final_run,
        )

    for supplied_proposal, supplied_invalidation, supplied_run in (
        (
            compilation.proposal.model_copy(update={"id": "forged-proposal"}),
            invalidation,
            final_run,
        ),
        (
            compilation.proposal,
            invalidation.model_copy(update={"changeset_id": "forged-changeset"}),
            final_run,
        ),
        (
            compilation.proposal,
            invalidation,
            final_run.model_copy(update={"active_revision": final_run.active_revision + 1}),
        ),
    ):
        with pytest.raises(ValueError, match="binding|mismatch|provenance|revision"):
            service.publish_multi_joint_result(
                store,
                decision_artifact=decision_artifact,
                compilation=compilation,
                proposal=supplied_proposal,
                applied=applied,
                invalidation=supplied_invalidation,
                final_run=supplied_run,
            )


def test_multi_joint_application_receipt_has_exact_fields_and_rejects_coercion(tmp_path):
    _, _, request, readiness, compilation = _decision_inputs(tmp_path)
    receipt = CandidateMultiJointPromotionApplicationResult(
        request=request,
        readiness=readiness,
        compilation=compilation,
        decision_artifact_id="MULTI-JOINT-PROMOTION-DECISION-123456789012345678901234",
        result_artifact_id="MULTI-JOINT-PROMOTION-RESULT-123456789012345678901234",
        applied_revision=request.source_revision + 1,
        applied_state_hash=HASH_B,
        status=PromotionApplicationStatus.PROMOTION_APPLIED,
    )

    assert set(receipt.model_dump(mode="json")) == {
        "schema_version",
        "request",
        "readiness",
        "compilation",
        "decision_artifact_id",
        "result_artifact_id",
        "applied_revision",
        "applied_state_hash",
        "status",
        "error",
    }
    assert receipt.schema_version == "candidate-multi-joint-promotion-application-result@1"
    assert "receipt_hash" not in receipt.model_dump(mode="json")
    assert "application_id" not in receipt.model_dump(mode="json")
    with pytest.raises(ValueError):
        CandidateMultiJointPromotionApplicationResult(
            request=request.model_dump(mode="json"),
            readiness=readiness,
            compilation=compilation,
            status=PromotionApplicationStatus.PRE_APPLY_FAILURE,
            error="typed request coercion is forbidden",
        )


@pytest.mark.parametrize(
    "status,include_result,include_applied,include_error",
    [
        (PromotionApplicationStatus.PROMOTION_APPLIED, True, True, False),
        (PromotionApplicationStatus.PRE_APPLY_FAILURE, False, False, True),
        (PromotionApplicationStatus.CHANGEENGINE_REJECTED, False, False, True),
        (
            PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED,
            False,
            True,
            True,
        ),
        (
            PromotionApplicationStatus.PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED,
            False,
            True,
            True,
        ),
        (
            PromotionApplicationStatus.PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED,
            False,
            True,
            True,
        ),
        (
            PromotionApplicationStatus.PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED,
            False,
            True,
            True,
        ),
    ],
)
def test_multi_joint_application_receipt_enforces_status_shape(
    tmp_path, status, include_result, include_applied, include_error
):
    _, _, request, readiness, compilation = _decision_inputs(tmp_path)
    values = {
        "request": request,
        "readiness": readiness,
        "compilation": compilation,
        "decision_artifact_id": "MULTI-JOINT-PROMOTION-DECISION-123456789012345678901234",
        "result_artifact_id": (
            "MULTI-JOINT-PROMOTION-RESULT-123456789012345678901234"
            if include_result
            else None
        ),
        "applied_revision": request.source_revision + 1 if include_applied else None,
        "applied_state_hash": HASH_B if include_applied else None,
        "status": status,
        "error": "application failed" if include_error else None,
    }
    receipt = CandidateMultiJointPromotionApplicationResult(**values)
    assert receipt.status is status

    if status is PromotionApplicationStatus.PROMOTION_APPLIED:
        with pytest.raises(ValueError):
            CandidateMultiJointPromotionApplicationResult(**(values | {"error": "not allowed"}))
    else:
        with pytest.raises(ValueError):
            CandidateMultiJointPromotionApplicationResult(
                **(values | {"error": None})
            )


def _canonical_payload_bytes(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _payload_self_hash(payload):
    identity_payload = dict(payload)
    identity_payload.pop("result_hash", None)
    return "sha256:" + hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _artifact_metadata_path(tmp_path, artifact):
    return (tmp_path / artifact.relative_path).parent / "metadata.json"


def _update_artifact_metadata(tmp_path, artifact, **updates):
    metadata_path = _artifact_metadata_path(tmp_path, artifact)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(updates)
    metadata_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _rewrite_result_payload(tmp_path, artifact, updates, *, validate=True, recompute=True):
    result_path = tmp_path / artifact.relative_path
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload.update(updates)
    if recompute:
        payload["result_hash"] = "pending"
        if validate:
            payload = MultiJointPromotionResultManifest.model_validate(payload).model_dump(mode="json")
        else:
            payload["result_hash"] = _payload_self_hash(payload)
    content = _canonical_payload_bytes(payload)
    result_path.write_bytes(content)
    _update_artifact_metadata(
        tmp_path,
        artifact,
        sha256="sha256:" + hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


def _resolver_artifact_inputs(tmp_path):
    store, run, request, readiness, compilation = _decision_inputs(tmp_path)
    service = PromotionManifestService()
    decision_artifact = service.publish_multi_joint_decision(
        store, run=run, request=request, readiness=readiness, compilation=compilation
    )
    decision = service.resolve_multi_joint_decision(store, decision_artifact.artifact_id)
    changed_paths = tuple(
        dict.fromkeys(operation.path for operation in compilation.proposal.operations)
    )
    manifest = MultiJointPromotionResultManifest(
        decision_artifact_id=decision_artifact.artifact_id,
        decision_artifact_hash=decision_artifact.sha256,
        decision_hash=decision.decision_hash,
        promotion_proposal_hash=compilation.promotion_proposal_hash,
        proposal_id=compilation.proposal.id,
        changeset_id="CS-M13-4E-RESOLVER",
        changed_paths=changed_paths,
        canonical_target_mechanism_id=decision.projection.canonical_target_mechanism_id,
        mechanism_path=f"/physical_mechanisms/{decision.projection.canonical_target_mechanism_id}",
        base_revision=decision.base_revision,
        base_state_hash=decision.base_state_hash,
        resulting_revision=decision.base_revision + 1,
        resulting_state_hash=HASH_B,
    )
    content = _canonical_payload_bytes(manifest.model_dump(mode="json"))
    result_artifact = store.publish(
        f"MULTI-JOINT-PROMOTION-RESULT-{manifest.result_hash[7:31]}",
        ArtifactType.JSON,
        "multi_joint_result.json",
        content,
        "mechcad-promotion-manifest",
        "1",
        manifest.resulting_revision,
        manifest.resulting_state_hash,
        input_hash=decision_artifact.sha256,
    )
    assert resolve_multi_joint_result(store, result_artifact.artifact_id) == manifest
    return {
        "tmp_path": tmp_path,
        "store": store,
        "result_artifact": result_artifact,
        "decision_artifact": decision_artifact,
        "manifest": manifest,
    }


@pytest.fixture
def isolated_resolver_case(tmp_path, monkeypatch):
    case = _resolver_artifact_inputs(tmp_path)

    class ForbiddenDependency:
        def __init__(self, *args, **kwargs):
            raise AssertionError("artifact-local resolver accessed a nonlocal service")

    import mechcad_harness.candidates.promotion_artifacts as promotion_artifacts
    import mechcad_harness.dependency as dependency_package
    from mechcad_harness.dependency import storage as evidence_storage
    import mechcad_harness.runs as runs_package
    from mechcad_harness.runs import controller as run_controller_module
    import mechcad_harness.state as state_package
    from mechcad_harness.state import manager as state_manager_module

    for module, name in (
        (promotion_artifacts, "StateManager"),
        (promotion_artifacts, "EvidenceStore"),
        (promotion_artifacts, "RunController"),
        (state_package, "StateManager"),
        (state_manager_module, "StateManager"),
        (dependency_package, "EvidenceStore"),
        (evidence_storage, "EvidenceStore"),
        (runs_package, "RunController"),
        (run_controller_module, "RunController"),
    ):
        monkeypatch.setattr(module, name, ForbiddenDependency, raising=False)
    return case


def _reject_resolver(case, artifact_id=None, *, match=None):
    with pytest.raises(ValueError, match=match):
        resolve_multi_joint_result(
            case["store"], artifact_id or case["result_artifact"].artifact_id
        )


def test_resolver_tamper_rejects_result_artifact_namespace(isolated_resolver_case):
    case = isolated_resolver_case
    artifact = case["result_artifact"]
    old_dir = _artifact_metadata_path(case["tmp_path"], artifact).parent
    forged_id = "PROMOTION-RESULT-" + artifact.artifact_id.rsplit("-", 1)[-1]
    new_dir = old_dir.with_name(forged_id)
    old_dir.rename(new_dir)
    metadata_path = new_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "artifact_id": forged_id,
            "relative_path": (
                f"projects/{case['store'].project_id}/runs/{case['store'].run_id}/"
                f"artifacts/{forged_id}/multi_joint_result.json"
            ),
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    _reject_resolver(case, forged_id)


def test_resolver_tamper_rejects_artifact_sha256_metadata(isolated_resolver_case):
    case = isolated_resolver_case
    _update_artifact_metadata(case["tmp_path"], case["result_artifact"], sha256=HASH_C)
    _reject_resolver(case)


def test_resolver_tamper_rejects_artifact_size_metadata(isolated_resolver_case):
    case = isolated_resolver_case
    _update_artifact_metadata(
        case["tmp_path"], case["result_artifact"], size_bytes=case["result_artifact"].size_bytes + 1
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_result_artifact_input_hash(isolated_resolver_case):
    case = isolated_resolver_case
    _update_artifact_metadata(case["tmp_path"], case["result_artifact"], input_hash=HASH_C)
    _reject_resolver(case)


def test_resolver_tamper_rejects_noncanonical_result_bytes(isolated_resolver_case):
    case = isolated_resolver_case
    result_path = case["tmp_path"] / case["result_artifact"].relative_path
    content = result_path.read_bytes()
    forged_content = content[:-1] + b" \n"
    result_path.write_bytes(forged_content)
    _update_artifact_metadata(
        case["tmp_path"],
        case["result_artifact"],
        sha256="sha256:" + hashlib.sha256(forged_content).hexdigest(),
        size_bytes=len(forged_content),
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_result_hash(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"],
        case["result_artifact"],
        {"result_hash": HASH_C},
        validate=False,
        recompute=False,
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_decision_artifact_id(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"],
        case["result_artifact"],
        {"decision_artifact_id": "MULTI-JOINT-PROMOTION-DECISION-missing"},
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_decision_artifact_byte_hash(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"], case["result_artifact"], {"decision_artifact_hash": HASH_C}
    )
    _update_artifact_metadata(case["tmp_path"], case["result_artifact"], input_hash=HASH_C)
    _reject_resolver(case)


def test_resolver_tamper_rejects_decision_manifest_self_hash(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"], case["result_artifact"], {"decision_hash": HASH_C}
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_base_revision(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"],
        case["result_artifact"],
        {"base_revision": case["manifest"].base_revision + 1, "resulting_revision": case["manifest"].resulting_revision + 1},
    )
    _update_artifact_metadata(
        case["tmp_path"],
        case["result_artifact"],
        bound_revision=case["manifest"].resulting_revision + 1,
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_base_state_hash(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"], case["result_artifact"], {"base_state_hash": HASH_C}
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_resulting_revision(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"],
        case["result_artifact"],
        {"resulting_revision": case["manifest"].resulting_revision + 1},
        validate=False,
    )
    _reject_resolver(case, match="multi-joint result revision must be base revision plus one")


def test_resolver_tamper_rejects_resulting_state_hash(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"], case["result_artifact"], {"resulting_state_hash": HASH_C}
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_artifact_bound_revision(isolated_resolver_case):
    case = isolated_resolver_case
    _update_artifact_metadata(
        case["tmp_path"],
        case["result_artifact"],
        bound_revision=case["result_artifact"].bound_revision + 1,
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_artifact_bound_state_hash(isolated_resolver_case):
    case = isolated_resolver_case
    _update_artifact_metadata(case["tmp_path"], case["result_artifact"], bound_state_hash=HASH_C)
    _reject_resolver(case)


def test_resolver_tamper_rejects_canonical_target_mechanism_id(isolated_resolver_case):
    case = isolated_resolver_case
    forged_target = "PM-M13-4E-FORGED"
    forged_path = f"/physical_mechanisms/{forged_target}"
    result_path = case["tmp_path"] / case["result_artifact"].relative_path
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    forged_paths = [forged_path if path == payload["mechanism_path"] else path for path in payload["changed_paths"]]
    _rewrite_result_payload(
        case["tmp_path"],
        case["result_artifact"],
        {
            "canonical_target_mechanism_id": forged_target,
            "mechanism_path": forged_path,
            "changed_paths": forged_paths,
        },
    )
    _reject_resolver(case)


def test_resolver_tamper_rejects_mechanism_path(isolated_resolver_case):
    case = isolated_resolver_case
    _rewrite_result_payload(
        case["tmp_path"],
        case["result_artifact"],
        {"mechanism_path": "/physical_mechanisms/M13-4E-FORGED"},
        validate=False,
    )
    _reject_resolver(case, match="multi-joint result mechanism path mismatch")


def test_resolver_tamper_rejects_result_artifact_run_id(isolated_resolver_case):
    case = isolated_resolver_case
    _update_artifact_metadata(case["tmp_path"], case["result_artifact"], run_id="RUN-FORGED")
    _reject_resolver(case)


def test_resolver_tamper_rejects_decision_artifact_run_id_relationship(isolated_resolver_case):
    case = isolated_resolver_case
    original_store = case["store"]
    decision_artifact = case["decision_artifact"]
    forged_run_id = "RUN-FORGED"
    source_dir = _artifact_metadata_path(case["tmp_path"], decision_artifact).parent
    forged_dir = (
        case["tmp_path"]
        / "projects"
        / original_store.project_id
        / "runs"
        / forged_run_id
        / "artifacts"
        / decision_artifact.artifact_id
    )
    shutil.copytree(source_dir, forged_dir)
    forged_relative_path = (
        f"projects/{original_store.project_id}/runs/{forged_run_id}/artifacts/"
        f"{decision_artifact.artifact_id}/multi_joint_decision.json"
    )
    forged_metadata_path = forged_dir / "metadata.json"
    forged_metadata = json.loads(forged_metadata_path.read_text(encoding="utf-8"))
    forged_metadata.update(run_id=forged_run_id, relative_path=forged_relative_path)
    forged_metadata_path.write_text(
        json.dumps(forged_metadata, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    forged_store = type(original_store)(
        case["tmp_path"], project_id=original_store.project_id, run_id=forged_run_id
    )
    forged_verified = forged_store.read_verified_strict(
        decision_artifact.artifact_id, expected_type=ArtifactType.JSON
    )
    assert forged_verified is not None
    assert forged_verified[0].run_id == forged_run_id
    assert forged_verified[0].relative_path == forged_relative_path
    assert resolve_multi_joint_result(original_store, case["result_artifact"].artifact_id) == case["manifest"]

    class CrossRunDecisionStore(type(original_store)):
        def __init__(self):
            super().__init__(
                case["tmp_path"],
                project_id=original_store.project_id,
                run_id=original_store.run_id,
            )
            self.decision_reads = 0

        def read_verified_strict(self, artifact_id, *, expected_type=None, expected_hash=None):
            if artifact_id != decision_artifact.artifact_id:
                return original_store.read_verified_strict(
                    artifact_id, expected_type=expected_type, expected_hash=expected_hash
                )
            self.decision_reads += 1
            source = original_store if self.decision_reads == 1 else forged_store
            return source.read_verified_strict(
                artifact_id, expected_type=expected_type, expected_hash=expected_hash
            )

    cross_run_store = CrossRunDecisionStore()
    with pytest.raises(ValueError, match="multi-joint result manifest artifact binding mismatch"):
        resolve_multi_joint_result(cross_run_store, case["result_artifact"].artifact_id)

    assert cross_run_store.decision_reads == 2
    original_verified = original_store.read_verified_strict(
        decision_artifact.artifact_id, expected_type=ArtifactType.JSON
    )
    assert original_verified is not None
    assert original_verified[0].run_id == original_store.run_id
