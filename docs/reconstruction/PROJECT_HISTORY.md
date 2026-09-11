# MechCAD Reconstructed Project History

This narrative is synthesized **only** from the accepted reconstruction records
under `milestones/**` and `evidence/**`. It is historical, not a statement of
current production behavior. Where a fact is disputed or unsupported, it is
marked. The reconstruction endpoint is M13-4 at
`185a304796c17793519fb5f01dbf80cca73ab51e`.

Status vocabulary used here: `IMPLEMENTATION` (source written), `DESIGN_ONLY`
(no source), `LIVE_VERIFICATION`/`ACCEPTANCE` (runtime proof), `REMEDIATION`,
`RECONCILIATION`, `DOCUMENTATION_ONLY`. A milestone that only validated a
capability is not credited with introducing it.

---

## Era 1 — Deterministic engineering substrate (M0–M4)

**Before:** nothing existed. `7185351` bootstrapped the package.

- **M0** introduced the canonical `DesignState` and project/revision storage
  (`IMPLEMENTATION`).
- **M1/M2** entered in one shared commit `37f3ff3`: immutable revisions (M1)
  and the ChangeSet/proposal mutation path (M2). The ledger documents that M1
  and M2 are distinct logical milestones sharing one Git boundary, and that
  M1/M2 historical execution is `NOT_RETAINED`/`HISTORICALLY_UNVERIFIED`.
- **M3** `df584f0` added dependency invalidation and Evidence freshness.
- **M4** `a958c397` added run control.

**State after:** a deterministic state/mutation/run substrate with no CAD,
agents, or external execution. Deviations: M3 provenance is path-level rather
than fully identity-bound (documented).

---

## Era 2 — Tool boundary, backend foundation, gear/section analysis (M5–M5.5C)

**Before:** M4 run control; no tool boundary.

- **M5** `6cbade0` introduced the Tool Broker, registry, built-ins, and
  task permissions. **Material defect:** the shared commit also imports
  M5.5A `BackendProvenance` although no `backends` package exists, so the M5
  tree cannot import; M5 is committed implementation evidence but not a
  runnable milestone (`IMPLEMENTATION_STATUS: PARTIAL`).
- **M5.5A** (same `6cbade0`) is `DESIGN_ONLY`; its six tests and provenance
  fields exist but the backend package is absent.
- **M5.5B** `b0d77e1` first supplies the backend package and adds gear
  calculation/CAD artifacts (pinned py_gearworks/build123d). It is
  `IMPLEMENTED_WITH_DEVIATIONS`; the pair operation stores only a nominal
  transform.
- **M5.5C** `4bc2310` added material/section/warping integration
  (`IMPLEMENTED_WITH_DEVIATIONS`).

**State after:** tools, an optional gear/CAD path, and section analysis; no
unified runtime acceptance. Overclaims in M0–M4 records were later corrected
during reconstruction.

---

## Era 3 — Reasoning agents and tool mediation (M6A–M6B)

**Before:** a tool boundary with no reasoning loop.

- **M6A-1** `e4f4c00` added the deterministic FakeAgent-only gateway
  (identity, context, invocation/result, provenance).
- **M6A-2B** `60ccc2d` added the loopback OpenCode HTTP adapter with execution
  provenance. Its structured-output handling was later hardened.
- **M6B** `928be44` bundled the transmission round trip: M6B-1 authored
  transmission responses, M6B-2A semantic torque tool mediation, and M6B-2B
  ToolResult→Evidence materialization. 68 test functions were added.
- **M6B-3** `53fa6c4` added bounded constraint discovery.
- **M6B-4A** `3c7c708` added the typed resolution foundation.
- **M6B-4C** `4468a62` added resolution workflow closure, but the later audit
  classifies it `IMPLEMENTED_BUT_UNUSED`: no production caller ever drove it,
  and it carries a Python 3.11/3.12 annotation-import defect.

**State after:** a reasoning-to-tool-to-Evidence loop bounded to the
transmission domain. Historical acceptance is largely `NOT_RETAINED`; the
resolution workflow was never connected to production.

---

## Era 4 — Generic CAD/assembly, exact geometry, and the domain reference (M7A–M7E)

**Before:** no CAD execution.

