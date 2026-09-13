# F11 Task 1 Report

## Status

DONE

Task 1 test specification is complete. The focused gate was run before any
production implementation, and it failed for the expected missing
`analysis.section` behavior.

## Files Changed

Only the six Task 1 test files were modified:

- `tests/unit/test_section_tools.py`
- `tests/unit/test_section_warping_tools.py`
- `tests/unit/test_section_engineering_tools.py`
- `tests/unit/test_dependency.py`
- `tests/unit/test_structural_evidence_models.py`
- `tests/unit/test_structural_evidence_verifier.py`

The required report file is this file. No production code, configuration,
reconstruction documentation, accepted audit record, or plan was modified.

## Tests Added or Updated

- Section geometry, warping, and preliminary engineering controller fixtures
  now recognize only `analysis.section`.
- Section geometry and warping executions request `analysis.section` and assert
  the persisted Evidence kind and absence of a structural payload.
- Complete preliminary section engineering requests `analysis.section` and
  asserts the persisted generic Evidence kind and absence of a structural
  payload.
- The existing partial preliminary engineering assertion remains in place and
  continues to require `partial.evidence_id is None`.
- Added node-specific readiness/freshness isolation and scoped invalidation
  coverage for `analysis.section` and `analysis.structural`, including the
  intentionally shared material invalidation family.
- Extended the structural discriminator test to lock the
  `analysis.structural` subject value, kind, and payload semantic hash.
- Added structural verifier coverage proving a generic `analysis.section` tool
  record is rejected with the existing fail-closed error.

## Focused RED Gate

Exact command:

```text
python -m pytest tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q
```

Exact pytest result counts:

```text
2 failed, 143 passed, 2 skipped in 31.08s
```

Completion-verification rerun of the same exact command reproduced the same
counts:

```text
2 failed, 143 passed, 2 skipped in 30.32s
```

The two skipped tests are the optional section geometry and warping success
tests. Their existing skip reason is:

```text
structural profile is not installed
```

## Failure Classification

Both failures are expected RED evidence for the unimplemented Task 2 changes.
There were no unrelated failures.

- `tests/unit/test_dependency.py::test_section_and_structural_nodes_have_isolated_readiness_and_invalidation`
  fails while writing the deliberately generic `analysis.section` record with:
  `EvidenceIntegrityError: unknown dependency node: analysis.section`.
  This proves the current dependency configuration does not yet recognize the
  new node.
- `tests/unit/test_section_engineering_tools.py::test_complete_stiffness_result_creates_evidence_but_partial_result_does_not`
  fails at the deliberate `analysis.section` ToolBroker request with:
  `ToolExecutionError: tool is not declared to produce evidence node`.
  This proves the current M5.5C registration still authorizes the old node.

The section geometry and warping authorization tests were skipped because the
optional `sectionproperties` package is unavailable in this environment. The
engineering test exercised the same registration authorization boundary and
failed for the expected reason.

## Verification And Scope Review

- `git diff --check -- tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py`
  produced no output and no whitespace errors.
- The test-only diff is `158 insertions, 8 deletions` across six files.
- No FreeCAD, Gmsh, or CalculiX command was run.
- No commit, push, reset, stash, clean, or staging operation was run.
- Pre-existing dirty and untracked work was preserved.
- No production implementation was added, consistent with Task 1 and the
  required pre-implementation RED gate.

## Self-Review

The changes stay within the exact Task 1 file list and cover each requested
boundary: producer node separation, wrong-family readiness/freshness, scoped
invalidation, unchanged M11 typed identity, and structural verifier rejection.
The RED failures are caused by the two intended absent Task 2 implementation
pieces, not by test setup errors or unrelated regressions. The optional skips
are explicitly reported rather than counted as passing execution evidence.

## Review Fix Wave

The requested Task 1 review findings were addressed without changing
production, configuration, plans, documentation outside this report,
reconstruction records, accepted audits, or unrelated work:

- The partial preliminary-engineering call now requests
  `evidence_node="analysis.section"` while retaining
  `partial.evidence_id is None`.
- Added a structural-only readiness scenario proving structural Evidence does
  not make `analysis.section` fresh.
- Added real ToolBroker negative authorization tests for geometry, warping, and
  preliminary engineering registrations. They use invalid inputs so the
  current RED path is deterministic and reaches broker input validation only
  when the old node is still authorized.
- Replaced the tautological semantic-hash comparison with an explicit
  `structural_evidence_hash(evidence_payload)` recomputation.

Exact fix-wave command:

```text
python -m pytest tests/unit/test_section_tools.py tests/unit/test_section_warping_tools.py tests/unit/test_section_engineering_tools.py tests/unit/test_dependency.py tests/unit/test_structural_evidence_models.py tests/unit/test_structural_evidence_verifier.py -q
```

Exact fix-wave result:

```text
5 failed, 144 passed, 2 skipped in 29.30s
```

Completion-verification rerun of the same exact command reproduced the same
counts:

```text
5 failed, 144 passed, 2 skipped in 29.07s
```

Failure classification for the fix wave:

- `test_section_and_structural_nodes_have_isolated_readiness_and_invalidation`
  still fails with `EvidenceIntegrityError: unknown dependency node:
  analysis.section`, as expected until Task 2 adds the configured node.
- `test_complete_stiffness_result_creates_evidence_but_partial_result_does_not`
  still fails with `ToolExecutionError: tool is not declared to produce
  evidence node`, as expected until Task 2 changes the engineering
  registration.
- The geometry, warping, and engineering negative authorization tests each
  fail their expected authorization-message match with `ToolExecutionError:
  invalid tool input`. This is expected RED evidence that the current
  registrations still authorize the old `analysis.structural` node and only
  reject the deliberately invalid inputs later in the broker path.

The fix-wave additions introduced no unrelated failures. The two optional
section geometry/warping success tests remain skipped because
`structural profile is not installed`.
