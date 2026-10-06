from __future__ import annotations

import hashlib
import json

import pytest

import mechcad_harness.candidates.provenance_artifacts as provenance_module
from mechcad_harness.application import ProductionApplication
from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.candidates.cad_realization import (
    CandidateCadInstanceMappingV2,
    CandidateCadRealizationRequestV3,
    CandidateCadRealizationV2,
    CandidateCadStageOutcomeV2,
    CandidateCadStageStatus,
    CandidateGeometryFidelity,
    SemanticPlacementOrigin,
    SemanticSourceGeometryIdentity,
    trusted_representation_identity,
)
from mechcad_harness.candidates.models import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisPolicy,
    CandidateSynthesisRequest,
    ComponentSpecificationSnapshot,
    GeometrySourceReference,
    MechanicalDesignCandidate,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.candidates.provenance_artifacts import (
    CandidateCadProvenance,
    CandidateCadProvenanceV2,
    CandidateProvenanceIntegrityError,
    CandidateProvenanceArtifactService,
)
from mechcad_harness.candidates.services import (
    CandidatePublicationService,
    bind_candidate_synthesis_request_semantic_identity,
    compute_verified_semantic_binding,
)
from mechcad_harness.imported_component import ImportedCadComponent
from mechcad_harness.models import DesignState
from mechcad_harness.models.semantic_component import (
    bind_component_specification_semantic_identity,
)
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_candidate_trusted_semantic_verification import _P2_STEP_VARIANTS


_PROJECT_ID = "PRJ-TP34"
_SLOTS = (("P1", "S1"), ("P2", "S2"))


def _artifact_pair(slot: str, variant: str):
    content = _P2_STEP_VARIANTS[variant]
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    return {
        "artifact_id": f"TP34-{slot}-{variant}",
        "artifact_hash": digest,
        "source_identity": f"supplier:tp34:{slot}@1",
        "format": "step",
        "content": content,
    }


