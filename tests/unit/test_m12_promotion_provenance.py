from __future__ import annotations

import json
from hashlib import sha256
from types import SimpleNamespace

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.changes.engine import AppliedChangeResult
from mechcad_harness.candidates import (
    CandidateCanonicalInstanceMapping,
    PrePromotionM10ScopeProjection,
    PromotionDecisionInputReference,
    PromotionPhysicalPairRequirement,
    PromotionValueClassification,
    PromotableMechanismProjection,
)
from mechcad_harness.candidates.promotion_artifacts import (
    CandidatePromotionResultManifest,
    PromotionManifestIntegrityError,
    PromotionManifestService,
    SelectedCandidateDecisionManifest,
    resolve_decision,
    resolve_result,
)
from mechcad_harness.models import (
    CanonicalComponentSpecification,
    CanonicalGeometrySourceReference,
    CanonicalPhysicalMechanism,
)


HASH = "sha256:" + "a" * 64


def _rewrite_json_artifact(path, payload):
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(content)
    metadata_path = path.parent / "metadata.json"
    metadata = json.loads(metadata_path.read_bytes())
    metadata["sha256"] = "sha256:" + sha256(content).hexdigest()
    metadata["size_bytes"] = len(content)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _projection(source_hash: str) -> PromotableMechanismProjection:
    from test_m12_canonical_physical_mechanism import _mechanism

    mechanism = _mechanism()
    payload = mechanism.model_dump(mode="python")
    specification = dict(payload["component_specifications"][0])
    geometry = dict(specification["geometry_source"])
    geometry["artifact_hash"] = source_hash
    geometry["reference_hash"] = "pending"
    specification["geometry_source"] = geometry
    specification["specification_hash"] = "pending"
    first_specification = CanonicalComponentSpecification.model_validate(specification)
    payload["component_specifications"] = (
        first_specification,
        *payload["component_specifications"][1:],
    )
    first_component = dict(payload["components"][0])
    first_component["specification_hash"] = first_specification.specification_hash
    first_component["component_hash"] = "pending"
    payload["components"] = (first_component, *payload["components"][1:])
    payload["mechanism_hash"] = "pending"
    mechanism = CanonicalPhysicalMechanism.model_validate(payload)
    return PromotableMechanismProjection(
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


def _scope() -> PrePromotionM10ScopeProjection:
    return PrePromotionM10ScopeProjection(
        joint_semantic_key="joint-output",
        angle_interval_deg=(0.0, 360.0),
        required_clearance_mm=1.0,
        physical_pair_requirements=(
            PromotionPhysicalPairRequirement(
                requirement_key="shaft-to-mount",
                first_instance_id="shaft-1",
                first_interface_id="output",
                second_instance_id="mount-1",
                second_interface_id="output-frame",
            ),
        ),
    )


def _bundle(tmp_path):
    store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-1")
    source = store.publish(
        "ART-shaft",
        ArtifactType.STEP,
        "shaft.step",
        b"trusted-step",
        "freecad",
        "1.1.3",
        3,
        HASH,
    )
    projection = _projection(source.sha256)
    mapping = tuple(
        CandidateCanonicalInstanceMapping(
            candidate_instance_id=item.instance_id,
            canonical_instance_id=item.instance_id,
            canonical_path=f"/physical_mechanisms/PM-1/components/{item.instance_id}",
            classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            source_identity=f"candidate:physical-instance:{item.instance_id}",
        )
        for item in projection.components
    )
    reference = PromotionDecisionInputReference(
        promotion_request_hash=HASH,
        project_id="PRJ-1",
        base_revision=3,
        base_state_hash=HASH,
        candidate_hash=HASH,
        synthesis_request_hash=HASH,
        synthesis_policy_hash=HASH,
        m12_3_result_hash=HASH,
        evaluation_hash=HASH,
        selection_hash=HASH,
        promotion_policy_hash=HASH,
        canonical_target_mechanism_id="PM-1",
        mapping_identities=tuple(item.mapping_hash for item in mapping),
        classification_identities=(HASH,),
    )
    return store, dict(
        input_reference=reference,
        pre_promotion_scope_projection=_scope(),
        promotion_policy_hash=HASH,
        base_revision=3,
        base_state_hash=HASH,
        compilation_hash=HASH,
        promotion_proposal_hash=HASH,
        projection_hash=projection.projection_hash,
        projection=projection,
        mapping=mapping,
    )


def test_decision_publication_is_compact_immutable_and_freshly_resolvable(tmp_path):
    store, values = _bundle(tmp_path)
    service = PromotionManifestService()

    artifact = service.publish_decision(store, **values)
    payload = json.loads((tmp_path / artifact.relative_path).read_bytes())

    assert set(payload) == {
        "schema_version",
        "input_reference",
        "pre_promotion_scope_projection",
        "promotion_policy_hash",
        "base_revision",
        "base_state_hash",
        "compilation_hash",
        "promotion_proposal_hash",
        "projection_hash",
        "projection",
        "mapping",
        "decision_hash",
    }
    assert "candidate" not in payload
    assert "evaluation" not in payload
    assert "selection" not in payload
    assert set(payload["input_reference"]) == {
        "schema_version",
        "promotion_request_hash",
        "project_id",
        "base_revision",
        "base_state_hash",
        "candidate_hash",
        "synthesis_request_hash",
        "synthesis_policy_hash",
        "m12_3_result_hash",
        "evaluation_hash",
        "selection_hash",
        "comparison_used",
        "comparison_result_hash",
        "comparison_request_hash",
        "promotion_policy_hash",
        "canonical_target_mechanism_id",
        "m11_target_intent",
        "mapping_identities",
        "classification_identities",
        "reference_hash",
    }
    with pytest.raises(ValueError, match="extra"):
        SelectedCandidateDecisionManifest.model_validate(
            payload | {"resulting_revision": 4}
        )
    assert resolve_decision(store, artifact.artifact_id).decision_hash == payload["decision_hash"]
    assert service.publish_decision(store, **values) == artifact


def test_decision_resolution_rejects_byte_tamper_schema_extras_and_forged_hashes(tmp_path):
    store, values = _bundle(tmp_path)
    artifact = PromotionManifestService().publish_decision(store, **values)
    path = tmp_path / artifact.relative_path
    metadata_path = path.parent / "metadata.json"

    original = path.read_bytes()
    original_metadata = metadata_path.read_bytes()
    path.write_bytes(original.replace(b'"decision_hash":"', b'"decision_hash":"sha256:' + b"b" * 64 + b'"forged":"'))
    with pytest.raises(PromotionManifestIntegrityError):
        resolve_decision(store, artifact.artifact_id)

    path.write_bytes(original)
    metadata_path.write_bytes(original_metadata)
    payload = json.loads(original)
    payload["unexpected"] = True
    _rewrite_json_artifact(path, payload)
    with pytest.raises(PromotionManifestIntegrityError):
        resolve_decision(store, artifact.artifact_id)

    path.write_bytes(original)
    metadata_path.write_bytes(original_metadata)
    payload = json.loads(original)
    payload["projection_hash"] = HASH
    _rewrite_json_artifact(path, payload)
    with pytest.raises(PromotionManifestIntegrityError):
        resolve_decision(store, artifact.artifact_id)


def test_historical_resolution_needs_no_transient_exploration_objects(tmp_path):
    store, values = _bundle(tmp_path)
    service = PromotionManifestService()
    decision_artifact = service.publish_decision(store, **values)
    result_artifact = service.publish_result(
        store,
        decision_artifact_id=decision_artifact.artifact_id,
        promotion_proposal_hash=values["promotion_proposal_hash"],
        proposal_id="proposal-1",
        changeset_id="changeset-1",
        changed_paths=("/physical_mechanisms/PM-1",),
        mechanism_path="/physical_mechanisms/PM-1",
        resulting_revision=4,
        resulting_state_hash=HASH,
    )

    resolved_decision = resolve_decision(store, decision_artifact.artifact_id)
    resolved_result = resolve_result(store, result_artifact.artifact_id)
    assert isinstance(resolved_decision, SelectedCandidateDecisionManifest)
    assert isinstance(resolved_result, CandidatePromotionResultManifest)
    assert resolved_result.decision_artifact_id == decision_artifact.artifact_id


def test_resolution_rejects_missing_or_tampered_selected_geometry_source(tmp_path):
    store, values = _bundle(tmp_path)
    artifact = PromotionManifestService().publish_decision(store, **values)
    source_path = tmp_path / "projects" / "PRJ-1" / "runs" / "RUN-1" / "artifacts" / "ART-shaft" / "shaft.step"
    source_path.unlink()
    with pytest.raises(PromotionManifestIntegrityError):
        resolve_decision(store, artifact.artifact_id)


def test_manifest_semantic_identity_does_not_depend_on_artifact_store_run_scope(tmp_path):
    store, values = _bundle(tmp_path)
    first = PromotionManifestService().publish_decision(store, **values)
    second_store = ArtifactStore(tmp_path, project_id="PRJ-1", run_id="RUN-2")
    second = PromotionManifestService().publish_decision(second_store, **values)

    assert first.artifact_id == second.artifact_id
    assert resolve_decision(store, first.artifact_id).decision_hash == resolve_decision(
        second_store, second.artifact_id
    ).decision_hash


def test_result_resolution_rejects_mismatched_decision_or_result_identity(tmp_path):
    store, values = _bundle(tmp_path)
    service = PromotionManifestService()
    decision = service.publish_decision(store, **values)
    result = service.publish_result(
        store,
        decision_artifact_id=decision.artifact_id,
        promotion_proposal_hash=values["promotion_proposal_hash"],
        changed_paths=("/physical_mechanisms/PM-1",),
        mechanism_path="/physical_mechanisms/PM-1",
        resulting_revision=4,
        resulting_state_hash=HASH,
    )
    result_path = tmp_path / result.relative_path
    payload = json.loads(result_path.read_bytes())
    payload["promotion_proposal_hash"] = "sha256:" + "b" * 64
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PromotionManifestIntegrityError):
        resolve_result(store, result.artifact_id)


