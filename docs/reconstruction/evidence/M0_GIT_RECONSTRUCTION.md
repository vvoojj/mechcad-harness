# MechCAD M0 Git Reconstruction Report

## 1. Verdict

```text
M0_RECONSTRUCTION_STATUS: M0_IMPLEMENTATION_BASELINE_RECONSTRUCTED_WITH_DEVIATIONS
M0_COMPLETION_STATUS: IMPLEMENTED
HISTORICAL_EXECUTION_VERIFICATION: UNVERIFIED
CONFIDENCE: MEDIUM_HIGH
```

M0 is the first retained MechCAD implementation milestone. Its implementation
is directly present in its root Git tree. Historical successful execution is
not established by retained evidence.

## 2. Commit Boundaries

```text
M0_START_COMMIT:
7185351d40c3cfe588c9f2c43ba3e2bc1f9e603f

M0_IMPLEMENTATION_RANGE:
7185351d40c3cfe588c9f2c43ba3e2bc1f9e603f

M0_COMPLETION_COMMIT:
7185351d40c3cfe588c9f2c43ba3e2bc1f9e603f
(inferred implementation boundary; no separate completion commit survives)

NEXT_RETAINED_MILESTONE_COMMIT:
37f3ff3ea143400adb460e4650e1b580a4f1488d
```

Evidence:

- `7185351d40c3cfe588c9f2c43ba3e2bc1f9e603f` is the root commit, subject
  `feat: bootstrap mechcad harness M0`; it adds 40 files and 681 lines.
- Its direct child is `37f3ff3ea143400adb460e4650e1b580a4f1488d`, subject
  `feat: add M2 changeset foundation`.
- No retained M1 commit, M0 completion/acceptance commit, tag, Git note, or
  unreachable M0 commit was found.
- The M0 completion SHA is therefore an inferred implementation boundary, not
  separately proven acceptance or verification evidence.

## 3. Artifact Inventory

### Design

- `7185351:docs/superpowers/specs/2026-08-18-mechcad-m0-bootstrap-design.md`
- Defines a typed Python/Pydantic foundation and the M0 exclusion boundary.

### Implementation Plan

- `7185351:docs/superpowers/plans/2026-08-18-mechcad-m0-bootstrap.md`
- Specifies the scaffold, IDs, models, configuration, documentation, and
  tests. Its final verification checkboxes remain unchecked.

### Completion / Acceptance Records

No M0 completion report, acceptance record, test transcript, CI artifact, or
Git tag was found in retained history.

### Other Historical References

- `7185351:README.md`
- `7185351:AGENTS.md`
- `7185351:.opencode/README.md`

## 4. Actual M0 Implementation

### Package Scaffold

`7185351` introduced:

- `.gitignore` and `pyproject.toml`.
- `src/mechcad_harness/__init__.py` and a setuptools `src` layout.
- Reserved package boundaries: `adapters`, `agents`, `core`, `dependency`,
  `state`, `storage`, `tools`, and `validation`.
- `workspace/.gitkeep` and `tests/integration/.gitkeep`.
- Python `>=3.11`, Pydantic `>=2,<3`, and pytest support in `pyproject.toml`.

### IDs

`7185351:src/mechcad_harness/ids.py` provides `IdPrefix`,
`generate_id(prefix)`, and `id_prefix(value)`.

The supported readable prefixes are `PRJ`, `REV`, `RUN`, `TASK`, `CP`, `CS`,
`ISSUE`, `EVD`, `VAL`, `DEC`, `REQ`, `PRT`, `ASM`, `MAT`, `JNT`, and `LC`.
Generated identifiers are `<PREFIX>-<uuid4>`; extraction validates both the
known prefix and UUID suffix.

### Domain Models

The M0 public model surface in `7185351:src/mechcad_harness/models/` includes:

- `DesignState`, `Requirement`, `Component`, `Assembly`, `MaterialProfile`,
  `Interface`, `Constraint`, and `LoadCase` in `design.py`.
