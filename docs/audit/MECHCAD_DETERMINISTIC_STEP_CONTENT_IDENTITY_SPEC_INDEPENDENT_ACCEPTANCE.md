# Deterministic STEP Content Identity Spec — Independent Acceptance Audit

## Verdict

```text
Target:
docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md

Exact accepted Spec SHA-256:
1C1284D3B6F281C09FF457D6C708B2D770038C67F7C72306D880A95F149DEFAF

Disposition:
INDEPENDENTLY_ACCEPTED

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENTLY_ACCEPTED
```

This disposition applies ONLY to the exact Spec bytes whose SHA-256 is stated
above. Any byte change to the Spec, including a status-wording change, produces
a different SHA and is not covered by this acceptance.

## Audit Independence

This audit did not edit the Spec, the implementation Plan, production code,
tests, architecture, reconstruction/history, the capability inventory, or any
existing accepted audit. It did not remediate findings, run implementation
tests, run FreeCAD/Gmsh/CalculiX/MINI/live runtime, commit, reset, stash,
clean, push, or install. The only intentional repository write is this record.
The prior session's acceptance output was treated as a claim to re-verify, not
as evidence; acceptance here rests on the independent SHA recomputation and
the focused re-check recorded below. The dirty worktree was preserved.

## Status-Text Relationship (Normative for Readers)

The accepted Spec bytes themselves contain "PROPOSED / pending independent
acceptance" wording (Spec lines 1–5 and §25) because that wording existed
before the independent audit. Those exact bytes MUST NOT be edited merely to
change status, because doing so would produce a different SHA and void this
acceptance. This later `docs/audit/**` record is the durable repository
evidence that the exact SHA stated above was independently accepted: a future
auditor establishes Spec bytes → exact SHA → this record → the exact marker
above, using only repository sources and never session memory.

## Input Authority

Read and applied (read-only):

- Repository-root `AGENTS.md` (source-role discipline; current production code
  as implemented truth; historical records as history only).
- `docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md`
  at the exact accepted SHA (943 lines on disk).
- Current-disk implementation only as cross-evidence for code-cited line
  references: `src/mechcad_harness/candidates/models.py`,
  `src/mechcad_harness/revolute_drive/service.py`,
  `src/mechcad_harness/revolute_drive/models.py`,
  `src/mechcad_harness/candidates/cad_realization.py`,
  `src/mechcad_harness/candidates/evaluation.py`,
  `src/mechcad_harness/candidates/promotion.py`,
  `src/mechcad_harness/candidates/dimensions.py`,
  `src/mechcad_harness/candidates/multi_joint_m10_bridge.py`,
  `src/mechcad_harness/candidates/multi_joint_m10_evaluation.py`,
  `src/mechcad_harness/candidates/multi_joint_selection.py`.

## SHA Verification

`Get-FileHash -Algorithm SHA256` recomputed independently on disk:

```text
1C1284D3B6F281C09FF457D6C708B2D770038C67F7C72306D880A95F149DEFAF
```

Match. The Spec remains `DOCUMENTATION_ONLY` in its own text and authorizes no
implementation by itself; acceptance is conferred solely by this record.

## Focused Acceptance Re-Check (All Closed, No New Defect)

Each item was re-verified present and consistent in the exact target bytes; no
new CRITICAL or IMPORTANT Spec defect was found:

- **Option A pre-activation versioning (line 110):** `mechanical-design-candidate@2`
  retained, no `@3`; repository-bounded pre-activation evidence stated
  (baseline `185a304` has no candidate@2; no accepted/persisted @2 identity;
  `@1` and legacy realization hash frozen; no backfill). Prior governance
  result unchanged; repository evidence unchanged since.
- **Shared projection (lines 157, 182):** `semantic_candidate_realization_payload`
  owned by `candidates/models.py`, sole canonical realization transformation,
  pure, `@1/@2` schema-dispatched, non-mutating, unknown-field/duplicate-key
  rejecting, `realization_hash` excluded; single axis-source helper with M10
  delegation; no second projection or ordering authority.
