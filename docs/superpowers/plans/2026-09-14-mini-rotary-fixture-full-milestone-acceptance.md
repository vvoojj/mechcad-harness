# MINI_ROTARY_FIXTURE Full Milestone Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute and document a truthful, project-local, single-axis acceptance fixture through the maximum reachable current MechCAD M0-M13 chain.

**Architecture:** A project-local Python driver composes the existing `ProductionApplication` with project-local ownership/dependency files and stores all durable data under `projects/mini_rotary_fixture/`. The connected core follows the existing legacy M12 direct-drive route with square plate candidate CAD; independent M5.5, M11, and M13 probes remain explicitly noncanonical or separately scoped. No platform source or bridge is added.

**Tech Stack:** Python 3.11+, Pydantic v2, existing MechCAD production services, real FreeCAD where configured, optional configured OpenCode/Gmsh/CalculiX, pytest.

## Global Constraints

- Controlling authority is the current `DesignState` / trusted change contract and the accepted M13-4 baseline, not historical reconstruction.
- All canonical mutation uses `ChangeProposal` / `ChangeSet` / `ChangeEngine` under ownership policy and project lock, via `RunController` where the existing API requires it.
- Use only `ProductionApplication.create(..., ownership_path=..., dependency_path=...)` for fixture-local composition; do not change global configuration or platform source.
- The user-authoritative speed is `5.0 RPM`; the acceptance record preserves that source value, while the harness resolution record uses `0.5235987755982988 rad/s`.
- Preserve existing torque invalidation rules for force, lever arm, and safety factor. Exercise only force as the staged trigger; add no speed-to-torque dependency.
- Square top plates use existing M12 candidate CAD. M13-2 is limited to naturally representable cylindrical generated parts.
- F10 retired `ConstraintResolutionApplicationService` and `ConstraintResolutionWorkflow`. Retained typed resolution materialization does not apply a resolution record to canonical state; the generic required resolution-record-to-canonical-application edge is `MISSING`, a `PLATFORM_CAPABILITY_GAP` / `REQUIRED_CURRENT_NOT_IMPLEMENTED`.
- M12-3 source-authoritative scalars require `SourceBoundScalar` and one matching `TrustedCanonicalScalarSourceBinding` for a canonical path whose resolved record is exactly `{"value": <number>, "unit": "<unit>"}`. Tool/Evidence records are derived and cannot meet this requirement.
- Do not create an M12-to-M13 bridge, a dummy joint, a new CAD primitive, a generated candidate search, or an automatic selection/promotion path.
- Do not modify `src/mechcad_harness/**`, existing audits/specs/plans/tests, normative architecture, or reconstruction records. Do not commit or push.
- Classify every inability as `PROJECT_LOCAL_MISSING`, `EXISTING_CAPABILITY_NOT_WIRED_TO_THIS_PATH`, or `PLATFORM_CAPABILITY_GAP`; classify absent configured executables as `BLOCKED_ENVIRONMENT` in runtime evidence.

## File Structure

| File | Responsibility |
| --- | --- |
| `projects/mini_rotary_fixture/ownership.yaml` | Complete fixture-only ownership policy for every canonical path mutated by the fixture. |
| `projects/mini_rotary_fixture/dependencies.yaml` | Existing dependency rules plus fixture physical-mechanism invalidation; no speed-to-torque edge. |
| `projects/mini_rotary_fixture/acceptance.py` | Project-local staged driver, bounded probes, result collection, and append-only logging helpers. |
| `projects/mini_rotary_fixture/test_acceptance.py` | Focused tests for local authority, configuration, staged revision behavior, and report classification. |
| `projects/mini_rotary_fixture/README.md` | Purpose, authority boundaries, entrypoint, and non-goals. |
| `projects/mini_rotary_fixture/EXECUTION_LOG.md` | Append-only run evidence. |
| `projects/mini_rotary_fixture/MILESTONE_COVERAGE.md` | Initial and final M0-M13 capability/execution matrix. |
| `docs/audit/MECHCAD_MINI_ROTARY_FIXTURE_COMPLETION_REPORT.md` | New completion claim only, never independent acceptance. |

## Production Capabilities To Reuse