- `AgentTask`, `AgentResult`, and `TaskStatus` in `task.py`.
- `ChangeOperation`, `ChangeProposal`, `ChangeSet`, `ConstraintRequest`, and
  `ProposalStatus` in `proposal.py`.
- `Issue`/`IssueStatus`, `ValidationResult`/`ValidationStatus`, `Evidence`,
  and `RunManifest` in their respective modules.
- `StateBinding`, the common model base, and `utc_now()` in `common.py`.

`Model` uses `extra="forbid"`. Identifying strings are non-empty, revisions are
positive where required, state hashes are non-empty, timestamps are UTC-aware,
and status fields use enums.

### Canonical State Boundary

`7185351:src/mechcad_harness/models/design.py:DesignState` holds only canonical
engineering lists: requirements, components, assemblies, materials, interfaces,
constraints, and load cases. It has no evidence or result fields.

`Evidence`, `AgentResult`, `ChangeProposal`, `ChangeSet`, `ConstraintRequest`,
`Issue`, and `ValidationResult` are separate bindable records through
`StateBinding`. `7185351:tests/unit/test_models.py::test_design_state_does_not_contain_evidence_or_results`
directly tests that separation.

### Configuration

The root commit adds all six requested files:

| File | M0 content |
| --- | --- |
| `config/harness.yaml` | `schema`, `version`, `harness: {}` |
| `config/agents.yaml` | `schema`, `version`, `agents: []` |
| `config/ownership.yaml` | `schema`, `version`, `ownership: []` |
| `config/validations.yaml` | `schema`, `version`, `validations: []` |
| `config/tools.yaml` | `schema`, `version` only |
| `config/dependencies.yaml` | `schema`, `version` only |

No configuration file provided execution integration behavior.

### Documentation

- `7185351:README.md` records M0 scope, exclusions, canonical-state ownership,
  placeholder configuration, and a local test command.
- `7185351:AGENTS.md` records Pydantic/UTC requirements, state separation,
  exclusions, and a no-commit instruction.
- `7185351:.opencode/README.md` explicitly says M0 has no OpenCode integration,
  agents, tool execution, workflows, or execution configuration.

### Tests

Six unit tests existed at the M0 boundary:

- `7185351:tests/unit/test_ids.py` has two tests for identifier uniqueness,
  prefix extraction, and declared-prefix coverage.
- `7185351:tests/unit/test_models.py` has four tests for construction, empty
  name and zero-revision rejection, revision/state-hash binding, and
  `DesignState` evidence/result separation.

The tests' existence is evidence of test implementation only; it is not
evidence that they were successfully executed historically.

## 5. Verification Evidence

### Historical pytest evidence

`UNVERIFIED`. The plan requests `pytest -q` at
`7185351:docs/superpowers/plans/2026-08-18-mechcad-m0-bootstrap.md:156`, but no
committed output, CI artifact, completion report, or log records a result.

### Historical compileall evidence

`UNVERIFIED`. The plan requests `python -m compileall src tests` at line 157,
but no immutable output or exit status survives.

### Completion marker

`MECHCAD_M0_BOOTSTRAP_COMPLETE` occurs only at plan line 159 as an unchecked
instruction. It was not emitted in a committed report, terminal transcript,
documentation update, or commit message.

### Other verification

The implementation and tests exist in the root tree. This proves their
historical presence, not successful execution. The forensic investigation that
established these findings was read-only and did not create this evidence file;
this file persists the subsequently accepted reconstruction.

## 6. Plan vs Actual Implementation

