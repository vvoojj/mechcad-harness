from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import assembly_hash
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.candidates import (
    CandidatePublicationService,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalMechanismRealization,
)
from mechcad_harness.candidates.cad_realization import (
    CandidateCadInstanceMapping,
    CandidateCadRealizationRequest,
    CandidateGeometryFidelity,
    CandidatePlacementOrigin,
)
from mechcad_harness.candidates.models import CandidateSynthesisPolicy, CandidateSynthesisRequest
from mechcad_harness.imported_component import ImportedCadComponent, imported_component_hash
from mechcad_harness.state import StateManager, state_hash

from task6_provenance_fixtures import (
    StateBackedCurrentnessVerifier,
    SelectionCurrentnessVerifier,
    canonical_inputs,
    comparison_policy,
    comparison_request,
    make_binding,
    make_bound_m10_inputs,
    make_candidate_cad_fixture,
    make_candidate_for_specification,
    make_cad_service,
    make_evaluation_candidate,
    make_home_result,
    make_m10_request,
    make_m12_result,
    make_proof_result,
    make_scope,
    make_state,
)


def publish_candidate_cad(service, publication, request, realization, **kwargs):
    """Exercise the Task 2 boundary, which creates its own candidate snapshot."""
    manifest = json.loads(
        (service.state_manager.workspace / publication.artifact.relative_path).read_text(encoding="utf-8")
    )
    return service.publish_candidate_cad(
        publication.candidate,
        CandidateSynthesisRequest.model_validate(manifest["request"]),
        CandidateSynthesisPolicy.model_validate(manifest["policy"]),
        request,
        realization,
        **kwargs,
    )


def candidate_cad_fixture(tmp_path):
    realization_service, candidate, request, policy, cad_request = make_candidate_cad_fixture(tmp_path)
    realization = realization_service.realize(candidate, request, policy, cad_request).realization
    assert realization is not None
    publication = CandidatePublicationService(
        tmp_path, candidate.source_binding.project_id, realization_service.state_manager
    ).publish(candidate, request, policy)
    source_store = ArtifactStore(
        tmp_path, project_id=candidate.source_binding.project_id, run_id="SOURCE-STEP"
    )
    source_store.publish(
        "TEST-SOURCE-STEP",
        ArtifactType.STEP,
        "source.step",
        b"synthetic-step-content",
        "test-source",
        "1",
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
    )
    return publication, realization, cad_request, realization_service.state_manager


def realization_source_artifacts(tmp_path, realization, project_id):
    lookup = ArtifactStore(tmp_path, project_id=project_id, run_id="SOURCE-LOOKUP")
    sources = []
    for identity in realization.verified_source_content_identities:
        mapping = next(mapping for mapping in realization.mappings if mapping.source_geometry_identity == identity)
        sources.append(lookup.existing_in_project(mapping.geometry_definition_identities[0]))
    assert all(source is not None for source in sources)
    return tuple(sources)


def trusted_candidate_cad_fixture(tmp_path):
    state = make_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12-4", state)
    source = ArtifactStore(tmp_path, project_id="PRJ-M12-4", run_id="INPUT").publish(
        "ART-source", ArtifactType.STEP, "source.step", b"trusted-step", "test-source", "1",
        state.revision, state_hash(state),
    )
    second_source = ArtifactStore(tmp_path, project_id="PRJ-M12-4", run_id="INPUT").publish(
        "ART-second-source", ArtifactType.STEP, "second-source.step", b"second-trusted-step",
        "test-source", "1", state.revision, state_hash(state),
    )
    from mechcad_harness.candidates import ComponentSpecificationSnapshot, PhysicalComponentRole

    specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="trusted:motor@1",
        geometry_source={
            "artifact_id": source.artifact_id,
            "artifact_hash": source.sha256,
            "source_identity": "trusted:motor@1",
        },
    )
    candidate, synthesis_request, policy = make_candidate_for_specification(
        state, specification=specification, instance_id="motor", role=PhysicalComponentRole.ACTUATOR
    )
    second_specification = ComponentSpecificationSnapshot(
        component_type="motor",
        source_identity="trusted:second-motor@1",
        geometry_source={
            "artifact_id": second_source.artifact_id,
            "artifact_hash": second_source.sha256,
            "source_identity": "trusted:second-motor@1",
        },
    )
    candidate = MechanicalDesignCandidate(
        source_binding=candidate.source_binding,
        synthesis_request_hash=synthesis_request.request_hash,
        synthesis_policy_hash=policy.policy_hash,
        component_specifications=(specification, second_specification),
        realization=PhysicalMechanismRealization(components=(
            candidate.realization.components[0],
            PhysicalComponentInstance(
                instance_id="second-motor",
                specification_hash=second_specification.specification_hash,
                role=PhysicalComponentRole.ACTUATOR,
            ),
        )),
        generator_identity="m12-4-test-generator",
        generator_version="1",
    )
    imported = ImportedCadComponent(
        component_id="cad_motor", artifact_id=source.artifact_id, artifact_hash=source.sha256,
        source_revision=state.revision, source_state_hash=state_hash(state),
    )
    second_imported = ImportedCadComponent(
        component_id="cad_second_motor",
        artifact_id=second_source.artifact_id,
        artifact_hash=second_source.sha256,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
    )
    request = CandidateCadRealizationRequest(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=("motor", "second-motor"),
        mappings=(CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id="motor",
            cad_instance_id="cad_motor",
            fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            representation_identity=imported_component_hash(imported),
            source_geometry_identity=source.sha256,
            geometry_definition_identities=(source.artifact_id,),
            placement={"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
            placement_origin=CandidatePlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=(source.artifact_id,),
                derivation="fixed-home-placement@1",
                transform={"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
            ),
        ), CandidateCadInstanceMapping(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id="second-motor",
            cad_instance_id="cad_second_motor",
            fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            representation_identity=imported_component_hash(second_imported),
            source_geometry_identity=second_source.sha256,
            geometry_definition_identities=(second_source.artifact_id,),
            placement={"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
            placement_origin=CandidatePlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=(second_source.artifact_id,),
                derivation="fixed-home-placement@1",
                transform={"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
            ),
        )),
    )
    outcome = make_cad_service(tmp_path, manager).realize(candidate, synthesis_request, policy, request)
    realization = outcome.realization
    assert realization is not None, outcome
    publication = CandidatePublicationService(tmp_path, candidate.source_binding.project_id, manager).publish(
        candidate, synthesis_request, policy
    )
    return publication, realization, request, manager


def test_candidate_cad_payload_is_canonical_and_keeps_execution_reference(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceArtifactService

    candidate_publication, realization, request, manager = candidate_cad_fixture(tmp_path)
    service = CandidateProvenanceArtifactService(tmp_path, candidate_publication.candidate.source_binding.project_id, manager)
    sources = ()

    first = publish_candidate_cad(service,
        candidate_publication, request, realization, source_step_artifacts=sources
    )
    second = publish_candidate_cad(service,
        candidate_publication, request, realization, source_step_artifacts=sources
    )

    assert first.artifact == second.artifact
    assert first.artifact.input_hash == realization.realization_hash
    assert first.artifact.run_id == candidate_publication.artifact.run_id
    assert first.payload.realization == realization
    assert first.payload.candidate_artifact.artifact.sha256 == candidate_publication.artifact.sha256
    assert first.payload.source_step_artifacts == sources


@pytest.mark.parametrize("source_mutation", ("missing", "added", "reordered", "unrelated"))
def test_candidate_cad_requires_exact_ordered_source_step_references(tmp_path, source_mutation):
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateCadProvenance,
    )

    publication, realization, request, _ = trusted_candidate_cad_fixture(tmp_path)
    sources = realization_source_artifacts(tmp_path, realization, request.source_binding.project_id)
    same_binding_store = ArtifactStore(
        tmp_path, project_id=request.source_binding.project_id, run_id="UNRELATED-STEP"
    )
    unrelated = same_binding_store.publish(
        "UNRELATED-STEP",
        ArtifactType.STEP,
        "unrelated.step",
        b"unrelated-step-content",
        "test-source",
        "1",
        request.source_binding.source_revision,
        request.source_binding.source_state_hash,
    )
    if source_mutation == "missing":
        supplied = ()
    elif source_mutation == "added":
        supplied = sources + (unrelated,)
    elif source_mutation == "reordered":
        supplied = tuple(reversed(sources))
    else:
        supplied = (unrelated,) + sources[1:]

    with pytest.raises(ValidationError, match="source STEP identity"):
        CandidateCadProvenance(
            realization=realization,
            request=request,
            candidate_artifact=ArtifactReference(artifact=publication.artifact),
            source_step_artifacts=supplied,
        )


def test_candidate_cad_publication_requires_source_step_references(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
    )

    publication, realization, request, manager = trusted_candidate_cad_fixture(tmp_path)
    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)

    with pytest.raises(TypeError, match="source_step_artifacts"):
        publish_candidate_cad(service, publication, request, realization)


def test_candidate_cad_rejects_same_bytes_from_different_source_artifact(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateCadProvenance,
    )

    publication, realization, request, _ = trusted_candidate_cad_fixture(tmp_path)
    source, *remaining_sources = realization_source_artifacts(
        tmp_path, realization, request.source_binding.project_id
    )
    alias_store = ArtifactStore(
        tmp_path, project_id=request.source_binding.project_id, run_id="ALIAS-STEP"
    )
    alias = alias_store.publish(
        "ALIAS-SOURCE-STEP",
        ArtifactType.STEP,
        "alias.step",
        (tmp_path / source.relative_path).read_bytes(),
        source.producer_tool_name,
        source.producer_tool_version,
        source.bound_revision,
        source.bound_state_hash,
        input_hash=source.input_hash,
    )

    with pytest.raises(ValidationError, match="source STEP identity"):
        CandidateCadProvenance(
            realization=realization,
            request=request,
            candidate_artifact=ArtifactReference(artifact=publication.artifact),
            source_step_artifacts=(alias, *remaining_sources),
        )


@pytest.mark.parametrize("mutation", ("unpublished", "byte-tampered"))
def test_candidate_cad_publication_rejects_unverified_source_step_artifact(tmp_path, mutation):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
    )

    publication, realization, request, manager = trusted_candidate_cad_fixture(tmp_path)
    source, *remaining_sources = realization_source_artifacts(
        tmp_path, realization, request.source_binding.project_id
    )
    if mutation == "unpublished":
        source = source.model_copy(update={"artifact_id": "FORGED-SOURCE-STEP"})
    else:
        (tmp_path / source.relative_path).write_bytes(b"tampered-step-content")

    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)
    with pytest.raises(CandidateProvenanceIntegrityError, match="(candidate publication|source STEP artifact)"):
        publish_candidate_cad(service,
            publication,
            request,
            realization,
            source_step_artifacts=(source, *remaining_sources),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("project_id", "OTHER-PROJECT"),
        ("run_id", "OTHER-RUN"),
        ("artifact_type", ArtifactType.STEP),
        ("sha256", "sha256:" + "0" * 64),
        ("bound_revision", 99),
        ("bound_state_hash", "sha256:" + "1" * 64),
    ),
)
def test_artifact_reference_rejects_metadata_that_disagrees_with_snapshot(tmp_path, field, value):
    from mechcad_harness.candidates.provenance_artifacts import ArtifactReference

    publication, _, _, _ = candidate_cad_fixture(tmp_path)

    with pytest.raises(ValidationError):
        ArtifactReference(artifact=publication.artifact, **{field: value})


