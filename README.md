# MechCAD Harness

MechCAD is a general-purpose, deterministic, provenance-aware mechanical-engineering
harness. It converts authoritative requirements into verified engineering state,
derived geometry and analysis, and reproducible evidence while preserving
ownership, revision history, and fail-closed validation.

This README describes **current** system state. Per-milestone history lives in the
accepted [historical reconstruction](docs/reconstruction/README.md).

## Documentation

Start with [`docs/README.md`](docs/README.md) for task-sized context bundles.

- Normative architecture: [`docs/architecture/`](docs/architecture/) —
  [Project Overview](docs/architecture/MECHCAD_PROJECT_OVERVIEW.md),
  [System Contract](docs/architecture/MECHCAD_SYSTEM_CONTRACT.md),
  [Capability Matrix](docs/architecture/MECHCAD_CAPABILITY_MATRIX.md),
  [Runtime Flow](docs/architecture/MECHCAD_RUNTIME_FLOW.md), and
  [Subsystem Contracts](docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md).
- Implemented capability inventory: [MECHCAD_IMPLEMENTED_CAPABILITIES.md](docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md).
- Accepted system / live audits: [`docs/audit/`](docs/audit/).
- Accepted historical reconstruction: [`docs/reconstruction/README.md`](docs/reconstruction/README.md) —
  [Project History](docs/reconstruction/PROJECT_HISTORY.md),
  [Capability Evolution](docs/reconstruction/CAPABILITY_EVOLUTION.md),
  [Milestone Ledger](docs/reconstruction/MILESTONE_LEDGER.md),
  [Milestone Catalog](docs/reconstruction/MILESTONE_CATALOG.json), and
  [Unresolved Gaps](docs/reconstruction/UNRESOLVED_GAPS.md).

## Current Accepted Capability Baseline

The current accepted product baseline reaches **M13-4** at commit
`185a304796c17793519fb5f01dbf80cca73ab51e`, with acceptance marker
`M13_4_INDEPENDENT_FINAL_ACCEPTED`. Every later commit through the reconstruction
synthesis `0cbb70e` is documentation only.

- **Deterministic substrate (M0–M4).** Canonical `DesignState`; immutable hashed
  revisions; `ChangeProposal` → `ChangeSet` → `ChangeEngine` mutation with
  stale-base, ownership, operation, and resulting-state validation; dependency
  invalidation and Evidence freshness; run/task control.
- **Tool, provider, and reasoning boundaries (M5–M6).** Exact-version
  `ToolRegistry`/`ToolBroker`; backend identity/health/provenance; narrow
  gear, material, and section providers; agent gateway; `FakeAgentAdapter` and the
  OpenCode transport; bounded `mechcad-transmission` reasoning.
- **Generic CAD, assemblies, and exact geometry (M7A).** Backend-independent
  `CadPartProgram`/`CadAssemblyProgram`, FreeCAD part and assembly backends, and
  exact `common().Volume`/`distToShape()` interference/clearance measurement — the
  primitive later reused by M8C/M9. M7A has no dedicated spec and is documented
  only by source plus later architecture prose
  ([gaps G-01](docs/reconstruction/UNRESOLVED_GAPS.md)); the generic discrete
  single-axis kinematic sweep first arrived at M7C-1, and the Yagi/azimuth work of
  M7B–M7D is a domain reference exercise, not generic synthesis.
- **Production orchestration and live CAD acceptance (M8–M9).** The
  `ProductionApplication` composition root; source-bound `DesignSpec` →
  `CadPartProgram` compilation; trusted imported STEP → `ImportedCadComponent` →
  mixed `CadAssemblyProgram`; production kinematic entrypoint. M9 live-verified
  these edges on real FreeCAD 1.1.3, including a real trusted imported STEP, a live
  mixed assembly with fresh reload, exact measurement, a discrete sweep, and
  durable provider/backend/runtime provenance (`M9_FULLY_CLOSED_LIVE_VERIFIED`).
- **Motion (M10).** M10-1 conservative continuous single-axis clearance proof;
  M10-2 deterministic multi-joint revolute forward kinematics; M10-3 exact
  discrete multi-joint collision sweep; M10-4 conservative continuous proof along
  one explicit piecewise-linear path; M10-5 live system acceptance
  (`M10_FULLY_CLOSED_LIVE_VERIFIED`). M10-multi-shape corrected transient imported
  STEP measurement to aggregate all top-level shapes
  (`M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED`).
- **Structural analysis (M11).** M11-1 design architecture; M11-2 typed structural
  authority model; M11-3 trusted FreeCAD → Gmsh C3D10 → CalculiX foundation;
  M11-4 FRD/DAT interpretation with typed `PASS`/`FAIL`/`NOT_EVALUABLE` outcomes
  and fixed-cantilever analytical validation; M11-5 durable structural Evidence,
  bounded repeatability, and declared displacement-metric mesh convergence;
  M11-6 live system closure (`M11_FULLY_CLOSED_LIVE_VERIFIED`).
