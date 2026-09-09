# M13-4 Second Re-Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the three M13-4 re-audit findings using only acceptance fixture, acceptance test, and report documentation changes.

**Architecture:** The fixture remains the sole owner of the truthful fifteen-pair policy; changing `motor-r/shaft-a` to clearance causes all request, result, scope, and Evidence identities to be derived by existing production paths. The Phase-A JSON remains diagnostic-only and grows complete primitive semantics. Phase B continues to create its fresh root and canonical M10 execution strictly from scalar locators and durable revision-2 state before reading that diagnostic JSON.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, FreeCAD 1.1.3 subprocess provider, existing M10/M12/M13 production APIs.

## Global Constraints

- Modify only `tests/integration/m13_4_acceptance_fixtures.py`, `tests/integration/test_m13_4_full_stack_acceptance.py`, and M13-4 documentation.
- Do not modify `src/mechcad_harness/`, contracts, storage, FreeCAD discovery/backend, dependencies, or predecessor goldens/hashes.
- Do not alter geometry, create contact authority, add exclusions, commit, tag, push, or authorize Rotator V2.
- Use `locator["project_id"]` to compose Phase B.
- Final status remains `M13_4_ACCEPTANCE_STATUS = PENDING_INDEPENDENT_REAUDIT` and `ROTATOR_V2_MAY_RESUME = NO`.

---

### Task 1: Truthful Pair Scope

**Files:**
- Modify: `tests/integration/m13_4_acceptance_fixtures.py:683-719`
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`

**Interfaces:**
- Consumes: `PhysicalPairClassificationBinding` and existing M13-3 exact-scope lowering.
- Produces: a complete fifteen-row policy with `motor-r/shaft-a` included in M10 exact scope.

- [ ] Replace the false `("motor-r", "shaft-a")` excluded row with the default `CHECK_CLEARANCE` policy; retain only same-body exclusions and the truthful J2 contact exclusion.
- [ ] In both candidate and fresh-canonical assertions, derive expected count from `request.exact_pair_scope`, assert it is `11`, and assert the mapped `motor-r/shaft-a` pair is in scope and appears in every exact-result configuration.
- [ ] Run `py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k pair` with `MECHCAD_FREECADCMD` configured; expected result: selected pair assertions pass.

### Task 2: Diagnostic Restart Semantics

**Files:**
- Modify: `tests/integration/m13_4_acceptance_fixtures.py:383-394`
- Modify: `tests/integration/test_m13_4_full_stack_acceptance.py:95-194,916-1179`
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`

**Interfaces:**
- Consumes: candidate/canonical mappings, placement derivations, verification scope, and canonical obligation.
- Produces: JSON-primitive `_semantic_snapshot(...)` values containing exact checked scope, tolerances, derivations, member/body offsets, and the pre-existing physical semantics.

- [ ] Make `build_m134_application_at(workspace, config_root, project_id, *, agent=None)` require the explicit project ID; update all callers, with Phase B passing `locator["project_id"]` and only diagnostic equality against the fixture identifier.
- [ ] Extend `_semantic_snapshot` with canonical primitive records for exact scope, `volume_tolerance_mm3`, `distance_tolerance_mm`, complete `GeneratedPlacementDerivation` model data, and explicit per-member body/reference/local placement offset data using the existing rigid-transform comparison representation.
- [ ] Pass candidate request scope/tolerances/derivations into Phase A snapshot generation and canonical obligation/request/derivations into Phase B snapshot generation. Keep all canonical construction and M10 execution before the only snapshot read in Phase B.
- [ ] Add a direct decoded-JSON assertion that verifies each required snapshot category exists and is primitive-only after `json.dumps` / `json.loads` round trip.
- [ ] Run `py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k serialized_restart`; expected result: one restart test passes with snapshot comparison and no agent invocation.

### Task 3: Compilation And Durable Canonical Evidence

**Files:**
- Modify: `tests/integration/test_m13_4_full_stack_acceptance.py:458-640,1041-1179`
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`

**Interfaces:**
- Consumes: observed production compilation, promotion receipt, canonical M10 request/result, durable `EvidenceStore`, and `get_evidence_freshness`.
- Produces: direct capstone assertions for full receipt compilation and fully bound/current canonical M10 Evidence after durable reload.

- [ ] Assert exactly one observed compile and `receipt.compilation == observed_compilations[0]`, including full projection, projection hash, and full mapping equality without a second compile call.
- [ ] Persist only compilation/projection scalar hashes in the locator and retain the fresh-root receipt verification path.
- [ ] Reload canonical M10 Evidence from the existing application/store boundary and assert project, revision/hash, assembly, model, configuration set, inventory, exact scope, tolerances, request/result hash, provider, backend/version, execution mode, and current freshness.
- [ ] Run `py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k "compilation or serialized_restart"`; expected result: selected assertions pass.

### Task 4: Gate Evidence And Report

**Files:**
- Modify: `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md`
- Test: required focused, predecessor, regression, static, and full-suite commands from the M13-4 execution plan.

**Interfaces:**
- Consumes: final test output and truthful pair/snapshot/Evidence results.
- Produces: second-remediation traceability without independent acceptance claim.

- [ ] Run focused M13-4, M13-4P, M13-4E, predecessor, exact required M10/M12/CAD group, then one final full suite after the tree is stable.
- [ ] Run `py -3 -m compileall -q src tests`, `git diff --check`, `git status --short`, `git diff --stat`, and `git diff`; verify no second-remediation change below `src/mechcad_harness/` and no golden/hash change.
- [ ] Add a clearly labeled second-remediation section recording the final 15-pair table, 11-pair scope, snapshot fields, locator project identity, compilation equality, durable Evidence verification, exact gate output, pending re-audit status, and Rotator prohibition.
