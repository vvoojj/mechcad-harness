# Formal Proposed Spec: Trusted Joint & Verification Engineering Authority

> **PROPOSED — PENDING FORMAL ACCEPTANCE — NO IMPLEMENTATION AUTHORIZATION**
>
> Prepared under the human H1-B approval for formal Spec/Plan preparation only
> (`H1B_DECISION_AND_CONDITIONS_RECORD.md`). This Spec is not accepted, does not
> amend any accepted Spec/Plan, and authorizes no production change, H2,
> `canonical-physical-mechanism@5`, promotion, or MINI execution. Publication
> into `docs/superpowers/**` is a separate acceptance action
> (`FORMAL_ACCEPTANCE_PREPARATION.md`).

Design-input artifacts (same directory): `BASELINE.md`,
`EXISTING_AUTHORITY_CAPABILITIES.md`, `TRUST_BOUNDARY_AND_ISSUER_ANALYSIS.md`,
`AUTHORITY_FIELD_SCHEMA.md`, `CANONICAL_ADMISSION_DESIGN.md`,
`STORAGE_COMPATIBILITY_AND_MIGRATION.md`, `PROMOTION_BINDING_DESIGN.md`,
`CURRENTNESS_AND_REPLAY_RULES.md`, `CONTRACT_ALTERNATIVES.md`,
`PROPOSED_TRUSTED_JOINT_VERIFICATION_AUTHORITY_SPEC.md`,
`PROPOSED_H1B_AUTHORITY_IMPLEMENTATION_PLAN.md`,
`INDEPENDENT_DESIGN_REVIEW.md`, `REVIEW_RESOLUTION.md`.

## 1. Motivation and confirmed production gap

The current-production M12 single-joint lineage (realization@1) constructs a
source-bound `mechanical-design-candidate@2` and can reach promotion readiness,
but the legacy promotion compiler sources canonical joint/obligation fields from
candidate M10 scope/model (`candidates/promotion.py:1639-1778`), which M12-5
classifies as a consistency snapshot, not canonical authority. Realization@1
carries only an `axis_frame_reference` string and a driven child; there is no
typed accepted axis/parent/frame declaration bound to a canonical source
revision. Prior independent verdict: `H1_AUTHORITY_PROOF_INCOMPLETE`.

## 2. Exact accepted baseline

HEAD `3da666f43be299a4d77f879c9a898caaebf204e0`, branch `master`. Sole
canonical store `DesignState` (`models/design.py:72-112`). Trusted mutation
`RunController.apply_approved_proposal` (`runs/controller.py:179-233`) →
`ChangeEngine.apply_proposal` (`changes/engine.py:145-156`). Project-bound
deny-by-default admission precedent
(`changes/constraint_resolution_admission.py`). Canonical target shapes
(`models/physical_mechanism.py:950-1078`). Accepted Deterministic STEP Content
Identity Spec `DE17C360…` unchanged.

## 3. Current capabilities reused

`DesignState`; `ChangeEngine`; `OwnershipPolicy`/`ownership.yaml`; project lock;
`RunController` apply/invalidation/events/replay; proposal/change-set/operation
models; `canonical_json_bytes`; project-bound deny-by-default policy/service
pattern; `CanonicalPhysicalComponentRole`/`CanonicalGeometryFidelity`/
`PhysicalPairClassification`; M13-1 frame/interface vocabulary as a resolution
input; candidate source binding for consumer checks.

## 4. Authority declaration schema

