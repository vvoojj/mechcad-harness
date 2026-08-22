from __future__ import annotations

import inspect
import json
from hashlib import sha256

import pytest

import mechcad_harness.application as application_module
from mechcad_harness.agents import AgentIdentity, FakeAgentAdapter
from mechcad_harness.application import ProductionApplication
from mechcad_harness.cad_service import CadSourceBindingError
from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram
from mechcad_harness.dependency.errors import EvidenceIntegrityError
from mechcad_harness.kinematic_sweep import CollisionClassification
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.models import Component, DesignState
from mechcad_harness.models.evidence import Evidence
from mechcad_harness.multi_joint_kinematics import (
    JointConfiguration,
    KinematicModel,
    RevoluteJointModel,
    kinematic_model_hash,
)
from mechcad_harness.state import StateManager
from mechcad_harness.transient_assembly_analysis import (
    TransientAssemblyAnalysisRequest,
)
from mechcad_harness.transient_freecad_measurement import (
    FreeCADTransientAssemblyMeasurementProvider,
)


def _application(tmp_path, *, measure=None):
    workspace = tmp_path / "workspace"
    ownership = tmp_path / "ownership.yaml"
    dependencies = tmp_path / "dependencies.yaml"
    ownership.write_text(
        "ownership:\n  - path: /components/*\n    owner: transmission_engineer\n",
        encoding="utf-8",
    )
    dependencies.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "when": ["/components/*"],
                        "invalidates": [
                            "analysis.multi_joint_collision_sweep",
                            "analysis.kinematic_sweep",
                        ],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    StateManager(workspace).create_project(
        "PRJ-m10-3",
        DesignState(
            id="DES-m10-3",
            revision=1,
            components=[Component(id="fixture", name="Fixture")],
        ),
    )
    identity = AgentIdentity(
        agent_name="mechcad-transmission",
        agent_version="1.0",
        role="transmission_engineer",
        protocol_version="1.0",
    )
    return ProductionApplication.create(
        workspace,
        "PRJ-m10-3",
        FakeAgentAdapter(identity, scripted_responses=()),
        ownership_path=ownership,
        dependency_path=dependencies,
        kinematic_measure=measure,
    )


def _assembly(*, include_second_stationary=False):
    part = CadPartProgram(
        part_id="link",
        operations=(
            BasePlateOperation(
                operation_id="plate",
                length_mm=10,
                width_mm=10,
                thickness_mm=2,
            ),
        ),
    )
    instances = (
        CadComponentInstance(instance_id="base", part_id="link"),
        CadComponentInstance(instance_id="link-1", part_id="link"),
        CadComponentInstance(instance_id="link-2", part_id="link"),
    )
    if include_second_stationary:
        instances += (CadComponentInstance(instance_id="base-2", part_id="link"),)
    return CadAssemblyProgram(
        assembly_id="m10-3-fixture",
        parts=(part,),
        instances=instances,
    )


def _model(*, axis_direction=(0.0, 0.0, 1.0)):
    return KinematicModel(
        model_id="model-3",
        joints=(
            RevoluteJointModel(
                joint_id="joint-1",
                parent_instance_id="base",
                child_instance_id="link-1",
                axis_direction_x=axis_direction[0],
                axis_direction_y=axis_direction[1],
                axis_direction_z=axis_direction[2],
            ),
            RevoluteJointModel(
                joint_id="joint-2",
                parent_instance_id="link-1",
                child_instance_id="link-2",
            ),
        ),
    )


def _configurations(model):
    return (
        JointConfiguration(
            model_id=model.model_id,
            positions={"joint-1": 0.0, "joint-2": 0.0},
        ),
        JointConfiguration(
            model_id=model.model_id,
            positions={"joint-1": 15.0, "joint-2": 5.0},
        ),
    )


def _measure(request: TransientAssemblyAnalysisRequest, _assembly):
    return tuple(
        (moving, stationary, 0.0, 1.0)
        for moving, stationary in request.pairs
    )


class _CustomBackend:
    pass


class _SpoofProvider(FreeCADTransientAssemblyMeasurementProvider):
    def exact_measure(self, request, assembly):
        return _measure(request, assembly)


