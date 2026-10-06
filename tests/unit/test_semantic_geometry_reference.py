import pytest

from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.models.geometry_identity import semantic_reference_hash
from mechcad_harness.models.physical_mechanism import CanonicalGeometrySourceReference


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
CONTENT = "sha256:" + "c" * 64


def _reference_class_pairs():
    return (GeometrySourceReference, CanonicalGeometrySourceReference)


@pytest.mark.parametrize("reference_class", _reference_class_pairs())
def test_historical_reference_dump_has_only_legacy_keys(reference_class):
    reference = reference_class(
        artifact_id="artifact-a",
        artifact_hash=HASH_A,
        source_identity="source-a",
    )

    expected = {
        "artifact_id",
        "artifact_hash",
        "source_identity",
        "format",
    }
    if reference_class is CanonicalGeometrySourceReference:
        expected.add("reference_hash")
    assert set(reference.model_dump(mode="json")) == expected


@pytest.mark.parametrize("reference_class", _reference_class_pairs())
def test_full_semantic_trio_is_serialized_and_recomputed(reference_class):
    reference = reference_class(
        artifact_id="artifact-a",
        artifact_hash=HASH_A,
        source_identity="source-a",
        coordinate_system_id="frame-0",
        content_identity=CONTENT,
        content_identity_algorithm="step-content-identity@1",
        semantic_reference_hash="pending",
    )

    payload = reference.model_dump(mode="json")
    assert payload["content_identity"] == CONTENT
    assert payload["content_identity_algorithm"] == "step-content-identity@1"
    assert payload["semantic_reference_hash"] == semantic_reference_hash(reference)


@pytest.mark.parametrize("reference_class", _reference_class_pairs())
def test_semantic_siblings_do_not_change_legacy_reference_hash(reference_class):
    legacy = reference_class(
        artifact_id="artifact-a",
        artifact_hash=HASH_A,
        source_identity="source-a",
        coordinate_system_id="frame-0",
    )
    semantic = reference_class(
        artifact_id="artifact-a",
        artifact_hash=HASH_A,
        source_identity="source-a",
        coordinate_system_id="frame-0",
        content_identity=CONTENT,
        content_identity_algorithm="step-content-identity@1",
    )

    assert semantic.reference_hash == legacy.reference_hash


@pytest.mark.parametrize("reference_class", _reference_class_pairs())
def test_semantic_reference_hash_ignores_timestamp_only_raw_rotation(reference_class):
    first = reference_class(
        artifact_id="artifact-a",
        artifact_hash=HASH_A,
        source_identity="source-a",
        coordinate_system_id="frame-0",
        content_identity=CONTENT,
        content_identity_algorithm="step-content-identity@1",
    )
    second = reference_class(
        artifact_id="artifact-b",
        artifact_hash=HASH_B,
        source_identity="source-a",
        coordinate_system_id="frame-0",
        content_identity=CONTENT,
        content_identity_algorithm="step-content-identity@1",
    )

    assert first.reference_hash != second.reference_hash
    assert first.semantic_reference_hash == second.semantic_reference_hash


@pytest.mark.parametrize("reference_class", _reference_class_pairs())
def test_semantic_trio_round_trips(reference_class):
    reference = reference_class(
        artifact_id="artifact-a",
        artifact_hash=HASH_A,
        source_identity="source-a",
        coordinate_system_id="frame-0",
        content_identity=CONTENT,
        content_identity_algorithm="step-content-identity@1",
    )

    restored = reference_class.model_validate(reference.model_dump(mode="json"))
    assert restored.model_dump(mode="json") == reference.model_dump(mode="json")


@pytest.mark.parametrize("reference_class", _reference_class_pairs())
@pytest.mark.parametrize(
    "updates",
    [
        {"content_identity": CONTENT},
        {"content_identity_algorithm": "wrong@1"},
        {"semantic_reference_hash": CONTENT},
    ],
)
def test_partial_or_wrong_semantic_trio_fails(reference_class, updates):
    with pytest.raises(ValueError):
        reference_class(
            artifact_id="artifact-a",
            artifact_hash=HASH_A,
            source_identity="source-a",
            **updates,
        )
