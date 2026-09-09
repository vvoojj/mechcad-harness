# M13-4E R12 Independent Re-Audit

## Verdict

```text
M13_4E_INDEPENDENT_R12_ACCEPTED
```

```text
R12-01 = CLOSED
R12-02 = CLOSED
```

This is a fresh, independent re-audit performed after the R12 rejection and the
subsequent narrow remediation. No production, test, or protected-surface code
was modified by this audit. The only file this audit created is this report.

## Audit Independence

This session did not perform the M13-4E implementation or the R12 remediation.
All commands below were executed independently in this session against the
exact received worktree. Candidate/report claims were treated as claims to
verify, not as evidence.

## Historical Context

- The initial corrective candidate was rejected by
  `docs/audit/MECHCAD_M13_4E_R12_INDEPENDENT_ACCEPTANCE.md`
  (`M13_4E_INDEPENDENT_R12_REJECTED`) with findings CRITICAL R12-01 (generic
  post-apply exception issued a trusted N+1 receipt from
  `Run.active_revision` / `Run.active_state_hash` without durable state proof)
  and IMPORTANT R12-02 (no fresh post-hardening full-suite evidence).
- The remediation is described in
  `docs/audit/MECHCAD_M13_4E_R12_REMEDIATION_REPORT.md` and the updated
  candidate evidence in `docs/audit/MECHCAD_M13_4E_COMPLETION_REPORT.md`.
- Authority documents used: accepted spec
  `docs/superpowers/specs/2026-09-06-m13-4e-multi-joint-promotion-evidence-contract.md`
  (failure-semantics table at lines 571-587; receipt field semantics at lines
  468-485; verifier requirements at lines 677-705) and the accepted corrective
  plan `docs/superpowers/plans/2026-09-06-m13-4e-multi-joint-promotion-evidence-contract.md`.

## Repository / Worktree State

`git status --short` (recorded before this report was added):

```text
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
?? docs/audit/MECHCAD_M13_4E_R12_INDEPENDENT_ACCEPTANCE.md
?? docs/audit/MECHCAD_M13_4E_R12_REMEDIATION_REPORT.md
?? docs/superpowers/plans/... (three untracked plan files)
?? docs/superpowers/specs/... (four untracked spec files)
?? err.txt
?? projects/
?? src/mechcad-harness/
?? tests/integration/test_m13_4e_promotion_evidence_acceptance.py
?? tests/unit/test_m13_4e_legacy_promotion_goldens.py
?? tests/unit/test_m13_4e_promotion_application.py
?? tests/unit/test_m13_4e_promotion_evidence.py
?? tests/unit/test_m13_4e_promotion_result.py
```

Classification:

- M13-4E semantic production changes: the four `src/mechcad_harness/candidates/*` files.
- M13-4E test files: the five untracked M13-4E test files.
- Audit/report files: the three untracked audit documents plus this report.
- Pre-existing unrelated worktree noise (verified by timestamps, not assumed):
  `.coverage` (8/28), `.superpowers/sdd/*`, unrelated plans/specs, `err.txt`
  (8/22), `projects/` (newest entry 9/3), `src/mechcad-harness/` (8/24 stray
  directory containing a 9/3-era structural solver copy — unrelated to M13-4E).
- `git diff --check`: exit 0; only non-failing CRLF normalization warnings.
- `git diff --stat`: production changes confined to the four candidates files
  (2169 insertions / 1068 deletions total including the noise files).

## Remediation Diff

The tree is an uncommitted candidate, so the remediation scope was verified by
file timestamps against the rejection-report write time (9/7/2026 10:34 AM):

| File | Last write | After rejection? |
| --- | --- | --- |
| `src/mechcad_harness/candidates/promotion.py` | 9/7 1:07 PM | YES (declared scope) |
| `tests/unit/test_m13_4e_promotion_application.py` | 9/7 1:06 PM | YES (declared scope) |
| `src/mechcad_harness/candidates/promotion_models.py` | 9/6 4:47 PM | no |
| `src/mechcad_harness/candidates/promotion_artifacts.py` | 9/6 9:46 PM | no |
| `src/mechcad_harness/candidates/__init__.py` | 9/6 11:21 AM | no |
| audit reports (remediation/completion) | 9/7 2:05 PM | reports only |

