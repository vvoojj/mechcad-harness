# M13-3 Generic Multi-Joint Candidate/Canonical M10 Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source-bound generic physical rigid-body, revolute-joint, root, and complete physical-pair-policy authority; lower it deterministically to existing M10 v2; and rebuild the same analysis freshly from canonical state after promotion.

**Architecture:** M13-3 is additive above the accepted M13-3P/M10 v2 boundary. Physical authority is persisted in explicit `PhysicalMechanismRealization@2` and `CanonicalPhysicalMechanism@3` branches; a shared pure compiler derives the M10 v2 model, exhaustive concrete inventory, and `ExactConstituentPair` scope. Candidate analysis and selection bind the exact derived chain; promotion projects only physical facts and pair-policy rederivation inputs, then canonical analysis creates new CAD, inventory, bridge, and M10 request without candidate objects.

**Tech Stack:** Python 3.11+, Pydantic v2, SHA-256 canonical JSON, existing `CadRigidTransform`/quaternion helpers, existing M13-1/M13-2 authority APIs, M13-3P M10 v2, pytest, and the existing FreeCAD production composition.

## Global Constraints

- Implement the final specification marker `M13_3_GENERIC_MULTI_JOINT_CANDIDATE_CANONICAL_M10_BRIDGE_SPEC_FINAL`, not drafts.
- Do not change generic M10 semantics, M11, M13-4, Rotator V2, CAD inference, or dependencies.
- Preserve literal `@1` serializers/hashes for `PhysicalMechanismRealization`, `CanonicalPhysicalMechanism`, `JointConfiguration`, `CanonicalM10VerificationObligation`, M12 candidate M10 records, M12 selection/promotion records, and M10 v1/v2 records.
- Use explicit schema branches; never retrofit historical wire records with optional fields plus `exclude_none`.
- `accepted-semantic-home@1` is the sole M13-3 zero-reference semantic.
- M10 bodies, joints, offsets, inventory, exact scope, requests, results, and bridges are derived and never promoted.
- Do not commit, tag, push, or release.

## File Map

- Modify `src/mechcad_harness/candidates/models.py`: candidate physical `@2` primitives and realization serializer/hash branch.
- Modify `src/mechcad_harness/models/physical_mechanism.py`: canonical projected primitives and mechanism `@3` serializer/hash branch.
- Create `src/mechcad_harness/models/physical_pair_policy.py`: neutral five-value enum, reason/pair canonicalization, and set hash helpers.
- Create `src/mechcad_harness/models/multi_joint_verification.py`: neutral replayable `MultiJointVerificationConfigurationSet@1` used by candidate scope and canonical obligation without a `models -> candidates` import.
- Create `src/mechcad_harness/candidates/multi_joint_m10_bridge.py`: shared semantic resolvers, validations, lowering, derived inventory/scope, bridge output, and equivalence comparator.
- Create `src/mechcad_harness/candidates/multi_joint_m10_evaluation.py`: additive replayable configuration-set owner, v2 scope/request/evaluation, shared configuration validator, and strict request reconstruction/execution.
- Create `src/mechcad_harness/candidates/multi_joint_selection.py`: additive bridge-bound selection.
- Modify `src/mechcad_harness/candidates/promotion_models.py` and `src/mechcad_harness/candidates/promotion.py`: additive multi-joint promotion request/readiness/compiler path and canonical physical projection.
- Modify `src/mechcad_harness/candidates/canonical_mechanism.py`, `candidates/canonical_cad.py`, and `application.py`: canonical reconstruction validation and narrow M13 service composition only.
- Modify `src/mechcad_harness/candidates/__init__.py` and `src/mechcad_harness/models/__init__.py` only for required exports.
- Create focused M13-3 unit/integration tests listed below; retain all existing M12/M13/M10 tests unchanged.

## Frozen Data Decisions

### Physical Body / Root Models

`PhysicalRigidBodyBinding` is frozen with `schema_version="physical-rigid-body-binding@1"`, `physical_body_id`, canonical `member_physical_instance_ids`, `reference_physical_instance_id`, and `binding_hash`. `CanonicalPhysicalRigidBodyBinding` is identical except `schema_version="canonical-physical-rigid-body-binding@1"` and canonical physical IDs. Both validate nonblank IDs, nonempty unique member IDs, lexical member ordering, and reference membership. Their hash payload is exactly `{schema_version, physical_body_id, member_physical_instance_ids, reference_physical_instance_id}`. They contain no CAD, transforms, M10 records, offsets, inventory, or bridge identity.

`physical_kinematic_root_hash(root)` hashes exactly `{"schema_version":"physical-kinematic-root@1","kinematic_root_physical_body_id":root}` using canonical JSON. `PhysicalMechanismRealization@2` and `CanonicalPhysicalMechanism@3` persist the ID plus the matching `kinematic_root_binding_hash`; they never derive it from M10/CAD.

### Physical Revolute Joint / Axis Models

Use `PhysicalAxisOwnerEndpoint(StrEnum)` with exactly `PARENT` and `CHILD`; `PhysicalJointMotionMode(StrEnum)` with exactly `BOUNDED` and `CONTINUOUS`. Add four discriminated source records, each with `schema_version`, `source_kind`, `source_physical_instance_id`, source ID, source self-hash, geometry/specification binding hash, and `source_hash`:

- `SuppliedRotationalInterfaceAxisSource@1`: `interface_id`, `interface_hash`, `geometry_reference_hash`, `specification_hash`.
- `SuppliedReferenceFrameAxisSource@1`: `frame_id`, `frame_hash`, `geometry_reference_hash`, `specification_hash`.
- `GeneratedRotationalInterfaceAxisSource@1`: `interface_id`, `interface_hash`, `generated_specification_hash`.
- `GeneratedReferenceFrameAxisSource@1`: `frame_id`, `frame_hash`, `generated_specification_hash`.

The union discriminator is `source_kind` with exact wire values `supplied_rotational_interface`, `supplied_reference_frame`, `generated_rotational_interface`, and `generated_reference_frame`. Each `source_hash` hashes its entire serialized variant excluding `source_hash`; no axis coordinates are duplicated.

`PhysicalRevoluteJointBinding` has four discriminated candidate axis-source variants listed above. `CanonicalPhysicalRevoluteJointBinding` has corresponding distinct `CanonicalSuppliedRotationalInterfaceAxisSource@1`, `CanonicalSuppliedReferenceFrameAxisSource@1`, `CanonicalGeneratedRotationalInterfaceAxisSource@1`, and `CanonicalGeneratedReferenceFrameAxisSource@1` variants. It projects every physical-instance-bearing field through `CandidateCanonicalInstanceMapping`: parent endpoint, child endpoint, and `axis_source.source_physical_instance_id`. Each canonical source preserves `source_kind`, applies the M13-1/M13-2 projected interface/frame identity rules, rebinds the accepted authoritative source-hash meaning, substitutes the canonical physical instance ID, and computes `source_hash` from its entire canonical serialized source payload. The canonical joint recomputes `binding_hash`; it never copies candidate source/binding hashes. Both joint records otherwise have exactly `physical_joint_id`, parent/child physical body IDs, `connection_id`, parent/child physical instance and interface IDs, `axis_source`, `axis_owner_endpoint`, `axis_sign`, `motion_mode`, `min_angle_deg`, `max_angle_deg`, `zero_reference_semantics`, and `binding_hash`. Hash payload is all preceding semantic fields including serialized source, owner/sign, mode/limits, and literal zero semantic; it excludes CAD, M10 axis/rest data, transforms, bridge, inventory, and results. `axis_sign` is `+1|-1`; zero is exactly `accepted-semantic-home@1`; bounded requires two finite ordered limits; continuous requires both `None`.