```text
JointAuthorityDeclaration@1
  schema_version: Literal["mechanical-joint-authority-declaration@1"]
  project_id: str
  id: str                                   # issuer/policy-assigned; engine-addressable; hashed
  authority_kind: str                       # "single-joint-verification-requirement@1"
  semantic_version: str
  authority_origin: AuthorityOrigin{origin_kind, issuer_id, issuer_role,
                                    scope_project_id, provenance_note}
  constituents: tuple[JointConstituent, ...]          # min_length 2
  parent_constituent_key: str
  child_constituent_key: str
  joint_semantic_key: str
  motion: {motion_kind, zero_reference_semantics, supports_internal_motion}
  axis:   {frame_reference{frame_id, supplied_by_constituent_key, interface_id},
           origin_x_mm, origin_y_mm, origin_z_mm,
           direction_x, direction_y, direction_z,
           length_unit, coordinate_system_id, axis_sign_rule,
           axis_owner_constituent_key}
  verification: {joint_semantic_key, angle_interval_deg, required_clearance_mm,
                 required_pairs, fidelity_requirements,
                 required_home_check_semantics, bounded_limitations,
                 verification_semantics_version}
  declaration_hash: str = "pending"

JointConstituent{constituent_key, component_ref, role, interface_refs}
ComponentAuthorityReference{ref_kind, source_identity, canonical_component_id}
  ref_kind ∈ {engineering_source_identity, canonical_component_identity,
              synthetic_fixture_identity}
JointPairRequirement{requirement_key, first_constituent_key, first_interface_id,
                     second_constituent_key, second_interface_id,
                     required_classification=check_clearance,
                     requires_home_exact_check=False}
JointBoundedLimitation{limitation_key, statement, scope_constituent_keys}
AuthorityOriginKind ∈ {trusted_engineering_declaration,
                       approved_synthetic_fixture,
                       explicit_approved_design_choice}
```

The declaration is frozen, `extra="forbid"`, deterministic-hashed. `id` is
issuer-assigned and included in the payload; only `declaration_hash` is excluded
(mirrors `physical_mechanism.py:52-56`).

## 5. Field-by-field semantic meaning

Per `AUTHORITY_FIELD_SCHEMA.md` §3: identity/topology; axis/frame; verification;
limitations; each with source classification, validator, canonical storage,
allowed deterministic transform, promotion comparison, and reconstruction rule.

## 6. Source authority requirements

Each field is one of `SOURCE_AUTHORIZED_ENGINEERING_FACT`,
`EXPLICITLY_APPROVED_DESIGN_CHOICE`, `DETERMINISTIC_DERIVATION_FROM_AUTHORIZED_FACTS`,
`DECLARED_VERIFICATION_REQUIREMENT`, `CONSISTENCY_SNAPSHOT`,
`DERIVED_EVIDENCE_ONLY`, `UNRESOLVED_AUTHORITY`. No field may source candidate
M10/CAD/evaluation/solver output (condition 3).

## 7. Trusted issuer/approver policy

Trust root: a trusted, out-of-band, project-bound `JointAuthorityAdmissionPolicy`
(deny-all default). `admit` is application-orchestration only, not exposed via
`AgentGateway`/`ToolBroker`. Issuer/approver are asserted claims validated
against the policy for `authority_kind`, project, and exact content hash, with a
distinct approver unless a rule explicitly allows self-approval. Provenance is
named `policy_validated_issuer_assertion`; **no cryptographic authentication is
claimed** (conditions 1, 2). Synthetic fixture origin is project-bound to
`MINI_ROTARY_FIXTURE` and denied by default elsewhere (condition 1).

## 8. Admission decision contract

```text
admit(declaration, approval, admission_run_id):
  with project_lock(project_id):
    policy = JointAuthorityAdmissionPolicy.for_project(project_id)   # deny-all if absent
    if not policy.authorize(issuer_id, approver_id, authority_kind, H_d, project, origin_kind, scope_project_id): reject
    if approval.content_hash != H_d: reject
    if policy.requires_limitation(authority_kind) and absent from declaration: reject
    if authority_origin.origin_kind == approved_synthetic_fixture and scope_project_id != project_id: reject
    validate declaration internal consistency; resolve canonical refs, if any, at N
    validate admission_run_id binding (project/identity/revision/state hash)
    compile deterministic ChangeProposal (ADD /joint_authority_declarations/<id>)
    apply via RunController.apply_approved_proposal(admission_run_id, ...)
    return admitted(N+1, replayed=False) | read-only replay if already applied
```

