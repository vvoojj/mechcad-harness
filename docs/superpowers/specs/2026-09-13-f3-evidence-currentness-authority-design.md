# F3 Evidence Currentness Authority Design

## Status and Scope

This is an approval-gated design for F3 only. It does not authorize production
implementation, an implementation plan, or tests. It does not remediate F8,
F21, any P3 finding, general cleanup, or unrelated refactoring.

The inspected baseline is `master` at
`be958e464ebd6c65567db15212aae2c278b134df`. It includes the accepted F2,
F7, F1, F4, F5, F6, and F11 remediations. Pre-existing modified and untracked
work was recorded and is outside this scope.

## Current Defect

F3 identified three live concepts under the broad names freshness and
currentness:

1. M3 graph freshness: `EvidenceStore.get_evidence_freshness()` evaluates one
   persisted Evidence record against its configured dependency node and all
   required later invalidation records.
2. Structural Evidence currentness: `StructuralEvidenceVerifier.currentness()`
   compares the typed structural Evidence source binding to the durable current
   state pointer.
3. Candidate currentness: `CandidateCurrentnessService.evaluate_source_binding()`
   evaluates a noncanonical candidate against its explicit consumed canonical
   authority paths.

`StructuralEvidenceCurrentness` and `CandidateCurrentness` declare the same
three wire values independently:

```text
current
stale_relative_to_current_state
currentness_unavailable
```

The audit correctly identified the duplicate vocabulary. Its description of
both later paths as the same pointer comparison does not describe the current
candidate implementation: candidate currentness deliberately permits a newer
revision when every declared consumed-authority value is unchanged. Therefore
the current code contains one duplicated status vocabulary, but not two
equivalent currentness evaluators.

## Historical Intent

M3 is the derived dependency/invalidation authority. It is not a canonical
revision writer. Its design requires exact Evidence provenance, complete
post-Evidence invalidation history, and no later impact to return graph
`CURRENT`; unknown history/provenance and unknown nodes fail closed.

M11-5 deliberately separated structural Evidence integrity, engineering
outcome, and currentness. Its approved design specifies a separate
current-pointer lookup and explicitly says that later graph additions may
affect selection/cache freshness only, not historical Evidence integrity.

M12 established candidates as immutable, noncanonical, source-bound records.
Its candidate-source model binds explicit canonical paths and value hashes.
The current M12 implementation retains a candidate after an unrelated
canonical revision, but returns stale when a consumed path's value changes.
This behavior is directly guarded by
`test_source_validation_and_relevance_sensitive_currentness`.

F11 has separated the former shared section-tool and typed-FEA Evidence node:
section tools write `analysis.section`; typed structural Evidence retains
`analysis.structural`. This removes wrong-family node selection and
cross-invalidation from M3 graph freshness. It does not change either
structural pointer currentness or candidate source currentness.

## Current Implementation Inventory

| Classification | Surface | Current role |
| --- | --- | --- |
| GRAPH_FRESHNESS | `dependency/models.py:EvidenceFreshness` | M3's `current` / `stale` / `unknown` result vocabulary. |
| GRAPH_FRESHNESS | `dependency/graph.py:DependencyGraph.impact` | Sole direct/transitive dependency-impact authority. |
| GRAPH_FRESHNESS | `dependency/storage.py:get_evidence_freshness` | Checks Evidence historical snapshot hash, graph membership, complete later invalidation history, and node impact. |
| READINESS_CONSUMER | `dependency/storage.py:fresh_evidence_status` | Aggregates M3 freshness by persisted Evidence `kind`. |
| READINESS_CONSUMER | `runs/controller.py:evaluate_completion` | Requires a fresh M3 Evidence record for every required node. |
| UI_OR_CONTEXT_SURFACE | `agents/context.py:ContextBuilder` | Requires M3 `CURRENT` before putting selected Evidence in agent context. |
| POINTER_CURRENTNESS | `structural/evidence.py:StructuralEvidenceCurrentness` | Structural currentness vocabulary. |
| POINTER_CURRENTNESS | `structural/evidence_service.py:StructuralEvidenceVerifier.currentness` | Validates typed structural Evidence binding, then compares its source `(revision, state_hash)` to `StateManager.load_current_pointer()`. |
| UI_OR_CONTEXT_SURFACE | `application.py:check_structural_evidence_currentness` | Public read-only structural currentness API. |
| STATUS_VOCABULARY | `candidates/services.py:CandidateCurrentness` | Candidate currentness vocabulary, byte-identical to the structural enum. |
| POINTER_CURRENTNESS | `candidates/services.py:CandidateCurrentnessService` | Candidate source-relevance evaluator. Exact pointer equality validates the source binding; after a newer revision it compares each explicit consumed path hash instead of requiring pointer equality. |
| READINESS_CONSUMER | `candidates/evaluation.py`, `cad_realization.py`, `promotion.py` | Rejects a non-current candidate before candidate CAD, evaluation, and promotion. |
| READINESS_CONSUMER | `candidates/multi_joint_m10_evaluation.py`, `multi_joint_selection.py` | Rejects a non-current candidate before multi-joint evaluation/selection. |
| PERSISTED_OR_WIRE_CONTRACT | `CandidateSourceBinding` and structural Evidence source binding | Persist revision/state-hash bindings and candidate consumed-path hashes; they do not persist a derived currentness result. |
| PERSISTED_OR_WIRE_CONTRACT | `Evidence.kind`, Evidence revision/state hash, invalidation JSON | Persist M3 inputs; `EvidenceFreshness` is derived rather than persisted. |
| TEST_ONLY | `test_dependency.py`, `test_runs.py`, `test_tools.py`, structural verifier/model tests, candidate foundation/service and M12/M13 tests | Assert the separate graph, structural, and candidate contracts. |

