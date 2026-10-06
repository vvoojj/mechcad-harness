# Task 2: Add Rigid-Body Member and Body Records

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

- Write failing tests for blank/whitespace IDs, empty members, duplicate members, missing reference member, duplicate reference member, non-identity reference offset, canonical member ordering, and body-hash sensitivity to ID, reference member, member membership, and exact offset values.
- Validate nonblank `body_id`, `reference_member_instance_id`, and `member_instance_id` with a shared local `_require_nonblank_kinematic_id(value, label)` helper. Canonicalize the persisted `members` tuple by `member_instance_id` with `object.__setattr__`; reject duplicates before sorting. Require the reference member to occur exactly once and its declared offset to be literal `CadRigidTransform()` equality, not the agreement predicate.
- Define the body hash payload as `schema_version`, `body_id`, `reference_member_instance_id`, and canonical `members`, with each member serialized as `member_instance_id` plus the unrounded `CadRigidTransform.model_dump(mode="json")`. Derive/verify `body_hash` in the after validator, excluding `body_hash` from its own payload.
- Run focused body tests and Task 0 goldens.

**Validation invariants:** Member offsets are explicit, persisted at full precision, and never derived from assembly geometry or source placement.

**Serialization/hash impact:** New v2-only records; v1 serializer and hashes do not observe these types.

**Legacy compatibility impact:** None.

**STOP conditions:** A member silently belongs to more than one body, an offset is inferred, a body is represented by a compound, or a reference offset is accepted by tolerance instead of literal identity.

**Exit criteria:** Body records canonicalize deterministically and fail closed for every listed malformed record.
