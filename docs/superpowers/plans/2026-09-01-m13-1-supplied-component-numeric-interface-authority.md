# M13-1 Supplied Component Numeric Interface Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved typed supplied-component numeric-interface authority (frames, shaft/mount interfaces, evidence/facts, derivation transforms, explicit materialization, promotion/reconstruction round trip) without breaking any M12 hash or behavior.

**Architecture:** Shared frozen Pydantic models in lower-level `models/` modules (including the existing authority enums, re-exported from their legacy modules), additive `@1`/`@2` schema branches on candidate and canonical component specifications, one pure role-aware derivation core plus one pure verifier, and extension of existing promotion classification / publication resolve / canonical reconstruction touchpoints. No new store, no M10/CAD change.

**Tech Stack:** Pydantic v2 (existing), MechCAD canonical JSON + SHA-256 (`state.hashing.canonical_json`), existing `ArtifactStore` / `ProjectArtifactResolver`. Pure-Python quaternion helpers consistent with `cad_assembly.CadRigidTransform` and `kinematic_sweep` conventions. No new dependencies.

**Authoritative specification:** `docs/superpowers/specs/2026-09-01-m13-1-supplied-component-numeric-interface-authority.md`

## Global Constraints

- Repository convention: **no commit, tag, or push.** This plan has no commit steps; all work remains uncommitted in the worktree, matching M12 practice.
- Python 3.11+, Pydantic v2, UTC-aware datetimes; `Model`/`CandidateModel`/`CanonicalModel` base classes with `frozen=True, extra="forbid"`.
- All self-hashes are `sha256:<hex>` over `canonical_json(payload)` with the hash field removed (see `_hash` in `candidates/models.py`, `_canonical_hash` in `models/physical_mechanism.py`). Never round or stringify numbers for identity.
- Quaternion convention (must not change): stored order `(w, x, y, z)`, normalized, first component whose `abs(value) > 1e-12` is nonnegative. Axis/direction normalization tolerance `1e-12`.
- Legacy compatibility is a hard gate: every persisted `@1` payload (candidate/canonical geometry reference, `component-specification@1`, `canonical-component-specification@1`, `candidate-canonical-mapping@1`) must parse, self-validate, serialize, and hash **byte-identically** to today. A field that is `None`/absent under `@1` is excluded from the hash payload and the version-aware serializer; M13 `@2` includes it. Default Pydantic `None` serialization is not relied upon.
- No ArtifactStore I/O inside Pydantic validators. Artifact byte verification only at existing trust boundaries (publication resolve, promotion readiness, canonical reconstruction).
- No runtime source->derived transformation: only explicit materialization creates a derived interface; resolvers never apply transforms.
- Text evidence: `canonical_unit = None`; numeric evidence: declared canonical unit required even when unavailable. Unavailable evidence carries `value = None`, never a sentinel.
- Scope: no M13-2/M13-3/M13-4, no generated CAD, no M10/M11 change, no Rotator-specific production types, no new dependencies (scipy/NumPy are optional-profile only and must NOT become core imports in `models/`).
- Full-suite verification ceiling: the accepted M12-6 full suite ran 3411 s (~57 min); use a tool ceiling of at least 4000 s for `pytest tests/`.

---

### Task 1 — Lower-level authority ownership and shared geometry identity

**Purpose:** Break the `candidates.models -> shared interface models -> candidates.models` cycle before adding interface fields, while establishing `GeometryArtifactIdentity` and the legacy-safe reference hash/serialization projections both geometry-reference models will use.

**Files:**
- Create: `src/mechcad_harness/models/component_property.py`
- Create: `src/mechcad_harness/models/geometry_identity.py`
- Modify: `src/mechcad_harness/candidates/models.py` (move enum definitions to import/re-export bindings only)
- Modify: `src/mechcad_harness/models/physical_mechanism.py` (replace canonical enum definitions with legacy-compatible aliases)
- Test: `tests/unit/test_m13_geometry_identity.py`
- Test: `tests/unit/test_m13_authority_enum_compatibility.py`

**Interfaces:**
- Consumes: `mechcad_harness.models.common.Model`, `mechcad_harness.state.hashing.canonical_json`, current `GeometrySourceReference` / `CanonicalGeometrySourceReference` field shapes.
- Produces:
  - `GeometryArtifactIdentity(artifact_id: str, artifact_hash: str, source_identity: str, format: Literal["step"] = "step", coordinate_system_id: str | None = None, geometry_identity_hash: str = "pending")`
  - `GeometryArtifactIdentity.from_candidate(ref: GeometrySourceReference)` / `.from_canonical(ref: CanonicalGeometrySourceReference)`
  - `geometry_identity_hash(identity) -> str`
  - `reference_hash_payload(ref_model_dump: dict) -> dict` — pops `reference_hash` and pops `coordinate_system_id` when it is `None`; returns the hash payload dict.
  - `candidate_geometry_reference_payload(reference, *, m13: bool) -> dict` and `canonical_geometry_reference_payload(reference, *, m13: bool) -> dict` — explicit nested projections used by specification hash payloads and version-aware serializers.

**Behavior / validation:**
- `GeometryArtifactIdentity` is frozen/`extra="forbid"`; `geometry_identity_hash` recomputed over exactly `artifact_id, artifact_hash, source_identity, format, coordinate_system_id` (canonical JSON, sorted keys). A non-`None` `coordinate_system_id` must be a nonempty string; `artifact_id`/`source_identity` nonblank; `artifact_hash` must be `sha256:…` (64 lowercase hex).
- `reference_hash_payload` is the single place that encodes the legacy rule: `coordinate_system_id=None` contributes nothing to any reference hash. This is what preserves golden hashes once Task 3 adds the field.
- Move the exact existing string values of `ComponentPropertyAvailability` and `ComponentPropertyAuthority` to `models/component_property.py`. `candidates.models` imports those same class objects under their existing names; `physical_mechanism.py` imports them as `CanonicalComponentPropertyAvailability` and `CanonicalComponentPropertyAuthority`. Existing import paths therefore remain valid and all serialized enum values remain byte-identical. No second authority taxonomy and no candidate/canonical enum-value mapping remain.
- `supplied_component_interface.py` (Task 4) imports only from `models.component_property`, never from `candidates.models`; candidate/canonical specifications may then import the shared interface models without a cycle.

**Hash impact:** none on existing models yet; helper only.

**Backward compatibility:** existing enum import paths and serialized values are retained through re-exports/aliases; geometry helper is additive.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_m13_geometry_identity.py
import pytest
from pydantic import ValidationError

from mechcad_harness.models.geometry_identity import (
    GeometryArtifactIdentity,
    geometry_identity_hash,
    reference_hash_payload,
)
from mechcad_harness.candidates.models import GeometrySourceReference
from mechcad_harness.models import CanonicalGeometrySourceReference


def test_identity_hash_is_deterministic_and_excludes_none_coordinate_system():
    a = GeometryArtifactIdentity(
        artifact_id="ART-1",
        artifact_hash="sha256:" + "a" * 64,
        source_identity="src:1",
    )
    b = GeometryArtifactIdentity.model_validate(a.model_dump(mode="json"))
    assert a.geometry_identity_hash == b.geometry_identity_hash
    assert "coordinate_system_id" not in reference_hash_payload(
        {"artifact_id": "x", "artifact_hash": "sha256:" + "b" * 64,
         "source_identity": "s", "format": "step",
         "coordinate_system_id": None, "reference_hash": "pending"}
    )
    payload = reference_hash_payload(
        {"artifact_id": "x", "artifact_hash": "sha256:" + "b" * 64,
         "source_identity": "s", "format": "step",
         "coordinate_system_id": "step-model-coordinates@1",
         "reference_hash": "pending"}
    )
    assert payload["coordinate_system_id"] == "step-model-coordinates@1"


def test_identity_projection_from_candidate_and_canonical_references():
    candidate_ref = GeometrySourceReference(
        artifact_id="ART-2", artifact_hash="sha256:" + "c" * 64,
        source_identity="src:2",
    )
    canonical_ref = CanonicalGeometrySourceReference(
        artifact_id="ART-2", artifact_hash="sha256:" + "c" * 64,
        source_identity="src:2",
    )
    assert GeometryArtifactIdentity.from_candidate(candidate_ref).geometry_identity_hash == geometry_identity_hash(
        GeometryArtifactIdentity.from_candidate(candidate_ref)
    )
    assert GeometryArtifactIdentity.from_canonical(canonical_ref) == GeometryArtifactIdentity.from_candidate(candidate_ref)


def test_invalid_inputs_rejected():
    with pytest.raises(ValidationError):
        GeometryArtifactIdentity(
            artifact_id=" ",
            artifact_hash="sha256:" + "a" * 64,
            source_identity="s",
        )
    with pytest.raises(ValidationError):
        GeometryArtifactIdentity(
            artifact_id="a",
            artifact_hash="not-a-hash",
            source_identity="s",
        )
```

```python
# tests/unit/test_m13_authority_enum_compatibility.py
from mechcad_harness.candidates.models import (
    ComponentPropertyAuthority as CandidateAuthority,
    ComponentPropertyAvailability as CandidateAvailability,
)
from mechcad_harness.models.component_property import (
    ComponentPropertyAuthority,
    ComponentPropertyAvailability,
)
from mechcad_harness.models.physical_mechanism import (
    CanonicalComponentPropertyAuthority,
    CanonicalComponentPropertyAvailability,
)


def test_legacy_authority_imports_are_the_shared_enum_classes_with_original_values():
    assert CandidateAvailability is ComponentPropertyAvailability
    assert CandidateAuthority is ComponentPropertyAuthority
    assert CanonicalComponentPropertyAvailability is ComponentPropertyAvailability
    assert CanonicalComponentPropertyAuthority is ComponentPropertyAuthority
    assert CandidateAuthority.MANUFACTURER_DATASHEET.value == "manufacturer_datasheet"
    assert CandidateAvailability.NOT_APPLICABLE.value == "not_applicable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/unit/test_m13_geometry_identity.py tests/unit/test_m13_authority_enum_compatibility.py -q`
Expected: FAIL with `ModuleNotFoundError: mechcad_harness.models.geometry_identity`.

- [ ] **Step 3: Implement the lower-level enum owner and `geometry_identity.py`**

`models/component_property.py` owns only these existing enum declarations, copied byte-for-byte in member names and serialized values from `candidates/models.py`:

```python
class ComponentPropertyAvailability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class ComponentPropertyAuthority(StrEnum):
    MANUFACTURER_DATASHEET = "manufacturer_datasheet"
    DISTRIBUTOR_LISTING = "distributor_listing"
    MEASURED_LOCAL = "measured_local"
    DERIVED_NORMALIZATION = "derived_normalization"
    USER_DECLARED = "user_declared"
```

In `candidates/models.py`, replace the two class declarations with `from mechcad_harness.models.component_property import ComponentPropertyAuthority, ComponentPropertyAvailability`; this preserves existing `from mechcad_harness.candidates.models import ...` imports. In `models/physical_mechanism.py`, import those two lower-level classes with `as CanonicalComponentPropertyAuthority` and `as CanonicalComponentPropertyAvailability`; existing canonical imports remain available with no serialized enum-value change.

Implement `geometry_identity.py`:

```python
from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mechcad_harness.state.hashing import canonical_json

from .common import Model


def _require_sha256(value: str) -> str:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValueError("must be a sha256 hash")
    if any(c not in "0123456789abcdef" for c in value[7:]):
        raise ValueError("must be a sha256 hash")
    return value


def reference_hash_payload(ref: dict) -> dict:
    payload = dict(ref)
    payload.pop("reference_hash", None)
    if payload.get("coordinate_system_id") is None:
        payload.pop("coordinate_system_id", None)
    return payload


def candidate_geometry_reference_payload(reference, *, m13: bool) -> dict:
    payload = {
        "artifact_id": reference.artifact_id,
        "artifact_hash": reference.artifact_hash,
        "source_identity": reference.source_identity,
        "format": reference.format,
    }
    if m13:
        payload["coordinate_system_id"] = reference.coordinate_system_id
        payload["reference_hash"] = reference.reference_hash
    return payload


def canonical_geometry_reference_payload(reference, *, m13: bool) -> dict:
    payload = {
        "artifact_id": reference.artifact_id,
        "artifact_hash": reference.artifact_hash,
        "source_identity": reference.source_identity,
        "format": reference.format,
        "reference_hash": reference.reference_hash,
    }
    if m13:
        payload["coordinate_system_id"] = reference.coordinate_system_id
    return payload


def geometry_identity_hash(identity: "GeometryArtifactIdentity") -> str:
    payload = geometry_identity_payload(identity)
    return "sha256:" + hashlib.sha256(canonical_json(payload)).hexdigest()


def geometry_identity_payload(identity: "GeometryArtifactIdentity") -> dict:
    return {
        "artifact_id": identity.artifact_id,
        "artifact_hash": identity.artifact_hash,
        "source_identity": identity.source_identity,
        "format": identity.format,
        "coordinate_system_id": identity.coordinate_system_id,
    }


class GeometryArtifactIdentity(Model):
    model_config = {"frozen": True, "extra": "forbid"}

    artifact_id: str = Field(min_length=1)
    artifact_hash: str
    source_identity: str = Field(min_length=1)
    format: Literal["step"] = "step"
    coordinate_system_id: str | None = None
    geometry_identity_hash: str = "pending"

    @field_validator("artifact_id", "source_identity")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty or whitespace")
        return value

    @field_validator("artifact_hash")
    @classmethod
    def _hash(cls, value: str) -> str:
        return _require_sha256(value)

    @field_validator("coordinate_system_id")
    @classmethod
    def _coordinate(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("coordinate_system_id must not be empty")
        return value

    @model_validator(mode="after")
    def _validate(self) -> "GeometryArtifactIdentity":
        expected = geometry_identity_hash(self)
        if self.geometry_identity_hash == "pending":
            object.__setattr__(self, "geometry_identity_hash", expected)
        elif self.geometry_identity_hash != expected:
            raise ValueError("geometry identity hash mismatch")
        return self

    @classmethod
    def from_fields(
        cls, artifact_id: str, artifact_hash: str, source_identity: str,
        format: str = "step", coordinate_system_id: str | None = None,
    ) -> "GeometryArtifactIdentity":
        return cls(
            artifact_id=artifact_id, artifact_hash=artifact_hash,
            source_identity=source_identity, format=format,
            coordinate_system_id=coordinate_system_id,
        )

    @classmethod
    def from_candidate(cls, ref) -> "GeometryArtifactIdentity":
        return cls.from_fields(
            artifact_id=ref.artifact_id,
            artifact_hash=ref.artifact_hash,
            source_identity=ref.source_identity,
            format=ref.format,
            coordinate_system_id=getattr(ref, "coordinate_system_id", None),
        )

    @classmethod
    def from_canonical(cls, ref) -> "GeometryArtifactIdentity":
        return cls.from_fields(
            artifact_id=ref.artifact_id,
            artifact_hash=ref.artifact_hash,
            source_identity=ref.source_identity,
            format=ref.format,
            coordinate_system_id=getattr(ref, "coordinate_system_id", None),
        )
```