Any failure → deny, no mutation, decision recorded.

## 9. Canonical DesignState storage (condition 4)

New `DesignState.joint_authority_declarations: list[...] = Field(default_factory=list)`
(a real `[]` default is mandatory so `ChangeEngine`'s `ADD /<collection>/<id>`
resolves the parent to a list; a `None` default would make the first declaration
un-addable — `changes/engine.py:46-58,104-105`). New ownership path
`/joint_authority_declarations/*` owned by `mechcad-joint-authority-admission`
(distinct from the scalar actor to keep the accepted scalar path untouched).
Serialized record exposes top-level `id`.

**Hash-neutral versioned compatibility** (`STORAGE_COMPATIBILITY_AND_MIGRATION.md`):
`state-hash@2` drops the field when it is absent/empty; `state-hash@1` drops it
unconditionally. Because legacy states have no such field (absent; loaded/defaulted to `[]`) and
`@2` drops it when absent/empty, **every existing revision/hash/manifest/evidence
is preserved byte-for-byte**; new revisions are marked `RevisionSnapshot.schema_version = "m2"`
while `m1` remains loadable. A read-only verification utility independently
proves `@1 == @2 == stored hash` for all pre-change revisions before any schema
edit (Plan Task B0).

## 10. Trusted ChangeEngine application (condition 5)

All canonical mutation flows through the existing `ChangeEngine` under
`OwnershipPolicy` and `StateManager.project_lock`, via
`RunController.apply_approved_proposal`. No ad-hoc writer, no parallel canonical
mutation or authority persistence.

## 11. Source revision/currentness rules (condition 6)

Admission binds `base_revision`/`base_state_hash` and an explicit admission run
(`RunController.create_run`, `runs/controller.py:31-43`, validated like
`_load_source`, `constraint_resolution_admission.py:388-414`). Consumers reject
on project/content-hash/version mismatch, absence, or unresolvable/drifted
references. No cross-revision bypass. Valid sequence: authority admission → N+1 →
candidate currentness → evaluation/selection → promotion.

## 12. Dependency invalidation

`/joint_authority_declarations/<id>` participates in the accepted dependency
graph via `RunController`; downstream nodes are marked stale as for any
proposal.

## 13. Exact binding to a future promotion request

Promotion references declaration `id` + `declaration_hash` + project + admission
revision; the 16 checks in `PROMOTION_BINDING_DESIGN.md` §3 pass fail-closed.

## 14. Candidate M10 consistency checks (condition 3)

Candidate M10 scope/binding/result and candidate CAD/evaluation/solver output are
`DERIVED_EVIDENCE_ONLY`: compared to the declaration only (joint key, endpoints/
interfaces, axis after transform, interval, clearance, pair universe, fidelity,
home checks). Equality is consistency, never authority. No candidate field is
copied into a canonical joint/obligation field as its source.

## 15. Axis/frame normalization

Axis lives in the declared frame owned by `axis_owner_constituent_key` (equal to
`frame_reference.supplied_by_constituent_key`); direction normalized
deterministically; conversion to the promoted parent-local frame is a pinned,
versioned transform (`axis_sign_rule` + `coordinate_system_id`); a global
convention is never assumed; unresolved frame fails closed.

## 16. Units and deterministic lowering

mm/degenerate-unit/deg; pinned `verification_semantics_version` and
`axis_sign_rule`; identical declarations lower to identical canonical payloads.
Required verification pairs are restricted to `check_clearance`.

## 17. External-spur limitations (condition 7)

`INTERNAL_MOTION_UNMODELED` and all accepted verification limitations are
preserved. The acknowledgement requirement is
`DECLARED_VERIFICATION_REQUIREMENT` (policy-enforceable); the concrete
`internal_motion_unmodeled@1` is `DETERMINISTIC_DERIVATION_FROM_AUTHORIZED_FACTS`
from accepted topology. The canonical obligation must carry it. The legacy
compiler omission (`promotion.py:1762-1777`) is a promotion-Epic fix; H1-B
guarantees the authority declares it and that admission preserves it.

