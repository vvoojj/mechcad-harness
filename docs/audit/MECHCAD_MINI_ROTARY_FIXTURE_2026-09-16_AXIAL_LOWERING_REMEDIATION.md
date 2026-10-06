# MINI_ROTARY_FIXTURE Axial Lowering Remediation

## Status

```text
PROJECT-LOCAL TEST AUTHORITY -- NOT ACCEPTED SPECIFICATION
MINI_SHAFT_AXIS_FRAME@1
```

This current remediation record captures explicit user-authorized synthetic
engineering authority for `mini_rotary_fixture` test execution. It was not
present in the accepted MINI Spec, Plan, or canonical `DesignState`; it does
not change generic MechCAD semantics.

## Axial Frame And Stations

`MINI_SHAFT_AXIS_FRAME@1` has world origin `(0.0, 0.0, 20.0) mm`. Its shaft
analysis coordinate maps to the frozen rotary axis by:

```text
Z_world_mm = 20.0 + s_mm
X_world_mm = 0.0
Y_world_mm = 0.0
```

The authorized stations are support A `s=0.0 mm`, load plane `s=10.0 mm`, and
support B `s=20.0 mm`, producing world Z values `20.0`, `30.0`, and `40.0 mm`.
Support separation is exactly `20.0 mm`.

## Project-Local CAD Representation Lowering

The synthetic bearing is an `18.0 mm` OD, `10.0 mm` bore, `8.0 mm` axial
representation whose local extent is `Z=0.0..8.0 mm`. Its support datum is the
local axial midplane at `Z=4.0 mm`; therefore its placement is
`support_world_z - 4.0 mm`. Bearing A is placed at Z `16.0 mm` and bearing B
at Z `36.0 mm`.

The synthetic hub is an `20.0 mm` OD, `8.0 mm` bore, `5.0 mm` axial
representation with local extent `Z=0.0..5.0 mm`. Its top face is the
authorized body/plate-hub datum, coincident with the frozen plate bottom at
world Z `55.0 mm`; its placement is Z `50.0 mm`. Its bottom face is the
authorized shaft/hub-side datum at world Z `50.0 mm`.

These dimensions are project-local synthetic representation authority. They
are neither supplier/manufacturer truth nor pre-existing frozen engineering
dimensions.

## Scope

The bearing B/hub pair remains `CHECK_CLEARANCE`; no topology exclusion is
introduced. The accepted M10 interval remains `0.0..360.0` degrees and the
minimum required clearance remains `5.0 mm`. Real FreeCAD and the existing
production M10 path remain required for all clearance claims.

## Implementation Plan

**Goal:** Lower the explicit project-local axial authority into deterministic
MINI CAD placements and re-evaluate the exact retained Revision 3 candidates.

**Constraints:** Do not modify `src/mechcad_harness/**`, accepted MINI
Spec/Plan, frozen engineering geometry, pair exclusions, or the M10 interval.
Do not commit, push, install packages, or make permanent environment changes.

### Task 1: Test The Lowering Contract

- Add focused tests in `projects/mini_rotary_fixture/test_acceptance.py` for
  the `20.0 mm` support-station separation, frame-derived bearing placements,
  source-traceable load-plane lowering, retained bearing-B/hub clearance
  classification, connected-pair topology authority, retained source identity,
  and full M10 interval.
- Run the new tests before implementation and retain their failure output.

### Task 2: Implement Project-Local Lowering

- Add one local axial-frame helper in
  `projects/mini_rotary_fixture/acceptance.py` that applies
  `Z_world_mm = 20.0 + s_mm`.
- Derive both bearing placements from their support station and local midplane
  datum `4.0 mm`; derive the hub placement from its top-face datum at world Z
  `55.0 mm` and local length `5.0 mm`.
- Replace only the previous absolute bearing/hub placement inputs with those
  derived values. Keep the topology, pair table, source binding, geometry
  dimensions, and M10 scope unchanged.
- Re-run the focused tests and require them to pass.

