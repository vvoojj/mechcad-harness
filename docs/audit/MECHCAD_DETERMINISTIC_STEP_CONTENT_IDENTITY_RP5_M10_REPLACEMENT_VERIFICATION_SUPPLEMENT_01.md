# R-P5.M10 Replacement Verification — Supplemental Field Probes

## Status and Authority

This is supplemental verification evidence for the independent auditor’s rejected review of the primary report. It addresses only the identified F1/F3/P5 sensitivity and rejection coverage gaps. It is not an acceptance record and does not modify or replace the primary report.

- Accepted Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Primary execution report SHA-256: `2935D8FF95BF4E9EFFBECE09C4DD076AB37E30A18F0778E07C5F77F3ACE95A58`.
- Verification-test source SHA-256: `499DD924FC34D0C0D8E017125236777E47B65ED4A80BFD6B42DD109A6DEB833A`.
- Code HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.

**NOT PROVEN:** historical pre-relocation vs post-relocation projection-output equality. The pre-relocation bodies/output snapshots were not preserved, and the original clause was not executed. Nothing in these supplemental probes changes that historical fact.

## Execution Method

Ran one read-only PowerShell here-string piped to `python -`. It imported the existing typed fixture helpers `_assembly`, `_v2_model`, `_v2_request`, `_v2_result` from `tests/unit/test_m10_semantic_projections.py`, constructed additional typed variants from accepted Spec fields, and directly asserted the applicable F1/F3/P5/P6 result. No production code, Plan, Spec, existing tests, existing verification report, prior acceptance, or reconstruction record was changed. No mock projection or fabricated history was used.

Command result:

```text
supplemental field probes passed: 35
```

All 35 individual assertions passed. Inputs and observed expected outcomes are enumerated below.

## F1 / F3 Supplemental Probes

Base F1 input: `_v2_model()` — `model-v2`, base-body/moving-body, identity reference-member transforms, one `joint` revolute joint around +Z. Base F3 input: `KinematicModel(model_id="single")` with one `joint` from `base` to `moving`, default +Z axis and no limits.

| # | Probe input relative to base | Expected / observed outcome |
|---:|---|---|
| 1 | F1 base body ID changed to `base-body-new`, with the joint parent changed to the matching new body ID | Output differs; PASS |
| 2 | Add a member with ID `base-alt` and identity home transform to the base body | Output differs; PASS |
| 3 | Add the non-reference member `offset` at x=1 mm versus x=2 mm, keeping the rest fixed | Output differs; PASS |
| 4 | Change the F1 revolute-joint minimum angle to −30° | Output differs; PASS |
| 5 | Reverse F1 body input tuple order | Output is invariant after canonical ordering; PASS |
| 6 | Compare F1 models containing the same `joint`/`joint-b` set in opposite tuple order | Output is invariant after joint-ID ordering; PASS |
| 7 | Construct a rigid body with duplicate `base` member IDs | Model construction rejects; PASS |
| 8 | Construct a V2 model with duplicate `joint` IDs | Model construction rejects; PASS |
| 9 | Add `unclassified_field` to the nested V2 rigid body | Model validation rejects; PASS |
| 10 | Add `unclassified_field` to the F3 single-joint model | Model validation rejects; PASS |

These probes complement the primary test’s F1 axis sensitivity, evaluator exclusion, body/member reordering, F3 evaluator exclusion, joint reordering, and axis sensitivity.

## P5 — All 11 Declared Request Fields

Base P5 input: `_v2_request(_assembly())`; model `model-v2`; two ordered configurations (`joint=0°`, `joint=45°`); exact pair `{base,moving}`; default tolerances `1e-9 mm³` and `1e-7 mm`; matching assembly ID/raw assembly hash.

