# Task 3: Version Kinematic Models and Revolute Joints Without V1 Drift

**Purpose:** Make v1 and v2 schema selection explicit and non-ambiguous before topology or execution changes.

**Files:**
- Modify: `src/mechcad_harness/multi_joint_kinematics.py`
- Modify: `tests/unit/test_m13_3p_legacy_goldens.py`
- Modify: `tests/unit/test_m13_3p_rigid_body_groups.py`

**Exact classes and helpers:**
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

- Add failing tests that an absent discriminator parses to the v1 classes, v1 `model_dump_json()` remains byte-identical, v2 requires its explicit discriminator, v1 rejects bodies/body endpoint fields, v2 rejects instance endpoint fields, a changed agreement version changes v2 model identity, and identical v2 topology with `joint_id="J1"` versus `joint_id="JX"` changes `kinematic_model_hash`.
- Use `@model_serializer(mode="wrap")` on the two v1 classes. Let the handler serialize normal fields, then remove only their in-memory `schema_version`; nested v1 joint serialization must also omit it. Do not use `exclude_none` for compatibility.
- Canonicalize persisted v2 tuples in their own after validators with `object.__setattr__`: `KinematicRigidBody.members` sorted by `member_instance_id`; `KinematicModelV2.bodies` sorted by `body_id`; and `KinematicModelV2.joints` sorted by `joint_id`. Reject duplicate body IDs and duplicate joint IDs before sorting. Do not canonicalize v1 tuples.
- Make `v2_revolute_joint_wire_payload` return exactly this ordered semantic mapping for every v2 joint: `schema_version`, `joint_id`, `joint_kind`, `parent_body_id`, `child_body_id`, `axis_origin_x_mm`, `axis_origin_y_mm`, `axis_origin_z_mm`, `axis_direction_x`, `axis_direction_y`, `axis_direction_z`, `min_angle_deg`, and `max_angle_deg`. Its source is the normalized in-memory joint fields; no endpoint aliasing or omitted `joint_id` is permitted.
- Keep the exact current v1 hash payload branch verbatim in `kinematic_model_hash`. Make its v2 branch hash a payload containing `schema_version`, `model_id`, `evaluator_version`, `transform_agreement_version`, `bodies` as canonical body hashes in persisted body order, and `joints` as `v2_revolute_joint_wire_payload(joint)` in persisted joint-ID order. Serialize that payload with the existing `json.dumps(..., sort_keys=True, separators=(",", ":"))` SHA-256 convention. Do not include a v1 discriminator in the v1 payload.
- `parse_kinematic_model` must inspect raw `schema_version`: absent or `kinematic-model@1` validates `KinematicModel`; exactly `kinematic-model@2` validates `KinematicModelV2`; any other value raises `ValueError`. The joint parser applies the analogous explicit rule. Existing concrete v1/v2 instances pass through only when their own discriminator is valid.
- Test body, member, and joint caller tuple reorder against both `model_dump(mode="json")` and `kinematic_model_hash`; test joint ID sensitivity separately from body/axis/limit sensitivity. Run the golden suite, v1 model tests in `tests/unit/test_multi_joint_kinematics.py`, and new schema mismatch/hash tests.

**Validation invariants:** No v1/v2 endpoint coexistence and no optional mixed-field constructor.

**Serialization/hash impact:** V2 emits schema/version fields. V1 emits exactly historical fields and uses the copied legacy hash branch.

**Legacy compatibility impact:** `KinematicModel` and `RevoluteJointModel` remain the v1 public import names and construction path.

**STOP conditions:** Any v1 JSON gains `schema_version`, a v1 hash payload changes, or a v2 model can be parsed/executed as v1.

**Exit criteria:** All golden values pass; v2 wire JSON and identity are canonical under body/member/joint input reorder and sensitive to joint ID, required version, body, member, endpoint, axis, and limit changes.
