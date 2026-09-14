# F10 M6B-4C Retirement Design

## Decision and scope

The human product/architecture decision is binding: **F10 = RETIRE**. Retire
the unused, unaccepted M6B-4C constraint-resolution workflow. This design is
specification only; it authorizes no implementation, deletion, production
change, test change, audit/map change, or reconstruction change.

Baseline inspected: `69c11dc809fe8622d371f891bc7b5216aa1875d2`
(`docs(p3): record human-in-the-loop triage decisions`). Pre-existing dirty and
untracked work is out of scope and must remain untouched.

M6B-4C is historically `PRESENT_BUT_UNUSED` with no acceptance and no
production caller. The current P3 triage independently confirms that
`ConstraintResolutionWorkflow.run()` is test-reachable only and that neither
the workflow nor its application service is composed by
`ProductionApplication`.

## Reachability inventory

### Retired workflow-local code

The implementation phase shall remove these workflow-local files and symbols:

| File or surface | Symbols / behavior | Current callers | Disposition |
| --- | --- | --- | --- |
| `agents/constraint_resolution_workflow.py` | `WorkflowOutcome`, `WorkflowTransition`, `ConstraintResolutionWorkflowResult`, `workflow_id`, `ConstraintResolutionWorkflow` and its transition/replay/invalidation/satisfaction logic | `test_constraint_resolution_workflow.py`; package re-export | Remove. No production caller exists. |
| `agents/constraint_resolution_application.py` | `ApplicationOutcome`, `ConstraintResolutionApplicationResult`, `ConstraintResolutionApplicationService`, `_anchor_for`, application/recovery/planning logic | workflow module; application/workflow/provenance tests; three M7 test fixtures; package re-export | Remove. No production caller exists. |
| `changes/provenance.py` | `operations_hash`, `application_id`, `StateApplicationPreparationRecord`, `StateApplicationReceiptRecord`, `StateApplicationStore` | retired application/workflow and their tests; public `changes` lazy re-export | Remove with the retired application. There is no non-retired source caller. |
| `state/manager.py:StateManager.promote_existing_revision` | prepared-application recovery promotion | retired application only | Remove as workflow-local recovery support. |
| `config/ownership.yaml` | `/authoritative_parameters` owner `mechcad-resolution` | retired application and its tests only | Remove this ownership entry. |
| `agents/__init__.py` | application/workflow imports and four corresponding `__all__` entries | package-import compatibility surface | Remove with the retired modules. |
| `changes/__init__.py` | provenance names in `__all__` and `__getattr__` | package-import compatibility surface | Remove with `changes/provenance.py`. |

The application phase must not delete `agents/constraint_resolution.py`. It
was introduced before M6B-4C and is outside the authorized retirement boundary.
Its answer, command, record, store, materializer, canonical-value conversion,
and deterministic ID functions remain unchanged.

### Retained shared and active behavior

| Surface | Why it remains |
| --- | --- |
| `agents/constraint_requests.py` | Active constraint-request discovery and durable request records. It is used by `agents/roundtrip.py`, `agents/persistence.py`, `agents/models.py`, the gateway materialization path, and the azimuth/Yagi authority consumers. |
| `ConstraintRequestMaterializer._anchors`, `anchor_for`, and `is_satisfied` | The sole authoritative anchor mapping and active satisfaction logic. Preserve byte-for-byte behavior unless a separately authorized change requires otherwise. |
| `agents/roundtrip.py`, `agents/gateway.py`, `agents/materialization.py`, `agents/opencode.py`, and agent models | Accepted agent/gateway behavior materializes requests only; it does not submit a resolution command or invoke the M6B-4C application/workflow. No change is authorized. |
| `agents/constraint_resolution.py` and its package exports | Retained public M6B-4A typed resolution data/materialization surface. No removal, wire change, hash change, or API cleanup is authorized by F10. |
| `DesignState.authoritative_parameters`, `AuthoritativeAnchor`, `AuthoritativeParameter`, `ChangeEngine`, and ordinary state revision behavior | Shared canonical-state machinery. F10 removes only the unused M6B-4C route that applied a resolution through it. |