`GeometryArtifactIdentity` has no custom serializer and never calls either geometry-reference projection helper. It is a new value object, so its ordinary `model_dump(mode="json")` includes `geometry_identity_hash`; only `geometry_identity_payload()` excludes that self-hash for semantic identity. The two reference payload helpers remain exclusively for candidate/canonical reference and specification compatibility branches.

Extend `test_identity_hash_is_deterministic_and_excludes_none_coordinate_system` with this nonlegacy value-object round trip:

```python
def test_identity_with_coordinate_system_serializes_and_validates_its_own_hash():
    identity = GeometryArtifactIdentity(
        artifact_id="ART-COORD",
        artifact_hash="sha256:" + "d" * 64,
        source_identity="vendor:coordinate:1",
        coordinate_system_id="step-model-coordinates@1",
    )
    payload = identity.model_dump(mode="json")
    assert payload["coordinate_system_id"] == "step-model-coordinates@1"
    assert payload["geometry_identity_hash"] == identity.geometry_identity_hash
    assert GeometryArtifactIdentity.model_validate(payload) == identity
    with pytest.raises(ValidationError):
        GeometryArtifactIdentity.model_validate(
            payload | {"geometry_identity_hash": "sha256:" + "0" * 64}
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/unit/test_m13_geometry_identity.py -q`
Expected: all PASS.

**Exit criteria:** lower-level enum ownership has no `candidates.models` dependency; legacy candidate/canonical enum imports are identical class objects with unchanged values; both real projection classmethods pass; `py -3 -m compileall -q src/mechcad_harness` clean.

---

### Task 2 — Pure quaternion/rotation helpers (one shared implementation)

**Purpose:** One MechCAD-owned quaternion helper used by frames, transforms, materialization, and verifier. SciPy decision: **rejected** — scipy is optional-profile only (see `pyproject.toml`); core code must not import it. The helper reuses the exact arithmetic already proven in `kinematic_sweep.py` (`_quaternion_multiply`, `_rotate_vector`) plus the `CadRigidTransform` sign-canonicalization, extracted so M13 does not duplicate it.

**Files:**
- Create: `src/mechcad_harness/models/quaternion.py`
- Test: `tests/unit/test_m13_quaternion.py`

**Interfaces:**
- Produces:
  - `normalize_quaternion(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]` — rejects nonfinite/near-zero norm; normalizes; sign-canonicalizes (first component with `abs > 1e-12` nonnegative).
  - `quaternion_multiply_raw(a, b) -> tuple[float, float, float, float]` — raw Hamilton product only; it never normalizes a pure-vector intermediate.
  - `quaternion_compose(a, b) -> tuple` — applies `b` then `a`, then returns `normalize_quaternion(quaternion_multiply_raw(a, b))`; this is the only orientation-composition API.
  - `rotate_vector(v, q) -> tuple[float, float, float]`
  - `QUATERNION_NORM_TOLERANCE = 1e-12`

**Behavior:** deterministic pure functions; no model I/O; used later by `SuppliedComponentReferenceFrame`, `GeometryDerivationTransform`, and the materialization core (single implementation — no per-model math).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_m13_quaternion.py
import math
import pytest

from mechcad_harness.models.quaternion import (
    normalize_quaternion, quaternion_compose, rotate_vector,
)

IDENTITY = (1.0, 0.0, 0.0, 0.0)
X_180 = (0.0, 1.0, 0.0, 0.0)
Y_180 = (0.0, 0.0, 1.0, 0.0)
Z_180 = (0.0, 0.0, 0.0, 1.0)


def test_q_and_minus_q_hash_identically_after_normalization():
    q = (0.5, 0.5, 0.5, 0.5)
    assert normalize_quaternion(q) == normalize_quaternion(tuple(-c for c in q))


def test_identity_and_180_degree_rotations():
    assert normalize_quaternion(IDENTITY) == IDENTITY
    assert rotate_vector((1.0, 0.0, 0.0), X_180) == pytest.approx((1.0, 0.0, 0.0))
    assert rotate_vector((1.0, 0.0, 0.0), Y_180) == pytest.approx((-1.0, 0.0, 0.0))
    assert rotate_vector((1.0, 0.0, 0.0), Z_180) == pytest.approx((-1.0, 0.0, 0.0))
    assert rotate_vector((0.0, 1.0, 0.0), X_180) == pytest.approx((0.0, -1.0, 0.0))


def test_nearly_zero_components_survive():
    small = normalize_quaternion((1e-13, 1.0, 0.0, 0.0))
    assert small[0] >= 0.0 and abs(math.sqrt(sum(c * c for c in small)) - 1.0) < 1e-12
    tiny_vector = normalize_quaternion((1.0, 1e-13, 0.0, 0.0))
    assert tiny_vector[0] == pytest.approx(1.0)


