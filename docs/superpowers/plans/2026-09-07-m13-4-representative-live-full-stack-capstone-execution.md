# M13-4 Representative Live Full-Stack Capstone Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute one generic, source-bound, live FreeCAD M13-4 capstone through candidate CAD, candidate M10-3, root-composed selection and promotion, ChangeEngine revision N+1, serialized canonical restart, fresh canonical M10-3, and focused M10-4 evidence without changing production semantics.

**Architecture:** The acceptance test builds a six-constituent physical fixture from accepted M13-1 supplied-interface and M13-2 generated-part authority, then enters every candidate and promotion operation through `ProductionApplication.create()`. After promotion, only durable scalar locators cross a fresh-process-equivalent serialization boundary; canonical CAD, bridge, inventory, M10 request/result, and evidence are reconstructed from persisted `DesignState` N+1 and trusted artifacts.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, `StateManager`, `ArtifactStore`, `EvidenceStore`, `ChangeEngine`, `ProductionApplication`, FreeCAD 1.1.3 or the runtime version discovered by `discover_freecad()`, and the existing exact transient FreeCAD provider.

## Global Constraints

- This plan is acceptance-only; it does not authorize production, M10, M11, M12, M13-1, M13-2, M13-3, M13-4E, or M13-4P semantic changes.
- Preserve the historical `M13_4_BLOCKED_BY_ARCHITECTURE_GAP` disposition as history; the short addendum in the M13-4 specification records the accepted M13-4P composition closure without rewriting that history.
- Current authorization remains `M13_4_MAY_RESUME = NO` and `ROTATOR_V2_MAY_RESUME = NO` until an authorized M13-4 execution records its own result.
- Do not use `projects/rotator_v2`, the `5840-31ZY` package, AZ/EL authority, Rotator, antenna, Yagi, pan-tilt, or equivalent domain terminology in the fixture, test names, report, or project files.
- Use exactly three explicit physical bodies: `R -> J1 -> A -> J2 -> B`.
- Use exactly six concrete physical constituents: `motor-r`, `frame-r`, `shaft-a`, `hub-a`, `shaft-b`, and `hub-b`.
- Use no implicit body membership, fixed relation, joint, axis, or degree of freedom.
- Use the accepted `PhysicalMechanismRealization` v2, `KinematicModelV2`, `MultiJointVerificationConfigurationSet@1`, complete physical pair universe, and `accepted-semantic-home@1` semantics.
- Use M10-3 only as discrete evaluation; every ordinary M10-3 result must retain `continuous_path_verified = False`.
- Use M10-4 only for the one explicit typed piecewise-linear path; do not claim arbitrary trajectory, configuration-space, or whole-mechanism safety.
- Use only existing `ArtifactStore` and `EvidenceStore`; do not create a result database, ambient candidate cache, or alternate provider.
- A supplied component may use the accepted generic M13-2 fixture authority, but the report must call it accepted fixture authority and must not represent the synthetic fixture record as supplier or manufacturer fact.
- The static on-disk `projects/PRJ-M13-2-T7/runs/INPUT/artifacts/ART-MOTOR/motor.step` is not a live input: its metadata identifies producer `test` and its recorded size is 13 bytes. Do not use it as real STEP geometry. Recreate the accepted M13-2 source fixture through the existing real `FreeCADBackend.generate_program()` path.
- Required live FreeCAD execution crosses `MECHCAD_FREECADCMD` and must report the actual executable, FreeCAD version, backend version, provider version, and execution mode.
- A missing FreeCAD runtime is an environment result, not a test skip and not a PASS. The final planning disposition in that case is `M13_4_ENVIRONMENT_BLOCKED_PLAN_READY`.
- Full-suite execution must use a timeout ceiling of at least 6000 seconds.
- Do not update expected JSON, hashes, goldens, or predecessor evidence.
- Do not commit, tag, push, or release.

## File Map

- Create `tests/integration/m13_4_acceptance_fixtures.py`: generic source authority, generated specifications, six-constituent candidate, placement derivations, physical body/joint records, complete pair policy, and explicit configuration set. This module must contain no domain-specific names.
- Create `tests/integration/test_m13_4_full_stack_acceptance.py`: one staged live capstone test plus bounded stale-authority negatives and static forbidden-scope assertions. It must enter through `ProductionApplication.create()` and must not construct the internal selection or promotion service graph.
- Create `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md` only after a live run has produced all required evidence. If runtime discovery fails, create an environment-blocked report instead and do not write the success marker.
- Modify `docs/superpowers/specs/2026-09-06-m13-4-representative-live-full-stack-capstone.md` only by appending the short historical-unblock addendum specified in Task 0. Do not rewrite the original blocker text or disposition.
- Do not modify any file under `src/`.

## Acceptance State And Gates

The live success marker is permitted only if every stage below passes:

```text
M13_4_REPRESENTATIVE_LIVE_FULL_STACK_CAPSTONE_VERIFIED
```

The environment-blocked result is:

```text
M13_4_ENVIRONMENT_BLOCKED_PLAN_READY
```

The generic fixture's structural M11 status is always:

```text
M11_STATUS = UNRESOLVED
M11_ELIGIBLE = False
```

### Task 0: Record Historical Unblock And Gate The Runtime

