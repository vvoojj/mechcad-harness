# MechCAD Harness

MechCAD is a deterministic, provenance-aware mechanical-engineering harness for
turning authoritative engineering inputs into controlled canonical state,
derived CAD/analysis artifacts, and reproducible verification evidence.

The architecture is intended to be general-purpose, while the **currently
accepted production capabilities are deliberately bounded**. This README
describes the current system and its accepted capability surface. Per-milestone
history, including rejected intermediate states and historical defects, belongs
in the accepted [historical reconstruction](docs/reconstruction/README.md).

## Status at a Glance

| Item | Accepted baseline |
| --- | --- |
| Product milestone | **M13-4** |
| Product commit | `185a304796c17793519fb5f01dbf80cca73ab51e` |
| Terminal acceptance marker | `M13_4_INDEPENDENT_FINAL_ACCEPTED` |
| Reconstruction synthesis | `0cbb70e` |
| Live CAD runtime verified at acceptance | FreeCAD 1.1.3 |

Commits after the accepted M13-4 product commit through the reconstruction
synthesis are documentation-only. For later repository changes, inspect the
current code/tests and applicable accepted audits rather than assuming this
snapshot describes unreviewed future work.

## Documentation Map

Start with [`docs/README.md`](docs/README.md) for task-sized context bundles.

- **Current normative architecture:** [`docs/architecture/`](docs/architecture/)
  - [Project Overview](docs/architecture/MECHCAD_PROJECT_OVERVIEW.md)
  - [System Contract](docs/architecture/MECHCAD_SYSTEM_CONTRACT.md)
  - [Capability Matrix](docs/architecture/MECHCAD_CAPABILITY_MATRIX.md)
  - [Runtime Flow](docs/architecture/MECHCAD_RUNTIME_FLOW.md)
  - [Subsystem Contracts](docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md)
- **Implemented capability / wiring inventory:**
  [MECHCAD_IMPLEMENTED_CAPABILITIES.md](docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md)
- **Accepted system and live verification:** [`docs/audit/`](docs/audit/)
- **Accepted historical reconstruction:**
  [`docs/reconstruction/README.md`](docs/reconstruction/README.md)
  - [Project History](docs/reconstruction/PROJECT_HISTORY.md)
  - [Capability Evolution](docs/reconstruction/CAPABILITY_EVOLUTION.md)
  - [Milestone Ledger](docs/reconstruction/MILESTONE_LEDGER.md)
  - [Milestone Catalog](docs/reconstruction/MILESTONE_CATALOG.json)
  - [Unresolved Gaps](docs/reconstruction/UNRESOLVED_GAPS.md)

> **Documentation freshness:** the normative `docs/architecture/*` set still
> describes the M8–M11 baseline, while the implemented-capability reference
> covers M12 but not M13. Accepted M12/M13 behavior is therefore established by
> the committed implementation/tests together with the accepted audit records.
> See `docs/reconstruction/UNRESOLVED_GAPS.md` (G-12).

## Current Accepted Capability Surface

### Canonical state and controlled mutation

- `DesignState` is the canonical engineering source of truth.
- Revisions are immutable and deterministically hashed.
- Canonical mutation flows through `ChangeProposal` → `ChangeSet` →
  `ChangeEngine`, with stale-base, ownership, operation, and resulting-state
  validation.
- Dependency invalidation, Evidence freshness, and run/task control are part of
  the production substrate.

### Tool, provider, and agent boundaries

- Exact-version `ToolRegistry` / `ToolBroker` mediation.
- Normalized backend identity, health, and provenance.
- Bounded gear, material, and section providers.
- Agent gateway with fake/test and OpenCode transports.
- Bounded `mechcad-transmission` reasoning; agent/tool outputs do not become
  canonical engineering authority merely by existing.

### CAD, assemblies, and exact geometry

- Backend-independent `CadPartProgram` and `CadAssemblyProgram`.
- FreeCAD part and assembly backends.
- Trusted imported STEP components with byte verification.
- Mixed generated/imported assemblies.
- Exact FreeCAD interference / clearance primitives using
  `common().Volume` and `distToShape()`.
- Generated mechanical-part CAD currently supports cylindrical stock and axial
  bores only.

### Motion

- Conservative continuous single-axis clearance proof.
- Deterministic multi-joint revolute forward kinematics.
- Exact discrete multi-joint collision sweeps.
- Conservative continuous proof along one explicitly supplied
  piecewise-linear path.
- M10 v2 rigid-body constituent groups and candidate/canonical multi-joint
  lowering.

### Structural analysis

- Typed structural authority model.
- Trusted FreeCAD → Gmsh C3D10 → CalculiX path.
- FRD/DAT interpretation with typed outcomes.
- Durable structural Evidence, bounded repeatability, and declared
  displacement-metric mesh convergence.

### Candidate realization, selection, and promotion

- Source-bound noncanonical candidate authority.
- Bounded direct-drive / external-spur revolute-drive realization and sizing.
- Candidate CAD realization, M10 evaluation, deterministic comparison, and
  explicit selection.
- Explicit promotion into canonical `physical_mechanisms` with N→N+1 rebinding,
  fresh canonical CAD/M10 verification, and durable promotion Evidence.