def test_invalid_quaternions_rejected():
    with pytest.raises(ValueError):
        normalize_quaternion((0.0, 0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        normalize_quaternion((float("nan"), 0.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        normalize_quaternion((1e-13, 1e-13, 1e-13, 1e-13))


def test_composition_matches_kinematic_sweep_convention():
    q = normalize_quaternion((math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4)))
    composed = quaternion_compose(q, q)  # 90 deg about Z applied twice
    assert composed == pytest.approx(Z_180)
    assert rotate_vector((1.0, 0.0, 0.0), composed) == pytest.approx((-1.0, 0.0, 0.0))
```

- [ ] **Step 2: Run to verify failure** — `py -3 -m pytest tests/unit/test_m13_quaternion.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement `quaternion.py`**

```python
from __future__ import annotations

import math
from typing import Sequence

QUATERNION_NORM_TOLERANCE = 1e-12

Quaternion = tuple[float, float, float, float]


def normalize_quaternion(quaternion: Sequence[float]) -> Quaternion:
    q = tuple(float(value) for value in quaternion)
    if len(q) != 4 or any(not math.isfinite(value) for value in q):
        raise ValueError("quaternion components must be finite (w, x, y, z)")
    norm = math.sqrt(sum(value * value for value in q))
    if norm <= QUATERNION_NORM_TOLERANCE:
        raise ValueError("quaternion must have non-zero norm")
    normalized = tuple(value / norm for value in q)
    first_nonzero = next(
        (value for value in normalized if abs(value) > QUATERNION_NORM_TOLERANCE), 1.0
    )
    return tuple(-value for value in normalized) if first_nonzero < 0 else normalized


def quaternion_multiply_raw(first: Sequence[float], second: Sequence[float]) -> Quaternion:
    aw, ax, ay, az = first
    bw, bx, by, bz = second
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def quaternion_compose(first: Sequence[float], second: Sequence[float]) -> Quaternion:
    return normalize_quaternion(quaternion_multiply_raw(first, second))


def rotate_vector(vector: Sequence[float], quaternion: Sequence[float]) -> tuple[float, float, float]:
    orientation = normalize_quaternion(quaternion)
    pure = (0.0, *vector)
    conjugate = (orientation[0], -orientation[1], -orientation[2], -orientation[3])
    # Never call quaternion_compose here: pure vectors are not rotations.
    return quaternion_multiply_raw(quaternion_multiply_raw(orientation, pure), conjugate)[1:]
```

- [ ] **Step 4: Run tests** — all PASS. Also run `py -3 -m pytest tests/unit/test_kinematic_sweep.py -q` to confirm no regression (helper is additive; `kinematic_sweep.py` is NOT refactored in M13-1 to avoid touching M10-adjacent code).

**Exit criteria:** helper green; M10-adjacent sweep tests unchanged and green.

---

### Task 3 — Geometry-reference extension with `@1` golden compatibility

**Purpose:** Add `coordinate_system_id` + `reference_hash` to `GeometrySourceReference` and `coordinate_system_id` to `CanonicalGeometrySourceReference`, preserving both legacy semantic hashes and the byte-identical persisted `@1` JSON shapes used by ordinary `model_dump(mode="json")` persistence.

**Files:**
- Modify: `src/mechcad_harness/candidates/models.py:156-163` (`GeometrySourceReference`)
- Modify: `src/mechcad_harness/models/physical_mechanism.py:180-198` (`CanonicalGeometrySourceReference`)
- Test: `tests/unit/test_m13_legacy_hash_compatibility.py`

**Interfaces:**
- Consumes: `reference_hash_payload` from `models/geometry_identity.py`.
- Produces:
  - `GeometrySourceReference(artifact_id, artifact_hash, source_identity, format="step", coordinate_system_id=None, reference_hash="pending")` — new self-hash and version-aware serializer.
  - `CanonicalGeometrySourceReference(..., coordinate_system_id=None, reference_hash="pending")` — hash payload now goes through `reference_hash_payload`.

**Validation rules:**
- `coordinate_system_id`: `None` (legacy) or nonempty string.
- Both reference hashes computed over `reference_hash_payload(...)` — `reference_hash` excluded always; `coordinate_system_id` excluded when `None`.
- `GeometrySourceReference` uses `@model_serializer(mode="wrap")`: when `coordinate_system_id is None`, serialize precisely `artifact_id`, `artifact_hash`, `source_identity`, `format`; when non-`None`, serialize those fields plus `coordinate_system_id` and `reference_hash`. `CanonicalGeometrySourceReference` serializes its historical five fields (including `reference_hash`) when `coordinate_system_id is None`, and adds `coordinate_system_id` only when non-`None`.
- The serializers are a persistence contract, distinct from the hash projections. `candidate_geometry_reference_payload(reference, m13=False)` and `canonical_geometry_reference_payload(reference, m13=False)` return the pre-M13 nested shapes regardless of accidental model defaults; their `m13=True` counterparts include the new coordinate-system semantics. Task 8 must call these helpers explicitly when constructing specification hash payloads.

**Hash impact / backward compatibility (the hard gate):**
- Candidate `GeometrySourceReference` previously had **no** self-hash, but it is nested in `ComponentSpecificationSnapshot@1`; therefore its `reference_hash` and `coordinate_system_id` must be absent from the legacy nested projection or the existing specification hash changes. Old payloads parse with `reference_hash="pending"` → recomputed in memory, while their version-aware serialized/hashing projection remains the four historical fields.
- Canonical `CanonicalGeometrySourceReference.reference_hash` **is** persisted. Golden regression proves adding the field changes nothing because `None` is excluded.

- [ ] **Step 1: Write the failing golden tests** using the complete literal payloads captured from unmodified M12 models below. Do not regenerate or update these values after changing a model.

```python
# tests/unit/test_m13_legacy_hash_compatibility.py
import json

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates.models import ComponentSpecificationSnapshot, GeometrySourceReference
from mechcad_harness.models import CanonicalComponentSpecification, CanonicalGeometrySourceReference
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity

# Goldens captured from unmodified M12 models on 2026-09-01. They are literal
# compatibility locks, never regenerated after M13 model work begins.
GOLDEN_CANDIDATE_REFERENCE_JSON = (
    '{"artifact_id":"ART-1","artifact_hash":"sha256:' + "1" * 64
    + '","source_identity":"vendor:geometry:1","format":"step"}'
)
GOLDEN_CANDIDATE_SPECIFICATION_JSON = (
    '{"schema_version":"component-specification@1","component_type":"motor",'
    '"manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1",'
    '"properties":[],"geometry_source":' + GOLDEN_CANDIDATE_REFERENCE_JSON
    + ',"interfaces":["output"],"compatibility_declarations":["mount"],'
    '"specification_hash":"sha256:8bf62043ceb309199f6e359cffccc3737a79ee1bd7e065cbd6a186ec7a611e4b"}'
)
GOLDEN_CANONICAL_REFERENCE_JSON = (
    '{"artifact_id":"ART-1","artifact_hash":"sha256:' + "1" * 64
    + '","source_identity":"vendor:geometry:1","format":"step",'
    '"reference_hash":"sha256:a3ec5de09c59fa48a2a331916ab5d060db2d03b4ff5dbe5e3b02185a3bb26f3a"}'
)
GOLDEN_CANONICAL_SPECIFICATION_JSON = (
    '{"schema_version":"canonical-component-specification@1","component_type":"motor",'
    '"manufacturer":"Acme","part_number":"M-1","source_identity":"vendor:acme:M-1",'
    '"properties":[],"geometry_source":' + GOLDEN_CANONICAL_REFERENCE_JSON
    + ',"interfaces":["output"],"compatibility_declarations":["mount"],'
    '"specification_hash":"sha256:10cef1cc30c9f53b92b7908a2b9992edb7ac95a9ac8f24700eb353c31d23f898"}'
)


def test_canonical_reference_legacy_payload_reloads_with_unchanged_hash():
    ref = CanonicalGeometrySourceReference.model_validate_json(GOLDEN_CANONICAL_REFERENCE_JSON)
    assert ref.reference_hash == "sha256:a3ec5de09c59fa48a2a331916ab5d060db2d03b4ff5dbe5e3b02185a3bb26f3a"
    assert ref.coordinate_system_id is None
    assert ref.model_dump(mode="json") == json.loads(GOLDEN_CANONICAL_REFERENCE_JSON)
    assert ref.model_dump_json() == GOLDEN_CANONICAL_REFERENCE_JSON


def test_legacy_candidate_reference_and_complete_specification_round_trip_byte_identically():
    candidate_payload = json.loads(GOLDEN_CANDIDATE_SPECIFICATION_JSON)
    specification = ComponentSpecificationSnapshot.model_validate(candidate_payload)
    assert specification.specification_hash == "sha256:8bf62043ceb309199f6e359cffccc3737a79ee1bd7e065cbd6a186ec7a611e4b"
    assert specification.model_dump(mode="json") == candidate_payload
    assert specification.model_dump_json() == GOLDEN_CANDIDATE_SPECIFICATION_JSON
    assert specification.geometry_source.model_dump(mode="json") == json.loads(GOLDEN_CANDIDATE_REFERENCE_JSON)
    assert specification.geometry_source.model_dump_json() == GOLDEN_CANDIDATE_REFERENCE_JSON


def test_complete_canonical_specification_legacy_hash_is_unchanged():
    canonical = CanonicalComponentSpecification.model_validate_json(GOLDEN_CANONICAL_SPECIFICATION_JSON)
    assert canonical.specification_hash == "sha256:10cef1cc30c9f53b92b7908a2b9992edb7ac95a9ac8f24700eb353c31d23f898"
    assert canonical.model_dump(mode="json") == json.loads(GOLDEN_CANONICAL_SPECIFICATION_JSON)
    assert canonical.model_dump_json() == GOLDEN_CANONICAL_SPECIFICATION_JSON


def test_candidate_reference_additive_fields_parse_old_payload():
    legacy = {
        "artifact_id": "ART-1",
        "artifact_hash": "sha256:" + "1" * 64,
        "source_identity": "src",
        "format": "step",
    }
    ref = GeometrySourceReference.model_validate(legacy)
    assert ref.coordinate_system_id is None
    assert ref.reference_hash.startswith("sha256:")
    assert ref.model_dump(mode="json") == legacy


def test_coordinate_system_id_changes_reference_hash_when_set():
    base = GeometrySourceReference(artifact_id="A", artifact_hash="sha256:" + "2" * 64, source_identity="s")
    stamped = GeometrySourceReference.model_validate(
        base.model_dump(mode="json") | {"coordinate_system_id": "step-model-coordinates@1"}
    )
    assert stamped.reference_hash != base.reference_hash
    assert GeometryArtifactIdentity.from_candidate(stamped).coordinate_system_id == "step-model-coordinates@1"
    canonical = CanonicalGeometrySourceReference.model_validate(
        CanonicalGeometrySourceReference(artifact_id="A", artifact_hash="sha256:" + "2" * 64, source_identity="s").model_dump(mode="json")
        | {"coordinate_system_id": "step-model-coordinates@1"}
    )
    assert GeometryArtifactIdentity.from_canonical(canonical).coordinate_system_id == "step-model-coordinates@1"


def test_coordinate_system_id_validation():
    with pytest.raises(ValidationError):
        GeometrySourceReference(artifact_id="A", artifact_hash="sha256:" + "2" * 64,
                                source_identity="s", coordinate_system_id="  ")
```

- [ ] **Step 2: Run to verify failure** — the first two tests fail because `coordinate_system_id` is rejected by `extra="forbid"` (key not present).

- [ ] **Step 3: Implement**

`candidates/models.py` — replace `GeometrySourceReference`:

```python
class GeometrySourceReference(CandidateModel):
    artifact_id: str = Field(min_length=1)
    artifact_hash: str
    source_identity: str = Field(min_length=1)
    format: Literal["step"] = "step"
    coordinate_system_id: str | None = None
    reference_hash: str = "pending"

    _validate_artifact_hash = field_validator("artifact_hash")(_require_hash)

    @field_validator("coordinate_system_id")
    @classmethod
    def validate_coordinate_system(cls, value):
        if value is not None and not value.strip():
            raise ValueError("coordinate_system_id must not be empty")
        return value

    @model_serializer(mode="wrap")
    def serialize_reference(self, handler):
        del handler
        return candidate_geometry_reference_payload(
            self, m13=self.coordinate_system_id is not None
        )

    @model_validator(mode="after")
    def validate_reference(self):
        expected = _hash_payload(reference_hash_payload(self.model_dump(mode="json")))
        if self.reference_hash == "pending":
            object.__setattr__(self, "reference_hash", expected)
        elif self.reference_hash != expected:
            raise ValueError("geometry source reference hash mismatch")
        return self
```

Add `model_serializer` to the Pydantic imports and `from mechcad_harness.models.geometry_identity import candidate_geometry_reference_payload, reference_hash_payload` to `candidates/models.py`, plus a tiny `_hash_payload(payload) -> str` helper using `canonical_json` (already imported). The serializer above is required; do not assume `None` drops from Pydantic output.

`models/physical_mechanism.py` — in `CanonicalGeometrySourceReference.validate_reference`, replace the hash computation:

```python
        from mechcad_harness.models.geometry_identity import reference_hash_payload
        payload = reference_hash_payload(self.model_dump(mode="json"))
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
```

and add `coordinate_system_id: str | None = None` plus the same nonempty validator and this exact canonical serializer:

```python
@model_serializer(mode="wrap")
def serialize_reference(self, handler):
    del handler
    return canonical_geometry_reference_payload(
        self, m13=self.coordinate_system_id is not None
    )
```

Import `model_serializer` and `canonical_geometry_reference_payload` for Task 8; do not make the canonical model import `candidates.models`.

- [ ] **Step 4: Run focused + golden tests**

Run: `py -3 -m pytest tests/unit/test_m13_legacy_hash_compatibility.py tests/unit/test_m13_geometry_identity.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_canonical_reconstruction.py tests/unit/test_m12_candidate_cad_models.py -q`
Expected: all PASS. **If the golden hash test fails, STOP — a legacy hash broke; fix by ensuring `None` exclusion, not by regenerating goldens.**

**Exit criteria:** old candidate reference, complete candidate specification, canonical reference, and complete canonical specification literal payloads byte-reload and hash identically; the serializer emits no M13 field for `@1`; M12 candidate/canonical/reconstruction suites green.

---

### Task 4 — Evidence, fact, and frame models (slice 2)

**Purpose:** `SuppliedInterfaceEvidence`, `SuppliedInterfaceFact`, `SuppliedComponentReferenceFrame` with unit rules, availability invariants, transform roles, deterministic ordering, and hashing.

**Files:**
- Create: `src/mechcad_harness/models/supplied_component_interface.py` (created in this task; extended by Tasks 5–7)
- Test: `tests/unit/test_m13_supplied_component_interfaces.py` (started here; extended by Tasks 5–8)

**Interfaces (produced):**
```python
class SuppliedInterfaceEvidenceShape(StrEnum): SCALAR="scalar"; VECTOR3="vector3"; QUATERNION="quaternion"; TEXT="text"
class SuppliedInterfaceEvidenceOrigin(StrEnum): SOURCE_DOCUMENT="source_document"; GEOMETRY_INFERRED="geometry_inferred"; HUMAN_CONFIRMED_INTERPRETATION="human_confirmed_interpretation"; DERIVED_MATERIALIZATION="derived_materialization"
class SuppliedInterfaceTransformRole(StrEnum): POINT_MM; LENGTH_MM; DISPLACEMENT_MM; DIRECTION_UNIT; ORIENTATION; TEXT
class SuppliedInterfaceEvidence(Model):  # frozen/forbid
    evidence_id: str; shape: SuppliedInterfaceEvidenceShape
    value: float | tuple[float,float,float] | tuple[float,float,float,float] | str | None = None
    canonical_unit: str | None = None
    availability: ComponentPropertyAvailability   # imported from models.component_property
    authority: ComponentPropertyAuthority
    source_identity: str; applicability_context: str | None = None
    conversion_provenance: str | None = None
    evidence_origin: SuppliedInterfaceEvidenceOrigin
    source_document_identity: str | None = None
    geometry_reference_hash: str | None = None
    basis_evidence_ids: tuple[str, ...] = ()
    evidence_hash: str = "pending"

class SuppliedInterfaceFact(Model):
    fact_id: str; expected_shape: SuppliedInterfaceEvidenceShape
    expected_unit: str | None; transform_role: SuppliedInterfaceTransformRole
    evidence: tuple[SuppliedInterfaceEvidence, ...]   # ordered by evidence_id
    accepted_evidence_id: str | None = None
    fact_hash: str = "pending"

class SuppliedComponentReferenceFrame(Model):
    frame_id: str; geometry_reference_hash: str
    origin: SuppliedInterfaceFact        # VECTOR3 / mm / POINT_MM
    orientation: SuppliedInterfaceFact   # QUATERNION / 1 / ORIENTATION
    frame_hash: str = "pending"
```

**Validation rules (fail closed, in this order):**
1. IDs nonblank; evidence IDs unique within a fact; evidence ordered by `evidence_id` (model validator re-sorts via `object.__setattr__` before hashing, rejects duplicate IDs).
2. Unit rules: `shape is TEXT` ⇒ fact `expected_unit is None` and every evidence `canonical_unit is None`; numeric shapes ⇒ `expected_unit` nonempty and **every** evidence `canonical_unit` equals it (including unavailable records).
3. Availability invariants: `available` ⇒ `value is not None` and shape-correct (scalar finite float; vector3 3 finite floats; quaternion 4 finite floats then `normalize_quaternion`; text nonblank after strip). `missing`/`not_applicable` ⇒ `value is None` (unit rules above still enforced).
4. Transform role is exact, not shape-family based: `POINT_MM -> VECTOR3 / mm`; `LENGTH_MM -> SCALAR / mm`; `DISPLACEMENT_MM -> VECTOR3 / mm`; `DIRECTION_UNIT -> VECTOR3 / 1`; `ORIENTATION -> QUATERNION / 1`; `TEXT -> TEXT / None`. Reject every other shape/unit pair, including scalar points and vector lengths.
5. `accepted_evidence_id`, when set, references existing evidence that is `available`, shape/unit matches the fact, and is not `GEOMETRY_INFERRED` or `DERIVED_MATERIALIZATION` on a direct fact. It may be absent: an unselected, proposed, missing, or inferred-only fact remains a valid persisted snapshot. A materialized fact may select `DERIVED_MATERIALIZATION` only after Task 7's provenance-bound verifier proves its external basis.
6. For `SOURCE_DOCUMENT`, `GEOMETRY_INFERRED`, and `HUMAN_CONFIRMED_INTERPRETATION` evidence, `basis_evidence_ids` is fact-local: every ID must exist in the same `SuppliedInterfaceFact`, IDs are unique, and the local graph is acyclic (DFS). For `DERIVED_MATERIALIZATION` evidence, local validation intentionally does not resolve `basis_evidence_ids`; those IDs are external derivation references and are legal only when the evidence is inside a complete provenance-bound materialized definition. Task 7 performs the bounded external resolution.
7. Self-hashes via canonical JSON excluding the `*_hash` field. Frame orientation value is the canonicalized quaternion (Task 2 helper), so sign variants hash identically.

**Structural validity versus authoritative consumability:** construction validates every evidence record and fact shape/unit/availability invariant, but does not require a selected fact. Add `require_authoritative_fact(fact, *, fact_name, allow_derived_materialization=False)` for consumers: it rejects an absent selection, unavailable selected evidence, inferred selection, and derived-materialization selection unless the caller explicitly supplies the complete provenance-bound materialized context. Task 7's materialization and the future M13-2 resolver call the interface-level helper defined in Task 5; ordinary model validation does not.

**Hash ownership:** evidence hash excludes `evidence_hash`; fact hash excludes `fact_hash` (includes evidence hashes); frame hash excludes `frame_hash` (includes fact hashes + frame binding). Authority, availability, evidence origin, source identity, acceptance selection, and confirmation basis enter; run IDs, timestamps, runtime paths, and ArtifactStore locations do not.

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_m13_supplied_component_interfaces.py  (initial cases)
import pytest
from pydantic import ValidationError

from mechcad_harness.models.component_property import ComponentPropertyAvailability, ComponentPropertyAuthority
from mechcad_harness.models.supplied_component_interface import (
    SuppliedInterfaceEvidence, SuppliedInterfaceEvidenceOrigin, SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceFact, SuppliedInterfaceTransformRole, SuppliedComponentReferenceFrame,
)


def _evidence(**overrides):
    base = dict(
        evidence_id="E1", shape=SuppliedInterfaceEvidenceShape.SCALAR, value=8.0,
        canonical_unit="mm", availability=ComponentPropertyAvailability.AVAILABLE,
        authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
        source_identity="datasheet:5840", evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
    )
    return SuppliedInterfaceEvidence.model_validate(base | overrides)


def test_scalar_evidence_hash_deterministic_and_changes_with_authority():
    first = _evidence()
    again = SuppliedInterfaceEvidence.model_validate(first.model_dump(mode="json"))
    assert first.evidence_hash == again.evidence_hash
    changed = SuppliedInterfaceEvidence.model_validate(
        first.model_dump(mode="json") | {"authority": ComponentPropertyAuthority.MEASURED_LOCAL}
    )
    assert changed.evidence_hash != first.evidence_hash


def test_numeric_missing_retains_unit_and_none_value():
    ev = _evidence(value=None, availability=ComponentPropertyAvailability.MISSING)
    assert ev.value is None and ev.canonical_unit == "mm"


def test_text_requires_unit_none_and_rejects_blank():
    text = _evidence(shape=SuppliedInterfaceEvidenceShape.TEXT, value="M4", canonical_unit=None)
    assert text.canonical_unit is None
    with pytest.raises(ValidationError):
        _evidence(shape=SuppliedInterfaceEvidenceShape.TEXT, value="M4", canonical_unit="mm")
    with pytest.raises(ValidationError):
        _evidence(shape=SuppliedInterfaceEvidenceShape.TEXT, value="   ", canonical_unit=None)


def test_unavailable_evidence_rejects_sentinel_values():
    with pytest.raises(ValidationError):
        _evidence(value=0.0, availability=ComponentPropertyAvailability.MISSING)
    with pytest.raises(ValidationError):
        _evidence(value=(0.0, 0.0, 0.0),
                  shape=SuppliedInterfaceEvidenceShape.VECTOR3,
                  availability=ComponentPropertyAvailability.NOT_APPLICABLE)


def test_fact_orders_evidence_and_rejects_duplicate_ids():
    a = _evidence(evidence_id="E2", value=8.01,
                  authority=ComponentPropertyAuthority.MEASURED_LOCAL,
                  evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
                  geometry_reference_hash="sha256:" + "a" * 64)
    b = _evidence(evidence_id="E1")
    fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(a, b), accepted_evidence_id="E1",
    )
    assert tuple(e.evidence_id for e in fact.evidence) == ("E1", "E2")
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR, expected_unit="mm",
            transform_role=SuppliedInterfaceTransformRole.LENGTH_MM, evidence=(a, a),
        )


def test_inferred_evidence_cannot_be_accepted():
    inferred = _evidence(value=8.01, authority=ComponentPropertyAuthority.MEASURED_LOCAL,
                         evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
                         geometry_reference_hash="sha256:" + "a" * 64)
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR, expected_unit="mm",
            transform_role=SuppliedInterfaceTransformRole.LENGTH_MM, evidence=(inferred,),
            accepted_evidence_id=inferred.evidence_id,
        )


