# MechCAD Integration Audit Procedure

This is a clean-session independent audit procedure, not an audit result or readiness declaration.

## Allowed Verdicts

`IMPLEMENTED_AND_CONNECTED`, `IMPLEMENTED_BUT_UNUSED`, `TEST_ONLY`, `STUB_OR_PLACEHOLDER`, `MISSING`, `BOUNDARY_VIOLATION`.

## Audit Layers

### A. Baseline Conformance Audit

Audit every `FOUNDATION` and `REQUIRED_CURRENT` capability in `MECHCAD_CAPABILITY_MATRIX.md`. A foundation is accepted current architecture and must be verified; it is not optional merely because broader wiring remains incomplete.

### B. Connected-Readiness Audit

Audit selected `TARGET_NEXT` capabilities needed for the staged motor-driven rotary-bracket workflow. This layer asks whether accepted foundations are connected through real production callers and consumers.

### C. Future

Document `FUTURE` capabilities only. Their absence does not fail baseline conformance or connected readiness.

## Evidence Standard

For each audited row prove: normative contract; production implementation; public typed API; production caller; downstream consumer; actual library/tool invocation; authority/ownership boundary; canonical mutation boundary; unit test; integration test where appropriate; runtime proof where required; provenance/hash binding; and absence of hidden manual mutation or workaround.

File existence is not integration evidence. An import, adapter, isolated unit test, manually modified test request, or passing fixture is not end-to-end proof. Follow concrete runtime calls and persisted records.

## Required Call-Path Questions

### Agents and Constraints

- Who constructs `AgentTask`, dispatches the agent, selects context, and consumes `AgentResult`?
- Which exact adapter and response mode run, and which schema/hash validates output?
- Does OpenCode/Luna supply only semantic content while the harness supplies trusted identity and binding?
- Does `AgentToolMediator` enforce semantic policy and exact tool permission?
- Does the torque flow persist ToolCall, ToolResult, current Evidence, and a second invocation without a second tool call?
- Are ConstraintRequest drafts, observations, records, identities, and lifecycle states distinct?
- Are satisfied keys suppressed only by exact authoritative anchors?
- Does trusted resolution use ChangeProposal, ChangeSet, ChangeEngine, revision, and invalidation without direct mutation?

### Engineering Providers

- What production caller reaches each adapter and real package function?
- Which normalized input and output models cross the boundary?
- Are expected package and adapter versions verified at runtime?
- Does provenance include backend identity, adapter version, library version/source/revision as applicable?
- Does the normalized result reach a real downstream evaluator, proposal, artifact, or assembly path?
- For build123d, what exact runtime version executed, where is that version represented in result/artifact provenance, is indirect py-gearworks adapter provenance sufficient for deterministic replay, and is a separate provider identity required?

### CAD and Kinematics

- What accepted DesignSpec creates each `CadPartProgram` or `CadAssemblyProgram`?
- Which service executes FreeCAD, and are FCStd/STEP files freshly reloaded and verified?
- Is the specialized py_gearworks/build123d gear path kept distinct from generic project CAD?
- What source assembly hash enters transient analysis and kinematic sweep?
- Are transforms, partitions, pair order, transformed hash, and exact measurements validated without state mutation?

## Fillable Acceptance Matrix

All observed columns intentionally remain `TO_BE_AUDITED`.