- **Candidate-level ordering (§6A 120/122–123/132/137; §14 rows 632–634):**
  `component_specifications` sorted by unique `specification_hash`;
  `design_variables` as complete `{name, value, canonical_path}` records sorted
  by unique `name` via the single helper
  `semantic_candidate_design_variable_records`; `unresolved_items` as complete
  records under the total multiset key with multiplicity preserved and no
  invented uniqueness. Current-consumer evidence recorded (line 134) and
  independently consistent with disk: hash/name-keyed lookups, name-resolved
  variables, order-independent `resolve_dimensions()`, exact-tuple echo checks
  (`promotion.py:541,1718`), non-empty-only promotion gate
  (`promotion.py:1691-1692`).
- **Mechanism closure (lines 159, 174-tail, 558):**
  `semantic_candidate_mechanism_hash` is a pure `@2`-only wrapper
  (`candidate-mechanism-semantic@1`) over the same projection; candidate track
  equality vs canonical `@4` track with cross-track/raw substitution rejected;
  all other bridge@2 inputs enumerated closed.
- **Admissibility@2 alignment (lines 533, 635, 666):** stored echo tuple
  retained for exact validation; `result_hash@2` only canonicalized through the
  same name-sorted helper; `@1` frozen; declared shape unchanged. The correction
  is required (current `_hash(self,…)` over the stored tuple would otherwise
  diverge downstream) and is covered by the same pre-activation condition as
  candidate@2; it generalizes to no other record.
- **MJ `project_id` INCLUDED (line 560):** one rule across MJ
  request/evaluation/selection@2 with the worktree gap explicitly flagged as a
  P5 alignment item, not a spec change.
- **Tests 89–93 (lines 921–925):** realization closure, engineering-order
  distinction, exact 15-field/13-entry closure with the three canonical orders
  and non-mutation, `@1` closure, and the additive candidate-level ordering
  closure with multiplicity/add/remove/change sensitivity and the §6B scope
  exclusion. Test 91 cannot pass under stored-order hashing.
- **Restart/raw-vs-semantic closure (line 798; §21):** ordered 10-step restart
  (raw → bindings → request → `@4`/axis-spec → `candidate_hash_v2` → `@2`-only
  wrapper → bridge equality → downstream), no CAD/solver execution, raw hashes
  replay-only and never substituted, no backfill, mixed chains fail closed.
- **No activation authorization:** the Spec authorizes no implementation,
  default, or production activation (lines 1–5, §25/941); P1–P4 remain
  worktree-only subject to revalidation.
- **N-G deferral intact (lines 143, 147, test 93 exclusion):** request-scope
  tuples unchanged, correctly out of scope.

## History Preserved Exactly

- Prior revision `4A8B3E6A…797B3EF623` disposition
  (`…_ACCEPTANCE_REQUIRES_REVISION` on blocker I-G1) stands as historical truth
  for those bytes; this record does not alter it.
- Earlier revision `A4567143…629325` acceptance remains historical truth for
  those bytes only.
- No historical audit disposition is rewritten by this record.

## Capability / Status Boundary at Acceptance Time

- SPEC: `INDEPENDENTLY_ACCEPTED` only for the exact SHA above.
- IMPLEMENTATION: not accepted by this audit — not implemented / tested /
  production-composed / runtime-verified / live-verified by virtue of this
  record.
- P1–P4: existing dirty worktree implementation/test state only, subject to
  later revalidation against this accepted Spec.
- P5: PARTIAL / STOPPED. P6+: NOT STARTED. Production deterministic default:
  LEGACY.
- Implementation Plan `F14CF4091DFE1331F0403995B8D7B5D7E952E1502F4ED7C56C3F513667C868A5`
  remains STALE and MUST NOT be reused as implementation authority. No
  implementation may resume until (1) this exact Spec SHA is accepted (done by
  this record), (2) the Plan is rebound/revised to it, (3) that Plan revision
  is independently accepted, and (4) implementation authority is explicitly
  rebound.

## File Scope of This Task

Before writing, `git status --short` showed the pre-existing dirty worktree
(93 entries, unchanged by this task). After writing, the only intentional
new file from this task is:

```text
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENT_ACCEPTANCE.md
```

No Spec, Plan, code, test, history, architecture, inventory, or existing audit
file was modified. Verification was limited to read-back of this record, the
Spec hash recomputation, and `git status` inspection. No implementation tests
were run.

Acceptance is now durable repository evidence under `docs/audit/**` rather
than chat-only output.