### Physical Pair Policy Models

`PhysicalPairClassificationBinding@1` and `CanonicalPhysicalPairClassificationBinding@1` have exact fields `schema_version`, lexical `first_physical_instance_id`, lexical `second_physical_instance_id`, `classification`, `exclusion_reason`, and `binding_hash`. Their hashes contain exactly those first five fields. `CHECK_CLEARANCE` requires `exclusion_reason is None`; every other class requires nonblank reason. `physical_pair_classification_set_hash(bindings)` hashes `{"schema_version":"physical-pair-classification-set@1","binding_hashes":[...sorted...]}` only.

### Enum / Dependency Ownership

Create neutral `models/physical_pair_policy.py` with `PhysicalPairClassification`; make `CandidateM10PairClassification = PhysicalPairClassification` in `candidates/m10_evaluation.py` and preserve its public import/export. The exact old values remain `check_clearance`, `intended_contact_excluded`, `same_rigid_group_excluded`, `unmodeled_motion_out_of_scope`, and `other_explicit_out_of_scope`. Canonical physical modules import only the neutral enum. This avoids a canonical-to-candidates dependency and duplicate meanings; an import-cycle test is mandatory.

### Schema Versioning

`PhysicalMechanismRealization` permits only `physical-mechanism-realization@1|@2`; `@1` serializer/hash payload stays byte-for-byte current and rejects every M13-3 field. `@2` contains current fields plus `physical_rigid_body_bindings` sorted by `physical_body_id`, `physical_revolute_joint_bindings` sorted by `physical_joint_id`, `kinematic_root_physical_body_id`, `kinematic_root_binding_hash`, and `physical_pair_classification_bindings` sorted lexically by `(first_physical_instance_id, second_physical_instance_id)`; its hash is its explicit serializer payload excluding `realization_hash`.

`CanonicalPhysicalMechanism` permits only `canonical-physical-mechanism@1|@2|@3`; `@1/@2` remain literal and reject `@3` fields. `@3` retains all current `@2` fields and adds body bindings sorted by `physical_body_id`, joint bindings sorted by `physical_joint_id`, pair-policy bindings sorted lexically by physical pair, root fields, and `multi_joint_verification_obligations`. Initial M13-3 `@3` requires exactly one canonical obligation: zero, duplicate, or two-or-more entries reject, and no tuple-item fallback exists. The sole entry is its deterministic replay target, so it has no ordering key. Its hash is the exact `@3` serializer payload excluding `mechanism_hash`. New records are `MultiJointCollisionPairEntry@1`, `MultiJointCollisionPairInventory@1`, `PhysicalToM10V2Bridge@1`, `MultiJointVerificationConfigurationSet@1`, `CandidateMultiJointM10EvaluationScope@1`, `CandidateMultiJointM10EvaluationRequest@1`, `CandidateMultiJointM10Evaluation@1`, `CandidateMultiJointSelection@1`, `CanonicalMultiJointVerificationObligation@1`, and `CandidateMultiJointPromotionRequest@1`.

## Shared Invariants

The shared validator requires one body owner per finalized physical ID and one CAD mapping per physical ID; their ID sets equal the exact realization assembly set and the resulting M10 body-member set. It rejects missing/extra/duplicate body membership, mappings, and CAD constituents. It also requires the complete unordered physical pair universe exactly once, rejects self/unknown/extra pairs, and enforces same-body pairs as `SAME_RIGID_GROUP_EXCLUDED` only.

The shared joint validator resolves exactly one current `MechanicalConnection`/`CanonicalMechanicalConnection` of `ROTATIONAL_DRIVE` with `KINEMATIC_REALIZATION_INTENT`, with exact directed endpoint identity. It validates a connected single-root body tree, no cycle, one incoming joint for each nonroot, all joints/bodies unique, and exact limits. It does not infer DOFs from connections.

Candidate semantic placements are accepted candidate placements or replayed `GeneratedPlacementDerivation`; canonical placements are `CanonicalPlacement` or replayed `CanonicalGeneratedPlacementDerivation`. CAD placements are agreement checks only. The pure lowerer maps a validated source-local point/direction through source semantic home to world, then through inverse parent-reference semantic home, applies sign, normalizes, and emits `RevoluteJointModelV2`. Body member offsets are `inverse(reference_world) * member_world`, full precision. All pose equality uses `rigid_transform_agrees(..., "rigid-transform-agreement@1.0")` only.

`MultiJointCollisionPairInventory@1` fields are `schema_version`, `physical_mechanism_hash`, canonical `physical_body_binding_hashes`, `cad_realization_hash`, `m10_model_hash`, `complete_concrete_instance_ids`, `expected_pair_universe`, canonical `entries`, and `inventory_hash`. Each entry fields are `schema_version`, lexical concrete IDs, `classification`, and `exclusion_reason`; it has no `requires_home_exact_check`. Inventory hash payload is exactly all preceding inventory fields, including every entry. It maps durable physical policy through the exact mapping, and its exact scope is the canonical `ExactConstituentPair` tuple of cross-body `CHECK_CLEARANCE` entries only.

`PhysicalToM10V2Bridge@1` fields are `schema_version`, `physical_mechanism_hash`, `kinematic_root_binding_hash`, canonical `physical_body_binding_hashes`, canonical `physical_joint_binding_hashes`, `semantic_placement_identities`, `axis_source_identities`, `cad_mapping_hashes`, `physical_pair_classification_set_hash`, `model`, `m10_model_hash`, `inventory`, `inventory_hash`, `exact_pair_scope`, `exact_pair_scope_hash`, `ordered_body_ids`, `ordered_joint_ids`, and `physical_to_m10_bridge_hash`. Physical body bindings sort by `physical_body_id`; joints and their axis-source identities sort by `physical_joint_id`; pair bindings sort lexically by `(first_physical_instance_id, second_physical_instance_id)`; semantic placement identities sort by their stable placement/derivation identity; and CAD mapping hashes sort lexically. The final hash payload is all fields except `model`, `inventory`, and its own hash, using their already-bound hashes; this eliminates the inventory/bridge cycle. Bridge creation finalizes model, inventory, and scope before hashing.