This exactly matches the declared remediation scope: semantic changes only in
`promotion.py` plus the application regression tests, and report updates.

## Protected Surface Audit

- `git status`/`git diff` show no modifications outside the four authorized
  candidates files. `src/mechcad_harness/application.py`, M10 implementation,
  CAD backends, state schemas, M13-3 request/evaluation/selection/promotion
  contracts, legacy promotion contracts, and dependency files are untouched.
- `candidates/__init__.py` diff is additive exports only (multi-joint models,
  resolvers, and verifiers), consistent with the accepted plan R9.
- The remediation introduced no changes to M13-3/M12/legacy semantics
  (timestamped above; content inspection of the verifier and models found only
  the accepted-candidate semantics previously reviewed by the prior audit).

## R12-01 Re-Audit

The generic post-apply exception branch in
`src/mechcad_harness/candidates/promotion.py:2722-2759` now performs:

1. `current = self.run_controller.get_run(run.run_id)` — reloaded durable run
   identifies the claimed applied revision.
2. Guard `current.active_revision > run.initial_revision` — only a run that
   actually advanced is considered.
3. `persisted_state = self.compiler.state_manager.load_revision(request.project_id, current.active_revision)`
   — durable load of exactly the claimed revision, project-bound.
   `StateManager.load_revision` routes through `_read_snapshot`
   (`state/manager.py:190-206`), which independently validates
   `snapshot.project_id`, `snapshot.revision`, `snapshot.state.revision`, and
   recomputes `state_hash(snapshot.state)`, raising on any mismatch or missing
   snapshot.
4. Exact equality checks `persisted_state.revision != current.active_revision`
   and `state_hash(persisted_state) != current.active_state_hash` — any
   mismatch raises and is swallowed into the fail-closed path.
5. Only on the `else` path does the branch return
   `PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED` with
   `applied_revision=current.active_revision` and
   `applied_state_hash=current.active_state_hash` — i.e., the values that were
   just proven equal to the durable persisted state.
6. Every failure (get_run failure, no advance, load failure, mismatch) falls
   through to `_fail_created_run(run, exc)` and a `PRE_APPLY_FAILURE` receipt
   with no `applied_revision`, no `applied_state_hash`, no
   `result_artifact_id`, and a required `error`.

Data-flow answers:

1. Loaded revision: `current.active_revision`, from the durable reloaded run.
2. Origin: `RunController.get_run` (durable run record) — used only to
   identify a claim, never as proof.
3. Loaded revision compared to claim: yes (`_read_snapshot` + explicit check).
4. Loaded state hash compared to claim: yes (recomputed canonical JSON hash).
5. Project identity bound: yes (`load_revision(request.project_id, ...)` plus
   `_read_snapshot` project-id envelope validation).
6. Receipt uses verified values: yes.
7. No exception path can bypass validation and still issue an N+1 receipt:
   the inner `try/except/else` only issues the receipt on the validated path.
8. Stale run state cannot be trusted: hash/revision equality with the durable
   snapshot is mandatory.
9. A result artifact ID cannot appear on this receipt (parameter defaults to
   `None` and is not passed; the receipt model additionally forbids it).
10. A physically existing untrusted result file cannot be promoted: the branch
    returns before result publication and carries no result artifact ID.

The remediation seam `_validate_applied_multi_joint_run`
(`promotion.py:2824-2827`) is a typed-run validation only; it does not alter
controller mechanics or fabricate authority.

The `PRE_APPLY_FAILURE` fail-closed path is permitted by the accepted contract:
the receipt model (`promotion_models.py:1006-1013`) forbids
`result_artifact_id` and the applied identity pair for `PRE_APPLY_FAILURE`, so
the fail-closed receipt asserts no N+1 fact at all — it does not falsely claim
anything. No new receipt status was added, matching the remediation claim.

**R12-01 = CLOSED.**

## Generic Post-Apply Regression Matrix

```text
py -3 -m pytest tests/unit/test_m13_4e_promotion_application.py -k "generic_post_apply" -q
5 passed, 13 deselected in 10.36s   (exit 0)
```

Matches the claimed `5 passed, 13 deselected`. Case-by-case audit
(`tests/unit/test_m13_4e_promotion_application.py:244-334`):