def _publish_inputs(tmp_path, *, variants=("A", "B")):
    state = DesignState(
        id="DES-TP34",
        revision=1,
        requirements=[],
        constraints=[],
        interfaces=[],
        authoritative_parameters=[],
    )
    raw_inputs = tuple(
        _artifact_pair(slot, variant)
        for (slot, _), variant in zip(_SLOTS, variants, strict=True)
    )
    state_payload = state.model_dump(mode="json")
    state_payload["yagi_payload_carrier_requirements"] = [
        {key: value for key, value in item.items() if key != "content"}
        for item in raw_inputs
    ]
    state = DesignState.model_validate(state_payload)
    manager = StateManager(tmp_path)
    manager.create_project(_PROJECT_ID, state)
    store = ArtifactStore(tmp_path, project_id=_PROJECT_ID, run_id="TP34-SOURCES")
    binding = CandidateSourceBinding(
        project_id=_PROJECT_ID,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=(
            CandidateSourceReference(
                path="/id",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
            ),
            *(
                CandidateSourceReference(
                    path=f"/yagi_payload_carrier_requirements/{index}",
                    value_hash="pending",
                    authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
                )
                for index in range(len(raw_inputs))
            ),
        ),
    ).bound_to(state)

    artifacts = []
    for item in raw_inputs:
        artifacts.append(
            store.publish(
                item["artifact_id"],
                ArtifactType.STEP,
                f"{item['artifact_id']}.step",
                item["content"],
                "tp34-test-source",
                "1",
                state.revision,
                state_hash(state),
            )
        )

    semantic_context, _ = compute_verified_semantic_binding(
        binding,
        state=state,
        store=store,
        project_id=_PROJECT_ID,
    )
    pending_request = CandidateSynthesisRequest(
        schema_version="candidate-synthesis-request@2",
        source_binding=binding,
        semantic_source_binding_hash="pending",
    )
    request = bind_candidate_synthesis_request_semantic_identity(
        pending_request,
        state_manager=manager,
        store=store,
        project_id=_PROJECT_ID,
    )

    specifications = []
    physical_components = []
    for index, ((physical_id, _), raw) in enumerate(
        zip(_SLOTS, raw_inputs, strict=True)
    ):
        geometry_source = GeometrySourceReference(
            artifact_id=raw["artifact_id"],
            artifact_hash=raw["artifact_hash"],
            source_identity=raw["source_identity"],
            content_identity="pending",
            content_identity_algorithm="step-content-identity@1",
            semantic_reference_hash="pending",
            reference_hash="pending",
        )
        pending_specification = ComponentSpecificationSnapshot(
            schema_version="component-specification@4",
            component_type=f"trusted-{physical_id.lower()}",
            source_identity=f"specification:{physical_id}@1",
            geometry_source=geometry_source,
        )
        specification = bind_component_specification_semantic_identity(
            pending_specification, semantic_context
        )
        specifications.append(specification)
        physical_components.append(
            PhysicalComponentInstance(
                instance_id=physical_id,
                specification_hash=specification.specification_hash,
                role=PhysicalComponentRole.MOUNT_OR_SUPPORT,
            )
        )

    policy = CandidateSynthesisPolicy()
    candidate = MechanicalDesignCandidate(
        schema_version="mechanical-design-candidate@2",
        source_binding=binding,
        semantic_source_binding_hash=request.semantic_source_binding_hash,
        synthesis_request_hash=request.request_hash,
        synthesis_policy_hash=policy.policy_hash,
        component_specifications=tuple(specifications),
        realization=PhysicalMechanismRealization(
            components=tuple(physical_components)
        ),
        generator_identity="tp34-fixture",
        generator_version="1",
    )

    content_identity = step_content_identity_v1(raw_inputs[0]["content"]).content_hash
    assert all(
        step_content_identity_v1(item["content"]).content_hash == content_identity
        for item in raw_inputs
    )
    mappings = []
    for index, ((physical_id, cad_id), raw) in enumerate(
        zip(_SLOTS, raw_inputs, strict=True)
    ):
        placement = CadRigidTransform(x_mm=float(index * 10))
        mapping = CandidateCadInstanceMappingV2(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id=physical_id,
            cad_instance_id=cad_id,
            fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            representation_identity=trusted_representation_identity(
                slot=cad_id,
                content_identity=content_identity,
            ),
            source_geometry_identity=SemanticSourceGeometryIdentity(
                content_identity=content_identity,
                content_identity_algorithm="step-content-identity@1",
            ),
            geometry_definition_identities=(content_identity,),
            placement=placement,
            placement_origin=SemanticPlacementOrigin(
                authority="source_authority",
                input_identities=(f"candidate:source-authority:{physical_id}",),
                derivation="tp34-fixed-placement@1",
                transform=placement,
            ),
        )
        mappings.append(mapping)

    cad_request = CandidateCadRealizationRequestV3(
        candidate_hash=candidate.candidate_hash,
        source_binding=binding,
        semantic_source_binding_hash=candidate.semantic_source_binding_hash,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=tuple(physical_id for physical_id, _ in _SLOTS),
        mappings=tuple(mappings),
    )
    realization = _realization(
        candidate,
        cad_request,
        raw_inputs,
        artifacts,
        actual_by_slot={physical_id: raw for (physical_id, _), raw in zip(_SLOTS, raw_inputs, strict=True)},
    )
    provenance = CandidateProvenanceArtifactService(
        tmp_path,
        _PROJECT_ID,
        manager,
        candidate_publication_service=CandidatePublicationService(
            tmp_path, _PROJECT_ID, manager
        ),
    )
    return {
        "artifacts": tuple(artifacts),
        "candidate": candidate,
        "cad_request": cad_request,
        "manager": manager,
        "policy": policy,
        "provenance": provenance,
        "raw_inputs": raw_inputs,
        "realization": realization,
        "request": request,
        "state": state,
        "store": store,
    }


