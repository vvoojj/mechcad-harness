# MechCAD Implementation / Integration Audit Result

**Audit mode:** independent, clean-session, read-only implementation and integration audit

**Audit date:** 2026-08-21

**Normative baseline:** `AGENTS.md`, `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`, `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`, `docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`, `docs/architecture/MECHCAD_RUNTIME_FLOW.md`, and required milestone specifications where applicable.

**Allowed verdicts:** `IMPLEMENTED_AND_CONNECTED`, `IMPLEMENTED_BUT_UNUSED`, `TEST_ONLY`, `STUB_OR_PLACEHOLDER`, `MISSING`, `BOUNDARY_VIOLATION`.

## A. Repository / Audit Identity

| Item | Evidence |
|---|---|
| Branch | `master` |
| HEAD | `9ab9e48b8bc54202d5fddd5edc85e7f8c7c3b903` (`feat: complete M7C1 kinematic sweep closure`) |
| Dirty state | Dirty before audit. Tracked changes: `README.md`, `config/ownership.yaml`, `src/mechcad_harness/models/design.py`, `src/mechcad_harness/yagi_carrier_packaging.py`. 131 untracked paths, including documentation, tests, source, and generated workspace content. Existing changes were not modified. |
| Python | `3.14.6`; project requires Python `>=3.11`. |
| Pydantic | Focused and full tests import successfully. |
| FreeCAD | `discover_freecad()` returned `available=False`, `executable=None`, `version=None`, `importable=False`. |
| Optional providers | `py_gearworks`, `build123d`, `bd_materials`, `sectionproperties` were not available to fresh runtime checks. NumPy import also failed with a native DLL error in the available Python environment. |

## B. Baseline Verdict Summary

The capability matrix contains 38 `FOUNDATION` / `REQUIRED_CURRENT` rows. Rows below are grouped only where they have the same implementation boundary and evidence; every baseline row is represented. The missing specialized-gear-to-assembly bridge is a connected-readiness finding, not a baseline row.

| Verdict | Count |
|---|---:|
| `IMPLEMENTED_AND_CONNECTED` | 15 |
| `IMPLEMENTED_BUT_UNUSED` | 18 |
| `TEST_ONLY` | 1 |
| `STUB_OR_PLACEHOLDER` | 0 |
| `MISSING` | 0 |
| `BOUNDARY_VIOLATION` | 4 |
| **Total** | **38** |

The count treats a capability as connected only when a real production call path reaches a downstream consumer. Test-created service graphs do not count as production callers.

## Baseline Audit Matrix

