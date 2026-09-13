# F11 Structural Evidence Node Authority Design

## Status and Scope

This is an approval-gated design for F11 only. It does not authorize or contain
production implementation. It does not remediate F3, F8, F21, any P3 finding,
general cleanup, or unrelated architectural work.

The inspected worktree is `master` at
`773da15dcc3863d00b0abb1e7bb5f4ac4942b377`, which contains the requested
accepted remediation baseline. The worktree also contains unrelated modified
and untracked user work; it was not changed.

## Current Defect

Two incompatible Evidence authorities currently use the same persisted
`kind`/dependency node, `analysis.structural`:

| Family | Producer | Evidence form | Current kind |
| --- | --- | --- | --- |
| SECTION_TOOL_FAMILY | M5.5C geometry, warping, and preliminary section-engineering tools | Generic tool Evidence referring to `SectionGeometryResult`, `SectionWarpingResult`, or `PreliminarySectionEngineeringResult` ToolResults | `analysis.structural` |
| TYPED_STRUCTURAL_EVIDENCE_FAMILY | M11-5 `StructuralEvidencePublisher` | Generic Evidence carrying a typed `StructuralEvidencePayload` | `analysis.structural` |

`EvidenceStore.fresh_evidence_status()` selects records solely by `kind`; run
completion uses that selection for required Evidence nodes. M3 freshness also
uses `evidence.kind` to compare invalidation records. Consequently, either
family can satisfy a query for the shared node, although
`StructuralEvidenceVerifier._require_payload()` fail-closes on a section-tool
record. The shared graph node also means material and structural-definition
changes stale both families.

## Historical Intent

M5.5C (`4bc2310`) intentionally registered section geometry, warping, and
preliminary section-engineering tools under `analysis.structural`, but its
reconstructed status is implementation present with no retained acceptance or
durable execution record. M11-2 (`682300b`) later made a canonical structural
definition invalidate that node. M11-5 (`07950cd`) deliberately reused the node
for durable typed FEA Evidence without identifying the existing section-tool
authority. M11-5 is accepted with retained bounded live evidence, but no M11-5
Evidence JSON or solver workspace is repository-managed.

The current normative structural contract also calls ordinary M11-5 Evidence
`analysis.structural`. Retaining that identity therefore preserves the most
specific current typed structural contract and its accepted identifier behavior.

## Producer and Consumer Inventory

All tracked `analysis.structural` occurrences were classified; there are no
UNKNOWN occurrences. Untracked `projects/**` was searched separately and has no
matching record. `.superpowers/sdd/task-3-report.md` is a tracked historical
working report, not a runtime authority.

| Classification | Files and symbols | Role and contract exposure |
| --- | --- | --- |
| SECTION_TOOL_FAMILY | `tools/sections.py:SectionTools.registrations` | Six persisted generic tool-Evidence producers. `kind` enters the UUIDv5 tool Evidence ID and is persisted. |
| SECTION_TOOL_FAMILY | `tools/section_engineering.py:SectionEngineeringTools.registrations` | One persisted generic tool-Evidence producer; complete-stiffness results only. Same identity behavior. |
| TYPED_STRUCTURAL_EVIDENCE_FAMILY | `structural/evidence.py:EvidenceSubject` | Typed subject discriminator and persisted/wire kind. The subject is included in `StructuralEvidencePayload.semantic_hash`. |
| TYPED_STRUCTURAL_EVIDENCE_FAMILY | `structural/evidence_service.py:StructuralEvidencePublisher.publish` and `StructuralEvidenceVerifier._require_payload` | Publishes typed FEA Evidence through `EvidenceStore`; verifier accepts only typed payload plus exact discriminator. The typed Evidence ID derives from the semantic hash. |
| SHARED_INFRASTRUCTURE | `dependency/storage.py:write_evidence`, `get_evidence_freshness`, `fresh_evidence_status` | Persists one project-scoped `evidence/<id>.json` namespace; validates graph membership and performs kind-only freshness/readiness selection. |
| SHARED_INFRASTRUCTURE | `dependency/graph.py:DependencyGraph.impact` | Computes invalidation by node identity and graph edges. |
| SHARED_INFRASTRUCTURE | `runs/controller.py:evaluate_completion`, `agents/context.py:ContextBuilder`, `agents/roundtrip.py` | Consumers of kind-based readiness/freshness. No structural-specific readiness selector exists. |
| SHARED_INFRASTRUCTURE | `config/dependencies.yaml` | `/materials/*` and `/structural_analysis_definitions/*` currently invalidate the shared node; `analysis.loads -> analysis.structural -> validation.structural` and the convergence edge couple the node downstream. |
| TEST_OR_FIXTURE | `test_section_tools.py`, `test_section_warping_tools.py`, `test_section_engineering_tools.py` | Local graph fixtures and exact section-tool node assertions. |
| TEST_OR_FIXTURE | `test_structural_evidence_models.py`, `test_structural_evidence_verifier.py`, `test_structural_models.py`, `test_m11_3_live_structural.py` | Exact M11 kind/discriminator, graph, persistence, and invalidation expectations. |
| TEST_OR_FIXTURE | `test_dependency.py`, `test_agent_authoritative_context.py` | Generic M3 fixtures using the literal; the latter is a non-authoritative generic-tool fixture, not section or FEA Evidence. |
| DOCUMENTATION | `docs/architecture/**`, `docs/audit/**`, `docs/reconstruction/**`, `docs/superpowers/**`, `.superpowers/sdd/task-3-report.md` | Normative/current, audit, historical, plan, and working-report references respectively. Historical records are read-only. |

