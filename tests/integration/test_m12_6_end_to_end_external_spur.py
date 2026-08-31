from __future__ import annotations

from types import SimpleNamespace
import json
import os

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad
from mechcad_harness.candidates import (
    CandidateComparisonRequest,
    CandidateDesignVariable,
    CandidateEvaluationOutcome,
    CandidateEvaluationPolicy,
    CandidateM10BodyDisposition,
    CandidateCollisionPairInventory,
    CandidateM10PairClassification,
    CandidateM10StageStatus,
    CandidateCadStageStatus,
    CandidateMetricKey,
    CandidatePromotionPolicy,
    CandidateSynthesisPolicy,
    CandidatePromotionRequest,
    PromotedMechanismVerificationStatus,
)
from mechcad_harness.models import CanonicalMechanicalConnectionKind
from mechcad_harness.state import StateManager
from mechcad_harness.tools import GearworksTools
from mechcad_harness.candidates.models import GeometrySourceReference

from m12_6_acceptance_fixtures import (
    SOURCE_LABEL,
    UninvokedAcceptanceAdapter,
    direct_drive_state,
    write_project_configuration,
)
from test_m12_candidate_cad_m10_production import (
    _candidate_template,
    _cad_request,
    _publish_gear_step,
    _publish_source_step,
)
from test_m12_promotion_production import (
    _promotion_classifications,
    _task17_m10_inputs,
)
from test_m12_revolute_drive_production import DriveArchitecture
from test_m12_revolute_drive_production import make_request, policy_for, spur_requirements
from mechcad_harness.application import ProductionApplication


FREECADCMD = r"C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe"


def _bootstrap_external_spur(tmp_path, project_id):
    workspace, ownership_path, dependency_path = write_project_configuration(tmp_path)
    StateManager(workspace).create_project(project_id, direct_drive_state())
    acceptance_adapter = UninvokedAcceptanceAdapter()
    app = ProductionApplication.create(
        workspace,
        project_id,
        acceptance_adapter,
        ownership_path=ownership_path,
        dependency_path=dependency_path,
        additional_tool_registrations=GearworksTools.registrations(),
    )
    source = app.load_state()
    assert source.revision == 1
    source_artifacts = {
        instance_id: _publish_source_step(
            app,
            part_id=f"m126-spur-{instance_id}",
            size=(20.0 + index, 20.0, 5.0),
        )
        for index, instance_id in enumerate(
            (
                "drive-motor",
                "output-shaft",
                "bearing-a",
                "bearing-b",
                "output-hub",
                "support-mount-a",
                "support-mount-b",
            )
        )
    }
    source_artifacts.update(
        {
            "driver-gear": _publish_gear_step(app, teeth=20),
            "driven-gear": _publish_gear_step(app, teeth=100),
        }
    )
    source_run_ids = {artifact.run_id for artifact in source_artifacts.values()}
    assert source_run_ids
    for artifact in source_artifacts.values():
        assert artifact.project_id == project_id
        assert artifact.bound_revision == source.revision
        assert artifact.bound_state_hash == source.state_hash
        assert artifact.artifact_type is ArtifactType.STEP
        store = ArtifactStore(
            workspace,
            project_id=project_id,
            run_id=artifact.run_id,
        )
        verified, content = store.read_verified_strict(
            artifact.artifact_id,
            expected_type=ArtifactType.STEP,
            expected_hash=artifact.sha256,
        )
        assert verified.artifact_id == artifact.artifact_id
        assert content
        assert (workspace / artifact.relative_path).read_bytes() == content
    return SimpleNamespace(
        app=app,
        source=source,
        source_artifacts=source_artifacts,
        source_run_ids=source_run_ids,
        ownership_path=ownership_path,
        dependency_path=dependency_path,
        acceptance_adapter=acceptance_adapter,
        source_label=SOURCE_LABEL,
    )


def _external_positions(output_x_mm):
    return {
        "drive-motor": (150.0, 150.0, 0.0),
        "driver-gear": (40.0, 0.0, 0.0),
        "driven-gear": (80.0, 0.0, 0.0),
        "output-shaft": (output_x_mm, 0.0, 0.0),
        "bearing-a": (100.0, 30.0, 0.0),
        "bearing-b": (100.0, -30.0, 0.0),
        "output-hub": (output_x_mm, 0.0, 0.0),
        "motor-mount": (0.0, 0.0, 0.0),
        "support-mount-a": (120.0, 30.0, 0.0),
        "support-mount-b": (120.0, -30.0, 0.0),
        "payload-body": (output_x_mm, 0.0, 0.0),
    }