def _external_callback_free_provider():
    provider = FreeCADTransientAssemblyMeasurementProvider()
    provider.exact_measure = _measure
    return provider


def _external_custom_backend_provider():
    provider = FreeCADTransientAssemblyMeasurementProvider(backend=_CustomBackend())
    provider.exact_measure = _measure
    return provider


def _run(
    application,
    assembly=None,
    model=None,
    configurations=None,
    moving_instance_ids=("link-1", "link-2"),
    stationary_instance_ids=("base",),
    source_revision=None,
    source_state_hash=None,
):
    assembly = assembly or _assembly()
    model = model or _model()
    source = application.load_state()
    return application.analyze_multi_joint_collision_sweep(
        source_revision=source.revision if source_revision is None else source_revision,
        source_state_hash=(
            source.state_hash if source_state_hash is None else source_state_hash
        ),
        assembly=assembly,
        model=model,
        configurations=(
            _configurations(model) if configurations is None else configurations
        ),
        moving_instance_ids=moving_instance_ids,
        stationary_instance_ids=stationary_instance_ids,
    )


def _assert_no_m10_3_evidence(application):
    evidence_dir = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "evidence"
    )
    if not evidence_dir.is_dir():
        return
    for path in evidence_dir.glob("*.json"):
        evidence = application.evidence_store.load_evidence(
            application.project_id, path.stem
        )
        assert evidence.kind != "analysis.multi_joint_collision_sweep"


def test_public_multi_joint_entrypoint_exposes_no_trusted_overrides():
    parameters = inspect.signature(
        ProductionApplication.analyze_multi_joint_collision_sweep
    ).parameters
    for forbidden in (
        "evaluator_version",
        "provider_name",
        "provider_version",
        "backend_provenance",
        "measurement_provider",
        "exact_measure",
    ):
        assert forbidden not in parameters


def test_deterministic_composition_persists_bound_m10_3_provenance(tmp_path):
    application = _application(tmp_path, measure=_measure)
    assembly = _assembly()
    model = _model()
    result = _run(application, assembly, model)

    evidence = application.get_multi_joint_collision_sweep_evidence(
        result.result_hash
    )
    assert evidence is not None
    provenance = evidence.analysis_execution_provenance
    assert provenance is not None
    assert provenance.provider_name == "deterministic-test-provider"
    assert provenance.backend_provenance is None
    assert provenance.model_hash == result.model_hash
    assert provenance.request_hash == result.request_hash
    assert provenance.result_hash == result.result_hash
    assert provenance.sweep_version == result.evaluator_version
    assert evidence.input_hash == result.request_hash
    assert evidence.output_hash == result.result_hash
    assert evidence.kind == "analysis.multi_joint_collision_sweep"
    assert evidence.backend_provenance is None
    assert evidence.id == application.get_multi_joint_collision_sweep_evidence(
        result.result_hash
    ).id


def test_default_application_composes_freecad_measurement_provider(tmp_path):
    application = _application(tmp_path)
    assert isinstance(
        application._kinematic_measurement_provider,
        FreeCADTransientAssemblyMeasurementProvider,
    )
    assert application._kinematic_measurement_provider_attested is True
    assert application._is_real_freecad_measurement_provider(
        application._kinematic_measurement_provider
    ) is True


@pytest.mark.parametrize(
    "provider_factory",
    (
        _external_callback_free_provider,
        _external_custom_backend_provider,
        _SpoofProvider,
    ),
    ids=("external-callback-free", "custom-backend", "subclass"),
)
def test_externally_supplied_freecad_provider_shapes_cannot_attest_as_live(
    tmp_path, provider_factory
):
    provider = provider_factory()
    application = _application(tmp_path, measure=provider)

    assert application._kinematic_measurement_provider_attested is False
    assert application._is_real_freecad_measurement_provider(provider) is False
    result = _run(application)
    evidence = application.get_multi_joint_collision_sweep_evidence(result.result_hash)
    assert evidence is not None
    assert evidence.analysis_execution_provenance.provider_name == (
        "deterministic-test-provider"
    )
    assert evidence.analysis_execution_provenance.backend_provenance is None


