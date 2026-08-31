# M12-6 Live End-to-End Physical Mechanism Acceptance

**Date:** 2026-08-30
**Status:** M12-6 acceptance specification - approved for implementation planning.
No production capability is proposed by this specification.

## Purpose

M12-6 proves the accepted bounded supplied-component revolute-drive workflow as
one production chain. It begins with explicit source-bound inputs and ends with
a newly promoted canonical physical mechanism that is freshly reconstructed,
realized, and verified without candidate authority.

The final claim is limited to direct-drive and external-spur candidates supplied
by the caller: deterministic M12-3 sizing/admissibility; candidate CAD and real
FreeCAD M10 evaluation; explicit evaluation, comparison when requested, and
selection; ChangeEngine-only promotion; fresh canonical CAD/M10 rebinding;
cross-revision source provenance; replay/currentness protection; and M11
eligibility assessment only.

## Accepted Baseline

M12-1 through M12-5 are closed and are reused without redesign. M9, M10, and
M11 accepted behavior remains authoritative. This acceptance does not add a
candidate-generation architecture, catalog search, automatic selection, a second
state-mutation mechanism, new M10 semantics, or M11 execution.

## Production Preflight

| Stage | Required production surface | Classification |
| --- | --- | --- |
| Candidate request and policy | `CandidateSynthesisRequest`, `CandidateSynthesisPolicy` | `PRODUCTION_READY` |
| Direct-drive and external-spur realization | `ProductionApplication.realize_and_evaluate_revolute_drive` | `PRODUCTION_READY` |
| Candidate CAD | `ProductionApplication.realize_candidate_cad` | `PRODUCTION_READY` |
| Candidate M10 and evaluation | `ProductionApplication.evaluate_candidate` | `PRODUCTION_READY` |
| Comparison and selection | `ProductionApplication.compare_candidates`, `ProductionApplication.select_candidate` | `PRODUCTION_READY` |
| Promotion | `ProductionApplication.promote_selected_candidate` -> `CandidatePromotionApplicationService` -> `RunController.apply_approved_proposal` -> `ChangeEngine` | `PRODUCTION_READY` |
| Promotion manifests | Composed `PromotionManifestService` and run-scoped `ArtifactStore` | `PRODUCTION_READY` |
| Canonical reconstruction | `ProductionApplication.reconstruct_promoted_mechanism` | `PRODUCTION_READY` |
| Primary post-promotion verification | `ProductionApplication.verify_promoted_mechanism` | `PRODUCTION_READY` |
| Canonical CAD and M10 boundary checks | Composed `canonical_cad_compiler.realize`, `canonical_m10_service.execute` | `PRODUCTION_READY` |
| M11 handoff | `build_handoff_request`, composed `m11_handoff_service.assess` | `PRODUCTION_READY_WITH_LIMITATION` |
| Artifact and Evidence persistence | Composed `ArtifactStore`, `EvidenceStore` | `PRODUCTION_READY` |

No required stage is test-helper-only, uncomposed, or blocked. No production edit
is currently indicated. If a production change becomes necessary, it must be
classified before implementation as `INTEGRATION_FIX`,
`PREDECESSOR_REGRESSION_FIX`, `ACCEPTANCE_EVIDENCE_SUPPORT`, or
`NEW_CAPABILITY`. An out-of-scope `NEW_CAPABILITY` stops this acceptance.

## Acceptance Fixtures And Authority

Dedicated integration modules use separate clean projects or independently
initialized revision-1 snapshots for direct-drive, external-spur comparison-used,
external-spur no-comparison, and non-top-ranked selection promotions. No
promotion-bearing scenario may reuse a stale candidate/evaluation/selection set
from another source lineage unless it intentionally tests staleness.

Fixture helpers may use accepted project/bootstrap/StateManager APIs to create
the initial source revision only. This **INITIAL ACCEPTANCE FIXTURE BOOTSTRAP**
is distinct from design mutation. Helpers must not edit revision JSON, rewrite
revision files, patch a current pointer, insert a physical mechanism into an
existing revision, or create an artificial source revision that cannot be loaded
through normal `StateManager` contracts. After bootstrap, every relevant
canonical change uses the normal ChangeEngine mutation path.

Helpers may create only input fixture authority: source `DesignState`, explicit
source bindings, supplied component snapshots, deterministic placement inputs,
and trusted STEP artifacts. Synthetic component data is labeled **M12-6
ACCEPTANCE FIXTURE SOURCE AUTHORITY**. It is not described as manufacturer or
catalog truth.

