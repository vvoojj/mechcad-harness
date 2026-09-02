from __future__ import annotations

from types import SimpleNamespace

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.candidates import (
    CandidatePromotionCompiler,
    CandidatePromotionPolicy,
    ComponentSpecificationSnapshot,
    ProjectArtifactResolver,
    PromotionClassification,
    PromotionValueClassification,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalPhysicalMechanismCompiler,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.models import CanonicalPhysicalComponent, CanonicalPhysicalMechanism
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity
from mechcad_harness.models.supplied_component_interface import (
    GeometryDerivationStatus,
    GeometryDerivationTransform,
    MaterializedInterfaceVerifier,
    MountingFaceInterface,
    MountingHole,
    SuppliedComponentInterfaceDefinition,
    SuppliedInterfaceTransformRole,
    materialize_interface,
)
from mechcad_harness.state import StateManager, state_hash

from test_m12_candidate_foundation import _state
from test_m13_publication_replay import (
    _geometry_reference,
    _publish_step_artifacts,
    _source_interface,
    _transform,
)
from test_m13_geometry_materialization import _interface_fact
from test_m13_supplied_component_interfaces import _spec_frame


PROJECT_ID = "PRJ-M12"


def _candidate_for(*specifications):
    return SimpleNamespace(
        component_specifications=tuple(specifications),
        design_variables=(),
        realization=SimpleNamespace(components=(), connections=(), joint_bindings=()),
    )


def _request_for(candidate, classifications=()):
    hash_value = "sha256:" + "0" * 64
    return SimpleNamespace(
        candidate=candidate,
        classifications=tuple(classifications),
        promotion_policy=CandidatePromotionPolicy(),
        m12_3_result=SimpleNamespace(result_hash=hash_value),
        evaluation=SimpleNamespace(
            evaluation_hash=hash_value,
            m10_stage_outcome=SimpleNamespace(m10_request_hashes=(), m10_result_hashes=()),
            cad_realization_hash=None,
        ),
        selection=SimpleNamespace(selection_hash=hash_value),
        comparison=None,
        comparison_request=None,
    )


def _m13_specification(source, derived, *, with_frame=True):
    transform = _transform(source, derived)
    source_interface = _source_interface(source)
    if with_frame:
        source_interface_payload = source_interface.model_dump(mode="json")
        source_interface_payload["shaft"]["reference_frame_id"] = "output-frame"
        source_interface_payload["shaft"]["interface_hash"] = "pending"
        source_interface_payload["interface_hash"] = "pending"
        source_interface = type(source_interface).model_validate(source_interface_payload)
        materialized = materialize_interface(source_interface, _spec_frame(source), transform)
        return (
            ComponentSpecificationSnapshot(
                schema_version="component-specification@2",
                component_type="motor",
                source_identity="source:motor",
                geometry_source=derived,
                interfaces=(materialized.interface.interface_id,),
                supplied_reference_frames=(materialized.reference_frame,),
                supplied_interface_definitions=(materialized.interface,),
                geometry_derivation_transforms=(transform,),
            ),
            transform,
        )
    return (
        ComponentSpecificationSnapshot(
            schema_version="component-specification@2",
            component_type="motor",
            source_identity="source:motor",
            geometry_source=source,
            geometry_derivation_transforms=(transform,),
        ),
        transform,
    )


def test_mapping_schema_is_selected_from_specification_schema_not_tuple_presence():
    compiler = object.__new__(CandidatePromotionCompiler)
    legacy = ComponentSpecificationSnapshot(
        component_type="motor", source_identity="source:motor"
    )
    empty_v2 = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="source:motor-v2",
    )

    compiler._verify_policy(CandidatePromotionPolicy(), _candidate_for(legacy))
    compiler._verify_policy(
        CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
        _candidate_for(empty_v2),
    )
    with pytest.raises(ValueError, match="mapping schema"):
        compiler._verify_policy(
            CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
            _candidate_for(legacy),
        )
    with pytest.raises(ValueError, match="mapping schema"):
        compiler._verify_policy(
            CandidatePromotionPolicy(),
            _candidate_for(empty_v2),
        )


