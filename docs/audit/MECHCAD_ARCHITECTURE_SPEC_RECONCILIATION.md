# MechCAD Architecture ↔ Superpowers Specs Reconciliation

## 1. Scope

This is a read-only documentation audit comparing the universal/current contracts in `docs/architecture/` with milestone-specific accepted contracts in `docs/superpowers/specs/`. It is not an architecture-versus-implementation comparison and does not establish production implementation or runtime integration.

The audit is bidirectional:

- Architecture -> specs: identify the accepted specification support for each important architecture claim.
- Specs -> architecture: determine whether each accepted specification's important contract is represented accurately in the universal architecture.

The audit procedure in `docs/audit/MECHCAD_INTEGRATION_AUDIT.md` was context only. No production audit verdict was assigned. Plans, completion reports, task reports, and project-status records were inspected only as acceptance/traceability evidence; they are not treated as equivalent to a dedicated specification.

### Evidence Model

Each finding distinguishes four questions:

- **Spec support:** does a dedicated accepted milestone specification define the capability?
- **Acceptance/completion evidence:** does another authoritative project record explicitly accept or close it?
- **Architecture authority:** does the current universal architecture intentionally include it and assign maturity?
- **Implementation evidence:** is production behavior actually wired and running? This fourth question was not evaluated here and belongs to the later implementation/integration audit.

## 2. Spec Inventory

Sixteen specification files exist. There are no specification files for M1, M7A, M7B, or M7C. There are no dedicated M6B-3 or M6B-4 specifications.

| Spec | Milestone / sub-milestone | Subsystem | Generic / Domain | Document status | Acceptance evidence | Primary contract | Relationship |
|---|---|---|---|---|---|---|---|
| `2026-08-18-mechcad-m0-bootstrap-design.md` | M0 | typed models and authority | Generic | Design specification; no explicit acceptance marker | No separate acceptance record identified | Minimal Pydantic foundation; `DesignState` canonical; external records separate; no persistence/execution | Foundation for later milestones |
| `2026-08-18-mechcad-m2-changeset-design.md` | M2 | change control and ownership | Generic | Design specification; no explicit acceptance marker | No separate acceptance record identified | Proposal -> stale/operation/ownership checks -> in-memory ChangeSet -> validated StateManager revision | Depends on an undocumented M1 state foundation |
| `2026-08-18-mechcad-m3-dependency-invalidation-design.md` | M3 | dependency and Evidence freshness | Generic | Design specification; no explicit acceptance marker | No separate acceptance record identified | Direct/transitive invalidation, immutable records, exact provenance, `CURRENT`/`STALE`/`UNKNOWN` | Extends M2 result boundary |
| `2026-08-18-mechcad-m4-run-control-design.md` | M4 | runs, task DAG, manifests, convergence | Generic | Design specification describing accepted M0-M3 boundaries | No separate completion record identified | State-bound runs, immutable history, mutable control state, resume, fail-closed completion | Extends M0-M3; composes rather than replaces them |
| `2026-08-18-mechcad-m5-tool-broker-design.md` | M5 | ToolRegistry and ToolBroker | Generic | Design specification; no explicit acceptance marker | No separate acceptance record identified | Exact registry dispatch, task permissions, immutable ToolCall/ToolResult, optional Evidence | Extends M4; preserves M4 authority |
| `2026-08-18-mechcad-m5-5a-backend-foundation-design.md` | M5.5A | backend identity/provenance/health | Generic | Foundation design; no explicit completion marker | No separate acceptance record identified | Identity, optional provenance, registry, safe metadata inspection; no external calculation | Extends M5 persistence models |
| `2026-08-18-mechcad-m5-5b2-gear-cad-artifacts-design.md` | M5.5B-2 | specialized gear CAD artifacts | Generic provider capability | Design specification; no explicit acceptance marker | No separate acceptance record identified | Narrow py_gearworks/build123d STEP/STL path behind ToolBroker; no general CAD/assembly | Extends M5/M5.5A independently of generic project CAD |
| `2026-08-18-mechcad-m5-5c3a-preliminary-section-integration-design.md` | M5.5C-3A | preliminary section engineering | Generic provider integration | Design specification; calls source tools accepted | No separate completion record identified | Persisted result IDs -> normalized models -> native mass/stiffness envelopes; no provider calls or material selection | Depends on undocumented C-1/C-2A/C-2B provider specs |
| `2026-08-18-mechcad-m6a1-agent-gateway-foundation-design.md` | M6A-1 | AgentGateway and FakeAgentAdapter | Generic | Foundation design; no explicit completion marker | No separate acceptance record identified | Read-only bound context, exact identity, immutable invocation/result, stale protection; Fake only | Extends M4/M3; excludes OpenCode and tools |
| `2026-08-19-mechcad-m6b1-transmission-reasoning-agent-design.md` | M6B-1 | bounded transmission agent | Generic agent boundary with transmission specialization | Design specification; no explicit completion marker | Project-status record reports M6B complete as a foundation; no dedicated M6B-1 completion record identified | Real OpenCode reasoning, deny-all agent, authored/trusted authority split, immutable AgentResult | Extends M6A-1; no tools/Evidence/state mutation |
| `2026-08-19-m6b1-validated-json-text-design.md` | M6B-1 transport | OpenCode structured response | Generic transport | Design specification; no explicit completion marker | Task 1 report covers only mode/provenance subtask; full transport acceptance record not identified | Native schema default plus explicitly selected validated whole-JSON-text mode; no fallback/repair | Refines M6B-1 transport without changing Gateway authority |
| `2026-08-19-mechcad-m6b2a-tool-mediation-design.md` | M6B-2A | semantic tool mediation | Generic mediation with torque fixture | Design specification with acceptance criteria | Later M6B-2B explicitly identifies M6B-2A as the accepted implementation baseline | Semantic `transmission.torque` -> exact trusted tool -> one ToolCall/ToolResult; no Evidence or Invocation B | Extends M6B-1 and M5 |
| `2026-08-19-mechcad-m6b2b-first-tool-roundtrip-design.md` | M6B-2B | bounded torque/Evidence round trip | Generic bounded workflow with transmission fixture | **Design-only**; design closed; explicitly says M6B-2A accepted baseline | Project-status record says M6B is complete as a foundation; no separate M6B-2B completion report, plan, or closure record found | One tool, two invocations, post-result Evidence, freshness, immutable transitions, recovery | Extends M6B-2A design; does not authorize implementation |
| `2026-08-21-m7d1-el-kinematic-architecture-design.md` | M7D-1 | EL reference adapter | Domain: Yagi/rotator | Design specification; no explicit completion marker | Project-status record reports M7D complete as a reference foundation; no dedicated completion record identified | Parametric EL reference and helper over generic `RevoluteAxis`; no mechanism selection | DOMAIN_ADAPTER_OVER_GENERIC M7C |
| `2026-08-21-m7d2-el-kinematic-sweep-integration-design.md` | M7D-2 | EL sweep adapter | Domain: Yagi/rotator | Design specification; no explicit completion marker | Project-status record reports M7D complete as a reference foundation; no dedicated completion record identified | Thin domain adapter to generic sweep/transient FreeCAD; no state/artifacts/mechanism | Extends M7D-1; DOMAIN_ADAPTER_OVER_GENERIC M7C |
| `2026-08-21-m7e2-preliminary-az-el-rotator-concept.md` | M7E-2 | preliminary FreeCAD concept | Domain: antenna rotator | Design specification; metadata `PRELIMINARY_CONCEPT_ONLY`, `NOT_VERIFIED`, `NOT_READY` | No acceptance record; explicit non-readiness statuses remain the applicable evidence | Preliminary packaging and discrete concept placements; no structural/manufacturing/final mechanism claim | Independent domain concept; not generic M7 acceptance evidence |

