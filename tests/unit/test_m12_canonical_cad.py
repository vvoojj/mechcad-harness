from __future__ import annotations

import pytest
from pydantic import ValidationError

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import assembly_hash
from mechcad_harness.candidates.canonical_cad import (
    CanonicalCadIntegrityError,
    CanonicalCadRealization,
    CanonicalPhysicalCadCompiler,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    CanonicalPhysicalMechanismCompiler,
    ProjectArtifactResolver,
    TrustedSourceArtifact,
)
from mechcad_harness.models import (
    CanonicalAcceptedDesignChoice,
    CanonicalPhysicalMechanism,
    DesignState,
)
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.state import StateManager, state_hash

from test_m12_canonical_physical_mechanism import _mechanism


def _fixture(tmp_path):
    manager = StateManager(tmp_path)
    base = DesignState(id="PRJ-CAD", revision=1)
    base_snapshot = manager.create_project("PRJ-CAD", base)
    source_store = ArtifactStore(tmp_path, project_id="PRJ-CAD", run_id="SOURCE")
    source = source_store.publish(
        "ART-shaft",
        ArtifactType.STEP,
        "shaft.step",
        b"trusted-source-N",
        "freecad",
        "1.1.3",
        base_snapshot.revision,
        base_snapshot.state_hash,
    )
    original = _mechanism()
    source_spec = type(original.component_specifications[0]).model_validate(
        original.component_specifications[0].model_dump(mode="python")
        | {
            "geometry_source": original.component_specifications[0].geometry_source.model_copy(
                update={"artifact_hash": source.sha256, "reference_hash": "pending"}
            ),
            "specification_hash": "pending",
        }
    )
    source_component = original.components[0].model_copy(
        update={"specification_hash": source_spec.specification_hash, "component_hash": "pending"}
    )
    choices = tuple(original.accepted_design_choices) + tuple(
        CanonicalAcceptedDesignChoice(
            key=f"mount-1.geometry.{key}",
            value=value,
            origin="explicit_policy_assumption",
            provenance="test:canonical-cad",
        )
        for key, value in (
            ("length_mm", 40.0),
            ("width_mm", 30.0),
            ("thickness_mm", 5.0),
        )
    )
    mechanism = CanonicalPhysicalMechanism.model_validate(
        original.model_dump(mode="python")
        | {
            "component_specifications": (source_spec, *original.component_specifications[1:]),
            "components": (source_component, *original.components[1:]),
            "accepted_design_choices": choices,
            "mechanism_hash": "pending",
        }
    )
    promoted = base.model_copy(update={"physical_mechanisms": [mechanism]})
    snapshot = manager.create_revision("PRJ-CAD", promoted)
    reconstruction = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id=project_id, run_id="lookup")
        ),
    ).reconstruct("PRJ-CAD", snapshot.revision, snapshot.state_hash, mechanism.id)
    resolver = ProjectArtifactResolver(
        ArtifactStore(tmp_path, project_id="PRJ-CAD", run_id="lookup")
    )
    return manager, source, mechanism, snapshot, reconstruction, resolver


def test_canonical_cad_rebinds_cross_revision_source_and_generates_fresh_identity(tmp_path):
    _, source, mechanism, snapshot, reconstruction, resolver = _fixture(tmp_path)

    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)

    assert isinstance(realization, CanonicalCadRealization)
    assert realization.project_id == "PRJ-CAD"
    assert realization.revision == snapshot.revision
    assert realization.state_hash == snapshot.state_hash
    assert realization.mechanism_hash == mechanism.mechanism_hash
    assert realization.selected_source_artifact_ids == (source.artifact_id,)
    assert realization.selected_source_content_identities == (source.sha256,)
    assert realization.selected_source_provenance[0].bound_revision == 1
    assert realization.selected_source_provenance[0].bound_state_hash == source.bound_state_hash
    assert realization.assembly.imported_components[0].source_revision == 1
    assert realization.assembly.imported_components[0].source_state_hash == source.bound_state_hash
    assert realization.assembly.instances[0].instance_id.startswith("canonical-")
    assert realization.assembly.instances[0].instance_id != "cad_mount"
    assert realization.realization_hash.startswith("sha256:")


