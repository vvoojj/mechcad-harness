# M13-4E Corrective Completion Report

## Marker

The previous M13-4E candidate failed independent audit. Corrective work R0-R10
was performed against the accepted corrective specification and plan.

This report contains candidate evidence only. It does not declare acceptance.

```text
CANDIDATE MARKER:
M13_4E_MULTI_JOINT_PROMOTION_EVIDENCE_CONTRACT_VERIFIED

PENDING INDEPENDENT R12 ACCEPTANCE
```

## Corrective Scope

- R0-R5 repairs were regression-checked before new work.
- R6 completed the independent rehashed substitution matrix.
- R7 replaced fabricated post-apply lifecycle proofs with real ChangeEngine
  persistence proofs.
- R8 completed metadata-rooted fresh restart and adversarial run recovery.
- R9 completed the artifact-local result resolver tamper and isolation matrix.
- R10 completed focused, predecessor, full-suite, skip, static, and protected
  surface audits.
- `_align_multi_joint_evidence_compilation()` was removed.
- The original `compile_multi_joint()` `CandidatePromotionCompilation` is
  preserved unchanged through decision evidence, result evidence, and receipts.
- Successful multi-joint result publication receives an `AppliedChangeResult`
  backed by the exact durable `RevisionSnapshot` for the applied revision; no
  `SimpleNamespace` snapshot is used.
- No M13-4P, M13-4, Rotator V2, FreeCAD acceptance, or production composition
  work was performed.

## R0-R5 Regression

The pre-existing repairs passed their focused smoke gate:

```text
17 passed
```

The gate covered removal of the normalization helper, original compilation
identity preservation, independent projection/mapping ordering, SHA identity
member validation, typed route context, and partial post-apply N+1 verification.

## R6 Rehashed Substitution Matrix

All required substitutions are self-consistent forged chains. Each nested record
was reconstructed with valid self-hashes and independently validated before the
full verifier was called. Every case was rejected at the intended independent
binding, not by a stale parent hash, malformed object, schema literal, or missing
field.

| Case | Result |
| --- | --- |
| `readiness` | PASS: readiness binding |
| `evaluation_request_substitution` | PASS: multi-joint evaluation request binding |
| `evaluation_substitution` | PASS: multi-joint evaluation binding |
| `selection_substitution` | PASS: multi-joint selection binding |
| `configuration_set_substitution` | PASS: configuration-set binding |
| `placement_derivation_substitution` | PASS: placement-derivation binding |
| `pair_policy_substitution` | PASS: physical-pair classification-set binding |
| `m10_request_substitution` | PASS: M10 v2 request binding |
| `m10_result_substitution` | PASS: M10 v2 result binding |
| `mapping_substitution` | PASS: exact candidate-to-canonical mapping pairing |
| `classification_substitution` | PASS: classification identity binding |

The mapping case swaps two `candidate_instance_id -> canonical_instance_id`
pairs while preserving both ID universes, candidate ordering, mapping hashes,
and parent hashes. Set equality therefore still passes, while exact typed
pairing comparison rejects the forged mapping. The classification case changes
classification semantics while preserving lexical ordering and valid hashes.

R6 gate:

```text
11 passed, 46 deselected
```

## R7 Real ChangeEngine Failure Matrix

All post-N+1 cases use the real `StateManager`, `ChangeEngine`,
`RunController`, and `DesignState` N-to-N+1 mutation. Only the exact operation
under test is narrowly failed after the real ChangeEngine mutation.

| Failure injection point | Real ChangeEngine applied | Persisted N+1 loaded | Receipt revision/hash matched | Result artifact ID absent |
| --- | --- | --- | --- | --- |
| Run-state transition persistence | YES | YES | YES | YES |
| Invalidation persistence | YES | YES | YES | YES |
| Invalidation reload after durable write | YES | YES | YES | YES |
| Invalidation verification after durable write | YES | YES | YES | YES |
| Result publication before durable write | YES | YES | YES | YES |
| Result fresh resolution after bytes write | YES | YES | YES | YES |

For every row, `StateManager.load_revision(project_id,
receipt.applied_revision)` succeeded, `receipt.applied_revision` equaled base
revision plus one, and the loaded state hash equaled
`receipt.applied_state_hash`. The result-resolution case also proved that
untrusted result bytes may physically exist while the receipt retains no result
artifact ID.

R7 gate:

```text
7 passed, 5 deselected
```

The old fabricated post-apply lifecycle tests and their fabricated
`AppliedChangeResult`/snapshot/`SimpleNamespace` proof path were removed from
`test_m13_4e_promotion_application.py`. No whole
`apply_approved_proposal()` monkeypatch remains there. The successful route
reloads the exact durable `RevisionSnapshot` before passing the typed
`AppliedChangeResult` to result publication; a narrow regression test asserts
the complete snapshot envelope and persisted state binding.