`ProductionApplication.create()` does not register section tools by default;
they can be supplied through `additional_tool_registrations`. M11 typed Evidence
is composed by default. This does not remove the collision when a caller adds
the section registrations to the same project EvidenceStore.

## Persisted Compatibility Findings

`EvidenceStore` writes `projects/<project_id>/evidence/<evidence-id>.json`.
The filename is ID-based, but `kind` is persisted and has identity effects:

| Question | Finding |
| --- | --- |
| Accepted/persisted section-tool Evidence at the old kind | None found in tracked managed data, accepted fixtures, goldens, or untracked `projects/**`. |
| Accepted/persisted typed FEA Evidence at the old kind | None found. M11-5 reconstruction explicitly records that no Evidence JSON was committed. |
| Deterministic classification | Canonical-valid FEA records are identifiable by `structural_evidence_payload`, typed `subject`, and structural producer bindings. A generic tool record is identifiable from its tool producer metadata. A malformed or generic legacy record without either binding is ambiguous and must not be reclassified heuristically. |
| Backward-read requirement | Not required by repository-managed authority because there are no legacy records. It is not proven for unmanaged external project stores. |
| Kind in identity | Yes. Tool Evidence ID is UUIDv5 over project, run, ToolResult ID, and node. FEA `subject` is included in the payload semantic hash that derives the deterministic Evidence ID. |
| Other impact | A rename changes persisted JSON, graph readiness/freshness/invalidation behavior, registered tool authorization, exact tests, and documents. It does not affect file naming independently of the identity-derived ID. |

No repository authority needs migration. An external store containing old generic
section Evidence is outside this evidence set. It must not silently be treated
as FEA Evidence after the change; if such support is required, it needs an
explicit approved migration policy.

## Authority-Boundary Matrix

| Concern | Section-tool authority | Structural-FEA authority |
| --- | --- | --- |
| Semantic purpose | Preliminary section geometry, warping, and stiffness properties | Source-bound single-solid linear-static FEA conclusion |
| Payload schema | Generic tool Evidence plus verified typed ToolResult output | `StructuralEvidencePayload` with typed subject |
| Producer | `SectionTools`, `SectionEngineeringTools`, `ToolEvidenceMaterializer` | `StructuralEvidencePublisher` |
| Verifier | Tool-result/tool-registration binding checks; no structural semantic verifier | `StructuralEvidenceVerifier` only |
| Dependency inputs | Tool inputs and bound revision; material affects the preliminary engineering subset | Canonical structural definition, its material assignment, loads, geometry, mesh, solver artifacts, and result bindings |
| Readiness semantics | A fresh `analysis.section` record may satisfy only a section-tool-required node | A fresh `analysis.structural` record may satisfy only a structural-FEA-required node |
| Freshness semantics | M3 graph freshness for `analysis.section` | M3 graph freshness for `analysis.structural`; structural pointer currentness remains separate F3 scope |
| Invalidation triggers | No structural-definition, load, validation, or FEA-convergence edge; material-family invalidation remains conservative for the section family | Existing M11 structural-definition/material/load-to-validation/convergence relationships remain unchanged |
| Persisted kind | `analysis.section` for newly written section-tool Evidence | `analysis.structural` unchanged |
| Compatibility constraint | New tool IDs/wire values for future output; no repository legacy record | Preserve existing M11 kind, subject, semantic hash, and deterministic ID bytes |

Required negative semantics follow from that matrix:

| Change/input | Section-tool Evidence | Structural-FEA Evidence |
| --- | --- | --- |
| Material change | May stale the conservative section family; section engineering consumes material | Stales under the existing FEA rule |
| Structural-analysis-definition change | Must not stale | Must stale |
| Section-tool-specific source change | Must not stale FEA | No FEA effect |
| FEA-specific definition/mesh/solver/result change | Must not stale section-tool Evidence | Is handled at the existing FEA verification/freshness authority as applicable |

The graph cannot express per-ToolResult dependency specificity. Retaining a
material-to-section-family rule is conservative; it must not be described as
per-record precision.

## Options Considered

