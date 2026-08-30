from __future__ import annotations

import pytest
from pydantic import ValidationError

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import (
    ProjectArtifactResolver,
    PromotableMechanismProjection,
    TrustedSourceArtifact,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    CanonicalPhysicalMechanismCompiler,
    normalized_projection,
)
from mechcad_harness.models import (
    CanonicalComponentPropertyAuthority,
    CanonicalComponentSpecification,
    CanonicalGeometrySourceReference,
    DesignState,
)
from mechcad_harness.state import StateManager, state_hash

from test_m12_canonical_physical_mechanism import _mechanism


def _mechanism_with_source(source_hash: str):
    mechanism = _mechanism()
    original_specification = mechanism.component_specifications[0]
    source = CanonicalGeometrySourceReference.model_validate(
        original_specification.geometry_source.model_dump(mode="json")
        | {"artifact_hash": source_hash, "reference_hash": "pending"}
    )
    specification = CanonicalComponentSpecification.model_validate(
        original_specification.model_dump(mode="json")
        | {
            "geometry_source": source,
            "specification_hash": "pending",
        }
    )
    component = type(mechanism.components[0]).model_validate(
        mechanism.components[0].model_dump(mode="json")
        | {
            "specification_hash": specification.specification_hash,
            "component_hash": "pending",
        }
    )
    return type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {
            "component_specifications": (
                specification,
                *mechanism.component_specifications[1:],
            ),
            "components": (component, *mechanism.components[1:]),
            "mechanism_hash": "pending",
        }
    )


def _fixture(tmp_path):
    manager = StateManager(tmp_path)
    base = DesignState(id="PRJ-RECON", revision=1)
    base_snapshot = manager.create_project("PRJ-RECON", base)
    source_store = ArtifactStore(tmp_path, project_id="PRJ-RECON", run_id="SOURCE")
    source = source_store.publish(
        "ART-shaft",
        ArtifactType.STEP,
        "shaft.step",
        b"trusted-step",
        "freecad",
        "1.1.3",
        base_snapshot.revision,
        base_snapshot.state_hash,
    )
    mechanism = _mechanism_with_source(source.sha256)
    promoted = base.model_copy(update={"physical_mechanisms": [mechanism]})
    snapshot = manager.create_revision("PRJ-RECON", promoted)
    return manager, source, mechanism, snapshot


def _resolver(tmp_path):
    return ProjectArtifactResolver(
        ArtifactStore(tmp_path, project_id="PRJ-RECON", run_id="lookup")
    )


def _frozen_decision_projection(mechanism):
    return PromotableMechanismProjection(
        canonical_target_mechanism_id=mechanism.id,
        canonical_instance_ids=tuple(
            component.instance_id for component in mechanism.components
        ),
        component_specifications=mechanism.component_specifications,
        components=mechanism.components,
        accepted_design_choices=mechanism.accepted_design_choices,
        placements=mechanism.placements,
        connections=mechanism.connections,
        joint_bindings=mechanism.joint_bindings,
        m10_obligations=mechanism.m10_obligations,
        mapping_identities=tuple(
            component.instance_id for component in mechanism.components
        ),
    )


def test_reconstructs_canonical_state_without_transient_candidate_objects(tmp_path):
    manager, source, mechanism, snapshot = _fixture(tmp_path)
    compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: _resolver(tmp_path),
    )

    reconstruction = compiler.reconstruct(
        "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
    )

    assert isinstance(reconstruction, CanonicalMechanismReconstruction)
    assert reconstruction.canonical_mechanism == mechanism
    assert reconstruction.normalized_projection_hash.startswith("sha256:")
    assert reconstruction.trusted_source_references[0].artifact_id == source.artifact_id
    assert reconstruction.trusted_source_references[0].run_id == "SOURCE"
    assert reconstruction.trusted_source_references[0].bound_revision == 1
    assert reconstruction.trusted_source_references[0].bound_state_hash != snapshot.state_hash

    projection = normalized_projection(reconstruction)
    assert isinstance(projection, PromotableMechanismProjection)
    assert projection.projection_hash == reconstruction.normalized_projection_hash
    assert "run_id" not in projection.model_dump(mode="json")


def test_reconstruction_projection_matches_frozen_decision_projection(tmp_path):
    manager, _, mechanism, snapshot = _fixture(tmp_path)
    compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: _resolver(tmp_path),
    )
    reconstruction = compiler.reconstruct(
        "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
    )
    frozen = _frozen_decision_projection(mechanism)

    reloaded = compiler.reconstruct(
        "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
    )
    assert normalized_projection(reloaded) == frozen
    assert normalized_projection(reloaded).projection_hash == frozen.projection_hash


