# M6B-4A Historical Reconstruction

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

`3c7c70883005cbfdc91b985d9a4bc2467fd41326` is the direct child of
`53fa6c4d356cabbfed5e0fa4b35532a9ca6ba882` and direct parent of
`4468a621dfdf0662acf74501e13b5b182920cf13`. The delta is 8 files, 727
insertions, and 13 deletions. The subject is `feat: complete M6B-4A typed
resolution foundation`; this is implementation intent, not acceptance proof.
No dedicated M6B-4A spec, plan, README section, audit, completion, or
acceptance record exists in the exact candidate tree.

## Delivered Contract

The candidate defines four transmission keys and four typed answer/value
variants, including canonical angular-speed conversion from `deg/s` to `rad/s`.
It persists resolution commands and results with deterministic `CMD-*`,
`CRRES-*`, and `PARAM-*` IDs, enforces request revision/state/scope/key binding,
supports immutable replay/conflict detection, and adds canonical
`DesignState.authoritative_parameters` with anchor/key/value validation.

The discovery satisfaction rule now requires typed authoritative parameters
rather than merely a raw canonical anchor. No application, ChangeProposal,
ChangeSet, revision, invalidation, Evidence, workflow, external resolver, or
live M6B-4A path is included.

## Tests And Reproduction Accounting

The candidate has 276 top-level test functions versus 250 in the parent: 25 new
resolution tests plus one added request-satisfaction test. Two existing request
tests are also modified. It collects 282 pytest cases.
Resolution-only reproduction: `25 passed`. Resolution plus request tests:
`31 passed`. Full exact-tree reproduction: `256 passed, 25 skipped, 1 failed`;
the failure is the inherited test expecting py_gearworks to be unavailable
while it is installed.

The inherited live discovery test skips unless `MECHCAD_OPENCODE_LIVE=1`; no
M6B-4A-specific live test exists. These are reproductions only; no historical
stdout, CI result, completion report, acceptance marker, tag, or Git note is
retained.

## Conformance And Deviation

`ConstraintRequestMaterializer.materialize()` does not pass its supplied
`engineering_scope_id` into `is_satisfied()` at the candidate boundary.
Non-`transmission` scopes therefore use the hard-coded default and may be
incorrectly suppressed or created. This is a trust-boundary deviation.

## Successor

The chain is `53fa6c4 -> 3c7c708 -> 4468a62`. M6B-4C adds application/workflow
closure, state-application provenance, revision promotion, invalidation,
satisfaction, recovery, and 30 tests while consuming this candidate's typed
resolution records and authoritative parameters.

## Review Conclusion

Skeptical review confirms the exact 8-file delta, typed resolution scope,
25-plus-one test accounting, 282 collected cases, focused/full reproduction
results, absent live path, scope-default deviation, and absent acceptance
evidence.