| Fixture path | Existing current API/path | Composition status | Planned treatment |
| --- | --- | --- | --- |
| M0-M4 | `StateManager`, `ChangeEngine`, `RunController`, `EvidenceStore` | production-composed; generic full workflow unverified | connected fixture execution |
| M5/M6B | `ProductionApplication.run_transmission_round_trip`, `ToolBroker`, `ToolEvidenceMaterializer` | production-composed | real deterministic torque/Evidence path |
| M6A | `OpenCodeAgentAdapter`, `AgentGateway`, `TransmissionToolRoundTripCoordinator` | production-composed but opt-in runtime | attempt real adapter; never credit fake |
| M7A/M8/M9/M10-1 | `realize_candidate_cad`, `evaluate_candidate`, `prove_continuous_single_axis_clearance` | production-composed and FreeCAD live-verified | core candidate/canonical execution |
| M12 | `realize_and_evaluate_revolute_drive`, `compare_candidates`, `select_candidate`, `promote_selected_candidate`, `verify_promoted_mechanism` | production-composed and live-verified | core execution |
| M13-1 | supplied interface models and candidate snapshots | production-composed, unverified live | bounded interface probe |
| M13-2 | generated cylindrical part authority/CAD | production-composed and verified | shaft/hub-only probe |
| M13-3P/M13-3/M13-4 | multi-joint bridge, selection, promotion, verification APIs | production-composed | one-joint attempt only; no bridge |
| M11 | `StructuralAnalysisService.execute(StructuralAnalysisRequest)` and structural Evidence services | production-composed and live-verified | handoff first, standalone only when source authority can be expressed |
| M5.5 | optional `GearworksTools`, `MaterialTools`, `SectionTools` registrations | `EXISTS_UNWIRED` | isolated supplemental probes |
| M6 -> M12 scalar authority | `SourceBoundScalar`, `TrustedCanonicalScalarSourceBinding`, `_source_scalar_binding_defects` | no compatible canonical representation | `PLATFORM_CAPABILITY_GAP`; stop only M12 direct-drive-dependent stages |

## Task 1: Fixture Scaffold And Capability Inventory

**Files:**
- Create: `projects/mini_rotary_fixture/README.md`
- Create: `projects/mini_rotary_fixture/EXECUTION_LOG.md`
- Create: `projects/mini_rotary_fixture/MILESTONE_COVERAGE.md`
- Create: `projects/mini_rotary_fixture/acceptance.py`
- Create: `projects/mini_rotary_fixture/test_acceptance.py`

**Consumes:** current architecture bundle, capability reference, accepted M9/M10/M11/M12-6/M13-4 audits, and current source APIs.

**Produces:** a fixture-local result schema, UTC log append helper, and an initial matrix containing every requested M0-M13 row.

- [ ] Write focused tests asserting that the matrix contains every required row and separately records capability existence, production composition, live execution, outcome, evidence, and blocker reason.
- [ ] Run `py -3 -m pytest projects/mini_rotary_fixture/test_acceptance.py -q`; expect failure because the project driver and matrix do not exist.
- [ ] Implement small immutable local result records and `append_execution_log(...)`; every log entry includes stage, source binding, API, command, provider identity, outcome, and classification.
- [ ] Write the initial matrix from current implementation truth. Use allowed capability statuses only, use `NOT_APPLICABLE_SINGLE_AXIS_FIXTURE` for incompatible multi-joint-only operations, and reserve PASS/FAIL/BLOCKED/NOT_APPLICABLE for actual execution.
- [ ] Run the focused test again; expect PASS.

## Task 2: Canonical Authority, Project Configuration, And N1

**Files:**
- Create: `projects/mini_rotary_fixture/ownership.yaml`
- Create: `projects/mini_rotary_fixture/dependencies.yaml`
- Modify: `projects/mini_rotary_fixture/acceptance.py`
- Modify: `projects/mini_rotary_fixture/test_acceptance.py`

**Consumes:** `ProductionApplication.create`, `StateManager.create_project`, `config/ownership.yaml`, and `config/dependencies.yaml`.

**Produces:** N1 `DesignState` and a `ProductionApplication` using only fixture-local configuration.

