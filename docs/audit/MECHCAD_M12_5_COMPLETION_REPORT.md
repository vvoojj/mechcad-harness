# M12-5 Completion Report

## Scope And Status

M12-5 Task 20 documentation and acceptance evidence are complete. The bounded
implementation consumes one explicitly selected, current feasible M12 candidate,
compiles canonical physical authority, applies one proposal through the ordinary
`RunController`/`ChangeEngine` path, reconstructs canonical state, rebinds fresh
CAD and M10 identities, and optionally assesses post-promotion M11 eligibility.

Bounded status: `M12-5 focused and live integration verified`.

Final disposition: `M12_5_PROMOTION_CANONICAL_REBIND_M11_HANDOFF_VERIFIED`.

This report does not claim M12-6, general synthesis or automatic selection,
candidate stores, rollback, assembly or broad structural verification, or M11
execution. M11 remains an eligibility-only post-promotion handoff.

## Authority And Mutation Boundaries

- `DesignState` remains the sole canonical authority. `physical_mechanisms` is a
  typed collection of complete `CanonicalPhysicalMechanism` values.
- `CandidatePromotionCompiler` is read-only with respect to state and external
  execution. It produces one complete canonical mechanism, one proposal, a
  semantic proposal hash, an explicit mapping, and a frozen projection.
- The only canonical mutation is `RunController.apply_approved_proposal()`, which
  calls the generic `ChangeEngine`. The promotion service does not call
  `ChangeEngine` directly or mutate state.
- The configured ownership path is
  `/physical_mechanisms/* -> mechcad-physical-mechanism`; the live operation is
  exactly one `add` at `/physical_mechanisms/<canonical-id>`.
- `ChangeEngine.apply_proposal()` holds the existing re-entrant project lock while
  revalidating the expected base and creating the revision. There is no promotion
  lock, rebase, retry, second engine, or rollback.

## Pre Promotion And Post Identities

The direct-drive live capstone starts at revision `N=1` with source state hash
`sha256:5e852eddfbe053762fcccb1ec13b73dbf3eb28c5c7de3914cc57133676e7baf9` and
revision-file byte hash
`sha256:5201b0fc6172fcaa2a7e87303e3f11d0ac86fbe917156caea3277b900c25d41f`.
Promotion creates exactly one revision, `N+1=2`, and the test fresh-loads and
byte-compares revision N after promotion.

The final direct-drive runs produced these identity sets:

| M11 intent | Candidate / candidate CAD / candidate M10 | Decision / proposal / result | Canonical projection / CAD / M10 | N+1 state | Scope |
|---|---|---|---|---|---|
| mapped mount/support | `sha256:203607c0f26f04888c00a31f62c3e75aa3239f5e9ff3f2866d5fa60459983b9c` / `sha256:8dee56696eeebfaf9eff42b840f1b00d55b03e2bc0f3f74f6c6fccc611140040` / `sha256:cad4a499899bcccfdc416537207e2d7066b3c59217f5b262120cc9795942c98e` | `PROMOTION-DECISION-745b07d1e13430e8b755ac59` / `sha256:a1835720158cdb9d9c022a70c547c741ef0cdb5a041a482a06a6b784ed0755e2` / `PROMOTION-RESULT-d7a5a698460711a6514e201c` (`sha256:d7a5a698460711a6514e201c6669d95b5714b9335d2a3967a6fdf3fdb5445f67`) | `sha256:65bf5efd8c9ebbddf9a02053990d0760b6372e2250a871f6f8125309a9278ab1` / `sha256:e6a9bc709d235c886162c30779487228b5f70abd7c9807b06c4592e008bb67ca` / `sha256:9c5444f67ffea5c923dd02ad65b6ead0e82d6b81014de557552011b7dd025262` | `sha256:29dd17e424d1c5fca73bc90d90862a164bd8053f4501c33e54f5da69f85f42a2` | `sha256:bbe09b58d47ab9db69f629dc555c21cb5d194c7810a8a7374cfc76f38202eefb`; M11 `UNRESOLVED` |
| whole mechanism | `sha256:bf8ff06ae3943e6b2cba1a21bb889cff0d5d57bdadaca6216ab8352afa22da89` / `sha256:c6b4cfdf559e8fd9ee87555c8dde8e1e5b2ebabca7587b9ae9af37271d9c12c1` / `sha256:bdc6ae9477b8e7530d8658c1a56b5b1d3c0e1727f8b66bb56262e3759c8306c9` | `PROMOTION-DECISION-5fae96f4564305cd9b2b99a6` / `sha256:002c12e1d90230a4ee55fc588b7b65e21c94d1a0b53a0f1be22ee3c22eb4a02b` / `PROMOTION-RESULT-75695eb7710fa61156fe7f01` (`sha256:75695eb7710fa61156fe7f01336cd0b41b5adfe474bb869bf638375702332b2b`) | `sha256:4660a318b42f0eb54c2112b248568f0c70e5f6972da49327bb1df41cdf98ca95` / `sha256:bf2723dda3b10dca0787a720283f3b78dd42dcd7c3b5b2de7f71294f53f56746` / `sha256:260286ce82d7181e822ada997f0960cc4faa6433e6a18133f7aa7932128756d1` | `sha256:6116f3bb20b9df6063f0385ed76f51c2977ecd7db8c4d837cc8abd195b3dfe0a` | `sha256:95271d7313ffd7b511d1bb5091c5280f8d9bff0aea3d2882aa99a19a481f7521`; M11 `NOT_ELIGIBLE` |

Candidate CAD realization/request and canonical CAD realization/request hashes
differ. Candidate M10 request and canonical M10 request hashes also differ. The
canonical projection contains promoted physical semantics, not candidate runtime
identities.

## Operation And Path Summary

The direct-drive operation was:

```text
add /physical_mechanisms/PM-task17-direct-drive
```

The external-spur operations were:

```text
add /physical_mechanisms/PM-task18-external-spur
add /physical_mechanisms/PM-task18-external-spur-no-comparison
```

Each invocation created one normal N-bound run, one decision artifact, one
ChangeEngine revision, one invalidation record, and one result artifact. The
external-spur comparison-used path selected an explicit feasible non-top-ranked
candidate; the no-comparison path did not invoke comparison. Promotion never
re-ranked or promoted comparison-only values.

## Direct Drive And External Spur Capstones

Direct-drive live evidence used FreeCAD 1.1 command-line runtime at
`C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`. Both parameterized M11 intent
cases completed with fresh canonical CAD and M10 `VERIFIED_CLEAR` results and an
overall promoted verification status of `VERIFIED`. The whole-mechanism intent
was `NOT_ELIGIBLE`; the explicit mapped mount/support target was `UNRESOLVED`.
Neither case made a structural execution call.

External-spur comparison-used canonical identities were:

- mechanism `sha256:596cc50f6b735a059716b3bf080eec3d06cd74a3abe7e502874e59d61244f66d`;
  promoted state `sha256:b5c164cacfc119379d7252dd22235fe1a2e71d824d89362d99fecbe9226af951`;
- CAD request `sha256:77c3df3081caa226bbe0465bbf2721d48be86164b9eef065f24c1386e866173e`;
  realization `sha256:8fdfd35d1b0e8fd40945c2f789824a99ce3d29cedde2b9f37aecf7126706c778`;
- M10 request `sha256:aba1a71463023ec387f779ba68661c4843787c15abcaa04d83bfc23ada779355`;
  result `sha256:58fc84b28c6224fe5d29b898394a3d4a3a21119daeda8a662a8521169aa7c7ab`.

External-spur no-comparison canonical identities were:

- mechanism `sha256:c77fc4aff8a2599a7e629af15df343dcd073c38babf66a751a0803632867cf7f`;
  promoted state `sha256:a29a9d1ce5534a2021505dd6c2819d1640edbae7731b4393a84e7f16e4725c4d`;