No occurrence in the F3 surface remains UNKNOWN. Other repository uses of
`state_hash` are source/provenance/identity bindings, not a currentness
authority, unless they call one of the evaluators above.

## Semantic Boundary Matrix

| Concern | M3 graph freshness | Structural currentness | Candidate currentness |
| --- | --- | --- | --- |
| Authority | `DependencyGraph.impact` plus `EvidenceStore` invalidation persistence/query | `StructuralEvidenceVerifier.currentness` | `CandidateCurrentnessService.evaluate_source_binding` |
| Input identity | Persisted Evidence `kind`, revision/state hash, graph configuration, later invalidation records | Typed structural Evidence payload/source binding and current pointer | Candidate source binding, current state, explicit consumed paths/value hashes |
| Dependency invalidation aware | Yes, direct and transitive node impact over complete later history | No | No M3 invalidation records; yes only to its explicitly enumerated source paths |
| Current revision aware | Only to determine required invalidation-history range; a later unrelated revision can remain fresh | Yes, exact tuple equality required | Yes; newer revision triggers consumed-path comparison rather than automatic stale |
| Current state hash aware | Verifies Evidence hash against its historical snapshot, not equality to current pointer | Yes, exact tuple equality required | Yes at the source revision; later revisions compare consumed-path value hashes |
| Persisted status | No; derived `current` / `stale` / `unknown` | No; derived status returned by public API | No; derived status returned to candidate gates |
| User/context-visible | Yes, agent-context and run-completion readiness | Yes, public application API | Indirectly, through candidate CAD/evaluation/selection/promotion rejection |
| Failure/unavailable semantics | `UNKNOWN` for missing/invalid provenance/history/configuration | `CURRENTNESS_UNAVAILABLE` only when current pointer is unavailable/malformed; typed Evidence failures are integrity errors | `CURRENTNESS_UNAVAILABLE` when current state/path resolution cannot be established; forged binding is an integrity error |

The resulting answers are explicit:

1. Graph freshness is not a stronger version of pointer currentness. It proves
   a different condition: graph-node invalidation history after a record's
   historical binding.
2. No, not for one ordinary M3 Evidence record under the current implementation.
   Pointer-current means the Evidence binding revision equals the current
   revision; M3 explicitly excludes that revision's invalidation and has no
   later revision to inspect. A matching later invalidation necessarily advances
   the pointer and makes strict structural pointer currentness stale as well.
   The audit's broader statement is a semantic warning, not a currently
   reachable same-record status combination.
3. Yes. Graph freshness can be `CURRENT` while structural pointer currentness is
   stale after an unrelated later revision with complete invalidation history
   that does not impact `analysis.structural`. Candidate currentness can also
   remain `CURRENT` after such an unrelated revision by its own contract.
4. Structural and candidate currentness are vocabulary-identical, not
   semantically identical. Structural currentness is strict current-pointer
   equality; candidate currentness is relevance-sensitive source authority.
5. Candidate CAD/evaluation/selection/promotion consumers require candidate
   source currentness and must not inherit M3 graph semantics. Their candidates
   have no Evidence node to query, and unrelated state revisions are accepted
   by current behavior.