def test_expected_m13_classifications_are_scoped_by_specification_hash():
    source = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    specification, transform = _m13_specification(source, derived)
    second = ComponentSpecificationSnapshot.model_validate(
        specification.model_dump(mode="json")
        | {"component_type": "motor-variant", "specification_hash": "pending"}
    )

    expected = CandidatePromotionCompiler._expected_classifications(
        _request_for(_candidate_for(specification, second))
    )

    for item, identity, classification, value in (
        (
            specification.supplied_reference_frames[0],
            "candidate:supplied-frame:{}:output-frame".format(specification.specification_hash),
            PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            specification.supplied_reference_frames[0].frame_hash,
        ),
        (
            specification.supplied_interface_definitions[0],
            "candidate:supplied-interface:{}:output-shaft".format(specification.specification_hash),
            PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            specification.supplied_interface_definitions[0].interface_hash,
        ),
        (
            transform,
            "candidate:geometry-derivation:{}:T1".format(specification.specification_hash),
            PromotionValueClassification.CANONICAL_REDERIVATION_INPUT,
            transform.transform_hash,
        ),
    ):
        assert expected[identity].source_value == value
        assert expected[identity].required_classification is classification

    first_identity = f"candidate:supplied-frame:{specification.specification_hash}:output-frame"
    second_identity = f"candidate:supplied-frame:{second.specification_hash}:output-frame"
    assert first_identity in expected
    assert second_identity in expected
    assert first_identity != second_identity


@pytest.mark.parametrize("kind", ["frame", "interface", "transform"])
def test_m13_classification_source_hash_substitution_is_rejected(kind):
    source = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    specification, transform = _m13_specification(source, derived)
    candidate = _candidate_for(specification)
    expected = CandidatePromotionCompiler._expected_classifications(_request_for(candidate))
    identity_fragment = {
        "frame": ":supplied-frame:",
        "interface": ":supplied-interface:",
        "transform": ":geometry-derivation:",
    }[kind]
    source_identity = next(identity for identity in expected if identity_fragment in identity)
    classifications = tuple(
        PromotionClassification(
            source_identity=identity,
            classification=(
                PromotionValueClassification.CANONICAL_REDERIVATION_INPUT
                if identity == source_identity and kind == "transform"
                else PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
            ),
            source_value=(
                "sha256:" + "f" * 64
                if identity == source_identity
                else expected_value.source_value
            ),
        )
        for identity, expected_value in expected.items()
    )

    with pytest.raises(ValueError, match="substitution"):
        CandidatePromotionCompiler._classifications_by_identity(
            _request_for(candidate, classifications), expected
        )


def test_missing_unknown_and_wrong_m13_classifications_fail_closed():
    source = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    specification, _ = _m13_specification(source, derived)
    candidate = _candidate_for(specification)
    request = _request_for(candidate)
    expected = CandidatePromotionCompiler._expected_classifications(request)
    classifications = tuple(
        PromotionClassification(
            source_identity=identity,
            classification=(
                PromotionValueClassification.CANONICAL_REDERIVATION_INPUT
                if identity.startswith("candidate:geometry-derivation:")
                else PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
            ),
            source_value=expected_value.source_value,
        )
        for identity, expected_value in expected.items()
    )
    frame = next(item for item in classifications if ":supplied-frame:" in item.source_identity)

    with pytest.raises(ValueError, match="missing"):
        CandidatePromotionCompiler._classifications_by_identity(
            _request_for(candidate, tuple(item for item in classifications if item != frame)),
            expected,
        )
    with pytest.raises(ValueError, match="unknown"):
        CandidatePromotionCompiler._classifications_by_identity(
            _request_for(
                candidate,
                classifications
                + (
                    PromotionClassification(
                        source_identity="candidate:supplied-interface:unknown:x",
                        classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                        source_value="sha256:" + "1" * 64,
                    ),
                ),
            ),
            expected,
        )
    wrong = tuple(
        item.model_copy(
            update={
                "classification": PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                "classification_hash": "pending",
            }
        )
        if item.source_identity.startswith("candidate:geometry-derivation:")
        else item
        for item in classifications
    )
    with pytest.raises(ValueError, match="classification"):
        CandidatePromotionCompiler._classifications_by_identity(
            _request_for(candidate, wrong), expected
        )