def test_candidate_cad_rejects_candidate_artifact_from_another_project(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateCadProvenance,
    )

    publication, realization, request, _ = candidate_cad_fixture(tmp_path)
    other_project_artifact = publication.artifact.model_copy(update={"project_id": "OTHER-PROJECT"})

    with pytest.raises(ValidationError, match="project mismatch"):
        CandidateCadProvenance(
            realization=realization,
            request=request,
            candidate_artifact=ArtifactReference(artifact=other_project_artifact),
            source_step_artifacts=(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("project_id", "OTHER-PROJECT"),
        ("bound_revision", 2),
        ("bound_state_hash", "sha256:" + "0" * 64),
    ),
)
def test_candidate_cad_rejects_source_step_outside_request_binding(tmp_path, field, value):
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateCadProvenance,
    )

    publication, realization, request, _ = trusted_candidate_cad_fixture(tmp_path)
    sources = realization_source_artifacts(tmp_path, realization, request.source_binding.project_id)
    source = sources[0]

    with pytest.raises(ValidationError, match="source STEP binding"):
        CandidateCadProvenance(
            realization=realization,
            request=request,
            candidate_artifact=ArtifactReference(artifact=publication.artifact),
            source_step_artifacts=(source.model_copy(update={field: value}),) + sources[1:],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("producer_tool_name", "forged-producer"),
        ("relative_path", "projects/PRJ-M12-4/runs/RUN/artifacts/X/forged.json"),
        ("input_hash", "sha256:" + "0" * 64),
        ("bound_revision", 2),
        ("bound_state_hash", "sha256:" + "0" * 64),
        ("artifact_id", "CANDIDATE-CAD-forged"),
    ),
)
def test_candidate_cad_resolver_rejects_unbound_metadata(tmp_path, field, value):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
    )

    publication, realization, request, manager = candidate_cad_fixture(tmp_path)
    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)
    envelope = publish_candidate_cad(service,
        publication,
        request,
        realization,
        source_step_artifacts=realization_source_artifacts(
            tmp_path, realization, request.source_binding.project_id
        ),
    )
    metadata_path = (
        tmp_path
        / "projects"
        / envelope.artifact.project_id
        / "runs"
        / envelope.artifact.run_id
        / "artifacts"
        / envelope.artifact.artifact_id
        / "metadata.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata[field] = value
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(CandidateProvenanceIntegrityError):
        service.resolve_candidate_cad(envelope.artifact)


def test_candidate_cad_resolver_reopens_artifact_store_in_recorded_task_scope(tmp_path, monkeypatch):
    import mechcad_harness.candidates.provenance_artifacts as provenance_artifacts
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceArtifactService

    publication, realization, request, manager = candidate_cad_fixture(tmp_path)
    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)
    envelope = publish_candidate_cad(service,
        publication,
        request,
        realization,
        source_step_artifacts=realization_source_artifacts(
            tmp_path, realization, request.source_binding.project_id
        ),
    )
    calls = []
    artifact_store = provenance_artifacts.ArtifactStore

    def scoped_store(*args, **kwargs):
        calls.append((kwargs["project_id"], kwargs["run_id"], kwargs.get("task_id")))
        return artifact_store(*args, **kwargs)

    monkeypatch.setattr(provenance_artifacts, "ArtifactStore", scoped_store)

    assert service.resolve_candidate_cad(envelope.artifact).artifact == envelope.artifact
    assert calls == [
        (envelope.artifact.project_id, envelope.artifact.run_id, envelope.artifact.task_id),
        (
            envelope.payload.candidate_artifact.artifact.project_id,
            envelope.payload.candidate_artifact.artifact.run_id,
            envelope.payload.candidate_artifact.artifact.task_id,
        ),
    ] + [
        (source.project_id, source.run_id, source.task_id)
        for source in envelope.payload.source_step_artifacts
    ]


def test_candidate_cad_resolver_rejects_byte_tampered_source_step_artifact(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
    )

    publication, realization, request, manager = trusted_candidate_cad_fixture(tmp_path)
    sources = realization_source_artifacts(tmp_path, realization, request.source_binding.project_id)
    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)
    envelope = publish_candidate_cad(service,
        publication, request, realization, source_step_artifacts=sources
    )
    (tmp_path / sources[0].relative_path).write_bytes(b"tampered-after-publication")

    with pytest.raises(CandidateProvenanceIntegrityError, match="source STEP artifact verification failed"):
        service.resolve_candidate_cad(envelope.artifact)


def test_candidate_cad_resolver_rejects_byte_tampered_candidate_artifact(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
    )

    publication, realization, request, manager = trusted_candidate_cad_fixture(tmp_path)
    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)
    envelope = publish_candidate_cad(service,
        publication,
        request,
        realization,
        source_step_artifacts=realization_source_artifacts(
            tmp_path, realization, request.source_binding.project_id
        ),
    )
    (tmp_path / publication.artifact.relative_path).write_bytes(b"tampered-candidate-json")

    with pytest.raises(CandidateProvenanceIntegrityError, match="candidate artifact verification failed"):
        service.resolve_candidate_cad(envelope.artifact)


def test_candidate_cad_resolver_rejects_nested_candidate_publication_metadata_substitution(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
    )

    publication, realization, request, manager = trusted_candidate_cad_fixture(tmp_path)
    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)
    envelope = publish_candidate_cad(
        service,
        publication,
        request,
        realization,
        source_step_artifacts=realization_source_artifacts(
            tmp_path, realization, request.source_binding.project_id
        ),
    )
    candidate_metadata_path = tmp_path / publication.artifact.relative_path
    candidate_metadata = json.loads(
        (candidate_metadata_path.parent / "metadata.json").read_text(encoding="utf-8")
    )
    candidate_metadata["producer_tool_name"] = "forged-candidate-publication"
    (candidate_metadata_path.parent / "metadata.json").write_text(
        json.dumps(candidate_metadata), encoding="utf-8"
    )

    payload = json.loads((tmp_path / envelope.artifact.relative_path).read_text(encoding="utf-8"))
    payload["candidate_artifact"]["artifact"]["producer_tool_name"] = candidate_metadata[
        "producer_tool_name"
    ]
    _replace_persisted_payload(tmp_path, envelope.artifact, payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="candidate"):
        service.resolve_candidate_cad(envelope.artifact.artifact_id)


def _candidate_artifact_with_invalid_publication_payload(tmp_path, publication, *, payload_kind):
    original_artifact, content = ArtifactStore(
        tmp_path,
        project_id=publication.artifact.project_id,
        run_id=publication.artifact.run_id,
        task_id=publication.artifact.task_id,
    ).read_verified_strict(
        publication.artifact.artifact_id,
        expected_type=ArtifactType.JSON,
        expected_hash=publication.artifact.sha256,
    )
    if payload_kind == "generic":
        content = canonical_json_bytes({"not": "a candidate publication"})
    else:
        payload = json.loads(content)
        payload["request"]["requested_evaluation_categories"] = ["different-category"]
        payload["request"]["request_hash"] = "pending"
        content = canonical_json_bytes(payload)
    artifact = ArtifactStore(
        tmp_path,
        project_id=original_artifact.project_id,
        run_id=original_artifact.run_id,
        task_id=original_artifact.task_id,
    ).publish(
        f"INVALID-CANDIDATE-{payload_kind}",
        ArtifactType.JSON,
        "candidate.json",
        content,
        "mechcad-candidate-publication",
        "1",
        original_artifact.bound_revision,
        original_artifact.bound_state_hash,
        input_hash=original_artifact.input_hash,
    )
    return publication.model_copy(update={"artifact": artifact})


@pytest.mark.parametrize("payload_kind", ("generic", "semantic-mismatch"))
def test_candidate_cad_resolver_rejects_invalid_verified_candidate_publication(tmp_path, payload_kind):
    from mechcad_harness.artifacts import EngineeringArtifact
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateCadProvenance,
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
    )

    publication, realization, request, manager = trusted_candidate_cad_fixture(tmp_path)
    service = CandidateProvenanceArtifactService(tmp_path, request.source_binding.project_id, manager)
    envelope = publish_candidate_cad(service,
        publication,
        request,
        realization,
        source_step_artifacts=realization_source_artifacts(
            tmp_path, realization, request.source_binding.project_id
        ),
    )
    invalid_publication = _candidate_artifact_with_invalid_publication_payload(
        tmp_path, publication, payload_kind=payload_kind
    )
    payload = CandidateCadProvenance(
        realization=envelope.payload.realization,
        request=envelope.payload.request,
        candidate_artifact=ArtifactReference(artifact=invalid_publication.artifact),
        source_step_artifacts=envelope.payload.source_step_artifacts,
    )
    content = canonical_json_bytes(payload.model_dump(mode="json"))
    artifact_path = tmp_path / envelope.artifact.relative_path
    metadata_path = artifact_path.parent / "metadata.json"
    artifact_path.write_bytes(content)
    artifact = EngineeringArtifact.model_validate_json(metadata_path.read_text(encoding="utf-8")).model_copy(
        update={
            "sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
    )
    metadata_path.write_text(json.dumps(artifact.model_dump(mode="json")), encoding="utf-8")

    with pytest.raises(CandidateProvenanceIntegrityError, match="candidate publication"):
        service.resolve_candidate_cad(artifact)


def _write_evidence(tmp_path, candidate, evidence):
    path = tmp_path / "projects" / candidate.source_binding.project_id / "evidence" / f"{evidence.id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(evidence.model_dump_json(), encoding="utf-8")


def test_candidate_evaluation_round_trip_requires_every_proof_evidence(tmp_path):
    from mechcad_harness.candidates import (
        CandidateEvaluationCurrentnessService,
        CandidateEvaluationPolicy,
        CandidateEvaluationService,
    )
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceArtifactService
    from mechcad_harness.models.evidence import Evidence
    state = make_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, request, policy = make_evaluation_candidate(state)
    cad_stage, m10, scope, binding, m10_request, cad_request = make_bound_m10_inputs(candidate)
    evaluation = CandidateEvaluationService(manager).evaluate(
        candidate, request, policy, make_m12_result(candidate), cad_stage, m10, CandidateEvaluationPolicy(),
        cad_request=cad_request, m10_request=m10_request, m10_scope=scope, m10_binding=binding,
    )
    publication = CandidatePublicationService(tmp_path, "PRJ-M12", manager).publish(candidate, request, policy)
    service = CandidateProvenanceArtifactService(
        tmp_path, "PRJ-M12", manager, cad_replay_verifier=lambda *args: None
    )
    cad = publish_candidate_cad(service, publication, cad_request, cad_stage.realization, source_step_artifacts=())
    proof = evaluation.m10_stage_outcome.pair_proofs[0]
    evidence_id = "EVD-CPROOF-" + hashlib.sha256(
        (proof.request_hash + proof.result_hash).encode()
    ).hexdigest()[:24]
    evidence = Evidence(
        id=evidence_id,
        kind="analysis.continuous_clearance_proof",
        summary="fixture proof",
        revision=candidate.source_binding.source_revision,
        state_hash=candidate.source_binding.source_state_hash,
        producer_result_id=proof.result_hash,
        input_hash=proof.request_hash,
        output_hash=proof.result_hash,
    )
    _write_evidence(tmp_path, candidate, evidence)

    published = service.publish_candidate_evaluation(cad.artifact, evaluation)
    resolved = service.resolve_candidate_evaluation(published.artifact.artifact_id)

    assert resolved.payload.evaluation == evaluation
    assert tuple(item.id for item in resolved.payload.proof_evidence) == (evidence_id,)


def test_candidate_evaluation_rejects_missing_proof_evidence(tmp_path):
    from mechcad_harness.candidates import (
        CandidateCurrentness,
        CandidateEvaluationPolicy,
        CandidateEvaluationService,
    )
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
    )
    state = make_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    candidate, request, policy = make_evaluation_candidate(state)
    cad_stage, m10, scope, binding, m10_request, cad_request = make_bound_m10_inputs(candidate)
    evaluation = CandidateEvaluationService(manager).evaluate(
        candidate, request, policy, make_m12_result(candidate), cad_stage, m10, CandidateEvaluationPolicy(),
        cad_request=cad_request, m10_request=m10_request, m10_scope=scope, m10_binding=binding,
    )
    publication = CandidatePublicationService(tmp_path, "PRJ-M12", manager).publish(candidate, request, policy)
    service = CandidateProvenanceArtifactService(
        tmp_path, "PRJ-M12", manager, cad_replay_verifier=lambda *args: None
    )
    cad = publish_candidate_cad(service, publication, cad_request, cad_stage.realization, source_step_artifacts=())

    with pytest.raises(CandidateProvenanceIntegrityError, match="evidence"):
        service.publish_candidate_evaluation(cad.artifact, evaluation)


