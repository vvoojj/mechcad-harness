# Agent Instructions

This file contains **operational rules for agents working in the MechCAD
repository**. Keep broad product description in `README.md`, current normative
architecture in `docs/architecture/**`, capability inventory in
`docs/reference/**`, accepted verification in `docs/audit/**`, and historical
truth in `docs/reconstruction/**`.

## Baseline Anchor

The accepted reconstructed product baseline reaches **M13-4** at commit
`185a304796c17793519fb5f01dbf80cca73ab51e` with terminal marker
`M13_4_INDEPENDENT_FINAL_ACCEPTED`. Commits after that product commit through the
reconstruction synthesis `0cbb70e` are documentation-only.

This is a baseline anchor, not permission to ignore later repository changes.
When working on a newer tree, determine current behavior from the current
implementation and applicable accepted records.

## Core Rule: Separate Current Truth from Historical Truth

Never use a historical record to override current implemented behavior, and
never use current code to rewrite what historically happened.

Use each source for the role it can actually prove:

| Question | Primary source | What it proves |
| --- | --- | --- |
| What is the intended current contract? | `docs/architecture/**` | Normative design intent within its documented coverage |
| What is implemented now? | `src/mechcad_harness/**` | Current production behavior and wiring |
| What behavior is guarded by tests? | `tests/**` | Current test contract; test presence is not execution evidence |
| What was actually accepted/live-verified? | `docs/audit/**` plus retained run evidence | Bounded verification / acceptance |
| What capabilities/wiring exist? | `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md` | Inventory and composition status |
| What happened historically? | `docs/reconstruction/**` | Accepted reconstructed milestone history |

If normative architecture and current production code disagree, do not silently
choose one meaning for both roles:

1. Treat architecture as the intended contract within its documented scope.
2. Treat current production code as ground truth for what is actually
   implemented.
3. Check tests and accepted audits for the affected behavior.
4. Record the documentation/implementation gap explicitly.

`docs/README.md` is a context-routing guide, not a stronger authority than the
sources above.

## Historical Reconstruction Discipline

For historical questions, use this evidence order:

1. accepted canonical reconstruction records under
   `docs/reconstruction/milestones/**` plus `MILESTONE_LEDGER.md` /
   `MILESTONE_CATALOG.json`;
2. detailed reconstruction evidence under `docs/reconstruction/evidence/**`;
3. historical committed production code and tests at the relevant Git boundary;
4. contemporary specifications and plans under `docs/superpowers/**`;
5. contemporary completion/review/acceptance artifacts according to their
   evidence role;
6. later retrospective narrative only as secondary context.

Historical reconstruction must preserve inconvenient facts. In particular:

- do not convert a later fix into a historical pass;
- do not infer a historical test run from committed test code;
- do not infer acceptance from implementation alone;
- do not erase rejected intermediate states after a later acceptance;
- distinguish **known**, **inferred**, and **not proven** boundaries;
- preserve shared-commit or missing-artifact ambiguity instead of inventing a
  dedicated milestone boundary;
- never fabricate completion markers, retained logs, CI results, or authority.

`docs/reconstruction/**` is authoritative for reconstructed history, not for
current runtime semantics.

## Evidence Semantics — Do Not Conflate

- **SPEC / DESIGN:** intended contract.
- **PLAN:** intended implementation approach.
- **COMMITTED CODE:** implementation evidence.
- **COMMITTED TEST:** test existence / expected behavior, not historical execution.
- **RETAINED TEST / CI / LIVE OUTPUT:** execution evidence for the recorded run.
- **COMPLETION REPORT:** completion claim/evidence; not automatically independent
  acceptance.
- **REVIEW / ACCEPTANCE:** evaluation and formal acceptance where present.
- **RETROSPECTIVE:** later description of earlier history.

Prefer precise claims such as *implemented*, *production-wired*, *unit-verified*,
*live-verified in a bounded scenario*, *accepted*, *rejected*, or *accepted as
design only*. Avoid using *accepted* as a synonym for *implemented*.

## Planning and Execution Model

Use the specification hierarchy:

```text
Project Spec → Epic Spec → Story Spec
```

Coding sessions are execution units, not an additional specification layer.
Resolve important uncertainty as far **left** as practical. Use Human-in-the-Loop
early for decisions that change requirements, authority, scope, or irreversible
engineering choices; after those decisions are resolved, continue autonomously
inside the authorized scope.

Independent Epics may proceed in parallel when dependencies allow. Within one
Epic, execute dependent Stories / implementation steps sequentially unless the
accepted Epic contract explicitly defines safe parallelism.

Before editing:

1. identify whether the task concerns current behavior, historical truth, or
   both;
2. read only the smallest relevant context bundle;
3. inspect the actual current implementation/API before relying on remembered
   names or behavior;
4. identify protected/accepted surfaces and downstream regression gates;
5. resolve material uncertainty before broad implementation.

Prefer minimal, reviewable changes. Do not redesign adjacent subsystems without
an explicit requirement.

## Production Authority and Wiring Invariants

These rules must not be contradicted unless the task explicitly changes the
contract and the applicable protected documentation/tests are updated:

- `DesignState` is canonical. Proposals, tool results, artifacts, analysis
  results, validation results, and Evidence remain separately bound records.
- Only trusted change machinery (`ChangeEngine` under ownership policy and the
  project lock, via `RunController` where applicable) creates canonical
  revisions.
