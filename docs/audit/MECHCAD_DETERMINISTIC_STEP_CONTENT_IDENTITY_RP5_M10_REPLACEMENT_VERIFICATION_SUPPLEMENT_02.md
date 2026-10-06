# R-P5.M10 Replacement Verification — Valid Pair-Set Probe

## Scope

This supplement adds a valid three-instance P5 exact-pair-scope probe after review of Supplement 01. It does not modify the Plan, Spec, production code, existing tests, primary report, prior acceptance, or reconstruction. It is verification evidence only, not independent acceptance.

- Accepted Plan SHA-256: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679`.
- Accepted Spec SHA-256: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68`.
- Primary report SHA-256: `2935D8FF95BF4E9EFFBECE09C4DD076AB37E30A18F0778E07C5F77F3ACE95A58`.
- Supplement 01 SHA-256: `0B1056AC7F014DE83574E34CA7C14496B6B883BDC01AE40FC2EAE433D694B63C`.
- Verification-test source SHA-256: `499DD924FC34D0C0D8E017125236777E47B65ED4A80BFD6B42DD109A6DEB833A`.
- Code HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.

## Typed Input and Assertions

The assembly starts with the existing `_assembly()` test fixture: one `link` base-plate part; instance `base` at identity; instance `moving` translated to x=20 mm. The probe adds a declared third instance, `other`, using the same registered `link` part at x=40 mm. Thus both exact-pair scopes refer only to declared instances in the same typed assembly; the assembly has a valid replay hash and all requests use that same assembly/model/configuration input.

- Scope A: `{base,moving}`.
- Scope B: `{base,moving}` plus `{base,other}`.
- Scope B reversed: the same two pair records in the opposite tuple order.

Expected/observed:

```text
P5(Scope A) != P5(Scope B): PASS (adding the declared pair changes semantic identity)
P5(Scope B) == P5(Scope B reversed): PASS (SET_SEMANTIC tuple reorder is invariant)
```

Exact verification command:

```powershell
@'
import sys
sys.path.insert(0, "tests/unit")
from test_m10_semantic_projections import _assembly, _v2_model, _v2_request
from mechcad_harness.cad_assembly import CadComponentInstance, CadRigidTransform
from mechcad_harness.multi_joint_collision_sweep import MultiJointCollisionSweepRequestV2
from mechcad_harness.multi_joint_pair_scope import ExactConstituentPair
from mechcad_harness.semantic_m10_kinematics import semantic_m10_v2_request_hash
base = _assembly()
three_instance_assembly = base.model_copy(update={"instances": base.instances + (CadComponentInstance(instance_id="other", part_id="link", placement=CadRigidTransform(x_mm=40.0)),)})
request = _v2_request(three_instance_assembly, model=_v2_model())
common = {"schema_version": request.schema_version, "source_assembly_id": request.source_assembly_id, "source_assembly_hash": request.source_assembly_hash, "model": request.model, "configurations": request.configurations, "volume_tolerance_mm3": request.volume_tolerance_mm3, "distance_tolerance_mm": request.distance_tolerance_mm, "evaluator_version": request.evaluator_version}
pair_a = ExactConstituentPair(first_instance_id="base", second_instance_id="moving")
pair_b = ExactConstituentPair(first_instance_id="base", second_instance_id="other")
one = MultiJointCollisionSweepRequestV2(**common, exact_pair_scope=(pair_a,))
two = MultiJointCollisionSweepRequestV2(**common, exact_pair_scope=(pair_a, pair_b))
two_reversed = MultiJointCollisionSweepRequestV2(**common, exact_pair_scope=(pair_b, pair_a))
one_hash = semantic_m10_v2_request_hash(one, three_instance_assembly, ())
two_hash = semantic_m10_v2_request_hash(two, three_instance_assembly, ())
assert one_hash != two_hash
assert two_hash == semantic_m10_v2_request_hash(two_reversed, three_instance_assembly, ())
print("valid three-instance P5 pair-set probes passed: membership changes identity; tuple reorder is invariant")
'@ | python -
```

Observed output:

```text
valid three-instance P5 pair-set probes passed: membership changes identity; tuple reorder is invariant
```

This valid-assembly probe supplements the lower-level scope-set sensitivity probe in Supplement 01; it changes no historical or protected artifact status. Historical pre-relocation vs post-relocation equality remains **NOT PROVEN**.