def test_provider_attestation_is_read_only_after_composition(tmp_path):
    application = _application(tmp_path, measure=_measure)

    with pytest.raises(AttributeError, match="read-only"):
        application._kinematic_measurement_provider_attested = True


def test_kinematic_measurement_dependencies_are_immutable_and_deterministic(tmp_path):
    application = _application(tmp_path, measure=_measure)
    original_measure = application.kinematic_measure
    original_provider = application._kinematic_measurement_provider

    with pytest.raises(AttributeError, match="read-only"):
        application.kinematic_measure = _measure
    with pytest.raises(AttributeError, match="read-only"):
        application._kinematic_measurement_provider = object()

    first = _run(application)
    second = _run(application)

    assert application.kinematic_measure is original_measure
    assert application._kinematic_measurement_provider is original_provider
    assert first.result_hash == second.result_hash
    first_evidence = application.get_multi_joint_collision_sweep_evidence(
        first.result_hash
    )
    assert first_evidence is not None
    assert first_evidence.analysis_execution_provenance.provider_name == (
        "deterministic-test-provider"
    )


def test_injected_freecad_provider_is_recorded_as_deterministic(tmp_path):
    provider = FreeCADTransientAssemblyMeasurementProvider(execute=_measure)
    application = _application(tmp_path, measure=provider)
    result = _run(application)

    evidence = application.get_multi_joint_collision_sweep_evidence(
        result.result_hash
    )
    assert evidence is not None
    provenance = evidence.analysis_execution_provenance
    assert provenance is not None
    assert provenance.provider_name == "deterministic-test-provider"
    assert provenance.provider_version == "deterministic-test@1.0"
    assert provenance.execution_mode == "deterministic-injected"
    assert provenance.backend_provenance is None
    assert evidence.backend_provenance is None


def test_injected_freecad_provider_cannot_run_continuous_proof(tmp_path):
    provider = FreeCADTransientAssemblyMeasurementProvider(execute=_measure)
    application = _application(tmp_path, measure=provider)
    source = application.load_state()

    with pytest.raises(ValueError, match="real FreeCAD measurement provider"):
        application.prove_continuous_single_axis_clearance(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=_assembly(),
            axis=RevoluteAxis(
                origin_x_mm=0.0,
                origin_y_mm=0.0,
                origin_z_mm=0.0,
                direction_x=0.0,
                direction_y=0.0,
                direction_z=1.0,
                frame_id="test-axis",
            ),
            moving_instance_ids=("link-1", "link-2"),
            stationary_instance_ids=("base",),
            start_angle_deg=0.0,
            end_angle_deg=10.0,
        )


def test_external_callback_free_freecad_provider_cannot_run_continuous_proof(tmp_path):
    application = _application(
        tmp_path, measure=FreeCADTransientAssemblyMeasurementProvider()
    )
    source = application.load_state()

    with pytest.raises(ValueError, match="real FreeCAD measurement provider"):
        application.prove_continuous_single_axis_clearance(
            source_revision=source.revision,
            source_state_hash=source.state_hash,
            assembly=_assembly(),
            axis=RevoluteAxis(
                origin_x_mm=0.0,
                origin_y_mm=0.0,
                origin_z_mm=0.0,
                direction_x=0.0,
                direction_y=0.0,
                direction_z=1.0,
                frame_id="test-axis",
            ),
            moving_instance_ids=("link-1", "link-2"),
            stationary_instance_ids=("base",),
            start_angle_deg=0.0,
            end_angle_deg=10.0,
        )


def test_legacy_provenance_payload_without_model_hash_remains_compatible():
    payload = {
        "request_hash": "sha256:request",
        "result_hash": "sha256:result",
        "source_assembly_hash": "sha256:assembly",
        "sweep_version": "cad-kinematic-sweep@1.0",
        "provider_name": "deterministic-test-provider",
        "provider_version": "deterministic-test@1.0",
        "execution_mode": "deterministic-injected",
        "recorded_at": "2026-01-01T00:00:00Z",
    }
    from mechcad_harness.analysis_provenance import AnalysisExecutionProvenance

    provenance = AnalysisExecutionProvenance.model_validate(payload)
    assert provenance.model_hash is None
    assert provenance.model_dump(mode="json", exclude_none=True) == payload


