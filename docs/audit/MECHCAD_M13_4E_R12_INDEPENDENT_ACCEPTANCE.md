# M13-4E R12 Independent Acceptance Audit

## Verdict

```text
M13_4E_INDEPENDENT_R12_REJECTED
```

The candidate satisfies several corrective requirements, including the focused
and predecessor gates, but it has a post-apply receipt path that does not prove
the claimed durable N+1 revision before returning the receipt. The accepted R7
contract requires that proof for every post-apply failure.

## Audit Scope

Read-only audit of the current worktree against
`docs/superpowers/specs/2026-09-06-m13-4e-multi-joint-promotion-evidence-contract.md`
and its accepted corrective plan. The candidate completion report was used only
as a navigation aid. No production, protected-surface, or test code was edited.

## Repository / Worktree State

Observed before this report was added:

```text
git status --short
 M .coverage
 M .superpowers/sdd/task-1-brief.md
 M .superpowers/sdd/task-1-report.md
 M .superpowers/sdd/task-1-review-package.md
 M .superpowers/sdd/task-2-brief.md
 M .superpowers/sdd/task-2-report.md
 M .superpowers/sdd/task-3-brief.md
 M .superpowers/sdd/task-3-report.md
 M .superpowers/sdd/task-3-review-package.md
 M src/mechcad_harness/candidates/__init__.py
 M src/mechcad_harness/candidates/promotion.py
 M src/mechcad_harness/candidates/promotion_artifacts.py
 M src/mechcad_harness/candidates/promotion_models.py
?? docs/audit/MECHCAD_M13_4E_COMPLETION_REPORT.md
?? docs/superpowers/plans/2026-08-29-task-13-review-fixes.md
?? docs/superpowers/plans/2026-09-01-m13-1-supplied-component-numeric-interface-authority.md
?? docs/superpowers/plans/2026-09-06-m13-4e-multi-joint-promotion-evidence-contract.md
?? docs/superpowers/specs/2026-09-01-m13-1-supplied-component-numeric-interface-authority.md
?? docs/superpowers/specs/2026-09-06-m13-4-representative-live-full-stack-capstone.md
?? docs/superpowers/specs/2026-09-06-m13-4e-multi-joint-promotion-evidence-contract.md
?? docs/superpowers/specs/2026-09-06-m13-4p-multi-joint-production-composition.md
?? err.txt
?? projects/
?? src/mechcad-harness/
?? tests/integration/test_m13_4e_promotion_evidence_acceptance.py
?? tests/unit/test_m13_4e_legacy_promotion_goldens.py
?? tests/unit/test_m13_4e_promotion_application.py
?? tests/unit/test_m13_4e_promotion_evidence.py
?? tests/unit/test_m13_4e_promotion_result.py
```

`git diff --stat`, `git diff`, and `git diff --check` were run. Candidate
production changes are confined to the four declared candidate files. The
`.coverage`, `.superpowers/sdd`, unrelated plan/specification, `err.txt`,
`projects/`, and `src/mechcad-harness/` entries are pre-existing unrelated
worktree noise. `git diff --check` exited successfully; Git emitted only CRLF
normalization warnings.

## Protected Surface Audit

The production diff is limited to:

- `src/mechcad_harness/candidates/promotion_models.py`
- `src/mechcad_harness/candidates/promotion_artifacts.py`
- `src/mechcad_harness/candidates/promotion.py`
- `src/mechcad_harness/candidates/__init__.py`

No diff was found in `application.py`, M10, CAD backends, state schemas, M13-3
request/evaluation/selection contracts, legacy promotion contracts, or dependency
files. The declared test files and candidate completion report are untracked,
which is consistent with the candidate scope.

## Original Compilation Identity

The normal multi-joint route retains the compiler return through publication and
the receipt: `promotion.py:2627-2630`, `2665-2673`, and `2798-2806`. No
`_align_multi_joint_evidence_compilation` symbol or replacement normalization
helper was found. The representative test at
`tests/unit/test_m13_4e_promotion_application.py:146-172` captures the compiler
return and establishes equality for the receipt and decision manifest.

The focused test fixture also accepts independent projection and mapping order:
`tests/unit/test_m13_4e_promotion_evidence.py:788-804`. The decision model
preserves the projection and requires mapping order by candidate ID without
positional projection/mapping equivalence:
`promotion_artifacts.py:338-356`.

