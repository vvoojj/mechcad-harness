# P3 Human-in-the-Loop Triage

## Purpose and boundary

This is a decision-support artifact for the remaining P3 findings in the logic
duplication audit. It is not an implementation specification, does not approve
remediation, and does not alter accepted audit, architecture, test, wire/hash,
or reconstruction contracts.

## Baseline and safety record

- Branch: `master`.
- HEAD: `503e8572ecfad587dd57a9880deba025e13a18eb`.
- Required accepted material-remediation baseline: present exactly at HEAD.
- No production, test, audit/map, or reconstruction files were modified by this
  triage.
- Read context: `AGENTS.md`, `README.md`, `docs/README.md`, the duplication
  audit, ownership map, directly relevant source/tests, and only the cited
  M6B-4C, M10, M13-3, M13-3P, M13-4, and structural records.

Pre-existing dirty/untracked material, left untouched:

- Modified: `.coverage`; `.superpowers/sdd/progress.md`;
  `.superpowers/sdd/task-1-report.md`;
  `.superpowers/sdd/task-1-review-package.md`;
  `.superpowers/sdd/task-2-brief.md`;
  `.superpowers/sdd/task-2-report.md`;
  `.superpowers/sdd/task-3-brief.md`;
  `.superpowers/sdd/task-3-report.md`;
  `.superpowers/sdd/task-3-review-package.md`.
- Untracked Rotator V2/audit/planning material: the five
  `docs/audit/ROTATOR_V2_EPIC_01_*` records; `docs/superpowers/plans/2026-08-29-task-13-review-fixes.md`; `docs/superpowers/plans/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`; `docs/superpowers/specs/2026-09-09-rotator-v2-epic-01-physical-mechanism-and-candidate-evaluation.md`; `err.txt`; `projects/`; and the three `tests/unit/test_rotator_v2_epic_01_*.py` files.
- Untracked F13 candidate: `src/mechcad-harness/`. It was inspected but not
  deleted, moved, added, or otherwise modified.

## Evidence summary and preliminary dispositions

| Finding | Current evidence summary | Preliminary disposition | Production risk | Maintenance cost | Compatibility risk if changed | Decision uncertainty | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F9 | v1 single-axis and multi-joint v1/v2 paths are production-reachable; M13-3P freezes v1 bytes/hashes. | KEEP_INTENTIONAL | LOW | MEDIUM | HIGH | LOW | No remediation; document boundary only if an authorized documentation task occurs. |
| F10 | M6B-4C workflow/application has no production root caller; duplicate anchor map matches today. Eager annotation evaluation fails, while ordinary gateway import succeeds. | REMOVE_DEAD | LOW | MEDIUM | MEDIUM | RESOLVED | Design exact removal boundaries first; preserve the active anchor-map owner. |
| F12 | Fresh canonical multi-joint M10 service is composed and integration-tested, but has no `ProductionApplication` entrypoint or production caller. | FIX_NOW | LOW | MEDIUM | MEDIUM | RESOLVED | Design a thin explicit application boundary; preserve fresh candidate-free replay and M10-v2 contracts. |
| F13 | Nested untracked older `structural/solver.py` is non-importable because its ancestor contains a hyphen; tracked solver is sole authority. | DEFER_LOW_RISK | NONE | LOW | LOW | MEDIUM | Leave untouched until its owner classifies it. |
| F14 | Azimuth/Yagi compilers and legacy analyzer are test-only or unwired; the Yagi carrier stub is a required fail-closed guard. | KEEP_INTENTIONAL | NONE | LOW | MEDIUM | LOW | Preserve fixtures/guard; do not batch-delete legacy CAD material. |
| F16 | Ownership matching is permissive, dependency matching fail-closed, and engine `_segments` is traversal parsing rather than matching. | DEFER_LOW_RISK | LOW | LOW | MEDIUM | LOW | Do not abstract absent a demonstrated semantic change. |
| F17 | Legacy task models have no in-repository consumers other than package export, but module and exports are public Python surfaces. | KEEP_INTENTIONAL | NONE | LOW | HIGH | RESOLVED | Preserve module and public re-exports; no API retirement in this wave. |
| F19 | Two public enum classes have identical wire values but distinct identities; no current cross-family pass/conversion exists. | DEFER_LOW_RISK | LOW | LOW | MEDIUM | LOW | Retain separate typed families until a cross-family requirement exists. |
| F20 | Transform stacks agree for valid input but normalize at different boundaries; M10/M13-3P hashes and v1 goldens constrain changes. | KEEP_INTENTIONAL | LOW | LOW | HIGH | LOW | Preserve layer separation; output samples alone are insufficient for a merge. |
| F21 | This is five separate cases: one already centralized, three intentional independent/layered checks, and one private extraction candidate. | NEEDS_DEEPER_DESIGN | LOW | MEDIUM | HIGH | MEDIUM | Split into bounded work; do not authorize a broad structural refactor. |

