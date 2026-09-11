# MechCAD Logic Duplication & Capability Ownership Audit

- **Audit type:** repository-wide semantic / architectural / authority duplication
  audit using the completed Historical Reconstruction as the temporal map.
- **Baseline:** product endpoint M13-4 at
  `185a304796c17793519fb5f01dbf80cca73ab51e`; reconstruction synthesis
  `0cbb70e64c2efdc021f15d341bc043b574ff552b` (both verified locally against the
  reconstruction ledger).
- **Audit scope:** `src/mechcad_harness/**` tracked production code, current
  composition root, and applicable reconstruction/architecture/audit records.
- **Not in scope / not modified:** `src/**`, `tests/**`,
  `docs/reconstruction/**`, `docs/superpowers/**`, `README.md`, `AGENTS.md`.
- **This is audit-only.** No production code, tests, specs, or reconstruction
  records were changed. Remediation is explicitly out of scope.

Companion artifact: [`MECHCAD_CAPABILITY_OWNERSHIP_MAP.md`](MECHCAD_CAPABILITY_OWNERSHIP_MAP.md).

---

## 1. Executive Verdict

| Metric | Value |
| --- | --- |
| TOTAL_CAPABILITIES_REVIEWED | 60 |
| DUPLICATION_CANDIDATES | 24 |
| CONFIRMED_MATERIAL_DUPLICATIONS (P0–P2) | 9 (2×P1, 7×P2) |
| AUTHORITY_CONFLICTS | 3 (all latent / bounded, none P0) |
| LEGACY_RESIDUES | 7 (P3) |
| LEGITIMATE_LAYERING_CASES | 13 |
| RECONSTRUCTION_DISCREPANCY_CANDIDATES | 0 |

**OVERALL_ARCHITECTURAL_DUPLICATION_RISK: MEDIUM**

The reconstructed evolution shows a generally disciplined pattern: later
milestones extended existing authorities far more often than they replaced them.
The M13-2 generated-part capability correctly extended the single FreeCAD
backend; the M13-3P M10-v2 work deliberately preserved v1 wire/hash semantics;
the M13-4E promotion-Evidence family is a spec-mandated additive design rather
than a re-implementation. Those are documented here as **rejected false
positives**.

The genuine duplication that accumulated is concentrated in three patterns:

1. **Re-implemented canonical serialization / identity hashing** across ~20
   modules with at least three divergent variants (`ensure_ascii` and
   `default=str` differences) — the M0/M2 revision-hashing authority has no
   single consumer surface (F2).
2. **Copy-forward verification between milestone stages** — M12-5 copied the
   M12-4 M10 result contracts into the canonical verifier and the copies have
   already diverged (F1, F7); M11-5 copied and re-derived M11-2 hashes and
   artifact checks (F4, F12).
3. **Parallel "currentness/freshness" and identity constants** introduced by
   later milestones instead of composing the earlier M3/M7A authorities
   (F3, F5, F6, F11).

No P0 was confirmed: no finding shows two authorities that can currently write
incompatible *canonical* or *accepted* results through the production
composition. The highest-risk items are latent identity drift and already-drifted
stage validators.

---

## 2. Method

1. **Verified baseline facts first** from Git and the reconstruction ledger:
   M13-4 `185a304`, synthesis `0cbb70e`, and the documented milestone→commit map.
2. **Used Historical Reconstruction as the temporal authority**:
   `PROJECT_HISTORY.md`, `CAPABILITY_EVOLUTION.md`, `MILESTONE_LEDGER.md`,
   `UNRESOLVED_GAPS.md`, and relevant `milestones/**` records supplied *when*
   each capability first appeared and *why* a later implementation existed.
   Reconstruction was treated as frozen; no record was edited.
3. **Built the capability ownership map** (companion document) from the
   reconstruction plus direct code wiring.
4. **Traced current wiring from the actual composition root**
   (`application.py:ProductionApplication.create`, line 775) rather than
   assuming a class is active because it exists.
5. **Searched with multiple signals**: symbol references, import graph,
   call sites, Protocol/interface implementations, Pydantic validator bodies,
   `git log -S`/`git log --` for introduction commits, and cross-checked
   separately-authored tests.
6. **Applied the task's duplication taxonomy** and, for every candidate,
   explicitly asked *"should these implementations share one authority?"*
7. **Independently re-verified every P1/P2 claim** by reading the cited code
   (see §16 for the reviewer pass), then wrote this report.

Historical attribution below is by milestone and commit, never by author.

---

## 3. Capability Ownership Map

The full 60-row matrix is in
[`MECHCAD_CAPABILITY_OWNERSHIP_MAP.md`](MECHCAD_CAPABILITY_OWNERSHIP_MAP.md).
Highest-traffic authority boundaries:

