# Deterministic STEP Content Identity — Live-Fixture Binding Repair (supplemental)

## Status

```text
T-P8.3 live gate (test_step_content_identity_live.py): GREEN (6/6) — unchanged
'pending' specification_hash defect: FIXED via accepted binding helper
Currentness verification mismatch: UNRESOLVED — genuine production gap (see below)
```

## Fixture changes (tests/integration/test_m12_candidate_cad_m10_production.py)

1. `_build_gear_application` / `_build_live_application`: append the eight accepted
   geometry identities (`_geometry_identities`) and publish the `ART-{slot}` source
   artifacts (`_publish_source_artifacts`), mirroring `build_application`.
2. New `_bind_candidate_template_specs(application, candidate_template)`: binds every
   `specification_hash == "pending"` component specification through the accepted
   `bind_component_specification_semantic_identity`, using a context built from the
   published source artifacts' real bytes (`step_content_identity_v1`) resolved via
   `ArtifactStore.read_verified_in_project`. No hashes are hard-coded or manually
   computed.
3. `_real_candidate` calls `_bind_candidate_template_specs` after `_candidate_template`.

## Non-live verification (before live)

```text
pending hashes before binding: motor/shaft/bearing_a/hub = "pending"
after binding: all real sha256 hashes (bearing_a == bearing_b, both -> ART-bearing)
NON-LIVE BINDING VERIFICATION PASSED
```

## Live result after binding repair

```text
python -m pytest tests/integration/test_m12_candidate_cad_m10_production.py -v \
  -k "rejects_unavailable or explicit_bounded or live_direct_drive or live_external_spur or live_comparison"
5 failed in 184.48s
```

New failure (the `'pending'` error is gone):

```text
CandidateIntegrityError: verified semantic geometry binding is missing or mismatched
  at candidates/services.py:109 (verify_candidate_semantic_binding)
  -> semantic_component_specification_hash(specification, context)
```

## Classification

The candidate's component specifications are now correctly bound (through the accepted
helper) to the test's own published source artifacts. The CAD request references those
specs' geometry sources, so the candidate MUST be bound to the test's source artifacts
(trusted-source / bounded-collision semantics).

`CandidateCurrentnessService.evaluate` -> `evaluate_source_binding` ->
`verify_candidate_semantic_binding` builds its verification context via
`compute_verified_semantic_binding`, which is keyed by the state's geometry identities
(`ART-{slot}`). It does NOT pass `exact_source_artifacts`. Therefore a candidate bound
to specific source artifacts (not the state's `ART-{slot}` identities) cannot satisfy
`semantic_component_specification_hash(specification, context)`.

At HEAD, `evaluate_source_binding` only checked the source binding's consumed authority
and did NOT verify the candidate's component specifications against a context, so this
check did not exist. The check is part of the current working tree.

This is a PRODUCTION/VERIFICATION GAP, not a fixture defect: the fixture is correctly
bound through the accepted helper, but production rejects it. Per the fixture-repair
authorization (no production changes), this is STOPPED here for classification.

## Protected / accepted bytes

All six protected pins and all five accepted implementation bytes remain unchanged
(verified after the fixture repair).