- **Candidate realization and promotion (M12).** M12-1 design architecture;
  M12-2 source-bound noncanonical candidate authority; M12-3 bounded
  revolute-drive realization/sizing from supplied direct-drive or external-spur
  snapshots; M12-4 candidate CAD realization, M10 evaluation, deterministic
  comparison, and noncanonical selection; M12-5 explicit promotion of one selected
  feasible candidate into canonical `physical_mechanisms` with N→N+1 rebinding,
  fresh canonical CAD/M10 verification, and eligibility-only M11 handoff; M12-6
  live end-to-end acceptance
  (`M12_6_LIVE_END_TO_END_PHYSICAL_MECHANISM_ACCEPTANCE_VERIFIED`).
- **Candidate/canonical unification (M13).** M13-1 gate-driven supplied-component
  numeric shaft/mounting interface authority (unit-verified); M13-2 generic
  generated mechanical-part CAD (cylindrical stock and axial bore) with live
  compound acceptance; M13-3P generic M10 v2 rigid-body constituent groups that
  preserve M10 v1 wire formats/hashes; M13-3 candidate/canonical multi-joint M10
  bridge with deterministic lowering and fresh canonical verification; M13-4E
  deterministic multi-joint promotion Evidence contract and M13-4P production
  composition wiring; M13-4 final live full-stack capstone
  (`M13_4_INDEPENDENT_FINAL_ACCEPTED`).

Current acceptance markers:

```text
M9_FULLY_CLOSED_LIVE_VERIFIED
M10_FULLY_CLOSED_LIVE_VERIFIED
M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED
M11_2_STRUCTURAL_AUTHORITY_MODEL_VERIFIED
M11_3_STRUCTURAL_MESH_SOLVER_FOUNDATION_VERIFIED
M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED
M11_5_DURABLE_STRUCTURAL_EVIDENCE_VERIFIED
M11_FULLY_CLOSED_LIVE_VERIFIED
M12_2_TYPED_CANDIDATE_COMPONENT_AUTHORITY_FOUNDATION_VERIFIED
M12_3_BOUNDED_PHYSICAL_REVOLUTE_DRIVE_REALIZATION_SIZING_VERIFIED
M12_4_CANDIDATE_CAD_M10_EVALUATION_COMPARISON_SELECTION_VERIFIED
M12_5_PROMOTION_CANONICAL_REBIND_M11_HANDOFF_VERIFIED
M12_6_LIVE_END_TO_END_PHYSICAL_MECHANISM_ACCEPTANCE_VERIFIED
M13_1_SUPPLIED_COMPONENT_NUMERIC_INTERFACE_AUTHORITY_IMPLEMENTED_AND_VERIFIED
M13_2_GENERIC_GENERATED_MECHANICAL_PART_CAD_FOUNDATION_VERIFIED
M13_3P_GENERIC_M10_RIGID_BODY_CONSTITUENT_GROUP_VERIFIED
M13_3_GENERIC_MULTI_JOINT_CANDIDATE_CANONICAL_M10_BRIDGE_VERIFIED
M13_4E_INDEPENDENT_R12_ACCEPTED
M13_4P_INDEPENDENT_ACCEPTED
M13_4_INDEPENDENT_FINAL_ACCEPTED
```

M11-1 and M12-1 are design-only architecture milestones; the list above carries
accepted verification/acceptance markers only.

> Documentation scope note: the normative `docs/architecture/*` documents still
> describe the M8–M11 baseline only, and the implemented-capability reference
> covers M12 but not M13. M12 and M13 are established by committed production
> code and tests plus the accepted audit records above; see
> [gaps G-12](docs/reconstruction/UNRESOLVED_GAPS.md).

## Current Production Flow

`ProductionApplication.create(...)` is the production composition root. It owns
state, Evidence, ownership, change, run, tool, agent, CAD, kinematic, structural,
candidate, and promotion services. Key production entrypoints include:

- CAD/assembly: `compile_design_spec`, `build_assembly_with_imported_components`,
  `analyze_assembly_kinematics`.
- Motion: `prove_continuous_single_axis_clearance`,
  `evaluate_multi_joint_configuration`, `analyze_multi_joint_collision_sweep`,
  `prove_continuous_multi_joint_path_clearance`.
- Structural: the bounded M11 analysis, interpretation, and
  `publish_structural_evidence` path.
- Candidate/promotion: `realize_and_evaluate_revolute_drive`,
  `realize_candidate_cad`, `evaluate_candidate`, `compare_candidates`,
  `select_candidate`, `compile_candidate_promotion`,
  `promote_selected_candidate`, `promote_selected_multi_joint_candidate`, and
  `verify_multi_joint_promotion_application`.

Providers, solvers, CAD backends, and agent transports are bounded participants;
none is canonical engineering authority.