def test_evidence_store_preserves_legacy_persisted_shape_hash_and_id(tmp_path):
    application = _application(tmp_path, measure=_measure)
    request_hash = "sha256:legacy-request"
    result_hash = "sha256:legacy-result"
    evidence_id = "EVD-KSWEEP-" + sha256(
        (request_hash + result_hash).encode("utf-8")
    ).hexdigest()[:24]
    evidence = Evidence(
        id=evidence_id,
        kind="analysis.kinematic_sweep",
        summary="Trusted execution provenance for CadKinematicSweepResult",
        revision=1,
        state_hash="sha256:legacy-state",
        producer_type="kinematic_sweep_provider",
        producer_name="deterministic-test-provider",
        producer_version="deterministic-test@1.0",
        producer_result_id=result_hash,
        input_hash=request_hash,
        output_hash=result_hash,
        backend_provenance=None,
        analysis_execution_provenance={
            "request_hash": request_hash,
            "result_hash": result_hash,
            "source_assembly_hash": "sha256:legacy-assembly",
            "sweep_version": "cad-kinematic-sweep@1.0",
            "provider_name": "deterministic-test-provider",
            "provider_version": "deterministic-test@1.0",
            "execution_mode": "deterministic-injected",
            "backend_provenance": None,
            "recorded_at": "2026-01-01T00:00:00Z",
        },
    )

    application.evidence_store.write_evidence(application.project_id, evidence)

    path = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "evidence"
        / f"{evidence_id}.json"
    )
    persisted = json.loads(path.read_text(encoding="utf-8"))
    expected = evidence.model_dump(mode="json")
    expected["analysis_execution_provenance"].pop("model_hash")
    assert persisted == expected
    assert "model_hash" not in persisted["analysis_execution_provenance"]
    persisted_hash = "sha256:" + sha256(
        json.dumps(persisted, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert persisted_hash == (
        "sha256:a6b760bd1f27320eabe01cac363847462ffac86458d18baae2c097cd908586d6"
    )
    assert persisted["id"] == "EVD-KSWEEP-6370b617bacd3a4b90eb6e0a"


def test_failed_sweep_does_not_publish_m10_3_evidence(tmp_path):
    calls = 0

    def fail_on_second(request, _assembly):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("measurement failed")
        return _measure(request, _assembly)

    application = _application(tmp_path, measure=fail_on_second)
    with pytest.raises(RuntimeError, match="measurement failed"):
        _run(application)
    assert calls == 2
    _assert_no_m10_3_evidence(application)


def test_m10_3_evidence_write_failure_raises_without_return_or_publish(
    tmp_path, monkeypatch
):
    application = _application(tmp_path, measure=_measure)
    sentinel = object()

    def fail_write(_project_id, _evidence):
        raise RuntimeError("evidence write failed")

    monkeypatch.setattr(application.evidence_store, "write_evidence", fail_write)
    returned = sentinel
    with pytest.raises(RuntimeError, match="evidence write failed"):
        returned = _run(application)

    assert returned is sentinel
    assert application.get_multi_joint_collision_sweep_evidence(
        "sha256:never-published"
    ) is None
    evidence_dir = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "evidence"
    )
    assert not any(
        path.is_file() and path.name.startswith("EVD-MJCS-")
        for path in evidence_dir.glob("*.json")
    ) if evidence_dir.is_dir() else True


def test_legacy_evidence_payload_without_model_hash_remains_compatible():
    from mechcad_harness.models.evidence import Evidence

    payload = {
        "id": "EVD-legacy",
        "kind": "analysis.kinematic_sweep",
        "summary": "legacy",
        "revision": 1,
        "state_hash": "sha256:state",
        "analysis_execution_provenance": {
            "request_hash": "sha256:request",
            "result_hash": "sha256:result",
            "source_assembly_hash": "sha256:assembly",
            "sweep_version": "cad-kinematic-sweep@1.0",
            "provider_name": "deterministic-test-provider",
            "provider_version": "deterministic-test@1.0",
            "execution_mode": "deterministic-injected",
            "recorded_at": "2026-01-01T00:00:00Z",
        },
    }
    evidence = Evidence.model_validate(payload)
    assert evidence.analysis_execution_provenance.model_hash is None
    assert evidence.model_dump(mode="json", exclude_none=True) == payload


def test_provenance_model_hash_is_derived_from_the_model(tmp_path):
    application = _application(tmp_path, measure=_measure)
    result = _run(application)
    evidence = application.get_multi_joint_collision_sweep_evidence(
        result.result_hash
    )
    assert evidence.analysis_execution_provenance.model_hash == kinematic_model_hash(
        _model()
    )
    assert result.source_assembly_hash == assembly_hash(_assembly())


@pytest.mark.parametrize(
    ("failure", "expected"),
    (
        ("empty configurations", "at least one configuration"),
        ("unknown joint ID", "configuration mismatch"),
        ("joint limit violation", "above max"),
        ("wrong configuration model ID", "configuration model ID"),
        ("invalid model topology", "not in assembly"),
        ("unknown partition ID", "unknown"),
        ("duplicate moving partition ID", "duplicate"),
        ("overlapping partition ID", "overlap"),
    ),
)
def test_production_failures_publish_no_m10_3_evidence(tmp_path, failure, expected):
    application = _application(tmp_path, measure=_measure)
    model = _model()
    configurations = _configurations(model)
    assembly = _assembly()
    kwargs = {}

    if failure == "empty configurations":
        kwargs["configurations"] = ()
    elif failure == "unknown joint ID":
        kwargs["configurations"] = (
            JointConfiguration(
                model_id=model.model_id,
                positions={"joint-1": 0.0, "unknown": 0.0},
            ),
        )
    elif failure == "joint limit violation":
        limited_joint = model.joints[0].model_copy(update={"max_angle_deg": 10.0})
        model = model.model_copy(update={"joints": (limited_joint, model.joints[1])})
        configurations = _configurations(model)
        kwargs["model"] = model
        kwargs["configurations"] = configurations
    elif failure == "wrong configuration model ID":
        kwargs["configurations"] = (
            JointConfiguration(
                model_id="other-model",
                positions={"joint-1": 0.0, "joint-2": 0.0},
            ),
        )
    elif failure == "invalid model topology":
        invalid_joint = model.joints[1].model_copy(
            update={"child_instance_id": "missing-instance"}
        )
        model = model.model_copy(update={"joints": (model.joints[0], invalid_joint)})
        kwargs["model"] = model
    elif failure == "unknown partition ID":
        kwargs["moving_instance_ids"] = ("link-1", "unknown")
        kwargs["stationary_instance_ids"] = ("base", "link-2")
    elif failure == "duplicate moving partition ID":
        kwargs["moving_instance_ids"] = ("link-1", "link-1")
    elif failure == "overlapping partition ID":
        kwargs["moving_instance_ids"] = ("link-1",)
        kwargs["stationary_instance_ids"] = ("link-1", "base", "link-2")

    with pytest.raises(ValueError, match=expected):
        _run(application, assembly=assembly, **kwargs)
    _assert_no_m10_3_evidence(application)


def test_wrong_source_binding_publishes_no_m10_3_evidence(tmp_path):
    application = _application(tmp_path, measure=_measure)
    source = application.load_state()

    with pytest.raises(CadSourceBindingError):
        _run(
            application,
            source_revision=source.revision,
            source_state_hash="sha256:wrong-source-state",
        )
    _assert_no_m10_3_evidence(application)


def test_wrong_source_assembly_publishes_no_m10_3_evidence(tmp_path, monkeypatch):
    application = _application(tmp_path, measure=_measure)
    assembly = _assembly()
    wrong_source = assembly.model_copy(update={"assembly_id": "other-source"})

    request_type = application_module.MultiJointCollisionSweepRequest

    def request_with_wrong_source_id(**kwargs):
        kwargs["source_assembly_id"] = assembly.assembly_id
        return request_type(**kwargs)

    monkeypatch.setattr(
        application_module,
        "MultiJointCollisionSweepRequest",
        request_with_wrong_source_id,
    )

    with pytest.raises(ValueError, match="source assembly ID"):
        _run(application, assembly=wrong_source)
    _assert_no_m10_3_evidence(application)


@pytest.mark.parametrize(
    ("provider", "expected"),
    (
        (
            lambda request, assembly: (
                tuple(
                    (*pair, 0.0, 1.0, "extra")
                    for pair in request.pairs
                )
            ),
            "unpack",
        ),
        (
            lambda request, assembly: tuple(
                (moving, stationary, float("nan"), 1.0)
                for moving, stationary in request.pairs
            ),
            "finite",
        ),
        (
            lambda request, assembly: (_ for _ in ()).throw(
                RuntimeError("provider failed")
            ),
            "provider failed",
        ),
        (
            lambda request, assembly: tuple(
                (moving, stationary, 0.0, 1.0)
                for moving, stationary in request.pairs[:-1]
            ),
            "pair inventory",
        ),
    ),
)
def test_provider_failures_publish_no_m10_3_evidence(
    tmp_path, provider, expected
):
    application = _application(tmp_path, measure=provider)

    with pytest.raises((RuntimeError, ValueError), match=expected):
        _run(application)
    _assert_no_m10_3_evidence(application)


def test_production_request_and_result_identity_is_order_sensitive(tmp_path):
    application = _application(tmp_path, measure=_measure)
    model = _model()
    configurations = _configurations(model)

    first = _run(application, model=model, configurations=configurations)
    second = _run(application, model=model, configurations=configurations)
    assert first.request_hash == second.request_hash
    assert first.result_hash == second.result_hash

    reversed_result = _run(
        application,
        model=model,
        configurations=tuple(reversed(configurations)),
    )
    assert reversed_result.request_hash != first.request_hash
    assert reversed_result.result_hash != first.result_hash


def test_same_result_replay_accepts_existing_evidence_ignoring_recorded_at(tmp_path):
    application = _application(tmp_path, measure=_measure)
    first = _run(application)
    evidence = application.get_multi_joint_collision_sweep_evidence(first.result_hash)
    assert evidence is not None
    evidence_path = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "evidence"
        / f"{evidence.id}.json"
    )
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["analysis_execution_provenance"]["recorded_at"] = "2026-01-01T00:00:00Z"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    replay = _run(application)

    assert replay.request_hash == first.request_hash
    assert replay.result_hash == first.result_hash