`MultiJointVerificationConfigurationSet@1` belongs in neutral `models/multi_joint_verification.py`: current repository layering already has candidate modules importing canonical physical models, so the preferred candidate module would create a prohibited `models -> candidates` cycle. It has exactly `schema_version="multi-joint-verification-configuration-set@1"`, nonempty semantic-order `configurations: tuple[JointConfiguration, ...]`, `configuration_hashes: tuple[str, ...]`, and `configuration_set_hash`. Actual current `JointConfiguration` wire payloads are persisted; hashes never substitute for commands. `configuration_hashes` must equal the ordered current `joint_configuration_hash` values. Its exact SHA-256 canonical JSON payload is `{"schema_version":"multi-joint-verification-configuration-set@1","configurations":<ordered canonical current JointConfiguration wire payloads>}`. It never hashes only configuration hashes.

`CandidateMultiJointM10EvaluationScope@1` has exactly `schema_version`, embedded `configuration_set: MultiJointVerificationConfigurationSet`, `volume_tolerance_mm3`, `distance_tolerance_mm`, `scope_identity`, and `scope_hash`. Its exact hash payload is those fields except `scope_hash`, with the full serialized configuration set. `scope_identity` is caller provenance metadata that deliberately participates in candidate scope identity; it is not canonical replay semantics and does not project to canonical authority. `required_clearance_mm` is absent from this discrete M10-3 scope, request, evaluation, selection, canonical obligation, and acceptance path; it remains only the existing focused M10-4 regression input.

`CandidateMultiJointM10EvaluationRequest@1` has exactly: `schema_version="candidate-multi-joint-m10-evaluation-request@1"`; currentness/provenance fields `project_id`, `source_revision`, `source_state_hash`, `source_binding_hash`, and `candidate_hash`; referenced physical fields `physical_mechanism_hash`, lexically sorted `physical_body_binding_hashes`, lexically sorted `physical_joint_binding_hashes`, `kinematic_root_binding_hash`, and `physical_pair_classification_set_hash`; referenced derived inputs `physical_to_m10_bridge_hash`, `cad_realization_hash`, lexically sorted `cad_mapping_hashes`, `m10_model_hash`, `inventory_hash`, and `exact_pair_scope_hash`; embedded semantic `scope`; checked references `scope_hash`, `configuration_set_hash`, and ordered `configuration_hashes`; M10 identity `m10_v2_request_hash`; and derived `request_hash`. All fields other than `scope`, hashes, `source_revision`, and `request_hash` are nonblank strings; every named hash is a SHA-256 identity; `scope_hash`, set hash, and ordered hashes must equal the embedded scope. Its exact `request_hash` payload is every preceding field in the stated order, with full serialized scope and no `request_hash`. It never contains a result/evaluation/selection field. The embedded scope provides all actual commands required to reconstruct a new `MultiJointCollisionSweepRequestV2`; a caller-authored prebuilt M10 request is never authority.

At candidate request construction and canonical replay, one shared `validate_multi_joint_verification_configurations` validator in `candidates/multi_joint_m10_evaluation.py` requires every configuration to name the exact bridge semantic model ID, contain exactly the emitted stable `physical_joint_id` keys with no missing/unknown ID, contain finite numeric values, satisfy inclusive bounded limits, and retain arbitrary finite raw values for continuous joints. It never wraps 360, normalizes to +/-180, falls back to q=0, derives samples from limits, or generates commands.

`CandidateMultiJointM10Evaluation@1` has exactly: `schema_version="candidate-multi-joint-m10-evaluation@1"`; `project_id`, `source_revision`, `source_state_hash`, `source_binding_hash`, `candidate_hash`; `candidate_request_hash`, `m10_v2_request_hash`, `m10_v2_result_hash`; `physical_to_m10_bridge_hash`, `m10_model_hash`, `physical_pair_classification_set_hash`, `inventory_hash`, `exact_pair_scope_hash`, `scope_hash`, `configuration_set_hash`; and `evaluation_hash`. Its exact hash payload is every preceding field in that order. Construction/replay revalidates the embedded request, requires every currentness field equal the request/candidate source binding, requires `request.scope.configuration_set_hash == evaluation.configuration_set_hash`, and reconstructs the returned M10 result to bind its result hash.

`CandidateMultiJointSelection@1` has exactly: `schema_version="candidate-multi-joint-selection@1"`; `project_id`, `source_revision`, `source_state_hash`, `source_binding_hash`, `candidate_hash`; `evaluation_hash`, `candidate_request_hash`, `m10_v2_request_hash`, `m10_v2_result_hash`; `physical_to_m10_bridge_hash`, `m10_model_hash`, `physical_pair_classification_set_hash`, `inventory_hash`, `exact_pair_scope_hash`, `scope_hash`, `configuration_set_hash`; `selector_identity`, `rationale`; and `selection_hash`. Its exact hash payload is every preceding field in that order. `selector_identity` and `rationale` are required nonblank semantic, identity-bearing values. Selection replays all request/evaluation/currentness fields and rejects any request/result/configuration-set chain substitution. Initial M13-3 has no comparison selection path; it does not introduce comparison fields or a second currentness subsystem.

`CandidateMultiJointPromotionRequest@1` follows the current promotion convention: it embeds no candidate-canonical mapping because the compiler derives it into readiness. It has exactly `schema_version="candidate-multi-joint-promotion-request@1"`, `project_id`, `source_revision`, `source_state_hash`, embedded `candidate`, `synthesis_request`, `synthesis_policy`, `m12_3_result`, embedded `multi_joint_request`, `multi_joint_evaluation`, and `multi_joint_selection`, embedded `promotion_policy`, `canonical_target_mechanism_id`, canonically lexically sorted `classifications`, optional `m11_target_intent`, and `request_hash`. Its exact hash payload is every preceding field, including full serialized embedded records and ordered classifications, excluding `request_hash`. It reuses current source binding/currentness validation through the embedded candidate and source revision/state fields; it does not add a new currentness service.

`MultiJointPromotionReadiness@1` is a transient but self-hashed compiler trust record, not canonical authority. It has exactly `schema_version="candidate-multi-joint-promotion-readiness@1"`, `project_id`, `source_revision`, `source_state_hash`, `source_binding_hash`, `request_hash`, `candidate_hash`, `synthesis_request_hash`, `synthesis_policy_hash`, `m12_3_result_hash`, `multi_joint_evaluation_hash`, `multi_joint_selection_hash`, `scope_hash`, `configuration_set_hash`, `promotion_policy_hash`, `canonical_target_mechanism_id`, canonically sorted `mapping`, lexically sorted `classification_identities`, lexically sorted `trusted_geometry_artifact_ids`, and `readiness_hash`. Its exact hash payload is all preceding fields. Readiness recomputes request/selection/evaluation identities, currentness, mappings, classifications, and geometry authority before projection.

