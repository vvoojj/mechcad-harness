# Agent Instructions

## Current Accepted Baseline

This repository implements the MechCAD Harness production system through the
accepted **M0 → M13-4** baseline. The terminal product milestone is M13-4 at
commit `185a304796c17793519fb5f01dbf80cca73ab51e`, acceptance marker
`M13_4_INDEPENDENT_FINAL_ACCEPTED`. Commits after it through the reconstruction
synthesis `0cbb70e` are documentation only.

Current capability families:

- **Deterministic substrate (M0–M4):** canonical `DesignState`, immutable hashed
  revisions, `ChangeProposal` → `ChangeSet` → `ChangeEngine` mutation, dependency
  invalidation and Evidence freshness, run/task control.
- **Tool/provider/reasoning boundaries (M5–M6):** exact-version
  `ToolRegistry`/`ToolBroker`, backend identity/health/provenance, narrow
  gear/material/section providers, agent gateway, OpenCode transport, bounded
  `mechcad-transmission` reasoning.
- **Generic CAD/assembly and exact geometry (M7A):** `CadPartProgram` /
  `CadAssemblyProgram`, FreeCAD backends, `common().Volume` / `distToShape()`.
- **Production orchestration and live CAD (M8–M9):** `ProductionApplication`
  composition root, source-bound CAD compilation, trusted imported STEP, mixed
  assembly, production kinematic entrypoint, live FreeCAD 1.1.3 verification.
- **Motion (M10):** continuous single-axis proof; multi-joint forward kinematics;
  exact discrete multi-joint collision sweep; continuous proof along one explicit
  path; multi-shape transient-STEP measurement closure.
- **Structural (M11):** typed authority; FreeCAD → Gmsh C3D10 → CalculiX;
  FRD/DAT interpretation; durable structural Evidence; bounded repeatability and
  displacement-metric mesh convergence.
- **Candidate realization and promotion (M12):** noncanonical candidate
  authority; bounded revolute-drive realization/sizing; candidate CAD, M10
  evaluation, comparison, selection; explicit promotion into canonical
  `physical_mechanisms` with fresh canonical CAD/M10 verification and
  eligibility-only M11 handoff.
- **Candidate/canonical unification (M13):** supplied-component interface
  authority; generic generated-part CAD; M10 v2 rigid-body constituent groups;
  candidate/canonical multi-joint M10 bridge; multi-joint promotion Evidence
  contract and production wiring.

Selected current acceptance markers (full per-milestone set in
[`docs/reconstruction/MILESTONE_LEDGER.md`](docs/reconstruction/MILESTONE_LEDGER.md)):

```text
M9_FULLY_CLOSED_LIVE_VERIFIED
M10_FULLY_CLOSED_LIVE_VERIFIED
M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED
M11_FULLY_CLOSED_LIVE_VERIFIED
M12_6_LIVE_END_TO_END_PHYSICAL_MECHANISM_ACCEPTANCE_VERIFIED
M13_3P_GENERIC_M10_RIGID_BODY_CONSTITUENT_GROUP_VERIFIED
M13_3_GENERIC_MULTI_JOINT_CANDIDATE_CANONICAL_M10_BRIDGE_VERIFIED
M13_4E_INDEPENDENT_R12_ACCEPTED
M13_4P_INDEPENDENT_ACCEPTED
M13_4_INDEPENDENT_FINAL_ACCEPTED
```

`docs/architecture/*` still describe the M8–M11 baseline only, and
`docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md` covers M12 but not M13;
M12/M13 are established by committed production code/tests plus the accepted
audit records (see `docs/reconstruction/UNRESOLVED_GAPS.md` G-12).

## Document Authority

Keep **current** authority and **historical** authority separate. Do not use a
historical record to decide current behavior, and do not use current code to
rewrite what historically happened.

### For current behavior

1. Current accepted normative architecture (`docs/architecture/*`).
2. Current production implementation and wiring (`src/mechcad_harness/**`) and
   current tests (`tests/**`).
3. Accepted current system/live audits (`docs/audit/**`) when the question is
   what was verified.
4. Current capability/wiring inventory
   (`docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md`).
5. Historical milestone documentation only for historical context.

When normative architecture and current code disagree, current code is ground
truth for what is implemented; record the documentation gap instead of assuming
either is current. `docs/README.md` is a task-sized context guide; where its
older "Source Precedence" ordering conflicts with this section, this section
governs.

### For historical questions

1. Accepted reconstruction canonical records (`docs/reconstruction/milestones/**`
   plus `MILESTONE_LEDGER.md` / `MILESTONE_CATALOG.json`).
2. Detailed reconstruction evidence (`docs/reconstruction/evidence/**`).
3. Historical committed production code and tests at the relevant Git boundary.
4. Contemporary specifications and plans (`docs/superpowers/specs/**`,
   `docs/superpowers/plans/**`).
5. Contemporary completion/review/acceptance artifacts according to their
   evidence role (see below).
6. Later retrospective narrative (for example, older project descriptions).

Do not treat `docs/reconstruction/**` as normative for current behavior; it is
authoritative only for the reconstructed history of milestone boundaries.

### Evidence semantics (do not conflate)

- **SPEC / DESIGN:** intended contract.
- **PLAN:** intended implementation approach.
- **COMMITTED CODE:** implementation evidence.
- **COMMITTED TEST:** test existence, not historical execution.
- **RETAINED TEST / CI / LIVE OUTPUT:** historical execution evidence.
- **COMPLETION REPORT:** reported completion evidence.
- **REVIEW / ACCEPTANCE:** evaluation and formal acceptance where present.
- **RETROSPECTIVE:** later description of earlier history.