def test_accepted_transform_artifacts_are_verified_before_materialized_replay(tmp_path, monkeypatch):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    _, transform = _m13_specification(source_ref, derived_ref, with_frame=False)
    source_interface = _source_interface(source_ref)
    materialized = materialize_interface(source_interface, None, transform)
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="source:motor",
        geometry_source=derived_ref,
        interfaces=(materialized.interface.interface_id,),
        supplied_interface_definitions=(materialized.interface,),
        geometry_derivation_transforms=(transform,),
    )
    request = SimpleNamespace(
        project_id="PRJ-M12",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        candidate=SimpleNamespace(component_specifications=(specification,)),
    )
    manager = StateManager(tmp_path)
    events = []
    store = ArtifactStore(tmp_path, project_id="PRJ-M12", run_id="promotion-lookup")
    original_read = store.read_verified_in_project
    original_verify = MaterializedInterfaceVerifier.verify

    def read(*args, **kwargs):
        events.append("artifact")
        return original_read(*args, **kwargs)

    def verify(*args, **kwargs):
        events.append("replay")
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(store, "read_verified_in_project", read)
    monkeypatch.setattr(MaterializedInterfaceVerifier, "verify", staticmethod(verify))
    compiler = CandidatePromotionCompiler(
        manager,
        store,
        cad_replay_verifier=lambda *args: None,
    )

    compiler._verify_geometry_sources(request)

    assert events[:2] == ["artifact", "artifact"]
    assert events[-1] == "replay"


@pytest.mark.parametrize("selected_role", ["source", "derived"])
def test_transform_rejects_forged_accepted_geometry_reference(selected_role):
    source_ref = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived_ref = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    transform = _transform(source_ref, derived_ref)
    field = f"{selected_role}_geometry_reference_hash"
    forged_payload = transform.model_dump(mode="json")
    forged_payload.update({field: "sha256:" + "f" * 64, "transform_hash": "pending"})
    with pytest.raises(ValueError, match="geometry reference hash"):
        GeometryDerivationTransform.model_validate(forged_payload)


@pytest.mark.parametrize("forged_role", ["source", "derived"])
def test_transform_rejects_forged_geometry_reference_before_readiness(forged_role):
    source_ref = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived_ref = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    payload = _transform(source_ref, derived_ref).model_dump(mode="json")
    payload.update(
        {f"{forged_role}_geometry_reference_hash": "sha256:" + "f" * 64,
         "transform_hash": "pending"}
    )
    with pytest.raises(ValueError, match="geometry reference hash"):
        GeometryDerivationTransform.model_validate(payload)


def test_readiness_accepts_coordinate_free_transform_with_correct_self_hashes(tmp_path):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12", run_id="promotion-lookup")
    selected = store.publish(
        "ART-SELECTED",
        ArtifactType.STEP,
        "selected.step",
        b"selected-step",
        producer_tool_name="test-cad",
        producer_tool_version="1",
        bound_revision=state.revision,
        bound_state_hash=state_hash(state),
    )
    selected_ref = _geometry_reference(selected, "selected-model-coordinates@1")
    source_ref = _geometry_reference(source, None)
    derived_ref = _geometry_reference(derived, None)
    transform = _transform(source_ref, derived_ref)
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="source:motor",
        geometry_source=selected_ref,
        geometry_derivation_transforms=(transform,),
    )
    request = SimpleNamespace(
        project_id="PRJ-M12",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        candidate=SimpleNamespace(component_specifications=(specification,)),
    )
    compiler = CandidatePromotionCompiler(
        StateManager(tmp_path),
        store,
        cad_replay_verifier=lambda *args: None,
    )

    assert source_ref.reference_hash == GeometrySourceReference.model_validate(
        source_ref.model_dump(mode="json")
    ).reference_hash
    assert derived_ref.reference_hash == GeometrySourceReference.model_validate(
        derived_ref.model_dump(mode="json")
    ).reference_hash
    assert transform.source_geometry_reference_hash == source_ref.reference_hash
    assert transform.derived_geometry_reference_hash == derived_ref.reference_hash
    assert compiler._verify_geometry_sources(request) == (
        selected.artifact_id,
        source.artifact_id,
        derived.artifact_id,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_identity", "different-component-geometry"),
        ("coordinate_system_id", "other-model-coordinates@1"),
    ),
)
def test_readiness_rejects_duplicate_geometry_artifact_with_conflicting_identity(
    tmp_path, field, value
):
    state = _state()
    artifact, _ = _publish_step_artifacts(tmp_path, state)
    first = _geometry_reference(artifact, "model-coordinates@1")
    conflicting_payload = first.model_dump(mode="json")
    conflicting_payload.update({field: value, "reference_hash": "pending"})
    conflicting = GeometrySourceReference.model_validate(conflicting_payload)
    request = SimpleNamespace(
        project_id="PRJ-M12",
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        candidate=SimpleNamespace(
            component_specifications=(
                SimpleNamespace(geometry_source=first),
                SimpleNamespace(geometry_source=conflicting),
            )
        ),
    )
    compiler = CandidatePromotionCompiler(
        StateManager(tmp_path),
        ArtifactStore(tmp_path, project_id="PRJ-M12", run_id="promotion-lookup"),
        cad_replay_verifier=lambda *args: None,
    )

    with pytest.raises(ValueError, match="ambiguous"):
        compiler._verify_geometry_sources(request)