- **M7A** (source `19f77a3`, acceptance artifacts `8079c57`) introduced the
  generic CAD/assembly/exact-geometry foundation: FreeCAD backend (M7A-1),
  typed operations (M7A-2A), rigid assemblies (M7A-2B), and exact
  interference/clearance via `common().Volume`/`distToShape()` (M7A-2C).
  This is the first real CAD capability and the origin of the exact-geometry
  primitive later reused by M8C/M9. It has **no dedicated spec/plan**
  (`TRACEABILITY_MISSING`, R-031/R-034) despite being `REQUIRED_CURRENT`.
- **M7B-1A-R2** `19f77a3` co-delivered azimuth drive-mount interface authority
  with the M7A source.
- **M7B-1B** `7c7352a` added deterministic azimuth mount-plate synthesis.
- **M7B-2A** `30b99eb` established Yagi payload-carrier authority.
- **M7B-2B/R2-R4** `3f7bbc7` added preliminary carrier CAD, clamp/slider and
  sliding-interface work; final carrier compilation remains fail-closed.
- **M7B-2C/M7C-1** `9ab9e48` added collision layout and the generic discrete
  kinematic sweep; M7B-2C was incomplete at its own boundary (missing state
  field, ownership, assembly builder) and was repaired in `8079c57`.
- **M7D-1/M7D-2** `8079c57` added EL kinematic reference and its sweep adapter
  (`IMPLEMENTED_BUT_UNUSED`).
- **M7E-2** `8079c57` added a preliminary AZ/EL rotator concept package,
  explicitly `NOT_VERIFIED`/`NOT_READY` (`DOCUMENTARY`).

**State after:** generic CAD + exact geometry + a substantial domain reference
exercise (Yagi/azimuth), but no production orchestration and no unified
acceptance. The domain work proves the architecture supports a real domain
without becoming the product purpose.

---

## Era 5 — Production orchestration and the CAD/assembly bridge (M8*)

**Before:** strong subsystems with no single composition root.

- **M8B-1/M8B-2** `8079c57` added `ProductionApplication.create()` (the
  composition root: state, Evidence, ownership, ChangeEngine, runs, tools,
  agents) and the production transmission round trip over it.
- **M8C** `6c6f46c` added source-bound `DesignSpec`→`CadPartProgram`
  compilation (M8C-1), trusted imported STEP→`ImportedCadComponent`→mixed
  assembly (M8C-2), and production kinematic orchestration (M8C-3).
  Classified `ARCHITECTURALLY_CLOSED_RUNTIME_GATED`: real FreeCAD was not yet
  proven, and its mixed imported routing and transient provider had defects
  fixed later.

**State after:** a production composition root and a CAD/assembly pipeline that
was architecturally closed but runtime-gated.

---

## Era 6 — Live CAD/assembly system acceptance (M9)

**Before:** M8C runtime gates: synthetic imports, no live mixed assembly.

- **M9** `a67cee3` closed the M8C gates live: real FreeCAD 1.1.3, a real
  trusted STEP produced through the gear/build123d stack, mixed
  generated/imported assembly realization with fresh reload, exact
  `common().Volume`/`distToShape()` measurement, a completed discrete sweep,
  and durable provider/backend/runtime provenance. Layers: M9-1 runtime,
  M9-2 trusted import, M9-3 live mixed exact kinematics, M9-4 provenance.

**State after:** `M9_FULLY_CLOSED_LIVE_VERIFIED`. Documented defects: an
M9-2 audit test-count error (8 vs 7); assembly/request/result hashes are
run-specific.

---

## Era 7 — Motion system acceptance (M10)

**Before:** single discrete sweeps only.

- **M10** `89b1d75` bundled M10-1 conservative single-axis continuous proof,
  M10-2 generic multi-joint revolute FK, M10-3 exact discrete multi-joint
  collision sweep, M10-4 continuous proof along one explicit piecewise-linear
  path, and M10-5 the live capstone. Acceptance: `M10_FULLY_CLOSED_LIVE_VERIFIED`.
- **M10-MULTI-SHAPE** `28ac193` later corrected a latent trust boundary so
  imported STEP measurement aggregates all top-level shapes.