**Files:**
- Modify: `docs/superpowers/specs/2026-09-06-m13-4-representative-live-full-stack-capstone.md` by appending only the historical addendum below.
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py` in the future implementation.

**Interfaces:**
- Consumes: `docs/audit/MECHCAD_M13_4P_INDEPENDENT_ACCEPTANCE.md`, `docs/audit/MECHCAD_M13_4E_R12_INDEPENDENT_REAUDIT.md`, and `discover_freecad()`.
- Produces: a truthful runtime record and a hard precondition for all later tasks.

- [ ] Append this exact addendum after the existing M13-4 self-review. It records the historical fact without changing the original blocker wording or claiming M13-4 acceptance:

```markdown
## Historical Unblock Addendum (2026-09-07)

The former production-composition gap described above was independently closed by
the accepted M13-4P reconciliation. `M13_4P_INDEPENDENT_ACCEPTED` verifies that
`ProductionApplication` now exposes the typed multi-joint selection, promotion,
and durable receipt-verification delegations while preserving the accepted
M13-4E lifecycle and legacy promotion route.

This addendum does not rewrite the historical disposition, authorize Rotator V2,
or claim M13-4 acceptance. The remaining M13-4 execution gate is the required
real FreeCAD runtime and all acceptance obligations in the execution plan. Until
those obligations pass, `M13_4_MAY_RESUME = NO` and no success marker is valid.
```

- [ ] Before any capstone test, run the runtime discovery command from the repository root:

```powershell
py -3 -c "from mechcad_harness.backends.freecad import discover_freecad; d=discover_freecad(); print({'available': d.available, 'executable': d.executable, 'version': d.version, 'importable': d.importable, 'execution_boundary': d.execution_boundary})"
```

Expected positive conditions: `available` is `True`, `executable` is a
nonblank absolute path, and `execution_boundary` is nonblank. The version probe
may report `None` until the command-line version script runs; the final report
must record the actual resolved value.

The current observed shape is:

```text
{'available': False, 'executable': None, 'version': None, 'importable': False, 'execution_boundary': None}
```

- [ ] If discovery is unavailable, do not run the capstone, do not mark the test skipped, and stop with `M13_4_ENVIRONMENT_BLOCKED_PLAN_READY`. Record `MECHCAD_FREECADCMD`, executable existence, discovery output, and the unchanged production/test worktree scope in the environment-blocked report.
- [ ] If discovery is available, run the actual version probe and record the backend/provider identity before the fixture is built:

```powershell
py -3 -c "from mechcad_harness.backends.freecad import FreeCADBackend, discover_freecad; d=discover_freecad().require_available(); b=FreeCADBackend(); print({'executable': d.executable, 'discovery_version': d.version, 'backend_version': b.provenance().adapter_version, 'library': b.provenance().library_name, 'library_version': b.provenance().library_version, 'execution_mode': d.execution_boundary})"
```

Expected positive shape has nonblank executable, backend version, library name/version, and execution mode. Do not substitute the historical `1.1.3` claim when the live probe reports another version.

### Task 1: Create The Generic Fixture Support Boundary

**Files:**
- Create: `tests/integration/m13_4_acceptance_fixtures.py`
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`

**Interfaces:**
- Consumes: `ProductionApplication`, `ProductionStateBinding`, accepted M13-2 fixture authority values, generated-part models, M13-3 physical models, and M13-3P v2 kinematic models.
- Produces: the following typed support records for the integration test:

```python
@dataclass(frozen=True)
class M134Fixture:
    application: ProductionApplication
    source: ProductionStateBinding
    supplied_artifact: EngineeringArtifact
    specifications: tuple[ComponentSpecificationSnapshot, ...]
    candidate: MechanicalDesignCandidate
    synthesis_request: CandidateSynthesisRequest
    synthesis_policy: CandidateSynthesisPolicy
    cad_request: CandidateCadRealizationRequest
    multi_joint_request: CandidateMultiJointM10EvaluationRequest
    m12_result: RevoluteDriveAdmissibilityResult
```

```python
def build_m134_fixture(tmp_path: Path) -> M134Fixture:
    """Return the fully validated source-bound candidate fixture."""
    raise NotImplementedError

def build_m134_application(tmp_path: Path) -> ProductionApplication:
    """Return the production-composed application for the fixture project."""
    raise NotImplementedError

def build_m134_configuration_set(model: KinematicModelV2) -> MultiJointVerificationConfigurationSet:
    """Return the four explicit ordered configurations for the model."""
    raise NotImplementedError

def build_m134_pair_bindings(candidate: MechanicalDesignCandidate) -> tuple[PhysicalPairClassificationBinding, ...]:
    """Return the canonicalized complete 15-pair physical policy."""
    raise NotImplementedError
```

Each helper must return fully materialized typed records; no helper may return
`None` or an unvalidated dictionary.

- [ ] Keep the helper boundary generic and explicit. It may import small accepted predecessor helpers for record construction, but it must not call `test_m13_3p_live_grouped_body_freecad._fixture()` as the capstone fixture, because the capstone must combine source-bound M13-1/M13-2 authority with the M13-3P body topology rather than rename that test.
- [ ] Add a fixture-local test that asserts the six IDs, three body IDs, two joint IDs, complete pair count, and four explicit configuration commands before any CAD or M10 execution.
- [ ] Run that fixture-local test with:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k fixture_shape
```

Expected output is one passed test and zero skips when the real runtime precondition from Task 0 is satisfied. The test must fail with an environment message rather than skip when the precondition is absent.

### Task 2: Reuse Accepted M13-1/M13-2 Source Authority

**Files:**
- Modify: `tests/integration/m13_4_acceptance_fixtures.py`
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`

