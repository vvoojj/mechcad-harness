# F10 M6B-4C Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire only the unused and unaccepted M6B-4C constraint-resolution
workflow while preserving the active constraint-request anchor authority and
all unrelated contracts.

**Architecture:** Remove the M6B-4C application/workflow route and the
provenance/recovery/ownership code reachable only from it. Retained M7 domain
tests will seed valid canonical authoritative parameters with ordinary
`StateManager` revisions, so they continue to test consuming authority without
depending on the retired route. The active `ConstraintRequestMaterializer`
remains the sole anchor-map owner; no replacement application service or
compatibility shim is introduced.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, ripgrep, Git.

## Global Constraints

- Baseline: `69c11dc809fe8622d371f891bc7b5216aa1875d2`.
- Design authority:
  `docs/superpowers/specs/2026-09-14-f10-m6b4c-retirement-design.md`.
- Use `apply_patch` for every source, test, configuration, and documentation
  edit; do not use destructive Git commands.
- Preserve `agents/constraint_resolution.py`, `ConstraintRequestMaterializer`,
  request/resolution records and identities, gateway/roundtrip/materialization,
  `DesignState.authoritative_parameters`, ordinary `ChangeEngine` and state
  revision behavior, and all unrelated public APIs.
- Do not create a new anchor helper or move the retired `_anchor_for` map.
- Do not modify audit/map material or `docs/reconstruction/**` in this wave.
- Do not perform audit/map synchronization until implementation acceptance and
  separate authorization.
- Do not commit or push unless separately authorized.
- Preserve unrelated dirty/untracked workspace material.

---

## Planned File Changes

### Delete

- `src/mechcad_harness/agents/constraint_resolution_workflow.py`
- `src/mechcad_harness/agents/constraint_resolution_application.py`
- `src/mechcad_harness/changes/provenance.py`
- `tests/unit/test_constraint_resolution_application.py`
- `tests/unit/test_constraint_resolution_workflow.py`
- `tests/unit/test_state_application_provenance.py`

### Modify

- `src/mechcad_harness/agents/__init__.py`: remove only application/workflow
  imports and four matching exports.
- `src/mechcad_harness/changes/__init__.py`: remove only provenance exports and
  lazy-import branch.
- `src/mechcad_harness/state/manager.py`: remove only
  `StateManager.promote_existing_revision` after the second zero-consumer census.
- `config/ownership.yaml`: remove only the `/authoritative_parameters` /
  `mechcad-resolution` entry.
- `tests/unit/test_m7b1br_authority.py`: seed direct valid azimuth authority in
  the retained consumer test.
- `tests/unit/test_m7b2a_yagi_authority.py`: seed direct persisted Yagi
  authority and rename the test away from the retired application claim.
- `tests/unit/test_m7b2b_yagi_carrier.py`: replace `state_with_authority`'s
  retired application setup with a direct persisted canonical authority fixture.

### Do Not Modify

- `src/mechcad_harness/agents/constraint_requests.py`
- `src/mechcad_harness/agents/constraint_resolution.py`
- `src/mechcad_harness/agents/roundtrip.py`
- `src/mechcad_harness/agents/gateway.py`
- `src/mechcad_harness/agents/materialization.py`
- `src/mechcad_harness/agents/opencode.py`
- audit/map and reconstruction records

## Task 1: Baseline and Mandatory Reference-Census Gate

**Files:**
- Modify: none
- Test: none

**Interfaces:**
- Consumes: the approved F10 design and the baseline commit.
- Produces: a dated implementation-workspace census record in the execution
  transcript, classified before any deletion.

- [ ] **Step 1: Confirm the implementation baseline and preserve unrelated work**

Run:

```powershell
git rev-parse HEAD
```

Expected: `HEAD` is
`69c11dc809fe8622d371f891bc7b5216aa1875d2`. Record all pre-existing modified
and untracked paths; do not stage, edit, delete, or otherwise normalize them.
If `HEAD` differs, stop before editing and reconcile the requested baseline with
the user.