`CanonicalMultiJointVerificationObligation@1` belongs in `models/physical_mechanism.py`. It has exactly `schema_version="canonical-multi-joint-verification-obligation@1"`, embedded `configuration_set: MultiJointVerificationConfigurationSet`, `volume_tolerance_mm3`, `distance_tolerance_mm`, checked `configuration_set_hash`, and `obligation_hash`. Its exact hash payload is schema version, serialized configuration set, both tolerances, and configuration-set hash. It contains no candidate scope identity/request/bridge/model/result/CAD/inventory identity. `CanonicalPhysicalMechanism@3` validates, serializes, and hash-binds the additive one-member tuple; promotion emits one, canonical replay requires one, and zero/two-or-more entries reject. It does not alter legacy `m10_obligations` or `CanonicalM10VerificationObligation`.

`physical_to_m10_v2_model_id` in `candidates/multi_joint_m10_bridge.py` derives the bridge-local `KinematicModelV2.model_id` as `"physical-to-m10-v2-model@1:" + sha256(canonical_payload).hexdigest()`, where the exact payload is `{"schema_version":"physical-to-m10-v2-model-id@1","physical_body_ids":<sorted stable physical body IDs>,"physical_joint_ids":<sorted stable physical joint IDs>}`. It excludes physical instance IDs, CAD identities, placements, pair policy, model hash, inventory hash, and bridge hash. Candidate and canonical models therefore share this semantic ID for the same physical body/joint topology even when fresh CAD, assembly, model, and request hashes differ. This is a bridge-only chosen value; do not alter global `KinematicModelV2` model-ID semantics.

## Implementation Tasks

Every task uses this non-negotiable TDD cycle: write the named failing test, run it and observe failure, implement only the named symbols, run focused tests, predecessor regressions, Task 0 goldens, and protected M10 checks where applicable. Any golden drift is `M13_3_LEGACY_COMPATIBILITY_FAILURE`; any unexpected M10 production diff stops work.

### Approved-Contract Stop Conditions

Stop with `M13_3_IMPLEMENTATION_BLOCKED_BY_APPROVED_CONTRACT_CONFLICT` and exact evidence if configuration hashes exist but actual commands are unavailable; candidate request reconstruction needs external untrusted configurations; canonical reconstruction requires candidate scope/request; the canonical obligation requires candidate CAD/model/result; current `JointConfiguration` wire behavior or legacy `CanonicalM10VerificationObligation` must change; M10-3 requires `required_clearance_mm`; command samples must be inferred from limits; q=0 fallback becomes necessary; candidate/canonical request hashes must be forced equal; stable bridge model ID cannot be implemented without changing M10 schema; or `MultiJointCollisionSweepRequestV2` requires an identity-bearing field not reconstructible from the frozen trusted inputs.

### Task 0: Immutable Legacy Goldens and Protected Baseline

**Purpose:** Capture immutable pre-edit compatibility and protected-M10 content baselines.

**Files:** create `tests/unit/test_m13_3_legacy_goldens.py`; temporary outside repo `C:\Users\vvooj\AppData\Local\Temp\opencode\capture_m13_3_goldens.py`; no production edit.

**Current symbols:** `PhysicalMechanismRealization`, `CanonicalPhysicalMechanism`, `MechanicalDesignCandidate`, all legacy `CandidateM10*` records, `CandidateEvaluation`, `CandidateSelection`, `CandidateCollisionPairInventory`, `CandidatePromotionRequest`, `CanonicalPhysicalMechanismCompiler`, and `CanonicalM10VerificationService`.

**Work:** Capture literals/hashes from unmodified code for every record named in the user Task 0 list, including `JointConfiguration`, `joint_configuration_hash`, `CanonicalM10VerificationObligation`, and current canonical M10 replay, using representative M12 promoted and freshly reconstructed fixtures from `test_m12_promoted_verification.py`; copy only constants into the test; delete helper before production edits. Record SHA-256 file hashes and `git diff --no-index`-compatible snapshots outside the repo for `multi_joint_kinematics.py`, `multi_joint_pair_scope.py`, `multi_joint_collision_sweep.py`, `multi_joint_continuous_path.py`, and `multi_joint_continuous_clearance.py`, plus strict revalidation call locations.

**Tests/exit:** Test literal JSON parse/dump and intrinsic hashes; run `py -3 -m pytest tests/unit/test_m13_3_legacy_goldens.py tests/unit/test_m13_3p_legacy_goldens.py -v`. Stop on uncertainty about source revision, retained helper, or baseline mismatch. Later comparisons allow documented exports only, never semantic content.

### Task 1: Neutral Pair Policy and Physical Body/Root Primitives

**Files:** create `src/mechcad_harness/models/physical_pair_policy.py`; modify `models/__init__.py`, `candidates/m10_evaluation.py`, `candidates/models.py`; create `tests/unit/test_m13_3_physical_primitives.py`.

**New symbols:** neutral enum/alias, pair binding/set helpers, `PhysicalRigidBodyBinding`, `physical_kinematic_root_hash`.

**Validation/hash:** Implement exactly the frozen body/root/pair payloads above; lexical ordering/reason rules; no defaults for classification/reason. Test reorder equality; body hash sensitivity only to body semantics; root stability under changed CAD/M10/inventory and sensitivity R-to-X; every malformed pair and enum alias wire compatibility.

**Authority:** Body/root are `ACCEPTED_PHYSICAL_FACT`; pair policy is analysis/policy semantics, not geometry fact.

**Regression/stop:** Run M12 M10 inventory tests and Task 0. Stop if M12 imports or JSON values change, or a canonical module imports candidates.

### Task 2: Physical Revolute Joint and Axis-Source Primitives

**Files:** modify `candidates/models.py`; create `tests/unit/test_m13_3_physical_joints.py`.

**New symbols:** all four axis-source records/union, enums, and `PhysicalRevoluteJointBinding`.

**Validation/hash:** Implement the exact source and joint payloads above. Test source schema/hash mismatch, owner/sign, required zero literal, finite bounded/multi-turn limits, continuous-only `None`, and hash sensitivity for same numeric axis with different source identity.

**Canonical projection:** Test every source variant projects parent endpoint, child endpoint, and `axis_source.source_physical_instance_id` through the accepted mapping; canonical source payload has canonical ID only, recomputes `source_hash`, and causes a recomputed canonical joint hash. Reject candidate-ID leakage, stale candidate source hash, copied candidate joint hash, and same numeric axis with wrong projected authority identity.

**Authority:** Source records bind M13-1/M13-2 authority identity; no CAD axis/rest transform permitted.

**Regression/stop:** Run `test_m13_supplied_component_interfaces.py`, M13-2 unit suites, Task 0. Stop if a source can be inferred or a zero key is arbitrary.

### Task 3: `PhysicalMechanismRealization@2`

**Files:** modify `candidates/models.py`; modify `tests/unit/test_m13_3_legacy_goldens.py`; create `tests/unit/test_m13_3_realization_v2.py`.

**Current symbols:** `PhysicalMechanismRealization.validate_graph_and_hash`, `MechanicalDesignCandidate`.