def test_inferred_only_fact_is_a_valid_unresolved_snapshot():
    inferred = _evidence(
        value=8.01, authority=ComponentPropertyAuthority.MEASURED_LOCAL,
        evidence_origin=SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED,
        geometry_reference_hash="sha256:" + "a" * 64,
    )
    fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(inferred,),
    )
    assert fact.accepted_evidence_id is None


def test_normal_confirmation_basis_is_fact_local_and_derived_basis_is_deferred():
    base = _evidence(evidence_id="E1")
    confirmation = _evidence(
        evidence_id="E2", value=8.0,
        evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
        basis_evidence_ids=("E1",),
    )
    fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(base, confirmation), accepted_evidence_id="E2",
    )
    assert fact.evidence[1].basis_evidence_ids == ("E1",)
    derived = _evidence(
        evidence_id="D1", value=10.0,
        evidence_origin=SuppliedInterfaceEvidenceOrigin.DERIVED_MATERIALIZATION,
        basis_evidence_ids=("SOURCE-EVIDENCE",),
    )
    derived_fact = SuppliedInterfaceFact(
        fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
        expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
        evidence=(derived,), accepted_evidence_id="D1",
    )
    assert derived_fact.accepted_evidence_id == "D1"


def test_dangling_normal_confirmation_basis_fails():
    with pytest.raises(ValidationError):
        SuppliedInterfaceFact(
            fact_id="F1", expected_shape=SuppliedInterfaceEvidenceShape.SCALAR,
            expected_unit="mm", transform_role=SuppliedInterfaceTransformRole.LENGTH_MM,
            evidence=(
                _evidence(
                    evidence_id="E2", basis_evidence_ids=("MISSING",),
                    evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION,
                ),
            ),
        )


def test_frame_normalizes_quaternion_sign_variants():
    origin_fact = SuppliedInterfaceFact(
        fact_id="FO", expected_shape=SuppliedInterfaceEvidenceShape.VECTOR3, expected_unit="mm",
        transform_role=SuppliedInterfaceTransformRole.POINT_MM,
        evidence=(SuppliedInterfaceEvidence.model_validate(dict(
            evidence_id="EO", shape=SuppliedInterfaceEvidenceShape.VECTOR3, value=(0.1, -5.1, 30.0),
            canonical_unit="mm", availability=ComponentPropertyAvailability.AVAILABLE,
            authority=ComponentPropertyAuthority.USER_DECLARED, source_identity="handoff",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION))),
    )
    def _orientation(value):
        return SuppliedInterfaceFact(
            fact_id="FQ", expected_shape=SuppliedInterfaceEvidenceShape.QUATERNION, expected_unit="1",
            transform_role=SuppliedInterfaceTransformRole.ORIENTATION,
            evidence=(SuppliedInterfaceEvidence.model_validate(dict(
                evidence_id="EQ", shape=SuppliedInterfaceEvidenceShape.QUATERNION, value=value,
                canonical_unit="1", availability=ComponentPropertyAvailability.AVAILABLE,
                authority=ComponentPropertyAuthority.USER_DECLARED, source_identity="handoff",
                evidence_origin=SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION))),)

    positive = SuppliedComponentReferenceFrame(
        frame_id="output-frame", geometry_reference_hash="sha256:" + "b" * 64,
        origin=origin_fact, orientation=_orientation((0.5, 0.5, 0.5, 0.5)))
    negative = SuppliedComponentReferenceFrame(
        frame_id="output-frame", geometry_reference_hash="sha256:" + "b" * 64,
        origin=origin_fact, orientation=_orientation((-0.5, -0.5, -0.5, -0.5)))
    assert positive.frame_hash == negative.frame_hash
```

- [ ] **Step 2: Run to verify failure** — `py -3 -m pytest tests/unit/test_m13_supplied_component_interfaces.py -q` → `ModuleNotFoundError`.

- [ ] **Step 3: Implement** the three models in `models/supplied_component_interface.py` exactly per the validation rules above. Reuse `ComponentPropertyAvailability`/`ComponentPropertyAuthority` only from `.component_property`, `normalize_quaternion` from `.quaternion`, and the canonical JSON self-hash pattern. This module must not import `candidates.models`, `physical_mechanism`, or ArtifactStore. Ordering canonicalization inside model validators uses `object.__setattr__` on the frozen instance (existing repository pattern, see `CanonicalPlacement`).

- [ ] **Step 4: Run tests** — all PASS. Also rerun `py -3 -m pytest tests/unit/test_m13_quaternion.py tests/unit/test_m13_geometry_identity.py -q`.

**Exit criteria:** evidence/fact/frame validation and hashing green; no existing model modified.

---

### Task 5 — Direct supplied interfaces (slice 3)

**Purpose:** `RotationalShaftInterface`, bounded D-flat profile, `MountingFaceInterface`, `MountingHole`, pilot/boss, and the direct variant of `SuppliedComponentInterfaceDefinition` with exact selected-geometry binding.

**Files:**
- Modify: `src/mechcad_harness/models/supplied_component_interface.py` (append)
- Test: `tests/unit/test_m13_supplied_component_interfaces.py` (append)

**Interfaces (produced):**
```python
class SuppliedShaftProfileKind(StrEnum): ROUND; D_FLAT; KEYWAY; SPLINE; THREAD; OTHER
class SuppliedShaftDFlatProfile(Model):
    flat_normal_direction: SuppliedInterfaceFact   # VECTOR3 / 1 / DIRECTION_UNIT
    flat_across_dimension: SuppliedInterfaceFact   # SCALAR / mm / LENGTH_MM
    start_from_shoulder: SuppliedInterfaceFact     # SCALAR / mm / LENGTH_MM
    effective_length: SuppliedInterfaceFact        # SCALAR / mm / LENGTH_MM

class RotationalShaftInterface(Model):
    interface_id: str; geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    reference_frame_id: str | None = None
    axis_point: SuppliedInterfaceFact            # VECTOR3 / mm / POINT_MM
    axis_direction: SuppliedInterfaceFact        # VECTOR3 / 1 / DIRECTION_UNIT
    nominal_shaft_diameter: SuppliedInterfaceFact    # SCALAR / mm / LENGTH_MM
    usable_axial_engagement_length: SuppliedInterfaceFact  # SCALAR / mm / LENGTH_MM
    shoulder_reference_plane: tuple[SuppliedInterfaceFact, SuppliedInterfaceFact] | None = None  # (point POINT_MM, normal DIRECTION_UNIT)
    shaft_profile: SuppliedShaftProfileKind | None = None
    d_flat_profile: SuppliedShaftDFlatProfile | None = None
    thread_designation: SuppliedInterfaceFact | None = None  # TEXT, optional
    interface_hash: str = "pending"

class MountingHole(Model):
    hole_id: str
    center: SuppliedInterfaceFact       # VECTOR3 / mm / POINT_MM
    axis: SuppliedInterfaceFact         # VECTOR3 / 1 / DIRECTION_UNIT
    nominal_diameter: SuppliedInterfaceFact  # SCALAR / mm / LENGTH_MM
    thread_designation: SuppliedInterfaceFact | None = None  # TEXT

class SuppliedPilotBossReference(Model):
    point: SuppliedInterfaceFact; axis: SuppliedInterfaceFact; diameter: SuppliedInterfaceFact

class MountingFaceInterface(Model):
    interface_id: str; geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    face_reference_id: str              # semantic, never a face index
    reference_frame_id: str             # REQUIRED, resolved at specification level (Task 8)
    plane_point: SuppliedInterfaceFact  # VECTOR3 / mm / POINT_MM
    outward_normal: SuppliedInterfaceFact  # VECTOR3 / 1 / DIRECTION_UNIT
    holes: tuple[MountingHole, ...] = ()    # ordered by hole_id
    pilot_boss: SuppliedPilotBossReference | None = None
    interface_hash: str = "pending"

class SuppliedComponentInterfaceDefinition(Model):
    model_config = {"frozen": True, "extra": "forbid"}
    kind: Literal["direct", "materialized"] = "direct"
    interface_id: str
    geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    shaft: RotationalShaftInterface | None = None
    mounting_face: MountingFaceInterface | None = None
    derivation: "InterfaceDerivationProvenance | None" = None  # defined Task 7; forward ref via model_rebuild()
    interface_hash: str = "pending"
```

**Validation rules:**
- Exactly one of `shaft` / `mounting_face` set; the variant's `interface_id`, `geometry_reference_hash`, and `geometry.geometry_identity_hash` must equal the definition-level values.
- Structural dimensions: every `available` evidence value in `nominal_shaft_diameter`, `usable_axial_engagement_length`, D-flat length fields, hole diameters, and pilot diameter must be finite and `> 0`; missing/not-applicable evidence and absent selections remain valid. This validator must not call a selected-evidence helper.
- Structural directions: every `available` `DIRECTION_UNIT` evidence vector is finite, nonzero, and normalized at fact construction through `normalize_direction`; missing/not-applicable evidence and absent selections remain valid. Direction sign remains meaningful.
- `d_flat_profile` allowed only when `shaft_profile is D_FLAT`; `thread_designation` fact must be TEXT-shaped.
- `kind == "direct"` ⇒ `derivation is None`; `kind == "materialized"` ⇒ Task 7 requirement (validator added there).
- `kind == "direct"` rejects an accepted evidence whose origin is `DERIVED_MATERIALIZATION`; only `kind == "materialized"` may select derived-materialization evidence, and only after its complete `InterfaceDerivationProvenance` validates. A direct interface may retain unselected derived observation records for audit but cannot consume them as authority.
- Add `require_authoritatively_consumable_interface(definition)` for materialization/resolver consumers. It requires all fields needed by the selected shaft or mount type to have selected available source-document/human-confirmed evidence; a materialized definition instead requires complete provenance plus selected derived-materialization evidence. This helper, not construction, is the authoritative gate.
- A standalone fact/evidence object with `DERIVED_MATERIALIZATION` origin may be parsed as structural data, but it is never consumable by itself. External basis resolution is enabled only by a `kind="materialized"` interface carrying complete `InterfaceDerivationProvenance`; direct interfaces and general fact consumers cannot opt into it.
- Hole ordering canonicalized by `hole_id`; duplicate IDs rejected.
- Self-hashes exclude the hash field and include all nested fact hashes.

**Hash ownership:** interface hash excludes `interface_hash`; consumes fact hashes, geometry identity hash, and `geometry_reference_hash`.

- [ ] **Step 1: Write failing tests** — append to `tests/unit/test_m13_supplied_component_interfaces.py`: valid shaft (round + D-flat), reversed axis direction yields different hash, every available nonpositive diameter rejected even when it is unselected, missing diameter and missing/unselected axis remain valid snapshots, inferred-only shaft facts with no `accepted_evidence_id` produce a valid direct interface but `require_authoritatively_consumable_interface` raises unresolved-authority `ValueError`, a later human-confirmed selected evidence makes the same shape consumable, direct selected `DERIVED_MATERIALIZATION` evidence is rejected, mounting face with 1 hole and 4 asymmetric holes hash-order independence (pass holes in reverse order → same hash), duplicate hole ID rejected, thread TEXT fact on hole, nonblank semantic `face_reference_id` accepted even when it looks like a source-document identifier such as `Face3`, blank ID rejected, and definition/direct variant mismatch rejected.

- [ ] **Step 2: Run to verify failure** (ModuleNotFoundError / AttributeError on new names).

- [ ] **Step 3: Implement** per the model shapes and rules above. Do not import or copy `models.structural._is_raw_identity_value`: it is appropriate to structural backend-selector provenance but would reject a legitimate source-document semantic ID here. M13-1 validates only nonblank `face_reference_id`; the associated mounting frame and facts carry typed source authority. No FreeCAD/topology/regex heuristic decides whether a semantic identifier is authoritative. Add `normalize_direction` to `models/quaternion.py`:

```python
def normalize_direction(vector: Sequence[float]) -> tuple[float, float, float]:
    v = tuple(float(value) for value in vector)
    if len(v) != 3 or any(not math.isfinite(value) for value in v):
        raise ValueError("direction components must be finite")
    norm = math.sqrt(sum(value * value for value in v))
    if norm <= QUATERNION_NORM_TOLERANCE:
        raise ValueError("direction must be non-zero")
    return tuple(value / norm for value in v)
