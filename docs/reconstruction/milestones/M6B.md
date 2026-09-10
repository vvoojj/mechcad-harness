# M6B - Transmission Round Trip

## Status

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: PARTIAL
HISTORICAL_EXECUTION_EVIDENCE: NOT_RETAINED
ACCEPTANCE_STATUS: NOT_FOUND
RECONSTRUCTION_CONFIDENCE: HIGH
```

## Git Boundary

M6B is bundled in `928be44a256091104b476a81fe480d2e5f1c5f7a`, titled
`feat: complete M6B-2B transmission tool round trip`. It is the direct child of
M6A-2B `60ccc2da6f2e6287a8d8b6baa697951f9a669404` and direct parent of M6B-3
`53fa6c4d356cabbfed5e0fa4b35532a9ca6ba882`. The commit changes 30 files with
2,481 insertions and 86 deletions.

## Historical Role And Result

The single commit delivers M6B-1 authored transmission responses and validated
JSON-text mode, M6B-2A semantic `transmission.torque` mediation to the exact
trusted torque tool, and M6B-2B ToolResult-to-Evidence materialization with a
one-tool/two-invocation coordinator. The boundary ends at a second reasoning
AgentResult with selected Evidence; it does not mutate canonical DesignState,
apply proposals, synthesize transmissions, analyze strength, or execute a
general workflow.

## Tests And Execution Evidence

The candidate adds 68 top-level test functions: the exact parent has 169 and
the candidate has 237. The exact candidate collects 243 pytest cases. Focused
M6B tests reproduce `87 passed, 3 skipped`;
a broader regression scope reproduces `116 passed, 3 skipped`. The full exact
snapshot reproduces `218 passed, 24 skipped, 1 failed`, due to the inherited
py_gearworks availability assertion. Three live tests are opt-in through
`MECHCAD_OPENCODE_LIVE=1` and did not run without that setting; these are the
three M6B-specific live tests.

These are reconstruction reproductions, not retained historical execution
evidence. No candidate-era spec, plan, completion report, CI transcript,
acceptance record, tag, or Git note exists.

## Material Deviations

- The gateway hard-codes agent role `test` rather than preserving registered
  transmission identity.
- Invocation B uses a no-tool schema; a B tool request becomes
  `INVOCATION_B_FAILED` rather than a durable `SECOND_TOOL_REQUEST` observation.
- `resume()` handles terminal workflow files but not every intermediate crash
  boundary described by later design material.
- Mediation lookup scans `*/final.json` instead of a deterministic mediation
  index with complete linkage validation.
- The global ToolBroker still accepts bare-name permissions despite exact-name
  mediation policy.
- An inherited live integration task objective contains an M6A-2A label,
  indicating test traceability drift rather than an M6B implementation issue.

## Successor Relationship

`53fa6c4` is the direct M6B-3 successor; later M6B-4A and M6B-4C follow. The
later `8079c57` adds M8B-2 production composition and design/retrospective
material, not candidate-era M6B acceptance.

## Reconstruction Conclusion

M6B is a proven implemented transmission round-trip slice with substantial
offline test coverage, known contract narrowings, opt-in live tests, and no
retained formal acceptance evidence.

See [detailed Git evidence](../evidence/M6B_GIT_RECONSTRUCTION.md).
