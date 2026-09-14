# MechCAD Logic Duplication & Capability Ownership Audit

- **Audit type:** repository-wide semantic / architectural / authority duplication
  audit using the completed Historical Reconstruction as the temporal map.
- **Original audit baseline:** product endpoint M13-4 at
  `185a304796c17793519fb5f01dbf80cca73ab51e`; reconstruction synthesis
  `0cbb70e64c2efdc021f15d341bc043b574ff552b` (both verified locally against the
  reconstruction ledger).
- **Current accepted production baseline:**
  `b63d010c4ce0cc93fc556c4890606c5eeecb1e08`.
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
| CONFIRMED_MATERIAL_DUPLICATIONS (P0–P2) | 9 (1×P1, 8×P2) |
| AUTHORITY_CONFLICTS | 2 (latent/bounded, none P0) |
| LEGACY_RESIDUES (P3 findings) | 10 |
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
   artifact checks (F4, F21).
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
| Revision hashing | `core/canonical.py` (neutral canonical serialization); `state/hashing.py:canonical_json` delegates to it for state hashing | WIRED |
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
  `revisions/` and `current.json`; `changes/engine.py` remains the ordinary
  production mutation path and the only production caller of `create_revision`.
  No second canonical revision writer exists.
- **Single invalidation engine.** `DependencyGraph.impact` computes impact;
  storage persists it; no competing engine.
- **Single FRD/DAT parser.** Structural result parsing is not duplicated in
  candidate code (`candidates/**` contains no FEA output parser).
- **Single FreeCAD primitive realization.** M13-2 added cylinder/bore/plate
  operations to the one backend rather than a second generator.

---

## 4. Confirmed Material Findings

### F1 — Candidate vs canonical M10 result validators: intentionally different trust contracts, with a duplicated and already-drifted shared kernel

- **SEVERITY:** P2 (downgraded from P1 — see resolution below)
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
- **DUPLICATION_TYPE:** SEMANTIC_DUPLICATION (shared M10 result-validation
  kernel copied across two intentionally distinct trust stages)