```

- [ ] **Step 4: Run tests** — focused file green.

**Exit criteria:** direct interface variants validate and hash deterministically; no canonical/candidate model touched yet.

---

### Task 6 — Role-aware derivation transform (slice 4)

**Purpose:** `GeometryDerivationTransform` plus the **single** production transformation core used later by both materialization creation and verification replay.

**Files:**
- Modify: `src/mechcad_harness/models/supplied_component_interface.py` (append transform model + `apply_transform_role`)
- Test: `tests/unit/test_m13_geometry_materialization.py` (created; extended by Task 7)

**Interfaces (produced):**
```python
class GeometryDerivationStatus(StrEnum): PROPOSED="proposed"; ACCEPTED="accepted"

class GeometryDerivationUnitConversion(Model):
    source_unit: str
    derived_unit: str
    declaration: str

class GeometryDerivationAuthorityRole(StrEnum):
    TRANSLATION_MM = "translation_mm"
    ROTATION = "rotation"
    UNIFORM_SCALE = "uniform_scale"

class GeometryDerivationAuthorityFact(Model):
    authority_role: GeometryDerivationAuthorityRole
    expected_shape: SuppliedInterfaceEvidenceShape
    expected_unit: str
    evidence: tuple[SuppliedInterfaceEvidence, ...]
    accepted_evidence_id: str | None = None
    authority_fact_hash: str = "pending"

class GeometryDerivationTransform(Model):
    transform_id: str
    source_geometry: GeometryArtifactIdentity
    derived_geometry: GeometryArtifactIdentity
    source_geometry_reference_hash: str
    derived_geometry_reference_hash: str
    translation_fact: GeometryDerivationAuthorityFact  # VECTOR3 / mm
    rotation_fact: GeometryDerivationAuthorityFact     # QUATERNION / 1
    uniform_scale_fact: GeometryDerivationAuthorityFact  # SCALAR / 1
    unit_conversion: GeometryDerivationUnitConversion
    status: GeometryDerivationStatus
    transform_hash: str = "pending"

def apply_transform_role(role, value, transform) -> value  # PURE, single implementation:
    # POINT_MM:        s*R*p + t
    # LENGTH_MM:       s*L
    # DISPLACEMENT_MM: s*R*v
    # DIRECTION_UNIT:  normalize_direction(R*d)
    # ORIENTATION:     normalize_quaternion(compose(q_R, q))
    # TEXT:            value unchanged
def transform_fact(fact, transform) -> SuppliedInterfaceEvidence  # pure; builds one
    # derived_materialization evidence carrying basis=(source accepted
    # evidence_id,). The ID is intentionally external to the derived fact;
    # Task 7 binds it to the matching source fact through provenance.
```

**Validation rules:**
- `source_geometry.geometry_identity_hash != derived_geometry.geometry_identity_hash` required (distinct artifacts); all four geometry hash strings nonblank.
- `GeometryDerivationAuthorityFact` reuses `SuppliedInterfaceEvidence` and its existing availability/authority/origin/source/basis semantics but is a transform-authority fact, not an interface materialization fact. Its exact role matrix is `TRANSLATION_MM -> VECTOR3/mm`, `ROTATION -> QUATERNION/1`, `UNIFORM_SCALE -> SCALAR/1`; IDs/order/selection validation and self-hash follow Task 4's fact rules. `UNIFORM_SCALE` is deliberately not `LENGTH_MM` and not added to `SuppliedInterfaceTransformRole`.
- Transform effective values are computed properties from selected authority facts: `translation_mm`, `rotation_quaternion`, and `scale`. No cached/default fields exist. Available translation is finite; rotation is normalized/canonical; scale is finite and strictly positive.
- `unit_conversion` is required and validates nonblank `source_unit`, `derived_unit`, and `declaration`; its complete three-field payload participates in `transform_hash`. It explicitly declares the source-to-derived unit relationship and is never inferred from scale alone.
- A source-document transform uses selected `SOURCE_DOCUMENT` evidence for all three authority facts; a geometry-observed proposal retains unselected `GEOMETRY_INFERRED` evidence; and a confirmed transform selects `HUMAN_CONFIRMED_INTERPRETATION` evidence that cites fact-local earlier evidence through `basis_evidence_ids`. These use the existing authority, source identity, source-document identity, geometry-reference hash, and confirmation-basis fields; no second authority taxonomy is introduced.
- `status == PROPOSED` is structurally valid but never materializable. `status == ACCEPTED` is materializable only when `require_authoritative_transform(transform)` finds selected available source-document/human-confirmed evidence for translation, rotation, and scale plus the required unit-conversion declaration. An accepted-but-unselected/inferred-only component remains a valid unresolved snapshot but is not authoritative. Explicit selected `(0,0,0)` and identity-quaternion evidence is required; no numeric default is authority.
- Nonuniform scale/shear is not representable — the model has only a uniform scalar `scale`; no code path can apply a per-axis scale.
- `transform_fact` accepts only facts satisfying the exact Task 4 role matrix; it does not infer a role from a scalar/vector shape. `apply_transform_role` also rejects a runtime value whose Python shape does not match the supplied role, so a future caller cannot scale a scalar point or rotate a length.

**Hash ownership:** transform hash excludes `transform_hash`; includes both geometry identities/reference hashes, complete translation/rotation/scale authority-fact hashes and selections, effective normalized values, complete `unit_conversion`, and status. Thus changing any component evidence, selection, authority, origin, source, confirmation basis, or unit declaration changes transform identity; paths, runs, and ArtifactStore locations do not. `InterfaceFactDerivationBinding` has no independent identity; its complete slot/source-fact/source-evidence/hash/role payload is consumed by the parent provenance hash.

- [ ] **Step 1: Write failing tests** — `tests/unit/test_m13_geometry_materialization.py`:

```python
import math
import pytest

from mechcad_harness.models.component_property import ComponentPropertyAuthority, ComponentPropertyAvailability
from mechcad_harness.models.supplied_component_interface import (
    GeometryDerivationAuthorityFact, GeometryDerivationAuthorityRole,
    GeometryDerivationStatus, GeometryDerivationTransform, GeometryDerivationUnitConversion,
    SuppliedInterfaceEvidence, SuppliedInterfaceEvidenceOrigin, SuppliedInterfaceEvidenceShape,
    SuppliedInterfaceTransformRole, apply_transform_role,
)
from mechcad_harness.models.geometry_identity import GeometryArtifactIdentity

SCALE_125 = 1.25


def _authority_fact(role, shape, unit, value, evidence_id):
    return GeometryDerivationAuthorityFact(
        authority_role=role, expected_shape=shape, expected_unit=unit,
        evidence=(SuppliedInterfaceEvidence(
            evidence_id=evidence_id, shape=shape, value=value, canonical_unit=unit,
            availability=ComponentPropertyAvailability.AVAILABLE,
            authority=ComponentPropertyAuthority.MANUFACTURER_DATASHEET,
            source_identity="vendor:normalization:1",
            evidence_origin=SuppliedInterfaceEvidenceOrigin.SOURCE_DOCUMENT,
        ),),
        accepted_evidence_id=evidence_id,
    )


def _transform(scale=SCALE_125, status=GeometryDerivationStatus.ACCEPTED):
    def identity(artifact_id):
        return GeometryArtifactIdentity(
            artifact_id=artifact_id, artifact_hash="sha256:" + "1" * 64,
            source_identity="s")

    return GeometryDerivationTransform(
        transform_id="T1",
        source_geometry=identity("ART-SRC"),
        derived_geometry=identity("ART-NRM"),
        source_geometry_reference_hash="sha256:" + "2" * 64,
        derived_geometry_reference_hash="sha256:" + "3" * 64,
        translation_fact=_authority_fact(
            GeometryDerivationAuthorityRole.TRANSLATION_MM,
            SuppliedInterfaceEvidenceShape.VECTOR3, "mm", (0.0, 0.0, 0.0), "translation-source",
        ),
        rotation_fact=_authority_fact(
            GeometryDerivationAuthorityRole.ROTATION,
            SuppliedInterfaceEvidenceShape.QUATERNION, "1", (1.0, 0.0, 0.0, 0.0), "rotation-source",
        ),
        uniform_scale_fact=_authority_fact(
            GeometryDerivationAuthorityRole.UNIFORM_SCALE,
            SuppliedInterfaceEvidenceShape.SCALAR, "1", scale, "scale-source",
        ),
        unit_conversion=GeometryDerivationUnitConversion(
            source_unit="source-model-unit", derived_unit="derived-model-unit",
            declaration="explicit-model-unit-normalization@1"
        ),
        status=status,
    )


def _proposed_inferred_transform():
    payload = _transform().model_dump(mode="json")
    payload["status"] = GeometryDerivationStatus.PROPOSED
    payload["uniform_scale_fact"]["evidence"][0]["evidence_origin"] = (
        SuppliedInterfaceEvidenceOrigin.GEOMETRY_INFERRED
    )
    payload["uniform_scale_fact"]["evidence"][0]["evidence_hash"] = "pending"
    payload["uniform_scale_fact"]["accepted_evidence_id"] = None
    payload["uniform_scale_fact"]["authority_fact_hash"] = "pending"
    payload["transform_hash"] = "pending"
    return GeometryDerivationTransform.model_validate(payload)


def test_point_and_length_roles_scale():
    t = _transform()
    assert apply_transform_role(SuppliedInterfaceTransformRole.POINT_MM, (8.0, 0.0, 24.0), t) == pytest.approx((10.0, 0.0, 30.0))
    assert apply_transform_role(SuppliedInterfaceTransformRole.LENGTH_MM, 8.0, t) == pytest.approx(10.0)


def test_direction_and_text_roles():
    t = _transform()
    assert apply_transform_role(SuppliedInterfaceTransformRole.DIRECTION_UNIT, (0.0, 0.0, 2.0), t) == pytest.approx((0.0, 0.0, 1.0))
    assert apply_transform_role(SuppliedInterfaceTransformRole.TEXT, "M4", t) == "M4"


def test_displacement_has_no_translation():
    t = _transform()
    payload = t.model_dump(mode="json")
    payload["translation_fact"]["evidence"][0]["value"] = (1.0, 2.0, 3.0)
    payload["translation_fact"]["evidence"][0]["evidence_hash"] = "pending"
    payload["translation_fact"]["authority_fact_hash"] = "pending"
    payload["transform_hash"] = "pending"
    t2 = GeometryDerivationTransform.model_validate(payload)
    assert apply_transform_role(SuppliedInterfaceTransformRole.DISPLACEMENT_MM, (1.0, 0.0, 0.0), t2) == pytest.approx((1.25, 0.0, 0.0))
    assert apply_transform_role(SuppliedInterfaceTransformRole.POINT_MM, (1.0, 0.0, 0.0), t2) == pytest.approx((2.25, 2.0, 3.0))


def test_orientation_composition_and_identity_scale():
    t = _transform(scale=1.0)
    assert apply_transform_role(SuppliedInterfaceTransformRole.ORIENTATION, (0.0, 1.0, 0.0, 0.0), t) == pytest.approx((0.0, 1.0, 0.0, 0.0))


def test_invalid_transforms_rejected():
    with pytest.raises(Exception):
        _transform(scale=0.0)
    with pytest.raises(Exception):
        _transform(scale=float("nan"))
    bad = _transform().model_dump(mode="json")
    bad["derived_geometry"]["artifact_id"] = bad["source_geometry"]["artifact_id"]
    with pytest.raises(Exception):
        GeometryDerivationTransform.model_validate(bad)


@pytest.mark.parametrize("fact_field, evidence_field, value", [
    ("translation_fact", "source_identity", "vendor:translation:2"),
    ("rotation_fact", "evidence_origin", SuppliedInterfaceEvidenceOrigin.HUMAN_CONFIRMED_INTERPRETATION),
    ("uniform_scale_fact", "authority", ComponentPropertyAuthority.MEASURED_LOCAL),
])
def test_all_transform_component_evidence_changes_identity(fact_field, evidence_field, value):
    transform = _transform()
    payload = transform.model_dump(mode="json")
    payload[fact_field]["evidence"][0][evidence_field] = value
    payload[fact_field]["evidence"][0]["evidence_hash"] = "pending"
    payload[fact_field]["authority_fact_hash"] = "pending"
    payload["transform_hash"] = "pending"
    assert GeometryDerivationTransform.model_validate(payload).transform_hash != transform.transform_hash


def test_unit_conversion_declaration_changes_transform_identity():
    transform = _transform()
    changed = GeometryDerivationTransform.model_validate(
        transform.model_dump(mode="json") | {
            "unit_conversion": {
                "source_unit": "source-model-unit", "derived_unit": "derived-model-unit",
                "declaration": "explicit-model-unit-normalization@2",
            },
            "transform_hash": "pending",
        }
    )
    assert changed.transform_hash != transform.transform_hash