### F9 evidence

- `ProductionApplication.analyze_assembly_kinematics()` executes the single-axis
  `CadKinematicSweepService` (`application.py:958-995`); candidate and canonical
  M10 home checks call it (`candidates/m10_evaluation.py:971-989`,
  `candidates/canonical_m10.py:760-785`).
- Public v1 multi-joint sweep is composed at `application.py:1060-1098`; v2 is
  used by candidate evaluation at `application.py:1177-1254` and
  `candidates/multi_joint_m10_evaluation.py:574-602`.
- The v1/v2 sweep orchestration duplicates execution structure
  (`multi_joint_collision_sweep.py:554-783`), but M13-3P requires literal v1
  JSON, hashes, parsing, and version values to remain unchanged
  (`tests/unit/test_m13_3p_legacy_goldens.py:281-452`).
- M10-3 explicitly kept the single-axis service unchanged, and M13-3P made the
  v1/v2 split an intentional compatibility contract.

### F10 evidence

- `ConstraintResolutionWorkflow.run()` is only test-reachable; neither workflow
  nor application service is composed by `ProductionApplication`
  (`constraint_resolution_workflow.py:64`, `application.py`). M6B-4C records
  this as `PRESENT_BUT_UNUSED` with no acceptance (`M6B-4C.md:5-13,30-33`).
- `constraint_resolution_application.py:193` references
  `ConstraintResolutionRecord` without importing it. Direct ordinary
  `from mechcad_harness.agents.gateway import AgentGateway` succeeded on this
  baseline, but accessing the method annotation raised `NameError`; the defect
  is deferred annotation evaluation, not an ordinary-import failure here.
- `_anchor_for` duplicates the current request materializer mapping
  (`constraint_resolution_application.py:223-232`, `constraint_requests.py:54,90`)
  without a proven behavior difference.

### F12 evidence

- The composed attribute is created at `application.py:637-640`; no `src/`
  caller exists. Integration/acceptance tests invoke it directly.
- The service is a real fresh canonical replay, building fresh v2 request/result
  bindings (`candidates/multi_joint_m10_bridge.py:470-544`), not a stub.
- M13-3 required candidate-free canonical verification, but does not establish
  a stable public application method; M13-4 tests intentionally called the
  composed seam. No record calls it reserved, deprecated, or intentionally
  unreachable.

### F13 evidence

- `git status --short` reports `?? src/mechcad-harness/`.
- Its nested `src/mechcad_harness/structural/solver.py` is outside an importable
  package path; production imports the tracked
  `src/mechcad_harness/structural/solver.py` (`application.py:110`,
  `structural/service.py:31`).
- The nested copy is divergent, including manifest/provenance details. Repository
  evidence cannot establish whether it is user work, generated residue, or an
  abandoned copy.

### F14 evidence

- `azimuth_mount_plate.py` compiler calls are test/live-fixture-only, but its
  domain types are imported by `engineering/values.py`; retain the module.
- `yagi_carrier_packaging.py` is a preliminary test fixture with no production
  caller.
- `yagi_carrier.py:242` deliberately raises for unavailable `through_slot`;
  accepted reconstruction requires this fail-closed boundary.
- `cad_analysis.py:153` result conversion serves the legacy analysis service;
  direct shape analysis is test-only. M10 production uses the distinct transient
  measurement provider.

### F16 evidence

- Ownership `_segments` strips slashes and permits loose segments
  (`changes/ownership.py:30-43`).
- Dependency `path_matches` requires strict non-root absolute paths and rejects
  empty segments/`~` (`dependency/graph.py:70-85`).
- Engine `_segments` validates executable operation paths and supports traversal;
  it is not a wildcard matcher (`changes/engine.py:30-105`).
- All are wired, but current configs use conventional valid patterns and no
  production divergence is proven.

### F17 evidence

- `models/task.py` only contains M0 `TaskStatus`, `AgentTask`, and `AgentResult`.
  Current run and agent result authorities are `runs/models.py` and
  `agents/models.py`.
