# Formal Proposed H1-B Authority Implementation Plan

> **PROPOSED — PENDING FORMAL ACCEPTANCE — NO IMPLEMENTATION AUTHORIZATION**
>
> Bounded plan for the H1-B authority contract only. It does not authorize the
> future single-joint promotion Epic, H2, or MINI. No task has started; no listed
> test has been executed. Publication into `docs/superpowers/**` is a separate
> acceptance action.

## 0. Planning sequence

```text
formal Spec/Plan acceptance (human)
→ B0 storage-compatibility verification utility (read-only, before schema edit)
→ typed declaration models
→ issuer/approval policy (synthetic scoped to MINI_ROTARY_FIXTURE)
→ typed trusted canonical admission
→ DesignState storage + hash projection + ownership/dependency config
→ hash / replay / currentness
→ promotion consumption contract (validation helper only)
→ focused positive and negative tests
→ M12/M13/STEP regressions
→ independent implementation audit
```

## 1. Reused services (no changes expected)

`StateManager`/`project_lock`; `ChangeEngine.apply_proposal`; `OwnershipPolicy` +
`ownership.yaml`; `RunController.apply_approved_proposal`; `ChangeProposal`/
`ChangeSet`/`ChangeOperation`; `core.canonical.canonical_json_bytes`; the
constraint-resolution admission **pattern**; shared enums; M13-1
frame/interface vocabulary.

## 2. Work packages (H1-B required)

| # | Task | Owner area | Prerequisite | Tests |
|---|---|---|---|---|
| B0 | Read-only storage-compatibility verification utility proving `state-hash@1 == state-hash@2 == stored hash` for all pre-change revisions and current pointers **plus** the mutation-implementability check (`[]` field is addable via `ADD /joint_authority_declarations/<id>`; `None` variant raises `InvalidChangePathError`); machine-readable report | `state/` + a verification script | Spec acceptance | new verification (evidence) |
| B1 | `JointAuthorityDeclaration` + sub-models + `declaration_hash`; `origin_kind`/`scope_project_id`; pinned pair classification | `models/` (new module) | B0 | proposed unit |
| B2 | `JointAuthorityAdmissionPolicy` (rules, deny-all, `from_file`, `for_project`, `authorize`, synthetic-scope guard) | `changes/` | B1 | proposed unit |
| B3 | `JointAuthorityAdmissionService` (lock → authorize → validate → compile → apply via `RunController.apply_approved_proposal`; explicit `admission_run_id`) | `changes/` | B1,B2 | proposed unit/integration |
| B4 | `DesignState.joint_authority_declarations: list = Field(default_factory=list)` + uniqueness validator; `state-hash@2` projection (`canonical_payload` drops the field when absent/empty); add `canonical_payload_v1`/`state_hash_v1`; `RevisionSnapshot` `SCHEMA_VERSION="m2"` | `models/design.py`, `state/hashing.py`, `state/manager.py` | B0 | proposed unit + B0 re-run |
| B5 | Ownership rule `/joint_authority_declarations/*` → `mechcad-joint-authority-admission` | `projects/*/ownership.yaml`, `config/ownership.yaml` | B4 | existing ownership tests extended |
| B6 | Dependency nodes for the new path where required | `config/dependencies.yaml`, `projects/*/dependencies.yaml` | B4 | existing dependency tests extended |
| B7 | Compose policy path/instance into `ProductionApplication` (deny-all default) | `application.py` | B2,B3 | proposed composition test |
| B8 | Deterministic ids + admission-run replay + currentness validation | `changes/` | B3 | proposed replay/currentness |
| B9 | Promotion-consumption validation helper (checks 1–16; no promotion activation, no target) | `candidates/` | B3,B8 | proposed unit (positive/negative) |
| B10 | Independent implementation audit (reproduce B0 report; verify hashes/replay/negatives) | separate reviewer | B0–B9 | audit |

