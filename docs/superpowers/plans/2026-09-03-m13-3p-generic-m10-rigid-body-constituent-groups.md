# M13-3P Generic M10 Rigid-Body Constituent Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add generic M10 v2 rigid-body constituent grouping while preserving literal M10 v1 serialization, identities, FK behavior, pair semantics, and proof mathematics.

**Architecture:** Keep the existing v1 classes and code paths as legacy-only records; add explicitly named v2 Pydantic records and parser/hash dispatch in the existing M10 modules. `MultiJointKinematicsService` remains the only FK engine, and M10-3/M10-4 continue to pass opaque concrete ID pairs to the existing transient FreeCAD boundary. A single fixed transform-agreement policy validates v2 offsets and q=0 pose agreement without changing persisted transform values.

**Tech Stack:** Python 3.11+, Pydantic v2, existing `CadRigidTransform` and quaternion helpers, deterministic SHA-256 JSON identities, pytest, FreeCAD transient measurement.

## Global Constraints

- Implement only generic M10/CAD plumbing. Do not resume M13-3 or start M13-4.
- Do not import candidate authority, promotion, physical-mechanism, supplied-component, generated-part, M11, or Rotator V2 modules into M13-3P production code.
- Do not create a second FK solver, collision implementation, continuous proof, compound body, or fake fixed joint.
- Retain existing revolute math, raw multi-turn configuration identity, M10-3 classification, M10-4 interpolation, subdivision, proof inequality, and `B_A + B_B` arithmetic.
- Preserve v1 model/request/result JSON and hash bytes exactly. Never update a captured v1 golden to match new code.
- `rigid-transform-agreement@1.0` is fixed: translation max absolute error `<= 1e-9` mm; sign-invariant normalized-quaternion angle `<= 1e-7` rad; full transform precision persists unchanged.
- Do not commit, tag, push, or release while executing this plan unless a later user instruction explicitly authorizes it.

## File Map

- Modify `src/mechcad_harness/multi_joint_kinematics.py`: v1/v2 model records, frozen transform agreement, body and cross-body pair validation, topology dispatch, and the sole FK implementation.
- Create `src/mechcad_harness/multi_joint_pair_scope.py`: neutral canonical constituent-pair model and scope helpers only.
- Modify `src/mechcad_harness/multi_joint_collision_sweep.py`: v2 typed request/result records and branch-local neutral mapping over the existing transient service.
- Modify `src/mechcad_harness/multi_joint_continuous_path.py`: v2 request record and body-member reach-input plumbing.
- Modify `src/mechcad_harness/multi_joint_continuous_clearance.py`: v2 neutral proof records and result construction over unchanged proof control flow.
- Modify `src/mechcad_harness/transient_assembly_analysis.py` and `src/mechcad_harness/transient_freecad_measurement.py`: neutralize implementation-local operand variable names only; retain the opaque wire tuple and current JSON keys.
- Modify `src/mechcad_harness/application.py`: explicit v2 production entrypoints and v1/v2 evidence-result parsing.
- Modify `src/mechcad_harness/analysis_provenance.py`: add an optional v2 reach-plumbing version field without changing existing serialized legacy payloads.
- Create `tests/unit/test_m13_3p_legacy_goldens.py`: immutable pre-change v1 JSON/hash goldens.
- Create `tests/unit/test_m13_3p_rigid_body_groups.py`: agreement, v2 models, FK, topology, pair scope, M10-3, and M10-4 deterministic tests.
- Create `tests/integration/test_m13_3p_live_grouped_body_freecad.py`: focused real FreeCAD six-constituent acceptance.
- Create `docs/audit/MECHCAD_M13_3P_COMPLETION_REPORT.md` only after all acceptance gates pass.

---

### Task 0: Capture Immutable V1 Goldens Before Production Changes

**Purpose:** Freeze current behavior from unmodified production code so every later task can detect literal legacy drift.

**Files:**
- Create: `tests/unit/test_m13_3p_legacy_goldens.py`
- Temporary only, outside the repository: `C:\Users\vvooj\AppData\Local\Temp\opencode\capture_m13_3p_v1_goldens.py`

**Current symbols:** `RevoluteJointModel`, `KinematicModel`, `kinematic_model_hash`, `MultiJointKinematicsService`, `MultiJointCollisionSweepRequest`, `MultiJointCollisionConfigurationResult`, `MultiJointCollisionSweepResult`, `MultiJointContinuousPathRequest`, `ContinuousExactPairResult`, `ContinuousPairCertificate`, `MultiJointContinuousCollisionWitness`, and `MultiJointContinuousClearanceProofResult`.

**Interfaces:** The golden test must expose `_literal_json(value) -> str`, using `json.dumps(value.model_dump(mode="json"), separators=(",", ":"))`, and `_record_digest(value) -> str`, using sorted-key canonical JSON with separators `( ",", ":" )`. The latter is a test-only digest for current result records which have no intrinsic hash field.

- [ ] Run the temporary capture script against the untouched source. It must construct the existing one-joint and two-joint fixtures from `tests/unit/test_multi_joint_kinematics.py`, use a deterministic injected transient provider, and print named constants for:
  - one v1 `RevoluteJointModel` JSON;
  - one v1 `KinematicModel` JSON and `kinematic_model_hash`;
  - one-joint and multi-joint FK result JSON and `result_hash`;
  - v1 M10-3 request JSON/request hash, configuration-result JSON/test-only digest, and sweep-result JSON/result hash;
  - v1 M10-4 request JSON/request hash, exact-pair JSON/test-only digest, certificate JSON/test-only digest, witness JSON/test-only digest, and final-result JSON/result hash;
  - identity-bearing literals: `multi-joint-forward-kinematics@1.0`, `multi-joint-exact-collision-sweep@1.0`, `piecewise-linear-joint-command-path@1.0`, `articulated-descendant-reach-bound@1.0`, and `conservative-multi-joint-path-clearance-proof@1.0`.
- [ ] Copy only the printed literals into `test_m13_3p_legacy_goldens.py`. Delete the temporary capture script before any production edit. The test must parse each JSON through its current v1 class, compare `model_dump_json()` to the captured literal, compare all intrinsic hashes, compare test-only digests, and assert the version literals.
- [ ] Run `py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v` before editing production files. Expected: all golden assertions pass on unmodified code.

**Validation invariants:** Goldens are captured from unmodified production code and never regenerated. A mismatch after Task 0 is `M13_3P_LEGACY_COMPATIBILITY_FAILURE`.

**Serialization/hash impact:** None at capture time. The test records the exact existing v1 wire/hashing behavior.

**Legacy compatibility impact:** Establishes the immutable acceptance boundary.

**Predecessor regressions:** Current M10 unit suites must already pass before capture.

**STOP conditions:** Any uncertainty about which code version produced a captured literal, a capture helper retained in the repository, or any golden drift after a later task.

**Exit criteria:** The immutable test is included in the future change set, passes independently, and the temporary helper is absent.

### Task 1: Implement `rigid-transform-agreement@1.0`

**Purpose:** Add the one and only v2 rigid-pose agreement predicate in the current transform/FK module.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_kinematics.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`

**Current symbols:** `CadRigidTransform`, `transform_compose`, `transform_inverse`; `normalize_quaternion` in `src/mechcad_harness/models/quaternion.py`.

**New symbols:**
```python
RIGID_TRANSFORM_AGREEMENT_VERSION = "rigid-transform-agreement@1.0"
RIGID_TRANSFORM_TRANSLATION_ABS_TOL_MM = 1e-9
RIGID_TRANSFORM_ORIENTATION_ABS_TOL_RAD = 1e-7

@dataclass(frozen=True)
class RigidTransformAgreementPolicy:
    version: str
    translation_metric: str
    translation_abs_tol_mm: float
    orientation_metric: str
    orientation_abs_tol_rad: float

RIGID_TRANSFORM_AGREEMENT_POLICY: RigidTransformAgreementPolicy