def _replace_persisted_payload(tmp_path, artifact, payload):
    """Replace an envelope payload and its recorded byte hash for resolver tests."""
    content = canonical_json_bytes(payload)
    artifact_path = tmp_path / artifact.relative_path
    metadata_path = artifact_path.parent / "metadata.json"
    artifact_path.write_bytes(content)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["sha256"] = "sha256:" + hashlib.sha256(content).hexdigest()
    metadata["size_bytes"] = len(content)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _published_evaluation(tmp_path, manager, state, *, suffix="", required_home=False):
    from mechcad_harness.candidates import (
        CandidateCurrentness,
        CandidateEvaluationPolicy,
        CandidateEvaluationService,
        CandidateM10EvaluationService,
    )
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceArtifactService
    from mechcad_harness.models.evidence import Evidence


    candidate, request, policy = make_evaluation_candidate(state)
    if suffix:
        candidate = type(candidate).model_validate(candidate.model_dump(mode="json") | {
            "generator_identity": f"provenance-fixture-{suffix}", "candidate_hash": "pending",
        })
    cad_stage, m10, scope, binding, m10_request, cad_request = make_bound_m10_inputs(candidate)
    if required_home:
        scope = make_scope()
        m10_request = make_m10_request(cad_stage.realization, binding, scope)
        m10 = CandidateM10EvaluationService(
            lambda **kwargs: make_proof_result(kwargs),
            lambda **kwargs: make_home_result(kwargs),
            scope=scope,
        ).evaluate(
            candidate.source_binding.source_revision,
            candidate.source_binding.source_state_hash,
            cad_stage.realization,
            binding,
            m10_request,
        )
    evaluation = CandidateEvaluationService(
        currentness_verifier=type("Current", (), {"evaluate": lambda *_: CandidateCurrentness.CURRENT})()
    ).evaluate(
        candidate, request, policy, make_m12_result(candidate), cad_stage, m10, CandidateEvaluationPolicy(),
        cad_request=cad_request, m10_request=m10_request, m10_scope=scope, m10_binding=binding,
    )
    publication = CandidatePublicationService(tmp_path, "PRJ-M12", manager).publish(candidate, request, policy)
    service = CandidateProvenanceArtifactService(
        tmp_path, "PRJ-M12", manager, cad_replay_verifier=lambda *args: None
    )
    cad = publish_candidate_cad(service, publication, cad_request, cad_stage.realization, source_step_artifacts=())
    proof = evaluation.m10_stage_outcome.pair_proofs[0]
    evidence = Evidence(
        id="EVD-CPROOF-" + hashlib.sha256((proof.request_hash + proof.result_hash).encode()).hexdigest()[:24],
        kind="analysis.continuous_clearance_proof", summary="fixture proof",
        revision=candidate.source_binding.source_revision, state_hash=candidate.source_binding.source_state_hash,
        producer_result_id=proof.result_hash, input_hash=proof.request_hash, output_hash=proof.result_hash,
    )
    _write_evidence(tmp_path, candidate, evidence)
    if required_home:
        home = evaluation.m10_stage_outcome.home_exact_checks[0]
        _write_evidence(tmp_path, candidate, Evidence(
            id="EVD-KSWEEP-" + hashlib.sha256(
                (home.request_hash + home.result_hash).encode()
            ).hexdigest()[:24],
            kind="analysis.kinematic_sweep",
            summary="fixture home check",
            revision=candidate.source_binding.source_revision,
            state_hash=candidate.source_binding.source_state_hash,
            producer_result_id=home.result_hash,
            input_hash=home.request_hash,
            output_hash=home.result_hash,
        ))
    return service, candidate, service.publish_candidate_evaluation(cad.artifact, evaluation)


def _evaluation_fixture(tmp_path, *, required_home=False):
    state = make_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    return _published_evaluation(tmp_path, manager, state, required_home=required_home)


def _canonical_provenance_fixture(tmp_path, *, requires_home=False):
    from mechcad_harness.candidates.canonical_m10 import CanonicalM10VerificationService
    from mechcad_harness.models.evidence import Evidence
    reconstruction, canonical_cad = canonical_inputs(tmp_path, requires_home=requires_home)
    manager = StateManager(tmp_path)

    class FakeApplication:
        def prove_continuous_single_axis_clearance(self, **kwargs):
            return make_proof_result(kwargs)

        def analyze_assembly_kinematics(self, **kwargs):
            return make_home_result(kwargs)

    outcome = CanonicalM10VerificationService(FakeApplication()).execute(
        reconstruction, canonical_cad
    )
    evidence_dir = tmp_path / "projects" / reconstruction.project_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for proof in outcome.pair_proofs:
        evidence_id = "EVD-CPROOF-" + hashlib.sha256(
            (proof.request_hash + proof.result_hash).encode()
        ).hexdigest()[:24]
        (evidence_dir / f"{evidence_id}.json").write_text(
            Evidence(
                id=evidence_id,
                kind="analysis.continuous_clearance_proof",
                summary="canonical proof fixture",
                revision=outcome.revision,
                state_hash=outcome.state_hash,
                producer_result_id=proof.result_hash,
                input_hash=proof.request_hash,
                output_hash=proof.result_hash,
            ).model_dump_json(exclude_none=True),
            encoding="utf-8",
        )
    for check in outcome.home_exact_checks:
        evidence_id = "EVD-KSWEEP-" + hashlib.sha256(
            (check.request_hash + check.result_hash).encode()
        ).hexdigest()[:24]
        (evidence_dir / f"{evidence_id}.json").write_text(
            Evidence(
                id=evidence_id,
                kind="analysis.kinematic_sweep",
                summary="canonical home fixture",
                revision=outcome.revision,
                state_hash=outcome.state_hash,
                producer_result_id=check.result_hash,
                input_hash=check.request_hash,
                output_hash=check.result_hash,
            ).model_dump_json(exclude_none=True),
            encoding="utf-8",
        )
    service = __import__(
        "mechcad_harness.candidates.provenance_artifacts",
        fromlist=["CandidateProvenanceArtifactService"],
    ).CandidateProvenanceArtifactService(
        tmp_path, reconstruction.project_id, manager
    )
    return service, reconstruction, canonical_cad, outcome


def _canonical_publications(tmp_path, *, requires_home=False):
    service, reconstruction, canonical_cad, outcome = _canonical_provenance_fixture(
        tmp_path, requires_home=requires_home
    )
    cad_publication = service.publish_canonical_cad(canonical_cad)
    m10_publication = service.publish_canonical_m10(cad_publication, outcome)
    return service, reconstruction, canonical_cad, outcome, cad_publication, m10_publication


def _republish_json_payload(tmp_path, artifact, payload, *, artifact_id=None, input_hash=None):
    content = canonical_json_bytes(payload)
    return ArtifactStore(
        tmp_path,
        project_id=artifact.project_id,
        run_id=artifact.run_id,
        task_id=artifact.task_id,
    ).publish(
        artifact_id or artifact.artifact_id,
        ArtifactType.JSON,
        artifact.relative_path.rsplit("/", 1)[-1],
        content,
        artifact.producer_tool_name,
        artifact.producer_tool_version,
        artifact.bound_revision,
        artifact.bound_state_hash,
        input_hash=input_hash if input_hash is not None else artifact.input_hash,
    )


def _cad_with_mechanism_identity(canonical_cad, *, mechanism_id=None, mechanism_hash=None):
    from mechcad_harness.candidates.canonical_cad import (
        CanonicalCadRealization,
        _canonical_request_hash,
    )

    mechanism_id = mechanism_id or canonical_cad.mechanism_id
    mechanism_hash = mechanism_hash or "sha256:" + "f" * 64
    mappings = tuple(
        type(mapping).model_validate(
            mapping.model_dump(mode="python")
            | {"mechanism_hash": mechanism_hash, "mapping_hash": "pending"}
        )
        for mapping in canonical_cad.mappings
    )
    request_hash = _canonical_request_hash(
        canonical_cad.project_id,
        canonical_cad.revision,
        canonical_cad.state_hash,
        mechanism_id,
        mechanism_hash,
        mappings,
        canonical_cad.compiler_identity,
        canonical_cad.compiler_version,
    )
    return CanonicalCadRealization.model_validate(
        canonical_cad.model_dump(mode="python")
        | {
            "mechanism_id": mechanism_id,
            "mechanism_hash": mechanism_hash,
            "mappings": mappings,
            "request_hash": request_hash,
            "realization_hash": "pending",
        }
    )


def _cad_with_rehashed_mapping_mutation(canonical_cad, mutation):
    from mechcad_harness.candidates.canonical_cad import (
        CanonicalCadRealization,
        _canonical_request_hash,
    )

    if mutation == "placement":
        original = canonical_cad.mappings[0]
        changed_mapping = type(original).model_validate(
            original.model_dump(mode="python")
            | {
                "placement": original.placement.model_copy(
                    update={"x_mm": original.placement.x_mm + 1.0}
                ),
                "mapping_hash": "pending",
            }
        )
    elif mutation == "geometry":
        original = next(
            mapping
            for mapping in canonical_cad.mappings
            if mapping.source_geometry_identity is None
        )
        changed_mapping = type(original).model_validate(
            original.model_dump(mode="python")
            | {
                "geometry_definition_identities": ("forged-geometry-identity",),
                "mapping_hash": "pending",
            }
        )
    else:
        raise AssertionError(mutation)

    mappings = tuple(
        changed_mapping if mapping is original else mapping
        for mapping in canonical_cad.mappings
    )
    instances = tuple(
        instance.model_copy(update={"placement": changed_mapping.placement})
        if instance.instance_id == changed_mapping.cad_instance_id
        else instance
        for instance in canonical_cad.assembly.instances
    )
    assembly = canonical_cad.assembly.model_copy(update={"instances": instances})
    request_hash = _canonical_request_hash(
        canonical_cad.project_id,
        canonical_cad.revision,
        canonical_cad.state_hash,
        canonical_cad.mechanism_id,
        canonical_cad.mechanism_hash,
        mappings,
        canonical_cad.compiler_identity,
        canonical_cad.compiler_version,
    )
    return CanonicalCadRealization.model_validate(
        canonical_cad.model_dump(mode="python")
        | {
            "mappings": mappings,
            "assembly": assembly,
            "assembly_hash": assembly_hash(assembly),
            "request_hash": request_hash,
            "realization_hash": "pending",
        }
    )


@pytest.mark.parametrize("mutation", ("placement", "geometry"))
def test_canonical_cad_publish_rejects_rehashed_mapping_identity_forgery(
    tmp_path, mutation
):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
    )

    service, reconstruction, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    forged = _cad_with_rehashed_mapping_mutation(canonical_cad, mutation)

    assert forged.mechanism_id == canonical_cad.mechanism_id
    assert forged.mechanism_hash == canonical_cad.mechanism_hash
    assert forged.realization_hash != canonical_cad.realization_hash

    with pytest.raises(CandidateProvenanceIntegrityError, match="realization"):
        service.publish_canonical_cad(reconstruction, forged)


@pytest.mark.parametrize("mutation", ("placement", "geometry"))
def test_canonical_cad_resolve_rejects_rehashed_mapping_identity_forgery(
    tmp_path, mutation
):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
        CanonicalCadProvenance,
    )

    service, _, canonical_cad, _, publication, _ = _canonical_publications(tmp_path)
    forged = _cad_with_rehashed_mapping_mutation(canonical_cad, mutation)
    payload = CanonicalCadProvenance(
        realization=forged,
        source_step_artifacts=publication.payload.source_step_artifacts,
    )
    persisted = _republish_json_payload(
        tmp_path,
        publication.artifact,
        payload.model_dump(mode="json"),
        artifact_id="CANONICAL-CAD-" + forged.realization_hash[7:31],
        input_hash=forged.realization_hash,
    )

    assert forged.mechanism_id == canonical_cad.mechanism_id
    assert forged.mechanism_hash == canonical_cad.mechanism_hash

    with pytest.raises(CandidateProvenanceIntegrityError, match="realization"):
        service.resolve_canonical_cad(persisted.artifact_id)


def _outcome_with_mechanism_identity(outcome, *, mechanism_id=None, mechanism_hash=None):
    mechanism_id = mechanism_id or outcome.mechanism_id
    mechanism_hash = mechanism_hash or "sha256:" + "e" * 64
    inventory = type(outcome.inventory).model_validate(
        outcome.inventory.model_dump(mode="python")
        | {
            "mechanism_id": mechanism_id,
            "mechanism_hash": mechanism_hash,
            "inventory_hash": "pending",
        }
    )
    scope = type(outcome.scope).model_validate(
        outcome.scope.model_dump(mode="python")
        | {
            "mechanism_id": mechanism_id,
            "mechanism_hash": mechanism_hash,
            "scope_hash": "pending",
        }
    )
    request = type(outcome.request).model_validate(
        outcome.request.model_dump(mode="python")
        | {
            "mechanism_id": mechanism_id,
            "mechanism_hash": mechanism_hash,
            "inventory": inventory,
            "scope_hash": scope.scope_hash,
            "request_hash": "pending",
        }
    )
    from mechcad_harness.candidates.canonical_m10 import CanonicalM10VerificationOutcome

    return CanonicalM10VerificationOutcome.model_validate(
        outcome.model_dump(mode="python")
        | {
            "mechanism_id": mechanism_id,
            "mechanism_hash": mechanism_hash,
            "scope": scope,
            "inventory": inventory,
            "request": request,
            "outcome_hash": "pending",
        }
    )