**Interfaces:**
- Consumes: `FreeCADBackend.generate_program()`, `RotationalShaftInterface`, `SuppliedComponentReferenceFrame`, `SuppliedComponentInterfaceDefinition`, `ArtifactStore`, and `StateManager`.
- Produces: one real, verified imported source artifact and a source-bound `ComponentSpecificationSnapshot`.

- [ ] Create a source project with `DesignState` revision 1 and capture `ProductionStateBinding` using `application.load_state()`.
- [ ] Generate the accepted generic source artifact through the existing M13-2 program shape, not by writing bytes directly:

```python
program = CadPartProgram(
    part_id="m13-2-supplied-motor",
    operations=(
        BasePlateOperation(
            operation_id="motor-plate",
            length_mm=30.0,
            width_mm=30.0,
            thickness_mm=5.0,
        ),
    ),
)
generated = FreeCADBackend().generate_program(
    program,
    application.state_manager.workspace,
    project_id=source.project_id,
    run_id="INPUT",
    revision=source.revision,
    state_hash=source.state_hash,
)
artifact = generated.step
```

- [ ] Verify the source artifact with `ArtifactStore.read_verified_strict(artifact.artifact_id, expected_type=ArtifactType.STEP, expected_hash=artifact.sha256)`, verify the actual file SHA-256, verify the FreeCAD backend provenance, and verify `generated.step_verification.shape_valid is True`, `solid_count == 1`, and the accepted `30 x 30 x 5` source dimensions.
- [ ] Reuse the accepted M13-2 authority values from `tests/integration/test_m13_2_acceptance_live.py` without adding supplier claims:
  - supplied interface ID: `output-shaft`;
  - axis point fact: `(1.0, 2.0, 3.0)` mm;
  - axis direction fact: `(0.0, 0.0, 1.0)`;
  - nominal shaft diameter fact: `10.0` mm;
  - usable engagement fact: `20.0` mm;
  - supplied frame ID: `motor-output-frame`;
  - frame origin fact: `(100.0, 100.0, 3.0)` mm;
  - frame orientation fact: `(1.0, 0.0, 0.0, 0.0)`.
- [ ] Bind the interface and frame to the actual generated artifact's ID/hash and the source specification's exact geometry reference. Use accepted M13-1 evidence replay and `require_authoritatively_consumable_interface` before extracting any axis or frame.
- [ ] In the acceptance report, describe this record as `accepted generic M13-2 fixture authority`; do not call its `vendor:motor` test identity a supplier or manufacturer fact.
- [ ] Verify that the source revision, state hash, artifact ID, artifact SHA-256, interface hash, frame hash, and accepted evidence IDs are captured as explicit scalar report values.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k supplied_authority
```

Expected output is one passed test and zero skips. The test must fail closed if the artifact bytes, source binding, interface hash, frame hash, or accepted evidence binding changes.

### Task 3: Build The Six-Constituent Candidate And Physical Topology

**Files:**
- Modify: `tests/integration/m13_4_acceptance_fixtures.py`
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`

**Interfaces:**
- Consumes: the Task 2 supplied specification, `SolidCircularShaftSpecification`, `CylindricalHubSpecification`, `RectangularFrameMemberSpecification`, `GeneratedPlacementDerivation`, `PhysicalMechanismRealization`, and M13-3 physical axis-source models.
- Produces: a deterministic `MechanicalDesignCandidate` with complete physical v2 authority.

- [ ] Define exactly three generated specification records and reuse them by reference for multiple physical instances:
  - `shaftdefinition`: solid circular shaft, diameter `12.5` mm, length `40.0` mm;
  - `hubdefinition`: cylindrical hub, outer diameter `30.0` mm, length `50.0` mm, input bore `10.5` mm from supplied diameter `10.0` plus declared clearance `0.5`, and output bore `12.5` mm from the selected shaft diameter;
  - `framedefinition`: rectangular frame member, length `60.0` mm, width `20.0` mm, height `10.0` mm.
- [ ] Bind every field to `GeneratedAuthorityInput` and `GeneratedPartFieldBinding`. Use only accepted design selections and the existing M13-1 interface fact locator for the hub input bore rule. Every generated field must pass `compile_generated_part()` replay.
- [ ] Create exactly these components:

```text
motor-r    supplied component, role ACTUATOR
frame-r    generated rectangular frame member, role MOUNT_OR_SUPPORT
shaft-a    generated shaft, role SHAFT
hub-a      generated hub, role HUB_OR_COUPLING
shaft-b    generated shaft, role SHAFT
hub-b      generated hub, role HUB_OR_COUPLING
```

- [ ] Create explicit body bindings:

```text
R = (motor-r, frame-r), reference motor-r
A = (shaft-a, hub-a), reference shaft-a
B = (shaft-b, hub-b), reference shaft-b
```

Use root body ID `R`, root binding hash from `physical_kinematic_root_hash("R")`, and no fourth body or implicit fixed relation.
- [ ] Create two explicit connections and two explicit revolute bindings:

```text
J1: motor-r/output-shaft -> shaft-a/shaftdefinition:shaft
    axis source: supplied motor-r/output-shaft
    parent body: R, child body: A, axis sign +1, limits -90..90 degrees

J2: hub-a/hubdefinition:bore:output:far -> shaft-b/shaftdefinition:shaft
    axis source: generated hub-a output-bore far interface
    parent body: A, child body: B, axis sign +1, limits -90..90 degrees
```

