# MechCAD M2 Git Reconstruction Report

## 1. Verdict

```text
M2_CAPABILITY_EXISTENCE: YES
M2_RECONSTRUCTION_STATUS: M2_SHARED_COMMIT_WITH_M1
M2_IMPLEMENTATION_STATUS: IMPLEMENTED_WITH_DEVIATIONS
M2_VERIFICATION_STATUS: HISTORICALLY_UNVERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
```

M2's core controlled canonical-state mutation boundary was implemented in the
shared M1/M2 commit. Retained history does not independently prove successful
historical test or final-verification execution.

## 2. Commit Boundary

```text
M0_COMMIT: 7185351d40c3cfe588c9f2c43ba3e2bc1f9e603f
M1_M2_SHARED_START_COMMIT: 37f3ff3ea143400adb460e4650e1b580a4f1488d
M2_START_COMMIT: 37f3ff3ea143400adb460e4650e1b580a4f1488d
M2_IMPLEMENTATION_RANGE: 37f3ff3ea143400adb460e4650e1b580a4f1488d only
M2_COMPLETION_TREE: 37f3ff3ea143400adb460e4650e1b580a4f1488d
M3_START_COMMIT: df584f00b240ef8086b99d408f76f42a90c4b517
```

`37f3ff3` is the only retained M2 implementation commit. Its completion-tree
classification is inferred from the implementation state; no dedicated M2
completion marker exists. `df584f0` immediately follows it, so no intermediate
M2 completion or repair commit exists.

## 3. Artifact Inventory

### Design / Spec

- `docs/superpowers/specs/2026-08-18-mechcad-m2-changeset-design.md`
- First commit: `37f3ff3`
- Role: contemporary original M2 design and scope contract.

### Implementation Plan

- `docs/superpowers/plans/2026-08-18-mechcad-m2-changeset.md`
- First commit: `37f3ff3`
- Role: contemporary implementation and verification plan.
- All 19 plan checkboxes remain unchecked.

### README / Historical Documentation

- `README.md` was created in M0; its M2 section was added in `37f3ff3`.
- `config/ownership.yaml` was created in M0; M2 rules were added in `37f3ff3`.
- Later architecture and audit documentation is retrospective evidence, not an
  original M2 completion record.

### Implementation / Test Evidence

- `src/mechcad_harness/changes/__init__.py`
- `src/mechcad_harness/changes/engine.py`
- `src/mechcad_harness/changes/errors.py`
- `src/mechcad_harness/changes/operations.py`
- `src/mechcad_harness/changes/ownership.py`
- `tests/unit/test_changes.py`

All first appear in `37f3ff3`.

### Completion / Acceptance

No dedicated completion report, acceptance report, M2 marker, tag, Git note,
CI artifact, or terminal transcript was found. Git history searches for
`MECHCAD_M2` and `M2.*COMPLETE` found no M2 completion record.

## 4. Shared M1/M2 Commit Partition

```text
37f3ff3
|- M1 State Foundation
`- M2 ChangeSet Foundation
```

### M1-Owned Changes

- `src/mechcad_harness/state/__init__.py`
- `src/mechcad_harness/state/errors.py`
- `src/mechcad_harness/state/hashing.py`
- `src/mechcad_harness/state/manager.py`
- `tests/unit/test_state_foundation.py`

These establish canonical JSON/hash identity, immutable revisions,
`current.json`, and persistence integrity.

### M2-Owned Changes

- `config/ownership.yaml`
- `docs/superpowers/plans/2026-08-18-mechcad-m2-changeset.md`
- `docs/superpowers/specs/2026-08-18-mechcad-m2-changeset-design.md`
- `src/mechcad_harness/changes/__init__.py`
- `src/mechcad_harness/changes/engine.py`
- `src/mechcad_harness/changes/errors.py`
- `src/mechcad_harness/changes/operations.py`
- `src/mechcad_harness/changes/ownership.py`
- `tests/unit/test_changes.py`

### Shared / Integration Changes

- `src/mechcad_harness/models/proposal.py`
- `src/mechcad_harness/models/__init__.py`
- `README.md`

```text
M2 mutation validation
        ↓