- [ ] **Step 2: Run useful pre-removal characterization gates**

Run:

```powershell
pytest -q tests/unit/test_constraint_requests.py tests/unit/test_constraint_resolution.py tests/unit/test_m7b1a_authority.py tests/unit/test_m7b1br_authority.py tests/unit/test_m7b2a_yagi_authority.py tests/unit/test_m7b2b_yagi_carrier.py
```

Expected: the current retained request, resolution-data, and M7 authority
contracts pass before fixture migration. This is characterization evidence, not
acceptance of the M6B-4C workflow.

- [ ] **Step 3: Perform the mandatory repository-wide reference census**

Run the following individual searches from the repository root. Do not use a
search that excludes tests or documentation.

```powershell
rg -n --hidden --glob '!.git/**' 'agents\.constraint_resolution_workflow' .
rg -n --hidden --glob '!.git/**' 'agents\.constraint_resolution_application' .
rg -n --hidden --glob '!.git/**' 'changes\.provenance' .
rg -n --hidden --glob '!.git/**' '\bConstraintResolutionWorkflow\b' .
rg -n --hidden --glob '!.git/**' '\bConstraintResolutionWorkflowResult\b' .
rg -n --hidden --glob '!.git/**' '\bConstraintResolutionApplicationService\b' .
rg -n --hidden --glob '!.git/**' '\bConstraintResolutionApplicationResult\b' .
rg -n --hidden --glob '!.git/**' '\bStateApplicationPreparationRecord\b' .
rg -n --hidden --glob '!.git/**' '\bStateApplicationReceiptRecord\b' .
rg -n --hidden --glob '!.git/**' '\bStateApplicationStore\b' .
rg -n --hidden --glob '!.git/**' '\boperations_hash\b' .
rg -n --hidden --glob '!.git/**' '\bapplication_id\b' .
rg -n --hidden --glob '!.git/**' 'StateManager\.promote_existing_revision|\.promote_existing_revision\(' .
rg -n --hidden --glob '!.git/**' 'mechcad-resolution' .
rg -n --hidden --glob '!.git/**' '\b_anchor_for\b' .
```

For every match, classify it in the execution notes as exactly one of:

1. removal-set source/test/export;
2. retained source/test consumer;
3. historical/docs-only reference;
4. unrelated false match.

Expected classifications at the approved baseline:

| Surface | Allowed non-doc matches before removal |
| --- | --- |
| workflow/application modules and symbols | the two modules, their package exports, the three obsolete workflow/application/provenance test modules, and the three listed M7 fixture setups |
| provenance module and symbols | `changes/provenance.py`, its `changes/__init__.py` export branch, retired module imports, and obsolete tests |
| `promote_existing_revision` | its definition and the retired application call only |
| `mechcad-resolution` | `config/ownership.yaml`, retired code, and obsolete tests/M7 fixture setup only |
| `_anchor_for` | retired application definition and calls only |

The F10 spec, P3 triage, audit/map, historical reconstruction, and old
design/plan records are category 3 and must not be edited. A generic term such
as `application_id` may produce unrelated results; mark such matches category 4
only after confirming they do not import, call, or serialize the retired
`changes.provenance` API.

**STOP CONDITION:** If any category-2 retained production or accepted-test
consumer is not explicitly listed in this plan or approved design, stop
immediately. Do not edit, delete, introduce a shim, broaden scope, or update
documentation. Report exactly:

```text
F10_PLAN_BLOCKED_BY_UNEXPECTED_RETAINED_CONSUMER
```

- [ ] **Step 4: Repeat targeted ownership and recovery assertions before deletion**

Run:

```powershell
rg -n 'promote_existing_revision|mechcad-resolution|/authoritative_parameters' src tests config
```

Expected: only the approved removal set and M7 fixtures appear. This confirms
the planned removal does not alter any unrelated `ChangeEngine` ownership or
state-revision path.

### Task 2: Migrate Retained M7 Authority Fixtures

