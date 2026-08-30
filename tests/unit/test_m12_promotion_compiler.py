from __future__ import annotations

from types import SimpleNamespace

import pytest

from mechcad_harness.artifacts import ArtifactStore
from mechcad_harness.candidates import (
    CandidatePromotionCompiler,
    CandidatePromotionPolicy,
    CandidatePromotionRequest,
    CandidateEvaluationOutcome,
    CandidateCanonicalInstanceMapping,
    PromotionClassification,
    PromotionValueClassification,
)
from mechcad_harness.revolute_drive import InputProvenanceKind
from mechcad_harness.state import StateManager, state_hash
from mechcad_harness.candidates.models import (
    ComponentPropertyAvailability,
    ComponentPropertyAuthority,
    ComponentPropertySnapshot,
    GeometrySourceReference,
)
from mechcad_harness.candidates.promotion import _ExpectedClassification


def _inputs():
    from test_m12_candidate_evaluation import (
        _bound_m10_inputs,
        _evaluation_candidate,
        _evaluation_service,
        _m12_result,
    )
    from test_m12_candidate_foundation import _state
    from mechcad_harness.candidates import CandidateEvaluationPolicy, CandidateSelection

    state = _state()
    candidate, synthesis_request, synthesis_policy = _evaluation_candidate(state)
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

    def request_builder(*, inputs, **updates):
        candidate, synthesis_request, synthesis_policy, m12, evaluation, selection = inputs
        values = {
            "project_id": candidate.source_binding.project_id,
            "source_revision": candidate.source_binding.source_revision,
            "source_state_hash": candidate.source_binding.source_state_hash,
            "candidate": candidate,
            "synthesis_request": synthesis_request,
            "synthesis_policy": synthesis_policy,
            "m12_3_result": m12,
            "evaluation": evaluation,
            "selection": selection,
            "promotion_policy": CandidatePromotionPolicy(),
            "canonical_target_mechanism_id": "PM-1",
        }
        values.update(updates)
        return CandidatePromotionRequest(**values)

    return (
        candidate,
        synthesis_request,
        synthesis_policy,
        m12,
        evaluation,
        selection,
    ), request_builder, state


def _classifications(request: CandidatePromotionRequest):
    candidate = request.candidate
    values = []
    for specification in candidate.component_specifications:
        for prop in specification.properties:
            values.append(
                PromotionClassification(
                    source_identity=(
                        f"candidate:property:{specification.source_identity}:{prop.key}"
                    ),
                    classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    source_value=(
                        prop.normalized_value
                        if prop.normalized_value is not None
                        else tuple(prop.normalized_range)
                        if prop.normalized_range is not None
                        else None
                    ),
                )
            )
        if specification.geometry_source is not None:
            values.append(
                PromotionClassification(
                    source_identity=f"candidate:geometry-source:{specification.geometry_source.artifact_id}",
                    classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
                    source_value=specification.geometry_source.artifact_hash,
                )
            )
    for variable in candidate.design_variables:
        values.append(
            PromotionClassification(
                source_identity=f"candidate:design-variable:{variable.name}",
                classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
                source_value=variable.value,
            )
        )
    for component in candidate.realization.components:
        values.append(
            PromotionClassification(
                source_identity=f"candidate:physical-instance:{component.instance_id}",
                classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            )
        )
    for connection in candidate.realization.connections:
        values.append(
            PromotionClassification(
                source_identity=f"candidate:connection:{connection.connection_id}",
                classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            )
        )
    for binding in candidate.realization.joint_bindings:
        values.append(
            PromotionClassification(
                source_identity=f"candidate:joint-binding:{binding.joint_id}",
                classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            )
        )
    return tuple(values)


def _compiler(tmp_path, state):
    manager = StateManager(tmp_path)
    manager.create_project("PRJ-M12", state)
    return manager, CandidatePromotionCompiler(
        manager,
        lambda project_id: ArtifactStore(
            tmp_path, project_id=project_id, run_id="promotion-lookup"
        ),
        cad_replay_verifier=lambda *args: None,
    )