def _realization(candidate, request, raw_inputs, raw_artifacts, *, actual_by_slot):
    imported = []
    instances = []
    for index, (physical_id, cad_id) in enumerate(_SLOTS):
        raw = actual_by_slot[physical_id]
        placement = request.mappings[index].placement
        component_id = f"part-{cad_id}"
        imported.append(
            ImportedCadComponent(
                component_id=component_id,
                artifact_id=raw["artifact_id"],
                artifact_hash=raw["artifact_hash"],
                source_revision=candidate.source_binding.source_revision,
                source_state_hash=candidate.source_binding.source_state_hash,
            )
        )
        instances.append(
            CadComponentInstance(
                instance_id=cad_id,
                part_id=component_id,
                placement=placement,
            )
        )
    assembly = CadAssemblyProgram(
        assembly_id="tp34-candidate-assembly",
        imported_components=tuple(imported),
        instances=tuple(instances),
    )
    content_identities = tuple(
        dict.fromkeys(
            mapping.source_geometry_identity.content_identity
            for mapping in request.mappings
            if mapping.source_geometry_identity is not None
        )
    )
    return CandidateCadRealizationV2(
        candidate_hash=candidate.candidate_hash,
        request_hash=request.request_hash,
        mappings=request.mappings,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        representation_identities=tuple(
            mapping.representation_identity for mapping in request.mappings
        ),
        semantic_placement_derivations_hash=request.semantic_placement_derivations_hash,
        verified_source_content_identities=content_identities,
        verified_source_artifact_hashes=tuple(
            sorted(artifact.sha256 for artifact in raw_artifacts)
        ),
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        provider_identity="tp34-fixture-provider",
    )


def _publish_case_94(inputs):
    class _CadRealizationService:
        def realize(self, candidate, synthesis_request, synthesis_policy, request):
            return CandidateCadStageOutcomeV2(
                status=CandidateCadStageStatus.SUCCESS,
                realization=inputs["realization"],
            )

    application = object.__new__(ProductionApplication)
    object.__setattr__(application, "project_id", _PROJECT_ID)
    object.__setattr__(
        application, "candidate_cad_realization_service", _CadRealizationService()
    )
    object.__setattr__(
        application,
        "candidate_provenance_artifact_service",
        inputs["provenance"],
    )
    stage = application.realize_candidate_cad(
        inputs["candidate"],
        inputs["request"],
        inputs["policy"],
        inputs["cad_request"],
    )
    assert stage.realization == inputs["realization"]
    return inputs["provenance"].resolve_candidate_cad(
        "CANDIDATE-CAD-" + inputs["realization"].realization_hash[7:31]
    )


def _fresh_service(tmp_path, inputs):
    return CandidateProvenanceArtifactService(
        tmp_path,
        _PROJECT_ID,
        inputs["manager"],
        candidate_publication_service=CandidatePublicationService(
            tmp_path, _PROJECT_ID, inputs["manager"]
        ),
    )


def _replace_envelope_bytes(tmp_path, artifact, payload):
    content = canonical_json_bytes(payload)
    path = tmp_path / artifact.relative_path
    path.write_bytes(content)
    metadata_path = path.parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["sha256"] = "sha256:" + hashlib.sha256(content).hexdigest()
    metadata["size_bytes"] = len(content)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _republish_envelope(tmp_path, artifact, payload):
    realization = CandidateCadRealizationV2.model_validate(payload["realization"])
    content = canonical_json_bytes(payload)
    return ArtifactStore(
        tmp_path,
        project_id=artifact.project_id,
        run_id=artifact.run_id,
        task_id=artifact.task_id,
    ).publish(
        "CANDIDATE-CAD-" + realization.realization_hash[7:31],
        ArtifactType.JSON,
        "candidate_cad_provenance.json",
        content,
        artifact.producer_tool_name,
        artifact.producer_tool_version,
        artifact.bound_revision,
        artifact.bound_state_hash,
        input_hash=realization.realization_hash,
    )


