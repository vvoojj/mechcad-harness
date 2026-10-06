from __future__ import annotations

from hashlib import sha256

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import assembly_hash
from mechcad_harness.candidates.canonical_cad import (
    CanonicalCadRealizationV2,
    CanonicalPhysicalCadCompiler,
    canonical_cad_realization_hash_v2,
    semantic_canonical_cad_request_hash,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    ProjectArtifactResolver,
    TrustedSourceArtifact,
    _projection_from_mechanism,
)
from mechcad_harness.core.canonical import canonical_json_bytes

from test_canonical_mechanism_v4 import _STEP_TEMPLATE, _mechanism_at4


def _fixture(tmp_path, *, variant="A", state_hash=None):
    mechanism = _mechanism_at4(variant=variant)
    step = _STEP_TEMPLATE.format(
        timestamp=(
            "2026-09-22T12:34:56"
            if variant == "A"
            else "2027-01-02T03:04:05"
        )
    ).encode()
    raw_hash = "sha256:" + sha256(step).hexdigest()
    workspace = tmp_path / variant
    workspace.mkdir(parents=True)
    store = ArtifactStore(workspace, project_id="PRJ-CAD-V4", run_id=f"SOURCE-{variant}")
    sources = []
    for specification in mechanism.component_specifications:
        reference = specification.geometry_source
        assert reference is not None
        artifact = store.publish(
            reference.artifact_id,
            ArtifactType.STEP,
            f"{reference.artifact_id.lower()}.step",
            step,
            "fixture-freecad",
            "1.1.3",
            1,
            "sha256:" + "a" * 64,
        )
        assert artifact.sha256 == raw_hash == reference.artifact_hash
        sources.append(TrustedSourceArtifact.from_artifact(artifact))
    reconstruction = CanonicalMechanismReconstruction(
        project_id="PRJ-CAD-V4",
        revision=7,
        state_hash=state_hash or "sha256:" + "b" * 64,
        canonical_mechanism=mechanism,
        trusted_source_references=tuple(sources),
        normalized_projection_hash=_projection_from_mechanism(mechanism).projection_hash,
    )
    resolver = ProjectArtifactResolver(
        ArtifactStore(workspace, project_id="PRJ-CAD-V4", run_id="LOOKUP")
    )
    return mechanism, reconstruction, resolver


def _realize(tmp_path, *, variant="A", state_hash=None):
    mechanism, reconstruction, resolver = _fixture(
        tmp_path, variant=variant, state_hash=state_hash
    )
    return mechanism, reconstruction, CanonicalPhysicalCadCompiler(resolver).realize(
        reconstruction
    )


def test_canonical_realization_at2_declares_exactly_17_fields_and_round_trips(tmp_path):
    mechanism, reconstruction, realization = _realize(tmp_path)

    assert set(CanonicalCadRealizationV2.model_fields) == {
        "schema_version",
        "project_id",
        "revision",
        "state_hash",
        "mechanism_id",
        "mechanism_hash",
        "request_hash",
        "mappings",
        "assembly",
        "assembly_hash",
        "selected_source_artifact_ids",
        "selected_source_content_identities",
        "selected_source_provenance",
        "compiler_identity",
        "compiler_version",
        "realization_hash",
        "selected_source_artifact_hashes",
    }
    assert realization.schema_version == "canonical-cad-realization@2"
    assert realization.mechanism_hash == mechanism.mechanism_hash
    assert realization.realization_hash == canonical_cad_realization_hash_v2(
        realization
    )
    assert realization.selected_source_artifact_hashes == tuple(
        source.sha256 for source in realization.selected_source_provenance
    )
    assert CanonicalCadRealizationV2.model_validate(
        realization.model_dump(mode="json")
    ) == realization
    assert realization.revision == reconstruction.revision


def test_semantic_canonical_cad_request_v2_has_exact_payload(tmp_path):
    mechanism, reconstruction, realization = _realize(tmp_path)
    payload = {
        "request_contract": "canonical-cad-request@2",
        "project_id": reconstruction.project_id,
        "revision": reconstruction.revision,
        "mechanism_id": mechanism.id,
        "mechanism_hash": mechanism.mechanism_hash,
        "mapping_hashes": [
            mapping.mapping_hash
            for mapping in sorted(
                realization.mappings, key=lambda mapping: mapping.cad_instance_id
            )
        ],
        "compiler_identity": "canonical-physical-cad-compiler",
        "compiler_version": "canonical-cad@1",
    }
    assert realization.request_hash == semantic_canonical_cad_request_hash(
        project_id=reconstruction.project_id,
        revision=reconstruction.revision,
        mechanism=mechanism,
        mappings=realization.mappings,
        compiler_identity="canonical-physical-cad-compiler",
        compiler_version="canonical-cad@1",
    )
    assert realization.request_hash == "sha256:" + sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    assert realization.request_hash == (
        "sha256:5de8efbdc4203316cbf1d0af812844164a4d0bceea009cc509362005d91853d1"
    )
    assert realization.realization_hash == (
        "sha256:d28ee1cc45824761b2a9d2f5d507c64af004c53490ef8055f54308b0333f58a4"
    )
    assert "state_hash" not in payload
    assert "mappings" not in payload
    assert "ART-" not in repr(payload)
    assert semantic_canonical_cad_request_hash(
        project_id=reconstruction.project_id,
        revision=reconstruction.revision,
        mechanism=mechanism,
        mappings=tuple(reversed(realization.mappings)),
        compiler_identity="canonical-physical-cad-compiler",
        compiler_version="canonical-cad@1",
    ) == realization.request_hash


