from __future__ import annotations

import json
import sys
from pathlib import Path

from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
from mechcad_harness.candidates.canonical_mechanism import (
    TrustedSourceArtifact,
    _projection_from_mechanism,
    CanonicalMechanismReconstruction,
)
from mechcad_harness.candidates.multi_joint_m10_bridge import compile_canonical
from mechcad_harness.candidates.multi_joint_m10_bridge import (
    compare_candidate_canonical_multi_joint_semantics,
)
from mechcad_harness.artifacts import ArtifactStore


def test_canonical_replay_acceptance_has_no_candidate_object_authority(tmp_path):
    unit_path = str(Path(__file__).parents[1] / "unit")
    if unit_path not in sys.path:
        sys.path.insert(0, unit_path)
    from test_m13_3_fresh_canonical_bridge import _canonical_reconstruction

    reconstruction = _canonical_reconstruction(tmp_path)
    mechanism = reconstruction.canonical_mechanism
    store = ArtifactStore(
        tmp_path, project_id=reconstruction.project_id, run_id="m13-3-acceptance"
    )
    fresh = CanonicalPhysicalCadCompiler(store).realize(reconstruction)
    bridge = compile_canonical(reconstruction, fresh)
    payload = json.dumps(mechanism.model_dump(mode="json"), sort_keys=True)

    assert bridge.model.model_id.startswith("physical-to-m10-v2-model@1:")
    assert len(mechanism.multi_joint_verification_obligations) == 1
    assert "CandidateMultiJoint" not in payload
    assert "candidate_scope" not in payload


def test_candidate_chain_replays_as_fresh_canonical_m10(tmp_path):
    unit_path = str(Path(__file__).parents[1] / "unit")
    if unit_path not in sys.path:
        sys.path.insert(0, unit_path)
    from test_m13_3_candidate_m10_production import _application
    from test_m13_3_promotion import _promotion_chain

    candidate, candidate_cad, candidate_bridge, multi_request, _, promotion_request, _, compiler = _promotion_chain(
        tmp_path
    )
    compilation = compiler.compile_multi_joint(
        compiler.state_manager.load_current_state(promotion_request.project_id),
        promotion_request,
    )
    mechanism = compilation.canonical_mechanism
    store = ArtifactStore(
        tmp_path, project_id=promotion_request.project_id, run_id="m13-3-fresh-m10"
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
    reconstruction = CanonicalMechanismReconstruction(
        project_id=promotion_request.project_id,
        revision=promotion_request.source_revision,
        state_hash=promotion_request.source_state_hash,
        canonical_mechanism=mechanism,
        trusted_source_references=trusted_sources,
        normalized_projection_hash=_projection_from_mechanism(mechanism).projection_hash,
    )
    fresh_cad = CanonicalPhysicalCadCompiler(store).realize(reconstruction)
    canonical_bridge = compile_canonical(reconstruction, fresh_cad)
    equivalence = compare_candidate_canonical_multi_joint_semantics(
        candidate_bridge,
        canonical_bridge,
        candidate_cad=candidate_cad,
        canonical_cad=fresh_cad,
        candidate_pair_bindings=(
            candidate.realization.physical_pair_classification_bindings
        ),
        canonical_pair_bindings=(
            reconstruction.canonical_mechanism.physical_pair_classification_bindings
        ),
        instance_mapping={
            candidate_mapping.physical_instance_id: canonical_mapping.physical_instance_id
            for candidate_mapping in candidate_cad.mappings
            for canonical_mapping in fresh_cad.mappings
            if candidate_mapping.cad_instance_id.endswith(
                candidate_mapping.physical_instance_id
            )
            and canonical_mapping.physical_instance_id.endswith(
                candidate_mapping.physical_instance_id
            )
        },
        candidate_configurations=multi_request.scope.configuration_set.configurations,
        canonical_configurations=(
            reconstruction.canonical_mechanism.multi_joint_verification_obligations[0]
            .configuration_set.configurations
        ),
        candidate_volume_tolerance_mm3=multi_request.scope.volume_tolerance_mm3,
        canonical_volume_tolerance_mm3=(
            reconstruction.canonical_mechanism.multi_joint_verification_obligations[0]
            .volume_tolerance_mm3
        ),
        candidate_distance_tolerance_mm=multi_request.scope.distance_tolerance_mm,
        canonical_distance_tolerance_mm=(
            reconstruction.canonical_mechanism.multi_joint_verification_obligations[0]
            .distance_tolerance_mm
        ),
        candidate_placement_derivations=multi_request.placement_derivations,
        canonical_placement_derivations=(
            reconstruction.canonical_mechanism.generated_placement_derivations
        ),
    )
    assert equivalence.equivalent, equivalence.differences

    application = _application(
        tmp_path,
        [],
        project_id=reconstruction.project_id,
        create_state=False,
    )
    verification = application.canonical_multi_joint_m10_verification_service.execute(
        reconstruction, fresh_cad
    )
    assert verification.request.request_hash != multi_request.m10_v2_request_hash
    assert verification.result.request_hash == verification.request.request_hash
    assert application.get_multi_joint_collision_sweep_evidence(
        verification.result.result_hash
    ) is not None