| Capability | Current authoritative owner | Wiring |
| --- | --- | --- |
| Canonical state + revisions | `state/manager.py`, `models/design.py` | WIRED |
| Revision hashing | `state/hashing.py:canonical_json` | WIRED (but re-implemented ~20×) |
| ChangeSet mutation | `changes/engine.py` | WIRED (sole canonical-revision caller) |
| Invalidation | `dependency/graph.py:impact` | WIRED |
| Evidence freshness | `dependency/storage.py` | WIRED |
| Exact transient measurement | `transient_freecad_measurement.py` | WIRED |
| FK / collision / continuous proof | `multi_joint_*` (v1 + v2) | WIRED |
| Structural geometry/mesh/solver/results | `structural/*` | WIRED |
| Candidate evaluation / promotion | `candidates/*` | WIRED |
| Production composition | `application.py:ProductionApplication` | WIRED |

Confirmed invariants (negative findings, important):
- **Single canonical-revision writer.** Only `state/manager.py` writes
  `revisions/` and `current.json`; `changes/engine.py` is the only production
  caller of `create_revision`; `changes/provenance.py` writes sidecar records,
  not canonical state. No second writer exists.
- **Single invalidation engine.** `DependencyGraph.impact` computes impact;
  storage persists it; no competing engine.
- **Single FRD/DAT parser.** Structural result parsing is not duplicated in
  candidate code (`candidates/**` contains no FEA output parser).
- **Single FreeCAD primitive realization.** M13-2 added cylinder/bore/plate
  operations to the one backend rather than a second generator.

---

## 4. Confirmed Material Findings

### F1 — Candidate and canonical M10 continuous-proof result contracts duplicated and already diverged

- **SEVERITY:** P1
- **CAPABILITY:** multi-joint / single-axis M10 evaluation result validation
- **ORIGINAL_MILESTONE:** M12-4 (`bae65cc`) — `candidates/m10_evaluation.py`
- **SECONDARY_MILESTONE:** M12-5 (`161986b`) — `candidates/canonical_m10.py`
- **ORIGINAL_IMPLEMENTATION:** `m10_evaluation.py:1095-1218`
  (`_validate_continuous_result`, `_validate_home_result`,
  `_induced_pair_assembly`)
- **SECOND_IMPLEMENTATION:** `canonical_m10.py:1121-1241` (near-identical
  functions under `-canonical-` naming)
- **CURRENT_WIRING:** both WIRED. Candidate:
  `application.py:505`/`2423`. Canonical: `application.py:636` →
  `candidates/promotion.py:3337`.
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION (validation contract copied across
  trust stages)
- **WHY_THIS_IS_DUPLICATION:** the same M10 result contract is enforced by two
  independently-maintained validators. Verified divergence:
  - canonical requires `request.source_assembly_id == assembly.assembly_id`
    (`canonical_m10.py:1140`); the candidate validator compares only the
    assembly *hash* (`m10_evaluation.py:1095`).
  - the candidate validator checks collision-witness classification
    (`m10_evaluation.py:1139-1143`); the canonical validator does not.
  - M10 collision-witness/v1 disposition models and pair-classification model
    families are duplicated (`m10_evaluation.py:98-763` vs
    `canonical_m10.py:103-576`).
- **HISTORICAL_CAUSE:** M12-5 needed a *fresh post-promotion* canonical
  verification. The M12-5 plan explicitly instructed not to extract candidate
  helpers unless a focused test required it
  (`docs/superpowers/plans/2026-08-29-m12-5-promotion-canonical-rebind-m11-handoff.md:305`),
  so the candidate validators were copy-forwarded. The independent-verifier
  role is legitimate, but the code was not kept contract-synchronized.
- **BEHAVIORAL_DIFFERENCE:** the two can return different verdicts for the same
  semantic result (canonical stricter on assembly identity; candidate stricter
  on witness classification). Because they run at different stages this is
  currently fail-closed, not inconsistent-canonical, which is why it is P1 not
  P0.
- **AUTHORITY_RISK:** a future change to one validator silently changes only one
  stage's trust contract. Reviewers can reasonably disagree which is
  authoritative.
- **RECOMMENDED_DIRECTION:** CANONICALIZE_ON_EXISTING_AUTHORITY — introduce one
  shared M10 result-contract validator parameterized by stage, or explicitly
  document the canonical validator as the sole authority and have the candidate
  path consume it.
- **CONFIDENCE:** HIGH (code verified directly).

### F2 — Canonical JSON / content-identity serialization re-implemented ~20× with divergent variants

- **SEVERITY:** P1
- **CAPABILITY:** revision/content identity hashing (canonical serialization)
- **ORIGINAL_MILESTONE:** M0/M2 (`37f3ff3`) —
  `state/hashing.py:canonical_json`
- **SECONDARY_MILESTONES (representative):** M6B-4A/4C (`3c7c708`/`4468a62`,
  `default=str` variant), M7B/M7C (`3f7bbc7`/`9ab9e48`, yagi trio), M10
  (`89b1d75`, motion hashes), M11-2/11-5 (`682300b`/`07950cd`, structural
  `_stable_json`/`_stable_hash`), M13-3 (`ca294e0`, pair policy / verification)
- **ORIGINAL_IMPLEMENTATION:** `state/hashing.py:canonical_json`
  (`ensure_ascii=False, sort_keys=True, separators=(",",":")`)