def _outcome_with_revision_state(outcome, *, revision, state_hash):
    scope = type(outcome.scope).model_validate(
        outcome.scope.model_dump(mode="python")
        | {"revision": revision, "state_hash": state_hash, "scope_hash": "pending"}
    )
    inventory = type(outcome.inventory).model_validate(
        outcome.inventory.model_dump(mode="python")
        | {
            "revision": revision,
            "state_hash": state_hash,
            "scope_hash": scope.scope_hash,
            "inventory_hash": "pending",
        }
    )
    request = type(outcome.request).model_validate(
        outcome.request.model_dump(mode="python")
        | {
            "revision": revision,
            "state_hash": state_hash,
            "inventory": inventory,
            "scope_hash": scope.scope_hash,
            "request_hash": "pending",
        }
    )
    from mechcad_harness.candidates.canonical_m10 import CanonicalM10VerificationOutcome

    return CanonicalM10VerificationOutcome.model_validate(
        outcome.model_dump(mode="python")
        | {
            "revision": revision,
            "state_hash": state_hash,
            "scope": scope,
            "inventory": inventory,
            "request": request,
            "outcome_hash": "pending",
        }
    )


def _reconstruction_with_mechanism(reconstruction, mechanism):
    from mechcad_harness.candidates import PromotableMechanismProjection
    from mechcad_harness.candidates.canonical_mechanism import CanonicalMechanismReconstruction

    projection = PromotableMechanismProjection(
        canonical_target_mechanism_id=mechanism.id,
        canonical_instance_ids=tuple(item.instance_id for item in mechanism.components),
        component_specifications=mechanism.component_specifications,
        components=mechanism.components,
        accepted_design_choices=mechanism.accepted_design_choices,
        placements=mechanism.placements,
        connections=mechanism.connections,
        joint_bindings=mechanism.joint_bindings,
        m10_obligations=mechanism.m10_obligations,
        mapping_identities=tuple(item.instance_id for item in mechanism.components),
    )
    return CanonicalMechanismReconstruction.model_validate(
        reconstruction.model_dump(mode="python")
        | {
            "canonical_mechanism": mechanism,
            "normalized_projection_hash": projection.projection_hash,
        }
    )


def test_canonical_m10_round_trip_requires_canonical_cad_and_all_evidence(tmp_path):
    service, _, canonical_cad, outcome = _canonical_provenance_fixture(tmp_path)

    cad_publication = service.publish_canonical_cad(canonical_cad)
    publication = service.publish_canonical_m10(cad_publication, outcome)

    resolved = service.resolve_canonical_m10(publication.artifact.artifact_id)

    assert resolved.payload.outcome == outcome
    assert resolved.payload.canonical_cad.artifact.sha256 == cad_publication.artifact.sha256


def test_canonical_m10_publication_round_trips_as_a_typed_parent(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CanonicalM10ProvenancePublication,
    )

    service, _, canonical_cad, outcome = _canonical_provenance_fixture(tmp_path)
    cad_publication = service.publish_canonical_cad(canonical_cad)
    publication = service.publish_canonical_m10(cad_publication, outcome)

    serialized = publication.model_dump(mode="json")
    assert serialized["payload"].get("schema_version") == "canonical-m10-provenance@1"
    reparsed = CanonicalM10ProvenancePublication.model_validate(serialized)

    assert reparsed == publication


def test_canonical_cad_publication_round_trips_as_a_typed_parent(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CanonicalCadProvenancePublication,
    )

    service, _, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    publication = service.publish_canonical_cad(canonical_cad)

    serialized = publication.model_dump(mode="json")
    assert serialized["payload"].get("schema_version") == "canonical-cad-provenance@1"
    reparsed = CanonicalCadProvenancePublication.model_validate(serialized)

    assert reparsed == publication


def _canonical_m10_v2_evidence_records(workspace, outcome):
    from mechcad_harness.models.evidence import Evidence

    evidence_dir = workspace / "projects" / outcome.project_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    groups = []
    for kind, prefix, records in (
        (
            "analysis.continuous_clearance_proof",
            "EVD-CPROOF-",
            outcome.pair_proofs,
        ),
        ("analysis.kinematic_sweep", "EVD-KSWEEP-", outcome.home_exact_checks),
    ):
        evidence_records = []
        for record in records:
            evidence_id = prefix + hashlib.sha256(
                (record.request_hash + record.result_hash).encode()
            ).hexdigest()[:24]
            evidence = Evidence(
                id=evidence_id,
                kind=kind,
                summary="canonical @2 provenance fixture evidence",
                revision=outcome.revision,
                state_hash=outcome.state_hash,
                producer_result_id=record.result_hash,
                input_hash=record.request_hash,
                output_hash=record.result_hash,
            )
            (evidence_dir / f"{evidence_id}.json").write_text(
                evidence.model_dump_json(exclude_none=True),
                encoding="utf-8",
            )
            evidence_records.append(evidence)
        groups.append(tuple(evidence_records))
    return tuple(groups)


def _canonical_provenance_v2_fixture(tmp_path):
    from hashlib import sha256

    from mechcad_harness.candidates.canonical_m10 import CanonicalM10VerificationService
    from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
    from mechcad_harness.candidates.canonical_mechanism import (
        CanonicalMechanismReconstruction,
        ProjectArtifactResolver,
        TrustedSourceArtifact,
        _projection_from_mechanism,
    )
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceArtifactService,
    )
    from mechcad_harness.models import DesignState
    from mechcad_harness.models.evidence import Evidence
    from test_canonical_m10_v2 import _canonical_m10_v4_fixture

    project_id = "PRJ-CAD-PROVENANCE-V2"
    workspace = tmp_path / "workspace"
    manager = StateManager(workspace)
    mechanism, _seed_reconstruction, _seed_cad, application = (
        _canonical_m10_v4_fixture(tmp_path / "seed")
    )
    state = DesignState(
        id="DES-CAD-V4",
        revision=1,
        physical_mechanisms=[mechanism],
    )
    snapshot = manager.create_project(project_id, state)
    from test_canonical_mechanism_v4 import _STEP_TEMPLATE

    step = _STEP_TEMPLATE.format(timestamp="2026-09-22T12:34:56").encode()
    raw_hash = "sha256:" + sha256(step).hexdigest()
    assert all(
        specification.geometry_source.artifact_hash == raw_hash
        for specification in mechanism.component_specifications
    )
    source_store = ArtifactStore(workspace, project_id=project_id, run_id="SOURCE")
    sources = tuple(
        TrustedSourceArtifact.from_artifact(
            source_store.publish(
                specification.geometry_source.artifact_id,
                ArtifactType.STEP,
                f"{specification.geometry_source.artifact_id.lower()}.step",
                step,
                "fixture-freecad",
                "1.1.3",
                snapshot.revision,
                "sha256:" + "a" * 64,
            )
        )
        for specification in mechanism.component_specifications
    )
    resolver = ProjectArtifactResolver(
        ArtifactStore(
            workspace,
            project_id=project_id,
            run_id="PROVENANCE-V2-LOOKUP",
        )
    )
    reconstruction = CanonicalMechanismReconstruction(
        project_id=project_id,
        revision=snapshot.revision,
        state_hash=snapshot.state_hash,
        canonical_mechanism=mechanism,
        trusted_source_references=sources,
        normalized_projection_hash=_projection_from_mechanism(mechanism).projection_hash,
    )
    cad = CanonicalPhysicalCadCompiler(resolver).realize(
        reconstruction,
        trusted_source_references=sources,
    )
    outcome = CanonicalM10VerificationService(application).execute(
        reconstruction, cad
    )
    _canonical_m10_v2_evidence_records(workspace, outcome)

    service = CandidateProvenanceArtifactService(
        workspace,
        project_id,
        manager,
    )
    return service, manager, reconstruction, cad, outcome, application


def test_canonical_cad_provenance_v2_round_trips_and_resolves_fresh_service(
    tmp_path,
):
    from mechcad_harness.candidates.canonical_cad import CanonicalCadRealizationV2
    from mechcad_harness.candidates.provenance_artifacts import (
        CanonicalCadProvenancePublication,
        CanonicalCadProvenanceV2,
        CandidateProvenanceArtifactService,
    )

    service, manager, reconstruction, cad, _outcome, _application = (
        _canonical_provenance_v2_fixture(tmp_path)
    )
    publication = service.publish_canonical_cad(reconstruction, cad)

    serialized = publication.model_dump(mode="json")
    assert set(CanonicalCadProvenanceV2.model_fields) == {
        "schema_version",
        "realization",
        "source_step_artifacts",
    }
    assert serialized["payload"]["schema_version"] == "canonical-cad-provenance@2"
    assert serialized["payload"]["realization"]["schema_version"] == (
        "canonical-cad-realization@2"
    )
    assert set(serialized["payload"]) == set(CanonicalCadProvenanceV2.model_fields)
    assert not {"provenance_hash", "semantic_hash"} & set(serialized["payload"])
    assert publication.artifact.input_hash == cad.realization_hash
    reparsed = CanonicalCadProvenancePublication.model_validate(serialized)
    assert reparsed == publication

    fresh_service = CandidateProvenanceArtifactService(
        manager.workspace,
        reconstruction.project_id,
        StateManager(manager.workspace),
    )
    resolved = fresh_service.resolve_canonical_cad(publication.artifact.artifact_id)
    assert type(resolved.payload) is CanonicalCadProvenanceV2
    assert type(resolved.payload.realization) is CanonicalCadRealizationV2
    assert resolved == publication
    assert resolved.payload.realization.realization_hash == cad.realization_hash

    _legacy_service, _legacy_reconstruction, legacy_cad, _legacy_outcome = (
        _canonical_provenance_fixture(tmp_path / "legacy-cad")
    )
    with pytest.raises(ValidationError):
        CanonicalCadProvenanceV2.model_validate(
            serialized["payload"]
            | {"realization": legacy_cad.model_dump(mode="json")}
        )


def test_canonical_m10_provenance_v2_round_trips_and_resolves_fresh_service(
    tmp_path,
):
    from mechcad_harness.candidates.canonical_m10 import (
        CanonicalM10VerificationOutcomeV2,
    )
    from mechcad_harness.candidates.provenance_artifacts import (
        CanonicalCadProvenanceV2,
        CanonicalM10ProvenancePublication,
        CanonicalM10ProvenanceV2,
        CandidateProvenanceArtifactService,
    )

    service, manager, reconstruction, cad, outcome, _application = (
        _canonical_provenance_v2_fixture(tmp_path)
    )
    cad_publication = service.publish_canonical_cad(reconstruction, cad)
    publication = service.publish_canonical_m10(cad_publication, outcome)

    serialized = publication.model_dump(mode="json")
    assert set(CanonicalM10ProvenanceV2.model_fields) == {
        "schema_version",
        "outcome",
        "canonical_cad",
        "proof_evidence",
        "home_evidence",
    }
    assert serialized["payload"]["schema_version"] == "canonical-m10-provenance@2"
    assert serialized["payload"]["outcome"]["schema_version"] == (
        "canonical-m10-verification-outcome@2"
    )
    assert set(serialized["payload"]) == set(CanonicalM10ProvenanceV2.model_fields)
    assert not {"provenance_hash", "semantic_hash"} & set(serialized["payload"])
    assert publication.artifact.input_hash == outcome.outcome_hash
    reparsed = CanonicalM10ProvenancePublication.model_validate(serialized)
    assert reparsed == publication

    fresh_service = CandidateProvenanceArtifactService(
        manager.workspace,
        reconstruction.project_id,
        StateManager(manager.workspace),
    )
    resolved = fresh_service.resolve_canonical_m10(publication.artifact.artifact_id)
    assert type(resolved.payload) is CanonicalM10ProvenanceV2
    assert type(resolved.payload.outcome) is CanonicalM10VerificationOutcomeV2
    assert type(
        fresh_service.resolve_canonical_cad(
            resolved.payload.canonical_cad.artifact
        ).payload
    ) is CanonicalCadProvenanceV2
    assert resolved.payload.outcome.outcome_hash == outcome.outcome_hash
    assert (
        resolved.payload.canonical_cad.artifact
        == cad_publication.artifact
    )

    _legacy_service, _legacy_reconstruction, _legacy_cad, legacy_outcome = (
        _canonical_provenance_fixture(tmp_path / "legacy-m10")
    )
    with pytest.raises(ValidationError):
        CanonicalM10ProvenanceV2.model_validate(
            serialized["payload"]
            | {"outcome": legacy_outcome.model_dump(mode="json")}
        )