**State after:** verified conservative motion analysis. Documented defect:
M10-4 does not enforce complete assembly-backed path partition validation at
execution (malformed partitions can reach `VERIFIED_CLEAR`); a named
regression file and evidence script are absent.

---

## Era 8 — Structural analysis (M11)

**Before:** no structural/FEA capability.

- **M11-1** `682300b` is `DESIGN_ONLY` architecture.
- **M11-2/M11-3/M11-4** `682300b` added the typed structural authority model,
  the FreeCAD→Gmsh C3D10→CalculiX mesh/solver foundation, and FRD/DAT result
  interpretation with analytical cantilever validation.
- **M11-5** `07950cd` added durable structural Evidence, bounded repeatability,
  and a declared three-level displacement-metric convergence study.
- **M11-6** `4d436cf` is `DOCUMENTATION_ONLY` final acceptance
  (`M11_FULLY_CLOSED_LIVE_VERIFIED`), adding no source.

**State after:** a bounded source-bound single-body linear-static structural
path with durable Evidence. Documented defects: FRD/DAT fixture EOL
sensitivity, stale report counts, and an audit transcription sign
inconsistency. Stress remains CalculiX extrapolated nodal stress with no
global yield/safety claim.

---

## Era 9 — Candidate realization (M12)

**Before:** no candidate concept; promotion did not exist.

- **M12-1** `28ac193` is `DESIGN_ONLY` candidate architecture.
- **M12-2/M12-3** `28ac193` added immutable source-bound candidate authority
  and bounded revolute-drive realization/sizing.
- **M12-4** `bae65cc` added candidate CAD realization, M10 evaluation,
  deterministic comparison, and noncanonical selection (live FreeCAD).
- **M12-5** `161986b` added promotion into canonical `physical_mechanisms`,
  N→N+1 rebinding, fresh canonical CAD/M10 verification, and non-gating M11
  eligibility handoff.
- **M12-6** `de78b4e` is `ACCEPTANCE_ONLY`: live end-to-end physical-mechanism
  acceptance with no production source delta.

**State after:** a candidate→evaluate→compare→select→promote→rebind chain with
live acceptance. Documented defects: DAT CRLF fixture sensitivity (full-suite
counts require normalized checkout), and stale report/governance counts.

---

## Era 10 — Candidate/canonical unification (M13)

**Before:** M12 candidates and canonical mechanisms were only partially unified.

- **M13-1** `f6d8124` added supplied-component numeric shaft/mounting interface
  authority (unit-verified, no live test).
- **M13-2** `664ec3b` added generic generated mechanical-part CAD
  (cylindrical stock/bore) with live compound acceptance.
- **M13-3P** `f3ab0c7` added generic M10 v2 rigid-body constituent groups,
  preserving M10 v1 wire formats and hashes.
- **M13-3** `ca294e0` added the physical candidate/canonical multi-joint M10
  bridge with deterministic lowering and fresh canonical verification.
- **M13-4E** (in `185a304`) added the multi-joint promotion Evidence contract
  (decision/input reference and decision/result manifests).
- **M13-4P** (in `185a304`) added the production composition wiring.
- **M13-4** (in `185a304`) is the representative live full-stack capstone,
  `M13_4_INDEPENDENT_FINAL_ACCEPTED`, after a documented chain of rejections
  and remediations.

**State after:** `M13_4_INDEPENDENT_FINAL_ACCEPTED`. Documented defects: the
commit bundles implementation, remediation, and acceptance records with
chronologically mixed markers; the final acceptance rested on a then-untracked
test file; several completion reports say "no commit was created" although the
commits exist; `AGENTS.md`/architecture docs still stop at M11.

---

## Endpoint and post-history

The last committed product milestone is **M13-4** at `185a304`. Every commit
after it (through the reconstruction HEAD `1a6a306`) is reconstruction
documentation and touches only `docs/`. Untracked Rotator V2 Epic 01 work is a
separate, explicitly-unaccepted activity gated on M13-4 acceptance; it is not
committed project history and is not a reconstructed milestone.

For the resolved and unresolved issues referenced above, see
[`UNRESOLVED_GAPS.md`](UNRESOLVED_GAPS.md) and
[`CAPABILITY_EVOLUTION.md`](CAPABILITY_EVOLUTION.md).