- [ ] Write tests that create N1 with the 4 N force, 0.025 m arm, factor 2, 24 V, 5 mm clearance, synthetic actuator/interface facts, the exact `REQ-TRANSMISSION-OUTPUT-SPEED` canonical Requirement anchor, no output-speed `AuthoritativeParameter`, and the exact fixed/rotary geometry authority. The N1 anchor exists only for current resolution binding and must not pre-populate the user-authoritative 5.0 RPM value.
- [ ] Write tests that prove local dependency configuration preserves all three current torque rules (`REQ-TORQUE-FORCE`, `REQ-TORQUE-ARM`, `REQ-TORQUE-SAFETY`) and contains no output-speed torque rule.
- [ ] Inspect the current global ownership file before writing fixture configuration. `ProductionApplication.create` calls `OwnershipPolicy.from_file(ownership_path)` directly and does not merge global rules. Reproduce only current ownership rules required by canonical mutations the fixture can truthfully execute, including `/requirements/*`, `/physical_mechanisms/*`, and each other actually mutated canonical path. Do not add `/authoritative_parameters -> mechcad-resolution` merely to emulate the retired M6B-4C application path; N2/N3 remain stopped as `PLATFORM_CAPABILITY_GAP` / `REQUIRED_CURRENT_NOT_IMPLEMENTED`.
- [ ] Implement `create_fixture_application(workspace)` using `ProductionApplication.create(workspace, "mini_rotary_fixture", adapter, ownership_path=..., dependency_path=...)`, then persist N1 only with `StateManager.create_project` bootstrap.
- [ ] Run focused tests; expect N1 revision 1, deterministic state hash, and successful reload/current identity.

## Task 3: M4-M6 Staged Speed, Torque Evidence, And Force Invalidation

**Files:**
- Modify: `projects/mini_rotary_fixture/acceptance.py`
- Modify: `projects/mini_rotary_fixture/test_acceptance.py`

**Consumes:** `RunController`, `TransmissionToolRoundTripCoordinator`, `ConstraintResolutionMaterializer`, and current trusted change machinery where an existing application path provides it.

**Produces:** N1 torque evidence and a documented determination whether the required N2/N3 canonical-resolution chain exists.

- [ ] Write tests that create a state-bound run/task and execute the current exact tool `mechcad-calc-torque@1.0` through `ToolBroker`; assert N1 output is `nominal_torque_nm=0.1` and `design_torque_nm=0.2`.
- [ ] Verify whether a current trusted resolution-record-to-canonical-state application path exists. F10 reconciliation established that the former application service/workflow was retired and no substitute is present.
- [ ] Record N2/N3 as blocked `PLATFORM_CAPABILITY_GAP` / `REQUIRED_CURRENT_NOT_IMPLEMENTED`; do not compose a fixture-local bridge, restore retired code, or handwrite a `ChangeProposal` substitute.
- [ ] Retain N1 torque Evidence as a bounded successful probe. Do not claim N2 currentness or N3 force invalidation/recomputation without the required canonical application edge.
- [ ] Attempt the real `OpenCodeAgentAdapter` only with configured opt-in runtime/credentials. Record PASS only for a real adapter response; record `BLOCKED_ENVIRONMENT` for absent runtime/credentials and never substitute `FakeAgentAdapter`.

## Task 4: M12-3 Canonical Scalar Authority Gate

**Files:**
- Modify: `projects/mini_rotary_fixture/acceptance.py`
- Modify: `projects/mini_rotary_fixture/test_acceptance.py`
- Modify: `projects/mini_rotary_fixture/MILESTONE_COVERAGE.md`

**Consumes:** `DesignState`, `SourceBoundScalar`, `TrustedCanonicalScalarSourceBinding`, `RevoluteDriveEngineeringRequirements`, and `revolute_drive.service._source_scalar_binding_defects` behavior.

**Produces:** an explicit decision on whether the M12 direct-drive path can obtain source-authoritative scalars without a fixture-only bridge.

- [ ] Inspect every current domain-neutral `DesignState` field and its serialized wire shape before constructing M12 requirements. A usable path must resolve to exactly `{"value": <number>, "unit": "<unit>"}` and be bindable in `CandidateSourceBinding.consumed_authority` with matching record hash and `TrustedCanonicalScalarSourceBinding`.
- [ ] Record the current finding: `requirements` provide `{id, name, description}`, `components` and other generic collections have no scalar record, and `authoritative_parameters` use typed `AuthoritativeValue` payloads such as `{kind, value_rad_s}`. None is the required domain-neutral `{value, unit}` scalar record.
- [ ] Write a focused negative test that executes `_source_scalar_binding_defects` with a source-bound scalar targeting the fixture requirement record and asserts the record is rejected for not being exactly `{value, unit}`. This is production-boundary validation evidence, not a fabricated authority path. Do not introduce Yagi fields, arbitrary dict buckets, or any Evidence-to-state bridge.
- [ ] Record `PLATFORM_CAPABILITY_GAP` and stop the M12 direct-drive-dependent branch when no compatible path exists. The exact limitation is `RevoluteDriveEngineeringRequirements.trusted_source_scalar_bindings` plus `_source_scalar_binding_defects`; project-local ownership/dependency files govern mutation/invalidation only and cannot alter `DesignState` wire shape or M12 validation semantics.
- [ ] Record the smallest unimplemented reusable extension: a domain-neutral typed canonical scalar-value collection with `{value, unit}` records, ownership, dependency rules, and a trusted authority-to-scalar admission path usable by M12. Do not implement it.