def rigid_transform_agrees(
    first: CadRigidTransform,
    second: CadRigidTransform,
    policy_version: str = RIGID_TRANSFORM_AGREEMENT_VERSION,
) -> bool
```

- [ ] Write failing direct tests for literal identity, an arbitrary normalized-quaternion round trip, the observed floating reconstruction, `q` versus `-q`, non-finite model-constructed input returning `False`, and a materially incorrect placement returning `False`.
- [ ] For translation boundaries, use transforms differing only in `x_mm` by exactly `1e-9` and by `math.nextafter(1e-9, math.inf)`; assert inclusive pass then fail.
- [ ] For orientation boundaries, construct `qb = (cos(theta / 2), sin(theta / 2), 0, 0)`, calculate the production metric in the test, and select `theta` values by a bounded `math.nextafter` search until one production metric is `<= 1e-7` and the next is `> 1e-7`. Assert the predicate on those verified pairs, not merely on analytically requested angles.
- [ ] Import `normalize_quaternion` from `mechcad_harness.models.quaternion`. Require all seven raw values of both transforms to be finite; return `False` before normalization when not finite. Normalize only with that shared helper. Compute `max(abs(dx), abs(dy), abs(dz))`, compute the absolute quaternion dot, clamp with `min(1.0, max(0.0, dot))`, compute `2.0 * math.acos(clamped_dot)`, and use only inclusive `<=` comparisons to the two frozen constants.
- [ ] Reject every `policy_version` other than `RIGID_TRANSFORM_AGREEMENT_VERSION` with `ValueError`. Do not accept tolerances, a policy object, rounding flags, relative tolerance, or a FreeCAD callback from callers.
- [ ] Run `py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -k transform_agreement -v` and the Task 0 goldens.

**Validation invariants:** No rounding, no transform-hash comparison, no geometry query, no caller-selected epsilon, and no `pytest.approx` in production.

**Serialization/hash impact:** None in v1; the version is only introduced into a later v2 model payload.

**Legacy compatibility impact:** `CadRigidTransform` and all existing transform helper output and serialization remain unchanged.

**STOP conditions:** Any need to change `CadRigidTransform`, replace `normalize_quaternion`, add a comparison tolerance, or use literal equality for v2 composed transforms.

**Exit criteria:** All direct agreement cases pass and Task 0 remains byte-identical.

### Task 2: Add Rigid-Body Member and Body Records

**Purpose:** Represent a generic rigid kinematic body with explicit full-precision constituent offsets.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_kinematics.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`

**New symbols:**
```python
class KinematicRigidBodyMember(Model):
    member_instance_id: str
    reference_to_member_home: CadRigidTransform

class KinematicRigidBody(Model):
    schema_version: Literal["kinematic-rigid-body@1"]
    body_id: str
    reference_member_instance_id: str
    members: tuple[KinematicRigidBodyMember, ...]
    body_hash: str

def kinematic_rigid_body_hash(body: KinematicRigidBody) -> str
```

- [ ] Write failing tests for blank/whitespace IDs, empty members, duplicate members, missing reference member, duplicate reference member, non-identity reference offset, canonical member ordering, and body-hash sensitivity to ID, reference member, member membership, and exact offset values.
- [ ] Validate nonblank `body_id`, `reference_member_instance_id`, and `member_instance_id` with a shared local `_require_nonblank_kinematic_id(value, label)` helper. Canonicalize the persisted `members` tuple by `member_instance_id` with `object.__setattr__`; reject duplicates before sorting. Require the reference member to occur exactly once and its declared offset to be literal `CadRigidTransform()` equality, not the agreement predicate.
- [ ] Define the body hash payload as `schema_version`, `body_id`, `reference_member_instance_id`, and canonical `members`, with each member serialized as `member_instance_id` plus the unrounded `CadRigidTransform.model_dump(mode="json")`. Derive/verify `body_hash` in the after validator, excluding `body_hash` from its own payload.
- [ ] Run focused body tests and Task 0 goldens.

**Validation invariants:** Member offsets are explicit, persisted at full precision, and never derived from assembly geometry or source placement.

**Serialization/hash impact:** New v2-only records; v1 serializer and hashes do not observe these types.

**Legacy compatibility impact:** None.

**STOP conditions:** A member silently belongs to more than one body, an offset is inferred, a body is represented by a compound, or a reference offset is accepted by tolerance instead of literal identity.

**Exit criteria:** Body records canonicalize deterministically and fail closed for every listed malformed record.

### Task 3: Version Kinematic Models and Revolute Joints Without V1 Drift

**Purpose:** Make v1 and v2 schema selection explicit and non-ambiguous before topology or execution changes.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_kinematics.py`
- Modify: `tests/unit/test_m13_3p_legacy_goldens.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`

**New symbols and exact ownership:**
```python
class RevoluteJointModel(Model):  # v1 public compatibility class
    schema_version: Literal["revolute-joint-model@1"] = "revolute-joint-model@1"
    joint_id: str
    joint_kind: KinematicJointKind = KinematicJointKind.REVOLUTE
    parent_instance_id: str
    child_instance_id: str
    axis_origin_x_mm: float = 0.0
    axis_origin_y_mm: float = 0.0
    axis_origin_z_mm: float = 0.0
    axis_direction_x: float = 0.0
    axis_direction_y: float = 0.0
    axis_direction_z: float = 1.0
    min_angle_deg: float | None = None
    max_angle_deg: float | None = None

class RevoluteJointModelV2(Model):
    schema_version: Literal["revolute-joint-model@2"] = "revolute-joint-model@2"
    joint_id: str
    joint_kind: KinematicJointKind
    parent_body_id: str
    child_body_id: str
    axis_origin_x_mm: float = 0.0
    axis_origin_y_mm: float = 0.0
    axis_origin_z_mm: float = 0.0
    axis_direction_x: float = 0.0
    axis_direction_y: float = 0.0
    axis_direction_z: float = 1.0
    min_angle_deg: float | None = None
    max_angle_deg: float | None = None

class KinematicModel(Model):  # v1 public compatibility class
    schema_version: Literal["kinematic-model@1"] = "kinematic-model@1"
    model_id: str
    joints: tuple[RevoluteJointModel, ...]
    evaluator_version: Literal["multi-joint-forward-kinematics@1.0"]

class KinematicModelV2(Model):
    schema_version: Literal["kinematic-model@2"] = "kinematic-model@2"
    model_id: str
    bodies: tuple[KinematicRigidBody, ...]
    joints: tuple[RevoluteJointModelV2, ...]
    evaluator_version: Literal["multi-joint-forward-kinematics@2.0"]
    transform_agreement_version: Literal["rigid-transform-agreement@1.0"]

KinematicModelInput = KinematicModel | KinematicModelV2
RevoluteJointModelInput = RevoluteJointModel | RevoluteJointModelV2

