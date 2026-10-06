from __future__ import annotations

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.candidates import (
    CandidateCadIntegrityError,
    CandidateCadInstanceMappingV2,
    CandidateCadRealizationV2,
    CandidateCadRealizationService,
    CandidateCadStageOutcomeV2,
    CandidateCadStageReason,
    CandidateCadStageStatus,
    SemanticSourceGeometryIdentity,
    candidate_realization_hash_v2,
    candidate_cad_stage_outcome_hash_v2,
    semantic_assembly_hash,
    trusted_representation_identity,
)
from mechcad_harness.candidates.provenance_artifacts import (
    CandidateProvenanceArtifactService,
)
from mechcad_harness.imported_component import ImportedCadComponent
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_candidate_cad_request_v3 import _INSTANCE_SLOTS, _mapping_at2, _request_at3
from test_candidate_trusted_semantic_verification import (
    _at2_setup,
    _P2_STEP_VARIANTS,
    _evaluation_candidate,
)


CONTENT_A = step_content_identity_v1(_P2_STEP_VARIANTS["A"]).content_hash


def _assembly(candidate, mappings):
    from hashlib import sha256

    raw_hash = "sha256:" + sha256(_P2_STEP_VARIANTS["A"]).hexdigest()
    binding_revision = candidate.source_binding.source_revision
    binding_state = candidate.source_binding.source_state_hash
    imported = []
    instances = []
    slot_by_instance = dict(_INSTANCE_SLOTS)
    for mapping in sorted(mappings, key=lambda item: item.physical_instance_id):
        slot = slot_by_instance[mapping.physical_instance_id]
        imported.append(
            ImportedCadComponent(
                component_id=mapping.cad_instance_id,
                artifact_id=f"ART-P2-{slot}-A",
                artifact_hash=raw_hash,
                source_revision=binding_revision,
                source_state_hash=binding_state,
            )
        )
        instances.append(
            CadComponentInstance(
                instance_id=mapping.cad_instance_id,
                part_id=mapping.cad_instance_id,
                placement=mapping.placement,
            )
        )
    return CadAssemblyProgram(
        assembly_id="candidate-assembly-at2",
        imported_components=tuple(
            sorted(imported, key=lambda component: component.component_id)
        ),
        instances=tuple(sorted(instances, key=lambda item: item.instance_id)),
    )


def _realization_at2(candidate, request):
    from hashlib import sha256

    raw_hash = "sha256:" + sha256(_P2_STEP_VARIANTS["A"]).hexdigest()
    assembly = _assembly(candidate, request.mappings)
    ordered = tuple(sorted(request.mappings, key=lambda item: item.physical_instance_id))
    contents = tuple(
        dict.fromkeys(
            mapping.source_geometry_identity.content_identity for mapping in ordered
        )
    )
    return CandidateCadRealizationV2(
        candidate_hash=request.candidate_hash,
        request_hash=request.request_hash,
        mappings=ordered,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        representation_identities=tuple(
            mapping.representation_identity for mapping in ordered
        ),
        semantic_placement_derivations_hash=request.semantic_placement_derivations_hash,
        verified_source_content_identities=contents,
        verified_source_artifact_hashes=(raw_hash,),
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        provider_identity="fixture-provider",
    )


def test_realization_at2_and_outcome_at2_have_exact_declared_fields():
    assert set(CandidateCadRealizationV2.model_fields) == {
        "schema_version",
        "candidate_hash",
        "request_hash",
        "mappings",
        "assembly",
        "assembly_hash",
        "representation_identities",
        "semantic_placement_derivations_hash",
        "verified_source_content_identities",
        "verified_source_artifact_hashes",
        "compiler_identity",
        "compiler_version",
        "provider_identity",
        "realization_hash",
    }
    assert set(CandidateCadStageOutcomeV2.model_fields) == {
        "schema_version",
        "status",
        "realization",
        "realization_hash",
        "reasons",
        "outcome_hash",
    }


