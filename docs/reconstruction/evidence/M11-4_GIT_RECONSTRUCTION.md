# M11-4 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_ANALYTICAL_VALIDATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_LIVE
ACCEPTANCE_STATUS: M11_4_REAL_FEA_RESULT_ANALYTICAL_VALIDATION_VERIFIED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Delivered Path

M11-4 is a logical slice of `682300b586b5e4f099d6da615a72405ba51b32e9`, after
M10 `89b1d75`, co-delivered with M11-2/3. M11-5 begins at
`07950cd1b172d2e110d1fbc1197a53bcb47f67e1`; M11-6 later begins at
`4d436cfe53b390a94490a067366c7ae3458bb045`.

The source parses strict CalculiX 2.22 FRD/DAT output into typed displacement,
stress, reaction, and criterion models, derives von Mises stress, evaluates
PASS/FAIL/NOT_EVALUABLE criteria, validates a rectangular cantilever
analytically, and exposes production evaluation. It does not publish durable
Evidence or claim mesh convergence.

## Retained Live Evidence

The committed completion report records 8 live passes and 386 focused passes;
it records full results of `1,231 passed, 34 skipped, 0 failed, 0 errors`.
The runtime is FreeCAD 1.1.3, Gmsh 4.15.0, and CalculiX 2.22. The cantilever
records `2.252616918035249 mm` maximum displacement,
`58.08477941035892 MPa` maximum von Mises stress, and `1.5198802083333157%`
analytical tip error.

These report values are retained historical evidence, not a clean-checkout
transcript. The committed FRD and DAT blobs are LF, while parser behavior
requires FRD LF and DAT CRLF materialization. Working-tree EOL conversion,
mixed source trees, and fixture materialization produce different failure
counts. The exact candidate's focused/full counts must therefore be reported
with source and EOL conditions.

## Limits And Successor

Stress is CalculiX extrapolated nodal stress; no global yield or safety claim is
made. Scope remains single-body linear-static small-deformation isotropic
elastic analysis. M11-5 adds durable Evidence and M11-6 adds final system
acceptance; neither is backward evidence for M11-4.

## Review Conclusion

Skeptical review confirms the typed result path, retained live cantilever
evidence, EOL/count qualifications, structural limits, and successor separation.
