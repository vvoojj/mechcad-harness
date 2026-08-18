from pathlib import Path

from mechcad_harness.section_engineering import (
    IntegrationSourceRecord,
    PreliminarySectionEngineeringCalculatorInput,
    PreliminarySectionEngineeringResult,
    PreliminarySectionEngineeringToolInput,
    calculate_preliminary_section_engineering,
)
from mechcad_harness.materials import TypicalMaterialPropertiesResult
from mechcad_harness.sections import SectionGeometryResult, SectionWarpingResult

from .broker import payload_hash
from .errors import ToolExecutionError
from .models import ToolRegistration, ToolResult, ToolResultStatus


MATERIAL_TOOL = ("mechcad-material-typical-properties", "1.0")
GEOMETRY_TOOLS = (
    ("mechcad-calc-rectangle-section-properties", "1.0"),
    ("mechcad-calc-circle-section-properties", "1.0"),
    ("mechcad-calc-hollow-circle-section-properties", "1.0"),
)
WARPING_TOOLS = (
    ("mechcad-calc-rectangle-section-warping", "1.0"),
    ("mechcad-calc-circle-section-warping", "1.0"),
    ("mechcad-calc-hollow-circle-section-warping", "1.0"),
)


def _result_path(controller, project_id: str, run_id: str, result_id: str) -> Path:
    return controller.workspace / "projects" / project_id / "runs" / run_id / "tool_results" / f"{result_id}.json"


def resolve_source_result(controller, project_id, run_id, result_id, expected_tools, revision, state_hash, output_model):
    path = _result_path(controller, project_id, run_id, result_id)
    if not path.exists():
        raise ToolExecutionError(f"source result not found: {result_id}")
    try:
        result = ToolResult.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ToolExecutionError(f"invalid source result: {result_id}") from exc
    if result.status is not ToolResultStatus.SUCCEEDED:
        raise ToolExecutionError(f"source result is not succeeded: {result_id}")
    if (result.tool_name, result.tool_version) not in expected_tools:
        raise ToolExecutionError(f"unexpected source producer: {result.tool_name}@{result.tool_version}")
    if result.project_id != project_id or result.run_id != run_id:
        raise ToolExecutionError("source project/run binding mismatch")
    if result.bound_revision != revision or result.bound_state_hash != state_hash:
        raise ToolExecutionError("source revision/state hash binding mismatch")
    if result.output is None or result.output_hash != payload_hash(result.output):
        raise ToolExecutionError("source output hash mismatch")
    parsed = output_model.model_validate(result.output)
    source = IntegrationSourceRecord(
        result_id=result.result_id,
        task_id=result.task_id,
        tool_name=result.tool_name,
        tool_version=result.tool_version,
        project_id=result.project_id,
        run_id=result.run_id,
        bound_revision=result.bound_revision,
        bound_state_hash=result.bound_state_hash,
        output_hash=result.output_hash,
        backend_provenance=result.backend_provenance,
    )
    return result, parsed, source


def calc_preliminary_section_engineering(value: PreliminarySectionEngineeringToolInput, controller=None, *, project_id=None, run_id=None, revision=None, state_hash=None):
    if controller is None or project_id is None or run_id is None or revision is None or state_hash is None:
        raise ToolExecutionError("integration execution requires bound tool context")
    _, material, material_source = resolve_source_result(controller, project_id, run_id, value.material_result_id, (MATERIAL_TOOL,), revision, state_hash, TypicalMaterialPropertiesResult)
    _, geometry, geometry_source = resolve_source_result(controller, project_id, run_id, value.section_geometry_result_id, GEOMETRY_TOOLS, revision, state_hash, SectionGeometryResult)
    warping = None
    warping_source = None
    if value.section_warping_result_id is not None:
        _, warping, warping_source = resolve_source_result(controller, project_id, run_id, value.section_warping_result_id, WARPING_TOOLS, revision, state_hash, SectionWarpingResult)
    return calculate_preliminary_section_engineering(PreliminarySectionEngineeringCalculatorInput(material=material, section_geometry=geometry, section_warping=warping, material_source=material_source, section_geometry_source=geometry_source, section_warping_source=warping_source))


class SectionEngineeringTools:
    @staticmethod
    def registrations():
        return [ToolRegistration(name="mechcad-calc-preliminary-section-engineering-properties", version="1.0", input_model=PreliminarySectionEngineeringToolInput, output_model=PreliminarySectionEngineeringResult, handler=calc_preliminary_section_engineering, evidence_nodes=("analysis.structural",))]