- There are no in-repository imports of the legacy types beyond
  `models/__init__.py`; nevertheless `models.__init__` eagerly imports and
  publicly re-exports all three (`models/__init__.py:10,235-236,397`).
- Removing the re-exports and removing the direct `models.task` import path are
  distinct compatibility changes.

### F19 evidence

- Both enums expose identical five strings (`physical_pair_policy.py:44-49`,
  `canonical_m10.py:105-110`), but all meaningful branches use identity tests.
- Physical flows use `PhysicalPairClassification`; canonical single-axis M10
  derives `CanonicalM10PairClassification` directly. No production source
  converts or cross-passes them.
- Both classes are public exports, so a shared enum changes Python type identity
  even if scalar serialization remains unchanged.

### F20 evidence

- Valid transform composition has the same order and quaternion rotation formula
  across stacks: `t1 + rotate(q1, t2)` and `q1*q2`
  (`multi_joint_kinematics.py:122-141`, `models/quaternion.py:44-70`,
  `models/generated_placement.py:620-629`).
- `CadRigidTransform` normalizes/canonicalizes at model construction; generated
  placement helpers normalize at helper boundaries. Near-zero/non-finite failure
  contracts and `rigid_transform_agrees` tolerance are separate contracts.
- No source labels a handedness convention. Tests establish directional outcomes,
  not a formal cross-layer coordinate-convention contract.

### F21 evidence and split

| Sub-finding | Determination | Preliminary treatment |
| --- | --- | --- |
| Backend provenance construction | Direct FreeCAD construction carries observed runtime version; helper supplies declared identity defaults. | Intentional adapter variant. |
| Mesh-input hash | A single `structural/models.py:mesh_input_hash` is used across execution, interpretation, and Evidence verification. | Already remediated; no P3 implementation remains. |
| Structural provenance and artifact reads | Result interpreter and Evidence verifier validate distinct execution versus durable-Evidence trust stages. | Intentional independent verifiers. |
| Application analytical observations | Two public flows rebuild the same trusted observation data at `application.py:1694-1747` and `:1914-2009`. | Candidate for a private behavior-preserving builder only. |
| M11 handoff revalidation | Build, assess, and promotion verification check different bindings and retain eligibility-only semantics. | Intentional layered revalidation. |

## Decision cards

### F9 — Versioned M10 sweep compatibility

CURRENT_STATE: Single-axis sweep and multi-joint v1/v2 sweep paths are production-reachable. The v1/v2 multi-joint branches duplicate orchestration, but are distinct typed/versioned contracts.
PRODUCTION_REACHABILITY: Yes.
COMPATIBILITY_CONSTRAINT: M13-3P freezes v1 wire bytes, hashes, FK behavior, and legacy public entrypoints.
PROVEN_DEFECT: No proven behavioral defect.
COST_OF_LEAVING: About 130 lines of duplicated orchestration and future synchronized-maintenance burden.
COST_OF_CHANGING: High risk of changing v1 bytes, hashes, exception behavior, or v1/v2 isolation.
RECOMMENDATION: KEEP_INTENTIONAL.
ALTERNATIVES: A future private extraction only after byte-for-byte v1 differential proof; removal is not supported.
HUMAN_DECISION_REQUIRED: No.
QUESTION_TO_USER: Do you approve retaining F9 as intentional versioned compatibility duplication with no remediation wave?

### F10 — Unwired constraint-resolution workflow

CURRENT_STATE: M6B-4C is internally tested but has no accepted production caller; its application service duplicates the active anchor map.
PRODUCTION_REACHABILITY: No production workflow caller; ordinary gateway import succeeds, but deferred evaluation of one missing annotation raises `NameError`.
COMPATIBILITY_CONSTRAINT: Historical record establishes no current accepted workflow contract; public `agents` exports remain a Python compatibility surface.
PROVEN_DEFECT: `ConstraintResolutionRecord` is absent from the application module imports, causing annotation reflection/introspection failure.
COST_OF_LEAVING: Latent annotation failure and two anchor maps can drift; dead subsystem ownership remains ambiguous.
COST_OF_CHANGING: Keeping it requires a supported-contract decision and focused repair; removing it can break external imports and requires separate anchor-map handling.
RECOMMENDATION: NEEDS_HUMAN_DECISION.
ALTERNATIVES: Retire the unaccepted workflow and its local map; or formally retain it, repair annotation behavior, and make the request materializer the anchor-map owner.
HUMAN_DECISION_REQUIRED: Yes.
QUESTION_TO_USER: Should the M6B-4C constraint-resolution workflow be retired as unused, or retained as a supported subsystem that must be repaired and given one anchor-map owner?

