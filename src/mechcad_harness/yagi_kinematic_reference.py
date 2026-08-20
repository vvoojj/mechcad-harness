from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.models.common import Model
from mechcad_harness.yagi_collision_layout import YagiCollisionLayoutSpec


REFERENCE_KINEMATIC_FIXTURE_ONLY = "REFERENCE_KINEMATIC_FIXTURE_ONLY"
YAGI_KINEMATIC_REFERENCE_ADAPTER_VERSION = "yagi-kinematic-reference-adapter@1.0"


class YagiKinematicReferencePlacement(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope_id: str = Field(min_length=1)
    transform: CadRigidTransform
    x_reference_status: Literal["REFERENCE_KINEMATIC_FIXTURE_ONLY"] = REFERENCE_KINEMATIC_FIXTURE_ONLY


class YagiKinematicReferenceModel(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_layout_hash: str = Field(min_length=1)
    synthesis_hash: str = Field(min_length=1)
    placements: tuple[YagiKinematicReferencePlacement, ...] = Field(min_length=1)
    adapter_version: Literal["yagi-kinematic-reference-adapter@1.0"] = YAGI_KINEMATIC_REFERENCE_ADAPTER_VERSION
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


def create_yagi_kinematic_reference(layout: YagiCollisionLayoutSpec) -> YagiKinematicReferenceModel:
    by_id = {placement.envelope_id: placement for placement in layout.placements}
    placements = tuple(
        YagiKinematicReferencePlacement(
            envelope_id=envelope_id,
            transform=CadRigidTransform(
                x_mm=0.0,
                y_mm=by_id[envelope_id].center_y_mm,
                z_mm=by_id[envelope_id].relative_z_offset_mm,
            ),
        )
        for envelope_id in layout.selected_envelope_ids
    )
    return YagiKinematicReferenceModel(
        source_layout_hash=layout.authority_hash,
        synthesis_hash=layout.synthesis_hash,
        placements=placements,
    )
