# Deterministic STEP Content Identity — Currentness Exact-Source Supplementation (production wiring)

## Change classification

```text
BEFORE: PARTIAL
  semantic-binding service supported exact artifact substitution but not accepted
  candidate-required supplementation.

AFTER (currentness semantic-binding path): EXISTS_PRODUCTION_VERIFIED
  (focused + owner-regression verified; the five live fixtures remain blocked by two
   separate, deeper fixture/contract issues — see below).
```

## Production change (minimal, existing owner)

`src/mechcad_harness/candidates/services.py` — extended the EXISTING semantic-binding
owner only; no new service/model/store/registry/context type.

- `_compute_semantic_binding(..., required_source_identities=None)`: preserves the
  consumed-authority pass EXACTLY, then adds an allowlisted supplementation pass. For
  each required identity whose semantic key is not already present, it locates the
  matching exact artifact (from `exact_source_artifacts` if provided, else the store),
  requires exact identity agreement (`artifact_id`, `artifact_hash`, `source_identity`,
  `format`, `coordinate_system_id`), enforces project/revision/state binding and
  byte verification, recomputes `step-content-identity@1`, and adds the binding. It
  never overrides an existing state-authority key.
- `compute_verified_semantic_binding(..., required_source_identities=None)`: forwards it.
- `verify_candidate_semantic_binding(...)`: derives the allowlist via the EXISTING
  `candidate_cad_required_raw_source_identities(candidate)` helper (no duplicated union
  logic) and forwards it.
- `CandidateCurrentnessService.evaluate(..., exact_source_artifacts=None)`: accepts and
  forwards it to `evaluate_source_binding` (the previously missing edge).

All new parameters default to `None`, so existing callers retain byte-for-byte behavior.
`semantic_source_binding_hash` is unaffected (it projects only consumed-authority
resolved values), so persisted request/candidate hash equality is preserved.

## Verification

Focused owner tests: `tests/unit/test_currentness_exact_source_supplementation.py`
(11 passed): state-only unchanged; supplemental added; mixed context; wrong exact
artifact fails; missing required fails; duplicate artifact_id fails; extra
undeclared artifact gains no authority; supplemental does not change source-binding
hash; candidate A artifact cannot satisfy B identity; same-key no override;
conflicting artifact_id/hash fails.

Owner regression: 106 passed
(`test_candidate_trusted_semantic_verification`, `test_candidate_cad_provenance_per_slot_v2`,
`test_candidate_decision_v2`, `test_semantic_source_binding`,
`test_candidate_synthesis_request_v2`, `test_candidate_cad_realization_v2`,
`test_candidate_cad_request_v3`, `test_currentness_exact_source_supplementation`).

## Five live fixtures — remaining blockers (beyond this authorization)

Fixture repairs applied (`tests/integration/test_m12_candidate_cad_m10_production.py`):
geometry identities + `ART-{slot}` publication; `_bind_candidate_template_specs`;
bound synthesis request in `_real_candidate`.

Two deeper issues remain:

1. **Gear STEP timestamp provider extension (2 tests:**
   `test_candidate_realization_rejects_unavailable_trusted_external_spur_artifact_without_downgrade`,
   `test_live_external_spur_preserves_unmodeled_internal_motion_boundary`**).** The
   build123d/Open CASCADE gear STEP has `FILE_NAME(...,'2000-01-01T00:00:00Z',...)`.
   Accepted Spec §21 (line 932) requires the timestamp grammar to be exactly
   `YYYY-MM-DDTHH:MM:SS` with "No timezone ... or provider extensions in @1. Any
   deviation fails closed." So `step-content-identity@1` correctly rejects the gear
   STEP; the gear artifact cannot be a semantic source artifact without normalizing the
   STEP (fixture/provider change) or changing the accepted contract (normative).
2. **Legacy CAD request for a `@2` candidate (3 tests:** `test_explicit_bounded_collision_fixture_is_candidate_bound_not_trusted_fallback`,
   `test_live_direct_drive_clear_collision_and_not_proven_chain`,
   `test_live_comparison_and_selection_are_deterministic_and_noncanonical`**).** These
   use the legacy `_cad_request` (`candidate-cad-realization-request@1`) and
   `_evaluate_real_candidate`; a `@2` candidate requires `candidate-cad-realization-request@3`
   (a `@3` builder exists at `_cad_m10_inputs_v2`, but the legacy helpers were not
   migrated).

Both are outside the authorized currentness semantic-binding wiring change.