def _external_spur_candidate(fixture, output_x_mm, tag):
    synthesis_request = make_request(
        fixture.app, DriveArchitecture.EXTERNAL_SPUR_REDUCTION
    )
    synthesis_policy = policy_for(DriveArchitecture.EXTERNAL_SPUR_REDUCTION)
    positions = _external_positions(output_x_mm)
    candidate_template = _candidate_template(
        DriveArchitecture.EXTERNAL_SPUR_REDUCTION,
        fixture.source_artifacts,
        positions,
        gear_artifact={
            "driver-gear": fixture.source_artifacts["driver-gear"],
            "driven-gear": fixture.source_artifacts["driven-gear"],
        },
        extra_design_variables=(CandidateDesignVariable(name="comparison-tag", value=tag),),
    )

    def relabel(specification, artifact):
        source = GeometrySourceReference(
            artifact_id=artifact.artifact_id,
            artifact_hash=artifact.sha256,
            source_identity=f"{fixture.source_label}:STEP:{artifact.artifact_id}",
        )
        return type(specification).model_validate(
            specification.model_dump(mode="json")
            | {"geometry_source": source.model_dump(mode="json"), "specification_hash": "pending"}
        )

    source_fields = {
        "motor_specification": "drive-motor",
        "shaft_specification": "output-shaft",
        "bearing_a_specification": "bearing-a",
        "bearing_b_specification": "bearing-b",
        "hub_specification": "output-hub",
        "driver_gear_specification": "driver-gear",
        "driven_gear_specification": "driven-gear",
    }
    updates = {
        field: relabel(getattr(candidate_template, field), fixture.source_artifacts[instance_id])
        for field, instance_id in source_fields.items()
    }
    updates["support_mount_specifications"] = tuple(
        relabel(specification, fixture.source_artifacts[instance_id])
        for specification, instance_id in zip(
            candidate_template.support_mount_specifications,
            ("support-mount-a", "support-mount-b"),
            strict=True,
        )
    )
    candidate_template = candidate_template.model_copy(update=updates)
    for specification, instance_id in (
        *(
            (getattr(candidate_template, field), instance_id)
            for field, instance_id in source_fields.items()
        ),
        *zip(
            candidate_template.support_mount_specifications,
            ("support-mount-a", "support-mount-b"),
            strict=True,
        ),
    ):
        source = specification.geometry_source
        expected_artifact = fixture.source_artifacts[instance_id]
        assert source is not None
        assert (
            source.artifact_id,
            source.artifact_hash,
            source.source_identity,
        ) == (
            expected_artifact.artifact_id,
            expected_artifact.sha256,
            f"{fixture.source_label}:STEP:{expected_artifact.artifact_id}",
        )

    policy_entries = list(synthesis_policy.entries)
    declared_policy_keys = {entry[0] for entry in policy_entries}
    for variable in candidate_template.design_variables:
        key = f"allow-design-variable:{variable.name}"
        if key not in declared_policy_keys:
            policy_entries.append(
                (
                    key,
                    json.dumps({"value": variable.value}, sort_keys=True, separators=(",", ":")),
                    "hard_admissibility",
                )
            )
    synthesis_policy = CandidateSynthesisPolicy(entries=tuple(policy_entries))
    outcome = fixture.app.realize_and_evaluate_revolute_drive(
        request=synthesis_request,
        policy=synthesis_policy,
        template_input=candidate_template,
        requirements=spur_requirements(require_nominal_interface_compatibility=True),
    )
    assert outcome.construction.status.value == "admissible"
    assert outcome.construction.candidate is not None
    assert outcome.evaluation is not None
    assert outcome.evaluation.status.value == "admissible"
    return outcome.construction.candidate, synthesis_request, synthesis_policy, outcome.evaluation


