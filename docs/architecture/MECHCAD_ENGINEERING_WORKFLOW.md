# MechCAD Engineering Workflow

**Maturity:** `FOUNDATION` and `REQUIRED_CURRENT` are current baseline audit scope; `TARGET_NEXT` is connected-readiness work; `FUTURE` covers broad structural approval and FEA beyond the bounded M11 path, dynamics, manufacturing, and optimization. See `MECHCAD_SYSTEM_CONTRACT.md` for authoritative definitions.

## Generic Lifecycle

```text
USER / EXTERNAL AUTHORITY
        |
        v
Requirements / Constraints
        |
        v
Canonical DesignState
        |
        v
Readiness / Dependency Analysis
        |
        v
AgentTask
        |
        v
Specialist Engineering Agent
        |
        +------------------------------+
        |                              |
        v                              v
Reasoning Result           Semantic / Typed Engineering Request
        |                              |
        |                              v
        |                 AgentToolMediator / ToolBroker
        |                              |
        |                 +------------+-------------+
        |                 |                          |
        |                 v                          v
        |       Registered Engineering Tool   Trusted Service / Adapter
        |                 |                    -> Engineering Library
        |                 +------------+-------------+
        |                              |
        |                              v
        |                         ToolResult
        |                              |
        |                              v
        |                    Evidence / Agent Context
        +------------------------------+
                       |
                       v
                  AgentResult
                 /           \
                v             v
      Missing Input       Engineering Proposal
                |             |
                v             v
      ConstraintRequest   ChangeProposal
                           |
                           v
                       ChangeSet
                           |
                           v
                  Immutable Revision
                           |
                           v
                  Derived CAD / Analysis
                           |
                           v
                       Verification
                           |
                           v
                     Evidence / Issue
                           |
                           v
                  Next Engineering Task
```

## Authority Boundaries

Authority enters at requirements and accepted state. Agents may reason, identify missing inputs, and propose changes. Deterministic tools calculate derived values. Only `ChangeEngine` may apply an accepted change to canonical state. CAD, analysis, artifacts, and evidence are derived outputs. Verification can reject or mark outputs unresolved, but does not silently promote them.

The current production entrypoints that turn accepted state into derived CAD/assembly/analysis are owned by `ProductionApplication` (M8B/M8C/M10): `compile_design_spec` (source-bound `DesignSpec` -> `CadPartProgram`), `build_assembly_with_imported_components` (generated + trusted imported -> `CadAssemblyProgram` -> FreeCAD), `analyze_assembly_kinematics` (discrete exact sweep), `evaluate_multi_joint_configuration` (deterministic FK), `analyze_multi_joint_collision_sweep` (exact discrete multi-joint collision), and `prove_continuous_multi_joint_path_clearance` (explicit-path conservative proof). M11-5 adds `publish_structural_evidence`, `verify_structural_evidence`, `check_structural_evidence_currentness`, `compare_structural_repeatability`, and `evaluate_structural_mesh_convergence` for the bounded source-bound structural path. M9, M10, and M11 live-verified these paths on real FreeCAD where applicable; they remain derived outputs and never mutate canonical state.

An engineering agent must not arbitrarily import or execute an engineering library. Agent-authored semantic requests pass through trusted mediation and tool/service boundaries. A deterministic internal service may call its implementation library behind its own trusted adapter boundary; this contract does not require every backend-internal call to re-enter ToolBroker.

## Engineering Decision Rules

- Physical facts and user requirements are not design variables.
- Placeholders and recommendations cannot be promoted silently.
- Parametric and unresolved values remain explicit.
- A derived value needs deterministic inputs and provenance.
- A verified result must bind to the state and dependencies from which it was calculated.
- A geometric clearance result is not manufacturing clearance approval.

## Durable Structural Evidence

The M11-5 structural evidence flow is:

```text
trusted M11-4 execution/result/verification/analytical validation
    -> ArtifactStore byte verification and source binding
    -> immutable structural Evidence
    -> fresh-store verification and separate currentness check
```

Only trusted PASS, FAIL, and NOT_EVALUABLE engineering outcomes may be
published. Integrity failure is not an engineering outcome. Repeatability is
declared and hashed before comparison, and convergence is a separate bounded
study over at least three ordered structural Evidence levels for the supported
free-end displacement-magnitude metric.

## Generic Examples

**Gearbox:** output speed and torque are authoritative requirements; ratio, tooth counts, and packaging are design variables; py_gearworks calculates candidate geometry; an owner proposes accepted transmission paths.

**Robotic revolute joint:** joint axis, range, payload, and interface are requirements; link dimensions and materials are design variables; generic CAD and kinematics operate without robot-specific assumptions in their core layers.

**Camera pan/tilt:** angular range, payload, and mounting envelope flow through the same state, proposal, CAD, and sweep boundaries. AZ/EL terminology is not required by the generic model.

**Structural frame:** member sections and material candidates feed section properties and preliminary mass/stiffness. Stress and safety approval require a future controlled load/structural contract.

**Antenna rotator:** a reference domain can reuse packaging, transmission, CAD, collision, and kinematic services. Its domain names do not define those services.

## Failure and Rework

Missing data returns `ConstraintRequest`; conflicting authority returns `Issue`; invalid structured output fails closed; stale results cannot apply proposals or create current evidence; failed changes create no revision; invalidated evidence must be recomputed. Transient kinematic samples remain analysis records and do not advance canonical state.

## Universal Acceptance Stages

**Stage A - Current baseline:** audit the accepted state, change, ownership, dependency, run, tool, Evidence, bounded agent, provider, CAD, exact analysis, transient, discrete kinematic, and bounded structural Evidence foundations independently.

**Stage B - Connected readiness:** use a motor-driven rotary bracket to prove requirements -> bounded agent -> deterministic tool/provider -> Evidence -> proposal -> new revision -> part CAD -> assembly -> discrete kinematic verification. This stage audits selected `TARGET_NEXT` wiring without assuming it already exists.

**Stage C - Future:** whole configuration-space certification, broad structural approval and FEA beyond the bounded M11 path, global convergence, dynamics, and manufacturing outputs. The accepted M10 explicit-path continuous proof and bounded M11 structural/Evidence path are current; these broader capabilities are not present baseline acceptance gates.
