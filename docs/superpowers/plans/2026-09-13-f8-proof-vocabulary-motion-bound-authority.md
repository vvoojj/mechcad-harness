# F8 Proof Vocabulary and Motion-Bound Authority Implementation Plan

> **For agentic workers:** This plan is non-executable until the blocking compatibility gate below receives explicit user approval. Do not invoke implementation sub-skills or modify production/test/audit files before that approval.

**Goal:** Preserve M10 proof compatibility while deciding whether F8 is bounded
as intentional status duplication and distinct numerical semantics rather than
performing an unsafe consolidation.

**Architecture:** The current evidence does not support a shared implementation.
The source-byte-frozen M10-4 module remains untouched, and M10-1 retains its
separate scaled-padding primitive. If approved, the only possible work is
characterization and compatibility documentation/testing that proves the
separation; it is not a shared-core refactor.

**Tech Stack:** Python 3.11+, Pydantic v2, `StrEnum`, pytest, deterministic
SHA-256 JSON identities.

## Blocking Compatibility Gate

**STOP. Do not execute this plan without explicit user approval.** The user must
choose one of these outcomes:

1. Accept Option D: retain both implementations, treat status vocabulary as
   intentional separately typed compatibility surface, and record that bound
   padding semantics differ.
2. Authorize supersession of the accepted M13-3P whole-file source-byte contract
   and explicitly select a new padding contract. This is a new compatibility
   decision, not a refactor approval; this plan does not authorize it.

Until an outcome is chosen, do not alter
`src/mechcad_harness/multi_joint_continuous_clearance.py`, its golden hashes, or
the M10-1 formula.

## Global Constraints

- Do not modify production code under the recommended Option D.
- Do not modify `docs/reconstruction/**`.
- Do not touch F3 surfaces.
- Preserve the full-byte hash of
  `src/mechcad_harness/multi_joint_continuous_clearance.py`:
  `sha256:66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5`.
- Preserve M13-3P v1 request/result JSON, digests, hashes, and proof
  mathematics.
- Preserve status strings, existing public imports, request/hash/wire formats,
  v1/v2 boundaries, and all conservative padding values.
- Do not regenerate or weaken a legacy golden.
- Do not update the duplication audit or ownership map until all approved tests
  pass and the user has approved the disposition.
- No commits, pushes, tags, releases, or live external runtimes.

## File Map

| File | Planned responsibility after approval |
| --- | --- |
| `tests/test_m10_1_continuous_proof.py` | Add M10-1 exact formula characterizations only. |
| `tests/unit/test_multi_joint_continuous_clearance.py` | Add M10-4 per-contribution-padding characterizations only, without production edits. |
| `tests/unit/test_f8_proof_authority_characterization.py` | Add cross-family status-string/type and numerical non-equivalence characterization. |
| `tests/unit/test_m13_3_legacy_goldens.py` | Existing whole-file source-byte regression gate; do not edit. |
| `tests/unit/test_m13_3p_legacy_goldens.py` | Existing v1 wire/hash regression gate; do not edit. |
| `docs/audit/MECHCAD_LOGIC_DUPLICATION_AUDIT.md` | Update only after user-approved Option D verification; no implementation authority change. |
| `docs/audit/MECHCAD_CAPABILITY_OWNERSHIP_MAP.md` | Update only with the approved audit disposition. |

---

### Task 1: Capture Exact Formula and Status Characterization

**Files:**
- Modify: `tests/test_m10_1_continuous_proof.py`
- Modify: `tests/unit/test_multi_joint_continuous_clearance.py`
- Create: `tests/unit/test_f8_proof_authority_characterization.py`

**Consumes:** Current baseline implementations without changing their imports,
types, functions, or result models.

**Produces:** Explicit regressions for actual M10-1 and M10-4 contracts, not a
claim that both engines use the same helper.

- [ ] Add a failing direct M10-1 test with `R = 100.0` asserting exact values
  for deltas `0.0`, `0.01`, `pi/2`, `pi`, and `2*pi`, including
  `motion_bound(100.0, 0.0) == 1.01e-07` and saturation at `pi`.
- [ ] Run `py -3 -m pytest tests/test_m10_1_continuous_proof.py -k motion_bound -v`.
  Expected before the new assertions: existing tests pass; any intentionally
  mistyped characterization fails.
- [ ] Add the minimal test assertions using the existing `motion_bound`; do not
  alter `continuous_proof.py`.
- [ ] Add a failing M10-4 test that uses a deterministic one-joint v1 request
  and asserts its certificate's one contribution follows
  `2 * R * sin(min(delta, pi) / 2) + 1e-9`, including the `R = 100`,
  `delta = 0` value `1e-09`. Add a two-influencing-joint fixture that proves
  the fixed pad is accumulated once per joint.
- [ ] Run `py -3 -m pytest tests/unit/test_multi_joint_continuous_clearance.py -v`.
  Expected before the new assertions: current tests pass; a test claiming the
  scaled M10-1 pad fails.