def _candidate_and_evaluation(fixture, output_x_mm, tag):
    candidate, synthesis_request, synthesis_policy, m12_result = _external_spur_candidate(
        fixture, output_x_mm, tag
    )
    candidate_cad_request = _cad_request(candidate)
    candidate_cad = fixture.app.realize_candidate_cad(
        candidate,
        synthesis_request,
        synthesis_policy,
        candidate_cad_request,
    )
    assert candidate_cad.status is CandidateCadStageStatus.SUCCESS
    assert candidate_cad.realization is not None
    assert (
        candidate.source_binding.source_revision,
        candidate.source_binding.source_state_hash,
    ) == (fixture.source.revision, fixture.source.state_hash)
    candidate_scope, candidate_binding, candidate_m10_request = _task17_m10_inputs(
        candidate,
        candidate_cad,
        external_spur=True,
    )
    base_inventory = CandidateCollisionPairInventory.complete_for(
        candidate_cad.realization,
        candidate_binding,
        candidate_scope,
    )
    classifications = tuple(
        item.model_copy(
            update={
                "classification": CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED,
                "reason": "declared gear mesh interface is outside M10 scope",
                "classification_hash": "pending",
            }
        )
        if set(item.pair)
        == {"cad-driver-gear", "cad-driven-gear"}
        else item
        for item in base_inventory.classifications
    )
    inventory = CandidateCollisionPairInventory.complete_for(
        candidate_cad.realization,
        candidate_binding,
        candidate_scope,
        classifications,
    )
    candidate_m10_request = type(candidate_m10_request).model_validate(
        candidate_m10_request.model_dump(mode="json")
        | {"inventory": inventory.model_dump(mode="json"), "request_hash": "pending"}
    )
    evaluation = fixture.app.evaluate_candidate(
        candidate,
        synthesis_request,
        synthesis_policy,
        m12_result,
        candidate_cad_request,
        candidate_m10_request,
        candidate_scope,
        candidate_binding,
        evaluation_policy=CandidateEvaluationPolicy(),
    )
    assert evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert evaluation.cad_stage_outcome.status is CandidateCadStageStatus.SUCCESS
    assert evaluation.m10_stage_outcome.status is CandidateM10StageStatus.SUCCESS
    stage = SimpleNamespace(
        candidate=candidate,
        synthesis_request=synthesis_request,
        synthesis_policy=synthesis_policy,
        m12_result=m12_result,
        cad_request=candidate_cad_request,
        cad=candidate_cad,
        scope=candidate_scope,
        binding=candidate_binding,
        m10_request=candidate_m10_request,
        evaluation=evaluation,
    )
    _assert_candidate_source_geometry(fixture, stage)
    return stage


def _verified_clearance_lower_bound(evaluation):
    metrics = tuple(
        metric
        for metric in evaluation.metrics
        if metric.key is CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM
    )
    assert len(metrics) == 1
    metric = next(iter(metrics))
    assert metric.unit == "mm"
    return metric.value


def _assert_candidate_source_geometry(fixture, stage):
    specifications = {
        specification.specification_hash: specification
        for specification in stage.candidate.component_specifications
    }
    source_by_artifact_id = {}
    for component in stage.candidate.realization.components:
        specification = specifications[component.specification_hash]
        source = specification.geometry_source
        expected_artifact = fixture.source_artifacts.get(component.instance_id)
        if expected_artifact is None:
            assert source is None
            continue
        assert source is not None
        assert (
            source.artifact_id,
            source.artifact_hash,
            source.source_identity,
        ) == (
            expected_artifact.artifact_id,
            expected_artifact.sha256,
            f"{fixture.source_label}:STEP:{expected_artifact.artifact_id}",
        )
        source_by_artifact_id[source.artifact_id] = source

    assert set(source_by_artifact_id) == {
        artifact.artifact_id for artifact in fixture.source_artifacts.values()
    }
    assert len(source_by_artifact_id) == len(fixture.source_artifacts)

    candidate_cad = stage.evaluation.cad_stage_outcome.realization
    assert candidate_cad is not None
    assert candidate_cad.realization_hash == stage.cad.realization_hash
    imported_by_id = {
        component.component_id: component
        for component in candidate_cad.assembly.imported_components
    }
    mappings_by_physical_id = {
        mapping.physical_instance_id: mapping for mapping in candidate_cad.mappings
    }
    for instance_id, expected_artifact in fixture.source_artifacts.items():
        source = source_by_artifact_id[expected_artifact.artifact_id]
        mapping = mappings_by_physical_id[instance_id]
        imported = imported_by_id[mapping.cad_instance_id]
        assert imported.artifact_id == source.artifact_id == expected_artifact.artifact_id
        assert imported.artifact_hash == source.artifact_hash == expected_artifact.sha256
        assert mapping.geometry_definition_identities == (expected_artifact.artifact_id,)
        assert mapping.source_geometry_identity == expected_artifact.sha256
    assert set(candidate_cad.verified_source_content_identities) == {
        artifact.sha256 for artifact in fixture.source_artifacts.values()
    }


