# M13-2 Generic Generated Mechanical-Part CAD Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn authority-bound `GeneratedPartSpecification` records (solid circular
shaft, cylindrical hub/sleeve coupling, rectangular frame member) into deterministic
generated CAD through the existing `CadPartProgram` -> FreeCAD -> `ArtifactStore`
pipeline, with typed derived interfaces, M13-1 consumption, semantic placement
derivations, promotion projection, and fresh canonical reconstruction.

**Architecture:** Extend the existing stack only. No new dependency, no second CAD
AST, no second backend, no build123d in the generated path, no M10 algorithm
change. Two new `CadPartProgram` operation types, one new semantic model pair
(`models/generated_part.py`, `models/generated_placement.py`), one pure compiler
(`generated_part_cad.py`), and bounded extensions to the existing candidate CAD,
promotion, and canonical CAD modules.

**Tech Stack:** Python 3.11+, Pydantic v2 (frozen, `extra="forbid"`), existing
canonical-JSON SHA-256 hashing, FreeCAD 1.1.3 subprocess backend, existing
`ArtifactStore`.

**Authoritative specification:**
`docs/superpowers/specs/2026-09-02-m13-2-generic-generated-mechanical-part-cad-foundation.md`
(marker `M13_2_GENERIC_GENERATED_MECHANICAL_PART_CAD_FOUNDATION_ARCHITECTURE_APPROVED`).
This plan adapts file placement to current repository structure only; it does not
change any approved contract. It is reconciled with the specification's
pre-implementation findings P1-P4 (scalar-angle rotation authority with typed
frame axis; geometry-definition identities = input-hash union binding-hash
helper; identity orientation as part of the named design-variable placement
contract; frozen frame-face convention).

## Global Constraints

- Python 3.11+, Pydantic v2, UTC-aware datetimes; all models frozen, `extra="forbid"`.
- Reject empty required strings and non-positive revisions (house style).
- Every self-hash: canonical JSON (`model_dump(mode="json")`, `sort_keys=True`,
  tight separators, `ensure_ascii=False`) -> `sha256:<64hex>`, excluding only the
  hash field itself (same pattern as `candidates/models._hash` and
  `models/physical_mechanism._canonical_hash`).
- `GeneratedAuthorityInput.value` is a finite scalar float only. Never `Any`,
  tuple, frame, quaternion, or geometry. Structured references are typed fields.
- **Drafting cleanup (explicit, does not reopen the architecture):** the
  closed numeric role enum contains only scalar roles: `dimension`,
  `selected_diameter`, `supplied_diameter`, `clearance`, `axial_offset`,
  `clocking_angle`. Frames and rotation axes are typed references
  (`source_frame_ref`, `target_generated_frame_ref`,
  `GeneratedPlacementRotationInput.axis_ref`).
- No `run_id`, artifact path, temp path, CAD instance ID, candidate/canonical
  instance ID, or FreeCAD object name may enter `GeneratedPartSpecification`
  identity.
- M10 (`candidates/m10_evaluation.py`, `candidates/canonical_m10.py`), M11,
  M13-3/M13-4, Rotator V2, imported multi-shape STEP semantics, and the legacy
  plate path (`MountingPlateDesignSpec` / `compile_mounting_plate`) are untouched
  except where explicitly listed below.
- **STOP rule:** if any approved pre-M13-2 golden (Task 0) changes after a
  production edit, stop and repair the versioned serialization/hash projection
  before continuing. Goldens are never regenerated.
- No commits unless the user explicitly requests them (house rule).

---

## Repository Reality Check (verified against current source)

Key anchors used throughout this plan (verified this session):

| Contract | Anchor |
|---|---|
| `CadPartProgram`, 4-plate-op union, one-first-base validation, plate coordinate literal | `cad_program.py:33-148` (`BasePlateOperation:33`, union `:90`, `validate_operations:105-134`, `cad_program_hash:146-148`) |
| `cad_manifest.py:14` `operation_kind` Literal | extends with `cylindrical_stock`, `axial_bore` |
| `CadAssemblyProgram` dual registries; multiple instances per `part_id` allowed; "unused component definitions are not allowed" | `cad_assembly.py:47-78` |
| `CadRigidTransform` quaternion normalization (norm, canonical sign) | `cad_assembly.py:16-38` |
| FreeCAD backend `compile_program`, `generate_program`, `_verify_persisted` (plate-specific bbox/probes) | `backends/freecad.py:195-235, 271-296, 298-363` |
| Assembly compile loads generated part via `source_objects[0].Shape` | `backends/freecad_assembly.py:231-241` |
| `ComponentSpecificationSnapshot` schema `@1|@2`, schema-aware serializer, M13 exactly-once interface check | `candidates/models.py:239-386` (`:240`, `:254-297`, `:353-354`) |
| `CanonicalComponentSpecification` mirror | `models/physical_mechanism.py:255-416` |
| `CanonicalPhysicalMechanism` schema `canonical-physical-mechanism@1`, hash via `_canonical_hash` over full `model_dump` | `models/physical_mechanism.py:699-805`, `_canonical_hash:31-37` |
| Fidelity enums, two members each | `candidates/cad_realization.py:499-501`, `models/physical_mechanism.py:119-123` |
| Generated routing `_compile_generated` (plate types, `part_id=mapping.cad_instance_id`) | `candidates/cad_realization.py:405-426` (`:417`) |
| Fidelity gate `mapping.fidelity is not DECLARED_BOUNDED` | `cad_realization.py:170-171` |
| Placement provenance `_placement_error` (xyz design variables only), `_validate_placement_provenance` allowed-identity set | `cad_realization.py:470-492`, `:316-369` |
| `CandidateCadRealizationRequest@1` / `CandidateCadRealization@1`, hash over full payload | `cad_realization.py:567-613`, `:616-717` |
| Geometry-input foreign check `allowed_geometry_inputs` | `candidates/evaluation.py:346-357` |
| `CandidateEvaluation` embeds `cad_request: CandidateCadRealizationRequest \| None` | `candidates/evaluation.py:578-586` |
| `CandidateM10Binding.cad_realization_hash` verified against realization; fidelity exact-enum check | `candidates/m10_evaluation.py:216, 286-295, 549-556` |
| Canonical M10 identical pattern | `candidates/canonical_m10.py:884-891` |
| Promotion `_verify_policy` (@2 trigger), `_expected_classifications`, `_canonical_specification`, `_canonical_choice`, `_canonical_placements`, `map_instances`/`canonical_by_candidate` | `candidates/promotion.py:947-970, 1112-1184, 446-489, 491-511, 513-545, 274-308` |
| `PromotionValueClassification`, `CandidatePromotionPolicy.mapping_schema_version` Literal | `candidates/promotion_models.py:101-115, 152-198` |
| `CandidatePromotionRequest` (no CAD payload; carries `evaluation`) | `promotion_models.py:413-547` |
| `PromotableMechanismProjection` (projection_hash over full payload) | `promotion_models.py:550-579`; built at `promotion.py:362-377` and `canonical_mechanism.py:409-427` |
| Canonical CAD compiler `CanonicalPhysicalCadCompiler.realize` (generated `part_id=cad_instance_id`; instances `part_id=mapping.cad_instance_id`) | `candidates/canonical_cad.py:336-508` (`:471-478`), `_compile_generated:570-629` |
| Reconstruction `CanonicalPhysicalMechanismCompiler.reconstruct`, projection hash check | `candidates/canonical_mechanism.py:188-263, 159-163` |
| M13-1 shared models + gates `require_authoritatively_consumable_interface` / `require_authoritative_fact`; `RotationalShaftInterface`; `SuppliedComponentReferenceFrame` | `models/supplied_component_interface.py:492-537, 683-903, 1225-1264` |
| Canonical quaternion helpers (`normalize_quaternion`, `quaternion_compose`, `rotate_vector`, `normalize_direction`) | `models/quaternion.py` |
| Shared hashing entry `canonical_json` | `state/hashing.py:13-19` |
| Golden-hash regression precedent (literal captured constants) | `tests/unit/test_m13_legacy_hash_compatibility.py:23-72` |
| Existing test families to keep green | `tests/unit/test_m12_*`, `tests/unit/test_m13_*`, `tests/unit/test_cad_*`, `tests/unit/test_freecad_*`, `tests/integration/test_m12_6_*`, `tests/integration/test_transient_imported_multishape_collision.py` |

Current worktree note: pre-existing unrelated dirty/untracked files exist
(`.coverage`, `.superpowers/*`, `projects/`, `err.txt`, `src/mechcad-harness/`,
M13-1 docs). They are not touched by this plan.

---

## Compatibility Golden Strategy (Task 0 — mandatory first)

Captured from the **unmodified** tree, as literal constants, following the M13-1
precedent (`test_m13_legacy_hash_compatibility.py:23-24`). Goldens live in
`tests/unit/test_m13_2_legacy_goldens.py` and are never regenerated.

Captured set:

1. Plate `CadPartProgram` JSON + `cad_program_hash` (representative program with
   base + hole + pocket + slot).
2. `ComponentSpecificationSnapshot` `@1` and `@2` JSON + `specification_hash`
   (the `@2` fixture carries M13 frames/definitions/transforms).
3. `CanonicalComponentSpecification` `@1` and `@2` JSON + `specification_hash`.
4. `CandidateCadRealizationRequest@1` JSON + `request_hash` (representative
   mapping with placement origin, built per `tests/unit/test_m12_candidate_cad_models.py`
   conventions).
5. Representative `CandidateCadRealization@1` `realization_hash` and
   `MechanicalDesignCandidate@1` `candidate_hash`.
6. `candidate-canonical-mapping@1`/`@2` **selection behavior** (all-`@1` specs ->
   `@1`; any-`@2` spec -> `@2`) — behavioral assertion, not a hash.
7. Representative `CandidatePlacementOrigin` JSON + `origin_hash`.
8. Fidelity enum serialized values (`trusted_source_geometry`,
   `declared_bounded_collision_representation`).
9. Small `CanonicalPhysicalMechanism@1` JSON + `mechanism_hash` (one
   design-variable placement, one connection).

Capture procedure (run once on the unmodified tree, then paste literals):

- Build the exact fixtures from Task 0 fixture code (given below) in a
  temporary capture script under
  `C:\Users\vvooj\AppData\Local\Temp\opencode\m13_2_capture_goldens.py`
  (outside the repo) that prints each literal constant.