**Work:** Add explicit serializer/hash branches. In `@2`, canonicalize body/joint/pair tuples by ID/pair and validate their complete consistency only when bridge universe inputs are provided downstream; retain normal component/connection checks. `@1` rejects all `@2` fields and emits the old payload literally. Candidate hash remains unchanged and naturally binds versioned realization.

**Tests/exit:** Assert `@1` literals/hashes, legacy candidate hash, and malformed `@2` fields reject. Run M12 candidate foundation/cad model tests and Task 0. Stop if `@1` payload changes.

### Task 4: Canonical Projected Primitives and `CanonicalPhysicalMechanism@3`

**Files:** modify `models/physical_mechanism.py`, `models/__init__.py`, `candidates/canonical_mechanism.py`; create `tests/unit/test_m13_3_canonical_mechanism_v3.py`.

**New symbols:** canonical body/joint/pair records, `CanonicalMultiJointVerificationObligation`, and `@3` serializer/hash branch.

**Work:** Add `@3` exact payload and `@1/@2` rejection rules. Add the validated, hash-bound exactly-one `multi_joint_verification_obligations` tuple using the exact obligation contract frozen above; it has no ordering semantics because cardinality is one. Preserve actual configuration values/order and legacy `m10_obligations` literally. Update `validate_canonical_mechanism` to revalidate projected physical fields and obligations and `CanonicalPhysicalMechanismCompiler._validate_mechanism` to call that branch without weakening M13-1/M13-2 checks.

**Tests/exit:** Prove `@1/@2` literals, `@3` ordering/hash including obligation hash, zero obligation rejection, exactly-one valid obligation acceptance, duplicate obligation rejection, two distinct obligation rejection, root hashes, canonical pair independent hashes, and old reconstruction still works. Run M12 canonical physical/reconstruction tests and Task 0. Stop if historical canonical serializers or `CanonicalM10VerificationObligation` change.

### Task 5: Physical/CAD and Pair-Universe Validator

**Files:** create `candidates/multi_joint_m10_bridge.py`; create `tests/unit/test_m13_3_bridge_validation.py`.

**New symbols:** `validate_physical_cad_universe`, `validate_complete_physical_pair_policy`, `validate_physical_body_pair_consistency`.

**Work:** Validate exact candidate or canonical mappings/assemblies, all body members, one-to-one physical/CAD correspondence, complete pair universe, and body/pair rules before constructing M10. Inputs are typed realization/mapping records and physical bindings; output is immutable normalized maps, never inferred bodies.

**Tests/exit:** Test all missing/extra/duplicate/self/unknown cases, caller reorder identity, and six-member 15-pair fixture. Run candidate/canonical CAD suites and Task 0. Stop if a mapping/body is synthesized.

### Task 6: Semantic Placement, Connection, Topology, and Limits

**Files:** modify `candidates/multi_joint_m10_bridge.py`; create `tests/unit/test_m13_3_authority_consumption.py`.

**New symbols:** candidate/canonical placement resolvers, source resolvers, `validate_physical_revolute_connections`, `validate_physical_kinematic_tree`.

**Work:** Call `require_authoritatively_consumable_interface` for M13-1 sources, verify active spec/geometry/evidence/frame/interface/source instance; resolve M13-2 source ID/hash through generated authority and replay current derivations. Validate exact connection endpoint direction/kind/meaning and single-root topology/limits.

**Tests/exit:** Cover generated interface/frame, supplied interface/frame, unauthorized/stale/inferred source, wrong connection, cycles/parents/disconnect, 360 vs 1080 vs continuous. Run all M13-1/M13-2 authority and placement tests. Stop if CAD geometry/viewer placement enters authority.

### Task 7: Pure Axis and Member-Offset Lowering

**Files:** modify `candidates/multi_joint_m10_bridge.py`; create `tests/unit/test_m13_3_lowering.py`.

**New symbols:** `lower_physical_axis_to_parent_body_reference`, `derive_body_member_offsets`, `compile_kinematic_model_v2`.

**Work:** Use only existing transform helpers and `rigid_transform_agrees`; emit M13-3P `KinematicRigidBody`, members, and v2 joints with stable physical body/joint IDs. Revalidate emitted model via `revalidate_v2_kinematic_model`, `validate_v2_body_assembly_agreement`, and all-zero FK agreement.

**Tests/exit:** Verify frame conversions/sign, exact reference identity, arbitrary quaternion offsets, q=0 candidate/canonical agreement, raw multi-turn preservation. Run M13-3P unit suite and Task 0. Stop on transform rounding/new math/tolerance.

### Task 8: Derived Inventory and Exact Scope

**Files:** modify `candidates/multi_joint_m10_bridge.py`; create `tests/unit/test_m13_3_pair_inventory.py`.

**New symbols:** `MultiJointCollisionPairEntry`, `MultiJointCollisionPairInventory`, `derive_multi_joint_collision_pair_inventory`, `exact_scope_from_inventory`.

**Work:** Implement exact frozen schemas/hashes, map every durable physical pair through exact CAD maps, validate complete concrete universe equals assembly and v2 member set, then project only cross-body clearance entries using existing `canonical_exact_pair_scope`/`exact_pair_scope_hash`.

**Tests/exit:** Assert 15 entries, explicit same-body exclusion, A2/B1 clearance scope, reason changes identity, no legacy flag, inventory substitutions reject. Run M13-3P exact-scope/M10-3 tests. Stop if inventory is promotable or classifies heuristically.

### Task 9: Bridge Compiler and Identity

**Files:** modify `candidates/multi_joint_m10_bridge.py`; create `tests/unit/test_m13_3_bridge_compiler.py`.

**New symbols:** `PhysicalToM10V2Bridge`, `PhysicalToM10V2BridgeCompiler`, `compile_candidate`, `compile_canonical`, `physical_to_m10_v2_model_id`, and `physical_to_m10_bridge_hash`.

**Work:** Candidate/canonical adapters feed the same pure core and must accept their own typed CAD realization only. Derive the exact bridge-local semantic `model_id` from sorted stable physical body/joint IDs using `physical_to_m10_v2_model_id`; changing either semantic ID changes it, while fresh CAD alone does not. Persist frozen projections/identities and finalize model->inventory->scope->bridge ordering. Defensively reconstruct all M13-3P inputs at the compiler boundary.

**Tests/exit:** Test exact model-ID payload, candidate/canonical equality for identical physical body/joint topology, sensitivity to a semantic body/joint ID change, and invariance to fresh CAD identity. Also run consumer rejection tests for bridge, pair set, inventory, scope, grouping, source, and limits substitutions; adversarial `model_copy`, `object.__setattr__`, stale body hash, nested schema/evaluator/agreement version all reject before FK/provider/extent. Run M13-3P suite and protected M10 diff. Stop on generic M10 edit or if bridge-local model identity requires a M10 schema change.

### Task 10: Candidate Scope and Pre-Execution Request

**Files:** create `models/multi_joint_verification.py`, `candidates/multi_joint_m10_evaluation.py`; modify `models/__init__.py`, `candidates/__init__.py`; create `tests/unit/test_m13_3_candidate_request.py`.