M1 immutable revision persistence
```

M2 validates and prepares the candidate. M1 persists the canonical revision.

## 5. Intended M2 Architecture

The contemporary design and plan intended:

```text
ChangeProposal
-> stale base revision/hash check
-> operation validation
-> ownership check
-> in-memory ChangeSet application
-> Pydantic DesignState validation
-> StateManager.create_revision()
```

They specified add, replace, and remove operations; literal JSON-Pointer-like
paths; fail-closed ownership; and exclusion of dependency invalidation,
orchestration, CAD, FEA, evidence storage, databases, and conflict resolution.
This is intent evidence, not execution proof.

## 6. Actual M2 Mutation Pipeline

`ChangeEngine.apply_proposal()` in `changes/engine.py` performed:

```text
_read_current()
-> compare base_revision and base_state_hash
-> load_current_state()
-> JSON copy of DesignState payload
-> for each operation:
     ownership_policy.check()
     apply_operation()
-> DesignState.model_validate(payload)
-> construct ChangeSet (discarded)
-> StateManager.create_revision()
-> RevisionSnapshot
```

Responsible symbols include `ChangeEngine.apply_proposal`, `apply_operation`,
`_segments`, `_resolve_parent`, `_get_value`, `_find_item`, `ChangeOperation`,
`OperationType`, `OwnershipPolicy`, the change error hierarchy, and
`StateManager.create_revision`.

## 7. ChangeProposal Model and Binding

Historical fields:

```text
revision
state_hash
id
title
status
base_revision
base_state_hash
actor
operations
```

`ProposalStatus` values were `draft`, `accepted`, and `rejected`. Pydantic
models were not frozen. Proposals had no direct `DesignState` mutation API.

`apply_proposal()` did not inspect proposal status. Therefore draft, accepted,
and rejected proposals could structurally reach application if other checks
passed. This is `IMPLEMENTED_DIFFERENTLY`.

Compatibility validators copied legacy `revision`/`state_hash` values into base
binding fields, defaulted actor to `legacy`, and defaulted operations to `[]`.
This weakened the intended explicit, fail-closed binding contract and is
`IMPLEMENTED_DIFFERENTLY`.

## 8. Stale Revision / Hash Protection

`apply_proposal()` first read `current.json` and compared both proposal base
fields. A revision mismatch or a correct revision with a wrong hash raises
`StaleProposalError` before state loading, candidate work, or persistence.

```text
STALE_PROTECTION: FAIL_CLOSED
```

`test_stale_revision_and_hash_are_rejected` directly covers both mismatch
forms. No project-wide lock existed across stale checking and revision creation
in M2; later locking is not retroactively M2 behavior.

## 9. Ownership Model

Historical production rules:

```text
/requirements                    -> mechcad-requirements
/materials                       -> mechcad-materials
/components/*/transmission       -> mechcad-transmission
/components/*/placement          -> mechcad-packaging
```

`OwnershipPolicy.from_file()` used a narrow line-oriented parser. Matching was
prefix-based over literal segments and one-segment wildcards. More literal
segments won; equal-specificity resolution was incidental tuple ordering, not
an explicit ambiguity policy. No match and wrong actor raised
`OwnershipViolationError`.

Tests use an in-memory broad component rule rather than the shipped config.
There is no retained file-loader, malformed-config, or production-rule test.

```text
OWNERSHIP_CONFIG_LOADING: PARTIAL
```

## 10. ChangeOperation and Path Semantics

`OperationType` supports `add`, `replace`, and `remove`. `ChangeOperation`
contains `operation`, `path`, `value`, and `expected`.

- Paths must start with `/`; root mutation, empty segments, and any `~` fail.
- The implementation is not RFC 6901: it has no escape interpretation.
- Dictionary keys are literal.
- Lists are traversed through dictionary item `id`, never numeric indexes.
- Missing parent/final paths raise `InvalidChangePathError`.
- `add` adds a missing dictionary key or appends a list item.
- `replace` and `remove` require an existing target.
- Duplicate add conflicts; duplicate replace is sequentially allowed; a second
  remove fails.
- Operations are sequential against one candidate.
- `expected` is checked only when non-`None`, so expected-null is impossible.
- List add does not bind the final path ID to the payload item's `id`.

## 11. ChangeSet Validation and Atomicity

Operations mutate an isolated JSON copy. An invalid later operation prevents
Pydantic validation and `create_revision()`, so partial candidate work does not
reach canonical persistence. A successful proposal calls `create_revision()`
once.

`test_previous_snapshot_is_unchanged_and_multiple_operations_are_atomic` and
`test_failed_operation_does_not_create_revision_or_move_pointer` cover this
semantic atomicity.

The implementation is not a filesystem-wide transaction. `StateManager` writes
the new snapshot before `current.json`; a pointer-write failure could leave an
orphan snapshot. Retained tests cover snapshot-write failure, not pointer-write
failure.

## 12. Resulting DesignState Validation

The complete candidate is checked through:

```python
DesignState.model_validate(payload)
```

The historical base `Model` used `ConfigDict(extra="forbid")`; Pydantic field
constraints and UTC-aware timestamp validation apply. Pydantic failures become
`ChangeSetValidationError`. `test_result_is_pydantic_revalidated` covers this
boundary. The resulting revision is harness-controlled because
`StateManager.create_revision()` assigns the next revision.

## 13. M1 StateManager Integration

On success, M1 reads the pointer and current state, determines the next revision
and parent revision, computes the hash, writes an immutable snapshot, and moves
`current.json`. M2 owns authorization and candidate validity; M1 owns durable
canonical revision mechanics.

## 14. Failed ChangeSet Behavior

| Failure class | Historical behavior |
| --- | --- |
| Stale revision/hash | No candidate persistence; pointer unchanged |
| Ownership violation | No candidate persistence; pointer unchanged |
| Invalid/missing path | No candidate persistence; pointer unchanged |
| Pydantic-invalid candidate | No candidate persistence; pointer unchanged |
| Snapshot write failure | Tested: pointer unchanged |
| Pointer write failure | Untested; orphan snapshot possible |

The README claim is supported for validation failures and snapshot-write
failure, but is not fully proven for every persistence failure.

## 15. ChangeSet / Application Result Records

Historical `ChangeSet` fields were:

```text
id
proposal_id
base_revision
base_state_hash
actor
status
operations
```

It had no `created_at`, was not persisted, and was not returned. M2 returned a
`RevisionSnapshot`. `df584f0` later added an ephemeral `AppliedChangeResult`
for M3 integration; it is not a durable M2 application record.

```text
CHANGESET_RECORD_STATUS: PARTIAL
```

## 16. Canonical Authority Boundary

```text
Proposal != Canonical State
ChangeSet != Canonical State
Result != Canonical State