- **SECOND_IMPLEMENTATION (examples):**
  - `models/physical_pair_policy.py:13` `_canonical_json` — byte-identical copy
    (verified).
  - `models/multi_joint_verification.py:13` `_hash_payload` — byte-identical.
  - `structural/models.py:651` `_stable_json` and
    `structural/evidence_models.py:207` `_stable_hash` — **omit
    `ensure_ascii=False`** (defaults to `ensure_ascii=True`).
  - `changes/provenance.py:11` `_canonical` and
    `agents/constraint_resolution.py:222` `_canonical_json` — use `default=str`.
  - Inline `json.dumps(sort_keys=True, separators=(",",":"))` in
    `cad_assembly.py`, `cad_program.py`, `imported_component.py`,
    `multi_joint_kinematics.py`, `multi_joint_continuous_clearance.py`,
    `models/physical_mechanism.py`, `candidates/canonical_m10.py`, and others.
- **CURRENT_WIRING:** WIRED. Many hashes are computed inside Pydantic
  validators and cross-module identity checks.
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION / AUTHORITY_DUPLICATION
- **WHY_THIS_IS_DUPLICATION:** the byte-level canonicalization that underpins
  revision/content identity has no single implementation. Two logically equal
  payloads containing non-ASCII text hash to **different** values depending on
  which module serialized them; the `default=str` variant additionally accepts
  values the shared serializer rejects.
- **HISTORICAL_CAUSE:** each milestone authored self-contained modules and
  copied a small `json.dumps` helper for local hashing rather than importing the
  M2 shared function. Introduced incrementally from M2 onward.
- **BEHAVIORAL_DIFFERENCE:** currently equivalent for ASCII-only payloads;
  divergent for non-ASCII strings and for non-JSON-coercible values.
- **AUTHORITY_RISK:** cross-module hash comparisons rely on accidental
  byte-equality. A future payload containing non-ASCII text, or a change to one
  variant, breaks identity checks in a way that is hard to localize.
- **RECOMMENDED_DIRECTION:** INTRODUCE_SHARED_CORE — route all content-identity
  hashing through `state.hashing.canonical_json` (which already accepts plain
  dicts) and delete the local variants.
- **CONFIDENCE:** HIGH (variants verified directly).

### F3 — Three currentness / freshness implementations; two enums byte-identical

- **SEVERITY:** P2
- **CAPABILITY:** Evidence freshness / currentness
- **ORIGINAL_MILESTONE:** M3 (`df584f0`) —
  `dependency/storage.py:get_evidence_freshness`
- **SECONDARY_MILESTONES:** M11-5 (`07950cd`) —
  `structural/evidence.py:StructuralEvidenceCurrentness` +
  `structural/evidence_service.py:currentness`; M12 (`28ac193`) —
  `candidates/services.py:CandidateCurrentness`
- **CURRENT_WIRING:** all WIRED (`application.py:1647`, `2114`, `2317`;
  context building).
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION (enum and comparison logic)
- **WHY_THIS_IS_DUPLICATION:** `StructuralEvidenceCurrentness`
  (`structural/evidence.py:58`) and `CandidateCurrentness`
  (`candidates/services.py:19`) are **byte-identical enums**
  (`current` / `stale_relative_to_current_state` / `currentness_unavailable`)
  and independently re-implement "compare bound `(revision, state_hash)` to the
  current pointer". The M3 graph/invalidation freshness is a third, distinct
  notion.
- **HISTORICAL_CAUSE:** M11-5 introduced a state-hash-equality notion for
  structural Evidence; M12 copied the enum and comparison verbatim instead of
  composing M3 or sharing a contract.
- **BEHAVIORAL_DIFFERENCE:** M3 freshness accounts for transitive invalidation;
  the two newer implementations only compare the current pointer. A record can
  be `CURRENT` by pointer while a dependency invalidation marks its node stale.
- **AUTHORITY_RISK:** status-string contract changes must be made in three
  places; two are already verbatim copies. Precedence between "freshness" and
  "currentness" is undocumented.
- **RECOMMENDED_DIRECTION:** DOCUMENT_AUTHORITY_BOUNDARY, then
  CANONICALIZE_ON_EXISTING_AUTHORITY — share the enum and have the state-hash
  check consume M3 freshness where applicable.
- **CONFIDENCE:** HIGH.

### F4 — Structural mesh-spec/input hashing implemented four (plus two) ways, cross-compared

- **SEVERITY:** P2
- **CAPABILITY:** structural mesh specification / mesh input identity
- **ORIGINAL_MILESTONE:** M11-2 (`682300b`)
- **SECONDARY_MILESTONE:** M11-5 (`07950cd`)
- **ORIGINAL_IMPLEMENTATION:** `structural/service.py:42`,
  `structural/validation.py:663`, `structural/results.py:1107`
  (`_mesh_specification_hash`); `structural/models.py:698` (`mesh_input_hash`)