| Capability | Contract Requirement | Implementation | Caller | Downstream Consumer | Library/Tool | Unit Test | Integration Test | Runtime Proof | Provenance/Hash Proof | Boundary Check | Verdict | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| canonical `DesignState` | Typed canonical engineering authority | `models/design.py:70-92` | `StateManager`, `ChangeEngine`, runs, agents, resolution | Revisions, context, changes, CAD bindings | Pydantic | `test_state_foundation.py`, `test_models.py` | State/agent/CAD fixtures | Full focused/full suite | Canonical model serialization and state hash | Separate external records; no direct mutation in audited paths | `IMPLEMENTED_AND_CONNECTED` | Canonical state is consumed by multiple production services. |
| immutable revision/hash | Immutable snapshot, current pointer, reload/tamper verification | `state/manager.py:42-81,116-135` | `ChangeEngine`, `RunController`, readers | Current/revision-bound tasks, evidence, artifacts | SHA-256/filesystem | `test_state_foundation.py`, provenance tests | Resolution and CAD service fixtures | Fresh unit/runtime-independent persistence checks | Revision snapshots, current pointer, recomputed hash, exclusive writes | State changes go through revision API | `IMPLEMENTED_AND_CONNECTED` | General engine path lacks a standalone receipt, but revision persistence is real. |
| `ChangeProposal` | Bound non-authoritative operations | `models/proposal.py:15-27` | Agent response materialization, resolution application | `ChangeEngine` | None | `test_changes.py`, resolution tests | Round-trip/resolution fixtures | Unit proof only | Base revision/hash and operation identity | Proposal cannot directly mutate canonical state | `IMPLEMENTED_AND_CONNECTED` | |
| `ChangeSet` / `ChangeEngine` | Stale/operation/ownership validation and immutable next revision | `changes/engine.py:108-149` | `RunController`, constraint resolution | `StateManager`, run convergence | StateManager | `test_changes.py`, resolution application | Resolution workflow | Unit/workflow proof | Preparation/receipt records in resolution path | Central mutation boundary is used by audited callers | `IMPLEMENTED_AND_CONNECTED` | General `apply_proposal` returns an in-memory result; resolution path persists stronger receipts. |
| ownership enforcement | Owner-scoped paths fail closed | `changes/ownership.py:45+` | `ChangeEngine` | Accepted/rejected proposal | Ownership policy | `test_changes.py`, ownership tests | Resolution application fixtures | Unit proof | Owner/path checks and receipt binding | Unowned/unrelated paths reject | `IMPLEMENTED_AND_CONNECTED` | |
| dependency graph / invalidation | Deterministic direct/transitive impact and immutable records | `dependency/graph.py:149-165`, `dependency/storage.py:39-67` | Run proposal application, resolution workflow | Evidence freshness and stale tasks | Dependency graph/EvidenceStore | `test_dependency.py` | Run/state application fixtures | Unit/workflow proof | Invalidation records bind revision and paths | Evidence remains separate from canonical state | `IMPLEMENTED_AND_CONNECTED` | |
| Evidence freshness | Exact `CURRENT`/`STALE`/`UNKNOWN` over complete history | `dependency/storage.py:84-106` | Context builder, run controller, round trip | Agent context, evidence rebuild gating | EvidenceStore | Dependency, gateway, round-trip tests | Round-trip fixture | Unit/workflow proof | Snapshot hash and intervening invalidations checked | Fail-closed freshness behavior observed | `IMPLEMENTED_AND_CONNECTED` | |
| `RunController` | State-bound orchestration, task DAG, completion/convergence/recovery | `runs/controller.py:15-186` | No non-test application entry point found | Test executors and service fixtures | RunStore | `test_runs.py` | Agent/CAD integration fixtures only | No fresh external runtime | Manifest/task/result bindings are persisted | No direct state mutation | `IMPLEMENTED_BUT_UNUSED` | Real controller implementation exists, but repository production code does not construct and dispatch it. |
| manifest / replay | Immutable source manifest and recoverable transitions | `runs/persistence.py:44-85` | `RunController` only in test-created workflows | Run/task/result recovery | Filesystem | `test_runs.py`, agent tests | No non-test application caller | No fresh external runtime | Manifest identity and state bindings persisted | No rollback path observed | `IMPLEMENTED_BUT_UNUSED` | |
| `ToolRegistry` | Exact registration and lookup | `tools/registry.py:5-20` | Broker/service construction in fixtures | `ToolBroker` | Registered handlers | `test_tools.py`, provider tool tests | Mediation/round-trip fixtures | Unit proof | Exact `(name, version)` lookup | Duplicate/unknown identity fails closed | `IMPLEMENTED_AND_CONNECTED` | Connected within production-capable broker and mediator objects, though no application entry point exists. |
| `ToolBroker` | Typed, bound, permissioned execution with immutable records | `tools/broker.py:21-81` | Gateway mediator and test-created services | Tool handlers, ToolResult, Evidence | Registered handlers | `test_tools.py`, mediation tests | Round-trip/provider fixtures | Unit proof only | ToolCall before execution, ToolResult persistence | **Accepts bare `tool_name` permission for versioned call at `broker.py:35-37`; exact workflow mediator is stricter.** | `BOUNDARY_VIOLATION` | Global broker behavior contradicts the exact permission/version baseline. |
| `ToolCall` / `ToolResult` | Immutable input/output and provenance records | `tools/persistence.py:35-49`, broker | ToolBroker | Evidence materializer, downstream evaluators | ToolStore | `test_tools.py` | Round-trip/provider fixtures | Unit proof | Input/output hashes, state/task bindings | Persistence precedes handler execution | `IMPLEMENTED_AND_CONNECTED` | |
| Evidence materialization | Eligible successful ToolResult becomes bound Evidence | `tools/evidence.py:21-50` | ToolBroker and round-trip coordinator | Agent context and freshness store | EvidenceStore | Tool/evidence/round-trip tests | Round-trip fixture | Unit/workflow proof | ToolCall/result, registration, output and state bindings | Evidence is not canonical authority | `IMPLEMENTED_AND_CONNECTED` | |
| `AgentGateway` | Bound context, schema/hash, invocation, stale response checks | `agents/gateway.py:16-118` | Round-trip coordinator and tests; no application entry point | AgentResult, observations, mediator | Agent registry/adapters | Gateway/authored-response tests | Opt-in OpenCode gateway tests | OpenCode runtime unavailable | Context/request/response schema hashes and bindings | **Gateway materializes every identity with `role="test"` at `gateway.py:36`, losing registered production role.** | `BOUNDARY_VIOLATION` | The gateway boundary is real but identity authority is corrupted. |
| `FakeAgentAdapter` | Deterministic no-I/O test adapter | `agents/fake.py:6-28` | Tests and gateway fixtures | AgentResult | None | Agent gateway/runtime tests | No production integration by contract | Test-only | Invocation binding | Correctly isolated from external I/O | `TEST_ONLY` | |
| OpenCode transport | Strict HTTP transport and validated response | `agents/opencode.py:141-304` | Test-created gateway/live tests | AgentGateway materialization | OpenCode/Luna HTTP | Adapter/gateway unit tests | Opt-in live tests only | Not available; live mode not run | Adapter/provider/model/server/session/message/request/schema provenance | Deny-all permissions; no model-owned IDs | `IMPLEMENTED_BUT_UNUSED` | Implementation exists but no production application caller was found. |
| structured response validation | Native schema or one whole JSON document; no repair/fallback | `agents/opencode.py:244-304`, materialization | OpenCode adapter -> gateway | Typed AgentResponsePayload | Pydantic JSON Schema | Adapter/authored-response tests | Opt-in OpenCode tests | No external runtime | Schema hash, response mode, request hash | Tool parts/regex/repair are rejected | `IMPLEMENTED_AND_CONNECTED` | Connected inside gateway transport path; external execution unavailable. |
| `mechcad-transmission` contract | Bounded transmission reasoning identity and output | Gateway/adapter contracts; roundtrip models | Tests and roundtrip only | Tool mediation/constraint discovery | OpenCode adapter | Transmission agent tests | Opt-in live tests | No OpenCode proof | Request/result bindings present | **Registered identity role is overwritten as `test`; no independently verified production executable registration/caller.** | `BOUNDARY_VIOLATION` | A registry label is not proof of a correctly constrained production engineering agent. |
| semantic transmission mediation | Semantic request -> exact authorized tool | `agents/tool_mediation.py:60-122` | Gateway when configured; roundtrip coordinator | ToolBroker/ToolResult | Torque tool | Mediation tests | Roundtrip fixture/live opt-in | Conditional only | Exact capability mapping and task/state binding | Mediator requires exact `name@version` | `IMPLEMENTED_AND_CONNECTED` | |
| torque Evidence round trip | Invocation A -> one tool -> Evidence -> Invocation B, recovery | `agents/roundtrip.py:23-179` | Tests and coordinator fixtures | AgentResult terminal record, Evidence | Torque ToolBroker path | `test_agent_roundtrip.py` | Opt-in live roundtrip | Live unavailable/not run | Immutable transitions and binding hashes | Second tool request rejected; recovery does not repeat success | `IMPLEMENTED_BUT_UNUSED` | Complete subsystem path exists, but no non-test workflow starts it. |
| ConstraintRequest discovery | Four supported typed drafts/observations | `agents/constraint_requests.py`, gateway observation path | Roundtrip coordinator only | Materializer/store/resolution | Structured response | Constraint request/roundtrip tests | Opt-in live discovery | No external runtime | Deterministic draft/request identity | Exact supported keys; no fuzzy matching | `IMPLEMENTED_BUT_UNUSED` | |
| ConstraintRequest materialization | Deterministic persistent lifecycle record and idempotency | `agents/constraint_requests.py:38-127` | Roundtrip coordinator | Resolution workflow | RequestStore | Constraint request/roundtrip tests | No non-test application caller | Unit/workflow proof | Hash based on project/scope/revision/state/key | Existing records are reused; exact anchors suppress satisfaction | `IMPLEMENTED_BUT_UNUSED` | |
| constraint satisfaction | Suppress only exact authoritative anchors | `agents/constraint_requests.py:70-87` | Discovery/resolution workflows | Request lifecycle and proof | Canonical state | Constraint/resolution tests | Workflow fixtures | Unit/workflow proof | Exact key/scope/value discriminator | No fuzzy/LLM satisfaction | `IMPLEMENTED_AND_CONNECTED` | Connected to resolution internals. |
| constraint resolution loop | Trusted answer -> proposal/change/revision/invalidation | `agents/constraint_resolution_workflow.py:55-133`, application service | Tests/workflow callers only | StateManager, EvidenceStore, request proof | ChangeEngine | Resolution application/workflow tests | No live integration | Unit/workflow proof | Preparation/receipt/revision/invalidation IDs | No direct canonical mutation observed | `IMPLEMENTED_BUT_UNUSED` | Internal path is real; no production application caller obtains and submits external answers. |
| `py_gearworks` calculation | Real pinned provider invocation and normalized result | `backends/adapters/py_gearworks.py:47-80` | `GearworksTools` in test-created broker | ToolResult/Evidence | `py_gearworks` | Gear backend/tool tests, skipped if absent | No fresh provider integration | Provider unavailable | Adapter/backend identity and Git revision | Narrow provider boundary is present | `IMPLEMENTED_BUT_UNUSED` | No current production workflow caller; package unavailable in audit runtime. |
| specialized gear CAD | py_gearworks -> build123d -> STEP/STL -> ArtifactStore | `backends/gearworks_cad.py:23-58` | Gear CAD tool registration/test broker | ArtifactStore/result consumers | py_gearworks/build123d | Gear CAD tests, skipped if absent | No fresh provider integration | Providers unavailable | **Uses py_gearworks provenance only; build123d runtime identity absent.** | **Insufficient deterministic replay provenance.** | `BOUNDARY_VIOLATION` | Specialized path is correctly separate from generic CAD, but provenance is incomplete. |
| material lookup / mass | Normalized bd_materials properties/mass | `backends/bd_materials.py:46-80` | Material tool registration/test broker | Section engineering tool in test-created path | bd_materials | Material tests, skipped if absent | No fresh provider integration | Provider unavailable | Backend/library provenance and typical authority status | Lookup is not canonical selection | `IMPLEMENTED_BUT_UNUSED` | |
| section geometry / warping | Normalized section results, oracle/convergence checks | `backends/section_properties.py:78-287` | Section tool registration/test broker | Preliminary section engineering | sectionproperties/NumPy/SciPy | Section backend/tool/warping tests, skipped if absent | No fresh provider integration | Provider unavailable; NumPy import failed | Provider provenance, convergence, analytic checks | No FEA/approval claim | `IMPLEMENTED_BUT_UNUSED` | |
| preliminary section integration | Persisted provider results -> normalized preliminary engineering result | `tools/section_engineering.py:69-151` | Test-created broker only | ToolResult/Evidence | Native arithmetic + provider results | Section engineering tests | No production workflow caller | Unit proof | Source result IDs and provider provenance retained | Preliminary status preserved | `IMPLEMENTED_BUT_UNUSED` | |
| `CadPartProgram` / CAD compiler | Typed generic operations and deterministic program hash | `cad_program.py:93+`; compile in FreeCAD backend | Direct program constructors/test services; no accepted DesignSpec compiler caller found | FreeCAD part backend | Generic CAD operations | CAD program/compiler tests | FreeCAD live tests only | FreeCAD unavailable | Program/source hashes and state binding | **No production accepted-DesignSpec -> compiler caller.** | `IMPLEMENTED_BUT_UNUSED` | Lower-level program execution is real; the normative compiler ingress is unused. |
| `CadAssemblyProgram` | Typed parts, instances, rigid transforms, deterministic ordering | `cad_assembly.py:46+` | Assembly/analysis/sweep test-created services | FreeCAD assembly, transient, kinematics | FreeCAD assembly backend | Assembly/integrity tests | Assembly live tests only | FreeCAD unavailable | Assembly hash, component/instance identity | Generic/domain separation observed | `IMPLEMENTED_AND_CONNECTED` | Connected across production-capable services, but no application orchestrator invokes it. |
| FreeCAD part / assembly realization | Persist FCStd/STEP, fresh reload, geometry/placement verification | `backends/freecad.py:256-348`, `freecad_assembly.py:133-232` | CAD services constructed by tests | ArtifactStore, analysis/sweep inputs | FreeCAD | FreeCAD backend/assembly verification tests | Live tests skipped | FreeCAD unavailable | Part provenance exists; assembly provenance incomplete and historical artifacts use older identity | Assembly output hard-codes `freecad_version="1.1.3"` and omits backend provenance | `IMPLEMENTED_BUT_UNUSED` | Real implementation exists, but no production app caller and no fresh current runtime proof. |
| ArtifactStore / durable CAD | Immutable hashed derived artifacts, no overwrite, bindings | `artifacts/storage.py:28-82` | Gear/CAD/analysis services | Artifact references, reload verification | Filesystem/SHA-256 | `test_artifacts.py` | CAD/provider live tests only | Existing historical artifacts only | Artifact SHA-256, size, source revision/hash, input hash | Derived storage cannot promote canonical state | `IMPLEMENTED_AND_CONNECTED` | |
| exact collision / clearance | `common().Volume` plus `distToShape()` classifications | `cad_analysis.py:128-165` | Analysis service/test-created path | Analysis result/Evidence/artifact | FreeCAD Part | CAD analysis tests | Live analysis skipped | Historical artifacts only; FreeCAD unavailable now | Assembly artifact/hash and source revision/state | Generic exact geometry boundary is clean; no manufacturing approval | `IMPLEMENTED_BUT_UNUSED` | Algorithm and downstream service exist, but no application caller. |
| transient assembly analysis | Temporary transformed measurement, no state/artifact side effect | `transient_assembly_analysis.py:27-44` | Kinematic service/test-created path | Sweep samples | Measurement provider | Transient analysis tests | M7C transient live skipped | FreeCAD unavailable | Source/transformed/sweep hashes | No ArtifactStore or revision mutation in path | `IMPLEMENTED_BUT_UNUSED` | |
| generic single-axis sweep | Normalized axis, partitions, ordered samples/pairs, exact aggregate | `kinematic_sweep.py:94-272` | M7D/test-created adapter path | Sweep result | Transient provider | Kinematic tests | M7C/M7D live skipped | FreeCAD unavailable | Request/transformed/result hashes and ordered inventories | `continuous_sweep_verified=False`; no Yagi semantics in generic service | `IMPLEMENTED_BUT_UNUSED` | |
| domain extension framework | Domain authority/spec -> thin adapter -> generic services | Yagi modules and generic contracts | Unit/integration fixtures | Generic request/result | Generic CAD/kinematics | Yagi/M7D tests | M7D live skipped | No FreeCAD runtime | Layout/reference/assembly hashes | Yagi does not mutate DesignState or redefine generic axis | `IMPLEMENTED_BUT_UNUSED` | |
| reference domain adapter proof | Yagi layout/reference -> generic sweep request | `yagi_el_reference.py:19-41`, `yagi_el_sweep.py:45-102` | Test-created M7D adapter path | `CadKinematicSweepService` | Generic transient service | M7D unit tests | M7D live skipped | FreeCAD unavailable | Source layout/reference/assembly/request hashes | Domain provenance and executable assembly provenance remain separate | `IMPLEMENTED_BUT_UNUSED` | |

