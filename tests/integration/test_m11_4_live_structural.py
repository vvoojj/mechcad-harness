from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pytest

from mechcad_harness.artifacts.storage import ArtifactStore, ArtifactType
from mechcad_harness.cad_program import cad_program_hash
from mechcad_harness.models.structural import (
    AcceptanceMaterialAuthorityPolicy,
    MaximumDisplacementCriterion,
    StructuralCoordinateFrame,
    StructuralMaterialPropertyName,
    StructuralPropertyAuthorityRule,
    StructuralResultantForce,
    StructuralLoadCase,
    YieldSafetyFactorCriterion,
    structural_definition_hash,
)
from mechcad_harness.structural.models import (
    CALCULIX_PROVIDER_IDENTITY,
    DAT_RESULT_PARSER_IDENTITY,
    FRD_RESULT_PARSER_IDENTITY,
    INTERPRETER_IDENTITY,
    StructuralCriterionStatus,
    StructuralExecutionStatus,
    StructuralResultMaturity,
)
from mechcad_harness.structural.results import (
    StructuralAnalysisEvaluation,
    StructuralResultInterpreter,
    _parse_verified_mesh,
    von_mises_mpa,
)
from mechcad_harness.structural.validation import (
    CantileverGeometryObservation,
    CantileverMaterialObservation,
    RectangularCantileverValidationPolicy,
    cantilever_geometry_observation,
    cantilever_material_observation,
    cantilever_validation_policy_hash,
)
from mechcad_harness.structural_request import (
    MeshSpecification,
    StructuralAnalysisRequest,
    StructuralExecutionSettings,
    StructuralResultField,
    StructuralSourceBinding,
)
from mechcad_harness.materials import MaterialDataAuthority

from test_m11_3_live_structural import _make_definition, _publish_step, live_app


os.environ.setdefault("MECHCAD_GMSH", r"C:\Program Files\FreeCAD 1.1\bin\gmsh.exe")

CANTILEVER_LENGTH_MM = 200.0
CANTILEVER_WIDTH_MM = 20.0
CANTILEVER_HEIGHT_MM = 10.0
CANTILEVER_FORCE_N = 100.0
CANTILEVER_MESH_SIZE_MM = 5.0
CANTILEVER_PASS_LIMIT_MM = 5.0
CANTILEVER_FAIL_LIMIT_MM = 1.0
CANTILEVER_DISPLACEMENT_TOLERANCE = 0.20
CANTILEVER_REACTION_TOLERANCE = 0.05
# These absolute residual ceilings cover CalculiX text-output rounding while
# remaining far below the 100 N / 20,000 N*mm physical resultants.
REACTION_FORCE_RESIDUAL_ABS_N = 1e-3
REACTION_MOMENT_RESIDUAL_ABS_N_MM = 0.1
CANTILEVER_ELASTIC_MODULUS_MPA = 70000.0
CANTILEVER_POISSON_RATIO = 0.33
CANTILEVER_MESH_SPECIFICATION = MeshSpecification(
    global_target_size_mm=CANTILEVER_MESH_SIZE_MM,
    quality_policy_id="m11-4-fixed-cantilever-quality@1",
    mesher_settings_version="m11-4-fixed-cantilever-mesher@1",
)