def test_proposed_transform_reference_binding_is_validated_before_artifact_read():
    source_ref = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived_ref = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    payload = _transform(source_ref, derived_ref).model_dump(mode="json")
    payload.update(
        status=GeometryDerivationStatus.PROPOSED,
        source_geometry_reference_hash="sha256:" + "f" * 64,
        transform_hash="pending",
    )
    with pytest.raises(ValueError, match="geometry reference hash"):
        GeometryDerivationTransform.model_validate(payload)


def test_proposed_transform_cannot_back_materialized_candidate_interface():
    source = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    specification, transform = _m13_specification(source, derived, with_frame=False)
    proposed_payload = transform.model_dump(mode="json")
    proposed_payload.update(status=GeometryDerivationStatus.PROPOSED, transform_hash="pending")
    proposed = GeometryDerivationTransform.model_validate(proposed_payload)
    request = SimpleNamespace(
        project_id="PRJ-M12",
        source_revision=1,
        source_state_hash="sha256:" + "c" * 64,
        candidate=SimpleNamespace(
            component_specifications=(
                specification.model_copy(
                    update={
                        "geometry_derivation_transforms": (proposed,),
                        "specification_hash": "pending",
                    }
                ),
            )
        ),
    )
    compiler = object.__new__(CandidatePromotionCompiler)
    compiler.artifact_store_factory = lambda *args, **kwargs: SimpleNamespace(
        read_verified_in_project=lambda *args, **kwargs: None
    )
    with pytest.raises(ValueError, match="accepted|materialized|missing"):
        compiler._verify_geometry_sources(request)


def test_canonical_specification_round_trip_preserves_all_m13_tuples():
    source = GeometrySourceReference(
        artifact_id="ART-SOURCE",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="source:geometry",
        coordinate_system_id="source-model-coordinates@1",
    )
    derived = GeometrySourceReference(
        artifact_id="ART-DERIVED",
        artifact_hash="sha256:" + "b" * 64,
        source_identity="source:geometry",
        coordinate_system_id="derived-model-coordinates@1",
    )
    specification, _ = _m13_specification(source, derived)

    canonical = CandidatePromotionCompiler._canonical_specification(specification)

    assert canonical.schema_version == "canonical-component-specification@2"
    assert tuple(item.model_dump(mode="json") for item in canonical.supplied_reference_frames) == tuple(
        item.model_dump(mode="json") for item in specification.supplied_reference_frames
    )
    assert tuple(item.model_dump(mode="json") for item in canonical.supplied_interface_definitions) == tuple(
        item.model_dump(mode="json") for item in specification.supplied_interface_definitions
    )
    assert tuple(item.model_dump(mode="json") for item in canonical.geometry_derivation_transforms) == tuple(
        item.model_dump(mode="json") for item in specification.geometry_derivation_transforms
    )