- [ ] Add the minimal tests only; do not alter
  `multi_joint_continuous_clearance.py`.
- [ ] Create cross-family tests asserting all three `.value` strings match,
  the corresponding enum members are not identical with `is`, the classes are
  distinct, and `motion_bound(100.0, 0.0) != 1e-09`. Construct one valid
  `ContinuousSingleAxisProofResult` and one valid
  `MultiJointContinuousClearanceProofResult` fixture using their own status
  types; assert each `model_dump(mode="json")["status"]` is the exact expected
  string and each class can parse its own JSON payload without type conversion.
- [ ] Run `py -3 -m pytest tests/unit/test_f8_proof_authority_characterization.py -v`.
  Expected: PASS.
- [ ] Run the two focused existing suites again. Expected: PASS without changed
  production behavior.

### Task 2: Prove Legacy Source, Wire, and Hash Compatibility

**Files:**
- Test only, no edits: `tests/unit/test_m13_3_legacy_goldens.py`
- Test only, no edits: `tests/unit/test_m13_3p_legacy_goldens.py`

**Consumes:** The untouched frozen module and existing compatibility fixtures.

**Produces:** Exact evidence that Option D introduced no v1/v2 source, wire, or
hash drift.

- [ ] Run `py -3 -m pytest tests/unit/test_m13_3_legacy_goldens.py -v`.
  Expected: PASS, including the complete frozen-module SHA-256 assertion.
- [ ] Run `py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v`.
  Expected: PASS, including M10-4 v1 request/result literal JSON and hashes.
- [ ] Run `py -3 -m pytest tests/integration/test_m10_4_provenance.py -v`.
  Expected: PASS or only existing environment-gated skips; no changed status,
  result-hash, or evidence payload behavior.
- [ ] Run `git diff --check`.
  Expected: no whitespace errors.
- [ ] Inspect `git diff -- src/mechcad_harness/multi_joint_continuous_clearance.py`.
  Expected: no output. Stop if output exists; do not update a golden.

### Task 3: Search for Remaining and Newly Introduced Authority Copies

**Files:**
- No code edits.

**Consumes:** Repository at the approved Option D state.

**Produces:** Search evidence that no shared-core claim masks an additional
formula or status authority.

- [ ] Search `ContinuousSingleAxisProofStatus`,
  `MultiJointContinuousProofStatus`, and `motion_bound(` across `src/` and
  `tests/` using repository search tooling.
- [ ] Search for the exact scaled pad `1e-9 * (1 + abs(radial_mm))` and the
  fixed per-contribution pad `+ 1e-9` in the two M10 modules.
- [ ] Record that the expected authorities are exactly the M10-1 primitive and
  the frozen M10-4 loop; no new shared helper or third production formula was
  introduced.
- [ ] Search for `isinstance` and `type(` checks involving either status class.
  Expected: no newly introduced cross-family type coercion or identity bridge.
- [ ] Stop if a third production authority or a cross-family type adapter is
  found. Do not silently expand scope.

### Task 4: Update Audit Disposition Only After Approval and Passing Gates

**Files:**
- Modify: `docs/audit/MECHCAD_LOGIC_DUPLICATION_AUDIT.md`
- Modify: `docs/audit/MECHCAD_CAPABILITY_OWNERSHIP_MAP.md`

**Consumes:** Explicit Option D approval plus Tasks 1-3 passing evidence.

**Produces:** A precise audit disposition that does not claim a completed
shared-core refactor.

- [ ] Before editing, verify the user approval explicitly selects Option D and
  permits the two audit document edits. Stop if approval is absent.
- [ ] Update F8 to state that status strings are value-equivalent but public enum
  types are distinct, and that M10-1 and M10-4 padding/aggregation formulas are
  not semantically equivalent.
- [ ] Update map rows 29 and 32 to retain separate M10-1 and frozen M10-4
  authorities, not a false single shared core.
- [ ] Do not edit `docs/reconstruction/**`, source-byte hashes, source code, or
  legacy golden constants.
- [ ] Run the Task 1 and Task 2 commands plus `git diff --check`.
  Expected: PASS/no whitespace errors.
- [ ] Inspect `git diff --check` and the staged/un-staged diff manually. Expected:
  only authorized tests and audit/map documentation changed.

## Plan Self-Review

- Spec coverage: Tasks 1-3 cover characterization, enum serialization/type
  compatibility, numerical non-equivalence, legacy source/wire/hash gates, and
  duplicate-authority searches. Task 4 is explicitly downstream of approval.
- Placeholder scan: no undecided implementation steps are presented as
  executable; the compatibility decision is a deliberate blocking gate.
- Type consistency: the plan retains both existing public enum classes and does
  not define a replacement type or helper.

## Execution Handoff

This plan is blocked pending the compatibility decision. It must not be executed
until the user explicitly approves Option D or supplies a separately governed
supersession decision for the M13-3P freeze and changed numerical semantics.