def _resolve_source_artifact(fixture, artifact_id, artifact_hash):
    verified = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id="project-lookup",
    ).read_verified_in_project(
        artifact_id,
        expected_type=ArtifactType.STEP,
        expected_hash=artifact_hash,
    )
    assert verified is not None
    artifact, content = verified
    assert content
    return artifact


def _assert_gear_provenance(fixture, stage, canonical_cad):
    candidate_cad = stage.evaluation.cad_stage_outcome.realization
    assert candidate_cad is not None
    imported_by_id = {
        component.component_id: component
        for component in candidate_cad.assembly.imported_components
    }
    candidate_mappings = {
        mapping.physical_instance_id: mapping for mapping in candidate_cad.mappings
    }
    canonical_sources = {
        source.artifact_id: source for source in canonical_cad.selected_source_provenance
    }
    for instance_id in ("driver-gear", "driven-gear"):
        expected = fixture.source_artifacts[instance_id]
        candidate_mapping = candidate_mappings[instance_id]
        imported = imported_by_id[candidate_mapping.cad_instance_id]
        assert imported.artifact_id == expected.artifact_id
        assert imported.artifact_hash == expected.sha256
        candidate_artifact = _resolve_source_artifact(
            fixture, imported.artifact_id, imported.artifact_hash
        )
        assert candidate_artifact.backend_provenance is not None
        assert candidate_artifact.backend_provenance.library_name == "py_gearworks"
        assert candidate_artifact.backend_provenance.library_version
        assert candidate_artifact.build123d_provenance is not None
        assert candidate_artifact.build123d_provenance.library_name == "build123d"
        assert candidate_artifact.build123d_provenance.library_version

        canonical_source = canonical_sources[expected.artifact_id]
        assert canonical_source.sha256 == expected.sha256
        canonical_artifact = _resolve_source_artifact(
            fixture, canonical_source.artifact_id, canonical_source.sha256
        )
        assert canonical_source.backend_provenance is not None
        assert canonical_source.backend_provenance == canonical_artifact.backend_provenance
        assert canonical_source.backend_provenance.library_name == "py_gearworks"
        assert canonical_source.build123d_provenance is not None
        assert canonical_source.build123d_provenance == canonical_artifact.build123d_provenance
        assert canonical_source.build123d_provenance.library_name == "build123d"
    print(
        "M12_6_EXTERNAL_SPUR_GEAR_PROVENANCE="
        + json.dumps(
            {
                "py_gearworks": candidate_artifact.backend_provenance.library_version,
                "build123d": candidate_artifact.build123d_provenance.library_version,
            },
            sort_keys=True,
        )
    )


def _assert_canonical_source_geometry(fixture, stage, reconstruction, canonical_cad):
    candidate_sources = {
        specification.source_identity: specification.geometry_source
        for specification in stage.candidate.component_specifications
        if specification.geometry_source is not None
    }
    canonical_sources = {
        specification.source_identity: specification.geometry_source
        for specification in reconstruction.mechanism.component_specifications
        if specification.geometry_source is not None
    }
    assert set(canonical_cad.selected_source_artifact_ids) == {
        artifact.artifact_id for artifact in fixture.source_artifacts.values()
    }
    assert set(canonical_cad.selected_source_content_identities) == {
        artifact.sha256 for artifact in fixture.source_artifacts.values()
    }
    assert set(candidate_sources) == set(canonical_sources)
    for source_identity, candidate_source in candidate_sources.items():
        canonical_source = canonical_sources[source_identity]
        assert canonical_source is not None
        assert (
            canonical_source.artifact_id,
            canonical_source.artifact_hash,
            canonical_source.source_identity,
        ) == (
            candidate_source.artifact_id,
            candidate_source.artifact_hash,
            f"{fixture.source_label}:STEP:{candidate_source.artifact_id}",
        )

def _payload_keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(  # noqa: PLC0206
            _payload_keys(item) for item in value.values()
        ))
    if isinstance(value, list):
        return set().union(*(_payload_keys(item) for item in value))
    return set()