Self-review classification of remaining M13-4E symbols: `promotion.py` uses the
typed `AppliedChangeResult` with a durable `RevisionSnapshot`;
`promotion_artifacts.py` uses it only as the publication type contract and
exact-type guard; the result unit helper constructs it from a real
`StateManager.create_revision()` snapshot for narrow artifact-publication
testing; and the application regression test imports it only to assert the
real route handoff type. No M13-4E acceptance test constructs a
`SimpleNamespace` snapshot or monkeypatches the whole
`apply_approved_proposal()` method.

## R8 Metadata-Rooted Restart

The positive fresh-restart path crosses the boundary only with the permitted
typed request, readiness, and original compilation, plus the decision artifact
ID. Recovery is:

```text
strict project decision EngineeringArtifact retrieval
  -> reloaded decision_artifact.run_id
  -> fresh scoped ArtifactStore decision retrieval
  -> RunController.get_run(decision_artifact.run_id, project_id)
```

The manifest service, ArtifactStore handles, RunController, StateManager, and
EvidenceStore are recreated. No pre-restart Run, candidate CAD, M10 result, or
transient evaluation execution object is used as authority. No run-manifest
glob, latest-run lookup, N+1 state inference, or only-run assumption is used.

The following adversarial cases pass:

- blank, missing, or corrupt decision-artifact `run_id` is rejected by strict
  retrieval;
- scoped ArtifactStore `run_id` differing from decision metadata is rejected;
- a decision naming a non-existent durable run reaches `get_run` using exactly
  the metadata run ID and is rejected;
- a durable run with wrong project binding is rejected;
- a durable run with wrong base binding is rejected;
- a result artifact with another run ID and matching N/N+1 values is rejected
  before nonlocal run lookup;
- a wrong run with an identical-looking state transition is rejected by exact
  run identity.

R8 gate:

```text
10 passed
```

## R9 Result Resolver Isolation

The artifact-local resolver uses only `ArtifactStore`, the persisted result
artifact, and the persisted referenced decision artifact. It does not access
`StateManager`, `EvidenceStore`, or `RunController`; package-level and defining
module dependency bombs were installed in the direct resolver tests.

Independent tamper cases all pass:

- result artifact namespace;
- result artifact SHA-256 metadata;
- result artifact size metadata;
- result artifact `input_hash`;
- canonical result JSON bytes;
- `result_hash`;
- `decision_artifact_id`;
- `decision_artifact_hash` equal to decision artifact byte hash;
- `decision_hash` equal to decision manifest self-hash;
- base revision;
- base state hash;
- resulting revision;
- resulting state hash;
- result artifact bound revision;
- result artifact bound state hash;
- canonical target mechanism ID;
- mechanism path;
- result artifact run ID;
- decision/result run-ID relationship.

The run-relationship case uses independently strict-valid persisted decision
artifacts in two run scopes and rejects their cross-run relationship. The public
wrapper `verify_multi_joint_promotion_application_result` is present in
`promotion_artifacts.__all__` and is also available through the package export.

R9 gate:

```text
19 passed, 22 deselected
```

## Identity Evidence

The representative final route fixture proves exact original-to-evidence
identity preservation:

```text
ORIGINAL_COMPILATION_HASH = sha256:0a4072bb0f56e76366e8627cf5f628024468bca61d18fbae475a9cd72be1fadd
EVIDENCE_COMPILATION_HASH  = sha256:0a4072bb0f56e76366e8627cf5f628024468bca61d18fbae475a9cd72be1fadd

ORIGINAL_PROJECTION_HASH = sha256:022b59cf44dc11da046f50a30c8138faeeb089a01549bcb61d0885c91a65c8bc
EVIDENCE_PROJECTION_HASH  = sha256:022b59cf44dc11da046f50a30c8138faeeb089a01549bcb61d0885c91a65c8bc
```

The original compilation hash equals the evidence compilation hash. The
original projection hash equals the evidence projection hash. Projection and
mapping retain independent order semantics: projection order remains the
M13-3 realization/projection order, while mapping order remains ascending
candidate instance ID. Candidate-to-canonical pairing is checked by exact
typed mapping records, not set equality or positional coercion. SHA-256 tuple
identity validation is enforced for mapping and classification identities.

## Typed Route

The private `_MultiJointPromotionRouteContext` is real and strongly typed. It
contains request, readiness, compilation, run, scoped ArtifactStore, and typed
decision artifact only. It derives the proposal from the original compilation
and validates request/readiness/compilation/run/store/decision-artifact
relationships before application.