def test_canonical_m10_provenance_v2_rejects_cad_parent_revision_mismatch(
    tmp_path,
):
    from mechcad_harness.candidates.canonical_cad import CanonicalPhysicalCadCompiler
    from mechcad_harness.candidates.canonical_m10 import CanonicalM10VerificationService
    from mechcad_harness.candidates.canonical_mechanism import (
        CanonicalMechanismReconstruction,
        ProjectArtifactResolver,
    )
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateProvenanceArtifactService,
        CandidateProvenanceIntegrityError,
        CanonicalM10ProvenanceV2,
    )

    service, manager, reconstruction, cad_at_revision_1, _outcome_1, application = (
        _canonical_provenance_v2_fixture(tmp_path)
    )
    cad_publication_at_revision_1 = service.publish_canonical_cad(
        reconstruction, cad_at_revision_1
    )

    state_at_revision_1 = manager.load_revision(
        reconstruction.project_id, reconstruction.revision
    )
    snapshot_2 = manager.create_revision(
        reconstruction.project_id,
        state_at_revision_1.model_copy(update={"revision": reconstruction.revision + 1}),
    )
    reconstruction_2 = CanonicalMechanismReconstruction.model_validate(
        reconstruction.model_dump(mode="python")
        | {"revision": snapshot_2.revision, "state_hash": snapshot_2.state_hash}
    )
    resolver = ProjectArtifactResolver(
        ArtifactStore(
            manager.workspace,
            project_id=reconstruction.project_id,
            run_id="PROVENANCE-V2-REVISION-2-LOOKUP",
        )
    )
    cad_at_revision_2 = CanonicalPhysicalCadCompiler(resolver).realize(
        reconstruction_2
    )
    outcome_at_revision_2 = CanonicalM10VerificationService(application).execute(
        reconstruction_2, cad_at_revision_2
    )
    proof_evidence, home_evidence = _canonical_m10_v2_evidence_records(
        manager.workspace, outcome_at_revision_2
    )

    forged_inventory_payload = outcome_at_revision_2.inventory.model_dump(mode="json")
    forged_inventory_payload.update(
        {
            "cad_realization_hash": cad_at_revision_1.realization_hash,
            "inventory_hash": "pending",
        }
    )
    forged_inventory = type(outcome_at_revision_2.inventory).model_validate(
        forged_inventory_payload
    )
    forged_request_payload = outcome_at_revision_2.request.model_dump(mode="json")
    forged_request_payload.update(
        {
            "cad_realization_hash": cad_at_revision_1.realization_hash,
            "inventory": forged_inventory.model_dump(mode="json"),
            "request_hash": "pending",
        }
    )
    forged_request = type(outcome_at_revision_2.request).model_validate(
        forged_request_payload
    )
    forged_outcome_payload = outcome_at_revision_2.model_dump(mode="json")
    forged_outcome_payload.update(
        {
            "cad_realization_hash": cad_at_revision_1.realization_hash,
            "inventory": forged_inventory.model_dump(mode="json"),
            "request": forged_request.model_dump(mode="json"),
            "outcome_hash": "pending",
        }
    )
    forged_outcome = type(outcome_at_revision_2).model_validate(
        forged_outcome_payload
    )
    assert forged_outcome.revision == cad_at_revision_2.revision
    assert forged_outcome.revision != cad_at_revision_1.revision
    assert forged_outcome.cad_realization_hash == cad_at_revision_1.realization_hash

    payload = CanonicalM10ProvenanceV2(
        outcome=forged_outcome,
        canonical_cad=ArtifactReference(artifact=cad_publication_at_revision_1.artifact),
        proof_evidence=proof_evidence,
        home_evidence=home_evidence,
    )
    artifact_id = f"CANONICAL-M10-V2{forged_outcome.outcome_hash[7:31]}"
    manifest_store = ArtifactStore(
        manager.workspace,
        project_id=reconstruction.project_id,
        run_id=cad_publication_at_revision_1.artifact.run_id,
    )
    forged_artifact = manifest_store.publish(
        artifact_id,
        ArtifactType.JSON,
        "canonical_m10_provenance_v2.json",
        canonical_json_bytes(payload.model_dump(mode="json")),
        cad_publication_at_revision_1.artifact.producer_tool_name,
        cad_publication_at_revision_1.artifact.producer_tool_version,
        forged_outcome.revision,
        forged_outcome.state_hash,
        input_hash=forged_outcome.outcome_hash,
    )
    fresh_service = CandidateProvenanceArtifactService(
        manager.workspace,
        reconstruction.project_id,
        StateManager(manager.workspace),
    )

    with pytest.raises(
        CandidateProvenanceIntegrityError,
        match="canonical M10@2 artifact identity/binding verification failed",
    ) as exc_info:
        fresh_service.resolve_canonical_m10(forged_artifact.artifact_id)
    assert str(exc_info.value.__cause__) == (
        "canonical M10@2 CAD parent coordinate binding mismatch"
    )


def test_canonical_cad_publish_rejects_unrelated_mechanism_hash(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, reconstruction, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    substituted = _cad_with_mechanism_identity(canonical_cad)

    with pytest.raises(CandidateProvenanceIntegrityError, match="mechanism hash"):
        service.publish_canonical_cad(reconstruction, substituted)


def test_canonical_cad_publish_rejects_self_consistent_reconstruction_forged_against_state(
    tmp_path,
):
    from mechcad_harness.candidates.canonical_mechanism import (
        CanonicalMechanismReconstruction,
    )
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, reconstruction, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    forged_mechanism = type(reconstruction.mechanism).model_validate(
        reconstruction.mechanism.model_dump(mode="python")
        | {"name": "forged canonical mechanism", "mechanism_hash": "pending"}
    )
    forged_reconstruction = _reconstruction_with_mechanism(
        reconstruction, forged_mechanism
    )
    forged_cad = _cad_with_mechanism_identity(
        canonical_cad, mechanism_hash=forged_mechanism.mechanism_hash
    )

    assert isinstance(forged_reconstruction, CanonicalMechanismReconstruction)
    with pytest.raises(CandidateProvenanceIntegrityError, match="reconstruction binding"):
        service.publish_canonical_cad(forged_reconstruction, forged_cad)


def test_canonical_cad_resolve_rejects_persisted_unrelated_mechanism_hash(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
        CanonicalCadProvenance,
    )

    service, _, canonical_cad, _, publication, _ = _canonical_publications(tmp_path)
    substituted = _cad_with_mechanism_identity(canonical_cad)
    payload = CanonicalCadProvenance(
        realization=substituted,
        source_step_artifacts=publication.payload.source_step_artifacts,
    )
    persisted = _republish_json_payload(
        tmp_path,
        publication.artifact,
        payload.model_dump(mode="json"),
        artifact_id="CANONICAL-CAD-" + substituted.realization_hash[7:31],
        input_hash=substituted.realization_hash,
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="mechanism hash"):
        service.resolve_canonical_cad(persisted.artifact_id)


def test_canonical_cad_publish_and_resolve_use_persisted_exact_source_scope(tmp_path):
    service, reconstruction, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    source = canonical_cad.selected_source_provenance[0]
    duplicate = ArtifactStore(
        tmp_path,
        project_id=source.project_id,
        run_id="DUPLICATE-SOURCE",
        task_id="TASK-DUPLICATE",
    ).publish(
        source.artifact_id,
        ArtifactType.STEP,
        "shaft.step",
        (tmp_path / source.relative_path).read_bytes(),
        source.producer_tool_name,
        source.producer_tool_version,
        source.bound_revision,
        source.bound_state_hash,
        input_hash=source.input_hash,
    )
    assert duplicate.sha256 == source.sha256
    assert (duplicate.run_id, duplicate.task_id) != (source.run_id, source.task_id)

    published = service.publish_canonical_cad(reconstruction, canonical_cad)
    resolved = service.resolve_canonical_cad(published.artifact.artifact_id)

    assert resolved.payload.realization == canonical_cad


def test_canonical_cad_source_bindings_are_identity_keyed_and_restart_resolvable(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import CanonicalCadProvenance

    service, reconstruction, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    reordered = tuple(reversed(canonical_cad.selected_source_provenance))

    publication = service.publish_canonical_cad(
        reconstruction,
        canonical_cad,
        trusted_source_references=reordered,
    )

    assert tuple(
        source.artifact_id for source in publication.payload.source_step_artifacts
    ) == canonical_cad.selected_source_artifact_ids
    reordered_payload = CanonicalCadProvenance(
        realization=canonical_cad,
        source_step_artifacts=tuple(
            reversed(publication.payload.source_step_artifacts)
        ),
    )
    assert reordered_payload.realization == canonical_cad

    restarted_service = type(service)(
        tmp_path,
        reconstruction.project_id,
        StateManager(tmp_path),
    )
    resolved = restarted_service.resolve_canonical_cad(
        publication.artifact.artifact_id
    )
    assert resolved.payload.realization == canonical_cad


def test_canonical_source_binding_normalization_is_order_independent(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        _canonical_source_bindings,
    )

    _, _, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    first = canonical_cad.selected_source_provenance[0]
    second = first.model_copy(
        update={
            "artifact_id": "SECOND-SOURCE-ARTIFACT",
            "sha256": "sha256:" + "2" * 64,
        }
    )

    assert _canonical_source_bindings((first, second)) == _canonical_source_bindings(
        (second, first)
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "extra",
        "duplicate",
        "artifact_id",
        "sha256",
        "bound_revision",
        "bound_state_hash",
        "producer_tool_name",
        "task_id",
    ),
)
def test_canonical_cad_source_bindings_remain_strict_after_order_normalization(
    tmp_path, mutation
):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
    )

    service, reconstruction, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    sources = tuple(canonical_cad.selected_source_provenance)
    source = sources[0]
    if mutation == "missing":
        supplied = sources[1:]
    elif mutation == "extra":
        supplied = (
            source.model_copy(update={"artifact_id": "EXTRA-SOURCE-ARTIFACT"}),
            *sources[1:],
        )
    elif mutation == "duplicate":
        supplied = sources + (source,)
    else:
        updates = {
            "artifact_id": "WRONG-SOURCE-ARTIFACT",
            "sha256": "sha256:" + "0" * 64,
            "bound_revision": source.bound_revision + 1,
            "bound_state_hash": "sha256:" + "1" * 64,
            "producer_tool_name": "wrong-provider",
            "task_id": "wrong-task",
        }
        supplied = (source.model_copy(update={mutation: updates[mutation]}), *sources[1:])

    with pytest.raises(CandidateProvenanceIntegrityError):
        service.publish_canonical_cad(
            reconstruction,
            canonical_cad,
            trusted_source_references=supplied,
        )


def test_canonical_cad_publish_rejects_wrong_scope_source_snapshot(tmp_path):
    from mechcad_harness.candidates.canonical_mechanism import TrustedSourceArtifact
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
    )

    service, reconstruction, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    source = canonical_cad.selected_source_provenance[0]
    duplicate = ArtifactStore(
        tmp_path,
        project_id=source.project_id,
        run_id="DUPLICATE-SOURCE",
        task_id="TASK-DUPLICATE",
    ).publish(
        source.artifact_id,
        ArtifactType.STEP,
        "shaft.step",
        (tmp_path / source.relative_path).read_bytes(),
        source.producer_tool_name,
        source.producer_tool_version,
        source.bound_revision,
        source.bound_state_hash,
        input_hash=source.input_hash,
    )
    wrong_scope = reconstruction.model_copy(
        update={
            "trusted_source_references": (
                TrustedSourceArtifact.from_artifact(duplicate),
            )
        }
    )

    with pytest.raises(CandidateProvenanceIntegrityError):
        service.publish_canonical_cad(wrong_scope, canonical_cad)


