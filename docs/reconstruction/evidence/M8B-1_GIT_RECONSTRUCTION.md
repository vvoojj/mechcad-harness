# M8B-1 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: CO_DELIVERED_IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_FOCUSED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Attribution

M8B-1 is co-delivered in `8079c5764d377df3b182f8ffc72a306a186b57af`, child of
`9ab9e48` and parent of `6c6f46c`. The subject names M8B-2, so the complete
187-file, `+21,399/-60` delta must not be attributed exclusively to M8B-1.
M8B-1 source centers on `src/mechcad_harness/application.py` and supporting
run/state/agent/tool changes; M8B-2 and M7 work are separate logical slices.

## Delivered Contract

The composition root constructs the service graph and emits immutable state/run
bindings. It validates project pointers, active revision/state hash, expected
source, fixed `mechcad-transmission@1.0` identity, exact `name@version` tool
permissions, and registration. Nested state is defensively copied. A narrow
project synchronization guard closes revision/run persistence races.

No task execution, workflow API, CAD ingress, provider bridge, scheduler, or
OpenCode default is introduced by this slice.

## Evidence

Committed SDD reports record 51 passed production/run tests, 15 passed
state/change regressions, passing compile checks, and earlier incremental
results. They were produced under Python 3.14; Python 3.11 was unavailable.
The reports explicitly prohibit commits during execution and were retained in
the target commit, so they are focused documentary evidence, not independent
system acceptance. No target-wide full-suite result or dedicated M8B-1 closure
record exists.

## Deviations

The implementation adds a constrained in-process/OS lock although the design
excludes a concurrency subsystem; reports describe it as revision/run race
protection only. The adapter remains injection-only and no default agent is
registered. The shared commit co-delivers M8B-2 and unrelated M7/workspace
content.

## Successor

M8B-2 uses this graph in the same commit. Direct successor `6c6f46c` extends
the application with M8C imported-component, mixed-assembly, and kinematic
paths. Later M9 acceptance is not M8B-1 standalone acceptance.

## Review Conclusion

Skeptical review confirms the co-delivered attribution, composition scope,
focused retained results, Python limitation, lock deviation, and absent
standalone acceptance.