Every partial post-apply receipt verifies the persisted N+1 revision and state
hash. No provenance-failure receipt contains a trusted result artifact ID.

## R10 Focused / Regression / Full Suite

The exact observed gates are:

| Gate | Command result | Pytest elapsed |
| --- | --- | ---: |
| Complete M13-4E corrective focused suite | `111 passed` | 105.49 s |
| Independent legacy goldens | `3 passed` | 2.25 s |
| Broader legacy promotion gate (six M12 promotion modules) | `75 passed` | 17.71 s |
| Selected M13-3 gate | `39 passed` | 23.38 s |
| Exact corrective-plan predecessor gate | `75 passed` | 33.94 s |
| Full suite | `2805 passed, 34 skipped` | 3778.76 s |

The recorded full suite had zero failures and zero errors. The complete
corrective focused suite had no skipped required M13-4E tests. The full-suite
command was run with a 7200-second command ceiling; measured wall time was
3788.52 seconds. After the final narrow durable-snapshot hardening, two full
suite reruns were started but the Windows execution harness detached them
before a pytest summary was captured (one stopped near 50%, one near 81%). No
post-hardening full-suite result is claimed; the post-hardening focused and
predecessor gates are the reproducible final gates.

The focused commands were:

```text
py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q

py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q

py -3 -m pytest -q -rs
```

Independent `ca294e0` legacy goldens remain unchanged and are literal baseline
values, not values dynamically derived from the current M13-4E implementation.

## Skip Audit

```text
REQUIRED_M13_4E_SKIPS = 0
```

All 34 full-suite skips are optional and outside M13-4E acceptance:

- OpenCode live-validation opt-ins;
- structural profile unavailable;
- materials extra unavailable;
- FreeCAD/FreeCADCmd unavailable;
- M10-1 FreeCAD live runtime unavailable.

The previous FreeCAD timeout claim remains `UNVERIFIABLE`: durable logs from
that exact old invocation were not retained. It is not classified as
`ENVIRONMENTAL_TRANSIENT`. M13-4E has no FreeCAD runtime gate. FreeCAD-related
skips are reported factually and separately from required M13-4E acceptance.

## Protected Surface Audit

Corrective production edits are limited to the authorized files:

- `src/mechcad_harness/candidates/promotion_models.py`
- `src/mechcad_harness/candidates/promotion_artifacts.py`
- `src/mechcad_harness/candidates/promotion.py`
- `src/mechcad_harness/candidates/__init__.py`

Corrective test/report files are:

- `tests/unit/test_m13_4e_legacy_promotion_goldens.py`
- `tests/unit/test_m13_4e_promotion_evidence.py`
- `tests/unit/test_m13_4e_promotion_result.py`
- `tests/unit/test_m13_4e_promotion_application.py`
- `tests/integration/test_m13_4e_promotion_evidence_acceptance.py`
- `docs/audit/MECHCAD_M13_4E_COMPLETION_REPORT.md`

No corrective semantic changes were made in `src/mechcad_harness/application.py`,
M10 files, CAD backends, state schemas, M13-3 request/evaluation/selection/
promotion contracts, dependency files, or legacy promotion contracts. The
production changes preserve the original compilation/projection identities and
only add the approved M13-4E evidence/verifier repairs.

## R11 Completion Report

This corrected report records the green R6-R10 gates and the subsequent narrow
typed-snapshot hardening. It explicitly records that the candidate previously
failed independent audit, that corrective work R0-R10 was performed, and that:

- `_align_multi_joint_evidence_compilation` was removed;
- original `compile_multi_joint()` `CandidatePromotionCompilation` was
  preserved;
- original and evidence compilation/projection hashes are equal;
- projection and mapping have independent order semantics;
- exact typed candidate-to-canonical pairing and SHA tuple validation are
  enforced;
- the typed route context is used;
- successful result publication receives a durable `RevisionSnapshot` through
  the typed `AppliedChangeResult` contract;
- every partial post-apply receipt verifies persisted N+1;
- R6 rehashed substitutions are complete;
- R7 uses real ChangeEngine persisted N+1 proof;
- R8 recovery starts from decision artifact metadata `run_id`;
- R9 resolver tamper/isolation coverage passes;
- independent `ca294e0` legacy goldens remain unchanged;
- protected surfaces remain unchanged;
- exact final counts are recorded above.

This is candidate evidence only. Independent R12 acceptance is pending.

## Remaining Findings

### CRITICAL

None identified by the completed corrective gates.

### IMPORTANT

None identified by the completed corrective gates.

### MINOR

The historical FreeCAD timeout remains unverifiable because its durable logs
were not retained. This is outside M13-4E, which has no FreeCAD runtime gate.