def parse_revolute_joint_model(value: Mapping[str, object] | RevoluteJointModelInput) -> RevoluteJointModelInput
def parse_kinematic_model(value: Mapping[str, object] | KinematicModelInput) -> KinematicModelInput
def kinematic_model_wire_payload(model: KinematicModelInput) -> dict[str, object]
def v2_revolute_joint_wire_payload(joint: RevoluteJointModelV2) -> dict[str, object]
```

- [ ] Add failing tests that an absent discriminator parses to the v1 classes, v1 `model_dump_json()` remains byte-identical, v2 requires its explicit discriminator, v1 rejects bodies/body endpoint fields, v2 rejects instance endpoint fields, a changed agreement version changes v2 model identity, and identical v2 topology with `joint_id="J1"` versus `joint_id="JX"` changes `kinematic_model_hash`.
- [ ] Use `@model_serializer(mode="wrap")` on the two v1 classes. Let the handler serialize normal fields, then remove only their in-memory `schema_version`; nested v1 joint serialization must also omit it. Do not use `exclude_none` for compatibility.
- [ ] Canonicalize persisted v2 tuples in their own after validators with `object.__setattr__`: `KinematicRigidBody.members` sorted by `member_instance_id`; `KinematicModelV2.bodies` sorted by `body_id`; and `KinematicModelV2.joints` sorted by `joint_id`. Reject duplicate body IDs and duplicate joint IDs before sorting. Thus equivalent v2 caller tuple reorder produces identical `model_dump(mode="json")` and identical model hash. Do not canonicalize v1 tuples.
- [ ] Make `v2_revolute_joint_wire_payload` return exactly this ordered semantic mapping for every v2 joint: `schema_version`, `joint_id`, `joint_kind`, `parent_body_id`, `child_body_id`, `axis_origin_x_mm`, `axis_origin_y_mm`, `axis_origin_z_mm`, `axis_direction_x`, `axis_direction_y`, `axis_direction_z`, `min_angle_deg`, and `max_angle_deg`. Its source is the normalized in-memory joint fields; no endpoint aliasing or omitted `joint_id` is permitted.
- [ ] Keep the exact current v1 hash payload branch verbatim in `kinematic_model_hash`. Make its v2 branch hash a payload containing `schema_version`, `model_id`, `evaluator_version`, `transform_agreement_version`, `bodies` as canonical body hashes in persisted body order, and `joints` as `v2_revolute_joint_wire_payload(joint)` in persisted joint-ID order. Serialize that payload with the existing `json.dumps(..., sort_keys=True, separators=(",", ":"))` SHA-256 convention. Do not include a v1 discriminator in the v1 payload.
- [ ] `parse_kinematic_model` must inspect raw `schema_version`: absent or `kinematic-model@1` validates `KinematicModel`; exactly `kinematic-model@2` validates `KinematicModelV2`; any other value raises `ValueError`. The joint parser applies the analogous explicit rule. Existing concrete v1/v2 instances pass through only when their own discriminator is valid.
- [ ] Test body, member, and joint caller tuple reorder against both `model_dump(mode="json")` and `kinematic_model_hash`; test joint ID sensitivity separately from body/axis/limit sensitivity. Run the golden suite, v1 model tests in `tests/unit/test_multi_joint_kinematics.py`, and new schema mismatch/hash tests.

**Validation invariants:** No v1/v2 endpoint coexistence and no optional mixed-field constructor.

**Serialization/hash impact:** V2 emits schema/version fields. V1 emits exactly historical fields and uses the copied legacy hash branch.

**Legacy compatibility impact:** `KinematicModel` and `RevoluteJointModel` remain the v1 public import names and construction path.

**STOP conditions:** Any v1 JSON gains `schema_version`, a v1 hash payload changes, or a v2 model can be parsed/executed as v1.

**Exit criteria:** All golden values pass; v2 wire JSON and identity are canonical under body/member/joint input reorder and sensitive to joint ID, required version, body, member, endpoint, axis, and limit changes.

### Task 4: Validate V2 Assembly Membership and Home Agreement

**Purpose:** Fail closed before FK, exact measurement, or proof when a body model does not truthfully bind the source assembly.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_kinematics.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`

**New symbols:**
```python
def validate_v2_body_assembly_agreement(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
) -> dict[str, KinematicRigidBody]

def body_by_member_id(model: KinematicModelV2) -> dict[str, KinematicRigidBody]
```

- [ ] Write failing tests for unknown body members, extra members, missing assembly members, duplicated membership across bodies, duplicate body IDs, a reference offset mismatch, a meaningful non-reference offset mismatch, and a valid arbitrary-quaternion composed offset.
- [ ] Build `instance_by_id` from source assembly. Validate unique nonblank body IDs and complete equality between the declared member ID set and source assembly instance ID set. Reject unknown and omitted IDs with sorted diagnostics. Return a member-to-body map only after all coverage checks pass.
- [ ] For every member, compute `transform_compose(reference_instance.placement, member.reference_to_member_home)` and require `rigid_transform_agrees(source_member.placement, recomposed, RIGID_TRANSFORM_AGREEMENT_VERSION)`. Reject on `False`; do not mutate, round, or replace the declared offset.
- [ ] Run focused validation tests and Task 0 goldens.

**Validation invariants:** Every source constituent belongs to one and only one v2 body; no implicit fixed or ungrouped member exists.

**Serialization/hash impact:** None beyond the v2 body/model identities from Tasks 2-3.

**Legacy compatibility impact:** V1 does not call this helper.

**STOP conditions:** Any source-placement substitution, a tolerance other than the frozen policy, or deferred validation after FreeCAD invocation.

**Exit criteria:** All v2 integrity errors occur before the recording provider is called.

### Task 5: Add V2 Body Topology and Member-Expanded FK

**Purpose:** Compute body poses in the existing `MultiJointKinematicsService` and project them to every concrete CAD constituent.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_kinematics.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`
- Regression: `tests/unit/test_multi_joint_kinematics.py`

**New symbols:** `_KinematicBodyTopology`, `_build_v2_kinematic_topology(assembly: CadAssemblyProgram, model: KinematicModelV2) -> _KinematicBodyTopology`, `_detect_v2_cycles(model: KinematicModelV2) -> None`, `_evaluate_v1(assembly: CadAssemblyProgram, model: KinematicModel, configuration: JointConfiguration) -> KinematicForwardKinematicsResult`, and `_evaluate_v2(assembly: CadAssemblyProgram, model: KinematicModelV2, configuration: JointConfiguration) -> KinematicForwardKinematicsResult`. These remain private helpers called only by `MultiJointKinematicsService.evaluate`.

- [ ] Preserve `_build_kinematic_topology`, `_detect_cycles`, and the current v1 evaluation statements in `_evaluate_v1` without semantic rewrite. Dispatch with `isinstance(model, KinematicModelV2)` only after configuration and model-type validation.
- [ ] Make `_build_v2_kinematic_topology` validate joint IDs, parent/child body existence, parent != child, one incoming joint per child body, cycles, and reachability. Compute roots sorted by `body_id`; BFS child joints sorted by `joint_id`; mark articulated body IDs from incoming joints.
- [ ] In `_evaluate_v2`, first call `validate_v2_body_assembly_agreement`. Initialize `world_body[root_body_id]` from each root reference member home transform. Build `t_parent_child_home[joint_id]` from body reference homes with the existing inverse/compose helpers. Reuse `axis_rotation_transform` and existing composition order to calculate each child body pose.
- [ ] Project every source assembly instance, in original `assembly.instances` order, as `transform_compose(world_body[body_by_member[instance_id].body_id], member.reference_to_member_home)`. Set `InstanceWorldTransform.is_articulated` from whether its body has an incoming joint. Build the transformed assembly from those concrete placements only.
- [ ] Add the pre-return q=0 integrity gate for v2: when every supplied joint position is exactly `0.0`, call `rigid_transform_agrees` for every projected placement versus source placement and raise `ValueError` on failure. Do not require literal placement equality or equal source/transformed hashes.
- [ ] Test a two-member body, a three-member grouped root, R -> J1 -> A -> J2 -> B with two members in each body, and a branching body forest. Assert J1 moves all A/B members, J2 moves only B members, relative poses remain fixed under the policy, concrete output order equals source assembly order, and q=0 passes agreement while assembly hashes differ for an arbitrary quaternion round trip.
- [ ] Run `tests/unit/test_multi_joint_kinematics.py`, the new FK tests, and Task 0 goldens after this task.

**Validation invariants:** One `world_body` map, one existing FK service, concrete output only, roots/body BFS deterministic, and no compound or descendant solver.

**Serialization/hash impact:** v2 FK result uses the existing result shape but its evaluator/model hashes are v2-derived. V1 result JSON/hash must be unchanged.

**Legacy compatibility impact:** V1 ordering, roots, limits, multi-turn values, parent-instance axis frame, result values, and hashes remain on the preserved v1 path.

**STOP conditions:** q=0 passes only by source-placement substitution, any body has multiple articulated parents, a v1 test expectation changes, or a second FK engine is introduced.

**Exit criteria:** The grouped FK matrix and all current M10-2 tests pass.

### Task 6: Add the Neutral Exact Pair-Scope Primitive

**Purpose:** Define a reusable v2 concrete-pair selection input independent of articulation or physical authority.

**Files:**
- Create: `src/mechcad_harness/multi_joint_pair_scope.py`
- Modify: `src/mechcad_harness/multi_joint_kinematics.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`

**New symbols:**
```python
EXACT_CONSTITUENT_PAIR_SCOPE_VERSION = "exact-constituent-pair-scope@1.0"