def test_canonical_m10_publish_rejects_unrelated_mechanism_identity(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, _, canonical_cad, outcome = _canonical_provenance_fixture(tmp_path)
    cad_publication = service.publish_canonical_cad(canonical_cad)
    substituted = _outcome_with_mechanism_identity(outcome)

    with pytest.raises(CandidateProvenanceIntegrityError, match="mechanism"):
        service.publish_canonical_m10(cad_publication, substituted)


def test_canonical_m10_publish_rejects_outcome_revision_state_substitution(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, _, canonical_cad, outcome = _canonical_provenance_fixture(tmp_path)
    cad_publication = service.publish_canonical_cad(canonical_cad)
    prior_state = service.state_manager.load_revision(outcome.project_id, 1)
    substituted = _outcome_with_revision_state(
        outcome, revision=1, state_hash=state_hash(prior_state)
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="revision/state"):
        service.publish_canonical_m10(cad_publication, substituted)


def test_canonical_m10_resolve_rejects_persisted_unrelated_mechanism_identity(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
        CanonicalM10Provenance,
    )

    service, _, _, outcome, cad_publication, publication = _canonical_publications(tmp_path)
    substituted = _outcome_with_mechanism_identity(outcome)
    payload = CanonicalM10Provenance(
        outcome=substituted,
        canonical_cad=publication.payload.canonical_cad,
        proof_evidence=publication.payload.proof_evidence,
        home_evidence=publication.payload.home_evidence,
    )
    persisted = _republish_json_payload(
        tmp_path,
        publication.artifact,
        payload.model_dump(mode="json"),
        artifact_id="CANONICAL-M10-" + substituted.outcome_hash[7:31],
        input_hash=substituted.outcome_hash,
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="mechanism"):
        service.resolve_canonical_m10(persisted.artifact_id)


def test_canonical_m10_resolve_rejects_persisted_outcome_revision_state_substitution(
    tmp_path,
):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, _, _, outcome, _, publication = _canonical_publications(tmp_path)
    prior_state = service.state_manager.load_revision(outcome.project_id, 1)
    substituted = _outcome_with_revision_state(
        outcome, revision=1, state_hash=state_hash(prior_state)
    )
    payload = json.loads(
        (tmp_path / publication.artifact.relative_path).read_text(encoding="utf-8")
    )
    payload["outcome"] = substituted.model_dump(mode="json")
    persisted = _republish_json_payload(
        tmp_path,
        publication.artifact,
        payload,
        artifact_id="CANONICAL-M10-" + substituted.outcome_hash[7:31],
        input_hash=substituted.outcome_hash,
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="canonical M10 artifact verification"):
        service.resolve_canonical_m10(persisted.artifact_id)


def test_canonical_publications_reject_copied_scope_and_nested_cad_scope(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateProvenanceIntegrityError,
    )

    service, _, _, _, cad_publication, m10_publication = _canonical_publications(tmp_path)
    assert (cad_publication.artifact.project_id, cad_publication.artifact.run_id, cad_publication.artifact.task_id) == (
        service.project_id,
        "CANONICAL",
        None,
    )
    assert (m10_publication.artifact.project_id, m10_publication.artifact.run_id, m10_publication.artifact.task_id) == (
        service.project_id,
        "CANONICAL",
        None,
    )

    cad_path = tmp_path / cad_publication.artifact.relative_path
    copied_cad = ArtifactStore(
        tmp_path,
        project_id=service.project_id,
        run_id="COPIED-CANONICAL",
        task_id="COPIED-TASK",
    ).publish(
        cad_publication.artifact.artifact_id,
        ArtifactType.JSON,
        "canonical_cad_provenance.json",
        cad_path.read_bytes(),
        cad_publication.artifact.producer_tool_name,
        cad_publication.artifact.producer_tool_version,
        cad_publication.artifact.bound_revision,
        cad_publication.artifact.bound_state_hash,
        input_hash=cad_publication.artifact.input_hash,
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="scope"):
        service.resolve_canonical_cad(copied_cad)

    m10_payload = json.loads(
        (tmp_path / m10_publication.artifact.relative_path).read_text(encoding="utf-8")
    )
    m10_payload["canonical_cad"] = ArtifactReference(
        artifact=copied_cad
    ).model_dump(mode="json")
    _replace_persisted_payload(tmp_path, m10_publication.artifact, m10_payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="scope"):
        service.resolve_canonical_m10(m10_publication.artifact.artifact_id)


def test_named_promoted_candidate_chain_resolver_is_public_api(tmp_path, monkeypatch):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceArtifactService

    service = CandidateProvenanceArtifactService(tmp_path, "PRJ-CHAIN", object())
    expected = object()
    monkeypatch.setattr(
        service,
        "resolve_selection_for_promotion",
        lambda **kwargs: expected,
    )

    assert service.resolve_promoted_candidate_chain(
        decision=object(), result_manifest=object()
    ) is expected


def test_canonical_m10_round_trip_requires_home_evidence_when_home_check_is_bound(tmp_path):
    service, _, canonical_cad, outcome = _canonical_provenance_fixture(
        tmp_path, requires_home=True
    )

    cad_publication = service.publish_canonical_cad(canonical_cad)
    publication = service.publish_canonical_m10(cad_publication, outcome)
    resolved = service.resolve_canonical_m10(publication.artifact.artifact_id)

    assert len(resolved.payload.proof_evidence) == len(outcome.pair_proofs)
    assert len(resolved.payload.home_evidence) == len(outcome.home_exact_checks)


def test_canonical_cad_round_trip_preserves_selected_source_execution_reference(tmp_path):
    service, _, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)

    publication = service.publish_canonical_cad(canonical_cad)
    resolved = service.resolve_canonical_cad(publication.artifact.artifact_id)

    assert resolved.payload.realization == canonical_cad
    assert tuple(item.run_id for item in resolved.payload.source_step_artifacts) == tuple(
        item.run_id for item in canonical_cad.selected_source_provenance
    )


def test_canonical_m10_publication_rejects_missing_evidence(tmp_path):
    service, _, canonical_cad, outcome = _canonical_provenance_fixture(tmp_path)
    cad_publication = service.publish_canonical_cad(canonical_cad)
    proof = outcome.pair_proofs[0]
    evidence_id = "EVD-CPROOF-" + hashlib.sha256(
        (proof.request_hash + proof.result_hash).encode()
    ).hexdigest()[:24]
    (tmp_path / "projects" / outcome.project_id / "evidence" / f"{evidence_id}.json").unlink()

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="evidence"):
        service.publish_canonical_m10(cad_publication, outcome)


def test_canonical_m10_resolver_rejects_evidence_result_substitution(tmp_path):
    service, _, canonical_cad, outcome = _canonical_provenance_fixture(tmp_path)
    cad_publication = service.publish_canonical_cad(canonical_cad)
    publication = service.publish_canonical_m10(cad_publication, outcome)
    evidence_id = publication.payload.proof_evidence[0].id
    evidence_path = (
        tmp_path
        / "projects"
        / outcome.project_id
        / "evidence"
        / f"{evidence_id}.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["producer_result_id"] = "sha256:" + "0" * 64
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="evidence"):
        service.resolve_canonical_m10(publication.artifact.artifact_id)


def test_canonical_cad_resolver_rechecks_bound_revision_state_hash(tmp_path, monkeypatch):
    service, _, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    publication = service.publish_canonical_cad(canonical_cad)
    original_load_revision = service.state_manager.load_revision

    def load_forged_state(project_id, revision):
        state = original_load_revision(project_id, revision)
        return state.model_copy(update={"revision": revision + 1})

    monkeypatch.setattr(service.state_manager, "load_revision", load_forged_state)
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="source state mismatch"):
        service.resolve_canonical_cad(publication.artifact.artifact_id)


def test_canonical_cad_resolver_rejects_missing_selected_step(tmp_path):
    service, _, canonical_cad, _ = _canonical_provenance_fixture(tmp_path)
    publication = service.publish_canonical_cad(canonical_cad)
    source = canonical_cad.selected_source_provenance[0]
    (tmp_path / source.relative_path).unlink()

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="source STEP"):
        service.resolve_canonical_cad(publication.artifact.artifact_id)


@pytest.mark.parametrize("kind", ("cad", "m10"))
def test_canonical_resolver_rejects_tampered_top_level_bytes(tmp_path, kind):
    service, _, _, _, cad_publication, m10_publication = _canonical_publications(tmp_path)
    publication = cad_publication if kind == "cad" else m10_publication
    (tmp_path / publication.artifact.relative_path).write_bytes(b"tampered-canonical-bytes")

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    resolver = service.resolve_canonical_cad if kind == "cad" else service.resolve_canonical_m10
    with pytest.raises(CandidateProvenanceIntegrityError, match=f"(?i)canonical {kind}"):
        resolver(publication.artifact.artifact_id)


@pytest.mark.parametrize("kind", ("cad", "m10"))
def test_canonical_resolver_rejects_persisted_top_level_project_mismatch(tmp_path, kind):
    service, _, _, _, cad_publication, m10_publication = _canonical_publications(tmp_path)
    publication = cad_publication if kind == "cad" else m10_publication
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    foreign_service = type(service)(tmp_path, "OTHER-PROJECT", service.state_manager)
    resolver = foreign_service.resolve_canonical_cad if kind == "cad" else foreign_service.resolve_canonical_m10
    with pytest.raises(CandidateProvenanceIntegrityError, match="project mismatch"):
        resolver(publication.artifact)


@pytest.mark.parametrize("field", ("bound_revision", "bound_state_hash"))
def test_canonical_cad_resolver_rejects_persisted_source_revision_state_mismatch(
    tmp_path, field
):
    service, _, _, _, publication, _ = _canonical_publications(tmp_path)
    metadata_path = (tmp_path / publication.artifact.relative_path).parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata[field] = 99 if field == "bound_revision" else "sha256:" + "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="metadata binding"):
        service.resolve_canonical_cad(publication.artifact.artifact_id)


def test_canonical_m10_resolver_rejects_altered_canonical_cad_realization_identity(tmp_path):
    service, _, _, _, _, publication = _canonical_publications(tmp_path)
    payload = json.loads((tmp_path / publication.artifact.relative_path).read_text(encoding="utf-8"))
    payload["outcome"]["cad_realization_hash"] = "sha256:" + "0" * 64
    _replace_persisted_payload(tmp_path, publication.artifact, payload)

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="canonical M10 artifact verification"):
        service.resolve_canonical_m10(publication.artifact.artifact_id)


@pytest.mark.parametrize("evidence_group", ("proof_evidence", "home_evidence"))
def test_canonical_m10_resolver_rejects_omitted_required_evidence(tmp_path, evidence_group):
    service, _, _, _, _, publication = _canonical_publications(
        tmp_path, requires_home=evidence_group == "home_evidence"
    )
    payload = json.loads((tmp_path / publication.artifact.relative_path).read_text(encoding="utf-8"))
    payload[evidence_group] = []
    _replace_persisted_payload(tmp_path, publication.artifact, payload)

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="evidence coverage"):
        service.resolve_canonical_m10(publication.artifact.artifact_id)


@pytest.mark.parametrize("field", ("input_hash", "output_hash", "producer_result_id"))
def test_canonical_m10_resolver_rejects_evidence_request_result_mismatch(tmp_path, field):
    service, _, _, outcome, _, publication = _canonical_publications(tmp_path)
    proof = outcome.pair_proofs[0]
    evidence_id = publication.payload.proof_evidence[0].id
    evidence_path = tmp_path / "projects" / outcome.project_id / "evidence" / f"{evidence_id}.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence[field] = "sha256:" + "0" * 64
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="M10 evidence binding mismatch"):
        service.resolve_canonical_m10(publication.artifact.artifact_id)


def test_canonical_m10_resolver_rejects_altered_inventory(tmp_path):
    service, _, _, _, _, publication = _canonical_publications(tmp_path)
    payload = json.loads((tmp_path / publication.artifact.relative_path).read_text(encoding="utf-8"))
    payload["outcome"]["inventory"]["checked_pairs"] = []
    _replace_persisted_payload(tmp_path, publication.artifact, payload)

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="canonical M10 artifact verification"):
        service.resolve_canonical_m10(publication.artifact.artifact_id)


def test_canonical_m10_resolver_rejects_incomplete_pair_proof_coverage(tmp_path):
    service, _, _, _, _, publication = _canonical_publications(tmp_path)
    payload = json.loads((tmp_path / publication.artifact.relative_path).read_text(encoding="utf-8"))
    payload["outcome"]["pair_proofs"] = []
    _replace_persisted_payload(tmp_path, publication.artifact, payload)

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="canonical M10 artifact verification"):
        service.resolve_canonical_m10(publication.artifact.artifact_id)


def test_canonical_m10_resolver_rejects_foreign_pair_result_hash(tmp_path):
    service, _, _, _, _, publication = _canonical_publications(tmp_path)
    payload = json.loads((tmp_path / publication.artifact.relative_path).read_text(encoding="utf-8"))
    payload["outcome"]["pair_proofs"][0]["result_hash"] = "sha256:" + "f" * 64
    _replace_persisted_payload(tmp_path, publication.artifact, payload)

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError, match="canonical M10 artifact verification"):
        service.resolve_canonical_m10(publication.artifact.artifact_id)


def test_canonical_publication_replay_preserves_artifact_identity(tmp_path):
    service, _, canonical_cad, outcome, cad_publication, m10_publication = _canonical_publications(
        tmp_path
    )

    replayed_cad = service.publish_canonical_cad(canonical_cad)
    replayed_m10 = service.publish_canonical_m10(replayed_cad, outcome)

    assert replayed_cad.artifact == cad_publication.artifact
    assert replayed_m10.artifact == m10_publication.artifact
    assert service.resolve_canonical_cad(replayed_cad.artifact.artifact_id).artifact == cad_publication.artifact
    assert service.resolve_canonical_m10(replayed_m10.artifact.artifact_id).artifact == m10_publication.artifact