def _wrong_semantic_tuple(inputs):
    from mechcad_harness.candidates.cad_realization import (
        CandidateCadRealizationRequestV3,
    )

    request = inputs["cad_request"]
    realization = inputs["realization"]
    mappings = list(request.mappings)
    mapping_payload = mappings[0].model_dump(mode="json")
    wrong_content_identity = "sha256:" + "f" * 64
    mapping_payload["source_geometry_identity"]["content_identity"] = (
        wrong_content_identity
    )
    mapping_payload["geometry_definition_identities"] = [wrong_content_identity]
    mapping_payload["representation_identity"] = trusted_representation_identity(
        slot=mappings[0].cad_instance_id,
        content_identity=wrong_content_identity,
    )
    mapping_payload["mapping_hash"] = "pending"
    mappings[0] = CandidateCadInstanceMappingV2.model_validate(mapping_payload)

    request_payload = request.model_dump(mode="json")
    request_payload["mappings"] = [item.model_dump(mode="json") for item in mappings]
    request_payload["request_hash"] = "pending"
    wrong_request = CandidateCadRealizationRequestV3.model_validate(request_payload)

    realization_payload = realization.model_dump(mode="json")
    realization_payload.update(
        {
            "request_hash": wrong_request.request_hash,
            "mappings": [item.model_dump(mode="json") for item in wrong_request.mappings],
            "representation_identities": [
                item.representation_identity for item in wrong_request.mappings
            ],
            "verified_source_content_identities": list(
                dict.fromkeys(
                    item.source_geometry_identity.content_identity
                    for item in wrong_request.mappings
                    if item.source_geometry_identity is not None
                )
            ),
            "realization_hash": "pending",
        }
    )
    wrong_realization = CandidateCadRealizationV2.model_validate(realization_payload)
    return wrong_request, wrong_realization


def test_case_94_two_raw_artifacts_deduplicate_semantics_through_fresh_resolve(
    tmp_path,
):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)

    restarted = _fresh_service(tmp_path, inputs)
    resolved = restarted.resolve_candidate_cad(published.artifact.artifact_id)

    assert isinstance(resolved.payload, CandidateCadProvenanceV2)
    assert len(resolved.payload.source_step_artifacts) == 2
    assert len(resolved.payload.realization.verified_source_artifact_hashes) == 2
    assert len(resolved.payload.realization.verified_source_content_identities) == 1
    assert len({item.sha256 for item in resolved.payload.source_step_artifacts}) == 2
    from mechcad_harness.candidates.evaluation import (
        _verify_candidate_cad_trusted_slot_raw_bindings,
    )

    verified_pairs = _verify_candidate_cad_trusted_slot_raw_bindings(
        inputs["candidate"],
        resolved.payload.realization,
        required_raw_pairs={
            (item.artifact_id, item.sha256)
            for item in resolved.payload.source_step_artifacts
        },
    )
    assert verified_pairs == {
        ("P1", "S1"): (
            inputs["raw_inputs"][0]["artifact_id"],
            inputs["raw_inputs"][0]["artifact_hash"],
        ),
        ("P2", "S2"): (
            inputs["raw_inputs"][1]["artifact_id"],
            inputs["raw_inputs"][1]["artifact_hash"],
        ),
    }
    expected_by_slot = {
        (mapping.physical_instance_id, mapping.cad_instance_id): (
            specification.geometry_source.artifact_id,
            specification.geometry_source.artifact_hash,
        )
        for mapping in resolved.payload.realization.mappings
        for component in inputs["candidate"].realization.components
        if component.instance_id == mapping.physical_instance_id
        for specification in inputs["candidate"].component_specifications
        if specification.specification_hash == component.specification_hash
    }
    actual_by_slot = {
        (mapping.physical_instance_id, mapping.cad_instance_id): (
            next(
                instance
                for instance in resolved.payload.realization.assembly.instances
                if instance.instance_id == mapping.cad_instance_id
            ).part_id,
            mapping.cad_instance_id,
        )
        for mapping in resolved.payload.realization.mappings
    }
    imported_by_id = {
        item.component_id: (item.artifact_id, item.artifact_hash)
        for item in resolved.payload.realization.assembly.imported_components
    }
    actual_by_slot = {
        slot: imported_by_id[part_id]
        for slot, (part_id, _) in actual_by_slot.items()
    }
    assert expected_by_slot == actual_by_slot