- **SECOND_IMPLEMENTATION:** `structural/evidence.py:464`
  (`structural_mesh_specification_hash`, strips volatile keys) and
  `structural/evidence_service.py:1515` (`_mesh_input_hash`, inline rebuild)
- **CURRENT_WIRING:** all WIRED; the values are directly cross-compared
  (service writes, validation/evidence/results verify).
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION / ALGORITHM_DUPLICATION
- **WHY_THIS_IS_DUPLICATION:** four independently defined mesh-spec hashes over
  the same `MeshSpecification`, one of which applies a volatile-key filter the
  others do not. They agree today only because `MeshSpecification` currently has
  no volatile field.
- **HISTORICAL_CAUSE:** M11-5's durable-Evidence layer re-derived the hash
  rather than importing the M11-2 helper.
- **BEHAVIORAL_DIFFERENCE:** none today; would diverge the moment a volatile
  field is added to the mesh specification.
- **AUTHORITY_RISK:** adding a correctly-named volatile field makes Evidence
  verification fail against the service-written hash.
- **RECOMMENDED_DIRECTION:** CANONICALIZE_ON_EXISTING_AUTHORITY.
- **CONFIDENCE:** HIGH.

### F5 — FreeCAD runtime identity literal duplicated across backend and structural runtime

- **SEVERITY:** P2
- **CAPABILITY:** FreeCAD runtime / backend identity
- **ORIGINAL_MILESTONE:** M7A (`19f77a3`) —
  `backends/freecad.py:FREECAD_BACKEND_VERSION = "mechcad-freecad@2.1"`
- **SECONDARY_MILESTONE:** M11-2 (`682300b`) —
  `structural/runtime.py:FREECAD_IDENTITY.adapter_version = "mechcad-freecad@2.1"`
- **CURRENT_WIRING:** WIRED. Structural provenance verification compares STEP
  `backend_provenance` against `FREECAD_IDENTITY`
  (`structural/results.py`, `structural/evidence_service.py`).
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION
- **WHY_THIS_IS_DUPLICATION:** the same adapter-version literal is asserted in
  two packages and must stay equal for M11 verification to pass.
- **HISTORICAL_CAUSE:** M11 introduced its own runtime-discovery identity
  constant instead of importing the backend's.
- **BEHAVIORAL_DIFFERENCE:** equivalent today; a unilateral bump makes all M11
  geometry provenance verification fail closed.
- **AUTHORITY_RISK:** silent, total M11 provenance-verification breakage after a
  version bump in one location.
- **RECOMMENDED_DIRECTION:** CANONICALIZE_ON_EXISTING_AUTHORITY — single shared
  identity constant.
- **CONFIDENCE:** HIGH.

### F6 — `physical_kinematic_root_hash` defined twice and cross-compared

- **SEVERITY:** P2
- **CAPABILITY:** physical kinematic root identity
- **ORIGINAL_MILESTONE:** M13-3 (`ca294e0`) — both copies introduced in the same
  milestone
- **ORIGINAL_IMPLEMENTATION:** `models/physical_mechanism.py:35`
- **SECOND_IMPLEMENTATION:** `candidates/models.py:58`
- **CURRENT_WIRING:** both WIRED; the candidate bridge explicitly compares them
  (`candidates/multi_joint_m10_bridge.py:2397`, `:2564`).
- **DUPLICATION_TYPE:** AUTHORITY_DUPLICATION (latent)
- **WHY_THIS_IS_DUPLICATION:** two definitions of the same identity hash,
  consumed by code that asserts their equality.
- **HISTORICAL_CAUSE:** same-commit candidate/canonical split re-declared the
  function instead of importing it.
- **BEHAVIORAL_DIFFERENCE:** none today (same payload); the candidate version
  delegates to `_hash_payload`, the canonical version inlines `json.dumps` with
  `ensure_ascii=False`, so they diverge if either serializer changes.
- **AUTHORITY_RISK:** identity mismatch / false bridge rejection.
- **RECOMMENDED_DIRECTION:** CANONICALIZE_ON_EXISTING_AUTHORITY (import the
  model-layer function).
- **CONFIDENCE:** HIGH.

### F7 — Candidate vs canonical generated/bounded CAD dimension resolution: alias precedence already differs

- **SEVERITY:** P2
- **CAPABILITY:** candidate CAD realization vs canonical CAD realization
- **ORIGINAL_MILESTONE:** M12-4 (`bae65cc`) —
  `candidates/cad_realization.py:_DIMENSION_ALIASES`
- **SECONDARY_MILESTONE:** M12-5 (`161986b`) —
  `candidates/canonical_cad.py:_DIMENSION_ALIASES`; extended by M13-2
  (`664ec3b`) in both files
- **ORIGINAL_IMPLEMENTATION:** `cad_realization.py:105`
  (`"length_mm": ("geometry.length_mm", "plate_length_mm", "length_mm")`)
- **SECOND_IMPLEMENTATION:** `canonical_cad.py:42`
  (`"length_mm": ("length_mm", "geometry.length_mm", "plate_length_mm")`)