**Files:**
- Modify: `tests/unit/test_m7b1br_authority.py:68-92`
- Modify: `tests/unit/test_m7b2a_yagi_authority.py:142-219`
- Modify: `tests/unit/test_m7b2b_yagi_carrier.py:70-133`
- Test: the three modified test modules

**Interfaces:**
- Consumes: retained `AuthoritativeAnchor`, `AuthoritativeParameter`, typed
  authoritative value models, `StateManager.create_project`, and
  `StateManager.create_revision`.
- Produces: revision-2, reloadable canonical test fixtures with the exact
  anchor/kind/scope/value expected by the azimuth and Yagi consumers, without
  `ConstraintResolutionApplicationService`.

- [ ] **Step 1: Replace the M7B-1BR retired application setup with direct canonical authority**

In `test_state_resolved_authorities_produce_the_accepted_synthesis_fixture`,
remove the request-store, resolution-command, materializer, application-service,
`ChangeEngine`, and `OwnershipPolicy` setup. Retain the `drive` and
`requirements()` domain fixtures. Create the project at revision 1, then create
one ordinary revision containing both valid authoritative parameters:

```python
from mechcad_harness.engineering.values import (
    AzimuthDriveMountInterfaceValue,
    AzimuthMotorMountPlateDesignRequirementsValue,
)
from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter

initial = manager.load_current_state("PRJ")
resolved = initial.model_copy(update={
    "authoritative_parameters": [
        AuthoritativeParameter(
            id="PARAM-DRIVE",
            anchor=AuthoritativeAnchor(
                kind="constraint", id="CON-AZIMUTH-DRIVE-MOUNT-INTERFACE"
            ),
            scope_id="transmission",
            key=SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE,
            value=AzimuthDriveMountInterfaceValue(
                kind=SupportedConstraintKey.AZIMUTH_DRIVE_MOUNT_INTERFACE.value,
                **drive.model_dump(mode="json"),
            ),
            source_resolution_id="FIXTURE-DRIVE",
        ),
        AuthoritativeParameter(
            id="PARAM-PLATE",
            anchor=AuthoritativeAnchor(
                kind="constraint",
                id="CON-AZIMUTH-MOUNT-PLATE-DESIGN-REQUIREMENTS",
            ),
            scope_id="transmission",
            key=SupportedConstraintKey.AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS,
            value=AzimuthMotorMountPlateDesignRequirementsValue.from_domain(
                requirements()
            ),
            source_resolution_id="FIXTURE-PLATE",
        ),
    ]
})
snapshot = manager.create_revision("PRJ", resolved)
```

Pass `snapshot.revision` and `snapshot.state_hash` to the synthesis service.
Keep the existing successful-synthesis assertions, including the expected
revision-2 proposal binding.

- [ ] **Step 2: Run the focused M7B-1BR regression**

Run:

```powershell
pytest -q tests/unit/test_m7b1br_authority.py
```

Expected: PASS. The test continues to prove the consumer accepts exact direct
canonical authority, not that M6B-4C applies a resolution.

- [ ] **Step 3: Replace the M7B-2A retired application setup and rename its claim**

Rename
`test_yagi_authority_uses_m6b_resolution_application_and_persisted_reload` to
`test_yagi_authority_uses_persisted_authoritative_parameter`. Remove its
request/materializer/command/application imports and setup. Create a revision-2
state with this direct parameter, then reload it for the existing assertions:

```python
from mechcad_harness.models.design import AuthoritativeAnchor, AuthoritativeParameter

initial = manager.load_current_state("PRJ-YAGI")
snapshot = manager.create_revision(
    "PRJ-YAGI",
    initial.model_copy(update={
        "authoritative_parameters": [
            AuthoritativeParameter(
                id="PARAM-YAGI",
                anchor=AuthoritativeAnchor(
                    kind="requirement",
                    id="REQ-YAGI-PAYLOAD-CARRIER-REQUIREMENTS",
                ),
                scope_id="yagi-carrier",
                key=SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS,
                value=requirements(),
                source_resolution_id="FIXTURE-YAGI",
            )
        ]
    }),
)
reloaded = manager.load_revision("PRJ-YAGI", snapshot.revision)
```