Both joints use `PhysicalJointMotionMode.BOUNDED`, explicit `PhysicalAxisOwnerEndpoint.PARENT`, exact connection correspondence, and `zero_reference_semantics="accepted-semantic-home@1"`.
- [ ] Add `JointPhysicalRealizationBinding` records for both joints with explicit driven instance, realization component IDs, connection IDs, axis frame references, and no fabricated load-path metadata.
- [ ] Create the placement derivation chain with no raw generated-member placement variables:
  - `place-frame-r`: `frame-generated-placement@1` from the accepted motor output frame to `framedefinition:frame`, target-owned axial offset `5.0` mm and target-frame `+z` clocking `15.0` degrees;
  - `place-shaft-a`: `coaxial-generated-placement@1` from `motor-r/output-shaft` to `shaftdefinition:shaft`;
  - `place-hub-a`: coaxial from `shaft-a/shaftdefinition:shaft` to `hubdefinition:bore:input:near`, target-owned axial offset `2.0` mm;
  - `place-shaft-b`: coaxial from `hub-a/hubdefinition:bore:output:far` to `shaftdefinition:shaft`;
  - `place-hub-b`: coaxial from `shaft-b/shaftdefinition:shaft` to `hubdefinition:bore:input:near`, target-owned axial offset `2.0` mm.
- [ ] Use `placement_derivations_hash()` and assert a non-identity derivation exists. The placement chain must be acyclic and each derivation dependency must have exact instance continuity.
- [ ] Define the complete 15-pair universe exactly once. Use `SAME_RIGID_GROUP_EXCLUDED` for `frame-r/motor-r`, `hub-a/shaft-a`, and `hub-b/shaft-b`, each with reason `same explicit rigid body`. Use `INTENDED_CONTACT_EXCLUDED` for `hub-a/shaft-b` and `motor-r/shaft-a`, with reasons naming the explicit J2/J1 connection. Use `CHECK_CLEARANCE` with no reason for the remaining ten cross-body pairs:

```text
frame-r/hub-a       CHECK_CLEARANCE
frame-r/hub-b       CHECK_CLEARANCE
frame-r/motor-r     SAME_RIGID_GROUP_EXCLUDED
frame-r/shaft-a     CHECK_CLEARANCE
frame-r/shaft-b     CHECK_CLEARANCE
hub-a/hub-b         CHECK_CLEARANCE
hub-a/motor-r       CHECK_CLEARANCE
hub-a/shaft-a       SAME_RIGID_GROUP_EXCLUDED
hub-a/shaft-b       INTENDED_CONTACT_EXCLUDED
hub-b/motor-r       CHECK_CLEARANCE
hub-b/shaft-a       CHECK_CLEARANCE
hub-b/shaft-b       SAME_RIGID_GROUP_EXCLUDED
motor-r/shaft-a     INTENDED_CONTACT_EXCLUDED
motor-r/shaft-b     CHECK_CLEARANCE
shaft-a/shaft-b     CHECK_CLEARANCE
```

Canonical pair ordering may reorder each pair lexically; the semantic pair set above must remain identical. The check scope must contain exactly the ten `CHECK_CLEARANCE` pairs, including root/articulated and articulated/articulated pairs.
- [ ] Define the explicit ordered configuration set:

```text
cfg0: J1=0.0,  J2=0.0
cfg1: J1=15.0, J2=0.0
cfg2: J1=0.0,  J2=15.0
cfg3: J1=15.0, J2=45.0
```

Assert cfg0 is semantic home, cfg1 moves A and B while R remains fixed, cfg2 moves B while A remains at home, and cfg3 produces a distinct descendant B pose. Do not generate commands from joint limits.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k candidate_authority
```

Expected output is one passed test and zero skips, with all hashes recomputed from typed records and no direct numeric axis or placement inference.

### Task 4: Real Candidate CAD Through Production Composition

**Files:**
- Modify: `tests/integration/m13_4_acceptance_fixtures.py` only for typed request construction.
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`.

**Interfaces:**
- Consumes: `ProductionApplication.realize_candidate_cad()` and the Task 3 candidate, synthesis request, synthesis policy, and CAD request.
- Produces: `CandidateCadStageOutcome` with a trusted imported motor mapping, exact generated shaft/hub/frame mappings, persisted FreeCAD artifacts, and verified placement derivations.

- [ ] Enter through `ProductionApplication.create()` with the real default provider. Do not pass `kinematic_measure`, create a fake provider, invoke `CandidateCadRealizationService` directly, or construct an alternate application graph.
- [ ] Call:

```python
cad_stage = fixture.application.realize_candidate_cad(
    fixture.candidate,
    fixture.synthesis_request,
    fixture.synthesis_policy,
    fixture.cad_request,
)
```

- [ ] Assert `cad_stage.status is CandidateCadStageStatus.SUCCESS`, then validate the returned `CandidateCadRealization` from its serialized JSON copy with `model_validate`.
- [ ] Assert the imported `motor-r` mapping has `CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY`, the actual source artifact ID/hash, and an `ImportedCadComponent` identity verified from artifact bytes.
- [ ] Assert all generated mappings have `EXACT_GENERATED_GEOMETRY`, generated geometry-definition identities, and placement origins derived from the five declared derivations rather than raw member variables.
- [ ] Reverify each generated part with `compile_generated_part()` and the candidate authority view. Reverify the placement derivation set hash and assert the frame clocking and shaft/hub offsets are non-identity where declared.
- [ ] Capture candidate assembly hash, candidate CAD realization hash, mapping hashes, source content identity, and every generated artifact identity as diagnostic scalars for the report. Do not compare them to canonical hashes later.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k candidate_cad
```

Expected output is one passed test and zero skips, with real FCStd/STEP verification and no generated compiler invocation for the imported source component.

### Task 5: Candidate M10-3 Discrete Evaluation And Evidence

**Files:**
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`.