### Milestone Count

| Milestone group | Spec count |
|---|---:|
| M0 | 1 |
| M1 | 0 |
| M2 | 1 |
| M3 | 1 |
| M4 | 1 |
| M5 | 1 |
| M5.5 | 3 |
| M6A | 1 |
| M6B | 4 |
| M7A | 0 |
| M7B | 0 |
| M7C | 0 |
| M7D | 2 |
| M7E | 1 |
| Other later milestones | 0 |

## 3. Architecture Coverage

| Architecture Document | Major Contracts | Supporting Specs | Coverage Status |
|---|---|---|---|
| `MECHCAD_PROJECT_OVERVIEW.md` | universal mission, authority, maturity, historical reconciliation | M0, M2-M6B, M7D/E | Partial: universalization is sound, but several current maturity claims lack dedicated specs |
| `MECHCAD_SYSTEM_CONTRACT.md` | authority taxonomy, state, ownership, runs, agents, providers, CAD, kinematics | M0, M2-M6B, M5.5A/B-2/C-3A, M7D | Partial: core boundaries match; M1, provider details, M6B-3/4, M7A/C traceability missing |
| `MECHCAD_ENGINEERING_WORKFLOW.md` | controlled agent/tool/provider/proposal lifecycle | M2, M5, M5.5A, M6A/B | Strong semantic coverage; connected universal workflow remains correctly target-next |
| `MECHCAD_RUNTIME_FLOW.md` | state mutation, invalidation, agent/tool, CAD/provider, torque/gear/material, kinematics | M2-M6B, M5.5B-2/C-3A, M7D plus M7C plan | Strong: current material foundation and `TARGET_NEXT` selection are separated |
| `MECHCAD_SUBSYSTEM_CONTRACTS.md` | responsibilities, inputs/outputs, authority and mutation permissions | M0, M2-M6B, M5.5, M7D | Strong: specialized build123d caller and derived-provider boundary are explicit; unspecced services remain traceability gaps |
| `MECHCAD_CAPABILITY_MATRIX.md` | maturity and milestone traceability | all available specs | Explicitly exposes many gaps, but assigns mandatory current maturity to some unspecced/design-only capabilities |
| `MECHCAD_DOMAIN_EXTENSION_GUIDE.md` | generic extension/non-bypass rules and reference domains | M0/M2/M5/M6 plus M7D | Strong generalization; Yagi remains domain-only |
| `MECHCAD_DOCUMENTATION_GAPS.md` | known conflicts and audit-required questions | all available specs | Good coverage: already records permission, M6B provenance/recovery, artifact, provider, and build123d questions |

## 4. Spec Coverage