- Real machinery: `_route_inputs` builds a real `StateManager`, real
  `ChangeEngine`, real `RunController`, real `EvidenceStore` over `tmp_path`.
  `apply_approved_proposal()` is NOT monkeypatched; real ChangeEngine N→N+1
  application completes before the injected exception
  (`_raise_generic_after_real_application` wraps only
  `_validate_applied_multi_joint_run`, which runs after the real controller
  call returns).
- `test_generic_post_apply_exception_verifies_real_durable_n_plus_one`:
  wraps `load_revision` with a recording delegate that still calls the real
  loader; asserts `durable_loads` non-empty (the generic branch actually
  exercised the durable N+1 load), status
  `PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED`,
  `applied_revision == source_revision + 1`, and
  `applied_state_hash == state_hash(durable_loads[-1])` (independent hash of
  the real loaded state — not circular), `result_artifact_id is None`.
- `..._fails_closed_when_durable_n_plus_one_cannot_load` (FileNotFoundError /
  OSError at exactly N+1): asserts `PRE_APPLY_FAILURE`, no applied identity,
  no result artifact ID.
- `..._fails_closed_when_run_disagrees_with_durable_state` (run claims N+2 or
  a bogus hash on the generic-branch `get_run` call): asserts `PRE_APPLY_FAILURE`
  with no applied identity.

No forbidden pattern: no wholesale `apply_approved_proposal` monkeypatch, no
`SimpleNamespace`, no fabricated `RevisionSnapshot`/`AppliedChangeResult`, no
fake `StateManager` returning the asserted value, no exception injected before
real persistence.

## Fail-Closed Semantics

The receipt model (`promotion_models.py:988-1027`) structurally enforces:

- `PRE_APPLY_FAILURE` / `CHANGEENGINE_REJECTED`: `result_artifact_id`,
  `applied_revision`, `applied_state_hash` must all be absent; `error` required.
- Every post-apply status: request/readiness/compilation/decision artifact ID
  and the applied revision+hash pair are required; `result_artifact_id` absent.
- `PROMOTION_APPLIED`: everything required, error absent.

Therefore a trusted N+1 claim cannot exist without an applied identity, and
every such claim is independently re-proven by
`verify_multi_joint_promotion_application_result`
(`promotion_artifacts.py:1397-1414`: `StateManager.load_revision` +
`state_hash` equality + `applied_revision == decision.base_revision + 1`).

## Post-Apply Branch Audit

| Branch | Failure point | Can N+1 exist? | Source of applied rev/hash | Durable authority | StateManager validation | Result artifact | Receipt semantics |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `PostApplyInvalidationError` (promotion.py:2688) | invalidation persistence after run transition | Yes | `exc.applied.snapshot` | `ChangeEngine.apply_proposal` → `StateManager.create_revision` durable `RevisionSnapshot` | snapshot IS the durable write | absent | `PROMOTION_APPLIED_BUT_INVALIDATION_PERSISTENCE_FAILED` |
| `PostApplyRunTransitionError` (2700) | run transition persistence | Yes | `exc.applied.snapshot` | same durable snapshot | snapshot IS the durable write | absent | `PROMOTION_APPLIED_BUT_RUN_TRANSITION_FAILED` |
| `ChangeError` (2712) | ChangeEngine rejection before revision creation | No | — | — | — | absent | `CHANGEENGINE_REJECTED` |
| Generic exception (2722) | any unexpected post-apply failure | Possible | reloaded run claim, then exact durable reload | `StateManager.load_revision` revision+hash equality | YES (mandatory) | absent | `RUN_TRANSITION_FAILED` only if proven; else `PRE_APPLY_FAILURE` |
| Invalidation verification failure (2768) | after successful controller return | Yes | `applied_run` = durable-reloaded run returned by `apply_approved_proposal` | durable run + ChangeEngine snapshot lineage; verifier re-proves exact N+1 | via downstream verifier (`promotion_artifacts.py:1397-1414`) | absent | `PROMOTION_APPLIED_BUT_INVALIDATION_VERIFICATION_FAILED` |
| Result publication/resolution failure (2800) | after verified invalidation; `applied` built from `_read_snapshot` | Yes | `applied_run` + durable `AppliedChangeResult` | same | via downstream verifier | absent | `PROMOTION_APPLIED_BUT_RESULT_PROVENANCE_FAILED` |
| Complete route (2812) | — | Yes | durable result manifest | full verifier path (result + decision + invalidation + state + run) | YES | trusted resolved ID | `PROMOTION_APPLIED` |

