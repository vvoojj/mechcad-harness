# M12-2 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_FOCUSED
ACCEPTANCE_STATUS: M12_2_TYPED_CANDIDATE_COMPONENT_AUTHORITY_FOUNDATION_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Delivered Foundation

M12-2 is co-delivered in `28ac193c21b8046973c7e53c304541eed88801aa`, after
`52e60e9`, within a 37-file, `+10,821/-247` bundle. Its source centers on
`candidates/models.py`, `candidates/services.py`, and candidate exports, with
the M12-2 foundation tests and completion report.

The candidate models are immutable and source-bound. Publication is explicit
through ArtifactStore, integrity/currentness are fail-closed, and canonical
state is not mutated. No component catalog, synthesis, sizing, CAD, analysis,
comparison, selection, or promotion is present.

## Evidence And Count Discrepancy

The retained report records 10 focused passes, 52 candidate/artifact/state
regressions, and `1,391 passed, 34 skipped` full-suite results. The committed
focused test file contains 11 test functions, including
`test_structural_owner_can_add_definition_but_other_owner_cannot`; exact
candidate recount therefore establishes 11 present functions, not the report's
10-pass snapshot. This is a historical count discrepancy, not evidence of
M12-4/5/6 capability.

No live FreeCAD/runtime acceptance or durable M12 candidate artifact is
retained; publication tests use temporary workspaces.

## Successor

M12-4 begins at `bae65cc` and adds candidate CAD/M10 evaluation, comparison,
and selection. That capability is not projected backward.