## C. State / Change / Dependency Findings

The canonical mutation path is implemented as:

```text
DesignState
 -> ChangeProposal
 -> ChangeEngine.prepare_proposal
 -> stale / operation / ownership / Pydantic validation
 -> StateManager immutable revision and current pointer
```

`StateManager` reload recomputes and verifies state hashes. Constraint resolution adds durable preparation and receipt records, and the run/resolution paths create invalidation records and verify exact satisfaction against the resulting state. No audited agent/provider/CAD path directly mutates canonical state.

The main limitation is connectivity: there is no discovered production application or scheduler entry point that constructs the complete run, gateway, mediator, provider, CAD, and analysis graph. General `ChangeEngine.apply_proposal` also does not persist a standalone application receipt; the stronger persisted receipt behavior is present in the M6B-4 resolution application path.

## D. RunController Findings

`RunController` implements run identity, source revision/hash binding, manifest persistence, task binding, result validation, convergence tracking, proposal application, invalidation, resume checks, and no-rollback behavior in its service API. Tests exercise these paths. No non-test caller was found that creates a run, adds tasks, and executes it. Verdicts for `RunController` and manifest/replay are therefore `IMPLEMENTED_BUT_UNUSED`.

## E. ToolBroker Findings

`ToolRegistry` resolves exact `(name, version)` registrations. `ToolBroker` persists `ToolCall` before handler execution and `ToolResult` for success/failure, validates typed inputs, binds task/run/revision/state, and can materialize Evidence.

