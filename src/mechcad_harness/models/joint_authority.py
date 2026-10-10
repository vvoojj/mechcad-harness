"""Typed trusted joint-and-verification engineering authority declaration.

A :class:`JointAuthorityDeclaration` is self-contained trusted engineering
authority: a policy-authorized issuer states the joint's constituents, roles,
axis/frame and verification requirements directly.  It is admitted into the sole
canonical ``DesignState`` through the existing trusted change machinery; it never
sources candidate CAD/M10/evaluation/solver output.

The declaration is domain-neutral and reusable beyond any single project.  The
admission provenance block is stored with the record but is deliberately excluded
from the semantic ``declaration_hash`` (identity is semantic; provenance is a
separately validated binding).
"""

from __future__ import annotations

import hashlib
import math
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from mechcad_harness.core.canonical import canonical_json_bytes

from .common import Model
from .physical_mechanism import (
    CanonicalGeometryFidelity,
    CanonicalPhysicalComponentRole,
)
from .physical_pair_policy import PhysicalPairClassification

_SCHEMA_VERSION = "mechanical-joint-authority-declaration@1"


def _nonblank(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


def _nonblank_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_nonblank(value) for value in values)


def _sha256(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{label} must be a sha256 hash")
    return value


def _hash_payload(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


class _AuthorityModel(Model):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AuthorityOriginKind(StrEnum):
    TRUSTED_ENGINEERING_DECLARATION = "trusted_engineering_declaration"
    APPROVED_SYNTHETIC_FIXTURE = "approved_synthetic_fixture"
    EXPLICIT_APPROVED_DESIGN_CHOICE = "explicit_approved_design_choice"


class ComponentReferenceKind(StrEnum):
    ENGINEERING_SOURCE_IDENTITY = "engineering_source_identity"
    CANONICAL_COMPONENT_IDENTITY = "canonical_component_identity"
    SYNTHETIC_FIXTURE_IDENTITY = "synthetic_fixture_identity"


class AuthorityOrigin(_AuthorityModel):
    origin_kind: AuthorityOriginKind
    issuer_id: str = Field(min_length=1)
    issuer_role: str | None = None
    scope_project_id: str | None = None
    provenance_note: str = Field(min_length=1)

    _validate = field_validator("issuer_id", "issuer_role", "scope_project_id")(
        lambda cls, value: None if value is None else _nonblank(value)
    )

    @model_validator(mode="after")
    def validate_origin(self) -> "AuthorityOrigin":
        if self.origin_kind is AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE:
            if not self.scope_project_id or not self.scope_project_id.strip():
                raise ValueError(
                    "approved_synthetic_fixture origin requires a scope project id"
                )
        return self


class ComponentAuthorityReference(_AuthorityModel):
    ref_kind: ComponentReferenceKind
    source_identity: str | None = None
    canonical_component_id: str | None = None

    @model_validator(mode="after")
    def validate_single_identity(self) -> "ComponentAuthorityReference":
        if self.ref_kind is ComponentReferenceKind.CANONICAL_COMPONENT_IDENTITY:
            if not self.canonical_component_id or self.source_identity is not None:
                raise ValueError(
                    "canonical component reference requires exactly a canonical_component_id"
                )
            _nonblank(self.canonical_component_id)
            return self
        if not self.source_identity or self.source_identity.strip() == "":
            raise ValueError(
                "non-canonical component reference requires a source_identity"
            )
        if self.canonical_component_id is not None:
            raise ValueError(
                "non-canonical component reference cannot carry a canonical_component_id"
            )
        _nonblank(self.source_identity)
        return self


class JointConstituent(_AuthorityModel):
    constituent_key: str = Field(min_length=1)
    component_ref: ComponentAuthorityReference
    role: CanonicalPhysicalComponentRole
    interface_refs: tuple[str, ...] = ()

    _validate_key = field_validator("constituent_key")(_nonblank)
    _validate_interfaces = field_validator("interface_refs")(_nonblank_tuple)


class JointFrameReference(_AuthorityModel):
    frame_id: str = Field(min_length=1)
    supplied_by_constituent_key: str = Field(min_length=1)
    interface_id: str | None = None

    _validate = field_validator("frame_id", "supplied_by_constituent_key", "interface_id")(
        lambda cls, value: None if value is None else _nonblank(value)
    )


class JointAxisDeclaration(_AuthorityModel):
    frame_reference: JointFrameReference
    origin_x_mm: float = 0.0
    origin_y_mm: float = 0.0
    origin_z_mm: float = 0.0
    direction_x: float = 0.0
    direction_y: float = 0.0
    direction_z: float = 1.0
    length_unit: Literal["mm"] = "mm"
    coordinate_system_id: str = Field(min_length=1)
    axis_sign_rule: str = Field(min_length=1)
    axis_owner_constituent_key: str = Field(min_length=1)

    _validate_text = field_validator("coordinate_system_id", "axis_sign_rule")(
        _nonblank
    )
    _validate_owner = field_validator("axis_owner_constituent_key")(_nonblank)

    @model_validator(mode="before")
    @classmethod
    def normalize_direction(cls, data):
        data = dict(data)
        values = (
            float(data.get("direction_x", 0.0)),
            float(data.get("direction_y", 0.0)),
            float(data.get("direction_z", 1.0)),
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("joint axis direction must be finite")
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 1e-12:
            raise ValueError("joint axis direction must be non-zero")
        return {
            **data,
            "direction_x": values[0] / norm,
            "direction_y": values[1] / norm,
            "direction_z": values[2] / norm,
        }

    @model_validator(mode="after")
    def validate_axis(self) -> "JointAxisDeclaration":
        values = (self.origin_x_mm, self.origin_y_mm, self.origin_z_mm)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("joint axis origin must be finite")
        if (
            self.frame_reference.supplied_by_constituent_key
            != self.axis_owner_constituent_key
        ):
            raise ValueError(
                "axis frame owner must equal the axis owner constituent key"
            )
        return self


class JointPairRequirement(_AuthorityModel):
    requirement_key: str = Field(min_length=1)
    first_constituent_key: str = Field(min_length=1)
    first_interface_id: str = Field(min_length=1)
    second_constituent_key: str = Field(min_length=1)
    second_interface_id: str = Field(min_length=1)
    required_classification: Literal[
        PhysicalPairClassification.CHECK_CLEARANCE
    ] = PhysicalPairClassification.CHECK_CLEARANCE
    requires_home_exact_check: bool = False

    _validate = field_validator(
        "requirement_key",
        "first_constituent_key",
        "first_interface_id",
        "second_constituent_key",
        "second_interface_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_pair(self) -> "JointPairRequirement":
        if self.first_constituent_key == self.second_constituent_key:
            raise ValueError("joint pair requirement must contain two constituents")
        return self


class JointBoundedLimitation(_AuthorityModel):
    limitation_key: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    scope_constituent_keys: tuple[str, ...] = ()

    _validate = field_validator("limitation_key", "statement")(_nonblank)
    _validate_scope = field_validator("scope_constituent_keys")(_nonblank_tuple)


class JointMotionDeclaration(_AuthorityModel):
    motion_kind: Literal["revolute"] = "revolute"
    zero_reference_semantics: Literal["accepted-semantic-home@1"] = (
        "accepted-semantic-home@1"
    )
    supports_internal_motion: bool = False


class JointVerificationRequirement(_AuthorityModel):
    joint_semantic_key: str = Field(min_length=1)
    angle_interval_deg: tuple[float, float]
    required_clearance_mm: float = Field(ge=0)
    required_pairs: tuple[JointPairRequirement, ...] = Field(min_length=1)
    fidelity_requirements: tuple[tuple[str, CanonicalGeometryFidelity], ...] = ()
    required_home_check_semantics: tuple[str, ...] = ()
    bounded_limitations: tuple[JointBoundedLimitation, ...] = ()
    verification_semantics_version: str = Field(min_length=1)

    _validate_text = field_validator("joint_semantic_key", "verification_semantics_version")(
        _nonblank
    )
    _validate_home = field_validator("required_home_check_semantics")(_nonblank_tuple)

    @model_validator(mode="after")
    def validate_verification(self) -> "JointVerificationRequirement":
        start, end = self.angle_interval_deg
        if not all(math.isfinite(value) for value in (start, end)) or start > end:
            raise ValueError("joint angle interval must be finite and ordered")
        if not math.isfinite(self.required_clearance_mm):
            raise ValueError("joint required clearance must be finite")
        fidelity_keys = tuple(key for key, _ in self.fidelity_requirements)
        if any(not key.strip() for key in fidelity_keys) or len(
            set(fidelity_keys)
        ) != len(fidelity_keys):
            raise ValueError("joint fidelity requirement keys must be unique and non-empty")
        limitation_keys = tuple(item.limitation_key for item in self.bounded_limitations)
        if len(set(limitation_keys)) != len(limitation_keys):
            raise ValueError("joint bounded limitation keys must be unique")
        for item in self.bounded_limitations:
            if not item.scope_constituent_keys:
                raise ValueError("joint bounded limitation requires scope constituents")
        return self


class JointAuthorityAdmissionProvenance(_AuthorityModel):
    trust_claim_kind: str = "policy_validated_issuer_assertion"
    admission_source_revision: int = Field(gt=0)
    admission_source_state_hash: str
    admission_run_id: str = Field(min_length=1)
    admission_policy_id: str = Field(min_length=1)
    admission_policy_hash: str
    issuer_id: str = Field(min_length=1)
    approver_id: str = Field(min_length=1)
    approval_content_hash: str
    admitted_at_revision: int = Field(gt=0)

    _validate_claim = field_validator("trust_claim_kind")(_nonblank)
    _validate_hashes = field_validator(
        "admission_source_state_hash",
        "admission_policy_hash",
        "approval_content_hash",
    )(_sha256)


class JointAuthorityDeclaration(_AuthorityModel):
    schema_version: Literal[_SCHEMA_VERSION] = _SCHEMA_VERSION
    project_id: str = Field(min_length=1)
    id: str = Field(min_length=1)
    authority_kind: str = Field(min_length=1)
    semantic_version: str = Field(min_length=1)
    authority_origin: AuthorityOrigin
    constituents: tuple[JointConstituent, ...] = Field(min_length=2)
    parent_constituent_key: str = Field(min_length=1)
    child_constituent_key: str = Field(min_length=1)
    joint_semantic_key: str = Field(min_length=1)
    motion: JointMotionDeclaration
    axis: JointAxisDeclaration
    verification: JointVerificationRequirement
    provenance: JointAuthorityAdmissionProvenance | None = None
    declaration_hash: str = "pending"

    _validate_text = field_validator(
        "project_id",
        "id",
        "authority_kind",
        "semantic_version",
        "parent_constituent_key",
        "child_constituent_key",
        "joint_semantic_key",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_declaration(self) -> "JointAuthorityDeclaration":
        keys = tuple(item.constituent_key for item in self.constituents)
        if len(set(keys)) != len(keys):
            raise ValueError("joint constituent keys must be unique")
        declared = set(keys)
        if self.parent_constituent_key == self.child_constituent_key:
            raise ValueError("joint parent and child constituents must differ")
        if self.parent_constituent_key not in declared:
            raise ValueError("joint parent constituent is not declared")
        if self.child_constituent_key not in declared:
            raise ValueError("joint child constituent is not declared")
        interfaces = {
            item.constituent_key: set(item.interface_refs) for item in self.constituents
        }
        frame = self.axis.frame_reference
        if frame.supplied_by_constituent_key not in declared:
            raise ValueError("joint axis frame owner is not a declared constituent")
        owner_interfaces = interfaces[frame.supplied_by_constituent_key]
        if frame.interface_id is not None:
            if frame.interface_id not in owner_interfaces:
                raise ValueError(
                    "joint axis frame interface is not declared on the owner constituent"
                )
        elif frame.frame_id not in owner_interfaces:
            raise ValueError(
                "joint axis frame reference is not grounded in a declared interface"
            )
        for constituent in self.constituents:
            if (
                constituent.component_ref.ref_kind
                is ComponentReferenceKind.SYNTHETIC_FIXTURE_IDENTITY
                and self.authority_origin.origin_kind
                is not AuthorityOriginKind.APPROVED_SYNTHETIC_FIXTURE
            ):
                raise ValueError(
                    "synthetic fixture component reference requires an approved "
                    "synthetic fixture origin"
                )
        for pair in self.verification.required_pairs:
            for key, interface_id in (
                (pair.first_constituent_key, pair.first_interface_id),
                (pair.second_constituent_key, pair.second_interface_id),
            ):
                if key not in declared:
                    raise ValueError("joint pair references an undeclared constituent")
                if interface_id not in interfaces[key]:
                    raise ValueError("joint pair interface is not declared on constituent")
        for key, _ in self.verification.fidelity_requirements:
            if key not in declared:
                raise ValueError("joint fidelity references an undeclared constituent")
        if self.verification.joint_semantic_key != self.joint_semantic_key:
            raise ValueError("verification joint key must match declaration joint key")
        payload = self.model_dump(mode="json")
        payload.pop("declaration_hash", None)
        payload.pop("provenance", None)
        expected = _hash_payload(payload)
        if self.declaration_hash == "pending":
            object.__setattr__(self, "declaration_hash", expected)
        elif self.declaration_hash != expected:
            raise ValueError("joint authority declaration hash mismatch")
        return self