Helpers may not construct or return an admissibility result, CAD result, M10
result, evaluation, comparison, selection, promotion result, canonical result,
or automatic selection. Those records must be produced visibly through the
production-composed service path.

Every positive mechanism includes at least one selected trusted imported STEP
source. The test freshly resolves it through `ArtifactStore`, verifies expected
STEP type, artifact ID, content hash, bytes, and original source revision/state
provenance. Imported STEP means the complete artifact including every top-level
shape.

## Direct-Drive Primary Scenario

The primary test visibly performs and asserts these stages:

```text
source N/HN
  -> explicit CandidateSynthesisRequest and CandidateSynthesisPolicy
  -> ProductionApplication.realize_and_evaluate_revolute_drive
  -> admissible immutable direct-drive candidate
  -> ProductionApplication.realize_candidate_cad
  -> ProductionApplication.evaluate_candidate with real FreeCAD M10
  -> FEASIBLE CandidateEvaluation
  -> explicit CandidateSelection without implicit ranking
  -> ProductionApplication.promote_selected_candidate
  -> exactly one N+1/HN1 revision through RunController and ChangeEngine
  -> fresh decision/result manifest resolution
  -> ProductionApplication.verify_promoted_mechanism
```

The direct template includes motor, shaft, exactly two supports/bearings, hub or
coupling, mount, driven body, accepted physical interfaces/connections, selected
geometry sources, placements, physical-joint binding, and one canonical M10
clearance obligation. The candidate M10 proof uses a bounded explicit interval
and required clearance that reach real `VERIFIED_CLEAR` without inflated proof
budgets. The test records the checked pair, certificate lower bound, and proof
evaluation/leaf counts where the result exposes them.

The public `verify_promoted_mechanism` path is mandatory for this primary result.
It must expose and assert its reconstruction, projection equivalence, canonical
CAD identities, scope equivalence, canonical M10 identities/results, and final
`VERIFIED` status. Calling canonical services directly does not replace that
proof.

## Fresh Canonical Restart Proof

After the primary promotion and fresh manifest verification, the test discards
the original `ProductionApplication`, promotion application result, promotion
request/compilation, candidate, M12-3 result, evaluation, comparison, selection,
candidate CAD/M10, and in-memory pre-promotion scope/projection records. It
constructs a new `ProductionApplication.create(...)` instance from persisted
workspace/configuration only. It cannot reuse the original application, its
service instances, or closures retaining candidate-side objects.

Only durable locators/expected integrity bindings may cross this boundary:
workspace and project ID, promoted N+1, HN1 as an expected integrity value,
canonical mechanism ID, result-manifest artifact ID, and any strictly necessary
immutable ArtifactStore locator. These are **DURABLE LOCATOR / AUDIT
IDENTIFIER** values, not engineering authority. They cannot supply candidate
physical semantics, properties, placements, evaluation/comparison/selection,
candidate CAD/M10, or canonical CAD/M10 inputs.

The fresh application loads N+1 from `StateManager` and recomputes/verifies HN1.
It uses the retained result-manifest locator to freshly resolve the
`CandidatePromotionResultManifest` from `ArtifactStore`. From the verified result
manifest's `decision_artifact_id` and `decision_artifact_hash`, it freshly
resolves the exact `SelectedCandidateDecisionManifest`; the test never supplies
an independent in-memory decision-artifact locator. The fresh decision manifest
supplies the durable promotable projection, pre-promotion M10 scope projection,
and candidate-to-canonical mapping for historical provenance, semantic round
trip, scope equivalence, and traceability only. The fresh application then
reconstructs the canonical mechanism from DesignState N+1, freshly resolves the
canonical selected source artifacts, runs fresh canonical CAD, and runs fresh
canonical M10. This proves the canonical physical mechanism is self-sufficient.
The test separately proves the candidate CAD realization hash differs from
canonical CAD realization hash and candidate M10 request hash differs from
canonical M10 request hash.

The durable pre-promotion scope projection is used only for the independent
scope-equivalence assertion. Neither it, the promotable projection, nor the
candidate-to-canonical mapping is passed into
`CanonicalM10VerificationService.execute` or used to supply canonical execution
semantics. They cannot influence canonical pair inventory, interval, clearance,
fidelity, home checks, or request construction; those inputs derive only from
canonical N+1 authority and selected trusted source artifacts.

The N snapshot is fresh-loaded after promotion and its state hash and serialized
bytes must remain unchanged.

## External-Spur Scenario