### Task 3: Execute And Record The Retained Chain

- Use process-local FreeCAD configuration and the exact retained Revision 3
  workspace.
- Verify the real transient provider emits `M7C1_JSON`, realize both
  candidates, and run each full `0.0..360.0` degree M10 evaluation.
- Stop before comparison/promotion if either CandidateEvaluation is not
  feasible. Otherwise use the existing explicit comparison, selection,
  promotion, canonical reconstruction/CAD/M10 path; do not execute M11.
- Append actual outcomes, hashes, pair classifications, provider evidence, and
  any failure/timeout to this current remediation record and the append-only
  execution log.

### Task 4: Verify

- Run focused project tests, applicable existing M10/CAD regressions,
  `python -m compileall -q projects/mini_rotary_fixture`, and a scoped
  `git diff --check`.
- Report pre-existing unrelated worktree diagnostics separately.

## Authorized Motor Interface Retry

The explicit MINI test authority selects motor `mount-face` for the
nonconnected motor/hub and motor/top-plate canonical clearance obligations.
The explicit `drive` connection continues to use motor `output-shaft`. This
selection is not a mechanical connection and does not change candidate
geometry, pair classifications, clearance requirements, motion range, or
candidate identity.

The retry consumed that authority through a project-local compiler subclass
wrapped by the existing `CandidatePromotionApplicationService`; the
`ProductionApplication` dependency graph and generic platform source were not
modified. The motor ambiguity was resolved, but promotion then stopped at:

```text
canonical M10 pair interface is ambiguous for hub
```

The hub exposes both `shaft` and `body` interfaces. The supplied authority
selects only the motor-side interface and does not select the hub-side interface
for the nonconnected motor/hub clearance obligation. No hub interface may be
guessed. No canonical mutation, canonical CAD/M10, or M11 execution was
performed. The candidate hashes and full-range M10 evaluation identities remain
unchanged.

The later explicit hub authority selects `hub.shaft` for `hub-coupling`,
`hub.body` for `payload-attachment`, and `hub.body` for the four nonconnected
hub clearance obligations. The retry therefore resolves the hub ambiguity
without adding connections or changing candidate/M10 identities. Promotion then
stops at:

```text
canonical M10 pair interface is ambiguous for shaft
```

The shaft declares `motor-side`, `hub-side`, `journal-a`, and `journal-b`.
The current authority does not select the shaft-side interface for the
nonconnected motor-mount/shaft clearance obligation. No shaft interface may be
guessed; no canonical mutation, canonical CAD/M10, or M11 execution was
performed.

## Execution Record

### Chronology

1. The prior unauthorized `0..10` degree run was rejected.
2. Restoring `0..360` degrees exposed bearing B/hub touching under the former
   independent Z placements.
3. The semantic/geometric audit classified that contact as
   `PROJECT_LOCAL_GEOMETRY_LOWERING_DEFECT`.
4. This record applies the later explicit MINI-only test authority and re-runs
   the exact retained Revision 3 candidate CAD/M10 path.

### Retained Source And Candidate Identity

- HEAD: `05da8edad18488492f02be1dad9d1ec3653ce807`.
- Exact source: Revision `3`,
  `sha256:d48680ac9bafde5f7328ea57ad66ef80ff0388cfbfec9ec553fbeb5ee8322270`.
- Historical geometry-less identities remain unchanged: Candidate A
  `sha256:78aaa7b818bd024f010df001b8ec047ea468a7059d3e60f07f7623ee89c688c4`;
  Candidate B
  `sha256:43ff20afbe6c3f0c3fd286002006b16d974c59f70da2a5a32b2cbfa817976b63`.
- Corrected Candidate A:
  `sha256:7d6ec2d2de957ec8638c71741b151bdf4e840c1b6f0406e32212d16fc3af3b5c`.
- Corrected Candidate B:
  `sha256:bc8ceb7295e575a3994eba92ec07fe5cd113119c2aefd7efd8226db42fbc971c`.