| Capability | Contract Requirement | Implementation | Caller | Downstream Consumer | Library/Tool | Unit Test | Integration Test | Runtime Proof | Provenance/Hash Proof | Boundary Check | Verdict | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DesignState | typed canonical engineering authority | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | Pydantic | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| StateManager | exclusive revision persistence and verified loading | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | filesystem/SHA-256 | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| immutable revision/hash | deterministic snapshot identity and no overwrite | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | SHA-256 | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ChangeProposal | bound non-authoritative proposed operations | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | none | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ChangeSet | accepted immutable operation package | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ChangeEngine | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ChangeEngine | sole validated proposal-to-revision boundary | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | StateManager | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ownership enforcement | owner may affect only governed paths | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ownership policy | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| DependencyEngine | deterministic direct/transitive impact | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | dependency graph | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| invalidation/freshness | changed inputs make dependent Evidence stale/unknown | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | EvidenceStore | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| RunController | exact state-bound orchestration and convergence | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | RunStore | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| manifest/replay | immutable source manifest and recoverable transitions | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | filesystem | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| AgentGateway | bound context, invocation, schema and stale checking | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | adapter/schema | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| OpenCodeAgentAdapter | strict OpenCode/Luna execution transport | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | OpenCode HTTP | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| FakeAgentAdapter | deterministic testing-only adapter | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | none | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| mechcad-transmission contract | bounded authoritative-context reasoning | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | OpenCode adapter | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| AgentToolMediator | semantic capability to exact authorized tool | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ToolBroker | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| TransmissionToolRoundTripCoordinator | one tool, Evidence, second invocation, recovery | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | torque tool/Evidence | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| structured response validation | exactly one schema-valid payload; no repair/fallback | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | Pydantic JSON Schema | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ConstraintRequest discovery | typed supported missing-input drafts/observations | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | agent schema | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ConstraintRequest materialization | deterministic trusted request records and lifecycle | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | request store | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| constraint satisfaction/resolution | exact satisfaction; trusted answer through change machinery | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ChangeEngine/EvidenceStore | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ToolRegistry | deterministic exact registration and lookup | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | handlers | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ToolBroker | typed, bound and permitted deterministic execution | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | registered tool | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| tool permission/version enforcement | exact permitted identity fails closed | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ToolRegistry | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ToolCall | immutable pre-execution input/provenance record | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ToolStore | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ToolResult | immutable normalized output/failure record | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ToolStore | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| Evidence | trusted derived computation fact, not decision authority | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | EvidenceStore | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| Evidence freshness | exact state/dependency history determines usability | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | DependencyEngine | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| PyGearworksAdapter | normalized pinned spur gear provider | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | py_gearworks | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| real py_gearworks invocation | adapter reaches actual pinned package functions | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | py_gearworks 0.0.18 | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| build123d integration | specialized gear solid/export path only | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | build123d 0.11.1 | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| BdMaterialsAdapter | normalized typical properties and mass | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | bd-materials 0.2.4 | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| sectionproperties integration | normalized geometry/warping with convergence | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | sectionproperties 3.10.2 | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| numerical/oracle paths | independent formulas and versioned numerical support | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | NumPy/SciPy/native arithmetic | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| CAD compiler | accepted Domain DesignSpec to generic program | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | generic operations | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| CadPartProgram | deterministic backend-independent part instructions | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCADBackend | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| CadAssemblyProgram | deterministic rigid assembly/transform instructions | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | assembly backend | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| FreeCAD part generation | program to verified persisted part | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| FreeCAD assembly generation | assembly program to verified placements/solids | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| fresh reload verification | persisted FCStd/STEP reopens and matches source manifest | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| ArtifactStore | immutable hashed derived artifact storage | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | filesystem | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| durable FCStd | verified project-CAD artifact and bindings | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| durable STEP | verified portable artifact and bindings | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD/build123d by path | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| specialized gear artifact path | typed gear input -> build123d STEP/STL artifact | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | py_gearworks/build123d | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| exact collision/interference | exact common-volume classification | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD shape common | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| clearance measurement | exact shape distance and touching/clearance semantics | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD distToShape | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| TransientAssemblyAnalysisService | temporary transformed analysis without artifacts/state changes | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | measurement provider | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| FreeCADTransientAssemblyMeasurementProvider | exact measurements in temporary FreeCAD workspace | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | FreeCAD | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| CadKinematicSweepService | ordered discrete single-axis transform/measurement/aggregate | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | transient service | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| domain authority/state ownership | domain paths and owners cannot bypass core | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | ChangeEngine | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| generic/domain separation | generic CAD/kinematics contain no Yagi assumptions | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | architecture boundary | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |
| reference domain adapter proof | one domain reaches generic capability without manual request mutation | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | Yagi adapter/reference only | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED | TO_BE_AUDITED |

## Universal Staged Acceptance

**Stage A - current baseline:** complete every `FOUNDATION` and `REQUIRED_CURRENT` row, allowing `IMPLEMENTED_BUT_UNUSED` where an accepted provider foundation lacks broader production wiring but still satisfies its own foundation contract.

**Stage B - connected readiness:** use a generic motor-driven rotary bracket to prove requirements -> DesignState -> agent -> deterministic tool/provider -> Evidence -> proposal -> ChangeSet/revision -> part CAD -> assembly -> discrete kinematic verification. Select and audit the relevant `TARGET_NEXT` rows.

**Stage C - future:** structural approval, FEA, continuous-motion proof, dynamics, and manufacturing. Do not use these as current acceptance gates.