| Spec | Architecture Destination | Verdict | Notes |
|---|---|---|---|
| M0 bootstrap | Overview, System Contract, Subsystem Contracts | MATCH | Canonical state and separate external records preserved; later architecture correctly extends M0 exclusions |
| M2 ChangeSet | System Contract, Runtime Flow D, Subsystem Contracts | MATCH | Trusted proposal/change boundary preserved; ChangeSet durability wording needs precision |
| M3 invalidation | System Contract, Runtime Flow E, Capability Matrix | MATCH | Concise fail-closed freshness invariant is represented; detailed algorithm remains in M3 |
| M4 run control | Overview, System Contract, Subsystem Contracts | MATCH | Concise revision/failure/convergence/recovery/no-rollback invariant is represented; detailed algorithm remains in M4 |
| M5 ToolBroker | System Contract, Workflow, Runtime Flow, Subsystem Contracts | MATCH | Exact registry, typed calls, permission, immutable records and Evidence boundary represented |
| M5.5A backend foundation | System Contract provider identity, Workflow | MATCH | Trust, registry, health, metadata-only inspection and no authority represented; optionality could be clearer |
| M5.5B-2 gear CAD | System Contract specialized path, Runtime Flow G/K | MATCH | Correctly separated from generic FreeCAD project CAD and assembly |
| M5.5C-3A preliminary section integration | Capability Matrix, provider inventory | MATCH | Native normalized-result integration and preliminary-only authority preserved |
| M6A-1 gateway | System Contract agent contract, Runtime Flow B | MATCH | Read-only context, exact identity, immutable result, stale behavior preserved |
| M6B-1 transmission agent | System Contract inventory, Runtime torque flow | MATCH | Bounded reasoning distinguished from general transmission synthesis |
| M6B-1 validated text | System Contract structured-output rules | MATCH | Explicit mode, whole document, no fallback/repair represented |
| M6B-2A mediation | System Contract, Runtime torque flow, Subsystem Contracts | MATCH | Semantic request, exact policy/tool, independent task permission, no direct model tool access represented |
| M6B-2B round trip | Runtime torque flow, Capability Matrix | AMBIGUOUS | Design contract is represented; the design-only spec is insufficient acceptance evidence, while project-status documentation records M6B as complete as a foundation |
| M7D-1 EL reference | Domain Guide, System kinematics, Capability Matrix | ARCHITECTURE_GENERALIZES_CORRECTLY | Generic axis remains generic; EL data stays in domain layer |
| M7D-2 EL sweep | Domain Guide, Runtime kinematics, Capability Matrix | ARCHITECTURE_GENERALIZES_CORRECTLY | Thin adapter over generic M7C represented without domain leakage |
| M7E-2 concept | Overview/domain notes, Capability Matrix | MATCH | Documentary-only preliminary status retained; not a capability or audit gate |

## 5. Detailed Reconciliation Matrix