A specification is not execution evidence; a committed test does not prove a
historical run; "accepted" is not a synonym for "implemented." Prefer terms such
as *implemented*, *production-wired*, *live-verified in a bounded scenario*, or
*accepted as design only*.

## Production Wiring and Capability Boundaries

- `DesignState` is canonical. Proposals, results, artifacts, analysis results,
  and Evidence are separate bindable records; only trusted change machinery
  (`ChangeEngine` under ownership policy and project lock, via `RunController`
  for promotion) creates canonical revisions.
- **`proposal.status` is not an enforced approval gate** in the current code (nor
  at the historical M2/M4 boundaries). Any proposal passing stale-base,
  ownership, operation, and resulting-state validation can advance canonical
  state. Do not claim an approval gate exists.
- `ImportedCadComponent` is the complete byte-verified STEP artifact; arbitrary
  filesystem STEP paths are not trusted imported components.
- Backend/library objects never cross normalization boundaries into persisted
  records; only normalized scalar provenance does.
- `run_id` is correlation/storage scope only, not engineering identity.
- `CadCompilationService` runs under `PREACCEPTED_CALLER_CONTRACT_ONLY`.
- Do not overstate bounded scopes: M10 is discrete plus one explicit path; M11 is
  single homogeneous solid linear-static; M12/M13 selection and promotion are
  explicit and support one selected candidate and one canonical obligation;
  promotion's M11 handoff is eligibility-only.

## Current Limitations (must not be contradicted)

- M10-3 keeps `continuous_path_verified = False`; M10-4 proves only the requested
  path; no configuration-space certification or general trajectory planning.
- M11 has no assembly FEA, nonlinear/fatigue/dynamics/thermal analysis, adaptive
  refinement, global or stress convergence, global yield/safety, or
  manufacturing approval; stress is CalculiX extrapolated nodal stress.
- No generic candidate generation/search, catalog selection, bearing/fastener
  sizing, gear strength/life, or optimization.
- Generated-part CAD is only cylindrical stock/axial bore; exactness is relative
  to the bound semantic spec, not manufacturing truth.
- M13-1 interface authority is unit-verified only.
- Materials selection, tolerance verification, manufacturing output/approval,
  optimization, and general automatic synthesis remain unimplemented.

## Progressive-Disclosure Reading Order

For general architecture work, read first:

- [`docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`](docs/architecture/MECHCAD_PROJECT_OVERVIEW.md)
- [`docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`](docs/architecture/MECHCAD_SYSTEM_CONTRACT.md)
- [`docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`](docs/architecture/MECHCAD_CAPABILITY_MATRIX.md)

For runtime / CAD / analysis work:

- [`docs/architecture/MECHCAD_RUNTIME_FLOW.md`](docs/architecture/MECHCAD_RUNTIME_FLOW.md)
- [`docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md`](docs/architecture/MECHCAD_SUBSYSTEM_CONTRACTS.md)
- [`docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md`](docs/audit/MECHCAD_M9_SYSTEM_ACCEPTANCE.md)
- [`docs/audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md`](docs/audit/MECHCAD_M10_SYSTEM_ACCEPTANCE.md)
- [`docs/audit/MECHCAD_M11_SYSTEM_ACCEPTANCE.md`](docs/audit/MECHCAD_M11_SYSTEM_ACCEPTANCE.md)

For candidate/promotion and M12/M13 work:

- [`docs/audit/MECHCAD_M12_6_SYSTEM_ACCEPTANCE.md`](docs/audit/MECHCAD_M12_6_SYSTEM_ACCEPTANCE.md)
- [`docs/audit/MECHCAD_M13_4_INDEPENDENT_FINAL_ACCEPTANCE.md`](docs/audit/MECHCAD_M13_4_INDEPENDENT_FINAL_ACCEPTANCE.md)
- [`docs/reconstruction/CAPABILITY_EVOLUTION.md`](docs/reconstruction/CAPABILITY_EVOLUTION.md)

For historical milestone questions (what happened, when, and with what evidence):

- [`docs/reconstruction/README.md`](docs/reconstruction/README.md)
- [`docs/reconstruction/PROJECT_HISTORY.md`](docs/reconstruction/PROJECT_HISTORY.md)
- [`docs/reconstruction/MILESTONE_LEDGER.md`](docs/reconstruction/MILESTONE_LEDGER.md)
- [`docs/reconstruction/CAPABILITY_EVOLUTION.md`](docs/reconstruction/CAPABILITY_EVOLUTION.md)
- [`docs/reconstruction/UNRESOLVED_GAPS.md`](docs/reconstruction/UNRESOLVED_GAPS.md)

For capability planning or integration work only:

- [`docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md`](docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md) — implementation and wiring inventory; read when checking whether a capability already exists, avoiding duplicate work, or investigating production composition. Do not load it for routine local code changes.

Do not load every milestone spec or reconstruction record by default.

## Operations Requiring Explicit User Approval

- Any `git commit`, amend, push, tag, or release.
- Modifying accepted tests, audit records, specs/plans, normative architecture, or
  `docs/reconstruction/**` (unless the task explicitly asks for it).
- Running live external execution (FreeCAD/CalculiX/Gmsh subprocesses, OpenCode
  live validation, network access, package installation).
- Destructive filesystem operations outside the repository workspace.

## Engineering Constraints

- Keep changes inside this repository.
- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Keep models minimal and reject empty required strings and non-positive
  revisions.
- Treat `DesignState` as canonical state; proposals, results, validation, and
  evidence remain separate bindable records.
- The historical M0 constraint (no agents, OpenCode, CAD, FreeCAD, FEA, databases,
  or external services) describes the M0 boundary only; later milestones
  deliberately added bounded versions of these capabilities.
