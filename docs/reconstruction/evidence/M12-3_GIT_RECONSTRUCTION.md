# M12-3 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_FOCUSED
ACCEPTANCE_STATUS: M12_3_BOUNDED_PHYSICAL_REVOLUTE_DRIVE_REALIZATION_SIZING_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Delivered Scope

M12-3 is co-delivered in `28ac193c21b8046973c7e53c304541eed88801aa`, whose
complete delta is 37 files, `+10,821/-247`. Its source is the revolute-drive
models/calculations/service and spur engineering primitive; its spec, plan,
completion report, eight focused/integration test modules, and production
entrypoint are all in the candidate tree.

The implementation supports exactly one scoped revolute joint with direct-drive
and external-spur templates, motor admissibility, nominal gear calculations,
efficiency-bound torque, and two-support static solid-shaft sizing. Results and
provenance are deterministic and source/candidate-bound. No CAD/FreeCAD,
ArtifactStore/EvidenceStore, M10/M11 executor, catalog/selection, optimization,
gear life/strength, fatigue, tolerance, or complete-machine safety is present.

## Evidence

Retained execution reports record 158 focused passes, 36 candidate/state/tool
regressions, 66 production/provider regressions, and full
`1,550 passed, 34 skipped, 0 failed, 0 errors`. They also record compile checks
and no Important/Critical review findings. This is focused/runtime evidence;
there is no separate live FreeCAD acceptance.

Integration tests verify no canonical revision, ChangeEngine call, publication,
Evidence, workspace file, or agent invocation. Derived gear mesh-plane mapping
remains `UNRESOLVED`.

## Successor

`bae65cc` adds candidate CAD/M10 evaluation, comparison, and selection; later
promotion/live acceptance is not M12-3 evidence.
