# Deterministic STEP Content Identity - T-P8.1 Coverage Closure Independent Acceptance

## Verdict

```text
Epic:
Deterministic STEP Content Identity

Gate:
T-P8.1 focused unit + field-set equality + hash pins + invariance +
mixed-version + restart coverage

Controlling Spec:
docs/superpowers/specs/2026-09-19-deterministic-step-content-identity.md
SHA-256: DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68
(UNCHANGED by this gate)

Controlling Plan:
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md
SHA-256: E449C60B641DBB5A4A630CC61553F5E586127443DC92B24BD5D983E3A15BB70E
(UNCHANGED by this gate)

Observed HEAD:
05da8edad18488492f02be1dad9d1ec3653ce807

Disposition:
INDEPENDENTLY_ACCEPTED (coverage closure only)

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_1_COVERAGE_CLOSED_GREEN
```

This disposition applies ONLY to the exact Spec and Plan bytes whose SHA-256
values are stated above, at the observed HEAD, with the remediation set
described below. It is a **coverage-closure** acceptance only. It does not
accept or authorize production activation, default-family activation, live
runtime verification, commit, release, or deployment.

## Materialization Boundary

This record materializes a fresh independent read-only re-audit result for the
exact byte state above. It does not edit the Spec, the Plan, production
semantics, architecture, reference material, reconstruction/history, or any
pre-existing audit record. The only intentional mutation associated with this
gate closure is this new audit record plus the remediation set listed below.

## B1 - Spec Ambiguity Resolution (no Spec revision)

B1 was the Case 92 ambiguity over the scope of the phrase "promotion@2 semantic
hashes". Two readings were considered:

```text
Option A: REQUEST_ONLY
Option B: FULL_APPLICABLE_PROMOTION_FAMILY
```

