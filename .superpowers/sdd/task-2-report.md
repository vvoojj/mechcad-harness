# M13-3P Task 2 Report

## Scope

Implemented Task 2 only: explicit generic M10 rigid-body member and body
records in the existing `multi_joint_kinematics` module, with focused unit
coverage. No FK, model versioning, topology, assembly validation, pair scope,
collision, or continuous-proof behavior was changed.

Production file:

- `src/mechcad_harness/multi_joint_kinematics.py`

Test file:

- `tests/unit/test_m13_3p_rigid_body_groups.py`

Report file:

- `.superpowers/sdd/task-2-report.md`

## Implementation

Added `KinematicRigidBodyMember` with:

- nonblank `member_instance_id` validation through the shared local
  `_require_nonblank_kinematic_id(value, label)` helper;
- explicit `reference_to_member_home: CadRigidTransform` storage.

Added `KinematicRigidBody` with:

- literal schema version `kinematic-rigid-body@1`;
- nonblank `body_id` and `reference_member_instance_id` validation through the
  same helper;
- rejection of empty members;
- duplicate member rejection before sorting;
- exactly-one reference-member membership validation;
- literal `CadRigidTransform()` equality for the reference member offset;
- deterministic persisted member ordering by `member_instance_id` using
  `object.__setattr__`;
- derived or verified `body_hash` in the after validator.

Added `kinematic_rigid_body_hash`, whose payload contains only
`schema_version`, `body_id`, `reference_member_instance_id`, and canonical
members. Each member includes its ID and unrounded
`reference_to_member_home.model_dump(mode="json")`; `body_hash` is excluded
from the payload.

## TDD Evidence

### RED

Added the Task 2 tests before adding the production records. The focused run
failed during collection because the requested symbols were absent:

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -k rigid_body -v
ImportError: cannot import name 'KinematicRigidBody'
```

### GREEN

After the minimal implementation, the same focused run passed:

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -k rigid_body -v
26 passed in 0.65s
```

The focused file also retains and passes all Task 1 transform-agreement tests:

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -v
26 passed in 0.68s
```

Coverage includes blank and whitespace IDs, empty members, duplicate members,
missing and duplicate reference membership, non-identity reference offsets,
canonical member ordering, hash derivation and mismatch rejection, and hash
sensitivity to body ID, reference member, membership, and exact offset values.

## Required Regression

The immutable Task 0 golden suite passed without changing any golden literal:

```text
py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v
5 passed in 0.67s
```

This preserves the existing v1 JSON, v1 hashes, FK results, collision records,
continuous-path records, and version literals.

## Worktree and Commit Policy

- No commit, tag, push, release, reset, stash, clean, checkout, revert, or
  discard was performed.
- Existing unrelated modified and untracked worktree contents were preserved.
- Only the requested kinematics module, focused test file, and requested report
  were changed by this task.

## Concerns

- The RED evidence is an expected import-time failure because this task adds
  new public symbols; no production implementation existed before the tests.
- Broader v2 model integration, source-assembly agreement, body topology, FK
  projection, pair scopes, and M10-3/M10-4 support remain later task scope.

## Review Finding Fix: Content-Addressed Record Immutability

### RED

Added adversarial tests for post-construction mutation of member IDs, member
offset fields, body IDs, reference membership, canonical members, and
`body_hash`. The tests also attempt nested offset mutation and mutation of the
caller-owned offset object after member construction.

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -k 'mutation_cannot' -q
2 failed, 26 deselected
```

The expected failure was that mutable member/body assignments did not raise.

### GREEN

The minimal fix freezes both content-addressed records and stores each member
offset as a detached frozen `CadRigidTransform` subtype. The subtype retains
field-wise equality with `CadRigidTransform`, preserving the literal identity
validation rule without changing the v1 transform model.

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -k 'mutation_cannot' -q
2 passed, 26 deselected
```

### Required Verification

```text
py -3 -m pytest tests/unit/test_m13_3p_rigid_body_groups.py -q
28 passed in 0.65s

py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -q
5 passed in 0.73s
```

No captured golden literal was modified. The existing v1 models and hashes
remain unchanged.

### Concerns

- The private frozen transform subtype is required because Pydantic's frozen
  model setting is shallow; without it, nested offset mutation would still
  alter the body hash payload.
- The complete repository suite was not run; the two requested focused suites
  passed.