def test_readiness_validates_current_feasible_inputs_and_returns_explicit_mappings(tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    request = request.model_copy(update={"classifications": _classifications(request), "request_hash": "pending"})
    # Rebuild through the public model so the classification/request identities are bound.
    request = CandidatePromotionRequest.model_validate(request.model_dump(mode="json"))
    manager, compiler = _compiler(tmp_path, state)

    readiness = compiler.validate_readiness(request)
    mapping = compiler.map_instances(request)

    assert readiness.request_hash == request.request_hash
    assert readiness.mapping == mapping
    assert len(mapping) == len(candidate.realization.components)
    assert all(item.canonical_path.startswith("/physical_mechanisms/PM-1/components/") for item in mapping)
    assert all(isinstance(item, CandidateCanonicalInstanceMapping) for item in mapping)
    assert state_hash(manager.load_current_state("PRJ-M12")) == state_hash(state)


def test_readiness_rejects_stale_or_forged_candidate_without_state_mutation(tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    request = CandidatePromotionRequest.model_validate(
        request.model_copy(update={"classifications": _classifications(request), "request_hash": "pending"}).model_dump(mode="json")
    )
    manager, compiler = _compiler(tmp_path, state)
    before = manager.load_current_pointer("PRJ-M12")
    manager.create_revision("PRJ-M12", state.model_copy(update={"id": "changed"}))

    with pytest.raises(ValueError, match="current|stale|source|integrity"):
        compiler.validate_readiness(
            request.model_copy(
                update={"candidate": candidate.model_copy(update={"candidate_hash": "sha256:" + "f" * 64})}
            )
        )
    after = manager.load_current_pointer("PRJ-M12")
    assert after["revision"] == before["revision"] + 1
    assert after["state_hash"] != before["state_hash"]


@pytest.mark.parametrize("field", ["m12_3_result", "evaluation", "selection"])
def test_readiness_rejects_substituted_decision_records(field, tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    request = CandidatePromotionRequest.model_validate(
        request.model_copy(update={"classifications": _classifications(request), "request_hash": "pending"}).model_dump(mode="json")
    )
    _, compiler = _compiler(tmp_path, state)
    replacements = {
        "m12_3_result": m12.model_copy(update={"result_hash": "sha256:" + "f" * 64}),
        "evaluation": evaluation.model_copy(update={"candidate_hash": "sha256:" + "f" * 64}),
        "selection": selection.model_copy(update={"candidate_hash": "sha256:" + "f" * 64}),
    }
    forged = request.model_copy(update={field: replacements[field]})

    with pytest.raises(ValueError, match="identity|binding|integrity|current|candidate"):
        compiler.validate_readiness(forged)


def test_readiness_rejects_non_feasible_evaluation_and_m12_result(tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    request = CandidatePromotionRequest.model_validate(
        request.model_copy(update={"classifications": _classifications(request), "request_hash": "pending"}).model_dump(mode="json")
    )
    from mechcad_harness.revolute_drive import EngineeringCheckStatus
    from test_m12_candidate_evaluation import _m12_result

    _, compiler = _compiler(tmp_path, state)
    unresolved = evaluation.model_copy(update={"outcome": CandidateEvaluationOutcome.UNRESOLVED})
    with pytest.raises(ValueError, match="FEASIBLE|unresolved|integrity|outcome"):
        compiler.validate_readiness(request.model_copy(update={"evaluation": unresolved}))

    inadmissible = _m12_result(candidate, EngineeringCheckStatus.VIOLATED)
    with pytest.raises(ValueError, match="ADMISSIBLE|inadmissible|integrity|identity"):
        compiler.validate_readiness(request.model_copy(update={"m12_3_result": inadmissible}))


def test_mapping_rejects_omitted_and_duplicated_classifications_without_mutating_state(tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    base = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    classifications = _classifications(base)
    manager, compiler = _compiler(tmp_path, state)
    before = manager.load_current_pointer("PRJ-M12")

    omitted = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications[:-1],
    )
    duplicated = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications + (classifications[0],),
    )
    for request in (omitted, duplicated):
        with pytest.raises(ValueError, match="classification"):
            compiler.map_instances(request)
        assert manager.load_current_pointer("PRJ-M12") == before


def test_mapping_rejects_derived_authority_and_delimiter_ids(tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    base = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    classifications = _classifications(base)
    manager, compiler = _compiler(tmp_path, state)
    derived = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications
        + (
            PromotionClassification(
                source_identity=m12.result_hash,
                classification=PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
            ),
        ),
    )
    with pytest.raises(ValueError, match="derived|promot"):
        compiler.map_instances(derived)

    delimiter = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications,
        canonical_target_mechanism_id="PM:1",
    )
    with pytest.raises(ValueError, match="identifier|delimiter"):
        compiler.map_instances(delimiter)
    assert manager.load_current_pointer("PRJ-M12")["revision"] == state.revision


def test_readiness_rejects_comparison_flag_mismatch_without_state_mutation(tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    base = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=_classifications(base),
    )
    manager, compiler = _compiler(tmp_path, state)
    before = manager.load_current_pointer("PRJ-M12")
    forged = request.model_copy(update={"comparison_used": True})

    with pytest.raises(ValueError, match="comparison|integrity"):
        compiler.validate_readiness(forged)
    assert manager.load_current_pointer("PRJ-M12") == before


def test_readiness_rejects_property_value_substitution(tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    base = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    classifications = tuple(
        item.model_copy(
            update={"source_value": 999.0, "classification_hash": "pending"}
        )
        if item.source_identity.endswith(":rated_voltage") else item
        for item in _classifications(base)
    )
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications,
    )
    _, compiler = _compiler(tmp_path, state)

    with pytest.raises(ValueError, match="substitution|classification"):
        compiler.validate_readiness(request)


def test_trusted_geometry_verification_rejects_missing_or_tampered_source():
    class _MissingArtifactStore:
        def read_verified_in_project(self, *args, **kwargs):
            return None

    source = GeometrySourceReference(
        artifact_id="STEP-1",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="fixture:step",
    )
    request = SimpleNamespace(
        project_id="PRJ-M12",
        source_revision=1,
        source_state_hash="sha256:" + "b" * 64,
        candidate=SimpleNamespace(
            component_specifications=(SimpleNamespace(geometry_source=source),)
        ),
    )
    compiler = CandidatePromotionCompiler(
        StateManager("."),
        lambda: _MissingArtifactStore(),
        cad_replay_verifier=lambda *args: None,
    )

    with pytest.raises(ValueError, match="geometry|tampered|missing"):
        compiler._verify_geometry_sources(request)


@pytest.mark.parametrize(
    "identity",
    [
        "candidate:property:datasheet:example:MTR-24-100@1:continuous_torque",
        "candidate:property:catalog:bearing@1:dynamic_load_rating",
        "candidate:physical-instance:shaft",
    ],
)
def test_classification_rejects_source_value_substitution_for_non_scalar_inputs(
    identity, tmp_path
):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    base = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    classifications = tuple(
        item.model_copy(
            update={"source_value": "forged", "classification_hash": "pending"}
        )
        if item.source_identity == identity else item
        for item in _classifications(base)
    )
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications,
    )
    _, compiler = _compiler(tmp_path, state)

    with pytest.raises(ValueError, match="substitution|source value|classification"):
        compiler.map_instances(request)


@pytest.mark.parametrize("identity", ["candidate:connection:drive", "candidate:joint-binding:J-1"])
def test_classification_rejects_source_value_for_connection_or_joint(identity):
    classification = PromotionClassification(
        source_identity=identity,
        classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
        source_value="forged",
    )
    request = SimpleNamespace(
        classifications=(classification,), promotion_policy=CandidatePromotionPolicy()
    )

    with pytest.raises(ValueError, match="source value"):
        CandidatePromotionCompiler._classifications_by_identity(
            request, {identity: _ExpectedClassification(False)}
        )


def test_available_range_classification_compares_the_complete_range():
    prop = ComponentPropertySnapshot(
        key="range",
        availability=ComponentPropertyAvailability.AVAILABLE,
        normalized_range=(1.0, 2.0),
        canonical_unit="mm",
        source_identity="fixture:range",
        authority=ComponentPropertyAuthority.USER_DECLARED,
    )
    request = SimpleNamespace(
        candidate=SimpleNamespace(
            component_specifications=(
                SimpleNamespace(
                    source_identity="fixture:spec",
                    properties=(prop,),
                    geometry_source=None,
                ),
            ),
            design_variables=(),
            realization=SimpleNamespace(components=(), connections=(), joint_bindings=()),
        )
    )
    expected = CandidatePromotionCompiler._expected_classifications(request)
    classification = PromotionClassification(
        source_identity="candidate:property:fixture:spec:range",
        classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
        source_value=(1.0, 2.0),
    )
    classification_request = SimpleNamespace(
        classifications=(classification,), promotion_policy=CandidatePromotionPolicy()
    )

    assert "candidate:property:fixture:spec:range" in CandidatePromotionCompiler._classifications_by_identity(
        classification_request, expected
    )

    forged = classification.model_copy(
        update={"source_value": (1.0, 3.0), "classification_hash": "pending"}
    )
    with pytest.raises(ValueError, match="substitution"):
        CandidatePromotionCompiler._classifications_by_identity(
            SimpleNamespace(
                classifications=(forged,), promotion_policy=CandidatePromotionPolicy()
            ),
            expected,
        )


def test_unknown_derived_looking_identity_is_not_an_implicit_do_not_promote_allowlist(
    tmp_path,
):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    base = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=_classifications(base)
        + (
            PromotionClassification(
                source_identity="candidate:m10:unrelated-result",
                classification=PromotionValueClassification.DO_NOT_PROMOTE,
            ),
        ),
    )
    _, compiler = _compiler(tmp_path, state)

    with pytest.raises(ValueError, match="unknown|derived|classification"):
        compiler.map_instances(request)