### F12 — Canonical multi-joint M10 invocation surface

CURRENT_STATE: A real canonical replay service is composed and integration-tested, but has no production-root caller or stable public wrapper.
PRODUCTION_REACHABILITY: Composed only; production-root unreachable.
COMPATIBILITY_CONSTRAINT: It consumes protected canonical-obligation and M10-v2 request/result contracts; it must not auto-run during promotion.
PROVEN_DEFECT: No corruption defect; the product invocation surface is ambiguous.
COST_OF_LEAVING: Capability remains an unprotected test/composition seam and may be overstated as a supported production feature.
COST_OF_CHANGING: A public wrapper defines external API scope; deletion conflicts with the fresh canonical replay contract.
RECOMMENDATION: NEEDS_HUMAN_DECISION.
ALTERNATIVES: Define it as an acceptance-only seam and protect/document it; or add a narrow typed `ProductionApplication` entrypoint without changing M10/Evidence semantics.
HUMAN_DECISION_REQUIRED: Yes.
QUESTION_TO_USER: Should canonical multi-joint M10 replay be a supported `ProductionApplication` capability, or remain an acceptance-only composed seam?

### F13 — Untracked nested solver copy

CURRENT_STATE: An untracked, divergent older solver copy sits under a non-importable hyphenated path; the tracked solver remains the sole production authority.
PRODUCTION_REACHABILITY: No.
COMPATIBILITY_CONSTRAINT: None from production code; user ownership of untracked material is unknown.
PROVEN_DEFECT: No runtime defect; it can mislead future editors.
COST_OF_LEAVING: Low housekeeping confusion.
COST_OF_CHANGING: Deleting or moving unknown untracked work could destroy user material.
RECOMMENDATION: DEFER_LOW_RISK.
ALTERNATIVES: Explicitly authorized owner cleanup can remove or relocate it later; do not add compatibility code.
HUMAN_DECISION_REQUIRED: No, unless cleanup is requested.
QUESTION_TO_USER: Should the untracked `src/mechcad-harness/` tree remain untouched until its owner explicitly authorizes cleanup?

### F14 — Test-only and fail-closed legacy CAD

CURRENT_STATE: The azimuth and packaging compilers are test/preliminary fixtures; `yagi_carrier` is a required raising guard; legacy clearance analysis is unwired from production M10.
PRODUCTION_REACHABILITY: No for compilers/direct analyzer; some supporting types and result conversion retain limited legacy use.
COMPATIBILITY_CONSTRAINT: The raising Yagi guard is an accepted capability boundary; fixture imports/tests may be external-facing development support.
PROVEN_DEFECT: No proven defect.
COST_OF_LEAVING: Low, primarily discoverability burden.
COST_OF_CHANGING: Removing broadly can erase useful fixtures or violate the fail-closed contract.
RECOMMENDATION: KEEP_INTENTIONAL.
ALTERNATIVES: Separately retire a specific fixture only with its tests/examples and an explicit support decision.
HUMAN_DECISION_REQUIRED: No.
QUESTION_TO_USER: Do you approve retaining F14's test fixtures and fail-closed Yagi guard without a consolidation/removal wave?

### F16 — Path matching and parsing variants

CURRENT_STATE: Three similarly named helpers serve authorization matching, dependency-config matching, and executable-path parsing.
PRODUCTION_REACHABILITY: Yes, for all three roles.
COMPATIBILITY_CONSTRAINT: Ownership accepts looser paths; dependency configuration fails closed; engine errors and traversal behavior are part of mutation safety.
PROVEN_DEFECT: No production divergence is proven.
COST_OF_LEAVING: Low repetition and a possible future drift surface.
COST_OF_CHANGING: A shared validator can silently tighten accepted ownership paths or change dependency/engine exception types.
RECOMMENDATION: DEFER_LOW_RISK.
ALTERNATIVES: Extract only a narrowly specified prefix predicate after an actual shared semantic requirement emerges.
HUMAN_DECISION_REQUIRED: No.
QUESTION_TO_USER: Do you approve deferring F16 rather than abstracting intentionally different validation contracts?

### F17 — Legacy task-model public exports