No sibling defect of the form "run/transient/ambient value → trusted N+1
receipt without durable proof" was found.

## Durable RevisionSnapshot / AppliedChangeResult Audit

- `Runs/errors.py`: `PostApplyRunTransitionError`/`PostApplyInvalidationError`
  carry `applied: AppliedChangeResult` from the controller.
- `changes/engine.py`: `apply_proposal` returns
  `AppliedChangeResult(snapshot=state_manager.create_revision(...))` — the
  real durable `RevisionSnapshot`.
- The successful route constructs the only production `AppliedChangeResult` at
  `promotion.py:2780-2786` with
  `snapshot=self.compiler.state_manager._read_snapshot(project_id, applied_revision)`
  — a real validated durable snapshot (`_read_snapshot` validates project,
  revision envelope, and recomputed hash).
- Test `test_result_publication_receives_the_durable_applied_revision_snapshot`
  proves the published `applied` is a typed `AppliedChangeResult` whose
  snapshot is a typed `RevisionSnapshot` binding the exact project/revision/hash
  and whose state equals `StateManager.load_revision(...)`.
- Searches found no production `SimpleNamespace`, no snapshot-shaped fabricated
  authority, and no `RevisionSnapshot(` construction in M13-4E production code.

## Original Compilation Identity Regression

- `_align_multi_joint_evidence_compilation` does not exist; no
  `dataclasses.replace`, compilation reordering, or mapping-driven
  normalization exists in M13-4E production code. The only `sorted(...)` is
  `promotion.py:750` — the compiler building the ORIGINAL mapping in ascending
  `candidate_instance_id` order, which is exactly the required mapping-order
  semantics, not a derived-compilation normalization.
- The representative route test
  (`test_m13_4e_promotion_application.py:146-171`) captures the compiler return
  and asserts full typed equality `receipt.compilation == compiled[0]`,
  `manifest.compilation_hash == compiled[0].compilation_hash`,
  `manifest.projection == compiled[0].projection`,
  `manifest.projection_hash == compiled[0].projection.projection_hash`, and
  `manifest.mapping == compiled[0].mapping`. Because the ENTIRE typed records
  are compared (not just hashes), hash equality is not an artifact of omitted
  identity fields.
- `verify_multi_joint_promotion_decision` builds the expected manifest from the
  original compilation (`promotion_artifacts.py:1252-1262`) and additionally
  rejects `manifest.mapping != compilation.mapping` (1267-1270).

## Projection vs Mapping Regression

- `test_original_compilation_projection_identity_and_projection_mapping_accepts_independent_orders`
  (`test_m13_4e_promotion_evidence.py:788-804`) uses a fixture where
  `projection.canonical_instance_ids != mapping canonical order` and requires
  acceptance — projection order is independent of mapping order.
- Mapping order is enforced as ascending candidate instance ID; the decision
  reference mapping identities remain canonical component IDs; no
  `zip(projection, mapping)` or sort-both comparison exists in production.
- Exact typed pair binding: the full verifier compares the complete typed
  mapping to the original typed compilation mapping (above), not set equality
  or positional coercion.

## R6 Regression

```text
py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py -k "rehash_substitution or swapped_pairing" -q
12 passed, 32 deselected in 19.05s   (exit 0)
```

Matches the claimed `12 passed, 32 deselected`. The forged mapping case
(`test_m13_4e_promotion_evidence.py:619-659, 903-941`) swaps canonical IDs
across two candidate IDs, rehashes the mapping records, rebuilds all dependent
chain hashes so every self-hash and parent hash is valid, and preserves the
candidate-ID order and canonical-ID universe (asserted at 639-647). The test
asserts rejection with the specific binding label
`"multi-joint decision mapping does not match the original compilation"` — i.e.,
rejection occurs because the exact semantic pairing is wrong, not because of a
stale hash, malformed data, or an earlier error. The standalone
`test_swapped_pairing_full_verifier_rejects_self_consistent_mapping` (826-865)
confirms the same at the full-verifier boundary.

