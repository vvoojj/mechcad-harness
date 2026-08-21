from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from mechcad_harness.kinematic_sweep import CadKinematicSweepRequest, RevoluteAxis
from mechcad_harness.models.common import Model
from mechcad_harness.yagi_collision_layout import YagiCollisionLayoutSpec
from mechcad_harness.yagi_el_reference import EL_AXIS_HEIGHT_PARAMETRIC, YagiELKinematicReference


REFERENCE_KINEMATIC_FIXTURE_ONLY = "REFERENCE_KINEMATIC_FIXTURE_ONLY"
YAGI_EL_SWEEP_ADAPTER_VERSION = "yagi-el-sweep-adapter@1.0"


class YagiELSweepReference(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_layout_hash: str = Field(min_length=1)
    el_reference_hash: str = Field(min_length=1)
    source_assembly_hash: str = Field(min_length=1)
    source_assembly_id: str = Field(min_length=1)
    axis: RevoluteAxis
    axis_reference_status: Literal["REFERENCE_KINEMATIC_FIXTURE_ONLY"] = REFERENCE_KINEMATIC_FIXTURE_ONLY
    sample_angles_deg: tuple[float, ...] = Field(min_length=1)
    moving_instance_ids: tuple[str, ...] = Field(min_length=1)
    stationary_instance_ids: tuple[str, ...] = Field(min_length=1)
    adapter_version: Literal["yagi-el-sweep-adapter@1.0"] = YAGI_EL_SWEEP_ADAPTER_VERSION
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


def create_yagi_el_sweep_reference(
    layout: YagiCollisionLayoutSpec,
    el_reference: YagiELKinematicReference,
    *,
    source_assembly_id: str,
    source_assembly_hash: str,
    axis: RevoluteAxis,
    sample_angles_deg: tuple[float, ...],
    moving_instance_ids: tuple[str, ...],
    stationary_instance_ids: tuple[str, ...],
) -> YagiELSweepReference:
    if el_reference.source_layout_hash != layout.authority_hash:
        raise ValueError("EL reference layout hash mismatch")
    if el_reference.selected_axis_height_mm is not None or el_reference.reference_status != EL_AXIS_HEIGHT_PARAMETRIC:
        raise ValueError("EL reference must remain parametric")
    return YagiELSweepReference(
        source_layout_hash=layout.authority_hash,
        el_reference_hash=el_reference.reference_hash,
        source_assembly_hash=source_assembly_hash,
        source_assembly_id=source_assembly_id,
        axis=axis,
        sample_angles_deg=sample_angles_deg,
        moving_instance_ids=moving_instance_ids,
        stationary_instance_ids=stationary_instance_ids,
    )


def create_yagi_el_sweep_request(
    layout: YagiCollisionLayoutSpec,
    el_reference: YagiELKinematicReference,
    *,
    source_assembly_id: str,
    source_assembly_hash: str,
    axis: RevoluteAxis,
    sample_angles_deg: tuple[float, ...],
    moving_instance_ids: tuple[str, ...],
    stationary_instance_ids: tuple[str, ...],
) -> CadKinematicSweepRequest:
    reference = create_yagi_el_sweep_reference(
        layout,
        el_reference,
        source_assembly_id=source_assembly_id,
        source_assembly_hash=source_assembly_hash,
        axis=axis,
        sample_angles_deg=sample_angles_deg,
        moving_instance_ids=moving_instance_ids,
        stationary_instance_ids=stationary_instance_ids,
    )
    if reference.source_layout_hash != layout.authority_hash:
        raise ValueError("EL sweep reference layout hash mismatch")
    return CadKinematicSweepRequest(
        source_assembly_id=reference.source_assembly_id,
        source_assembly_hash=reference.source_assembly_hash,
        axis=reference.axis,
        sample_angles_deg=reference.sample_angles_deg,
        moving_instance_ids=reference.moving_instance_ids,
        stationary_instance_ids=reference.stationary_instance_ids,
    )