Observed permission behavior:

```text
ToolBroker: permission matches exact name@version OR bare tool name
AgentToolMediator: permission must match exact name@version
```

The broker condition is at `src/mechcad_harness/tools/broker.py:35-37`. Thus a task permission containing `mechcad-calc-torque` can permit `mechcad-calc-torque@1.0` at the broker, while the M6B mediator rejects the same bare permission before broker execution. This is the documented M5 ambiguity observed in actual code. It is a `BOUNDARY_VIOLATION` because the global broker does not fail closed on exact version permission.

## F. Agent / OpenCode Findings

The gateway builds bound context, computes context and schema hashes, creates immutable invocation records, validates authored output, rejects stale response bindings, and persists results and observations. The OpenCode adapter supports native schema and explicit whole-JSON-text modes without regex extraction, repair, or fallback. It denies model-side tools.

No application entry point was found that registers and dispatches OpenCode in production. OpenCode construction is present in tests and opt-in live fixtures. The live external runtime was unavailable and was not started.

The gateway creates `AgentIdentity(... role="test")` for every requested agent at `src/mechcad_harness/agents/gateway.py:33-36`. This means the `mechcad-transmission@1.0` production contract cannot retain its registered engineering role through the trusted gateway boundary. The implementation is therefore a `BOUNDARY_VIOLATION`, independent of whether its tests pass.

