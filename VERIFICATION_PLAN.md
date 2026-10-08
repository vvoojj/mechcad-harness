# MechCAD independent full M0→M13 verification runbook

## Baseline

Current verification anchor:

`4675c6cdaaf63c817719db356b05f30175071081`

The runner verifies this exact in-place worktree and fails closed if its HEAD
differs. It does not create a clone, install packages, or mutate accepted
audits/specs/plans/reconstruction records. Focused `-OnlyStages` runs record
unselected pytest stages as `NOT_RUN` and cannot establish full verification
credit.

## What “through all M” means

This is a **current-HEAD cumulative regression**, not a replay of historical
commits. Every top-level capability layer M0 through M13 receives an explicit
stage and an explicit PASS/FAIL/BLOCKED result. Historical sublayers are covered
inside the owning top-level stage:

- M5 includes the current descendants of M5.5A/B/C;
- M6 includes M6A/M6B current agent/transmission/constraint capabilities;
- M7 includes generic CAD/assembly/exact geometry plus retained reference-domain
  regressions;
- M8 covers production composition and trusted CAD/assembly bridges;
- M9/M10/M11/M12/M13 include their accepted live boundaries.

Retired/unused historical paths are **not resurrected as alternative production
routes**. They remain historical truth only. The verification exercises current
production code and current guarded behavior.

## Required live boundaries

A milestone cannot receive PASS merely because pytest skipped its live tests.
The runner parses JUnit and converts any skip in a required milestone stage into
`BLOCKED`.

Required external-runtime boundaries:

| Milestone | Required runtime |
|---|---|
| M7 | real FreeCAD |
| M9 | real FreeCAD |
| M10 | real FreeCAD |
| M11 | real FreeCAD + Gmsh + CalculiX |
| M12 | real FreeCAD (plus the already-installed provider dependencies used by the tests) |
| M13 | real FreeCAD |
| POST_M13 T-P8.3 | real FreeCAD |

M6 OpenCode live probes remain separately visible but optional because historical
M6 did not retain an M6-wide live acceptance. If `MECHCAD_OPENCODE_LIVE=1` is
set, they run and failures remain visible.

## Milestone stages

1. M0 — IDs/models/canonical serialization foundation.
2. M1 — immutable state/revision/hash foundation.
3. M2 — ChangeProposal/ChangeSet/ChangeEngine behavior.
4. M3 — dependency invalidation and Evidence currentness.
5. M4 — run/task controller and persistence.
6. M5 — tool broker/registry plus M5.5 artifacts, gear/material/section providers.
7. M6 — agents, OpenCode adapter contract, transmission reasoning/tool mediation,
   constraint requests/resolution, and current canonical admission edge.
8. M7 — generic CAD/assembly/exact measurement/kinematic foundations plus live
   FreeCAD and retained reference adapters.
9. M8 — production composition, source-bound CAD compilation, imported-component
   trust, and production vertical slices.
10. M9 — accepted real-FreeCAD system chain.
11. M10 — deterministic multi-joint motion plus real-FreeCAD exact collision and
    continuous path proof.
12. M11 — structural unit boundary plus mandatory real FreeCAD/Gmsh/CalculiX
    execution.
13. M12 — candidate realization/CAD/M10/selection/promotion plus live end-to-end
    production flows.
14. M13 — supplied interfaces, generated parts, grouped-body/multi-joint bridge,
    promotion evidence/composition, and full-stack live acceptance.
15. POST_M13 — exact accepted deterministic STEP-content-identity P8.2 minimum
    broad regression and T-P8.3 fresh semantic MINI live replay.
16. GLOBAL — complete `tests/` suite after all explicit milestone gates.

## MINI isolation

Historical `projects/mini_rotary_fixture` is never copied into the executable
snapshot. T-P8.3 gets a new `.tmp-live-m12/tp8_3_mini_replay/` workspace, which
is deleted before the dedicated live replay so a preceding full/milestone run
cannot contaminate it.

## Fresh evidence produced

- `logs/<stage>.log` — stdout/stderr and credited status for every stage;
- `meta/<stage>.xml` — JUnit for every pytest stage;
- `meta/<stage>.txt` — exact test selectors used by that stage;
- `meta/results.csv|json` — all stages, exit codes, counts, skip counts, duration;
- `meta/milestone_summary.csv|json` — explicit M0…M13 + POST_M13 verdicts;
- `meta/runtime_inventory.txt` — configured Python/FreeCAD/Gmsh/CalculiX/OpenCode
  state;
- `meta/source_status.txt` / `snapshot_commit.txt` — source condition and exact
  commit;
- `SUMMARY.txt` — whether every M0…M13 gate passed and whether full verification
  credit is allowed.

No old pass counts are reused as fresh evidence. Failures, skips, blocked
runtimes, timeouts, and later successes remain independently visible.