## Projection vs Mapping Semantics

`SelectedMultiJointCandidateDecisionManifest` enforces candidate-order mapping
and the same canonical-ID universe while preserving projection order. Its full
verifier compares the complete typed mapping to the supplied original compilation
at `promotion_artifacts.py:1267-1270`; it does not zip the sequences or compare
their positions. The swapped-pair and rehashed-substitution tests pass:

```text
py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py -k "rehash_substitution or swapped_pairing" -q
12 passed, 32 deselected in 15.97s
```

This supports the required original-compilation decision boundary. Tuple member
SHA-256 grammar is independently enforced by
`promotion_models.py:478-480` and exercised in
`test_m13_4e_promotion_evidence.py:807-823`.

## R6 Rehashed Substitution Audit

The eleven parameterized R6 substitutions reconstruct typed records and
recompute their hashes before invoking the decision verifier
(`test_m13_4e_promotion_evidence.py:898-947`). The mapping substitution swaps
canonical IDs while retaining candidate order and the canonical-ID universe
(`619-659`). The focused R6 subset above passed. No R6 acceptance-blocking
defect was found.

## R7 Real ChangeEngine Persistence Audit

The named failure-injection tests use real `StateManager`, `ChangeEngine`,
`RunController`, and `EvidenceStore`; they do not replace
`apply_approved_proposal()` wholesale. The normal route calls it at
`promotion.py:2685`, and the named post-apply cases reload N+1 in
`test_m13_4e_promotion_application.py:244-413`.

This does not cover the generic post-application exception path at
`promotion.py:2720-2736`. See finding R12-01.

## Durable RevisionSnapshot Handoff

The successful route creates a typed `AppliedChangeResult` only after
`StateManager._read_snapshot(project_id, applied_revision)` at
`promotion.py:2766-2772`. The published snapshot is a `RevisionSnapshot` and
the handoff test confirms its project, revision, state hash, and state equality
with `StateManager.load_revision()`
(`test_m13_4e_promotion_application.py:79-105`). No production
`SimpleNamespace` use was found.

## R8 Metadata-Rooted Restart Audit

The fresh-restart tests recreate the manifest service, scoped store,
`StateManager`, `EvidenceStore`, and `RunController`. The verifier resolves the
decision artifact and loads the exact run ID from artifact metadata:
`promotion_artifacts.py:1363-1378` and `1432-1438`. Tests cover blank/missing
run IDs, scope mismatch, missing run, wrong project/base binding, different
result run, and an identical-looking wrong run. No latest-run or run-glob
recovery exists in the M13-4E route.

## R9 Artifact-Local Resolver Audit

`resolve_multi_joint_result()` has only `ArtifactStore` and persisted artifacts
in its signature. It does not instantiate or access `StateManager`,
`EvidenceStore`, or `RunController`. The dependency-bomb fixture in
`test_m13_4e_promotion_result.py:470-498` and the tamper matrix at `508-769`
passed as part of the focused gate. The resolver enforces namespace, metadata,
canonical bytes, result hash, decision byte/self hashes, base/result binding,
target/path, and decision/result run equality. The wrapper is exported through
`promotion_artifacts.__all__` and `candidates.__init__`.

## Legacy Golden Audit

`test_m13_4e_legacy_promotion_goldens.py` contains literal canonical JSON,
hash, artifact-ID, byte-hash, and receipt-status constants rather than deriving
expectations from the current implementation. The dedicated test is included in
the focused gate and passed.

## Test Quality Audit

The named R7 injections are narrow failures after real persistence. The result
resolver dependency bombs are legitimate isolation tests. However, the tests do
not exercise the generic exception branch after a real N+1 with a missing,
corrupt, or mismatched persisted snapshot. Therefore they do not prove the
requirement for every post-apply receipt.

## Focused Gate Results

```text
py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
111 passed in 106.81s (0:01:46)
```

No required M13-4E test skipped.

## Predecessor Gate Results

```text
py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q
75 passed in 34.07s
```

## Full-Suite Evidence Adjudication

No fresh post-hardening full-suite result was obtained in this audit. The
candidate's historical `2805 passed, 34 skipped` result predates its stated
durable-RevisionSnapshot hardening and is not credited as fresh evidence.