@pytest.mark.parametrize("source_value", [0, 0.0, False])
def test_policy_assumption_classification_requires_explicit_value_even_when_falsy(source_value, tmp_path):
    (candidate, synthesis_request, synthesis_policy, m12, evaluation, selection), request_builder, state = _inputs()
    base_request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=(),
    )
    classifications = tuple(
        item.model_copy(
            update={
                "source_provenance": InputProvenanceKind.POLICY_ASSUMPTION,
                "classification": PromotionValueClassification.ACCEPTED_DESIGN_CHOICE,
                "source_value": source_value,
                "classification_hash": "pending",
            }
        )
        if item.source_identity == "candidate:physical-instance:shaft" else item
        for item in _classifications(base_request)
    )
    request = request_builder(
        inputs=(candidate, synthesis_request, synthesis_policy, m12, evaluation, selection),
        classifications=classifications,
    )
    _, compiler = _compiler(tmp_path, state)
    with pytest.raises(ValueError, match="classification|design variable|policy"):
        compiler.validate_readiness(request)


def test_compile_rejects_unrepresentable_motion_before_mutating_state(tmp_path):
    inputs, request_builder, state = _inputs()
    base_request = request_builder(inputs=inputs, classifications=())
    request = CandidatePromotionRequest.model_validate(
        base_request.model_copy(
            update={"classifications": _classifications(base_request), "request_hash": "pending"}
        ).model_dump(mode="json")
    )
    manager, compiler = _compiler(tmp_path, state)
    before_hash = state_hash(manager.load_current_state("PRJ-M12"))

    with pytest.raises(ValueError, match="exact|joint binding|correspond"):
        compiler.compile(state, request)

    assert state_hash(manager.load_current_state("PRJ-M12")) == before_hash


