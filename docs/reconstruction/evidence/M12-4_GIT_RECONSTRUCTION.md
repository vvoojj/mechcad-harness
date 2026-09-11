# M12-4 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_LIVE_VALIDATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M12_4_CANDIDATE_CAD_M10_EVALUATION_COMPARISON_SELECTION_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Delivered Scope

`bae65cc3663f97b8a2c669e6940f8660b4732a58` is the direct child of
`28ac193c21b8046973c7e53c304541eed88801aa` and direct parent of
`161986b9d4a4d6b19e8afa9e2ee8e58f8f06eb2b`. The delta is 23 files, 11,856
insertions, and 17 deletions.

The source realizes candidate-bound trusted/bounded CAD, maps physical
components, evaluates existing M10 exact/continuous scope, emits immutable
FEASIBLE/INFEASIBLE/UNRESOLVED results, compares only certified clearance lower
bounds, and selects noncanonically. It does not promote or mutate canonical
state.

## Live Evidence

Retained candidate audit results are 157 focused passes, 15 M12-4
integration/capstone passes including 5 FreeCAD-gated tests,
151 shared regression passes with 1 skip, and two full runs of
`1,707 passed, 34 skipped` out of 1,741 collected. FreeCAD 1.1.3, subprocess
execution, and exact `common().Volume`/`distToShape()` are recorded.

The three direct-drive outcomes are FEASIBLE, INFEASIBLE, and UNRESOLVED under
clear, collision, and constrained-budget conditions. Comparison proves
certified ranking and ties; selection works with/without comparison and can
choose a non-top-ranked feasible candidate with rationale.

No M12-4 candidate artifact is committed. Live source artifacts are transient;
later M12-5 promotion is not part of this boundary.

## Limits And Reproducibility

Only supplied-component direct-drive/external-spur, one-joint, explicitly
sampled/pair-scoped M10 evaluation is supported. There is no automatic catalog
selection, optimization, manufacturing/tolerance/safety/strength/mass claim,
or structural/FEA bridge. External-spur internal motion remains unmodeled.

DAT parser fixtures require Windows CRLF materialization; raw Git-blob replay
without that normalization can produce unrelated parser failures. The
historical validated runs used the normalized Windows checkout.

## Successor

`161986b` adds canonical promotion and fresh canonical CAD/M10 rebinding. It
consumes this selected-candidate boundary and does not belong to M12-4.

## Review Conclusion

Skeptical review confirms the exact delta, focused/live/full results, real
FreeCAD path, deterministic comparison/selection, noncanonical boundary, and
CRLF reproducibility qualification.
