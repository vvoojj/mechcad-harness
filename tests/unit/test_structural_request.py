import pytest
from pydantic import ValidationError

from mechcad_harness.models.structural import (
    StructuralResultField,
    structural_definition_hash,
)
from mechcad_harness.structural_request import (
    MeshRefinement,
    MeshSpecification,
    StructuralAnalysisRequest,
    StructuralExecutionSettings,
    StructuralSourceBinding,
    structural_request_hash,
)
from tests.unit.test_structural_models import make_case, make_definition, make_force


def make_source_binding(definition):
    return StructuralSourceBinding(
        project_id="project-1",
        source_revision=3,
        source_state_hash="sha256:state",
        definition_id=definition.id,
        definition_hash=structural_definition_hash(definition),
        target_body_id=definition.target_body_id,
        source_program_hash="sha256:program",
        geometry_identity="geometry:body-1",
        geometry_artifact_id="artifact-1",
        geometry_artifact_hash="sha256:artifact",
    )


def make_request(
    definition,
    *,
    global_target_size_mm=5.0,
    refinements=(),
    requested_result_fields=("displacement", "von_mises_stress"),
    max_runtime_seconds=60.0,
    selected_load_case_ids=("case-1",),
):
    return StructuralAnalysisRequest(
        source_binding=make_source_binding(definition),
        selected_load_case_ids=selected_load_case_ids,
        mesh_specification=MeshSpecification(
            global_target_size_mm=global_target_size_mm,
            refinements=refinements,
            quality_policy_id="quality:standard",
            mesher_settings_version="mesher@1.0",
        ),
        requested_result_fields=requested_result_fields,
        execution_settings=StructuralExecutionSettings(
            max_elements=100_000,
            max_runtime_seconds=max_runtime_seconds,
            max_output_bytes=10_000_000,
            retain_raw_artifacts=True,
        ),
    )


def test_request_binds_definition_and_hashes_computational_inputs():
    definition = make_definition()
    base = make_request(definition, global_target_size_mm=5.0)
    refined = make_request(definition, global_target_size_mm=2.5)
    changed_outputs = make_request(
        definition, requested_result_fields=("displacement",)
    )
    changed_limits = make_request(definition, max_runtime_seconds=90.0)

    assert base.source_binding.definition_hash == structural_definition_hash(definition)
    assert base.request_hash != refined.request_hash
    assert base.request_hash != changed_outputs.request_hash
    assert base.request_hash != changed_limits.request_hash
    assert base.source_binding.definition_hash == refined.source_binding.definition_hash
    assert structural_request_hash(base) == base.request_hash


def test_request_hash_binds_predeclared_analytical_policy_hash():
    definition = make_definition()
    first = StructuralAnalysisRequest.model_validate({
        **make_request(definition).model_dump(mode="json"),
        "analytical_policy_hash": "sha256:" + "a" * 64,
        "request_hash": "pending",
    })
    second = StructuralAnalysisRequest.model_validate({
        **first.model_dump(mode="json"),
        "analytical_policy_hash": "sha256:" + "b" * 64,
        "request_hash": "pending",
    })

    assert first.request_hash != second.request_hash


def test_refinement_order_is_canonical_and_hash_is_order_insensitive():
    definition = make_definition()
    first = make_request(
        definition,
        refinements=(
            MeshRefinement(region_id="free-end", target_size_mm=2.0),
            MeshRefinement(region_id="fixed-end", target_size_mm=1.0),
        ),
    )
    second = make_request(
        definition,
        refinements=(
            MeshRefinement(region_id="fixed-end", target_size_mm=1.0),
            MeshRefinement(region_id="free-end", target_size_mm=2.0),
        ),
    )

    assert tuple(item.region_id for item in first.mesh_specification.refinements) == (
        "fixed-end",
        "free-end",
    )
    assert first.request_hash == second.request_hash


@pytest.mark.parametrize(
    "field_values",
    [
        {"source_revision": 0},
        {"source_state_hash": ""},
        {"definition_hash": ""},
        {"geometry_artifact_hash": ""},
    ],
)
def test_source_binding_rejects_invalid_revision_and_hash_fields(field_values):
    definition = make_definition()
    with pytest.raises(ValidationError):
        StructuralSourceBinding(**{**make_source_binding(definition).model_dump(), **field_values})


def test_request_rejects_empty_or_duplicate_selected_cases():
    definition = make_definition()
    with pytest.raises(ValidationError):
        make_request(definition, selected_load_case_ids=())
    with pytest.raises(ValueError, match="non-empty"):
        make_request(definition, selected_load_case_ids=("",))
    with pytest.raises(ValueError, match="unique"):
        make_request(definition, selected_load_case_ids=("case-1", "case-1"))


