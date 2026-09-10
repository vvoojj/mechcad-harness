# MechCAD M1 Git Reconstruction Report

## 1. Verdict

```text
M1_CAPABILITY_EXISTENCE: PROVEN
M1_EXPLICIT_GIT_MILESTONE_EXISTENCE: NOT_RETAINED
M1_RECONSTRUCTION_STATUS: M1_IMPLEMENTED_WITHIN_M2_COMMIT
M1_IMPLEMENTATION_STATUS: IMPLEMENTED
M1_VERIFICATION_STATUS: UNVERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
```

M1 is a proven capability state. Its executable implementation first appears
in a commit labelled M2, not in a separately retained M1 commit.

## 2. Commit Boundary

```text
M0_PREDECESSOR_COMMIT:
7185351d40c3cfe588c9f2c43ba3e2bc1f9e603f

M1_START_COMMIT:
37f3ff3ea143400adb460e4650e1b580a4f1488d

M1_IMPLEMENTATION_RANGE:
37f3ff3ea143400adb460e4650e1b580a4f1488d

M1_COMPLETION_TREE:
37f3ff3ea143400adb460e4650e1b580a4f1488d

M2_START_COMMIT:
37f3ff3ea143400adb460e4650e1b580a4f1488d
```

`37f3ff3` is a shared M1/M2 commit. Its subject is `feat: add M2 changeset
foundation`; its diff introduces the complete M1 State Foundation and the M2
ChangeSet Foundation. The boundary is exact for capability introduction, shared
with M2, and not a separately proven M1 completion or acceptance commit.

## 3. Reason No Explicit M1 Commit Is Retained

- Reachable history is linear from M0 `7185351` directly to `37f3ff3`.
- No reachable commit subject identifies M1.
- Reflogs likewise transition directly from M0 to `37f3ff3`.
- No Git notes were found.
- No unreachable commit or tree contains M1 State Foundation evidence.

This proves no explicit M1 commit is retained. It does not prove that a
separate M1 commit never existed before the surviving object and reflog history.

## 4. Artifact Inventory

### Spec / Design

- No dedicated M1 spec or design was found.
- `8079c576:docs/audit/MECHCAD_ARCHITECTURE_SPEC_RECONCILIATION.md` explicitly
  records M1 spec count `0` and classifies M1 provenance as
  `TRACEABILITY_MISSING`.

### Implementation Plan

- No dedicated M1 plan was found.
- `37f3ff3:docs/superpowers/plans/2026-08-18-mechcad-m2-changeset.md` describes
  M2 on top of M1 revisions and delegates persistence to
  `StateManager.create_revision`. It is successor evidence, not an M1 plan.

### Completion / Acceptance

- No dedicated M1 completion or acceptance record was found.
- `8079c576:docs/MechCAD_Harness_Project_Description.md` retrospectively calls
  M1 State Foundation complete. This is historical narrative, not independent
  execution verification.

### Historical README / Documentation

- `37f3ff3:README.md` first adds the M1 State Foundation section.
- `8079c576:docs/architecture/MECHCAD_CAPABILITY_MATRIX.md` records M1
  immutable revision/hash capability.
- `8079c576:docs/architecture/MECHCAD_PROJECT_OVERVIEW.md` preserves M1 state
  authority in later architecture reconciliation.

### Implementation and Tests

- `37f3ff3:src/mechcad_harness/state/hashing.py`
- `37f3ff3:src/mechcad_harness/state/manager.py`
- `37f3ff3:src/mechcad_harness/state/errors.py`
- `37f3ff3:tests/unit/test_state_foundation.py`

M0's `src/mechcad_harness/state/__init__.py` contains only the placeholder
`"State package reserved for future state services."`.

## 5. Capability Introduction Timeline