class ExactConstituentPair(Model):
    schema_version: Literal["exact-constituent-pair@1"]
    first_instance_id: str
    second_instance_id: str

def canonical_exact_pair_scope(
    pairs: tuple[ExactConstituentPair, ...],
) -> tuple[ExactConstituentPair, ...]

def exact_pair_scope_hash(pairs: tuple[ExactConstituentPair, ...]) -> str

def validate_v2_exact_pair_scope(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
    exact_pair_scope: tuple[ExactConstituentPair, ...],
) -> tuple[ExactConstituentPair, ...]
```

- [ ] Write failing tests for reversed input normalization, caller tuple reorder equivalence, lexical order, self-pair, blank/whitespace ID, duplicate unordered pair, and empty scope rejection.
- [ ] In `ExactConstituentPair` before validation, lexically reorder the two supplied IDs. After validation, require both nonblank, require strict `first_instance_id < second_instance_id`, and serialize the schema version. In `canonical_exact_pair_scope`, reject duplicates by `(first_instance_id, second_instance_id)` then sort by that key.
- [ ] Hash a payload containing `exact_pair_scope_version` and the canonical serialized pairs. Do not import `CadAssemblyProgram`, FreeCAD, candidates, physical models, collision classification, or M13 modules.
- [ ] Implement `validate_v2_exact_pair_scope` in `multi_joint_kinematics.py`, not the neutral pair module, because it depends on `CadAssemblyProgram` and `KinematicModelV2`. Call `validate_v2_body_assembly_agreement`, compute `canonical = canonical_exact_pair_scope(exact_pair_scope)`, require `exact_pair_scope == canonical`, require both IDs in each pair to exist in the source assembly and in the returned member-to-body map, and reject pairs whose two mapped `body_id` values are equal. Return the verified canonical tuple. This is the only v2 pair-to-model/assembly validation implementation.
- [ ] Add recording-provider tests for an unknown first ID, unknown second ID, same-body pair, articulated-articulated cross-body pair, sibling cross-body pair, and ancestor/descendant cross-body pair. The three valid categories return their canonical scope; every invalid category raises before the provider callback.
- [ ] Run pair-scope tests, `tests/unit/test_transient_assembly_analysis.py`, `tests/unit/test_transient_freecad_measurement.py`, and Task 0 goldens.

**Validation invariants:** Pair operand order is non-semantic to v2 callers but deterministic before transient transport; cross-body validity has one generic implementation shared by M10-3 and M10-4.

**Serialization/hash impact:** V2-only schema and scope identity; no v1 request or result uses this helper.

**Legacy compatibility impact:** None.

**STOP conditions:** A scope imports policy/physical authority, silently drops duplicate/same-body data, uses moving/stationary labels, or a second M10-specific pair-membership validator is introduced.

**Exit criteria:** Canonical scope ordering and rejection behavior are fully unit tested.

### Task 7: Implement M10-3 V2 Request, Results, and Existing-Provider Dispatch

**Purpose:** Execute arbitrary cross-body concrete pairs without changing exact measurement or classification mathematics.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_collision_sweep.py`
- Modify: `src/mechcad_harness/transient_assembly_analysis.py`
- Modify: `src/mechcad_harness/transient_freecad_measurement.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`
- Regression: `tests/unit/test_multi_joint_collision_sweep.py`

**New symbols:**
```python
MULTI_JOINT_EXACT_COLLISION_SWEEP_V2_VERSION = "multi-joint-exact-collision-sweep@2.0"

class MultiJointCollisionSweepRequestV2(Model):
    schema_version: Literal["multi-joint-collision-sweep-request@2"]
    source_assembly_id: str
    source_assembly_hash: str
    model: KinematicModelV2
    configurations: tuple[JointConfiguration, ...]
    exact_pair_scope: tuple[ExactConstituentPair, ...]
    volume_tolerance_mm3: float = 1e-9
    distance_tolerance_mm: float = 1e-7
    evaluator_version: Literal["multi-joint-exact-collision-sweep@2.0"]
    model_hash: str = "pending"
    request_hash: str = "pending"

class ExactConstituentPairResultV2(Model):
    schema_version: Literal["exact-constituent-pair-result@2"]
    first_instance_id: str
    second_instance_id: str
    interference_volume_mm3: float
    exact_distance_mm: float
    classification: CollisionClassification

class MultiJointCollisionConfigurationResultV2(Model):
    schema_version: Literal["multi-joint-collision-configuration-result@2"]
    configuration_index: int
    configuration_hash: str
    transformed_assembly_hash: str
    ordered_joint_states: tuple[EvaluatedJointState, ...]
    instance_world_transforms: tuple[InstanceWorldTransform, ...]
    pair_results: tuple[ExactConstituentPairResultV2, ...]
    classification: CollisionClassification
    any_interference: bool
    any_touching: bool
    all_positive_clearance: bool
    minimum_exact_distance_mm: float

class MultiJointCollisionSweepResultV2(Model):
    schema_version: Literal["multi-joint-collision-sweep-result@2"]
    evaluator_version: Literal["multi-joint-exact-collision-sweep@2.0"]
    source_assembly_hash: str
    model_hash: str
    request_hash: str
    configuration_results: tuple[MultiJointCollisionConfigurationResultV2, ...]
    any_interference: bool
    any_touching: bool
    all_positive_clearance: bool
    collision_configuration_indices: tuple[int, ...]
    minimum_exact_distance_mm: float
    minimum_distance_configuration_index: int
    continuous_path_verified: Literal[False] = False
    result_hash: str = "pending"

def multi_joint_collision_sweep_result_v2_hash(
    result: MultiJointCollisionSweepResultV2,
) -> str
```

- [ ] Keep `MultiJointCollisionSweepRequest`, `MultiJointCollisionConfigurationResult`, and `MultiJointCollisionSweepResult` as literal v1 records. Add v2 classes rather than optional fields, and type `MultiJointDiscreteCollisionSweepService.execute` as accepting the explicit v1-or-v2 request union.
- [ ] Make the v2 request validator require the v2 FK evaluator, v2 sweep evaluator, at least one configuration, matching model IDs, finite nonnegative existing tolerances, canonical nonempty pair scope, and a model hash equal to `kinematic_model_hash(model)`. Canonicalize and persist its `exact_pair_scope` with `canonical_exact_pair_scope` in the request validator. Its hash payload must contain schema version, source ID/hash, model hash, ordered configuration hashes, canonical pair-scope hash, exact-pair-scope version, both tolerances, and `multi-joint-exact-collision-sweep@2.0`.
- [ ] In the v2 source validator, call `validate_v2_exact_pair_scope(assembly, request.model, request.exact_pair_scope)` before FK evaluation and before transient measurement. Do not duplicate unknown-ID, complete-membership, canonical-scope, or same-body checks here. Do not require a v2 scope to cover every assembly instance; exact measurement scope is explicitly caller-selected.
- [ ] Keep v1 `collision_pairs()` as its existing Cartesian product. Add `v2_collision_pairs()` returning `(pair.first_instance_id, pair.second_instance_id)` from the canonical scope. V2 must never call the v1 Cartesian helper.
- [ ] Convert each v2 transient tuple `(first_instance_id, second_instance_id, interference_volume_mm3, exact_distance_mm)` to `ExactConstituentPairResultV2`, preserving tuple order and calling unchanged `CollisionClassification.from_measurement`. Construct the explicit v2 configuration and sweep result records above. Keep v1 mapping to `CadKinematicCollisionPairResult` byte-for-byte.
- [ ] Give no nested v2 M10-3 record an intrinsic hash. Follow the current v1 outer-result convention: `multi_joint_collision_sweep_result_v2_hash` hashes one explicit JSON payload, serialized with `_digest`, containing exactly `schema_version`, `evaluator_version`, `source_assembly_hash`, `model_hash`, `request_hash`, ordered `configuration_results` serialized in request configuration order, `any_interference`, `any_touching`, `all_positive_clearance`, `collision_configuration_indices`, `minimum_exact_distance_mm`, `minimum_distance_configuration_index`, and `continuous_path_verified`. Every nested configuration result binds its transformed assembly hash, ordered joint states, ordered concrete transforms, and canonical-scope-ordered pair results through that enclosing payload.
- [ ] Rename only local tuple variables in `transient_assembly_analysis.py` and `transient_freecad_measurement.py` from `moving, stationary` to `first, second`; retain tuple field positions and existing emitted transient JSON keys `moving_instance_id` and `stationary_instance_id` so historical transient contracts do not change.
- [ ] Add tests for request hash sensitivity to scope changes, equal hash under caller scope reorder, same-body rejection before a recording provider call, unknown IDs, v2 result fields with no stationary label, v2 final result hash changes when pair identity or a configuration-result transformed-assembly hash changes, and v1 request/result goldens. A reordered non-semantic caller body/member/joint/pair input must produce the same canonical v2 final result hash; ordered request configurations remain semantic and retain their existing order-sensitive identity.
- [ ] Run focused M10-3 v2 tests, all current `tests/unit/test_multi_joint_collision_sweep.py`, transient unit tests, and Task 0 goldens.