| Planned Capability | Actual M0 State | Evidence | Deviation |
| --- | --- | --- | --- |
| Python/Pydantic `src` package | IMPLEMENTED | `7185351:pyproject.toml` | None |
| Readable identifiers and prefixes | IMPLEMENTED | `ids.py`; `test_ids.py` | None |
| Canonical `DesignState` | IMPLEMENTED | `models/design.py:DesignState` | None |
| Separate bindable records | IMPLEMENTED | `StateBinding`; model modules | None |
| Revision/state-hash binding | IMPLEMENTED | `models/common.py:StateBinding` | None |
| UTC-aware timestamps and enum statuses | IMPLEMENTED | `common.py`, status enums | None |
| Focused concept model modules | PARTIAL | re-export modules around `design.py` | IMPLEMENTED_DIFFERENTLY |
| Placeholder config empty collections | PARTIAL | tools/dependencies have schema/version only | MISSING_FROM_IMPLEMENTATION |
| Documentation boundaries | IMPLEMENTED | README, AGENTS, OpenCode README | None |
| Unit tests | IMPLEMENTED | `test_ids.py`, `test_models.py` | None |
| Recorded test/compile verification | NOT_IMPLEMENTED | no retained execution artifact | MISSING_FROM_IMPLEMENTATION |
| Completion marker/report | NOT_IMPLEMENTED | marker only in plan instruction | MISSING_FROM_IMPLEMENTATION |

## 7. Historical M0 File Inventory

All significant M0 files were introduced by `7185351`:

- Scaffold: `.gitignore`, `pyproject.toml`, `workspace/.gitkeep`, and
  `tests/integration/.gitkeep`.
- Documentation: `README.md`, `AGENTS.md`, `.opencode/README.md`, and the M0
  plan/design documents.
- Configuration: all six `config/*.yaml` files.
- Package: the package root, `ids.py`, reserved-package initializers, and all
  M0 model modules.
- Tests: `tests/unit/test_ids.py` and `tests/unit/test_models.py`.

## 8. Later Evolution of M0 Foundations

| M0 Foundation | Later State | Evidence |
| --- | --- | --- |
| Readable IDs | PRESERVED | M0 ID system and tests remain through current history |
| Canonical `DesignState` | EXTENDED | `3c7c708`, `8079c57`, `682300b`, `161986b` add later authority fields |
| Change proposal model | SUPERSEDED | `37f3ff3` adds the M2 changeset foundation |
| Separate Evidence record | EXTENDED | Later M5, M9, M10, and M11 work retains the separation principle |
| M0 exclusions | SUPERSEDED | Later milestones intentionally add controlled runtime/CAD/FEA capabilities |
| M0 plan and design | PRESERVED | Original records remain historical artifacts |

## 9. Unresolved Questions

- Whether the author ran the final M0 pytest suite is not established.
- Whether `compileall` was successfully executed is not established.
- Whether an external completion report existed is not established.
- No retained M1 commit exists; the reason history moves directly to M2 is
  unknown.

## 10. Final Reconstructed Classification

```text
REPORTED_STATUS: UNKNOWN
AT_TIME_IMPLEMENTATION_STATUS: IMPLEMENTED
AT_TIME_VERIFICATION_STATUS: UNVERIFIED
CURRENT_HISTORICAL_STATUS: M0_HISTORICALLY_COMPLETE_WITH_DEVIATIONS
```

## 11. Recommended Canonical M0 Record

M0 was implemented in the single root commit `7185351`
(`feat: bootstrap mechcad harness M0`). It established the Python/Pydantic
foundation, readable identifiers, canonical `DesignState`, separate state-bound
records, configuration placeholders, boundary documentation, and six unit
tests. No separate completion commit, completion marker, acceptance record, or
historical test/compile execution result survives. The next retained commit is
M2 (`37f3ff3`); no M1 commit was found. The implementation has two minor
deviations: re-exported focused model modules and two configuration placeholders
without explicit empty collections.

## Original Worktree Observation

At the time of the read-only forensic investigation, the worktree was already
dirty with unrelated modified and untracked files; the staged diff was empty.
The investigation made no changes.

This observation predates publication of the reconstruction. The M0-M4 ledger
and records were later committed together in
`8fda5aa580993b5256bfbf1267216ce0f066d0cd`; that publication commit is not
historical execution evidence for M0.

```text
WORKTREE_CHANGED: YES
STAGED_DIFF: EMPTY
```