| M1 Capability | First Proven Commit | State | Evidence |
| --- | --- | --- | --- |
| project state persistence | `37f3ff3` | ADDED | `StateManager` project paths |
| canonical JSON | `37f3ff3` | ADDED | `canonical_json` |
| SHA-256 state hash | `37f3ff3` | ADDED | `state_hash` |
| immutable revisions | `37f3ff3` | ADDED | exclusive snapshot write |
| `current.json` | `37f3ff3` | ADDED | pointer create/load logic |
| tamper detection | `37f3ff3` | ADDED | `_read_snapshot` hash recomputation |

## 6. M0 vs M1 Boundary

M0 provides the typed `DesignState` model, positive revisions, UTC-aware
timestamps, and external-record separation. It does not provide persistence,
canonical serialization, SHA-256 calculation, snapshots, `current.json`, or
tamper detection. Its state package is placeholder-only and its README
explicitly excludes persistence.

M0's `StateBinding` accepts a non-empty state-hash string, including the test
placeholder `sha256:abc`; it does not calculate or validate a SHA-256 identity.

## 7. M1 vs M2 Boundary

```text
DID_COMMIT_37f3ff3_INTRODUCE_M1_CAPABILITIES: YES
```

The M0 parent contains none of the M1 persistence capability surface.
`37f3ff3` adds `state/hashing.py`, `state/manager.py`, `state/errors.py`, State
Foundation exports, the M1 README section, and State Foundation tests.

The same diff also adds the independent M2 `changes/` package, M2 tests, and
M2 plan/spec. M2 uses the StateManager introduced in that same commit. M1
remains canonical-state persistence and revision identity; M2 remains the
controlled ChangeSet mutation boundary.

## 8. Actual State Foundation Implementation

### Workspace Layout

`StateManager(workspace)` stores data at:

```text
<workspace>/projects/<project_id>/
  current.json
  revisions/REV-000001.json
  revisions/REV-000002.json
```

### Canonical Serialization

`canonical_payload(state)` returns the complete
`DesignState.model_dump(mode="json")` payload. `canonical_json(...)` uses
`json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`
and UTF-8 encoding. Mapping order is normalized; list order remains significant.

### State Hashing

`state_hash(...)` calculates `hashlib.sha256(canonical_json(...)).hexdigest()`
and returns `sha256:<hex digest>`. External records are excluded because they
are not fields of `DesignState`, not because selected state fields are removed.

### Revision Snapshots

`RevisionSnapshot` stores project ID, revision, parent revision, revision ID,
state hash, schema version `m1`, and embedded `DesignState`.

- `create_project` forces revision `1`.
- `create_revision` requires a strictly greater revision.
- Revision files use `REV-{revision:06d}.json`.
- Exclusive snapshot writes reject existing targets.
- Writes use a same-directory temporary file, flush/fsync, then `os.replace`.

### current.json

`current.json` contains `project_id`, `revision`, and `state_hash`. It is a
lightweight pointer, not a duplicate state payload. Initial M1 checks that the
pointed snapshot has the same hash, but does not yet strictly validate pointer
field types or hash format.

### Tamper Detection

`_read_snapshot` Pydantic-parses persisted JSON, recomputes the embedded
state's hash, and raises `StateIntegrityError` on mismatch. `load_current_state`
also rejects pointer/snapshot hash disagreement.

### Canonical Authority Boundary

`DesignState` is canonical; proposals, evidence, results, and validation remain
external records. StateManager is the persistence authority. “Only the harness
creates revisions” is an architectural/process boundary in initial M1, not a
caller authorization mechanism enforced by this code.

## 9. Historical Tests

`37f3ff3:tests/unit/test_state_foundation.py` contains:

- `test_equivalent_states_have_same_canonical_hash`
- `test_hash_ignores_mapping_order_but_changes_with_state`
- `test_project_revisions_are_immutable_and_current_points_to_latest`
- `test_existing_revision_cannot_be_overwritten`
- `test_tampered_snapshot_is_detected`
- `test_current_pointer_is_unchanged_when_snapshot_persistence_fails`
- `test_evidence_is_not_part_of_design_state`