def _assert_spur_limitations(stage):
    candidate = stage.candidate
    physical_ids = {item.instance_id for item in candidate.realization.components}
    assert {"driver-gear", "driven-gear"} <= physical_ids
    assert "driver-gear" != "driven-gear"
    cad_ids = {
        item.physical_instance_id: item.cad_instance_id
        for item in stage.cad.realization.mappings
    }
    assert cad_ids["driver-gear"] != cad_ids["driven-gear"]
    gear_mesh = next(
        connection
        for connection in candidate.realization.connections
        if connection.kind.value == CanonicalMechanicalConnectionKind.GEAR_MESH.value
    )
    assert {
        gear_mesh.from_instance_id,
        gear_mesh.to_instance_id,
    } == {"driver-gear", "driven-gear"}
    assert gear_mesh.from_interface_id == gear_mesh.to_interface_id == "mesh"
    assert len(candidate.realization.joint_bindings) == 1
    assert not any(
        connection.kind.value == "coupling"
        and {connection.from_instance_id, connection.to_instance_id}
        & {"driver-gear", "driven-gear"}
        for connection in candidate.realization.connections
    )

    driver = stage.binding.disposition_for(cad_ids["driver-gear"])
    assert driver.disposition is CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED
    gear_pair = next(
        item
        for item in stage.m10_request.inventory.classifications
        if set(item.pair) == {cad_ids["driver-gear"], cad_ids["driven-gear"]}
    )
    assert gear_pair.classification is CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED
    assert all(
        cad_ids["driver-gear"] not in proof.pair
        for proof in stage.evaluation.m10_stage_outcome.pair_proofs
    )
    assert all(
        cad_ids["driver-gear"] not in check.pair
        for check in stage.evaluation.m10_stage_outcome.home_exact_checks
    )
    assert all("gear" not in claim.lower() for claim in stage.evaluation.hard_witnesses)
    assert all("gear" not in claim.lower() for claim in stage.evaluation.unresolved_findings)
    forbidden_keys = {"ratio", "gear_ratio", "phase", "backlash", "gear_coupling"}
    assert not forbidden_keys & _payload_keys(candidate.model_dump(mode="json"))
    evaluation_payload = json.dumps(stage.evaluation.model_dump(mode="json"), sort_keys=True).lower()
    assert not any(
        marker in evaluation_payload
        for marker in ("counter_rotation", "transmission_internal_proof", "transmission-internal")
    )


def _comparison(fixture, first, second):
    # Exact tie behavior remains covered by the M12-4 predecessor test; these
    # acceptance scenarios use distinct trusted clearance values.
    policy = fixture.app.candidate_comparison_service.policy
    assert policy.metric_keys == (CandidateMetricKey.VERIFIED_CLEARANCE_LOWER_BOUND_MM,)
    assert policy.expected_units == ("mm",)
    first_metric = _verified_clearance_lower_bound(first.evaluation)
    second_metric = _verified_clearance_lower_bound(second.evaluation)
    request = CandidateComparisonRequest(
        project_id=fixture.app.project_id,
        source_binding_hash=fixture.app._candidate_source_binding_hash(first.candidate),
        evaluation_scope_hash=first.scope.scope_hash,
        policy_hash=policy.policy_hash,
        candidate_evaluation_pairs=(
            (first.candidate.candidate_hash, first.evaluation.evaluation_hash),
            (second.candidate.candidate_hash, second.evaluation.evaluation_hash),
        ),
    )
    result = fixture.app.compare_candidates(
        request,
        ((first.candidate, first.evaluation), (second.candidate, second.evaluation)),
    )
    assert dict(result.metric_values) == {
        first.candidate.candidate_hash: first_metric,
        second.candidate.candidate_hash: second_metric,
    }
    expected_ranking = tuple(
        candidate_hash
        for candidate_hash, _ in sorted(
            (
                (first.candidate.candidate_hash, first_metric),
                (second.candidate.candidate_hash, second_metric),
            ),
            key=lambda item: item[1],
            reverse=True,
        )
    )
    assert result.ranked_candidate_hashes == expected_ranking
    assert result.ties == ()
    return request, result


def _promotion_request(fixture, stage, selection, *, comparison=None, comparison_request=None, comparison_entries=None, mechanism_id):
    return CandidatePromotionRequest(
        project_id=fixture.app.project_id,
        source_revision=fixture.source.revision,
        source_state_hash=fixture.source.state_hash,
        candidate=stage.candidate,
        synthesis_request=stage.synthesis_request,
        synthesis_policy=stage.synthesis_policy,
        m12_3_result=stage.m12_result,
        evaluation=stage.evaluation,
        selection=selection,
        comparison_used=comparison is not None,
        comparison=comparison,
        comparison_request=comparison_request,
        comparison_entries=comparison_entries,
        promotion_policy=CandidatePromotionPolicy(),
        canonical_target_mechanism_id=mechanism_id,
        classifications=_promotion_classifications(stage.candidate),
    )