- **CURRENT_WIRING:** both WIRED; candidate via `application.py:500`/`2136`,
  canonical via `application.py:633` → `candidates/promotion.py:3273`.
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION with latent AUTHORITY_CONFLICT
- **WHY_THIS_IS_DUPLICATION:** the same bounded-representation fallback and
  dimension-alias resolution is implemented twice with **different precedence
  order**. A specification carrying more than one alias (e.g. both
  `geometry.length_mm` and `length_mm`) resolves to different values in the
  candidate vs canonical path.
- **HISTORICAL_CAUSE:** M12-5 copied the M12-4 resolution logic (documented
  decision not to extract helpers); M13-2 then extended both copies with the
  `generated_part` branch.
- **BEHAVIORAL_DIFFERENCE:** verified different alias tuples; divergence only
  for ambiguous inputs (multiple aliases with conflicting values). Roundtrip
  tests mitigate today.
- **AUTHORITY_RISK:** pre-promotion candidate CAD can differ from post-promotion
  canonical CAD for an ambiguous but otherwise accepted specification.
- **RECOMMENDED_DIRECTION:** INTRODUCE_SHARED_CORE for input-neutral dimension
  resolution; keep candidate/canonical stages separate.
- **CONFIDENCE:** HIGH (alias tuples verified directly).

### F8 — Duplicated proof status enums and motion-bound formula (M10, same commit)

- **SEVERITY:** P2
- **CAPABILITY:** continuous-proof status and conservative motion bound
- **ORIGINAL_MILESTONE:** M10 (`89b1d75`) — both copies introduced in the same
  commit
- **ORIGINAL_IMPLEMENTATION:** `continuous_proof.py:32`
  `ContinuousSingleAxisProofStatus`; `continuous_proof.py:145-158` `motion_bound`
- **SECOND_IMPLEMENTATION:** `multi_joint_continuous_clearance.py:33`
  `MultiJointContinuousProofStatus` (byte-identical enum);
  `multi_joint_continuous_clearance.py:466` inline
  `2 * reach_bound_mm * sin(min(delta, π)/2) + 1e-9`
- **CURRENT_WIRING:** both WIRED (separate proof engines).
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION
- **WHY_THIS_IS_DUPLICATION:** one status vocabulary for "clear / witness / not
  proven" exists twice, and the load-bearing conservative bound is implemented
  in two places with independently chosen padding constants.
- **HISTORICAL_CAUSE:** single-axis and multi-joint proof paths were authored
  together but not factored.
- **BEHAVIORAL_DIFFERENCE:** equivalent today; any new status or bound
  tightening must be applied in both.
- **AUTHORITY_RISK:** divergent status semantics / proof conservatism after a
  one-sided change.
- **RECOMMENDED_DIRECTION:** INTRODUCE_SHARED_CORE.
- **CONFIDENCE:** HIGH.

### F11 — `analysis.structural` Evidence/dependency node dual-produced with different schemas

- **SEVERITY:** P2
- **CAPABILITY:** `analysis.structural` dependency node / Evidence kind
- **ORIGINAL_MILESTONE:** M5.5C (`4bc2310`) — section tools register
  `evidence_nodes=("analysis.structural",)` (`tools/sections.py:39-44`,
  `tools/section_engineering.py:84`)
- **SECONDARY_MILESTONE:** M11-5 (`07950cd`) —
  `structural/evidence.py:54` `STRUCTURAL_ANALYSIS = "analysis.structural"`
- **CURRENT_WIRING:** WIRED (both).
- **DUPLICATION_TYPE:** AUTHORITY_DUPLICATION (node overload)
- **WHY_THIS_IS_DUPLICATION:** one dependency/Evidence node name now denotes two
  incompatible payload schemas (`SectionGeometryResult` tool output vs typed
  `StructuralEvidencePayload`). The structural verifier rejects tool-produced
  records, and graph invalidation couples unrelated producers.
- **HISTORICAL_CAUSE:** M11-5 reused the existing `analysis.structural` node
  string for a different Evidence kind instead of namespacing it.
- **BEHAVIORAL_DIFFERENCE:** verification already fails closed for the wrong
  schema; the practical effect is coupling and confusing provenance.
- **AUTHORITY_RISK:** invalidation of section-tool Evidence may mark structural
  Evidence stale and vice versa.
- **RECOMMENDED_DIRECTION:** DOCUMENT_AUTHORITY_BOUNDARY /
  REMOVE_DEAD_LEGACY_PATH for the older tool node, or namespace the structural
  node.
- **CONFIDENCE:** MEDIUM-HIGH.

---

## 5. Legacy / Unused / Minor Findings Register

This register defines the remaining finding IDs referenced by the ownership map.
They are bounded, currently-equivalent, or dead; none reach P0–P2.

