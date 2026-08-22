from __future__ import annotations

from collections.abc import Callable

from pydantic import Field

from mechcad_harness.cad_assembly import CadAssemblyProgram, assembly_hash
from mechcad_harness.models.common import Model


class TransientAssemblyAnalysisRequest(Model):
    source_assembly_hash: str = Field(min_length=1)
    transformed_assembly_hash: str = Field(min_length=1)
    sweep_request_hash: str = Field(min_length=1)
    sample_angle_deg: float | None = None
    sample_id: str | None = None
    pairs: tuple[tuple[str, str], ...] = Field(min_length=1)


class TransientAssemblyAnalysisResult(Model):
    source_assembly_hash: str = Field(min_length=1)
    transformed_assembly_hash: str = Field(min_length=1)
    sweep_request_hash: str = Field(min_length=1)
    sample_angle_deg: float | None = None
    sample_id: str | None = None
    measurements: tuple[tuple[str, str, float, float], ...] = Field(min_length=1)


class TransientAssemblyAnalysisService:
    def __init__(self, exact_measure: Callable[[TransientAssemblyAnalysisRequest, CadAssemblyProgram], tuple[tuple[str, str, float, float], ...]]):
        self.exact_measure = exact_measure

    def analyze(self, request: TransientAssemblyAnalysisRequest, transformed_assembly: CadAssemblyProgram) -> TransientAssemblyAnalysisResult:
        transformed_hash = assembly_hash(transformed_assembly)
        if request.transformed_assembly_hash != transformed_hash:
            raise ValueError("transformed assembly hash mismatch")
        measurements = tuple(self.exact_measure(request, transformed_assembly))
        if tuple((moving, stationary) for moving, stationary, _, _ in measurements) != request.pairs:
            raise ValueError("exact measurement pairs do not match requested pair inventory")
        return TransientAssemblyAnalysisResult(
            source_assembly_hash=request.source_assembly_hash,
            transformed_assembly_hash=request.transformed_assembly_hash,
            sweep_request_hash=request.sweep_request_hash,
            sample_angle_deg=request.sample_angle_deg,
            sample_id=request.sample_id,
            measurements=measurements,
        )