The final narrow durable-snapshot hardening was verified by the complete
focused and predecessor suites, but the Windows harness did not retain a
post-hardening full-suite summary; the previously recorded full-suite result
is retained as historical R10 evidence.

## Worktree Status

No commit, tag, push, release, M13-4P, R12, or acceptance action was performed.

Pre-existing `.coverage`, `.superpowers/sdd/*`, unrelated specifications/plans,
`err.txt`, `projects/`, and `src/mechcad-harness/` worktree noise was left
untouched and is outside M13-4E product scope.

M13_4E_CORRECTIVE_IMPLEMENTATION_READY_FOR_INDEPENDENT_AUDIT

## R12 Remediation After Rejection

The prior independent verdict was:

```text
M13_4E_INDEPENDENT_R12_REJECTED
```

The rejection identified real findings `CRITICAL R12-01` and `IMPORTANT R12-02`.
They are preserved here as remediation history and are not rewritten as an
acceptance result.

### R12-01 Durable Generic Post-Apply Receipt Proof

`CandidatePromotionApplicationService._promote_multi_joint_route()` now treats
the generic exception branch as a fail-closed recovery path. A reloaded run may
identify a possible N+1 only. Before returning a post-apply receipt it calls
`StateManager.load_revision(project_id, current.active_revision)` and requires
both the loaded state's exact revision and `state_hash` to equal the run's
claimed active values. A missing, unreadable, wrong-revision, or wrong-hash
snapshot returns the existing `PRE_APPLY_FAILURE` receipt form with no applied
revision/state hash and no result artifact ID.

The new generic-exception matrix uses real `StateManager`, `ChangeEngine`, and
`RunController`. It injects an exception only at a multi-joint typed-run
validation immediately after the real application has completed; it does not
replace or fake `apply_approved_proposal()`, `AppliedChangeResult`, or a
snapshot. Cases cover valid durable N+1, missing snapshot, durable load failure,
run-state-hash mismatch, and run-revision mismatch.

### Post-Apply Branch Audit

| Branch | N+1 possible | Claimed identity source | Durable state proof before receipt | Result artifact |
| --- | --- | --- | --- | --- |
| `PostApplyInvalidationError` | Yes | typed `AppliedChangeResult.snapshot` | ChangeEngine durable snapshot | Absent |
| `PostApplyRunTransitionError` | Yes | typed `AppliedChangeResult.snapshot` | ChangeEngine durable snapshot | Absent |
| Generic exception with run at N+1 | Possible | reloaded run, then exact state reload | `StateManager.load_revision` revision/hash equality | Absent |
| Generic exception without proven N+1 | Unknown | None | Fails closed | Absent |
| Invalidation reload/verification failure | Yes | returned active run after normal controller completion | downstream receipt verifier reloads exact N+1 | Absent |
| Result publication/resolution failure | Yes | returned active run and durable result preparation snapshot | downstream receipt verifier reloads exact N+1 | Absent |
| Complete route | Yes | durable result manifest and receipt | full application verifier reloads exact N+1 | Trusted resolved ID |

### Fresh Remediation Evidence

```text
py -3 -m pytest tests/unit/test_m13_4e_promotion_application.py -k "generic_post_apply" -q
5 passed, 13 deselected in 9.16s

py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
116 passed in 127.28s

py -3 -m pytest tests/unit/test_m13_4e_promotion_evidence.py -k "rehash_substitution or swapped_pairing" -q
12 passed, 32 deselected in 19.88s

py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q
75 passed in 36.64s

py -3 -m pytest -q -rs
2811 passed, 34 skipped in 3255.73s (0:54:15)
```

The fresh full suite is final-tree evidence. Its 34 skips are optional OpenCode
live-validation, unavailable structural/material profile, or unavailable
FreeCAD/FreeCADCmd tests. Required M13-4E skips are zero. The historical
FreeCAD timeout remains `UNVERIFIABLE`.

`py -3 -m compileall src tests` and `git diff --check` completed successfully.
Production remediation is limited to `src/mechcad_harness/candidates/promotion.py`;
the regression matrix is limited to
`tests/unit/test_m13_4e_promotion_application.py`. No protected M13-3, M10,
CAD, state-schema, dependency, legacy-promotion, or `application.py` surface
was changed.

```text
M13_4E_R12_REMEDIATION_READY_FOR_REAUDIT
M13_4E_ACCEPTANCE_STATUS = PENDING_INDEPENDENT_REAUDIT
M13_4P_MAY_RESUME = NO
M13_4_MAY_RESUME = NO
ROTATOR_V2_MAY_RESUME = NO
```