def test_compile_rejects_a_state_that_is_not_the_request_base(tmp_path):
    inputs, request_builder, state = _inputs()
    base_request = request_builder(inputs=inputs, classifications=())
    request = CandidatePromotionRequest.model_validate(
        base_request.model_copy(
            update={"classifications": _classifications(base_request), "request_hash": "pending"}
        ).model_dump(mode="json")
    )
    _, compiler = _compiler(tmp_path, state)

    with pytest.raises(ValueError, match="source|state|revision|base"):
        compiler.compile(state.model_copy(update={"id": "different"}), request)


def test_interface_resolution_requires_a_unique_declared_pair_endpoint():
    from types import SimpleNamespace

    compiler = object.__new__(CandidatePromotionCompiler)
    request = SimpleNamespace(
        candidate=SimpleNamespace(
            realization=SimpleNamespace(
                components=(SimpleNamespace(instance_id="hub", interfaces=("shaft", "body")),),
                connections=(),
            )
        )
    )

    with pytest.raises(ValueError, match="ambiguous|interface"):
        compiler._interface_for(request, "hub", "mount", "hub-mount")


def test_interface_resolution_uses_only_the_unique_connection_between_pair_endpoints():
    from types import SimpleNamespace

    compiler = object.__new__(CandidatePromotionCompiler)
    request = SimpleNamespace(
        candidate=SimpleNamespace(
            realization=SimpleNamespace(
                components=(
                    SimpleNamespace(instance_id="hub", interfaces=("shaft", "body")),
                    SimpleNamespace(instance_id="mount", interfaces=("frame", "motor")),
                ),
                connections=(
                    SimpleNamespace(
                        from_instance_id="hub",
                        from_interface_id="shaft",
                        to_instance_id="mount",
                        to_interface_id="frame",
                    ),
                ),
            )
        )
    )

    assert compiler._interface_for(request, "hub", "mount", "hub-mount") == "shaft"