6. Agent context and run completion require M3 graph freshness. Pointer
   currentness alone is unsafe there because it cannot prove dependency
   invalidation coverage.
7. F11 namespace separation makes M3 graph freshness unambiguous between
   `analysis.section` and `analysis.structural`; it changes no pointer/current
   status result and must remain intact.

## Compatibility Findings

The three shared currentness strings appear in the two enum declarations and
tests. No tracked JSON/YAML fixture, golden payload, managed project Evidence,
or accepted persisted record was found containing
`stale_relative_to_current_state` or `currentness_unavailable`. The literal
`current` has unrelated ordinary-language/test occurrences but no F3 persisted
status fixture contract.

The values still participate in public behavior: the structural public API and
candidate service/consumer injection interfaces return enum members whose JSON
form is the stated string. The enum import paths are also public Python surface
used by tests and candidate consumers. Any future enum unification must retain
the exact serialized values and deliberately decide whether the existing module
imports remain re-export aliases. That import-path question is separate from
wire compatibility.

M3 `EvidenceFreshness` is a distinct public vocabulary (`current`, `stale`,
`unknown`) and is derived from persisted Evidence/invalidation inputs. It must
not be renamed to the structural/candidate vocabulary or serialized as one.

## Options Considered

| Option | Assessment | Decision |
| --- | --- | --- |
| A. Shared currentness vocabulary only | Introduce one neutral leaf `Currentness` enum with the three existing string values. Structural and candidate retain separate evaluation functions. Existing module names can re-export the shared enum if import compatibility is required. This removes the proven duplicate authority without changing either semantic contract. | Recommended. |
| B. Shared pointer-currentness evaluator | A neutral tuple-comparison primitive could serve structural currentness and candidate's same-revision fast path, but candidate's newer-revision relevance test remains a separate authority. It does not replace candidate currentness and would add an abstraction with little proven duplication removed. | Not recommended now. Reconsider only if a second strict pointer consumer is added. |
| C. Compose graph freshness where applicable | Structural Evidence consumers could explicitly require both pointer currentness and M3 freshness, but no current consumer is proven to require that conjunction. M11-5 explicitly preserves graph effects as selection/cache freshness, while run/context already use M3 directly. | Deferred. Add only with a consumer-specific approved contract and a declared Evidence node. |
| D. Collapse all three into one function | Incorrect: M3 depends on graph/history, structural requires exact pointer equality, and candidate allows relevance-preserving newer revisions. It would change accepted behavior and make one condition falsely stand in for another. | Rejected. |

## Recommended Authority Design

Adopt option A after approval:

1. Define one neutral shared currentness status vocabulary at a leaf dependency
   boundary, preserving exactly `current`, `stale_relative_to_current_state`,
   and `currentness_unavailable`.
2. Make structural and candidate public enum names aliases/re-exports of that
   one vocabulary only if focused import and serialized-value tests prove no
   compatibility change.
3. Retain `StructuralEvidenceVerifier.currentness()` as the sole strict
   structural-pointer evaluator.
4. Retain `CandidateCurrentnessService` as the sole candidate source-relevance
   evaluator, including its newer-revision consumed-authority comparison.
5. Retain `DependencyGraph` and `EvidenceStore` as the sole M3 invalidation and
   graph-freshness authority. Do not route it through the shared currentness
   enum or evaluator.
6. Document each consumer's required condition instead of adding implicit
   fallback or conjunction behavior.

This is `DOCUMENT_AUTHORITY_BOUNDARY` followed by the smallest semantically
valid `CANONICALIZE_ON_EXISTING_AUTHORITY`: canonicalize the identical status
vocabulary only. It does not claim a common evaluator where the implementations
do not have one.

## Graph Freshness vs Pointer Currentness

Graph freshness answers: "Does this Evidence node remain usable under complete
recorded M3 invalidation history?" It is node-scoped and fails closed on missing
history.

Structural pointer currentness answers: "Does this valid typed structural
Evidence bind exactly to the present canonical pointer?" It does not inspect
the dependency graph or invalidation records.

Candidate currentness answers: "Does this valid candidate still agree with the
current values at every explicitly consumed canonical authority path?" It is
not an Evidence-node query and has no M3 history dependency.

No current API may substitute one answer for another. A new consumer that needs
both must call both named authorities and define a combined result at that
consumer boundary, without changing either underlying status meaning.

