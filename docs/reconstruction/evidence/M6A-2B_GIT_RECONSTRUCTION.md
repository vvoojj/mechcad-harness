# M6A-2B Historical Reconstruction

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

`60ccc2da6f2e6287a8d8b6baa697951f9a669404` is the direct child of
`e4f4c002365d877e6d39d97b62386b8e51e67d76` and direct parent of
`928be44a256091104b476a81fe480d2e5f1c5f7a`. The delta is 12 files,
614 insertions, and 12 deletions. No M6A-2B-specific spec, plan, README
section, audit, completion record, or acceptance record is present in the
candidate tree.

## Delivered Contract

`agents/opencode.py` implements loopback-only HTTP transport, Basic Auth,
explicit or session-selected model, project-directory transport header,
healthcheck, response-size limit, structured payload validation, provider/model/
session/message/request-hash provenance, and fail-closed errors. Gateway and
model changes preserve typed adapter execution outcomes and provenance. The
candidate adds a deny-all `.opencode/agents/mechcad-test-agent.md`.

The adapter is connected through M6A-1's persistence and binding rules. The
overall contract still forbids proposal application, tool execution, canonical
state mutation, and autonomous loops.

## Tests And Reproduction Accounting

Exactly 16 functions were added:

| File/group | Functions |
| --- | ---: |
| `test_opencode_adapter.py` | 9 |
| `test_opencode_gateway.py` | 2 |
| `test_agent_gateway.py` additions | 3 |
| two live integration files | 2 |

The predecessor contains 153 test functions and the candidate 169. The
adapter/gateway/live focused scope accounts for `21 passed, 2 skipped`; live
tests are opt-in with `MECHCAD_OPENCODE_LIVE=1`. A broader scope including
M6A-1 model/context tests yielded `29 passed, 2 skipped`. The exact-tree full-suite
reproduction is `147 passed, 21 skipped, 1 failed`; the failure is the inherited
test expecting py_gearworks to be unavailable while it is installed. No stdout,
CI artifact, or other historical transcript is retained.

## Conformance And Deviation

The candidate sends OpenCode's JSON-schema format but parses concatenated text
parts, not `info.structured_output`. The direct successor later adds native
structured-output extraction and an explicit validated-JSON-text mode, showing
the compatibility hardening required after this boundary. This does not prove
that a live M6A-2B run failed.

The test suite includes an M6A-2A-named objective, which is traceability drift.
The two live tests are skipped by default, so source presence and unit behavior
do not establish live provider acceptance.

## Successor

`928be44` preserves the adapter/gateway foundation and adds response modes,
authored-response contracts, transmission reasoning, tool mediation,
materialization, and round-trip orchestration. Later M6B-1 documentation first
appears at `8079c57`, not in this candidate.

## Review Conclusion

Skeptical review confirms the exact boundary, 16 additions, focused/full test
accounting, opt-in live behavior, structured-output gap, and absence of retained
acceptance evidence.