| ID | Architecture Claim | Architecture Source | Spec Source(s) | Verdict | Severity | Explanation | Recommended Resolution |
|---|---|---|---|---|---|---|---|
| R-001 | MechCAD is a reusable mechanical-engineering harness; Yagi is one reference domain | Overview sections 1, 2, 17, 21; Domain Guide | M0 general future harness; M7D/E domain scopes | MATCH | INFO | No accepted spec redefines MechCAD as Yagi-specific. | None. |
| R-002 | `DesignState` is canonical and external records are separate | System Contract Authority Rules; Overview sections 4-6 | M0 lines 18-31; M2 lines 5-23 | MATCH | INFO | Semantics align exactly despite different wording. | None. |
| R-003 | Canonical serialization, SHA-256 identity, immutable snapshots and current-pointer behavior are current | Overview sections 5-6; Capability Matrix M1 rows | No M1 spec; M0 explicitly excludes persistence; M2 assumes StateManager | TRACEABILITY_MISSING | HIGH | The architecture's central state-memory contract has no dedicated milestone spec, while project-status documentation records M1 complete. | Prefer an acceptance/traceability record if provenance is needed. Use a `RETROSPECTIVE_BASELINE_CONTRACT` only if a standalone normative source is genuinely useful; no new spec is required for the later implementation audit by default. |
| R-004 | Proposal -> ChangeSet -> ChangeEngine/StateManager is the only mutation path | System Contract; Runtime Flow D; Subsystem Contracts | M2 lines 10-23 | MATCH | INFO | Architecture preserves stale, ownership, operation and resulting-state checks. | None. |
| R-005 | Ownership fails closed and restricts owner paths | System Contract Ownership; Subsystem Contracts | M2 lines 35-40 | MATCH | INFO | Core exact-segment/wildcard ownership semantics agree. | Add exact descendant/path-match wording for completeness. |
| R-006 | Dependency graph produces direct/transitive invalidation outside state | Overview section 8; Runtime Flow E | M3 lines 11-31 | MATCH | INFO | Architecture accurately represents the generic dependency boundary. | None. |
| R-007 | Evidence freshness is exact-bound and fail-closed | System Contract Dependency; Capability Matrix | M3 lines 15-17, 33-37 | MATCH | INFO | Architecture now states the concise invariant that freshness fails closed over the complete accepted M3 revision/invalidation history; detailed algorithm remains in M3. | None. |
| R-008 | RunController binds run/manifest/tasks/results to exact source state | Overview section 9; System Contract Run | M4 lines 20-53, 90-101 | MATCH | INFO | Core run identity, immutable records, binding and resume integrity align. | None. |
| R-009 | Run failure/revision advancement behavior is fully represented | Runtime/Subsystem run summaries | M4 lines 55-88 | MATCH | INFO | Architecture now states accepted revision, failure, convergence, recovery and no-rollback invariants without duplicating M4 algorithms. | None. |
| R-010 | ToolRegistry dispatches exact name/version and ToolBroker enforces typed/bound calls | System Contract Tool Contract; Subsystem Contracts | M5 lines 26-64 | MATCH | INFO | Exact resolution, binding, permissions and fail-closed behavior align. | None. |
| R-011 | Task tool permission is necessarily exact `name@version` | System Contract and gaps GAP-007 | M5 lines 33-37; M6B-2B lines 115-120 | AMBIGUOUS | MEDIUM | The architecture now distinguishes concrete ToolRegistry resolution, broader M5 compatibility wording, and stricter workflow-specific exact permission. Global runtime behavior remains audit-required. | None before audit; preserve GAP-007 as `AUDIT_REQUIRED`. |
| R-012 | ToolCall precedes execution and ToolResult is immutable derived history | Subsystem Contracts; Runtime Flow C/H | M5 lines 39-56, 107-111 | MATCH | INFO | Architecture preserves authority separation and persistence ordering. | None. |
| R-013 | Evidence is eligible only after successful trusted deterministic results and is not a decision | System Evidence Contract | M5 lines 86-105; M3 | MATCH | INFO | Optional evidence fields and freshness remain separate from canonical authority. | None. |
| R-014 | Backend identity/health/provenance are trusted normalized boundaries | System provider section | M5.5A lines 23-80 | MATCH | INFO | Required backend identity fields and conditional library/provider provenance now match M5.5A optionality. | None. |
| R-015 | Standalone py_gearworks calculation models/identity are accepted-spec-backed | System provider table; Capability Matrix py_gearworks row | M5.5B-2 covers provider use in specialized CAD only | TRACEABILITY_MISSING | HIGH | No accepted M5.5B-1 calculation spec exists; the dependent CAD spec is indirect evidence, not direct calculation-provider support. | Qualify the provider row as direct-spec-missing/indirect-evidence-present. An acceptance/traceability record is preferable; a retrospective baseline contract is optional. |
| R-016 | Specialized py_gearworks/build123d gear CAD is narrow derived artifact generation | System specialized path; Runtime Flow G/K | M5.5B-2 lines 3-23, 41-45 | MATCH | INFO | Correctly separated from FreeCAD generic project CAD and assembly. | None. |
| R-017 | bd_materials lookup/mass adapter contract is accepted-spec-backed | Provider table; Capability Matrix material row | C-3A consumes normalized material result but excludes lookup | TRACEABILITY_MISSING | HIGH | No accepted M5.5C-1 provider spec exists; C-3A is indirect dependent evidence only. | Qualify direct versus indirect support and use an acceptance/traceability record if needed; do not create an original-looking spec by default. |
| R-018 | sectionproperties geometry/warping provider contract is accepted-spec-backed | Provider table; Capability Matrix section row | C-3A consumes C-2A/C-2B results; no C-2A/B spec exists | TRACEABILITY_MISSING | HIGH | Detailed shapes, solver, versions and adapter identity are not established by a direct accepted spec; C-3A supplies indirect dependency evidence only. | Qualify direct versus indirect support. An acceptance/traceability record or optional `RETROSPECTIVE_BASELINE_CONTRACT` may be used later if the contract needs a standalone source. |
| R-019 | C-3A consumes persisted IDs and preserves source authority/provenance | Capability Matrix preliminary integration | M5.5C-3A lines 9-54, 102-139 | MATCH | INFO | The architecture's preliminary-only classification agrees. | Add ID-only source-integrity detail to System Contract if useful. |
| R-020 | Material lookup -> comparison -> canonical selection is an unlabeled current runtime flow | Runtime Flow L | C-3A lines 131-139 explicitly excludes material selection | MATCH | INFO | Runtime Flow now separates current provider lookup/preliminary evaluation from `TARGET_NEXT` comparison and canonical selection. | None. |
| R-021 | build123d's expected caller includes the generic CAD compiler | Subsystem Contracts build123d row | M5.5B-2 places narrow CAD adapter behind ToolBroker and excludes general CAD | MATCH | INFO | The subsystem row now names the specialized gear CAD service/tool and optional later artifact verification. | None. |
| R-022 | AgentGateway provides bound read-only context, strict result persistence and stale protection | System Agent Contract; Runtime Flow B | M6A-1 lines 9-25, 27-86 | MATCH | INFO | Fake-only milestone details are not incorrectly universalized into LLM authority. | Attribute FakeAdapter specifically to M6A-1. |
| R-023 | OpenCode is untrusted execution transport and harness owns IDs/binding | System Agent Contract/inventory | M6B-1 lines 16-24, 44-94 | MATCH | INFO | Architecture correctly separates adapter from engineering authority. | Attribute OpenCode to M6B-1, not M6A-1 alone. |
| R-024 | Native schema and validated-text mode are separate fail-closed contracts | System Agent Contract; Capability Matrix | validated-text spec lines 9-84 | MATCH | INFO | No repair, regex extraction, fallback or model-owned metadata is allowed. | None. |
| R-025 | `mechcad-transmission` is bounded reasoning, not general gearbox synthesis | Overview; System inventory; Capability Matrix | M6B-1 lines 9-42, 59-73, 130-134 | MATCH | INFO | General transmission synthesis remains `TARGET_NEXT`. | None. |
| R-026 | Semantic torque mediation uses trusted exact policy and ToolBroker, with no direct agent tool | Workflow; Runtime Torque; Subsystem Contracts | M6B-2A lines 3-29, 166-232, 308-352 | MATCH | INFO | Architecture preserves the bounded one-request ToolResult-only M6B-2A contract. | None. |
| R-027 | ToolResult -> Evidence -> Invocation B round trip is an accepted `FOUNDATION` | System inventory; Capability Matrix M6B-2B | M6B-2B lines 3-28 and 986-1010; project description sections 17-18 | AMBIGUOUS | HIGH | The dedicated design is explicitly design-only and does not authorize implementation/completion. No separate M6B-2B completion report, plan, or closure record was found, but the current project-status record says M6B is complete as a foundation. This is insufficient acceptance provenance, not proof that architecture maturity is wrong. | Add a dated acceptance/traceability record if the milestone was completed, or explicitly record architecture authority pending such evidence. Do not demote maturity solely from spec absence. |
| R-028 | Round-trip recovery is a current foundation matching every designed durable boundary | Subsystem Contracts coordinator row; gaps GAP-008 | M6B-2B lines 122-174, 481-527, 717-774, 877-900 | AMBIGUOUS | HIGH | Detailed recovery is designed, while architecture itself records possible narrower recovery/indexing. Documentation cannot determine accepted current behavior. | Resolve with an accepted M6B-2B completion/contract-narrowing record; leave runtime verdict to later audit. |
| R-029 | M6B-3 typed discovery/materialization/satisfaction is accepted `FOUNDATION` | Capability Matrix rows 27-29; Subsystem Contracts | No M6B-3 spec or plan | TRACEABILITY_MISSING | HIGH | Project summary is lower-precedence acceptance/completion evidence, not an equivalent milestone spec. | Record acceptance/traceability separately if needed. Use a `RETROSPECTIVE_BASELINE_CONTRACT` only if the current architecture lacks a sufficient standalone normative contract. |
| R-030 | M6B-4 trusted resolution loop is `REQUIRED_CURRENT` | Capability Matrix row 30 and M6B trace | No M6B-4 spec or plan; project description sections 17-18 | TRACEABILITY_MISSING | HIGH | Current architecture intentionally defines this maturity, and project-status documentation records the loop implemented and accepted. No dedicated milestone-level specification supplies independent contract traceability. Spec absence alone does not establish a maturity conflict. | Preserve architecture maturity for audit expectations. Add an acceptance/traceability record if useful; use a `RETROSPECTIVE_BASELINE_CONTRACT` only if a standalone normative source is genuinely needed. |
| R-031 | M7A CAD, M7B reference and M7C generic kinematics have accepted milestone spec traceability | Capability Matrix M7 trace | No M7A/B/C specs; M7C plan mentions M7B regression; M7D specs depend on generic M7C | TRACEABILITY_MISSING | HIGH | Direct specification support is missing. Indirect accepted dependency evidence is present for M7C through M7D's explicit use of the existing generic sweep contract, but this does not independently accept M7C. M7A lacks comparable direct milestone support; M7B remains a project-status/domain reference claim. | Preserve the architecture contract and record direct support, indirect dependency evidence, and acceptance evidence separately. Add a traceability record only where useful. |
| R-032 | EL reference/sweep requirements define generic kinematics | System Kinematics and Domain Guide | M7D-1/2 | ARCHITECTURE_GENERALIZES_CORRECTLY | INFO | Architecture extracts valid generic axis/sweep boundaries while retaining EL/Yagi specifics in domain adapters. | None. |
| R-033 | M7E concept is preliminary domain documentation, not generic/current verification | Capability Matrix M7E; Overview domain examples | M7E-2 lines 3-48 | MATCH | INFO | `NOT_VERIFIED` and `NOT_READY` are preserved. | Clarify that “obvious self-collision” is not M7A exact collision evidence. |
| R-034 | Exact collision, transient analysis and generic sweep are accepted-spec-backed current capabilities | Capability Matrix M7A/C rows; System Kinematics | No M7A/C specs; M7D depends on generic M7C; M7C plan describes the generic boundary | TRACEABILITY_MISSING | HIGH | Direct support is missing. M7D provides indirect accepted dependency evidence for M7C's generic service boundary, but not independent M7C acceptance. Architecture remains the current universal authority for expected behavior. | Record direct versus indirect support and completion evidence separately; add a retrospective baseline contract only if a standalone normative source is needed. |
| R-035 | Domain extensions construct generic requests without redefining generic CAD/state/kinematics | Domain Guide; System domain layer | M7D-1/2 boundaries | ARCHITECTURE_GENERALIZES_CORRECTLY | INFO | No domain leakage found in the universal diagrams. | None. |
| R-036 | BackendProvenance always has all six provider fields | System provider identity prose/table | M5.5A lines 45-58 | MATCH | INFO | Architecture now requires backend identity and makes library/provider fields conditional where applicable. | None. |
| R-037 | Pair gear CAD output may be treated as assembly | Generic/specialized CAD descriptions | M5.5B-2 lines 19-23 | MATCH | INFO | System Contract now states that a pair is two artifacts plus nominal transform information, not a `CadAssemblyProgram`. | None. |

