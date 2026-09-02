from __future__ import annotations

import json

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import (
    CandidateIntegrityError,
    CandidatePublicationService,
    ComponentSpecificationSnapshot,
    MechanicalDesignCandidate,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    GeometryDerivationStatus,
    GeometryDerivationTransform,
    MaterializedInterfaceVerifier,
    SuppliedComponentInterfaceDefinition,
    materialize_interface,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.state import StateManager, state_hash

from test_m12_candidate_foundation import _candidate, _state
from test_m13_geometry_materialization import (
    _accepted_shaft_definition,
    _materialization_transform,
)
from test_m13_supplied_component_interfaces import _spec_frame


PROJECT_ID = "PRJ-M12"


def _publish_step_artifacts(tmp_path, state):
    StateManager(tmp_path).create_project(PROJECT_ID, state)
    store = ArtifactStore(tmp_path, project_id=PROJECT_ID, run_id="CAD")
    kwargs = dict(
        producer_tool_name="test-cad",
        producer_tool_version="1",
        bound_revision=state.revision,
        bound_state_hash=state_hash(state),
    )
    source = store.publish("ART-SRC", ArtifactType.STEP, "source.step", b"source-step", **kwargs)
    derived = store.publish("ART-DERIVED", ArtifactType.STEP, "derived.step", b"derived-step", **kwargs)
    return source, derived


def _geometry_reference(artifact, coordinate_system_id):
    return GeometrySourceReference(
        artifact_id=artifact.artifact_id,
        artifact_hash=artifact.sha256,
        source_identity="component-geometry",
        coordinate_system_id=coordinate_system_id,
    )


def _source_interface(source_reference):
    geometry = GeometryArtifactIdentity.from_candidate(source_reference)
    payload = _accepted_shaft_definition().model_dump(mode="json")
    geometry_payload = geometry.model_dump(mode="json")
    payload.update(geometry_reference_hash=source_reference.reference_hash, geometry=geometry_payload)
    payload["shaft"].update(
        geometry_reference_hash=source_reference.reference_hash,
        geometry=geometry_payload,
        interface_hash="pending",
    )
    payload["interface_hash"] = "pending"
    return SuppliedComponentInterfaceDefinition.model_validate(payload)


def _source_interface_with_frame(source_reference):
    payload = _source_interface(source_reference).model_dump(mode="json")
    payload["shaft"].update(reference_frame_id="output-frame", interface_hash="pending")
    payload["interface_hash"] = "pending"
    return SuppliedComponentInterfaceDefinition.model_validate(payload)


def _transform(source_reference, derived_reference):
    source_geometry = GeometryArtifactIdentity.from_candidate(source_reference)
    derived_geometry = GeometryArtifactIdentity.from_candidate(derived_reference)
    payload = _materialization_transform().model_dump(mode="json")
    payload.update(
        source_geometry=source_geometry.model_dump(mode="json"),
        derived_geometry=derived_geometry.model_dump(mode="json"),
        source_geometry_reference_hash=source_reference.reference_hash,
        derived_geometry_reference_hash=derived_reference.reference_hash,
        transform_hash="pending",
    )
    return GeometryDerivationTransform.model_validate(payload)


def _candidate_with_spec(state, specification):
    candidate, request, policy = _candidate(state)
    candidate_payload = candidate.model_dump(mode="json")
    candidate_payload["component_specifications"] = [
        specification.model_dump(mode="json"),
        *[item.model_dump(mode="json") for item in candidate.component_specifications[1:]],
    ]
    candidate_payload["realization"]["components"][0]["specification_hash"] = specification.specification_hash
    candidate_payload["realization"]["realization_hash"] = "pending"
    candidate_payload["candidate_hash"] = "pending"
    return MechanicalDesignCandidate.model_validate(candidate_payload), request, policy


def _specification(reference, *, frames=(), definitions=(), transforms=(), schema="component-specification@2"):
    return ComponentSpecificationSnapshot(
        schema_version=schema,
        component_type="motor",
        source_identity="source:motor",
        geometry_source=reference,
        interfaces=tuple(item.interface_id for item in definitions),
        supplied_reference_frames=frames,
        supplied_interface_definitions=definitions,
        geometry_derivation_transforms=transforms,
    )


def _publisher(tmp_path, state, specification):
    manager = StateManager(tmp_path)
    candidate, request, policy = _candidate_with_spec(state, specification)
    service = CandidatePublicationService(tmp_path, PROJECT_ID, manager)
    publication = service.publish(candidate, request, policy)
    return service, publication


def _recorded_resolve(service, artifact_id, monkeypatch):
    calls = []
    original = service.store.read_verified_in_project

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(service.store, "read_verified_in_project", record)
    service.resolve(artifact_id)
    return calls


def test_accepted_transform_replay_verifies_selected_source_and_both_step_artifacts(tmp_path, monkeypatch):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    specification = _specification(source_ref, transforms=(_transform(source_ref, derived_ref),))
    service, publication = _publisher(tmp_path, state, specification)

    calls = _recorded_resolve(service, publication.artifact.artifact_id, monkeypatch)

    assert [call[0][0] for call in calls] == ["ART-SRC", "ART-DERIVED"]
    assert all(call[1] == {"expected_type": ArtifactType.STEP, "expected_hash": source.sha256 if call[0][0] == "ART-SRC" else derived.sha256} for call in calls)


@pytest.mark.parametrize("artifact_name", ("source.step", "derived.step"))
def test_accepted_transform_tampered_step_artifact_is_candidate_integrity_failure(tmp_path, artifact_name):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    specification = _specification(source_ref, transforms=(_transform(source_ref, derived_ref),))
    service, publication = _publisher(tmp_path, state, specification)

    path = tmp_path / (source.relative_path if artifact_name == "source.step" else derived.relative_path)
    path.write_bytes(b"tampered")
    with pytest.raises(CandidateIntegrityError):
        service.resolve(publication.artifact.artifact_id)


def test_frames_only_trigger_selected_geometry_verification_without_transform_artifact_reads(tmp_path, monkeypatch):
    state = _state()
    source, _ = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    specification = _specification(source_ref, frames=(_spec_frame(source_ref),))
    service, publication = _publisher(tmp_path, state, specification)

    calls = _recorded_resolve(service, publication.artifact.artifact_id, monkeypatch)

    assert [call[0][0] for call in calls] == ["ART-SRC"]


def test_proposed_transform_is_model_validated_but_does_not_verify_transform_artifacts(tmp_path, monkeypatch):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    proposed_payload = _transform(source_ref, derived_ref).model_dump(mode="json")
    proposed_payload.update(status=GeometryDerivationStatus.PROPOSED, transform_hash="pending")
    proposed = GeometryDerivationTransform.model_validate(proposed_payload)
    specification = _specification(source_ref, transforms=(proposed,))
    service, publication = _publisher(tmp_path, state, specification)

    calls = _recorded_resolve(service, publication.artifact.artifact_id, monkeypatch)

    assert [call[0][0] for call in calls] == ["ART-SRC"]


def test_materialized_interface_replay_runs_after_artifact_verification(tmp_path, monkeypatch):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    transform = _transform(source_ref, derived_ref)
    source_interface = _source_interface(source_ref)
    result = materialize_interface(source_interface, None, transform)
    specification = _specification(
        derived_ref,
        definitions=(result.interface,),
        transforms=(transform,),
    )
    service, publication = _publisher(tmp_path, state, specification)
    original_verify = MaterializedInterfaceVerifier.verify
    verify_calls = []

    def record_verify(*args, **kwargs):
        verify_calls.append(args)
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(MaterializedInterfaceVerifier, "verify", staticmethod(record_verify))
    calls = _recorded_resolve(service, publication.artifact.artifact_id, monkeypatch)

    assert [call[0][0] for call in calls] == ["ART-DERIVED", "ART-SRC"]
    assert len(verify_calls) >= 2


def test_materialized_publication_replays_with_exact_active_derived_frame_after_artifacts(
    tmp_path, monkeypatch
):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    transform = _transform(source_ref, derived_ref)
    source_interface = _source_interface_with_frame(source_ref)
    source_frame = _spec_frame(source_ref)
    materialized = materialize_interface(source_interface, source_frame, transform)
    specification = _specification(
        derived_ref,
        frames=(materialized.reference_frame,),
        definitions=(materialized.interface,),
        transforms=(transform,),
    )
    service, publication = _publisher(tmp_path, state, specification)
    events = []
    verify_calls = []
    original_read = service.store.read_verified_in_project
    original_verify = MaterializedInterfaceVerifier.verify

    def record_read(*args, **kwargs):
        events.append(("artifact", args, kwargs))
        return original_read(*args, **kwargs)

    def record_verify(*args, **kwargs):
        events.append(("replay", args, kwargs))
        verify_calls.append(args)
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(service.store, "read_verified_in_project", record_read)
    monkeypatch.setattr(MaterializedInterfaceVerifier, "verify", staticmethod(record_verify))

    service.resolve(publication.artifact.artifact_id)

    artifact_events = [event for event in events if event[0] == "artifact"]
    assert [event[1][0] for event in artifact_events] == ["ART-DERIVED", "ART-SRC"]
    assert [event[2] for event in artifact_events] == [
        {"expected_type": ArtifactType.STEP, "expected_hash": derived.sha256},
        {"expected_type": ArtifactType.STEP, "expected_hash": source.sha256},
    ]
    assert events[-1][0] == "replay"
    last_replay = max(index for index, event in enumerate(events) if event[0] == "replay")
    assert all(
        index < last_replay
        for index, event in enumerate(events)
        if event[0] == "artifact"
    )
    assert verify_calls[-1][0] == materialized.interface.derivation
    assert verify_calls[-1][1] == transform
    assert verify_calls[-1][2] == materialized.interface
    assert verify_calls[-1][3] == materialized.reference_frame


def test_empty_at_2_and_legacy_at_1_use_only_the_selected_geometry_path(tmp_path, monkeypatch):
    state = _state()
    source, _ = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    for specification in (
        _specification(source_ref),
        _specification(
            GeometrySourceReference(
                artifact_id=source.artifact_id,
                artifact_hash=source.sha256,
                source_identity="component-geometry",
            ),
            schema="component-specification@1",
        ),
    ):
        service, publication = _publisher(tmp_path, state, specification)
        calls = _recorded_resolve(service, publication.artifact.artifact_id, monkeypatch)
        assert [call[0][0] for call in calls] == ["ART-SRC"]


def test_materialized_interface_semantic_tamper_is_wrapped_as_candidate_integrity_failure(tmp_path):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    transform = _transform(source_ref, derived_ref)
    result = materialize_interface(_source_interface(source_ref), None, transform)
    specification = _specification(derived_ref, definitions=(result.interface,), transforms=(transform,))
    service, publication = _publisher(tmp_path, state, specification)
    manifest_path = tmp_path / publication.artifact.relative_path
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    active = payload["candidate"]["component_specifications"][0]["supplied_interface_definitions"][0]
    active["shaft"]["nominal_shaft_diameter"]["evidence"][0]["value"] = 999.0
    manifest_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    with pytest.raises(CandidateIntegrityError):
        service.resolve(publication.artifact.artifact_id)
