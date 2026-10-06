# Deterministic STEP Content Identity Plan R-P5.M10 Verification Revision — Independent Acceptance

## Verdict

```text
Target Plan:
docs/superpowers/plans/2026-09-21-deterministic-step-content-identity-implementation.md

Exact Plan SHA-256:
291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679

Controlling accepted Spec SHA-256:
DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68

Disposition:
INDEPENDENTLY_ACCEPTED

MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_PLAN_RP5_M10_VERIFICATION_REVISION_INDEPENDENTLY_ACCEPTED_291B39B0
```

This acceptance binds only the exact Plan bytes and controlling Spec bytes named
above. Any byte change to either object is outside this disposition.

## Acceptance Boundary

This is planning-authority acceptance only. It is not proof of implementation,
test execution, prospective semantic conformance, or historical pre-relocation
versus post-relocation projection-output equality. The historical equality is
**NOT PROVEN**; the original equality clause was part of `R-P5.M10`, which the
Plan records as **NOT EXECUTED**. The prospective A–H contract has not been
executed or accepted by this record. A future `PROVEN INSTEAD` conformance claim
must be supported by the complete A–H evidence and its separate independent
evidence audit, and can never establish historical equality.

No implementation tests, application tests, static checks, runtime import
smokes, FreeCAD/Gmsh/CalculiX execution, or implementation work were run for
this audit.

## Exact-Byte and Authority Checks

- Recomputed Plan SHA-256 from disk: `291B39B0DAF33DD3D55937D8062ECCE70F4E2FED511C3C611D56A3E98A5D6679` — matches the requested target.
- Recomputed Spec SHA-256 from disk: `DE17C360F09A9C9CB9A8A01118789B41AD4F1366A23AD728BFA3A9B19E2B1B68` — matches the controlling value.
- Read the durable Spec acceptance record at `docs/audit/MECHCAD_DETERMINISTIC_STEP_CONTENT_IDENTITY_SPEC_REVISION_DE17C360_INDEPENDENT_ACCEPTANCE.md`; its bound Spec hash and independent-acceptance marker match the controlling Spec.
- The Plan binds future work to that Spec hash and states that this revised Plan requires independent acceptance before verification-test/vector edits or `R-P5.5`.

## Findings

No acceptance-blocking finding remains against the requested criteria.

### Historical boundary and limited revision

- Plan §0 and §§401–414 state that `R-P5.M10` is future/not executed and keep `R-P5.1`–`R-P5.4` historical execution distinct from future work.
- New Plan §734 says the former before/after phrase records a requirement and is not evidence it ran. §738 labels historical output equality **NOT PROVEN** because the original bodies/snapshots are unrecoverable.
- New Plan §§741–743 explicitly prohibit treating prospective conformance as before/after equality or as evidence of history. The replacement is limited to the unrecoverable projection-output comparison and its matching duplicated review-note phrase. The other relocation and phase gates remain binding.
- No Spec or reconstruction/history change is proposed.

### Relocation invariants retained

Plan §§410, 420–426 and 741 retain all substantive relocation conditions:

- exactly four named projection functions and one pure owner, `semantic_m10_kinematics.py`;
- unchanged accepted semantic payloads, field allowlists, canonicalization, and `m10-execution-semantics@1`;
- exact protected source SHA-256 pins for `multi_joint_kinematics.py` and `multi_joint_collision_sweep.py`;
- unchanged protected `tests/unit/test_m13_3_legacy_goldens.py`, with no golden update;
- no duplicate production definition or compatibility re-export;
- direct production imports from the semantic owner and acyclic dependencies.

The acceptance audit independently recomputed the current file hashes:

| Protected file | Required SHA-256 | Recomputed SHA-256 | Result |
|---|---|---|---|
| `src/mechcad_harness/multi_joint_kinematics.py` | `514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f` | `514340c2f16b4bb29ff39a47c10d4446de2e84c27040d117b0099d53eb440c4f` | MATCH |
| `src/mechcad_harness/multi_joint_collision_sweep.py` | `56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f` | `56e55b664e980eeda9ffc9d67a038a6eb726dccb73f42c2b6d0214a06df9706f` | MATCH |
| `tests/unit/test_m13_3_legacy_goldens.py` | `7dc391f10e545fc3291669a894a3c2a10729672eba9e847c1dca4dd88c8d5ba4` | `7dc391f10e545fc3291669a894a3c2a10729672eba9e847c1dca4dd88c8d5ba4` | MATCH |

Read-only current-worktree observation: `semantic_m10_kinematics.py` exists as
an untracked file; the two protected source files are clean and at the required
hashes. This observation is not evidence that `R-P5.M10` or its verification
gate was executed. The Plan's mandatory current-byte/worktree reconciliation
remains controlling before any future implementation or verification work.

### Prospective A–H contract completeness

- **A — Owner and shape:** requires mechanical ownership/duplicate/export checks, direct production imports, static acyclicity, and a separate production import smoke.
- **B — Accepted-contract matrix:** maps each function independently to the controlling Spec: model hash to §12A/F1, single-joint hash to §12A/F3, request hash to §12B/P5, and result hash to §12B/P6. It requires declared-field classifications, exact payloads, collection semantics, replay/raw/execution/self-hash rules, failure behavior, and version pins.
- **C — Independent vectors:** requires fixed typed inputs, complete expected payloads and digests derived from the accepted Spec or independently before invoking the functions; prohibits current-output-derived expectations and specifically requires independent §10 assembly inputs for P5/P6.
- **D — Sensitivity/invariance:** covers applicable Spec cases for semantic sensitivity, validated raw/provenance/execution/self-hash invariance, SET_SEMANTIC and ORDERED distinctions, and rejection cases; requires each matrix row to cite an exact test/input and forbids invented invariances.
- **E — Protected bytes:** pins the two M10 sources and legacy golden; keeps the other three protected M10 inputs clean/byte-identical.
- **F — Fresh focused gate:** requires the complete relocation-focused unit set, T-P5.1 predecessor gate, new C/D verification tests, compileall, and targeted diff check, with exact fresh command evidence.
- **G — Import/ownership:** requires static dependency/ownership proof plus a production import smoke, including no project-semantic dependency or alternate implementation.
- **H — Downstream consistency:** names the accepted candidate and canonical P5/P6 focused consumers and relevant closure cases. It expressly says these checks do not prove historical equality or complete P5.3/P6; all other P6/P7 gates and ordering stay unchanged.

The Plan requires a new evidence record bound to exact Plan/Spec hashes and a
separate independent read-only audit of that evidence before `R-P5.5`. It does
not authorize edits before this exact Plan acceptance.

## Status

- Plan: independently accepted for planning authority only, for the exact Plan SHA above.
- Spec: accepted only for the exact controlling Spec SHA above.
- Historical projection-output equality: **NOT PROVEN**; original clause not executed.
- Prospective A–H verification: **NOT RUN / NOT PROVEN** by this audit.
- Implementation, tests, runtime imports, and live verification: **NOT PROVEN** by this audit.
- `R-P5.5`: remains blocked until post-acceptance R-P5.M10 verification is complete and its separate independent evidence audit accepts.

## Files and Scope

All pre-existing files consulted were inspected read-only. This new audit is the
only file created by this task. No Plan, Spec, source, test, reconstruction
record, or existing audit was edited. No tests or implementation work were
performed.