def test_realization_service_dispatches_request_at3_to_v2_stage(tmp_path):
    _, manager, _, _, synthesis_request, synthesis_policy, candidate = _at2_setup(
        tmp_path
    )
    mappings = tuple(
        _mapping_at2(candidate.candidate_hash, instance_id, slot)
        for instance_id, slot in _INSTANCE_SLOTS
    )
    request = _request_at3(
        candidate,
        synthesis_request.semantic_source_binding_hash,
        mappings=mappings,
    )

    service = CandidateCadRealizationService(tmp_path, "PRJ-M12", manager)
    outcome = service.realize(candidate, synthesis_request, synthesis_policy, request)

    assert type(outcome) is CandidateCadStageOutcomeV2
    assert outcome.status is CandidateCadStageStatus.SUCCESS, outcome.reasons
    assert type(outcome.realization) is CandidateCadRealizationV2
    assert outcome.realization.request_hash == request.request_hash
    assert outcome.realization.verified_source_content_identities == (CONTENT_A,)
    expected_raw_hashes_by_artifact = {
        specification.geometry_source.artifact_id: specification.geometry_source.artifact_hash
        for specification in candidate.component_specifications
        if specification.geometry_source is not None
    }
    assert sorted(outcome.realization.verified_source_artifact_hashes) == sorted(
        expected_raw_hashes_by_artifact.values()
    )
    assert CONTENT_A not in outcome.realization.verified_source_artifact_hashes
    service.validate_realization(candidate, request, outcome.realization)

    provenance = CandidateProvenanceArtifactService(
        tmp_path, "PRJ-M12", manager
    )
    published = provenance.publish_candidate_cad(
        candidate,
        synthesis_request,
        synthesis_policy,
        request,
        outcome.realization,
        source_step_artifacts=None,
    )
    resolved = provenance.resolve_candidate_cad(published.artifact.artifact_id)
    assert resolved.payload.realization == outcome.realization


def test_realization_service_does_not_accept_raw_sha_as_semantic_content(tmp_path):
    _, manager, _, _, synthesis_request, synthesis_policy, candidate = _at2_setup(
        tmp_path
    )
    mappings = tuple(
        _mapping_at2(candidate.candidate_hash, instance_id, slot)
        for instance_id, slot in _INSTANCE_SLOTS
    )
    request = _request_at3(
        candidate,
        synthesis_request.semantic_source_binding_hash,
        mappings=mappings,
    )
    mapping = request.mappings[0]
    component = next(
        item
        for item in candidate.realization.components
        if item.instance_id == mapping.physical_instance_id
    )
    specification = next(
        item
        for item in candidate.component_specifications
        if item.specification_hash == component.specification_hash
    )
    source = specification.geometry_source
    assert source is not None
    assert source.artifact_hash != source.content_identity
    forged_mapping = CandidateCadInstanceMappingV2.model_validate(
        mapping.model_dump(mode="json")
        | {
            "source_geometry_identity": SemanticSourceGeometryIdentity(
                content_identity=source.artifact_hash
            ).model_dump(mode="json"),
            "geometry_definition_identities": (source.artifact_hash,),
            "representation_identity": trusted_representation_identity(
                slot=mapping.cad_instance_id,
                content_identity=source.artifact_hash,
            ),
            "mapping_hash": "pending",
        }
    )
    forged_request = _request_at3(
        candidate,
        synthesis_request.semantic_source_binding_hash,
        mappings=(forged_mapping, *request.mappings[1:]),
    )

    with pytest.raises(CandidateCadIntegrityError, match="semantic source"):
        CandidateCadRealizationService(
            tmp_path, "PRJ-M12", manager
        ).realize(candidate, synthesis_request, synthesis_policy, forged_request)


def test_request_at3_rejects_candidate_at1_without_legacy_downgrade(tmp_path):
    state, manager, _, _, synthesis_request, synthesis_policy, candidate = _at2_setup(
        tmp_path
    )
    candidate_at1, request_at1, policy_at1 = _evaluation_candidate(state)
    request_at3 = _request_at3(
        candidate, synthesis_request.semantic_source_binding_hash
    )

    with pytest.raises(CandidateCadIntegrityError, match="requires candidate@2"):
        CandidateCadRealizationService(
            tmp_path, "PRJ-M12", manager
        ).realize(candidate_at1, request_at1, policy_at1, request_at3)


def test_realization_at2_binds_request_and_recomputes_hash(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    realization = _realization_at2(candidate, request)

    assert realization.schema_version == "candidate-cad-realization@2"
    assert realization.semantic_placement_derivations_hash == (
        request.semantic_placement_derivations_hash
    )
    assert realization.realization_hash == candidate_realization_hash_v2(realization)
    wire = realization.model_dump(mode="json")
    assert "representation_policy_version" not in wire
    outcome = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.SUCCESS, realization=realization
    )
    assert outcome.realization_hash == realization.realization_hash
    assert outcome.outcome_hash == candidate_cad_stage_outcome_hash_v2(outcome)