## Anchor-map authority

`ConstraintRequestMaterializer` is the active owner of the supported-key to
canonical-anchor mapping:

- `_anchors` owns six standard requirement/constraint locations.
- `anchor_for()` owns the special azimuth-drive anchor and normalizes collection
  names to `requirement` or `constraint` kinds.
- `is_satisfied()` uses the same mapping to fail closed on missing anchors,
  duplicate authoritative parameters, scope mismatch, or key/value mismatch.
- Active request discovery and azimuth/Yagi consumers call this class directly.

`constraint_resolution_application._anchor_for` has no behavior not already
represented by this owner. It maps the same seven keys to the same normalized
kind/ID pairs. Its only consumer is the retired application service. The
implementation must remove `_anchor_for` with that service; it must not move or
copy the map into a new helper.

## Persisted, wire, and hash boundary

The retired path writes only workflow-local records:

- `projects/<project>/runs/<run>/resolution_workflow/*.json` transition files;
- `projects/<project>/runs/<run>/state_application/preparations/*.json`;
- `projects/<project>/runs/<run>/state_application/receipts/*.json`.

No current production reader or accepted retained flow consumes these records.
No migration, conversion, or compatibility reader is required. Existing local
records become historical workspace residue and must not be interpreted as an
active supported workflow after retirement.

F10 must preserve the request and resolution record paths under
`agents/constraint_requests`, `agents/constraint_resolution_commands`, and
`agents/constraint_resolutions`, the `CRREQ-*`, `CMD-*`, `CRRES-*`, and
`PARAM-*` identity algorithms, `AuthoritativeParameter.source_resolution_id`,
and all unrelated state/hash wire semantics. Those surfaces are outside this
retirement even where they were exercised by M6B-4C tests.

## Package and compatibility policy

The following imports will intentionally cease to resolve in the implementation
change:

- Direct modules: `mechcad_harness.agents.constraint_resolution_workflow` and
  `mechcad_harness.agents.constraint_resolution_application`.
- `mechcad_harness.agents` re-exports:
  `ConstraintResolutionWorkflow`, `ConstraintResolutionWorkflowResult`,
  `ConstraintResolutionApplicationService`, and
  `ConstraintResolutionApplicationResult`.
- Direct module and aggregate `mechcad_harness.changes` provenance imports:
  `StateApplicationPreparationRecord`, `StateApplicationReceiptRecord`,
  `StateApplicationStore`, `application_id`, and `operations_hash`.
- `StateManager.promote_existing_revision` and the
  `mechcad-resolution` ownership route.

These are Python-visible surfaces, but repository evidence establishes no
accepted public contract, production caller, documented entrypoint, or retained
consumer outside the subsystem being retired. They belong exclusively to the
unaccepted M6B-4C workflow and may be removed under the human retirement
decision. No compatibility shim, deprecated alias, or replacement API will be
added: each would retain a supported-looking path without an active workflow.

External users of these imports could break. There is no in-repository evidence
for such users and no currently accepted public import whose break requires a
blocking compatibility decision. If external distribution compatibility is
later required, that is a separate product decision; do not silently retain the
workflow to speculate about it.

## Test disposition

### Remove as obsolete retired-workflow tests

Remove these complete test modules with the code they exclusively exercise:

- `tests/unit/test_constraint_resolution_application.py`;
- `tests/unit/test_constraint_resolution_workflow.py`;
- `tests/unit/test_state_application_provenance.py`.

Their application, recovery, transition, provenance, ownership, and stale
resolution assertions are tests of the retired route. The ownership assertions
for `mechcad-resolution` are obsolete with the associated ownership entry.

### Retain and rewrite only the retired setup

Retain these accepted domain-authority regressions, but replace their use of
`ConstraintResolutionApplicationService` with direct construction of a valid
canonical `AuthoritativeParameter` fixture. The tests must continue to assert
the consuming service's actual authority boundary, not the retired application
mechanism used to seed it.