## R8 Restart Regression

Restart authority remains: strict decision-artifact retrieval →
`decision_artifact.run_id` → fresh scoped `ArtifactStore` →
`RunController.get_run(decision_artifact_model.run_id, project_id)`
(`promotion_artifacts.py:1363-1395`, `1436-1438`). No latest-run, glob,
only-run, pre-restart-run, transient-object, or N+1-inference recovery exists in
the M13-4E route (targeted searches: no `latest_run`, no route-level `glob`).
The remediation (timestamped) did not touch this code, and the restart/
adversarial-recovery integration tests passed inside the focused gate.

## R9 Resolver Regression

`PromotionManifestService.resolve_multi_joint_result`
(`promotion_artifacts.py:1144-1196`) uses only its `ArtifactStore`, the
persisted result artifact, and the persisted referenced decision artifact
(via `resolve_multi_joint_decision`). It does not access `StateManager`,
`EvidenceStore`, or `RunController`. The R12-01 fix's `StateManager` usage is
confined to lifecycle recovery (`promotion.py:2730`) and the verifiers
(`promotion_artifacts.py:1399, 1432`) — outside the artifact-local resolver.
The two concerns remain separate.

## Legacy Golden Audit

`tests/unit/test_m13_4e_legacy_promotion_goldens.py` contains literal baseline
constants (`LEGACY_REQUEST_JSON`, `LEGACY_READINESS_JSON`,
`LEGACY_REFERENCE_JSON/HASH`, `LEGACY_DECISION_*`, `LEGACY_RESULT_*`,
`LEGACY_STATUS_VALUES`, `LEGACY_APPLICATION_RESULT_JSON`) compared by direct
equality; no expectation is computed from current production output. The file
passed inside the focused gate. The remediation (timestamped) did not touch it.

## Test Quality Audit

- The five generic-branch cases and the six real post-apply failure-matrix
  cases use real `StateManager`/`ChangeEngine`/`RunController`/`EvidenceStore`
  with narrow, targeted failure injection after real persistence; expected
  values are independent (e.g., `state_hash(loaded_state)` compared to receipt
  values; `source_revision + 1` computed from the request, not the receipt).
- No circularity found: no test asserts a value by asking the same route that
  produced the receipt to recompute it (durable loads go through the real
  `StateManager`).
- No test fails before reaching its intended binding: the substitution matrix
  asserts rejection against the specific intended binding label.
- Minor observation (non-blocking): the run-mismatch test keys on
  `calls == 3` for the generic-branch `get_run` call — brittle but currently
  deterministic and correct (see NOTES).

## Focused Gate

```text
py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
116 passed in 129.45s (0:02:09)   (exit 0)
```

Matches the claimed `116 passed`. Pass = 116, fail = 0, error = 0, skip = 0.

```text
REQUIRED_M13_4E_SKIPS = 0
```

## Predecessor Gate

```text
py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q
75 passed in 34.64s   (exit 0)
```

Matches the claimed `75 passed`.

## R12-02 Full-Suite Evidence Audit

The remediation claims `2811 passed, 34 skipped in 3255.73s (0:54:15)` from
`py -3 -m pytest -q -rs` but no durable log of that invocation is retained in
the repository, and mtimes alone cannot prove the claimed run's outcome. The
historical `2805 passed, 34 skipped` remains older evidence and was NOT
credited. Per the audit protocol, because the reported result could not be
independently bound to the final tree, this audit re-ran the full suite itself:

```text
py -3 -m pytest -q -rs
2811 passed, 34 skipped in 3600.59s (1:00:00)   (exit 0)
```

Executed 9/7/2026 starting ~14:12, completing ~15:12, in the exact received
worktree (production files unchanged since 9/7 1:07 PM; no semantic change
occurred before or during this audit). This independent run is the accepted
fresh full-suite evidence.

**R12-02 = CLOSED.**

## Skip Audit

The independent full-suite run reported exactly 34 skips, all in the permitted
optional categories:

- OpenCode live-validation opt-ins: 6
- structural profile not installed: 14
- materials extra not installed: 5
- FreeCAD/FreeCADCmd runtime unavailable: 9

