# Deterministic STEP Content Identity - T-P8.4a Activation Independent Verification

## Verdict

```text
Epic:
Deterministic STEP Content Identity

Gate:
T-P8.4a CODED FINAL activation (new homogeneous semantic family as the
ProductionApplication deterministic production default)

Human authorization:
H3 granted for the activation mutation

Controlling Spec:
DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Controlling Plan:
E449C60B641DBB5A4A630CC61553F5E586127443DC92B24BD5D983E3A15BB70E

Observed HEAD:
05da8edad18488492f02be1dad9d1ec3653ce807

Disposition:
INDEPENDENTLY_VERIFIED (activation only)

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_4A_ACTIVATION_INDEPENDENTLY_VERIFIED
```

This disposition covers the activation only. It does not accept live
verification, final implementation acceptance, commit, release, or deployment.

## Activation Mutation (minimal, scoped)

Exactly two hunks, both in `src/mechcad_harness/application.py`:

1. `ProductionApplication.realize_and_evaluate_revolute_drive` (~lines 2211-2219):
   the pre-activation reject-only gate
   `raise CandidateIntegrityError("candidate-synthesis-request@2 admission requires M12-3@2")`
   was removed. The `@2` branch now falls through to the pinned final-default
   sequence: trusted `bind_candidate_synthesis_request_semantic_identity` →
   pure `construct_candidate` (candidate@2) → local `CandidateIntegrityVerifier`
   → `CandidateCurrentnessService.evaluate` (contextual
   `verify_candidate_semantic_binding` for candidate@2) →
   `revolute_drive_service.evaluate` (`revolute-drive-admissibility@2`). The
   `construction.candidate is None` unresolved return is preserved.
2. `_validate_candidate_m12_3_result` (~lines 2639-2643): the M12-3
   source-binding comparison now schema-dispatches the expected hash
   (`candidate.semantic_source_binding_hash` for candidate@2, else the legacy
   raw `_candidate_source_binding_hash(candidate)`), matching the producing
   service convention at `revolute_drive/service.py:651-655` / `:833-837`.
   This closed the latent activation defect flagged by the readiness audit.

No new model, service, registry, persistence mechanism, or schema version was
introduced. The dispatcher and binder are pre-existing P2-owned capability.

## Independently Verified Properties

- **`@2` positive path**: genuine (real route emits
  `mechanical-design-candidate@2` and `revolute-drive-admissibility@2`).
- **`@1` legacy path**: preserved and byte-compatible (schema-version dispatch).
- **Mixed-family fail-closed**: confirmed at integrity, binder, currentness, and
  downstream staged boundaries.
- **Protected surfaces**: `multi_joint_kinematics.py` and
  `multi_joint_collision_sweep.py` byte-identical to their pinned SHAs;
  `test_m13_3_legacy_goldens.py` unchanged from HEAD.
- **Static checks**: `compileall` clean; `git diff --check` clean on
  `application.py`.

## Fresh Post-Activation Gate (exact invocations)

```text
python -m pytest tests/unit/test_candidate_production_admission_matrix.py \
  tests/unit/test_candidate_trusted_semantic_verification.py \
  tests/unit/test_candidate_multijoint_m10_v2.py \
  tests/unit/test_candidate_decision_v2.py tests/unit/test_promotion_v2.py -q
66 passed

python -m pytest tests/integration/test_m12_candidate_cad_m10_production.py \
  tests/integration/test_m12_promotion_production.py -q -k "not live"
31 passed, 7 deselected

python -m pytest tests/unit/test_production_application.py \
  tests/unit/test_m12_revolute_drive_service.py -q
84 passed

python -m pytest tests/integration/test_m12_revolute_drive_production.py -q -k "not live"
19 passed

python -m pytest tests/unit/test_semantic_family_closure.py -q
132 passed
```

Counts are evidence only for the exact invocations that produced them.

## Recorded Documentation/Implementation Gap (non-blocking)

The accepted Plan states in several places that the final construction
entrypoint "requires inbound `candidate-synthesis-request@2`, rejects `@1`/mixed"
(T-P2.6 ~line 297/308; T-P8.4a ~lines 546/710). The implementation instead keeps
a schema-version-dispatched `@1` legacy branch on the same entrypoint.

Independent adjudication: the implementation is the **Spec-conformant** reading.
Spec §20 (controlling authority) states "Historical replay/verification
dispatches WHOLLY to legacy semantics via schema-version dispatch. Legacy
remains solely for historical read/verify + compatibility tests." The Plan's own
post-activation gate (line 547) also requires
`tests/integration/test_m12_candidate_cad_m10_production.py` and
`test_m12_promotion_production.py` to pass with "legacy paths unchanged", and
those tests construct `candidate-synthesis-request@1` (the model default) and
call this entrypoint; a strict "reject `@1` at method entry" implementation would
break the Plan's own gate. The Plan is therefore internally inconsistent
(line 547 vs lines 297/308/546/710), and the implementation follows the Spec.

Recorded as a documentation/implementation gap per `AGENTS.md`. It is
non-blocking: the production default for new-family callers is `@2`; the `@1`
branch is the historical-replay/compatibility dispatch path. No Spec or Plan
bytes were changed by this record.

## Boundary

This record does NOT claim:

```text
T-P8.3 live verification (separate H4 approval)
final implementation acceptance
commit / release / deployment
```

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_4A_ACTIVATION_INDEPENDENTLY_VERIFIED