### Verdict Totals

| Verdict | Count |
|---|---:|
| MATCH | 24 |
| ARCHITECTURE_GENERALIZES_CORRECTLY | 2 |
| ARCHITECTURE_TOO_BROAD | 0 |
| ARCHITECTURE_TOO_NARROW | 0 |
| SPEC_SUPERSEDED | 0 |
| SPEC_NOT_REFLECTED | 0 |
| DOMAIN_LEAKAGE | 0 |
| MATURITY_MISMATCH | 0 |
| TRACEABILITY_MISSING | 8 |
| AMBIGUOUS | 3 |

## 6. Maturity Reconciliation

Specifications generally define milestone scope rather than the architecture's later four-value maturity taxonomy. “Spec-supported maturity” below means the highest maturity support defensible from accepted specifications alone. Separate columns distinguish direct specification support, indirect accepted dependency evidence, acceptance/completion evidence, and current architecture authority. None of these columns is implementation evidence.

| Capability | Architecture Maturity | Direct Spec Support | Indirect Accepted Dependency Evidence | Acceptance/Completion Evidence | Architecture Authority | Implementation Evidence | Verdict | Evidence |
|---|---|---|---|---|---|---|---|---|
| Canonical typed state separation | FOUNDATION | PRESENT: M0 | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | M0 directly establishes canonical/separate model foundation |
| Immutable revision/hash | REQUIRED_CURRENT | MISSING: no M1 spec | PRESENT: M2 assumes StateManager | Project description records M1 complete | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | M0 excludes persistence; architecture is current authority, but M1 spec provenance is absent |
| ChangeEngine/ownership | REQUIRED_CURRENT | PRESENT: M2 | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | M2 exact mutation/ownership boundary |
| Dependency invalidation/freshness | REQUIRED_CURRENT | PRESENT: M3 | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | M3 direct/transitive/fail-closed semantics |
| RunController | REQUIRED_CURRENT | PRESENT: M4 | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | M4 binds runs and gates completion |
| ToolBroker | REQUIRED_CURRENT | PRESENT: M5 | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | M5 exact dispatch/persistence/binding |
| Backend identity/provenance | FOUNDATION | PRESENT: M5.5A | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | M5.5A explicitly calls itself a foundation for future adapters |
| py_gearworks calculation | FOUNDATION | MISSING: no B-1 spec | PRESENT: M5.5B-2 uses provider in specialized CAD context | Project description records M5.5 foundations complete | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | Do not treat CAD-provider dependency as a direct standalone calculation spec |
| specialized gear CAD | FOUNDATION | PRESENT: M5.5B-2 | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | Narrow accepted milestone scope |
| material lookup/mass | FOUNDATION | MISSING: no C-1 spec | PRESENT: C-3A consumes normalized material result | Project description records M5.5 foundations complete | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | C-3A does not define the provider itself |
| section geometry/warping | FOUNDATION | MISSING: no C-2A/B spec | PRESENT: C-3A consumes C-2A/C-2B results | Project description records M5.5 foundations complete | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | C-3A does not independently define provider details |
| preliminary section integration | FOUNDATION | PRESENT: M5.5C-3A | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | Narrow accepted milestone scope |
| AgentGateway/FakeAdapter | FOUNDATION | PRESENT: M6A-1 | None needed | No separate marker identified | PRESENT - both | NOT AUDITED | MATCH | M6A-1 explicitly defines a gateway foundation |
| OpenCode transport/strict output | REQUIRED_CURRENT | PRESENT: M6B-1 and validated-text specs | None needed | Project description records M6A/M6B foundation complete | PRESENT - both | NOT AUDITED | MATCH | M6A-1 itself excludes OpenCode; M6B owns this refinement |
| bounded transmission agent | REQUIRED_CURRENT | PRESENT: M6B-1 | None needed | Project description records M6B foundation complete | PRESENT - both | NOT AUDITED | MATCH | Bounded reasoning only |
| M6B-2A mediation | REQUIRED_CURRENT | PRESENT: M6B-2A | None needed | Later M6B-2B explicitly accepts M6B-2A baseline | PRESENT - both | NOT AUDITED | MATCH | Acceptance evidence exists outside the design file |
| M6B-2B round trip | FOUNDATION | PRESENT: design-only M6B-2B | None identified | Project description records M6B complete as foundation; no separate M6B-2B closure record | PRESENT - both | NOT AUDITED | AMBIGUOUS | Design contract exists, but design-only status makes acceptance provenance incomplete; this does not independently disprove architecture maturity |
| M6B-3 discovery/satisfaction | FOUNDATION | MISSING: no dedicated spec/plan | None identified | Project description records M6B foundation complete | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | Current architecture may remain authoritative while detailed milestone provenance is weak |
| M6B-4 resolution | REQUIRED_CURRENT | MISSING: no dedicated spec/plan | None identified | Project description says implemented and accepted | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | No dedicated specification; absence alone is not a maturity mismatch |
| Generic M7A CAD/exact geometry | REQUIRED_CURRENT | MISSING: no M7A spec | None identified | Project description records M7A complete | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | Architecture remains current authority for expected behavior |
| Generic M7C transient/sweep | REQUIRED_CURRENT | MISSING: no M7C spec | PRESENT through M7D-1/2 | Project description records M7C complete; plan remains unchecked | PRESENT - both | NOT AUDITED | TRACEABILITY_MISSING | Indirect evidence is present but does not independently accept M7C |
| M7D domain adapters | FOUNDATION | PRESENT: M7D-1/2 | Depends on generic M7C | Project description records M7D complete reference integration | PRESENT - both | NOT AUDITED | MATCH | Domain-reference specs explicitly keep generic layers unchanged |
| M7E concept | No capability maturity/audit gate | PRESENT: M7E-2 documentary concept | None needed | Explicit `NOT_VERIFIED`/`NOT_READY` statuses | PRESENT - both | NOT AUDITED | MATCH | Preliminary concept only |
| General transmission synthesis | TARGET_NEXT | M6B explicitly excludes broad synthesis | None needed | Project roadmap | PRESENT - both | NOT AUDITED | MATCH | M6B specs exclude general synthesis/state model |
| Structural/FEA/dynamics/manufacturing | FUTURE | M5.5/M6/M7 exclusions | None needed | Roadmap future status | PRESENT - both | NOT AUDITED | MATCH | Future scope consistently excluded |