`mechcad-transmission@1.0` is represented by policy/schema and test-created adapter registrations, but no independently verified production executable agent registration and caller were found. A registry label alone is not executable-agent proof.

## G. M6B Findings

### M6B-1

**Verdict:** `IMPLEMENTED_BUT_UNUSED`.

Gateway, strict adapters, schema advertisement/hash, invocation identity, stale checks, authored/trusted separation, and OpenCode transport are implemented. No non-test production caller dispatches the gateway. Live proof is opt-in and external runtime was unavailable.

### M6B-2A

**Verdict:** `IMPLEMENTED_AND_CONNECTED`.

The internal production-capable path is `AgentGateway -> AgentToolMediator -> exact capability mapping -> ToolBroker -> ToolRegistry -> torque handler -> ToolCall/ToolResult`. Exact workflow permission is enforced by the mediator. It is exercised by the round-trip coordinator and focused tests, though no application entry point starts the workflow.

### M6B-2B

**Verdict:** `IMPLEMENTED_BUT_UNUSED`.

The coordinator enforces one tool execution, current Evidence, a second no-tool invocation, immutable transitions, and recovery without repeating successful calls. Focused tests prove these invariants. No non-test production caller was found, so the overall capability is not production-connected. This verdict is independent of the design-only acceptance provenance ambiguity.