**Interfaces:**
- Consumes: `ProductionApplication.evaluate_candidate_multi_joint_m10()`, the candidate CAD realization, `PhysicalToM10V2Bridge`, and the explicit configuration/pair scope.
- Produces: a trusted candidate `MultiJointCollisionSweepResultV2`, candidate evaluation record, durable M10 Evidence, and provenance scalars.

- [ ] Compile the candidate bridge through the accepted candidate bridge boundary and assert the model is v2, the model hash is recomputed, inventory has six concrete IDs and all 15 pair entries, and exact scope has the ten checked pairs.
- [ ] Call:

```python
evaluation = fixture.application.evaluate_candidate_multi_joint_m10(
    fixture.candidate,
    candidate_cad,
    candidate_bridge,
    fixture.multi_joint_request,
)
```

- [ ] Assert the request and evaluation source revision/state hash, candidate hash, CAD realization hash, bridge model hash, configuration-set hash, placement-derivation hash, pair-scope hash, and exact tolerances all bind consistently.
- [ ] Assert every configuration has every checked concrete pair exactly once, all measured interference and distance values are finite, pair identity is concrete, and `evaluation.result.continuous_path_verified is False`.
- [ ] Assert the production application provider snapshot reports `real_freecad is True`, provider name `freecad-transient-exact`, provider version `mechcad-freecad-transient@1.0`, and execution mode `freecadcmd-subprocess` or the exact live mode reported by the provider.
- [ ] Resolve `get_multi_joint_collision_sweep_evidence(evaluation.m10_v2_result_hash)` and assert its provenance binds the exact provider, backend, runtime, source assembly, model, request, result, and artifact identities.
- [ ] Record actual pair classifications and numeric measurements in the report. Do not add a golden or claim a positive-clearance outcome if live geometry produces a truthful collision/touching classification.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k candidate_m10
```

Expected output is one passed test and zero skips, with no fake exact measurement path and no continuous-proof claim.

### Task 6: Root-Composed Selection, Promotion, And Receipt Verification

**Files:**
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`.

**Interfaces:**
- Consumes: the Task 5 candidate evaluation and the typed M13-4E/M13-4P request records.
- Produces: `CandidateMultiJointSelection`, `CandidateMultiJointPromotionRequest`, `CandidateMultiJointPromotionApplicationResult`, decision/result artifacts, and persisted revision N+1.

- [ ] Call selection only through the root:

```python
selection = fixture.application.select_candidate_multi_joint(
    fixture.candidate,
    candidate_cad,
    candidate_bridge,
    fixture.multi_joint_request,
    evaluation,
    "m13-4-representative-selector",
    "Selected the bounded generic six-constituent candidate after trusted replay.",
)
```

- [ ] Snapshot `application.__dict__` before and after selection and assert no candidate CAD, bridge, replay result, latest run, or per-candidate cache is retained by the root.
- [ ] Build a typed `CandidateMultiJointPromotionRequest` containing the candidate, accepted M12 predecessor result, synthesis request/policy, multi-joint request/evaluation/selection, placement derivations/hash, promotion policy `candidate-canonical-mapping@2`, canonical target ID `PM-M13-4`, and all required classifications produced by the existing typed promotion contract. Do not call a private promotion route.
- [ ] Call only:

```python
receipt = fixture.application.promote_selected_multi_joint_candidate(promotion_request)
```

- [ ] Assert `receipt.status is PromotionApplicationStatus.PROMOTION_APPLIED`, decision and result artifact IDs are nonblank, applied revision equals source revision plus one, and applied state hash equals the persisted revision snapshot hash.
- [ ] Assert `receipt.compilation` is the original typed `CandidatePromotionCompilation` returned by the existing `compile_multi_joint()` route. Compare full typed compilation equality, including compilation hash, projection order/hash, mapping order/equality, and canonical mechanism identity; do not normalize or reorder the projection.
- [ ] Resolve the decision artifact by its exact ID, obtain its persisted run ID, load the run, and prove the run's initial source binding, revision advancement, `REVISION_ADVANCED` event, and changeset/invalidation binding. Record the `ChangeProposal` from the compilation and the durable `ChangeSet` identity from the accepted ChangeEngine route.
- [ ] Call `fixture.application.verify_multi_joint_promotion_application(receipt)` and assert it is read-only and succeeds using exact decision-artifact lookup. Call it a second time to prove repeatable durable verification.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k promotion_composition
```

Expected output is one passed test and zero skips, with root composition only and no direct internal-service orchestration.

### Task 7: Stale Candidate And Composition-Boundary Negatives

**Files:**
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`.

**Interfaces:**
- Consumes: the same fixture builder and existing typed currentness/error boundaries.
- Produces: fail-closed evidence for stale source, foreign project, request/result mismatch, and forbidden legacy dispatch.

- [ ] Add a stale candidate test that changes the candidate's source revision or source state hash without changing the persisted source, then calls `evaluate_candidate_multi_joint_m10()` or `select_candidate_multi_joint()`. Assert `CandidateIntegrityError` before exact provider execution or promotion publication.
- [ ] Add a foreign-project selection test and assert `CandidateIntegrityError` before replay. Record the exact provider execution count before and after; it must not change.
- [ ] Add a valid-but-different replay result test by altering only the recomputed result payload in a test-local adapter. Assert the root selection path rejects the replay-result identity mismatch.
- [ ] Add a legacy route test proving `promote_selected_candidate()` does not accept `CandidateMultiJointPromotionRequest` and does not dispatch a union.
- [ ] Do not duplicate the full M13-4E adversarial matrix; test only the root composition boundaries above.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k stale_candidate
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k composition_negative
```

Expected output is all selected tests passed and zero skips. Any stale input that reaches lowering, exact measurement, decision publication, or ChangeEngine application is a failure.

### Task 8: Serialize Durable Locators And Dispose Candidate Runtime

**Files:**
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`.

