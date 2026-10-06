# Deterministic STEP Content Identity Implementation Plan — Independent Acceptance Audit

## Verdict

```text
Target:
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md

Exact accepted Plan SHA-256:
AF1C6C4AB8445FF4A848FAD6D478B1D1A46B970CE70E7855A3B5A64E9867D607

Controlling accepted Spec SHA-256:
1C1284D3B6F281C09FF457D6C708B2D770038C67F7C72306D880A95F149DEFAF

Disposition:
INDEPENDENTLY_ACCEPTED

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_INDEPENDENTLY_ACCEPTED
```

This disposition applies only to the exact Plan bytes identified above, under
the exact accepted Spec bytes identified above. Any byte change to either
document is outside this acceptance.

## Audit Independence and Scope

This was a read-only final re-audit and acceptance-evidence materialization. No
Plan, Spec, production code, test, architecture, reference inventory,
reconstruction/history, or existing audit was edited. No implementation tests,
FreeCAD/Gmsh/CalculiX/MINI/live runtime, commit, reset, stash, clean, push, or
installation was performed. This new document is the only file created by this
task. The dirty worktree was preserved.

The previous rejection was treated as a claim to re-check, not as authority.
The exact target and accepted Spec hashes were independently recomputed from
disk. The re-audit inspected the revised Plan, its controlling Spec and durable
Spec acceptance record, current source APIs for the claimed partial/blocked
boundaries, and the current worktree status. Tests were not executed; test
commands in the Plan remain future implementation gates, not execution evidence
from this audit.

## Authority Chain

```text
Spec:
docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md
  → SHA-256 1C1284D3B6F281C09FF457D6C708B2D770038C67F7C72306D880A95F149DEFAF
  → docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENT_ACCEPTANCE.md
  → MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENTLY_ACCEPTED

Plan:
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md
  → SHA-256 AF1C6C4AB8445FF4A848FAD6D478B1D1A46B970CE70E7855A3B5A64E9867D607
  → this independent acceptance record
  → MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_INDEPENDENTLY_ACCEPTED
```

The accepted Spec retains its pre-audit PROPOSED status wording. The Spec
acceptance audit explains why those exact bytes must remain unchanged and is the
durable repository evidence for acceptance. The Spec’s acceptance does not
accept the implementation or authorize implementation by itself.

The Plan is proposed before this record; it is accepted for implementation
planning authority only by this audit. The historical Plan SHA
`F14CF4091DFE1331F0403995B8D7B5D7E952E1502F4ED7C56C3F513667C868A5` remains
accepted for its own stale revision only and must not authorize future work.
The previously rejected Plan SHA
`F1295B370D49B641FFC60356480F8FF1A79FA1196A18181DDB58E4417B6ACFFB` remains a
historical rejection disposition; this record does not rewrite it.

## Final Re-Audit Reconfirmation

No new CRITICAL or IMPORTANT finding remains in the exact Plan revision.

- **P5-R0 is mandatory before P5.3 resumes.** R-P5.6 requires current-byte
  reconciliation, alignment tasks R-P5.1–R-P5.5, fresh candidate-owner tests
  first, candidate trusted request/candidate verification, candidate-CAD
  predecessor revalidation, a minimal P4 regression, fresh P5.1 and P5.2 runs,
  `compileall`, and targeted `git diff --check`. P6/P7 positive suites are
  explicitly excluded from this gate.
- **Cases 89/90/92/93 have staged ownership.** P5 owns only the candidate/CAD/
  mechanism/bridge/MJ-prefix applicable to each case; P7.1 owns the generic
  evaluation/comparison/selection suffixes; P7.2 owns promotion suffixes; P8.1
  owns the complete aggregate. Case 91 remains entirely P5-R0-owned, and its
  candidate-owner test commands are required by R-P5.6 before P5.3 resumes.
  The case-93 unresolved-item rules preserve multiset multiplicity, sensitivity
  to add/remove/field change, promotion ineligibility, and the rule against
  inventing promotion identities. Request-scope tuple ordering remains deferred
  by NOTE N-G.
- **Wire/replay and semantic specification identity are separate.** The
  existing `_specification_payload_for_schema` remains the persisted/wire owner
  and retains raw/replay/provenance data. The existing
  `semantic_component_specification_hash` /
  `semantic_component_specification_projection` path, reusing
  `semantic_m13.py`, owns the @4 semantic hash. The Plan forbids a second
  component projection and requires round-trip, raw-only invariance,
  engineering-change sensitivity, and legacy compatibility tests.