def test_conflicting_existing_m10_3_evidence_fails_closed(tmp_path):
    application = _application(tmp_path, measure=_measure)
    result = _run(application)
    evidence = application.get_multi_joint_collision_sweep_evidence(result.result_hash)
    assert evidence is not None
    evidence_path = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "evidence"
        / f"{evidence.id}.json"
    )
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["output_hash"] = "sha256:conflicting-output"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvidenceIntegrityError, match="existing evidence mismatch"):
        _run(application)


def test_corrupt_m10_3_evidence_with_prefix_or_kind_fails_closed(tmp_path):
    application = _application(tmp_path, measure=_measure)
    evidence_dir = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "evidence"
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)

    prefix_path = evidence_dir / "EVD-MJCS-corrupt.json"
    prefix_path.write_text(
        "{not-json", encoding="utf-8"
    )
    with pytest.raises(EvidenceIntegrityError, match="invalid evidence record"):
        application.get_multi_joint_collision_sweep_evidence("sha256:missing")
    prefix_path.unlink()

    (evidence_dir / "EVD-legacy-m10-3.json").write_text(
        json.dumps({"kind": "analysis.multi_joint_collision_sweep"}),
        encoding="utf-8",
    )
    with pytest.raises(EvidenceIntegrityError, match="invalid evidence record"):
        application.get_multi_joint_collision_sweep_evidence("sha256:missing")