## 18. Semantic identity and hash rules

Non-circular `id`/`declaration_hash`; `canonical_json_bytes`; deterministic
proposal/change-set ids; admission provenance excluded from the semantic hash; no
accepted legacy/STEP/promotion hash is changed; `state-hash@1/@2` agreement
preserves all historical `DesignState` hashes.

## 19. Provenance and restart

Admission provenance records source revision/hash, admission run id, policy
id/hash, issuer/approver assertion, approval content hash, origin kind, scope
project id, and admitted revision. Restart reads the declaration and re-validates
recorded hashes from persisted data only; no N+2, no duplicate. `run_id` is
correlation scope only.

## 20. Negative/fail-closed behavior

Reject (record a decision, no mutation) on: absent policy; unrecognized
issuer/approver; synthetic origin outside its accepted project scope;
self-approval without an explicit rule; content-hash mismatch; missing required
bounded limitation; unresolved `component_ref`/frame/semantics version; stale
base revision/hash; missing/invalid admission run; duplicate `id`; unsupported
kind/version; any attempt to use candidate M10/CAD/evaluation/solver output as
authority.

## 21. Compatibility with existing M12 and M13

Additive. `canonical-physical-mechanism@1…@4`, realization@1/@2, candidate@2,
promotion request@2, mapping@3, M12-6 and M13-4 model meanings and model hashes
are unchanged. One deliberate exception: adding the `DesignState` field changes
no existing stored hash because `state-hash@2` is hash-neutral when the field is
absent (§9). The future single-joint canonical target (previously proposed
`canonical-physical-mechanism@5`) is **not finalized**; the contract does not
claim M13 rigid-body/revolute/root/pair authority.

## 22. Compatibility boundaries with STEP Content Identity

No amendment. The accepted Deterministic STEP Content Identity Spec and its
canonical@4 hash pin remain controlling; H2 is not authorized here.

## 23. Explicit non-goals

Implementation; promotion activation; candidate selection/generation; canonical@5
finalization; STEP Spec amendment; H2; MINI execution; cryptographic
identity/PKI; project-specific platform logic; fabrication of engineering values;
M13 field inference; parallel mutation/authority persistence.

## 24. Proposed acceptance criteria

1. Two new typed artifacts only; mutation/ownership/lock/replay reused; no
   parallel canonical mutation or authority persistence (conditions 5).
2. Every declaration field has a classified source and deterministic lowering;
   no field sourced from candidate M10/CAD/evaluation/solver output (condition 3).
3. Issuer/approver authorization deny-by-default, content/project-bound, distinct
   approver; synthetic origin scoped to `MINI_ROTARY_FIXTURE` and denied
   elsewhere; no authentication overclaim (conditions 1, 2).
4. Admission atomic N→N+1 through `RunController`/`ChangeEngine`; replay
   read-only/idempotent; restart no N+2 (condition 6).
5. `state-hash@1/@2` agreement independently proves every existing revision/hash/
   manifest/evidence preserved; versioned migration strategy verified before any
   schema edit (condition 4).
6. `INTERNAL_MOTION_UNMODELED` and accepted limitations declared and admitted
   truthfully (condition 7).
7. M12-6, M13-4, and STEP Identity model/hash regressions pass unchanged.
8. Independent implementation audit accepts the bounded implementation before
   promotion work proceeds (condition 8).

## 25. Remaining authority decisions

1. Authoritative `semantic_version` string for joint semantics (distinct from the
   candidate M10 evaluator version).
2. `angle_interval_deg` range/path convention.
3. Completeness of the fixed `axis_sign_rule` literal set.
4. Whether the two owner actor strings should be unified.
5. The eventual single-joint canonical target version/hash (future work; H2).

The authorized issuer/origin is now resolved by the human decision (option (b),
scoped to `MINI_ROTARY_FIXTURE`).