The corrected identities differ because the candidate placement design variables
now contain frame-derived bearing A Z `16.0 mm` and bearing B Z `36.0 mm`, not
the former independent values. Candidate A was rebuilt in separate retained
executions with the same hash; Candidate B's separate retained evaluation and
CAD rebuild also produced the same hash. The prior geometry-bearing hashes were
not retained as a distinct identity record and are not reconstructed here.

### Real CAD And Transient Provider

Real FreeCAD `1.1.3` was invoked through the configured process-local command
`C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`.

| Candidate | Candidate CAD realization |
| --- | --- |
| A | `sha256:c1bd90ac2be03218c73e1b61f2e09f9f5c9ad4e066f516b8153eface9e3aae9e` |
| B | `sha256:cd228d253a588e62792e68b1f063770b432cc342fbc0bf4baaeafe33598b0dff` |

The retained `diagnose_retained_m7c1(...)` execution returned code `0`, emitted
valid `M7C1_JSON`, and measured top plate/motor mount at `0.0` degrees with
`20.0 mm` exact distance and `0.0 mm^3` interference. Its sweep identity was
`sha256:a4c997e5df227815267f8d5b8d9389cff15c31f4379ccf85fb110ec7f6e7a355`.

### Final Pair Authority

All 21 pairs remain classified. The nine `CHECK_CLEARANCE` pairs are evaluated
by M10; the following twelve exclusions have explicit semantic authority.

| Pair | Classification | Authority |
| --- | --- | --- |
| actuator / bearing A | out of scope | fixed-fixed disposition |
| actuator / bearing B | out of scope | fixed-fixed disposition |
| actuator / motor mount | out of scope | `motor-mount` connection |
| actuator / shaft | out of scope | `drive` connection |
| bearing A / bearing B | out of scope | fixed-fixed disposition |
| bearing A / motor mount | out of scope | fixed-fixed disposition |
| bearing A / shaft | out of scope | `support-a` connection |
| bearing B / motor mount | out of scope | fixed-fixed disposition |
| bearing B / shaft | out of scope | `support-b` connection |
| hub / shaft | out of scope | `hub-coupling` connection |
| hub / top plate | out of scope | `payload-attachment` connection |
| shaft / top plate | out of scope | shared output-rigid group `J-1` |

The required clearance pairs are actuator/hub, actuator/top plate, bearing
A/hub, bearing A/top plate, bearing B/hub, bearing B/top plate,
motor-mount/hub, motor-mount/shaft, and motor-mount/top plate. Bearing B/hub
remains `CHECK_CLEARANCE`; no exclusion was added.

### Full-Range M10 Results

Each required pair was proved by the real production continuous proof over
`0.0..360.0` degrees at required clearance `5.0 mm`. No proof has a collision
witness or unresolved interval.

| Pair | A lower bound mm | B lower bound mm |
| --- | ---: | ---: |
| actuator / hub | 9.176077981168556 | 9.176077981168556 |
| actuator / top plate | 8.446037199206835 | 8.446037199206835 |
| bearing A / hub | 5.999999983443651 | 5.999999983443651 |
| bearing A / top plate | 14.446037199206835 | 14.446037199206835 |
| bearing B / hub | 5.305869220520782 | 5.305869220520782 |
| bearing B / top plate | 6.836469725999017 | 6.836469725999017 |
| motor mount / hub | 6.715728735395963 | 6.715728735395963 |
| motor mount / shaft | 6.999999991928927 | 6.999999991928927 |
| motor mount / top plate | 5.23692969076842 | 5.236929690768434 |

Candidate A is `feasible`, evaluation
`sha256:9cda22c41f2056eed832e303bc931875587f4400f9835fc255cb9b0bf102baf9`,
with certified metric `5.23692969076842 mm`. Candidate B is `feasible`,
evaluation `sha256:e321dc85b5377294f6c369f8ca6f5505aa9a771ff82d9ead0893c2a11f769dae`,
with certified metric `5.236929690768434 mm`. The limiting pair for each is
motor mount/top plate, not bearing B/hub.