# Authority-gate cases: accepted scale plus altered/unselected translation
# rejects materialization; accepted scale plus altered/unselected rotation
# rejects; translation/rotation evidence changes change transform hash; explicit
# selected identity translation + identity rotation + scale is authoritative;
# inferred-only translation or rotation remains structurally valid but is not
# materializable.
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** `GeometryDerivationUnitConversion`, `GeometryDerivationTransform`, `require_authoritative_transform`, `apply_transform_role`, and `transform_fact` using only the existing M13 evidence enums/models, `models/quaternion.py`, and `math`. `ORIENTATION` calls normalized `quaternion_compose`; vector rotation uses `rotate_vector`, whose raw pure-vector intermediates never pass through composition normalization. One role-aware implementation, no wrapper duplication. Do not accept a bare `scale + authority + source_identity` as transform provenance.

- [ ] **Step 4: Run tests** — both M13 test files green.

**Exit criteria:** role-aware math proven for point/length/displacement/direction/orientation/text with scale `1.25`; transform authority requires selected evidence for all three components with no implicit identity defaults; invalid/unresolved transforms rejected.

---

### Task 7 — Materialization provenance and verifier (slice 5)

**Purpose:** `InterfaceDerivationProvenance` with durable embedded `source_interface_snapshot`, and the `MaterializedInterfaceVerifier` that **recomputes** the derived interface rather than trusting stored hashes.

**Files:**
- Modify: `src/mechcad_harness/models/supplied_component_interface.py` (append provenance + verifier)
- Test: `tests/unit/test_m13_geometry_materialization.py` (append)

**Interfaces (produced):**
```python
class InterfaceDerivationProvenance(Model):
    source_interface_snapshot: SuppliedComponentInterfaceDefinition  # kind MUST be "direct"
    source_interface_hash: str
    source_reference_frame_snapshot: SuppliedComponentReferenceFrame | None = None
    source_reference_frame_hash: str | None = None
    derived_reference_frame_id: str | None = None
    derived_reference_frame_hash: str | None = None
    transform_id: str
    transform_hash: str
    source_geometry: GeometryArtifactIdentity
    derived_geometry: GeometryArtifactIdentity
    source_geometry_reference_hash: str
    derived_geometry_reference_hash: str
    fact_derivation_bindings: tuple["InterfaceFactDerivationBinding", ...]
    materialization_algorithm: Literal["supplied-interface-materialization@1"] = "supplied-interface-materialization@1"
    provenance_hash: str = "pending"

class InterfaceFactDerivationBinding(Model):
    # One bounded source/derived fact slot. `fact_path` is a closed frame or
    # interface slot such as "reference_frame.origin", "shaft.axis_point", or
    # "mounting_face.holes[hole-id].axis", never a general reference path.
    fact_path: str
    source_fact_id: str
    derived_fact_id: str
    source_evidence_id: str
    source_evidence_hash: str
    transform_role: SuppliedInterfaceTransformRole

class DerivedInterfaceSemantics(Model):
    # Immutable derived body only: interface ID, derived geometry binding, and
    # exactly one transformed shaft or mounting-face payload. No provenance/hash.
    interface_id: str
    geometry_reference_hash: str
    geometry: GeometryArtifactIdentity
    shaft: RotationalShaftInterface | None = None
    mounting_face: MountingFaceInterface | None = None

class MaterializedInterfaceResult(Model):
    interface: SuppliedComponentInterfaceDefinition
    reference_frame: SuppliedComponentReferenceFrame | None = None

def derive_reference_frame_semantics(source_frame, transform) -> SuppliedComponentReferenceFrame:
    # Transforms accepted origin POINT_MM and orientation ORIENTATION through
    # the same transform_fact/apply_transform_role core; binds derived geometry.

def derive_interface_semantics(source, transform) -> DerivedInterfaceSemantics:
    # Requires source.kind == "direct" and transform.status == ACCEPTED.
    # Transforms accepted source facts only, using Task 6 transform_fact.

def build_derivation_provenance(source, source_frame_or_none, transform) -> InterfaceDerivationProvenance:
    # Does not require a materialized interface. It binds the durable direct
    # source snapshot/hash and every source/derived transform geometry field.
    # It also emits one deterministic binding for every transformed fact slot;
    # the binding records source/derived fact IDs, source evidence ID/hash, and
    # role because fact IDs alone are only local to an individual fact. When a
    # frame is present, persist its snapshot/hash and expected derived ID/hash.
    # Use the closed slot vocabulary for the source variant: frame fields use
    # "reference_frame.origin" / "reference_frame.orientation"; shaft fields
    # use "shaft.<field>", mounting fields use "mounting_face.<field>", and
    # hole fields use "mounting_face.holes[<hole_id>].<field>". The derived
    # fact ID is the ID produced for that same slot by the corresponding derive
    # function. No arbitrary path is accepted.

def construct_materialized_result(interface_semantics, frame_semantics_or_none, provenance) -> MaterializedInterfaceResult:
    # Requires derived geometry bindings, frame provenance fields, and matching
    # materialized interface reference_frame_id; returns interface + optional frame.

def materialize_interface(source, source_frame_or_none, transform) -> MaterializedInterfaceResult:
    interface_semantics = derive_interface_semantics(source, transform)
    frame_semantics = None if source_frame_or_none is None else derive_reference_frame_semantics(source_frame_or_none, transform)
    return construct_materialized_result(
        interface_semantics, frame_semantics,
        build_derivation_provenance(source, source_frame_or_none, transform),
    )

class MaterializedInterfaceVerifier:
    @staticmethod
    def replay(provenance, transform) -> MaterializedInterfaceResult:
        # PURE semantic replay:
        #  1. validate provenance self-hash and that snapshot is direct
        #  2. validate transform hash/id match provenance; require_authoritative_transform
        #     rejects proposed, unselected, and inferred-only transform evidence
        #  3. rebuild interface semantics and optional frame semantics from
        #     embedded snapshots, then construct the expected result
        #  4. For every derived-materialization evidence, resolve its basis ID
        #     only through the matching fact_derivation_binding and embedded
        #     source fact; verify source fact/evidence IDs and hashes, source
        #     accepted_evidence_id, role, and derived fact correspondence.
        #  5. compare provenance.source_interface_hash == snapshot.interface_hash
        #  6. return expected (caller compares against the persisted active interface)
    @staticmethod
    def verify(provenance, transform, persisted_active_interface, persisted_active_frame=None) -> None:
        # caller resolves the exact active frame from the enclosing specification;
        # raises MaterializationIntegrityError unless replay equals both records.
```

**Validation rules:**
- Provenance self-hash excludes `provenance_hash`; `source_interface_hash` must equal `source_interface_snapshot.interface_hash` (validated at construction).
- `MaterializationIntegrityError(ValueError)` is the only failure type raised by replay/verify — integrity semantics (per spec §Failure Semantics).
- Replay compares **complete typed interface semantics** (Pydantic equality), then the persisted `interface_hash` — never hash fields alone.
- `InterfaceFactDerivationBinding` is the only external-basis association. It is emitted for every closed source/derived fact slot and sorted by `fact_path`; `fact_path` is an allowlisted interface slot, not a general cross-document reference. For normal evidence origins, basis IDs still resolve only within their own fact. For `DERIVED_MATERIALIZATION`, each basis ID must resolve uniquely through the corresponding binding to the embedded direct source fact, and replay must verify source fact ID, source evidence ID, source evidence hash, source accepted selection, transform role, and derived fact/evidence correspondence. Missing source evidence, same-ID/different-hash substitution, wrong source fact, wrong role, or a basis aimed at another source fact raises `MaterializationIntegrityError`.
- Construction is deliberately non-circular: `derive_reference_frame_semantics` / `derive_interface_semantics` have no provenance input; `build_derivation_provenance` has no materialized result; only `construct_materialized_result` joins their independently complete results. `MaterializedInterfaceVerifier` calls the same derivation and construction functions, not an alternate implementation.
- `derive_interface_semantics` first calls both `require_authoritatively_consumable_interface(source)` and `require_authoritative_transform(transform)`. An inferred-only or unselected direct source interface, and a proposed/unselected/inferred-only transform, are structurally valid but materialization raises unresolved-authority `ValueError`; neither is silently transformed. The source must select only source-document/human-confirmed evidence, while constructed derived facts select deterministic `DERIVED_MATERIALIZATION` evidence and are permitted only on the provenance-bound materialized definition. A direct interface with selected derived-materialization evidence is rejected before any external basis lookup.

- [ ] **Step 1: Write failing tests** — append to `tests/unit/test_m13_geometry_materialization.py`:

```python
def test_materialization_replay_recomputes_derived_interface():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)  # helper in this module
    transform = _transform()
    semantics = derive_interface_semantics(source, transform)
    provenance = build_derivation_provenance(source, None, transform)
    materialized = construct_materialized_result(semantics, None, provenance)
    expected = MaterializedInterfaceVerifier.replay(provenance, transform)
    assert expected == materialized
    MaterializedInterfaceVerifier.verify(provenance, transform, materialized.interface)  # no raise


@pytest.mark.parametrize("mutate", [
    lambda p: p.model_copy(update={"source_interface_hash": "sha256:" + "9" * 64}),
    lambda p: p.model_copy(update={"transform_hash": "sha256:" + "9" * 64}),
    lambda p: p.model_copy(update={"materialization_algorithm": "supplied-interface-materialization@2"}),
])
def test_tampered_provenance_fails_integrity(mutate):
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    transform = _transform()
    materialized = materialize_interface(source, None, transform)
    provenance = materialized.interface.derivation
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(mutate(provenance), transform, materialized.interface)


def test_changed_source_value_breaks_replay():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    transform = _transform()
    materialized = materialize_interface(source, None, transform)
    provenance = materialized.interface.derivation

    # Forge a persisted active interface whose diameter differs from what the
    # durable source snapshot + transform actually recompute.
    forged_active = _replace_accepted_diameter(materialized, 9.0)
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(provenance, transform, forged_active)


def test_materialization_rejects_structurally_valid_unresolved_source_interface():
    unresolved = _inferred_only_shaft_definition()
    with pytest.raises(ValueError, match="unresolved authority"):
        materialize_interface(unresolved, None, _transform())


def test_materialization_rejects_proposed_or_inferred_only_transform():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    with pytest.raises(ValueError, match="unresolved authority"):
        materialize_interface(source, None, _proposed_inferred_transform())


def test_materialized_external_basis_is_bound_to_source_fact_and_hash():
    source = _accepted_shaft_definition(scale_independent_fixtures=True)
    materialized = materialize_interface(source, None, _transform())
    provenance = materialized.interface.derivation
    assert provenance.fact_derivation_bindings
    assert all(binding.source_evidence_hash.startswith("sha256:") for binding in provenance.fact_derivation_bindings)

    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(
            _remove_source_evidence_from_provenance(provenance), _transform(), materialized
        )
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(
            _substitute_source_evidence_hash(provenance), _transform(), materialized
        )
    with pytest.raises(MaterializationIntegrityError):
        MaterializedInterfaceVerifier.verify(
            _bind_basis_to_another_source_fact(provenance), _transform(), materialized
        )


# These helpers rebuild only the typed provenance/source snapshot and all
# affected self-hashes, leaving the persisted active materialized interface
# unchanged. They do not bypass Pydantic validation or use arbitrary paths:
# `_remove_source_evidence_from_provenance` removes the mapped source evidence;
# `_substitute_source_evidence_hash` keeps the same evidence_id but changes its
# value and recomputed hash; `_bind_basis_to_another_source_fact` changes only a
# binding's source_fact_id to a different closed source slot.


def test_direct_interface_cannot_use_external_derivation_basis():
    with pytest.raises(ValueError, match="derived_materialization"):
        _direct_definition_with_derived_materialization_evidence()


# Frame-materialization cases: source mounting frame -> accepted transform ->
# one derived frame plus materialized mount; optional shaft frame follows the
# same path; origin/orientation are transformed correctly; interface references
# the active derived frame; source/derived frame tamper fails replay; two
# interfaces sharing one source frame deduplicate to one equal derived frame;
# same derived frame ID with unequal hash is rejected by specification validation.
# Fresh candidate resolve, promotion, and canonical reconstruction each replay
# this source-frame -> derived-frame binding without candidate-memory.


def _replace_accepted_diameter(definition, new_value):
    """Rebuild a materialized shaft definition with a substituted diameter
    evidence value and a recomputed (self-consistent) hash, so the tamper is
    detected by replay recomputation rather than by a stale hash."""
    import copy
    payload = definition.model_dump(mode="json")
    shaft = payload["shaft"]
    evidence = shaft["nominal_shaft_diameter"]["evidence"][0]
    evidence["value"] = new_value
    # Recompute nested fact/evidence/interface hashes from the bottom up so the
    # forged record is internally valid: revalidate through the models.
    from mechcad_harness.models.supplied_component_interface import (
        SuppliedInterfaceEvidence, SuppliedInterfaceFact, RotationalShaftInterface,
    )
    diameter_fact = SuppliedInterfaceFact.model_validate(
        shaft["nominal_shaft_diameter"] | {"fact_hash": "pending"})
    shaft["nominal_shaft_diameter"] = diameter_fact.model_dump(mode="json")
    payload["shaft"] = RotationalShaftInterface.model_validate(
        shaft | {"interface_hash": "pending"}).model_dump(mode="json")
    payload["interface_hash"] = "pending"
    return type(definition).model_validate(payload)
```

(Implement `_accepted_shaft_definition` in the test module: build a shaft interface whose diameter/length facts carry accepted `source_document` evidence, points carry accepted evidence, per Task 4/5 helpers.)

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** `DerivedInterfaceSemantics`, `MaterializedInterfaceResult`, `derive_reference_frame_semantics`, `derive_interface_semantics`, `build_derivation_provenance(source, source_frame_or_none, transform)`, `construct_materialized_result`, thin convenience `materialize_interface`, `MaterializedInterfaceVerifier`, and `MaterializationIntegrityError` in `models/supplied_component_interface.py`. `derive_reference_frame_semantics` and `derive_interface_semantics` both call the same `transform_fact` / `apply_transform_role` core. Reject direct source interfaces with absent/unaccepted required facts, proposed transforms, source/derived geometry binding mismatches, source-bound frame reuse, missing active derived frame, conflicting shared derived frame, and active materialized definitions whose provenance snapshot is treated as an endpoint.