| Option | Compatibility and risk | Decision |
| --- | --- | --- |
| A. Rename M11 typed FEA to `analysis.structural.evidence` | Changes the normative M11 kind, typed subject, payload semantic hash, deterministic FEA ID, all M11 graph edges, convergence relation, readiness, and accepted test/golden values. It preserves old section tool output, but requires relocating all historical structural graph meaning away from the retained name. | Rejected: larger authority reinterpretation and worse M11 compatibility. |
| B. Rename M5.5C section tools to `analysis.section` | Changes only future section-tool registered kind and derived tool Evidence ID. Keeps M11 typed wire/hash/ID behavior and existing structural graph semantics. Requires a distinct graph node and section-focused test fixtures. | Recommended. |
| C. Versioned compatibility namespace | Could retain or explicitly migrate old generic section records only if authoritative legacy stores are supplied and approved. Runtime schema guessing cannot be the authority. | Deferred/not needed for repository state; required only on approved external legacy-store support. |

## Recommended Namespace Design

Adopt `analysis.section` as the sole M5.5C section-tool Evidence node. Retain
`analysis.structural` and `analysis.structural.convergence` exclusively for
M11 typed structural Evidence.

The implementation phase, if approved, must:

1. Change only section-tool registrations and their focused fixtures to
   `analysis.section`.
2. Add `analysis.section` to the dependency graph through the narrow existing
   material rule so `EvidenceStore.write_evidence()` recognizes it.
3. Leave every M11 `EvidenceSubject`, structural Evidence kind, semantic hash,
   structural Evidence ID, and existing structural graph edge unchanged.
4. Ensure section nodes have no edge to `validation.structural` or
   `analysis.structural.convergence`; a structural-definition change must not
   list `analysis.section`.
5. Update only current normative/inventory documentation required to state the
   new authority boundary. Do not edit `docs/reconstruction/**` or accepted
   audit records without separate authorization.

## Compatibility Policy

The selected policy is a clean namespace boundary for newly produced records,
with no repository-data migration. The generic Evidence loader may continue to
parse an old `analysis.structural` record because it is schema-permissive, but
the implementation must not claim it is section Evidence or let it qualify as
new section readiness. No "accept either schema" verifier path and no heuristic
runtime classification is allowed.

If a user later provides an authoritative external legacy store containing
section-tool records, implementation must stop before supporting it. The user
must approve a separate policy that defines the authoritative classifier,
reissued IDs, preserved source records, readiness behavior during migration, and
legacy-support end condition.

## Verification Strategy

The implementation plan must add focused tests for:

| Proof | Required assertion |
| --- | --- |
| Section output node | Every section geometry, warping, and engineering registration authorizes only `analysis.section`; materialized Evidence uses that kind. |
| FEA output node | `StructuralEvidencePublisher` emits only unchanged `analysis.structural`; typed discriminator and verifier behavior remain exact. |
| Wrong-family readiness | Section Evidence cannot satisfy a plan requiring `analysis.structural`; typed FEA Evidence cannot satisfy `analysis.section`. |
| Wrong-family freshness/currentness | Kind-based lookup and M3 freshness for one authority do not qualify the other; structural verifier still rejects section Evidence. |
| Scoped invalidation | Structural-definition changes stale structural FEA but not section Evidence. Section/material-family invalidation does not stale FEA unless material is deliberately shared; test the intended material case explicitly. |
| Persistence/reload | Newly emitted `analysis.section` tool Evidence reloads and is fresh under the section node; typed FEA reload bytes and identity remain unchanged. |
| Regression scope | Existing M11 discriminators, IDs/hashes, convergence node, M3 structural dependencies, and unrelated node identities remain unchanged. |
| Legacy guard | A synthetic old generic `analysis.structural` section-like record cannot be used as new section readiness and is rejected by `StructuralEvidenceVerifier`; no heuristic reclassification occurs. |

Run the focused section, dependency/run readiness, structural Evidence model,
structural verifier, and structural model tests. Use the existing M11 live suite
only if the approved implementation alters its configuration path; no live
runtime execution is authorized by this design.

## Explicit Non-Goals

- No F3 currentness/freshness consolidation.
- No F8, F21, P3, general cleanup, or architectural redesign.
- No change to F1 M10 validation, F4 mesh identity, F5 provenance identity,
  F6 physical-root identity, or F7 CAD-dimension semantics.
- No removal of either producer family.
- No multi-objective readiness, schema-union verifier, or automatic migration.
- No modification of `docs/reconstruction/**`.

## Acceptance Criteria

1. The two families have distinct persisted node identities.
2. Both families remain supported under their own authority.
3. No wrong-family record satisfies readiness, freshness, or currentness merely
   by matching a string.
4. Invalidation is scoped to semantic authority and structural verification
   remains fail-closed and typed-only.
5. The M11 typed wire/hash/ID contract remains unchanged.
6. No repository-managed authoritative legacy record becomes unreadable or
   misclassified.
7. Focused tests prove the matrix above and unrelated node identities do not
   change.

## Approval Gate

No production implementation has started. Approval is required before writing
an implementation plan or changing code/tests/configuration.