def _promote_and_fresh_verify(fixture, stage, selection, *, comparison=None, comparison_request=None, comparison_entries=None, mechanism_id):
    request = _promotion_request(
        fixture,
        stage,
        selection,
        comparison=comparison,
        comparison_request=comparison_request,
        comparison_entries=comparison_entries,
        mechanism_id=mechanism_id,
    )
    promotion = fixture.app.promote_selected_candidate(request)
    assert promotion.status.value == "promotion_applied", promotion.error
    assert promotion.applied_revision == fixture.source.revision + 1
    assert promotion.applied_state_hash != fixture.source.state_hash
    assert len(fixture.app.load_state().state.physical_mechanisms) == 1

    verification = fixture.app.verify_promoted_mechanism(promotion)
    assert verification.status is PromotedMechanismVerificationStatus.VERIFIED
    reconstruction = fixture.app.reconstruct_promoted_mechanism(
        revision=promotion.applied_revision,
        state_hash=promotion.applied_state_hash,
        mechanism_id=mechanism_id,
    )
    canonical_cad = fixture.app.canonical_cad_compiler.realize(reconstruction)
    canonical_m10 = fixture.app.canonical_m10_service.execute(reconstruction, canonical_cad)
    _assert_canonical_source_geometry(fixture, stage, reconstruction, canonical_cad)
    _assert_gear_provenance(fixture, stage, canonical_cad)
    assert canonical_m10.status.value == "verified_clear"
    assert verification.canonical_cad_request_hash == canonical_cad.request_hash
    assert verification.canonical_cad_realization_hash == canonical_cad.realization_hash
    assert canonical_cad.request_hash != stage.cad_request.request_hash
    assert canonical_cad.realization_hash != stage.cad.realization_hash
    assert canonical_m10.request.request_hash != stage.m10_request.request_hash

    candidate_to_canonical = {
        item.candidate_instance_id: item.canonical_instance_id
        for item in promotion.compilation.mapping
    }
    canonical_cad_ids = {
        item.physical_instance_id: item.cad_instance_id
        for item in canonical_cad.mappings
    }
    canonical_driver = canonical_cad_ids[candidate_to_canonical["driver-gear"]]
    canonical_driven = canonical_cad_ids[candidate_to_canonical["driven-gear"]]
    canonical_driver_disposition = next(
        item
        for item in canonical_m10.inventory.constituent_dispositions
        if item.cad_instance_id == canonical_driver
    )
    assert canonical_driver_disposition.disposition.value == "internal_motion_unmodeled"
    canonical_pair = next(
        item
        for item in canonical_m10.inventory.classifications
        if set(item.pair) == {canonical_driver, canonical_driven}
    )
    assert canonical_pair.classification.value == "intended_contact_excluded"
    assert all(canonical_driver not in proof.pair for proof in canonical_m10.pair_proofs)
    canonical_gear_mesh = next(
        connection
        for connection in reconstruction.mechanism.connections
        if connection.kind.value == CanonicalMechanicalConnectionKind.GEAR_MESH.value
    )
    assert {
        canonical_gear_mesh.from_instance_id,
        canonical_gear_mesh.to_instance_id,
    } == {
        candidate_to_canonical["driver-gear"],
        candidate_to_canonical["driven-gear"],
    }
    assert not any(
        connection.kind.value == "coupling"
        and {connection.from_instance_id, connection.to_instance_id}
        & {candidate_to_canonical["driver-gear"], candidate_to_canonical["driven-gear"]}
        for connection in reconstruction.mechanism.connections
    )
    assert not {
        "ratio",
        "gear_ratio",
        "phase",
        "backlash",
        "gear_coupling",
        "counter_rotation",
        "transmission_internal_proof",
    } & _payload_keys(reconstruction.mechanism.model_dump(mode="json"))
    canonical_m10_payload = json.dumps(canonical_m10.model_dump(mode="json"), sort_keys=True).lower()
    assert not any(
        marker in canonical_m10_payload
        for marker in ("counter_rotation", "transmission_internal_proof", "transmission-internal")
    )

    result_meta = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id="project-lookup",
    ).existing_in_project(promotion.result_artifact_id)
    assert result_meta is not None
    assert result_meta.run_id not in fixture.source_run_ids
    assert result_meta.run_id != fixture.source_artifacts["driver-gear"].run_id
    return promotion, verification, canonical_cad, canonical_m10