**Validation invariants:** V2 flow is configuration -> existing FK -> complete transformed assembly -> canonical concrete pairs -> existing transient service/provider -> existing classification.

**Serialization/hash impact:** V2 records explicitly serialize schemas and neutral IDs. V1 classes and `_digest` payloads remain exact.

**Legacy compatibility impact:** Existing v1 directional partitions remain accepted only by the v1 request class.

**STOP conditions:** A v2 model reaches the Cartesian path, M10-3 common volume/distance/classification changes, a pair result names a second moving operand as stationary, or provider output is reimplemented.

**Exit criteria:** V2 M10-3 unit tests and all legacy M10-3 tests pass.

### Task 8: Prove the Articulated-Articulated M10-3 Path

**Purpose:** Close the concrete pair omission that motivated the prerequisite.

**Files:**
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`
- Regression: `tests/unit/test_multi_joint_collision_sweep.py`

**Fixture:** Six deterministic constituent IDs `R1`, `R2`, `A1`, `A2`, `B1`, `B2`; v2 bodies `R`, `A`, `B`; joints `J1: R -> A` and `J2: A -> B`; explicit scope contains canonical `ExactConstituentPair(A2, B1)` and a root/articulated pair.

- [ ] Use a recording `TransientAssemblyAnalysisService` callback that records `request.pairs`, verifies the transformed assembly carries both FK-derived placements, and returns deterministic positive-clearance and interference cases.
- [ ] Assert J1 changes A1/A2/B1/B2; J2 changes B1/B2 only; `A2/B1` reaches the callback exactly as `("A2", "B1")`; the v2 pair result uses `first_instance_id == "A2"` and `second_instance_id == "B1"`; and the unchanged classification is correct.
- [ ] Run this test with Task 7 focused tests, legacy M10-3 tests, and Task 0 goldens.

**Validation invariants:** Both endpoints have articulated ancestry, but articulation never partitions pair selection.

**Serialization/hash impact:** Confirms v2 result neutrality only.

**Legacy compatibility impact:** None; v1 Cartesian expectations remain tested separately.

**STOP conditions:** `A2/B1` is excluded because both move, a body ID replaces a constituent ID, or an internal pair partition is reintroduced.

**Exit criteria:** The recording provider proves the exact articulated-articulated pair reaches the unchanged transient boundary.

### Task 9: Add M10-4 V2 Request and Neutral Proof Records

**Purpose:** Allow explicit cross-body pair scope in continuous analysis while preserving the current proof algorithm and all v1 evidence shapes.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_continuous_path.py`
- Modify: `src/mechcad_harness/multi_joint_continuous_clearance.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`
- Regression: `tests/unit/test_multi_joint_continuous_path.py`, `tests/unit/test_multi_joint_continuous_clearance.py`, `tests/integration/test_m10_4_provenance.py`

**New symbols:**
```python
class MultiJointContinuousPathRequestV2(Model):
    schema_version: Literal["multi-joint-continuous-path-request@2"]
    source_assembly_id: str
    source_assembly_hash: str
    model: KinematicModelV2
    path: MultiJointPath
    exact_pair_scope: tuple[ExactConstituentPair, ...]
    required_clearance_mm: float = 0.0
    proof_guard_mm: float = 1e-6
    volume_tolerance_mm3: float = 1e-9
    distance_tolerance_mm: float = 1e-7
    max_depth: int = 16
    minimum_path_interval: float = 1e-6
    max_exact_evaluations: int = 4096
    model_hash: str = "pending"
    request_hash: str = "pending"

class ContinuousExactPairResultV2(Model):
    schema_version: Literal["continuous-exact-pair-result@2"]
    first_instance_id: str
    second_instance_id: str
    interference_volume_mm3: float
    exact_distance_mm: float
    classification: CollisionClassification

class ContinuousExactEvaluationV2(Model):
    schema_version: Literal["continuous-exact-evaluation@2"]
    evaluation_index: int
    location: ProofWitnessLocation
    configuration: JointConfiguration
    configuration_hash: str
    transformed_assembly_hash: str
    pair_results: tuple[ContinuousExactPairResultV2, ...]
    produced_requested_clearance_witness: bool

class ContinuousPairCertificateV2(Model):
    schema_version: Literal["continuous-pair-certificate@2"]
    first_instance_id: str
    second_instance_id: str
    exact_distance_mm: float
    motion_bound_A_mm: float
    motion_bound_B_mm: float
    pair_motion_bound_mm: float
    certified_lower_clearance_mm: float

class ContinuousIntervalCertificateV2(Model):
    schema_version: Literal["continuous-interval-certificate@2"]
    segment_index: int
    t_start: float
    t_end: float
    t_reference: float
    reference_configuration: JointConfiguration
    reference_configuration_hash: str
    transformed_assembly_hash: str
    reach_bound_algorithm_version: Literal["body-member-reach-bound-plumbing@2.0"]
    pair_certificates: tuple[ContinuousPairCertificateV2, ...]

class MultiJointContinuousCollisionWitnessV2(Model):
    schema_version: Literal["multi-joint-continuous-collision-witness@2"]
    location: ProofWitnessLocation
    configuration: JointConfiguration
    configuration_hash: str
    transformed_assembly_hash: str
    first_instance_id: str
    second_instance_id: str
    interference_volume_mm3: float
    exact_distance_mm: float
    classification: CollisionClassification

class ContinuousSegmentResultV2(Model):
    schema_version: Literal["continuous-segment-result@2"]
    segment_index: int
    certified_intervals: tuple[ContinuousIntervalCertificateV2, ...]
    unresolved_intervals: tuple[UnresolvedInterval, ...]

class ReachBoundRecordV2(Model):
    instance_id: str
    influencing_joint_id: str
    component_identity: str
    local_geometry_radius_mm: float
    offset_lengths_mm: tuple[float, ...]
    reach_bound_mm: float
    chain_body_ids: tuple[str, ...]
    algorithm_version: Literal["body-member-reach-bound-plumbing@2.0"]

class ReachBoundTableV2(Model):
    algorithm_version: Literal["body-member-reach-bound-plumbing@2.0"]
    extent_algorithm_version: str
    records: tuple[ReachBoundRecordV2, ...]

    def for_instance_joint(
        self, instance_id: str, joint_id: str,
    ) -> ReachBoundRecordV2 | None

class MultiJointContinuousClearanceProofResultV2(Model):
    schema_version: Literal["multi-joint-continuous-clearance-proof-result@2"]
    request_hash: str
    source_assembly_hash: str
    model_hash: str
    proof_algorithm_version: Literal["conservative-multi-joint-path-clearance-proof@1.0"]
    reach_bound_algorithm_version: Literal["body-member-reach-bound-plumbing@2.0"]
    status: MultiJointContinuousProofStatus
    segment_results: tuple[ContinuousSegmentResultV2, ...]
    certified_leaf_certificates: tuple[ContinuousIntervalCertificateV2, ...]
    unresolved_intervals: tuple[UnresolvedInterval, ...]
    collision_witness: MultiJointContinuousCollisionWitnessV2 | None
    reach_bounds: ReachBoundTableV2
    exact_evaluations: tuple[ContinuousExactEvaluationV2, ...]
    exact_evaluations_count: int
    cache_hits: int
    continuous_path_verified: bool
    minimum_certified_lower_clearance_mm: float | None
    result_hash: str = "pending"

def multi_joint_continuous_clearance_proof_result_v2_hash(
    result: MultiJointContinuousClearanceProofResultV2,
) -> str
```

