import pytest
from pydantic import ValidationError

from mechcad_harness.models.geometry_identity import (
    GeometryArtifactIdentity,
    geometry_identity_hash,
    geometry_reference_hash,
    reference_hash_payload,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.models import CanonicalGeometrySourceReference


def test_identity_hash_is_deterministic_and_excludes_none_coordinate_system():
    a = GeometryArtifactIdentity(
        artifact_id="ART-1",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="src:1",
    )
    b = GeometryArtifactIdentity.model_validate(a.model_dump(mode="json"))
    assert a.geometry_identity_hash == b.geometry_identity_hash
    assert "coordinate_system_id" not in reference_hash_payload(
        {"artifact_id": "x", "artifact_hash": "sha256:" + "b" * 64,
         "source_identity": "s", "format": "step",
         "coordinate_system_id": None, "reference_hash": "pending"}
    )
    payload = reference_hash_payload(
        {"artifact_id": "x", "artifact_hash": "sha256:" + "b" * 64,
         "source_identity": "s", "format": "step",
         "coordinate_system_id": "step-model-coordinates@1",
         "reference_hash": "pending"}
    )
    assert payload["coordinate_system_id"] == "step-model-coordinates@1"


def test_identity_projection_from_candidate_and_canonical_references():
    candidate_ref = GeometrySourceReference(
        artifact_id="ART-2", artifact_hash="sha256:" + "c" * 64,
        source_identity="src:2",
    )
    canonical_ref = CanonicalGeometrySourceReference(
        artifact_id="ART-2", artifact_hash="sha256:" + "c" * 64,
        source_identity="src:2",
    )
    assert GeometryArtifactIdentity.from_candidate(candidate_ref).geometry_identity_hash == geometry_identity_hash(
        GeometryArtifactIdentity.from_candidate(candidate_ref)
    )
    assert GeometryArtifactIdentity.from_canonical(canonical_ref) == GeometryArtifactIdentity.from_candidate(candidate_ref)


def test_geometry_reference_hash_matches_candidate_projection_for_legacy_and_m13_identities():
    legacy = GeometrySourceReference(
        artifact_id="ART-LEGACY",
        artifact_hash="sha256:" + "e" * 64,
        source_identity="src:legacy",
    )
    legacy_identity = GeometryArtifactIdentity.from_candidate(legacy)
    assert geometry_reference_hash(legacy_identity) == legacy.reference_hash
    assert geometry_reference_hash(legacy_identity) != legacy_identity.geometry_identity_hash

    stamped = GeometrySourceReference(
        artifact_id="ART-M13",
        artifact_hash="sha256:" + "f" * 64,
        source_identity="src:m13",
        coordinate_system_id="step-model-coordinates@1",
    )
    assert geometry_reference_hash(GeometryArtifactIdentity.from_candidate(stamped)) == stamped.reference_hash


def test_invalid_inputs_rejected():
    with pytest.raises(ValidationError):
        GeometryArtifactIdentity(
            artifact_id=" ",
            artifact_hash="sha256:" + "a" * 64,
            source_identity="s",
        )
    with pytest.raises(ValidationError):
        GeometryArtifactIdentity(
            artifact_id="a",
            artifact_hash="not-a-hash",
            source_identity="s",
        )


def test_identity_with_coordinate_system_serializes_and_validates_its_own_hash():
    identity = GeometryArtifactIdentity(
        artifact_id="ART-COORD",
        artifact_hash="sha256:" + "d" * 64,
        source_identity="vendor:coordinate:1",
        coordinate_system_id="step-model-coordinates@1",
    )
    payload = identity.model_dump(mode="json")
    assert payload["coordinate_system_id"] == "step-model-coordinates@1"
    assert payload["geometry_identity_hash"] == identity.geometry_identity_hash
    assert GeometryArtifactIdentity.model_validate(payload) == identity
    with pytest.raises(ValidationError):
        GeometryArtifactIdentity.model_validate(
            payload | {"geometry_identity_hash": "sha256:" + "0" * 64}
        )
