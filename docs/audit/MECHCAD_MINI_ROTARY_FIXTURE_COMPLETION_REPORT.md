# MINI_ROTARY_FIXTURE Completion Report

## Claim Status

```text
MINI_ROTARY_FIXTURE_CORE_REJECTED
MILESTONE_COVERAGE_PARTIAL
```

This is a project completion claim, not independent acceptance. It does not
claim any historical milestone acceptance marker.

## Purpose And Baseline

`MINI_ROTARY_FIXTURE` is a bounded, project-local +Z single-axis rotary fixture
with two explicit square top-plate candidates: A `60 x 60 x 8 mm` and B
`50 x 50 x 8 mm`. Its purpose is maximum truthful exercise of the current
MechCAD chain, not mechanism synthesis, optimization, manufacturing, supplier,

Current source, architecture, capability inventory, and accepted M9/M10/M11/
M12-6/M13-4 audits were inspected. The accepted baseline anchor is M13-4, but
this report uses the current source for implementation truth.

The original implementation predecessor relevant to the prior audit was
`0997bf510e6888571b4468a2772abafddde29336`. The current remediation checkout
is `a11dc507adedb8e4466c4d2e1f0e01c4d6326c7d` on `master`. The MINI files in
this working tree are untracked project artifacts and are not claimed to be
immutably tied to the predecessor SHA. The retained N1 run below was executed
at the current remediation HEAD.

Evidence labels in this report are kept separate: `TEST EXECUTION` means a
pytest invocation, `RETAINED MINI FIXTURE EXECUTION` means a project-local run
whose durable records were reloaded, and `REGRESSION VERIFICATION` means a
current platform test gate. Regression verification does not count as MINI
fixture execution.

## Authority And Revisions

N1 was implemented and tested with:

- `project_id`: `mini_rotary_fixture`;
- 4.0 N force, 0.025 m lever arm, factor 2.0;
- 24 V and 5.0 mm clearance requirements;
- synthetic `fixture_actuator_01` authority;
- exact speed anchor requirement `REQ-TRANSMISSION-OUTPUT-SPEED`;
- no output-speed `AuthoritativeParameter`.

The intended user source value is `5.0 RPM`. The current resolution record
format accepts only deg/s or rad/s, so its normalized value would be
`0.5235987755982988 rad/s`; the acceptance record retains the original RPM
source value separately.

The retained MINI N1 execution used the current durable production stores:

- HEAD: `a11dc507adedb8e4466c4d2e1f0e01c4d6326c7d`;
- workspace: `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace`;
- project: `mini_rotary_fixture`;
- revision/hash: `1` /
  `sha256:634ca6fe26a39a2c6aa7f4255328e44170f3248eaf17c4f312d45f048acb6ddf`;
- run/task: `RUN-2df6e4b4-1031-470a-83f5-6e77d01232e7` /
  `TASK-MINI-N1-TORQUE`;
- tool: `mechcad-calc-torque@1.0`;
- ToolCall: `CALL-69a06e91-e9c5-4d27-bcdb-7834ed8afc81`;
- ToolResult: `TOOLRES-07b12a33-936e-4150-bfe5-55565571d5c2`;
- Evidence: `EVD-fc05f315-2718-519b-90c1-c2d8bee7ae15`;
- output: nominal `0.10 N*m`, design `0.20 N*m`.

The durable record locators are:

| Record | Locator |
| --- | --- |
| Current state pointer | `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace/projects/mini_rotary_fixture/current.json` |
| N1 revision snapshot | `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace/projects/mini_rotary_fixture/revisions/REV-000001.json` |
| Run manifest | `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace/projects/mini_rotary_fixture/runs/RUN-2df6e4b4-1031-470a-83f5-6e77d01232e7/manifest.json` |
| Task definition | `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace/projects/mini_rotary_fixture/runs/RUN-2df6e4b4-1031-470a-83f5-6e77d01232e7/tasks/TASK-MINI-N1-TORQUE/definition.json` |
| ToolCall | `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace/projects/mini_rotary_fixture/runs/RUN-2df6e4b4-1031-470a-83f5-6e77d01232e7/tool_calls/CALL-69a06e91-e9c5-4d27-bcdb-7834ed8afc81.json` |
| ToolResult | `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace/projects/mini_rotary_fixture/runs/RUN-2df6e4b4-1031-470a-83f5-6e77d01232e7/tool_results/TOOLRES-07b12a33-936e-4150-bfe5-55565571d5c2.json` |
| Evidence | `projects/mini_rotary_fixture/runtime/2026-09-15-n1/workspace/projects/mini_rotary_fixture/evidence/EVD-fc05f315-2718-519b-90c1-c2d8bee7ae15.json` |

