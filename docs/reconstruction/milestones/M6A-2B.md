# M6A-2B - OpenCode Gateway

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

M6A-2B is `60ccc2da6f2e6287a8d8b6baa697951f9a669404`, the direct child of
M6A-1 `e4f4c002365d877e6d39d97b62386b8e51e67d76` and direct parent of
`928be44a256091104b476a81fe480d2e5f1c5f7a`. It changes 12 files with 614
insertions and 12 deletions.

## Historical Role And Result

The commit adds a loopback-only HTTP OpenCode adapter through the existing
gateway. It provides Basic Auth without persisted passwords, explicit/session
model selection, project-directory headers, health and response-size checks,
structured response validation, execution outcome/error provenance, and
fail-closed adapter errors. A deny-all `.opencode` test-agent declaration is
also added.

The scope remains reasoning-only: no automatic proposal application, tool
execution, canonical-state mutation, or engineering-agent semantics.

## Tests And Execution Evidence

The commit adds 16 test functions: 9 adapter, 2 OpenCode gateway, 3 gateway /
provenance, and 2 opt-in live integration tests. The exact candidate has 169
test functions; its predecessor has 153.

The focused adapter/gateway/live scope accounts for `21 passed, 2 skipped`;
the two live tests skip unless `MECHCAD_OPENCODE_LIVE=1`. A broader focused
scope including authoritative-context and model tests yielded `29 passed, 2
skipped`.
The exact-tree full-suite reproduction is `147 passed, 21 skipped, 1 failed`,
where the failure is the inherited py_gearworks availability assumption.
These results are not retained historical execution evidence.

## Material Deviations

- No M6A-2B-specific spec, plan, README section, completion report, or
  acceptance artifact exists at this boundary; the M6A-1 docs remain the
  predecessor documentation.
- The adapter sends OpenCode JSON Schema but parses concatenated text parts
  rather than native `info.structured_output`.
- The live integration test's task objective includes an M6A-2A label,
  indicating traceability drift.

## Successor Relationship

`928be44` directly extends this adapter/gateway foundation and hardens response
handling with native structured-output extraction and validated-JSON-text mode,
then adds broader M6B orchestration. That successor behavior confirms the
candidate compatibility gap but does not prove M6A-2B live acceptance.

## Reconstruction Conclusion

M6A-2B is a proven implemented OpenCode gateway slice, offline-tested in
reproduction, with a structured-output compatibility deviation and no retained
formal acceptance evidence.

See [detailed Git evidence](../evidence/M6A-2B_GIT_RECONSTRUCTION.md).