### Stop At Promotion

After both candidate evaluations were feasible, the existing comparison,
explicit selection, and promotion path was invoked. Promotion failed before a
canonical mutation with:

```text
canonical M10 pair interface is ambiguous for motor
```

Canonical promotion requires every clearance-pair constituent to expose one
unique interface. The motor has the explicitly declared `output-shaft` and
`mount-face` interfaces, but no project authority selects either for the
nonconnected motor/hub or motor/top-plate clearance obligations. Selecting one
would invent semantic authority. This is `PROJECT_LOCAL_MISSING_AUTHORITY`, not
a generic platform gap and not a clearance failure. No comparison result,
selection, promotion receipt, canonical revision, canonical reconstruction/CAD
or canonical M10 result is claimed. M11 remains upstream-blocked.

### Project-Local Promotion Projection Wiring

The motor, hub, and shaft authorities were implemented in a project-local
compiler subclass. A fresh projection regression exposed a second generic
static lookup boundary in `CandidatePromotionApplicationService._scope_projection`;
that method called `CandidatePromotionCompiler._interface_for` directly and
therefore bypassed the compiler subclass. A project-local application-service
subclass now mirrors the existing projection contract while resolving interface
IDs through the MINI compiler authority. The generic `src/mechcad_harness/**`
implementation, `ProductionApplication` dependency graph, candidate hashes,
21-pair inventory, and M10 scope were not changed.

Focused projection and authority tests passed: `4 passed`. The bounded
non-geometry project tests passed: `23 passed, 1 skipped, 3 deselected`.
With process-local `MECHCAD_FREECADCMD=C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe`,
the full-chain integration test passed in `1479.59s`, including comparison,
explicit selection, promotion, Revision 4 canonical reconstruction/CAD, and
fresh canonical M10 `verified_clear`. This result used the test-created
temporary source workspace and is not exact-retained-source acceptance evidence.

The retained workspace `runtime/2026-09-15-n1/workspace` is not present in the
current workspace. A newly generated N1/N2/N3 workspace produced Revision 3
state hash `sha256:c126a02b6e400c0f35379340d4134d52b8f2ef712d0ebfcdb203992319c8a0f2`,
which differs from the required retained hash
`sha256:d48680ac9bafde5f7328ea57ad66ef80ff0388cfbfec9ec553fbeb5ee8322270`.
The exact retained full-chain function therefore failed closed at its source
guard; no exact-hash canonical promotion or M11 execution is claimed.

## Later Exact-Retained Execution

The preceding entries preserve earlier rejected and blocked attempts. A later
authorized execution used the actual retained workspace after its path was
recovered; it did not use the `c126...` workspace and did not regenerate N1/N2/N3.
The retained source was Revision `3` with hash
`sha256:d48680ac9bafde5f7328ea57ad66ef80ff0388cfbfec9ec553fbeb5ee8322270`.

The real transient provider again returned code `0` with valid `M7C1_JSON`.
Both corrected geometry-bearing candidates completed production CAD and full
`0.0..360.0` degree M10 with 21 classified pairs and nine required clearance
checks. Candidate A is feasible with evaluation
`sha256:9cda22c41f2056eed832e303bc931875587f4400f9835fc255cb9b0bf102baf9`;
Candidate B is feasible with evaluation
`sha256:e321dc85b5377294f6c369f8ca6f5505aa9a771ff82d9ead0893c2a11f769dae`.
Their CAD realization identities are:

| Candidate | Candidate identity | CAD realization |
| --- | --- | --- |
| A | `sha256:7d6ec2d2de957ec8638c71741b151bdf4e840c1b6f0406e32212d16fc3af3b5c` | `sha256:c1bd90ac2be03218c73e1b61f2e09f9f5c9ad4e066f516b8153eface9e3aae9e` |
| B | `sha256:bc8ceb7295e575a3994eba92ec07fe5cd113119c2aefd7efd8226db42fbc971c` | `sha256:cd228d253a588e62792e68b1f063770b432cc342fbc0bf4baaeafe33598b0dff` |