def test_canonical_m10_resolver_recomputes_rehashed_nested_proof_metric(tmp_path):
    service, _, _, outcome, _, publication = _canonical_publications(tmp_path)
    payload = json.loads((tmp_path / publication.artifact.relative_path).read_text(encoding="utf-8"))
    proof_payload = payload["outcome"]["pair_proofs"][0]
    certificate = proof_payload["result"]["certified_leaf_certificates"][0]
    certificate["pair_certificates"][0]["certified_lower_clearance_mm"] = 8.8
    certificate["minimum_certified_lower_clearance_mm"] = 8.8
    proof_payload["result"]["result_hash"] = "pending"
    proof_payload["proof_hash"] = "pending"

    from mechcad_harness.candidates.canonical_m10 import (
        CanonicalM10PairProof,
        CanonicalM10VerificationOutcome,
        canonical_m10_aggregate_summary,
    )
    from mechcad_harness.candidates.m10_result_validation import m10_result_hash
    from mechcad_harness.continuous_proof import ContinuousSingleAxisProofResult
    from mechcad_harness.models.evidence import Evidence
    from mechcad_harness.candidates.provenance_artifacts import CanonicalM10Provenance

    result = ContinuousSingleAxisProofResult.model_validate(proof_payload["result"])
    result = result.model_copy(update={"result_hash": m10_result_hash(result)})
    proof_payload["result"] = result.model_dump(mode="json")
    proof_payload["result_hash"] = result.result_hash
    proof = CanonicalM10PairProof.model_validate(proof_payload)
    outcome_payload = payload["outcome"] | {
        "pair_proofs": [proof.model_dump(mode="json")],
        "outcome_hash": "pending",
    }
    rehashed_outcome = CanonicalM10VerificationOutcome.model_validate(outcome_payload)
    changed_proof = rehashed_outcome.pair_proofs[0]
    evidence_id = "EVD-CPROOF-" + hashlib.sha256(
        (changed_proof.request_hash + changed_proof.result_hash).encode()
    ).hexdigest()[:24]
    evidence_dir = tmp_path / "projects" / outcome.project_id / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / f"{evidence_id}.json").write_text(
        Evidence(
            id=evidence_id,
            kind="analysis.continuous_clearance_proof",
            summary="rehashed canonical proof fixture",
            revision=outcome.revision,
            state_hash=outcome.state_hash,
            producer_result_id=changed_proof.result_hash,
            input_hash=changed_proof.request_hash,
            output_hash=changed_proof.result_hash,
        ).model_dump_json(exclude_none=True),
        encoding="utf-8",
    )
    payload["outcome"] = rehashed_outcome.model_dump(mode="json")
    payload["proof_evidence"] = [
        Evidence.model_validate_json((evidence_dir / f"{evidence_id}.json").read_text(encoding="utf-8")).model_dump(mode="json")
    ]
    rehashed_payload = CanonicalM10Provenance.model_validate(payload)
    rehashed_artifact = _republish_json_payload(
        tmp_path,
        publication.artifact,
        rehashed_payload.model_dump(mode="json"),
        artifact_id="CANONICAL-M10-" + rehashed_outcome.outcome_hash[7:31],
        input_hash=rehashed_outcome.outcome_hash,
    )

    resolved = service.resolve_canonical_m10(rehashed_artifact.artifact_id)

    _, limiting_metric, limiting_pair = canonical_m10_aggregate_summary(
        resolved.payload.outcome
    )
    assert limiting_metric == 8.8
    assert limiting_pair == (
        changed_proof.moving_instance_id,
        changed_proof.stationary_instance_id,
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "source-revision",
        "source-state",
        "mapping-candidate-hash",
        "mapping-geometry-definition",
        "missing-candidate-publication",
        "wrong-artifact-type",
    ),
)
def test_candidate_cad_resolver_rejects_persisted_dependency_mutations(tmp_path, mutation):
    service, _, published = _evaluation_fixture(tmp_path)
    cad = published.payload.candidate_cad.artifact
    payload = json.loads((tmp_path / cad.relative_path).read_text(encoding="utf-8"))
    if mutation == "source-revision":
        payload["request"]["source_binding"]["source_revision"] += 1
    elif mutation == "source-state":
        payload["request"]["source_binding"]["source_state_hash"] = "sha256:" + "0" * 64
    elif mutation == "mapping-candidate-hash":
        payload["realization"]["mappings"][0]["candidate_hash"] = "sha256:" + "0" * 64
    elif mutation == "mapping-geometry-definition":
        forged_identity = "FORGED-GEOMETRY-DEFINITION"
        for section in ("request", "realization"):
            payload[section]["mappings"][0]["geometry_definition_identities"] = [
                forged_identity
            ]
            payload[section]["mappings"][0]["mapping_hash"] = "pending"
        payload["request"]["request_hash"] = "pending"
        payload["realization"]["realization_hash"] = "pending"
    elif mutation == "missing-candidate-publication":
        reference = payload["candidate_artifact"]
        reference["artifact"]["artifact_id"] = "MISSING-CANDIDATE-PUBLICATION"
        reference["artifact_id"] = "MISSING-CANDIDATE-PUBLICATION"
    else:
        metadata_path = (tmp_path / cad.relative_path).parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["artifact_type"] = ArtifactType.STEP.value
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        with pytest.raises(__import__("mechcad_harness.candidates.provenance_artifacts", fromlist=["CandidateProvenanceIntegrityError"]).CandidateProvenanceIntegrityError):
            service.resolve_candidate_cad(cad.artifact_id)
        return
    _replace_persisted_payload(tmp_path, cad, payload)
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError
    expected = {
        "source-revision": "source|binding",
        "source-state": "source|binding",
        "mapping-candidate-hash": "identity|binding",
        "mapping-geometry-definition": "identity|binding",
        "missing-candidate-publication": "candidate publication|missing|artifact",
        "wrong-artifact-type": "type",
    }[mutation]
    with pytest.raises(CandidateProvenanceIntegrityError, match=f"(?i){expected}"):
        service.resolve_candidate_cad(cad.artifact_id)


@pytest.mark.parametrize(
    "mutation",
    (
        "omitted-proof",
        "wrong-producer-result",
        "wrong-evidence-id",
        "evaluation-cad-hash",
        "omitted-home",
        "tampered-home",
    ),
)
def test_candidate_evaluation_resolver_rejects_persisted_evidence_and_cad_mutations(tmp_path, mutation):
    service, candidate, published = _evaluation_fixture(
        tmp_path, required_home=mutation in ("omitted-home", "tampered-home")
    )
    if mutation in ("wrong-producer-result", "wrong-evidence-id", "tampered-home"):
        evidence = (
            published.payload.proof_evidence[0]
            if mutation in ("wrong-producer-result", "wrong-evidence-id")
            else published.payload.home_evidence[0]
        )
        path = tmp_path / "projects" / candidate.source_binding.project_id / "evidence" / f"{evidence.id}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        if mutation == "wrong-evidence-id":
            raw["id"] = "EVD-FORGED-ID"
        else:
            raw["producer_result_id"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(raw), encoding="utf-8")
    else:
        payload = json.loads((tmp_path / published.artifact.relative_path).read_text(encoding="utf-8"))
        if mutation == "omitted-proof":
            payload["proof_evidence"] = []
        elif mutation == "omitted-home":
            assert published.payload.home_evidence
            payload["home_evidence"] = []
        else:
            payload["evaluation"]["cad_realization_hash"] = "sha256:" + "0" * 64
        _replace_persisted_payload(tmp_path, published.artifact, payload)
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError
    expected = {
        "omitted-proof": "evidence",
        "wrong-producer-result": "evidence",
        "wrong-evidence-id": "evidence",
        "evaluation-cad-hash": "identity|binding",
        "omitted-home": "evidence",
        "tampered-home": "evidence",
    }[mutation]
    with pytest.raises(CandidateProvenanceIntegrityError, match=f"(?i){expected}"):
        service.resolve_candidate_evaluation(published.artifact.artifact_id)


def test_publish_candidate_evaluation_reopens_supplied_cad_publication(tmp_path):
    service, _, published = _evaluation_fixture(tmp_path)
    cad = service.resolve_candidate_cad(published.payload.candidate_cad.artifact)
    payload = json.loads((tmp_path / cad.artifact.relative_path).read_text(encoding="utf-8"))
    payload["candidate_artifact"]["artifact"]["artifact_id"] = "MISSING-CANDIDATE-PUBLICATION"
    payload["candidate_artifact"]["artifact_id"] = "MISSING-CANDIDATE-PUBLICATION"
    _replace_persisted_payload(tmp_path, cad.artifact, payload)

    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    with pytest.raises(CandidateProvenanceIntegrityError):
        service.publish_candidate_evaluation(cad, published.payload.evaluation)


@pytest.mark.parametrize("mutation", ("reordered-pairs", "metric-mismatch"))
def test_candidate_comparison_resolver_rejects_persisted_pair_and_metric_mutations(tmp_path, mutation):
    from mechcad_harness.candidates import CandidateComparisonService
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError
    state = make_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    service, first_candidate, first = _published_evaluation(tmp_path, manager, state, suffix="first")
    _, second_candidate, second = _published_evaluation(tmp_path, manager, state, suffix="second")
    policy = comparison_policy()
    entries = ((first_candidate, first.payload.evaluation), (second_candidate, second.payload.evaluation))
    request = comparison_request(policy, entries)
    result = CandidateComparisonService(
        policy, project_id="PRJ-M12", currentness_verifier=StateBackedCurrentnessVerifier(manager)
    ).compare(request, entries)
    published = service.publish_candidate_comparison(request, result, (first.artifact, second.artifact))
    payload = json.loads((tmp_path / published.artifact.relative_path).read_text(encoding="utf-8"))
    if mutation == "reordered-pairs":
        payload["request"]["candidate_evaluation_pairs"].reverse()
    else:
        payload["result"]["metric_values"][0][1] += 1.0
    _replace_persisted_payload(tmp_path, published.artifact, payload)
    expected = "pair|request|binding" if mutation == "reordered-pairs" else "comparison|result|metric"
    with pytest.raises(CandidateProvenanceIntegrityError, match=f"(?i){expected}"):
        service.resolve_candidate_comparison(published.artifact.artifact_id)


def test_candidate_selection_resolver_rejects_persisted_comparison_mismatch(tmp_path):
    from mechcad_harness.candidates import CandidateComparisonService, CandidateSelectionService
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError
    state = make_state()
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    service, first_candidate, first = _published_evaluation(tmp_path, manager, state, suffix="first")
    _, second_candidate, second = _published_evaluation(tmp_path, manager, state, suffix="second")
    policy = comparison_policy()
    entries = ((first_candidate, first.payload.evaluation), (second_candidate, second.payload.evaluation))
    request = comparison_request(policy, entries)
    comparison = CandidateComparisonService(
        policy, project_id="PRJ-M12", currentness_verifier=StateBackedCurrentnessVerifier(manager)
    ).compare(request, entries)
    comparison_artifact = service.publish_candidate_comparison(request, comparison, (first.artifact, second.artifact))
    selection = CandidateSelectionService(
        project_id="PRJ-M12", currentness_verifier=SelectionCurrentnessVerifier(manager)
    ).select(first_candidate, first.payload.evaluation, "reviewer", "Persisted mismatch test.", comparison, entries)
    published = service.publish_candidate_selection(selection, first.payload.candidate_cad.artifact, first.artifact, comparison_artifact.artifact)
    payload = json.loads((tmp_path / published.artifact.relative_path).read_text(encoding="utf-8"))
    payload["selection"]["comparison_result_hash"] = "sha256:" + "0" * 64
    payload["selection"]["selection_hash"] = "pending"
    _replace_persisted_payload(tmp_path, published.artifact, payload)
    with pytest.raises(CandidateProvenanceIntegrityError, match="(?i)(comparison|identity|binding)"):
        service.resolve_candidate_selection(published.artifact.artifact_id)