def test_tampered_promoted_state_fact_breaks_frozen_projection_equivalence(tmp_path):
    manager, _, mechanism, snapshot = _fixture(tmp_path)
    compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: _resolver(tmp_path),
    )
    frozen_projection = _frozen_decision_projection(mechanism)

    property_value = type(
        mechanism.component_specifications[0].properties[0]
    ).model_validate(
        mechanism.component_specifications[0].properties[0].model_dump(mode="json")
        | {
            "authority": CanonicalComponentPropertyAuthority.MEASURED_LOCAL,
            "property_hash": "pending",
        }
    )
    specification = CanonicalComponentSpecification.model_validate(
        mechanism.component_specifications[0].model_dump(mode="json")
        | {
            "properties": (
                property_value,
                *mechanism.component_specifications[0].properties[1:],
            ),
            "specification_hash": "pending",
        }
    )
    component = type(mechanism.components[0]).model_validate(
        mechanism.components[0].model_dump(mode="json")
        | {
            "specification_hash": specification.specification_hash,
            "component_hash": "pending",
        }
    )
    tampered = type(mechanism).model_validate(
        mechanism.model_dump(mode="json")
        | {
            "component_specifications": (
                specification,
                *mechanism.component_specifications[1:],
            ),
            "components": (component, *mechanism.components[1:]),
            "mechanism_hash": "pending",
        }
    )
    tampered_state = manager.load_revision("PRJ-RECON", snapshot.revision).model_copy(
        update={"physical_mechanisms": [tampered]}
    )
    tampered_snapshot = manager.create_revision("PRJ-RECON", tampered_state)
    tampered_reconstruction = compiler.reconstruct(
        "PRJ-RECON",
        tampered_snapshot.revision,
        tampered_snapshot.state_hash,
        mechanism.id,
    )

    assert (
        normalized_projection(tampered_reconstruction).projection_hash
        != frozen_projection.projection_hash
    )


@pytest.mark.parametrize(
    "kwargs",
    (
        {"revision": 1},
        {"state_hash": "sha256:" + "f" * 64},
        {"mechanism_id": "missing"},
    ),
)
def test_reconstruction_rejects_wrong_canonical_binding(tmp_path, kwargs):
    manager, _, mechanism, snapshot = _fixture(tmp_path)
    compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: _resolver(tmp_path),
    )
    values = {
        "project_id": "PRJ-RECON",
        "revision": snapshot.revision,
        "state_hash": snapshot.state_hash,
        "mechanism_id": mechanism.id,
    }
    values.update(kwargs)
    with pytest.raises((ValueError, ValidationError)):
        compiler.reconstruct(**values)


def test_reconstruction_result_is_frozen_and_strict(tmp_path):
    manager, _, mechanism, snapshot = _fixture(tmp_path)
    compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: _resolver(tmp_path),
    )
    reconstruction = compiler.reconstruct(
        "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
    )

    with pytest.raises((TypeError, ValidationError)):
        reconstruction.canonical_mechanism = mechanism
    with pytest.raises(ValidationError, match="extra"):
        CanonicalMechanismReconstruction.model_validate(
            reconstruction.model_dump(mode="json") | {"candidate": {}}
        )

    with pytest.raises((TypeError, ValidationError)):
        reconstruction.trusted_source_references[0].run_id = "candidate-run"


def test_reconstruction_rejects_foreign_workspace_and_project_resolvers(tmp_path):
    manager, _, mechanism, snapshot = _fixture(tmp_path)
    foreign_workspace = tmp_path / "foreign"
    foreign_workspace.mkdir()

    foreign_compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(foreign_workspace, project_id=project_id, run_id="lookup")
        ),
    )
    with pytest.raises(ValueError, match="workspace"):
        foreign_compiler.reconstruct(
            "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
        )

    wrong_project_compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id="OTHER", run_id="lookup")
        ),
    )
    with pytest.raises(ValueError, match="project scope"):
        wrong_project_compiler.reconstruct(
            "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
        )


def test_reconstruction_requires_explicit_project_resolver_factory(tmp_path):
    manager, _, mechanism, snapshot = _fixture(tmp_path)

    raw_store_compiler = CanonicalPhysicalMechanismCompiler(
        manager,
        lambda project_id: ArtifactStore(
            tmp_path, project_id=project_id, run_id="lookup"
        ),
    )
    with pytest.raises(ValueError, match="ProjectArtifactResolver"):
        raw_store_compiler.reconstruct(
            "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
        )

    def run_scoped_factory(project_id, run_id):
        return ProjectArtifactResolver(
            ArtifactStore(tmp_path, project_id=project_id, run_id=run_id)
        )

    run_scoped_compiler = CanonicalPhysicalMechanismCompiler(
        manager, run_scoped_factory
    )
    with pytest.raises(ValueError, match="project_id only"):
        run_scoped_compiler.reconstruct(
            "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
        )


def test_reconstruction_model_requires_exact_trusted_source_snapshot_binding(
    tmp_path,
):
    manager, _, mechanism, snapshot = _fixture(tmp_path)
    compiler = CanonicalPhysicalMechanismCompiler(
        manager, lambda project_id: _resolver(tmp_path)
    )
    reconstruction = compiler.reconstruct(
        "PRJ-RECON", snapshot.revision, snapshot.state_hash, mechanism.id
    )

    with pytest.raises(ValueError, match="trusted source"):
        CanonicalMechanismReconstruction.model_validate(
            reconstruction.model_dump(mode="json")
            | {"trusted_source_references": ()}
        )

    tampered_source = reconstruction.model_dump(mode="json")
    tampered_source["trusted_source_references"][0]["sha256"] = (
        "sha256:" + "f" * 64
    )
    with pytest.raises(ValueError, match="trusted source"):
        CanonicalMechanismReconstruction.model_validate(tampered_source)

    assert isinstance(reconstruction.trusted_source_references[0], TrustedSourceArtifact)
