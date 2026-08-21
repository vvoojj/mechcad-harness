# MechCAD Subsystem Contracts

**Maturity:** `FOUNDATION` and `REQUIRED_CURRENT` contracts are mandatory baseline audit scope; `TARGET_NEXT` is connected-readiness scope when selected; `FUTURE` is documentary only. A contract row is not an implementation verdict.

| Subsystem | Responsibility | Inputs | Outputs | Authority | May mutate state? | Caller / consumer | Verification / failure |
|---|---|---|---|---|---|---|---|
| StateManager | Persist, hash, load, verify revisions | DesignState | immutable snapshot/current pointer | canonical | Yes, only through revision API | ChangeEngine / all readers | hash/tamper checks; exclusive-write failure |
| DesignState | Hold canonical typed engineering state | accepted requirements/changes | revisioned state | canonical | No direct external mutation | all services | Pydantic validation; reject empty/invalid values |
| ChangeProposal | Describe requested canonical changes | state binding, operations | proposal | non-authoritative | No | agents/services -> ChangeEngine | stale/ownership validation |
| ChangeSet | Accepted operation package | proposal | ordered operations | transition record | No | ChangeEngine | immutable identity and binding |
| ChangeEngine | Enforce mutation boundary | proposal, owner policy, StateManager | new revision/receipt | trusted authority boundary | Yes | RunController | atomic apply; fail closed |
| Ownership enforcement | Restrict paths to owners | path, identity, policy | allow/reject | policy | No | ChangeEngine | unowned/unrelated paths reject |
| DependencyEngine | Compute impact/invalidation | changed paths, graph | nodes/records | derived control | No | ChangeEngine/EvidenceStore | cycle and deterministic matching errors |
| RunController | Bind tasks and convergence | project/state/plan | run/task/result transitions | orchestration | No direct state mutation | scheduler/executors | exact bindings; blocked on stale/unknown |
| Manifest | Freeze run source and inputs | project/revision/hash | immutable run manifest | provenance | No | RunController/auditor | exclusive write and replay |
| AgentGateway | Build context and validate agent output | task, state, evidence IDs | AgentResult | reasoning boundary | No | RunController | schema, hash, stale checks |
| OpenCodeAgentAdapter | Transport to OpenCode/LLM | gateway invocation | structured response | untrusted transport | No | AgentGateway | URL, schema, timeout, binding failures |
| FakeAgentAdapter | Deterministic gateway test transport | gateway invocation | structured response | test transport | No | AgentGateway/tests | no external I/O or hidden state |
| AgentToolMediator | Map one semantic capability to an authorized exact tool | authored typed request, policy, task binding | mediation record/ToolResult | trusted mediation | No | transmission workflow/ToolBroker | semantic policy and exact permission checks |
| TransmissionToolRoundTripCoordinator | Bound torque request, result, Evidence, and second reasoning invocation | exact state-bound workflow records | immutable terminal workflow record | workflow coordination | No | transmission workflow | one-tool/two-invocation limit, freshness, recovery |
| ToolRegistry | Register exact tools | name/version/handler | deterministic lookup | policy | No | ToolBroker | duplicate/unknown identity fails |
| ToolBroker | Mediate deterministic computation | typed ToolCall/context | ToolResult | trusted computation boundary | No | agents/services | permission, binding, version, handler errors |
| Evidence | Record computation fact | result, source bindings | freshness-bound record | derived evidence | No | tools/analysis/auditor | stale/unknown if dependencies change |
| ConstraintRequest | Record missing authority | key/description/binding | request | non-authoritative | No | agent/requirements loop | explicit resolution required |
| ConstraintRequest materialization | Derive trusted request identity and persist lifecycle record | typed draft, state and invocation binding | ConstraintRequestRecord | trusted record materialization | No | gateway/constraint workflow | supported key, deterministic identity, idempotency |
| Constraint satisfaction | Suppress already-satisfied requests using exact anchors | supported key, canonical state | satisfaction decision/proof | deterministic authority check | No | discovery/resolution workflow | exact IDs only; no fuzzy or LLM matching |
| Constraint resolution | Validate trusted external answers and apply canonical values through change machinery | resolution command and request records | resolution records, proposal, revision, invalidation | trusted transition boundary | Only through ChangeEngine | external authority/ChangeEngine | binding, ownership, idempotency, replay |
| ArtifactStore | Store hashed derived files | bytes, identity, provenance | artifact reference | derived storage | No | CAD/analysis | no overwrite; hash/conflict failure |
| Transmission subsystem | Reason about speed/torque/packaging | requirements/evidence | findings, requests, proposals | bounded domain reasoning | No direct | gateway/tool broker | missing/conflicting inputs fail closed |
| py_gearworks adapter | Calculate narrow spur geometry | typed gear inputs | normalized gear result | derived provider | No | gear tools/services | optional dependency/version/provenance |
| build123d integration | Generate specialized parametric gear solids | accepted typed gear geometry input | solid/STEP/STL | derived provider | No | specialized gear CAD service/tool -> ArtifactStore and optional later assembly/import verification | geometry/export validation |
| bd_materials adapter | Provide candidate properties | material query | typed properties/provenance | derived provider | No | material evaluator | typical/missing status preserved |
| sectionproperties integration | Compute section geometry/warping | normalized section input | scalar section result | derived provider | No | section tools | convergence/unit checks |
| CAD compiler | Translate domain meaning to generic program | accepted DesignSpec | part/assembly program | derived compiler | No | CAD backend | deterministic program hash |
| FreeCAD backend | Realize and verify CAD | CAD program/assembly | FCStd/STEP/verification | derived backend | No | CAD service/artifact store | fresh reload, shape/solid checks |
| Assembly backend | Build rigid instances/manifests | parts, transforms | assembly artifact/result | derived backend | No | analysis/kinematics | ordering/identity integrity |
| Exact collision analysis | Measure common volume/distance | geometry pairs | interference/clearance result | derived analysis | No | CAD service/kinematics | exact measurement; no manufacturing approval |
| Transient analysis | Measure temporary transformed geometry | source assembly, transform | transient result | derived analysis | No | kinematic service | no public artifact/state side effect |
| Generic kinematic sweep | Aggregate ordered discrete samples | axis, groups, angles, provider | sweep result | derived analysis | No | domains/verification | normalized axis; continuous proof false |
| Domain extension layer | Add domain authority and services | domain requirements/state paths | proposals/specs/adapters | domain bounded | Only via ChangeEngine | core contracts | ownership and generic-boundary checks |

No subsystem may silently bypass the proposal boundary, state binding, ownership, or provenance requirements.