- [ ] Keep all existing v1 request/result classes and their fields unchanged. V2 request fields omit both directional partitions and expose a `.pairs` property that projects the canonical exact scope to tuples.
- [ ] Make the v2 request validate the v2 model, path model ID and joint schema, existing limits/tolerances/resource fields, canonical scope, and its v2 reach-plumbing version. Canonicalize and persist its `exact_pair_scope` with `canonical_exact_pair_scope` in the request validator. Hash schema version, source identity, model hash, path hash, canonical scope hash, scope version, current tolerance/resource values, unchanged proof algorithm version, and the v2 reach-plumbing version.
- [ ] At the beginning of `MultiJointContinuousClearanceProofService.execute`, after existing source ID/hash validation and before extent lookup, reach-bound derivation, waypoint evaluation, recursive proof execution, or exact provider calls, branch only for `MultiJointContinuousPathRequestV2` and call `validate_v2_exact_pair_scope(assembly, request.model, request.exact_pair_scope)`. Use its returned canonical tuple for `pairs`. The v1 request path remains untouched. This is the same helper and error semantics used by M10-3 v2.
- [ ] Add v2 records with `first_instance_id` and `second_instance_id` for exact samples, certificates, and witness. `ContinuousIntervalCertificateV2` must carry `reach_bound_algorithm_version`; therefore each v2 certificate is bound to the same plumbing version as the request/result. `MultiJointContinuousClearanceProofResultV2` serializes `schema_version = "multi-joint-continuous-clearance-proof-result@2"` and retains concrete transforms, bounds, status, and result hash.
- [ ] Refactor only record factories inside `MultiJointContinuousClearanceProofService`: branch on request type to build v1 directional or v2 neutral records. Retain the same cache key components plus v2 pairs, exact calls, witness conditions, subdivision ordering, certificate lower bound, and success inequality.
- [ ] Give no nested v2 M10-4 record an intrinsic hash. Follow the current v1 outer-result convention: `multi_joint_continuous_clearance_proof_result_v2_hash` hashes one explicit `_digest` payload containing exactly `schema_version`, `request_hash`, `source_assembly_hash`, `model_hash`, `proof_algorithm_version`, `reach_bound_algorithm_version`, `status`, ordered `segment_results`, ordered `certified_leaf_certificates`, ordered `unresolved_intervals`, `collision_witness`, complete `reach_bounds`, ordered `exact_evaluations`, `exact_evaluations_count`, `cache_hits`, `continuous_path_verified`, and `minimum_certified_lower_clearance_mm`. Nested exact evaluations, certificates, witnesses, and reach records are serialized at full precision in that payload. Their order is deterministic from canonical pair scope and existing path/subdivision order; they receive no symmetry-only hashes.
- [ ] Add a `parse_multi_joint_continuous_result(payload)` helper which dispatches absent schema to the v1 result class and explicit v2 schema to the v2 result class. Use it later for evidence reload. Do not change `MultiJointPath` or `JointConfiguration` wire shape.
- [ ] Add recording-provider tests that unknown first ID, unknown second ID, and same-body pair each reject before extent-provider or exact-provider calls; articulated-articulated, sibling, and ancestor/descendant cross-body pairs are accepted and reach proof setup. Add final-result hash tests for pair identity changes, an exact-evaluation/certificate/witness transformed-assembly hash change, reach plumbing version change, and witness pair change. Assert non-semantic body/member/joint/pair caller reorder produces the same canonical v2 final result hash, while the v1 result hash/digest goldens remain unchanged. Run focused v2 request/result tests, all current M10-4 unit/provenance tests, and Task 0 goldens.

**Validation invariants:** The proof version stays `conservative-multi-joint-path-clearance-proof@1.0`; only request/result schema and reach input plumbing differ. Every v2 pair passes the one cross-body validation gate before proof work.

**Serialization/hash impact:** V2 request/result schemas and hashes are new. V1 request/result JSON, hash, moving/stationary labels, and proof version are unchanged.

**Legacy compatibility impact:** V1 continuous proof execution remains a separate type and path.

**STOP conditions:** Any continuous algorithm branch changes interpolation, midpoint selection, resource ceiling behavior, lower-bound math, or v1 result bytes; any v2 invalid pair reaches an extent/exact provider; or nested v2 records gain intrinsic hashes.

**Exit criteria:** V2 records are neutral and v1 M10-4 goldens/regressions remain green.

### Task 10: Add V2 Body-Member Reach-Bound Plumbing

**Purpose:** Derive conservative per-constituent v2 reach inputs for both sides of any pair without changing the existing bound equation.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_continuous_path.py`
- Modify: `src/mechcad_harness/multi_joint_continuous_clearance.py`
- Modify: `src/mechcad_harness/analysis_provenance.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`

**New symbols:**
```python
BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION = "body-member-reach-bound-plumbing@2.0"
def _v2_body_parent_chain(model: KinematicModelV2, body_id: str) -> list[RevoluteJointModelV2]
def _derive_v2_reach_bounds(
    assembly: CadAssemblyProgram,
    model: KinematicModelV2,
    extents: Mapping[str, TrustedLocalGeometryExtent],
) -> ReachBoundTableV2
```

- [ ] Keep the current v1 `_parent_chain` and `derive_reach_bounds` algorithm branch intact under `ARTICULATED_DESCENDANT_REACH_BOUND_VERSION`. Dispatch to `_derive_v2_reach_bounds` only for `KinematicModelV2`.
- [ ] For each concrete member extent, resolve its body, then the articulated body-joint ancestor chain. For each influencing joint, reuse the current telescoping terms expressed in body-reference frames and append the fixed terminal distance from the terminal body reference origin to `transform_apply(member.reference_to_member_home, (0.0, 0.0, 0.0))`. Keep `TrustedLocalGeometryExtent` keyed by the concrete member ID and keep `_BOUND_PADDING_MM` and `reach_bound_mm = local_radius + sum(offsets) + padding` unchanged.
- [ ] Emit the explicit `ReachBoundRecordV2` and `ReachBoundTableV2` records above with `algorithm_version = BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION`; retain the existing v1 classes and default version unchanged. Preserve the concrete member ID in every record and use body IDs only in `chain_body_ids` provenance.
- [ ] In proof construction, use the unchanged loop: derive an independent total for first endpoint, derive an independent total for second endpoint, set `relative = sum(body_bounds)`, and retain `distance - relative` and the existing proof guard inequality exactly.
- [ ] Add the optional `reach_bound_plumbing_version` field to `ContinuousProofExecutionProvenance`. Existing payloads omit it with the existing serializer behavior; v2 application evidence supplies `BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION`. The version is also hash-bound in the v2 request, final v2 result, and v2 interval certificate.
- [ ] Test root/articulated, ancestor/descendant, sibling bodies, and separate articulated branches. In every case assert both `motion_bound_A_mm` and `motion_bound_B_mm` are independently computed and pair bound equals their sum.
- [ ] Run focused reach tests, current M10-4 unit tests, provenance tests, and Task 0 goldens.

**Validation invariants:** No root/articulated special case, no geometry-derived offset, no double-count suppression for shared ancestry, and no new motion-bound formula.

**Serialization/hash impact:** V2 request/result/certificate/provenance explicitly bind `body-member-reach-bound-plumbing@2.0`; v1 retains `articulated-descendant-reach-bound@1.0` and exact bytes.

**Legacy compatibility impact:** Existing v1 reach-bound records and proof result hashes do not change.

**STOP conditions:** Any changed `B_A + B_B` mathematics, missing concrete local extent, a v2 result claiming the v1 version, or a change to v1 proof identity.

**Exit criteria:** All four pair topologies have conservative two-sided v2 bound coverage and v1 M10-4 tests pass.

### Task 11: Prove V2 M10-4 Two-Moving-Side Semantics

**Purpose:** Verify neutral continuous evidence and conservative proof execution for an articulated-articulated pair.

**Files:**
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`
- Regression: `tests/unit/test_multi_joint_continuous_clearance.py`