def test_validate_against_rejects_inactive_or_unknown_cases():
    definition = make_definition(
        load_cases=(
            make_case("case-1"),
            make_case("case-2", loads=(make_force("force-2"),), active=False),
        )
    )
    inactive = make_request(definition, selected_load_case_ids=("case-2",))
    unknown = make_request(definition, selected_load_case_ids=("missing",))

    with pytest.raises(ValueError, match="unknown or inactive"):
        inactive.validate_against(definition)
    with pytest.raises(ValueError, match="unknown or inactive"):
        unknown.validate_against(definition)


def test_validate_against_rejects_refinement_for_unknown_definition_region():
    definition = make_definition()
    request = make_request(
        definition,
        refinements=(MeshRefinement(region_id="missing-region", target_size_mm=1.0),),
    )

    with pytest.raises(ValueError, match="region"):
        request.validate_against(definition)


@pytest.mark.parametrize(
    "binding_update",
    [
        {"definition_id": "other-definition"},
        {"definition_hash": "sha256:other"},
        {"target_body_id": "other-body"},
    ],
)
def test_validate_against_rejects_definition_binding_mismatches(binding_update):
    definition = make_definition()
    request = make_request(definition)
    request = request.model_copy(
        update={"source_binding": request.source_binding.model_copy(update=binding_update)}
    )

    with pytest.raises(ValueError):
        request.validate_against(definition)


@pytest.mark.parametrize(
    "field_values",
    [
        {"global_target_size_mm": 0.0},
        {"global_target_size_mm": -1.0},
        {"quality_policy_id": ""},
        {"mesher_settings_version": ""},
    ],
)
def test_mesh_specification_rejects_invalid_mesh_settings(field_values):
    with pytest.raises(ValidationError):
        MeshSpecification(**field_values)


@pytest.mark.parametrize(
    "refinements",
    [
        ({"region_id": "", "target_size_mm": 1.0},),
        ({"region_id": "region-1", "target_size_mm": 0.0},),
        (
            {"region_id": "region-1", "target_size_mm": 1.0},
            {"region_id": "region-1", "target_size_mm": 2.0},
        ),
    ],
)
def test_mesh_specification_rejects_invalid_refinements(refinements):
    with pytest.raises((ValidationError, ValueError)):
        MeshSpecification(refinements=refinements)


@pytest.mark.parametrize(
    "field_values",
    [
        {"max_elements": 0},
        {"max_runtime_seconds": 0.0},
        {"max_runtime_seconds": float("inf")},
        {"max_output_bytes": 0},
    ],
)
def test_execution_settings_reject_nonpositive_or_nonfinite_limits(field_values):
    with pytest.raises(ValidationError):
        StructuralExecutionSettings(**field_values)


def test_request_rejects_unsupported_result_fields_and_nonmatching_hash():
    definition = make_definition()
    with pytest.raises(ValidationError):
        make_request(definition, requested_result_fields=("reaction_forces",))

    request_values = make_request(definition).model_dump()
    request_values["request_hash"] = "sha256:not-the-request"
    with pytest.raises(ValueError, match="request hash"):
        StructuralAnalysisRequest(**request_values)


def test_requested_result_fields_are_typed_shared_semantics():
    request = make_request(
        make_definition(),
        requested_result_fields=(StructuralResultField.DISPLACEMENT,),
    )

    assert request.requested_result_fields == (StructuralResultField.DISPLACEMENT,)


def test_structural_request_records_are_immutable_and_hash_stays_bound():
    request = make_request(
        make_definition(),
        refinements=(MeshRefinement(region_id="free-end", target_size_mm=2.0),),
    )
    original_hash = request.request_hash

    with pytest.raises(ValidationError):
        request.request_hash = "sha256:changed"
    with pytest.raises(ValidationError):
        request.selected_load_case_ids = ("case-2",)
    with pytest.raises(ValidationError):
        request.source_binding.project_id = "project-2"
    with pytest.raises(ValidationError):
        request.mesh_specification.global_target_size_mm = 2.0
    with pytest.raises(ValidationError):
        request.mesh_specification.refinements[0].target_size_mm = 1.0
    with pytest.raises(ValidationError):
        request.execution_settings.max_runtime_seconds = 120.0

    assert request.request_hash == original_hash
    assert structural_request_hash(request) == request.request_hash