No M13-4E test was skipped (the focused gate also had zero skips).

```text
REQUIRED_M13_4E_SKIPS = 0
```

The historical FreeCAD timeout claim remains `UNVERIFIABLE` (no new durable
evidence about that exact old invocation was found); it is reported factually
and is outside M13-4E acceptance, which has no FreeCAD live-runtime gate.

## Static Audit

- `py -3 -m compileall -q src tests` → exit 0.
- `git diff --check` → exit 0 (non-failing CRLF warnings only).
- Targeted searches in M13-4E production files
  (`promotion.py`, `promotion_models.py`, `promotion_artifacts.py`,
  `__init__.py`): no `SimpleNamespace`, no
  `_align_multi_joint_evidence_compilation`, no `latest_run`, no route-level
  `glob`, no `MagicMock`/`Mock`. All acceptance-relevant occurrences of
  `load_revision` (3: generic branch + two verifiers), `_read_snapshot`
  (1: durable handoff), `AppliedChangeResult(` (1: durable handoff), and the
  single production `sorted(...)` (compiler mapping construction) were
  individually inspected and classified as correct.

## Prior Finding Adjudication

```text
R12-01 = CLOSED
R12-02 = CLOSED
```

R12-01 is closed by the production fix verified in
`promotion.py:2722-2759` plus the real-persistence regression matrix. R12-02 is
closed by this audit's own fresh final-tree full-suite run.

## New Findings

### CRITICAL

None.

### IMPORTANT

None.

### MINOR

None.

### NOTES

- NOTE-1: The remediation's own claimed full-suite invocation
  (`3255.73s`) has no durable retained log; this audit did not credit it and
  instead produced independent fresh evidence. Future candidates should retain
  full-suite stdout/exit-status artifacts.
- NOTE-2: `_multi_joint_receipt`'s fallback retry (`promotion.py:2853-2866`)
  nulls readiness/compilation on model-validation failure; for a post-apply
  status the model still requires the applied identity pair, so a truly invalid
  post-apply receipt raises rather than emitting false evidence — fail-closed.
- NOTE-3: The run-mismatch regression keys the mismatched `get_run` response on
  call ordinal (`calls == 3`); brittle if `apply_approved_proposal`'s internal
  `get_run` call count changes, but currently deterministic and correct.
- NOTE-4: `.pytest_cache/v/cache/lastfailed` contains stale entries from older
  candidate iterations (including removed M13-4E test names); this is historical
  test-runner noise, not a candidate defect, and did not affect any gate.
- NOTE-5: Worktree noise (`.coverage`, `.superpowers/sdd/*`, `err.txt`,
  `projects/`, `src/mechcad-harness/`, unrelated plans/specs) was verified by
  timestamps as pre-existing and outside M13-4E scope.

## Acceptance Decision

All acceptance criteria are satisfied:

- R12-01 closed; R12-02 closed; no new CRITICAL/IMPORTANT findings.
- One original `CandidatePromotionCompilation` identity, compilation hash, and
  projection hash preserved (full typed-record equality, not hash-only).
- Projection/mapping order semantics independent; exact typed
  candidate→canonical pair binding enforced by the full verifier.
- R6 self-consistent rehashed substitution coverage valid (forged pairing
  rejected at the exact-pairing binding).
- Durable N+1 authority valid; generic post-apply recovery fail-closed;
  successful publication uses a durable `RevisionSnapshot`.
- R8 metadata-rooted restart valid; R9 artifact-local resolver isolated.
- Legacy goldens unchanged and literal; protected surfaces untouched.
- Focused gate 116 passed (0 skips); predecessor gate 75 passed.
- Fresh final-tree full-suite evidence: 2811 passed, 34 skipped (independent
  rerun, exit 0); required M13-4E skips = 0.
- Static gates pass.

```text
M13_4E_INDEPENDENT_R12_ACCEPTED
M13_4E_ACCEPTANCE_STATUS = ACCEPTED
```

## Downstream Authorization

```text
M13_4P_MAY_RESUME = YES
M13_4_MAY_RESUME = NO
ROTATOR_V2_MAY_RESUME = NO
```

This authorizes only M13-4P reconciliation. It does NOT authorize M13-4 or
Rotator V2. No commit, tag, or push was performed by this audit.