**New symbols:** frozen scope/request classes and `CandidateMultiJointM10EvaluationService.build_request`.

**Work:** Implement `MultiJointVerificationConfigurationSet` and the exact frozen scope/request payloads. The scope owns actual ordered commands and tolerances; the request embeds that immutable complete scope and binds its scope/set/ordered-command identities. Apply the shared validator before request construction. Reconstruct a new `MultiJointCollisionSweepRequestV2` only from trusted candidate/bridge source assembly, strict bridge `KinematicModelV2`, exact pair scope, `scope.configuration_set.configurations`, and the two discrete tolerances; recompute and compare `request_hash` to `m10_v2_request_hash`. If a current M10 request needs another identity-bearing field not reconstructible from these frozen trusted inputs, stop with `M13_3_IMPLEMENTATION_BLOCKED_BY_APPROVED_CONTRACT_CONFLICT`, rather than taking it from caller state.

**Tests/exit:** Assert the exact request field list/hash payload, source revision/state/binding currentness replay, configuration-set wire/hash payload, nonempty/order sensitivity, checked ordered configuration hashes, one-command sensitivity, actual-value persistence, model-ID/key/finite/limit validation, continuous raw multi-turn preservation, no q=0/limit-derived fallback, absence of `required_clearance_mm`, request reconstruction from embedded scope only, no future fields, stale candidate rejection, hash sensitivity for every bound chain element, and no caller-authored M10 authority. Run M12 request/binding/replay tests and Task 0. Stop if commands are unavailable outside hashes, request can contain result/evaluation/selection, or reconstruction needs untrusted configuration data.

### Task 11: M10-3 Execution and Candidate Evaluation

**Files:** modify `candidates/multi_joint_m10_evaluation.py`, `application.py`; create `tests/unit/test_m13_3_candidate_evaluation.py` and `tests/integration/test_m13_3_candidate_m10_production.py`.

**New symbols:** `CandidateMultiJointM10Evaluation`, `execute`, `candidate_multi_joint_m10_evaluation_hash`.

**Work:** Defensively reconstruct the request from its embedded scope, recompute M10 request hash, invoke the existing v2 production method, reconstruct/re-hash result, verify `request.scope.configuration_set_hash == evaluation.configuration_set_hash`, then create evaluation. `application.py` only composes/invokes this service; it adds no M10 algorithms or schemas.

**Tests/exit:** Prove the exact evaluation field/hash payload and request/source revision/state/binding replay, request A/result B rejection, configuration-set A request plus configuration-set B evaluation metadata rejection, and real/recording v2 A2/B1 reaches exact scope. Run M10-3 unit/provenance/live tests and protected diff. Stop if a result is treated as authority failure rather than engineering outcome.

### Task 12: Candidate Selection and Substitution Protection

**Files:** create `candidates/multi_joint_selection.py`; create `tests/unit/test_m13_3_multi_joint_selection.py`.

**New symbols:** `CandidateMultiJointSelection`, `CandidateMultiJointSelectionService`.

**Work:** Validate/replay candidate, embedded request scope/configuration set, evaluation, currentness, and every identity including `configuration_set_hash` before selection; use exact frozen selection payload.

**Tests/exit:** Prove exact selection field/hash payload; required nonblank identity-bearing selector/rationale; source revision/state/binding and request/evaluation/result/configuration chain replay; and the actual consumer-rejection matrix, including evaluation A with B chain and an otherwise identical candidate/bridge/model/pair-policy/inventory/exact scope whose one command changes. Prove the old evaluation/selection chain is rejected by the consumer, not only that hashes differ. Run M12 selection tests unchanged and Task 0. Stop if legacy `CandidateSelection` is overloaded.

### Task 13: Multi-Joint Promotion Request, Physical Facts, and Pair Policy

**Files:** modify `candidates/promotion_models.py`, `candidates/promotion.py`; create `tests/unit/test_m13_3_promotion.py`.

**New symbols:** `CandidateMultiJointPromotionRequest@1`, `MultiJointPromotionReadiness@1`, `CandidatePromotionCompiler.validate_multi_joint_readiness`, `compile_multi_joint`.

**Work:** Keep `CandidatePromotionRequest@1` literal. Add additive request carrying candidate, multi-joint request/evaluation/selection, policy, mapping, classifications, and the exact selected `GeneratedPlacementDerivation` tuple plus existing `placement_derivations_hash`. Bind the tuple and hash into the M13-3 evaluation/promotion request identities and verify the set against the selected candidate CAD realization hash/provenance before projection. Replay and validate the candidate request, evaluation, selection, embedded scope, actual configuration set, ordered configuration hashes, configuration-set hash, discrete tolerances, derivation ordering/hash, candidate coverage, generated authority inputs, and semantic placement result before projection. Require classifications for body/joint/root as exact `ACCEPTED_PHYSICAL_FACT` source strings, pair bindings and existing generated-placement identities as `CANONICAL_REDERIVATION_INPUT`, and exactly one selected discrete verification obligation as `candidate:multi-joint-verification-obligation:{scope_hash}` with `CANONICAL_REDERIVATION_INPUT` and `source_value=scope_hash`. Project replay semantics only; reject promotion of a candidate scope object as opaque authority, candidate request, `MultiJointCollisionSweepRequestV2`, bridge, M10 result, CAD, inventory, or exact scope.

**Tests/exit:** Prove exact multi-joint promotion request/readiness field and hash payloads, canonical collection ordering, derivation-set/hash binding to the selected CAD chain, candidate/generated-target coverage, stale or substituted derivation rejection, derived-not-embedded mapping convention, all source identity formatting, complete pair/set validation, ID/reason preservation, rejection of inventory promotion, selected obligation classification/value, configuration set A evaluated plus configuration set B promotion obligation rejection, and same commands with changed M10-3 tolerance producing a changed scope/obligation identity and rejection. Test the resulting `ChangeProposal`/`ChangeSet` route. Run all M12 promotion suites and Task 0. Stop if a new promotion enum value or legacy request change is needed.

### Task 14: Canonical `@3` Projection

**Files:** modify `candidates/promotion.py`, `candidates/promotion_models.py`; modify `candidates/canonical_mechanism.py`; create `tests/unit/test_m13_3_canonical_projection.py`.

**Work:** Project every candidate physical-instance-bearing field through `CandidateCanonicalInstanceMapping`: body members/references, joint parent/child endpoints, and all four axis-source variants' `source_physical_instance_id`. Project the carried `GeneratedPlacementDerivation` tuple through the existing M13-2 canonical derivation conversion, preserving exact derivation IDs, inputs, source/target authority identities, and rederived hashes. Rebind canonical source authority, recompute canonical source and joint hashes, preserve body/joint/root semantic IDs, recompute pair-set hashes, and project selected candidate replay semantics into the exactly-one `CanonicalMultiJointVerificationObligation` with actual ordered configuration values, configuration-set identity, and two discrete tolerances. Because `physical_joint_id` remains the M10 v2 joint ID, retain keyed command IDs and raw numeric values exactly; do not convert commands to positional vectors or copy candidate M10 request identity. Populate only canonical `@3` authority. Extend normalized promotion projection additively so `@1` payload remains literal.