def test_motion_compilation_requires_exact_candidate_physical_joint_binding():
    inputs, request_builder, _ = _inputs()
    base_request = request_builder(inputs=inputs, classifications=())
    request = CandidatePromotionRequest.model_validate(
        base_request.model_copy(
            update={"classifications": _classifications(base_request), "request_hash": "pending"}
        ).model_dump(mode="json")
    )
    compiler = object.__new__(CandidatePromotionCompiler)
    canonical_by_candidate = {
        component.instance_id: f"PM-1:{component.instance_id}"
        for component in request.candidate.realization.components
    }

    with pytest.raises(ValueError, match="exact|joint binding|correspond"):
        compiler._canonical_motion_semantics(request, canonical_by_candidate)


def test_motion_compilation_rejects_a_physical_binding_with_a_different_driven_instance():
    from mechcad_harness.candidates.models import JointPhysicalRealizationBinding

    inputs, request_builder, _ = _inputs()
    base_request = request_builder(inputs=inputs, classifications=())
    request = CandidatePromotionRequest.model_validate(
        base_request.model_copy(
            update={"classifications": _classifications(base_request), "request_hash": "pending"}
        ).model_dump(mode="json")
    )
    canonical_by_candidate = {
        component.instance_id: f"PM-1:{component.instance_id}"
        for component in request.candidate.realization.components
    }
    m10_binding = request.evaluation.m10_binding
    physical_binding = JointPhysicalRealizationBinding(
        joint_id=m10_binding.output_joint_id,
        driven_instance_id="motor",
        realization_component_ids=tuple(canonical_by_candidate),
        axis_frame_reference="joint:output-joint",
        load_path_metadata_available=False,
    )
    request = request.model_copy(
        update={
            "candidate": request.candidate.model_copy(
                update={
                    "realization": request.candidate.realization.model_copy(
                        update={"joint_bindings": (physical_binding,)}
                    )
                }
            )
        }
    )

    with pytest.raises(ValueError, match="child|driven|selected joint"):
        object.__new__(CandidatePromotionCompiler)._canonical_motion_semantics(
            request, canonical_by_candidate
        )