## 3. DesignState model and schema effects (condition 4)

- New field defaulting to `[]` (a real list, required for `ChangeEngine` ADD);
  only admission appends. A `None` default is rejected as un-addable.
- `canonical_payload`/`state_hash` adopt `state-hash@2`; frozen
  `canonical_payload_v1`/`state_hash_v1` retained for audit. The `@2` rule applies
  to both `DesignState` and raw-dict inputs.
- `state-hash@2` equals `@1` for every declaration-free state, so all existing
  revisions, `current.json` pointers, run manifests and evidence remain valid
  with **no rewrite**. New revisions are `schema_version="m2"`; `m1` still loads.
- Full strategy and independent verification: `STORAGE_COMPATIBILITY_AND_MIGRATION.md`.
- No accepted model meaning, promotion/STEP hash, or existing wire semantics
  changes.

## 4. Ownership and dependency configuration (condition 5)

- `ownership.yaml`: add `/joint_authority_declarations/*` → new owner.
- `dependencies.yaml`: add only nodes whose invalidation is required.

## 5. Canonical mutation wiring (condition 5)

One `ChangeProposal` with ADD operations at `/joint_authority_declarations/<id>`,
`actor` = new owner, applied via `RunController.apply_approved_proposal`. No
direct `StateManager` write, no new mutation API, no second store.

## 6. Source binding (condition 6)

Admission validates `base_revision`/`base_state_hash` and an explicit admission
run, and resolves canonical refs if used; consumers apply the fail-closed
currentness rule.

## 7. Promotion consumption contract

Validation helper implementing `PROMOTION_BINDING_DESIGN.md` checks 1–16,
returning typed failures. It does not modify the promotion compiler or activate
realization@1 promotion.

## 8. Replay / provenance verification (condition 6)

Deterministic ids; prepared/admission events via `RunStore`; read-only replay;
restart reads persisted state only.

## 9. Regression tests

- Existing gates (re-run unchanged): `tests/unit/test_constraint_resolution_admission.py`,
  `tests/integration/test_constraint_resolution_canonical_admission.py`,
  `tests/unit/test_m12_promotion_*`, `tests/unit/test_m13_4e_*`,
  `tests/unit/test_m12_canonical_*`, `tests/unit/test_canonical_mechanism_v4.py`,
  `tests/unit/test_candidate_trusted_semantic_verification.py`, STEP-identity
  suites, and acceptance gates
  `tests/integration/test_m12_6_end_to_end_direct_drive.py`,
  `tests/integration/test_m13_4_full_stack_acceptance.py`,
  `tests/integration/test_m13_4p_production_composition.py`.
- Proposed new: declaration model validation; policy authorize/deny matrices
  (including synthetic-origin scope denial); admission apply/replay; currentness
  fail-closed; content-hash replay rejection; unresolved-reference rejection;
  limitation-required rejection; promotion-consumption checks; restart/no-N+2;
  storage-compatibility (`@1/@2`) preservation.

## 10. Live proof boundaries

The H1-B implementation needs no live FreeCAD/Gmsh/CalculiX proof. Any future
live single-joint verification belongs to the promotion Epic.

## 11. Stop conditions

Return to human authority if: the storage-compatibility strategy cannot be
demonstrated to preserve all existing hashes (condition 4); a required
`component_ref` cannot be resolved within the trust boundary; implementing the
contract requires changing an accepted M12/M13/STEP hash/meaning; or the
anti-duplication rule cannot be honored without unsafely editing the accepted
constraint-resolution path.

## 12. Deferred to the future single-joint promotion Epic (NOT authorized)

Activating the realization@1 route and the canonical single-joint target; H2
STEP-Spec amendment and new canonical CAD/M10/promotion/M11 hashes; fixing the
legacy `bounded_limitations` omission; fresh canonical reconstruction/CAD/M10;
M11 handoff; MINI readiness re-audit and execution.