def _fresh_reload_promotion_manifests(fixture, promotion):
    fresh_adapter = UninvokedAcceptanceAdapter()
    fresh_app = ProductionApplication.create(
        fixture.app.state_manager.workspace,
        fixture.app.project_id,
        fresh_adapter,
        ownership_path=fixture.ownership_path,
        dependency_path=fixture.dependency_path,
        additional_tool_registrations=GearworksTools.registrations(),
    )
    fresh_state = fresh_app.load_state()
    assert fresh_state.revision == promotion.applied_revision
    assert fresh_state.state_hash == promotion.applied_state_hash

    lookup = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id="project-lookup",
    )
    result_meta = lookup.existing_in_project(promotion.result_artifact_id)
    assert result_meta is not None
    assert result_meta.artifact_type is ArtifactType.JSON
    manifest_store = ArtifactStore(
        fixture.app.state_manager.workspace,
        project_id=fixture.app.project_id,
        run_id=result_meta.run_id,
    )
    result_manifest = fresh_app.promotion_manifest_service.resolve_result(
        manifest_store, result_meta.artifact_id
    )
    decision_meta, _ = manifest_store.read_verified_strict(
        result_manifest.decision_artifact_id,
        expected_type=ArtifactType.JSON,
        expected_hash=result_manifest.decision_artifact_hash,
    )
    decision = fresh_app.promotion_manifest_service.resolve_decision(
        manifest_store, result_manifest.decision_artifact_id
    )
    assert result_manifest.decision_artifact_id == decision_meta.artifact_id
    assert result_manifest.decision_artifact_hash == decision_meta.sha256
    assert result_meta.input_hash == decision_meta.sha256
    return fresh_app, fresh_adapter, result_meta, manifest_store, result_manifest, decision


def _assert_no_comparison_durable_records(fixture, result_meta, result_manifest, decision):
    assert result_manifest.resulting_revision == fixture.source.revision + 1
    assert decision.input_reference.comparison_used is False
    assert decision.input_reference.comparison_result_hash is None
    assert decision.input_reference.comparison_request_hash is None

    project_runs_root = (
        fixture.app.state_manager.workspace
        / "projects"
        / fixture.app.project_id
        / "runs"
    )
    schemas = []
    for metadata_path in sorted(project_runs_root.glob("*/artifacts/*/metadata.json")):
        run_store = ArtifactStore(
            fixture.app.state_manager.workspace,
            project_id=fixture.app.project_id,
            run_id=metadata_path.parents[2].name,
        )
        artifact = run_store.existing(metadata_path.parent.name)
        assert artifact is not None
        if artifact.artifact_type is ArtifactType.JSON:
            payload = json.loads(
                (fixture.app.state_manager.workspace / artifact.relative_path).read_text(
                    encoding="utf-8"
                )
            )
            schemas.append(payload.get("schema_version"))
    assert "candidate-comparison-request@1" not in schemas
    assert "candidate-comparison-result@1" not in schemas


def _set_live_freecad(monkeypatch):
    monkeypatch.setenv("MECHCAD_FREECADCMD", FREECADCMD)
    runtime = discover_freecad().require_available()
    assert os.path.normcase(runtime.executable) == os.path.normcase(FREECADCMD)
    backend_provenance = FreeCADBackend().provenance()
    assert backend_provenance.library_name == "FreeCAD"
    assert backend_provenance.library_version
    print(
        "M12_6_EXTERNAL_SPUR_RUNTIME="
        + json.dumps(
            {
                "executable": runtime.executable,
                "version": runtime.version,
                "freecad_backend": backend_provenance.model_dump(mode="json"),
            },
            sort_keys=True,
        )
    )


def test_live_external_spur_positive_promotion_is_verified(tmp_path, monkeypatch):
    _set_live_freecad(monkeypatch)
    fixture = _bootstrap_external_spur(tmp_path, "PRJ-M12-6-SPUR-COMPARISON")
    assert fixture.source_label == "M12-6 ACCEPTANCE FIXTURE SOURCE AUTHORITY"
    first = _candidate_and_evaluation(fixture, 80.0, "comparison-a")
    second = _candidate_and_evaluation(fixture, 60.0, "comparison-b")
    assert first.m12_result.status.value == "admissible"
    assert second.m12_result.status.value == "admissible"
    assert first.evaluation.outcome is second.evaluation.outcome is CandidateEvaluationOutcome.FEASIBLE
    assert _verified_clearance_lower_bound(second.evaluation) > _verified_clearance_lower_bound(
        first.evaluation
    )
    _assert_spur_limitations(first)
    _assert_spur_limitations(second)
    comparison_request, comparison = _comparison(fixture, first, second)
    comparison_rationale = "explicitly selected highest verified-clearance lower bound"
    selection = fixture.app.select_candidate(
        second.candidate,
        second.evaluation,
        "m12-6-spur-comparison-selector",
        comparison_rationale,
        comparison=comparison,
        comparison_entries=((first.candidate, first.evaluation), (second.candidate, second.evaluation)),
    )
    assert selection.comparison_used is True
    assert selection.comparison_result_hash == comparison.result_hash
    assert selection.rationale == comparison_rationale
    assert comparison.ranked_candidate_hashes[0] == second.candidate.candidate_hash
    _promote_and_fresh_verify(
        fixture,
        second,
        selection,
        comparison=comparison,
        comparison_request=comparison_request,
        comparison_entries=((first.candidate, first.evaluation), (second.candidate, second.evaluation)),
        mechanism_id="PM-m12-6-spur-comparison",
    )
    assert fixture.acceptance_adapter.call_count == 0


