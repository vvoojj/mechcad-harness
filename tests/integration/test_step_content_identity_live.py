"""T-P8.3 LIVE verification for deterministic STEP content identity.

This module proves, against the REAL FreeCAD 1.1.3 runtime invoked through the
production ``freecadcmd`` subprocess boundary, that:

(a) two real FreeCAD STEP exports of the same geometry at different wall-clock
    times (so the STEP ``FILE_NAME`` timestamp differs) have DIFFERENT raw
    SHA-256 bytes but the SAME ``step-content-identity@1`` content identity, and
    that the downstream semantic identities produced by the FINAL default
    ``ProductionApplication.realize_and_evaluate_revolute_drive`` path
    (``semantic_reference_hash``, ``candidate-synthesis-request@2.request_hash``,
    ``component-specification@4.specification_hash``,
    ``mechanical-design-candidate@2.candidate_hash`` and
    ``revolute-drive-admissibility@2.result_hash``) are EQUAL while the raw
    provenance (artifact ids / raw hashes / bound state / run ids) differs;

(b) a fresh isolated replay workspace at
    ``.tmp-live-m12/tp8_3_mini_replay/`` (outside ``projects/``) exercises that
    same FINAL default path with a ``candidate-synthesis-request@2`` and emits
    the new homogeneous ``@2`` family from the accepted M12 direct-drive
    engineering authority plus a real FreeCAD STEP artifact;

(c) a genuinely fresh separate Python interpreter reloads the live artifacts
    from ``ArtifactStore``, rehashes the raw bytes, recomputes
    ``step-content-identity@1`` and the semantic source binding, and validates
    both bindings;

(d) a real engineering change (different real geometry and a changed supplied
    shaft specification) changes the corresponding semantic identity.

Boundaries: no Gmsh, no CalculiX, no solver/mesh execution, no M11 structural
analysis. The historical MINI workspaces under ``projects/mini_rotary_fixture``
and every accepted audit/reconstruction record are never read or written. The
``@2`` candidate CAD realization/mapping route is reject-only in the activated
default (see ``tests/unit/test_candidate_production_admission_matrix.py``), so
those specific identities are not reachable through the single-joint FINAL
default; this module records that boundary instead of fabricating a route.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.candidates import (
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
)
from mechcad_harness.candidates.models import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    GeometrySourceReference,
    MechanicalDesignCandidate,
    candidate_hash_v2,
)
from mechcad_harness.candidates.services import (
    CandidatePublicationService,
    bind_candidate_synthesis_request_semantic_identity,
)
from mechcad_harness.models.semantic_component import (
    bind_component_specification_semantic_identity,
)
from mechcad_harness.revolute_drive import (
    DriveArchitecture,
    RevoluteDriveAdmissibilityResult,
)
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_m12_revolute_drive_production import (
    _ALL_CONSUMED_PATHS,
    body_specification,
    bearing_specification,
    hub_specification,
    motor_specification,
    mount_specification,
    policy_for,
    production_state,
    requirements,
    shaft_specification,
    template,
)


PROJECT_ID = "PRJ-M12"
SOURCE_RUN_ID = "LIVE-REPLAY"
_GEOMETRY_INDEX_BASE = 13
_SLOTS = ("motor", "shaft", "bearing", "hub", "mount", "body")

_FREECADCMD = (
    os.environ.get("MECHCAD_FREECADCMD")
    or r"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"
)
_FREECAD_AVAILABLE = Path(_FREECADCMD).is_file()
if _FREECAD_AVAILABLE:
    os.environ.setdefault("MECHCAD_FREECADCMD", _FREECADCMD)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIVE_ROOT = _REPO_ROOT / ".tmp-live-m12" / "tp8_3_mini_replay"

pytestmark = pytest.mark.skipif(
    not _FREECAD_AVAILABLE,
    reason="FreeCADCmd is not available through the configured MECHCAD_FREECADCMD path",
)


@dataclass(frozen=True)
class LiveVariant:
    label: str
    workspace: Path
    export_artifact: EngineeringArtifact
    step_bytes: bytes
    raw_hash: str
    content_identity: str
    geometry_artifact_id: str
    geometry_run_id: str
    bound_request: CandidateSynthesisRequest
    policy: CandidateSynthesisPolicy
    bound_specs: dict
    candidate: MechanicalDesignCandidate
    evaluation: RevoluteDriveAdmissibilityResult
    publication_artifact_id: str
    publication_artifact_hash: str

    @property
    def semantic_reference_hashes(self) -> tuple[str, ...]:
        return tuple(
            specification.geometry_source.semantic_reference_hash
            for specification in self.candidate.component_specifications
            if specification.geometry_source is not None
        )

    @property
    def specification_hashes(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                specification.specification_hash
                for specification in self.candidate.component_specifications
            )
        )


def _agent() -> FakeAgentAdapter:
    return FakeAgentAdapter(
        AgentIdentity(
            agent_name="tp8-3-live-verification-agent",
            agent_version="1.0",
            role="tp8-3-live",
            protocol_version="1.0",
        ),
        scripted_responses=(),
    )


def _write_config(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    ownership = root / "ownership.yaml"
    dependencies = root / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /requirements/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps({"rules": [], "edges": []}), encoding="utf-8"
    )
    return ownership, dependencies


def _application(root: Path) -> ProductionApplication:
    ownership, dependencies = _write_config(root)
    return ProductionApplication.create(
        root,
        PROJECT_ID,
        _agent(),
        ownership_path=ownership,
        dependency_path=dependencies,
    )


def _export_real_step(
    export_root: Path,
    run_id: str,
    *,
    length_mm: float = 30.0,
    width_mm: float = 30.0,
    thickness_mm: float = 5.0,
) -> tuple[EngineeringArtifact, bytes]:
    """Run the REAL production FreeCAD CAD path and return the stored STEP bytes."""

    export_root.mkdir(parents=True, exist_ok=True)
    program = CadPartProgram(
        part_id=f"mini-replay-{run_id}",
        operations=(
            BasePlateOperation(
                operation_id="base",
                length_mm=length_mm,
                width_mm=width_mm,
                thickness_mm=thickness_mm,
            ),
        ),
    )
    generated = FreeCADBackend().generate_program(
        program,
        export_root,
        project_id="EXPORT",
        run_id=run_id,
        revision=1,
        state_hash="sha256:" + "0" * 64,
    )
    store = ArtifactStore(export_root, project_id="EXPORT", run_id=run_id)
    artifact, content = store.read_verified_strict(
        generated.step.artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash=generated.step.sha256,
    )
    assert "sha256:" + hashlib.sha256(content).hexdigest() == generated.step.sha256
    return artifact, content


def _build_live_variant(
    *,
    label: str,
    root: Path,
    export_artifact: EngineeringArtifact,
    step_bytes: bytes,
    shaft_diameter_mm: float = 12.0,
) -> LiveVariant:
    """Build one fully bound request@2/candidate@2 chain through the FINAL default."""

    root.mkdir(parents=True, exist_ok=True)
    raw_hash = export_artifact.sha256
    content_identity = step_content_identity_v1(step_bytes).content_hash
    chosen = {slot: f"ART-LIVE-{label}-{slot}" for slot in _SLOTS}
    identities = [
        {
            "artifact_id": chosen[slot],
            "artifact_hash": raw_hash,
            "source_identity": f"mini:rev3:{slot}@1",
            "format": "step",
        }
        for slot in _SLOTS
    ]

    base_state = production_state()
    state = base_state.model_copy(
        update={
            "yagi_payload_carrier_requirements": list(
                base_state.yagi_payload_carrier_requirements
            )
            + identities
        }
    )
    manager = StateManager(root)
    manager.create_project(PROJECT_ID, state)
    stored = manager.load_revision(PROJECT_ID, 1)
    stored_hash = state_hash(stored)

    consumed = tuple(
        CandidateSourceReference(path=path, value_hash="pending", authority=authority)
        for path, authority in _ALL_CONSUMED_PATHS
    ) + tuple(
        CandidateSourceReference(
            path=f"/yagi_payload_carrier_requirements/{_GEOMETRY_INDEX_BASE + index}",
            value_hash="pending",
            authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
        )
        for index in range(len(identities))
    )
    binding = CandidateSourceBinding(
        project_id=PROJECT_ID,
        source_revision=stored.revision,
        source_state_hash=stored_hash,
        consumed_authority=consumed,
    ).bound_to(stored)

    store = ArtifactStore(root, project_id=PROJECT_ID, run_id=SOURCE_RUN_ID)
    for slot in _SLOTS:
        store.publish(
            chosen[slot],
            ArtifactType.STEP,
            f"{chosen[slot].lower()}.step",
            step_bytes,
            export_artifact.producer_tool_name,
            export_artifact.producer_tool_version,
            stored.revision,
            stored_hash,
            backend_provenance=export_artifact.backend_provenance,
            input_hash=export_artifact.input_hash,
        )

    context = {
        (identity["artifact_id"], raw_hash, identity["source_identity"], "step", None): {
            "algorithm": "step-content-identity@1",
            "content_hash": content_identity,
        }
        for identity in identities
    }
    base_specs = {
        "motor": motor_specification(),
        "shaft": shaft_specification(diameter=shaft_diameter_mm),
        "bearing": bearing_specification(),
        "hub": hub_specification(),
        "mount": mount_specification(),
        "body": body_specification(),
    }
    bound_specs = {}
    for slot, base_spec in base_specs.items():
        pending = base_spec.model_copy(
            update={
                "schema_version": "component-specification@4",
                "geometry_source": GeometrySourceReference(
                    artifact_id=chosen[slot],
                    artifact_hash=raw_hash,
                    source_identity=f"mini:rev3:{slot}@1",
                    content_identity="pending",
                    content_identity_algorithm="step-content-identity@1",
                ),
                "specification_hash": "pending",
            }
        )
        bound_specs[slot] = bind_component_specification_semantic_identity(
            pending, context
        )

    pending_request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@2",
        source_binding=binding,
        semantic_source_binding_hash="pending",
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )
    bound_request = bind_candidate_synthesis_request_semantic_identity(
        pending_request,
        state_manager=manager,
        store=store,
        project_id=PROJECT_ID,
    )
    policy = policy_for(DriveArchitecture.DIRECT_DRIVE)
    template_input = template(
        DriveArchitecture.DIRECT_DRIVE,
        motor_specification=bound_specs["motor"],
        shaft_specification=bound_specs["shaft"],
        bearing_a_specification=bound_specs["bearing"],
        bearing_b_specification=bound_specs["bearing"],
        hub_specification=bound_specs["hub"],
        mount_specification=bound_specs["mount"],
        driven_body_specification=bound_specs["body"],
    )
    application = _application(root)
    outcome = application.realize_and_evaluate_revolute_drive(
        request=bound_request,
        policy=policy,
        template_input=template_input,
        requirements=requirements(require_nominal_interface_compatibility=True),
    )
    assert outcome.construction.candidate is not None
    candidate = outcome.construction.candidate
    assert outcome.evaluation is not None

    publication = CandidatePublicationService(root, PROJECT_ID, manager).publish(
        candidate, bound_request, policy
    )
    return LiveVariant(
        label=label,
        workspace=root,
        export_artifact=export_artifact,
        step_bytes=step_bytes,
        raw_hash=raw_hash,
        content_identity=content_identity,
        geometry_artifact_id=chosen["shaft"],
        geometry_run_id=SOURCE_RUN_ID,
        bound_request=bound_request,
        policy=policy,
        bound_specs=bound_specs,
        candidate=candidate,
        evaluation=outcome.evaluation,
        publication_artifact_id=publication.artifact.artifact_id,
        publication_artifact_hash=publication.artifact.sha256,
    )


def _file_name_timestamp(step_bytes: bytes) -> str:
    marker = b"FILE_NAME("
    start = step_bytes.find(marker)
    assert start >= 0, "STEP bytes do not contain a FILE_NAME entity"
    open_position = start + len(marker) - 1
    first_comma = step_bytes.find(b",", open_position)
    second_field_start = first_comma + 1
    quote_start = step_bytes.find(b"'", second_field_start)
    quote_end = step_bytes.find(b"'", quote_start + 1)
    return step_bytes[quote_start + 1 : quote_end].decode("ascii")


@pytest.fixture(scope="module", autouse=True)
def _live_runtime_environment():
    if Path(_FREECADCMD).is_file():
        os.environ["MECHCAD_FREECADCMD"] = _FREECADCMD
    yield


@pytest.fixture(scope="module")
def live_variants():
    """Real FreeCAD exports plus the FINAL-default @2 chains built from them."""

    if not _FREECAD_AVAILABLE:
        pytest.skip("FreeCADCmd is not available")
    if _LIVE_ROOT.exists():
        import shutil

        shutil.rmtree(_LIVE_ROOT)
    _LIVE_ROOT.mkdir(parents=True, exist_ok=True)
    export_root = _LIVE_ROOT / "exports"

    artifact_a, bytes_a = _export_real_step(export_root / "a", "LIVE-A")
    artifact_b, bytes_b = _export_real_step(export_root / "b", "LIVE-B")
    if bytes_b == bytes_a:
        time.sleep(1.2)
        artifact_b, bytes_b = _export_real_step(export_root / "b-retry", "LIVE-B2")
    assert bytes_b != bytes_a, "real exports did not differ in raw bytes"
    artifact_c, bytes_c = _export_real_step(
        export_root / "c",
        "LIVE-C",
        length_mm=40.0,
        width_mm=25.0,
        thickness_mm=6.0,
    )

    variant_a = _build_live_variant(
        label="A",
        root=_LIVE_ROOT / "variant_a",
        export_artifact=artifact_a,
        step_bytes=bytes_a,
    )
    variant_b = _build_live_variant(
        label="B",
        root=_LIVE_ROOT / "variant_b",
        export_artifact=artifact_b,
        step_bytes=bytes_b,
    )
    variant_c = _build_live_variant(
        label="C",
        root=_LIVE_ROOT / "variant_c",
        export_artifact=artifact_c,
        step_bytes=bytes_c,
    )
    variant_d = _build_live_variant(
        label="D",
        root=_LIVE_ROOT / "variant_d",
        export_artifact=artifact_a,
        step_bytes=bytes_a,
        shaft_diameter_mm=14.0,
    )
    return {
        "A": variant_a,
        "B": variant_b,
        "C": variant_c,
        "D": variant_d,
    }


def test_live_runtime_is_real_freecad_subprocess_boundary():
    discovery = discover_freecad().require_available()
    assert discovery.executable == _FREECADCMD
    assert discovery.execution_boundary == "bundled FreeCAD command line"
    assert discovery.importable is False, "FreeCAD must not be importable in-process"
    provenance = FreeCADBackend().provenance()
    assert provenance.library_name == "FreeCAD"
    assert provenance.library_version == "1.1.3"


def test_live_repeated_exports_raw_differs_content_identity_equal(live_variants):
    a = live_variants["A"]
    b = live_variants["B"]

    assert a.step_bytes != b.step_bytes
    assert a.raw_hash != b.raw_hash
    assert "sha256:" + hashlib.sha256(a.step_bytes).hexdigest() == a.raw_hash
    assert "sha256:" + hashlib.sha256(b.step_bytes).hexdigest() == b.raw_hash

    timestamp_a = _file_name_timestamp(a.step_bytes)
    timestamp_b = _file_name_timestamp(b.step_bytes)
    assert timestamp_a != timestamp_b
    assert a.step_bytes.replace(timestamp_a.encode(), b"<TS>") == b.step_bytes.replace(
        timestamp_b.encode(), b"<TS>"
    ), "timestamp is the only raw difference"

    content_a = step_content_identity_v1(a.step_bytes)
    content_b = step_content_identity_v1(b.step_bytes)
    assert content_a.algorithm == "step-content-identity@1"
    assert content_b.algorithm == "step-content-identity@1"
    assert content_a.content_hash == b.content_identity
    assert content_b.content_hash == a.content_identity
    assert content_a.content_hash == content_b.content_hash
    assert a.content_identity == b.content_identity

    raw_provenance_a = (
        a.export_artifact.artifact_id,
        a.export_artifact.run_id,
        a.export_artifact.relative_path,
        a.raw_hash,
    )
    raw_provenance_b = (
        b.export_artifact.artifact_id,
        b.export_artifact.run_id,
        b.export_artifact.relative_path,
        b.raw_hash,
    )
    assert raw_provenance_a != raw_provenance_b


def test_live_downstream_semantic_identities_equal_under_timestamp_rotation(live_variants):
    a = live_variants["A"]
    b = live_variants["B"]

    assert (
        a.bound_request.semantic_source_binding_hash
        == b.bound_request.semantic_source_binding_hash
    )
    assert a.bound_request.request_hash == b.bound_request.request_hash
    assert a.bound_request.schema_version == "candidate-synthesis-request@2"

    assert a.semantic_reference_hashes == b.semantic_reference_hashes
    assert a.specification_hashes == b.specification_hashes
    assert all(
        value is not None and value.startswith("sha256:")
        for value in a.semantic_reference_hashes
    )

    assert a.candidate.schema_version == "mechanical-design-candidate@2"
    assert a.candidate.candidate_hash == b.candidate.candidate_hash
    assert a.candidate.candidate_hash == candidate_hash_v2(a.candidate)
    assert a.candidate.semantic_source_binding_hash == (
        a.bound_request.semantic_source_binding_hash
    )

    assert a.evaluation.schema_version == "revolute-drive-admissibility@2"
    assert a.evaluation.candidate_hash == a.candidate.candidate_hash
    assert a.evaluation.result_hash == b.evaluation.result_hash

    # Raw provenance differs independently while the semantic identity is equal.
    assert a.bound_request.source_binding.source_state_hash != (
        b.bound_request.source_binding.source_state_hash
    )
    assert a.candidate.source_binding != b.candidate.source_binding
    assert a.raw_hash != b.raw_hash


def test_live_mini_rev3_replay_through_final_default_emits_at2_family(live_variants):
    a = live_variants["A"]

    assert _LIVE_ROOT.is_dir()
    assert "projects" not in _LIVE_ROOT.parts
    assert a.workspace.is_relative_to(_LIVE_ROOT)

    # The FINAL default emitted the new homogeneous family from a real artifact.
    assert a.candidate.schema_version == "mechanical-design-candidate@2"
    assert a.evaluation.schema_version == "revolute-drive-admissibility@2"
    assert a.bound_request.schema_version == "candidate-synthesis-request@2"
    assert a.evaluation.candidate_hash == a.candidate.candidate_hash
    assert a.evaluation.result_hash.startswith("sha256:")
    assert a.evaluation.status.value == "admissible"

    # The real STEP artifact is byte-verifiable in the isolated workspace.
    store = ArtifactStore(a.workspace, project_id=PROJECT_ID, run_id=a.geometry_run_id)
    artifact, content = store.read_verified_strict(
        a.geometry_artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash=a.raw_hash,
    )
    assert artifact.artifact_id == a.geometry_artifact_id
    assert step_content_identity_v1(content).content_hash == a.content_identity

    # The historical MINI workspace is never touched by this replay.
    historical = _REPO_ROOT / "projects" / "mini_rotary_fixture"
    assert historical.is_dir()
    assert not historical.is_relative_to(_LIVE_ROOT)


_CHILD_SCRIPT = r'''
import hashlib
import json
import os
import sys

_locator_path = sys.argv[1]
with open(_locator_path, encoding="utf-8") as handle:
    _locator = json.load(handle)

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import CandidateSynthesisPolicy, CandidateSynthesisRequest
from mechcad_harness.candidates.models import candidate_hash_v2
from mechcad_harness.candidates.services import (
    CandidatePublicationService,
    compute_verified_semantic_binding,
)
from mechcad_harness.state import StateManager
from mechcad_harness.step_content_identity import step_content_identity_v1

_MARKER = "TP8_3_FRESH_PROCESS_RESULT "


def _emit(payload):
    sys.stdout.write(_MARKER + json.dumps(payload) + "\n")
    sys.stdout.flush()


def main():
    workspace = _locator["workspace"]
    project_id = _locator["project_id"]
    manager = StateManager(workspace)
    store = ArtifactStore(workspace, project_id=project_id, run_id="PUBLISH")

    publication = CandidatePublicationService(workspace, project_id, manager).resolve(
        _locator["publication_artifact_id"]
    )
    candidate = publication.candidate

    _artifact, content = store.read_verified_strict(
        _locator["publication_artifact_id"], expected_type=ArtifactType.JSON
    )
    payload = json.loads(content)
    request = CandidateSynthesisRequest.model_validate(payload["request"])
    CandidateSynthesisPolicy.model_validate(payload["policy"])

    raw = {}
    content_identity = {}
    for item in _locator["geometry"]:
        _source, bytes_ = ArtifactStore(
            workspace, project_id=project_id, run_id=item["run_id"]
        ).read_verified_strict(
            item["artifact_id"],
            expected_type=ArtifactType.STEP,
            expected_hash=item["raw_hash"],
        )
        raw[item["artifact_id"]] = "sha256:" + hashlib.sha256(bytes_).hexdigest()
        content_identity[item["artifact_id"]] = step_content_identity_v1(
            bytes_
        ).content_hash

    state = manager.load_revision(project_id, candidate.source_binding.source_revision)
    _context, semantic_hash = compute_verified_semantic_binding(
        candidate.source_binding,
        state=state,
        store=store,
        project_id=project_id,
    )

    geometry_specs = [
        specification
        for specification in candidate.component_specifications
        if specification.geometry_source is not None
    ]
    recomputed = {
        "pid": os.getpid(),
        "raw": raw,
        "content_identity": content_identity,
        "semantic_source_binding_hash": semantic_hash,
        "request_hash": request.request_hash,
        "candidate_hash": candidate_hash_v2(candidate),
        "semantic_reference_hashes": [
            specification.geometry_source.semantic_reference_hash
            for specification in geometry_specs
        ],
        "specification_hashes": sorted(
            specification.specification_hash
            for specification in candidate.component_specifications
        ),
    }
    _emit({"ok": True, "recomputed": recomputed})


try:
    main()
except Exception as exc:  # fail closed
    _emit({"ok": False, "error": type(exc).__name__ + ": " + str(exc)})
    sys.exit(1)
'''


def _run_fresh_process_child(variant: LiveVariant) -> dict:
    locator = {
        "workspace": str(variant.workspace),
        "project_id": PROJECT_ID,
        "publication_artifact_id": variant.publication_artifact_id,
        "geometry": [
            {
                "artifact_id": variant.geometry_artifact_id,
                "run_id": variant.geometry_run_id,
                "raw_hash": variant.raw_hash,
            }
        ],
    }
    locator_path = variant.workspace / "tp8_3_restart_locator.json"
    locator_path.write_text(json.dumps(locator), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT, str(locator_path)],
        capture_output=True,
        text=True,
        cwd=str(variant.workspace),
    )
    marker = "TP8_3_FRESH_PROCESS_RESULT "
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(marker):
            return {"completed": completed, "payload": json.loads(line[len(marker):])}
    raise AssertionError(
        f"child emitted no result marker; stdout was:\n{completed.stdout}\n"
        f"stderr was:\n{completed.stderr}"
    )


def test_live_fresh_process_restart_recomputes_live_step_identities(live_variants):
    a = live_variants["A"]
    result = _run_fresh_process_child(a)
    completed = result["completed"]
    payload = result["payload"]

    assert completed.returncode == 0, completed.stderr
    assert payload["ok"] is True, payload
    recomputed = payload["recomputed"]
    assert recomputed["pid"] != os.getpid()

    # Raw binding reloaded from ArtifactStore bytes.
    assert recomputed["raw"][a.geometry_artifact_id] == a.raw_hash
    # Semantic binding recomputed from the same bytes.
    assert recomputed["content_identity"][a.geometry_artifact_id] == a.content_identity
    assert recomputed["semantic_source_binding_hash"] == (
        a.bound_request.semantic_source_binding_hash
    )
    assert recomputed["request_hash"] == a.bound_request.request_hash
    assert recomputed["candidate_hash"] == a.candidate.candidate_hash
    assert tuple(recomputed["semantic_reference_hashes"]) == a.semantic_reference_hashes
    assert tuple(recomputed["specification_hashes"]) == a.specification_hashes


def test_live_real_engineering_change_changes_semantic_identity(live_variants):
    a = live_variants["A"]
    c = live_variants["C"]
    d = live_variants["D"]

    # A genuinely different real geometry changes the STEP content identity and
    # therefore the whole downstream semantic identity.
    assert c.raw_hash != a.raw_hash
    assert c.content_identity != a.content_identity
    assert c.candidate.candidate_hash != a.candidate.candidate_hash
    assert c.evaluation.result_hash != a.evaluation.result_hash

    # A changed real supplied engineering input (shaft diameter) leaves the STEP
    # content identity untouched but changes the component-specification@4 and
    # candidate@2 semantic identities.
    assert d.raw_hash == a.raw_hash
    assert d.content_identity == a.content_identity
    assert d.specification_hashes != a.specification_hashes
    assert d.candidate.candidate_hash != a.candidate.candidate_hash
    assert d.evaluation.result_hash != a.evaluation.result_hash
    # The source binding and request scope are unchanged, so the request@2
    # identity stays equal; only the engineering content identity changes.
    assert d.bound_request.request_hash == a.bound_request.request_hash