def test_decision_rejects_duplicate_geometry_id_with_conflicting_hash(tmp_path):
    store, values = _bundle(tmp_path)
    projection = values["projection"]
    conflicting_source = CanonicalGeometrySourceReference(
        artifact_id="ART-shaft",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="step:mount@1",
    )
    second_specification = CanonicalComponentSpecification(
        **projection.component_specifications[1].model_dump(mode="python")
        | {"geometry_source": conflicting_source, "specification_hash": "pending"}
    )
    second_component = projection.components[1].model_copy(
        update={"specification_hash": second_specification.specification_hash, "component_hash": "pending"}
    )
    conflicting_projection = projection.__class__(
        **projection.model_dump(mode="python")
        | {
            "component_specifications": (
                projection.component_specifications[0],
                second_specification,
            ),
            "components": (projection.components[0], second_component),
            "projection_hash": "pending",
        }
    )
    conflicting_values = dict(values)
    conflicting_values.update(
        projection=conflicting_projection,
        projection_hash=conflicting_projection.projection_hash,
    )

    with pytest.raises(PromotionManifestIntegrityError, match="geometry source"):
        PromotionManifestService().publish_decision(store, **conflicting_values)


def test_result_rejects_explicit_fields_conflicting_with_applied_receipt(tmp_path):
    store, values = _bundle(tmp_path)
    service = PromotionManifestService()
    decision = service.publish_decision(store, **values)
    applied = AppliedChangeResult(
        snapshot=SimpleNamespace(revision=4, state_hash=HASH),
        changeset_id="changeset-actual",
        changed_paths=("/physical_mechanisms/PM-1",),
    )

    with pytest.raises(PromotionManifestIntegrityError, match="supplied provenance"):
        service.publish_result(
            store,
            decision_artifact_id=decision.artifact_id,
            promotion_proposal_hash=values["promotion_proposal_hash"],
            changeset_id="changeset-forged",
            changed_paths=("/physical_mechanisms/PM-1", "/requirements/forged"),
            mechanism_path="/physical_mechanisms/PM-1",
            resulting_revision=4,
            resulting_state_hash="sha256:" + "b" * 64,
            applied=applied,
        )
