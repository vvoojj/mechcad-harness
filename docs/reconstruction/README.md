# MechCAD Historical Reconstruction

This directory is an **evidence-driven historical reconstruction** of how
MechCAD was actually built, milestone by milestone, from M0 through M13-4. It is
not a statement of current production behavior and it is not normative.

## What this is

- A forensic reconstruction of each logical milestone from exact Git objects,
  committed specifications/plans/audits, and committed artifacts.
- A strict separation of `SPEC`, `PLAN`, `IMPLEMENTATION`, `TESTS`,
  `EXECUTION`, `COMPLETION`, `REVIEW`, `ACCEPTANCE`, `AUDIT`, and
  `RETROSPECTIVE`.
- A record that preserves historical defects and rejected acceptance rounds
  rather than smoothing them away.

## What this is not

- Not proof. The catalog and ledger are **discovery indexes**, not authority.
- Not a replacement for the normative architecture under `docs/architecture/`
  or the system acceptance audit under `docs/audit/`.
- Not current behavior. A capability's existence here is historical; consult
  current code and normative docs for present behavior.

## Evidence methodology

1. Milestones are discovered from the union of commit subjects/ancestry,
   README/AGENTS references, `docs/superpowers/specs/**`,
   `docs/superpowers/plans/**`, `docs/audit/**`, completion/acceptance/review/
   remediation/reconciliation artifacts, and capability matrices.
2. Each milestone is reconstructed from exact trees via
   `git show <sha>:<path>`, `git diff <parent>..<commit>`, and ancestry checks.
3. Committed test presence is **never** treated as historical execution
   success. Where no transcript survives, status is `NOT_RETAINED`; where live
   evidence survives it is marked `RETAINED_LIVE`.
4. Shared commits are represented as shared; bundled logical milestones are
   kept nested rather than flattened.
5. Historical implementation defects and report discrepancies are documented,
   not fixed.

## Status semantics

- `DELIVERABLE_TYPE`: `DESIGN_ONLY`, `IMPLEMENTATION`, `IMPLEMENTATION_AND_
  LIVE_VALIDATION`, `LIVE_VERIFICATION`, `ACCEPTANCE_ONLY`, `REMEDIATION`,
  `RECONCILIATION`, `DOCUMENTATION_ONLY`, `TRUST_BOUNDARY_CORRECTION`,
  `DOCUMENTARY_ARTIFACT_PACKAGE`, `MIXED`.
- `HISTORICAL_EXECUTION_EVIDENCE`: `NOT_RETAINED`, `RETAINED_FOCUSED`,
  `RETAINED_LIVE`, `ARTIFACT_INSPECTION_ONLY`, `NOT_APPLICABLE`.
- `ACCEPTANCE_STATUS`: an exact recorded marker where one exists, else
  `NOT_FOUND`.

## Where to look

- [`MILESTONE_LEDGER.md`](MILESTONE_LEDGER.md) — one row per boundary with
  status.
- [`MILESTONE_CATALOG.json`](MILESTONE_CATALOG.json) — machine-readable
  logical-milestone graph (including bundled sub-layers).
- [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md) — chronological narrative.
- [`CAPABILITY_EVOLUTION.md`](CAPABILITY_EVOLUTION.md) — when each capability
  first became real and how it evolved.
- [`UNRESOLVED_GAPS.md`](UNRESOLVED_GAPS.md) — remaining historical gaps.
- `milestones/**` — canonical per-milestone records.
- `evidence/**` — forensic Git evidence per milestone.

## Historical vs current

Reconstruction conclusions are anchored to the milestone's **own boundary
commit**, never to current `master`. The reconstructed endpoint is M13-4
(`185a304796c17793519fb5f01dbf80cca73ab51e`). Commits after it are this
reconstruction's own documentation checkpoints. Untracked Rotator V2 work is a
separate, unaccepted activity and is not reconstructed here.
