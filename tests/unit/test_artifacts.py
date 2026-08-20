import json
from hashlib import sha256

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType, EngineeringArtifact


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


def test_artifact_store_existing_rejects_metadata_from_another_scope(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    artifact = store.publish("ART-1", ArtifactType.FCSTD, "plate.FCStd", b"fcstd", "freecad", "1.0", 1, "sha256:state")
    metadata = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-1" / "metadata.json"
    metadata.write_text(metadata.read_text().replace('"run_id":"RUN-1"', '"run_id":"RUN-2"'), encoding="utf-8")
    assert store.existing(artifact.artifact_id) is None


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
