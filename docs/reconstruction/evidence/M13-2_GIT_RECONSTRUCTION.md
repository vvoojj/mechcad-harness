# M13-2 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_LIVE_VALIDATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M13_2_GENERIC_GENERATED_MECHANICAL_PART_CAD_FOUNDATION_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`664ec3bf4ad7ef6d038f8e5bac483382dbda1125` is the direct child of
`f6d812422794e034eaf91d94ea88412e504b1488` and sole parent of
`f3ab0c7b16000bb14041c7f0fa56cef375441ceb`. The delta is 36 files, 16,491
insertions, and 97 deletions: generated-part/placement models and authority,
CAD program/backend changes, candidate promotion/canonical realization, spec/
plan/audit, and ten new plus five modified test modules.

## Delivered Scope

Generated shaft/hub/frame authority, `CylindricalStockOperation` and
`AxialBoreOperation`, deterministic `generated-part-compiler@1` lowering,
candidate and canonical generated-part realization, semantic placement
derivations (`frame-generated-placement@1`, `coaxial-generated-placement@1`),
promotion mapping `candidate-canonical-mapping@2`, canonical schemas
`@3`/`canonical-physical-mechanism@2`, and bounded M10 integration are added.
Legacy `@1` hash payloads omit generated derivations to preserve stability.

`EXACT_GENERATED_GEOMETRY` is exact only with respect to the bound semantic
specification; no tolerance, materials, FEA, manufacturing, or stepped-shaft/
keyway/spline/thread feature support is added.

## Tests And Reproduction

Independent reproduction: eight M13-2 unit files `197 passed in 36.35s`; five
modified predecessor files `105 passed in 11.31s`; compound live acceptance
`1 passed in 67.55s`; three standalone generated-parts live tests skipped
because FreeCAD was not discovered, while the acceptance test hardcodes the
FreeCAD 1.1 executable. The retained report records full suite
`2,348 passed, 34 skipped`, not re-run during reconstruction.

The live acceptance proves candidate CAD generation and double-run determinism,
fresh reload with analytic volume/bounding-box/probe verification, candidate M10
`FEASIBLE`/`verified_clear`, promotion to canonical mechanism `@2` with two
derivations, fresh canonical reconstruction and CAD regeneration without
candidate objects, canonical M10 `verified_clear`, revision N+1 with N
immutable, and unchanged source motor bytes/hash with backend provenance 1.1.3.

## Deviations

The completion report ends "No commit was created" while the commit exists; the
spec status header remains stale; predecessor tests are edited (source-backed
specs now require trusted source geometry); and no M13 baseline update appears
in `AGENTS.md`/architecture docs.

## Successor

`f3ab0c7` (M13-3P) does not modify M13-2 source and is a sibling capability.
Later M13-3/M13-4 extend integration files but leave M13-2 core modules
unchanged, confirming M13-2 as a stable consumed foundation.

## Review Conclusion

Skeptical verification confirms the exact delta, 152/201 test accounting, live
acceptance path, marker, and the noted provenance/baseline gaps.