CURRENT_STATE: Legacy M0 task classes are dead inside the repository but eagerly imported and re-exported from `mechcad_harness.models`.
PRODUCTION_REACHABILITY: No internal consumer beyond package export.
COMPATIBILITY_CONSTRAINT: `mechcad_harness.models.AgentTask`, `AgentResult`, and `TaskStatus`, plus direct `models.task`, may have external users.
PROVEN_DEFECT: No runtime defect.
COST_OF_LEAVING: Low dead API and naming ambiguity with current run/agent types.
COST_OF_CHANGING: Export removal and module removal are separate breaking Python API changes.
RECOMMENDATION: NEEDS_HUMAN_DECISION.
ALTERNATIVES: Preserve all; retire only aggregate exports while keeping direct module compatibility; or intentionally remove both after a public API retirement decision.
HUMAN_DECISION_REQUIRED: Yes.
QUESTION_TO_USER: Which public API policy should govern F17: retain all legacy task symbols, retire only `models` re-exports, or remove the module and exports as a deliberate breaking change?

### F19 — Pair-classification enum identities

CURRENT_STATE: Physical and canonical-M10 enums serialize five identical strings but intentionally remain distinct Python types with identity-sensitive branches.
PRODUCTION_REACHABILITY: Yes, in separate flows; no cross-family pass exists.
COMPATIBILITY_CONSTRAINT: Both class names are public; type identity can matter to external callers even when wire values are unchanged.
PROVEN_DEFECT: No live cross-pass or divergence is proven.
COST_OF_LEAVING: Low future integration hazard if callers cross types without validation.
COST_OF_CHANGING: Shared-enum migration changes public Python identity and requires a compatibility strategy.
RECOMMENDATION: DEFER_LOW_RISK.
ALTERNATIVES: Define an explicit conversion boundary if a cross-family use case appears; do not merge solely on matching values.
HUMAN_DECISION_REQUIRED: No.
QUESTION_TO_USER: Do you approve deferring F19 until a real cross-family pair-classification requirement justifies a public API migration?

### F20 — Quaternion and transform layer separation

CURRENT_STATE: Kinematic, model, and placement layers use mathematically aligned operations for valid input but normalize and reject invalid input at different boundaries.
PRODUCTION_REACHABILITY: Yes.
COMPATIBILITY_CONSTRAINT: Transform outputs feed M10 placement/result hashes; M13-3P v1 goldens protect byte-level behavior.
PROVEN_DEFECT: No proven behavioral divergence; sample output agreement is not sufficient proof of full semantic equivalence.
COST_OF_LEAVING: Low duplicate arithmetic maintenance.
COST_OF_CHANGING: High risk of coupling model validation with raw kinematic computation or changing normalization/failure/hash behavior.
RECOMMENDATION: KEEP_INTENTIONAL.
ALTERNATIVES: Consider a shared primitive only after a formal convention and exhaustive differential contract exists.
HUMAN_DECISION_REQUIRED: No.
QUESTION_TO_USER: Do you approve retaining F20's separate transform layers pending a formally specified normalization and coordinate-convention contract?

### F21 — Mixed structural verification candidates

CURRENT_STATE: F21 combines already-centralized hashing, intentional independent artifact/provenance verification, layered M11 handoff checks, and one duplicated observation-construction block.
PRODUCTION_REACHABILITY: Yes for all structural and handoff boundaries.
COMPATIBILITY_CONSTRAINT: Backend provenance, artifacts, structural Evidence, M11 handoff bindings, and their hashes are protected persisted contracts.
PROVEN_DEFECT: Only the two analytical-observation construction blocks are mechanically duplicate; no authority conflict is proven for the other sub-findings.
COST_OF_LEAVING: Medium localized maintenance cost in the observation block; low elsewhere.
COST_OF_CHANGING: A broad helper refactor can collapse independent verification and weaken defense in depth.
RECOMMENDATION: NEEDS_DEEPER_DESIGN.
ALTERNATIVES: Close the already-remediated hash subfinding, retain independent verifiers/revalidation, then design a private observation builder with strict preserved trust and error boundaries.
HUMAN_DECISION_REQUIRED: No immediate product decision; a design review is required before any change.
QUESTION_TO_USER: Do you approve scoping F21 to a later design review limited to the duplicated analytical-observation construction, while retaining independent structural verification and M11 handoff checks?

## Human-decision buckets

### A. NO HUMAN DECISION NEEDED

- F9: retain intentional versioned compatibility duplication.
- F13: defer and leave unknown untracked material untouched.
- F14: retain fixtures and required fail-closed guard.
- F16: defer; contracts differ.
- F19: defer; no cross-family user exists.
- F20: retain layer separation.