The persisted promotion decision binds the exact comparison and selection
inputs:

| Record | Identity |
| --- | --- |
| comparison request | `sha256:98d5679d98d48d8f75f85307655177a1bab51edb5748674fd5398d00c6a3a76b` |
| comparison result | `sha256:eed217a59afec86a230e2b958d916297c23ce2785ba56b09449361a2bde32de3` |
| explicit selection | `sha256:45fbf508913d91d7ddaf3e09b8c5bfeaa5238d2db2824c994f2a0a0dff1bdd03` |
| selected candidate | Candidate B, `sha256:bc8ceb7295e575a3994eba92ec07fe5cd113119c2aefd7efd8226db42fbc971c` |

The selection was explicit; no automatic selection or promotion occurred. The
comparison result payload was not persisted as a standalone artifact, so its
full ordered metric payload cannot be independently re-read after the wrapper
process ended. The durable hashes, selected candidate, candidate evaluation
hashes, and persisted promotion decision are retained; no comparison metric is
being reconstructed from the hash.

Promotion then persisted:

- run `RUN-881dbaaa-1276-4f78-a310-c31625ec8603`;
- decision artifact `PROMOTION-DECISION-2a344f5cce42318c232623f6`, decision hash `sha256:2a344f5cce42318c232623f66dab3ca5a6d4ac4c58d84ae7c71c4b7870026e6e`;
- promotion compilation hash `sha256:b7dbb52c91b2b411129b10756d9be57bfd0f73a95415316f4354b832033e85ae`;
- changeset `CS-3b3c7232-43be-4c5a-946d-cd6f8d121656`;
- Revision `4`, state hash `sha256:bae8d54368e127408e027bf875da5ef9edfa62de0dda9af8999ebd1ed4f20767`.

Revision 3 remains retained and unchanged. Revision 4 reload verification
confirmed mechanism `PM-MINI-GEOMETRY-BEARING`, seven components, six topology
connections, `top_plate_side_mm=50.0`, bearing placements Z `16.0/36.0 mm`, hub
placement Z `50.0 mm`, output shaft diameter `8.0 mm`, and the six frozen
requirements. The current pointer is Revision 4 with the same state hash.

The fresh canonical downstream calls returned:

| Result | Identity/status |
| --- | --- |
| canonical mechanism | `PM-MINI-GEOMETRY-BEARING`, mechanism hash `sha256:006c611728b2f76f5632231c13adfbb3241aa05aa61750dc066646845f18423e` |
| canonical projection | `sha256:bf35d0a9b9c66c04c37162c41e2b089a1427b19800122ff1c79322f4d9f656c4` |
| canonical CAD realization | `sha256:0157fce9576e3c56c2db42c0035551f9a926b35fa65f4f9312a387b9d1fbbaa5` |
| canonical CAD assembly | `sha256:6d1e8530d96ff3215ff6113e3a54e148e6dfbf87f822f12196ef306ee6bf7a4b` |
| canonical M10 | `verified_clear`, outcome `sha256:83ec224cedbe882f89ba7a55cf24f9fb4df2428d984446d626f8581b0a5912b7` |
| canonical M10 request/scope | `sha256:063fe75a343211533a19decfb2a3383a9e6a976db03a0e981d2baae705f0b711` / `sha256:5d1dff20b3ada8812a969e1e81d522638a27d4d597eec85bbbc2b7e5de68f9a1` |

Canonical M10 covered all nine required pairs over the full interval with no
home checks, collision witness, or unresolved interval. The wrapper printed
`RESULT=SUCCESS` after the chain returned, then failed while reading a
nonexistent `comparison_hash` field; this was a reporting error after durable
promotion, not a production-chain failure.

No M11 call, structural solve, or M11 acceptance marker was performed.
