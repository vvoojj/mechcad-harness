# MechCAD Capability Evolution Map

Answers "when did capability X first become real, and how did it evolve?"
Derived only from accepted reconstruction records and exact Git. Introduction
is based on the **first commit that introduced the capability**, never on its
later existence in current `master`. "Live/verified" means retained runtime
evidence exists; "Unit" means test/commit presence only.

`I` = introduced, `X` = extended, `LV` = live-verified, `A` = accepted,
`SUP` = superseded.

| Capability | I | X | LV | A | SUP / notes |
| --- | --- | --- | --- | --- | --- |
| Canonical `DesignState` | M0 `7185351` | M1 `37f3ff3`; M11-2 `682300b`; M13-2 `664ec3b` | — | M0 baseline | not superseded |
| Immutable revisions | M1 `37f3ff3` | M2 `37f3ff3`; M4 `a958c397` | — | M1 (hist. unverified) | — |
| ChangeSet / proposal mutation | M2 `37f3ff3` | M4; M12-5 | — | M2 | — |
| Dependency invalidation | M3 `df584f0` | M4 | — | M3 | path-level provenance only |
| Evidence freshness | M3 `df584f0` | M4; M9-4; M11-5; M13-4E | M9-4 `a67cee3` | M3 | — |
| Run Control | M4 `a958c397` | M8B-1 `8079c57` | — | M4 (hist. unverified) | — |
| Tool Broker | M5 `6cbade0` | M5.5B `b0d77e1`; M6B `928be44` | — | NOT_FOUND | M5 import-broken at its own tree |
| Backend boundary | M5.5A design `6cbade0` | M5.5B `b0d77e1` (first package) | M9 | NOT_FOUND | M5.5A "foundation" was design-only |
| Gear calculation + CAD artifacts | M5.5B-2 `b0d77e1` | — | — | partial | optional py_gearworks/build123d profile |
| Section/warping analysis | M5.5C `4bc2310` | — | — | partial | — |
| Agent gateway | M6A-1 `e4f4c00` | M6B-1 `928be44` | — | M6A-1 (hist. unverified) | FakeAgent-only |
| OpenCode integration | M6A-2B `60ccc2d` | M6B-1 `928be44` (validated JSON text) | — | NOT_FOUND (focused) | structured-output hardened later |
| Tool-mediated reasoning | M6B-2A/2B `928be44` | M8B-2 `8079c57` | — | NOT_FOUND | M6B-4C unused path |
| Generic CAD / FreeCAD backend | **M7A-1/2A** `19f77a3` | M8C-1 `6c6f46c`; M13-2 `664ec3b` | M7A-2C `8079c57`; M9; M13-2 | normative `COMPLETE` | **no dedicated spec; TRACEABILITY_MISSING** |
| Rigid assembly foundation | **M7A-2B** `19f77a3` | M8C-2; M13-3P | M7A acceptance; M9 | M7A normative | — |
| Exact interference / clearance primitive | **M7A-2C** `19f77a3` | M8C-3; M9-3 | M7A-2C `8079c57` | M7A normative | origin of `common().Volume`/`distToShape()` |
| Production orchestration | M8B-1 `8079c57` | M8C-3 `6c6f46c`; M12-5 | M9/M12 | M8B-1 focused | — |
| Imported assembly support | M8C-2 `6c6f46c` (synthetic) | M9-2 `a67cee3` (real trusted STEP) | M9-3 `a67cee3` | M9 | M8C-2 defects named |
| Kinematic analysis | M7C-1 `9ab9e48` (generic discrete single-axis) | M7D-2 `8079c57`; M8C-3 `6c6f46c`; M10-2..4 `89b1d75` | M9-3; M10-3/4 | M10-5 | — |
| FreeCAD live verification | M9 `a67cee3` | M13-3P `f3ab0c7` | M9 | M9 | FreeCAD 1.1.3 |
| Trusted runtime provenance | M9-4 `a67cee3` | M11-3; M12-4; M13-3P | M9 | M9 | — |
| Single-axis continuous proof | M10-1 `89b1d75` | M13-3P | M10-1/M10-5 | M10 | — |
| Multi-joint forward kinematics | M10-2 `89b1d75` | M13-3P `f3ab0c7` | M10-2 | M10 | — |
| Multi-joint exact discrete collision sweep | M10-3 `89b1d75` | M13-3P | M10-3 | M10 | `continuous_path_verified=False` |
| Continuous multi-joint path proof | M10-4 `89b1d75` | M13-3P | M10-4 | M10 | one explicit path; partition gap documented |
| Imported multi-shape transient measurement | M10-MULTI-SHAPE `28ac193` | — | M10-MULTI-SHAPE | M10 closure | status asserted earlier at `52e60e9` before implementation |
| Structural authority | M11-2 `682300b` | — | — | M11-2 | authority only |
| Gmsh/CalculiX execution | M11-3 `682300b` | — | M11-3 | M11-3 | Gmsh 4.15.0 / CalculiX 2.22 |
| FEA result interpretation | M11-4 `682300b` | — | M11-4 | M11-4 | extrapolated nodal stress |
| Durable structural Evidence | M11-5 `07950cd` | M11-6 (acceptance) | M11-5 | M11-5/M11-6 | displacement-metric convergence only |
| Candidate authority / realization | M12-2/M12-3 `28ac193` | M13-1/M13-2 | M12-4 `bae65cc` | M12-3 | — |
| Candidate comparison / selection | M12-4 `bae65cc` | — | M12-4 | M12-4 | single clearance metric |
| Promotion / canonical rebind | M12-5 `161986b` | M13-3 | M12-5 | M12-5 | — |
| Supplied-component interface authority | M13-1 `f6d8124` | — | — | M13-4E (R12) | unit-verified only at boundary |
| Generic generated-part CAD | M13-2 `664ec3b` | — | M13-2 | M13-2 marker | cylindrical stock/bore |
| Rigid-body constituent groups (M10 v2) | M13-3P `f3ab0c7` | M13-3 | M13-3P | M13-3P | v1 wire/hash preserved |
| Candidate/canonical multi-joint M10 bridge | M13-3 `ca294e0` | M13-4P | M13-3 | M13-3 | one canonical obligation |
| Promotion Evidence contract | M13-4E `185a304` | — | M13-4E R12 | M13-4E R12 | deterministic decision/result manifests |
| Full-stack candidate→promotion capstone | M13-4 `185a304` | — | M13-4 final | M13-4 final | acceptance-only component; see gaps |