**Tests/exit:** Candidate/canonical raw hashes differ where IDs project; semantic fields/reasons and verification commands/tolerances match after projection; legacy canonical obligations remain unchanged; candidate scope identity, CAD/model/request/inventory/result are absent. Run M12 canonical mechanism and M13-2 roundtrip suites. Stop if projected mechanism stores candidate analysis objects.

### Task 15: Fresh Canonical CAD, Inventory, and Bridge

**Files:** modify `candidates/canonical_cad.py`, `candidates/canonical_mechanism.py`, `candidates/multi_joint_m10_bridge.py`; create `tests/unit/test_m13_3_fresh_canonical_bridge.py`.

**Work:** Existing `CanonicalPhysicalCadCompiler.realize` remains the only CAD producer. Its M13-3 path validates `@3` body universe against fresh mappings; canonical bridge accepts only reconstruction + fresh canonical CAD. Require exactly one canonical multi-joint verification obligation; reject zero/two-or-more rather than selecting an item. Reconstruct generated canonical placements from the projected `CanonicalGeneratedPlacementDerivation` set before realizing fresh CAD. Derive fresh inventory/exact scope/model through the same core with no candidate parameters.

**Tests/exit:** Explicitly discard references to `MechanicalDesignCandidate`, `CandidateMultiJointM10EvaluationScope`, `CandidateMultiJointM10EvaluationRequest`, `CandidateMultiJointM10Evaluation`, `CandidateMultiJointSelection`, candidate bridge, `CandidateCadRealization`, candidate inventory, candidate `KinematicModelV2`, and candidate M10 result before reconstruction from state/canonical/artifacts. Assert candidate CAD/inventory/model/configuration lookup rejection at canonical adapter and that projected canonical placement derivations replay without candidate objects. Run canonical CAD/reconstruction tests and Task 0. Stop if candidate IDs/CAD/inventory or candidate configuration authority leaks into canonical input.

### Task 16: Candidate/Canonical Equivalence and Fresh M10-3

**Files:** modify `candidates/multi_joint_m10_bridge.py`, `candidates/multi_joint_m10_evaluation.py`, `application.py`; create `tests/integration/test_m13_3_fresh_canonical_m10.py`.

**New symbols:** `CandidateCanonicalMultiJointEquivalence`, `compare_candidate_canonical_multi_joint_semantics`, `CanonicalMultiJointM10VerificationService`.

**Work:** Compare every required projected semantic field, axes/offsets/q=0 through frozen agreement, universes, policy/reasons, inventory meaning, clearance correspondence, and candidate/canonical placement derivation semantics. Compare configuration count/order, semantic model-ID validity, keyed physical-joint-ID set, raw numeric values, configuration-set semantics, and both M10-3 tolerances; verify candidate/canonical bridge model IDs are equal by the frozen semantic derivation. Fresh verification validates the canonical obligation against fresh bridge model ID, emitted joint keys, and fresh canonical limits; then constructs a new `MultiJointCollisionSweepRequestV2` from fresh assembly, strict fresh model, fresh exact pair scope, canonical actual configurations, and canonical tolerances before calling the existing v2 application API. Recompute the fresh request identity but never require it equal the candidate `m10_v2_request_hash`; candidate result/request/object lookup is forbidden. If a required M10 request identity-bearing field cannot be reconstructed from frozen trusted canonical inputs, stop with `M13_3_IMPLEMENTATION_BLOCKED_BY_APPROVED_CONTRACT_CONFLICT`.

**Tests/exit:** Full R/A/B representative flow, negative projected equivalence, exact derivation-set substitution rejection, candidate-object-free canonical placement/configuration replay, fresh evidence/provenance reload, and candidate/canonical request-hash difference accepted while semantic commands/tolerances remain equivalent. Run M10-3/M10-5 and canonical verification regressions. Stop if raw candidate/canonical hashes are required equal or canonical replay needs candidate scope/request.

### Task 17: Focused Bridge-Generated M10-4 Regression

**Files:** create `tests/integration/test_m13_3_bridge_m10_4.py`.

**Work:** Use bridge-generated v2 model and exact scope with one explicit two-waypoint path through `ProductionApplication.prove_continuous_multi_joint_path_clearance_v2`; assert existing M10-4 outcome/provenance/reach version. Do not add candidate selection/promotion M10-4 records.

**Tests/exit:** Run this test plus M10-4 unit/provenance/live suites and protected diff. Stop if it needs a new M10 API/schema/algorithm.

### Task 18: Representative Live Acceptance

**Files:** create `tests/integration/test_m13_3_generic_multi_joint_acceptance.py`.

**Work:** Build R=(R1,R2), A=(A1,A2), B=(B1,B2); J1 generated authoritative axis; J2 supplied authoritative axis when fixture permits else generated plus separate supplied test. Declare all 15 pair policies, including same-body exclusions, root/articulated clearance, A2/B1 clearance, and an explicit reasoned exclusion. Explicitly supply a nontrivial ordered two-configuration sequence: semantic q=0 home and one valid nonzero two-joint command appropriate to fixture limits. Do not derive the nonzero command from limits. Exercise candidate bridge, M10-3 over exactly that sequence, evaluation, selection, promotion emitting exactly one obligation, candidate-object disposal, fresh canonical CAD/inventory/bridge, equivalence, and fresh canonical M10-3 over that sole reconstructed obligation. Assert no candidate physical instance ID survives in canonical axis authority.

**Tests/exit:** Use no Rotator terminology. Assert no required path skips; retain exact provenance. Stop if a fixture relies on CAD inference or M10 promotion.

### Task 19: Legacy and Boundary Regression Closure

**Files:** modify only tests created by this milestone and `tests/unit/test_m13_3_legacy_goldens.py` if it adds pre-captured constants; no historical expected value edits.

**Work:** Run and record M12 physical/candidate M10/pair inventory/evaluation-selection/promotion/fresh canonical tests; M13-1/M13-2/M13-3P; M10-2/3/4/5; generated/canonical CAD; transient provider; provenance/currentness. Compare protected files byte-for-byte to Task 0 baseline, allowing only documented exports if strictly required.

**Exit:** Zero protected semantic diff and all goldens remain literal. Stop on any historical expected-value update.

### Task 20: Full Verification and Completion Report

**Files:** create `docs/audit/MECHCAD_M13_3_COMPLETION_REPORT.md` only after all gates pass.

**Work:** Run `py -3 -m compileall -q src/mechcad_harness tests`; `py -3 -m pytest tests/` with timeout at least 6000 seconds; capture collected/passed/skipped/failed/errors/elapsed/Python/pytest. Run `git diff --check`, trailing-whitespace scan, final-newline scan, dependency manifest diff, scope scan for M11/M13-4/Rotator/CAD inference/promoted M10/candidate canonical reuse, configuration-hash-only reconstruction, q=0 fallback, limit-derived samples, discrete `required_clearance_mm`, and protected M10 diff.