- **RESOLVED_INTENT:** **DIFFERENT_TRUST_CONTRACTS.** The M12-4 and M12-5
  specs/plans explicitly intend two different trust boundaries: a
  candidate-bound M12-4 stage (`M12-4 spec:243-249`, stage vocabulary
  `SUCCESS/UNRESOLVED/NOT_REACHED`) versus an independent candidate-free M12-5
  canonical execution (`M12-5 spec:468-473` "derives a new … disposition …
  and M10 request from the canonical obligation"; `M12-5 spec:472` "Candidate
  and canonical M10 request hashes must differ even when the physical
  obligation is equivalent"; `M12-5 plan:318` "no candidate-bound M10 type or
  frozen scope is an execution input"). The verdict is **not** a strict
  superset: the candidate validator is *stricter* on witness classification and
  sweep-version; the canonical validator is *stricter* on assembly identity and
  model-level self-verification.
- **VALIDATOR_DIFFERENCES (exhaustive):**

  | # | Difference | Candidate | Canonical | Direction |
  | --- | --- | --- | --- | --- |
  | D1 | continuous `source_assembly_id` check | hash only, and skipped during evaluation revalidation (`evaluation.py:703` calls the validator without `assembly`) | checks id **and** hash, `assembly` mandatory (`canonical_m10.py:1140`) | canonical stricter; candidate coverage weak |
  | D2 | collision-witness classification restriction | requires `INTERFERENCE`/`TOUCHING` (`m10_evaluation.py:1139-1143`) | no classification restriction (`canonical_m10.py:1170-1180`) | candidate stricter |
  | D3 | home sweep-service version pin | pins `RIGID_BODY_COLLISION_SWEEP_VERSION` (`m10_evaluation.py:1151-1156`) | request/result mutual equality only | candidate stricter |
  | D4 | recompute underlying `result_hash` at model level | service-level only | model-level (`canonical_m10.py:314`, `:362`) | canonical stricter |
  | D5 | nested per-sample pair partition at model level | service-level | model-level (`canonical_m10.py:343-353`) | canonical stricter |
  | D6 | stage status vocabulary | `SUCCESS/UNRESOLVED/NOT_REACHED` (`m10_evaluation.py:664`) | `VERIFIED_CLEAR/COLLISION_WITNESS/NOT_PROVEN` aggregate (`canonical_m10.py:100`, `:565-570`) | intentional vocabulary split (M12-4 spec:243-249; M12-5 spec:485-497) |
  | D7 | outcome embedded-identity completeness | binds hashes only | embeds scope/inventory/request and cross-checks (`canonical_m10.py:469-576`) | different trust boundaries (M12-5 plan:316-319) |
  | D8 | induced pair-assembly suffix | `-m10-pair-` | `-canonical-m10-pair-` | intentional (M12-5 spec:472 requires differing hashes) |
  | D9 | scope carries `proof_service_version` | yes (`m10_evaluation.py:173`) | no | intentional (candidate-bound scope not used canonically) |
  | D10 | `_result_hash`/`_require_hash`/`_canonical_pair` helpers | equivalent bodies | equivalent bodies | copy, no semantic difference |

- **WHY_THIS_IS_DUPLICATION:** the *existence* of two validators is legitimate,
  but the shared M10 result-validation kernel (`_validate_*_result`,
  `_induced_pair_assembly`, the v1 disposition/pair-classification models at
  `m10_evaluation.py:98-763` vs `canonical_m10.py:103-576`) was copy-forwarded
  rather than parameterized by stage. D1 and D2 are genuine, **untested**
  divergences; no M12-4/M12-5 spec or plan states an intended superset or a
  shared kernel.
- **HISTORICAL_CAUSE:** M12-5 required a fresh post-promotion, candidate-free
  canonical execution. The M12-5 plan preferred independent derivation
  (`2026-08-29-...plan.md:318`, `:442`) and the CAD tasks advised against
  extracting candidate helpers unless a focused test required it
  (`...plan.md:305`), so the candidate validators were copied. The independent
  trust stage was intended; the un-synchronized duplication was not addressed.
- **BEHAVIORAL_DIFFERENCE:** the two can return different verdicts on the same
  *tampered/stored* result (canonical catches a forged `source_assembly_id`;
  candidate catches an invalid witness classification). In live execution both
  sides derive `assembly_id`+hash together, so the divergence is unreachable
  without tampering.
- **AUTHORITY_RISK:** bounded. M12-5 does **not** reuse candidate M10 results
  (it executes fresh canonical M10), so no accepted-then-rejected canonical
  inconsistency arises. Residual risk is candidate-side validation weakness on
  tampered persisted artifacts plus future one-sided drift. This is why the
  finding is P2, not P1/P0.
- **RECOMMENDED_DIRECTION:** INTRODUCE_SHARED_CORE for the M10 result kernel,
  parameterized by trust stage (keep D6-D9 structural differences); add explicit
  tests for D1/D2 so the intended per-stage strictness is encoded rather than
  accidental.
- **TIMELINE / TEST_DIFFERENCE:** see §14 (F1 row) and §15 (F1 row).
- **CONFIDENCE:** HIGH (both files, specs, plans, and tests read directly).

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
- **RESOLVED_ARCHITECTURAL_BOUNDARY:** `state/hashing.py:canonical_json` is
  **not** the correct common dependency target. `state/hashing.py:5` imports
  `models.DesignState`, so having leaf `models/**` (or `backends/**`,
  `tools/**`, `yagi_*.py`, which today have **zero** state-layer imports) import
  it inverts the `models → state → models` layering. The inversion is currently
  masked by deferred imports (`models/generated_part.py:27-28` comment,
  `models/geometry_identity.py:54,72`, `models/supplied_component_interface.py`,
  `models/generated_placement.py`) and lazy `models/__init__.__getattr__`.
  Corrected direction: **EXTRACT_NEUTRAL_CANONICAL_SERIALIZATION_CORE** — a leaf
  module exporting the exact byte contract
  (`ensure_ascii=False, sort_keys=True, separators=(",", ":")`) that both
  `state/hashing.py` and the ~20 content-identity sites import, preserving all
  existing hash bytes. Artifact byte hashing (`artifacts/storage.py`) remains a
  separate authority and must **not** be routed through it.
- **RESOLVED_CROSS_COMPARISON:** **no** `default=str` serializer output
  (`changes/provenance.py:11` `_canonical`→`operations_hash`/`application_id`;
  `agents/constraint_resolution.py:222` `_canonical_json`→`command_id`/
  `resolution_id`) is directly cross-compared against a strict
  `canonical_json`-produced value. `operations_hash` is only compared to
  `operations_hash`; `application_id`/`command_id`/`resolution_id` are
  UUID-derived identifiers, not digests. Therefore F2 does **not** escalate to
  P0. The residual F2 risk is identity-byte instability among the duplicate
  serializers (chiefly the `ensure_ascii` variants in `structural/**` and
  `application.py:218`), which is why it remains P1.
- **RECOMMENDED_DIRECTION:** EXTRACT_NEUTRAL_CANONICAL_SERIALIZATION_CORE;
  migrate the content-identity serializers to it and delete the local variants
  **without** changing emitted bytes. Do not merge artifact byte hashing or the
  structural volatile-key filtering policy into the core.
- **TIMELINE / TEST_DIFFERENCE:** see §14 (F2 row) and §15 (F2 row).
- **CONFIDENCE:** HIGH (variants and dependency direction verified directly).

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
- **BEHAVIORAL_DIFFERENCE:** verified different alias tuples **and** different
  source priority (candidate resolves spec `properties` first then design
  variables; canonical resolves `accepted_design_choices` first then
  properties). Confirmed divergence for inputs carrying two aliases with
  conflicting values.
- **RESOLVED_REACHABILITY:** **REACHABLE — F7 remains P2.** No validator on the
  supported path collapses aliases or requires them to agree. Candidate property
  keys and design-variable names are only checked for exact-duplicate strings
  (`candidates/models.py:334-336`, `:1097-1099`); promotion copies all
  properties verbatim and remaps design variables into accepted choices without
  alias collapse (`candidates/promotion.py:1189-1260`); and
  `verify_promoted_mechanism` has **no** candidate-vs-canonical dimension
  agreement gate (it compares M10 scope, not geometry,
  `candidates/promotion.py:3272-3408`). Smallest example: a `mount`
  specification carrying both `geometry.length_mm = 100.0` and
  `length_mm = 30.0` (all `AVAILABLE`, `mm`, finite, positive) yields a
  100 mm candidate plate and a 30 mm canonical plate. The prior audit's claim
  that "roundtrip tests mitigate today" is **not supported**: the M12-6 fixtures
  use a single alias spelling (`{instance}.length_mm`), so alias precedence is
  never exercised and no test compares candidate vs canonical dimensions.
- **AUTHORITY_RISK:** pre-promotion candidate CAD can differ from post-promotion
  canonical CAD for an ambiguous but otherwise accepted specification.
- **RECOMMENDED_DIRECTION:** INTRODUCE_SHARED_CORE for input-neutral dimension
  resolution; keep candidate/canonical stages separate; add an explicit
  alias-collapse or alias-agreement validator at the candidate-specification
  boundary.
- **TIMELINE / TEST_DIFFERENCE:** see §14 (F7 row) and §15 (F7 row).
- **CONFIDENCE:** HIGH (alias tuples, source priority, promotion copy, and
  verifier gate verified directly).

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
- **RESOLVED_AUTHORITY_SEMANTICS:** **CONFIRMED_AUTHORITY_DUPLICATION (node /
  namespace overload); F11 remains P2.** Both producers use the **same**
  `EvidenceStore` namespace `projects/<project_id>/evidence/*.json`
  (`dependency/storage.py:68-86`), the **same** `kind` literal
  `"analysis.structural"` (`tools/sections.py:39-44`,
  `structural/evidence.py:53-55`), and the **same kind-based retrieval and
  invalidation**: `get_evidence_freshness` keys off `evidence.kind`
  (`dependency/storage.py:88-107`) and `fresh_evidence_status` matches
  `evidence.kind == node` (`:118-130`), while `config/dependencies.yaml:41-56`
  invalidates `analysis.structural` on `/materials/*` and
  `/structural_analysis_definitions/*` — so one change stales **both** the
  M5.5C section-tool records and the M11-5 FEA records. The payload schemas are
  incompatible (`SectionGeometryResult`/`SectionWarpingResult` vs
  `StructuralEvidencePayload`), and verification is asymmetric:
  `StructuralEvidenceVerifier._require_payload` rejects tool records
  (`structural/evidence_service.py:1031-1037`) while no semantic verifier
  exists for tool records. This fails the `LEGITIMATE_SHARED_DOMAIN` test
  (which requires distinct `kind` and no shared retrieval/verification).
  `LEGACY_NODE_COLLISION` is a defensible alternative label, but the
  cross-invalidation coupling is proven current behavior.
- **INTENT:** literal reuse was intentional **per authoring site** (M5.5C plan
  `2026-08-18-mechcad-m5-5c3a-...md:157` chose `analysis.structural`; M11-5 plan
  `2026-08-25-...md:70` reused it and `:45` says "do not redefine historical
  validity semantics"), but **no M11-5 spec/plan acknowledges the pre-existing
  M5.5C tool producer or the incompatible schema**. The cross-producer collision
  was not evaluated.
- **BEHAVIORAL_DIFFERENCE:** schema verification fails closed, but a tool record
  can still satisfy an `analysis.structural` freshness/fulfillment query, and
  invalidation couples unrelated producers.
- **AUTHORITY_RISK:** invalidation of section-tool Evidence marks structural
  Evidence stale and vice versa; node-based readiness queries can be satisfied
  by the wrong record family.
- **RECOMMENDED_DIRECTION:** DOCUMENT_AUTHORITY_BOUNDARY and separate the
  node identity (namespace the M11-5 typed node, e.g.
  `analysis.structural.evidence`, or give the M5.5C tools a distinct
  `analysis.section` node); do not remove either producer.
- **TIMELINE / TEST_DIFFERENCE:** see §14 (F11 row) and §15 (F11 row).
- **CONFIDENCE:** HIGH (store, kind, retrieval, invalidation, and verifier
  paths verified directly).

---

## 5. Legacy / Unused / Minor Findings Register

This register defines the remaining finding IDs referenced by the ownership map.
They are bounded, currently-equivalent, or dead; none reach P0–P2.
This table is the preserved pre-closure audit snapshot. Current final
dispositions are governed by §25; its `CLOSED`, `RETAINED`, and `DEFERRED`
statuses supersede this table for the current accepted tree. The historical
rows below are not rewritten as though the findings never existed.

| ID | Category | Implementation | Origin | Reconciled status | Severity |
| --- | --- | --- | --- | --- | --- |
| F9 | LEGACY_RESIDUE / INTENTIONAL_SUPERSESSION | `kinematic_sweep.py` v1 + `MultiJointCollisionSweep*` v1 bodies | M7C-1/M10 | WIRED but superseded by v2 for candidates; ~130 duplicated orchestration lines | P3 |
| F10 | LEGACY_RESIDUE | M6B-4C `constraint_resolution_workflow.py` / `constraint_resolution_application.py`; duplicate constraint-anchor map (`constraint_requests.py` vs `constraint_resolution_application.py:_anchor_for`) | M6B-4C `4468a62` / M6B-3 `53fa6c4` | `IMPLEMENTED_BUT_UNUSED` (confirmed; no `ProductionApplication` caller) | P3 |
| F12 | LEGACY_RESIDUE / composed-but-unused | `CanonicalMultiJointM10VerificationService` composed at `application.py:637` but no `src/` caller | M13-3 `ca294e0` | WIRED attribute, unreachable from production composition; tests only | P3 |
| F13 | DEAD_DUPLICATE_ARTIFACT | stray untracked `src/mechcad-harness/src/mechcad_harness/structural/solver.py` | post-M13-4 untracked artifact | divergent older copy of `structural/solver.py`; not importable (hyphenated path) | P3 |
| F14 | TEST_ONLY / LEGACY | test-only CAD compilers `azimuth_mount_plate.py`, `yagi_carrier_packaging.py`; raising stub `yagi_carrier.py:242`; `cad_analysis.py` clearance analyzer | M7B/M7C/M8B | TESTS / dead | P3 |
| F15 | LEGITIMATE_ADAPTER_VARIANTS | FreeCAD shape-loading / STEP trust checks / exact-clearance primitive across `backends/freecad.py`, `backends/freecad_assembly.py`, `transient_freecad_measurement.py`, `structural/geometry.py`, `imported_component.py` | M7A/M8C/M9/M11 | distinct trust boundaries; only generic boilerplate repeats | INFO |
| F16 | POSSIBLE_DUPLICATION | three path-segment/wildcard matchers: `changes/ownership.py:_segments`, `dependency/graph.py:path_matches`, `changes/engine.py:_segments` | M2/M3 | WIRED; different validation strictness, no proven divergence | P3 |
| F17 | LEGACY_RESIDUE | legacy `models/task.py` `TaskStatus`/`AgentTask`/`AgentResult` | M0 `7185351` | DEAD, still exported from `models/__init__.py` | P3 |
| F18 | INTENTIONAL_SUPERSESSION / LEGITIMATE_LAYERING | CAD/assembly manifest hashes (`cad_manifest.py`, `cad_assembly_manifest.py`) and legacy vs M13-4E promotion manifest families | M7A/M7B/M12-5/M13-4E | distinct scopes; M13-4E is spec-mandated additive | INFO |
| F19 | POSSIBLE_DUPLICATION | duplicate physical pair-classification enums: `models/physical_pair_policy.py:PhysicalPairClassification` (M13-3) vs `candidates/canonical_m10.py:CanonicalM10PairClassification` (M12-5); values identical, but `is`-identity comparisons would silently fail if the enums are ever cross-passed | M12-5 (`161986b`) / M13-3 (`ca294e0`) | WIRED, but no live path cross-passes the two enums | P3 |
| F20 | SEMANTIC_DUPLICATION (low risk) | quaternion / rigid-transform primitives: `kinematic_sweep.py` private quaternion helpers + `multi_joint_kinematics.transform_*` vs `models/quaternion.py` + `models/generated_placement.compose_poses` | M7C-1 (`9ab9e48`) / M10 (`89b1d75`) vs M13-1 (`f6d8124`) / M13-2 (`664ec3b`) | WIRED; equivalent today, but the normalization responsibility differs (validator vs helper) | P3 |
| F21 | POSSIBLE_DUPLICATION | duplicated verification/identity helper bodies: backend provenance direct construction vs `provenance_from_identity`; structural `_mesh_input_hash` / `_is_trusted_freecad_provenance` / artifact-read duplicates; duplicated `application.py` analytical-observation block (`:1693` vs `:1875`); M11 handoff partial re-validation | M11-5 / M12-5 / M13-3 | mixed WIRED + TESTS | P3 |

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
   copied rather than shared, and the copies have drifted (F1, F4, F7, F21).
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

The F1, F2, F4, F5, F6, F7, and F11 entries above retain their historical audit
risk statements. Their accepted current-state remediation records are appended
below and the companion ownership map reflects the resulting authorities. The
pre-remediation status summary recorded F3 and F8 as unresolved; current-tree
status is now governed by the appended records: F3 is resolved by the F3
post-acceptance record, and F8 is closed under the approved Option D
disposition.

---

## 9. Suggested Remediation Order

High-level direction only; no implementation is authorized by this audit.
The ordered directions below are the original pre-remediation recommendations;
current dispositions are recorded in §25 and do not rewrite this history.

1. **`EXTRACT_NEUTRAL_CANONICAL_SERIALIZATION_CORE`** for canonical
   serialization (F2): a leaf module exporting the exact existing byte contract,
   imported by `state/hashing.py` and the ~20 content-identity sites; preserve
   emitted bytes; keep artifact byte hashing and the structural volatile-key
   filter out of it. This is the lowest-risk, highest-leverage step **for the
   serializer duplication only**. It does **not** by itself resolve F5
   (FreeCAD identity constant), F6 (duplicate `physical_kinematic_root_hash`),
   or F11 (`analysis.structural` node overload) — those are separate
   authorities with different failure modes. It partially reduces F4's drift
   surface insofar as the mesh-spec hashes are migrated to the shared
   serializer, but the four-way mesh-spec **hash authority** still needs a
   single owner.
2. **  `INTRODUCE_SHARED_CORE`** for the M10 result-contract validators (F1,
   parameterized by trust stage; keep D6-D9 structural differences), for
   candidate/canonical dimension resolution (F7; add an alias-agreement gate),
   and for the duplicated verification/identity helper bodies (F21), without
   merging candidate and canonical stages.
3. **`CANONICALIZE_ON_EXISTING_AUTHORITY`** for the remaining duplicated
   identity and hash helpers, each independently: FreeCAD identity (F5),
   `physical_kinematic_root_hash` (F6), mesh-spec/input hashing (F4).
4. **`DOCUMENT_AUTHORITY_BOUNDARY`** for freshness vs currentness (F3) and the
   `analysis.structural` node (F11); separate the node identity rather than
   removing either producer.
5. **`REMOVE_DEAD_LEGACY_PATH`** (separate follow-up, not this audit): unused
   M6B-4C workflow / duplicate anchor map (F10) — after fixing the documented
   supported-Python import defect; test-only CAD compilers / dead `TaskStatus`
   (F14, F17); the duplicate pair-classification enum (F19) and transform
   primitives (F20) can be consolidated with the shared core; determine the fate
   of the composed-but-unused `CanonicalMultiJointM10VerificationService` (F12).
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

## 11. Resolved Uncertainties and Remaining Questions

All uncertainties that could change a P1/P2 classification are now resolved.
The P3 questions below are the pre-closure audit snapshot. Current P3
dispositions are recorded in §25 and do not rewrite this historical register.

**Resolved (this closure pass):**

1. **F1 intent → DIFFERENT_TRUST_CONTRACTS; downgraded to P2.** Both files
   implement two intentionally different trust stages; the duplication is the
   copy-forwarded shared M10 result kernel, with D1/D2 untested drift. Safe
   (fail-closed, candidate M10 results are not reused canonically).
2. **F7 reachability → REACHABLE; remains P2.** No validator collapses aliases;
   promotion preserves ambiguity; no candidate-vs-canonical dimension gate. The
   smallest divergence example is recorded in the finding. The prior
   "roundtrip tests mitigate" statement was removed as unsupported.
3. **F11 intent → CONFIRMED_AUTHORITY_DUPLICATION (node/namespace overload);
   remains P2.** Same store, same `kind`, shared kind-based retrieval and
   invalidation, incompatible schemas, asymmetric verification. Literal reuse
   was intentional per site, but the cross-producer collision was not
   acknowledged and is proven current behavior.
4. **F2 remediation boundary → `EXTRACT_NEUTRAL_CANONICAL_SERIALIZATION_CORE`.**
   `state/hashing.canonical_json` is the wrong dependency target because it
   imports `models.DesignState`; low-level `models/**`/`backends/**`/`tools/**`
   importing it inverts layering. The `default=str` cross-comparison question is
   resolved: **no** cross-comparison exists, so F2 does not escalate to P0.

**Remaining, non-blocking (no P1/P2 impact):**

- **F12:** whether fresh canonical multi-joint M10 verification is part of the
  accepted M13-4E contract or intentionally omitted (P3; the composed service
  has no `src/` caller). This does not affect any P1/P2 classification.
- **F21:** whether the duplicated verification/identity helper bodies should be
  consolidated (P3; behavior currently equivalent). No P1/P2 impact.
- **F9/F18:** whether the M13-3P v1/v2 and M12-5/M13-4E additive families should
  eventually be pruned (P3/INFO; documented as intentional).

---

## 12. Independent Review Record

Every P1/P2 finding was re-verified against the cited source before inclusion
and again during the acceptance-closure pass.

| Finding | Original claim | Independent check | Verdict |
| --- | --- | --- | --- |
| F1 | candidate/canonical M10 validators diverge | read both files plus M12-4/M12-5 specs, plans, reconstruction, and tests; enumerated D1–D10 | **DOWNGRADED_P2** |
| F2 | canonical JSON variants diverge | read serializers, dependency direction, and every consumer of the `default=str` hashes | CONFIRMED (P1) |
| F3 | two currentness enums byte-identical | read `structural/evidence.py:58` and `candidates/services.py:19`; identical | CONFIRMED |
| F4 | 4 mesh-spec + 2 mesh-input hashes | grep confirmed 6 definitions | CONFIRMED |
| F5 | FreeCAD version literal duplicated | read `structural/runtime.py:21-23` and `backends/freecad.py:22`; both `mechcad-freecad@2.1` | CONFIRMED |
| F6 | `physical_kinematic_root_hash` twice | read both definitions; same payload, different serializer | CONFIRMED |
| F7 | alias precedence differs | read both alias maps **and** source priority; promotion preserves ambiguity; no candidate-vs-canonical dimension gate; constructed minimal example | CONFIRMED (P2) |
| F8 | proof enums identical, same commit | read both enum bodies; byte-identical | CONFIRMED |
| F11 | `analysis.structural` dual-produced | traced same store, same `kind`, kind-based retrieval, shared invalidation, asymmetric verifier | CONFIRMED (P2) |
| F19 | duplicate pair-classification enums | read both `StrEnum` bodies; identical values; no live cross-pass | CONFIRMED (P3) |
| F20 | duplicate transform/quaternion primitives | read both stacks; equivalent outputs, differing normalization responsibility | CONFIRMED (P3) |

**Skeptical-review dispositions (attempts to disprove each P1/P2):**

- **F1 — DOWNGRADED_P2.** The intent question is resolved: the M12-4/M12-5
  sources intentionally define two different trust stages, and canonical is not
  a strict superset (candidate is stricter on D2/D3). The transferable defect is
  the copy-forwarded shared kernel with untested D1/D2 drift, bounded and
  fail-closed; not an authority conflict. It cannot remain P1.
- **F2 — CONFIRMED P1.** The variant divergence is real and byte-level. The
  attempt to disprove it failed; the attempt to escalate it to P0 via a
  `default=str` cross-comparison **failed** (no cross-comparison exists), so P1
  stands.
- **F3, F4, F5, F6, F8, F11 — CONFIRMED.** No counter-evidence found; each is a
  verified duplicate authority/enum/hash. F11 is confirmed as a genuine
  node/namespace overload (not legitimate shared domain) because `kind`,
  retrieval, and invalidation are shared.
- **F7 — CONFIRMED P2.** The attempted disprove (that ambiguous aliases are
  unreachable) **failed**: no validator collapses aliases, promotion preserves
  them, and no geometry-agreement gate exists. The prior
  "roundtrip tests mitigate" mitigation was rejected as unsupported.
- **F19/F20 — CONFIRMED P3**, not elevated: no live path cross-passes the pair
  enums and the transform primitives are equivalent today.

One prior-review assertion was corrected during this pass: the pair
classification duplication was previously mis-referenced as "F8"; it is now the
distinct finding **F19**. No finding was rejected. False-positive candidates
(M13-3P v1/v2, M13-2 CAD extension, FreeCAD shape-loading scripts, `state_hash`
vs content hashes, M11 independent verifiers, M12-5/M13-4E manifest families)
were each explicitly checked and **rejected** as harmful duplication (§6).

---

## 13. Acceptance Closure Summary

| Closure item | Result |
| --- | --- |
| Finding IDs unique (F1–F21) | YES |
| F1 intent | DIFFERENT_TRUST_CONTRACTS → DOWNGRADE_P2 |
| F7 reachability | REACHABLE → P2 retained |
| F11 authority | CONFIRMED_AUTHORITY_DUPLICATION (node overload) → P2 retained |
| F2 architectural boundary | EXTRACT_NEUTRAL_CANONICAL_SERIALIZATION_CORE; no P0 escalation |
| All P1/P2 independently challenged | YES (§12) |
| Ownership map synchronized | YES (§16 summary) |
| Unresolved questions affecting P1/P2 | NONE (§11) |

---

## 14. P1/P2 Timeline Register

Compact timeline for every remaining P1/P2 finding. No distinct milestone is
invented where both implementations share one commit; those rows state the
shared boundary explicitly.

**F1 — M10 result validators**
- ORIGINAL: M12-4 `bae65cc` — candidate M10 result validators in
  `candidates/m10_evaluation.py`.
- SECOND IMPLEMENTATION: M12-5 `161986b` — copy-forwarded into
  `candidates/canonical_m10.py` for candidate-free post-promotion execution.
- PRODUCTION REACHABILITY: M12-5; candidate via `application.py:505`/`2423`,
  canonical via `application.py:636` → `promotion.py:3337`.
- CURRENT: both wired; D1/D2 drift untested.

**F2 — canonical serialization**
- ORIGINAL: M0/M2 `37f3ff3` — `state/hashing.py:canonical_json`/`state_hash`.
- SECOND IMPLEMENTATIONS (incremental): M6B-4A/4C `3c7c708`/`4468a62`
  (`default=str`), M7B/M7C `3f7bbc7`/`9ab9e48` (yagi trio), M10 `89b1d75`
  (motion hashes), M11-2/11-5 `682300b`/`07950cd` (`ensure_ascii` variants),
  M13-3 `ca294e0` (pair policy / verification).
- PRODUCTION REACHABILITY: each copy wired within its own module from its
  introduction commit.
- CURRENT: ~20 copies wired; shared `canonical_json` still owns state hashing.

**F3 — currentness / freshness**
- ORIGINAL: M3 `df584f0` — `dependency/storage.py:get_evidence_freshness`.
- SECOND IMPLEMENTATIONS: M11-5 `07950cd` `StructuralEvidenceCurrentness`;
  M12 `28ac193` `CandidateCurrentness` (verbatim enum copy).
- PRODUCTION REACHABILITY: M11-5 and M12 respectively, concurrent with M3
  freshness.
- CURRENT: all three wired.

**F4 — mesh-spec / mesh-input hashing**
- ORIGINAL: M11-2 `682300b` — `structural/service.py:42`,
  `validation.py:663`, `results.py:1107`, `models.py:698`.
- SECOND IMPLEMENTATION: M11-5 `07950cd` — `structural/evidence.py:464`
  (volatile-key filter) and `evidence_service.py:1515`.
- PRODUCTION REACHABILITY: M11-5 onward; values are cross-compared.
- CURRENT: all wired.

**F5 — FreeCAD runtime identity**
- ORIGINAL: M7A `19f77a3` — `backends/freecad.py:FREECAD_BACKEND_VERSION`.
- SECOND IMPLEMENTATION: M11-2 `682300b` — `structural/runtime.py:FREECAD_IDENTITY`.
- PRODUCTION REACHABILITY: M11-2 onward (M11 provenance verification compares
  STEP `backend_provenance` against `FREECAD_IDENTITY`).
- CURRENT: both wired.

**F6 — `physical_kinematic_root_hash`**
- ORIGINAL: M13-3 `ca294e0` — `models/physical_mechanism.py:35` (canonical model
  authority).
- SECOND IMPLEMENTATION: M13-3 `ca294e0` — `candidates/models.py:58`, **same
  commit** (candidate/canonical split).
- PRODUCTION REACHABILITY: same commit; explicitly cross-compared at
  `candidates/multi_joint_m10_bridge.py:2397`, `:2564`.
- CURRENT: both wired.

**F7 — CAD dimension alias resolution**
- ORIGINAL: M12-4 `bae65cc` — `candidates/cad_realization.py:_DIMENSION_ALIASES`
  (geometry-first, property-first).
- SECOND IMPLEMENTATION: M12-5 `161986b` — `candidates/canonical_cad.py`
  (bare-first, choice-first); extended by M13-2 `664ec3b` in both files.
- PRODUCTION REACHABILITY: M12-5/M13-2 onward.
- CURRENT: both wired; no geometry-agreement gate.

**F8 — proof status / motion bound**
- ORIGINAL: M10 `89b1d75` — `continuous_proof.py:32`, `:145-158`.
- SECOND IMPLEMENTATION: M10 `89b1d75` —
  `multi_joint_continuous_clearance.py:33`, `:466`, **same commit**.
- PRODUCTION REACHABILITY: same commit; two separate proof engines.
- CURRENT: both wired.

**F11 — `analysis.structural` node**
- ORIGINAL: M5.5C `4bc2310` — section tools register
  `evidence_nodes=("analysis.structural",)`.
- SECOND IMPLEMENTATION: M11-5 `07950cd` — `structural/evidence.py:53-55`
  reuses the same node for typed `StructuralEvidencePayload`.
- PRODUCTION REACHABILITY: M11-5 onward, sharing `EvidenceStore`, kind-based
  retrieval, and `config/dependencies.yaml` invalidation.
- CURRENT: both producers wired; structural verifier rejects tool records.

---

## 15. P1/P2 Test-Difference Register

For each P1/P2 finding: whether the duplicated implementations are independently
encoded by tests and whether the tests already describe semantic drift.

**F1**
- TESTS_FOR_ORIGINAL: `tests/unit/test_m12_candidate_m10_service.py`,
  `test_m12_candidate_m10_replay.py`, `test_m12_candidate_evaluation.py`.
- TESTS_FOR_SECONDARY: `tests/unit/test_m12_canonical_m10.py`,
  `test_m12_canonical_reconstruction.py`.
- SHARED_BEHAVIOR_TESTED: request/path/clearance/partition equality;
  collision-witness pair membership; algorithm version; `NOT_PROVEN` retention.
- DIFFERENT_ASSUMPTIONS: candidate pins the discrete sweep constant
  (`test_home_result_requires_the_accepted_discrete_sweep_identity`) and keeps
  the execution-completion status vocabulary; canonical recomputes nested
  partitions/result hashes and checks request/result sweep-version equality
  (`test_home_check_rejects_request_result_sweep_version_mismatch`).
- KNOWN_UNTESTED_DRIFT_SURFACE: D1 (`source_assembly_id`) and D2 (witness
  classification) have no test on either side.

## F1 Remediation Record (post-acceptance)

**Date:** 2026-09-13

This record remediates F1 only. It does not rewrite the accepted historical
finding, alter candidate/canonical M10 stage authority, or remediate F3, F4,
F5, F6, F8, F11, or any P3 finding.

### Shared Kernel

`src/mechcad_harness/candidates/m10_result_validation.py` owns the input-neutral
continuous-result and home-result validation mechanics plus the M10 result-hash
calculation. It defines frozen validation contracts; it does not import candidate
realizations, canonical mechanisms, promotion services, application composition,
or stage outcome models.

`CandidateM10EvaluationService` and `CanonicalM10VerificationService` remain
separate execution stages. Each owns an explicit contract instance and its own
pair-assembly construction, requests, models, outcomes, and callers. Canonical
execution still derives from canonical reconstruction and fresh canonical CAD;
it accepts no candidate M10 result as an execution input.

### D1-D10 Contract Matrix

| Difference | Classification | Preserved contract |
| --- | --- | --- |
| Shared result/request, path, partition, certificate, witness-pair, aggregate, and result-hash validation | SHARED | one neutral kernel |
| D1 continuous `source_assembly_id` | CANDIDATE_ONLY relaxation | candidate validates the assembly hash; canonical validates assembly ID and hash |
| D2 collision-witness classification | CANDIDATE_ONLY strictness | candidate permits only `INTERFERENCE`/`TOUCHING`; canonical does not add that restriction |
| D3 accepted discrete sweep version | CANDIDATE_ONLY strictness | candidate pins the accepted sweep version; canonical retains its model-level request/result equality check |
| D4 model-level result-hash recomputation | CANONICAL_ONLY | canonical proof/home models retain the additional check |
| D5 nested model partition validation | CANONICAL_ONLY | canonical proof/home/outcome models retain the additional checks |
| D6 stage-status vocabulary | STRUCTURALLY_DIFFERENT | unchanged candidate stage versus canonical aggregate vocabulary |
| D7 outcome bindings | STRUCTURALLY_DIFFERENT | unchanged candidate hashes versus canonical embedded scope/inventory/request |
| D8 induced-pair assembly suffix | STRUCTURALLY_DIFFERENT | candidate and canonical assembly identities remain distinct |
| D9 scope proof-service version | STRUCTURALLY_DIFFERENT | candidate-bound scope retains it; canonical scope excludes it |
| D10 result-hash utility | SHARED | one `m10_result_hash` implementation |

No request model, result model, schema version, request hash payload, result hash
payload, or wire format changed. Candidate and canonical M10 request hashes remain
intentionally distinct.

### D1 And D2 Regressions

`tests/unit/test_m12_candidate_m10_service.py` now explicitly verifies:

- D1: a request with the right induced-assembly hash but a forged assembly ID is
  accepted by the candidate contract and rejected by the canonical contract.
- D2: a collision witness with `POSITIVE_CLEARANCE` classification is rejected by
  the candidate contract and accepted by the canonical contract.

### Verification

| Command | Result |
| --- | --- |
| `py -3 -m pytest tests/unit/test_m12_candidate_m10_service.py::test_d1_continuous_source_assembly_id_strictness_is_explicit_per_stage tests/unit/test_m12_candidate_m10_service.py::test_d2_collision_witness_classification_strictness_is_explicit_per_stage -q` | `2 passed` |
| `py -3 -m pytest tests/unit/test_m12_candidate_m10_binding.py tests/unit/test_m12_candidate_m10_service.py tests/unit/test_m12_candidate_m10_replay.py tests/unit/test_m12_canonical_m10.py tests/test_m10_1_continuous_proof.py -q` | `103 passed` |
| broader candidate/promotion matrix | `300 passed` |
| `py -3 -m pytest tests/unit -q` | `2627 passed, 19 skipped, 5 failed` in `382.41s`; failures were four existing README-content assertions and one unrelated untracked Rotator V2 test |
| `py -3 -m pytest tests/ -q` | did not complete before the explicit `3700s` ceiling; three failure markers appeared before timeout, so this run is not recorded as a pass |
| `py -3 -m compileall -q src/mechcad_harness tests` | exit `0` |

A fresh skeptical review found no functional F1 regression, authority crossover,
stage-merging, hash/wire change, D6-D9 regression, or scope expansion. It found
only obsolete imports introduced during extraction; those imports were removed
before the final focused rerun.

**F2**
- TESTS_FOR_ORIGINAL: state/revision hash stability tests.
- TESTS_FOR_SECONDARY: per-module content-hash tests exist, but none compare
  outputs across serializer variants.
- SHARED_BEHAVIOR_TESTED: none across variants.
- DIFFERENT_ASSUMPTIONS: structural variants assume ASCII-only payloads
  (`ensure_ascii` default); shared expects preserved UTF-8; `default=str`
  accepts non-JSON-coercible values.
- KNOWN_UNTESTED_DRIFT_SURFACE: no test hashes a non-ASCII payload through two
  variants and compares bytes.

**F3**
- TESTS_FOR_ORIGINAL: M3 freshness/invalidation tests.
- TESTS_FOR_SECONDARY: structural currentness tests; candidate currentness tests.
- SHARED_BEHAVIOR_TESTED: "current / stale / unavailable" strings, independently.
- DIFFERENT_ASSUMPTIONS: M3 uses transitive graph invalidation;
  structural/candidate use current-pointer equality.
- KNOWN_UNTESTED_DRIFT_SURFACE: no cross-consistency test; precedence
  undocumented.

**F4**
- TESTS_FOR_ORIGINAL: structural service/validation mesh-spec hash tests.
- TESTS_FOR_SECONDARY: M11-5 evidence verification tests.
- SHARED_BEHAVIOR_TESTED: cross-verification on a `MeshSpecification` with no
  volatile fields.
- DIFFERENT_ASSUMPTIONS: the evidence variant strips volatile keys; the others
  do not.
- KNOWN_UNTESTED_DRIFT_SURFACE: no test adds a volatile field and checks
  cross-verification.

**F5**
- TESTS_FOR_ORIGINAL: backend FreeCAD identity/provenance tests.
- TESTS_FOR_SECONDARY: structural provenance-verification tests.
- SHARED_BEHAVIOR_TESTED: literal equality only implicitly (M9/M11 suites pass).
- DIFFERENT_ASSUMPTIONS: none documented.
- KNOWN_UNTESTED_DRIFT_SURFACE: no test asserts the two constants are equal; a
  unilateral bump is caught only by end-to-end fail-closed tests.

**F6**
- TESTS_FOR_ORIGINAL: `physical_mechanism` identity-hash tests.
- TESTS_FOR_SECONDARY: candidate model hash tests; bridge equality tests.
- SHARED_BEHAVIOR_TESTED: the bridge compares the candidate hash against the
  model hash.
- DIFFERENT_ASSUMPTIONS: none currently.
- KNOWN_UNTESTED_DRIFT_SURFACE: no test asserts the two function bodies remain
  byte-equal.

**F7**
- TESTS_FOR_ORIGINAL: `tests/unit/test_m12_candidate_cad_compiler.py`,
  `test_m12_candidate_cad_replay.py` (single `geometry.*` alias).
- TESTS_FOR_SECONDARY: `tests/unit/test_m12_canonical_cad.py`,
  `test_m12_promoted_verification.py` (single choice alias).
- SHARED_BEHAVIOR_TESTED: candidate/canonical identity separation (M12-6
  asserts the hashes differ).
- DIFFERENT_ASSUMPTIONS: candidate property-first/geometry-first; canonical
  choice-first/bare-first.
- KNOWN_UNTESTED_DRIFT_SURFACE: no test supplies two aliases for one dimension;
  no test compares candidate vs canonical dimensions.

**F8**
- TESTS_FOR_ORIGINAL: `continuous_proof` tests.
- TESTS_FOR_SECONDARY: `multi_joint_continuous_clearance` tests.
- SHARED_BEHAVIOR_TESTED: proof-status semantics within each engine.
- DIFFERENT_ASSUMPTIONS: padding constants chosen independently (both `1e-9`
  today).
- KNOWN_UNTESTED_DRIFT_SURFACE: no test asserts enum identity or bound-formula
  equality across the two engines.

**F11**
- TESTS_FOR_ORIGINAL: section-tool Evidence materialization tests.
- TESTS_FOR_SECONDARY: structural Evidence publish/verify tests.
- SHARED_BEHAVIOR_TESTED: node registration by string; freshness/invalidation by
  `kind`.
- DIFFERENT_ASSUMPTIONS: the structural verifier expects
  `StructuralEvidencePayload`; tool records have no equivalent semantic verifier.
- KNOWN_UNTESTED_DRIFT_SURFACE: no test asserts a section-tool record cannot
  satisfy an `analysis.structural` readiness/fulfillment query.

---

## 16. Audit Metadata

- Historical baseline verified: M13-4 `185a304796c17793519fb5f01dbf80cca73ab51e`;
  synthesis `0cbb70e64c2efdc021f15d341bc043b574ff552b`.
- Current accepted production baseline: `b63d010c4ce0cc93fc556c4890606c5eeecb1e08`.
- Production composition root: `src/mechcad_harness/application.py:404` /
  `:775`.
- Production code modified: NO.
- Tests modified: NO.
- Reconstruction modified: NO.
- Unrelated dirty work preserved: YES (`.coverage`, `.superpowers/sdd/*`,
  untracked Rotator V2 audit/plan/test files, `projects/`, and
  `src/mechcad-harness/` left untouched).

---

## 17. F2 Remediation Record (post-acceptance)

Records the authorized F2-only remediation. It does not revise any finding above.

- **Direction executed:** `EXTRACT_NEUTRAL_CANONICAL_SERIALIZATION_CORE` (§9.1).
- **Neutral core:** `src/mechcad_harness/core/canonical.py`
  (`canonical_json_bytes` / `canonical_json_text`), a dependency leaf importing
  only the standard library and preserving the accepted strict byte contract
  (`ensure_ascii=False, sort_keys=True, separators=(",", ":")`).
- **`state/hashing.py:canonical_json`** delegates to the neutral core; its public
  surface and emitted bytes are unchanged.
- **Migrated content-identity serializers:** the strict `json.dumps` sites in
  `models/{physical_pair_policy,multi_joint_verification,physical_mechanism,`
  `structural}.py`, `tools/broker.py`,
  `candidates/{multi_joint_selection,multi_joint_m10_evaluation,canonical_m10,`
  `m10_evaluation,multi_joint_m10_bridge,services}.py`,
  `structural/{models,evidence_models,validation,results,service,`
  `evidence_service,evidence}.py`, `cad_{assembly,program,compilation,analysis}.py`,
  `imported_component.py`, `structural_request.py`, `application.py`,
  `agents/{models,opencode,fake}.py`, and the `yagi_*` / `azimuth_mount_plate.py`
  helpers.
- **Intentionally not migrated:** `artifacts/storage.py` (artifact byte/metadata
  authority); `structural/evidence.py` volatile-key filtering remains local;
  `default=str` sites (`changes/provenance.py`, `agents/constraint_resolution.py`,
  `runs/persistence.py`, `tools/persistence.py`); canonical-record file
  persistence (`state/manager.py`, `dependency/storage.py`); embedded FreeCAD
  script strings and backend manifest/wire serializers (`backends/**`,
  `transient_freecad_measurement.py`, `structural/geometry.py`,
  `analysis_service.py`); and the accepted M13-3P source-byte **frozen** M10
  modules (`multi_joint_kinematics.py`, `multi_joint_pair_scope.py`,
  `multi_joint_collision_sweep.py`, `multi_joint_continuous_path.py`,
  `multi_joint_continuous_clearance.py`) locked by
  `tests/unit/test_m13_3_legacy_goldens.py`.
- **Hash bytes:** all existing accepted/persisted ASCII payload hashes are
  unchanged; consolidation normalizes non-ASCII serialization to the canonical
  UTF-8 contract (the F2 drift fix).
- **Other findings:** this remediation does not close F1/F3/F4/F5/F6/F7/F8/F11.

## 18. F7 Remediation Record (post-acceptance)

**Record date:** 2026-09-13

This appended record documents the authorized current-tree F7 remediation. The
historical F7 finding text above is retained as written and describes the
pre-remediation duplication and reachability evidence; this record does not
rewrite that finding or reclassify any other finding.

- **Shared semantic authority:**
  `src/mechcad_harness/candidates/dimensions.py` owns
  `LEGACY_PLATE_DIMENSION_ALIASES`, `DimensionInput`,
  `ResolvedDimension`, and `resolve_dimensions`. Resolution is scoped by
  `(component_instance_id, semantic_name)` and requires exact equality across
  every supplied alias value.
- **Legacy plate families covered:** `length_mm` uses
  `geometry.length_mm`, `plate_length_mm`, and `length_mm`; `width_mm` uses
  `geometry.width_mm`, `plate_width_mm`, and `width_mm`; `thickness_mm` uses
  `geometry.thickness_mm`, `plate_thickness_mm`, and `thickness_mm`.
- **Alias policy:** aliases are an unordered agreement set, not a precedence
  list. Equal values are accepted and retain deterministic source identities;
  conflicting finite positive millimetre values fail closed.
- **Candidate boundary:** `candidates/models.py` performs the early agreement
  gate. `candidates/cad_realization.py` is a candidate-stage adapter that
  normalizes candidate properties and scoped variables into the shared API;
  resolver conflicts become `CandidateCadIntegrityError` at the existing CAD
  boundary.
- **Canonical boundary:** `candidates/canonical_cad.py` is an independent
  canonical-stage adapter. It collects canonical accepted choices and
  properties into the same shared API and retains resolver-level defense in
  depth; it does not consume candidate CAD records or artifacts.
- **Fixture-search checkpoint:** the accepted, golden, and persisted fixture
  search from the F7 compatibility checkpoint found no authoritative fixture
  containing contradictory aliases for one component instance and semantic
  dimension. Matches were classified as unambiguous single-spelling fixtures,
  generated-part fields, or explicit remediation regressions. This is evidence
  about the searched fixture set, not a compatibility migration or a claim
  that ambiguous persisted authority was repaired.
- **Promotion evidence:** `tests/unit/test_m12_promoted_verification.py::test_promoted_legacy_plate_preserves_candidate_and_canonical_base_dimensions`
  realizes an unambiguous geometry-alias candidate plate, executes the existing
  promoted verification/reconstruction path, realizes canonical CAD, and
  compares only the candidate/canonical `BasePlateOperation` dimensions. It
  intentionally does not compare stage-specific request, realization, or
  assembly hashes.
- **Generated-part evidence:**
  `tests/unit/test_m13_2_candidate_cad_integration.py::test_candidate_and_canonical_generated_shaft_compilation_preserve_parameters_and_identities`
  confirms the existing generated shaft parameters and
  `generated_geometry_definition_identities` through candidate and canonical
  stage adapters without introducing legacy plate aliases or changing M13-2
  generated-part models.
- **Focused test result:**
  `python -m pytest tests/unit/test_m12_promoted_verification.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m13_2_candidate_cad_integration.py tests/unit/test_m13_2_promotion_canonical_roundtrip.py -q`
  — **132 passed in 62.45s** after the final fix wave. The requested `pytest
  ... -q` spelling was not available as a command in the execution environment;
  `python -m pytest` ran the equivalent suite.
- **Earlier final fix-wave regression result:**
  `python -m pytest tests/unit/test_f7_dimension_resolution.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py tests/unit/test_m12_promoted_verification.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m13_2_candidate_cad_integration.py tests/unit/test_m13_2_promotion_canonical_roundtrip.py -q`
  — **236 passed in 71.23s**. This covers the resolver, candidate adapters and
  replay, canonical CAD and M10, promotion/canonical roundtrip, and promoted
  verification boundaries after the fix wave.
- **Final fix-wave regression result after the incomplete canonical-input
  regression:**
  `python -m pytest tests/unit/test_f7_dimension_resolution.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_cad_replay.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py tests/unit/test_m12_promoted_verification.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m13_2_candidate_cad_integration.py tests/unit/test_m13_2_promotion_canonical_roundtrip.py -q`
  — **237 passed in 72.07s**. This covers the same resolver, candidate
  adapters and replay, canonical CAD and M10, promotion/canonical roundtrip,
  and promoted verification boundaries, including the final canonical
  incomplete-input regression.
- **Excluded findings:** this record does not resolve or reclassify F1, F2, F3,
  F4, F5, F6, F8, F11, or any P3/INFO finding. M13-2 generated-part behavior
  remains unchanged.

## 19. F11 Remediation Record (post-acceptance)

**Record date:** 2026-09-13

This appended record documents the accepted F11 remediation. The historical F11
finding above remains unchanged, including its P2 classification and its account
of the former `analysis.structural` node overload. This record does not begin or
resolve F3, and it does not modify `docs/reconstruction/**`.

### Distinct Evidence Authorities

- M5.5C section geometry, warping, and preliminary section-engineering tools
  publish generic ToolBroker Evidence at `analysis.section`. The section family
  covers `SectionGeometryResult`, `SectionWarpingResult`, and complete
  `PreliminarySectionEngineeringResult` outputs; it is not typed structural-FEA
  authority.
- M11 typed structural-FEA Evidence remains at `analysis.structural`, with
  `EvidenceSubject.STRUCTURAL_ANALYSIS` and the existing
  `analysis.structural.convergence` node. `StructuralEvidenceVerifier` remains
  typed-only and rejects generic section-tool Evidence.
- The two families remain separately bound records in the shared EvidenceStore;
  matching one node cannot satisfy readiness for the other authority.

### Compatibility Decision

The accepted policy is a clean namespace boundary for newly produced records.
No repository-managed legacy Evidence record required migration, and no runtime
classification or reclassification heuristic was added. The generic loader may
parse an old record where the schema permits it, but an old generic
`analysis.structural` section-like record is not treated as new section
Evidence or as typed structural-FEA Evidence.

M11 compatibility is preserved: `analysis.structural`, the typed subject
discriminator, the structural payload semantic hash, and deterministic typed
Evidence IDs remain unchanged. New section-tool Evidence IDs intentionally use
the new `analysis.section` node identity.

### Dependency And Invalidation Separation

- `/materials/*` conservatively invalidates both `analysis.section` and
  `analysis.structural`, because section engineering and structural FEA both
  consume material authority.
- `/structural_analysis_definitions/*` invalidates only
  `analysis.structural`; it cannot stale section-tool Evidence.
- Existing structural edges remain unchanged:
  `analysis.loads -> analysis.structural -> validation.structural` and
  `analysis.structural -> analysis.structural.convergence`.
- No edge was added from `analysis.section` to structural validation or
  convergence. The material rule is family-level conservative invalidation, not
  per-ToolResult dependency precision.

### Verification And Review Evidence

| Evidence | Result |
| --- | --- |
| Focused F11 gate: `python -m pytest tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_runs.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q` | `181 passed, 2 skipped` |
| Full unit suite: `python -m pytest tests/unit -q` | `2635 passed, 19 skipped, 5 failed`; the five failures match the accepted unrelated baseline: four README documentation-contract failures and one untracked Rotator V2 candidate-inventory failure |
| Ordinary repository suite: `python -m pytest -q --durations=20` | Timed out at the 1800-second tool ceiling after reaching 80%; reported failures matched the same waived baseline, so this is not recorded as a green full-suite run |
| Production compile check | `python -m compileall -q src/mechcad_harness/tools/sections.py src/mechcad_harness/tools/section_engineering.py` exited `0` |
| Fresh independent review | `PASS_WITH_NOTES`; no F11 defect, authority crossover, M11 identity change, or scope expansion found. Notes were limited to optional `sectionproperties` skips and unrelated dirty worktree files. |
| Implementation commit | `1806f34d43798b25b04fcd94c88d2e19bfd5d886` |

**F11 STATUS:** ACCEPTED remediation. **F3 STATUS:** UNRESOLVED; no F3
remediation was started by this change.

The F3 status in this F11 record is scoped to that earlier remediation and is
historical, not the current-tree status. The appended F3 post-acceptance record
below resolves F3 for the current tree.

## 20. F4 Remediation Record (post-acceptance)

**Record date:** 2026-09-13

This appended record documents the accepted F4 remediation. The historical F4
finding, timeline, and evidence above remain unchanged. This record does not
resolve F1, F2, F3, F5, F6, F7, F8, F11, or any P3/INFO finding.

- **Mesh-specification authority:** `src/mechcad_harness/structural/models.py::mesh_specification_hash`.
- **Mesh-input authority:** `src/mechcad_harness/structural/models.py::mesh_input_hash`.
- **Accepted commit:** `d398e07`.
- **Current behavior:** the former 4+2 semantic implementations are reduced to
  one mesh-specification and one mesh-input authority. Producers and verifiers
  continue to recompute through these model-layer functions.
- **Compatibility:** existing digest bytes remain unchanged, including the
  accepted characterization vectors and persisted structural bindings.
- **Focused evidence:** `python -m pytest tests/unit/test_structural_models.py tests/unit/test_structural_service.py tests/unit/test_structural_results.py tests/unit/test_structural_evidence_verifier.py -q` produced `372 passed`.
- **Full-unit evidence:** `python -m pytest tests/unit -q` produced `2635 passed, 19 skipped, 5 failed`; the five failures were the accepted unrelated baseline of four README documentation-contract failures and one untracked Rotator V2 candidate-inventory failure.
- **Independent review:** **PASS_WITH_NOTES**; no blocking authority, digest-compatibility, producer/verifier, or scope regression was found.

**F4 STATUS:** ACCEPTED remediation; the original F4 finding remains the
historical pre-remediation record.

## 21. F5 Remediation Record (post-acceptance)

**Record date:** 2026-09-13

This appended record documents the accepted F5 remediation. The historical F5
finding, timeline, and evidence above remain unchanged. This record does not
resolve F1, F2, F3, F4, F6, F7, F8, F11, or any P3/INFO finding.

- **FreeCAD provenance identity authority:** `src/mechcad_harness/backends/models.py::FREECAD_PROVENANCE_IDENTITY`.
- **Accepted commit:** `3a1fdfd`.
- **Current behavior:** structural runtime discovery derives its compatibility
  view from the backend model authority; the FreeCAD backend no longer owns a
  second independent provenance identity value.
- **Compatibility:** accepted FreeCAD provenance bytes remain unchanged.
- **Focused evidence:** `python -m pytest tests/unit/test_structural_runtime.py -q` produced `7 passed`.
- **Full-unit evidence:** `python -m pytest tests/unit -q` produced `2635 passed, 19 skipped, 5 failed`; the five failures were the accepted unrelated baseline of four README documentation-contract failures and one untracked Rotator V2 candidate-inventory failure.
- **Independent review:** **PASS_WITH_NOTES**; no blocking identity, provenance-byte, structural-runtime, or scope regression was found.

**F5 STATUS:** ACCEPTED remediation; the original F5 finding remains the
historical pre-remediation record.

## 22. F6 Remediation Record (post-acceptance)

**Record date:** 2026-09-13

This appended record documents the accepted F6 remediation. The historical F6
finding, timeline, and evidence above remain unchanged. This record does not
resolve F1, F2, F3, F4, F5, F7, F8, F11, or any P3/INFO finding.

- **Physical-root hash authority:** `src/mechcad_harness/models/physical_mechanism.py::physical_kinematic_root_hash`.
- **Accepted commit:** `773da15`.
- **Current behavior:** `candidates/models.py` imports and re-exports the same
  function rather than defining a second candidate hash implementation.
- **Compatibility:** physical-root hash bytes remain unchanged, and identity
  checks continue to use the canonical model-layer function.
- **Focused evidence:** `python -m pytest tests/unit/test_m13_3_physical_primitives.py tests/unit/test_m13_3_bridge_compiler.py -q` produced `41 passed`.
- **Full-unit evidence:** `python -m pytest tests/unit -q` produced `2635 passed, 19 skipped, 5 failed`; the five failures were the accepted unrelated baseline of four README documentation-contract failures and one untracked Rotator V2 candidate-inventory failure.
- **Independent review:** **PASS_WITH_NOTES**; no blocking hash-byte, import/re-export, bridge, or scope regression was found.

**F6 STATUS:** ACCEPTED remediation; the original F6 finding remains the
historical pre-remediation record.

## 23. F3 Remediation Record (post-acceptance)

**Record date:** 2026-09-13

The historical F3 finding above remains unchanged as the pre-remediation audit
record. The current-tree correction is that the duplicated implementation was
the three-value structural/candidate status vocabulary, not an equivalent
pointer evaluator: structural currentness requires exact current-pointer tuple
equality, while candidate currentness may remain current across a newer revision
when every explicit consumed-authority path remains equal.

`core/currentness.py::Currentness` is the standard-library-only neutral status
authority. `StructuralEvidenceCurrentness` and `CandidateCurrentness` are direct
re-export aliases of that one enum. `EvidenceFreshness` remains the independent
M3 graph/history vocabulary and no evaluator's semantics changed.

F11's `analysis.section` / `analysis.structural` separation remains retained:
section-tool Evidence uses `analysis.section`, while typed structural-FEA
Evidence remains at `analysis.structural`; their records, readiness, and
verification authorities remain distinct.

### Verification Evidence

| Command | Result |
| --- | --- |
| `python -m pytest tests/unit/test_core_currentness.py tests/unit/test_dependency.py tests/unit/test_runs.py tests/unit/test_agent_authoritative_context.py tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_revolute_drive_service.py -q` | `237 passed, 2 skipped in 33.06s` |
| `python -m compileall -q src/mechcad_harness tests` | exit code `0`, no output |
| `git diff --check` | diagnostics only for unrelated pre-existing worktree changes: `.superpowers/sdd/progress.md:60-61,87,89-92` and `.superpowers/sdd/task-1-brief.md:33` |

The two skipped tests were optional-dependency skips: structural profile is not
installed in `tests/unit/test_section_tools.py:38` and
`tests/unit/test_section_warping_tools.py:37`. No live CAD/solver invocation was
run. No implementation commit was created or separately authorized; commits:
none.

**F3 STATUS:** ACCEPTED remediation record for this bounded current-tree
correction; it is not an independent final acceptance marker. The original F3
finding remains the historical pre-remediation record.

## 24. F8 Post-Review Correction / Option D Disposition

**Record date:** 2026-09-13

This is an appended post-review correction to the F8 finding. The original F8
finding, its P2 classification, timeline, and pre-disposition evidence above
remain unchanged. This record does not begin F3 remediation, supersede the
M13-3P compatibility freeze, or begin any P3 finding.

### Approved Direction

Option D was approved: no production consolidation is performed. The accepted
M13-3P source-byte contract remains in force, and
`src/mechcad_harness/multi_joint_continuous_clearance.py` remains byte-frozen.
Approval source: the explicit user instruction for this F8 execution on
2026-09-13. This is a bounded remediation disposition, not a new independent
acceptance marker.

The current F8 surfaces are reclassified as follows:

- The status classes are **separately typed compatibility vocabularies**. Their
  members have equal wire strings (`verified_clear`, `collision_witness`, and
  `not_proven`), but the Python enum classes and members are not identical. Each
  proof engine retains its own public enum class and local `is` checks.
- The bound calculations are **distinct semantic contracts**, not one duplicated
  motion-bound authority. M10-1 uses
  `2*R*sin(min(abs(delta), pi)/2) + 1e-9*(1+abs(R))`; M10-4 accumulates
  `2*R*sin(min(delta, pi)/2) + 1e-9` once per influencing joint and then sums
  endpoint bounds. The shared chord term does not make the complete primitives
  interchangeable.

### Compatibility Evidence

- New characterization coverage is in
  `tests/unit/test_f8_proof_authority_characterization.py`.
- The tests cover zero, small, `pi/2`, `pi`, and greater-than-`pi` deltas,
  exact padding formulas, equal wire strings, distinct enum type identity, and
  status serialization round trips.
- `tests/unit/test_m13_3_legacy_goldens.py` passed 3 tests, including the
  protected source digest assertion.
- `tests/unit/test_m13_3p_legacy_goldens.py` passed 10 tests, including v1
  M10-4 JSON, record digests, and result hashes.
- The frozen file digest remains
  `sha256:66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5`.
- No F8 production source, frozen module, legacy golden constant, request/result
  hash, public enum class, proof padding semantic, or reconstruction record was
  modified.

### Current F8 Disposition

**F8 STATUS:** CLOSED AS OPTION D / INTENTIONAL COMPATIBILITY AND DISTINCT
SEMANTICS. The historical finding remains retained as pre-disposition evidence;
the current ownership map records the corrected authority boundary.

## 25. Current Finding Disposition Synchronization

This section is the current status register for the accepted production baseline
`b63d010c4ce0cc93fc556c4890606c5eeecb1e08`. The original finding entries,
pre-remediation recommendations, and remediation records above remain retained
as temporal evidence. They are not rewritten as though the findings never
existed.

| Finding | Accepted final disposition | Current status | Accepted implementation commit(s) | Current synchronization note |
| --- | --- | --- | --- | --- |
| F9 | `KEEP_INTENTIONAL` | RETAINED | — | Superseded v1 surfaces remain intentionally retained; no active remediation. |
| F10 | `IMPLEMENTED / CLOSED` | CLOSED | `93167dc58406d273c8014a203dfeea8354317abc`; integrated at `8e8aa3e9bcacde9cead9fcb53a8027c2df324ceb` | Unused M6B-4C workflow and duplicate anchor-map route were retired; the active request materializer remains authoritative. |
| F12 | `IMPLEMENTED / CLOSED` | CLOSED | `a2b29e41522ed0e1db747c9a261c727c3f928e27`; integrated at `8e8aa3e9bcacde9cead9fcb53a8027c2df324ceb` | Explicit canonical multi-joint application invocation now delegates to the existing verifier without auto-running during promotion or creating a second result authority. |
| F13 | `DEFER_LOW_RISK` | DEFERRED | — | The stray duplicate artifact remains deferred and is not treated as resolved. |
| F14 | `KEEP_INTENTIONAL` | RETAINED | — | Test-only and legacy surfaces remain intentionally retained; no active remediation. |
| F16 | `DEFER_LOW_RISK` | DEFERRED | — | Path-matcher overlap remains deferred and is not treated as resolved. |
| F17 | `KEEP_INTENTIONAL` | RETAINED | — | Legacy task-model exports remain intentionally retained; no active remediation. |
| F19 | `DEFER_LOW_RISK` | DEFERRED | — | The duplicate pair-classification enums remain deferred and are not treated as resolved. |
| F20 | `KEEP_INTENTIONAL` | RETAINED | — | Equivalent transform/quaternion primitives remain intentionally retained; no active remediation. |
| F21 | `IMPLEMENTED / CLOSED` | CLOSED | `b63d010c4ce0cc93fc556c4890606c5eeecb1e08` | Analytical-observation construction is centralized; independent provenance/artifact verification and M11 handoff re-validation remain intentionally separate. |

### Current Gate Summary

- `P0_REMAINING`: NONE.
- `P1_REMAINING`: NONE.
- `P2_REMAINING`: NONE.
- `ACTIVE_P3_REMEDIATIONS`: NONE.
- `P3_DEFERRED`: F13, F16, F19.
- `CURRENT_ACCEPTED_BASELINE_RECORDED`: YES (`b63d010c4ce0cc93fc556c4890606c5eeecb1e08`).
