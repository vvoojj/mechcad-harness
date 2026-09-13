# MechCAD Capability Ownership Map

Companion artifact to
[`MECHCAD_LOGIC_DUPLICATION_AUDIT.md`](MECHCAD_LOGIC_DUPLICATION_AUDIT.md).

This map records, for each major capability, the intended current owner and any
other implementations that appear to own the same responsibility. It is an
audit artifact, not normative architecture and not a historical record.

- `ORIG` = original milestone / commit that first introduced the capability.
- `CURRENT OWNER` = the implementation actually reachable from the production
  composition root (`ProductionApplication.create()`, `application.py:775`).
- `OTHER IMPLS` = additional implementations of the same / overlapping
  responsibility.
- `STATUS` uses the audit vocabulary from section 9 of the task:
  `SINGLE_AUTHORITY`, `LEGITIMATE_LAYERING`, `LEGITIMATE_ADAPTER_VARIANTS`,
  `INTENTIONAL_SUPERSESSION`, `LEGACY_RESIDUE`, `BRIDGE_RESIDUE`,
  `SEMANTIC_DUPLICATION`, `AUTHORITY_CONFLICT`, `POSSIBLE_DUPLICATION`,
  `UNKNOWN`.
- `FIND` references findings in the main report (`F1`…`F21`). Every finding ID
  below refers to exactly one semantic finding; `—` means the row's
  duplication status is explained directly in the main report or its
  final "Legitimate Similarity / False Positives" table.

Verification convention: `WIRED` = reachable from production composition;
`TESTS` = only test reachable; `DEAD` = neither.

## A. State / change / run authority (M0–M4, M8B)

| # | CAPABILITY | ORIG | CURRENT OWNER | OTHER IMPLS | FIND | STATUS |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Canonical `DesignState` | M0 `7185351` | `models/design.py`, `state/manager.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 2 | Immutable revisions | M1 `37f3ff3` | `state/manager.py:create_revision` (WIRED) | — | — | SINGLE_AUTHORITY |
| 3 | ChangeSet / proposal mutation | M2 `37f3ff3` | `changes/engine.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 4 | Revision hashing / canonical JSON | M0/M2 `37f3ff3` | `core/canonical.py` (WIRED); `state/hashing.py:canonical_json` delegates to it | intentional separate serializers for artifact persistence, `default=str` records, and frozen wire contracts | F2 | SINGLE_AUTHORITY |
| 5 | Dependency invalidation | M3 `df584f0` | `dependency/graph.py:impact`, `dependency/storage.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 6 | Dependency path matching | M2/M3 | `dependency/graph.py:path_matches` (WIRED) | `changes/ownership.py`, `changes/engine.py:_segments` | F16 | POSSIBLE_DUPLICATION |
| 7 | Evidence freshness | M3 `df584f0` | `dependency/graph.py:impact`, `dependency/storage.py:get_evidence_freshness` (WIRED) | structural strict-pointer currentness and candidate source-relevance currentness are distinct layered contracts | F3 | LEGITIMATE_LAYERING |
| 8 | Run control / status machine | M4 `a958c397` | `runs/controller.py`, `runs/models.py` (WIRED) | legacy `models/task.py:TaskStatus`/`AgentTask` | F17 | LEGACY_RESIDUE |
| 9 | Production orchestration | M8B-1 `8079c57` | `application.py:ProductionApplication` (WIRED) | — | — | SINGLE_AUTHORITY |

## B. Tool / agent / mediation (M5–M6)

| # | CAPABILITY | ORIG | CURRENT OWNER | OTHER IMPLS | FIND | STATUS |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | Tool Broker / registry | M5 `6cbade0` | `tools/broker.py`, `tools/registry.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 11 | Backend identity / provenance | M5.5A/B `6cbade0`/`b0d77e1` | `backends/models.py:FREECAD_PROVENANCE_IDENTITY`, `backends/provenance.py:provenance_from_identity` (WIRED) | distinct non-FreeCAD backend identities and adapters; no duplicate FreeCAD provenance authority | F5, F21 | LEGITIMATE_ADAPTER_VARIANTS (F5 resolved; F21 remains) |
| 12 | Material / section / warping | M5.5C `4bc2310` | `backends/section_properties.py`, `tools/sections.py`, `tools/section_engineering.py` (WIRED; generic Evidence at `analysis.section`) | — | F11 | SINGLE_AUTHORITY |
| 13 | Agent gateway | M6A-1 `e4f4c00` | `agents/gateway.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 14 | OpenCode integration | M6A-2B `60ccc2d` | `agents/opencode.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 15 | Tool-mediated reasoning / roundtrip | M6B `928be44` | `agents/roundtrip.py`, `agents/tool_mediation.py`, `tools/evidence.py` (WIRED) | — | — | LEGITIMATE_LAYERING |
| 16 | Constraint discovery / anchor map | M6B-3 `53fa6c4` | `agents/constraint_requests.py` (WIRED) | `agents/constraint_resolution_application.py:_anchor_for` | F10 | POSSIBLE_DUPLICATION |
| 17 | Constraint resolution workflow | M6B-4C `4468a62` | — (no production caller) | `agents/constraint_resolution_workflow.py`, `..._application.py` (TESTS) | F10 | LEGACY_RESIDUE |

