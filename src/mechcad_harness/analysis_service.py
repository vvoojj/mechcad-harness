from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.backends.freecad_assembly import FreeCADAssemblyBackend
from mechcad_harness.backends.freecad import discover_freecad
from mechcad_harness.cad_analysis import CadAssemblyAnalysisPlan, CadAssemblyAnalysisResult, CadClearanceAnalyzer, analysis_artifact_id, analysis_plan_hash
from mechcad_harness.cad_assembly import instance_object_name
from mechcad_harness.cad_service import CadGenerationService


class CadAssemblyAnalysisService(CadGenerationService):
    def __init__(self, state_manager, backend: FreeCADAssemblyBackend, analyzer: CadClearanceAnalyzer | None = None):
        super().__init__(state_manager, backend)
        self.analyzer = analyzer or CadClearanceAnalyzer()

    def analyze(self, project_id: str, run_id: str, revision: int, state_hash: str, program, plan: CadAssemblyAnalysisPlan, workspace) -> CadAssemblyAnalysisResult:
        binding = self.validate_source(project_id, revision, state_hash)
        assembly = self.backend.verify_persisted_assembly(program, workspace, project_id=binding.project_id, run_id=run_id, revision=binding.revision, state_hash=binding.state_hash)
        known = {item.instance_id for item in assembly.manifest.instances}
        if any(instance not in known for check in plan.checks for instance in (check.instance_a, check.instance_b)):
            raise ValueError("analysis check references an unknown instance")
        plan_hash = analysis_plan_hash(plan, assembly.manifest.assembly_hash)
        artifact_id = analysis_artifact_id(plan.analysis_id, plan_hash, assembly.fcstd.artifact_id, assembly.fcstd.sha256, self.analyzer.version)
        store = ArtifactStore(workspace, project_id=project_id, run_id=run_id)
        existing = store.existing(artifact_id)
        if existing is not None:
            persisted = CadAssemblyAnalysisResult.model_validate_json((Path(workspace) / existing.relative_path).read_text(encoding="utf-8"))
            if persisted.analysis_id != plan.analysis_id or persisted.analysis_plan_hash != plan_hash or persisted.assembly_hash != assembly.manifest.assembly_hash or persisted.assembly_artifact_id != assembly.fcstd.artifact_id or persisted.assembly_artifact_sha256 != assembly.fcstd.sha256 or persisted.analyzer_version != self.analyzer.version or persisted.source_revision != binding.revision or persisted.source_state_hash != binding.state_hash:
                raise ValueError("persisted analysis provenance mismatch")
            return persisted
        names = tuple(sorted({instance_object_name(instance) for check in plan.checks for instance in (check.instance_a, check.instance_b)}))
        payload = self._run_geometry_analysis(workspace, assembly.fcstd.relative_path, names, plan)
        result = self.analyzer.result_from_measurements(plan, assembly.manifest.assembly_hash, payload, project_id=binding.project_id, run_id=run_id, source_revision=binding.revision, source_state_hash=binding.state_hash, assembly_artifact_id=assembly.fcstd.artifact_id, assembly_artifact_sha256=assembly.fcstd.sha256, freecad_version=assembly.freecad_version)
        content = (json.dumps(result.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        artifact = store.publish(artifact_id, ArtifactType.JSON, f"{artifact_id}.json", content, "mechcad-freecad-clearance", self.analyzer.version, binding.revision, binding.state_hash, input_hash=result.analysis_plan_hash)
        persisted = CadAssemblyAnalysisResult.model_validate_json((Path(workspace) / artifact.relative_path).read_text(encoding="utf-8"))
        if persisted != result or persisted.analysis_id != plan.analysis_id or persisted.analysis_plan_hash != result.analysis_plan_hash or persisted.assembly_hash != assembly.manifest.assembly_hash or persisted.assembly_artifact_id != assembly.fcstd.artifact_id or persisted.assembly_artifact_sha256 != assembly.fcstd.sha256 or persisted.source_revision != binding.revision or persisted.source_state_hash != binding.state_hash:
            raise ValueError("persisted analysis result mismatch")
        return persisted

    def _run_geometry_analysis(self, workspace, relative_path, names, plan):
        script = self._analysis_script((Path(workspace) / relative_path).resolve(), names, plan)
        with tempfile.TemporaryDirectory(prefix="mechcad-analysis-") as directory:
            completed = self.backend.part_backend._run(discover_freecad().require_available().executable, script, cwd=Path(directory))
        if completed.returncode != 0:
            raise ValueError(completed.stderr or completed.stdout or "assembly analysis failed")
        line = next((line for line in completed.stdout.splitlines() if line.startswith("M7A2C_JSON=")), None)
        if line is None:
            raise ValueError("structured assembly analysis output missing")
        return json.loads(line.removeprefix("M7A2C_JSON="))

    @staticmethod
    def _analysis_script(path, names, plan):
        pairs = [(check.check_id, check.instance_a, check.instance_b, check.kind) for check in plan.checks]
        return "\n".join([
            "import FreeCAD, json",
            f"doc = FreeCAD.openDocument({str(path)!r})",
            f"names = {names!r}",
            "shapes = {}",
            "for name in names:",
            "    obj = doc.getObject(name)",
            "    if obj is None or obj.Shape.isNull() or not obj.Shape.isValid(): raise RuntimeError('analysis shape invalid')",
            "    shapes[name] = obj.Shape",
            f"checks = {pairs!r}",
            "items = []",
            "for check_id, first, second, kind in checks:",
            "    a, b = shapes['inst_' + bytes(first, 'utf-8').hex()], shapes['inst_' + bytes(second, 'utf-8').hex()]",
            "    common_volume = float(a.common(b).Volume)",
            "    distance = float(a.distToShape(b)[0])",
            "    items.append({'check_id': check_id, 'instance_a': first, 'instance_b': second, 'kind': kind, 'interference_volume_mm3': common_volume, 'distance_mm': distance})",
            "print('M7A2C_JSON=' + json.dumps({'checks': items}, sort_keys=True))",
            "FreeCAD.closeDocument(doc.Name)",
            "",
        ])
