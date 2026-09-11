# MechCAD Reconstruction Unresolved Gaps Register

This register lists **genuine unresolved historical gaps** only. Already
documented deviations that were later fixed, or that are simply historical
defects now recorded, are excluded unless they leave a residual question.

Severity: `MINOR`, `MATERIAL_NON_BLOCKING`, `BLOCKING`.

**There are no BLOCKING gaps.** The reconstruction is internally complete and
evidence-traceable at the level of the discovered logical milestone graph.

---

## G-01 — M7A has no dedicated specification or plan

- **Affected:** M7A (M7A-1, M7A-2A, M7A-2B, M7A-2C).
- **Question:** What was the accepted requirement/spec baseline for the generic
  CAD/assembly/exact-geometry foundation?
- **Known evidence:** production source in `19f77a3`; live acceptance artifacts
  in `8079c57`; project description §M7A "COMPLETE"; capability matrix
  `REQUIRED_CURRENT`; reconciliation R-031/R-034.
- **Missing evidence:** no M7A spec, plan, or dedicated acceptance record.
- **Historical impact:** M7A's contract cannot be verified against a
  contemporary specification; only against later architecture prose and
  artifacts.
- **Downstream impact:** M8C/M9 reuse the M7A exact-geometry primitive without
  tracing back to an accepted M7A spec.
- **Severity:** MATERIAL_NON_BLOCKING.

## G-02 — M7B-2C repair commit is separate from its boundary

- **Affected:** M7B-2C (boundary `9ab9e48`; repair `8079c57`).
- **Question:** Which commit completes M7B-2C?
- **Known evidence:** the candidate is unrunnable at `9ab9e48` (missing
  `DesignState.yagi_collision_layouts`, ownership, and
  `collision_resolved_yagi_carrier_assembly`); `8079c57` adds all three.
- **Missing evidence:** no single completion commit or acceptance marker for
  M7B-2C.
- **Historical impact:** the milestone is a two-commit logical span not
  visible in the single ledger boundary column.
- **Downstream impact:** none functional; catalog now records the repair commit.
- **Severity:** MINOR.

## G-03 — M13-4 final acceptance rested on a then-untracked test file

- **Affected:** M13-4 (capstone).
- **Question:** Was the final acceptance reproducible from the commit?
- **Known evidence:** `MECHCAD_M13_4_INDEPENDENT_FINAL_ACCEPTANCE.md` states the
  governing capstone test `tests/integration/test_m13_4_full_stack_acceptance.py`
  was an untracked accepted artifact in a dirty worktree at acceptance time; it
  was later committed in `185a304`.
- **Missing evidence:** a clean-checkout acceptance transcript.
- **Historical impact:** final M13-4 acceptance is not reproducible from the
  terminal commit alone without reconstructing the dirty state.
- **Downstream impact:** none; the test is now tracked.
- **Severity:** MATERIAL_NON_BLOCKING.

## G-04 — Capability matrix labels M6B-2B `AMBIGUOUS` while reconstruction records implementation

- **Affected:** M6B / M6B-2B.
- **Question:** Was M6B-2B implemented or design-only?
- **Known evidence:** `928be44` contains committed M6B-2B implementation and 68
  added test functions; `MECHCAD_CAPABILITY_MATRIX.md` labels it `AMBIGUOUS`.
- **Missing evidence:** a resolution reconciling the normative and
  reconstruction classifications.
- **Historical impact:** two authoritative-looking documents disagree.
- **Downstream impact:** none functional.
- **Severity:** MATERIAL_NON_BLOCKING.

## G-05 — M0 change-proposal model "SUPERSEDED BY M2" vs M2 consuming it unchanged

- **Affected:** M0, M2.
- **Question:** Was the proposal model superseded or extended by M2?
- **Known evidence:** `milestones/M0.md` marks it `SUPERSEDED`; M2 consumes
  `ChangeProposal` unchanged at its boundary.
- **Missing evidence:** none; this is a documentation classification conflict.
- **Historical impact:** minor lifecycle-label inaccuracy.
- **Downstream impact:** none.
- **Severity:** MINOR.

## G-06 — M10-4 path partition validation gap

- **Affected:** M10-4.
- **Question:** Does M10-4 fail closed on malformed path partitions?
- **Known evidence:** duplicate/omitted IDs, and unknown IDs under a permissive
  measurement stub, can reach `VERIFIED_CLEAR`; a real FreeCAD provider fails on
  unknown instance lookup. The M10-4 plan names a regression file absent from
  the candidate.
- **Missing evidence:** assembly-backed partition validation and the named
  regression test were never added.
- **Historical impact:** the accepted M10 disposition overstates fail-closed
  coverage for malformed partitions.
- **Downstream impact:** M13-3/M13-4 reuse the path-proof concept; the gap did
  not propagate as a new defect in the reconstruction.
- **Severity:** MATERIAL_NON_BLOCKING.

## G-07 — Structural/FEA fixture EOL sensitivity affects reproducibility

- **Affected:** M11-3, M11-4, and DAT-fixture suites reused later.
- **Question:** What is the exact, reproducible focused/full test count?
- **Known evidence:** committed FRD/DAT blobs are LF; parser behavior requires
  FRD LF and DAT CRLF materialization; raw-archive replay yields counts
  differing from the retained report.