def test_candidate_evaluation_resolver_rejects_nested_cad_scope_replay(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        ArtifactReference,
        CandidateProvenanceIntegrityError,
    )

    service, _, published = _evaluation_fixture(tmp_path)
    cad = service.resolve_candidate_cad(published.payload.candidate_cad.artifact)
    cad_path = tmp_path / cad.artifact.relative_path
    wrong_scope = ArtifactStore(
        tmp_path,
        project_id=cad.artifact.project_id,
        run_id="FOREIGN-CAD-RUN",
        task_id="FOREIGN-CAD-TASK",
    ).publish(
        cad.artifact.artifact_id,
        ArtifactType.JSON,
        "candidate_cad_provenance.json",
        cad_path.read_bytes(),
        cad.artifact.producer_tool_name,
        cad.artifact.producer_tool_version,
        cad.artifact.bound_revision,
        cad.artifact.bound_state_hash,
        input_hash=cad.artifact.input_hash,
    )
    evaluation_payload = json.loads(
        (tmp_path / published.artifact.relative_path).read_text(encoding="utf-8")
    )
    evaluation_payload["candidate_cad"] = ArtifactReference(
        artifact=wrong_scope
    ).model_dump(mode="json")
    _replace_persisted_payload(tmp_path, published.artifact, evaluation_payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="scope"):
        service.resolve_candidate_evaluation(published.artifact.artifact_id)


def _provenance_boundary_fixture(tmp_path, boundary):
    if boundary == "candidate-cad":
        service, _, published = _evaluation_fixture(tmp_path)
        return service, published.payload.candidate_cad.artifact, service.resolve_candidate_cad
    if boundary == "candidate-evaluation":
        service, _, published = _evaluation_fixture(tmp_path)
        return service, published.artifact, service.resolve_candidate_evaluation
    if boundary in {"candidate-comparison", "candidate-selection"}:
        from mechcad_harness.candidates import CandidateComparisonService, CandidateSelectionService
        state = make_state()
        manager = StateManager(tmp_path)
        manager.create_project("PRJ-M12", state)
        service, first_candidate, first = _published_evaluation(
            tmp_path, manager, state, suffix="matrix-first"
        )
        _, second_candidate, second = _published_evaluation(
            tmp_path, manager, state, suffix="matrix-second"
        )
        policy = comparison_policy()
        entries = ((first_candidate, first.payload.evaluation), (second_candidate, second.payload.evaluation))
        request = comparison_request(policy, entries)
        comparison = CandidateComparisonService(
            policy,
            project_id="PRJ-M12",
            currentness_verifier=StateBackedCurrentnessVerifier(manager),
        ).compare(request, entries)
        comparison_publication = service.publish_candidate_comparison(
            request, comparison, (first.artifact, second.artifact)
        )
        selection = CandidateSelectionService(
            project_id="PRJ-M12",
            currentness_verifier=SelectionCurrentnessVerifier(manager),
        ).select(
            first_candidate,
            first.payload.evaluation,
            "matrix-selector",
            "persisted matrix selection",
            comparison,
            entries,
        )
        selection_publication = service.publish_candidate_selection(
            selection,
            first.payload.candidate_cad.artifact,
            first.artifact,
            comparison_publication.artifact,
        )
        publication = (
            comparison_publication
            if boundary == "candidate-comparison"
            else selection_publication
        )
        resolver = (
            service.resolve_candidate_comparison
            if boundary == "candidate-comparison"
            else service.resolve_candidate_selection
        )
        return service, publication.artifact, resolver
    if boundary == "canonical-cad":
        service, _, _, _, publication, _ = _canonical_publications(tmp_path)
        return service, publication.artifact, service.resolve_canonical_cad
    if boundary == "canonical-m10":
        service, _, _, _, _, publication = _canonical_publications(tmp_path)
        return service, publication.artifact, service.resolve_canonical_m10
    raise AssertionError(f"unknown provenance boundary: {boundary}")


def test_candidate_cad_publication_round_trip_preserves_typed_envelope(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateCadProvenancePublication,
    )

    _, artifact, resolver = _provenance_boundary_fixture(tmp_path, "candidate-cad")
    publication = resolver(artifact)

    reparsed = CandidateCadProvenancePublication.model_validate(
        publication.model_dump(mode="json")
    )

    assert reparsed.payload.schema_version == publication.payload.schema_version


@pytest.mark.parametrize(
    ("boundary", "mutation"),
    tuple(
        (boundary, mutation)
        for boundary in (
            "candidate-cad",
            "candidate-evaluation",
            "candidate-comparison",
            "candidate-selection",
            "canonical-cad",
            "canonical-m10",
        )
        for mutation in ("artifact-content", "wrong-artifact-type")
    ),
)
def test_every_persisted_provenance_boundary_rejects_top_level_mutation(
    tmp_path, boundary, mutation
):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, artifact, resolver = _provenance_boundary_fixture(tmp_path, boundary)
    artifact_path = tmp_path / artifact.relative_path
    metadata_path = artifact_path.parent / "metadata.json"
    if mutation == "artifact-content":
        artifact_path.write_bytes(b"tampered persisted provenance bytes")
    else:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["artifact_type"] = ArtifactType.STEP.value
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    expected = {
        "artifact-content": "byte/hash",
        "wrong-artifact-type": "type",
    }[mutation]
    with pytest.raises(CandidateProvenanceIntegrityError, match=f"(?i){expected}"):
        resolver(artifact)


@pytest.mark.parametrize(
    "boundary",
    (
        "candidate-cad",
        "candidate-evaluation",
        "candidate-comparison",
        "candidate-selection",
        "canonical-cad",
        "canonical-m10",
    ),
)
def test_every_persisted_provenance_boundary_rejects_nested_identity_mutation(
    tmp_path, boundary
):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, artifact, resolver = _provenance_boundary_fixture(tmp_path, boundary)
    payload = json.loads((tmp_path / artifact.relative_path).read_text(encoding="utf-8"))
    if boundary == "candidate-cad":
        payload["realization"]["candidate_hash"] = "sha256:" + "0" * 64
    elif boundary == "candidate-evaluation":
        payload["evaluation"]["candidate_hash"] = "sha256:" + "0" * 64
    elif boundary == "candidate-comparison":
        payload["result"]["metric_values"][0][1] += 1.0
    elif boundary == "candidate-selection":
        payload["selection"]["comparison_result_hash"] = "sha256:" + "0" * 64
    elif boundary == "canonical-cad":
        payload["realization"]["realization_hash"] = "sha256:" + "0" * 64
    else:
        payload["outcome"]["cad_realization_hash"] = "sha256:" + "0" * 64
    _replace_persisted_payload(tmp_path, artifact, payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="(?i)(identity|binding)"):
        resolver(artifact.artifact_id)


_SUPPORTED_DEPENDENCY_MUTATIONS = (
    # Candidate CAD uses declared bounded geometry here, so it has no STEP or
    # Evidence dependency for the normal evaluation fixture. The trusted CAD
    # fixture below supplies the separate candidate-CAD missing-STEP case.
    ("candidate-cad", "missing-step", "source STEP"),
    ("candidate-cad", "foreign-project", "project"),
    ("candidate-cad", "source-revision", "source revision"),
    ("candidate-evaluation", "foreign-project", "project"),
    ("candidate-evaluation", "source-revision", "source revision"),
    ("candidate-evaluation", "missing-evidence", "evidence"),
    ("candidate-comparison", "foreign-project", "project"),
    ("candidate-comparison", "source-revision", "source revision"),
    ("candidate-comparison", "missing-evidence", "evidence"),
    ("candidate-selection", "foreign-project", "project"),
    ("candidate-selection", "source-revision", "source revision"),
    ("candidate-selection", "missing-evidence", "evidence"),
    ("canonical-cad", "foreign-project", "project"),
    ("canonical-cad", "source-revision", "source revision"),
    ("canonical-cad", "missing-step", "source STEP"),
    ("canonical-m10", "foreign-project", "project"),
    ("canonical-m10", "source-revision", "source revision"),
    ("canonical-m10", "missing-step", "source STEP"),
    ("canonical-m10", "missing-evidence", "evidence"),
)


def _remove_provenance_dependency(tmp_path, service, artifact, mutation):
    if mutation in {"foreign-project", "source-revision"}:
        metadata_path = (tmp_path / artifact.relative_path).parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if mutation == "foreign-project":
            metadata["project_id"] = "PRJ-FOREIGN"
        else:
            metadata["bound_revision"] = artifact.bound_revision + 1
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        return

    payload = json.loads(
        (tmp_path / artifact.relative_path).read_text(encoding="utf-8")
    )
    if mutation == "missing-step":
        if artifact.artifact_id.startswith("CANDIDATE-CAD-"):
            source = payload["source_step_artifacts"][0]
        elif artifact.artifact_id.startswith("CANONICAL-M10-"):
            canonical_cad_reference = payload["canonical_cad"]["artifact"]
            canonical_cad_payload = json.loads(
                (tmp_path / canonical_cad_reference["relative_path"]).read_text(
                    encoding="utf-8"
                )
            )
            source = canonical_cad_payload["realization"][
                "selected_source_provenance"
            ][0]
        else:
            canonical_cad_payload = payload
            source = canonical_cad_payload["realization"][
                "selected_source_provenance"
            ][0]
        (tmp_path / source["relative_path"]).unlink()
        return

    if mutation == "missing-evidence":
        if artifact.artifact_id.startswith("CANDIDATE-COMPARISON-"):
            evaluation_reference = payload["candidate_evaluation_artifacts"][0]["artifact"]
            evaluation_payload = json.loads(
                (tmp_path / evaluation_reference["relative_path"]).read_text(
                    encoding="utf-8"
                )
            )
        elif artifact.artifact_id.startswith("CANDIDATE-SELECTION-"):
            evaluation_reference = payload["evaluation"]["artifact"]
            evaluation_payload = json.loads(
                (tmp_path / evaluation_reference["relative_path"]).read_text(
                    encoding="utf-8"
                )
            )
        else:
            evaluation_payload = payload
        evidence_id = evaluation_payload["proof_evidence"][0]["id"]
        evidence_path = (
            tmp_path / "projects" / service.project_id / "evidence" / f"{evidence_id}.json"
        )
        evidence_path.unlink()
        return

    raise AssertionError(f"unsupported mutation {mutation}")


@pytest.mark.parametrize(
    ("boundary", "mutation", "expected"), _SUPPORTED_DEPENDENCY_MUTATIONS
)
def test_supported_dependency_mutations_reject_at_each_provenance_boundary(
    tmp_path, boundary, mutation, expected
):
    from mechcad_harness.candidates.provenance_artifacts import (
        CandidateProvenanceIntegrityError,
    )

    if boundary == "candidate-cad" and mutation == "missing-step":
        publication, realization, request, manager = trusted_candidate_cad_fixture(tmp_path)
        service = __import__(
            "mechcad_harness.candidates.provenance_artifacts",
            fromlist=["CandidateProvenanceArtifactService"],
        ).CandidateProvenanceArtifactService(
            tmp_path, request.source_binding.project_id, manager
        )
        published = publish_candidate_cad(
            service,
            publication,
            request,
            realization,
            source_step_artifacts=realization_source_artifacts(
                tmp_path, realization, request.source_binding.project_id
            ),
        )
        artifact, resolver = published.artifact, service.resolve_candidate_cad
    else:
        service, artifact, resolver = _provenance_boundary_fixture(tmp_path, boundary)
    _remove_provenance_dependency(tmp_path, service, artifact, mutation)

    with pytest.raises(CandidateProvenanceIntegrityError, match=f"(?i){expected}"):
        resolver(artifact)


def test_project_scoped_semantic_replay_is_ambiguous_without_exact_reference(tmp_path):
    from mechcad_harness.candidates.provenance_artifacts import CandidateProvenanceIntegrityError

    service, _, published = _evaluation_fixture(tmp_path)
    resolved_evaluation = service.resolve_candidate_evaluation(published.artifact.artifact_id)
    evaluation_artifact = published.artifact
    replay = ArtifactStore(
        tmp_path,
        project_id=service.project_id,
        run_id="DISTINCT-REPLAY-RUN",
        task_id="DISTINCT-REPLAY-TASK",
    ).publish(
        evaluation_artifact.artifact_id,
        ArtifactType.JSON,
        "candidate_cad_provenance.json",
        (tmp_path / evaluation_artifact.relative_path).read_bytes(),
        evaluation_artifact.producer_tool_name,
        evaluation_artifact.producer_tool_version,
        evaluation_artifact.bound_revision,
        evaluation_artifact.bound_state_hash,
        input_hash=evaluation_artifact.input_hash,
    )

    with pytest.raises(CandidateProvenanceIntegrityError, match="missing or ambiguous"):
        service.resolve_candidate_evaluation(replay.artifact_id)
    assert service.resolve_candidate_evaluation(evaluation_artifact).payload == resolved_evaluation.payload