## 7. Generic vs Domain Boundary

| Relationship | Generic Contract | Domain Contract | Verdict | Notes |
|---|---|---|---|---|
| M7D-1 -> generic axis | `RevoluteAxis`, `CadRigidTransform`, discrete sweep request | `YagiELKinematicReference`, 180-300 mm parametric range, no selected height | ARCHITECTURE_GENERALIZES_CORRECTLY | Domain data does not redefine the generic axis |
| M7D-2 -> generic sweep | generic sweep, transient service, FreeCAD measurement provider | Yagi layout/reference binding and fixture-only caller axis | ARCHITECTURE_GENERALIZES_CORRECTLY | Adapter returns a normal generic request |
| M7E-2 -> project CAD | generic persisted CAD is a universal architecture claim | preliminary antenna concept tree and discrete placements | MATCH | M7E does not establish generic CAD acceptance or structural/manufacturing proof |
| M7B references | domain extension architecture | no dedicated M7B spec found | TRACEABILITY_MISSING | M7B remains a domain reference by architecture; no spec supports individual M7B milestone claims |
| Yagi terminology | generic diagrams use axes, frames, instances and domain specs | EL/AZ/Yagi terms stay in M7D/E domain records | MATCH | No `DOMAIN_LEAKAGE` finding |

## 8. M6B Reconciliation

