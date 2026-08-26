# MechCAD System Contract

**Status:** normative. This document is the authoritative source for maturity semantics.

## Maturity Semantics

| Maturity | Normative meaning | Audit treatment |
|---|---|---|
| `FOUNDATION` | A reusable accepted subsystem or capability foundation exists and is part of the baseline, but it may not yet be wired into every intended production workflow. | Mandatory baseline conformance audit. Foundation never means optional or exempt from audit. |
| `REQUIRED_CURRENT` | The current baseline requires the capability to operate according to its accepted contract. | Mandatory baseline conformance audit, including connected behavior required by that contract. |
| `TARGET_NEXT` | Intended next integration or capability work; it is not required for current baseline conformance. | Audit only when selected for connected-readiness or the universal staged fixture. |
| `FUTURE` | Longer-term architecture, not a present acceptance gate. | Document only; do not fail current conformance for absence. |

`CURRENT` is descriptive prose only and means the union of `FOUNDATION` and `REQUIRED_CURRENT`. Capability tables must use the four authoritative values above.

## System Definition

MechCAD is a deterministic, provenance-aware, multi-agent mechanical-engineering harness that converts authoritative engineering requirements into verified engineering state, derived CAD and analysis while preserving ownership, reproducibility, traceability, and fail-closed validation.

## Layered Contract

1. **Requirements / Authority:** external facts, requirements, interfaces, constraints, and loads enter through typed records.
2. **Canonical Engineering State:** `DesignState` is the only canonical design authority.
3. **Engineering Memory / Revisions:** deterministic serialization, hashes, immutable snapshots, replay, and recovery.
4. **Agent Orchestration:** tasks and bounded agents receive state-bound context and return typed records.
5. **Deterministic Engineering Computation:** ToolBroker and adapters invoke declared tools and libraries.
6. **Proposal / Change Control:** proposed canonical changes are checked, assembled, and applied centrally.
7. **Dependency / Invalidation:** changed authority invalidates dependent derived nodes and evidence.
8. **CAD / Geometry:** typed design specs compile to generic CAD programs and derived artifacts.
9. **Engineering Analysis:** deterministic geometry, kinematic, material, section, structural, or solver analyses produce bound results.
10. **Validation:** results are checked for schema, source identity, freshness, geometry, and domain acceptance criteria.
11. **Artifact / Evidence Management:** facts and files are hashed, bound, immutable, and refreshable.
12. **Domain Extensions:** domain-specific meaning stays above generic state machinery and backend contracts.
13. **Production Orchestration (M8B):** `ProductionApplication.create(...)` is the trusted composition root that owns the production service graph (`StateManager`, `EvidenceStore`, `OwnershipPolicy`, `ChangeEngine`, `RunController`, `ToolRegistry` → `ToolBroker`, `AgentRegistry` → injected adapter, `ContextBuilder` → `AgentGateway` → `AgentToolMediator` → `ToolBroker`). It owns trusted identities/permissions and the composition of analysis providers; it does not add a second canonical-mutation API.
14. **Production CAD / Assembly / Kinematics (M8C → M9):** M8 connected source-bound `DesignSpec` → `CadPartProgram` compilation, trusted `ImportedCadComponent` resolution through `ArtifactStore`, generic mixed `CadAssemblyProgram`, and the `ProductionApplication.analyze_assembly_kinematics` entrypoint. M9 live-verified the runtime edges on real FreeCAD: `CadPartProgram` realization, real trusted imported STEP, live mixed assembly, fresh reload, exact `common().Volume` / `distToShape()`, real discrete kinematic sweep, and durable trusted analysis-execution provenance (`M9_FULLY_CLOSED_LIVE_VERIFIED`).
15. **Durable Structural Evidence (M11-5):** the bounded source-bound single-solid linear-static structural path can publish immutable structural Evidence through the existing `EvidenceStore`, independently reload it, and preserve trusted PASS, FAIL, and NOT_EVALUABLE engineering outcomes. Exact source, artifact, result, criterion, material, analytical, and provider/parser bindings are required; bounded repeatability and explicitly declared displacement-metric mesh-convergence studies are supported.

## Authority Rules

