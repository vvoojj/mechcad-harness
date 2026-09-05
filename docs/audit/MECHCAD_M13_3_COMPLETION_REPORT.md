# M13-3 Completion Report

## Final Marker

M13_3_GENERIC_MULTI_JOINT_CANDIDATE_CANONICAL_M10_BRIDGE_VERIFIED

## Scope

M13-3 provides the generic physical multi-joint candidate-to-canonical bridge
through the existing M10 v2 discrete and continuous analysis boundaries. The
candidate chain is source-bound and hash-bound; canonical reconstruction uses
fresh canonical CAD, inventory, bridge, configuration authority, and M10
request construction without candidate-object lookup.

No new M10 algorithm, M10 schema, CAD inference, automatic synthesis, M11
execution, M13-4 capability, or Rotator-specific behavior was added.

## Implemented

- Neutral physical pair policy, body/member, revolute-joint, axis-source, and
  complete pair-universe authority.
- Candidate physical realization v2 validation and stable semantic lowering to
  the existing M10 v2 model.
- Candidate M10-3 request, evaluation, selection, replay, and currentness
  bindings, including ordered configuration-set and CAD placement-derivation
  hashes.
- Physical-only promotion with exactly one canonical multi-joint verification
  obligation and canonical placement-derivation projection.
- Fresh canonical CAD, inventory, bridge, configuration, and M10-3
  reconstruction from canonical state and trusted artifacts.
- Candidate/canonical semantic comparison over model versions, body/member
  offsets, joints, pair classifications/reasons, inventory meaning, exact
  scope, configurations, tolerances, and placement derivations.
- Focused bridge-generated M10-4 coverage through the existing production API.

## Acceptance Evidence

The candidate chain uses a trusted imported motor, generated shaft, generated
hub, two semantic generated-placement derivations, a physical revolute
binding, complete pair policy, ordered configurations, candidate M10
evaluation/selection, promotion, and fresh canonical reconstruction. The fresh
canonical M10 service creates a new v2 request from the canonical obligation
and executes it through the composed production application. Candidate and
canonical request hashes are allowed to differ; semantic model/configuration
authority is compared independently.

The canonical replay test asserts that the generated hub retains the derived
axial placement offset of `2.0` mm after candidate objects are discarded.
Substituted placement derivations and stale source bindings are rejected.

## Verification

- `py -3 -m pytest tests/unit/test_m13_3_fresh_canonical_m10.py tests/integration/test_m13_3_candidate_m10_production.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py tests/integration/test_m13_3_bridge_m10_4.py -q`
  -> `13 passed in 15.75s`.
- `py -3 -m pytest tests/`
  -> `2704 passed, 25 skipped in 3123.43s`.
- `py -3 -m compileall -q src tests` -> passed.
- `git diff --check` -> passed.
- Protected M10 source and test diff -> empty.

The skipped tests are existing runtime-gated cases. The dedicated M13-3
candidate/canonical acceptance test is not skipped. FreeCAD-backed M10 and
M13-3P regressions remain included in the full-suite result.

## Boundaries

- Ordinary M10-3 discrete results do not imply continuous-path verification.
- M10-4 remains an explicit-path proof, not a configuration-space certificate.
- Structural analysis, FEA, materials selection, manufacturing approval,
  tolerances, optimization, and automatic candidate synthesis remain outside
  this milestone.
- Stress, yield, safety, fatigue, dynamics, thermal, nonlinear, and assembly
  structural claims are not made.

No commit was created.
