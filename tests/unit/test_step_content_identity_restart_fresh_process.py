"""B2 closure: a GENUINE fresh-process child-interpreter restart proof.

The parent process builds the real candidate@2 + synthesis-request@2 + CAD
realization@2 chain through production services and persists durable artifacts
(candidate publication ``CAND-``, candidate CAD provenance ``CANDIDATE-CAD-``,
and the ``candidate-multi-joint-m10-provenance@1`` envelope) into a real
``ArtifactStore`` workspace. It then spawns a REAL separate Python interpreter
via ``subprocess`` passing ONLY durable locator/lookup inputs (project id,
workspace path, artifact IDs/hashes). The child imports production fresh,
reconstructs its own ``StateManager``/``ArtifactStore``/services, resolves the
persisted artifacts, recomputes raw SHA, ``step-content-identity@1``,
``semantic_source_binding_hash``, typed parent resolution, ``candidate_hash_v2``
and the P5/P6 semantic identities, installs zero-execution spies, and emits its
recomputed identities as JSON on stdout. The parent asserts equality and a
negative tampered-bytes case fails closed.

No Python production object crosses the process boundary; same-process fresh
stores do not count.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates.cad_realization import CandidateCadRealizationV2
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    PhysicalToM10V2BridgeCompiler,
)
from mechcad_harness.candidates.multi_joint_m10_evaluation import (
    CandidateMultiJointM10EvaluationService,
    CandidateMultiJointM10ReplayV2,
)
from mechcad_harness.candidates.multi_joint_selection import (
    CandidateMultiJointSelectionService,
)
from mechcad_harness.candidates.provenance_artifacts import (
    ArtifactReference,
    CandidateMultiJointM10Provenance,
    CandidateProvenanceArtifactService,
    candidate_multi_joint_m10_provenance_artifact_id,
)
from mechcad_harness.candidates.services import CandidateCurrentnessService
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_candidate_multijoint_m10_v2 import (
    _candidate_cad_v2,
    _candidate_with_m13_multi_joint_authority,
    _multi_joint_scope,
    _raw_m10_result,
)

_RESULT_MARKER = "B2_FRESH_PROCESS_RESULT "


# The child interpreter imports production fresh; it never receives a parent
# production object. It only reads the durable locator JSON path in argv[1].
_CHILD_SCRIPT = r'''
import builtins
import hashlib
import json
import os
import sys

_locator_path = sys.argv[1]
with open(_locator_path, encoding="utf-8") as _handle:
    _locator = json.load(_handle)

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates.models import candidate_hash_v2
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    PhysicalToM10V2BridgeCompiler,
)
from mechcad_harness.candidates.multi_joint_m10_evaluation import (
    CandidateMultiJointM10EvaluationService,
    candidate_multi_joint_m10_evaluation_hash_v2,
    candidate_multi_joint_m10_request_hash_v2,
)
from mechcad_harness.candidates.multi_joint_selection import (
    candidate_multi_joint_selection_hash_v2,
)
from mechcad_harness.candidates.provenance_artifacts import (
    CandidateMultiJointM10Provenance,
    CandidateProvenanceArtifactService,
    validate_candidate_multi_joint_m10_provenance_chain,
)
from mechcad_harness.candidates.services import (
    CandidateCurrentnessService,
    CandidatePublicationService,
    compute_verified_semantic_binding,
)
from mechcad_harness.multi_joint_collision_sweep import (
    MultiJointCollisionSweepResultV2,
    multi_joint_collision_sweep_result_v2_hash,
)
from mechcad_harness.semantic_m10_kinematics import (
    semantic_m10_v2_request_hash,
    semantic_m10_v2_result_hash,
)
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.step_content_identity import step_content_identity_v1

# Zero-execution spies installed INSIDE the child. Live CAD/solver module
# imports raise; the M10 sweep provider sentinel raises and records calls.
_LIVE_RUNTIME_MODULES = {
    "FreeCAD", "FreeCADGui", "Part", "Mesh", "MeshPart",
    "gmsh", "calculix", "ccx", "PyCalculix", "build123d",
}
_live_imports = []
_original_import = builtins.__import__


def _guarded_import(name, *args, **kwargs):
    if name.split(".")[0] in _LIVE_RUNTIME_MODULES:
        _live_imports.append(name)
        raise AssertionError(
            "live CAD/solver module imported during restart: " + name
        )
    return _original_import(name, *args, **kwargs)


builtins.__import__ = _guarded_import


def _spy_probe():
    """Prove the import guard actually intercepts a live-runtime module."""
    try:
        __import__("FreeCAD")
    except AssertionError:
        return True
    except ImportError:
        return False
    return False


_spy_armed = _spy_probe()
_live_imports.clear()

_provider_calls = []


def _no_exec(**kwargs):
    _provider_calls.append(kwargs)
    raise AssertionError("zero execution: M10 provider must not run during restart")


def _emit(payload):
    sys.stdout.write("B2_FRESH_PROCESS_RESULT " + json.dumps(payload) + "\n")
    sys.stdout.flush()


def main():
    workspace = _locator["workspace"]
    project_id = _locator["project_id"]
    manager = StateManager(workspace)
    store = ArtifactStore(workspace, project_id=project_id, run_id="LOOKUP")
    provenance = CandidateProvenanceArtifactService(workspace, project_id, manager)
    publication_service = CandidatePublicationService(workspace, project_id, manager)

    # Typed parent resolution from durable candidate-CAD provenance only.
    cad = provenance.resolve_candidate_cad(_locator["candidate_cad_artifact_id"])
    assert cad.artifact.sha256 == _locator["candidate_cad_artifact_hash"]
    candidate, synthesis_request, _policy = provenance._candidate_from_cad(cad)
    assert (
        cad.payload.candidate_artifact.artifact.artifact_id
        == _locator["candidate_publication_artifact_id"]
    )

    publication = publication_service.resolve(
        _locator["candidate_publication_artifact_id"]
    )
    assert publication.candidate == candidate
    recomputed_candidate_hash = candidate_hash_v2(candidate)
    assert recomputed_candidate_hash == candidate.candidate_hash

    state = manager.load_revision(
        project_id, candidate.source_binding.source_revision
    )
    assert state_hash(state) == candidate.source_binding.source_state_hash
    _geometry_bindings, semantic_hash = compute_verified_semantic_binding(
        candidate.source_binding,
        state=state,
        store=store,
        project_id=project_id,
    )
    assert semantic_hash == candidate.semantic_source_binding_hash

    raw_sha_by_artifact = {}
    content_identity_by_artifact = {}
    for source in cad.payload.source_step_artifacts:
        _verified, content = ArtifactStore(
            workspace,
            project_id=project_id,
            run_id=source.run_id,
            task_id=source.task_id,
        ).read_verified_strict(
            source.artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=source.sha256,
        )
        raw_sha_by_artifact[source.artifact_id] = (
            "sha256:" + hashlib.sha256(content).hexdigest()
        )
        content_identity_by_artifact[source.artifact_id] = (
            step_content_identity_v1(content).content_hash
        )

    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate,
        cad.payload.realization,
        cad.payload.request.placement_derivations,
    )

    verified = store.read_verified_in_project(
        _locator["mj_provenance_artifact_id"],
        expected_type=ArtifactType.JSON,
        expected_hash=_locator["mj_provenance_artifact_hash"],
    )
    assert verified is not None, "MJ provenance envelope did not resolve"
    mj_artifact, mj_content = verified
    envelope = CandidateMultiJointM10Provenance.model_validate_json(mj_content)
    p6_result = MultiJointCollisionSweepResultV2.model_validate(
        envelope.m10_v2_result
    )
    expected_tuple = validate_candidate_multi_joint_m10_provenance_chain(
        envelope, candidate_hash=candidate.candidate_hash, project_id=project_id
    )
    assert expected_tuple == (
        envelope.request.request_hash,
        envelope.evaluation.evaluation_hash,
        envelope.selection.selection_hash,
    )

    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=CandidateCurrentnessService(manager),
        analyze_multi_joint_collision_sweep_v2=_no_exec,
    )
    reconstructed = service.reconstruct_m10_request(
        candidate,
        synthesis_request,
        cad.payload.realization,
        bridge,
        envelope.request,
    )
    semantic_request = semantic_m10_v2_request_hash(
        reconstructed,
        cad.payload.realization.assembly,
        cad.payload.realization.mappings,
    )
    semantic_result = semantic_m10_v2_result_hash(
        p6_result,
        reconstructed,
        cad.payload.realization.assembly,
        cad.payload.realization.mappings,
    )
    assert semantic_request == envelope.request.semantic_m10_v2_request_hash
    assert semantic_result == envelope.evaluation.semantic_m10_v2_result_hash
    assert (
        multi_joint_collision_sweep_result_v2_hash(p6_result)
        == p6_result.result_hash
    )
    assert (
        candidate_multi_joint_m10_request_hash_v2(envelope.request)
        == envelope.request.request_hash
    )
    assert (
        candidate_multi_joint_m10_evaluation_hash_v2(
            envelope.evaluation, envelope.request
        )
        == envelope.evaluation.evaluation_hash
    )
    assert (
        candidate_multi_joint_selection_hash_v2(envelope.selection)
        == envelope.selection.selection_hash
    )

    recomputed = {
        "project_id": project_id,
        "source_revision": candidate.source_binding.source_revision,
        "source_state_hash": candidate.source_binding.source_state_hash,
        "candidate_publication_artifact_id": publication.artifact.artifact_id,
        "candidate_cad_artifact_id": cad.artifact.artifact_id,
        "candidate_cad_artifact_hash": cad.artifact.sha256,
        "mj_provenance_artifact_id": mj_artifact.artifact_id,
        "mj_provenance_artifact_hash": mj_artifact.sha256,
        "raw_sha_by_artifact": raw_sha_by_artifact,
        "content_identity_by_artifact": content_identity_by_artifact,
        "semantic_source_binding_hash": semantic_hash,
        "candidate_hash": recomputed_candidate_hash,
        "synthesis_request_hash": synthesis_request.request_hash,
        "semantic_m10_v2_request_hash": semantic_request,
        "semantic_m10_v2_result_hash": semantic_result,
        "mj_request_hash": envelope.request.request_hash,
        "mj_evaluation_hash": envelope.evaluation.evaluation_hash,
        "mj_selection_hash": envelope.selection.selection_hash,
        "p6_result_hash": p6_result.result_hash,
    }
    _emit(
        {
            "ok": True,
            "pid": os.getpid(),
            "spy_armed": _spy_armed,
            "recomputed": recomputed,
            "provider_calls": len(_provider_calls),
            "live_imports": _live_imports,
        }
    )


try:
    main()
except Exception as exc:  # fail closed
    _emit({"ok": False, "error": type(exc).__name__ + ": " + str(exc)})
    sys.exit(1)
'''


def _build_and_persist(tmp_path):
    """Parent: build the real @2/@3 chain and persist durable artifacts only."""

    project_id = "PRJ-M12"
    state, manager, _store, synthesis_request, policy, candidate = (
        _candidate_with_m13_multi_joint_authority(tmp_path)
    )
    cad_request, cad_realization = _candidate_cad_v2(
        candidate, synthesis_request, state
    )
    required_raw = {
        item["artifact_id"]: item["artifact_hash"]
        for item in state.yagi_payload_carrier_requirements
    }
    realization = CandidateCadRealizationV2.model_validate(
        cad_realization.model_dump(mode="json")
        | {
            "verified_source_artifact_hashes": list(sorted(required_raw.values())),
            "realization_hash": "pending",
        }
    )

    provenance = CandidateProvenanceArtifactService(tmp_path, project_id, manager)
    candidate_cad = provenance.publish_candidate_cad(
        candidate,
        synthesis_request,
        policy,
        cad_request,
        realization,
        source_step_artifacts=None,
    )

    bridge = PhysicalToM10V2BridgeCompiler().compile_candidate(
        candidate, realization, cad_request.placement_derivations
    )
    scope = _multi_joint_scope(bridge.model.model_id)
    currentness = CandidateCurrentnessService(manager)
    service = CandidateMultiJointM10EvaluationService(
        currentness_verifier=currentness,
        analyze_multi_joint_collision_sweep_v2=_raw_m10_result,
    )
    request = service.build_request(
        candidate,
        synthesis_request,
        realization,
        bridge,
        scope,
        cad_request=cad_request,
    )
    evaluation = service.execute(
        candidate, synthesis_request, realization, bridge, request
    )

    def replayer(replay_candidate, replay_request, replay_evaluation, replay):
        low_request = service.reconstruct_m10_request(
            replay_candidate, replay_request, realization, bridge, replay_evaluation
        )
        low_result = _raw_m10_result(
            source_revision=replay_evaluation.source_revision,
            source_state_hash=replay_evaluation.source_state_hash,
            assembly=realization.assembly,
            model=low_request.model,
            configurations=low_request.configurations,
            exact_pair_scope=low_request.exact_pair_scope,
            volume_tolerance_mm3=low_request.volume_tolerance_mm3,
            distance_tolerance_mm=low_request.distance_tolerance_mm,
        )
        return CandidateMultiJointM10ReplayV2(low_request, low_result, realization, bridge)

    selection = CandidateMultiJointSelectionService(
        project_id=project_id,
        currentness_verifier=currentness,
        result_replayer=replayer,
    ).select(
        candidate,
        request,
        evaluation,
        "b2-fresh-process-selector@1",
        "durable restart proof",
        synthesis_request=synthesis_request,
    )

    low_request = service.reconstruct_m10_request(
        candidate, synthesis_request, realization, bridge, request
    )
    p6_result = _raw_m10_result(
        source_revision=request.source_revision,
        source_state_hash=request.source_state_hash,
        assembly=realization.assembly,
        model=low_request.model,
        configurations=low_request.configurations,
        exact_pair_scope=low_request.exact_pair_scope,
        volume_tolerance_mm3=low_request.volume_tolerance_mm3,
        distance_tolerance_mm=low_request.distance_tolerance_mm,
    )

    envelope = CandidateMultiJointM10Provenance(
        request=request,
        evaluation=evaluation,
        selection=selection,
        m10_v2_result=p6_result,
        candidate_publication=ArtifactReference(
            artifact=candidate_cad.payload.candidate_artifact.artifact
        ),
        candidate_cad=ArtifactReference(artifact=candidate_cad.artifact),
    )
    mj_artifact = ArtifactStore(
        tmp_path, project_id=project_id, run_id="MJPROV"
    ).publish(
        candidate_multi_joint_m10_provenance_artifact_id(selection.selection_hash),
        ArtifactType.JSON,
        "candidate_multi_joint_m10_provenance.json",
        canonical_json_bytes(envelope.model_dump(mode="json")),
        "mechcad-candidate-provenance",
        "1",
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
        input_hash=selection.selection_hash,
    )

    raw_sha_by_artifact = {}
    content_identity_by_artifact = {}
    for source in candidate_cad.payload.source_step_artifacts:
        _verified, content = ArtifactStore(
            tmp_path,
            project_id=project_id,
            run_id=source.run_id,
            task_id=source.task_id,
        ).read_verified_strict(
            source.artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=source.sha256,
        )
        raw_sha_by_artifact[source.artifact_id] = (
            "sha256:" + hashlib.sha256(content).hexdigest()
        )
        content_identity_by_artifact[source.artifact_id] = (
            step_content_identity_v1(content).content_hash
        )

    expected = {
        "project_id": project_id,
        "source_revision": candidate.source_binding.source_revision,
        "source_state_hash": candidate.source_binding.source_state_hash,
        "candidate_publication_artifact_id": (
            candidate_cad.payload.candidate_artifact.artifact.artifact_id
        ),
        "candidate_cad_artifact_id": candidate_cad.artifact.artifact_id,
        "candidate_cad_artifact_hash": candidate_cad.artifact.sha256,
        "mj_provenance_artifact_id": mj_artifact.artifact_id,
        "mj_provenance_artifact_hash": mj_artifact.sha256,
        "raw_sha_by_artifact": raw_sha_by_artifact,
        "content_identity_by_artifact": content_identity_by_artifact,
        "semantic_source_binding_hash": candidate.semantic_source_binding_hash,
        "candidate_hash": candidate.candidate_hash,
        "synthesis_request_hash": synthesis_request.request_hash,
        "semantic_m10_v2_request_hash": request.semantic_m10_v2_request_hash,
        "semantic_m10_v2_result_hash": evaluation.semantic_m10_v2_result_hash,
        "mj_request_hash": request.request_hash,
        "mj_evaluation_hash": evaluation.evaluation_hash,
        "mj_selection_hash": selection.selection_hash,
        "p6_result_hash": p6_result.result_hash,
    }
    locator = {
        "workspace": str(tmp_path),
        "project_id": project_id,
        "candidate_publication_artifact_id": expected[
            "candidate_publication_artifact_id"
        ],
        "candidate_cad_artifact_id": expected["candidate_cad_artifact_id"],
        "candidate_cad_artifact_hash": expected["candidate_cad_artifact_hash"],
        "mj_provenance_artifact_id": expected["mj_provenance_artifact_id"],
        "mj_provenance_artifact_hash": expected["mj_provenance_artifact_hash"],
        "expected": expected,
    }
    return {
        "expected": expected,
        "locator": locator,
        "source_step_artifacts": tuple(
            candidate_cad.payload.source_step_artifacts
        ),
    }


def _run_child(tmp_path, locator):
    locator_path = tmp_path / "b2_restart_locator.json"
    locator_path.write_text(json.dumps(locator), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT, str(locator_path)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )


def _extract_result(stdout: str):
    for line in reversed(stdout.splitlines()):
        if line.startswith(_RESULT_MARKER):
            return json.loads(line[len(_RESULT_MARKER):])
    raise AssertionError(f"child emitted no result marker; stdout was:\n{stdout}")


def test_fresh_process_restart_recomputes_step_content_identity_chain(tmp_path):
    context = _build_and_persist(tmp_path)
    completed = _run_child(tmp_path, context["locator"])
    payload = _extract_result(completed.stdout)

    assert completed.returncode == 0, completed.stderr
    assert payload["ok"] is True, payload
    assert payload["pid"] != os.getpid()
    assert payload["spy_armed"] is True
    assert payload["provider_calls"] == 0
    assert payload["live_imports"] == []
    assert payload["recomputed"] == context["expected"]


def test_fresh_process_restart_fails_closed_on_tampered_step_bytes(tmp_path):
    context = _build_and_persist(tmp_path)
    source = context["source_step_artifacts"][0]
    artifact_path = tmp_path / source.relative_path
    original = artifact_path.read_bytes()
    # Same-length raw-byte tamper: the stored metadata hash stays valid-looking,
    # so only the child's own byte rehash can detect it.
    tampered = original.replace(b"PRODUCT('p2-geometry')", b"PRODUCT('p2-geometrx')")
    assert tampered != original
    assert len(tampered) == len(original)
    artifact_path.write_bytes(tampered)

    completed = _run_child(tmp_path, context["locator"])
    payload = _extract_result(completed.stdout)

    assert completed.returncode != 0
    assert payload["ok"] is False
    assert payload["error"]
    assert any(
        hint in payload["error"].lower()
        for hint in ("artifact", "byte", "hash", "verification", "missing")
    )