`DesignState` is canonical. Agents do not mutate it directly. The trusted path is `AgentResult -> ChangeProposal -> ChangeSet -> ChangeEngine -> immutable DesignState revision`. Libraries and backends are not authority: `py_gearworks`, `build123d`, `bd_materials`, FreeCAD, MuJoCo, FEA solvers, and numerical libraries cannot approve requirements or silently write state. Agent prose, CAD files, temporary solver state, evidence, and passing tests are not design decisions.

## Authority Taxonomy

| Term | Contract meaning |
|---|---|
| Physical fact | Externally fixed real-world property. |
| User requirement | Behavior or performance required by external authority. |
| Interface requirement | Mating or integration condition imposed by another system. |
| Engineering constraint | Condition the design must satisfy. |
| Design variable | Parameter MechCAD may synthesize or select. |
| Derived value | Deterministic value calculated from accepted inputs. |
| Placeholder | Temporary non-authoritative approximation. |
| Preferred / recommended | Optimization guidance, not a hard requirement. |
| Parametric | Intentionally unresolved variable. |
| Unresolved | Required information or decision is missing. |
| Verified | Supported by accepted deterministic evidence. |
| Not verified | No valid engineering proof currently exists. |

## Canonical State and Memory

Project identity, revision identity, state hash, source binding, and canonical serialization are mandatory for reproducibility. Evidence and artifacts bind to source state and become stale when dependency inputs change. Replay uses immutable records and exact identities; recovery must not guess or overwrite. A CAD artifact, analysis result, temporary solver state, or evidence record becomes canonical only if a trusted, accepted proposal explicitly promotes an authoritative value through change machinery.

## Ownership

Ownership is enforced by state path and owner identity. A transmission owner may propose only transmission paths; a material owner only material-design paths; a structural owner only structural paths; and a domain-layout owner only domain paths. Scope, owner identity, base revision/hash, resulting validation, and rejection reasons are explicit. Unowned or unrelated paths fail closed.

## Dependency and Invalidation

Dependencies form a directed graph. For example, payload mass can affect required torque, transmission sizing, shaft/bearing requirements, CAD geometry, and structural verification. An upstream revision invalidates dependent nodes transitively. Evidence remains stored but is `STALE` or `UNKNOWN` until rebuilt against a valid source revision and complete invalidation history.

Evidence freshness must fail closed over the complete accepted revision/invalidation history defined by the current M3 contract.

## Run and Manifest

`RunController` records run identity, project, source revision/hash, immutable manifest, invocation and tool calls, results, evidence, artifact references, state transitions, convergence, and resume/replay state. A reviewer must be able to identify exactly which state and inputs produced each result.

RunController must preserve the accepted revision, failure, convergence, recovery, and no-rollback invariants defined by the current M4 contract.

## Agent Contract

An engineering agent has bounded responsibility, typed inputs, declared outputs, owned paths, allowed tools, forbidden actions, and an expected caller. An execution adapter transports requests to an LLM/runtime. An orchestrator selects tasks. A domain owner is an ownership identity, not necessarily an executable agent. A test agent is testing-only.

`AgentGateway` builds canonical context, binds project/revision/hash, advertises and hashes schemas, creates invocation identity, validates responses, rejects stale returns, and records provenance. `OpenCodeAgentAdapter` is transport. OpenCode/Luna cannot choose trusted revision IDs, state hashes, Evidence IDs, ChangeSet IDs, or canonical artifact IDs. Invalid structured output fails closed; regex extraction, prose repair, and hidden fallback interpretation are forbidden.

### Actual Agent and Adapter Inventory