**Exit:** 0 failed, 0 errors, no required M13-3 skip, no new dependency, no generic M10 semantic change, exactly-one canonical obligation replay, candidate-instance-free canonical axis authority, and replayable candidate/canonical configuration authority proven without candidate-object lookup. Then write report evidence for every final-spec completion-report bullet and only then use `M13_3_GENERIC_MULTI_JOINT_CANDIDATE_CANONICAL_M10_BRIDGE_VERIFIED`.

## Regression Strategy

- M12 physical/candidate foundation: `tests/unit/test_m12_candidate_foundation.py`, `test_m12_candidate_cad_models.py`, `test_m12_candidate_cad_compiler.py`, `test_m12_candidate_cad_replay.py`.
- M12 candidate M10/inventory/evaluation/selection: `test_m12_candidate_m10_binding.py`, `test_m12_candidate_m10_service.py`, `test_m12_candidate_m10_replay.py`, `test_m12_candidate_evaluation.py`, `test_m12_candidate_selection.py`.
- M12 promotion/canonical: `test_m12_promotion_models.py`, `test_m12_promotion_compiler.py`, `test_m12_promotion_projection.py`, `test_m12_promotion_replay.py`, `test_m12_promotion_apply.py`, `test_m12_promoted_verification.py`, `test_m12_canonical_physical_mechanism.py`, `test_m12_canonical_reconstruction.py`, `test_m12_canonical_cad.py`, `test_m12_canonical_m10.py`.
- M13-1/M13-2: all `tests/unit/test_m13_*.py`, especially supplied interfaces, placement derivations, candidate CAD integration, promotion canonical roundtrip, and both M13-2 integrations.
- M13-3P: `tests/unit/test_m13_3p_rigid_body_groups.py`, `tests/unit/test_m13_3p_legacy_goldens.py`, `tests/integration/test_m13_3p_live_grouped_body_freecad.py`.
- M10: `tests/unit/test_multi_joint_kinematics.py`, `test_multi_joint_collision_sweep.py`, `test_multi_joint_continuous_path.py`, `test_multi_joint_continuous_clearance.py`, integrations `test_m10_3_*`, `test_m10_4_*`, `test_m10_5_system_acceptance.py`.
- Configuration authority: new focused tests must cover configuration-set wire/hash payload, ordering, checked hashes, single-command change, model-ID mismatch, missing/extra joint, nonfinite command, bounded limit violation, raw continuous multi-turn command, absence of discrete `required_clearance_mm`, reconstruction from embedded scope only, evaluation/selection/promotion configuration-set substitution, canonical obligation projection, candidate-object-free canonical replay, and acceptance of different candidate/canonical M10 request hashes.
- CAD/transient/provenance/currentness: `test_transient_assembly_analysis.py`, `test_transient_freecad_measurement.py`, `test_m12_candidate_cad_m10_production.py`, `test_m12_promotion_provenance.py`, `test_m12_promotion_production.py`.

## Live Acceptance

The live test must explicitly supply an ordered nontrivial configuration sequence of at least two values: q=0 semantic home and one valid nonzero two-joint command. It must reconstruct canonical analysis after references to `MechanicalDesignCandidate`, `CandidateMultiJointM10EvaluationScope`, `CandidateMultiJointM10EvaluationRequest`, `CandidateMultiJointM10Evaluation`, `CandidateMultiJointSelection`, candidate bridge, `CandidateCadRealization`, candidate inventory, candidate `KinematicModelV2`, and candidate M10 result are discarded. It must show the canonical pair-policy set plus `CanonicalMultiJointVerificationObligation` is sufficient to derive fresh canonical inventory/scope, reconstruct the same semantic sequence, and execute fresh M10-3. A focused v2 M10-4 regression is required but does not create a second selection/promotion pipeline.

## Completion Report Plan

After Task 20 only, report legacy compatibility; body/joint/root/pair authority; every canonical axis-source physical-ID projection/recomputed hash; exactly-one obligation cardinality/replay evidence; M13-1/M13-2 consumption; universe/zero/lowering; derived A2/B1 scope; `MultiJointVerificationConfigurationSet@1` wire/hash contract and actual command replay evidence; stable bridge-local semantic model ID; absence of discrete `required_clearance_mm`; exact request/evaluation/selection/promotion currentness and hash payloads; configuration-set binding through evaluation/selection; physical-only promotion including the `CANONICAL_REDERIVATION_INPUT` verification obligation; `CanonicalMultiJointVerificationObligation@1`; candidate-object-free canonical configuration replay; fresh canonical request construction; candidate/canonical request-hash non-equality semantics; focused M10-4; M13-3P adversarial revalidation; regressions, static checks, protected M10 diff, and the M13-4 boundary.

## Self-Review

- Pair enum import layering is resolved by neutral ownership and legacy aliasing.
- Every body/joint/pair/root/set/bridge/request/evaluation/selection hash payload is frozen above.
- Pair policy is exhaustive, durable, reason-bound, non-geometric, and is never promoted as a physical fact.
- Inventory and exact scope are derived, never promoted; canonical derivation prohibits candidate inputs.
- Body grouping/root are physical authority independent of CAD/M10; zero has one literal semantic.
- Request cannot bind a result; evaluation binds exact returned result; selection/promotion replay the entire chain.
- Actual ordered `JointConfiguration` values have one candidate owner (`MultiJointVerificationConfigurationSet`) and one canonical owner (`CanonicalMultiJointVerificationObligation`); hashes never reconstruct commands.
- Initial M13-3 has exactly one canonical multi-joint obligation; no tuple-order, first-item, or all-obligation replay decision remains.
- Canonical axis sources are distinct projected records: no candidate physical-instance ID, candidate source hash, or candidate joint binding hash can enter canonical authority.
- Request, evaluation, selection, promotion request, and readiness field/hash payloads and collection ordering are explicit; readiness is transient but self-hashed.
- Configuration ordering, set hash payload, scope fields/hash, and bridge-local model-ID derivation are frozen above; scope identity is candidate provenance metadata and does not become canonical replay authority.
- Discrete M10-3 has no `required_clearance_mm`; q=0 is a semantic configuration when explicitly supplied, never a fallback, and commands are never inferred from limits.
- Request embeds replayable scope; evaluation and selection bind configuration-set identity; promotion verifies it before projecting canonical replay semantics.
- Fresh canonical verification uses no candidate object and does not compare candidate/canonical M10 request hashes; M10-4 remains a focused regression only.
- Inventory finalizes before bridge hashing, so no identity cycle exists.
- M13-3P strict reconstruction remains mandatory and protected M10 files require no semantic edit.
- Legacy `JointConfiguration`, M12, and canonical-obligation serialization is guarded by pre-edit goldens and explicit version branches.
