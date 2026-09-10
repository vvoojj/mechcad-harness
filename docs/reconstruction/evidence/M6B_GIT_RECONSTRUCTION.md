# M6B Historical Reconstruction

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

## Boundary And Inventory

`928be44a256091104b476a81fe480d2e5f1c5f7a` is the direct child of
`60ccc2da6f2e6287a8d8b6baa697951f9a669404` and direct parent of
`53fa6c4d356cabbfed5e0fa4b35532a9ca6ba882`. It changes 30 files, with 2,481
insertions and 86 deletions. Its subject identifies M6B-2B, but the commit
bundles M6B-1, M6B-2A, and M6B-2B. M6B-specific specs/plans and acceptance
records do not exist in this exact tree; later documentation cannot be used as
candidate-era proof.

## Delivered Layers

M6B-1 adds the deny-all transmission agent, authored response schema, validated
JSON-text mode, selected context, and immutable AgentResult without a canonical
transmission field or automatic proposal application. M6B-2A adds semantic
`transmission.torque` mediation, exact trusted `mechcad-calc-torque@1.0`
mapping, mediation records, permission checks, and persisted ToolCall/ToolResult
without Evidence. M6B-2B adds deterministic materialization of successful
ToolResults into Evidence and a one-tool/two-invocation round trip with
freshness checks and selected Evidence in Invocation B.

No canonical mutation, proposal application, transmission synthesis, stress
analysis, or general workflow execution is present.

## Tests And Reproduction Accounting

The candidate adds 68 top-level test functions, from 169 in the parent to 237
in the candidate. Pytest collection reports 243 cases. The literal M6B-focused
scope yields `87 passed, 3 skipped`; adding dependency/tools/runtime/OpenCode
gateway regression files yields `116 passed, 3 skipped`. The complete exact
snapshot yields `218 passed, 24 skipped, 1 failed`; the failure is the inherited
test expecting py_gearworks to be unavailable while version 0.0.18 is installed.
Three M6B-specific live tests require `MECHCAD_OPENCODE_LIVE=1` and skip
otherwise; the full tree also contains two inherited opt-in OpenCode live tests.

These are available reproductions only. No stdout, CI artifact, live OpenCode
log, completion report, acceptance marker, tag, or Git note is retained.

## Conformance And Trust-Boundary Notes

The implementation preserves invocation-before-execution, typed provenance,
exact mediation mapping, ToolCall/ToolResult persistence, Evidence
materialization, freshness checks, and no automatic canonical mutation.

Observed deviations are:

- `gateway.py` hard-codes role `test` instead of preserving registered
  transmission identity.
- Invocation B declares no tools; a B tool request fails rather than producing
  the designed durable second-tool-request observation.
- `resume()` handles terminal workflow files only, not the complete intermediate
  crash-boundary recovery later described.
- Round-trip mediation lookup scans final files instead of a deterministic index
  and full linkage validation.
- Global ToolBroker permissions still accept bare names.
- An inherited live task objective retains an M6A-2A label, which is test
  traceability drift rather than an M6B-added implementation issue.

## Successor

`53fa6c4` adds M6B-3. `3c7c708` and `4468a62` follow with later M6B work.
`8079c57` is a later M8B-2 successor that connects production composition and
adds design/retrospective material; it is not M6B acceptance evidence.

## Review Conclusion

Skeptical review confirms the bundled scope, exact 30-file delta, 68 added
functions, 243 collected cases, focused/full reproduction accounting, opt-in
live behavior, and absent candidate-era acceptance evidence.