def test_semantic_canonical_cad_request_rejects_duplicate_cad_slots(tmp_path):
    mechanism, reconstruction, realization = _realize(tmp_path)
    with pytest.raises(ValueError, match="cad_instance_id|unique"):
        semantic_canonical_cad_request_hash(
            project_id=reconstruction.project_id,
            revision=reconstruction.revision,
            mechanism=mechanism,
            mappings=(realization.mappings[0], realization.mappings[0]),
            compiler_identity="canonical-physical-cad-compiler",
            compiler_version="canonical-cad@1",
        )


def test_canonical_realization_at2_is_invariant_to_raw_step_rotation(tmp_path):
    _, _, first = _realize(tmp_path / "first", variant="A")
    _, _, second = _realize(tmp_path / "second", variant="B")

    assert first.assembly_hash != second.assembly_hash
    assert first.selected_source_artifact_ids != second.selected_source_artifact_ids
    assert first.selected_source_artifact_hashes != second.selected_source_artifact_hashes
    assert first.request_hash == second.request_hash
    assert first.realization_hash == second.realization_hash


def test_state_hash_is_an_excluded_coordinate_but_revision_remains_bound(tmp_path):
    mechanism, reconstruction, resolver = _fixture(tmp_path)
    first = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
    changed_coordinate = CanonicalMechanismReconstruction.model_validate(
        reconstruction.model_dump(mode="json")
        | {"state_hash": "sha256:" + "e" * 64}
    )
    second = CanonicalPhysicalCadCompiler(resolver).realize(changed_coordinate)

    assert first.state_hash != second.state_hash
    assert first.request_hash == second.request_hash
    assert first.realization_hash == second.realization_hash
    moved_revision_hash = semantic_canonical_cad_request_hash(
        project_id=reconstruction.project_id,
        revision=reconstruction.revision + 1,
        mechanism=mechanism,
        mappings=first.mappings,
        compiler_identity="canonical-physical-cad-compiler",
        compiler_version="canonical-cad@1",
    )
    assert moved_revision_hash != first.request_hash


def test_legacy_canonical_request_helper_cannot_bind_realization_at2(tmp_path):
    from mechcad_harness.candidates.canonical_cad import _canonical_request_hash

    mechanism, reconstruction, realization = _realize(tmp_path)
    legacy_hash = _canonical_request_hash(
        reconstruction.project_id,
        reconstruction.revision,
        reconstruction.state_hash,
        mechanism.id,
        mechanism.mechanism_hash,
        realization.mappings,
        "canonical-physical-cad-compiler",
        "canonical-cad@1",
    )

    with pytest.raises(ValueError, match="request hash|request identity"):
        CanonicalCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
            | {"request_hash": legacy_hash, "realization_hash": "pending"}
        )


def test_realization_at2_rejects_mapping_at1_nesting(tmp_path):
    from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadMapping

    mechanism, _, realization = _realize(tmp_path)
    component = mechanism.components[0]
    legacy = CanonicalPhysicalCadMapping(
        mechanism_hash=mechanism.mechanism_hash,
        physical_instance_id=component.instance_id,
        cad_instance_id="legacy-cad",
        component_hash=component.component_hash,
        specification_hash=component.specification_hash,
        fidelity="trusted_source_geometry",
        representation_identity="sha256:" + "a" * 64,
        source_geometry_identity="sha256:" + "b" * 64,
        geometry_definition_identities=("ART-LEGACY",),
        placement=realization.mappings[0].placement,
        placement_id=None,
        placement_hash=None,
        placement_input_identities=(component.component_hash,),
        placement_relation="canonical-default-home-placement@1",
    )
    with pytest.raises(ValueError, match="mapping@2|valid dictionary|version"):
        CanonicalCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
            | {"mappings": (legacy,), "realization_hash": "pending"}
        )
