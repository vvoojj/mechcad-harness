# M13-2 Completion Report

## Final Marker

M13_2_GENERIC_GENERATED_MECHANICAL_PART_CAD_FOUNDATION_VERIFIED

## Scope

M13-2 adds a generic, source-bound generated mechanical-part CAD foundation.
It supports typed generated shaft, hub, and frame authority; deterministic
CAD lowering; candidate and canonical generated-part realization; semantic
placement derivations; promotion and canonical reconstruction; and bounded
integration with the existing M10 evaluation services.

The implementation is generic and does not add Rotator V2, M13-3, M13-4,
automatic synthesis, manufacturing approval, tolerance verification, or new
CAD backends.

## Implemented

- Generated authority inputs, bindings, interfaces, frames, face semantics,
  identity hashes, and fail-closed registry validation.
- Cylindrical stock and axial bore `CadPartProgram` operations with deterministic
  manifests and FreeCAD FCStd/STEP lowering.
- Pure `GeneratedPartCompiler` with exact dimension and binding replay.
- Candidate component specification `@3` generated/imported exclusivity and
  active interface registry semantics.
- Candidate generated CAD routing with exact fidelity, trusted source imports,
  definition reuse, and derivation-set hash binding.
- Scalar-axis semantic placement derivations with coaxial and explicit-frame
  rules, including candidate and canonical replay.
- Promotion mapping `@2`, classification, derivation survival, placement
  verification, and structured canonical projection.
- Fresh canonical generated CAD compilation and reconstruction using canonical
  records only.
- M10 candidate and canonical integration regressions with a complete pair
  universe and exact-generated fidelity requirements.
- Safe FreeCAD verification probes for operation IDs containing punctuation,
  while preserving existing public probe keys.
- Candidate reference-frame identity deduplication when source and target share
  one generated definition.

## Acceptance Chain

The bounded live acceptance uses one generic fixture containing:

- A trusted imported motor STEP artifact with an authoritative M13-1
  rotational shaft interface and reference frame.
- A generated shaft with selection-bound diameter and length.
- A generated hub with an M13-1 shaft-diameter binding, explicit clearance,
  and a selected output shaft diameter binding.
- Two coaxial generated placement derivations with zero clocking.

The test proves candidate generation, real FreeCAD FCStd/STEP realization and
fresh verification, candidate M10 clearance evaluation, selection-bound
promotion, canonical generated placement derivations, fresh canonical CAD, and
canonical M10 re-verification. Fresh reconstruction does not use candidate
objects. Source artifact bytes and the historical source revision remain
unchanged.

## Verification

- `py -3 -m pytest tests/integration/test_m13_2_acceptance_live.py -q`
  -> `1 passed in 67.57s` on the final run.
- `py -3 -m pytest tests/ -q`
  -> `2348 passed, 34 skipped in 2985.53s`.
- M13-2 candidate CAD, canonical, and placement regressions -> `91 passed`.
- M12 candidate M10 and canonical regressions -> `92 passed`.
- Legacy compatibility goldens -> `9 passed`.
- `py -3 -m compileall -q src/mechcad_harness tests` -> passed.
- `git diff --check` -> passed.
- Touched untracked files -> no trailing whitespace and final newlines present.
- Protected M10 source diff -> empty.

The skipped tests are existing runtime-gated cases; the dedicated acceptance
test executed live through the available FreeCAD 1.1.3 command-line boundary.
No manufacturing-tolerance claim is made.

## Boundaries

- No M10 algorithm source was changed.
- M11, M13-1 supplied-interface authority, legacy plate behavior, imported
  component semantics, assembly backend contracts, dependency execution, and
  Rotator-specific modules remain outside this milestone.
- The normal M10-3 discrete sweep still does not imply continuous-path proof;
  this acceptance proves only its explicitly requested bounded path.
- No materials selection, FEA, optimization, tolerance analysis, or automatic
  design selection was added.

No commit was created.