| Canonical name | Classification | Responsibility | Inputs / outputs | Owned paths | Expected tools | Forbidden actions | Expected caller | Maturity |
|---|---|---|---|---|---|---|---|---|
| `mechcad-test-agent@1.0` | Test agent identity | deterministic gateway fixture | bound context -> findings/proposal/request | none | none | tools, shell, filesystem, network, direct state mutation | unit/integration tests | FOUNDATION |
| `FakeAgentAdapter` | Execution adapter | deterministic adapter boundary | invocation -> structured response | none | none | external I/O and state mutation | AgentGateway | FOUNDATION |
| `mechcad-transmission@1.0` | Engineering agent identity | bounded transmission reasoning | requirements/evidence -> findings, `Issue`, `ConstraintRequest`, proposal | transmission paths only when explicitly governed | exact mediated capability only | direct state mutation, arbitrary tools, shell, filesystem, network | AgentGateway / transmission workflow | REQUIRED_CURRENT |
| `OpenCodeAgentAdapter` (`opencode-http@0.1.0`) | Execution adapter | OpenCode/Luna transport and strict response validation | bound invocation -> validated response | none | only gateway-authorized mediation | trusted identity selection, direct state mutation, arbitrary repository actions | AgentGateway | REQUIRED_CURRENT |
| `AgentToolMediator` | Trusted mediation service | authorize declared agent tool requests | typed request -> mediated ToolResult/observation | none | exact registered capability | arbitrary imports, unapproved tools, state mutation | gateway/round-trip coordinator | REQUIRED_CURRENT |
| `TransmissionToolRoundTripCoordinator` | Bounded workflow coordinator | execute the accepted one-tool/two-invocation torque/Evidence flow | bound workflow records -> terminal workflow record | no direct canonical paths | exact `transmission.torque` mapping | direct state mutation, hidden fallback, unbound evidence | transmission workflow | FOUNDATION; runtime connection audit required |
| `mechcad-yagi-carrier` | Domain owner label (Yagi reference domain) | ownership of Yagi carrier paths | domain proposals -> owned-path proposal | `/yagi_carriers/*` and configured related paths | domain services as authorized | generic-layer mutation, direct state mutation | ChangeEngine ownership checks | FOUNDATION |

An owner label such as `mechcad-yagi-carrier` is not described as a production engineering agent unless a separate executable agent contract exists.

## Tool Contract

```text
Agent -> semantic typed request -> ToolBroker -> registered tool -> ToolResult
      -> optional trusted Evidence / Agent context
```

The broker checks typed input/output, resolves a concrete exact tool name/version, applies task and state binding, records backend/tool provenance and deterministic hashes, and fails closed on errors. The general M5 permission wording permits a compatibility form that may be broader than a concrete `name@version` entry; individual workflows may impose a stricter exact `name@version` permission policy, as M6B-2A/B does. Agents must not silently import arbitrary engineering libraries in place of brokered execution.

## Engineering Provider Identity

All accepted providers use normalized MechCAD models. `BackendProvenance` always carries backend identity through the required fields `backend_name` and `backend_adapter_version`. Library/provider fields, where applicable to the provider contract, are `library_name`, `library_version`, `library_source`, and `library_revision`; unavailable or non-applicable fields are not mandatory.

| Capability | Adapter/module | Package contract | Backend identity | Normalized input -> output | Runtime verification | Expected consumer |
|---|---|---|---|---|---|---|
| Spur gear and gear-pair calculation | `PyGearworksAdapter`, `backends/adapters/py_gearworks.py` | `py_gearworks==0.0.18`, Git revision `2fc2a13d82a9997a65f30c870498f0bb3be62318`; profile includes `build123d==0.11.1`, NumPy `>=2,<2.4`, SciPy `>=1.10.1` | `py-gearworks@0.1.0` adapter | `SpurGearGeometryInput -> SpurGearGeometryResult`; `SpurGearPairInput -> SpurGearPairResult` | metadata health check before calculation; missing is unavailable, mismatch incompatible | gear tools, engineering evaluation, narrow gear CAD |
| Specialized gear solid generation | `backends/gearworks_cad.py`; no standalone Build123dAdapter | `build123d==0.11.1` | no independent backend identity; artifact currently carries py-gearworks adapter provenance | `SpurGearCadInput -> SpurGearCadResult`; pair equivalents | verified indirectly by py-gearworks profile; lazy import; shape validity, volume, bounds, thickness, and export checks | ArtifactStore, optional later assembly/import verification |
| Typical material properties and mass estimate | `BdMaterialsAdapter`, `backends/bd_materials.py` | `bd-materials==0.2.4` | `bd-materials@0.1.0` adapter | `TypicalMaterialPropertiesInput -> TypicalMaterialPropertiesResult`; `MaterialMassInput -> MaterialMassResult` | exact distribution version and required dependency metadata | material tools and preliminary section integration |
| Section geometry and warping | `SectionPropertiesAdapter`, `backends/section_properties.py` | `sectionproperties==3.10.2`; NumPy `>=2,<2.4`; structural profile pins SciPy `1.18.0` and supporting packages | `section-properties@0.2.0` adapter | rectangle/circle/hollow inputs -> `SectionGeometryResult` or `SectionWarpingResult` | package/profile health; direct solver; coarse/fine convergence; analytic oracles where normative | section tools and preliminary section engineering |
| General persisted project CAD | `FreeCADBackend`, `FreeCADAssemblyBackend`, transient measurement provider | FreeCAD `UNPINNED_BY_CONTRACT` | `freecad` / `mechcad-freecad@2.1`; assembly producer `mechcad-freecad-assembly@1.0` | `CadPartProgram -> FreeCADGenerationResult`; `CadAssemblyProgram -> FreeCADAssemblyGenerationResult`; transient request -> exact measurements | executable/import discovery; runtime `FreeCAD.Version()` capture; FCStd/STEP existence, reload, manifest, shape, solid, placement, and measurement checks | CAD/assembly services, analysis, ArtifactStore, kinematics |