- **`proposal.status` is not an enforced approval gate** in the accepted current
  code. Do not claim an approval check exists where it is not implemented.
- `ImportedCadComponent` is the complete byte-verified STEP artifact. An
  arbitrary filesystem STEP path is not trusted supplied geometry.
- Do not infer semantic engineering authority from CAD/STEP geometry, filenames,
  labels, or test fixture names. Geometry may support geometry claims; semantic
  authority must come from an accepted authority source.
- Backend/library objects must not cross normalization boundaries into persisted
  records; persist normalized scalar/typed provenance instead.
- `run_id` is correlation/storage scope, not engineering identity.
- `CadCompilationService` operates under
  `PREACCEPTED_CALLER_CONTRACT_ONLY`.
- Selection and promotion are explicit. Do not silently auto-select or
  auto-promote a candidate.
- Current bounded M12/M13 flows support one selected feasible candidate and one
  canonical obligation in the relevant path; do not generalize this into a
  multi-objective optimizer.
- Promotion's M11 handoff is eligibility-only; it does not perform structural
  analysis.

## Capability Boundaries That Must Not Be Overstated

- M10-3 is discrete and keeps `continuous_path_verified = False`; M10-4 proves
  only the explicitly requested path. There is no general trajectory planner or
  whole configuration-space certification.
- M11 is a source-bound, single homogeneous solid, linear-static path. No
  assembly FEA, nonlinear/fatigue/dynamics/thermal analysis, global/stress
  convergence, or manufacturing/safety approval is implied.
- There is no generic candidate generation/search, catalog selection,
  bearing/fastener sizing, gear strength/life calculation, or optimization.
- Generated-part CAD is currently cylindrical stock plus axial bore; exactness is
  relative to the bound semantic specification, not manufacturing truth.
- M13-1 interface authority is unit-verified at its own boundary.
- Materials selection, tolerance verification, manufacturing output/approval,
  whole configuration-space certification, and general automatic synthesis are
  not implemented.

When a capability status matters, verify the whole chain: model → service →
provider/tool → registration → production composition → caller → end-to-end
path → retained/live proof. Importability or a unit test alone does not make a
capability production-wired or live-verified.

## Verification Workflow

For implementation changes:

1. run the smallest focused test(s) that directly exercise the changed contract;
2. run required predecessor/regression gates for affected accepted surfaces;
3. run broader/full-suite verification only when required by the task,
   acceptance contract, or risk of the change;
4. run relevant static checks (`compileall`, `git diff --check`, lint/type checks)
   when they are part of the affected gate;
5. retain exact command/result evidence when making an acceptance or historical
   execution claim.

A passing test count is evidence only for the exact invocation that produced it.
Do not copy stale counts forward. A timeout, skip, failure, environmental event,
or aborted run must remain visible in the historical record even if a later run
passes.

For live CAD/solver validation, verify the real executable/provider identity and
execution boundary. Do not credit fake adapters, mocks, or importability as live
FreeCAD/Gmsh/CalculiX proof.

## Progressive-Disclosure Reading Order

Do not load every milestone spec, audit, or reconstruction record by default.

For a general current architecture task, start with:

- `docs/README.md`
- `docs/architecture/MECHCAD_PROJECT_OVERVIEW.md`
- `docs/architecture/MECHCAD_SYSTEM_CONTRACT.md`
- `docs/architecture/MECHCAD_CAPABILITY_MATRIX.md`

Add, only when relevant:

- runtime/CAD/analysis: `MECHCAD_RUNTIME_FLOW.md`,
  `MECHCAD_SUBSYSTEM_CONTRACTS.md`, and the applicable M9/M10/M11 audits;
- candidate/promotion/M12/M13: M12-6 and M13-4 accepted audits plus the relevant
  current code/tests;
- capability discovery/integration: `docs/reference/MECHCAD_IMPLEMENTED_CAPABILITIES.md`;
- historical questions: `docs/reconstruction/README.md`, the relevant canonical
  milestone record, ledger/catalog, and only the evidence needed to resolve the
  question.

## Protected Operations and Approval

Do not perform these without explicit authorization in the user's task or a
separate user approval:

- `git commit`, amend, push, tag, release, or history rewrite;
- modification of accepted audit records, accepted tests, specs/plans, normative
  architecture, or `docs/reconstruction/**` when the task did not explicitly ask
  to change that protected surface;
- package installation or network-dependent mutation;
- destructive filesystem operations outside the repository workspace.

Live external execution (FreeCAD/CalculiX/Gmsh/OpenCode live validation) is
allowed only when the task explicitly calls for live verification or the user
has authorized it. Once live verification is authorized for the task, do not
interrupt the user for approval before every individual bounded invocation;
stay inside the authorized scope and report what was actually run.

Read-only inspection and ordinary local focused/unit tests that do not invoke
those external live runtimes do not require repeated approval.

## Engineering Constraints

- Keep changes inside this repository unless the task explicitly says otherwise.
- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Keep models minimal; reject empty required strings and non-positive revisions
  where those invariants apply.
- Fail closed on missing authority, stale identity, invalid provenance, or
  unverifiable required bindings.
- Never fabricate missing engineering values to make a test or acceptance flow
  pass.
- Preserve backward-compatible wire/hash semantics where an accepted contract
  explicitly requires them.
- The historical M0 restriction against agents/CAD/FEA/external services applies
  only to the M0 boundary; later accepted milestones deliberately add bounded
  versions of those capabilities.