### M6B-3

**Verdict:** `IMPLEMENTED_BUT_UNUSED`.

Typed supported-key drafts, observations, deterministic IDs, exact satisfaction anchors, persistence, idempotency, and resolution consumption are implemented. The only callers found are coordinator/workflow/test paths; no application-level production caller starts discovery.

### M6B-4

**Verdict:** `IMPLEMENTED_BUT_UNUSED`.

Trusted resolution reaches `ChangeProposal -> ChangeEngine -> immutable revision -> receipt -> invalidation -> exact satisfaction`. Replay, stale binding, ownership, and batch atomicity are tested. No production application caller obtains trusted answers and invokes the workflow outside test-created services.

## H. Engineering Provider Findings

### py_gearworks

The adapter invokes real `py_gearworks.SpurGear` and pair mesh operations and normalizes results. Registration and ToolBroker paths exist, with adapter/Git revision provenance and health checks. The package was unavailable in the audit runtime, and no non-test production caller was found. Verdict: `IMPLEMENTED_BUT_UNUSED`.

### build123d

The specialized gear path calls `gear.build_part()`, exports STEP/STL, validates shape metrics, and publishes artifacts. It is distinct from generic FreeCAD project CAD. No typed bridge turns its pair result into `CadAssemblyProgram`; that bridge is `MISSING` and is intentionally not bypassed.

The build123d path records only py_gearworks adapter provenance. It does not record the actual build123d package/runtime version in `SpurGearCadResult` or artifact provenance. Because a build123d change can alter artifact bytes without changing recorded provider identity, this is a `BOUNDARY_VIOLATION` against deterministic provenance requirements.

### bd_materials

The adapter performs version/profile checks, real lookup/mass calls when installed, and returns typical-reference authority plus backend/library provenance. It is exposed through tools and consumed by preliminary section engineering in test-created broker graphs. No production workflow caller was found. Verdict: `IMPLEMENTED_BUT_UNUSED`. Lookup is not canonical material selection.

### sectionproperties

The adapter supports geometry/warping inputs, direct solver calls, analytic checks, and convergence. Tool registration and preliminary section integration exist. No production workflow caller was found. Provider package/runtime was unavailable and NumPy failed to import in the audit environment. Verdict: `IMPLEMENTED_BUT_UNUSED`.

## I. CAD / Assembly Findings

Typed generic `CadPartProgram` and `CadAssemblyProgram` models, operation validation, hashes, FreeCAD generation, FCStd/STEP export, fresh reload, shape/solid checks, placement checks, and ArtifactStore publication exist. The lower-level services are production-capable but are constructed only by tests or direct callers; no accepted `DesignSpec -> compiler` application path was found. The generic CAD compiler is therefore `IMPLEMENTED_BUT_UNUSED`; direct program realization is `IMPLEMENTED_BUT_UNUSED` at application level despite real implementation.