Retain assertions for revision 2, exact requirement anchor, user-supplied
provenance, and
`ConstraintRequestMaterializer().is_satisfied(key, reloaded,
engineering_scope_id="yagi-carrier")`.

- [ ] **Step 4: Run the focused M7B-2A regression**

Run:

```powershell
pytest -q tests/unit/test_m7b2a_yagi_authority.py
```

Expected: PASS. The renamed test describes the retained authority contract
accurately and contains no import of the retired application module.

- [ ] **Step 5: Replace the M7B-2B shared fixture with the same direct authority boundary**

In `state_with_authority`, remove the datetime, constraint-request, resolution,
application-service, `ChangeEngine`, and `OwnershipPolicy` setup. After project
creation, create revision 2 with the direct `AuthoritativeParameter` used in
Task 2 Step 3, preserving:

```python
AuthoritativeAnchor(
    kind="requirement", id="REQ-YAGI-PAYLOAD-CARRIER-REQUIREMENTS"
)
```

Use `scope_id="yagi-carrier"`,
`key=SupportedConstraintKey.YAGI_PAYLOAD_CARRIER_REQUIREMENTS`,
`value=requirements()`, and `source_resolution_id="FIXTURE-YAGI-CARRIER"`.
Return the same `StateManager`; its current pointer must be revision 2 so the
existing state-backed synthesis assertion remains meaningful.

- [ ] **Step 6: Run M7B-2B and the combined retained M7 gate**

Run:

```powershell
pytest -q tests/unit/test_m7b2b_yagi_carrier.py
pytest -q tests/unit/test_m7b1a_authority.py tests/unit/test_m7b1br_authority.py tests/unit/test_m7b2a_yagi_authority.py tests/unit/test_m7b2b_yagi_carrier.py
```

Expected: PASS. The unchanged anchor-map tests continue to prove
`ConstraintRequestMaterializer` owns the exact mapping.

### Task 3: Remove the Retired M6B-4C Workflow, Application, and Provenance Code

**Files:**
- Delete: `src/mechcad_harness/agents/constraint_resolution_workflow.py`
- Delete: `src/mechcad_harness/agents/constraint_resolution_application.py`
- Delete: `src/mechcad_harness/changes/provenance.py`
- Test: no new test; use the Task 2 retained regressions after removal

**Interfaces:**
- Consumes: the completed Task 1 census and Task 2 fixture migration.
- Produces: no importable M6B-4C workflow/application/provenance module.

- [ ] **Step 1: Confirm the census gate is passed immediately before deletion**

Review the Task 1 classification table. Confirm each retained M7 fixture has
already been migrated and that no category-2 consumer was found. If a new
consumer appeared since Task 1, apply the same stop condition and report
`F10_PLAN_BLOCKED_BY_UNEXPECTED_RETAINED_CONSUMER`.

- [ ] **Step 2: Delete only the three retired modules**

Use `apply_patch` with exactly these deletions:

```diff
*** Delete File: src/mechcad_harness/agents/constraint_resolution_workflow.py
*** Delete File: src/mechcad_harness/agents/constraint_resolution_application.py
*** Delete File: src/mechcad_harness/changes/provenance.py
```

Do not edit `agents/constraint_requests.py` or
`agents/constraint_resolution.py`. In particular, do not move `_anchor_for`,
copy its mapping, or alter `ConstraintRequestMaterializer._anchors`,
`anchor_for`, or `is_satisfied`.

- [ ] **Step 3: Prove the retained direct modules still import before export cleanup**

Run:

```powershell
python -c "from mechcad_harness.agents.constraint_requests import ConstraintRequestMaterializer; from mechcad_harness.agents.constraint_resolution import ConstraintResolutionBatchCommand; print(ConstraintRequestMaterializer.__name__, ConstraintResolutionBatchCommand.__name__)"
```