- [ ] Reuse the R/A/B six-constituent v2 fixture with `ExactConstituentPair(A2, B1)` and deterministic trusted extents for all concrete members.
- [ ] Use a recording exact callback that returns the requested canonical pairs and positive distance. Assert it receives `("A2", "B1")` at waypoints and subdivision samples, both endpoints have nonzero articulated ancestry where expected, v2 exact evaluations/certificates use only `first_instance_id`/`second_instance_id`, and `pair_motion_bound_mm == motion_bound_A_mm + motion_bound_B_mm`.
- [ ] Add a witness case using `required_clearance_mm` above the deterministic exact distance. Assert `MultiJointContinuousCollisionWitnessV2` retains `A2`/`B1`, not body IDs or a stationary label.
- [ ] Run focused tests, `tests/unit/test_multi_joint_continuous_clearance.py`, and Task 0 goldens.

**Validation invariants:** Exact pair identity is concrete and neutral; two moving sides do not change proof mathematics.

**Serialization/hash impact:** Validates the v2 result types introduced in Task 9.

**Legacy compatibility impact:** Existing directional v1 test `test_both_pair_sides_motion_is_recorded_in_relative_bound` remains unchanged.

**STOP conditions:** A false stationary field appears in v2, articulated-articulated pair scope is lost, or a proof branch is added for articulated endpoints.

**Exit criteria:** V2 clear and witness paths both prove neutral concrete identities and unchanged conservative arithmetic.

### Task 12: Add Explicit V2 Production APIs, Trusted Versions, and Result Reloading

**Purpose:** Expose unambiguous typed v2 construction paths while retaining exact v1 production APIs and provenance behavior.

**Files:**
- Modify: `src/mechcad_harness/application.py`
- Modify: `src/mechcad_harness/analysis_provenance.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`
- Modify: `tests/integration/test_m10_3_provenance.py`
- Modify: `tests/integration/test_m10_4_provenance.py`

**New `ProductionApplication` methods:**
```python
def analyze_multi_joint_collision_sweep_v2(
    self, *, source_revision: int, source_state_hash: str,
    assembly: CadAssemblyProgram, model: KinematicModelV2,
    configurations: tuple[JointConfiguration, ...],
    exact_pair_scope: tuple[ExactConstituentPair, ...],
) -> MultiJointCollisionSweepResultV2

def prove_continuous_multi_joint_path_clearance_v2(
    self, *, source_revision: int, source_state_hash: str,
    assembly: CadAssemblyProgram, model: KinematicModelV2,
    path: MultiJointPath, exact_pair_scope: tuple[ExactConstituentPair, ...],
    required_clearance_mm: float = 0.0, proof_guard_mm: float = 1e-6,
    max_depth: int = 16, minimum_path_interval: float = 1e-6,
    max_exact_evaluations: int = 4096,
) -> MultiJointContinuousClearanceProofResultV2
```

- [ ] Retain current `analyze_multi_joint_collision_sweep` and `prove_continuous_multi_joint_path_clearance` signatures as v1-only typed paths. Add the two v2 methods above; neither accepts directional partitions, evaluator overrides, provider overrides, or optional schema fields.
- [ ] Both v2 methods validate the same source binding and use the same composed provider/service construction as v1. Each constructs only its explicit V2 request type and publishes existing Evidence kinds with v2 request/result hashes.
- [ ] Extend trusted evaluator validation in M10-3 and M10-4 to accept only the exact v1/v2 model and service constants appropriate to the typed request. `evaluate_multi_joint_configuration` accepts `KinematicModelInput` and dispatches only through the existing `MultiJointKinematicsService`.
- [ ] Make `get_multi_joint_continuous_proof_result` use `parse_multi_joint_continuous_result` so a v2 evidence payload reloads as the v2 class and validates its correct result hash. Keep v1 reloads on the exact v1 class. Do not add a discrete-result lookup API: current M10-3 exposes only evidence lookup, so discrete v2 result parsing remains local to request execution and evidence serialization.
- [ ] Export the v2 M10 public types from their existing modules' `__all__` lists. Do not expand package-root `src/mechcad_harness/__init__.py`, which intentionally exports only M0 ID helpers.
- [ ] Test exact method signatures have no trusted caller overrides, v1 APIs reject v2 models, v2 APIs reject v1 models and directional fields, v2 evidence reloads, and v1 provenance/evidence payloads remain compatible.
- [ ] Run M10-3/M10-4 provenance suites and Task 0 goldens.

**Validation invariants:** Production composition retains provider ownership; callers choose explicit typed versioned APIs, not semantics through optional fields.

**Serialization/hash impact:** V2 provenance is bound through the existing request/result hashes and explicitly carries the new reach plumbing version for M10-4. Legacy optional provenance behavior remains unchanged.

**Legacy compatibility impact:** Existing v1 application callers and signatures remain valid and preserve their directional semantics.

**STOP conditions:** A public API infers v1/v2 from optional fields, permits caller-supplied trust identity, or changes a legacy evidence payload.

**Exit criteria:** All application/provenance tests pass for both typed request paths.

### Task 13: Close Historical Regression and Dependency-Firewall Coverage

**Purpose:** Demonstrate no M10 or M12 legacy regression and no M13 authority leak before expensive live acceptance.