def test_canonical_bounded_geometry_uses_canonical_choices_not_candidate_cad(tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)

    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)

    mount = next(
        mapping for mapping in realization.mappings if mapping.physical_instance_id == "mount-1"
    )
    assert mount.fidelity.value == "declared_bounded_collision_representation"
    assert realization.assembly.parts[0].part_id == mount.cad_instance_id
    base = realization.assembly.parts[0].operations[0]
    assert (base.length_mm, base.width_mm, base.thickness_mm) == (40.0, 30.0, 5.0)


def test_canonical_cad_rejects_tampered_or_foreign_selected_source(tmp_path):
    _, source, _, _, reconstruction, resolver = _fixture(tmp_path)
    tampered = reconstruction.model_copy(
        update={
            "trusted_source_references": (
                TrustedSourceArtifact.model_validate(
                    source.model_dump(mode="json")
                    | {
                        "run_id": "FOREIGN",
                        "sha256": "sha256:" + "f" * 64,
                    }
                ),
            )
        }
    )
    with pytest.raises((ValueError, ValidationError)):
        CanonicalPhysicalCadCompiler(resolver).realize(tampered)


def test_canonical_cad_realization_is_frozen_and_strict(tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)
    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)

    with pytest.raises((TypeError, ValidationError)):
        realization.revision = 99
    with pytest.raises(ValidationError, match="extra"):
        CanonicalCadRealization.model_validate(
            realization.model_dump(mode="json") | {"candidate": {}}
        )


def test_canonical_realization_rejects_cross_mapped_trusted_source(tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)
    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)
    other = ArtifactStore(tmp_path, project_id="PRJ-CAD", run_id="OTHER").publish(
        "ART-other",
        ArtifactType.STEP,
        "other.step",
        b"different-source",
        "freecad",
        "1.1.3",
        1,
        realization.selected_source_provenance[0].bound_state_hash,
    )
    imported = ImportedCadComponent(
        component_id=realization.assembly.imported_components[0].component_id,
        artifact_id=other.artifact_id,
        artifact_hash=other.sha256,
        source_revision=other.bound_revision,
        source_state_hash=other.bound_state_hash,
    )
    assembly = realization.assembly.model_copy(
        update={"imported_components": (imported,)}
    )
    mapping = realization.mappings[0].model_copy(
        update={
            "source_geometry_identity": other.sha256,
            "representation_identity": imported_component_hash(imported),
            # Leave the declared geometry artifact bound to the original source.
            "mapping_hash": "pending",
        }
    )
    payload = realization.model_dump(mode="json")
    payload.update(
        mappings=(
            mapping.model_dump(mode="json"),
            *(item.model_dump(mode="json") for item in realization.mappings[1:]),
        ),
        assembly=assembly.model_dump(mode="json"),
        assembly_hash=assembly_hash(assembly),
        realization_hash="pending",
    )

    with pytest.raises((CanonicalCadIntegrityError, ValidationError), match="source|artifact"):
        CanonicalCadRealization.model_validate(payload)


def test_validated_canonical_copy_rejects_nested_assembly_mutation(tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)
    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)

    realization.assembly.parts[0].operations[0].length_mm += 1.0

    with pytest.raises(CanonicalCadIntegrityError, match="assembly hash"):
        realization.validated_canonical_copy()


def test_validated_canonical_copy_is_a_defensive_complete_copy(tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)
    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)

    copied = realization.validated_canonical_copy()

    assert copied == realization
    assert copied is not realization
    assert copied.assembly is not realization.assembly
    assert copied.validated_canonical_assembly == realization.assembly


def test_validated_canonical_copy_rejects_stale_realization_hash(tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)
    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)

    realization.assembly.assembly_id += "-tampered"
    tampered = realization.model_copy(
        update={"assembly_hash": assembly_hash(realization.assembly)}
    )

    with pytest.raises(CanonicalCadIntegrityError, match="realization hash"):
        tampered.validated_canonical_copy()