def _mesh_specification_hash(mesh_specification: MeshSpecification) -> str:
    payload = json.dumps(
        mesh_specification.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def test_m11_4_live_reaction_dat_discovery(live_app, tmp_path: Path):
    definition = _make_definition()
    revision, state_hash, step_artifact, program = _publish_step(live_app, definition, tmp_path)
    binding = StructuralSourceBinding(
        project_id="PRJ-M11-3-live", source_revision=revision, source_state_hash=state_hash,
        definition_id=definition.id, definition_hash=structural_definition_hash(definition),
        target_body_id=definition.target_body_id, source_program_hash=cad_program_hash(program),
        geometry_identity=program.part_id, geometry_artifact_id=step_artifact.artifact_id,
        geometry_artifact_hash=step_artifact.sha256,
    )
    request = StructuralAnalysisRequest(
        source_binding=binding, selected_load_case_ids=("LC-1",),
        mesh_specification=MeshSpecification(
            global_target_size_mm=5.0, quality_policy_id="q1", mesher_settings_version="1"
        ),
        requested_result_fields=(StructuralResultField.REACTIONS,),
        execution_settings=StructuralExecutionSettings(
            max_elements=1_000_000, max_runtime_seconds=300, max_output_bytes=50_000_000,
            retain_raw_artifacts=True,
        ),
    )

    result = live_app.execute_structural_analysis(request=request)

    assert result.execution_status is StructuralExecutionStatus.SUCCEEDED, result.error_detail
    assert result.manifest is not None
    provider = live_app.structural_service.calculix_provider
    assert provider.identity == CALCULIX_PROVIDER_IDENTITY
    assert provider._discovery.identity.library_name == "CalculiX"
    assert provider._discovery.identity.library_version == "2.22"
    assert provider._discovery.version == "2.22"
    assert result.manifest.calculix_identity == provider.identity
    assert result.manifest.calculix_version == provider._discovery.identity.library_version
    expected_solver_provenance = provider._discovery.provenance
    assert result.manifest.case_manifests[0].solver_manifest.backend_provenance == expected_solver_provenance
    store = ArtifactStore(tmp_path, project_id="PRJ-M11-3-live", run_id=result.run_id)
    dat_artifact = store.existing(result.manifest.dat_artifact_id)
    assert dat_artifact is not None
    assert dat_artifact.artifact_type is ArtifactType.DAT
    assert dat_artifact.backend_provenance == expected_solver_provenance
    frd_artifact = store.existing(result.manifest.frd_artifact_id)
    log_artifact = store.existing(result.manifest.log_artifact_id)
    assert frd_artifact is not None and frd_artifact.backend_provenance == expected_solver_provenance
    assert log_artifact is not None and log_artifact.backend_provenance == expected_solver_provenance
    deck_artifact = store.existing(result.manifest.deck_artifact_id)
    assert deck_artifact is not None
    deck_text = (tmp_path / deck_artifact.relative_path).read_text(encoding="ascii")
    assert "*NODE PRINT,NSET=fixed_nodes\nRF\n" in deck_text
    assert "*EL FILE\nS\n" not in deck_text
    assert "*NODE FILE\nU\n" not in deck_text
    assert "*NODE PRINT,NSET=fixed_nodes\nU\n" not in deck_text
    dat_text = (tmp_path / dat_artifact.relative_path).read_text(encoding="utf-8", errors="replace")
    assert " forces (fx,fy,fz) for set FIXED_NODES and time  0.1000000E+01" in dat_text
    record_lines = [
        line for line in dat_text.splitlines()
        if len(line.split()) == 4 and line.split()[0].isdigit()
    ]
    scientific = re.compile(r"^[+-]?\d+\.\d+E[+-]\d+$")
    assert record_lines
    assert all(len(line.split()) == 4 for line in record_lines)
    assert all(
        line.split()[0].isdigit() and int(line.split()[0]) > 0
        for line in record_lines
    )
    assert all(scientific.fullmatch(token) for line in record_lines for token in line.split()[1:])
    assert all("UR" not in line and len(line.split()) != 5 for line in record_lines)


def test_m11_4_live_interprets_two_ordered_cases_and_empty_criteria_status(live_app, tmp_path: Path):
    base_definition = _make_definition()
    second_case = base_definition.load_cases[0].model_copy(update={
        "id": "LC-2",
        "name": "load case 2",
        "loads": tuple(load.model_copy(update={"load_id": "LF-2"}) for load in base_definition.load_cases[0].loads),
    })
    definition = base_definition.model_copy(update={
        "load_cases": (base_definition.load_cases[0], second_case),
        "boundary_conditions": tuple(
            support.model_copy(update={"applies_to_load_case_ids": ("LC-1", "LC-2")})
            for support in base_definition.boundary_conditions
        ),
    })
    revision, state_hash, step_artifact, program = _publish_step(live_app, definition, tmp_path)
    binding = StructuralSourceBinding(
        project_id="PRJ-M11-3-live", source_revision=revision, source_state_hash=state_hash,
        definition_id=definition.id, definition_hash=structural_definition_hash(definition),
        target_body_id=definition.target_body_id, source_program_hash=cad_program_hash(program),
        geometry_identity=program.part_id, geometry_artifact_id=step_artifact.artifact_id,
        geometry_artifact_hash=step_artifact.sha256,
    )
    request = StructuralAnalysisRequest(
        source_binding=binding, selected_load_case_ids=("LC-1", "LC-2"),
        mesh_specification=CANTILEVER_MESH_SPECIFICATION,
        requested_result_fields=(StructuralResultField.DISPLACEMENT,),
        execution_settings=StructuralExecutionSettings(
            max_elements=1_000_000, max_runtime_seconds=300, max_output_bytes=50_000_000,
            retain_raw_artifacts=True,
        ),
    )

    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    assert execution.manifest is not None
    assert execution.manifest.solver_manifest is None
    assert execution.manifest.case_manifests[0].mesh_artifact_id == execution.manifest.mesh_artifact_id
    assert execution.manifest.case_manifests[1].mesh_artifact_id == execution.manifest.mesh_artifact_id
    evaluated = live_app.evaluate_structural_analysis(execution_manifest=execution.manifest)

    assert tuple(case.load_case_id for case in evaluated.result.load_case_results) == ("LC-1", "LC-2")
    assert all(case.displacements for case in evaluated.result.load_case_results)
    assert evaluated.verification.overall_status is StructuralCriterionStatus.NOT_EVALUABLE


def _cantilever_definition(criterion):
    definition = _make_definition()
    load = StructuralResultantForce(
        load_id="LF-1",
        target_region_id="free",
        magnitude_n=CANTILEVER_FORCE_N,
        direction_xyz=(0.0, 0.0, -1.0),
        frame=StructuralCoordinateFrame.COMPONENT_LOCAL,
        distribution="uniform_surface_traction_equivalent",
    )
    authority_policy = AcceptanceMaterialAuthorityPolicy(
        allowed_authorities_by_property=(
            StructuralPropertyAuthorityRule(
                property_name=StructuralMaterialPropertyName.ELASTIC_MODULUS,
                allowed_authorities=(MaterialDataAuthority.TYPICAL_REFERENCE,),
            ),
            StructuralPropertyAuthorityRule(
                property_name=StructuralMaterialPropertyName.POISSON_RATIO,
                allowed_authorities=(MaterialDataAuthority.TYPICAL_REFERENCE,),
            ),
            StructuralPropertyAuthorityRule(
                property_name=StructuralMaterialPropertyName.YIELD_STRENGTH,
                allowed_authorities=(MaterialDataAuthority.TYPICAL_REFERENCE,),
            ),
        ),
    )
    return definition.model_copy(update={
        "load_cases": (StructuralLoadCase(id="LC-1", name="transverse load", loads=(load,)),),
        "acceptance_criteria": (criterion,),
        "material_authority_policy": authority_policy,
    })


def _cantilever_binding(definition, revision, state_hash, step_artifact, program):
    return StructuralSourceBinding(
        project_id="PRJ-M11-3-live",
        source_revision=revision,
        source_state_hash=state_hash,
        definition_id=definition.id,
        definition_hash=structural_definition_hash(definition),
        target_body_id=definition.target_body_id,
        source_program_hash=cad_program_hash(program),
        geometry_identity=program.part_id,
        geometry_artifact_id=step_artifact.artifact_id,
        geometry_artifact_hash=step_artifact.sha256,
    )


def _cantilever_request(binding, *, analytical_policy_hash=None, displacement_limit=CANTILEVER_PASS_LIMIT_MM):
    # The request is intentionally created without an analytical policy first;
    # the pre-execution declaration is bound after source artifact identity is
    # available and before the production solver is called.
    criterion = MaximumDisplacementCriterion(
        criterion_id="DISP-1",
        load_case_id="LC-1",
        assessment_region_id="free",
        maximum_allowed_displacement_mm=displacement_limit,
    )
    return StructuralAnalysisRequest(
        source_binding=binding,
        selected_load_case_ids=("LC-1",),
        mesh_specification=CANTILEVER_MESH_SPECIFICATION,
        requested_result_fields=(
            StructuralResultField.DISPLACEMENT,
            StructuralResultField.VON_MISES_STRESS,
            StructuralResultField.REACTIONS,
        ),
        execution_settings=StructuralExecutionSettings(
            max_elements=1_000_000,
            max_runtime_seconds=300,
            max_output_bytes=50_000_000,
            retain_raw_artifacts=True,
        ),
        analytical_policy_hash=analytical_policy_hash,
    )


def _prepare_cantilever(live_app, definition, tmp_path: Path):
    # Pre-execution declaration phase: freeze analytical expectations before
    # the helper observes FreeCAD geometry or runs Gmsh/CalculiX.
    snapshots = {
        snapshot.property_name: snapshot
        for snapshot in definition.material_assignment.property_snapshot
    }
    policy = RectangularCantileverValidationPolicy(
        request_hash=None,
        geometry_artifact_hash=None,
        material_identity="Alu7075",
        length_mm=CANTILEVER_LENGTH_MM,
        width_mm=CANTILEVER_WIDTH_MM,
        height_mm=CANTILEVER_HEIGHT_MM,
        elastic_modulus_mpa=snapshots[StructuralMaterialPropertyName.ELASTIC_MODULUS].value,
        poisson_ratio=snapshots[StructuralMaterialPropertyName.POISSON_RATIO].value,
        resultant_force_n=(0.0, 0.0, -CANTILEVER_FORCE_N),
        mesh_specification_hash=_mesh_specification_hash(CANTILEVER_MESH_SPECIFICATION),
        mesh_hash=None,
        region_map_hash=None,
        free_end_region_id="free",
        fixed_end_region_id="fixed",
        free_end_area_mm2=CANTILEVER_WIDTH_MM * CANTILEVER_HEIGHT_MM,
        displacement_relative_tolerance=CANTILEVER_DISPLACEMENT_TOLERANCE,
        reaction_relative_tolerance=CANTILEVER_REACTION_TOLERANCE,
        reference_point_mm=(0.0, CANTILEVER_WIDTH_MM / 2.0, CANTILEVER_HEIGHT_MM / 2.0),
        transverse_axis=2,
    )
    revision, state_hash, step_artifact, program = _publish_step(
        live_app,
        definition,
        tmp_path,
        length_mm=CANTILEVER_LENGTH_MM,
    )
    binding = _cantilever_binding(definition, revision, state_hash, step_artifact, program)
    base_request = _cantilever_request(binding)
    request_values = base_request.model_dump(mode="json")
    request_values["analytical_policy_hash"] = cantilever_validation_policy_hash(policy)
    request_values["request_hash"] = "pending"
    request = StructuralAnalysisRequest.model_validate(request_values)
    policy = policy.model_copy(update={"request_hash": request.request_hash})
    structural = live_app.structural_service
    step_path = tmp_path / step_artifact.relative_path
    assert StructuralResultInterpreter._mesh_specification_hash(request) == policy.mesh_specification_hash
    assert request.analytical_policy_hash == cantilever_validation_policy_hash(policy)
    realization = structural.geometry_adapter.realize_geometry(step_path)
    region_map = structural.region_resolver.resolve(
        definition.regions, realization, source_geometry_hash=step_artifact.sha256,
    )
    _inp_mesh, _mesh_manifest, msh_bytes = structural.gmsh_provider.mesh(
        step_path,
        region_map,
        mesh_spec_hash=StructuralResultInterpreter._mesh_specification_hash(request),
        target_size_mm=request.mesh_specification.global_target_size_mm,
        element_family=request.mesh_specification.element_family,
    )
    return (
        request,
        policy,
        _parse_verified_mesh(msh_bytes),
        cantilever_geometry_observation(request, definition, realization, region_map),
        cantilever_material_observation(request, definition),
    )


def test_live_cantilever_pass_and_analytical_validation(live_app, tmp_path: Path):
    criterion = MaximumDisplacementCriterion(
        criterion_id="DISP-1", load_case_id="LC-1", assessment_region_id="free",
        maximum_allowed_displacement_mm=CANTILEVER_PASS_LIMIT_MM,
    )
    definition = _cantilever_definition(criterion)
    request, policy, parsed_mesh, geometry_observation, material_observation = _prepare_cantilever(
        live_app, definition, tmp_path
    )

    source_before = live_app.load_state()
    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    assert execution.manifest is not None
    source_after = live_app.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    evaluated = live_app.evaluate_structural_analysis(execution_manifest=execution.manifest)
    evaluated_source = live_app.load_state()
    assert (evaluated_source.revision, evaluated_source.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    validation = live_app.evaluate_structural_analytical_validation(
        execution_manifest=execution.manifest,
        evaluation=evaluated,
        policy=policy,
        mesh=parsed_mesh,
        geometry_observation=geometry_observation,
        material_observation=material_observation,
        request=request,
        definition=definition,
    )

    assert evaluated.verification.overall_status is StructuralCriterionStatus.PASS
    assert validation.status == "pass", (
        policy.mesh_hash, evaluated.result.mesh_hash, execution.manifest.mesh_artifact_hash,
        [(check.check_id, check.status, check.reason) for check in validation.checks],
    )
    case = evaluated.result.load_case_results[0]
    assert case.maximum_displacement_mm is not None
    assert case.stress_samples
    assert case.reactions
    assert evaluated.result.parser_provenance.frd_parser_identity == FRD_RESULT_PARSER_IDENTITY
    assert evaluated.result.parser_provenance.dat_parser_identity == DAT_RESULT_PARSER_IDENTITY
    assert evaluated.result.parser_provenance.interpreter_identity == INTERPRETER_IDENTITY
    assert evaluated.result.maturity is StructuralResultMaturity.FEA_EXECUTED
    assert execution.manifest.gmsh_version == "4.15.0"
    assert execution.manifest.calculix_identity == CALCULIX_PROVIDER_IDENTITY
    assert execution.manifest.calculix_version == "2.22"
    maximum_stress = max(case.stress_samples, key=lambda sample: von_mises_mpa(sample.tensor_mpa))
    assert case.maximum_von_mises_stress_mpa == pytest.approx(von_mises_mpa(maximum_stress.tensor_mpa))
    assert maximum_stress.identity.mesh_hash == case.mesh_hash
    assert case.force_equilibrium_residual_n == pytest.approx(0.0, abs=REACTION_FORCE_RESIDUAL_ABS_N)
    assert case.moment_equilibrium_residual_n_mm == pytest.approx(0.0, abs=REACTION_MOMENT_RESIDUAL_ABS_N_MM)
    assert request.analytical_policy_hash == cantilever_validation_policy_hash(policy)
    assert policy.request_hash == request.request_hash
    assert execution.manifest.analytical_policy_hash == request.analytical_policy_hash
    assert validation.policy_hash == request.analytical_policy_hash


def test_live_analytical_validation_ignores_forged_caller_observations(live_app, tmp_path: Path):
    definition = _cantilever_definition(MaximumDisplacementCriterion(
        criterion_id="DISP-FORGED-INPUTS", load_case_id="LC-1", assessment_region_id="free",
        maximum_allowed_displacement_mm=CANTILEVER_PASS_LIMIT_MM,
    ))
    request, policy, parsed_mesh, geometry_observation, material_observation = _prepare_cantilever(
        live_app, definition, tmp_path
    )
    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    evaluated = live_app.evaluate_structural_analysis(execution_manifest=execution.manifest)

    parsed_mesh.nodes[1] = (999.0, 999.0, 999.0)
    forged_geometry = geometry_observation.model_copy(update={"length_mm": 999.0})
    forged_material = material_observation.model_copy(update={"elastic_modulus_mpa": 999.0})

    validation = live_app.evaluate_structural_analytical_validation(
        execution_manifest=execution.manifest,
        evaluation=evaluated,
        policy=policy,
        mesh=parsed_mesh,
        geometry_observation=forged_geometry,
        material_observation=forged_material,
        request=request,
        definition=definition,
    )

    assert validation.status == "pass"


def test_live_analytical_validation_rejects_forged_evaluation_result(live_app, tmp_path: Path):
    definition = _cantilever_definition(MaximumDisplacementCriterion(
        criterion_id="DISP-FORGED-RESULT", load_case_id="LC-1", assessment_region_id="free",
        maximum_allowed_displacement_mm=CANTILEVER_PASS_LIMIT_MM,
    ))
    request, policy, parsed_mesh, geometry_observation, material_observation = _prepare_cantilever(
        live_app, definition, tmp_path
    )
    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    evaluated = live_app.evaluate_structural_analysis(execution_manifest=execution.manifest)
    forged_result = evaluated.result.model_copy(update={
        "load_case_results": tuple(
            case.model_copy(update={"maximum_displacement_mm": 999.0})
            for case in evaluated.result.load_case_results
        ),
    })
    forged_evaluation = StructuralAnalysisEvaluation(
        result=forged_result,
        verification=evaluated.verification,
    )

    with pytest.raises(ValueError, match="supplied evaluation result hash"):
        live_app.evaluate_structural_analytical_validation(
            execution_manifest=execution.manifest,
            evaluation=forged_evaluation,
            policy=policy,
            mesh=parsed_mesh,
            geometry_observation=geometry_observation,
            material_observation=material_observation,
            request=request,
            definition=definition,
        )


def test_live_valid_solution_reports_engineering_fail(live_app, tmp_path: Path):
    definition = _cantilever_definition(MaximumDisplacementCriterion(
        criterion_id="DISP-FAIL", load_case_id="LC-1", assessment_region_id="free",
        maximum_allowed_displacement_mm=CANTILEVER_FAIL_LIMIT_MM,
    ))
    request, _policy, _parsed_mesh, _geometry_observation, _material_observation = _prepare_cantilever(
        live_app, definition, tmp_path
    )

    source_before = live_app.load_state()
    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    evaluated = live_app.evaluate_structural_analysis(execution_manifest=execution.manifest)
    source_after = live_app.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    criterion = evaluated.verification.criterion_results[0]
    assert criterion.status is StructuralCriterionStatus.FAIL
    assert criterion.reason == "maximum_displacement_exceeded"
    assert criterion.observed_value > CANTILEVER_FAIL_LIMIT_MM


def test_live_valid_solution_reports_missing_yield_not_evaluable(live_app, tmp_path: Path):
    definition = _cantilever_definition(YieldSafetyFactorCriterion(
        criterion_id="YIELD-MISSING", load_case_id="LC-1", assessment_region_id="free",
        stress_sampling="element_nodal_extrapolated", minimum_yield_safety_factor=1.5,
        zero_stress_tolerance_mpa=1e-9,
    ))
    request, _policy, _parsed_mesh, _geometry_observation, _material_observation = _prepare_cantilever(
        live_app, definition, tmp_path
    )

    source_before = live_app.load_state()
    execution = live_app.execute_structural_analysis(request=request)
    assert execution.execution_status is StructuralExecutionStatus.SUCCEEDED, execution.error_detail
    evaluated = live_app.evaluate_structural_analysis(execution_manifest=execution.manifest)
    source_after = live_app.load_state()
    assert (source_after.revision, source_after.state_hash) == (
        source_before.revision,
        source_before.state_hash,
    )
    assert evaluated.result.load_case_results[0].stress_samples
    criterion = evaluated.verification.criterion_results[0]
    assert criterion.status is StructuralCriterionStatus.NOT_EVALUABLE
    assert criterion.reason == "missing_material_property"