def test_corrupt_unrelated_legacy_evidence_remains_permissive(tmp_path):
    application = _application(tmp_path, measure=_measure)
    evidence_dir = (
        application.state_manager.workspace
        / "projects"
        / application.project_id
        / "evidence"
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "EVD-legacy-corrupt.json").write_text(
        "{not-json", encoding="utf-8"
    )

    assert application.get_multi_joint_collision_sweep_evidence("sha256:missing") is None


def test_angle_and_model_changes_change_production_identities(tmp_path):
    application = _application(tmp_path, measure=_measure)
    model = _model()
    configurations = _configurations(model)
    baseline = _run(application, model=model, configurations=configurations)

    angle_changed = _run(
        application,
        model=model,
        configurations=(
            configurations[0],
            JointConfiguration(
                model_id=model.model_id,
                positions={"joint-1": 16.0, "joint-2": 5.0},
            ),
        ),
    )
    assert (
        angle_changed.configuration_results[1].configuration_hash
        != baseline.configuration_results[1].configuration_hash
    )
    assert angle_changed.request_hash != baseline.request_hash
    assert angle_changed.result_hash != baseline.result_hash

    changed_model = _model(axis_direction=(1.0, 0.0, 0.0))
    model_changed = _run(application, model=changed_model)
    assert model_changed.model_hash != baseline.model_hash
    assert model_changed.request_hash != baseline.request_hash
    assert model_changed.result_hash != baseline.result_hash

    topology_changed = model.model_copy(
        update={
            "joints": (
                model.joints[0],
                model.joints[1].model_copy(update={"parent_instance_id": "base"}),
            )
        }
    )
    topology_result = _run(application, model=topology_changed)
    assert topology_result.model_hash != baseline.model_hash
    assert topology_result.request_hash != baseline.request_hash
    assert topology_result.result_hash != baseline.result_hash