- **Missing evidence:** a canonical command capturing source and EOL state.
- **Historical impact:** reported counts (M11-3, M11-4, M12-5) are
  environment-dependent.
- **Downstream impact:** none functional.
- **Severity:** MATERIAL_NON_BLOCKING.

## G-08 — Stale report counts and "no commit" prose

- **Affected:** M5.5B, M9-2, M11-2, M11-3, M12-2, M13-1, M13-2, M13-3.
- **Question:** Which documented test counts and release statements are
  accurate?
- **Known evidence:** documented discrepancies include M5.5B full-suite
  reproduction 84/1 vs reported; M9-2 audit 8 vs 7 committed tests; M11-2
  153 vs 154; M11-3 151 vs 173 collected; M12-2 focused 10 vs 11 committed
  tests; and M13-1/2/3 completion reports stating "no commit was created"
  although the commits exist.
- **Missing evidence:** corrected historical reports (intentionally not
  rewritten; the reconstruction documents the discrepancy).
- **Historical impact:** minor count/process inaccuracies.
- **Downstream impact:** none functional.
- **Severity:** MINOR.

## G-09 — Documentation assertion precedes implementation (M10 multi-shape)

- **Affected:** `52e60e9` (documentation-only) vs M10-MULTI-SHAPE `28ac193`.
- **Question:** Which commit carries the multi-shape verification?
- **Known evidence:** `52e60e9` asserts
  `M10_MULTI_SHAPE_TRANSIENT_GEOMETRY_CONSISTENCY_VERIFIED`; the implementing
  source and tests first appear in the child `28ac193`.
- **Missing evidence:** none; this is a historical ordering anomaly.
- **Historical impact:** a verification claim chronologically precedes its
  introduction commit.
- **Downstream impact:** none functional.
- **Severity:** MINOR.

## G-10 — M6B-4C resolution workflow is implemented but unused, with a supported-Python defect

- **Affected:** M6B-4C.
- **Question:** Was the resolution workflow ever a production capability?
- **Known evidence:** `4468a62` implements application/workflow/provenance; a
  later audit classifies it `IMPLEMENTED_BUT_UNUSED`; an unimported
  `ConstraintResolutionRecord` annotation causes an import-time error under
  Python 3.11/3.12.
- **Missing evidence:** a production caller and a supported-version import fix.
- **Historical impact:** a substantial implementation never became a live
  capability.
- **Downstream impact:** superseded conceptually by later M12/M13 promotion
  paths; no code dependency.
- **Severity:** MATERIAL_NON_BLOCKING.

## G-11 — M11-5 live-evidence script and M10-4 regression file are absent

- **Affected:** M10-4, M11-5.
- **Question:** Are the named capture/regression artifacts present?
- **Known evidence:** `MECHCAD_M10_1_COMPLETION_REPORT.md` references an absent
  `scripts/m10_1_evidence_capture.py`; the M10-4 plan names an absent
  `tests/unit/test_m10_4_regressions.py`.
- **Missing evidence:** the referenced files.
- **Historical impact:** report claims are not fully rerunnable from the commit.
- **Downstream impact:** none functional.
- **Severity:** MINOR.

## G-12 — M12/M13 are not represented in the normative baseline documents

- **Affected:** M12-1..M12-6, M13-1..M13-4.
- **Question:** Are M12/M13 part of the accepted normative architecture?
- **Known evidence:** `AGENTS.md` and `docs/architecture/*` stop at M11-6;
  M12/M13 acceptance markers live only in `docs/audit/**`.
- **Missing evidence:** normative reconciliation of M12/M13 (out of scope for
  this reconstruction, which must not modify those files).
- **Historical impact:** M12/M13 are post-baseline candidates by the documents,
  though they have committed acceptance records.
- **Downstream impact:** a future reconciliation pass is needed to fold
  M12/M13 into the accepted baseline; not a reconstruction defect.
- **Severity:** MATERIAL_NON_BLOCKING.

## G-13 — M5 is import-broken at its own boundary

- **Affected:** M5 (and M5.5A).
- **Question:** Was M5 a runnable milestone at `6cbade0`?
- **Known evidence:** the shared commit imports absent
  `mechcad_harness.backends.models.BackendProvenance`; the package first
  appears in `b0d77e1`.
- **Missing evidence:** none; the defect is proven.
- **Historical impact:** M5 is committed implementation evidence but not a
  self-contained executable milestone; M5 acceptance is `NOT_FOUND`.
- **Downstream impact:** resolved by M5.5B.
- **Severity:** MINOR (historical, resolved downstream).

## G-14 — Artifact-package acceptance is metadata-based

- **Affected:** M7E-2 (and analogous preliminary artifact packages).
- **Question:** Is the artifact package independently verified?
- **Known evidence:** FCStd/STEP parse with matching solid counts/volume and
  embedded `KinematicConceptChecks`; the metadata is self-described and
  declares `NOT_VERIFIED`/`NOT_READY`.
- **Missing evidence:** an independent test/reload transcript or solver
  verification.
- **Historical impact:** acceptance is documentary only.
- **Downstream impact:** none; explicitly preliminary.
- **Severity:** MINOR.
