from __future__ import annotations

import pytest

from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
from mechcad_harness.candidates.canonical_cad import CanonicalCadRealization
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    TrustedSourceArtifact,
    _projection_from_mechanism,
)
from mechcad_harness.candidates.multi_joint_m10_bridge import compile_canonical
from mechcad_harness.models import CanonicalPhysicalMechanism
from test_m13_3_promotion import _promotion_chain


def _canonical_reconstruction(tmp_path, *, incomplete_body: bool = False):
    candidate, _, _, _, _, request, _, compiler = _promotion_chain(tmp_path)
    compilation = compiler.compile_multi_joint(
        compiler.state_manager.load_current_state(request.project_id), request
    )
    mechanism = compilation.canonical_mechanism
    if incomplete_body:
        body = max(
            mechanism.physical_rigid_body_bindings,
            key=lambda item: len(item.member_physical_instance_ids),
        )
        removed_member = next(
            member
            for member in body.member_physical_instance_ids
            if member != body.reference_physical_instance_id
        )
        incomplete = body.model_copy(
            update={
                "member_physical_instance_ids": tuple(
                    member
                    for member in body.member_physical_instance_ids
                    if member != removed_member
                ),
                "binding_hash": "pending",
            }
        )
        mechanism = CanonicalPhysicalMechanism.model_validate(
            mechanism.model_dump(mode="python")
            | {
                "physical_rigid_body_bindings": tuple(
                    incomplete if item.physical_body_id == body.physical_body_id else item
                    for item in mechanism.physical_rigid_body_bindings
                ),
                "mechanism_hash": "pending",
            }
        )

    store = ArtifactStore(
        tmp_path, project_id=request.project_id, run_id="task-15-test-lookup"
    )
    trusted_sources = tuple(
        TrustedSourceArtifact.from_artifact(
            store.read_verified_in_project(
                specification.geometry_source.artifact_id,
                expected_hash=specification.geometry_source.artifact_hash,
            )[0]
        )
        for specification in mechanism.component_specifications
        if specification.geometry_source is not None
    )
    return CanonicalMechanismReconstruction(
        project_id=request.project_id,
        revision=request.source_revision,
        state_hash=request.source_state_hash,
        canonical_mechanism=mechanism,
        trusted_source_references=trusted_sources,
        normalized_projection_hash=_projection_from_mechanism(mechanism).projection_hash,
    )


def test_canonical_bridge_requires_canonical_reconstruction_not_bare_mechanism():
    with pytest.raises(ValueError, match="canonical bridge reconstruction"):
        compile_canonical(
            CanonicalPhysicalMechanism.model_construct(),
            CanonicalCadRealization.model_construct(),
        )


def test_canonical_bridge_requires_fresh_canonical_cad_with_reconstruction():
    with pytest.raises(ValueError, match="canonical bridge CAD"):
        compile_canonical(
            CanonicalMechanismReconstruction.model_construct(),
            object(),
        )


def test_fresh_canonical_cad_rejects_an_unowned_physical_member(tmp_path):
    reconstruction = _canonical_reconstruction(tmp_path, incomplete_body=True)
    compiler = CanonicalPhysicalCadCompiler(
        ArtifactStore(
            tmp_path,
            project_id=reconstruction.project_id,
            run_id="task-15-cad-lookup",
        )
    )

    with pytest.raises(ValueError, match="body|CAD|universe|member"):
        compiler.realize(reconstruction)