- CAD request `sha256:83d6709d3d1633d7e27f78429681bc529aa33935ee42a6c141e05ef72349865a`;
  realization `sha256:021589e0fe85f062e3b8310db19581c04288489e98a80dd6ec63b5fe9d748d2c`;
- M10 request `sha256:3bdb6e2a89ed8b86997cb5071e8028f48726e562748e01b2a749e13b86205389`;
  result `sha256:ecb701f1b3258f3ca69eef3fec928985afabbb76669bf1bd3bf6ee4787cf62e0`.

The gear mesh remains physical/interface semantics. The driver remains
`INTERNAL_MOTION_UNMODELED`; the gear pair is excluded as intended contact, and
no ratio, coupling, phase, backlash, or transmission-internal clearance claim is
created.

## Rejected And Failure Cases

Focused regressions cover fail-closed rejection of stale or forged candidates,
non-admissible M12-3 results, non-feasible or unresolved evaluations, candidate /
evaluation / selection / comparison substitutions, missing or byte-tampered
trusted sources, property and design-variable substitutions, incomplete or
duplicated classifications, policy-origin zero/false values, delimiter-bearing
IDs, target collisions, incomplete projections, and semantic tampering of a reused
operational proposal ID.

Application-stage regressions distinguish decision publication failure,
`CHANGEENGINE_REJECTED`, post-apply invalidation persistence failure, post-apply
invalidation verification failure, run-transition failure, and result provenance
failure. Pre-application failures preserve revision N and its serialized bytes;
post-application failures preserve the truthful N+1 receipt and do not roll back.
Replaying the same N-bound request after promotion returns a stale pre-application
failure and does not add a second mechanism.

Canonical source foreignness, selected-source byte tampering, canonical source
identity corruption, projection tampering, CAD/backend failure, M10 collision or
`NOT_PROVEN`, malformed manifests, and historical manifest binding failures are
also covered. Candidate objects can be discarded before canonical CAD/M10
re-execution from N+1 state and selected trusted sources.

## M11 Non-Gating Assessments

`PostPromotionM11TargetIntent` exists only as pre-promotion workflow intent; it
does not contain an N+1/HN1 canonical handoff request. The canonical
`CanonicalM11HandoffRequest` is constructed only after successful ChangeEngine
application, invalidation verification, `CandidatePromotionResultManifest`
verification, canonical reconstruction, and target resolution through the
persisted candidate-to-canonical mapping. The request is then bound to N+1/HN1
before eligibility assessment. The direct-drive capstone demonstrates both
accepted non-executing outcomes:

- Whole mechanism target: `NOT_ELIGIBLE`.
- Explicit mapped mount/support single-solid target without complete structural
  authority: `UNRESOLVED`.

Both cases retain overall bounded promotion status `VERIFIED`, and the structural
service call list is empty. M12-5 does not fabricate material, load, support,
region, structural-definition, STEP, mesh, request, or solver inputs.

## Durable Manifest And Run Storage Ordering

The verified ordering is:

```text
readiness -> compilation -> normal run at N/HN -> run-scoped ArtifactStore
-> decision publish -> decision fresh reload -> RunController/ChangeEngine
-> invalidation fresh reload/verification -> result publish
-> result fresh reload -> canonical reconstruction/CAD/M10/M11 assessment
```

The decision manifest is pre-application and binds N/HN, the request references,
policy, compilation/proposal/projection hashes, scope projection, and mapping. It
does not claim an applied revision. The result manifest binds the decision
artifact, semantic proposal identity, operational proposal/ChangeSet IDs, changed
paths, mechanism path, and N+1/HN1. Both are immutable JSON artifacts in the same
normal run scope. Equivalent manifest publication through another run scope
produces the same semantic identities and bytes, proving `run_id` is excluded from
promotion semantic identity.

## Cross-Revision Source Provenance