## C. CAD / assembly / geometry (M7A–M9, M10-MULTI-SHAPE)

| # | CAPABILITY | ORIG | CURRENT OWNER | OTHER IMPLS | FIND | STATUS |
| --- | --- | --- | --- | --- | --- | --- |
| 18 | Generic CAD / FreeCAD backend | M7A-1/2A `19f77a3` | `backends/freecad.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 19 | Rigid assembly foundation | M7A-2B `19f77a3` | `backends/freecad_assembly.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 20 | Exact clearance primitive | M7A-2C `19f77a3` | `transient_freecad_measurement.py` (WIRED) | `cad_analysis.py` (TESTS) | F14, F15 | LEGACY_RESIDUE |
| 21 | STEP import / trusted artifact | M8C-2/M9-2 | `imported_component.py:resolve_imported_component` (WIRED) | `backends/freecad_assembly.py`, `transient_freecad_measurement.py` re-check subsets | F15 | POSSIBLE_DUPLICATION |
| 22 | `DesignSpec`→`CadPartProgram` compilation | M8C-1 `6c6f46c` | `cad_compilation.py` (WIRED) | `azimuth_mount_plate.py`, `yagi_carrier_packaging.py` (TESTS) | F14 | LEGITIMATE_LAYERING + LEGACY_RESIDUE |
| 23 | Generic single-axis kinematic sweep | M7C-1 `9ab9e48` | `kinematic_sweep.py` (WIRED, candidate M10 path) | — | F9 | SINGLE_AUTHORITY |
| 24 | Artifact persistence / byte hashing | M7A `19f77a3` | `artifacts/storage.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 25 | CAD / assembly manifest hashing | M7A/M7B | `cad_manifest.py`, `cad_assembly_manifest.py` (WIRED) | — | F18 | LEGITIMATE_LAYERING |
| 26 | Generated mechanical-part CAD | M13-2 `664ec3b` | `generated_part_cad.py` → `backends/freecad.py` (WIRED) | — | — | SINGLE_AUTHORITY (correct extension) |

## D. Motion / kinematics / collision (M10, M13-3P, M13-3)

| # | CAPABILITY | ORIG | CURRENT OWNER | OTHER IMPLS | FIND | STATUS |
| --- | --- | --- | --- | --- | --- | --- |
| 27 | Multi-joint forward kinematics | M10-2 `89b1d75` | `multi_joint_kinematics.py:evaluate` (WIRED) | V1 / V2 schemas in same module | — | INTENTIONAL_SUPERSESSION (see main report §6) |
| 28 | Multi-joint exact discrete collision sweep | M10-3 `89b1d75` | `multi_joint_collision_sweep.py` (WIRED) | V1/V2 orchestration bodies ~130 duplicated lines | F9 | INTENTIONAL_SUPERSESSION + LEGACY_RESIDUE |
| 29 | Continuous single-axis clearance proof | M10-1 `89b1d75` | `continuous_proof.py` (WIRED) | status enum duplicated | F8 | SEMANTIC_DUPLICATION |
| 30 | Continuous multi-joint path proof | M10-4 `89b1d75` | `multi_joint_continuous_clearance.py` (WIRED) | V1/V2 schemas; one proof engine | — | LEGITIMATE_ADAPTER_VARIANTS (see main report §6) |
| 31 | Reach-bound derivation | M10-4 `89b1d75` | `multi_joint_continuous_path.py` (WIRED) | V1/V2 | — | INTENTIONAL_SUPERSESSION (see main report §6) |
| 32 | Motion-bound math (`2R·sin(Δ/2)+pad`) | M10 `89b1d75` | `continuous_proof.py:145-158` (WIRED) | inline copy in `multi_joint_continuous_clearance.py:466` | F8 | SEMANTIC_DUPLICATION |
| 33 | Exact transient measurement provider | M7C1/M10 `9ab9e48`/`89b1d75` | `transient_freecad_measurement.py` (WIRED) | `cad_analysis.py` (TESTS) | F15 | SINGLE_AUTHORITY (live) |
| 34 | Rigid-body constituent groups (M10 v2) | M13-3P `f3ab0c7` | `multi_joint_pair_scope.py`, v2 schemas (WIRED) | — | — | SINGLE_AUTHORITY |
| 35 | Physical pair classification | M12-5 / M13-3 | `models/physical_pair_policy.py:PhysicalPairClassification` (WIRED) | `candidates/canonical_m10.py:CanonicalM10PairClassification` | F19 | POSSIBLE_DUPLICATION |
| 36 | `physical_kinematic_root_hash` | M13-3 `ca294e0` | `models/physical_mechanism.py:physical_kinematic_root_hash` (WIRED) | `candidates/models.py` imports/re-exports the same function | F6 | SINGLE_AUTHORITY |
| 37 | FK/transform primitives | M7C-1 / M10 / M13-1/2 | `multi_joint_kinematics.py:transform_*` (WIRED) | `models/quaternion.py`, `models/generated_placement.py:compose_poses` | F20 | SEMANTIC_DUPLICATION (low risk) |

## E. Structural / FEA (M11)

| # | CAPABILITY | ORIG | CURRENT OWNER | OTHER IMPLS | FIND | STATUS |
| --- | --- | --- | --- | --- | --- | --- |
| 38 | Structural authority model | M11-2 `682300b` | `structural/models.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 39 | Structural FreeCAD geometry adapter / region resolver | M11-2 `682300b` | `structural/geometry.py` (WIRED) | — | F15 | LEGITIMATE_ADAPTER_VARIANTS |
| 40 | Gmsh mesh generation / MSH parsing | M11-3 `682300b` | `structural/mesh.py` (WIRED) | strict verifier `structural/results.py:_parse_verified_msh` | — | INTENTIONAL_INDEPENDENT_VERIFIER (divergent subtype handling) |
| 41 | CalculiX solver execution | M11-3 `682300b` | `structural/solver.py` (WIRED) | stray untracked duplicate `src/mechcad-harness/.../solver.py` | F13 | SINGLE_AUTHORITY + DEAD artifact |
| 42 | FRD/DAT parsing / result interpretation | M11-4 `682300b` | `structural/results.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 43 | Structural deck / load lowering | M11-3 `682300b` | `structural/deck.py` (WIRED) | independent verifier in `structural/results.py` | — | INTENTIONAL_INDEPENDENT_VERIFIER |
| 44 | Structural Evidence publish/verify | M11-5 `07950cd` | `structural/evidence_service.py` (WIRED) | duplicate artifact-read/verify | F4, F21 | POSSIBLE_DUPLICATION (F21 only; F4 resolved) |
| 45 | Structural Evidence currentness | M11-5 `07950cd` | `structural/evidence_service.py:currentness` plus `core/currentness.py:Currentness` (WIRED) | candidate source-relevance evaluator shares status vocabulary only | F3 | SINGLE_AUTHORITY |
| 46 | Mesh specification / input hashing | M11-2/M11-5 | `structural/models.py:mesh_specification_hash`, `structural/models.py:mesh_input_hash` (WIRED) | — | F4 | SINGLE_AUTHORITY |
| 47 | FreeCAD runtime identity | M7A / M11-2 | `backends/models.py:FREECAD_PROVENANCE_IDENTITY` (WIRED) | `structural/runtime.py:FREECAD_IDENTITY` is a derived compatibility view | F5 | SINGLE_AUTHORITY |
| 48 | `analysis.structural` dependency node / typed FEA Evidence | M11-5 `07950cd` | `structural/evidence.py:EvidenceSubject.STRUCTURAL_ANALYSIS`, `structural/evidence_service.py` (WIRED; typed Evidence at `analysis.structural`) | — | F11 | SINGLE_AUTHORITY |

## F. Candidate / promotion (M12–M13)

| # | CAPABILITY | ORIG | CURRENT OWNER | OTHER IMPLS | FIND | STATUS |
| --- | --- | --- | --- | --- | --- | --- |
| 49 | Candidate authority / realization | M12-2/3 `28ac193` | `candidates/models.py`, `candidates/services.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 50 | Candidate CAD realization | M12-4 `bae65cc` | `candidates/dimensions.py` (WIRED, shared semantic authority) | `candidates/cad_realization.py` and `candidates/canonical_cad.py` (WIRED, stage-specific adapters) | F7 | LEGITIMATE_ADAPTER_VARIANTS (shared dimension resolution) |
| 51 | Candidate M10 evaluation | M12-4 `bae65cc` | `candidates/m10_evaluation.py` (WIRED; candidate-stage contract) | `candidates/m10_result_validation.py` shared kernel; `candidates/canonical_m10.py` separate canonical stage | F1 | LEGITIMATE_LAYERING |
| 52 | Candidate comparison / selection | M12-4 `bae65cc` | `candidates/comparison.py`, `candidates/selection.py` (WIRED) | `candidates/multi_joint_selection.py` (WIRED, distinct family) | — | LEGITIMATE_LAYERING |
| 53 | Promotion / canonical rebind | M12-5 `161986b` | `candidates/promotion.py`, `candidates/canonical_mechanism.py` (WIRED) | `candidates/promotion_artifacts.py` (post-apply verify) | — | SINGLE_AUTHORITY + independent verifier |
| 54 | Canonical M10 verification | M12-5 `161986b` | `candidates/canonical_m10.py` (WIRED; canonical-stage contract) | `candidates/m10_result_validation.py` shared kernel; `candidates/m10_evaluation.py` separate candidate stage | F1 | LEGITIMATE_LAYERING |
| 55 | M11 handoff eligibility | M12-5 `161986b` | `candidates/m11_handoff.py` (WIRED) | partial re-validation of `models/structural.py` | F21 | POSSIBLE_DUPLICATION |
| 56 | Supplied-component interface authority | M13-1 `f6d8124` | `models/supplied_component_interface.py` (WIRED) | — | — | SINGLE_AUTHORITY |
| 57 | Candidate/canonical multi-joint M10 bridge | M13-3 `ca294e0` | `candidates/multi_joint_m10_bridge.py` (WIRED via service) | single shared lowering core | — | SINGLE_AUTHORITY |
| 58 | Multi-joint canonical M10 verification | M13-3 `ca294e0` | `CanonicalMultiJointM10VerificationService` (`application.py:637`) | no `src/` caller (TESTS) | F12 | LEGACY_RESIDUE (composed-but-unused) |
| 59 | Multi-joint promotion Evidence contract | M13-4E `185a304` | `candidates/promotion_artifacts.py` (WIRED) | legacy M12-5 manifest family | F18 | INTENTIONAL_SUPERSESSION |
| 60 | Promotion manifest verification | M12-5/M13-4E | `candidates/promotion_artifacts.py`, `candidates/promotion.py` (WIRED) | two manifest families | F18 | INTENTIONAL_SUPERSESSION |