def test_motion_compilation_rejects_unrepresentable_scope_policy_assumptions():
    from mechcad_harness.candidates.models import JointPhysicalRealizationBinding

    inputs, request_builder, _ = _inputs()
    base_request = request_builder(inputs=inputs, classifications=())
    request = CandidatePromotionRequest.model_validate(
        base_request.model_copy(
            update={"classifications": _classifications(base_request), "request_hash": "pending"}
        ).model_dump(mode="json")
    )
    compiler = object.__new__(CandidatePromotionCompiler)
    canonical_by_candidate = {
        component.instance_id: f"PM-1:{component.instance_id}"
        for component in request.candidate.realization.components
    }
    binding = request.evaluation.m10_binding
    candidate = request.candidate.model_copy(
        update={
            "realization": request.candidate.realization.model_copy(
                update={
                    "joint_bindings": (
                        JointPhysicalRealizationBinding(
                            joint_id=binding.output_joint_id,
                            driven_instance_id="shaft",
                            realization_component_ids=tuple(canonical_by_candidate),
                            axis_frame_reference="joint:output-joint",
                            load_path_metadata_available=False,
                        ),
                    )
                }
            )
        }
    )
    request = request.model_copy(update={"candidate": candidate})

    with pytest.raises(ValueError, match="policy assumption|unrepresentable|scope"):
        compiler._canonical_motion_semantics(request, canonical_by_candidate)


def test_motion_compilation_rejects_scope_without_a_clearance_obligation():
    from mechcad_harness.candidates.models import JointPhysicalRealizationBinding
    from mechcad_harness.candidates.m10_evaluation import CandidateM10PairClassification

    inputs, request_builder, _ = _inputs()
    base_request = request_builder(inputs=inputs, classifications=())
    request = CandidatePromotionRequest.model_validate(
        base_request.model_copy(
            update={"classifications": _classifications(base_request), "request_hash": "pending"}
        ).model_dump(mode="json")
    )
    compiler = object.__new__(CandidatePromotionCompiler)
    canonical_by_candidate = {
        component.instance_id: f"PM-1:{component.instance_id}"
        for component in request.candidate.realization.components
    }
    binding = request.evaluation.m10_binding
    physical_binding = JointPhysicalRealizationBinding(
        joint_id=binding.output_joint_id,
        driven_instance_id="shaft",
        realization_component_ids=tuple(canonical_by_candidate),
        axis_frame_reference="joint:output-joint",
        load_path_metadata_available=False,
    )
    candidate = request.candidate.model_copy(
        update={
            "realization": request.candidate.realization.model_copy(
                update={"joint_bindings": (physical_binding,)}
            )
        }
    )
    excluded_scope = request.evaluation.m10_scope.model_copy(
        update={
            "pair_scope_requirements": tuple(
                requirement.model_copy(
                    update={
                        "required_classification": CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED
                    }
                )
                for requirement in request.evaluation.m10_scope.pair_scope_requirements
            ),
            "policy_assumptions": (),
            "scope_hash": "pending",
        }
    )
    evaluation = request.evaluation.model_copy(
        update={"m10_scope": excluded_scope, "evaluation_hash": "pending"}
    )
    request = request.model_copy(update={"candidate": candidate, "evaluation": evaluation})

    with pytest.raises(ValueError, match="clearance|represent|obligation"):
        compiler._canonical_motion_semantics(request, canonical_by_candidate)