def test_candidate_cad_provenance_at2_has_five_fields_and_no_self_hash():
    assert set(CandidateCadProvenanceV2.model_fields) == {
        "schema_version",
        "realization",
        "request",
        "candidate_artifact",
        "source_step_artifacts",
    }
    assert len(CandidateCadProvenanceV2.model_fields) == 5
    assert "provenance_hash" not in CandidateCadProvenanceV2.model_fields
    assert set(CandidateCadProvenanceV2.model_fields) == set(
        CandidateCadProvenance.model_fields
    )
    assert CandidateCadProvenanceV2.model_fields["schema_version"].default == (
        "candidate-cad-provenance@2"
    )
    assert CandidateCadProvenanceV2.model_fields["realization"].annotation is (
        CandidateCadRealizationV2
    )
    assert CandidateCadProvenanceV2.model_fields["request"].annotation is (
        CandidateCadRealizationRequestV3
    )


@pytest.mark.parametrize(
    ("case", "actual_by_slot"),
    (
        ("95", {"P1": _artifact_pair("P2", "B"), "P2": _artifact_pair("P1", "A")}),
        ("96", {"P1": _artifact_pair("P2", "B"), "P2": _artifact_pair("P2", "B")}),
    ),
)
def test_cases_95_96_reject_equal_content_raw_slot_substitution_after_publish(
    tmp_path, case, actual_by_slot
):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    forged_realization = _realization(
        inputs["candidate"],
        inputs["cad_request"],
        inputs["raw_inputs"],
        inputs["artifacts"],
        actual_by_slot=actual_by_slot,
    )
    assert forged_realization.realization_hash == inputs["realization"].realization_hash
    payload = published.payload.model_dump(mode="json")
    payload["realization"] = forged_realization.model_dump(mode="json")
    _replace_envelope_bytes(tmp_path, published.artifact, payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="per-slot raw verification.*slot raw binding mismatch"):
        _fresh_service(tmp_path, inputs).resolve_candidate_cad(
            published.artifact.artifact_id
        )


def test_missing_required_raw_artifact_rejects_on_fresh_resolve(tmp_path):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    payload = published.payload.model_dump(mode="json")
    payload["source_step_artifacts"] = payload["source_step_artifacts"][:1]
    _replace_envelope_bytes(tmp_path, published.artifact, payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="exactly match.*required raw set"):
        _fresh_service(tmp_path, inputs).resolve_candidate_cad(
            published.artifact.artifact_id
        )


def test_publish_rejects_missing_required_raw_artifact(tmp_path):
    inputs = _publish_inputs(tmp_path)

    with pytest.raises(
        CandidateProvenanceIntegrityError,
        match="exactly match.*required raw set",
    ):
        inputs["provenance"].publish_candidate_cad(
            inputs["candidate"],
            inputs["request"],
            inputs["policy"],
            inputs["cad_request"],
            inputs["realization"],
            source_step_artifacts=inputs["artifacts"][:1],
        )


def test_extra_raw_artifact_rejects_on_fresh_resolve(tmp_path):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    extra = _artifact_pair("P3", "A")
    extra_artifact = inputs["store"].publish(
        extra["artifact_id"],
        ArtifactType.STEP,
        f"{extra['artifact_id']}.step",
        extra["content"],
        "tp34-test-source",
        "1",
        inputs["candidate"].source_binding.source_revision,
        inputs["candidate"].source_binding.source_state_hash,
    )
    payload = published.payload.model_dump(mode="json")
    payload["source_step_artifacts"].append(extra_artifact.model_dump(mode="json"))
    _replace_envelope_bytes(tmp_path, published.artifact, payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="exactly match.*required raw set"):
        _fresh_service(tmp_path, inputs).resolve_candidate_cad(
            published.artifact.artifact_id
        )