| ID | Category | Implementation | Origin | Reconciled status | Severity |
| --- | --- | --- | --- | --- | --- |
| F9 | LEGACY_RESIDUE / INTENTIONAL_SUPERSESSION | `kinematic_sweep.py` v1 + `MultiJointCollisionSweep*` v1 bodies | M7C-1/M10 | WIRED but superseded by v2 for candidates; ~130 duplicated orchestration lines | P3 |
| F10 | LEGACY_RESIDUE | M6B-4C `constraint_resolution_workflow.py` / `constraint_resolution_application.py`; duplicate constraint-anchor map (`constraint_requests.py` vs `constraint_resolution_application.py:_anchor_for`) | M6B-4C `4468a62` / M6B-3 `53fa6c4` | `IMPLEMENTED_BUT_UNUSED` (confirmed; no `ProductionApplication` caller) | P3 |
| F12 | POSSIBLE_DUPLICATION / composed-but-unused | duplicate verification helpers: `CanonicalMultiJointM10VerificationService` (`application.py:637`, no `src/` caller); backend provenance direct construction vs `provenance_from_identity`; structural `_mesh_input_hash` / `_is_trusted_freecad_provenance` / artifact-read duplicates; duplicated `application.py` analytical-observation block (`:1693` vs `:1875`); M11 handoff partial re-validation | M11-5 / M12-5 / M13-3 | mixed WIRED + TESTS | P3 |
| F13 | DEAD_DUPLICATE_ARTIFACT | stray untracked `src/mechcad-harness/src/mechcad_harness/structural/solver.py` | post-M13-4 untracked artifact | divergent older copy of `structural/solver.py`; not importable (hyphenated path) | P3 |
| F14 | TEST_ONLY / LEGACY | test-only CAD compilers `azimuth_mount_plate.py`, `yagi_carrier_packaging.py`; raising stub `yagi_carrier.py:242`; `cad_analysis.py` clearance analyzer | M7B/M7C/M8B | TESTS / dead | P3 |
| F15 | LEGITIMATE_ADAPTER_VARIANTS | FreeCAD shape-loading / STEP trust checks / exact-clearance primitive across `backends/freecad.py`, `backends/freecad_assembly.py`, `transient_freecad_measurement.py`, `structural/geometry.py`, `imported_component.py` | M7A/M8C/M9/M11 | distinct trust boundaries; only generic boilerplate repeats | INFO |
| F16 | POSSIBLE_DUPLICATION | three path-segment/wildcard matchers: `changes/ownership.py:_segments`, `dependency/graph.py:path_matches`, `changes/engine.py:_segments` | M2/M3 | WIRED; different validation strictness, no proven divergence | P3 |
| F17 | LEGACY_RESIDUE | legacy `models/task.py` `TaskStatus`/`AgentTask`/`AgentResult` | M0 `7185351` | DEAD, still exported from `models/__init__.py` | P3 |
| F18 | INTENTIONAL_SUPERSESSION / LEGITIMATE_LAYERING | CAD/assembly manifest hashes (`cad_manifest.py`, `cad_assembly_manifest.py`) and legacy vs M13-4E promotion manifest families | M7A/M7B/M12-5/M13-4E | distinct scopes; M13-4E is spec-mandated additive | INFO |

Note on F10: the reconstruction already records the M6B-4C module as
`IMPLEMENTED_BUT_UNUSED` with a Python 3.11/3.12 annotation-import defect
(UNRESOLVED_GAPS `G-10`). This audit independently confirmed the defect:
`constraint_resolution_application.py:193` annotates a parameter with
`ConstraintResolutionRecord` without importing it, and the module lacks
`from __future__ import annotations`. Because `agents/__init__.py:26` imports
the module unconditionally, `from mechcad_harness.agents.gateway import ...`
(used by `application.py:12`) fails on Python 3.11–3.13 under the project's
declared `requires-python = ">=3.11"`. This is an existing documented gap, not a
new duplication finding; it is reported here only as corroboration. It does not
change the duplication severity.

---

## 6. Legitimate Similarity / False Positives

These were investigated and **rejected as harmful duplication**.