- **Existing dirty implementations are reused and aligned.** T-P1.1,
  T-P2.2–T-P2.5 and T-P5.1 distinguish current partial work from historical
  absence and require reuse/verification/minimal alignment. The existing
  `candidate_synthesis_request_hash_v2`, semantic authority module, semantic
  M13/component projections, and M10 projection functions are not represented
  as absent or as new parallel authorities.
- **Candidate@2 closure remains exact.** The Plan pins the 15 declared fields
  and 13-entry candidate hash payload, excludes `source_binding` as a full
  object and the self-hash, requires a verified request@2, sorts component
  specifications and complete design-variable records, preserves unresolved
  item multiset multiplicity, and uses only the shared realization projection.
  Candidate@1 stays frozen; no candidate@3 is introduced.
- **P5 semantic closure is explicit.** One shared realization projection feeds
  candidate hashing and `semantic_candidate_mechanism_hash`; one shared
  design-variable projection feeds candidate and admissibility@2 hashing; one
  shared axis-source projection is delegated to by M10-local logic. The
  admissibility@2 variable correction is restricted to its unaccepted,
  pre-activation family; admissibility@1 stays frozen, with no @3.
- **Bridge and MJ identities are bound consistently.** Candidate-track
  `physical_mechanism_hash` is rebound to
  `semantic_candidate_mechanism_hash(candidate.realization)`; canonical-track
  identity remains canonical mechanism@4. Raw and cross-track substitutions
  must fail without a bridge shape change. `project_id` is included in MJ
  request@2, evaluation@2, and selection@2 hashes; no @3 or coordinate-only
  interpretation remains. The Plan calls out the current evaluation digest
  omission as a P5 alignment task.
- **Request@2 trust/currentness/restart remains request-first.** The Plan
  requires one trusted semantic-binding core, typed request@2 binding before
  pure candidate@2 construction, contextual request/candidate verification,
  typed-request currentness, no @1→@2 upgrade, no candidate pending-binding
  authority, and verify-only restart. Candidate@2 source-only currentness
  cannot return CURRENT.
- **P7 current-worktree precision is corrected.** Candidate-canonical-mapping@3
  is recorded as P4-owned PARTIAL. The distinct evaluation/comparison/selection,
  promotion, M11, and provenance@2 families are MISSING in current code. The
  complete P7 production family remains unimplemented.
- **P8 order is acyclic and bound to the final default.** P8.1 → P8.2 → P8.4a
  CODED FINAL activation → post-activation composition/mixed-version tests →
  P8.3 LIVE through the same final default → independent implementation audit
  → accepted/deployed release state only. There is no caller family flag,
  downgrade, post-audit code/default flip, or verification-only live route.

## Status and Evidence Boundary

- **Plan:** independently accepted only for the exact Plan SHA in this record.
- **Spec:** independently accepted only for the exact Spec SHA and marker in
  the Spec acceptance record above.
- **Implementation:** NOT accepted by this audit. No code/test execution or
  production/live evidence was created here.
- **P1–P4:** dirty-worktree implementation/test artifacts only, subject to
  fresh P5-R0 revalidation; presence of tests is not proof they passed.
- **P5:** PARTIAL / STOPPED at acceptance time. P5.3 must not resume until
  P5-R0 and fresh P5.1/P5.2 gates are green.
- **P6+:** NOT STARTED.
- **Production deterministic default:** LEGACY until T-P8.4a.
- **First implementation action under this accepted Plan:** execute P5-R0,
  not direct P5.3 continuation. Implementation still requires its separately
  explicit authorization.

## Worktree Scope

Pre-write `git status --short` was captured before creating this file. It showed
94 existing entries: 46 modified tracked paths and 48 untracked paths. The
dirty worktree was left intact; no existing path was edited or removed. The
only intended addition by this task is:

```text
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_INDEPENDENT_ACCEPTANCE.md
```

The pre-write command output was captured during this audit; its entry count and
modified/untracked counts are retained here. No commit, stage, reset, stash,
cleanup, push, package installation, implementation test, or live runtime was
performed.

After creation, `git status --short` showed 95 entries: 46 modified tracked paths
and 49 untracked paths. Compared with the pre-write snapshot, the only new entry
is this audit file; the prior dirty entries remain present and unchanged.