## Detection results

- **BACKWARD_PROJECTION:** `M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED`
  is asserted in the documentation-only predecessor `52e60e9` before its
  implementing child `28ac193`. Documented; not corrected (historical record).
- **DUPLICATE_INTRODUCTION / naming:** "exact collision/interference/clearance"
  appears at M7A-2C (primitive), M8C-3 (production connection), and M9-3 (live
  proof). These are semantically distinct stages, and M7A is now recorded as
  the primitive's origin.
- **MISSING_INTRODUCTION (resolved):** the M7A CAD/assembly/exact-geometry
  introduction previously had no reconstruction record; it is now recorded in
  `milestones/M7A.md` with live acceptance evidence.
- **CONTRADICTORY_SUPERSESSION (documented):** `milestones/M0.md` marks the
  change-proposal model `SUPERSEDED BY M2`, while M2 consumes `ChangeProposal`
  unchanged (extended, not superseded). See `UNRESOLVED_GAPS.md`.
- **Normative-vs-reconstruction disagreement:** the capability matrix labels
  M6B-2B `AMBIGUOUS` (design-only) while the reconstruction records committed
  implementation at `928be44`. See `UNRESOLVED_GAPS.md`.

No capability is credited to a milestone that only validated it; no successor
capability is attributed to an earlier commit.