- Supplied-component numeric shaft/mounting interface authority and generated
  mechanical-part authority.
- Candidate/canonical multi-joint M10 bridge and production promotion wiring.

For the exact per-milestone evolution and acceptance markers, use
[`docs/reconstruction/MILESTONE_LEDGER.md`](docs/reconstruction/MILESTONE_LEDGER.md)
instead of duplicating that ledger here.

## Current Production Flow

`ProductionApplication.create(...)` is the production composition root. It
composes state, Evidence, ownership, change, run, tool, agent, CAD, kinematic,
structural, candidate, and promotion services.

Important production entrypoints include:

- **CAD / assembly:** `compile_design_spec`,
  `build_assembly_with_imported_components`, `analyze_assembly_kinematics`.
- **Motion:** `prove_continuous_single_axis_clearance`,
  `evaluate_multi_joint_configuration`, `analyze_multi_joint_collision_sweep`,
  `prove_continuous_multi_joint_path_clearance`.
- **Structural:** the bounded M11 analysis / interpretation path and
  `publish_structural_evidence`.
- **Candidate / promotion:** `realize_and_evaluate_revolute_drive`,
  `realize_candidate_cad`, `evaluate_candidate`, `compare_candidates`,
  `select_candidate`, `compile_candidate_promotion`,
  `promote_selected_candidate`, `promote_selected_multi_joint_candidate`, and
  `verify_multi_joint_promotion_application`.

Providers, solvers, CAD backends, and agent transports are bounded participants;
none is canonical engineering authority.

## Trust and Authority Boundaries

- `DesignState` is canonical. Proposals, results, artifacts, analysis results,
  and Evidence are separately bound records and do not implicitly mutate it.
- Only trusted change machinery (`ChangeEngine` under ownership policy and the
  project lock, via `RunController` where applicable) creates canonical
  revisions.
- **`proposal.status` is not currently an enforced approval gate.** A proposal
  that passes the implemented stale-base, ownership, operation, and
  resulting-state checks can advance canonical state; do not assume an approval
  status check exists where the code does not enforce one.
- `ImportedCadComponent` is a complete byte-verified STEP artifact checked by
  `ArtifactStore`; an arbitrary filesystem STEP path is not a trusted imported
  component.
- External library/backend objects do not cross normalization boundaries into
  persisted `ToolCall`, `ToolResult`, Evidence, Run, artifact, or `DesignState`
  records.
- `run_id` is correlation/storage scope, not engineering identity. Engineering
  records are bound through source revision/state hashes and deterministic
  request/result identities.
- `CadCompilationService` operates under
  `PREACCEPTED_CALLER_CONTRACT_ONLY`: source binding is checked, but the exact
  input spec is not durably represented as selected canonical design authority.

## Current Limitations

The accepted system must not be described as providing capabilities beyond the
following bounds:

- **Motion:** M10-3 discrete sweeps keep `continuous_path_verified = False`;
  M10-4 proves only the explicitly requested path. There is no general
  configuration-space certification or trajectory planner.
- **Structural:** M11 is a source-bound, single homogeneous solid,
  linear-static, small-deformation, isotropic linear-elastic path. There is no
  assembly FEA, nonlinear/fatigue/dynamics/thermal analysis, adaptive
  refinement, generic/stress convergence, or global manufacturing/safety
  approval. Stress remains CalculiX extrapolated nodal stress.
- **Candidate realization:** there is no generic candidate search/generation,
  catalog selection, bearing/fastener sizing, gear strength/life calculation,
  or optimizer. M12-3 is bounded to supplied direct-drive and external-spur
  templates.
- **Selection / promotion:** selection and promotion are explicit, not
  automatic. Current M12/M13 flows support one selected feasible candidate and
  one canonical obligation in the relevant bounded path.
- **M11 promotion handoff:** eligibility-only; it does not create a structural
  definition, mesh, solve, or structural Evidence.
- **Generated-part CAD:** cylindrical stock and axial bore only; exactness is
  relative to the bound semantic specification, not manufacturing truth.
- **Supplied-component interface authority:** M13-1 is unit-verified at its own
  boundary.
- **Broader gaps:** materials selection, tolerance verification, manufacturing
  output/approval, optimization, whole configuration-space certification,
  multi-agent engineering convergence, and general automatic synthesis remain
  unimplemented. See
  [`UNRESOLVED_GAPS.md`](docs/reconstruction/UNRESOLVED_GAPS.md).

## Development

```text
python -m pip install -e ".[test]"
pytest -q
```

Optional dependency profiles are declared in `pyproject.toml`: `gear`,
`materials`, and `structural`. The core runtime requires Python 3.11+ and
Pydantic v2. The `config/` files are schema/version-marked placeholders and do
not contain runtime integration settings.

Live FreeCAD / Gmsh / CalculiX validation has additional environment
requirements; use the relevant audit and architecture documents before treating
an optional external runtime as available.

## Historical Development

Do not reconstruct milestone history from this README. The accepted
[`docs/reconstruction/`](docs/reconstruction/README.md) set is the evidence-based
authority for historical commit boundaries, capability evolution, accepted and
rejected intermediate states, retained execution evidence, and unresolved gaps.
Historical defects are preserved there rather than rewritten to match the final
implementation.