- `test_m7b1br_authority.py::test_state_resolved_authorities_produce_the_accepted_synthesis_fixture`;
- `test_m7b2a_yagi_authority.py::test_yagi_authority_uses_m6b_resolution_application_and_persisted_reload`;
- `test_m7b2b_yagi_carrier.py::state_with_authority` and the dependent
  state-backed synthesis regression.

The M7B-2A test name must be updated because it currently claims the retired
application is the authority path. Its retained assertion is the exact
authoritative parameter anchor/value/scope consumed by the Yagi service after
a persisted reload, not M6B-4C application behavior.

### Retain unchanged

Retain `test_constraint_requests.py` and the M7 anchor-map assertions in
`test_m7b1a_authority.py`, `test_m7b1br_authority.py`, and
`test_m7b2a_yagi_authority.py`. They prove the active materializer's exact
anchor/satisfaction authority.

Retain `test_constraint_resolution.py` unchanged. It covers the retained
M6B-4A typed resolution module and must not be removed as collateral F10 API
cleanup. No negative import-boundary regression is required: asserting the
absence of intentionally deleted internal modules would freeze an unsupported
implementation detail.

## Alternatives considered

1. **Direct retirement (selected):** remove all M6B-4C-local code and migrate
   only shared-authority test setup. This exactly implements the binding human
   decision and removes duplicate anchor ownership.
2. **Retain module shims:** preserve imports that immediately fail or warn. This
   would leave a public-looking but nonfunctional workflow and has no accepted
   compatibility requirement.
3. **Repair and production-wire the workflow:** retain provenance/recovery and
   fix the annotation defect. This contradicts the binding retirement decision
   and would require a new supported-contract decision.

## Non-goals

- No implementation in this design phase.
- No changes to production, tests, accepted audit/map material, or
  `docs/reconstruction/**` in this design phase.
- No new canonical mutation path, resolution gateway, agent capability, or
  automatic application of answers.
- No modification to active request discovery, gateway behavior, anchor map,
  M6B-4A resolution data, or generic ChangeEngine semantics.
- No unrelated `agents` or `changes` package API cleanup.

## Implementation verification strategy

The later, separately approved implementation plan must:

1. Verify removed modules/symbols and package exports are absent, while retained
   `ConstraintRequestMaterializer`, `constraint_resolution` exports, and agent
   gateway imports remain available.
2. Run focused request/anchor tests: `tests/unit/test_constraint_requests.py`,
   `tests/unit/test_m7b1a_authority.py`, `tests/unit/test_m7b1br_authority.py`,
   `tests/unit/test_m7b2a_yagi_authority.py`, and
   `tests/unit/test_m7b2b_yagi_carrier.py`.
3. Run focused retained resolution tests:
   `tests/unit/test_constraint_resolution.py`.
4. Run focused agent/gateway regression tests that exercise
   `ProductionApplication.run_transmission_round_trip` and constraint-request
   materialization, selected from the current suite after confirming their
   concrete file names.
5. Run `python -m compileall src` and `git diff --check`.
6. Confirm that no production source imports the retired modules or provenance
   surface, and that no retained test relies on `mechcad-resolution` ownership.

## Acceptance criteria

- The removal set contains only M6B-4C-local workflow/application/provenance
  code, its recovery helper, its ownership route, and their exports/tests.
- `ConstraintRequestMaterializer` remains the single anchor-map owner; no new
  map/helper exists.
- Active agent/gateway request discovery and all retained request/resolution
  wire/hash behavior are unchanged.
- M7 authority regressions remain and assert consumer behavior using direct,
  valid canonical-state fixtures rather than the retired workflow.
- The exact retired imports are intentionally removed with no shim; no accepted
  public import break remains unresolved.
- No production caller, test-only code, documentation history, or audit record
  is misrepresented as accepted production behavior.
- No implementation begins until this design receives user approval and a
  separate implementation plan is authorized.