The external-spur module uses an independent source project/snapshot and invokes
the same production M12-3, candidate CAD/M10, evaluation, selection, promotion,
and canonical verification paths. At least one positive external-spur scenario
must reach `PromotedMechanismVerificationResult.VERIFIED` for its exact declared
bounded canonical output-joint M10 obligation. An unexpected failure to do so is
an M12-6 acceptance failure requiring fixture, predecessor-regression, or
integration investigation; it cannot be accepted merely by documenting an
unresolved outcome. It preserves the direct template plus driver gear, driven
gear, support mounts, and the physical gear-mesh connection.

The test explicitly asserts that the driver and driven gears exist, the gear-mesh
connection exists, the driver is `INTERNAL_MOTION_UNMODELED`, no coupled gear
joint exists, no phase model exists, no backlash model exists, no driver
counter-rotation proof exists, and no transmission-internal clearance
certification is claimed. Its required `VERIFIED` result applies only to the
declared bounded canonical output-joint obligation; it is not complete
transmission-kinematics verification.

This module separately demonstrates comparison-used selection, no-comparison
selection, and explicit non-top-ranked feasible selection. It uses only the
accepted `verified_clearance_lower_bound_mm` metric. Where the fixture supports
it, equal metric values prove deterministic tie behavior without using candidate
hash as an engineering preference. Selection remains explicit in every case.

## Representative Cross-Stage Failure Matrix

The dedicated failure module covers these end-to-end boundaries; exhaustive
lower-level cases remain predecessor regression coverage.

| Scenario | Required outcome |
| --- | --- |
| Missing authority or M12-3 violation | No feasible evaluation or promotion path; M12-3 retains its actual inadmissible/unresolved result. |
| Candidate M10 collision witness | `CandidateEvaluation.INFEASIBLE`; no feasible selection/promotion. |
| Candidate M10 `NOT_PROVEN` | `CandidateEvaluation.UNRESOLVED`; no feasible selection/promotion. |
| Candidate currentness | A valid N-bound candidate/selection becomes stale after relevant canonical advancement and is rejected. |
| Post-promotion source tamper or foreign substitution | Canonical reconstruction/CAD fails closed; no candidate CAD or alternate source fallback. |
| Promotion replay | Replaying the exact N-bound request after N -> N+1 is rejected with no N+2 and no second mechanism. |
| Later canonical change | A normal ChangeProposal changes a relevant physical-mechanism input; prior canonical CAD/M10 no longer meet the implemented currentness/hash/dependency contract. |
| Target/instance collision and joint/obligation drift | Promotion or canonical M10 fails closed; no overwrite, silent remapping, or old proof reuse. |

Collision remains an engineering witness, `NOT_PROVEN` remains unresolved,
artifact mismatch remains integrity failure, provider failure remains operational,
and candidate staleness remains a currentness failure.

## Promotion, Provenance, And Identity

Promotion must use M12-5 exactly: readiness, compilation, normal N/HN-bound
run, decision artifact publication and fresh reload, RunController proposal
application, invalidation verification, result artifact publication and fresh
reload. It creates exactly one canonical revision on success. Candidate
evaluation, comparison, selection, canonical reconstruction, CAD, M10, and M11
handoff do not create revisions.

The acceptance evidence records, without large payload dumps:

- source project, N, HN, trusted STEP artifact ID/hash/original provenance;
- synthesis request/policy, M12-3 result, candidate, candidate CAD request/result,
  candidate M10 scope/request/result, and evaluation hashes;
- comparison request/result and selection hashes where used;
- promotion request/policy, projection, scope projection, compilation,
  proposal-semantic hash, operational proposal/ChangeSet IDs, run ID as
  correlation only, decision/result artifact IDs and hashes, N+1/HN1;
- canonical mechanism/reconstruction, canonical CAD request/result, canonical
  M10 scope/request/result, scope-equivalence, promoted-verification, and M11
  handoff hashes.

Run IDs, timestamps, paths, and operational UUIDs are not asserted as semantic
identity. Run-ID independence is proved in a focused pure semantic test or an
isolated acceptance fixture, never by duplicate manifest publication in a
primary direct/spur project where project-wide artifact lookup could become
ambiguous. One normal promotion run and its truthful artifacts are sufficient in
each primary lineage. Decision and result manifests are fresh-resolved before
reliance. Historical manifest integrity is separate from replay currentness.

## Semantic Round Trip

The direct and spur scenarios compare the frozen promotable projection with the
normalized projection reconstructed from canonical N+1. They prove representative
property value, unit, authority, source, property hash, availability/applicability;
accepted design-choice classification; selected geometry-source reference;
placement semantics; physical topology; interface/connection role; joint binding;
and canonical M10 obligation round trips. Candidate evaluation, comparison rank,
selection rationale, candidate CAD, and candidate M10 remain historical
provenance only after promotion.