Expected: prints both class names. If package eager imports prevent this before
Task 4 removes retired exports, proceed directly to Task 4; do not restore a
shim or modify retained modules.

### Task 4: Remove Exact Exports, Recovery Method, and Ownership Route

**Files:**
- Modify: `src/mechcad_harness/agents/__init__.py:26-27,64-67`
- Modify: `src/mechcad_harness/changes/__init__.py:13-17,41-43`
- Modify: `src/mechcad_harness/state/manager.py:218` (`promote_existing_revision` only)
- Modify: `config/ownership.yaml:6-7`
- Test: import and ownership-focused checks

**Interfaces:**
- Consumes: deleted retired modules and a fresh zero-consumer check for
  `StateManager.promote_existing_revision`.
- Produces: retained package exports only; no M6B-4C recovery or ownership API.

- [ ] **Step 1: Remove only the four `agents` application/workflow exports**

Delete these imports and only their matching `__all__` strings:

```python
from .constraint_resolution_application import (
    ConstraintResolutionApplicationResult,
    ConstraintResolutionApplicationService,
)
from .constraint_resolution_workflow import (
    ConstraintResolutionWorkflow,
    ConstraintResolutionWorkflowResult,
)
```

Delete these entries:

```python
"ConstraintResolutionApplicationResult",
"ConstraintResolutionApplicationService",
"ConstraintResolutionWorkflow",
"ConstraintResolutionWorkflowResult",
```

Retain the existing `ConstraintRequest*` and `ConstraintResolution*` imports
and exports exactly as they are.

- [ ] **Step 2: Remove only the `changes.provenance` aggregate exports**

In `changes/__init__.py`, delete the five provenance names from `__all__` and
delete the complete lazy-import branch:

```python
if name in {
    "StateApplicationPreparationRecord",
    "StateApplicationReceiptRecord",
    "StateApplicationStore",
    "application_id",
    "operations_hash",
}:
    from .provenance import (
        StateApplicationPreparationRecord,
        StateApplicationReceiptRecord,
        StateApplicationStore,
        application_id,
        operations_hash,
    )
    return locals()[name]
```

Do not alter exports for `ChangeEngine`, `ChangeOperation`, `OwnershipPolicy`,
or `AppliedChangeResult`.

- [ ] **Step 3: Re-run the `promote_existing_revision` reference census immediately before removing it**

Run:

```powershell
rg -n --hidden --glob '!.git/**' 'StateManager\.promote_existing_revision|\.promote_existing_revision\(' src tests config
```

Expected: only the definition in `src/mechcad_harness/state/manager.py` remains.
If any retained source or accepted-test caller exists, stop and report:

```text
F10_PLAN_BLOCKED_BY_UNEXPECTED_RETAINED_CONSUMER
```

- [ ] **Step 4: Remove the recovery-only state method**

Delete the complete `StateManager.promote_existing_revision(self, project_id:
str, *, expected_current_revision: int, expected_current_hash: str,
target_revision: int, target_hash: str) -> RevisionSnapshot` method and no
adjacent `StateManager` method. Do not change
`create_project`, `create_revision`, `load_revision`, current-pointer writes,
or project locking.

```diff
*** Update File: src/mechcad_harness/state/manager.py
@@
-    def promote_existing_revision(self, project_id: str, *, expected_current_revision: int, expected_current_hash: str, target_revision: int, target_hash: str) -> RevisionSnapshot:
-        with self.project_lock(project_id):
-            current = self._read_current(project_id)
-            if current["revision"] != expected_current_revision or current["state_hash"] != expected_current_hash:
-                raise RevisionConflictError("current pointer does not match expected base")
-            snapshot = self._read_snapshot(project_id, target_revision)
-            if snapshot.state_hash != target_hash or snapshot.parent_revision != expected_current_revision:
-                raise StateIntegrityError("existing target revision does not match expected application")
-            self._write_atomic(self._current_path(project_id), {"project_id": project_id, "revision": target_revision, "state_hash": target_hash})
-            return snapshot
```