def test_realization_at2_ignores_provider_and_raw_assembly_naming(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    baseline = _realization_at2(candidate, request)
    renamed_provider = baseline.model_copy(
        update={"provider_identity": "other-provider"}
    )
    renamed_assembly = baseline.assembly.model_copy(
        update={"assembly_id": "renamed-assembly"}
    )
    renamed = CandidateCadRealizationV2.model_validate(
        baseline.model_dump(mode="json")
        | {
            "provider_identity": "other-provider",
            "assembly": renamed_assembly.model_dump(mode="json"),
            "assembly_hash": assembly_hash(renamed_assembly),
            "realization_hash": "pending",
        }
    )

    assert renamed_provider.realization_hash == baseline.realization_hash
    assert renamed.realization_hash == baseline.realization_hash


def test_realization_at2_rejects_a_raw_hash_as_semantic_identity(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    realization = _realization_at2(candidate, request)

    with pytest.raises(ValueError, match="hash mismatch"):
        CandidateCadRealizationV2.model_validate(
            realization.model_dump(mode="json")
            | {
                "realization_hash": assembly_hash(realization.assembly),
            }
        )


def test_realization_at2_is_sensitive_to_semantic_changes(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    baseline = _realization_at2(candidate, request)
    moved_mapping = request.mappings[0].model_copy(
        update={
            "placement": CadRigidTransform(x_mm=999.0),
            "placement_origin": request.mappings[0].placement_origin.model_copy(
                update={"transform": CadRigidTransform(x_mm=999.0), "origin_hash": "pending"}
            ),
            "mapping_hash": "pending",
        }
    )
    moved_mappings = tuple(
        sorted(
            (moved_mapping, *request.mappings[1:]),
            key=lambda item: item.physical_instance_id,
        )
    )
    moved_realization = CandidateCadRealizationV2.model_validate(
        baseline.model_dump(mode="json")
        | {
            "mappings": [item.model_dump(mode="json") for item in moved_mappings],
            "assembly": _assembly(candidate, moved_mappings).model_dump(mode="json"),
            "assembly_hash": assembly_hash(_assembly(candidate, moved_mappings)),
            "representation_identities": [
                item.representation_identity for item in moved_mappings
            ],
            "realization_hash": "pending",
        }
    )

    assert moved_realization.realization_hash != baseline.realization_hash


def test_outcome_at2_status_matrix_is_exact(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    realization = _realization_at2(candidate, request)

    success = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.SUCCESS, realization=realization
    )
    assert success.reasons == ()
    unresolved = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.UNRESOLVED,
        reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
    )
    assert unresolved.realization is None
    not_reached = CandidateCadStageOutcomeV2(
        status=CandidateCadStageStatus.NOT_REACHED,
        reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,),
    )
    assert not_reached.realization is None

    with pytest.raises(ValueError, match="successful|reason"):
        CandidateCadStageOutcomeV2(
            status=CandidateCadStageStatus.SUCCESS,
            realization=realization,
            reasons=(CandidateCadStageReason.GEOMETRY_UNAVAILABLE,),
        )
    with pytest.raises(ValueError, match="prior stage|reason"):
        CandidateCadStageOutcomeV2(
            status=CandidateCadStageStatus.UNRESOLVED,
            reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,),
        )
    with pytest.raises(ValueError, match="cannot carry a realization"):
        CandidateCadStageOutcomeV2(
            status=CandidateCadStageStatus.NOT_REACHED,
            realization=realization,
            reasons=(CandidateCadStageReason.PRIOR_STAGE_FAILED,),
        )


def test_outcome_at2_rejects_mixed_version_nesting(tmp_path):
    from mechcad_harness.candidates import (
        CandidateCadRealization,
        CandidateCadStageOutcome,
    )

    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    realization = _realization_at2(candidate, request)

    with pytest.raises(ValueError, match="realization|version|valid dictionary|extra"):
        CandidateCadStageOutcomeV2(
            status=CandidateCadStageStatus.SUCCESS,
            realization=CandidateCadRealization.model_validate(
                realization.model_dump(mode="json")
                | {
                    "schema_version": "candidate-cad-realization@1",
                    "placement_derivations_hash": None,
                    "realization_hash": "pending",
                }
            ),
        )
    with pytest.raises(ValueError, match="realization|version|valid dictionary"):
        CandidateCadStageOutcome(
            status=CandidateCadStageStatus.SUCCESS, realization=realization
        )


def test_verified_source_content_binding_is_exact(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    baseline = _realization_at2(candidate, request)

    assert baseline.verified_source_content_identities == (CONTENT_A,)
    with pytest.raises(ValueError, match="verified source content|match"):
        CandidateCadRealizationV2.model_validate(
            baseline.model_dump(mode="json")
            | {
                "verified_source_content_identities": ("sha256:" + "f" * 64,),
                "realization_hash": "pending",
            }
        )


def test_semantic_assembly_hash_orders_and_excludes_raw(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    realization = _realization_at2(candidate, request)
    digest = semantic_assembly_hash(realization.assembly, realization.mappings)

    assert digest.startswith("sha256:")
    renamed = realization.assembly.model_copy(update={"assembly_id": "other"})
    assert semantic_assembly_hash(renamed, realization.mappings) == digest