- [ ] **Step 4: Run tests** — both materialization files green.

**Exit criteria:** materialization is durable, independently recomputable, tamper-fail-closed; replay uses identical core as creation; every derived basis is resolved through a closed provenance binding with source evidence hash verification, and direct interfaces cannot invoke that external-basis path.

---

### Task 8 — Candidate + canonical specification integration, `@1`/`@2` (slice 6)

**Purpose:** Add the three tuple fields plus `@1`/`@2` schema branches to `ComponentSpecificationSnapshot` and `CanonicalComponentSpecification`, with specification-level frame resolution and materialization-consistency validation.

**Files:**
- Modify: `src/mechcad_harness/candidates/models.py:165-189` (`ComponentSpecificationSnapshot`)
- Modify: `src/mechcad_harness/models/physical_mechanism.py:201-233` (`CanonicalComponentSpecification`)
- Test: `tests/unit/test_m13_legacy_hash_compatibility.py` (append specification goldens) and `tests/unit/test_m13_supplied_component_interfaces.py` (append integration cases)

**Interfaces (produced):**
```python
class ComponentSpecificationSnapshot(CandidateModel):
    schema_version: Literal["component-specification@1", "component-specification@2"] = "component-specification@1"
    component_type: str
    manufacturer: str | None = None
    part_number: str | None = None
    source_identity: str
    properties: tuple[ComponentPropertySnapshot, ...] = ()
    geometry_source: GeometrySourceReference | None = None
    interfaces: tuple[str, ...] = ()
    compatibility_declarations: tuple[str, ...] = ()
    supplied_reference_frames: tuple[SuppliedComponentReferenceFrame, ...] = ()
    supplied_interface_definitions: tuple[SuppliedComponentInterfaceDefinition, ...] = ()
    geometry_derivation_transforms: tuple[GeometryDerivationTransform, ...] = ()
    specification_hash: str = "pending"
```
(`CanonicalComponentSpecification` mirrors this with `canonical-component-specification@1|@2`.)

**Validation rules (both classes):**
1. `schema_version == "@1"` ⇒ the three M13 tuples MUST be empty and `geometry_source.coordinate_system_id` MUST be `None`. Its hash payload must use the complete pre-M13 top-level field set and replace nested `geometry_source` with `candidate_geometry_reference_payload(geometry_source, m13=False)` or `canonical_geometry_reference_payload(..., m13=False)`: candidate shape is exactly `artifact_id`, `artifact_hash`, `source_identity`, `format`; canonical shape additionally contains its historical `reference_hash`. This preserves goldens even though candidate references now carry an in-memory `reference_hash`.
2. `schema_version == "@2"` ⇒ hash payload includes all three tuples; if any supplied interface/transform exists, `geometry_source` is required with nonempty `coordinate_system_id`.
3. Unique IDs across frames (`frame_id`), interfaces (`interface_id`), transforms (`transform_id`).
4. Every interface `reference_frame_id` resolves to a `frame_id` in the same specification (dangling/cross-spec invalid); every typed `interface_id` appears exactly once in the existing string `interfaces` tuple, so endpoint resolution remains exclusively through the active typed registry.
5. Every direct interface / frame / materialized interface `geometry_reference_hash` equals the hash of the enclosing `geometry_source` (candidate: `geometry_source.reference_hash`; canonical: same field name). Materialized interfaces additionally bind to the `derived_geometry` of their provenance's transform, and that transform must exist in `geometry_derivation_transforms` with status `ACCEPTED`.
6. A materialized interface with `reference_frame_id` requires exactly one active derived frame of that ID in `supplied_reference_frames`; the frame must bind to selected derived geometry and match provenance `derived_reference_frame_id`/hash. Its provenance source-frame snapshot/hash must match the source interface's resolved frame; pure replay receives this exact active frame from the enclosing specification. Multiple materialized interfaces sharing a derived frame ID are valid only when the active frame hash is identical; conflicting same-ID derived frames fail closed.
7. For a `MountingFaceInterface`, resolve its required frame and compare the accepted outward-normal fact with the frame orientation's accepted local `+Z` (using the shared `rotate_vector`) within the approved `1e-9` angular residual only when both accepted values exist. If either selection is absent, preserve the unresolved structural snapshot; `require_authoritatively_consumable_interface` later rejects it as unresolved. If both are selected and mismatch, validation fails.
8. Unused frames intentionally allowed.
9. Deterministic ordering: frames/interfaces/transforms canonicalized by their ID fields before hashing.
10. Both specification classes use `@model_serializer(mode="wrap")`: `@1` returns the exact historical top-level field set (no M13 tuples) and its nested legacy geometry projection; `@2` returns all M13 tuples and the M13 geometry projection. This is required because `StateManager` and candidate publication persist ordinary `model_dump(mode="json")`; hash compatibility alone would otherwise leave `None`/empty M13 defaults in persisted JSON.
11. For each active materialized interface, model validation resolves its transform by ID/hash and exact active frame by ID/hash from that same specification, then calls the pure `MaterializedInterfaceVerifier.verify(...)` path from Task 7. It recomputes source-to-derived interface/frame semantics but performs no ArtifactStore access; artifact-aware callers repeat the same verification after byte checks.

**Hash impact:** `@2` specifications change candidate identity when any nested record changes (spec §Candidate Identity). `@1` untouched.

- [ ] **Step 1: Write failing tests** — use the pre-change literal candidate/canonical reference and complete specification JSON/hash goldens already defined in `test_m13_legacy_hash_compatibility.py` (Task 3), and add direct `model_dump(mode="json")` equality assertions alongside the `model_dump_json()` assertions. New `@2` cases: interface present ⇒ candidate hash changes; evidence annotation change changes hash; frame reorder does not change hash; dangling frame reference rejected; a typed interface omitted from string `interfaces` rejected; plane/frame `+Z` mismatch rejected; `@1` with nonempty frames rejected; `@1` rejects non-`None` coordinate system; `@2` interface/transform payload rejects missing selected-geometry coordinate system. Active/historical test: construct a materialized active interface whose durable source snapshot shares its `interface_id`, then assert all endpoint membership/resolution checks inspect only `supplied_interface_definitions`; adding/removing/mutating the embedded snapshot cannot make it an active `PhysicalComponentInstance.interfaces` or `MechanicalConnection` endpoint.

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** both classes. Hash helper pattern:

```python
def _specification_hash_payload(self) -> dict:
    payload = self.model_dump(mode="json")
    payload.pop("specification_hash")
    if self.schema_version.endswith("@1"):
        for field in ("supplied_reference_frames", "supplied_interface_definitions",
                      "geometry_derivation_transforms"):
            payload.pop(field)
        if self.geometry_source is not None:
            payload["geometry_source"] = candidate_geometry_reference_payload(
                self.geometry_source, m13=False
            )  # canonical class calls canonical_geometry_reference_payload instead
    elif self.geometry_source is not None:
        payload["geometry_source"] = candidate_geometry_reference_payload(
            self.geometry_source, m13=True
        )  # canonical class calls canonical_geometry_reference_payload instead
    return payload
```

Do not share this method by importing candidate models into canonical models. Give each class a local `_specification_hash_payload` with the corresponding lower-level projection helper; the two bodies differ only in that explicit helper name.

Each class also implements its exact persistence branch, not a generic `exclude_none` call:

```python
@model_serializer(mode="wrap")
def serialize_specification(self, handler):
    del handler
    payload = self._specification_payload_for_schema()  # no hash removal
    return payload
```

`_specification_payload_for_schema()` returns all historical declared fields and the explicit legacy nested geometry projection for `@1`; for `@2`, it returns all declared fields including the three canonicalized M13 tuples and the M13 nested geometry projection. `_specification_hash_payload()` starts from this same version-specific payload and removes only `specification_hash`. This keeps persisted JSON and semantic hashing aligned without relying on Pydantic defaults.

- [ ] **Step 4: Run focused + regression** — `py -3 -m pytest tests/unit/test_m13_legacy_hash_compatibility.py tests/unit/test_m13_supplied_component_interfaces.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_canonical_physical_mechanism.py tests/unit/test_m12_canonical_reconstruction.py tests/unit/test_m12_promotion_models.py -q` — all PASS.

**Exit criteria:** literal `@1` candidate and canonical specifications round-trip byte-identically via both `model_dump(mode="json")` and `model_dump_json()`, retain exact pre-change hashes, and never expose M13 defaults; `@2` semantics and complete M13 projections are enforced; M12 candidate/canonical suites green. **STOP if any `@1` candidate or canonical golden hash changes; repair the version-specific projection/serializer, never regenerate the golden.**

---

### Task 9 — Candidate publication / fresh artifact-aware replay (slice 7)

**Purpose:** A freshly persisted candidate with any nonempty M13 `@2` semantic payload receives the exact artifact-aware trust checks required for that payload at resolve time. `CandidateCurrentnessService` remains unchanged.

**Files:**
- Modify: `src/mechcad_harness/candidates/services.py` (`CandidatePublicationService.resolve` only, lines ~111-133)
- Test: `tests/unit/test_m13_publication_replay.py` (new)

**Behavior:**
- After the existing `CandidateIntegrityVerifier().verify(...)` and source-binding check in `resolve`, compute exactly `has_m13_payload = bool(spec.supplied_reference_frames) or bool(spec.supplied_interface_definitions) or bool(spec.geometry_derivation_transforms)` for each `component_specifications` entry. Only when `spec.schema_version == "component-specification@2" and has_m13_payload` is true does the additional M13 artifact-aware pass run. For an entirely empty `component-specification@2`, do not add this M13 pass; its selected `geometry_source`, when present, still follows the existing geometry-source trust path. An `@1` specification cannot carry M13 tuples by Task 8 validation and follows the unchanged legacy path. For a triggered `@2` specification:
  - the enclosing selected `geometry_source` continues through the existing selected-geometry verification;
  - for every `ACCEPTED` `geometry_derivation_transform`, verify both exact `source_geometry` and `derived_geometry` through `store.read_verified_in_project(artifact_id, expected_type=ArtifactType.STEP, expected_hash=artifact_hash)`. `None`/missing, byte tamper, wrong type, or hash/project binding mismatch raises existing `CandidateIntegrityError`. `PROPOSED` transforms are still fully model/hash validated but do not receive mandatory source/derived ArtifactStore verification because they are not accepted geometry authority and cannot materialize an interface;
  - for every materialized interface, verify the provenance source/derived geometry identities using the same byte-verified artifacts, resolve the accepted transform by provenance ID/hash and the exact active derived frame from the enclosing specification, then call `MaterializedInterfaceVerifier.verify(provenance, transform, active_interface, active_frame_or_none)`. Failure raises `CandidateIntegrityError` — an integrity failure, not currentness and not engineering infeasibility;
  - frames alone require no additional artifacts beyond the enclosing selected `geometry_source`.
- Both proposed and accepted transforms are always parsed, self-hash validated, and semantically checked by the model layer. ArtifactStore byte verification is intentionally limited to accepted transforms and materialized provenance, matching the approved rule that only accepted geometry derivations are trusted authority; a proposed transform remains persisted proposal data rather than an accepted artifact claim.
- Pydantic validators perform no I/O (Global Constraint 9): the pure replay inside model validation is hash/semantics-only; artifact reads happen only in this service method.

**Tests:** publish an `@2` candidate with an accepted transform and no active interface; resolve verifies both transform source/derived STEP artifacts. Tamper the transform source artifact or derived artifact → `CandidateIntegrityError`. Publish an `@2` candidate with frames only; resolve verifies only the selected enclosing geometry. Publish an `@2` candidate with a materialized interface; resolve performs artifact verification plus replay. Mutate the persisted interface semantics (rebuild candidate JSON with a changed derived diameter and stale `interface_hash`) → replay fails. Resolve an entirely empty `@2` specification and an `@1` interface-free candidate through the unchanged legacy geometry path. The tests assert the exact `has_m13_payload` trigger rather than the phrase “nonempty interface fields.”

**Exit criteria:** resolve-time replay proven for persisted candidates; currentness service untouched; existing publication tests green.

---

### Task 10 — Promotion classification and mapping `@2` (slice 8)

**Purpose:** Complete candidate→canonical projection of the new fields with exact self-hash classifications and truthful `candidate-canonical-mapping@1|@2` compatibility.

**Files:**
- Modify: `src/mechcad_harness/candidates/promotion_models.py` (`CandidatePromotionPolicy.mapping_schema_version` → `Literal["candidate-canonical-mapping@1", "candidate-canonical-mapping@2"] = "candidate-canonical-mapping@1"`; `PromotableMechanismProjection` needs no field change — it already carries full `CanonicalComponentSpecification` tuples)
- Modify: `src/mechcad_harness/candidates/promotion.py` (`_verify_policy` ~line 927, `_expected_classifications` ~line 1001, `_canonical_specification` ~line 436, `_verify_geometry_sources` ~line 943)
- Test: `tests/unit/test_m13_interface_promotion_roundtrip.py` (new)

**Behavior (exact):**
1. `_verify_policy`: compute `has_v2_specification = any(specification.schema_version == "component-specification@2" for specification in candidate.component_specifications)`. If true, require `mapping_schema_version == "candidate-canonical-mapping@2"`; if false, require `candidate-canonical-mapping@1`. This rule is schema-based, not tuple-content-based: an empty `@2` specification must never cross promotion under mapping `@1`. No other policy semantics change.
2. `_expected_classifications` additions (identities scoped by the candidate `specification.specification_hash`, never `specification.source_identity`):
    - `candidate:supplied-frame:{specification_hash}:{frame_id}` → `ACCEPTED_PHYSICAL_FACT`, `source_value = frame.frame_hash`
    - `candidate:supplied-interface:{specification_hash}:{interface_id}` → `ACCEPTED_PHYSICAL_FACT`, `source_value = interface.interface_hash`
    - `candidate:geometry-derivation:{specification_hash}:{transform_id}` → `CANONICAL_REDERIVATION_INPUT`, `source_value = transform.transform_hash`
   - Evidence/accepted selections: **no** separate identity (nested inside classified interface hash).
