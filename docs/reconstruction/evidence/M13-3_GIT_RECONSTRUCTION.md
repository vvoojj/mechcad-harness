# M13-3 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_LIVE_VALIDATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M13_3_GENERIC_MULTI_JOINT_CANDIDATE_CANONICAL_M10_BRIDGE_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`ca294e045f53979cf6bc1d90404888501e50271f` is the direct child of
`f3ab0c7b16000bb14041c7f0fa56cef375441ceb` and sole parent of
`185a304796c17793519fb5f01dbf80cca73ab51e`. The delta is 40 files, 13,317
insertions, and 22 deletions: five new source modules
(`multi_joint_m10_bridge.py`, `multi_joint_m10_evaluation.py`,
`multi_joint_selection.py`, `models/multi_joint_verification.py`,
`models/physical_pair_policy.py`), ten modified modules, spec/plan/audit, and 21
new test files.

## Delivered Bridge

A single pure `_compile_physical_to_m10_core` feeds candidate and canonical
adapters. `PhysicalMechanismRealization@2` carries rigid-body bindings,
revolute-joint bindings, a kinematic root, and complete pair classifications;
canonical mirror is `CanonicalPhysicalMechanism@3`. Validation enforces one body
owner and one CAD mapping per instance, exact realization/assembly member
agreement, single root, one incoming joint per non-root, acyclicity, and
directed drive/intent endpoints. Placements use full-precision
`inverse(T_ref_home)*T_member_home` offsets. Axis lowering resolves the
source-local axis into the parent-reference frame with post-resolution sign.

The stable `physical-to-m10-v2-model@1:<sha256>` model ID depends only on
topology, so candidate and canonical share it while fresh CAD differs.
`physical_to_m10_bridge_hash` binds physical/root/joint/pair identities,
placement identities, CAD mapping hashes, model/inventory/scope hashes with
finalization ordering to avoid a cycle. `compare_candidate_canonical_multi_joint_semantics`
compares after explicit projection under `rigid-transform-agreement@1.0`
without requiring raw hash equality. Only cross-body `CHECK_CLEARANCE` pairs
enter the exact scope; same-body pairs must be `SAME_RIGID_GROUP_EXCLUDED`.
`CanonicalMultiJointM10VerificationService` requires exactly one canonical
obligation and re-executes through the trusted tolerance adapter.

## Evidence

The 21 new test files collect 205 cases; an independent candidate run
reproduced `204 passed, 1 skipped` (the skip is the FreeCAD-gated M10-4 bridge
test). The retained report records `2,704 passed, 25 skipped` full-suite results
and an empty protected-M10 diff, not re-run during reconstruction. The generic
acceptance test proves fresh canonical reconstruction without candidate objects,
candidate≠canonical request hashes with a bound result hash, and that a `2.0`
mm hub axial offset survives derivation reconstruction.

## Deviations And Limits

The completion report says no commit was created although the commit exists;
`AGENTS.md` omits M13; the full-suite result was not reproduced. M10-3 is
discrete and M10-4 proves only the requested path. Only one canonical obligation
is supported. No M10 algorithm change, CAD inference, M11 execution, FEA,
materials, tolerance, optimization, or synthesis is added.

## Successor

`185a304` (M13-4) builds strictly above M13-3 without rewriting its files.

## Review Conclusion

Skeptical verification confirms the exact delta, 205-collection/204-pass
reproduction, verified marker, bridge semantics, and bounded limits.
