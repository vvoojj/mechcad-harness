# F8 Proof Vocabulary and Motion-Bound Authority Design

**Date:** 2026-09-13

## Status

Design and implementation planning only. This document authorizes no production
or test change. F3 surfaces are out of scope. No reconstruction record may be
modified.

## Current Defect

The duplication audit records F8 as a P2 duplication between the M10-1
single-axis and M10-4 multi-joint continuous-proof engines. The apparent shared
surfaces are proof outcome vocabulary and the rigid-rotation chord term.

Current source inspection refines that finding. The three status *strings* are
equivalent, but the two `StrEnum` classes have distinct Python identities. More
importantly, the motion-bound implementations are not fully equivalent: their
numerical padding differs. F8 therefore cannot be treated as one directly
extractable semantic primitive.

## Historical Intent

M10 (`89b1d75`) introduced both engines in one bundled motion commit. M10-1
specified a chord-bound proof for one revolute axis. M10-4 specified a
hierarchical proof that sums one chord contribution for every influencing joint
and both pair endpoints. M13-3P later added M10 v2 while preserving literal M10
v1 JSON, hashes, FK behavior, collision behavior, and clearance mathematics.

The M13-3P accepted completion record and reconstruction state that v1 proof
mathematics remains unchanged. This is a compatibility constraint, not evidence
that the two engines must use one implementation.

## Exact Surfaces

| Surface | File/symbol | Consumers | Persisted/wire? | Hash-sensitive? | Source-byte frozen? |
| --- | --- | --- | --- | --- | --- |
| Single-axis status | `continuous_proof.py:ContinuousSingleAxisProofStatus` | M10-1 result model; candidate evaluation and validation; canonical M10; `ProductionApplication`; unit/integration tests | Yes, `status` serializes as a string in result payloads | Yes, result hash includes serialized status | No identified file-level golden |
| Single-axis bound | `continuous_proof.py:motion_bound` | `ContinuousSingleAxisClearanceProof._prove_interval`; direct M10-1 tests | Indirectly through certificate values and result JSON | Yes, certificate values contribute to result hash | No identified file-level golden |
| Multi-joint status | `multi_joint_continuous_clearance.py:MultiJointContinuousProofStatus` | v1/v2 multi-joint result models, validators, service, `ProductionApplication`, live/unit tests, project runner | Yes, v1/v2 `status` strings are serialized in result/Evidence payloads | Yes, result hash includes serialized status | Yes, entire file SHA-256 is locked |
| Multi-joint bound | `multi_joint_continuous_clearance.py:MultiJointContinuousClearanceProofService.execute` lines 459-469 | v1/v2 certificate construction; M10-4 result/Evidence paths | Indirectly through bound/certificate values | Yes, v1/v2 result hashes include certificates | Yes, entire file SHA-256 is locked |

`test_m13_3_legacy_goldens.py` locks the complete bytes of
`multi_joint_continuous_clearance.py` to
`sha256:66a62f30a7fe96c40f6cb049bf96906a427931b276ce9847dad42e6f95ad2bc5`.
`test_m13_3p_legacy_goldens.py` separately locks v1 M10-4 request/result JSON,
record digests, and final result hashes produced through that module.

## Status-Vocabulary Comparison

Both classes define exactly:

```text
VERIFIED_CLEAR     -> "verified_clear"
COLLISION_WITNESS  -> "collision_witness"
NOT_PROVEN         -> "not_proven"
```

Both are `StrEnum` classes. Their values compare equal because they are strings,
but they are not the same member or the same class:

```text
ContinuousSingleAxisProofStatus.VERIFIED_CLEAR ==
MultiJointContinuousProofStatus.VERIFIED_CLEAR     # True

ContinuousSingleAxisProofStatus.VERIFIED_CLEAR is
MultiJointContinuousProofStatus.VERIFIED_CLEAR     # False
```

Type identity matters within each engine: result validators and services use
`is` against their own class members. No current source consumer was found using
`isinstance` or `type(...)` across the two classes, and no cross-engine value is
passed as the other enum type. Replacing either public class with the other
would nonetheless change the public import/type contract and may invalidate
downstream identity checks. The multi-joint class is explicitly exported in its
module `__all__`; the single-axis class is publicly importable from its module
and is imported by production candidate code.

## Motion-Bound Semantic Comparison

The single-axis primitive is:

```text
C_single(R, delta) = 2 * R * sin(min(abs(delta), pi) / 2)
                   + 1e-9 * (1 + abs(R))
```

It rejects `R < 0`; it does not independently reject non-finite values. `delta`
is in radians, is absolute-value clamped to `pi`, and a negative delta therefore
has the same output as its positive counterpart. The result is millimetres.

The multi-joint loop calculates, once for each available reach-bound record:

```text
C_multi(R, delta) = 2 * R * sin(min(delta, pi) / 2) + 1e-9
B_endpoint = sum(C_multi(R(i,j), delta_j))
B_pair = B_A + B_B
```

Here `delta` is built as `radians(abs(endpoint_angle_difference) * half_span)`,
so it is non-negative before the inline `min`. The caller obtains non-negative
reach bounds from `derive_reach_bounds`; the inline expression has no standalone
validation. It also produces millimetres.

Both use the same chord term, clamp large excursions at `pi`, and are
conservative. They diverge for every non-zero `R` because the single-axis pad
scales with reach while the multi-joint pad is constant per joint contribution.
The multi-joint total also accumulates that constant for every influencing
joint. It is therefore not valid to replace the inline expression with
`motion_bound` while preserving result bytes.

Characterization from the baseline for `R = 100.0` mm:

| Delta (rad) | `C_single` | One `C_multi` contribution |
| --- | ---: | ---: |
| `0` | `1.01e-07` | `1e-09` |
| `0.01` | `0.9999959343385416` | `0.9999958343385416` |
| `pi/2` | `141.42135633830952` | `141.4213562383095` |
| `pi` | `200.000000101` | `200.000000001` |
| `2*pi` | `200.000000101` | `200.000000001` |

For `R = 0`, both shown formulas produce `1e-09`. The distinct floating-point
operation order and pad accumulation remain part of the current observable
certificate/result values.

## M13-3P Source-Freeze Findings

1. `multi_joint_continuous_clearance.py` is source-byte frozen by the current
   `test_m13_3_legacy_goldens.py` whole-file SHA-256 assertion.
2. The freeze is the entire file, not selected symbols or behavior.
3. Importing a shared status type or helper changes the file hash.
4. Replacing the inline formula changes the file hash and, if the single-axis
   helper is used, changes numerical outputs.
5. No external persistent source-hash registry was identified. The hash locks
   are accepted compatibility tests, supplemented by accepted M13-3P prose and
   v1 JSON/hash goldens.
6. M13-3P expressly requires v1 wire formats, hashes, FK behavior, collision
   classification, and clearance mathematics to remain unchanged.
7. No accepted extension mechanism permits changing the frozen v1 file text.
   V2 is additive inside the same frozen file, not a carve-out from the hash.
8. Making single-axis depend on the multi-joint implementation would invert the
   useful proof-layer dependency direction, import an unrelated larger engine,
   preserve neither distinct padding semantics nor a neutral authority, and
   still does not remove the frozen implementation.
9. A neutral core can be added only for new/non-frozen callers while leaving the
   frozen module text untouched. It cannot make both existing implementations
   delegate to one primitive.
10. The frozen multi-joint path must retain its local implementation unless an
    explicit compatibility decision authorizes a new baseline and the accepted
    freeze contract is superseded through the appropriate governance process.

## Options Considered

| Option | Assessment |
| --- | --- |
| A. Neutral shared proof core used by both engines | Rejected. It modifies the whole-file-frozen module. A helper matching single-axis padding changes multi-joint numbers; one matching multi-joint padding changes single-axis numbers. |
| B. Neutral core for new/non-frozen consumers; frozen multi-joint compatibility shell remains | Technically compatible if no frozen file is changed. It cannot consolidate either existing F8 surface and should not be created without a concrete new consumer. |
| C. Treat frozen multi-joint code as authority and delegate single-axis toward it | Rejected. The formula is not equivalent, a large multi-joint module is not a neutral low-level dependency, and the resulting single-axis numeric change violates existing semantics. |
| D. No production consolidation; classify the frozen status duplication as intentional compatibility duplication and recognize the bound formulas as distinct | Recommended. It preserves every protected contract and prevents false claims of equivalent math. Future work may add characterization and explicit public-type/serialization tests without changing production authority. |

## Recommended Authority Design

Retain both existing public status classes and both existing bound
implementations. The single-axis class and scaled-padding primitive remain the
M10-1 authority. The frozen multi-joint class and per-contribution fixed-padding
expression remain the M10-4 v1/v2 compatibility authority.

The audit should not be updated until a user-approved remediation concludes.
If approval is limited to documentation/testing, reclassify F8 precisely:

- the status values are duplicated but intentionally separately typed public
  compatibility vocabularies;
- the motion calculations share a chord subexpression but are not equivalent
  semantic primitives because padding and aggregation differ.

No shared core is justified until a new unfrozen consumer has an independently
specified padding/aggregation contract. Such a future core must not become a
pretext to modify the frozen legacy module.

## Compatibility Constraints and Impact

- Preserve M13-3P whole-file source bytes and both v1/v2 result behavior.
- Preserve all existing status strings, model JSON, request/result hashes,
  evidence payloads, version boundaries, and conservative padding.
- Preserve status enum public imports and class identity within each engine.
- Do not regenerate, weaken, or update legacy goldens to enable refactoring.
- Do not touch F3, F1, F4, F5, F6, F7, F11, or `docs/reconstruction/**`.

The recommended no-production-change direction has no public, wire, or hash
impact. Any attempt at Option A or C has public type, source-hash, numerical,
certificate, result-hash, and potentially Evidence impact.

## Verification Strategy

Before any approved work, add characterization tests from untouched baseline
behavior for both formula families, including zero, small, `pi/2`, `pi`, and
greater-than-`pi` deltas; zero and representative positive reach; negative
single-axis reach rejection; and multi-joint per-joint pad accumulation.

Retain and run both legacy suites:

```text
py -3 -m pytest tests/unit/test_m13_3_legacy_goldens.py -v
py -3 -m pytest tests/unit/test_m13_3p_legacy_goldens.py -v
```

Add status serialization tests that prove both result families retain the three
exact strings, parse their own serialized payloads, and retain their separate
Python type identities. Repository searches must demonstrate that no new shared
authority is presented as serving the frozen source and that the only remaining
formula copies are the intentionally distinct M10-1 and frozen M10-4 forms.

## Explicit Non-Goals

- No production refactor, helper, import change, or test-golden update in this
  planning task.
- No change to M10 proof conservatism, M13-3P v1/v2 behavior, or evidence
  schemas/hashes.
- No generic trajectory or configuration-space certification.
- No F3 remediation or P3 finding work.
- No update to audit/map records before an approved remediation result.

## Acceptance Criteria

1. A reviewer can reproduce that the M13-3 legacy test hashes the entire
   multi-joint module.
2. A reviewer can reproduce the unequal padding outputs using the listed
   characterization cases.
3. The design distinguishes string equality from enum type identity.
4. The design states that full consolidation is unsafe and not currently
   possible under the accepted freeze and semantic constraints.
5. Any future execution plan blocks before changing the frozen source or
   redefining either padding contract.