## Task 5: Conditional Source CAD, Imported Actuator, And Direct-Drive Candidates

**Files:**
- Modify: `projects/mini_rotary_fixture/acceptance.py`
- Modify: `projects/mini_rotary_fixture/test_acceptance.py`

**Consumes:** `FreeCADBackend.generate_program`, `ArtifactStore`, `ImportedCadComponent`, `CandidateSynthesisRequest`, `CandidateSynthesisPolicy`, `RevoluteDriveTemplateInput`, `RevoluteDriveEngineeringRequirements`, and `ProductionApplication.realize_and_evaluate_revolute_drive`.

**Produces:** two source-bound M12 direct-drive candidates sharing all authority except `top_plate_side_mm`, only if Task 4 finds a compatible existing canonical scalar source.

- [ ] Write tests that require a trusted synthetic actuator STEP to be created by the accepted FreeCAD/artifact route, byte-verified through `ArtifactStore`, and resolved as `ImportedCadComponent`; no arbitrary STEP path may enter a candidate.
- [ ] Implement source CAD for only required authority geometry: actuator envelope, cylindrical shaft/hub/support components where the current template needs them, and legacy M12 plate representations for the two square plates. Realize the fixed base and wall as one synthetic, byte-verified multi-solid `motor-mount` STEP artifact through existing `CadPartProgram` / `CadAssemblyProgram` generic plate operations and placements; do not add a wall component role or CAD primitive.
- [ ] Implement two explicit candidate builders only if Task 4 succeeds. Each must include all current direct-drive roles, exactly two supports, one +Z output joint, declared design variables, same source revision/hash, and exact `SOURCE_AUTHORITY` scalar paths/record hashes/trusted bindings resolved from canonical `DesignState`; fresh torque Evidence may be recorded alongside the source chain but is not scalar authority. Include all required hard-admission policy entries.
- [ ] Run focused tests asserting motor continuous-torque, speed-range, voltage where current model supports it, shaft equilibrium/stress/admissibility, physical topology, and joint realization. Assert candidate A/B differ only in `top_plate_side_mm`.

## Task 6: Conditional Candidate CAD, Complete M10-1 Evaluation, Comparison, And Selection

**Files:**
- Modify: `projects/mini_rotary_fixture/acceptance.py`
- Modify: `projects/mini_rotary_fixture/test_acceptance.py`

**Consumes:** `CandidateCadRealizationRequest`, `CandidateCadInstanceMapping`, `CandidateM10EvaluationScope`, `CandidateM10Binding`, `CandidateCollisionPairInventory.complete_for`, `CandidateM10EvaluationRequest`, `ProductionApplication.realize_candidate_cad`, `evaluate_candidate`, `compare_candidates`, and `select_candidate`.

**Produces:** real candidate FCStd/STEP artifacts, complete pair inventories, home checks, discrete checks where available, 0..360 degree continuous proof records, two immutable evaluations, comparison, and explicit selection, only if Task 4 permits candidate construction.

- [ ] Write tests that reject omitted physical pairs and assert all moving/stationary constituent pairs are classified. The required `payload-body` / `motor-mount` pair measures the square plate against the base-plus-wall compound; include every other current template-required pair.
- [ ] Implement candidate CAD mappings with the supported fidelity classifications. Preserve the square plate as legacy M12 candidate CAD, not M13-2; use fixed wall/base and output-rigid moving group truthfully.
- [ ] Run real FreeCAD candidate execution when configured. Capture FCStd/STEP artifact IDs, hashes, locations, fresh reload, `freecad-transient-exact` provider, `common().Volume`, `distToShape()`, and runtime provenance.
- [ ] Execute exact home checks, discrete samples when supported, and `ContinuousSingleAxisClearanceProof` via `evaluate_candidate` for each candidate over 0..360 degrees at 5 mm. Accept only `VERIFIED_CLEAR` as feasible.
- [ ] Compare only `verified_clearance_lower_bound_mm`, record ties if real values tie, and explicitly call `select_candidate` with the recorded rationale. Never choose automatically.

