# MechCAD Deterministic STEP Content Identity — Implementation Plan Revision 36ABD3CE Independent Acceptance

## Title

MechCAD Deterministic STEP Content Identity — Implementation Plan Revision 36ABD3CE Independent Acceptance

## Task

Independent acceptance of exact implementation-Plan bytes only.

This task is an independent audit / acceptance materialization. It is not
implementation, not Plan remediation, and not Spec remediation. No production
code, test, Plan, Spec, architecture, capability inventory, reconstruction /
history, or existing accepted audit was edited. No commit, amend, push, tag,
release, reset, stash, clean, package installation, FreeCAD/Gmsh/CalculiX/MINI
execution, or implementation test was performed.

## Plan Path

```text
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md
```

## Accepted Plan SHA-256

```text
36ABD3CEC2A61C45F4DD4260DA7D3A281B74C9656AF254FE98CF4F19321B4BE2
```

Independently recomputed from current disk via
`Get-FileHash -Algorithm SHA256` before any other acceptance action. Exact
match with the required value.

## Controlling Spec Path

```text
docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md
```

## Controlling Spec SHA-256

```text
DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68
```

Independently recomputed from current disk via
`Get-FileHash -Algorithm SHA256`. Exact match with the required value.

## Spec Acceptance Record

```text
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_REVISION_DE17C360_INDEPENDENT_ACCEPTANCE.md
```

Verified on disk: the record binds the exact Spec SHA
`DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`
with disposition `INDEPENDENTLY_ACCEPTED` and marker
`MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_INDEPENDENTLY_ACCEPTED`.

## Disposition

```text
INDEPENDENTLY_ACCEPTED
```

## Scope

Acceptance applies ONLY to the exact Plan bytes identified by SHA-256
36ABD3CEC2A61C45F4DD4260DA7D3A281B74C9656AF254FE98CF4F19321B4BE2.

Any byte change creates a different Plan revision not covered by this acceptance.

## Independent Pre-Acceptance Check

Acceptance was not granted on the word of any prior chat/orchestrator report.
The exact current Plan bytes were independently inspected. The independently
audited closure is still present in those bytes. Findings per required check:

### A. Authority

- Accepted Spec is `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`
  (Plan Global Constraints + §0 rebind + Plan-status footer).
- Superseded Spec revisions (`1C1284D3B6F281C09FF457D6C708B2D770038C67F7C72306D880A95F149DEFAF`,
  `A4567143EE2583F95A2C6C680CBCA7AFBFD3761F2568AB5AD20EBDE38C629325`,
  `C1652A61F100EE66F6CF8EE6EC311CD46F0CB778FA72C61B42A63690FA087DED`)
  appear only as historical / superseded authority and must not control future
  work.