Assembly identity, instance identity, rigid transforms, ordering, component artifact verification, placements, fresh reload, and solid checks are implemented. Specialized gear results are two artifacts plus nominal transform information and cannot enter generic assembly without a typed imported-component bridge. That bridge is `MISSING`.

Assembly artifact publication omits `backend_provenance` and the returned assembly result hard-codes FreeCAD version `1.1.3` at `backends/freecad_assembly.py:220`. Historical artifacts also use older backend identity than current source. These are provenance concerns, but the audit assigns the explicit boundary verdict to the build123d provenance defect and records assembly provenance as incomplete evidence.

## J. Collision / Transient / Kinematic Findings

Exact collision and clearance use `Shape.common().Volume` and `Shape.distToShape()` with the required interference/touching/positive-clearance classifications. Transient analysis uses temporary workspaces and preserves source/transformed hashes without ArtifactStore or DesignState side effects. Generic sweep normalizes non-zero axes, validates complete partitions, preserves ordered angles/pairs, uses quaternion transforms, hashes requests/results, and sets `continuous_sweep_verified=False`.

These implementations are covered by focused tests and opt-in FreeCAD live tests, but no application-level production caller was found and FreeCAD was unavailable for fresh runtime proof. Verdicts: exact collision/clearance, transient analysis, and generic sweep are `IMPLEMENTED_BUT_UNUSED`.

## K. Domain Boundary Findings

The Yagi EL reference and sweep adapters preserve parametric EL authority, source layout/reference hashes, generic `RevoluteAxis`, generic `CadKinematicSweepRequest`, and separate source assembly provenance. Generic kinematic code contains no Yagi/AZ/EL semantics. No direct DesignState mutation or manual generic request mutation was observed.

The real M7D-shaped path is present in test-created integrations:

```text
Yagi layout/reference
 -> Yagi thin adapter
 -> CadKinematicSweepRequest
 -> CadKinematicSweepService
 -> TransientAssemblyAnalysisService
 -> FreeCAD transient provider
 -> exact result
```

It is `IMPLEMENTED_BUT_UNUSED` because no non-test application caller was found and FreeCAD runtime proof was unavailable. It is reference integration, not complete rotator synthesis.

## L. Connected-Readiness Map

Target: generic motor-driven rotary bracket. This is a connectivity assessment, not an implementation claim.

| Edge | Classification | Evidence |
|---|---|---|
| Requirements -> DesignState | `CONNECTED` | Typed state is consumed by state, change, run, agent, and CAD-boundary services. |
| DesignState -> production agent | `DISCONNECTED` | AgentGateway is implemented, but no application entry point constructs/dispatches it. |
| production agent -> deterministic tool/provider | `MISSING_BRIDGE` | M6B mediation is internally connected; no universal production agent workflow reaches py_gearworks/material/section providers. |
| deterministic tool/provider -> Evidence | `CONNECTED` | ToolBroker and Evidence materialization persist bound results; provider-specific paths are test-created. |
| Evidence -> ChangeProposal | `DISCONNECTED` | Round-trip and constraint-resolution internals support it, but no application workflow connects the universal target. |
| ChangeProposal -> ChangeSet/revision | `CONNECTED` | ChangeEngine and StateManager path is implemented and tested. |
| revision -> generic CAD | `MISSING_BRIDGE` | No accepted DesignSpec-to-program production compiler ingress found. |
| generic CAD -> assembly | `CONNECTED` | Typed assembly and FreeCAD backend paths consume generic parts. |
| specialized gear artifact -> assembly | `MISSING_BRIDGE` | No typed imported STEP/component asset bridge; pair result is not a CadAssemblyProgram. |
| assembly -> exact collision/clearance | `CONNECTED` | Analysis service and exact FreeCAD measurement implementation exist. |
| assembly -> transient analysis | `CONNECTED` | Transient service/provider path exists and is consumed by sweep. |
| transient analysis -> kinematics | `CONNECTED` | Sweep invokes transient measurement with bound transformed assembly and ordered pairs. |
| kinematics -> verified universal result | `DISCONNECTED` | Generic result path is implemented but only test-created callers were found. |

Overall universal path:

```text
Requirements -> DesignState [CONNECTED]
-> production agent [DISCONNECTED]
-> tool/provider [MISSING_BRIDGE]
-> Evidence [CONNECTED internally]
-> proposal [DISCONNECTED at application level]
-> revision [CONNECTED internally]
-> CAD [MISSING_BRIDGE from accepted DesignSpec]
-> assembly [CONNECTED internally]
-> kinematics [DISCONNECTED at application level]
```