3. `_classifications_by_identity`: unchanged logic covers the new identities (existing `source_value` StrictStr path handles the hashes). `PROVENANCE_ONLY`/`DO_NOT_PROMOTE` rejected for these identities via the existing `expected_value.has_source_value` checks plus a new explicit guard.
4. `_canonical_specification`: copy all three tuples field-for-field into `CanonicalComponentSpecification`, revalidating with `specification_hash="pending"`. The existing frame classification covers a derived active frame as `ACCEPTED_PHYSICAL_FACT` by `frame_hash`; its source-frame snapshot and derivation fields remain nested in materialized-interface provenance, while the transform remains `CANONICAL_REDERIVATION_INPUT` by `transform_hash`. Partial projection (e.g. derived frame copied but its interface/provenance dropped) fails because `@2` canonical validation re-checks frame resolution and materialization provenance.
5. `_verify_geometry_sources`: additionally byte-verify every `source_geometry`/`derived_geometry` artifact of accepted transforms at promotion readiness.

`CandidatePromotionPolicy.schema_version` and all other policy fields remain unchanged. The constrained `mapping_schema_version` default remains `candidate-canonical-mapping@1`, so legacy policy serialization/hash behavior is unchanged; any request carrying an `@2` component specification selects `@2` and is rejected if it claims `@1`. An `@1`-only request claiming `@2` is rejected to preserve the truthful mapping shape. After artifact verification, promotion readiness invokes `MaterializedInterfaceVerifier.verify` for every active materialized interface with its resolved accepted transform; pure model construction still performs no artifact I/O.

**Fail-closed cases tested:** missing classification for one frame; unknown classification; substituted `frame_hash`/`interface_hash`/`transform_hash` in `source_value`; transform with `PROPOSED` status whose materialized interface is in the candidate → promotion rejected; partial projection rejected; `@1`-only candidate with mapping `@1` passes; `@1`-only candidate with mapping `@2` rejects; any single `@2` specification with mapping `@2` passes; any `@2` specification with mapping `@1` rejects even when its M13 tuples are empty; mixed `@1`/`@2` specifications with mapping `@2` pass. Add two valid `@2` specifications with the same `source_identity`, the same `frame_id`, and distinct specification hashes: assert `_expected_classifications` yields two distinct classification identities and a policy containing both promotes successfully. This locks collision-free scope to semantic specification identity.

**Exit criteria:** full candidate→canonical round trip preserves every frame/interface/transform byte-semantically; M12 promotion suites (`test_m12_promotion_*`) green.

---

### Task 11 — Fresh canonical reconstruction and exports (slices 9–10)

**Purpose:** Fresh reconstruction verifies all named artifacts and replays materialization without candidate objects; public exports added.

**Files:**
- Modify: `src/mechcad_harness/candidates/canonical_mechanism.py` (`CanonicalPhysicalMechanismCompiler._verify_sources` ~line 260 and `_validate_mechanism` ~line 219)
- Modify: `src/mechcad_harness/models/__init__.py` and `src/mechcad_harness/candidates/__init__.py` (exports only)
- Test: `tests/unit/test_m13_interface_promotion_roundtrip.py` (append fresh-reconstruction cases)

**Behavior:**
- `_verify_sources` extends the existing per-`geometry_source` verification loop: also verify, through the same `ProjectArtifactResolver.read_verified_in_project`, every artifact in accepted `geometry_derivation_transforms` (`source_geometry`, `derived_geometry`) referenced by this mechanism's specifications, and every `source_geometry`/`derived_geometry` of materialized-interface provenance; resolve the active derived frame by the materialized interface's frame ID from that same specification and pass it explicitly to `MaterializedInterfaceVerifier.verify`. Failure raises `ValueError` with a clear integrity message (existing reconstruction convention); no verifier registry lookup is allowed.
- `_validate_mechanism` gains no new semantics beyond revalidation (the `@2` canonical model self-validates frame resolution/provenance).
- Exports: add `GeometryArtifactIdentity`, `SuppliedInterfaceEvidence`, `SuppliedInterfaceFact`, `SuppliedInterfaceTransformRole`, `SuppliedComponentReferenceFrame`, `RotationalShaftInterface`, `MountingFaceInterface`, `MountingHole`, `GeometryDerivationAuthorityRole`, `GeometryDerivationAuthorityFact`, `GeometryDerivationUnitConversion`, `GeometryDerivationTransform`, `InterfaceFactDerivationBinding`, `InterfaceDerivationProvenance`, `SuppliedComponentInterfaceDefinition`, `MaterializedInterfaceResult`, `MaterializedInterfaceVerifier`, `MaterializationIntegrityError` to the appropriate `__init__` files. No other API redesign.

**Fresh reconstruction test:** build a promoted state containing source-frame provenance, one active derived frame, shaft + mounting face + accepted transform + materialized interface; construct a brand-new `CanonicalPhysicalMechanismCompiler`; `reconstruct(...)` succeeds; tamper source frame/origin/orientation evidence or active derived frame hash → reconstruction raises; tamper one persisted STEP byte → reconstruction raises; change a derived diameter in persisted state with stale hash → replay raises.

**Exit criteria:** fresh application reconstructs identical interface semantics/hashes from `DesignState` + ArtifactStore alone (spec §Acceptance Criteria); exports complete.

---

## Updated Task Graph

1. **Task 1** must land first: it relocates the authority enums beneath both candidate and canonical models and provides the geometry projection helpers. No later shared model may import `candidates.models`.
2. **Task 2** depends only on Task 1's lower-level model package and supplies the one M13 quaternion API.
3. **Task 3** depends on Task 1's projections and introduces reference serializers/self-hashes, locked by literal pre-change candidate and canonical goldens before any specification change.
4. **Task 4** depends on Tasks 1–2; it imports the lower-level authority enums and owns exact fact/unit/role validation.
5. **Task 5** depends on Task 4 for fact validation and Task 1 for geometry identity.
6. **Task 6** depends on Tasks 1–2 and Task 4; it is the only role-aware fact transformation implementation.
7. **Task 7** depends on Tasks 5–6; its non-circular `derive -> provenance -> construct` sequence is the only materialization construction/replay path.
8. **Task 8** depends on Tasks 3–7; it adds the explicit `@1` nested hash/serialization projection and `@2` specification integration, including pure replay.
9. **Task 9** depends on Task 8 and adds ArtifactStore-backed candidate publication replay only.
10. **Task 10** depends on Tasks 8–9 and scopes classification identities by candidate specification hash; promotion readiness repeats artifact-aware replay.
11. **Task 11** depends on Task 10 and completes fresh canonical reconstruction plus minimal exports.

Task 9's exact trigger is `spec.schema_version == "component-specification@2" and (bool(spec.supplied_reference_frames) or bool(spec.supplied_interface_definitions) or bool(spec.geometry_derivation_transforms))`. The trigger is independent of whether an active interface exists; the accepted-transform-only artifact rule is then applied inside the pass. Empty `@2` remains on the existing selected-geometry path.

## Test Fixture Clarification

The Task 6 scale `1.25` is only a similarity/normalization example. It must not be labeled as inches converted to millimetres. Use `source_unit="source-model-unit"`, `derived_unit="derived-model-unit"`, and declaration `explicit-model-unit-normalization@1`; these are semantic labels recording an explicit declared model-unit relationship, not a general conversion engine. The transform tests exercise scale and declaration identity without claiming a physical inch-to-millimetre conversion.

## Verification Strategy (staged)

- **Stage A (after Tasks 1–4):** `py -3 -m pytest tests/unit/test_m13_authority_enum_compatibility.py tests/unit/test_m13_geometry_identity.py tests/unit/test_m13_legacy_hash_compatibility.py tests/unit/test_m13_quaternion.py tests/unit/test_m13_supplied_component_interfaces.py -q`
- **Stage B (after Tasks 5–7):** `py -3 -m pytest tests/unit/test_m13_geometry_materialization.py tests/unit/test_m13_supplied_component_interfaces.py tests/unit/test_m13_legacy_hash_compatibility.py -q`
- **Stage C (after Tasks 8–11):** `py -3 -m pytest tests/unit/test_m13_interface_promotion_roundtrip.py tests/unit/test_m13_publication_replay.py -q`
- **Stage D (M12 regressions, after every stage):** `py -3 -m pytest tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_candidate_cad_models.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_revolute_drive_models.py tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m12_canonical_physical_mechanism.py tests/unit/test_m12_canonical_reconstruction.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py -q`
- **Stage E (final):** `py -3 -m pytest tests/` with a tool ceiling of **4000 s** (accepted M12-6 full suite: 3411 s; 25 accepted skips are unrelated optional-backend tests).
- **Always:** `py -3 -m compileall -q src/mechcad_harness tests`; `git diff --check`; explicit trailing-whitespace + final-newline scan of every touched file (`rg -n "[ \t]+$" <files>` — expect zero matches).

## No Scope Expansion (explicit exclusions)

No M13-2 generated part CAD (shafts/hubs/bearings/brackets/frames), no assembly mating solver, no M13-3 multi-joint bridge, no M10 changes (`kinematic_sweep.py` quaternion math is extracted-by-copy into the new helper, not refactored), no timing belts, no component catalog, no automatic geometry/shaft recognition, no Pint/unit subsystem, no tolerance/GD&T, no M11 work, no Rotator V2 design or consumption of `projects/rotator_v2` as test authority.

## Plan Self-Review Result

- Dependency layering: `models.component_property` owns the original enum classes; `candidates.models` and `physical_mechanism.py` retain their public import names as bindings to those classes. `supplied_component_interface.py` cannot import `candidates.models`, so the reported cycle is eliminated.
- Legacy candidate closure: `component-specification@1` explicitly replaces its nested candidate geometry source with the original four-field payload; neither in-memory `reference_hash` nor `coordinate_system_id` can enter the legacy hash. The canonical counterpart preserves its original five-field nested shape. Literal complete candidate and canonical payload/hash goldens are embedded in Task 3, with a STOP rule for either hash.
- Serialization versus identity: ordinary StateManager and publication persistence uses `model_dump(mode="json")`; therefore reference/specification `@model_serializer` branches are required. Tests assert both dict and JSON-string historical forms. No assertion falsely relies on Pydantic default omission of `None`.
- Geometry identity: `GeometryArtifactIdentity` has an explicit five-field semantic payload and excludes only `geometry_identity_hash` from that payload. It has no legacy serializer and never accesses `reference_hash`; ordinary serialization includes its self-hash and the non-`None` coordinate-system round-trip/tamper test locks this boundary. Its projection classmethods remain real attribute projections from reference models.
- Quaternion correctness: raw Hamilton product is isolated; orientation composition normalizes/canonicalizes; vector rotation uses raw pure-vector intermediates. The corrected double-90° Z test expects 180° Z and `(+X -> -X)`.
- Evidence/role contract: quaternion facts use unit `"1"`; text alone uses `None`; all six transform roles have exact shape/unit pairs, enforced twice (fact validator and transform core).
- Structural validity versus authority: unselected, missing, and inferred-only facts/interfaces remain valid immutable snapshots; available dimensions/directions are still strictly validated. Authoritative consumption is an explicit helper gate. Direct definitions cannot select `DERIVED_MATERIALIZATION`; materialized definitions require complete provenance. Plane/frame normal checks defer until both values are selected.
- Derivation provenance: transform identity includes source/derived geometry, similarity data, explicit unit-conversion declaration, and ordered scale evidence carrying the existing source/authority/origin/basis fields. Proposed, unselected, and inferred-only transforms persist but fail `require_authoritative_transform`; only accepted source-document/human-confirmed evidence can materialize.
- Materialization construction: no cyclic API remains. `derive_reference_frame_semantics` / `derive_interface_semantics` have no provenance, `build_derivation_provenance` has no materialized result, and `construct_materialized_result` joins them. Verifier replay uses the same pure derivation core and compares interface/frame semantics and hashes.
- Frame materialization: a source frame snapshot/hash is durable provenance only; a materialized interface referencing a frame requires one active derived frame bound to derived geometry. Shared source-frame results deduplicate by equal `frame_id`/hash and conflicts fail closed; verifier callers pass the already-resolved typed active frame rather than allowing registry lookup.
- Full transform authority: translation, rotation, and uniform scale each have selected evidence-bound transform-authority facts; effective values are derived from them with no cached/default authority. Scale-only evidence cannot authorize translation/rotation, including identity values, and all component evidence/selection changes enter `transform_hash`.
- Promotion scope: new classification identities use candidate `specification_hash`, not non-unique `source_identity`; mapping selection is driven by whether any component specification is schema `@2`, even with empty M13 tuples. Explicit same-source/different-specification and @1/@2/mixed mapping tests lock both rules.
- Interface IDs: the structural raw-backend selector heuristic is not reused. `face_reference_id` is nonblank semantic text; typed frame/fact authority validates the interface and no regex rejects legitimate source-document IDs.
- Artifact boundaries: Pydantic validators perform only pure semantics/hash replay. Candidate resolution, promotion readiness, and canonical reconstruction perform byte verification and then reuse the pure verifier.
- Scope: no new dependency, CAD, M10/M11, Rotator V2, M13-2/M13-3/M13-4, catalog, recognition, unit-system, tolerance, or assembly work is planned.
- No architectural choice is left to the implementation worker; every reported reconciliation defect maps to Tasks 1, 3, 4, 5, 7, 8, or 10 and the staged checks above.