Selected STEP artifacts are byte-verified from the project-wide ArtifactStore and
may retain their original N/HN artifact binding. Canonical CAD and its request /
realization identities bind N+1/HN1 separately. The live direct-drive test
preserved the exact original revision bytes and state hash above. External-spur
replay fresh-loaded every selected source artifact and compared its bytes after
canonical re-execution. No source artifact was republished or rebound.

## Race Ordering

The generic ChangeEngine race tests use `threading.Event` barriers and no sleeps.
They cover both orderings: a promotion-first writer commits N+1 while a competing
N-bound writer then fails stale-base validation, and a competing writer commits
N+1 before promotion acquires the lock so promotion fails stale without revision
N+2. A nested project-lock test confirms the existing re-entrant lock behavior.
The promotion application therefore cannot commit a payload validated against an
intervened base.

The final targeted race and post-apply failure regression command was:

```text
py -3 -m pytest tests/unit/test_changes.py::test_apply_revalidates_after_promotion_before_competing_writer_can_commit tests/unit/test_changes.py::test_apply_rejects_promotion_after_competing_writer_commits_without_extra_revision tests/unit/test_changes.py::test_apply_proposal_is_safe_under_nested_project_lock tests/unit/test_m12_promotion_apply.py::test_decision_publication_failure_fails_created_run_without_canonical_mutation tests/unit/test_m12_promotion_apply.py::test_change_engine_rejection_is_distinct_and_does_not_advance_revision tests/unit/test_m12_promotion_apply.py::test_post_apply_run_transition_failure_is_not_change_engine_rejection tests/unit/test_m12_promotion_apply.py::test_post_apply_invalidation_persistence_failure_preserves_applied_revision tests/unit/test_m12_promotion_apply.py::test_invalidation_verification_failure_keeps_applied_revision_and_publishes_no_result tests/unit/test_m12_promotion_apply.py::test_result_provenance_failure_never_rolls_back_applied_revision -q
9 passed in 3.73s
```

## Invalidation Verification

After controller application, promotion fresh-loads the invalidation record and
checks project, N+1 revision, N parent revision, exact changed paths, and
ChangeSet ID before publishing the result manifest. Persistence failure and fresh
verification failure are separate post-application statuses. Both preserve N+1,
publish no successful result manifest, and make no canonical `VERIFIED` claim.

## Exact Verification Evidence

Focused M12-5 matrix, final fresh run:

```text
py -3 -m pytest tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py tests/unit/test_m12_canonical_physical_mechanism.py tests/unit/test_m12_canonical_reconstruction.py tests/unit/test_m12_m11_handoff.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_projection.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promoted_verification.py tests/unit/test_m12_promotion_replay.py tests/unit/test_m12_candidate_foundation.py tests/unit/test_m12_candidate_cad_compiler.py tests/unit/test_m12_candidate_m10_service.py tests/unit/test_m12_candidate_evaluation.py tests/unit/test_m12_candidate_selection.py tests/unit/test_m12_candidate_comparison.py tests/unit/test_changes.py tests/unit/test_runs.py tests/unit/test_dependency.py tests/unit/test_artifacts.py tests/integration/test_transient_imported_multishape_collision.py -q
401 passed in 110.28s (0:01:50)
```

Required M12-5 integration, final fresh run:

```text
py -3 -m pytest tests/integration/test_m12_promotion_production.py -q -s
5 passed in 391.09s (0:06:31)
```

The integration run reported FreeCAD available through the bundled FreeCAD 1.1
command-line executable and exercised direct-drive, external-spur comparison,
external-spur no-comparison, replay, source cleanup, canonical re-execution, and
both optional M11 intents.

Full repository run, final fresh run with an explicit 3700-second ceiling:

```text
py -3 -m pytest tests/ -q
```

Auditable invocation details:

```text
OpenCode tool timeout ceiling: 3700000 ms (3700 s)
Process result: exit code 0
Pytest elapsed: 1941.16s (0:32:21)
Pytest result: 1930 passed, 34 skipped
```

