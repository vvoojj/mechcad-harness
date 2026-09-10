# M6B-4A - Typed Resolution Foundation

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

M6B-4A is `3c7c70883005cbfdc91b985d9a4bc2467fd41326`, the direct child of
M6B-3 `53fa6c4d356cabbfed5e0fa4b35532a9ca6ba882` and direct parent of M6B-4C
`4468a621dfdf0662acf74501e13b5b182920cf13`. It changes 8 files with 727
insertions and 13 deletions. No separate M6B-4B commit exists.

## Historical Role And Result

The commit implements four typed transmission keys and answer/value unions,
canonical angular-speed conversion including `deg/s` to `rad/s`, durable
resolution commands/records, deterministic `CMD-*`, `CRRES-*`, and `PARAM-*`
identities, strict request revision/state/scope/key binding, immutable replay
and conflict detection, and `DesignState.authoritative_parameters` validation.

It tightens discovery satisfaction from raw-anchor presence to matching typed
authoritative parameters. It does not apply state, create ChangeProposal or
ChangeSet records, create revisions/invalidation, write Evidence, orchestrate a
workflow, authorize external resolvers, or provide a live M6B-4A path.

## Tests And Execution Evidence

The candidate grows from 250 to 276 top-level test functions: 25 new resolution
tests plus one added request-satisfaction test. Two existing request tests are
also modified. It collects 282 pytest cases. Resolution
tests reproduce `25 passed`; resolution plus request tests reproduce `31 passed`.
The full exact-tree reproduction is `256 passed, 25 skipped, 1 failed`, with the
inherited py_gearworks availability assertion causing the failure.

The inherited live discovery test skips without `MECHCAD_OPENCODE_LIVE=1`; no
M6B-4A-specific live test exists. No retained transcript, completion report,
acceptance record, CI artifact, tag, or Git note exists.

## Material Deviations

- `ConstraintRequestMaterializer.materialize()` omits `engineering_scope_id`
  when calling `is_satisfied()`, so non-`transmission` scopes use the default
  scope and may be incorrectly suppressed or created.
- No dedicated M6B-4A spec, plan, README section, or acceptance record exists
  at the candidate boundary.

## Successor Relationship

M6B-4C adds application, workflow, state-application provenance, revision
promotion, invalidation, satisfaction, recovery, and 30 tests. It directly
consumes M6B-4A resolution records and authoritative parameters; that confirms
the foundation boundary but does not establish M6B-4A acceptance.

## Reconstruction Conclusion

M6B-4A is a proven typed resolution foundation with partial scope handling,
offline reproduction coverage, and no retained formal acceptance evidence.

See [detailed Git evidence](../evidence/M6B-4A_GIT_RECONSTRUCTION.md).
