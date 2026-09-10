# M7B-1B Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Scope

`7c7352a57632d6202a25351761f5cfe0e15adc5b` is the direct child of
`19f77a30ef42040d5f07688ab4235a25daaba7f0` and direct parent of
`30b99eb02cf2fbb627fb59378e34372dbd7adfc9`. The delta is 11 files, 457
insertions, and 5 deletions. Naming evidence identifies this as M7B-1B;
there is no supported R3 label.

The source adds plate requirements authority/resolution, ownership,
deterministic synthesis, envelope/edge/ligament/opening/stock calculations,
`NOT_READY`/`INFEASIBLE`/`SUCCESS` outcomes, bound hashes, draft proposals,
and CAD-path integration. It does not apply proposals, persist canonical plate
state, analyze structure, select materials, optimize, ingest hardware, or write
durable Evidence.

## Tests And Reproduction Accounting

Exactly 16 test functions are added:

| File | Functions |
| --- | ---: |
| `test_m7b1b_synthesis.py` | 8 |
| `test_m7b1br_authority.py` | 7 |
| FreeCAD integration addition | 1 |

Top-level `test_*` functions are `396 -> 412`; collected pytest cases are
`415 -> 431`. The full reproduction is `399 passed, 31 skipped, 1 failed`
versus the parent's `383 passed, 31 skipped, 1 failed`; the unchanged failure
is the inherited py_gearworks-unavailable expectation while version 0.0.18 is
installed.

The integration test uses synthetic data and
`M7B1B_TEST_FIXTURE_ONLY` provenance. No historical stdout, generated artifact,
CI result, completion report, acceptance marker, tag, or Git note is retained.

## Conformance And Deviations

The FreeCAD guard tests package importability instead of
`discover_freecad().available` and hard-codes the executable. Authority and
plate carriers use `tuple[dict]` / `list[dict]` rather than fully typed domain
models. The service checks only that the supplied state hash is non-empty; it
does not recompute the hash from the state.

Mount-point ordering is normalized. Stock-thickness ordering does not affect
the selected `88 x 78 x 8 mm` geometry, but it remains significant to the
requirements hash, synthesis hash, and proposal ID.

## Successor

The relevant chain is `19f77a3 -> 7c7352a -> 30b99eb -> 3f7bbc7 -> 9ab9e48`.
`30b99eb` begins Yagi payload-carrier authority work; later commits add Yagi
CAD closure and kinematic sweep. Those are successor work, not candidate-era
acceptance evidence.

## Review Conclusion

Skeptical review confirms the M7B-1B label, exact 11-file delta, 16 tests,
396/412 and 415/431 accounting, full-suite reproduction, synthetic fixture
boundary, and recorded identity/typing deviations.