NumPy and SciPy are numerical infrastructure with versions governed by the provider profiles above. They are not independent design authorities.

Actual adapter existence or optional dependency installation does not prove that a production caller reaches the library. That question belongs to the independent audit.

The build123d path has no standalone backend identity. The independent audit must verify its exact runtime version, whether artifact/result provenance represents that version sufficiently for deterministic replay, whether indirect py-gearworks adapter provenance is sufficient, and whether a separate provider identity is required. This contract does not decide those questions.

## Evidence Contract

Evidence binds where relevant to project, revision, state hash, run, tool call/result, backend/library version, inputs, and artifact/geometry identity. It is computation evidence, not automatic approval. Input invalidation makes it stale. A result may be successful but still ineligible for Evidence if required values or freshness criteria are missing.

## CAD and Analysis Contract

### Generic Project CAD Path

```text
accepted DesignState -> typed Domain DesignSpec -> deterministic compiler
-> CadPartProgram/CadAssemblyProgram -> FreeCAD part/assembly backend
-> FCStd/STEP -> fresh reload and geometry verification -> ArtifactStore/Evidence
```

### Specialized Parametric Geometry Path

```text
accepted specialized geometry input -> specialized engineering provider
-> py_gearworks where applicable -> build123d solid generation
-> STEP/STL artifact -> optional later assembly/import/verification
```

Generic operations include plates, holes, pockets, and slots. `CadRigidTransform` and assembly manifests are generic. FreeCAD is the general persisted realization and verification backend. build123d is a specialized parametric geometry generator in a narrow gear path; it is not interchangeable with FreeCAD and does not replace the project-CAD pipeline. Project CAD may become a durable artifact; transient analysis CAD remains temporary.

A generated specialized gear-pair CAD result consists of two generated gear artifacts plus nominal relative transform/placement information. It is not automatically a `CadAssemblyProgram` and is not proof of a general assembly model.

## Kinematics Contract

M7C provides `RevoluteAxis`, `CadRigidTransform`, `CadKinematicSweepRequest`, ordered samples, exact pair results, and aggregate classification. The axis must be normalized and non-zero; frame identity, moving/stationary partition, source assembly hash, transformed assembly hash, quaternion composition, and pair ordering are deterministic. Current discrete sampling has `continuous_sweep_verified = False`. Samples do not create revisions or durable public CAD artifacts.

M10-2 additionally provides `KinematicModel`, `JointConfiguration`, and
`KinematicForwardKinematicsResult` for deterministic forward kinematics over a
rooted acyclic tree of revolute joints. Axis frames are parent-instance local;
home parent-to-child transforms come from source assembly placements. The
result contains instance world transforms and a transformed
`CadAssemblyProgram`, with separate model, configuration, transformed-assembly,
and result identities. Core FK is FreeCAD-independent and makes no collision,
clearance, or continuous-verification claim.

M10-3 provides `MultiJointCollisionSweepRequest` and
`MultiJointCollisionSweepResult` for exact discrete collision evaluation over
ordered multi-joint configurations. Each configuration is evaluated from the
unchanged source assembly through the M10-2 transformed assembly path, then
measured by the composed FreeCAD provider using `common().Volume` and
`distToShape()`. Pair order, configuration/model/transformed-assembly/request/
result identities, exact classifications, and trusted provider/backend/runtime
provenance are deterministic and persisted atomically with one Evidence record.
The result is discrete-only and does not establish interpolated or continuous
multi-axis clearance.