- [ ] **Step 5: Remove the retired ownership route**

Delete exactly this mapping from `config/ownership.yaml`:

```yaml
  - path: /authoritative_parameters
    owner: mechcad-resolution
```

Do not remove or alter any other ownership path, including requirements, azimuth,
Yagi, materials, structural, components, placement, or physical mechanisms.

- [ ] **Step 6: Verify retained imports and the intended import removals**

Run:

```powershell
python -c "from mechcad_harness.agents import ConstraintRequestMaterializer, ConstraintResolutionBatchCommand, ConstraintResolutionRecord, ConstraintResolutionStore; from mechcad_harness.changes import ChangeEngine, OwnershipPolicy; print('retained imports available')"
python -c "from mechcad_harness.agents import ConstraintResolutionWorkflow"; if ($LASTEXITCODE -eq 0) { throw 'retired workflow export still exists' }
python -c "from mechcad_harness.changes import StateApplicationStore"; if ($LASTEXITCODE -eq 0) { throw 'retired provenance export still exists' }
```

Expected: the first command succeeds; each latter import raises `ImportError`.
Those failures are intentional retirement checks, not failures to repair.

### Task 5: Remove Obsolete Retired-Workflow Tests

**Files:**
- Delete: `tests/unit/test_constraint_resolution_application.py`
- Delete: `tests/unit/test_constraint_resolution_workflow.py`
- Delete: `tests/unit/test_state_application_provenance.py`
- Test: retained test modules only

**Interfaces:**
- Consumes: deleted retired code, exports, recovery method, and ownership route.
- Produces: no test imports of retired M6B-4C surfaces.

- [ ] **Step 1: Confirm the tests are entirely within the approved obsolete set**

Run:

```powershell
rg -n 'ConstraintResolutionApplicationService|ConstraintResolutionWorkflow|StateApplicationStore|mechcad-resolution' tests/unit/test_constraint_resolution_application.py tests/unit/test_constraint_resolution_workflow.py tests/unit/test_state_application_provenance.py
```

Expected: every match exercises the retired application, workflow, provenance,
or ownership route. Do not delete any retained request, resolution-data, or M7
test module.

- [ ] **Step 2: Delete the three obsolete test modules**

Use `apply_patch` with exactly these deletions:

```diff
*** Delete File: tests/unit/test_constraint_resolution_application.py
*** Delete File: tests/unit/test_constraint_resolution_workflow.py
*** Delete File: tests/unit/test_state_application_provenance.py
```

- [ ] **Step 3: Prove no retained test imports the retired surfaces**

Run:

```powershell
rg -n 'constraint_resolution_workflow|constraint_resolution_application|ConstraintResolutionWorkflow|ConstraintResolutionApplicationService|StateApplicationStore|mechcad-resolution' tests
```

Expected: no retained-test source match. Documentation or historical matches are
out of scope and must remain untouched.

### Task 6: Focused Regression, Absence, Static Checks, and Skeptical Review

**Files:**
- Modify: none
- Test: retained request/resolution/M7/gateway regressions and static checks

**Interfaces:**
- Consumes: completed source/test retirement.
- Produces: exact verification evidence for the implementation acceptance review.

- [ ] **Step 1: Run retained constraint and authority regressions**

Run:

```powershell
pytest -q tests/unit/test_constraint_requests.py tests/unit/test_constraint_resolution.py tests/unit/test_m7b1a_authority.py tests/unit/test_m7b1br_authority.py tests/unit/test_m7b2a_yagi_authority.py tests/unit/test_m7b2b_yagi_carrier.py
```

Expected: PASS. This proves exact request anchors/satisfaction, retained typed
resolution records/identities, and M7 consumer authority without M6B-4C.

- [ ] **Step 2: Identify and run the concrete gateway/roundtrip regression gate**

Run:

```powershell
rg -l 'run_transmission_round_trip|ConstraintRequestMaterializer|constraint_requests' tests/unit tests/integration
```