## Task 7: Conditional Legacy Promotion And Fresh Canonical Verification

**Files:**
- Modify: `projects/mini_rotary_fixture/acceptance.py`
- Modify: `projects/mini_rotary_fixture/test_acceptance.py`

**Consumes:** `CandidatePromotionRequest`, `CandidatePromotionPolicy`, `PromotionClassification`, `ProductionApplication.promote_selected_candidate`, and `verify_promoted_mechanism`.

**Produces:** N4 canonical physical mechanism, decision/result artifacts, fresh canonical reconstruction/CAD/M10 verification, and M11 eligibility assessment, only if Task 4 permits the M12 branch.

- [ ] Write tests that reject promotion without current feasible selection and that confirm no candidate CAD/M10 identity is reused as canonical proof.
- [ ] Construct classifications for candidate properties, geometry source, design variables, physical instances, connections, and joint bindings; construct one explicit `CandidatePromotionRequest` for the selected candidate.
- [ ] Call `promote_selected_candidate`, capture the trusted run/ChangeSet/receipt/manifests, and assert one N3 to N4 canonical mutation at `/physical_mechanisms/<id>`.
- [ ] Call `verify_promoted_mechanism`; assert fresh canonical reconstruction, CAD, and required M10 verification have source N4/hash bindings and distinct candidate/canonical identities.
- [ ] Reload the application from scalar durable locators and rerun canonical verification to exercise the recovery/reload boundary.

## Task 8: Bounded M5.5, M11, And M13 Supplemental Probes

**Files:**
- Modify: `projects/mini_rotary_fixture/acceptance.py`
- Modify: `projects/mini_rotary_fixture/test_acceptance.py`

**Consumes:** explicit optional tool registrations for `GearworksTools`, `MaterialTools`, and `SectionTools`; M11 handoff service; `StructuralAnalysisService.execute`; M13 supplied-interface/generated-part/multi-joint APIs.

**Produces:** isolated supplemental results that cannot change core design authority.

- [ ] Attempt gear provider input `(module=1.0 mm, driver_teeth=20, driven_teeth=40, pressure_angle=20 deg)` only through explicit existing registration. If it produces STEP, publish/reload it as a noncanonical artifact; otherwise record optional registration, unavailable environment, unwired status, or failure exactly.
- [ ] Attempt one material lookup and one simple rectangular section calculation through their optional existing registrations. Store their actual typical/preliminary authority and keep them separate from M11 Evidence.
- [ ] If Task 7 produced a promotion, request post-promotion M11 eligibility using the selected canonical top plate mapping. If `ELIGIBLE`, use the ordinary structural path; if `NOT_ELIGIBLE` or `UNRESOLVED`, attempt a separately labelled `M11_STANDALONE_SUBSYSTEM_PROBE` only when existing source-bound single-solid authority/semantic regions can express central support and edge load. If Task 4 blocked M12, record `POST_PROMOTION_M11_HANDOFF` as blocked by that dependent branch and assess only the separate standalone probe. Do not bridge candidates to M11.
- [ ] Attempt M13-1 typed shaft/mount interface authority. Attempt M13-2 only with cylindrical shaft/hub generated-part authority/CAD. Attempt M13-3P/M13-3/M13-4 only if current one-joint models accept the topology; otherwise record `NOT_APPLICABLE_SINGLE_AXIS_FIXTURE` or the precise unwired gap. Do not use the square plate as M13-2 and do not add an M12-to-M13 mapping.

## Task 9: Final Documentation, Completion Claim, And Verification

**Files:**
- Modify: `projects/mini_rotary_fixture/README.md`
- Modify: `projects/mini_rotary_fixture/EXECUTION_LOG.md`
- Modify: `projects/mini_rotary_fixture/MILESTONE_COVERAGE.md`
- Create: `docs/audit/MECHCAD_MINI_ROTARY_FIXTURE_COMPLETION_REPORT.md`

