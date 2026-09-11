# M13-4 Historical Reconstruction

## Verdict

```text
MILESTONE_EXISTENCE: PROVEN
DELIVERABLE_TYPE: IMPLEMENTATION_AND_SYSTEM_ACCEPTANCE
IMPLEMENTATION_STATUS: PRESENT
SPEC_CONFORMANCE_STATUS: ACCEPTED_WITH_LIMITATIONS
HISTORICAL_EXECUTION_EVIDENCE: RETAINED_FOCUSED
ACCEPTANCE_STATUS: M13_4_INDEPENDENT_FINAL_ACCEPTED
RECONSTRUCTION_CONFIDENCE: HIGH
RECONSTRUCTION_REVIEW_RESULT: PASS_WITH_NOTES
```

## Boundary And Inventory

`185a304796c17793519fb5f01dbf80cca73ab51e` is the direct child of
`ca294e045f53979cf6bc1d90404888501e50271f`. The delta is 35 files, 17,985
insertions, and 3 deletions. It bundles M13-4E, M13-4P, and the M13-4 capstone
plus their audit records. No committed `src/` or `tests/` diff follows in the
current successor, and no committed `PRJ-M13*` workspace artifact exists
(untracked `projects/PRJ-M13-2-T7` belongs to unrelated local work).

## Delivered Contract

The core production contract is M13-4E: a promotion decision-input reference
binding all relevant identities, a compact pre-application decision manifest
preserving typed compilation and candidate-to-canonical mapping, and a result
manifest binding decision artifact, proposal, ChangeSet, changed paths, base
revision/state, and actual N+1 revision/state. Manifests are deterministic
`ArtifactStore` JSON artifacts. The application receipt is transient and
hashless; trusted verification resolves durable artifacts. `EvidenceStore`
retains invalidation ownership. Failure statuses distinguish pre-apply failure,
ChangeEngine rejection, partial post-apply failures, and verified promotion.

M13-4P is composition wiring over the M13-4E route; M13-4 is the representative
live capstone and audit material.

## Evidence

Retained M13-4E R12 re-audit records `116 passed` focused, `75 passed`
predecessor, and full `2,811 passed, 34 skipped`, with R12-01/R12-02 closed.
M13-4P records `8 passed` focused, `116` M13-4E regression, `75` predecessor,
and full `2,819 passed, 34 skipped`. The final M13-4 capstone records a fresh
pass with `2,832 passed, 25 skipped`. These are candidate-tree report claims
that were not rerun during reconstruction.

## Deviations

The commit mixes implementation, remediation, independent audits, and later
acceptance records. Intermediate `M13_4E_INDEPENDENT_R12_REJECTED`,
`M13_4_RUNTIME_FULL_SUITE_RECOVERY_READY_FOR_INDEPENDENT_REAUDIT`, and
`PENDING_INDEPENDENT_REAUDIT` markers coexist with later accepted markers
(`M13_4E_INDEPENDENT_R12_ACCEPTED`, `M13_4P_INDEPENDENT_ACCEPTED`,
`M13_4_INDEPENDENT_FINAL_ACCEPTED`). The terminal authority is the
`MECHCAD_M13_4_INDEPENDENT_FINAL_ACCEPTANCE.md` record.

## Structural Boundary

Structural analysis is explicitly excluded (`M11_STATUS = UNRESOLVED`,
`M11_ELIGIBLE = False`; no structural definition, material, load, mesh, solver,
or FEA). Optional M11 handoff fields are intent/provenance binding only and do
not constitute structural execution.

## Review Conclusion

Skeptical verification confirms the exact delta, the M13-4E/M13-4P/FINAL
markers, chronological audit interpretation, durable manifest design, and
structural exclusion.