**Interfaces:**
- Consumes: the successful Task 6 receipt and persisted state/artifact records.
- Produces: one locator JSON record containing only durable scalar values and a fresh application boundary with no candidate object authority.

- [ ] Before disposal, verify the receipt through the root and write only this scalar locator payload to a test-local file:

```python
locators = {
    "project_id": receipt.request.project_id,
    "canonical_revision": receipt.applied_revision,
    "canonical_state_hash": receipt.applied_state_hash,
    "canonical_target_mechanism_id": receipt.request.canonical_target_mechanism_id,
    "decision_artifact_id": receipt.decision_artifact_id,
    "result_artifact_id": receipt.result_artifact_id,
    "source_artifact_ids": tuple(sorted(source.artifact_id for source in canonical_sources)),
    "candidate_assembly_hash": candidate_cad.assembly_hash,
    "candidate_bridge_hash": candidate_bridge.physical_to_m10_bridge_hash,
}
locator_path.write_text(
    json.dumps(locators, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
```

The actual revision and state hash are read from the receipt. The canonical input
may read only these persisted scalar locators. Do not serialize candidate, CAD
realization, bridge, request, result, evaluation, selection, readiness,
promotion request, or receipt objects into the canonical input.
- [ ] Persist a plain JSON semantic snapshot for comparison diagnostics, containing only primitive body/member/reference facts, joint endpoint/axis/limit/zero facts, placement/member-offset facts, pair classification/reason facts, ordered commands, tolerances, inventory meaning, exact scope, and placement derivation semantics. This snapshot is not an authority input and must not be loaded as a candidate model.
- [ ] Delete or shadow every candidate/runtime analysis variable before constructing canonical inputs: candidate, candidate CAD request/realization/derivations, bridge, candidate M10 model/inventory/scope/request/result, evaluation, selection, promotion request/readiness, and candidate M10 Evidence object.
- [ ] Read the locator file with `json.loads`, then construct a newly composed `ProductionApplication` using the same workspace and project ID. Construct new `StateManager`, `ArtifactStore`, and `EvidenceStore` instances through the production root; do not reuse the previous object graph.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k serialized_restart
```

Expected output is one passed test and zero skips. A test that merely assigns candidate variables to `None` without reloading persisted state and artifacts fails this gate.

### Task 9: Fresh Canonical CAD And Semantic Equivalence

**Files:**
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`.

**Interfaces:**
- Consumes: only the Task 8 scalar locators, fresh `ProductionApplication`, persisted `DesignState` N+1, and canonical compiler boundaries.
- Produces: fresh `CanonicalPhysicalMechanism@3`, `CanonicalCadRealization`, fresh canonical bridge/inventory/scope, and semantic equivalence evidence.

- [ ] Load revision N+1 from the new `StateManager` and assert its computed `state_hash` equals the locator. Reconstruct only by:

```python
reconstruction = fresh_application.reconstruct_promoted_mechanism(
    project_id=locators["project_id"],
    revision=locators["canonical_revision"],
    state_hash=locators["canonical_state_hash"],
    mechanism_id=locators["canonical_target_mechanism_id"],
)
```

- [ ] Assert `reconstruction.canonical_mechanism.schema_version == "canonical-physical-mechanism@3"`, its body/member universe contains the six canonical physical instances, and its single canonical multi-joint obligation contains the exact four ordered configurations and ten checked pairs.
- [ ] Call the fresh composed canonical CAD boundary:

```python
canonical_cad = fresh_application.canonical_cad_compiler.realize(reconstruction)
```