**Consumes:** all durable records and exact command results created by Tasks 1-8.

**Produces:** final core verdict, final coverage verdict, completion claim, and no independent-acceptance language.

- [ ] Append every significant attempt and remediation in time order; retain failures, skips, timeouts, and blocks.
- [ ] Complete the matrix rows requested by the fixture: M0, M1, M2, M3, M4, M5, M5.5A/B/C, M6A/B, M7A/B/C/D/E, M8B/C, M9, M10-1/2/3/4, M11, M12-1 through M12-6, M13-1/2/3P/3/4E/4P/4. Name `MECHCAD_M10_SYSTEM_ACCEPTANCE.md` separately as the accepted M10 closure record, not as a fixture milestone row. For each row, preserve separate existence, composition, execution, outcome, exact evidence, and reason.
- [ ] Write the completion claim with current baseline inspected, authority, revision chain, speed conversion, torque Evidence/invalidation, agent status, artifacts, clearance values, selection/promotion/canonical results, M11 handoff/probe result, provider probes, commands, test results, worktree status, and all gaps.
- [ ] Run `py -3 -m pytest projects/mini_rotary_fixture/test_acceptance.py -q` first, then exact existing predecessor gates selected for each invoked production surface. Run live tests only with the user-authorized configured runtime.
- [ ] Run `py -3 -m compileall -q projects/mini_rotary_fixture` and `git diff --check`; record exact output, including pre-existing unrelated diagnostics, without modifying unrelated worktree content.
- [ ] Set core verdict only after checking the complete connected N1 -> N2 -> N3 -> Task 4 authority gate -> candidates -> CAD/M10 -> comparison -> explicit selection -> promotion -> fresh canonical verification chain. If N2/N3 or Task 4 is blocked, report `MINI_ROTARY_FIXTURE_CORE_REJECTED` with the exact platform gap; end the completion claim with no independent acceptance marker.

## Stop Conditions

- Stop only the dependent branch when a required current API cannot express its authority or binding. Continue independent M5.5, M6A, M10-v2, M11, and M13 probes.
- Stop the core path as `MINI_ROTARY_FIXTURE_CORE_REJECTED` if trusted canonical mutation, fresh torque Evidence, the M12 canonical-scalar gate, candidate feasibility, explicit selection/promotion, or fresh canonical verification cannot complete truthfully.
- The current M6 -> M12 scalar path is `PLATFORM_CAPABILITY_GAP`: M12 `RevoluteDriveEngineeringRequirements` requires `TrustedCanonicalScalarSourceBinding`, and `_source_scalar_binding_defects` requires an exact canonical `{value, unit}` source record. Current generic canonical records are descriptions/metadata, while `AuthoritativeParameter.value` is a typed `AuthoritativeValue`, not that record; Evidence is derived/noncanonical. Project-local ownership/dependency composition cannot create a compatible model or validation boundary. The smallest reusable extension is the typed domain-neutral scalar authority described in Task 4; it is not part of this fixture.
- Classify any other inability to express a required contract as `PLATFORM_CAPABILITY_GAP`; a present but non-default callable service as `EXISTING_CAPABILITY_NOT_WIRED_TO_THIS_PATH`; missing fixture driver/config/docs/tests as `PROJECT_LOCAL_MISSING`.
- Do not repair platform source, accepted fixtures, or global configuration to pass any stage.

## Verification Gates

1. Project-local tests before each implementation stage.
2. Focused existing tests for changed/exercised boundaries: state/change/dependency/runs/tools/agents, candidate direct-drive/CAD/M10/promotion, M13 probes, and structural path only if executed.
3. Live FreeCAD/OpenCode/Gmsh/CalculiX execution only where configured and actually requested by the fixture.
4. Final `compileall` and `git diff --check` with exact retained output.

## Plan Self-Review

- Spec coverage: Tasks 1-9 cover authority, staged revisions, the M12 scalar gate, conditional CAD/M10/M12 core, independent provider/M11/M13 probes, documentation, and final verification.
- Cross-path boundary: Tasks 5-8 explicitly retain M12 square-plate CAD and prohibit an M12-to-M13 bridge.
- Precision: the plan distinguishes capability existence, default production composition, and actual execution; F10's retired workflow is not treated as a callable unwired service.
- Protected surfaces: all planned implementation files are new project-local files or the new completion claim; commits and platform edits are prohibited.