def test_joint_mapping_insertion_order_does_not_change_production_identity(tmp_path):
    application = _application(tmp_path, measure=_measure)
    model = _model()
    first = _run(
        application,
        model=model,
        configurations=(
            JointConfiguration(
                model_id=model.model_id,
                positions={"joint-1": 10.0, "joint-2": 20.0},
            ),
        ),
    )
    second = _run(
        application,
        model=model,
        configurations=(
            JointConfiguration(
                model_id=model.model_id,
                positions={"joint-2": 20.0, "joint-1": 10.0},
            ),
        ),
    )
    assert first.request_hash == second.request_hash
    assert first.result_hash == second.result_hash


def test_production_evaluates_two_moving_by_two_stationary_pairs_in_order(tmp_path):
    application = _application(tmp_path, measure=_measure)
    model = _model()
    result = _run(
        application,
        assembly=_assembly(include_second_stationary=True),
        model=model,
        configurations=_configurations(model),
        stationary_instance_ids=("base", "base-2"),
    )

    expected_pairs = (
        ("link-1", "base"),
        ("link-1", "base-2"),
        ("link-2", "base"),
        ("link-2", "base-2"),
    )
    assert [
        tuple(
            (item.moving_instance_id, item.stationary_instance_id)
            for item in configuration_result.pair_results
        )
        for configuration_result in result.configuration_results
    ] == [expected_pairs, expected_pairs]


@pytest.mark.parametrize(
    ("volume", "distance", "classification", "summary"),
    (
        (
            1.0,
            1.0,
            CollisionClassification.INTERFERENCE,
            (True, False, False),
        ),
        (
            0.0,
            0.0,
            CollisionClassification.TOUCHING,
            (False, True, False),
        ),
        (
            0.0,
            1.0,
            CollisionClassification.POSITIVE_CLEARANCE,
            (False, False, True),
        ),
    ),
)
def test_production_summaries_distinguish_interference_touching_and_clearance(
    tmp_path, volume, distance, classification, summary
):
    def measure(request, assembly):
        return tuple(
            (moving, stationary, volume, distance)
            for moving, stationary in request.pairs
        )

    application = _application(tmp_path, measure=measure)
    result = _run(application)
    assert (
        result.any_interference,
        result.any_touching,
        result.all_positive_clearance,
    ) == summary
    assert all(
        configuration_result.classification is classification
        for configuration_result in result.configuration_results
    )