def test_equal_content_whole_raw_set_substitution_rejects(tmp_path):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    substitutes = []
    for slot, variant in (("P3", "A"), ("P4", "B")):
        item = _artifact_pair(slot, variant)
        substitutes.append(
            inputs["store"].publish(
                item["artifact_id"],
                ArtifactType.STEP,
                f"{item['artifact_id']}.step",
                item["content"],
                "tp34-test-source",
                "1",
                inputs["candidate"].source_binding.source_revision,
                inputs["candidate"].source_binding.source_state_hash,
            )
        )
    payload = published.payload.model_dump(mode="json")
    payload["source_step_artifacts"] = [item.model_dump(mode="json") for item in substitutes]
    _replace_envelope_bytes(tmp_path, published.artifact, payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="exactly match.*required raw set"):
        _fresh_service(tmp_path, inputs).resolve_candidate_cad(
            published.artifact.artifact_id
        )


def test_wrong_raw_sha_rejects_before_per_slot_or_semantic_acceptance(tmp_path):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    source = inputs["artifacts"][0]
    (tmp_path / source.relative_path).write_bytes(b"wrong STEP bytes")

    with pytest.raises(CandidateProvenanceIntegrityError, match="byte verification"):
        _fresh_service(tmp_path, inputs).resolve_candidate_cad(
            published.artifact.artifact_id
        )


def test_fresh_resolve_recomputes_semantics_only_after_raw_slot_verification(
    tmp_path, monkeypatch
):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    restarted = _fresh_service(tmp_path, inputs)
    events = []

    original_raw_verifier = restarted._verify_candidate_cad_raw_artifacts
    original_slot_verifier = (
        provenance_module._verify_candidate_cad_trusted_slot_raw_bindings
    )
    original_content_identity = provenance_module.step_content_identity_v1

    def verify_raw(*args, **kwargs):
        result = original_raw_verifier(*args, **kwargs)
        events.append("raw-bytes")
        return result

    def verify_slots(*args, **kwargs):
        result = original_slot_verifier(*args, **kwargs)
        events.append("slot-pairs")
        return result

    def recompute_semantics(content):
        events.append("semantic-content")
        return original_content_identity(content)

    monkeypatch.setattr(restarted, "_verify_candidate_cad_raw_artifacts", verify_raw)
    monkeypatch.setattr(
        provenance_module,
        "_verify_candidate_cad_trusted_slot_raw_bindings",
        verify_slots,
    )
    monkeypatch.setattr(
        provenance_module, "step_content_identity_v1", recompute_semantics
    )

    restarted.resolve_candidate_cad(published.artifact.artifact_id)

    assert events.index("raw-bytes") < events.index("slot-pairs")
    assert events.index("slot-pairs") < events.index("semantic-content")


def test_wrong_semantic_tuple_rejects_after_raw_slot_verification(tmp_path):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    wrong_request, wrong_realization = _wrong_semantic_tuple(inputs)
    payload = published.payload.model_dump(mode="json")
    payload["request"] = wrong_request.model_dump(mode="json")
    payload["realization"] = wrong_realization.model_dump(mode="json")
    forged_artifact = _republish_envelope(tmp_path, published.artifact, payload)

    with pytest.raises(
        CandidateProvenanceIntegrityError,
        match="trusted semantic identity does not match its slot raw bytes",
    ):
        _fresh_service(tmp_path, inputs).resolve_candidate_cad(
            forged_artifact.artifact_id
        )


@pytest.mark.parametrize("conflicting", (False, True))
def test_duplicate_or_conflicting_raw_identity_rejects(tmp_path, conflicting):
    inputs = _publish_inputs(tmp_path)
    published = _publish_case_94(inputs)
    payload = published.payload.model_dump(mode="json")
    duplicate = dict(payload["source_step_artifacts"][0])
    if conflicting:
        duplicate["sha256"] = "sha256:" + "0" * 64
    payload["source_step_artifacts"].append(duplicate)
    _replace_envelope_bytes(tmp_path, published.artifact, payload)

    with pytest.raises(CandidateProvenanceIntegrityError, match="unique"):
        _fresh_service(tmp_path, inputs).resolve_candidate_cad(
            published.artifact.artifact_id
        )
