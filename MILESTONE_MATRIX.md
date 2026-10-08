# M0→M13 current verification matrix

This matrix maps the historical milestone vocabulary to **current HEAD** test
surfaces. It is intentionally a regression map, not a claim that present tests
prove historical execution.

| M | Current verification focus | Dedicated runner stage |
|---|---|---|
| M0 | identifiers, base models, canonical serialization | `10_m0_foundation` |
| M1 | StateManager immutable revision/hash/current pointer | `11_m1_state_foundation` |
| M2 | change proposal/operations/ownership/atomic revision | `12_m2_changes` |
| M3 | dependency graph, invalidation, Evidence freshness | `13_m3_dependency_evidence` |
| M4 | run/task state, resume, persistence, completion gates | `14_m4_runs` |
| M5 | tool registry/broker plus M5.5 artifacts/gear/material/section providers | `15_m5_tools`, `16_m5_5_providers_artifacts_sections` |
| M6 | agent gateway/OpenCode contract/transmission/tool mediation/constraints/current admission | `17_m6_agents_transmission_constraints` (+ optional OpenCode live) |
| M7 | generic CAD/assembly/exact geometry/kinematic sweep and reference adapters | `18_m7_cad_assembly_kinematics_unit`, `18b_m7_live_freecad` |
| M8 | production composition, source-bound CAD, trusted imported-component bridge | `19_m8_production_composition` |
| M9 | accepted live FreeCAD production chain | `20_m9_live_system` |
| M10 | continuous single-axis, multi-joint FK, discrete collision, explicit continuous path | `21_m10_motion_unit`, `21b_m10_live_system` |
| M11 | structural authority/pipeline/evidence + real FreeCAD/Gmsh/CalculiX | `22_m11_structural_unit`, `22b_m11_live_structural` |
| M12 | candidate authority/realization/CAD/M10/selection/promotion/live E2E | `23_m12_candidate_promotion_unit`, `23b_m12_live_production` |
| M13 | supplied interfaces/generated parts/multi-joint bridge/promotion/full stack | `24_m13_unit`, `24b_m13_live_integration` |

Current HEAD also contains accepted post-M13 deterministic STEP content identity
work. It is verified separately so M13 historical/accepted scope is not silently
rewritten: `25_*` P8.2 gates and `26_*` T-P8.3 live fresh MINI replay.

A final whole-tree `pytest tests` is run after these explicit gates. It is a
broad regression safety net, not a substitute for the milestone verdicts.