def test_live_external_spur_selection_without_comparison_has_no_comparison_record(tmp_path, monkeypatch):
    _set_live_freecad(monkeypatch)
    fixture = _bootstrap_external_spur(tmp_path, "PRJ-M12-6-SPUR-NO-COMPARISON")
    stage = _candidate_and_evaluation(fixture, 80.0, "no-comparison")
    comparison_calls = []

    def forbidden_comparison(*args, **kwargs):
        comparison_calls.append((args, kwargs))
        raise AssertionError("no-comparison selection must not invoke comparison")

    monkeypatch.setattr(fixture.app.candidate_comparison_service, "compare", forbidden_comparison)
    no_comparison_rationale = "explicitly selected feasible candidate without comparison"
    selection = fixture.app.select_candidate(
        stage.candidate,
        stage.evaluation,
        "m12-6-spur-no-comparison-selector",
        no_comparison_rationale,
    )
    assert selection.comparison_used is False
    assert selection.comparison_result_hash is None
    assert selection.rationale == no_comparison_rationale
    assert comparison_calls == []
    promotion, _, _, _ = _promote_and_fresh_verify(
        fixture,
        stage,
        selection,
        mechanism_id="PM-m12-6-spur-no-comparison",
    )
    assert promotion.request.comparison_used is False
    assert promotion.request.comparison is None
    assert promotion.request.comparison_request is None
    assert promotion.request.comparison_entries is None
    (
        fresh_app,
        fresh_adapter,
        result_meta,
        _manifest_store,
        result_manifest,
        decision,
    ) = _fresh_reload_promotion_manifests(fixture, promotion)
    _assert_no_comparison_durable_records(fixture, result_meta, result_manifest, decision)
    assert fresh_adapter.call_count == 0
    assert fresh_app.load_state().state.physical_mechanisms[0].id == "PM-m12-6-spur-no-comparison"
    assert fixture.acceptance_adapter.call_count == 0


def test_live_external_spur_explicitly_promotes_lower_ranked_feasible_candidate(tmp_path, monkeypatch):
    _set_live_freecad(monkeypatch)
    fixture = _bootstrap_external_spur(tmp_path, "PRJ-M12-6-SPUR-NON-TOP")
    lower = _candidate_and_evaluation(fixture, 80.0, "non-top-a")
    higher = _candidate_and_evaluation(fixture, 60.0, "non-top-b")
    comparison_request, comparison = _comparison(fixture, lower, higher)
    assert comparison.ranked_candidate_hashes[0] == higher.candidate.candidate_hash
    assert _verified_clearance_lower_bound(higher.evaluation) > _verified_clearance_lower_bound(
        lower.evaluation
    )
    non_top_rationale = "explicitly selected lower-ranked feasible candidate"
    selection = fixture.app.select_candidate(
        lower.candidate,
        lower.evaluation,
        "m12-6-spur-non-top-selector",
        non_top_rationale,
        comparison=comparison,
        comparison_entries=((lower.candidate, lower.evaluation), (higher.candidate, higher.evaluation)),
    )
    assert selection.comparison_used is True
    assert selection.candidate_hash == lower.candidate.candidate_hash
    assert selection.candidate_hash != comparison.ranked_candidate_hashes[0]
    assert selection.rationale == non_top_rationale
    _promote_and_fresh_verify(
        fixture,
        lower,
        selection,
        comparison=comparison,
        comparison_request=comparison_request,
        comparison_entries=((lower.candidate, lower.evaluation), (higher.candidate, higher.evaluation)),
        mechanism_id="PM-m12-6-spur-non-top",
    )
    assert fixture.acceptance_adapter.call_count == 0