### B. HUMAN DECISION REQUIRED NOW

- None. The F10, F12, F17, and F21 decisions below resolve the identified
  product/architecture/API gates for this P3 triage scope.

### C. DEEPER DESIGN REQUIRED BEFORE IMPLEMENTATION

- F12: specify the thin explicit `ProductionApplication` invocation boundary.
- F10: specify exact M6B-4C removal boundaries while preserving the active
  anchor-map owner.
- F21: specify only the private analytical-observation extraction while
  preserving independent verifiers.

## Recorded HITL decisions

The following decisions were supplied by the human product/architecture owner
after the initial triage. They authorize design/spec work only, not
implementation.

| Finding | Decision | Binding constraints |
| --- | --- | --- |
| F12 | `SUPPORTED_APPLICATION_CAPABILITY` | Explicit invocation only; never auto-run during promotion; delegate to the existing canonical multi-joint verification service; retain fresh candidate-free replay and existing M10-v2 request/result/hash contracts; do not create a second verifier. |
| F10 | `RETIRE` | Retire the unused/unaccepted M6B-4C workflow; preserve still-authoritative shared behavior, including the active constraint-request anchor-map owner; design exact removal boundaries before deletion. |
| F17 | `KEEP` | Preserve `models.task` and all existing public re-exports; no API retirement in this wave. |
| F21 | `DESIGN` | Scope design strictly to duplicated analytical-observation construction; retain independent structural provenance/artifact verification and M11 handoff revalidation. |

## Recommended design/planning order

1. F12 design/spec: define the one explicit application method, its typed input
   and return boundary, and non-goals. It may delegate only to the existing
   composed service.
2. F10 removal design/spec: identify all package exports, test-only callers,
   durable records, and workflow-local code to remove; retain
   `ConstraintRequestMaterializer` as anchor-map authority.
3. F21 design/spec: compare the two analytical-observation call sites and state
   the exact private builder contract, preserving each caller's independent
   reload/verification and error boundary.
4. F12, F10, and F21 implementation plans: prepare only after each design/spec
   is accepted. F17 has no design or implementation work in this wave.

## Dependency and conflict map

- F9 and F20 overlap `kinematic_sweep.py`/motion transform behavior. They must
  not execute concurrently; F9's frozen v1 contract is a regression gate for
  any F20 work.
- F10 and F17 overlap package import/export cleanup. They must not execute
  concurrently if the chosen F10 disposition touches `agents/__init__.py` or
  shared model import behavior.
- F12 and F21 overlap application composition and canonical verification/Evidence
  trust boundaries. Do not execute concurrently.
- F10 and F14 both touch legacy agent/CAD fixture support only at broad cleanup
  policy level; no direct source-file conflict is currently known.
- F13 has no source overlap because it is untracked and must remain untouched.
- F16 and F17 have no direct overlap and can proceed independently after their
  respective decisions.
- F19 has no source overlap with F9/F20 and can remain deferred independently.

## Proposed safe design/planning waves

No implementation is authorized by these waves.

| Wave | Scope | Parallelization | Completion gate |
| --- | --- | --- | --- |
| D1 | F12 application-boundary design/spec | Run alone. It overlaps F21 at application composition and canonical verification boundaries. | Accepted design explicitly preserves delegation-only behavior, explicit invocation, candidate-free freshness, and M10-v2 wire/hash contracts. |
| D2 | F10 retirement design/spec | May run in parallel with D1 because agent-workflow removal does not overlap application canonical-M10 source. | Exact removal/retention inventory proves that active anchor mapping remains owned by `ConstraintRequestMaterializer`; no deletion occurs in this wave. |
| D3 | F21 analytical-observation design/spec | Run after D1, not concurrently. | Design names one private builder only and explicitly excludes provenance/artifact verifier and M11 handoff consolidation. |
| P1 | Separate implementation plans for accepted D1, D2, and D3 designs | F10 plan may proceed independently of F12/F21. F12 and F21 remain sequential. | Each plan preserves its finding's protected contracts and defines focused regression gates. |
| Deferred | F9, F13, F14, F16, F17, F19, F20 | No work. | Re-open only on an authorized requirement/support-policy change. |

## Triage conclusion

The recorded decisions authorize design/spec work for F12, F10, and F21 only.
F17 remains preserved without work. F9, F13, F14, F16, F19, and F20 remain
intentional or deferred. No P3 implementation is authorized by this artifact.