def test_end_to_end_promotion_scopes_m13_classifications_by_distinct_specification_hash(
    tmp_path,
):
    from mechcad_harness.candidates import (
        CandidateEvaluationPolicy,
        CandidatePromotionRequest,
        CandidateSelection,
    )
    from test_m12_candidate_evaluation import (
        _bound_m10_inputs,
        _evaluation_service,
        _m12_result,
    )
    from test_m12_promotion_compiler import _compiler, _inputs

    inputs, request_builder, state = _inputs()
    candidate, synthesis_request, synthesis_policy, _, _, _ = inputs
    _, compiler = _compiler(tmp_path, state)
    store = ArtifactStore(tmp_path, project_id="PRJ-M12", run_id="promotion-lookup")
    artifact = store.publish(
        "ART-SHARED",
        ArtifactType.STEP,
        "shared.step",
        b"shared-step",
        producer_tool_name="test-cad",
        producer_tool_version="1",
        bound_revision=state.revision,
        bound_state_hash=state_hash(state),
    )
    reference = _geometry_reference(artifact, "shared-model-coordinates@1")
    motor = candidate.component_specifications[0]
    frame_a = _spec_frame(reference, "frame-a")
    frame_b = _spec_frame(reference, "frame-b")

    def specification(frame):
        payload = motor.model_dump(mode="json")
        payload.update(
            schema_version="component-specification@2",
            source_identity="shared:source",
            geometry_source=reference.model_dump(mode="json"),
            supplied_reference_frames=(frame.model_dump(mode="json"),),
            specification_hash="pending",
        )
        return ComponentSpecificationSnapshot.model_validate(payload)

    first = specification(frame_a)
    second = specification(frame_b)
    assert first.source_identity == second.source_identity
    assert first.specification_hash != second.specification_hash
    candidate_payload = candidate.model_dump(mode="json")
    candidate_payload["component_specifications"] = [
        first.model_dump(mode="json"),
        second.model_dump(mode="json"),
        *[
            item.model_dump(mode="json")
            for item in candidate.component_specifications[1:]
        ],
    ]
    for component in candidate_payload["realization"]["components"]:
        if component["instance_id"] == "motor":
            component["specification_hash"] = first.specification_hash
        elif component["instance_id"] == "driver":
            component["specification_hash"] = second.specification_hash
    candidate_payload["realization"]["realization_hash"] = "pending"
    candidate_payload["candidate_hash"] = "pending"
    candidate = type(candidate).model_validate(candidate_payload)

    m12 = _m12_result(candidate)
    cad, m10, scope, binding, m10_request, cad_request = _bound_m10_inputs(candidate)
    evaluation = _evaluation_service().evaluate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12,
        cad,
        m10,
        CandidateEvaluationPolicy(),
        cad_request=cad_request,
        m10_request=m10_request,
        m10_scope=scope,
        m10_binding=binding,
    )
    selection = CandidateSelection(
        candidate_hash=candidate.candidate_hash,
        evaluation_hash=evaluation.evaluation_hash,
        source_binding_hash=evaluation.source_binding_hash,
        evaluation_scope_hash=evaluation.evaluation_scope_hash,
        selector_identity="fixture-selector",
        rationale="fixture selection",
    )
    base_request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
        promotion_policy=CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
    )
    expected = CandidatePromotionCompiler._expected_classifications(base_request)
    classifications = tuple(
        PromotionClassification(
            source_identity=identity,
            classification=(
                expected_value.required_classification
                or (
                    PromotionValueClassification.ACCEPTED_DESIGN_CHOICE
                    if identity.startswith("candidate:design-variable:")
                    else PromotionValueClassification.ACCEPTED_PHYSICAL_FACT
                )
            ),
            source_value=expected_value.source_value if expected_value.has_source_value else None,
        )
        for identity, expected_value in expected.items()
    )
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications,
        promotion_policy=CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
    )
    request = CandidatePromotionRequest.model_validate(request.model_dump(mode="json"))

    readiness = compiler.validate_readiness(request)

    assert len(readiness.mapping) == len(candidate.realization.components)
    frame_classifications = tuple(
        item
        for item in request.classifications
        if item.source_identity.startswith("candidate:supplied-frame:")
    )
    assert len(frame_classifications) == 2
    assert len({item.classification_hash for item in frame_classifications}) == 2
    assert {item.source_identity for item in frame_classifications} == {
        f"candidate:supplied-frame:{first.specification_hash}:frame-a",
        f"candidate:supplied-frame:{second.specification_hash}:frame-b",
    }
    assert {
        item.classification_hash for item in frame_classifications
    } <= set(readiness.classification_identities)
    assert {
        frame.frame_id
        for item in (first, second)
        for frame in item.supplied_reference_frames
    } == {"frame-a", "frame-b"}