## Summary counts

Counts are per row by its **primary (first-listed) status**; some rows carry a
secondary status noted in the row (e.g. #22, #28). This differs from the main
report's `LEGACY_RESIDUES = 10`, which counts P3 **findings**, not rows.

| Status | Count |
| --- | --- |
| SINGLE_AUTHORITY | 29 |
| LEGITIMATE_LAYERING | 7 |
| LEGITIMATE_ADAPTER_VARIANTS | 4 |
| INTENTIONAL_SUPERSESSION | 5 |
| INTENTIONAL_INDEPENDENT_VERIFIER | 2 |
| SEMANTIC_DUPLICATION | 3 |
| POSSIBLE_DUPLICATION | 6 |
| AUTHORITY_CONFLICT (latent/overload) | 0 |
| LEGACY_RESIDUE | 4 |
| UNKNOWN | 0 |

Total rows: 60.

## Finding cross-reference

| Finding | Map rows citing it |
| --- | --- |
| F1 | 51, 54 |
| F2 | 4 |
| F3 | 7, 45 |
| F4 | 44, 46 |
| F5 | 11, 47 |
| F6 | 36 |
| F7 | 50 |
| F8 | 29, 32 |
| F9 | 23, 28 |
| F10 | 16, 17 |
| F11 | 12, 48 |
| F12 | 58 |
| F13 | 41 |
| F14 | 20, 22 |
| F15 | 20, 21, 33, 39 |
| F16 | 6 |
| F17 | 8 |
| F18 | 25, 59, 60 |
| F19 | 35 |
| F20 | 37 |
| F21 | 11, 44, 55 |

Rows with `—` have no finding ID because their similarity is intentional and
documented in the main report's false-positive table (§6) or they are a
single-authority capability.