Validated persisted DesignState revision = Canonical State
```

Only `StateManager` creates canonical revisions. M2 exposes no caller snapshot
write path and checks ownership per operation. Proposal and ChangeSet records
are not `DesignState` fields.

## 17. Historical M2 Tests

```text
M2_TEST_FILES: tests/unit/test_changes.py
M2_TEST_COUNT: 8
TEST_CODE_PRESENT: YES
HISTORICAL_TEST_EXECUTION_STATUS: NOT_PROVEN
```

Proposal/revision creation:
- `test_replace_add_and_remove_create_revisions`

Stale protection:
- `test_stale_revision_and_hash_are_rejected`

Ownership:
- `test_unowned_and_wrong_owner_paths_fail`

Operations and paths:
- `test_replace_add_and_remove_create_revisions`
- `test_missing_replace_and_remove_paths_fail`

Atomicity/pointer stability:
- `test_previous_snapshot_is_unchanged_and_multiple_operations_are_atomic`
- `test_failed_operation_does_not_create_revision_or_move_pointer`

Resulting-state validation:
- `test_result_is_pydantic_revalidated`

Boundary separation:
- `test_constraint_request_is_not_an_operation`

The M1-owned supporting file `tests/unit/test_state_foundation.py` has seven
tests. The full shared-boundary unit tree had 21 tests in four files. Test code
does not prove historical execution.

## 18. Design vs Plan vs Actual Implementation

| Requirement | Design | Plan | Actual Git | Test Evidence | Classification |
| --- | --- | --- | --- | --- | --- |
| Stale revision/hash rejection | Required | Required | Implemented before candidate work | Direct | IMPLEMENTED_AS_DESIGNED |
| Add/replace/remove | Required | Required | Implemented | Direct | IMPLEMENTED_AS_DESIGNED |
| Literal ID-addressed paths | Required | Required | Implemented without RFC escaping | Partial | IMPLEMENTED_AS_DESIGNED |
| Fail-closed ownership | Required | Required | Implemented | Fixture-only | IMPLEMENTED_AS_DESIGNED |
| Config ownership loading | Required | Required | Narrow parser | No loader test | PARTIAL |
| In-memory complete validation | Required | Required | Sequential candidate application | Direct | IMPLEMENTED_AS_DESIGNED |
| Resulting DesignState validation | Required | Required | `model_validate` | Direct | IMPLEMENTED_AS_DESIGNED |
| One persistence call | Required | Required | `create_revision` once | Indirect | IMPLEMENTED_AS_DESIGNED |
| Explicit required binding | Required | Required | Legacy defaults/synthesis | No direct binding test | IMPLEMENTED_DIFFERENTLY |
| ChangeSet record contract | Required | Required | No timestamp; discarded | None | PARTIAL |
| Durable application record | Implied | Planned fields | None | None | MISSING |
| All persistence-failure guarantee | Required | Required | Pointer-write case untested | Partial | PARTIAL |
| Proposal status gate | Not explicit | Not explicit | No gate | None | IMPLEMENTED_DIFFERENTLY |

## 19. Historical Verification Evidence

```text
pytest: NOT_PROVEN
compileall: NOT_PROVEN
git diff --check: NOT_PROVEN
completion marker: NOT_FOUND
completion report: NOT_FOUND
acceptance: NOT_FOUND
CI/audit: NOT_FOUND
```

The plan requested pytest, compileall, `git diff --check`, and a final
inspection, but all plan checkboxes are unchecked. No current tests were run
for this historical determination.

## 20. Completion Classification

```text
REPORTED_STATUS: README describes M2 as the ChangeSet Foundation
AT_TIME_IMPLEMENTATION_STATUS: IMPLEMENTED_WITH_DEVIATIONS
AT_TIME_VERIFICATION_STATUS: HISTORICALLY_UNVERIFIED
```

## 21. M2 vs M3 Boundary

```text
M3_START_COMMIT: df584f00b240ef8086b99d408f76f42a90c4b517
CLASSIFICATION: PURE_M3
```

M3 adds dependency invalidation integration and `AppliedChangeResult`. No
retained evidence indicates M3 was required to complete the core M2 capability.

## 22. Later Evolution of M2 Foundations

| M2 Foundation | Later State | Evidence |
| --- | --- | --- |
| ChangeProposal base model | PRESERVED | No later direct model rewrite found |
| ChangeSet/application receipt | EXTENDED | `df584f0` adds ephemeral `AppliedChangeResult` |
| Ownership policy | EXTENDED | Later domain rules added |
| Path semantics | PRESERVED | Core traversal retained |
| Stale protection | EXTENDED | `8079c57`, `161986b` add lock serialization |
| Resulting-state validation | PRESERVED | Candidate `model_validate` remains |
| StateManager integration | EXTENDED | `8079c57` adds lock-protected state operations |
| Canonical mutation boundary | EXTENDED | Later production/promotion paths retain ChangeEngine |

## 23. Unresolved Questions

- Whether unretained external CI or terminal output proved M2 verification.
- Whether legacy `ChangeProposal` defaults were intentional compatibility
  behavior or an undocumented design deviation.
- Whether pointer-write failure had tests outside retained history.

## 24. Repository Safety

The forensic investigation began with an already-dirty worktree: nine modified
files and seventeen untracked paths. It made no repository changes, created no
commit, and left the staged diff empty. Those pre-existing changes are distinct
from this documentation persistence task.

## 25. Final Reconstructed Classification

```text
M2_CAPABILITY_STATUS: M2_IMPLEMENTED_WITH_DEVIATIONS
M2_GIT_HISTORY_STATUS: M2_SHARED_COMMIT_WITH_M1
AT_TIME_IMPLEMENTATION_STATUS: IMPLEMENTED_WITH_DEVIATIONS
AT_TIME_VERIFICATION_STATUS: HISTORICALLY_UNVERIFIED
CURRENT_HISTORICAL_STATUS: M2_IMPLEMENTED_BUT_HISTORICALLY_UNVERIFIED
```