def _canonical_m13_fixture(tmp_path):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    specification, _ = _m13_specification(source_ref, derived_ref, with_frame=True)
    canonical_specification = CandidatePromotionCompiler._canonical_specification(specification)
    mechanism = CanonicalPhysicalMechanism(
        id="PM-M13-1",
        name="M13 reconstruction fixture",
        component_specifications=(canonical_specification,),
        components=(
            CanonicalPhysicalComponent(
                instance_id="motor",
                specification_hash=canonical_specification.specification_hash,
                role="actuator",
                interfaces=canonical_specification.interfaces,
            ),
        ),
    )
    manager = StateManager(tmp_path)
    snapshot = manager.create_revision(
        PROJECT_ID,
        state.model_copy(update={"physical_mechanisms": [mechanism]}),
    )
    resolver = ProjectArtifactResolver(
        ArtifactStore(tmp_path, project_id=PROJECT_ID, run_id="canonical-lookup")
    )
    return manager, resolver, source, derived, mechanism, snapshot


def _fresh_canonical_compiler(manager, resolver):
    return CanonicalPhysicalMechanismCompiler(manager, lambda project_id: resolver)


def test_fresh_canonical_reconstruction_verifies_all_m13_geometry_artifacts(
    tmp_path, monkeypatch
):
    manager, resolver, source, derived, mechanism, snapshot = _canonical_m13_fixture(tmp_path)
    reads = []
    verified_frames = []
    original_read = resolver.read_verified_in_project
    original_verify = MaterializedInterfaceVerifier.verify

    def record_read(*args, **kwargs):
        reads.append((args, kwargs))
        return original_read(*args, **kwargs)

    def record_verify(*args, **kwargs):
        verified_frames.append(args[3])
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(resolver, "read_verified_in_project", record_read)
    monkeypatch.setattr(MaterializedInterfaceVerifier, "verify", staticmethod(record_verify))

    reconstruction = _fresh_canonical_compiler(manager, resolver).reconstruct(
        PROJECT_ID, snapshot.revision, snapshot.state_hash, mechanism.id
    )

    assert reconstruction.canonical_mechanism == mechanism
    assert [call[0][0] for call in reads] == [derived.artifact_id, source.artifact_id]
    assert [call[1] for call in reads] == [
        {"expected_type": ArtifactType.STEP, "expected_hash": derived.sha256},
        {"expected_type": ArtifactType.STEP, "expected_hash": source.sha256},
    ]
    assert verified_frames[-1] == mechanism.component_specifications[0].supplied_reference_frames[0]


@pytest.mark.parametrize("artifact_name", ("source", "derived"))
def test_fresh_canonical_reconstruction_rejects_tampered_step_bytes(
    tmp_path, artifact_name
):
    manager, resolver, source, derived, mechanism, snapshot = _canonical_m13_fixture(tmp_path)
    artifact = source if artifact_name == "source" else derived
    artifact_path = tmp_path / artifact.relative_path
    artifact_path.write_bytes(f"tampered-{artifact_name}-step".encode())

    with pytest.raises(ValueError, match="canonical .*verification failed|tampered"):
        _fresh_canonical_compiler(manager, resolver).reconstruct(
            PROJECT_ID, snapshot.revision, snapshot.state_hash, mechanism.id
        )