Reload through `ProductionApplication.load_state`, `ToolStore`, and
`EvidenceStore` verified revision/hash equality, ToolCall and ToolResult
identity/binding, unchanged output, Evidence revision/hash binding, and
Evidence freshness `current`. The current ToolResult record reloads
successfully; its persisted `evidence_id` field is unset by the existing
production broker persistence order, while the separately persisted Evidence
record identifies the ToolResult through `producer_result_id`.

N2 and N3 were not created. F10 retired
`ConstraintResolutionApplicationService` and `ConstraintResolutionWorkflow`.
Current source retains `ConstraintResolutionMaterializer`, which persists typed
resolution records, but the generic required resolution-record ->
canonical-state application edge is `MISSING`. This is
`PLATFORM_CAPABILITY_GAP` / `REQUIRED_CURRENT_NOT_IMPLEMENTED`, not an existing
unwired workflow. Applying a local handwritten `ChangeProposal` as a substitute
or restoring the retired workflow would be a prohibited fixture-only bridge.
Therefore the required N1 -> N2 currentness check and the N2 -> N3 force
invalidation/recomputation sequence could not be truthfully run.

## N1 Evidence Levels

### TEST EXECUTION

Earlier focused pytest runs created temporary N1 workspaces and proved the
project-local driver output. Those runs are retained as test evidence only and
are not the durable MINI fixture run.

### RETAINED MINI FIXTURE EXECUTION

The durable run created N1 through `StateManager.create_project`, a
production-composed `ProductionApplication`, a bound `RunController` task, and
a `ToolBroker` call to `mechcad-calc-torque@1.0` with:

```json
{"force_n": 4.0, "lever_arm_m": 0.025, "safety_factor": 2.0}
```

The persisted and reloaded `analysis.transmission.torque` Evidence output was:

```json
{"nominal_torque_nm": 0.1, "design_torque_nm": 0.2}
```

The expected N3 calculation, not manually entered as Evidence, remains
`0.15 N*m` nominal and `0.30 N*m` design.

### REGRESSION VERIFICATION

Current platform regression suites independently verify the relevant tool,
Evidence, dependency, resolution, and M12 boundaries. They do not count as
MINI fixture execution and do not create candidate or promotion evidence.

## M6 To M12 Scalar Authority Gap

```text
PLATFORM_CAPABILITY_GAP
```

`RevoluteDriveEngineeringRequirements` requires `SourceBoundScalar` inputs and
`TrustedCanonicalScalarSourceBinding` records. The current
`_source_scalar_binding_defects` implementation requires every
`SOURCE_AUTHORITY` path to resolve in canonical `DesignState` to exactly:

```json
{"value": <number>, "unit": "<unit>"}
```

Current generic state records are descriptions or metadata. Its
`AuthoritativeParameter.value` is a typed `AuthoritativeValue` such as
`{"kind": "transmission.output_angular_speed", "value_rad_s": ...}`, not the
required scalar wire record. Tool/Evidence is derived/noncanonical and is not
candidate authority. Project-local ownership/dependency composition cannot
change the model shape or M12 validation semantics.

A fixture-local negative probe directly executed the current production
`_source_scalar_binding_defects` boundary with a source-bound 5.0 rpm scalar,
a matching `CandidateSourceBinding`, and a matching
`TrustedCanonicalScalarSourceBinding` targeting `/requirements/3`. It rejected
the resolved requirement record because it is not an explicit scalar record.
This is `SOURCE_INSPECTION_VERIFIED` plus production-validator negative-test
evidence for the gap, not a valid authority path and not MINI candidate
execution.

The current integration test
`tests/integration/test_m12_revolute_drive_production.py::test_recomputed_scalar_against_old_composite_source_record_fails_closed`
also passed. It reaches `ProductionApplication.realize_and_evaluate_revolute_drive`
and verifies `UNRESOLVED` rejection for a composite source record, providing
`RUNTIME_VALIDATION_VERIFIED` evidence for that tested rejection path only. The
MINI fixture did not execute that production candidate path with valid
requirements; the M12 candidate branch remains unexecuted.

The smallest reusable unimplemented extension is a typed domain-neutral
canonical scalar authority collection with `{value, unit}` wire records,
ownership, dependency rules, and trusted admission from authority resolution.
It was not implemented.

This blocks only M12 direct-drive candidate construction, candidate CAD/M10,
comparison, selection, promotion, fresh canonical reconstruction, and the
post-promotion M11 handoff. No M12-to-M13 bridge was created.

## Independent Probes