From the returned tracked tests, select the smallest modules that exercise both
`ProductionApplication.run_transmission_round_trip` and durable constraint
request materialization. Run their exact paths with `pytest -q`. Record each
selected file and result. Do not run live OpenCode/FreeCAD/Gmsh/CalculiX tests.

- [ ] **Step 3: Run the complete unit regression gate**

Run:

```powershell
pytest -q tests/unit
```

Record the complete command, exit status, pass/fail/skip summary, collection
result, and every failure identifier. If the baseline characterization from
Task 1 or a separately retained baseline run has known unrelated failures,
compare the post-removal result against that baseline and require all of the
following:

```text
1. No new F10-caused unit failure.
2. No new import or collection failure.
3. No regression attributable to a removed F10 module, symbol, export,
   provenance API, recovery method, or ownership route.
```

Do not broaden F10 to repair unrelated baseline failures. Do not run the full
live repository suite or FreeCAD/Gmsh/CalculiX validation without separate
authorization.

- [ ] **Step 4: Verify final absence and classification policy**

Run the Task 1 census commands again, first scoped to `src`, `tests`, and
`config`, then repository-wide. Apply the same four classifications from Task 1
to every result.

```text
1. Exact retired F10 modules, imports, symbols, and exports must have zero
   retained src/tests/config consumers.
2. Generic names such as application_id and operations_hash may have category-4
   unrelated matches.
3. Inspect every category-4 match and record why it does not import, call,
   construct, serialize, or otherwise depend on the retired
   changes.provenance API.
4. Repository-wide category-3 historical/docs references may remain and must
   not be edited.
5. Any unexpected category-2 retained consumer requires an immediate stop:
   F10_PLAN_BLOCKED_BY_UNEXPECTED_RETAINED_CONSUMER.
```

Do not require zero matches for raw generic-name searches. The zero-consumer
requirement applies to the exact retired F10 surfaces in retained source, tests,
and configuration only.

- [ ] **Step 5: Compile the retained production tree**

Run:

```powershell
python -m compileall src
```

Expected: successful compilation with no import or syntax failure.

- [ ] **Step 6: Run a scoped whitespace/diff check**

Run:

```powershell
git diff --check -- src/mechcad_harness/agents src/mechcad_harness/changes src/mechcad_harness/state config/ownership.yaml tests/unit
git diff -- src/mechcad_harness/agents src/mechcad_harness/changes src/mechcad_harness/state config/ownership.yaml tests/unit
```

Expected: no whitespace errors in F10-owned paths. Do not treat unrelated dirty
workspace warnings as F10 failures; report them separately and leave them
untouched.

- [ ] **Step 7: Perform a skeptical review before implementation acceptance**

Check each statement against the diff and retained tests:

```text
1. Only the approved M6B-4C workflow/application/provenance route was removed.
2. agents/constraint_resolution.py and all retained request/resolution identity
   algorithms are unchanged.
3. ConstraintRequestMaterializer remains the sole anchor-map owner; no new map
   or helper exists.
4. Retained M7 tests now seed direct valid canonical authority and still prove
   consumer behavior after reload.
5. Gateway/roundtrip/materialization behavior has focused passing coverage.
6. The complete `tests/unit` result has no new F10-caused failure, import or
   collection failure, or removed-surface regression relative to baseline.
7. Exact retired surfaces have zero retained src/tests/config consumers;
   generic category-4 matches were inspected and category-3 docs/history was
   left untouched.
8. Retired imports fail intentionally; all unrelated public imports remain.
9. No audit/map or reconstruction file changed.
10. No audit/map synchronization is included in this source-removal wave.
```

If any statement is false, do not claim implementation acceptance. Correct only
the approved F10 scope, rerun the affected gates, and keep any unexpected
retained-consumer finding blocked rather than expanding the retirement.

## Post-Acceptance Boundary

After source-removal implementation is independently accepted, audit/map
synchronization may be designed and authorized as a separate documentation
operation. It is explicitly not part of this plan's initial source-removal
execution.