### M6B-1

The architecture accurately represents M6B-1 as bounded transmission reasoning, not general transmission synthesis. It preserves deny-all OpenCode execution, selected authoritative context, harness-owned IDs/bindings, immutable AgentResult, zero automatic proposal application, no direct calculations, and no writable canonical transmission field.

The validated-text spec correctly refines transport without creating fallback: native schema remains default, validated text is explicit, the complete JSON document is validated, and no regex extraction, repair, coercion, or mode switching is allowed.

### M6B-2A

The architecture matches the semantic request -> trusted mediator -> exact torque tool -> ToolCall/ToolResult boundary. M6B-2A stops at ToolResult, passes `evidence_node=None`, and does not create Evidence or Invocation B. The later M6B-2B spec explicitly says M6B-2A is accepted and remains the baseline.

Global task permission semantics remain ambiguous: M5 wording permits a bare name interpretation, while M6B-2B records existing bare-name compatibility but requires exact `mechcad-calc-torque@1.0` for this bounded workflow.

### M6B-2B

The architecture accurately describes the designed one-tool/two-invocation sequence, trusted Evidence materialization, no second ToolCall, no direct OpenCode tool, immutable transitions, freshness gates, and no state mutation. The documentation search found no separate M6B-2B completion report, plan closure, or milestone acceptance record. The project-status document does record M6B as complete as a foundation, while the dedicated design remains explicitly design-only. The resulting issue is `AMBIGUOUS/HIGH`: acceptance provenance is weak, but the design-only specification does not by itself disprove the current architecture maturity.

The recovery contract is also unresolved. The spec requires deterministic mediation indexing and recovery across immutable boundaries without repeating successful calls. The architecture gap register reports potential narrower behavior. Documentation alone cannot choose between them.

### M6B-3 / M6B-4

No dedicated specs or plans exist. The project summary is not equivalent to an accepted milestone spec, but it is relevant acceptance/completion evidence for the current project-status layer. Architecture claims for supported keys, typed drafts, deterministic request IDs, exact satisfaction anchors, persistence/recovery, trusted answers, proposal/ChangeSet application, revision and invalidation therefore lack direct milestone specification traceability. M6B-4 is `TRACEABILITY_MISSING/HIGH`, not a maturity mismatch: current architecture authority and project-status acceptance evidence exist, and no authoritative source says every `REQUIRED_CURRENT` capability must have a dedicated spec.

## 9. M7 Reconciliation

### M7A

No M7A specification or plan exists. Architecture claims for `CadPartProgram`, typed operations, `CadAssemblyProgram`, `CadRigidTransform`, FreeCAD FCStd/STEP generation, fresh reload, exact common volume and exact distance may form a coherent universal contract, but they are not traceable to an accepted M7A spec.

### M7B

No M7B umbrella or sub-milestone specification/plan exists. The only Superpowers mention is an M7B regression command in the M7C plan. M7B remains a domain reference exercise in architecture, but its milestone claims cannot be reconciled against absent specs.

### M7C

No M7C specification exists. The plan defines a generic transient FreeCAD measurement boundary, no canonical mutation, no per-angle durable public artifacts, and generic discrete sweep integration, but all plan checkboxes remain open. The M7D specs depend on an existing generic M7C contract; they do not independently establish M7C acceptance.

### M7D

M7D-1 and M7D-2 align strongly with the architecture. `RevoluteAxis` remains normalized, non-zero and frame-bound; `CadKinematicSweepService` remains single-axis and generic; ordered angles and identities are preserved; the Yagi reference is parametric; the fixture axis is not a selected production axis; transient execution forbids ArtifactStore and state/change mutation; `continuous_sweep_verified=False` remains explicit.

### M7E

M7E-2 is correctly treated as a documentary preliminary concept. Its “obvious self-collision” check is not equivalent to the generic exact collision contract and must not be cited as exact verification.

## 10. Missing Traceability

The following architecture claims have no direct accepted specification support:

1. M1 canonical serialization, immutable revision persistence, hash/current-pointer/recovery details.
2. Standalone py_gearworks calculation API and adapter identity (no M5.5B-1 spec).
3. bd_materials lookup/mass provider contract (no M5.5C-1 spec).
4. sectionproperties geometry/warping provider contract (no M5.5C-2A/B specs).
5. M6B-3 typed constraint discovery/materialization/satisfaction.
6. M6B-4 trusted resolution through ChangeProposal/ChangeSet/revision/invalidation.
7. Generic M7A CAD/assembly/exact collision contract.
8. M7B domain reference sub-milestone contracts.
9. Generic M7C transient/discrete sweep acceptance.