## M11 Eligibility Boundary

The direct path makes two post-promotion eligibility-only assessments without M11
execution or fabricated structural authority:

- whole-mechanism target -> `NOT_ELIGIBLE`;
- explicit canonical single-solid mount/support target lacking material, load,
  support, region, and structural definition authority -> `UNRESOLVED`.

Neither optional result blocks the bounded CAD/M10 `VERIFIED` outcome.

## Live Backend Evidence

The report records Python version, pytest version, platform/OS summary, FreeCAD
executable actually invoked, FreeCAD runtime-reported version, and actual
MechCAD CAD/M10 backend/provider identities. It distinguishes `INSTALLED`,
`PRODUCTION_COMPOSED`, and `LIVE_INVOKED` for every backend. The primary direct
scenario must invoke real FreeCAD. py-gearworks and build123d versions are
reported only when the external-spur scenario actually invokes those providers;
installation alone is not execution evidence.

## Test Organization And Verification

Add focused modules equivalent to:

```text
tests/integration/test_m12_6_end_to_end_direct_drive.py
tests/integration/test_m12_6_end_to_end_external_spur.py
tests/integration/test_m12_6_end_to_end_failures.py
```

The M12-3, M12-4, and M12-5 capstones remain unchanged as predecessor tests.
The acceptance run includes the dedicated M12-6 suite, a curated shared-boundary
regression matrix (candidate authority/currentness, M12-3 sizing, M12-4 CAD/M10/
evaluation/comparison/selection, M12-5 promotion/rebinding, state/change/run/
ownership/dependency/artifact, imported multi-shape CAD, M10, and M11 handoff),
then `py -3 -m pytest tests/` using a tool ceiling of at least 4000 seconds.

Required final checks are `compileall`, `git diff --check`, and an explicit
trailing-whitespace/final-newline scan of all new M12-6 files. The final audit
report is `docs/audit/MECHCAD_M12_6_SYSTEM_ACCEPTANCE.md`. It is durable audit
evidence, not canonical design authority.

## Non-Goals

M12-6 does not implement general synthesis, topology generation, catalog search,
automatic component/candidate selection, optimization, manufacturing approval,
complete-machine safety, arbitrary trajectory or configuration-space proof,
coupled gear kinematics, phase, backlash, tooth contact, bearing life, gear
strength, fatigue, thermal/nonlinear/contact/assembly FEA, tolerance/GD&T, cost,
release hardening, tagging, M13, commit, push, or a new store.

## Acceptance Self-Review Gate

Before requesting acceptance, review the implementation and report for: test
helpers acting as product paths; a new run-everything API; private canonical
services replacing an existing public application path; missing cross-stage
failure evidence; same-process-only re-execution; direct/spur lineage
contamination; auto-selection; hidden spur limitation; fixture facts presented as
catalog truth; installed-versus-invoked backend ambiguity; unclassified production
changes; candidate authority or candidate CAD/M10 reuse after promotion; direct
state mutation; fabricated M11 authority; and release/M13 scope creep.

## Specification Readiness

After the final correction self-review passes, the lifecycle status is
**M12-6 acceptance specification - approved for implementation planning**:

`M12_6_LIVE_END_TO_END_PHYSICAL_MECHANISM_ACCEPTANCE_SPEC_READY`

This marker means the acceptance contract is ready for implementation planning;
it does not mean M12-6 is verified.

## Final Gate

The final disposition may be
`M12_6_LIVE_END_TO_END_PHYSICAL_MECHANISM_ACCEPTANCE_VERIFIED` only when the
primary direct-drive real-FreeCAD path, fresh restart proof, promotion manifests,
candidate-independent canonical verification, replay/currentness checks, M11
eligibility boundary, and at least one independent live external-spur end-to-end
scenario reaches `PromotedMechanismVerificationResult.VERIFIED` for its declared
bounded output-joint obligation all pass. That external-spur scenario must also
show `INTERNAL_MOTION_UNMODELED` driver motion, no coupled gear joint, no
phase/backlash model, no driver counter-rotation proof, and no
transmission-internal clearance certification; its `VERIFIED` result is not
complete transmission-kinematics verification. Focused suite, predecessor
regressions, full suite, compile/diff/untracked scan, and self-review must also
pass. Otherwise the result is `M12_6_NEEDS_FIXES` or
`M12_6_BLOCKED_BY_OUT_OF_SCOPE_CAPABILITY` with the exact blocker.