@pytest.mark.parametrize("tamper", ["source_origin", "source_orientation", "active_frame_hash"])
def test_fresh_canonical_reconstruction_rejects_tampered_m13_frame_records(
    tmp_path, tamper, monkeypatch
):
    manager, resolver, _, _, mechanism, snapshot = _canonical_m13_fixture(tmp_path)
    reads = []
    original_read = resolver.read_verified_in_project

    def record_read(*args, **kwargs):
        reads.append((args, kwargs))
        return original_read(*args, **kwargs)

    monkeypatch.setattr(resolver, "read_verified_in_project", record_read)
    specification = mechanism.component_specifications[0]
    active_frame = specification.supplied_reference_frames[0]
    active_interface = specification.supplied_interface_definitions[0]
    provenance = active_interface.derivation
    assert provenance is not None

    if tamper == "active_frame_hash":
        tampered_frame = active_frame.model_copy(
            update={"frame_hash": "sha256:" + "f" * 64}
        )
        tampered_specification = specification.model_copy(
            update={"supplied_reference_frames": (tampered_frame,)}
        )
    else:
        source_frame = provenance.source_reference_frame_snapshot
        assert source_frame is not None
        fact = source_frame.origin if tamper == "source_origin" else source_frame.orientation
        evidence = fact.evidence[0].model_copy(update={"value": None})
        tampered_fact = fact.model_copy(update={"evidence": (evidence,)})
        tampered_source_frame = source_frame.model_copy(
            update={"origin" if tamper == "source_origin" else "orientation": tampered_fact}
        )
        tampered_provenance = provenance.model_copy(
            update={"source_reference_frame_snapshot": tampered_source_frame}
        )
        tampered_interface = active_interface.model_copy(
            update={"derivation": tampered_provenance}
        )
        tampered_specification = specification.model_copy(
            update={"supplied_interface_definitions": (tampered_interface,)}
        )

    tampered_mechanism = mechanism.model_copy(
        update={"component_specifications": (tampered_specification,)}
    )
    tampered_state = manager.load_revision(PROJECT_ID, snapshot.revision).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    manager.load_revision = lambda project_id, revision: tampered_state
    tampered_hash = state_hash(tampered_state)

    with pytest.raises(
        ValueError,
        match="canonical (mechanism|materialized interface) integrity failure|canonical materialized interface frame does not resolve",
    ):
        _fresh_canonical_compiler(manager, resolver).reconstruct(
            PROJECT_ID, snapshot.revision, tampered_hash, mechanism.id
        )
    assert [call[0][0] for call in reads] == ["ART-DERIVED", "ART-SRC"]


def test_fresh_canonical_reconstruction_materializes_mounting_face_after_artifact_verification(
    tmp_path, monkeypatch
):
    state = _state()
    source, derived = _publish_step_artifacts(tmp_path, state)
    source_ref = _geometry_reference(source, "source-model-coordinates@1")
    derived_ref = _geometry_reference(derived, "derived-model-coordinates@1")
    source_geometry = GeometryArtifactIdentity.from_candidate(source_ref)
    source_interface = SuppliedComponentInterfaceDefinition(
        interface_id="mount-face",
        geometry_reference_hash=source_ref.reference_hash,
        geometry=source_geometry,
        mounting_face=MountingFaceInterface(
            interface_id="mount-face",
            geometry_reference_hash=source_ref.reference_hash,
            geometry=source_geometry,
            face_reference_id="Face3",
            reference_frame_id="output-frame",
            plane_point=_interface_fact(
                "plane-point", SuppliedInterfaceTransformRole.POINT_MM, (0.0, 0.0, 0.0)
            ),
            outward_normal=_interface_fact(
                "plane-normal",
                SuppliedInterfaceTransformRole.DIRECTION_UNIT,
                (0.0, 0.0, 1.0),
            ),
            holes=(
                MountingHole(
                    hole_id="H.1",
                    center=_interface_fact(
                        "hole-center",
                        SuppliedInterfaceTransformRole.POINT_MM,
                        (3.0, 5.0, 0.0),
                    ),
                    axis=_interface_fact(
                        "hole-axis",
                        SuppliedInterfaceTransformRole.DIRECTION_UNIT,
                        (0.0, 0.0, 1.0),
                    ),
                    nominal_diameter=_interface_fact(
                        "hole-diameter",
                        SuppliedInterfaceTransformRole.LENGTH_MM,
                        4.0,
                    ),
                ),
            ),
        ),
    )
    transform = _transform(source_ref, derived_ref)
    materialized = materialize_interface(
        source_interface, _spec_frame(source_ref), transform
    )
    specification = ComponentSpecificationSnapshot(
        schema_version="component-specification@2",
        component_type="motor",
        source_identity="source:motor",
        geometry_source=derived_ref,
        interfaces=(materialized.interface.interface_id,),
        supplied_reference_frames=(materialized.reference_frame,),
        supplied_interface_definitions=(materialized.interface,),
        geometry_derivation_transforms=(transform,),
    )
    canonical_specification = CandidatePromotionCompiler._canonical_specification(
        specification
    )
    mechanism = CanonicalPhysicalMechanism(
        id="PM-M13-1-MOUNT",
        name="M13 mounting-face reconstruction fixture",
        component_specifications=(canonical_specification,),
        components=(
            CanonicalPhysicalComponent(
                instance_id="motor",
                specification_hash=canonical_specification.specification_hash,
                role="mount_or_support",
                interfaces=canonical_specification.interfaces,
            ),
        ),
    )
    manager = StateManager(tmp_path)
    snapshot = manager.create_revision(
        PROJECT_ID,
        state.model_copy(update={"physical_mechanisms": [mechanism]}),
    )
    canonical_state = manager.load_revision(PROJECT_ID, snapshot.revision)
    manager.load_revision = lambda project_id, revision: canonical_state
    resolver = ProjectArtifactResolver(
        ArtifactStore(
            tmp_path, project_id=PROJECT_ID, run_id="canonical-mount-lookup"
        )
    )
    events = []
    original_read = resolver.read_verified_in_project
    original_verify = MaterializedInterfaceVerifier.verify

    def record_read(*args, **kwargs):
        events.append(("artifact", args, kwargs))
        return original_read(*args, **kwargs)

    def record_verify(*args, **kwargs):
        events.append(("replay", args, kwargs))
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(resolver, "read_verified_in_project", record_read)
    monkeypatch.setattr(
        MaterializedInterfaceVerifier, "verify", staticmethod(record_verify)
    )

    reconstruction = _fresh_canonical_compiler(manager, resolver).reconstruct(
        PROJECT_ID, snapshot.revision, snapshot.state_hash, mechanism.id
    )

    assert reconstruction.canonical_mechanism == mechanism
    assert (
        reconstruction.canonical_mechanism.component_specifications[0]
        .supplied_interface_definitions[0]
        .mounting_face
        is not None
    )
    artifact_events = [event for event in events if event[0] == "artifact"]
    assert [event[1][0] for event in artifact_events] == [
        "ART-DERIVED",
        "ART-SRC",
    ]
    first_replay = min(
        index for index, event in enumerate(events) if event[0] == "replay"
    )
    assert all(
        index < first_replay
        for index, event in enumerate(events)
        if event[0] == "artifact"
    )