## M. Missing Bridges

- Production application/scheduler entry point that creates a state-bound RunController workflow and dispatches AgentGateway.
- Production registration/caller path for `mechcad-transmission@1.0` with preserved engineering role.
- Accepted DesignSpec to deterministic generic `CadPartProgram` / `CadAssemblyProgram` compiler ingress.
- py_gearworks result to build123d gear geometry as a production agent/provider workflow.
- build123d STEP/solid to typed generic imported component / `CadAssemblyProgram` bridge.
- bd_materials result to engineering comparison and canonical material-selection proposal. Lookup exists; selection is `TARGET_NEXT` and not implemented here.
- Accepted assembly to a production universal kinematic workflow caller.

## N. Boundary Violations

- `ToolBroker` permits a bare tool name to authorize a versioned tool execution at `src/mechcad_harness/tools/broker.py:35-37`, while the exact permission contract requires fail-closed version identity. The mediator is stricter, producing an observed semantic split.
- `AgentGateway` overwrites the requested/registered agent role with `"test"` at `src/mechcad_harness/agents/gateway.py:33-36`, undermining the bounded `mechcad-transmission` production identity.
- Specialized build123d artifacts use py_gearworks provenance without recording build123d runtime identity at `src/mechcad_harness/backends/gearworks_cad.py:23-54`, weakening deterministic replay provenance.

Assembly provenance is also incomplete: `freecad_assembly.py:157-158` publishes without backend provenance and `freecad_assembly.py:220` hard-codes FreeCAD `1.1.3`. This is recorded as an evidence/provenance gap and risk; it was not counted as a separate verdict to avoid double-counting the same assembly capability row.

## O. Highest-Priority Fixes

No fixes were implemented. Priority order:

1. Establish one real production orchestration entry point that binds RunController, AgentGateway, exact ToolBroker mediation, Evidence, ChangeEngine, CAD, assembly, and discrete kinematics.
2. Correct the trusted agent identity path so production roles and agent policy are preserved through gateway invocation.
3. Make tool permission semantics fail closed on exact `name@version` identity at every broker boundary.
4. Add complete provider/backend provenance, including actual build123d identity and current FreeCAD runtime identity, to durable derived records.
5. Add the typed specialized-gear imported-component bridge if gear artifacts are intended to enter generic assembly.
6. Add accepted DesignSpec compiler ingress and an application caller for generic CAD.

## P. Verification

| Check | Result |
|---|---|
| Focused state/change/dependency/run tests | `43 passed in 7.05s` |
| Focused tools/agents/constraints tests | `72 passed in 12.36s` |
| Focused CAD/assembly/transient/kinematic/artifact tests | `57 passed in 2.13s` |
| Focused OpenCode/gateway/agent tests | `64 passed in 5.87s` |
| Full test suite | `514 passed, 48 skipped in 164.20s` |
| Skipped/runtime-gated tests | Optional provider tests, FreeCAD tests, and `MECHCAD_OPENCODE_LIVE=1` tests. |
| FreeCAD runtime | Not available; no FreeCAD process was started. |
| OpenCode/Luna live smoke | Not run; external runtime unavailable/not confirmed. |
| Provider runtime | Not available in audit environment; no provider installation or mutation performed. |
| Real DesignState mutation | None performed. |
| Generated artifact mutation | None performed by audit. Existing workspace artifacts were not changed. |

Passing tests establish implementation behavior for their exercised paths. They do not establish production callers, universal connectivity, external runtime availability, or provenance completeness.

## Q. Final System Classification

**BASELINE_HAS_BOUNDARY_VIOLATIONS**

The repository has substantial implementations and the focused/full test suites pass, but actual implementation inspection found boundary violations in exact tool permission enforcement, agent identity materialization, and specialized build123d provenance. It also remains only partially connected at application level. The boundary-violation classification takes precedence over the partial-connectivity condition.

## Scope Confirmation

- Production code was not modified.
- Architecture documents were not modified.
- Specs/plans were not modified.
- Tests were not modified.
- A real project `DesignState` was not mutated.
- No production `ChangeSet` was created.
- No fixes were implemented.
- No commit was created.
- No push, stash, reset, or clean operation was performed.
- This result document is the only file created by the audit.

MECHCAD_IMPLEMENTATION_INTEGRATION_AUDIT_COMPLETE
