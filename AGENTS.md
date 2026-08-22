# Agent Instructions

## Current Accepted Baseline

This repository implements the MechCAD Harness production system up to the
accepted **M8 + M9 + M10-1 + M10-2 + M10-3 + M10-4** baseline.

- **M8 — production architecture connected:** production orchestration
  (`ProductionApplication` composition root), source-bound `DesignSpec` →
  `CadPartProgram` compilation, trusted imported STEP artifacts
  (`ImportedCadComponent` via `ArtifactStore`), generic mixed assembly
  (`CadAssemblyProgram`), and the production kinematic entrypoint
  (`ProductionApplication.analyze_assembly_kinematics`).
- **M9 — live FreeCAD / trusted import / exact discrete analysis / execution
  provenance verified:** real FreeCAD (1.1.3) realized generic CAD; a real
  trusted imported STEP artifact was produced and resolved; a live mixed
  FreeCAD assembly was generated, persisted, and fresh-reloaded; real
  `common().Volume` / `distToShape()` measured exact collision/clearance; a real
  discrete kinematic sweep completed; and durable trusted analysis-execution
  provenance was persisted.
- **M10-1 — continuous single-axis clearance proof:** conservative bisection
  algorithm with chord-displacement motion bound; three semantic outcomes
  (`VERIFIED_CLEAR`, `COLLISION_WITNESS`, `NOT_PROVEN`); resource limits are
  computation ceilings not correctness shortcuts; touching is not positive
  clearance; single-axis only.
- **M10-2 — generic multi-joint kinematic model:** deterministic forward
  kinematics over a rooted acyclic tree (forest) of revolute joints; at least
  two dependent revolute joints in series; explicit configuration → instance
  world transforms + transformed `CadAssemblyProgram`; separate configuration /
  model / transformed-assembly identity hashes; fail-closed topology validation
  (unique joint IDs, parent/child existence, single articulated parent, no
  cycles, reachability); production entrypoint
  (`ProductionApplication.evaluate_multi_joint_configuration`); core FK has no
  FreeCAD dependency.
- **M10-3 — exact discrete multi-joint collision sweep:** ordered multi-joint
  configurations are evaluated through transformed assemblies and real
  FreeCAD `common().Volume` / `distToShape()` measurements; exact pair
  classifications, deterministic request/result identities, and trusted
  provider/backend/runtime provenance are persisted atomically.
- **M10-4 — continuous multi-joint path clearance proof:** conservative adaptive
  proof along one explicit piecewise-linear raw joint-space path, using trusted
  local geometry extents, topology-derived invariant reach bounds, hierarchical
  telescoping motion bounds, exact pair-relative `B_A + B_B`, and real FreeCAD
  exact measurements. The result distinguishes `VERIFIED_CLEAR`,
  `COLLISION_WITNESS`, and fail-closed `NOT_PROVEN`.
- **M10-5 — final M10 system acceptance:** the complete M10-1 through M10-4
  motion stack was live-verified as one coherent production chain, including
  shared FK/discrete/continuous configuration equality, durable M10-4 result
  reload, trusted provenance, source immutability, M9 foundation regressions,
  and full-suite regression safety.
- **Current system acceptance: `M10_FULLY_CLOSED_LIVE_VERIFIED`.**
- **Current hard limitation:** ordinary M10-3 discrete sweeps retain
  `continuous_path_verified = False`; M10-4 proves only the explicitly
  requested path, not an entire configuration-space region. FEA, materials selection,
  manufacturing approval, tolerance verification, optimization, and automatic
  synthesis/selection are **not** implemented. M10-2 provides multi-joint
  *discrete* forward kinematics and collision evaluation only; it does not
  general trajectories, and configuration-space certification are not implemented.

## Precedence / Discovery Rules

1. Current accepted system-level normative architecture (`docs/architecture/*`)
   is authoritative for current behavior.
2. Accepted system-level audit / M9 acceptance
   (`docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md`) is authoritative for what was
   live-verified.
3. Accepted milestone specs and completion records
   (`docs/superpowers/specs/`, `docs/audit/`) are historical execution evidence.
4. Current code/tests behavior is ground truth for implementation.
5. Older historical project descriptions (e.g. M0–M6B milestone narrative) are
   lowest precedence for current behavior.

Historical milestone records are **secondary** to current normative architecture
and system acceptance except when investigating history. Do not treat a
historical `RUNTIME_GATED` statement as the current status.

## Progressive-Disclosure Reading Order

For general architecture work, read first:

- [`docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`](docs/architecture/MECHCAD_PROJECT_OVERVIEW.md)
- [`docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`](docs/architecture/MECHCAD_SYSTEM_CONTRACT.md)
- [`docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`](docs/architecture/MECHCAD_CAPABILITY_MATRIX.md)

For runtime / CAD / analysis work:

- [`docs/architecture/MECHCAD_RUNTIME_FLOW.md`](docs/architecture/MECHCAD_RUNTIME_FLOW.md)
- [`docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`](docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md)
- [`docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md`](docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md)
- [`docs/audit/MECHCAD_M10_2_COMPLETION_REPORT.md`](docs/audit/MECHCAD_M10_2_COMPLETION_REPORT.md)
- [`docs/audit/MECHCAD_M10_3_COMPLETION_REPORT.md`](docs/audit/MECHCAD_M10_3_COMPLETION_REPORT.md)

For historical M8 → M9 context:

- [`docs/audit/MECHCAD_POST_M8_M9_DOCUMENTATION_RECONCILIATION.md`](docs/audit/MECHCAD_POST_M8_M9_DOCUMENTATION_RECONCILIATION.md)

Do not load every milestone spec by default.

## Engineering Constraints

- Keep changes inside this repository.
- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Keep models minimal and reject empty required strings and non-positive revisions.
- Treat `DesignState` as canonical state; proposals, results, validation, and
  evidence remain separate bindable records.
- Do not add agents, OpenCode integration, CAD, FreeCAD, FEA, scheduling,
  dependency execution, LLM workflows, databases, or external services in M0.
- Do not commit unless the user explicitly requests it.