M10-4 provides `MultiJointPath` and
`MultiJointContinuousClearanceProofResult` for conservative continuous clearance
proof along one explicitly requested ordered piecewise-linear raw joint-space
path. Trusted local geometry extents and pure topology-derived reach bounds feed
hierarchical telescoping pair bounds around exact FreeCAD waypoint and midpoint
measurements. Only complete leaf coverage produces `VERIFIED_CLEAR`; exact
interference/touching/requested-clearance violations produce `COLLISION_WITNESS`,
and unresolved budgets produce `NOT_PROVEN`. M10-4 does not certify a
configuration-space region.

## Structural Evidence Contract

M11-5 adds a frozen `StructuralEvidencePayload` to the generic `Evidence`
model. Ordinary structural Evidence is `analysis.structural`; convergence-study
Evidence is `analysis.structural.convergence` and binds complete ordered level
Evidence rather than representing a physical analysis result. Existing legacy
Evidence remains valid without the optional payload.

`ProductionApplication.publish_structural_evidence()` is the trusted
publication boundary. It reconstructs the accepted M11-4 result and criterion
verification from the immutable source definition, durable execution manifest,
and byte-verified ArtifactStore records before writing one immutable Evidence
record. `StructuralEvidenceVerifier` reloads and rechecks those bindings
without runtime discovery or solver/CAD subprocesses. Integrity failure is not
converted to an engineering `NOT_EVALUABLE` outcome.

Structural Evidence currentness is separate from internal validity and is
`CURRENT`, `STALE_RELATIVE_TO_CURRENT_STATE`, or
`CURRENTNESS_UNAVAILABLE`. State advancement leaves historical Evidence
verifiable against its bound revision.

`StructuralRepeatabilityPolicy` compares declared semantic summaries and does
not require raw bytes or mesh node/element correspondence. A
`StructuralMeshConvergenceStudy` requires an ordered bounded sequence of at
least three mesh levels for the supported free-end displacement-magnitude
metric. This is not adaptive refinement, generic mesh correspondence, stress
convergence, or a global convergence claim.

## Maturity

**FOUNDATION / REQUIRED_CURRENT:** state/revision/change/ownership/dependency/run/tool/Evidence foundations; AgentGateway, fake and OpenCode adapters, bounded transmission reasoning, strict structured response, tool mediation, torque/Evidence round-trip foundation, constraint discovery/materialization/satisfaction/resolution; narrow engineering providers; generic CAD programs and rigid assemblies; exact collision, transient measurement, discrete single-axis kinematics, single-axis continuous proof, generic multi-joint discrete forward kinematics, exact discrete multi-joint collision evaluation, explicit-path continuous multi-joint clearance proof, and durable bounded structural Evidence/repeatability/convergence.

The accepted M11 bounded structural path is also current: M11-2 provides the
typed source-bound single-body linear-static authority model; M11-3 provides
trusted FreeCAD geometry, Gmsh C3D10 meshing, deterministic CalculiX deck
lowering, per-case execution, and raw artifact provenance; and M11-4 provides
trusted FRD/DAT/LOG interpretation, typed criterion outcomes, and separate
predeclared fixed-cantilever analytical validation. These milestones do not
constitute general structural approval or unrestricted FEA.

**TARGET_NEXT:** one connected universal mechanical workflow across the current foundations, broader domain services, canonical transmission/material selection, controlled load cases, and stronger provider wiring proof.

**FUTURE:** whole configuration-space certification, broad structural approval
and unrestricted FEA beyond the bounded M11 path, global or automatic mesh convergence, dynamics,
manufacturing, optimization, and broad multi-agent convergence.

## Generic Acceptance Scenario

A motor-driven rotary bracket is the universal target fixture. **Stage A - baseline conformance** audits every `FOUNDATION` and `REQUIRED_CURRENT` capability independently. **Stage B - connected readiness** selects `TARGET_NEXT` wiring to prove requirements -> agent -> tool/provider -> Evidence -> proposal -> revision -> part CAD -> assembly -> discrete kinematic verification. **Stage C - future** adds whole configuration-space certification, broad structural approval and FEA beyond the bounded M11 path, dynamics, and manufacturing; the accepted M10 explicit-path proof and bounded M11 structural path are current but these broader claims are not current gates.