def test_canonical_cad_rejects_placement_reference_owned_by_other_component(tmp_path):
    manager, _, mechanism, snapshot, _, resolver = _fixture(tmp_path)
    mount = mechanism.components[1].model_copy(
        update={"placement_id": mechanism.components[0].placement_id, "component_hash": "pending"}
    )
    invalid_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {"components": (mechanism.components[0], mount), "mechanism_hash": "pending"}
    )
    invalid_state = manager.load_revision("PRJ-CAD", snapshot.revision).model_copy(
        update={"physical_mechanisms": [invalid_mechanism]}
    )
    invalid_snapshot = manager.create_revision("PRJ-CAD", invalid_state)
    reconstruction = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id=project_id, run_id="lookup")
        ),
    ).reconstruct(
        "PRJ-CAD", invalid_snapshot.revision, invalid_snapshot.state_hash, mechanism.id
    )

    with pytest.raises(CanonicalCadIntegrityError, match="placement"):
        CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)


def test_canonical_cad_rejects_unowned_placement_without_component_declaration(tmp_path):
    manager, _, mechanism, snapshot, _, resolver = _fixture(tmp_path)
    unowned = mechanism.placements[0].model_copy(
        update={
            "placement_id": "placement-mount-unowned",
            "instance_id": "mount-1",
            "placement_hash": "pending",
        }
    )
    invalid_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {"placements": (*mechanism.placements, unowned), "mechanism_hash": "pending"}
    )
    invalid_state = manager.load_revision("PRJ-CAD", snapshot.revision).model_copy(
        update={"physical_mechanisms": [invalid_mechanism]}
    )
    invalid_snapshot = manager.create_revision("PRJ-CAD", invalid_state)
    reconstruction = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id=project_id, run_id="lookup")
        ),
    ).reconstruct(
        "PRJ-CAD", invalid_snapshot.revision, invalid_snapshot.state_hash, mechanism.id
    )

    with pytest.raises(CanonicalCadIntegrityError, match="placement"):
        CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)


def test_canonical_cad_rejects_duplicate_placements_for_one_component(tmp_path):
    manager, _, mechanism, snapshot, _, resolver = _fixture(tmp_path)
    duplicate = mechanism.placements[0].model_copy(
        update={"placement_id": "placement-shaft-duplicate", "placement_hash": "pending"}
    )
    invalid_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "placements": (*mechanism.placements, duplicate),
            "mechanism_hash": "pending",
        }
    )
    invalid_state = manager.load_revision("PRJ-CAD", snapshot.revision).model_copy(
        update={"physical_mechanisms": [invalid_mechanism]}
    )
    invalid_snapshot = manager.create_revision("PRJ-CAD", invalid_state)
    reconstruction = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id=project_id, run_id="lookup")
        ),
    ).reconstruct(
        "PRJ-CAD", invalid_snapshot.revision, invalid_snapshot.state_hash, mechanism.id
    )

    with pytest.raises(CanonicalCadIntegrityError, match="placement"):
        CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)


def test_same_artifact_id_with_changed_bytes_fails_closed(tmp_path):
    _, source, _, _, reconstruction, resolver = _fixture(tmp_path)
    path = tmp_path / source.relative_path
    path.write_bytes(b"changed-bytes")

    with pytest.raises(ValueError, match="source|artifact|integrity"):
        CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)


def test_non_selected_old_source_is_not_accepted_as_canonical_input(tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)
    store = ArtifactStore(tmp_path, project_id="PRJ-CAD", run_id="OTHER-SOURCE")
    other = store.publish(
        "ART-other",
        ArtifactType.STEP,
        "other.step",
        b"non-selected-old-source",
        "freecad",
        "1.1.3",
        1,
        reconstruction.trusted_source_references[0].bound_state_hash,
    )
    forged = reconstruction.model_copy(
        update={
            "trusted_source_references": (
                *reconstruction.trusted_source_references,
                TrustedSourceArtifact.from_artifact(other),
            )
        }
    )

    with pytest.raises(ValueError, match="trusted source|canonical"):
        CanonicalPhysicalCadCompiler(resolver).realize(forged)


def test_canonical_compiler_does_not_invoke_candidate_cad(monkeypatch, tmp_path):
    _, _, _, _, reconstruction, resolver = _fixture(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("candidate CAD must not be called")

    monkeypatch.setattr(
        "mechcad_harness.candidates.cad_realization.CandidateCadRealizationService.realize",
        fail_if_called,
    )

    realization = CanonicalPhysicalCadCompiler(resolver).realize(reconstruction)

    assert realization.compiler_identity == "canonical-physical-cad-compiler"