The accepted R10 plan requires a full regression run with at least a 6000-second
timeout. This audit did not start a new approximately hour-long full suite after
the independent CRITICAL finding already made acceptance impossible. Therefore
the fresh full-suite result is `UNVERIFIABLE`, not PASS, FAIL, or an execution-
harness classification. Its absence remains an acceptance-blocking evidence gap
until a corrected candidate produces it.

## Skip Audit

The independently run focused M13-4E gate had zero skips. No fresh full-suite
skip list is available. The historical FreeCAD timeout remains `UNVERIFIABLE`;
M13-4E has no FreeCAD live-runtime gate.

## Static/Search Audit

Targeted searches covered `SimpleNamespace`, alignment helpers, projection/
mapping sorting, latest-run/glob recovery, compilation construction,
`AppliedChangeResult`, `RevisionSnapshot`, and mocks. No candidate-production
`SimpleNamespace`, alignment helper, `latest_run`, or route-level glob was
found. The only M13-4E route `AppliedChangeResult` construction is the durable
snapshot handoff at `promotion.py:2766`. Test monkeypatches are narrow failure
injections or observation hooks, except for the missing generic-exception case
described below.

## Findings

### CRITICAL

#### R12-01: Generic post-apply exception returns an unproven N+1 receipt

- **Classification:** CRITICAL
- **Requirement:** Every partial post-apply failure must verify persisted N+1
  before returning a receipt.
- **Evidence:** `promotion.py:2720-2736` catches any exception from
  `apply_approved_proposal()`, loads only `RunController.get_run()`, and returns
  `PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED` from `current.active_revision`
  and `current.active_state_hash`. It never calls
  `StateManager.load_revision(project_id, current.active_revision)` or checks
  the durable snapshot hash. The receipt therefore makes an N+1 claim based on
  a run record alone. `test_m13_4e_promotion_application.py:244-413` covers
  only named exception classes and never injects this branch with a missing,
  corrupt, or hash-mismatched snapshot.
- **Affected files/symbols:**
  `src/mechcad_harness/candidates/promotion.py:_promote_multi_joint_route`;
  `tests/unit/test_m13_4e_promotion_application.py`.
- **Why it matters:** A post-apply receipt is trusted lifecycle evidence. It
  must not claim N+1 unless that exact persisted revision and hash can be read
  from `StateManager`.
- **Minimal remediation boundary:** Restrict the generic branch so it either
  reuses a typed applied result that proves N+1 or independently reloads and
  validates the claimed revision/hash before issuing a post-apply receipt. Add a
  real persistence regression for that branch.
- **Acceptance impact:** Blocks acceptance.

### IMPORTANT

#### R12-02: No fresh post-hardening full-suite evidence

- **Classification:** IMPORTANT
- **Requirement:** R10 requires `py -3 -m pytest -q` with at least a
  6000-second timeout after corrective implementation evidence.
- **Evidence:** The candidate report explicitly says its retained full-suite
  summary predates the final durable-snapshot hardening and that later attempts
  have no retained pytest summary. This audit did not treat that historical
  result as current evidence.
- **Affected files/symbols:** Candidate R10 evidence and
  `docs/audit/MECHCAD_M13_4E_COMPLETION_REPORT.md`.
- **Why it matters:** Focused and predecessor tests do not establish that the
  final hardening preserved the broader repository.
- **Minimal remediation boundary:** After correcting R12-01, retain one fresh
  full-suite command, exit status, exact pass/skip counts, elapsed time, and
  skip reasons.
- **Acceptance impact:** Blocks acceptance until fresh evidence exists.

### MINOR

None.

### NOTES

- `python -m compileall src tests` completed successfully.
- `git diff --check` completed successfully, aside from Git's non-failing CRLF
  warnings.
- The focused and predecessor test gates pass, but do not override the
  authority/persistence finding.

## Acceptance Decision

```text
M13_4E_INDEPENDENT_R12_REJECTED
M13_4E_ACCEPTANCE_STATUS = REJECTED
```

Acceptance-blocking findings: R12-01 and R12-02.

## Downstream Authorization

```text
M13_4P_MAY_RESUME = NO
M13_4_MAY_RESUME = NO
ROTATOR_V2_MAY_RESUME = NO
```
