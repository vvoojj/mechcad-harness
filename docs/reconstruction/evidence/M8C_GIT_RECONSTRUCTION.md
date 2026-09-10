# M8C Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_IMPLEMENTATION
IMPLEMENTATION_STATUS: ARCHITECTURALLY_CLOSED_RUNTIME_GATED
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_AUDIT_SUMMARY
ACCEPTANCE_STATUS: RUNTIME_GATED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`6c6f46c06fb0ba624639832c1f7c224d3c34d39b` is the direct child of
`8079c5764d377df3b182f8ffc72a306a186b57af` and direct parent of
`a67cee375e793a573fe4c77fceddf9cea76d9dc0`. The delta is 19 files, 3,483
insertions, and 10 deletions. It bundles M8C-1, M8C-2, and M8C-3.

The target includes three specs, two plans, one aggregate M8C closure audit,
six source-file changes, and seven test files. M8C-1 has no separate plan. No
M8C files are added under `workspace/`; existing workspace artifacts are
inherited from earlier milestones.

## Delivered Layers

M8C-1 provides spec validation, deterministic CAD program compilation, and a
source-bound compilation service. M8C-2 provides typed artifact-backed
components, fail-closed resolution, mixed generated/imported assembly identity,
artifact byte-integrity checks, and an assembly service. M8C-3 adds production
application entrypoints over unchanged generic kinematic/transient cores.

Canonical spec/program/component/assembly/result identities and source
revision/hash checks are implemented. DesignState remains isolated and
`continuous_sweep_verified=False`.

## Tests And Retained Evidence

The candidate adds 81 test functions: 35 M8C-1, 35 M8C-2, and 11 M8C-3. The
aggregate audit reports `632 passed, 51 skipped`; the M8C-3 plan retains a
conflicting `629 passed, 51 skipped` earlier count. Skips are FreeCAD-gated.
These are documentary audit/plan summaries, not raw execution logs. No durable
M8C kinematic result, provider provenance, or live FreeCAD transcript exists.

## Candidate-Limit Findings

`FreeCADAssemblyBackend._compile` can route imported components through the
generated-part branch because imported artifacts already appear in
`part_artifacts`; M9-2 adds explicit imported routing, canonical names, and
temporary-object removal. The transient provider supports generated parts only,
so mixed imported/generated sweeps fail until M9-3 adds trusted imported-artifact
resolution. Assembly callers can provide authored provenance without explicit
component resolution.

Other accepted limitations are caller-preaccepted DesignSpec, separate
compilation provenance, runtime-only run ID, absent provider/backend provenance,
and no live FreeCAD execution. The candidate diff also contains trailing
whitespace.

## Successor

`a67cee3` preserves M8C as a runtime-gated baseline. Later M9 live work creates
real STEP, reloads mixed FreeCAD assemblies, measures exact volume/distance,
persists execution provenance, and fixes the two mixed-import paths. M9
acceptance must not be projected backward.

## Review Conclusion

Skeptical review confirms the 19-file delta, three-layer scope, 81 tests,
conflicting audit/plan counts, FreeCAD-gated evidence, no workspace additions,
successor fixes, and runtime-gated classification.