No failure node rerun was required because this invocation exited zero. The prior
Task 19 run remains a documented historical discrepancy: it timed out one live
FreeCAD subprocess and reported `1929 passed, 34 skipped, 1 failed`; the current
fresh invocation is the authoritative final result.

## Compile, Diff, And Untracked Scans

Final required commands:

```text
py -3 -m compileall -q src/mechcad_harness tests
git diff --check
```

Both completed with exit code 0 and no whitespace errors. Git emitted only its
normal LF/CRLF working-copy warnings. The explicit scan covered 26 new or
untracked M12-5 source, test, specification, plan, audit, and Task 20 report
files:

```text
M12_5_SCANNED_FILE_COUNT=26
TRAILING_WHITESPACE_MATCH_COUNT=0
MISSING_FINAL_NEWLINE_COUNT=0
```

The scan included all eight M12-5 production modules, twelve unit tests, the
promotion integration test, the M12-5 specification, both M12-5 plans including
the Task 13 review-fix plan, both audit/task-20 reports, and this completion
report.

## Known Limits And Full-Suite Status

The accepted M12-5 capability is explicit and bounded. It does not generate or
select candidates, certify arbitrary configuration space, model general gear
coupling or driver internal motion, perform rollback, publish a candidate store,
perform assembly/contact FEA, or execute M11. Canonical M10 remains the unchanged
bounded single-axis proof path after fresh canonical rebinding. M11 assessment is
eligibility-only and non-gating.

The final full-suite skip count was 34, matching the accepted predecessor
baseline. The authoritative final invocation exited zero with 1930 passed, 34
skipped, 0 failed, and 0 errors.

## Files And Worktree

Files changed by the final Task-20 documentation correction:

- `docs/audit/MECHCAD_M12_5_COMPLETION_REPORT.md`
- `docs/superpowers/plans/2026-08-29-m12-5-promotion-canonical-rebind-m11-handoff.md`
- `.superpowers/sdd/task-20-report.md`

Files changed by this final reconciliation:

- `docs/audit/MECHCAD_M12_5_COMPLETION_REPORT.md`

The M12-5 implementation/test/configuration file set includes the following
principal paths:

- Production: `src/mechcad_harness/models/physical_mechanism.py`,
  `src/mechcad_harness/candidates/promotion_models.py`,
  `src/mechcad_harness/candidates/promotion.py`,
  `src/mechcad_harness/candidates/promotion_artifacts.py`,
  `src/mechcad_harness/candidates/canonical_mechanism.py`,
  `src/mechcad_harness/candidates/canonical_cad.py`,
  `src/mechcad_harness/candidates/canonical_m10.py`,
  `src/mechcad_harness/candidates/m11_handoff.py`,
  `src/mechcad_harness/candidates/__init__.py`,
  `src/mechcad_harness/application.py`,
  `src/mechcad_harness/changes/engine.py`,
  `src/mechcad_harness/runs/controller.py`,
  `src/mechcad_harness/runs/errors.py`,
  `src/mechcad_harness/runs/__init__.py`, and
  `src/mechcad_harness/agents/constraint_resolution_application.py`.
- Configuration: `config/ownership.yaml` and `config/dependencies.yaml`.
- Tests: `tests/unit/test_m12_*.py`, `tests/unit/test_changes.py`,
  `tests/unit/test_runs.py`, `tests/unit/test_dependency.py`,
  `tests/unit/test_artifacts.py`, `tests/unit/test_constraint_resolution_application.py`,
  `tests/unit/test_production_application.py`,
  `tests/integration/test_m12_promotion_production.py`, and
  `tests/integration/test_transient_imported_multishape_collision.py`.

The existing capability-reference and M12-5 implementation/test changes were
preserved and not modified by this reconciliation. The worktree remains
intentionally dirty with M12-5 implementation/test/configuration files and
unrelated user or generated changes. No commit, tag, push, reset, checkout,
stash, cleanup, or other destructive Git operation was performed.
