import json
from hashlib import sha256

import pytest

from mechcad_harness.backends.models import BackendProvenance
from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact


def _symlink_or_skip(link, target, *, target_is_directory=False):
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")


def test_artifact_store_publishes_hashed_immutable_metadata(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1")
    artifact = store.publish(
        artifact_id="ART-1",
        artifact_type=ArtifactType.STEP,
        filename="gear.step",
        content=b"step-data",
        producer_tool_name="tool",
        producer_tool_version="1.0",
        bound_revision=1,
        bound_state_hash="sha256:state",
    )
    path = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1" / "gear.step"
    assert artifact.sha256 == f"sha256:{sha256(b'step-data').hexdigest()}"
    assert artifact.size_bytes == len(b"step-data")
    assert path.read_bytes() == b"step-data"
    assert json.loads((path.parent / "metadata.json").read_text()) == artifact.model_dump(mode="json")
    with pytest.raises(Exception):
        store.publish("ART-1", ArtifactType.STEP, "gear.step", b"other", "tool", "1.0", 1, "sha256:state")


def test_artifact_store_rejects_unsafe_paths(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    with pytest.raises(ValueError):
        store.publish("ART-2", ArtifactType.STEP, "..\\escape.step", b"x", "tool", "1.0", 1, "sha256:state")


@pytest.mark.parametrize("filename", ("metadata.json", "METADATA.JSON"))
def test_artifact_store_rejects_payload_metadata_path_collision(tmp_path, filename):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")

    with pytest.raises(ValueError, match="metadata"):
        store.publish(
            "ART-2", ArtifactType.JSON, filename, b'{"payload": true}\n',
            "tool", "1.0", 1, "sha256:state",
        )

    artifact_dir = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-2"
    assert not (artifact_dir / "metadata.json").exists()
    assert not (artifact_dir / filename).exists()


def test_artifact_store_rejects_symlinked_artifact_directory(tmp_path):
    outside = tmp_path.parent / "artifact-publish-outside"
    outside.mkdir()
    artifact_dir = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1"
    artifact_dir.parent.mkdir(parents=True)
    _symlink_or_skip(artifact_dir, outside, target_is_directory=True)
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")

    with pytest.raises(ValueError, match="workspace|symlink|reparse"):
        store.publish("ART-1", ArtifactType.STEP, "gear.step", b"step-data", "tool", "1.0", 1, "sha256:state")

    assert not (outside / "gear.step").exists()
    assert not (outside / "metadata.json").exists()


def test_artifact_store_rejects_existing_artifact_symlink_target(tmp_path):
    artifact_dir = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1"
    artifact_dir.mkdir(parents=True)
    outside = tmp_path.parent / "artifact-file-outside.step"
    outside.write_bytes(b"original")
    artifact_path = artifact_dir / "gear.step"
    _symlink_or_skip(artifact_path, outside)
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")

    with pytest.raises(ValueError, match="workspace|symlink|reparse"):
        store.publish("ART-1", ArtifactType.STEP, "gear.step", b"replacement", "tool", "1.0", 1, "sha256:state")

    assert outside.read_bytes() == b"original"


def test_artifact_store_rejects_existing_metadata_symlink_target(tmp_path):
    artifact_dir = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1"
    artifact_dir.mkdir(parents=True)
    outside = tmp_path.parent / "metadata-outside.json"
    outside.write_text("sentinel", encoding="utf-8")
    _symlink_or_skip(artifact_dir / "metadata.json", outside)
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")

    with pytest.raises(ValueError, match="workspace|symlink|reparse"):
        store.publish("ART-1", ArtifactType.STEP, "gear.step", b"step-data", "tool", "1.0", 1, "sha256:state")

    assert outside.read_text(encoding="utf-8") == "sentinel"


def test_artifact_store_rejects_dangling_artifact_symlink(tmp_path):
    artifact_dir = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1"
    artifact_dir.mkdir(parents=True)
    artifact_path = artifact_dir / "gear.step"
    _symlink_or_skip(artifact_path, tmp_path.parent / "missing-artifact.step")
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")

    with pytest.raises(ValueError, match="workspace|symlink|reparse"):
        store.publish("ART-1", ArtifactType.STEP, "gear.step", b"step-data", "tool", "1.0", 1, "sha256:state")


def test_artifact_model_is_json_safe():
    artifact = EngineeringArtifact(
        artifact_id="ART-1", project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1", artifact_type=ArtifactType.STL, media_type="model/stl", relative_path="projects/PRJ-1/runs/RUN-1/artifacts/ART-1/gear.stl", sha256="sha256:a", size_bytes=1, producer_tool_name="tool", producer_tool_version="1.0", bound_revision=1, bound_state_hash="sha256:s"
    )
    assert artifact.model_dump(mode="json")["artifact_type"] == "stl"


def test_same_artifact_id_is_scoped_to_run(tmp_path):
    first = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    second = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-2")
    first.publish("ART-1", ArtifactType.STEP, "gear.step", b"one", "tool", "1.0", 1, "sha256:one")
    second.publish("ART-1", ArtifactType.STEP, "gear.step", b"two", "tool", "1.0", 1, "sha256:two")
    assert (tmp_path / "projects/PRJ-1/runs/RUN-1/artifacts/ART-1/gear.step").read_bytes() == b"one"
    assert (tmp_path / "projects/PRJ-1/runs/RUN-2/artifacts/ART-1/gear.step").read_bytes() == b"two"


def test_scope_and_filename_traversal_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        ArtifactStore(tmp_path, project_id="PRJ-1", run_id="../RUN-1")
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    for filename in ("..", "../gear.step", "/absolute/gear.step", "C:/gear.step", "a\\..\\gear.step"):
        with pytest.raises(ValueError):
            store.publish("ART-2", ArtifactType.STEP, filename, b"x", "tool", "1.0", 1, "sha256:x")


def test_artifact_store_reuses_exact_immutable_replay(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    first = store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", b"fcstd", "freecad", "1.0", 1, "sha256:state")
    second = store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", b"fcstd", "freecad", "1.0", 1, "sha256:state")
    assert second == first


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "PRJ-OTHER"),
        ("run_id", "RUN-OTHER"),
        ("task_id", "TASK-OTHER"),
        ("artifact_type", "stl"),
        ("media_type", "application/octet-stream"),
        ("relative_path", "projects/PRJ-1/runs/RUN-1/artifacts/ART-1/other.step"),
        ("producer_tool_name", "other-tool"),
        ("producer_tool_version", "other-version"),
        ("bound_revision", 2),
        ("bound_state_hash", "sha256:other-state"),
        ("input_hash", "sha256:other-input"),
        ("backend_provenance", None),
        ("build123d_provenance", None),
        ("size_bytes", 999),
        ("sha256", "sha256:" + "0" * 64),
    ],
)
def test_artifact_store_rejects_same_bytes_when_immutable_metadata_differs(tmp_path, field, value):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1", task_id="TASK-1")
    backend_provenance = BackendProvenance(
        backend_name="freecad",
        backend_adapter_version="adapter@1",
        library_name="FreeCAD",
        library_version="1.1.3",
        library_source="bundled",
        library_revision="freecad-1.1.3",
    )
    build123d_provenance = BackendProvenance(
        backend_name="build123d",
        backend_adapter_version="adapter@1",
        library_name="build123d",
        library_version="0.1",
        library_source="bundled",
        library_revision="build123d-0.1",
    )
    store.publish(
        "ART-1",
        ArtifactType.STEP,
        "plate.step",
        b"step-data",
        "freecad",
        "1.0",
        1,
        "sha256:state",
        backend_provenance=backend_provenance,
        build123d_provenance=build123d_provenance,
        input_hash="sha256:input",
    )
    metadata_path = (
        tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1" / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata[field] = value
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(FileExistsError, match="conflict"):
        store.publish(
            "ART-1", ArtifactType.STEP, "plate.step", b"step-data", "freecad", "1.0", 1, "sha256:state",
            backend_provenance=backend_provenance,
            build123d_provenance=build123d_provenance,
            input_hash="sha256:input",
        )


def test_artifact_store_existing_rejects_metadata_from_another_scope(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    artifact = store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", b"fcstd", "freecad", "1.0", 1, "sha256:state")
    metadata = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1" / "metadata.json"
    metadata.write_text(metadata.read_text().replace('"run_id":"RUN-1"', '"run_id":"RUN-2"'), encoding="utf-8")
    assert store.existing(artifact.artifact_id) is None


def test_artifact_store_existing_rejects_metadata_with_wrong_lookup_identity(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    artifact = store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", b"fcstd", "freecad", "1.0", 1, "sha256:state")
    metadata_path = tmp_path / artifact.relative_path
    metadata = json.loads((metadata_path.parent / "metadata.json").read_text(encoding="utf-8"))
    metadata["artifact_id"] = "ART-FORGED"
    (metadata_path.parent / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    assert store.existing("ART-1") is None


def test_artifact_store_existing_rejects_relative_path_escape(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    content = b"fcstd"
    artifact = store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", content, "freecad", "1.0", 1, "sha256:state")
    outside = tmp_path.parent / "outside.FCStd"
    outside.write_bytes(content)
    metadata_path = tmp_path / artifact.relative_path
    metadata = json.loads((metadata_path.parent / "metadata.json").read_text(encoding="utf-8"))
    metadata["relative_path"] = "../outside.FCStd"
    (metadata_path.parent / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    assert store.existing("ART-1") is None


def test_artifact_store_verified_read_enforces_expected_type_and_hash(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    artifact = store.publish("ART-1", ArtifactType.STEP, "gear.step", b"step-data", "tool", "1.0", 1, "sha256:state")

    assert store.read_verified(
        artifact.artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash=artifact.sha256,
    ) is not None
    assert store.read_verified(
        artifact.artifact_id,
        expected_type=ArtifactType.JSON,
        expected_hash=artifact.sha256,
    ) is None
    assert store.read_verified(
        artifact.artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash="sha256:" + "0" * 64,
    ) is None


def test_artifact_store_rejects_conflicting_replay(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", b"fcstd", "freecad", "1.0", 1, "sha256:state")
    with pytest.raises(Exception, match="conflict"):
        store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", b"other", "freecad", "1.0", 1, "sha256:state")


def test_artifact_store_supports_immutable_json_analysis_results(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    artifact = store.publish("ANALYSIS-1", ArtifactType.JSON, "analysis.json", b'{"passed":true}\n', "analyzer", "1.0", 1, "sha256:state", input_hash="sha256:plan")
    assert store.existing("ANALYSIS-1") == artifact
    assert artifact.media_type == "application/json"