| Case | Why it looks duplicated | Why it is legitimate |
| --- | --- | --- |
| M13-3P M10 v1 vs v2 schemas (`KinematicModel`/`V2`, sweep/path/clearance request+result) | Two parallel record families and dispatch branching | Deliberate versioning; M13-3P record explicitly preserves v1 wire formats, hashes, FK behavior, and clearance math. v1 remains a live public `ProductionApplication` surface. |
| M13-2 `generated_part_cad.py` vs earlier CAD generators | Another CAD generator | It maps semantics→`CadPartProgram` and reuses the single `FreeCADBackend.compile_program`; `git log -S` shows the cylinder/bore operations were added once, to that backend. Correct extension, not duplication. |
| FreeCAD shape-loading scripts (`backends/freecad.py`, `backends/freecad_assembly.py`, `transient_freecad_measurement.py`, `structural/geometry.py`, `analysis_service.py`) | Repeated `Part.insert`/`makeCompound`/`BoundBox`/`Volume` boilerplate | Distinct runtime and trust boundaries: generation verification, assembly verification, transient collision measurement, FEA region resolution, and legacy clearance analysis. Not one authority owned twice. |
| `state_hash` vs artifact/content hashes (`assembly_hash`, `cad_program_hash`, `imported_component_hash`, candidate/result hashes) | Many `*_hash` functions | Different responsibilities (state identity vs content identity). Only the **serialization implementation** is flagged (F2). |
| M3 dependency graph vs M4 task DAG | Both graph-like | Invalidation DAG vs run/task state; different owners, no shared decision. |
| M12 candidate model vs canonical `DesignState` | Both represent mechanism state | Candidate is pre-promotion noncanonical authority; canonical is the DesignState revision. Explicit conversion boundaries exist. |
| M11 structural geometry adapter vs M9/M10 measurement provider | Both load FreeCAD geometry | Distinct BREP/face resolution vs transient overlap measurement; the structural adapter deliberately avoids backend private methods. |
| Production backend vs `structural/fakes.py` | Fake provenance/adapters | Test doubles, correctly labeled. |
| Source model vs persisted provenance model | Field overlap | Serialization boundary, not duplicate authority. |
| M11-4 deck lowering vs M11-4 result-side load verification (`deck.py:_lower_resultant_force` vs `results.py:_reconstruct_resultant_lowering`) | Two implementations of load lowering | Intentional independent verifier recomputing force/moment conservation from canonical loads + trusted mesh. Preserve. |
| M12-5 vs M13-4E promotion manifest families | Two manifest/verification families | Spec-mandated additive family; the M13-4E spec explicitly states the earlier `PrePromotionM10ScopeProjection@1` "is not reused". |
| Defense-in-depth tool checks (`agents/tool_mediation.py` and `tools/broker.py`) | Both check capability/permission/currentness | Independent boundary validation; legitimate layering. |
| `build_candidate_view` vs `build_canonical_view` | Two adapters | Same interface over different record layers; legitimate adapter variants. |

---

## 7. Cross-Milestone Patterns

1. **Copy-forward between staged verifiers (M12→M12/M13; M11-2→M11-5).** When a
   later milestone needed a fresh "post" verifier, the "pre" implementation was
   copied rather than shared, and the copies have drifted (F1, F4, F7, F12).
   This is the dominant duplication mechanism.
2. **Local hash helpers instead of the M2 shared core (M2 onward).** Every major
   milestone added its own canonicalization snippet (F2). The M2 authority was
   never established as the single consumer surface.
3. **Parallel identity/status vocabularies (M3→M11→M12; M7A→M11; M10).** Later
   milestones re-declared enums/constants for the same concept (F3, F5, F6,
   F8, F11).
4. **Deliberate versioning done correctly (M13-3P) and deliberate additive
   design (M13-4E).** These show the project can avoid authority duplication
   when the contract requires it; the harmful cases are copy-for-convenience,
   not architectural versioning.

---

## 8. Highest-Risk Authority Boundaries

| Rank | Boundary | Risk |
| --- | --- | --- |
| 1 | Canonical serialization / identity (`canonical_json` vs ~20 copies) | Different bytes → different hashes → identity checks fail; hard to localize (F2). |
| 2 | M10 result contract (candidate `m10_evaluation.py` vs canonical `canonical_m10.py`) | Already-diverged validation; one stage may accept/reject differently (F1). |
| 3 | Candidate vs canonical CAD dimension resolution | Different alias precedence can produce different canonical CAD from the same spec (F7). |
| 4 | FreeCAD runtime identity (`FREECAD_BACKEND_VERSION` vs `FREECAD_IDENTITY`) | Unilateral bump breaks all M11 provenance verification (F5). |
| 5 | Evidence validity (`get_evidence_freshness` vs structural/candidate currentness) | Two notions of "still valid"; precedence undocumented (F3). |
| 6 | `analysis.structural` node overload | Cross-invalidation of unrelated producers (F11). |
| 7 | Structural mesh-spec/input hashing (4 + 2 variants) | A future volatile field splits verification hashes (F4). |

None of these currently allows two production paths to write incompatible
*canonical* records; the canonical-revision-writer and invalidation-engine
invariants hold.

---

## 9. Suggested Remediation Order

High-level direction only; no implementation is authorized by this audit.

1. **CRM → `CANONICALIZE_ON_EXISTING_AUTHORITY`** for canonical serialization
   (F2): route content-identity hashing through `state/hashing.canonical_json`.
   Lowest risk, highest leverage; it de-risks F4/F5/F6/F11.
2. **`INTRODUCE_SHARED_CORE`** for the M10 result-contract validators (F1) and
   candidate/canonical dimension resolution (F7), without merging candidate and
   canonical stages.
3. **`CANONICALIZE_ON_EXISTING_AUTHORITY`** for identity constants and hash
   helpers: FreeCAD identity (F5), `physical_kinematic_root_hash` (F6),
   mesh-spec/input hashing (F4).
4. **`DOCUMENT_AUTHORITY_BOUNDARY`** for freshness vs currentness (F3) and the
   `analysis.structural` node (F11); consider namespacing.