## Current Trust / Authority Boundaries

- `DesignState` is the canonical engineering source of truth. Proposals, results,
  artifacts, analysis results, and Evidence are separate bindable records and do
  not implicitly mutate canonical state.
- Only the trusted change machinery (`ChangeEngine` under the ownership policy and
  project lock, via `RunController` for promotion) creates canonical revisions.
- **Proposal status is not an enforced approval gate.** In the current code (as at
  the historical M2/M4 boundaries) `proposal.status` is never checked; any
  proposal that passes stale-base, ownership, operation, and resulting-state
  validation can advance canonical state.
- `ImportedCadComponent` is a complete, byte-verified STEP artifact, recomputed
  and checked by `ArtifactStore`; arbitrary filesystem STEP paths are not trusted
  imported components.
- External library/backend objects never cross normalization boundaries into
  `ToolCall`, `ToolResult`, Evidence, Run, artifacts, or `DesignState`.
- `run_id` is correlation/storage scope only, not engineering identity;
  source revision/state hash and deterministic request/result hashes bind
  engineering records.
- `CadCompilationService` operates under `PREACCEPTED_CALLER_CONTRACT_ONLY`: a
  source-bound spec is compiled against state binding, but the exact spec is not
  durably represented as selected canonical design authority.

## Current Limitations

- **Motion:** M10-3 discrete sweeps retain `continuous_path_verified = False`;
  M10-4 proves only the explicitly requested piecewise-linear path, not an entire
  configuration-space region or general trajectory. M10-2 provides discrete
  forward kinematics only.
- **Structural:** M11 is a source-bound, single homogeneous solid, linear-static,
  small-deformation, isotropic linear-elastic path only. Assembly FEA, nonlinear
  analysis, fatigue, dynamics, thermal stress, adaptive refinement, generic or
  stress convergence, and global yield, safety, or manufacturing approval are not
  implemented. Stress remains CalculiX extrapolated nodal stress.
- **Candidate realization:** no generic candidate generation, search, catalog
  lookup, bearing or fastener sizing, gear strength/life, or optimization.
  M12-3 realization is limited to supplied direct-drive and external-spur
  templates; comparison uses one certified clearance metric.
- **Selection and promotion:** selection and promotion are explicit, never
  automatic. Candidate records are noncanonical until explicit promotion. Exactly
  one selected feasible candidate and (in M13-3/M13-4) exactly one canonical
  obligation are supported.
- **M11 handoff during promotion:** eligibility-only; it creates no structural
  definition, mesh, solve, or structural Evidence.
- **Generated-part CAD:** limited to cylindrical stock and axial bore;
  `EXACT_GENERATED_GEOMETRY` is exact only relative to the bound semantic
  specification, not manufacturing truth.
- **Supplied-component interface authority:** M13-1 is unit-verified with no live
  acceptance at its own boundary.
- **Broader gaps:** materials selection, tolerance verification, manufacturing
  output/approval, optimization, whole configuration-space certification,
  multi-agent engineering convergence, and general automatic synthesis remain
  unimplemented. See [UNRESOLVED_GAPS.md](docs/reconstruction/UNRESOLVED_GAPS.md).

## Development

```text
python -m pip install -e ".[test]"
pytest -q
```

Optional dependency profiles are declared in `pyproject.toml`: `gear`,
`materials`, and `structural`. The core runtime requires Python 3.11+ and Pydantic
v2. The `config/` files are schema/version-marked placeholders and contain no
runtime integration settings.

## Historical Development

The accepted reconstruction ([`docs/reconstruction/`](docs/reconstruction/README.md))
is the evidence-based authority for per-milestone history, including historical
defects that were preserved rather than smoothed over. In brief:

- **M0–M4** built the deterministic state/mutation/run substrate.
- **M5–M5.5** added the tool boundary and optional gear/material/section providers.
- **M6A–M6B** added the agent gateway, OpenCode transport, and bounded transmission
  reasoning.
- **M7** added generic CAD/assembly and exact geometry plus a domain reference
  exercise.
- **M8–M9** connected production orchestration and live-verified real FreeCAD.
- **M10** added conservative motion proofs and exact discrete multi-joint sweeps.
- **M11** added the bounded structural (mesh/solve/interpret/Evidence) path.
- **M12** added candidate realization, evaluation, comparison, selection, and
  promotion.
- **M13** unified candidate/canonical multi-joint realization and finalized the
  promotion Evidence contract.

For narrative, chronological, and per-capability detail read
[PROJECT_HISTORY.md](docs/reconstruction/PROJECT_HISTORY.md),
[CAPABILITY_EVOLUTION.md](docs/reconstruction/CAPABILITY_EVOLUTION.md),
[MILESTONE_LEDGER.md](docs/reconstruction/MILESTONE_LEDGER.md), and the canonical
per-milestone records under [`docs/reconstruction/milestones/`](docs/reconstruction/milestones/).