- This Plan revision is internally PROPOSED / NOT accepted
  ("PROPOSED REVISION ... this revision is NOT accepted until independently
  re-audited"; "NEW revised Plan independent acceptance: UNKNOWN / NOT YET
  AUDITED"; "No implementation continuation is authorized by this planning
  revision").
- No self-reference claims the current post-pass Plan SHA is accepted
  (Final-pass fix A: no pre-audit Plan SHA is labeled accepted; the new
  revised Plan SHA is unaccepted until audit succeeds).

### B. Capability Classification

The Plan consistently describes exactly THREE
`EXISTING_CAPABILITY_NOT_WIRED_TO_THIS_PATH` path-specific wiring edges under
the same accepted deterministic-content-identity Epic:

1. request@2/candidate@2 trusted semantic binding/verification (existing
   candidate integrity/publication/currentness services + `ProductionApplication`
   composition have no semantic trusted-binding/verifier connection yet);
2. T-P3.4 candidate-CAD trusted per-slot raw provenance verification (existing
   authority/specification/mapping/assembly/imported-component join pieces and
   exact-source resolve have no per-slot expected/actual verifier connection
   yet);
3. T-P7.2 §18B MJ typed-parent provenance publication/resolution (existing
   `ArtifactStore` + `CandidateProvenanceArtifactService` machinery is already
   used for current provenance families but is not connected to the MJ
   typed-parent path).

For edge 3 the distinction is confirmed: the
`candidate-multi-joint-m10-provenance@1` MODEL/ENVELOPE is separately `MISSING`
and requires the minimum Spec-required (§18B) extension; the existing
`ArtifactStore` + `CandidateProvenanceArtifactService` machinery is the
existing capability; only the connection to the MJ typed-parent path is
`EXISTING_CAPABILITY_NOT_WIRED_TO_THIS_PATH`. No fourth contradictory count.
No stale "exactly TWO" wording exists in the Plan bytes.

### C. T-P3.4

- T-P3.4 owns `candidate-cad-provenance@2` (exactly one §18A envelope).
- Spec tests 94/95/96 are owned by T-P3.4 via the new focused suite
  `tests/unit/test_candidate_cad_provenance_per_slot_v2.py`, exercised through
  the actual publish → fresh resolve/restart path.
- Fresh publish→resolve/restart boundary is required; a prior in-memory
  evaluation check is explicitly insufficient.
- Global raw completeness, per-slot raw correctness, and semantic equivalence
  stay three independent obligations, never merged.
- No positional zip; no raw-semantic cardinality / length equality.
- No P3→P7→P3 cycle: T-P3.4 (P3) performs first positive construction +
  verification; T-P7.2 regression-verifies compatibility without redefinition
  or a duplicated verifier.

### D. §18A

Exactly SIX provenance @2 envelopes total:

1. `candidate-cad-provenance@2` — T-P3.4
2. `candidate-evaluation-provenance@2` — T-P7.2
3. `candidate-comparison-provenance@2` — T-P7.2
4. `candidate-selection-provenance@2` — T-P7.2
5. `canonical-cad-provenance@2` — T-P7.2
6. `canonical-m10-provenance@2` — T-P7.2

Confirmed as "6 §18A envelopes + 1 §18B sibling = 7 no-self-hash containers;
§18B is NOT a seventh §18A @2 envelope". No envelope self-hash
("no-hash containers"). Canonical-M10 provenance remains EXACTLY 5 fields
(preserved closure, DE17C360 rebind + per-slot scan bullet).

### E. §18B

ONE separate sibling `candidate-multi-joint-m10-provenance@1` with EXACTLY
7 declared fields:

1. `schema_version`;
2. typed RequestV2 (`CandidateMultiJointM10EvaluationRequestV2`);
3. typed EvaluationV2 (`CandidateMultiJointM10EvaluationV2`);
4. typed SelectionV2 (`CandidateMultiJointSelectionV2`);
5. persisted `MultiJointCollisionSweepResultV2` body (P6 execution record);
6. candidate-publication `ArtifactReference` (`CAND-` artifact);
7. candidate-CAD `ArtifactReference` (`candidate-cad-provenance@2` artifact).

Confirmed: T-P7.2 owns its first implementation (focused suite
`tests/unit/test_candidate_multi_joint_m10_provenance_v1.py`); T-P5.3 still
owns the MJ RequestV2/EvaluationV2/SelectionV2 records; no
`candidate-multi-joint-m10-provenance@2`; no `locator@2`; no self-hash;
existing `ArtifactStore` / `CandidateProvenanceArtifactService` reused with no
new store/service/registry/locator.

### F. Restart

- P5 request = PURE_REDERIVED (existing `_reconstruct_m10_request_v2` from
  persisted/resolved bridge@2 + CAD realization@2 + scope; no P5 body
  persisted).
- P6 result = persisted / RESOLVED typed replay (model-validate + legacy
  self-hash recompute + legacy replay validation before semantic acceptance).
- Root A = verified in-process entry context only (NOT durable).
- Roots B/C = durable fresh-process restart roots (decision manifest@2 /
  result manifest@2 with byte-verified decision artifact and recomputed
  `decision_hash`).
- The MJ provenance artifact ID derives only after the expected selection hash
  is verified (`"CANDIDATE-MULTI-JOINT-M10-" + selection_hash[7:31]` from the
  verified expected tuple; ID truncation can never alias).
- Zero CAD/solver/sweep/provider execution during replay.

### G. Dependency / Status

- Phase graph remains acyclic (P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8; P8.1 →
  P8.2 → P8.4a CODED FINAL activation → post-activation tests → P8.3 LIVE →
  audit; "no cycles").
- R-P5.1–R-P5.4 are preserved historical executed work (implemented under
  predecessor `AF1C6C4A...`, subject to fresh R-P5.6 verification).
- R-P5.5 NOT performed; R-P5.6 NOT performed.
- P5.3 STOPPED (promotion-ownership STOP; resumes at R-P5.5 after
  re-acceptance, then R-P5.6; no P6/P7 early start).
- P6+ NOT STARTED as claimed by the Plan baseline.
- T-P7.2 STOPPED (reject-only boundary until predecessors green + this Plan
  accepted + explicit authorization).
- Production default LEGACY (change occurs once at coded T-P8.4a; no
  post-audit flip).
- Implementation remains unauthorized by Plan acceptance alone.

## Findings Summary

```text
CRITICAL: none
IMPORTANT: none
```

Accepted planning closure:

- one deterministic STEP content-identity Epic;
- one genuine reusable primitive platform gap at P1
  (`step-content-identity@1` + bounded STEP HEADER parser);
- exactly three path-specific existing-capability wiring edges;
- no duplicate store/service/registry/authority path;
- T-P3.4 candidate-CAD provenance ownership;
- tests 94/95/96 ownership;
- six §18A @2 provenance envelopes;
- separate §18B seven-field MJ @1 sibling;
- T-P7.2 §18B publication/resolution ownership;
- P5 PURE_REDERIVED / P6 RESOLVED boundary;
- Root A entry-only / Roots B+C durable;
- no MJ@2;
- no locator@2;
- phase graph acyclic;
- LEGACY production default retained until planned T-P8.4a coded final
  activation.

## Historical / Future Authority Statement

The predecessor Plan SHA

```text
AF1C6C4AB8445FF4A848FAD6D478B1D1A46B970CE70E7855A3B5A64E9867D607
```

and its existing acceptance record

```text
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_INDEPENDENT_ACCEPTANCE.md
```

remain the historical authority/evidence for the already-executed R-P5.1–R-P5.4
work.

This new acceptance of

```text
36ABD3CEC2A61C45F4DD4260DA7D3A281B74C9656AF254FE98CF4F19321B4BE2
```

supersedes prior Plan revisions as the applicable planning authority for
FUTURE work beginning with R-P5.5 onward.

This acceptance does NOT claim that
`36ABD3CEC2A61C45F4DD4260DA7D3A281B74C9656AF254FE98CF4F19321B4BE2`
was the Plan under which R-P5.1–R-P5.4 originally executed. It was not.

This acceptance does NOT retroactively execute, test, verify, or accept any
implementation work.

## Implementation Authorization Boundary

```text
PLAN ACCEPTANCE IS NOT IMPLEMENTATION AUTHORIZATION.
```

After this acceptance:

- R-P5.5 remains NOT EXECUTED;
- R-P5.6 remains NOT EXECUTED;
- P5.3 remains STOPPED;
- P6/P7/P8 do not start automatically;
- T-P7.2 remains STOPPED;
- production default remains LEGACY.

A separate explicit human implementation authorization is required before any
implementation resumes.

When such authorization is later given, implementation must start by:

1. recomputing accepted Plan SHA from disk;
2. verifying it equals 36ABD3...;
3. recomputing accepted Spec SHA;
4. recording HEAD/worktree/diffs;
5. reconciling dirty targets;
6. resuming at R-P5.5;
7. then executing R-P5.6 before P5.3 continuation.

None of those implementation actions were performed in this acceptance task.

## Evidence / Execution Claim Boundary

No implementation tests were run for this acceptance materialization.

No FreeCAD/Gmsh/CalculiX runtime was executed.

No implementation capability is newly TESTED, PRODUCTION_COMPOSED,
RUNTIME_VERIFIED, LIVE_VERIFIED, or INDEPENDENTLY_ACCEPTED by this Plan
acceptance.

This record accepts the implementation PLAN, not its future execution.

## Worktree Safety Record

- Branch: `master`.
- HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.
- Dirty-worktree presence: YES — preserved. Pre-write `git status --short`
  showed 100 entries (46 modified tracked paths, 54 untracked paths). The only
  intentional addition by this task is:

```text
docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_REVISION_36ABD3CE_INDEPENDENT_ACCEPTANCE.md
```

- No other repository file was changed by this task.
- No commit/reset/stash/clean/push/install occurred.
- Pre-existing dirty files were not created or modified by this task; their
  presence is recorded here only as worktree context, not as work performed.

## Acceptance Marker

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_IMPLEMENTATION_PLAN_REVISION_36ABD3CE_INDEPENDENTLY_ACCEPTED