- [ ] Assert supplied geometry is reverified from exact artifact ID/hash and bytes, generated shaft/hub/frame programs are regenerated from canonical authority, canonical placement derivations are replayed, and the fresh assembly has fresh CAD instance IDs and mappings.
- [ ] Compile a fresh bridge using `PhysicalToM10V2BridgeCompiler().compile_canonical(reconstruction, canonical_cad)` or the existing canonical wrapper, then assert v2 model, complete inventory, exact scope, and concrete pair identity.
- [ ] Build a canonical primitive semantic snapshot from the fresh mechanism, CAD, bridge, obligation, and mapping. Compare it to the reloaded candidate semantic snapshot over bodies, members/reference members, joints/axes/limits/zero semantics, placements/member offsets, pair classifications/reasons, ordered commands, tolerances, inventory meaning, exact scope, and placement derivations.
- [ ] Use `rigid-transform-agreement@1.0` for transform comparison. Do not require candidate and canonical raw CAD, bridge, inventory, model, or request hashes to match. Assert canonical request hash differs from the candidate request hash whenever fresh canonical CAD identity makes it differ; hash equality is not an acceptance criterion.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k canonical_restart
```

Expected output is one passed test and zero skips, with no candidate object supplied to canonical reconstruction or canonical CAD.

### Task 10: Fresh Canonical M10-3, Focused M10-4, Stale Canonical Negative, And Report

**Files:**
- Test: `tests/integration/test_m13_4_full_stack_acceptance.py`.
- Create: `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md` after all positive gates pass, or an environment-blocked report when Task 0 blocks execution.

**Interfaces:**
- Consumes: fresh canonical reconstruction/CAD/bridge and the scalar locators.
- Produces: canonical M10-3 Evidence, focused M10-4 Evidence, stale canonical rejection, M11 handoff decision, and the audit report.

- [ ] Execute fresh canonical M10-3 only through the composed canonical service:

```python
canonical_m10 = fresh_application.canonical_multi_joint_m10_verification_service.execute(
    reconstruction,
    canonical_cad,
)
```

- [ ] Assert the fresh canonical request is `multi-joint-collision-sweep-request@2`, its request/result hashes bind to the fresh canonical assembly/model/scope/configurations/tolerances, its result is `MultiJointCollisionSweepResultV2`, and `continuous_path_verified is False`.
- [ ] Resolve and reload canonical M10 Evidence from `EvidenceStore`. Assert provider/backend/runtime provenance is trusted and bound to the canonical source, model, request, result, and canonical CAD artifacts.
- [ ] Select one truthful root/articulated checked pair and one truthful articulated/articulated checked pair from the canonical exact scope. Build one explicit path from canonical cfg0 to a small nonzero endpoint, for example `J1=1.0, J2=1.0`, using the canonical model ID and no generated trajectory.
- [ ] Call `fresh_application.prove_continuous_multi_joint_path_clearance_v2()` with that explicit path, the selected canonical checked pairs, `required_clearance_mm=0.0`, and bounded `max_depth`/`max_exact_evaluations` values. Require a truthful `VERIFIED_CLEAR` or `COLLISION_WITNESS`; reject `NOT_PROVEN` as an acceptance result. Record the actual status and witness/clearance data without upgrading it to a global safety statement.
- [ ] Resolve and reload focused M10-4 Evidence and assert provider/backend/runtime provenance. Assert the result remains labeled as the requested path only.
- [ ] Add the stale canonical negative after capturing the positive canonical result: in a test-local workspace copy, substitute or tamper the trusted source artifact bytes/metadata or canonical derivation binding, then call the fresh canonical CAD or bridge boundary. Assert `CanonicalCadIntegrityError` or the exact existing integrity error before invalid canonical M10 or Evidence publication.
- [ ] Set the structural decision explicitly to `M11_STATUS = UNRESOLVED` and `M11_ELIGIBLE = False`. Do not create a structural definition, material, semantic region, load, support, mesh, solver request, or FEA result.
- [ ] Write `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md` with these sections and actual values: final marker/status; generic fixture boundary; source artifact/interface/frame authority; generated dimensions/bindings; placements; bodies/joints/configurations; complete pair universe; candidate CAD and M10-3; selection/replay; promotion readiness; `ChangeProposal`, `ChangeSet`, `ChangeEngine`, and N -> N+1; receipt verification; candidate disposal; locator serialization; canonical reload/CAD/bridge/M10-3; semantic equivalence; focused M10-4; M11 decision; all artifact/result/Evidence IDs; stale negatives; runtime versions; predecessor regressions; static checks; dependency/scope audit; remaining Rotator V2 boundary.
- [ ] If the runtime was unavailable, write only an environment-blocked report with `M13_4_ENVIRONMENT_BLOCKED_PLAN_READY`, the discovery output, and the exact unexecuted gates. Never write `M13_4_REPRESENTATIVE_LIVE_FULL_STACK_CAPSTONE_VERIFIED`.
- [ ] Run:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -k canonical_m10
```

Expected output is all selected positive and negative tests passed and zero skips when the runtime is available.

### Task 11: Predecessor Regression, Static Audit, And Final Disposition

**Files:**
- Test: all existing predecessor files listed below; do not modify them.
- Inspect: `docs/audit/MECHCAD_M13_4_COMPLETION_REPORT.md` and the two M13-4 authority reports.

**Interfaces:**
- Consumes: the complete Task 10 evidence/report and the unchanged repository baseline.
- Produces: final regression evidence or an environment-blocked planning disposition.

- [ ] Run the focused M13-4 acceptance with no skip allowance:

```powershell
py -3 -m pytest tests/integration/test_m13_4_full_stack_acceptance.py -q -rs
```

Expected output is all M13-4 tests passed, `0 skipped`, and the success marker only when the real runtime is available.
- [ ] Run the exact accepted M13-4P gate:

```powershell
py -3 -m pytest tests/integration/test_m13_4p_production_composition.py -q
```

Expected historical baseline: `8 passed`, zero skips.
- [ ] Run the exact accepted M13-4E gate:

```powershell
py -3 -m pytest tests/unit/test_m13_4e_legacy_promotion_goldens.py tests/unit/test_m13_4e_promotion_evidence.py tests/unit/test_m13_4e_promotion_result.py tests/unit/test_m13_4e_promotion_application.py tests/integration/test_m13_4e_promotion_evidence_acceptance.py -q
```

Expected historical baseline: `116 passed`, zero skips.
- [ ] Run the exact accepted M13-3/predecessor gate:

```powershell
py -3 -m pytest tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m13_3_candidate_request.py tests/unit/test_m13_3_candidate_evaluation.py tests/unit/test_m13_3_multi_joint_selection.py tests/unit/test_m13_3_promotion.py tests/unit/test_m13_3_legacy_goldens.py tests/integration/test_m13_3_generic_multi_joint_acceptance.py -q
```

Expected historical baseline: `75 passed`, zero skips.
- [ ] Run the required M10/M12/CAD/provenance regression group:

```powershell
py -3 -m pytest tests/unit/test_multi_joint_kinematics.py tests/unit/test_multi_joint_collision_sweep.py tests/unit/test_multi_joint_continuous_path.py tests/unit/test_multi_joint_continuous_clearance.py tests/integration/test_m10_3_provenance.py tests/integration/test_m10_3_live_multi_joint_collision.py tests/integration/test_m10_4_provenance.py tests/integration/test_m10_4_live_continuous_multi_joint_path.py tests/integration/test_m10_5_system_acceptance.py tests/unit/test_m12_promotion_models.py tests/unit/test_m12_promotion_compiler.py tests/unit/test_m12_promotion_apply.py tests/unit/test_m12_promotion_provenance.py tests/unit/test_m12_promotion_replay.py tests/unit/test_m12_canonical_cad.py tests/unit/test_m12_canonical_m10.py tests/unit/test_transient_freecad_measurement.py tests/unit/test_m13_2_m13_1_consumption.py tests/unit/test_m13_2_generated_part_models.py tests/unit/test_m13_2_generated_part_bindings.py tests/unit/test_m13_2_generated_part_cad.py tests/unit/test_m13_2_candidate_cad_integration.py tests/unit/test_m13_2_placement_derivations.py tests/unit/test_m13_2_promotion_canonical_roundtrip.py tests/integration/test_m13_2_generated_parts_live.py tests/integration/test_m13_2_acceptance_live.py tests/unit/test_m13_3p_rigid_body_groups.py tests/unit/test_m13_3p_legacy_goldens.py tests/integration/test_m13_3p_live_grouped_body_freecad.py tests/unit/test_m13_3_bridge_compiler.py tests/unit/test_m13_3_bridge_validation.py tests/unit/test_m13_3_authority_consumption.py tests/unit/test_m13_3_physical_primitives.py tests/unit/test_m13_3_physical_joints.py tests/unit/test_m13_3_pair_inventory.py tests/unit/test_m13_3_realization_v2.py tests/unit/test_m13_3_lowering.py tests/unit/test_m13_3_canonical_projection.py tests/unit/test_m13_3_canonical_mechanism_v3.py tests/unit/test_m13_3_fresh_canonical_bridge.py tests/unit/test_m13_3_fresh_canonical_m10.py tests/integration/test_m13_3_candidate_m10_production.py tests/integration/test_m13_3_bridge_m10_4.py -q
```

Expected result is zero failures and zero errors. Existing runtime-gated predecessor tests may retain their historical skips; no M13-4 positive test may skip.
- [ ] Run static checks:

```powershell
py -3 -m compileall -q src tests
git diff --check
```

Expected result is exit code 0. Do not clean unrelated dirty-worktree files.
- [ ] Run the full suite with a harness timeout of at least 6000 seconds:

```powershell
py -3 -m pytest -q -rs
```

Expected result is zero failures and zero errors. Record the actual pass/skip counts and elapsed time; do not copy historical counts into the new report.
- [ ] Run a targeted forbidden-scope audit against only the new acceptance files and report:

```powershell
rg -n -i "rotator|antenna|yagi|pan[- ]?tilt|azimuth|elevation|5840-31ZY|projects/rotator_v2|automatic synthesis|configuration[- ]space" tests/integration/m13_4_acceptance_fixtures.py tests/integration/test_m13_4_full_stack_acceptance.py
```

Expected result is no output. Separately inspect the completion report and
require those terms to appear only in its explicit remaining-boundary section.
Also inspect `git diff -- src` and require no output from this task.
- [ ] Review the final report against every section of `docs/superpowers/specs/2026-09-06-m13-4-representative-live-full-stack-capstone.md`, verify no predecessor hashes/goldens changed, and leave the worktree uncommitted.
- [ ] If any required live stage is unavailable, stale, skipped, or not proven, use `M13_4_ENVIRONMENT_BLOCKED_PLAN_READY` or the exact truthful failure disposition and do not claim the success marker.

## Self-Review Checklist

- [ ] The old composition gap is documented as historical and is not reimplemented in M13-4.
- [ ] The static `ART-MOTOR` 13-byte test artifact is never treated as valid STEP geometry.
- [ ] The supplied source uses accepted M13-1 interface/frame authority without new supplier facts.
- [ ] The fixture has six constituents, exactly three bodies, two dependent revolute joints, nonzero semantic placements, multiple members in two or more bodies, and all 15 physical pairs exactly once.
- [ ] The ten checked pairs include root/articulated and articulated/articulated cases; the two intended-contact exclusions are tied to explicit connections; same-body exclusions are tied to explicit body bindings.
- [ ] Candidate M10-3 is real FreeCAD and discrete-only.
- [ ] Selection, promotion, receipt verification, ChangeEngine, and N+1 state application all enter through the production root.
- [ ] Candidate runtime objects do not cross the canonical serialization boundary.
- [ ] Canonical CAD, bridge, inventory, request, result, provenance, and Evidence are fresh and source-bound.
- [ ] Semantic equivalence uses typed semantic facts and `rigid-transform-agreement@1.0`, not raw CAD/bridge/request hash equality.
- [ ] The M10-4 result is labeled only as the requested path.
- [ ] M11 is recorded as `UNRESOLVED` and ineligible without structural execution.
- [ ] Runtime, stale negatives, predecessor regressions, full suite, static checks, dependency audit, and remaining boundaries are recorded with actual outputs.

## Execution Handoff

This plan is complete only when the plan file and the historical addendum are present, the runtime gate is recorded, and no implementation or capstone execution has been performed in this planning session. Execution requires a separate authorized choice of subagent-driven or inline plan execution and must keep the no-commit/no-push restriction.