**Files:**
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`
- Regression: `tests/unit/test_multi_joint_kinematics.py`
- Regression: `tests/unit/test_multi_joint_collision_sweep.py`
- Regression: `tests/unit/test_multi_joint_continuous_path.py`
- Regression: `tests/unit/test_multi_joint_continuous_clearance.py`
- Regression: `tests/unit/test_m12_candidate_m10_binding.py`
- Regression: `tests/integration/test_m10_3_provenance.py`
- Regression: `tests/integration/test_m10_4_provenance.py`
- Regression: `tests/integration/test_m10_5_system_acceptance.py`
- Regression: `tests/integration/test_transient_imported_multishape_collision.py`

- [ ] Add a source-import regression that parses imports from the five M13-3P production modules and asserts none starts with `mechcad_harness.candidates`, `mechcad_harness.models.physical_mechanism`, `mechcad_harness.supplied_component`, or `mechcad_harness.generated_part`.
- [ ] Add a regression that constructs M12 bindings containing identical `output_transform_group` metadata and proves generic v2 construction requires explicit `KinematicRigidBody` records; no M10 type imports or reads `CandidateM10BodyDisposition` or `output_transform_group`.
- [ ] Run the complete listed historical groups and the immutable Task 0 test after every future implementation task, not only at the end.
- [ ] Inspect the complete diff for protected regions: `axis_rotation_transform`, v1 `_build_kinematic_topology`, v1 `collision_pairs`, `CollisionClassification.from_measurement` use, `MultiJointPath.interpolate`, the proof recursion, and `distance - relative`. Changes outside version dispatch/record construction/reach input plumbing require review and rejection.

**Validation invariants:** v1 remains directional; `OUTPUT_RIGID` remains M12 metadata; no physical authority enters generic M10.

**Serialization/hash impact:** The golden suite protects every historical literal.

**Legacy compatibility impact:** This is the regression closure gate.

**STOP conditions:** Any v1 golden drift, required old expectation update, physical/candidate import, anonymous compound, fake joint, changed classification, or changed proof mathematics.

**Exit criteria:** All named historical groups pass without altered legacy assertions.

### Task 14: Run Focused Live FreeCAD Grouped-Body Acceptance

**Purpose:** Exercise generic v2 grouped FK, discrete exact collision, and continuous proof through the real FreeCAD transient provider.

**Files:**
- Create: `tests/integration/test_m13_3p_live_grouped_body_freecad.py`

**Fixture:** Generate one deterministic simple `CadPartProgram` plate and instantiate it as `R1`, `R2`, `A1`, `A2`, `B1`, `B2`. Construct v2 bodies `R=(R1 reference, R2)`, `A=(A1 reference, A2)`, `B=(B1 reference, B2)`, joints `J1: R -> A` and `J2: A -> B`, and explicit full-precision offsets whose assembly agreement passes the frozen policy. Use the real composed `FreeCADTransientAssemblyMeasurementProvider`; skip only when the repository's existing FreeCAD discovery gate says unavailable.

- [ ] At q=0, assert `rigid_transform_agrees` for all six transformed/source placements. Assert at least one projected transform differs literally and source/transformed assembly hashes differ, proving the test does not accidentally reintroduce literal/hash equality.
- [ ] Compare q=0, J1-only, J2-only, and combined configurations. Assert J1 moves A1/A2/B1/B2; J2 changes B1/B2 but not A1/A2; R1/R2 stay fixed; and `transform_inverse(A1) * A2` plus `transform_inverse(B1) * B2` agree with their source relative poses at every configuration.
- [ ] Execute `analyze_multi_joint_collision_sweep_v2` with a root/articulated pair and `A2/B1`; assert the real provider measures both canonical pairs, exact result pairs use neutral concrete IDs, and `A2/B1` is not omitted despite both bodies moving.
- [ ] Execute `prove_continuous_multi_joint_path_clearance_v2` twice for a path with J1/J2 changes and `A2/B1` scope: once with demonstrated clear clearance and once with `required_clearance_mm` above the measured distance. Assert both results use the unchanged proof version and carry `BODY_MEMBER_REACH_BOUND_PLUMBING_VERSION`; assert the witness result contains only `first_instance_id == "A2"` and `second_instance_id == "B1"`.
- [ ] Run this file with the documented FreeCAD/gear prerequisites, then run Task 0 goldens.

**Validation invariants:** The fixture is generic M10/CAD only, contains no candidate, canonical, physical, promotion, M13-3, M11, or Rotator semantics.

**Serialization/hash impact:** Produces v2-only evidence; source assembly immutability remains asserted.

**Legacy compatibility impact:** Existing live M10-3/M10-4/M10-5 fixtures remain unchanged and run in Task 15.

**STOP conditions:** A required positive v2 path is skipped with available runtime, FreeCAD pair measurement is replaced with a stub, `A2/B1` is missing, or any fixture introduces physical authority.

**Exit criteria:** All six live acceptance claims pass against the real provider.

### Task 15: Full Verification and Completion Report

**Purpose:** Establish acceptance evidence and document the bounded generic M10 foundation for later M13-3 consumption.

**Files:**
- Create: `docs/audit/MECHCAD_M13_3P_COMPLETION_REPORT.md`

- [ ] Run staged verification in this order, running `py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v` after every task and every stage:
  - Stage A: Task 0 goldens, transform agreement, v2 model records.
  - Stage B: body membership/home validation, topology, FK expansion, q=0 agreement.
  - Stage C: exact pair scope and M10-3 v2 execution.
  - Stage D: M10-4 v2 neutral records and body-member reach plumbing.
  - Stage E: all historical M10/M12/transient groups listed in Task 13.
  - Stage F: `tests/integration/test_m13_3p_live_grouped_body_freecad.py`.
  - Stage G: `py -3 -m pytest tests/` with a timeout of at least 4500 seconds.
- [ ] Record full-suite collected, passed, skipped, failed, errors, elapsed time, Python version, and pytest version. Acceptance requires zero failures, zero errors, and no required positive M13-3P test skipped.
- [ ] Run `py -3 -m compileall -q src/mechcad_harness tests`, `git diff --check`, `rg -n "[ \t]+$"` over changed files, and a Python final-newline check over every changed text file. Inspect `git status --short`, `git diff --stat`, and the complete relevant diff.
- [ ] Verify no changed file adds M13 physical authority, M11, Rotator code, dependencies, an alternative FK/collision/proof, a compound, or fake joints.
- [ ] Write the completion report only after all checks pass. Include the final marker `M13_3P_GENERIC_M10_RIGID_BODY_CONSTITUENT_GROUP_VERIFIED`, exact files changed, v1 golden evidence, frozen agreement algorithm/thresholds, v2 body/member model, q=0 evidence, grouped hierarchy, exact scope, articulated-articulated M10-3 result, two-moving-side M10-4 result, concrete witnesses, live runtime/provenance, historical regression outcomes, full suite, compileall, diff checks, dependency firewall, remaining M13-3 handoff, and known boundaries.

**Validation invariants:** The success marker is emitted only after every Task 0-15 exit criterion and all static/live/full-suite gates pass.

**Serialization/hash impact:** Final evidence must explicitly state no v1 JSON/hash drift.

**Legacy compatibility impact:** Final gate re-runs all preserved M10 paths.

**STOP conditions:** Any required check failure, skipped positive v2 route, v1 golden drift, or Critical/Important review finding. Stop and repair; do not relax the approved architecture.

**Exit criteria:** Completion report exists and every success-marker gate is demonstrated.

## Staged Regression Commands

Run these in addition to the focused task commands:

```powershell
py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v
py -3 -m pytest tests/unit/test_multi_joint_kinematics.py tests/unit/test_multi_joint_collision_sweep.py -v
py -3 -m pytest tests/unit/test_multi_joint_continuous_path.py tests/unit/test_multi_joint_continuous_clearance.py -v
py -3 -m pytest tests/unit/test_transient_assembly_analysis.py tests/unit/test_transient_freecad_measurement.py -v
py -3 -m pytest tests/unit/test_m12_candidate_m10_binding.py -v
py -3 -m pytest tests/integration/test_m10_3_provenance.py tests/integration/test_m10_4_provenance.py tests/integration/test_m10_5_system_acceptance.py -v
py -3 -m pytest tests/integration/test_transient_imported_multishape_collision.py -v
py -3 -m pytest tests/integration/test_m13_3p_live_grouped_body_freecad.py -v
py -3 -m pytest tests/  # timeout >= 4500 seconds
py -3 -m compileall -q src/mechcad_harness tests
git diff --check
```

## Plan Self-Review

- Model strategy is fixed: current public `KinematicModel`/`RevoluteJointModel` are v1 compatibility classes; `KinematicModelV2`/`RevoluteJointModelV2` are explicit v2 classes; parser/hash/serializer dispatch is named and version-driven.
- V1 schema fields are in-memory only and omitted by explicit v1 serializers; v1 hashes use the current copied payload branch.
- Transform comparison is fixed to the named shared-normalizer algorithm and constants. No worker selects an epsilon, quaternion convention, rounding, or literal q=0 equality.
- Full-precision member offsets are persisted/hash-bound and checked only against source placement through the fixed agreement predicate.
- Body membership is complete and unique; topology is body-level only for v2; v1 topology/FK remains on its own path. V2 body, member, and joint tuples are persisted in body-ID, member-ID, and joint-ID canonical order respectively.
- V2 joint identity is hash-bound through its complete frozen payload, including `joint_id`; a joint rename changes `kinematic_model_hash` even when endpoints, axis, and limits do not change.
- V2 pair scope is canonical, hash-bound, neutral, and rejects same-body pairs without deleting higher-level inventory data. The one `validate_v2_exact_pair_scope` helper performs all source/member/cross-body checks before either M10-3 provider work or M10-4 extent/proof work.
- M10-3 retains current transient exact measurement and classification; M10-4 retains its proof algorithm and independently sums both endpoint bounds.
- V2 final result hashes are outer-record-only SHA-256 `_digest` payloads with explicitly listed fields; nested records have no intrinsic hashes and are bound through deterministic enclosing serialized content.
- V2 witnesses name concrete constituent IDs, not bodies or directional moving/stationary labels.
- The dependency firewall and `OUTPUT_RIGID` regression prevent M13/M12 semantics from becoming generic M10 authority.
- The implementation plan does not resume M13-3, create M13-4 behavior, or modify M11/Rotator scope.
