from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from mechcad_harness.kinematic_sweep import CadKinematicSweepRequest, RevoluteAxis
from mechcad_harness.models.common import Model
from mechcad_harness.yagi_collision_layout import YagiCollisionLayoutSpec
from mechcad_harness.yagi_kinematic_reference import create_yagi_kinematic_reference


EL_AXIS_HEIGHT_PARAMETRIC = "EL_AXIS_HEIGHT_PARAMETRIC"
YAGI_EL_REFERENCE_ADAPTER_VERSION = "yagi-el-reference-adapter@1.0"


class YagiELKinematicReference(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_layout_hash: str = Field(min_length=1)
    el_axis_height_range_mm: tuple[Literal[180.0], Literal[300.0]] = (180.0, 300.0)
    selected_axis_height_mm: None = None
    reference_status: Literal["EL_AXIS_HEIGHT_PARAMETRIC"] = EL_AXIS_HEIGHT_PARAMETRIC
    adapter_version: Literal["yagi-el-reference-adapter@1.0"] = YAGI_EL_REFERENCE_ADAPTER_VERSION
    reference_hash: str = "pending"

    @model_validator(mode="after")
    def validate_reference_hash(self):
        payload = self.model_dump(mode="json", exclude={"reference_hash"})
        expected = f"sha256:{hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()}"
        if self.reference_hash == "pending":
            object.__setattr__(self, "reference_hash", expected)
        elif self.reference_hash != expected:
            raise ValueError("reference hash does not match canonical reference")
        return self


def create_yagi_el_reference(layout: YagiCollisionLayoutSpec) -> YagiELKinematicReference:
    return YagiELKinematicReference(source_layout_hash=layout.authority_hash)


def create_yagi_el_sweep_reference(
    layout: YagiCollisionLayoutSpec,
    *,
    source_assembly_id: str,
    source_assembly_hash: str,
    axis: RevoluteAxis,
    sample_angles_deg: tuple[float, ...],
    moving_instance_ids: tuple[str, ...],
    stationary_instance_ids: tuple[str, ...],
) -> CadKinematicSweepRequest:
    create_yagi_kinematic_reference(layout)
    create_yagi_el_reference(layout)
    return CadKinematicSweepRequest(
        source_assembly_id=source_assembly_id,
        source_assembly_hash=source_assembly_hash,
        axis=axis,
        sample_angles_deg=sample_angles_deg,
        moving_instance_ids=moving_instance_ids,
        stationary_instance_ids=stationary_instance_ids,
    )