5. **`REMOVE_DEAD_LEGACY_PATH`** (separate follow-up, not this audit): unused
   M6B-4C workflow / duplicate anchor map (F10) — after fixing the documented
   supported-Python import defect; test-only CAD compilers / dead `TaskStatus`
   (F14, F17); determine fate of the composed-but-unused
   `CanonicalMultiJointM10VerificationService` (F12).
6. **Housekeeping:** remove or relocate the untracked stray
   `src/mechcad-harness/**/solver.py` (F13) so future edits cannot target the
   wrong path.

---

## 10. Historical Reconstruction Discrepancies

**RECONSTRUCTION_DISCREPANCY_CANDIDATES: 0.**

No factual error was found in `docs/reconstruction/**`. The reconstruction's
M13-3P versioning statement, M13-2 capability attribution, M6B-4C
`IMPLEMENTED_BUT_UNUSED` classification, and `UNRESOLVED_GAPS G-10` import defect
were all independently consistent with current code. This audit's findings are
about **current** duplication accumulated across the reconstructed evolution;
they do not reinterpret history and required no reconstruction edits.

---

## 11. Unresolved Questions

1. **F7 reachability:** can an accepted candidate specification carry multiple
   dimension aliases with conflicting values? If not, F7 is P3 rather than P2.
   Requires reading the candidate-synthesis/acceptance validators and M12-6
   roundtrip tests.
2. **F11 intent:** was reusing `analysis.structural` for typed structural
   Evidence intentional (single engineering domain) or accidental? Needs a
   contemporary spec/plan that may be under `docs/superpowers/**`.
3. **F1 canonical validator authority:** is `canonical_m10.py` intended to be
   strictly stronger than `m10_evaluation.py`, or should they be identical? The
   M12-5 plan notes a preference against extraction but not an intended
   superset.
4. **F12 capability boundary:** `CanonicalMultiJointM10VerificationService` is
   composed but never called in `src/`; is fresh canonical multi-joint M10
   verification part of the accepted M13-4E contract or intentionally omitted?
5. **`default=str` serializer sites** (`changes/provenance.py`,
   `agents/constraint_resolution.py`): do any persisted records hash through
   these and also get compared against a `canonical_json`-produced value? If so,
   F2 escalates to P0.

---

## 12. Independent Review Record

Every P1/P2 finding was re-verified against the cited source before inclusion.

| Finding | Original claim | Independent check | Verdict |
| --- | --- | --- | --- |
| F1 | candidate/canonical M10 validators diverge | read both `_validate_continuous_result` bodies; canonical adds `source_assembly_id` check, candidate does not | CONFIRMED |
| F2 | canonical JSON variants diverge | read `state/hashing.py`, `models/physical_pair_policy.py`, `structural/models.py`, `structural/evidence_models.py`; confirmed `ensure_ascii` difference and one byte-identical copy | CONFIRMED |
| F3 | two currentness enums byte-identical | read `structural/evidence.py:58` and `candidates/services.py:19`; identical | CONFIRMED |
| F4 | 4 mesh-spec + 2 mesh-input hashes | grep confirmed 6 definitions | CONFIRMED |
| F5 | FreeCAD version literal duplicated | read `structural/runtime.py:21-23` and `backends/freecad.py:22`; both `mechcad-freecad@2.1` | CONFIRMED |
| F6 | `physical_kinematic_root_hash` twice | read both definitions; same payload, different serializer | CONFIRMED |
| F7 | alias precedence differs | read both `_DIMENSION_ALIASES` tuples; different order | CONFIRMED |
| F8 | proof enums identical, same commit | read both enum bodies; byte-identical; git `-S` in subagent evidence | CONFIRMED |
| F11 | `analysis.structural` dual-produced | grep confirmed tool registrations and structural `STRUCTURAL_ANALYSIS` | CONFIRMED |

No finding was downgraded or rejected during review. Two subagent assertions were
corrected/rejected:
- "`physical_pair_policy._canonical_json` is divergent from shared" — **rejected**;
  it is byte-identical (still counted under F2 as a duplicate copy).
- "candidate-side M10 pair classification was aliased to the new authority" —
  **downgraded** to POSSIBLE_DUPLICATION (F8) because no live path cross-passes
  the two enums.

False-positive candidates (M13-3P v1/v2, M13-2 CAD extension, FreeCAD
shape-loading scripts, `state_hash` vs content hashes, M11 independent verifiers,
M12-5/M13-4E manifest families) were each explicitly checked and **rejected** as
harmful duplication (§6).

---

## 13. Audit Metadata

- Historical baseline verified: M13-4 `185a304796c17793519fb5f01dbf80cca73ab51e`;
  synthesis `0cbb70e64c2efdc021f15d341bc043b574ff552b`.
- Production composition root: `src/mechcad_harness/application.py:404` /
  `:775`.
- Production code modified: NO.
- Tests modified: NO.
- Reconstruction modified: NO.
- Unrelated dirty work preserved: YES (`.coverage`, `.superpowers/sdd/*`,
  untracked Rotator V2 audit/plan/test files, `projects/`, and
  `src/mechcad-harness/` left untouched).