| Declared field | Probe input | Expected / observed outcome |
|---|---|---|
| `schema_version` | Substitute `multi-joint-collision-sweep-request@1` | Reject as unsupported request contract; PASS |
| `source_assembly_id` | Change only to `wrong` | Reject replay/context mismatch; PASS |
| `source_assembly_id` + `source_assembly_hash` | Rename the matching assembly and rebuild the request against it | Same semantic P5 identity; PASS in primary H/F1 vector suite |
| `source_assembly_hash` | Substitute `sha256:` + 64 `c` characters without changing assembly | Reject raw replay binding; PASS |
| `model` | Change the V2 joint axis direction to `(1,0,0)` | Output differs through F1; PASS |
| `configurations` values | Change the first commanded joint position from 0° to 1° | Output differs; PASS |
| `configurations` ordering | Reverse the 0°/45° tuple | Output differs; PASS |
| `exact_pair_scope` membership | Compare `{base,moving}` against `{base,moving}` plus `{base,other}` | Output differs; PASS |
| `exact_pair_scope` ordering | Reverse those two exact-pair entries | Same output after set canonicalization; PASS |
| `exact_pair_scope` duplicate | Supply `{base,moving}` twice | Reject duplicate pair; PASS |
| `volume_tolerance_mm3` | Change `1e-9` to `2e-9` | Output differs; PASS |
| `distance_tolerance_mm` | Change `1e-7` to `2e-7` | Output differs; PASS |
| `evaluator_version` | Change only to `other-executor` at the semantic projection boundary | Output invariant; PASS (execution pin remains a separate validation responsibility) |
| `model_hash` | Change only the legacy model hash to `sha256:` + 64 `a` characters | Output invariant; PASS |
| `request_hash` | Change only the legacy request hash to `sha256:` + 64 `b` characters | Output invariant; PASS |

The table has 15 rows because source-ID/source-hash behavior is checked both independently (rejection) and as a valid paired raw identity rotation (invariance). It accounts for all 11 declared request fields, including multi-case behavior for the raw binding pair and the two tolerances.

## P6 Additional Field-Probe Coverage

Base P6 input: `_v2_result(_v2_request(_assembly()))` from the existing typed test fixture. Each top-level change is applied alone unless described as a replay-paired raw identity change.

| Probe input | Expected / observed outcome |
|---|---|
| Set `any_interference=True` | Output differs; PASS |
| Set `any_touching=True` | Output differs; PASS |
| Set `all_positive_clearance=False` | Output differs; PASS |
| Set `collision_configuration_indices=(0,)` | Output differs; PASS |
| Change `minimum_exact_distance_mm` from 3.0 to 4.0 | Output differs; PASS |
| Change `minimum_distance_configuration_index` from 0 to 1 | Output differs; PASS |
| Change nested pair `exact_distance_mm` from 3.0 to 4.0 | Output differs; PASS |
| Change nested moving world transform x from 20 mm to 21 mm | Output differs; PASS |
| Change `model_hash` and `request_hash` to the same new `sha256:` + 64 `d` characters in request and result | Output invariant after replay-link equality; PASS |
| Change only result `result_hash` to `sha256:` + 64 `e` characters | Output invariant; PASS |
| Change only evaluator version to `other-executor` at the semantic projection boundary | Output invariant; PASS |

The primary verification gate additionally tested configuration order sensitivity, assembly-name/raw-identity paired invariance, transformed-assembly-hash exclusion, invalid continuous-path claim, result cardinality mismatch, raw source-hash replay rejection, and V1/V2 type rejection.

## Final Separation

- **NOT PROVEN:** historical pre-relocation vs post-relocation output equality.
- **PROVEN INSTEAD:** the current relocated functions pass the independently Spec-derived vectors, accepted field classifications, primary and supplemental sensitivity/invariance/rejection probes, full focused gate, and downstream P5/P6 consistency runs; protected source/golden pins remain exact.
- Independent evidence audit: still required. `R-P5.5` remains blocked until a separate auditor accepts the primary report plus this supplement.