- Paste the printed values into the golden module header constants, run
  `py -3 -m pytest tests/unit/test_m13_2_legacy_goldens.py -q` to green.
- From then on the constants are immutable.

STOP rule enforcement: `tests/unit/test_m13_2_legacy_goldens.py` is included in
every subsequent task's regression command. Any failure = serialization/hash
projection bug; fix the projection, never the golden.

---

## Dependency Layering (closed, no cycles)

```text
state/hashing.py            (canonical_json)            [leaf]
models/common.py            (Model)                     [leaf]
models/quaternion.py        (quaternion math)           [leaf]
cad_program.py              (SAFE_ID, CadPartProgram)   [imports models.common only]
cad_assembly.py             (CadRigidTransform)         [imports cad_program, imported_component]
models/supplied_component_interface.py                  [shared leaf family]

NEW models/generated_part.py      imports: models.common, models.quaternion,
                                  state.hashing.canonical_json, cad_program.SAFE_ID,
                                  models.supplied_component_interface (M13-1 gates for the
                                  shared resolver).  NEVER imports candidates.*.
NEW models/generated_placement.py imports: models.common, models.quaternion,
                                  state.hashing.canonical_json, cad_assembly.CadRigidTransform,
                                  models.generated_part.  NEVER imports candidates.* and
                                  NEVER imports models.physical_mechanism.
NEW candidates/generated_authority.py  imports: candidates.models, models.generated_part,
                                  models.physical_mechanism (canonical view builder),
                                  models.supplied_component_interface.  [top layer]
NEW generated_part_cad.py         imports: cad_program, models.generated_part,
                                  models.generated_placement.  NEVER imports candidates.*
                                  (the resolution view object is passed in; its dataclass
                                  lives in models/generated_part.py).
cad_compilation.py            untouched (legacy plate compiler)
candidates/cad_realization.py imports generated_part_cad + models.generated_placement
candidates/promotion.py       imports models.generated_placement + candidates.generated_authority
candidates/canonical_cad.py   imports generated_part_cad + candidates.generated_authority
models/physical_mechanism.py  imports models.generated_placement (collection type); one-way.
```

Layering consequence: `GeneratedAuthorityView` (the plain container consumed by
the shared resolver) is defined in `models/generated_part.py`;
`candidates/generated_authority.py` builds it from candidate records and from
canonical mechanism records (two adapters, one rule set). The compiler accepts a
`GeneratedAuthorityView`; it never imports `candidates.*`.

---

## Placement Input Ownership (resolved rule — no ambiguity left to the worker)

For **part-level** `GeneratedAuthorityInput` resolution, the owning instance
context is the physical instance using the generated component specification
(candidate instance ID candidate-side; canonical instance ID canonical-side).

For **placement derivations** (both `source_physical_instance_id` and
`target_physical_instance_id` are present), the bounded rule adopted is:
**the placement rule itself fixes the owner — the TARGET physical instance owns
every placement numeric/rotation `DESIGN_SELECTION` input.** Enforcement:

- `INSTANCE_SCOPED` selection keys inside placement derivations resolve against
  the target instance's owning context only, through the shared resolver's
  explicit `owning_instance_context` parameter (the placement-input resolver is
  always invoked with the target instance ID). The owner is never persisted —
  consistent with the spec ("the owning-instance context is supplied by the
  verifier at resolution time; it is never persisted").
- `COMPONENT_SCOPED` selection keys remain available for mechanism-wide
  selections. Two derivations needing different offsets for two instances use
  `INSTANCE_SCOPED` target-owned keys (e.g. `{target_a}.placement.axial_offset_mm`),
  which is exactly the promotion-remappable alias family.
- Validation enforces this in the shared resolver signature (single call path);
  nothing is left to caller convention. Unequal per-instance resolutions fail
  closed as in the part-level rule.
- Source-side placement semantics come exclusively from `source_placement_ref`
  (existing placement records), never from a selection lookup on the source.

This is a verifier-convention decision under the approved architecture
("INSTANCE_SCOPED ... receives its owning-instance context from the verifier");
it adds no persisted field and no schema change. If implementation discovers a
concrete case requiring a SOURCE-owned selection, stop and return
`M13_2_IMPLEMENTATION_PLAN_NEEDS_SPEC_CLARIFICATION` rather than widening.

## Numeric vs Rotation Placement Inputs (exact)

- Numeric placement inputs: `GeneratedAuthorityInput` records only, roles limited
  to `axial_offset` inside derivations (the `clocking_angle` role exists in the
  closed enum but is admitted by no initial rule; plus the rule-admitted
  roles at part level). Frames/quaternions are never scalar inputs.
- Rotation/reference inputs: typed `source_interface_ref`, `source_frame_ref`,
  `target_generated_interface_ref`, `target_generated_frame_ref` fields, plus
  `GeneratedPlacementRotationInput` (Rotation Authority Resolution — scalar
  angle authority, Option A):
  - `rotation_id` (SAFE_ID), `axis_ref`
    (`{frame_role: Literal["source", "target"],
    axis: Literal["+x", "+y", "+z", "-x", "-y", "-z"]}` — resolves against the
    derivation's already-bound `source_frame_ref` / `target_generated_frame_ref`;
    the frame's `frame_hash` is the axis authority; **no caller-supplied axis
    vector exists**), `angle_degrees` (the authoritative scalar, resolved from
    an existing scalar `DESIGN_SELECTION` record),
    `provenance` (the same layer-independent `DESIGN_SELECTION` locator
    semantics: `name_form` + `selection_key` + `selection_hash`), `value_hash`
    (canonical JSON of the angle value), `input_hash`.
  - Resolution (both layers): resolve per the shared `DESIGN_SELECTION` rules;
    require numeric (not `bool`), finite, **exactly equal** to the persisted
    `angle_degrees`, and `value_hash` match. Promotion survival is the same
    dual-side verification as every other `DESIGN_SELECTION` input; any
    failure is UNRESOLVED, never silent.
  - The rotation quaternion is **never persisted as authority**: the shared
    pure composition reconstructs it as a rotation about the referenced
    frame's local axis by the resolved angle via
    `models.quaternion.normalize_quaternion` (canonical sign) — no duplicated
    normalization logic. No M13-2 record accepts a free quaternion or
    multi-component tuple; free quaternion authority is explicitly deferred.
    Orientation beyond one authority-bound single-axis rotation is expressed
    only by acyclic chained derivations.
- `frame-generated-placement@1` requires exactly one explicit
  `GeneratedPlacementRotationInput` (absence fails validation; no hidden identity
  rotation). `axisymmetric-zero-clocking@1` must NOT carry a rotation input and is
  applicability-checked (target part kind must be `solid_circular_shaft` or
  `cylindrical_hub`; any other kind fails INVALID PLACEMENT PROVENANCE).

---

## Placement Derivation Plan (`src/mechcad_harness/models/generated_placement.py`)

### Types

```python
PLACEMENT_RULES = ("coaxial-generated-placement@1", "frame-generated-placement@1")

class GeneratedInterfaceRef(Model):        # typed reference (interface)
    interface_id: str = Field(min_length=1)
    interface_hash: str                    # sha256-shaped

class GeneratedFrameRef(Model):            # typed reference (frame)
    frame_id: str = Field(min_length=1)
    frame_hash: str

class SourcePlacementRef(Model):           # discriminator "kind"
    # {"kind": "design_variable_placement"}
    # {"kind": "derivation", "derivation_id": str}   # acyclic chaining only

class GeneratedFrameAxisRef(Model):        # typed frame-axis reference (P1)
    frame_role: Literal["source", "target"]
    axis: Literal["+x", "+y", "+z", "-x", "-y", "-z"]

class GeneratedPlacementRotationInput(Model):   # scalar-angle authority (P1)
    rotation_id: str                       # SAFE_ID
    axis_ref: GeneratedFrameAxisRef        # resolves against the derivation's
                                           # source/target frame ref (frame_hash
                                           # is the axis authority)
    angle_degrees: float                   # authoritative scalar, resolved from
                                           # an existing scalar DESIGN_SELECTION
                                           # record (exact value + hash equality)
    provenance: DesignSelectionLocator     # same locator semantics as GeneratedAuthorityInput
    value_hash: str                        # sha256 over canonical JSON of the angle
    input_hash: str = "pending"            # self-hash

class GeneratedPlacementDerivation(Model):      # candidate semantic form
    derivation_id: str                     # SAFE_ID, unique within the derivation set
    rule_id: Literal["coaxial-generated-placement@1", "frame-generated-placement@1"]
    source_physical_instance_id: str       # candidate instance id (candidate form)
    source_interface_ref: GeneratedInterfaceRef        # resolved in SOURCE spec
    source_frame_ref: GeneratedFrameRef | None = None  # frame-based rules
    source_placement_ref: SourcePlacementRef
    target_physical_instance_id: str       # candidate instance id of the generated part
    target_generated_interface_ref: GeneratedInterfaceRef | None = None
    target_generated_frame_ref: GeneratedFrameRef | None = None
    inputs: tuple[GeneratedAuthorityInput, ...] = ()   # NUMERIC only (axial_offset;
                                             # clocking_angle admitted by no initial rule)
    rotation: GeneratedPlacementRotationInput | None = None
    derivation_hash: str = "pending"       # self-hash
```

Validation: rule consistency (coaxial requires `target_generated_interface_ref`
and forbids `rotation` and `source_frame_ref`/`target_generated_frame_ref`;
frame rule requires `source_frame_ref`, `target_generated_frame_ref`, and
exactly one `rotation`); numeric inputs only (role `axial_offset`; the
`clocking_angle` role is admitted by no initial rule, so no derivation carries
it); `derivation_id` uniqueness is enforced at set level; `derivation_hash`
self-consistent.

```python
class CanonicalGeneratedPlacementDerivation(Model):   # shared model, canonical ID form
    derivation_id: str                     # same id as the candidate derivation
    rule_id: Literal[...same registry...]
    source_canonical_instance_id: str
    source_interface_id: str
    source_interface_hash: str
    source_frame_id: str | None = None
    source_frame_hash: str | None = None
    source_placement_ref: SourcePlacementRef           # canonical placement identity
    target_canonical_instance_id: str
    target_generated_interface_id: str | None = None
    target_generated_interface_hash: str | None = None
    target_generated_frame_id: str | None = None
    target_generated_frame_hash: str | None = None
    inputs: tuple[GeneratedAuthorityInput, ...]        # byte-identical, layer-independent
    rotation: GeneratedPlacementRotationInput | None = None
    derivation_hash: str = "pending"       # self-hash (payload with canonical IDs)

def placement_derivations_hash(derivations) -> str:
    # sha256 over canonical JSON of {"derivations": [d.model_dump(mode="json")
    #                                for d in sorted(derivations, key=lambda x: x.derivation_id)]}
```

Note (file placement, approved adaptation): `CanonicalGeneratedPlacementDerivation`
lives in `models/generated_placement.py` (not `models/physical_mechanism.py`) so
the pure projection function below can live beside it without a
`generated_placement -> physical_mechanism` import. `models/physical_mechanism.py`
imports the class one-way.

### Pure composition (single shared implementation, candidate AND canonical)

```python
def pose_from_interface(interface) -> CadRigidTransform
    # rotational interface -> pose with axis_direction mapped to +Z, at axis_point
    # attachment face / frame -> pose from plane_point/origin + orientation

def _rotation_aligning(from_dir, to_dir) -> tuple[float, float, float, float]
    # deterministic shortest-arc quaternion mapping from_dir -> to_dir;
    # 180-degree case uses axis = normalize(cross(from, (1,0,0))) if non-degenerate
    # else normalize(cross(from, (0,1,0))); result via normalize_quaternion

def compose_poses(outer: CadRigidTransform, inner: CadRigidTransform) -> CadRigidTransform
    # position: R_outer * p_inner + t_outer ; rotation: quaternion_compose(q_outer, q_inner)

def invert_pose(pose) -> CadRigidTransform

def place_generated_target(rule_id, source_world_pose: CadRigidTransform,
                           target_local_pose: CadRigidTransform,
                           axial_offset: float | None,
                           explicit_rotation: tuple[float, float, float, float] | None
                           ) -> CadRigidTransform:
    # explicit_rotation is the RECONSTRUCTED quaternion of the derivation's
    # GeneratedPlacementRotationInput (rotation about the referenced frame's
    # local axis by the resolved authoritative angle, normalize_quaternion,
    # canonical sign) — never a persisted authority value and never caller-
    # supplied. The derivation model guarantees: coaxial rule -> rotation
    # input absent (explicit_rotation is None); frame rule -> exactly one
    # rotation input present (explicit_rotation is not None).
    # shared skeleton (closed form; no solver):
    #   P  = source_world_pose                     for frame-generated-placement@1
    #   P  = axis-aligned pose of the source interface (origin = world axis point,
    #        rotation = the source pose rotation composed with the local interface
    #        pose rotation)                        for coaxial-generated-placement@1
    #   T  = P o Translate(offset * z_hat) o Rotate(explicit_rotation) o invert(target_local_pose)
    # result quaternion canonicalized via normalize_quaternion
```

- The world source pose is composed exactly as approved:
  `world_source_pose = compose_poses(source_instance_semantic_placement, local_M13_1_interface_or_frame_pose)`.
  The local pose is extracted from the M13-1 record's accepted fact values
  (frame origin/orientation, or rotational axis point/direction) � extraction
  happens in the per-layer resolution adapters AFTER the M13-1 gates; the pure
  function receives already-extracted numeric poses only.
- No FreeCAD geometry queries; no STEP inference; identical inputs produce a
  bit-identical canonicalized quaternion on candidate and canonical replay.
- Source placement resolution:
  - candidate `design_variable_placement`: the source instance's authoritative
    xyz placement from design variables `{src}.placement.{axis}` (all three
    required, per the existing `_placement_error` convention,
    `cad_realization.py:470-492`). **Orientation contract (exact — no implicit
    orientation):** the accepted design-variable placement contract is
    translation-only, and its identity orientation is **part of the named
    contract** `accepted-design-variable-placement@1`, NOT a fallback for
    unspecified data. Verified: `_placement_error` (cad_realization.py:470-492)
    expects the mapping transform to equal exactly
    `CadRigidTransform(x_mm, y_mm, z_mm)` — it asserts the identity orientation
    unconditionally; `_canonical_placements` (promotion.py:513-545) constructs
    `CanonicalPlacement(..., relation="accepted-design-variable-placement@1")`
    with no orientation argument and `CanonicalPlacement` fixes
    `rotation_quaternion = (1, 0, 0, 0)` (physical_mechanism.py:489) — the
    projection itself establishes identity as part of the named relation.
    Replay must verify the full contract pose (translation AND orientation) by
    exact equality. A source instance needing non-identity orientation cannot
    be expressed through `design_variable_placement` (the contract is
    translation-only); it is placed via a chained derivation
    (`kind=derivation`) carrying an explicit
    `GeneratedPlacementRotationInput` — the supported mechanism in M13-2.
    There is no "unspecified orientation" state anywhere.
  - candidate `derivation`: the referenced derivation's recomputed transform
    from the same derivation set; acyclicity enforced by topological order over
    the set (deterministic: Kahn's algorithm with `derivation_id` tiebreak;
    cycle -> INVALID PLACEMENT PROVENANCE).
  - canonical `design_variable_placement`: the source instance's stored
    `CanonicalPlacement` with `origin=ACCEPTED_DESIGN_CHOICE` and
    `relation == "accepted-design-variable-placement@1"`.
  - canonical `derivation`: the placement produced by the referenced canonical
    derivation.

---

## Selection / Derivation-Set Binding (exact chain)

```text
sorted GeneratedPlacementDerivation set (derivation_id order)
  -> placement_derivations_hash
  -> CandidateCadRealizationRequest@2 (field placement_derivations + hash; request_hash covers both)
  -> CandidateCadRealization (echoed placement_derivations_hash; realization_hash covers it
     directly AND transitively via request_hash)
  -> CandidateM10EvaluationScope binding.cad_realization_hash (m10_evaluation.py:216,
     verified :291-295 against the realization)
  -> CandidateM10Evaluation (embeds cad_request; evaluation_hash covers it)
  -> CandidateSelection.evaluation_hash / evaluation_scope_hash (selection.py)
  -> promotion readiness (validate_readiness) re-proves:
       recomputed placement_derivations_hash(request.evaluation.cad_request.placement_derivations)
         == cad_request.placement_derivations_hash
         == realization echoed placement_derivations_hash
```

Promotion never accepts a derivation set that was not the evaluated/selected
one: a set B supplied where A was evaluated changes `cad_request.request_hash`
-> `realization_hash` -> `binding_hash` -> `evaluation_hash` -> selection
mismatch and fails closed (UNRESOLVED / INTEGRITY FAILURE). Legacy candidates
(request `@1`, no derivations) keep their existing hashes and pass unchanged.

`MechanicalDesignCandidate` hashes are NOT modified � the derivation set rides
the request/evaluation chain only.

---

## Candidate CAD Integration (exact)

- `CandidateCadRealizationService._compile_generated` (`cad_realization.py:405-426`)
  gains a routing branch BEFORE the component-type check: if
  `specification.generated_part is not None`, compile via
  `generated_part_cad.compile_generated_part(specification, view, owning_instance_context)`
  where `view = build_candidate_view(candidate, specification.specification_hash)`
  and `owning_instance_context = mapping.physical_instance_id`; require
  `mapping.fidelity is EXACT_GENERATED_GEOMETRY`; enforce
  `mapping.representation_identity == cad_program_hash(program)` as today;
  set `mapping.geometry_definition_identities :=
  generated_geometry_definition_identities(spec)` — the shared helper defined
  once (in `models/generated_part.py`) as the canonical sorted union of every
  `GeneratedAuthorityInput.input_hash` and every
  `GeneratedPartFieldBinding.binding_hash` (spec: Geometry Definition
  Identities contract). The **same helper** is used canonical-side. This
  truthfully identifies the geometry-definition dependency set: two specs
  with the same inputs but different binding graphs get different identity
  sets. The helper output contains only hash-shaped identities, so it
  contributes nothing to the candidate identity-string crosscheck at
  `cad_realization.py:294-314` (design-variable/interface identities
  continue to be declared through `placement_origin.input_identities`).
  The `_GENERATED_COMPONENT_TYPES` allowlist (`:72`) continues to gate the
  legacy plate path only; specs carrying `generated_part` are routed by the
  typed spec (role instances `SHAFT`, `HUB_OR_COUPLING`, `MOUNT_OR_SUPPORT`,
  `ROTATING_MEMBER` get real generated CAD).
- `evaluation.py:346-357` `allowed_geometry_inputs` gains, for specifications
  with `generated_part is not None`, exactly the shared helper's values
  (`{input.input_hash}` union `{binding.binding_hash}` of
  `specification.generated_part`) so the definition identities are not
  rejected as foreign. No other evaluation.py logic change.
- Definition reuse: `_realize_current` (`:124-213`) collects generated programs
  into `parts` keyed by `program.part_id` (dict dedup). Two physical instances
  sharing one specification produce ONE `CadPartProgram` in
  `assembly.parts` and TWO `CadComponentInstance`s with distinct
  `instance_id`s sharing `part_id = program.part_id` (allowed by
  `cad_assembly.py:53-78`). Legacy plate programs keep
  `part_id = cad_instance_id` (unchanged; one program per mapping).
- `CandidateCadRealization.validate_realization` (`:654-676`): the non-trusted
  branch already looks up `parts_by_id[instance.part_id]` and checks
  `representation_identity == cad_program_hash(part)` — works unchanged for
  shared generated definitions (two instances -> same part lookup).
- Placement from semantic derivations: `_realize_current` replaces the
  design-variable `_placement_error` check for mappings that are derivation
  targets. New helper `_derived_placement(request, mapping, specifications,
  candidate)`:
  1. find the derivation in `request.placement_derivations` whose
     `target_physical_instance_id == mapping.physical_instance_id`;
  2. resolve the source instance's authoritative placement (design variables
     `{src}.placement.{axis}` or another derivation's transform, acyclic);
  3. resolve source/target local poses (M13-1 gates + fact-value extraction
     candidate-side via `build_candidate_view`; target pose from the target
     spec's generated interface/frame records);
  4. resolve placement numeric/rotation inputs (`owning_instance_context` =
     TARGET instance);
  5. compute the transform via the shared pure `place_generated_target`;
  6. require exact equality with `mapping.placement` and
     `mapping.placement_origin.transform`.
  `CandidatePlacementOrigin` is constructed with
  `authority="deterministic_derived_relation"`,
  `derivation=rule_id`, `input_identities=("generated-placement:{derivation_id}",
  source_interface_hash, target_generated_interface_hash, *sorted input hashes,
  rotation input hash)` — evidence only, never semantic authority.
- `_validate_placement_provenance` (`:316-369`): the allowed-identity set gains,
  for derivation-target mappings, exactly the identities listed above (computed
  from `request.placement_derivations`). Non-derivation mappings keep the
  existing allowed set unchanged.
- `CandidateCadStageReason` reuse: unresolvable/unverifiable authority ->
  `GEOMETRY_UNAVAILABLE`; unsupported features -> `UNSUPPORTED_REPRESENTATION`
  (never silent substitution).

## Canonical Placement / Schema Plan

### Mechanism schema bump (exact version chosen)

`CanonicalPhysicalMechanism.schema_version` (`models/physical_mechanism.py:700`)
widens to `Literal["canonical-physical-mechanism@1", "canonical-physical-mechanism@2"]`
(next explicit version per repository convention; `@2` is unused today).
New field:

```python
generated_placement_derivations: tuple[CanonicalGeneratedPlacementDerivation, ...] = ()
```

Hash/serialization compatibility (exact mechanism): the current
`_canonical_hash(self, "mechanism_hash")` hashes the full `model_dump`; to keep
`@1` payloads byte-identical the mechanism gains a schema-aware payload:

```python
def _mechanism_payload_for_schema(self) -> dict:
    payload = self.model_dump(mode="json")
    if self.schema_version.endswith("@1"):
        payload.pop("generated_placement_derivations", None)
    return payload
```

The mechanism validator hashes `_mechanism_payload_for_schema()` minus
`mechanism_hash`. Validation: non-empty collection requires `@2`; `@1`
mechanisms must have the collection empty. Legacy promoted mechanisms reload
with unchanged hashes (golden-guarded).

`PromotableMechanismProjection` (`promotion_models.py:550-579`) gains
`generated_placement_derivations: tuple[...] = ()` with a `@model_serializer(mode="wrap")`
that omits the key when the tuple is empty (same omission pattern as
`candidate_geometry_reference_payload`) — legacy projection hashes unchanged.
`_projection` (`promotion.py:362-377`) and `_projection_from_mechanism`
(`canonical_mechanism.py:409-427`) populate it.

### Canonical placement result vs derivation input

`CanonicalPlacement` (`models/physical_mechanism.py:480-529`) remains the
persisted RESULT record. Fresh validation plan:

- canonical derivation -> resolve source canonical instance placement via
  `source_placement_ref` -> resolve canonical interface/frame records by
  shared-model hashes -> resolve numeric/rotation inputs against
  `CanonicalAcceptedDesignChoice`/canonical properties/canonical M13-1 records
  (canonical view adapter) -> recompute `CadRigidTransform` via the shared
  `place_generated_target` -> require exact equality with the stored
  `CanonicalPlacement` transform (mismatch = INTEGRITY FAILURE).
- `CanonicalPlacement` conventions for derivation targets:
  `placement_id = f"{canonical_instance_id}:placement"`,
  `origin = CanonicalPlacementOrigin.DETERMINISTIC_RELATION` (existing enum,
  `physical_mechanism.py:115`), `relation = rule_id`,
  `input_identities` = ordered layer-independent references (source interface
  hash, target generated interface hash, derivation input hashes, rotation
  hash) — provenance summary ONLY; structured resolution always goes through
  the `CanonicalGeneratedPlacementDerivation` record.

## Fresh Canonical Reconstruction

- `CanonicalPhysicalMechanismCompiler.reconstruct`
  (`canonical_mechanism.py:188-263`) gains, after `_validate_mechanism`:
  for every `@3` canonical specification, verify all authority inputs/bindings
  against `build_canonical_view(mechanism, ...)` and replay field relations and
  interface derivation (shared `generated_part_cad.verify_generated_part` with
  `owning_instance_context = component.instance_id`); for every canonical
  placement derivation, recompute the transform and compare exactly against the
  stored `CanonicalPlacement`. No candidate object, no candidate design
  variables, no candidate CAD, no previous FreeCAD document, no temp STEP, no
  parser state is consulted.
- Supplied M13-1 artifact/interface dependencies continue through the existing
  `_verify_sources` + `MaterializedInterfaceVerifier` path (`:265-383`),
  untouched.

---

## Promotion Plan (exact)

### Mapping schema (`_verify_policy`, promotion.py:947-970)

`has_v2_specification` becomes:

```python
has_v2_class_specification = any(
    specification.schema_version in ("component-specification@2", "component-specification@3")
    for specification in candidate.component_specifications
)
```

Expected mapping schema: any `@2` OR `@3` spec -> `candidate-canonical-mapping@2`;
all `@1` -> `@1`. No `@3` mapping is introduced (payload shape unchanged).
Regressions cover all three combinations.

### New classifications (`_expected_classifications`, promotion.py:1112-1184)

Added inside the per-specification loop and a new per-derivation loop:

```python
if specification.generated_part is not None:
    gp = specification.generated_part
    add_expected(
        f"candidate:generated-part:{specification.specification_hash}:{gp.generated_part_id}",
        _ExpectedClassification(True, gp.generated_part_hash,
                                PromotionValueClassification.ACCEPTED_PHYSICAL_FACT),
    )
# after the spec loop, from request.evaluation.cad_request.placement_derivations
for derivation in placement_derivations:
    add_expected(
        f"candidate:generated-placement:{derivation.derivation_id}",
        _ExpectedClassification(True, derivation.derivation_hash,
                                PromotionValueClassification.CANONICAL_REDERIVATION_INPUT),
    )
```

`PROVENANCE_ONLY`/`DO_NOT_PROMOTE` are rejected for both (existing
`_classifications_by_identity` checks at `:1201-1205`). Nested
`GeneratedAuthorityInput` records receive NO independent classification: their
candidate sources are already classified (`candidate:design-variable:{name}` at
`:1166-1168`, `candidate:property:{source_identity}:{key}` at `:1127-1134`,
`candidate:supplied-interface:{spec_hash}:{interface_id}` at `:1148-1156`);
layer-specific resolved identity strings are checked as provenance during
survival verification, never persisted in the spec.

### Input/binding survival (`_verify_generated_authority_survival`, new method)

Called from `_compile_mechanism` before mechanism construction:

- for every candidate spec with `generated_part`:
  candidate-side `verify_generated_part(spec, build_candidate_view(candidate,
  spec.specification_hash), owning_instance_id)` succeeds;
  canonical-side the projected `CanonicalComponentSpecification` (already built
  by `_canonical_specification` in this compile) verifies against
  `build_canonical_view(projected mechanism records, canonical_instance_id)`;
  every input and binding resolves on BOTH sides with identical values and
  hashes; field relations replay.
- No assumption of candidate `property_hash` == canonical `property_hash`, nor
  outer `specification_hash` equality — only layer-independent locators and
  shared-model hashes.
- Any failure raises `ValueError` (UNRESOLVED) — never a silent drop.

### Derivation-set binding verification (`_verify_placement_derivation_binding`, new method)

Called from `validate_readiness` and `compile`:

- `request.evaluation.cad_request` must be present when the candidate contains
  any `@3` specification or any placement derivation.
- Recompute `placement_derivations_hash` from
  `request.evaluation.cad_request.placement_derivations`; require equality with
  `cad_request.placement_derivations_hash` and with
  `request.evaluation.cad_stage_outcome.realization.placement_derivations_hash`
  (echoed field). Mismatch fails closed.

### Placement verification and projection (extension of `_canonical_placements`, :513-545)

- Existing xyz design-variable projection unchanged for non-generated
  components.
- For each derivation target instance: recompute the transform from the
  semantic derivation (candidate-side resolution, shared pure function) and
  require exact equality with the candidate CAD mapping placement
  (`request.evaluation.cad_stage_outcome.realization.mappings` matched by
  `physical_instance_id`); inconsistent placement fails promotion.
- Project the derivation through `canonical_by_candidate`
  (`map_instances`, `:274-308`) into `CanonicalGeneratedPlacementDerivation`
  (source/target canonical instance IDs, byte-identical inputs/rotation, same
  `derivation_id`, self-hash over the canonical-ID payload).
- Construct the result `CanonicalPlacement` per the conventions above and link
  `CanonicalPhysicalComponent.placement_id`.
- Mechanism built with `schema_version="canonical-physical-mechanism@2"` when
  the projected derivation collection is non-empty, else `@1` (legacy hash
  unchanged).
- CAD artifact IDs never become canonical design authority; CAD artifacts are
  never promoted.

### Promotion storage

- Candidate derivation set: persisted inside the CAD realization request (`@2`)
  — no new store.
- Canonical derivation records: the new schema-gated mechanism collection —
  no new store.

## Fresh Canonical Generated CAD (canonical_cad.py)

`CanonicalPhysicalCadCompiler._compile_generated` (`:570-629`) gains a routing
branch FIRST: `if specification.generated_part is not None:` compile via
`generated_part_cad.compile_generated_part(specification,
build_canonical_view(mechanism, ...), component.instance_id)`; mapping fidelity
`EXACT_GENERATED_GEOMETRY`; `representation_identity = cad_program_hash(program)`;
`geometry_definition_identities = generated_geometry_definition_identities(spec)`
(the same shared helper as the candidate side — input hashes union binding
hashes). Canonical generated programs get `part_id = generated_cad_definition_id` (NOT
`cad_instance_id`). The legacy `_GENERATED_COMPONENT_TYPES` plate path
(`:571-574`, `:629`) is unchanged for specs without `generated_part`.

Definition reuse: `realize` (`:336-508`) collects parts into a dict keyed by
`program.part_id`; instances use `part_id = program.part_id` for generated
components (legacy plates keep `part_id = cad_instance_id` at `:471-478`).
Fresh backend execution publishes fresh artifacts; candidate CAD artifacts are
never consulted or reused as semantic authority.

Placement replay: for components whose `CanonicalPlacement.relation` is a
generated placement rule id, the mapping placement comes from the stored
`CanonicalPlacement` (as today, `:397-406`) and `realize` verifies the stored
transform against the recomputed derivation replay (Task 11 helper).

---

## M10 Boundary

- Zero M10 model/algorithm modifications. The fidelity checks at
  `m10_evaluation.py:549-556` and `canonical_m10.py:884-891` are exact
  enum-equality; `EXACT_GENERATED_GEOMETRY` flows through unchanged.
- Generated parts enter as ordinary `CadAssemblyProgram` constituents; pair
  universes, sweeps, and continuous proofs operate unchanged.
- Candidate/canonical M10 integration regressions (Task 14) prove a generated
  candidate completes the existing evaluation path with a complete pair
  universe and no M10 source change (M10 files diff-checked empty).

## Failure Semantics (owner map — existing categories only)

| Failure | Category | Owner |
|---|---|---|
| Missing binding / non-authoritative dimension | INVALID/UNRESOLVED AUTHORITY | `GeneratedPartSpecification` construction (Pydantic) -> `CandidateCadStageReason.GEOMETRY_UNAVAILABLE` (`cad_realization.py:727`) |
| Input/binding resolution or mismatch | UNRESOLVED AUTHORITY / INTEGRITY | `GeneratedAuthorityError` -> wrapped `CandidateCadIntegrityError` / `CanonicalCadIntegrityError` |
| Unresolvable/aliased source (instance, placement) | INVALID PLACEMENT PROVENANCE | placement resolver -> `CandidateCadStageReason.INVALID_PLACEMENT_PROVENANCE` (`:729`) |
| Non-axisymmetric part with `axisymmetric-zero-clocking@1` | INVALID PLACEMENT PROVENANCE | derivation model/`place` applicability check |
| Placement derivation set substituted after selection | INTEGRITY / UNRESOLVED | promotion `_verify_placement_derivation_binding` |
| CAD placement inconsistent with semantic derivation | INTEGRITY | promotion `_canonical_placements` extension |
| Canonical placement replay mismatch | INTEGRITY | canonical reconstruction / canonical CAD replay |
| Relation cycle / illegal role/arity | INVALID SEMANTIC MODEL | relation validation (Pydantic + registry checks) |
| Unsupported feature (D-bore, keyway, ...) | UNSUPPORTED | `UNSUPPORTED_REPRESENTATION` (`:728`) |
| `@3` exclusivity violation | INVALID SEMANTIC MODEL | schema validation (`candidates/models.py` / `physical_mechanism.py`) |
| Deterministic compilation failure | COMPILATION FAILURE | wrapped `CandidateCadIntegrityError` (`cad_realization.py:422-423`) |
| FreeCAD crash/timeout | OPERATIONAL | `backends/errors.py` hierarchy (`FreeCADExecutionError` etc.) |
| Wrong artifact hash on reload | INTEGRITY | `ArtifactStore` + `_verify_persisted` |
| Stale CAD | STALE/INTEGRITY | existing request/realization hash checks + `dependency/storage.py` freshness |
| Promotion input/binding survival failure | UNRESOLVED | promotion survival verification |
| Promotion integrity (classification missing/substituted) | INTEGRITY | `_classifications_by_identity` (existing) |
| M10 collision witness | ENGINEERING RESULT | existing M10/M12 semantics (`promotion.py:1983-1992` handling) |
| M13-1 interface not authorized | UNRESOLVED AUTHORITY | existing gates (`supplied_component_interface.py:683-903`) |

No generic `M13_2_Error` is created.

---

## Implementation Tasks

Conventions for every task: run
`py -3 -m pytest tests/unit/test_m13_2_legacy_goldens.py -q` (STOP rule) plus the
listed regressions; run `py -3 -m compileall -q src/mechcad_harness tests` before
declaring a task complete; no commits.

### Task 0 — Pre-change compatibility goldens

- **Purpose:** freeze literal pre-M13-2 behavior for every schema/union touched later.
- **Production files:** none (test-only).
- **Test files:** `tests/unit/test_m13_2_legacy_goldens.py` (new).
- **Content:** fixture builders (complete code written by the worker per the
  fixture spec below) + literal captured constants + behavioral mapping-schema
  assertions. Fixtures:
  - plate program: `BasePlateOperation("base", 80, 60, 8)` + hole (10,10,6) +
    hole (70,50,6) + pocket (25,20,30,20,3) + slot (40,30,20,8,"x") via
    `CadPartProgram(part_id="M13GoldenPlate", ...)`.
  - `@1`/`@2` candidate + canonical specifications built exactly like
    `tests/unit/test_m13_legacy_hash_compatibility.py` (`@2` adds one frame,
    one direct shaft interface, one accepted transform).
  - candidate/request/realization/origin/mechanism fixtures mirror
    `tests/unit/test_m12_candidate_cad_models.py` and
    `tests/unit/test_m12_canonical_physical_mechanism.py` conventions
    (smallest complete records).
- **Validation invariants:** every literal constant round-trips
  byte-identically (JSON + hash).
- **Hash impact:** none. **Legacy impact:** none.
- **Exit criteria:** golden module green on the unmodified tree; capture script
  deleted; constants immutable.

### Task 1 — Shared generated-part authority inputs, bindings, hashes

- **Purpose:** the lower-level semantic authority layer.
- **Production files:** create `src/mechcad_harness/models/generated_part.py`;
  extend `src/mechcad_harness/models/__init__.py` exports
  (`GeneratedPartSpecification`, `GeneratedAuthorityInput`,
  `GeneratedPartFieldBinding`, `HubBoreSegment`, `SolidCircularShaftSpecification`,
  `CylindricalHubSpecification`, `RectangularFrameMemberSpecification`,
  `GeneratedRotationalInterface`, `GeneratedAttachmentFaceInterface`,
  `GeneratedReferenceFrame`, `GeneratedInterfaceDerivation`,
  `GeneratedAuthorityView`, `resolve_generated_inputs`,
  `GeneratedAuthorityError`, `evaluate_generated_field_rule`,
  `derive_shaft_interfaces`, `derive_hub_interfaces`,
  `derive_frame_interfaces`, `generated_geometry_definition_identities`,
  slot/rule/role constants).
- **New types/functions:** exactly as specified in the Generated-Part Model
  Plan section above.
- **Validation invariants:** every invariant listed in that section; the model
  re-derives interfaces and compares exact equality; bores sorted by `bore_id`;
  union round-trips via `model_validate(model_dump(mode="json"))`.
- **Hash impact:** new hashes only (`input_hash`, `binding_hash`,
  `interface_hash`, `frame_hash`, `generated_part_hash`).
- **Legacy compatibility impact:** none (no existing file behavior change).
- **Tests added:** `tests/unit/test_m13_2_generated_part_models.py` (valid
  round-trips per kind; deterministic hashes; field-order insensitivity;
  invalid dims; bore containment/overlap; duplicate bore_id;
  exactly-one-binding; unknown/duplicate slots; scalar-only inputs — a
  frame/quaternion value rejected; registry checks; **exact frame-face
  convention tests: each of the six `GeneratedAttachmentFaceInterface`
  records has exactly the frozen plane point / outward normal from the
  spec's Frame Face Semantics table, deterministic `interface_hash`, and
  pure replay equality under `generated-frame-faces@1`**) and
  `tests/unit/test_m13_2_generated_part_bindings.py` (locator semantics,
  selection_hash/value_hash recomputation, relation arity/roles, relation cycle
  impossibility, interface replay).
- **Regressions run:** `tests/unit/test_m13_legacy_hash_compatibility.py`,
  `tests/unit/test_models.py`, goldens.
- **Exit criteria:** new tests green; goldens green.

### Task 2 — Generated placement models + pure composition

- **Purpose:** the placement semantic layer (shared by both layers).
- **Production files:** create `src/mechcad_harness/models/generated_placement.py`;
  extend `src/mechcad_harness/models/__init__.py`
  (`GeneratedPlacementDerivation`, `GeneratedPlacementRotationInput`,
  `CanonicalGeneratedPlacementDerivation`, `SourcePlacementRef`,
  `GeneratedInterfaceRef`, `GeneratedFrameRef`, `placement_derivations_hash`,
  `place_generated_target`, `compose_poses`, `pose_from_interface`,
  `invert_pose`).
- **New types/functions:** exactly as in the Placement Derivation Plan.
- **Validation invariants:** rule consistency, numeric-only inputs, rotation
  requirements per rule, axisymmetric applicability, acyclic derivation sets,
  deterministic `placement_derivations_hash`, bit-identical composition.
- **Hash impact:** new `derivation_hash`, `input_hash` (rotation), set hash.
- **Legacy compatibility impact:** none.
- **Tests added:** `tests/unit/test_m13_2_placement_derivations.py` (model
  validation; rotation quaternion reconstruction from the resolved scalar
  angle + typed frame axis via `normalize_quaternion`; **no record accepts a
  free quaternion or multi-component tuple — free quaternion authority
  deferred**; angle resolution through an existing scalar `DESIGN_SELECTION`
  record with exact value + `value_hash` equality and fail-closed mismatch;
  axis_ref frame-hash authority; two motors sharing one
  `interface_hash` with different placements resolve to the referenced instance
  only — pure-function oracle; chained derivations acyclic; frame rule without
  rotation fails; axisymmetric rule with rotation fails; identity + offset +
  rotation compositions match hand-computed oracles; set hash ordering).
- **Regressions run:** goldens, `tests/unit/test_cad_assembly.py`
  (`CadRigidTransform` untouched).
- **Exit criteria:** new tests green; goldens green.

### Task 3 — CadPartProgram cylindrical operations + legacy compatibility

- **Purpose:** express positive cylinders and concentric subtractive bores.
- **Production files:** `src/mechcad_harness/cad_program.py`
  (`CadOperationValue:90`, `coordinate_system:96`, `validate_operations:105-134`,
  new `CylindricalStockOperation`/`AxialBoreOperation`);
  `src/mechcad_harness/cad_manifest.py:14`.
- **New types/functions:** the two op classes; base-kind-aware
  `validate_operations` (exact rules in the CAD Program / Backend Plan).
- **Validation invariants:** one-first-base still enforced for both base kinds;
  coordinate-system coupling; bore containment (diameter and axial extent);
  plate op classes rejected on cylinder base and vice versa; legacy plate
  programs byte-identical.
- **Hash impact:** none for existing plate programs (golden-proven); new
  program hashes only for new ops.
- **Legacy compatibility impact:** plate serialization/hash untouched.
- **Tests added:** extend `tests/unit/test_cad_program.py`
  (`test_m13_2_*` functions: cylinder base program validation; bore containment
  failures; coordinate coupling failures; mixed-base rejection; manifest kind
  extension in `tests/unit/test_cad_manifest.py`).
- **Regressions run:** `tests/unit/test_cad_program.py`,
  `tests/unit/test_cad_manifest.py`, `tests/unit/test_cad_compilation.py`,
  goldens.
- **Exit criteria:** new + existing CAD tests green; goldens green.

### Task 4 — FreeCAD cylindrical backend + real geometry tests

- **Purpose:** real single-solid generated cylinder geometry through the
  existing verified pipeline.
- **Production files:** `src/mechcad_harness/backends/freecad.py`
  (`compile_program:195-235` two new branches; `_verify_persisted:298-363`
  base-kind-aware bbox + bore probes via new `_base_kind` helper).
- **New types/functions:** `_base_kind(program)` module helper; no new classes.
- **Validation invariants:** cylindrical programs verify with expected bbox
  `(D, D, L)`, `solid_count == 1`; bore probes report the bore void; FCStd/STEP
  published with `input_hash = cad_program_hash`; fresh reopen verification
  passes; plate programs unchanged.
- **Hash impact:** none on existing artifacts.
- **Legacy compatibility impact:** none (probe payload gains keys only for
  cylindrical programs).
- **Tests added:** `tests/integration/test_m13_2_generated_parts_live.py`
  (live-marked, mirroring `tests/integration/test_cad_program_live.py` style):
  - shaft program -> FreeCAD FCStd/STEP; bbox == (D, D, L) within 1e-6;
    volume == pi * r^2 * L within 1e-6 relative; solid count 1; fresh reload
    in a separate process re-verifies.
  - hub program (stock - bore): volume == pi*(R^2 - r^2)*L within 1e-6
    relative; bbox == (D, D, L); one solid; fresh reload.
  - two-segment stepped-bore hub: volume == pi*R^2*L - pi*(r1^2*d1 + r2^2*d2).
- **Regressions run:** `tests/integration/test_cad_program_live.py`,
  `tests/integration/test_freecad_backend_live.py`, `tests/unit/test_freecad_backend.py`,
  goldens.
- **Exit criteria:** live tests green (geometric floating-point tolerance only —
  no manufacturing-tolerance claim); goldens green.

### Task 5 — GeneratedPartCompiler

- **Purpose:** the deterministic pure compiler boundary.
- **Production files:** create `src/mechcad_harness/generated_part_cad.py`.
- **New types/functions:** `GENERATED_PART_COMPILER_VERSION`,
  `generated_cad_definition_id`, `required_field_slots`, `verify_generated_part`,
  `compile_generated_part`, `GeneratedPartCompilation` — exactly as in the
  Generated Compiler Plan.
- **Validation invariants:** compiler refuses any unbound field; verifies every
  input/binding (steps 1-5 of the Authority Binding Plan); stable operation IDs
  (`{pid}-stock`, `{pid}-bore-{bore_id}`); correct coordinate-system literal per
  base kind; `part_id == generated-part-{full hash hex}`; no geometry constants
  anywhere (review + test asserts module has no numeric-literal geometry
  defaults); never touches FreeCAD.
- **Hash impact:** program hashes deterministic across constructions.
- **Legacy compatibility impact:** none.
- **Tests added:** `tests/unit/test_m13_2_generated_part_cad.py` (same spec ->
  identical program + hash across constructions; slot completeness failures;
  dimension == bound value; the "20 admitted / 15 generated" scenario fails
  both exact-value and hash checks; clearance variant changes bore and hash;
  missing relation input fails; unknown rule fails; frame lowering uses
  `BasePlateOperation`; identity tests: same spec -> same part_id; different
  specs with same `generated_part_id` -> different part_id).
- **Regressions run:** `tests/unit/test_cad_compilation.py` (legacy compiler
  untouched), goldens.
- **Exit criteria:** compiler tests green; goldens green.

### Task 6 — @3 component-specification integration + generated interface registry

- **Purpose:** embed generated parts in both specification snapshots with
  schema/version discipline.
- **Production files:** `src/mechcad_harness/candidates/models.py`
  (`ComponentSpecificationSnapshot` schema Literal `:240`, new
  `generated_part` field, serializer `:254-297`, validator `:299-386`);
  `src/mechcad_harness/models/physical_mechanism.py`
  (`CanonicalComponentSpecification` mirror `:255-416`).
- **New types/functions:** none beyond the field + validator branches (plus a
  shared `@3` registry-check helper imported from `models/generated_part.py`).
- **Validation invariants:** @1/@2 reject `generated_part`; @3 requires it and
  enforces exclusivity (`geometry_source is None`, M13 records empty) and
  exactly-once registry coverage; serializers keep @1/@2 byte-identical and
  include `generated_part` only at @3; hash determinism for @3.
- **Hash impact:** @3 payloads hash deterministically; @1/@2 unchanged.
- **Legacy compatibility impact:** @1/@2 goldens must stay green (STOP rule).
- **Tests added:** in `tests/unit/test_m13_2_generated_part_models.py`
  (`@3` required-with/without `generated_part`; exclusivity violations; @3
  serialization/hash determinism; registry exactly-once; frame non-endpoint) —
  plus golden re-checks.
- **Regressions run:** `tests/unit/test_m13_legacy_hash_compatibility.py`,
  `tests/unit/test_m12_candidate_foundation.py`, `tests/unit/test_m13_*`,
  goldens.
- **Exit criteria:** @3 green, @1/@2 goldens green.

### Task 7 — Exact-generated fidelity + candidate generated CAD routing

- **Purpose:** honest exact-generated fidelity and M12-4 routing.
- **Production files:** `src/mechcad_harness/candidates/cad_realization.py`
  (fidelity enum `:499-501`; gate `:170-171`; `_compile_generated:405-426`
  routing; parts dedup in `_realize_current:124-213`);
  `src/mechcad_harness/models/physical_mechanism.py`
  (`CanonicalGeometryFidelity` `:119-123`);
  `src/mechcad_harness/candidates/evaluation.py:330-337` review +
  `:346-357` allowed-identity extension.
- **New types/functions:** enum member `EXACT_GENERATED_GEOMETRY` (both
  enums); `_compile_generated` generated-part branch.
- **Validation invariants:** exact member required for `generated_part` specs;
  bounded member unchanged for legacy plates; `source_geometry_identity is
  None` for exact-generated; `representation_identity == cad_program_hash`;
  dual-representation (`geometry_source + generated_part`) impossible via @3
  exclusivity; fidelity conversion at `promotion.py:676-681` flows the new
  member (value-based).
- **Hash impact:** none on legacy mappings.
- **Legacy compatibility impact:** legacy generated-plate routing byte-stable.
- **Tests added:** `tests/unit/test_m13_2_candidate_cad_integration.py`
  (routing + fidelity enforcement; wrong fidelity rejected; imported purchased
  component with `geometry_source` never routes to `GeneratedPartCompiler` —
  routing precedence; definition reused by two instances -> one part, two
  instances, shared part_id, distinct instance_ids;
  **geometry-definition identity: mapping identities equal the shared helper
  output exactly, and the same `GeneratedAuthorityInput` set + binding graph
  A produces a different identity set than the same input set + binding graph
  B** — proving the validation distinguishes binding semantics).
- **Regressions run:** `tests/unit/test_m12_candidate_cad_*`,
  `tests/unit/test_m12_candidate_evaluation.py`,
  `tests/integration/test_m12_candidate_cad_m10_production.py`, goldens.
- **Exit criteria:** new + M12 CAD tests green; goldens green.

### Task 8 — CandidateCadRealizationRequest@2 + selected derivation-set binding

- **Purpose:** carry the semantic derivation set on the CAD request.
- **Production files:** `src/mechcad_harness/candidates/cad_realization.py`
  (`CandidateCadRealizationRequest` schema Literal `:568` + fields +
  schema-aware serializer; `CandidateCadRealization` `:616-717` echoed
  `placement_derivations_hash` with omission serializer).
- **New types/functions:** request fields
  `placement_derivations: tuple[GeneratedPlacementDerivation, ...] = ()` and
  `placement_derivations_hash: str | None = None`; realization echo field;
  validation: @1 forbids non-empty derivations and any hash; @2 requires the
  hash to equal `placement_derivations_hash(derivations)`; derivation_id
  uniqueness within the set; uniqueness of derivation targets per instance;
  serializer omits both keys at @1 (byte-identical legacy payloads).
- **Validation invariants:** request hash covers the set; realization hash
  covers the echo; legacy request/realization hashes unchanged.
- **Hash impact:** new requests hash with the set; @1 goldens unchanged.
- **Legacy compatibility impact:** @1 requests/realizations byte-stable.
- **Tests added:** `tests/unit/test_m13_2_candidate_cad_integration.py`
  (request @1 golden; @2 round-trip; hash covers set content and ordering;
  set substitution changes request identity; realization echo validated).
- **Regressions run:** `tests/unit/test_m12_candidate_cad_models.py`,
  `tests/unit/test_m12_candidate_cad_replay.py`, goldens.
- **Exit criteria:** @2 green; @1 goldens green.

### Task 9 — Candidate placement integration + definition reuse in realization

- **Purpose:** candidate CAD placement computed FROM the semantic derivation.
- **Production files:** `src/mechcad_harness/candidates/cad_realization.py`
  (`_realize_current:124-213` derivation-target branch; new
  `_derived_placement` helper; `_validate_placement_provenance:316-369`
  allowed-set extension; `_placement_error:470-492` bypass for derivation
  targets).
- **New types/functions:** `_derived_placement(request, mapping, specifications,
  candidate)` as specified in Candidate CAD Integration.
- **Validation invariants:** mapping placement == semantic recomputation
  (exact); `CandidatePlacementOrigin` authority `deterministic_derived_relation`
  with the specified identity tuple; provenance validation accepts exactly the
  derivation-derived identities and nothing more; non-derivation mappings keep
  the legacy path byte-stable.
- **Hash impact:** mapping/realization hashes for generated candidates only.
- **Legacy compatibility impact:** none for design-variable placements.
- **Tests added:** `tests/unit/test_m13_2_candidate_cad_integration.py`
  (mixed candidate: imported motor + generated hub + generated shaft ->
  realization succeeds; candidate CAD placement equals semantic recomputation;
  two identical supplied motors with different placements -> the referenced
  motor instance is used; unresolvable (instance, placement) pairs fail;
  foreign provenance identity rejected;
  **orientation-contract regression: replay of a `design_variable_placement`
  source asserts the exact `accepted-design-variable-placement@1` contract
  pose (translation + contract identity orientation) by full-transform
  equality, and a non-identity-oriented source cannot be expressed without a
  chained derivation — no orientation outside the named contract ever
  silently becomes identity**).
- **Regressions run:** `tests/unit/test_m12_candidate_cad_*`,
  `tests/integration/test_m12_candidate_cad_m10_production.py`, goldens.
- **Exit criteria:** new tests green; M12 CAD regressions green.

### Task 10 — Candidate resolution adapter + M13-1 consumption

- **Purpose:** the candidate-side authority view and M13-1 fact consumption.
- **Production files:** create
  `src/mechcad_harness/candidates/generated_authority.py`
  (`build_candidate_view`, instance-scoped full-name enumeration, fact-value
  extraction helpers); wire into `generated_part_cad` call sites from Task 7/9.
- **New types/functions:** `build_candidate_view(candidate, specification_hash)
  -> GeneratedAuthorityView`; `candidate_placement_design_variables(candidate,
  instance_id)`; `m13_local_pose(definition_or_frame) -> CadRigidTransform`
  (post-gate fact-value extraction using `require_authoritative_fact`).
- **Validation invariants:** bounded search (candidate specs only); M13-1 gates
  run before any value is accepted; multiple `interface_hash` matches must be
  byte-identical; `COMPONENT_SCOPED` vs `INSTANCE_SCOPED` resolution including
  the two legal alias forms and exclusion of the `geometry.{instance}.{dim}`
  legacy form; persisted bindings contain no `candidate:` strings and no
  instance IDs.
- **Hash impact:** none.
- **Legacy compatibility impact:** none.
- **Tests added:** `tests/unit/test_m13_2_m13_1_consumption.py`
  (authorized `RotationalShaftInterface.nominal_shaft_diameter` determines the
  hub bore via `hub-bore-from-supplied-shaft@1` and the clearance variant;
  unauthorized/missing interface fails closed; changed evidence fails;
  locator survives with differing outer container hashes — explicit test that
  no outer `specification_hash` is used; binding bytes identical across two
  constructed candidates with different instance IDs; unequal per-instance
  selections fail).
- **Regressions run:** `tests/unit/test_m13_supplied_component_interfaces.py`,
  `tests/unit/test_m13_publication_replay.py`, goldens.
- **Exit criteria:** new tests green; M13-1 regressions green.

### Task 11 — Canonical generated-placement models/schema

- **Purpose:** the canonical mechanism carries the semantic re-derivation
  inputs.
- **Production files:** `src/mechcad_harness/models/physical_mechanism.py`
  (mechanism schema `@1|@2` at `:700`; new
  `generated_placement_derivations` field; `_mechanism_payload_for_schema`
  hash/serializer change; validator additions);
  `src/mechcad_harness/candidates/promotion_models.py`
  (`PromotableMechanismProjection` field + omission serializer);
  `src/mechcad_harness/candidates/promotion.py:362-377` and
  `src/mechcad_harness/candidates/canonical_mechanism.py:409-427` projection
  population.
- **New types/functions:** `_mechanism_payload_for_schema`; schema-gated
  validation (non-empty requires @2).
- **Validation invariants:** legacy `@1` mechanisms reload with unchanged
  `mechanism_hash` (golden); `@2` includes the collection in the hash;
  projection omission keeps legacy projection hashes unchanged.
- **Hash impact:** `@2` mechanisms only.
- **Legacy compatibility impact:** goldens guard `@1` byte-stability.
- **Tests added:** `tests/unit/test_m13_2_promotion_canonical_roundtrip.py`
  (mechanism `@1` golden; `@2` round-trip + hash determinism; non-empty @1
  rejected; projection hash stability).
- **Regressions run:** `tests/unit/test_m12_canonical_physical_mechanism.py`,
  `tests/unit/test_m12_canonical_reconstruction.py`, goldens.
- **Exit criteria:** new tests green; canonical mechanism regressions green.

### Task 12 — Promotion: mapping, classifications, survival, projection

- **Purpose:** promotion carries generated semantics truthfully.
- **Production files:** `src/mechcad_harness/candidates/promotion.py`
  (`_verify_policy:947-970` trigger extension; `_expected_classifications:1112-1184`
  additions; `_canonical_specification:446-489` @3 mapping; new
  `_verify_generated_authority_survival`; new
  `_verify_placement_derivation_binding`; `_canonical_placements:513-545`
  derivation projection; `_compile_mechanism:379-444` mechanism schema +
  collection wiring).
- **New types/functions:** the three new verification methods listed above.
- **Validation invariants:** all-@1 -> mapping@1; any @2/@3 -> mapping@2; the
  two new classification identities with exact values; missing classification,
  substituted value, unsupported classification all fail; input/binding
  survival on BOTH sides; derivation-set binding proven; CAD placement ==
  semantic derivation; canonical projection via `canonical_by_candidate`;
  CAD artifacts never promoted.
- **Hash impact:** mapping schema unchanged (@1/@2 only); canonical mechanism
  @2 when derivations exist.
- **Legacy compatibility impact:** legacy promotions byte-stable (readiness
  hash payload unchanged — no new readiness fields).
- **Tests added:** `tests/unit/test_m13_2_promotion_canonical_roundtrip.py`
  (@3 -> mapping@2; missing/incorrect classifications fail; survival failures
  fail promotion; evaluated-with-set-A + promoted-with-set-B fails / set-A
  passes; inconsistent CAD placement fails; byte-identical spec crossing
  golden; source instance and source placement identity preserved through
  projection).
- **Regressions run:** `tests/unit/test_m12_promotion_*.py`,
  `tests/integration/test_m12_promotion_production.py`, goldens.
- **Exit criteria:** new tests green; promotion regressions green.

### Task 13 — Fresh canonical generated CAD + reconstruction

- **Purpose:** canonical regeneration and placement replay without candidates.
- **Production files:** `src/mechcad_harness/candidates/canonical_cad.py`
  (`_compile_generated:570-629` generated routing; `realize:336-508` part
  dedup + instance `part_id` + fidelity + placement replay);
  `src/mechcad_harness/candidates/canonical_mechanism.py`
  (`_validate_mechanism`/`reconstruct` extension: input/binding verification +
  placement replay).
- **New types/functions:** canonical view builder
  `build_canonical_view(mechanism, specification_hash)` in
  `candidates/generated_authority.py`; replay helpers reusing
  `generated_part_cad.verify_generated_part` and
  `models.generated_placement.place_generated_target`.
- **Validation invariants:** canonical program hash == candidate program hash
  for identical semantics (same `generated_part_hash` -> same part_id ->
  same hash); canonical placement recomputes from canonical records only and
  matches the stored `CanonicalPlacement`; fresh backend execution publishes
  fresh artifacts; candidate objects never consulted.
- **Hash impact:** none on legacy canonical realizations.
- **Legacy compatibility impact:** legacy plate routing untouched.
- **Tests added:** `tests/unit/test_m13_2_promotion_canonical_roundtrip.py`
  (canonical regeneration; definition identity preserved; reconstruction
  verifies all inputs/bindings/derivations without candidate state; tampered
  derivation -> integrity failure).
- **Regressions run:** `tests/unit/test_m12_canonical_cad.py`,
  `tests/unit/test_m12_canonical_reconstruction.py`, goldens.
- **Exit criteria:** new tests green; canonical regressions green.

### Task 14 — Candidate/canonical M10 integration regressions

- **Purpose:** prove generated parts traverse the existing M10 path unchanged.
- **Production files:** none expected; if a defect surfaces it is fixed in the
  owning module, never in M10.
- **Tests added:** `tests/unit/test_m13_2_candidate_cad_integration.py`
  M10 section: generated candidate runs `CandidateM10EvaluationService` with a
  complete pair universe; fidelity requirements satisfied by
  `EXACT_GENERATED_GEOMETRY`; `CandidateM10Binding.cad_realization_hash` binds
  the realization carrying the derivation set. Canonical side mirrors via
  `CanonicalM10VerificationService` (existing fidelity equality at
  `canonical_m10.py:884-891`).
- **Regressions run:** `tests/unit/test_m12_candidate_m10_*.py`,
  `tests/unit/test_m12_canonical_m10.py`,
  `tests/integration/test_m10_3_live_multi_joint_collision.py`,
  `tests/integration/test_transient_imported_multishape_collision.py`.
- **Exit criteria:** all M10 suites green; `git diff --stat` shows zero M10
  source changes.

### Task 15 — Live bounded M13-2 acceptance + full regression

- **Purpose:** the bounded live acceptance (NOT M13-4; generic fixture, no
  Rotator V2).
- **Test files:** `tests/integration/test_m13_2_acceptance_live.py`
  (new, mirroring `tests/integration/test_m12_6_end_to_end_direct_drive.py`
  and `tests/integration/m12_6_acceptance_fixtures.py` style).
- **Fixture (bounded):** one imported supplied "motor" STEP component
  (tiny plate-like STEP published via `ArtifactStore` exactly like the M12-6
  fixtures) carrying an M13-1 `RotationalShaftInterface` + reference frame;
  one generated hub (input bore bound via
  `hub-bore-from-supplied-shaft-with-clearance@1` over the M13-1 fact + an
  explicit `clearance` DESIGN_SELECTION; output bore bound to the shaft's
  admitted `selected-output-shaft-diameter`); one generated shaft (diameter
  bound to the admitted selection, length a DESIGN_SELECTION); optionally one
  rectangular frame member with an explicit rotation placement. Exactly one
  `GeneratedPlacementDerivation` set (coaxial placements +
  `axisymmetric-zero-clocking@1` for shaft/hub; frame rule with explicit
  rotation if the frame is included).
- **Flow proven end to end:** imported supplied component + M13-1 authoritative
  shaft interface + generated hub + generated shaft (+ optional frame) ->
  candidate generated CAD -> real FreeCAD FCStd/STEP -> fresh reload -> existing
  M10 candidate evaluation -> selection-bound placement derivation ->
  promotion (mapping@2, classifications, survival, placement verification) ->
  canonical generated placement derivations -> fresh canonical generated CAD
  (fresh FreeCAD execution) -> canonical M10 re-verification. Fresh
  reconstruction from `DesignState` + `CanonicalPhysicalMechanism` +
  `ArtifactStore`/`ProjectArtifactResolver` only (no candidate objects).
- **Exit criteria:** acceptance green; then full suite.

---

## Test Strategy (file plan)

| File | Covers |
|---|---|
| `tests/unit/test_m13_2_legacy_goldens.py` | all pre-M13-2 compatibility goldens (Task 0; STOP rule) |
| `tests/unit/test_m13_2_generated_part_models.py` | models, hashes, per-kind validation, hub bores/mouths, frame faces, @3 schema/exclusivity/registry |
| `tests/unit/test_m13_2_generated_part_bindings.py` | authority locators, value/selection hashes, direct + relation bindings, failure categories |
| `tests/unit/test_m13_2_generated_part_cad.py` | compiler lowering, operation IDs, coordinate literals, definition identity, no-defaults |
| `tests/unit/test_m13_2_placement_derivations.py` | placement models, pure composition, clocking rules, acyclicity, set hash |
| `tests/unit/test_m13_2_candidate_cad_integration.py` | candidate routing/fidelity, definition reuse, request @2, placement integration, M10 integration |
| `tests/unit/test_m13_2_m13_1_consumption.py` | M13-1 fact resolution, gates, layer-stability, candidate view |
| `tests/unit/test_m13_2_promotion_canonical_roundtrip.py` | promotion mappings/classifications/survival/binding, canonical schema, reconstruction, canonical CAD |
| `tests/integration/test_m13_2_generated_parts_live.py` | real FreeCAD shaft/hub geometry, fresh reload |
| `tests/integration/test_m13_2_acceptance_live.py` | bounded live acceptance chain |

Focused modules per concern; no single giant integration test. Existing suites
listed per task are the regression floor.

## Staged Verification

- **Stage A** (Tasks 1-2): pure models/hashes/bindings/interfaces/placement —
  unit only.
- **Stage B** (Tasks 3, 5): CadPartProgram ops + compiler — unit.
- **Stage C** (Task 4): real FreeCAD primitive/part tests — live-marked.
- **Stage D** (Tasks 6-10): @3 + candidate CAD + placement — unit (+ existing
  live M12 suites).
- **Stage E** (Tasks 11-13): promotion + canonical reconstruction — unit.
- **Stage F** (Task 14): M12/M13-1 focused regressions.
- **Stage G** (Task 15): dedicated M13-2 live acceptance.
- **Stage H:** full suite: `py -3 -m pytest tests/` with a tool ceiling of at
  least **4000 seconds** (M13-1 full-suite history was ~3000 s; M13-2 adds live
  tests — use 6000 s to be safe).
- Static: `py -3 -m compileall -q src/mechcad_harness tests`;
  `git diff --check`; explicit trailing-whitespace scan of touched files;
  final-newline check of touched files.

## Live Acceptance Strategy

Bounded, generic, non-Rotator fixture as specified in Task 15. Success marker
for the future implementation milestone:
`M13_2_GENERIC_GENERATED_MECHANICAL_PART_CAD_FOUNDATION_VERIFIED`. Volume/bbox
tolerances follow the existing live-test style (1e-6 relative/absolute
geometric tolerance); no manufacturing-tolerance claim is made.

## Regression Strategy

- Task 0 goldens run in every task.
- Legacy plate path: `test_cad_compilation.py`, `test_cad_program.py`,
  `test_m8c1_production_cad_compilation.py` untouched behavior.
- Imported multi-shape: `test_transient_imported_multishape_collision.py`
  (all-top-level-shape aggregation untouched).
- M13-1: `test_m13_*.py` full family.
- M12: candidate CAD/evaluation/M10/promotion families.
- Full suite at Stage H (>= 4000 s ceiling).

## Planned Files

Created:
- `src/mechcad_harness/models/generated_part.py`
- `src/mechcad_harness/models/generated_placement.py`
- `src/mechcad_harness/generated_part_cad.py`
- `src/mechcad_harness/candidates/generated_authority.py`
- `tests/unit/test_m13_2_legacy_goldens.py`
- `tests/unit/test_m13_2_generated_part_models.py`
- `tests/unit/test_m13_2_generated_part_bindings.py`
- `tests/unit/test_m13_2_generated_part_cad.py`
- `tests/unit/test_m13_2_placement_derivations.py`
- `tests/unit/test_m13_2_candidate_cad_integration.py`
- `tests/unit/test_m13_2_m13_1_consumption.py`
- `tests/unit/test_m13_2_promotion_canonical_roundtrip.py`
- `tests/integration/test_m13_2_generated_parts_live.py`
- `tests/integration/test_m13_2_acceptance_live.py`

Modified:
- `src/mechcad_harness/cad_program.py`
- `src/mechcad_harness/cad_manifest.py`
- `src/mechcad_harness/backends/freecad.py`
- `src/mechcad_harness/candidates/models.py`
- `src/mechcad_harness/candidates/cad_realization.py`
- `src/mechcad_harness/candidates/evaluation.py`
- `src/mechcad_harness/candidates/promotion.py`
- `src/mechcad_harness/candidates/promotion_models.py`
- `src/mechcad_harness/candidates/canonical_cad.py`
- `src/mechcad_harness/candidates/canonical_mechanism.py`
- `src/mechcad_harness/models/physical_mechanism.py`
- `src/mechcad_harness/models/__init__.py`
- `src/mechcad_harness/candidates/__init__.py`

Untouched (contract): everything under M10 (`m10_evaluation.py`,
`canonical_m10.py`, all `multi_joint_*`, `kinematic_sweep.py`,
`continuous_proof.py`), M11 (`structural/*`), M13-1
(`models/supplied_component_interface.py`), `cad_compilation.py`,
`imported_component.py`, `backends/freecad_assembly.py`, `dependency/*`,
Rotator-specific modules.

## Plan Self-Review (checklist results)

- Hidden engineering defaults: none — every dimension carries exactly one
  verified binding; compiler has no defaults (Task 5 test).
- Numeric field without authority binding: impossible by construction
  (completeness validation) and by compiler refusal.
- Candidate-only identity persisted in `GeneratedPartSpecification`: none —
  locators are layer-independent; instance IDs never persisted (Task 1/10
  tests).
- INSTANCE_SCOPED resolution ambiguity: resolved exactly — target-owned rule,
  enforced by the shared resolver signature (Placement Input Ownership).
- Stale `clocking_reference`: dropped everywhere (spec and plan reconciled to
  `clocking_angle`, which no initial rule admits).
- Rotation authority: scalar-angle only — resolved from an existing scalar
  `DESIGN_SELECTION` record (candidate `CandidateDesignVariable` /
  canonical `CanonicalAcceptedDesignChoice`, exact value + hash equality)
  with the axis taken from a typed frame reference whose `frame_hash` is the
  authority; no record accepts a free quaternion or multi-component tuple;
  free quaternion authority explicitly deferred (Task 2 tests).
- Geometry-definition identities: shared helper `generated_geometry_definition_identities`
  (input hashes union binding hashes) used identically candidate-side and
  canonical-side; same inputs + binding graph A != same inputs + binding
  graph B is regression-tested (Task 7); `CandidatePlacementOrigin`
  provenance carries placement-derivation references only (never the
  geometry identity set).
- Source orientation: identity orientation is part of the named
  `accepted-design-variable-placement@1` contract (verified at
  `cad_realization.py:470-492` / `promotion.py:513-545`), never a fallback;
  full-contract-pose replay regression in Task 9.
- Frame-face convention: the six face plane points / outward normals are
  frozen in the spec's Frame Face Semantics table with hash/replay tests
  (Task 1).
- M13-1 outer `specification_hash` reliance: none — locator is 4 keys only
  (Task 10 test with differing outer hashes).
- Tuple-index bore identity: banned; `bore_id` everywhere (Task 1 tests).
- Same direction on opposite bore mouths: near +Z / far -Z fixed and tested.
- `generated_part_id` as global CAD part ID: banned;
  `generated-part-{full hash}` only (Task 5 identity tests).
- Definition collisions in the parts registry: impossible (different specs ->
  different hashes -> different part_ids; Task 5/13 tests).
- One definition compiled per instance: dedup planned candidate-side (Task 7)
  and canonical-side (Task 13).
- @1/@2 hash/JSON drift: guarded by goldens (Task 0) and schema-aware
  serializers.
- Request@1 drift: guarded (Task 8).
- Legacy candidate hash drift: `MechanicalDesignCandidate` payload untouched;
  guarded by goldens.
- Empty canonical placement collection leaking into old mechanism hashes:
  schema-aware `_mechanism_payload_for_schema` omits the key at @1
  (Task 11 golden).
- `CandidatePlacementOrigin` as semantic authority: no — evidence only;
  semantic owner is the derivation set (Task 9).
- Placement derivation set not selection-bound: bound via request @2 ->
  realization -> M10 binding -> evaluation -> selection -> promotion (Task 8/12).
- Source physical instance lost in projection: retained as
  `source_canonical_instance_id` (Task 12 test).
- Source placement identity lost: retained via `source_placement_ref`
  (Task 12 test).
- `CanonicalPlacement.input_identities` as the only structured authority: no —
  summary only; structured resolution via the canonical derivation record.
- Hidden frame-member identity rotation: impossible — explicit rotation input
  required, tested (Task 2).
- Generated interfaces absent from endpoint registry: exactly-once registry
  validation at @3 (Task 6).
- Exact-generated fidelity treated as manufacturing truth: bounded docstring +
  acceptance wording (Task 7).
- build123d in the generated path: excluded (no import anywhere in planned
  files).
- M10 algorithm changes: none; Task 14 asserts empty M10 diff.
- Rotator-specific semantics: none; generic fixture only.
- M13-3/M13-4 scope creep: none (handoff boundaries only).

## Worktree Note

This session creates only this plan file
(`docs/superpowers/plans/2026-09-02-m13-2-generic-generated-mechanical-part-cad-foundation.md`).
Pre-existing unrelated dirty/untracked worktree state is not touched.