| Area | Result |
| --- | --- |
| M5.5 gear | `TESTED`: `py_gearworks` and `build123d` provider regression gate passed; no MINI M5.5 probe exists, and output remains noncanonical. |
| M5.5 materials | `BLOCKED_ENVIRONMENT`: `bd_materials` unavailable during discovery; no MINI material probe was invoked. |
| M5.5 section | `BLOCKED_ENVIRONMENT`: `sectionproperties` unavailable during discovery; no MINI section probe was invoked. |
| M6A real agent | `NOT_EXECUTED`: `MECHCAD_OPENCODE_LIVE` unset; no live agent invocation was attempted and no fake agent was credited. |
| M9 FreeCAD | Blocked: `discover_freecad()` found no deterministic local command; actual probe raised `FreeCADUnavailableError`. |
| M11 | `POST_PROMOTION_M11_HANDOFF=BLOCKED_UPSTREAM` because promotion never occurred; `M11_STANDALONE_SUBSYSTEM_PROBE=NOT_EXECUTED`, with FreeCAD/Gmsh unavailable and no standalone MINI invocation. |
| M13-1/M13-2 | `TESTED` by current regression gates only. No MINI invocation; M13-2 remains limited to cylindrical generated parts and no square-plate claim exists. |
| M13-3P/M13-3/M13-4 | Blocked before MINI execution: no M12 candidate/topology and no M12-to-M13 bridge. |

The planned fixed base/wall strategy remains a synthetic multi-solid
`motor-mount` STEP made only with existing `CadPartProgram`, `CadAssemblyProgram`,
FreeCAD, `ArtifactStore`, and trusted imported-component contracts. It was not
executed because the dependent M12 branch stopped before source CAD realization.

## Candidate, Promotion, And M11 Results

No M12 candidate was constructed. Candidate A/B identities, certified
clearances, comparison, selection, promotion, canonical reconstruction, FCStd,
STEP, and canonical M10 results are therefore unavailable. This is not an
infeasibility conclusion about either plate; it is a source-authority gate
failure before candidate construction.

## Commands And Results

Fresh remediation verification at
`a11dc507adedb8e4466c4d2e1f0e01c4d6326c7d`:

```text
py -3 -m pytest projects/mini_rotary_fixture/test_acceptance.py -q
4 passed, 1 skipped in 2.31s

py -3 -m pytest tests/unit/test_constraint_resolution.py -q
25 passed in 1.89s

py -3 -m pytest tests/unit/test_m12_revolute_drive_models.py tests/unit/test_m12_revolute_drive_service.py -q
78 passed in 2.65s

py -3 -m pytest tests/integration/test_m12_revolute_drive_production.py::test_recomputed_scalar_against_old_composite_source_record_fails_closed -q
1 passed in 2.43s


py -3 -c "from mechcad_harness.backends.freecad import discover_freecad; print(discover_freecad())"
FreeCADDiscovery(available=False, executable=None, version=None, importable=False, execution_boundary=None)
```

The retained earlier regression gates remain historical regression evidence only:
the gear provider gate recorded 16 passed, and the M13 supplied/generated-part
gate recorded 157 passed. Neither is MINI fixture execution.

Final static checks:

```text
py -3 -m compileall -q projects/mini_rotary_fixture
exit 0

git diff --check
seven pre-existing trailing-whitespace diagnostics in .superpowers/sdd/progress.md
```

## Protected Surfaces And Worktree

No file under `src/mechcad_harness/**`, `docs/architecture/**`,
`docs/reference/**`, `docs/reconstruction/**`, F10 documents, or existing
platform tests was modified by this remediation. The current checkout remains
`a11dc507adedb8e4466c4d2e1f0e01c4d6326c7d`; the untracked MINI artifacts and
durable runtime records are not claimed as immutable content of
`0997bf510e6888571b4468a2772abafddde29336`. No commit, push, tag, release,
package installation, or history operation was performed. Concurrent and
unrelated worktree changes were preserved.

## Remaining Gaps

- `PLATFORM_CAPABILITY_GAP` / `REQUIRED_CURRENT_NOT_IMPLEMENTED`: F10 retired
  the former resolution application workflow; typed resolution materialization
  does not provide generic resolution-record-to-canonical-state application.
- `PLATFORM_CAPABILITY_GAP`: no domain-neutral canonical scalar `{value, unit}`
  authority can satisfy current M12-3 source-bound scalar validation.
- `BLOCKED_ENVIRONMENT`: no deterministic FreeCAD, Gmsh, CalculiX,
  `bd_materials`, or `sectionproperties` runtime is available.
- `BLOCKED_ENVIRONMENT`: real OpenCode validation opt-in is not configured.

MINI_ROTARY_FIXTURE_READY_FOR_REAUDIT