## Consumer Integration Rules

- `RunController.evaluate_completion` and `ContextBuilder.build` must continue
  to require M3 `EvidenceFreshness.CURRENT`; they must not use structural or
  candidate currentness.
- Structural verification remains separate from structural currentness. A
  pointer failure is not a structural integrity or engineering-outcome change.
- `check_structural_evidence_currentness` must remain strict-pointer only until
  an approved consumer explicitly requires graph freshness as well.
- Candidate CAD, candidate evaluation, selection, and promotion must continue
  to require candidate source-relevance currentness. They must not require a
  generic Evidence record, dependency node, or graph invalidation history.
- A candidate or structural record may never be reported current because an
  unrelated Evidence record is fresh.
- Preserve F11 node separation: structural M3 queries use
  `analysis.structural`; section-tool M3 queries use `analysis.section`.

## Verification Strategy

The implementation plan, if approved, must add and run focused tests for:

| Proof | Required assertion |
| --- | --- |
| Shared vocabulary | Structural and candidate names have the exact three unchanged string values and, if unified, identify the same enum members without import cycles. |
| Structural strict pointer | Matching current revision/state hash returns `CURRENT`; either mismatch returns `STALE_RELATIVE_TO_CURRENT_STATE`; unavailable/malformed pointer returns `CURRENTNESS_UNAVAILABLE`. |
| Candidate relevance | Matching source returns `CURRENT`; a newer unrelated revision remains `CURRENT`; a changed consumed path returns `STALE_RELATIVE_TO_CURRENT_STATE`; unavailable current state/path returns `CURRENTNESS_UNAVAILABLE`. |
| Structural/candidate non-equivalence | A newer unrelated revision makes structural pointer currentness stale while candidate source currentness remains current for an unchanged consumed path. |
| M3 distinction | Prove an unrelated later recorded invalidation can leave graph freshness `CURRENT` while strict structural pointer currentness is stale. Also prove a matching later invalidation makes graph freshness stale; it necessarily makes strict pointer currentness stale too under M3's own-revision exclusion. |
| Correct readiness authority | Run completion and agent context reject M3 stale/unknown Evidence even if a pointer-current result exists; candidate consumers reject candidate non-currentness without querying M3. |
| F11 isolation | `analysis.section` and `analysis.structural` freshness/readiness remain independent under their separate nodes. |
| Serialization | Existing JSON values for the three currentness strings and M3's separate `current`/`stale`/`unknown` vocabulary remain unchanged; accepted/golden tests remain valid. |
| Dependency safety | Importing structural, candidates, and dependency packages introduces no cycle; run focused existing M3, structural Evidence, candidate currentness, M12/M13 currentness, and F11 node-isolation regressions. |

The graph/pointer distinction test must construct its invalidation records
explicitly. It must not rely on a live CAD/solver invocation, and it must not
claim that the two concepts are ordinarily synchronized.

## Explicit Non-Goals

- No collapse of M3 freshness, structural currentness, and candidate currentness.
- No graph-invalidation policy change, dependency configuration change, or M3
  persistence-format change.
- No change to F11's `analysis.section` / `analysis.structural` separation.
- No F1 M10 trust-stage change, F4 mesh hash change, F5 provenance identity
  change, F6 physical root hash change, or F7 CAD dimension change.
- No new automatic Evidence selection, promotion, candidate search, or
  multi-objective behavior.
- No live FreeCAD/Gmsh/CalculiX execution.
- No modification of `docs/reconstruction/**` or accepted audit records.

## Acceptance Criteria

1. M3 remains the sole dependency-invalidation and graph-freshness authority.
2. Structural strict-pointer currentness and candidate source-relevance
   currentness remain distinguishable and behaviorally unchanged.
3. The duplicated three-value currentness vocabulary has one neutral authority
   without changing serialized values or approved public compatibility surface.
4. No readiness/context consumer substitutes pointer/source currentness for M3
   graph freshness.
5. No candidate consumer inherits graph invalidation semantics without an
   explicit approved candidate-Evidence contract.
6. F11-separated Evidence node identities remain independent.
7. Focused regression tests prove the graph-versus-currentness distinction,
   unchanged status strings, and absence of an import cycle.
8. No protected unrelated finding or reconstruction record changes.

## Approval Gate

No production implementation has started. User approval is required before an
implementation plan, code, tests, configuration, or public API changes are
made.
