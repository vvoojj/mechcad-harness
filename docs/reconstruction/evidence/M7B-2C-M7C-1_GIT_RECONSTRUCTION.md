# M7B-2C / M7C-1 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: BUNDLED_IMPLEMENTATION
IMPLEMENTATION_STATUS: PARTIAL_UNRUNNABLE
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Labels

`9ab9e48b8bc54202d5fddd5edc85e7f8c7c3b903` is the direct child of
`3f7bbc76f6031d1374b0b476a4d58da1dce37dfd` and direct parent of
`8079c5764d377df3b182f8ffc72a306a186b57af`. The delta is 14 files and 1,576
insertions. It bundles M7B-2C and M7C-1; M7D appears only later.

## Delivered Scope

M7B-2C implements deterministic collision-layout synthesis for two or three
envelopes, axis-aligned overlap/clearance, lateral adjustment, representative
vertical stagger, bound identities, proposal generation, and explicit
non-final statuses for placement, COM, structure, manufacturing, and mechanical
stagger.

M7C-1 implements normalized nonzero `RevoluteAxis`, quaternion transforms,
moving/stationary pair inventory, transient transformed `CadAssemblyProgram`,
temporary FreeCAD compilation, exact common-volume and distance measurements,
deterministic request/result identities, and ordered aggregate classification.
It remains discrete only with `continuous_sweep_verified=False`.

## Tests And Reproduction Accounting

M7C-1 focused tests: `20 passed, 4 skipped`. M7B-2C unit tests: `24 passed, 3
failed`. Combined focused accounting: `44 passed, 3 failed`, with 4 M7C-1 skips.
The M7B-2C live test cannot collect because it imports missing
`collision_resolved_yagi_carrier_assembly`.

The normal full suite cannot collect because the successor symbol
`collision_resolved_yagi_carrier_assembly` is missing. With
the failing live file ignored, reproduction yields `510 passed, 37 skipped, 4
failed`; one failure is the inherited py_gearworks availability assertion. The
other three are two missing ownership-rule failures and one missing
`DesignState.yagi_collision_layouts` field failure. FreeCAD discovery
was unavailable, so M7C-1 live tests skipped.

No historical stdout, durable sweep result, M7B-2C/M7C-1-specific generated artifact, CI result,
completion report, acceptance marker, tag, or Git note is retained. Later audit
numbers are not projected backward.

## Boundary Defects And Successor Repair

The candidate omits `DesignState.yagi_collision_layouts`, omits ownership for
`/yagi_collision_layouts/*`, and omits
`collision_resolved_yagi_carrier_assembly`. The missing builder makes the
M7B-2C live test uncollectable; the missing field and ownership rule cause the
unit/application failures. `8079c57` adds all three repairs while carrying M7C-1
implementation forward unchanged.

## Review Conclusion

Skeptical review confirms the bundled labels, exact 14-file delta, focused test
failures/skips, the singular missing builder symbol, discrete-only M7C-1 semantics,
unavailable FreeCAD, successor repair, and absent candidate acceptance evidence.