Independent analysis and a separate independent acceptance audit resolved B1 as
**Option B (FULL_APPLICABLE_PROMOTION_FAMILY)** with **no Spec revision
required**. The Spec already resolves the ambiguity when Case 92 is read in
context with §17 (complete promotion-family enumeration), §21 (exhaustive
timestamp-invariance list, including the full promotion@2 family), Case 89
(parallel multi-joint usage), and Case 93 (explicit "complete promotion@2
readiness/compilation/decision" chain). No new platform semantic identity was
introduced. The Spec SHA is therefore unchanged.

Structural basis: the shared `semantic_candidate_realization_payload` preserves
`candidate_hash@2`; all promotion@2 hashes are downstream of `candidate_hash@2`
and the other preserved @2 identities; no promotion@2 hash directly consumes the
realization object. Preserving `candidate_hash@2` therefore necessarily
preserves the applicable promotion@2 family.

## Remediation Set

The following test-only changes and one minimal production check closed the
coverage gaps B2-B8. All changes are inside this Epic.

### Production (minimal, Spec-required)

`src/mechcad_harness/candidates/promotion.py`:

```text
CandidatePromotionCompilerV2.validate_readiness_v2
CandidatePromotionCompilerV2.validate_multi_joint_readiness_v2
```

Both now enforce the accepted Spec §6C / §23 Case 93 rule that non-empty
`unresolved_items` blocks promotion admission in both orderings, matching the
pre-existing legacy `CandidatePromotionCompiler._verify_candidate` check. No
new model, service, registry, persistence mechanism, schema version, or
semantic contract was added. Legacy behavior is unchanged.

### Tests (new / strengthened)

```text
tests/unit/test_step_content_identity_restart_fresh_process.py   (NEW, B2)
tests/unit/test_candidate_production_admission_matrix.py         (NEW, B3)
tests/unit/test_candidate_decision_v2.py                         (B4/B6 additions)
tests/unit/test_promotion_v2.py                                  (B4/B8 rewrites + V2 gate)
tests/unit/test_semantic_family_closure.py                       (B5 rewrite + aggregate fixes)
```

## Blocker Disposition

```text
B1  SPEC_AMBIGUITY      RESOLVED (Option B, no Spec revision)
B2  TEST_COVERAGE_GAP   CLOSED - genuine fresh-process child-interpreter restart
B3  TEST_COVERAGE_GAP   CLOSED - literal 9-row T-P2.6 production route matrix
B4  TEST_COVERAGE_GAP   CLOSED - Case 93 unresolved-items multiset + V2 gate
B5  TEST_COVERAGE_GAP   CLOSED - genuine mechanical closure (cases 40/43/46/67)
B6  TEST_COVERAGE_GAP   CLOSED - Case 90 connection/joint reversal propagation
B7  TEST_COVERAGE_GAP   CLOSED - Case 26 N1/N2 self-hash exclusion
B8  TEST_COVERAGE_GAP   CLOSED - Case 89/92 applicable promotion@2 family
```

### B2 - Genuine fresh-process restart

`tests/unit/test_step_content_identity_restart_fresh_process.py` spawns a real
separate Python interpreter via `subprocess` + `sys.executable -c`. The parent
persists durable artifacts through production publication services and passes
only a durable JSON locator (workspace path, project id, artifact ids/hashes).
The child re-imports production fresh, reconstructs its own
`StateManager`/`ArtifactStore`/services, resolves the persisted artifacts, and
recomputes raw SHA, `step-content-identity@1`, `semantic_source_binding_hash`,
`candidate_hash_v2`, and the P5/P6 semantic identities. Zero-execution spies are
installed inside the child and a negative same-length raw-byte tamper case fails
closed. No production object crosses the process boundary.

### B3 - Literal T-P2.6 production route matrix

`tests/unit/test_candidate_production_admission_matrix.py` transcribes the
accepted Plan's 9-row T-P2.6 `ProductionApplication` candidate-admission table
literally and calls the real production routes (not signature-only). The
observed pre-activation split (rows 4-7 positive; rows 1-3 and 8-9 reject-only
before legacy construction) is pinned and documented in-test.

### B5 - Genuine mechanical closure

`tests/unit/test_semantic_family_closure.py` now captures REAL production hash
payloads (via a `hashlib` recorder that records the exact bytes fed to
`sha256`, keyed by digest) and applies the forbidden-terminal check to the
PAYLOAD (not to bare hash strings). The registry is cross-checked
bidirectionally (missing production edge and extra invented edge both fail),
and raw/legacy terminal VALUES are excluded via a record-derived raw-terminal
set. Cases 40, 43 (single AND multi), 46 (real scope payload), and 67 (maximal
causal chain plus real canonical/promotion/M11 suffix records) are covered. The
previously vacuous aggregate tests were strengthened with real assertions. An
independent in-memory sensitivity probe confirmed detection of injected
forbidden keys, removed dependencies, invented dependencies, injected raw
terminal values, and missing payloads.

## Independent Verification Evidence

Fresh independent re-audit results (exact invocations):

```text
python -m pytest tests/unit/test_semantic_family_closure.py -q
132 passed

python -m pytest tests/unit/test_step_content_identity_restart_fresh_process.py \
  tests/unit/test_candidate_production_admission_matrix.py \
  tests/unit/test_promotion_v2.py tests/unit/test_candidate_decision_v2.py -q
41 passed

python -m pytest tests/unit/test_candidate_m10_v2.py \
  tests/unit/test_candidate_multijoint_m10_v2.py \
  tests/unit/test_canonical_m10_v2.py tests/unit/test_m11_handoff_v2.py -q
49 passed

python -m pytest tests/unit/test_m13_3_legacy_goldens.py \
  tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py \
  tests/unit/test_m12_promoted_verification.py \
  tests/unit/test_production_application.py -q
150 passed
```

A passing test count is evidence only for the exact invocation that produced it.

Static checks:

```text
python -m compileall -q src/mechcad_harness tests/unit   -> clean (exit 0)
git diff --check -- src/mechcad_harness/candidates/promotion.py -> clean
```

## Protected Surfaces

```text
src/mechcad_harness/multi_joint_kinematics.py
  514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f  (UNCHANGED)

src/mechcad_harness/multi_joint_collision_sweep.py
  56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f  (UNCHANGED)

tests/unit/test_m13_3_legacy_goldens.py
  unchanged from HEAD
```

## Documented Non-Blocking Limitations

These are recorded as known limitations, not as open coverage defects:

1. **B3 route staging**: on the current worktree, `realize_and_evaluate_revolute_drive`,
   `realize_candidate_cad`, `evaluate_candidate`, `compile_candidate_promotion`,
   and `promote_selected_*` remain reject-only before legacy construction. This
   matches the Plan's reserved pre-activation boundary for their owner phases;
   their positive admission belongs to the P3/P5/P7 owner tasks and the
   T-P8.4a activation gate.
2. **B8 promotion@2 family breadth**: `candidate-promotion-compilation@2`,
   `promotable-mechanism-projection@2`, decision manifests, result manifests,
   and `promoted-mechanism-verification-result@2` are model definitions with no
   production constructor and no candidate-to-`canonical-physical-mechanism@4`
   bridge in the accepted implementation; they are not causally constructible in
   the focused fixture chain. Case 89/92 promotion@2 coverage therefore asserts
   the constructible applicable members (policy/request/readiness/decision-input)
   and documents the rest. This is consistent with the accepted Spec reading and
   with T-P7.2 remaining unactivated.
3. **`application.py` candidate@2 single-joint source-binding comparison**: the
   application-level M12-3 gate compares against the legacy raw binding hash,
   which is a latent T-P8.4a activation concern. It is fail-closed and
   non-blocking for this pre-activation coverage gate.
4. **Residual well-formedness-only stubs**: a small number of legacy
   well-formedness assertions remain redundant with the substantive B5 closure
   registry and the B2 fresh-process proof; they are test-hygiene debt, not
   coverage holes.

## Scope Boundary

This record does NOT claim:

```text
production activation
default-family activation (T-P8.4a)
live FreeCAD / Gmsh / CalculiX / MINI verification (T-P8.3)
P8.2 broad regression
final implementation acceptance
commit / release / deployment
```

Production default remains LEGACY. T-P8.4a activation and T-P8.3 live
verification remain unauthorized and not performed.

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_TP8_1_COVERAGE_CLOSED_GREEN