def test_fresh_canonical_reconstruction_rejects_stale_persisted_derived_value_after_artifact_verification(
    tmp_path, monkeypatch
):
    manager, resolver, _, _, mechanism, snapshot = _canonical_m13_fixture(tmp_path)
    specification = mechanism.component_specifications[0]
    active_interface = specification.supplied_interface_definitions[0]
    assert active_interface.shaft is not None
    diameter = active_interface.shaft.nominal_shaft_diameter
    tampered_diameter = diameter.model_copy(
        update={
            "evidence": (
                diameter.evidence[0].model_copy(update={"value": 999.0}),
            )
        }
    )
    tampered_shaft = active_interface.shaft.model_copy(
        update={"nominal_shaft_diameter": tampered_diameter}
    )
    tampered_interface = active_interface.model_copy(update={"shaft": tampered_shaft})
    tampered_specification = specification.model_copy(
        update={"supplied_interface_definitions": (tampered_interface,)}
    )
    tampered_mechanism = mechanism.model_copy(
        update={"component_specifications": (tampered_specification,)}
    )
    tampered_state = manager.load_revision(PROJECT_ID, snapshot.revision).model_copy(
        update={"physical_mechanisms": [tampered_mechanism]}
    )
    manager.load_revision = lambda project_id, revision: tampered_state
    reads = []
    original_read = resolver.read_verified_in_project

    def record_read(*args, **kwargs):
        reads.append((args, kwargs))
        return original_read(*args, **kwargs)

    monkeypatch.setattr(resolver, "read_verified_in_project", record_read)

    with pytest.raises(
        ValueError,
        match="canonical mechanism integrity failure|canonical materialized interface integrity failure",
    ):
        _fresh_canonical_compiler(manager, resolver).reconstruct(
            PROJECT_ID, snapshot.revision, state_hash(tampered_state), mechanism.id
        )
    assert [call[0][0] for call in reads] == ["ART-DERIVED", "ART-SRC"]