These are documentation traceability findings, not claims that production capabilities are missing.

## 11. Specs Not Reflected in Architecture

No major accepted specification behavior remains unrepresented after the current architecture corrections. Detailed M3 freshness, M4 transition ordering, and M5.5B-2 artifact algorithms remain in their milestone documents by design rather than being duplicated in universal contracts.

The remaining absence of dedicated milestone specifications is recorded under traceability, not treated as missing architecture behavior.

## 12. Superseded / Historical Specs

No specification is explicitly superseded in full.

| Earlier Spec | Later Spec | Relationship | Current Contract |
|---|---|---|---|
| M0 bootstrap | M2-M7 specs | EXTENDS | M0 exclusions describe M0 scope, not permanent system exclusions |
| M2 ChangeSet | M3 invalidation | EXTENDS | M2 owns canonical mutation; M3 consumes changed paths and persists derived invalidation |
| M3 invalidation | M4 run control | EXTENDS | M4 composes EvidenceStore/freshness and gates run completion |
| M4 run control | M5 ToolBroker | EXTENDS | M4 remains run authority; M5 adds deterministic tool records |
| M5 ToolBroker | M5.5A backend foundation | EXTENDS | Backend identity/provenance augments ToolResult/Evidence without backend execution in A |
| M5.5A | M5.5B-2 / C-3A | EXTENDS | Narrow provider/artifact/integration contracts use normalized boundaries |
| M6A-1 | M6B-1 | EXTENDS | Fake-only gateway remains valid; M6B-1 adds real OpenCode transmission reasoning |
| M6B-1 agent | M6B-1 validated text | REFINES | Adds explicit transport mode without changing trusted materialization |
| M6B-1 | M6B-2A | EXTENDS | Adds semantic requests and trusted mediation; existing no-request behavior remains |
| M6B-2A | M6B-2B | EXTENDS | M6B-2B design adds Evidence/Invocation B and explicitly preserves accepted M6B-2A baseline |
| Generic M7C (no spec) | M7D-1 / M7D-2 | DOMAIN_ADAPTER_OVER_GENERIC | Domain references construct generic requests without changing generic services |
| M7D-1 | M7D-2 | EXTENDS | Adds thin executable domain adapter/fixture over the reference model |
| M7E-2 | Generic architecture | INDEPENDENT | Preliminary concept is not generic acceptance evidence |

## 13. Blocking Contradictions

No direct normative contradiction was found that prevents a clean implementation/integration audit from using the current architecture as the expected contract. The following high-severity traceability weaknesses should be made explicit to the auditor but are not blockers by themselves:

1. **M6B-2B acceptance provenance:** architecture assigns `FOUNDATION`; the design-only spec does not authorize implementation, while the project-status document records M6B as complete as a foundation. The auditor must treat acceptance provenance as weak and still test against the current architecture contract.
2. **M6B-4 direct spec traceability:** architecture assigns `REQUIRED_CURRENT`; no dedicated milestone spec exists, but project-status documentation records the loop as implemented and accepted. The auditor can test the explicit architecture contract without inventing behavior.

Missing M1, provider, and M7A/C specs are traceability gaps, not semantic contradictions. They weaken the specification evidence chain but do not prevent the later audit from using the current architecture contract as the expected behavior.

## 14. Recommended Documentation Fixes

Do not apply these changes as part of this audit.

### A. Architecture Corrections Before Implementation Audit

The material-flow staging, specialized build123d caller, conditional provenance wording, gear-pair boundary, and concise M3/M4 invariants are corrected. No additional architecture correction is required by this reconciliation.

M5 permission semantics remain intentionally audit-required: the architecture distinguishes concrete registry resolution, general M5 compatibility wording, and stricter M6B workflow policy without inventing a new global rule.

### B. Traceability Improvements

1. Add an M1 acceptance/traceability record if the existing current-state contract needs a dedicated provenance anchor.
2. Add a dated M6B-2B completion/acceptance record if the round trip was completed; otherwise retain its design-only status as acceptance evidence limitation.
3. Record M6B-3/M6B-4 acceptance provenance separately from the project summary if stronger milestone traceability is needed.
4. Record M7A/M7B/M7C acceptance/traceability evidence, including M7C's indirect dependency evidence through M7D.
5. Qualify provider rows with direct spec support versus indirect C-3A/dependent evidence.

### C. Optional Retrospective Documentation

Retrospective documentation is not required solely because an original dedicated spec is absent. Where useful, a later document may be explicitly labeled `RETROSPECTIVE_BASELINE_CONTRACT`; it must not be presented as the original pre-implementation design specification. An acceptance/completion record is preferable when the current architecture already provides the normative contract and only milestone provenance is missing. No new specification is required when the architecture plus accepted predecessor/successor specs provide sufficient expected behavior for the implementation audit.

## 15. Audit Readiness

**READY_FOR_IMPLEMENTATION_AUDIT**

The architecture now provides a coherent, testable expected contract. Remaining issues are traceability weaknesses, M6B-2B acceptance ambiguity, and M5 permission behavior explicitly reserved for observation in the later audit. M6B-4 remains `TRACEABILITY_MISSING/HIGH`, not a maturity conflict. No direct normative contradiction prevents the implementation/integration audit from proceeding.