```text
TEST_CODE_PRESENT: YES
HISTORICAL_TEST_EXECUTION_STATUS: NOT_PROVEN
```

The tests prove historical test-code presence, not historical successful test
execution.

## 10. Historical Verification Evidence

```text
IMPLEMENTATION: CONFIRMED
TEST CODE: CONFIRMED
HISTORICAL SUCCESSFUL EXECUTION: NOT CONFIRMED
```

The M2 plan lists pytest, compileall, and diff checks, but its checkboxes remain
unchecked. No immutable pytest output, compileall output, completion marker,
completion report, acceptance record, or CI artifact for M1 was found.

`VERIFICATION_STATUS: HISTORICALLY_UNVERIFIED` means retained success evidence
is unavailable; it does not mean the tests failed.

## 11. Documentation vs Actual Git State

| Documented Claim | Actual Historical State | Evidence | Classification |
| --- | --- | --- | --- |
| canonical workspace state | implemented in `37f3ff3` | `StateManager` | SUPPORTED |
| complete DesignState canonical hash | implemented | `canonical_payload` / `canonical_json` | SUPPORTED |
| SHA-256 `sha256:<hex>` identity | implemented | `state_hash` | SUPPORTED |
| immutable monotonic snapshots | implemented | revision creation and exclusive writes | SUPPORTED |
| `current.json` pointer | implemented | manager pointer logic | SUPPORTED |
| tamper rejection on snapshot load | implemented | hash recomputation and test | SUPPORTED |
| separate M1 Git milestone commit | no retained proof | graph, reflog, fsck | UNPROVEN |
| M1 complete/verified | executable implementation complete; execution unproven | later project description | RETROSPECTIVE_ONLY |

## 12. Reflog / Unreachable-History Investigation

```text
reachable explicit M1 commit: NONE
reflog M1 commit: NONE
unreachable M1 commit/tree: NONE
NO_RETAINED_UNREACHABLE_M1_EVIDENCE_FOUND
```

`git fsck --full --unreachable --no-reflogs` found only three unrelated dangling
blobs: `1d31dba9ebab5e7b21ec8c314c0fb314f3451dd0`,
`53894e2db2d1d74251a7959652d6312a717f6ae8`, and
`32ed88c7d3406c568bca4108c8d3353b6188c3f5`.

## 13. Later Evolution

| M1 Foundation | Later State | Evidence |
| --- | --- | --- |
| canonical JSON / hash input | PRESERVED | `hashing.py` unchanged after `37f3ff3` |
| SHA-256 state identity | PRESERVED | format retained |
| revision snapshots | EXTENDED | promotion, locking, and envelope checks added later |
| `current.json` | EXTENDED | strict pointer validation added later |
| tamper detection | EXTENDED | initial hash checks retained; cross-field checks added later |
| canonical state fields | EXTENDED | later authority fields join `DesignState` hash payload |

## 14. Unresolved Questions

- Was an explicit M1 commit never created, or did it disappear before the
  retained Git history?
- Were the original M1 tests and compileall successfully executed?

## 15. Final Reconstructed Classification

```text
M1_CAPABILITY_STATUS: M1_IMPLEMENTED_WITHIN_M2_COMMIT
M1_GIT_HISTORY_STATUS: M1_IMPLEMENTED_WITHOUT_EXPLICIT_MILESTONE_COMMIT
AT_TIME_IMPLEMENTATION_STATUS: IMPLEMENTED
AT_TIME_VERIFICATION_STATUS: UNVERIFIED
CURRENT_HISTORICAL_STATUS: M1_HISTORY_PARTIALLY_LOST
```

The partial historical loss concerns explicit milestone identity and execution
provenance, not the retained executable M1 implementation.

## 16. Repository Safety Observation

The original forensic investigation was read-only. It observed a pre-existing
dirty worktree with an empty staged diff and made no repository changes.
