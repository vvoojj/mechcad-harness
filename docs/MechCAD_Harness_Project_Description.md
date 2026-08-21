# MechCAD Harness — Short Technical Project Description

**Document role:** historical + evolving project overview. Historical roadmap statements are retained where useful and visibly superseded by later current-status sections. Implementation claims in this overview remain subject to the independent implementation/integration audit.

## 1. What This Project Is

**MechCAD Harness** is an engineering software framework for automated mechanical-system design using agents, deterministic calculation tools, and CAD/simulation backends.

The core idea:

> the user provides physical requirements and constraints → the system forms a canonical design state → agents analyze it → deterministic tools perform critical calculations → the results become verified Evidence → new engineering requests/decisions are created from that Evidence → derived CAD/analysis backends such as FreeCAD realize and verify the design → later simulation/FEA backends can add further verification.

The first practical target object is an **antenna rotation mechanism** with azimuth/pan and elevation/tilt axes. Rotation of the antenna around its own axis for polarization is not currently required.

The system is not being built as a one-off script for a single antenna, but as a **general multi-agent mechanical-engineering harness** that can later be applied to other mechanical assemblies.

---

# 2. Desired Final Behavior

In its final form, the workflow should look approximately like this:

```text
User requirements
        ↓
DesignState
        ↓
Agents analyze the task
        ↓
Identify missing authoritative inputs
        ↓
Deterministic engineering calculations
        ↓
Evidence
        ↓
Selection/verification of mechanical concept
        ↓
ChangeProposal / ChangeSet
        ↓
New immutable DesignState revision
        ↓
Dependency invalidation
        ↓
Recalculation of dependent parameters
        ↓
FreeCAD
        ↓
Parametric 3D model
        ↓
MuJoCo / FEA / additional verification
        ↓
Iteration until an acceptable solution is reached
```

For example:

```text
The antenna becomes heavier
        ↓
the load requirement changes
        ↓
old torque Evidence becomes stale
        ↓
the system recalculates required torque
        ↓
checks the motor/gearbox
        ↓
updates transmission parameters
        ↓
FreeCAD rebuilds the geometry
        ↓
clearances, strength, and kinematics are checked
```

---

# 3. Main Input Data

The system must receive **authoritative input**, meaning data supplied by the user or an external system as source physical requirements. The agent must not invent these values.

## 3.1. Geometry

Typical parameters:

- antenna dimensions;
- mass;
- center-of-mass position;
- load lever-arm length;
- allowable envelope;
- available space for motors and gearbox;
- shaft diameters;
- fit dimensions;
- output-shaft interface;
- mounting points;
- plate/bracket thickness;
- allowable clearances;
- bearing diameters;
- gear-train geometry.

## 3.2. Loads

For example:

- force;
- torque;
- mass;
- gravitational load;
- wind load;
- impact/dynamic load;
- safety factor;
- direction of applied force.

The already implemented torque flow uses:

```text
force_n
lever_arm_m
safety_factor
```

Example:

```text
force_n = 10 N
lever_arm_m = 0.2 m
safety_factor = 2.0
```

Deterministic result:

```text
nominal torque = 2.0 N·m
design torque  = 4.0 N·m
```

## 3.3. Kinematics

Required parameters may include:

- desired angular speed of the axis;
- angular range;
- maximum/minimum position;
- allowable speed;
- acceleration;
- positioning accuracy;
- backlash;
- continuous or intermittent motion.

## 3.4. Motor

Authoritative motor data:

- specific motor model or acceptable motor class;
- rated speed;
- operating RPM range;
- continuous torque;
- peak torque;
- voltage;
- current;
- motor type;
- output-shaft type.

The gear ratio should preferably **not be entered manually** if the harness can derive it from:

```text
motor speed
+
required output speed
```

## 3.5. Materials

For each part, the following may be specified:

- material;
- allowed materials;
- Young’s modulus;
- density;
- Poisson ratio;
- shear modulus;
- yield/ultimate properties;
- manufacturing constraints.

For 3D-printed parts, future support may include, for example:

- PA / Nylon;
- PA-CF;
- PETG;
- ASA;
- other structural plastics.

Critical shafts, bearings, gear racks, and load-bearing elements may be metallic.

---

# 4. Engineering State Format

The central object in the system is **DesignState**.

This is the canonical project state containing:

- Requirements;
- Constraints;
- Components;
- Parameters;
- engineering bindings;
- revision;
- state hash.

Agents **must not modify DesignState directly**.

They may only propose:

- findings;
- ConstraintRequests;
- ChangeProposals;
- Issues;
- other structured results.

Changes to canonical state must pass through the trusted harness.

---

# 5. Immutable Revisions

Every change to DesignState creates a new revision.

For example:

```text
Revision 1
antenna_mass = 3 kg

Revision 2
antenna_mass = 4.5 kg
```

The previous state is not overwritten.

Each revision has a hash.

This makes it possible to know precisely:

- which state version a calculation was based on;
- whether Evidence is still current;
- whether an older result may still be reused;
- which data became stale after the design changed.

---

# 6. Dependency and Invalidation

The harness has a dependency graph.

For example:

```text
force
lever_arm
safety_factor
      ↓
analysis.transmission.torque
      ↓
gear selection
      ↓
shaft dimensions
      ↓
CAD geometry
```

If `force` changes, the old:

```text
analysis.transmission.torque
```

must automatically become stale.

Dependent CAD/analysis results must also be invalidated.

This is one of the key mechanisms for future automatic redesign.

---

# 7. RunController

Every engineering execution has its own run.

RunController is responsible for:

- run ID;
- binding to revision;
- state hash;
- immutable manifests;
- recovery;
- resume;
- transitions;
- execution status.

Conceptually:

```text
project
└── run
    ├── manifest
    ├── agent invocations
    ├── tool calls
    ├── evidence
    ├── constraint requests
    └── workflow transitions
```

A completed run can later be inspected without rerunning the model.

---

# 8. Tool Registry and ToolBroker

Critical engineering calculations must not be performed by the LLM “in its head.”

For this purpose, the system provides:

- **Tool Registry**;
- **ToolBroker**;
- typed inputs;
- typed outputs;
- deterministic ToolCall;
- immutable ToolResult.

An agent may say:

```text
torque must be calculated
```

but the actual calculation is performed by a trusted tool.

For example:

```text
transmission.torque
```

receives:

```text
force_n
lever_arm_m
safety_factor
```

and returns a normalized typed result.

---

# 9. Evidence

ToolResult itself is not passed to the agent as arbitrary text.

The harness creates trusted **Evidence**.

Example:

```text
Evidence node:
analysis.transmission.torque

Summary:
Required design torque: 4 N*m
```

Evidence is bound to:

- project;
- run;
- revision;
- state hash;
- ToolCall;
- ToolResult;
- backend provenance.

In the next reasoning step, the agent works with CURRENT Evidence.

---

# 10. Agent Gateway

Agents are executed only through the Agent Gateway.

The Gateway is responsible for:

- canonical context;
- revision/state binding;
- response schema;
- schema hash;
- invocation record;
- adapter execution;
- structured response validation;
- AgentResult;
- stale detection.

The model is not allowed to choose trusted metadata itself.

---

# 11. OpenCode / Luna

OpenCode Desktop is used for real reasoning invocations.

Current backend:

```text
OpenCode Desktop
http://127.0.0.1:4096
```

One of the verified profiles:

```text
screenpipe/gpt-5.6-luna
```

Project agent:

```text
mechcad-transmission@1.0
```

OpenCode does not have direct access to the mechanical harness ToolBroker.

The agent only returns a structured semantic response.

---

# 12. Structured Output

Luna uses strict validated JSON text mode.

The model must return exactly one JSON document.

The harness:

1. advertises a Pydantic JSON Schema;
2. receives JSON;
3. validates it;
4. does not repair it;
5. does not extract JSON with regex;
6. does not fall back to arbitrary text.

Invalid response → fail closed.

---

# 13. Transmission Reasoning Agent

The first real engineering agent is the transmission agent.

It can already:

1. see authoritative inputs;
2. determine the need for torque calculation;
3. issue a semantic tool request;
4. receive CURRENT Evidence through the harness;
5. perform a second reasoning step without a second ToolCall.

Basic bounded flow:

```text
Invocation A
    ↓
transmission.torque request
    ↓
ToolBroker
    ↓
ToolResult
    ↓
Evidence
    ↓
Invocation B
```

Hard limits:

```text
2 reasoning invocations
1 engineering tool execution
1 torque Evidence
0 second ToolCall
```

---

# 14. Constraint Discovery

The next layer is structured missing-input discovery.

The agent does not merely say:

> “I am missing data”

Instead, it creates a typed draft:

```text
key
description
rationale
```

Initially, exactly four semantic keys are supported:

```text
transmission.output_angular_speed
transmission.motor_characteristics
transmission.output_interface
transmission.packaging_envelope
```

For example:

```text
key:
transmission.output_angular_speed

description:
Required target output angular speed

rationale:
Needed to derive transmission ratio from motor speed
```

---

# 15. Trusted ConstraintRequest

The LLM does not create canonical IDs.

The harness materializes:

```text
ConstraintRequest
ConstraintRequestRecord
```

Canonical identity is derived from:

```text
project_id
engineering_scope_id
bound_revision
bound_state_hash
supported_constraint_key
```

Therefore:

- different wording in the description does not create a new request;
- recovery does not create duplicates;
- one semantic key on one state has one deterministic identity.

---

# 16. Satisfaction Checking

The harness does not trust the LLM to decide whether authoritative input already exists.

The first exact anchors are:

```text
transmission.output_angular_speed
→ REQ-TRANSMISSION-OUTPUT-SPEED

transmission.motor_characteristics
→ REQ-TRANSMISSION-MOTOR-CHARACTERISTICS

transmission.output_interface
→ CON-TRANSMISSION-OUTPUT-INTERFACE

transmission.packaging_envelope
→ CON-TRANSMISSION-PACKAGING-ENVELOPE
```

There is no:

- fuzzy matching;
- semantic text matching;
- LLM interpretation;
- aliases.

If an exact authoritative record exists → the request is suppressed.

---

# 17. M6B Status — Constraint Discovery and Resolution

The earlier project description stopped while M6B-3 live acceptance was still pending. That is no longer the current project position.

## M6B-3 — Constraint Discovery

The structured missing-input discovery layer is now established.

Implemented capabilities include:

- `SupportedConstraintKey`;
- typed discovery responses;
- `AgentConstraintRequestDraft`;
- explicit response contracts;
- typed constraint observations;
- deterministic request identity;
- exact authoritative satisfaction anchors;
- immutable `ConstraintRequestRecord`;
- idempotent materialization;
- durable persistence and recovery;
- bounded agent/tool/evidence workflow integration.

The system can distinguish between:

```text
missing authoritative input
        ↓
ConstraintRequest
```

and:

```text
already satisfied authoritative input
        ↓
no duplicate request
```

The LLM still does not decide canonical identity or satisfaction semantics.

## M6B-4 — Constraint Resolution Loop

The constraint-resolution loop has also been implemented and accepted.

The intended path is now available as a trusted state transition:

```text
ConstraintRequest
        ↓
trusted user/external resolution
        ↓
authoritative Requirement / Constraint
        ↓
ChangeProposal
        ↓
ChangeSet
        ↓
ChangeEngine
        ↓
new immutable DesignState revision
        ↓
dependency invalidation
        ↓
new engineering analysis
```

This closes an important architectural gap between:

```text
"the agent discovered missing information"
```

and:

```text
"the information was supplied and became trusted canonical state"
```

The exact runtime integration of every future engineering domain still needs separate audit, but the generic constraint-discovery/resolution foundation is no longer merely future work.

---

# 18. Major Milestone Status

The project has progressed substantially beyond the roadmap described in the original historical document.

## M0 — Bootstrap — COMPLETE

Established the basic typed harness structure.

## M1 — State Foundation — COMPLETE

Established:

- `DesignState`;
- immutable revisions;
- deterministic hashing;
- canonical serialization.

## M2 — Change Proposal / ChangeSet Foundation — COMPLETE

Established:

- structured proposals;
- ownership boundaries;
- ChangeSet transition contract;
- trusted state-mutation boundary.

## M3 — Dependency / Invalidation — COMPLETE

Established:

- dependency graph;
- dependent-node invalidation;
- Evidence freshness/staleness semantics.

## M4 — Run / Manifest Boundary — COMPLETE

Established:

- run identity;
- revision/state-hash binding;
- immutable manifests;
- recovery/resume behavior;
- deterministic run provenance.

## M5 — ToolBroker — COMPLETE

Established:

- Tool Registry;
- typed deterministic tools;
- `ToolCall`;
- `ToolResult`;
- permissions;
- backend/tool provenance;
- fail-closed execution.

## M5.5 — Engineering Library Foundations — COMPLETE AS FOUNDATIONS

Adapters/capabilities exist for engineering libraries including:

- `py_gearworks`;
- `build123d`;
- `bd_materials`;
- `sectionproperties`;
- numerical support through NumPy/SciPy.

Important:

> adapter existence is not the same thing as complete end-to-end workflow integration.

A later independent integration audit must prove which production workflows actually invoke each provider.

## M6A — Agent Infrastructure — COMPLETE AS FOUNDATION

Established:

- `AgentGateway`;
- OpenCode transport;
- real Luna invocation path;
- strict structured response validation;
- invocation/state provenance.

## M6B — First Engineering Agent / Tool / Constraint Loops — COMPLETE AS FOUNDATION

Established:

- bounded transmission reasoning;
- semantic tool mediation;
- deterministic torque execution;
- ToolResult → Evidence;
- Evidence-grounded second reasoning invocation;
- structured missing-input discovery;
- deterministic ConstraintRequest persistence;
- trusted satisfaction checks;
- constraint-resolution loop into new canonical revisions.

## M7A — Generic CAD / Assembly / Exact Geometry Foundation — COMPLETE

M7A moved FreeCAD from "future backend" into a working generic CAD foundation.

### M7A-1 — FreeCAD Backend Foundation

Established deterministic FreeCAD execution and derived CAD generation.

### M7A-2A — Typed CAD Operations

Established generic typed operations including:

- base plates;
- holes;
- rectangular pockets;
- slots.

The CAD operation layer is generic and must not contain domain-specific Yagi logic.

### M7A-2B — Assembly Foundation

Established:

- rigid component placement;
- `CadAssemblyProgram`;
- `CadRigidTransform`;
- deterministic assembly identity and ordering.

### M7A-2C — Exact Interference / Clearance Analysis

Established exact FreeCAD geometry measurement using:

```text
shape.common(other).Volume
shape.distToShape(other)[0]
```

with generic classifications for:

- interference;
- touching;
- positive clearance.

## M7B — First Substantial Domain Reference Exercise — PARTIALLY DOMAIN-SPECIFIC

M7B is important as a proof that the generic architecture can support a real domain, but it is not the purpose of MechCAD.

The Yagi/antenna payload work established:

- payload authority models;
- preliminary carrier synthesis;
- native T-slot carrier architecture;
- preliminary packaging CAD;
- deterministic collision-layout synthesis;
- canonical domain revisions.

Important unresolved/reference-only conditions remain:

- packaging geometry is not final manufacturing geometry;
- structural approval is not complete;
- final physical clamp/T-slot implementation remains unresolved;
- final antenna fore/aft position may remain unresolved;
- some real authority inputs remain unavailable;
- the domain must not redefine generic MechCAD architecture.

## M7C — Generic Kinematic Sweep Foundation — COMPLETE

M7C introduced a reusable, domain-independent discrete revolute sweep capability.

Established:

- `RevoluteAxis`;
- canonical quaternion axis-angle transforms;
- `CadKinematicSweepRequest`;
- deterministic moving/stationary partitioning;
- exact ordered collision-pair evaluation;
- `CadKinematicSweepSample`;
- aggregate classification;
- deterministic result hashing.

### Transient Analysis Boundary

M7C also established a crucial transient architecture:

```text
source assembly
        ↓
transient transformed assembly
        ↓
temporary FreeCAD workspace
        ↓
exact measurement
        ↓
analysis result
```

Per-angle samples do **not** create:

- DesignState revisions;
- ChangeSets;
- public per-angle FCStd artifacts;
- public per-angle STEP artifacts.

The generic sweep remains discrete:

```text
continuous_sweep_verified = False
```

## M7D — Domain Adapter over Generic Kinematics — COMPLETE

M7D exercised the M7C generic kinematic engine through the current antenna-rotator reference domain.

### M7D-1 — EL Kinematic Reference Architecture

Established:

- strict `YagiELKinematicReference`;
- parametric EL-axis-height range;
- no final axis-height selection;
- deterministic reference hash;
- preservation of generic `RevoluteAxis`.

### M7D-2 — EL Kinematic Sweep Integration

Established a thin domain adapter that:

- binds domain layout provenance separately from executable assembly identity;
- accepts a caller-supplied `RevoluteAxis`;
- preserves ordered samples and instance identities;
- executes through the generic M7C sweep service;
- reaches the real transient FreeCAD measurement path without manual request mutation.

The final live fixture verifies:

```text
0°   -> positive clearance
90°  -> touching
180° -> interference
```

and aggregate collision classification.

After the provenance-boundary correction, the reported full suite was:

```text
528 passed, 34 skipped
```

This is a domain integration proof, not a complete mechanical rotator design.

---

# 19. Engineering Libraries and Their Current Role

## py_gearworks

Current role:

- deterministic gear-related engineering provider;
- spur-gear / gear-pair calculations and validation;
- normalized results through an adapter.

It is not engineering authority.

A future integration audit must prove which production workflows actually invoke it end-to-end.

## build123d

Current role:

- specialized parametric geometry generation;
- used for narrow procedural CAD paths such as gear solids;
- STEP/STL generation where supported.

It is not a replacement for the generic FreeCAD project-CAD pipeline.

## bd_materials

Current role:

- normalized material-property lookup;
- density and other typical properties;
- provenance for engineering evaluation.

It does not automatically select the final project material.

## sectionproperties

Current role:

- cross-section geometry;
- area and centroid;
- moments of inertia;
- warping/torsion-related properties.

This is not equivalent to full structural approval or FEA.

## NumPy / SciPy

Current role:

- numerical infrastructure supporting deterministic engineering services.

They are implementation infrastructure, not authority.

## FreeCAD

FreeCAD is now an implemented generic CAD realization and verification backend.

Current capabilities include:

- typed part generation;
- assemblies;
- placements/transforms;
- FCStd/STEP derived output;
- exact solid intersection;
- exact distance measurement;
- transient analysis geometry.

FreeCAD remains a **derived backend**.

It does not own canonical engineering truth.

## MuJoCo

Still planned/future as a generalized dynamics and mechanism-simulation backend.

Potential uses:

- multi-joint motion;
- trajectories;
- joint limits;
- dynamics;
- collision;
- acceleration;
- center-of-mass effects.

No current general MuJoCo production contract should be assumed without a later accepted milestone.

## FEA / scikit-fem

Still future.

Possible future uses:

- displacement;
- stress;
- deformation;
- structural verification.

Current section-property support must not be mistaken for FEA or structural approval.

## trimesh

Still future/unresolved unless a later accepted contract establishes a production role.

---

# 20. Current CAD Architecture

The current generic project-CAD path is conceptually:

```text
DesignState revision
        ↓
typed Domain DesignSpec
        ↓
deterministic CAD compiler
        ↓
CadPartProgram / CadAssemblyProgram
        ↓
FreeCAD backend
        ↓
FCStd / STEP
        ↓
fresh reload / geometry verification
        ↓
derived artifact / Evidence
```

Specialized procedural geometry may follow a different narrow path:

```text
accepted specialized geometry input
        ↓
engineering provider
        ↓
py_gearworks where applicable
        ↓
build123d
        ↓
solid / STEP / STL
        ↓
derived artifact
        ↓
optional later assembly/import/verification
```

The two paths must not be confused.

FreeCAD and build123d have different architectural roles.

---

# 21. What Happened to the "First FreeCAD Model" Step

The historical roadmap expected the next major milestone to be the first single-axis FreeCAD model.

That roadmap is now obsolete.

The project has already passed through:

```text
FreeCAD backend
        ↓
typed CAD operations
        ↓
assembly support
        ↓
exact collision analysis
        ↓
transient transformed geometry
        ↓
generic kinematic sweep
        ↓
domain EL sweep integration
```

An exploratory preliminary AZ/EL rotator concept has also been created directly in FreeCAD.

However, that concept is **not accepted as proof of the intended integrated MechCAD workflow**, because it bypassed important layers such as:

- specialist agent orchestration;
- engineering library usage;
- canonical design/proposal flow;
- integrated transmission/material reasoning.

Therefore, the next goal is not simply:

```text
"make another FreeCAD model"
```

The next goal is:

```text
prove that the existing harness pieces are connected correctly
```

and then use the connected system to synthesize a mechanical concept.

---

# 22. Current Documentation / Integration Phase

A new universal documentation baseline has been created to describe MechCAD as a general-purpose engineering harness rather than an antenna-specific system.

The documentation now covers:

- universal system contract;
- engineering workflow;
- runtime flow;
- subsystem contracts;
- capability matrix;
- domain-extension rules;
- independent integration-audit procedure.

The universal documentation baseline has now been hardened and reconciled. It distinguishes `FOUNDATION`, `REQUIRED_CURRENT`, `TARGET_NEXT`, and `FUTURE`; separates FreeCAD from build123d and torque from gear calculation; records M6B/M7 traceability; and defines the independent audit matrix.

Current sequence:

```text
documentation baseline hardened
        ↓
independent implementation/integration audit
        ↓
close critical wiring gaps
        ↓
universal connected acceptance workflow
```

This overview is a project-status source, not runtime proof. The clean-session audit must determine actual implementation and integration verdicts.

---

# 23. What Is Already Proven

The project already has strong proof for individual foundations.

## Canonical State and Change Control

Proven:

- immutable DesignState revisions;
- hashing;
- state binding;
- ChangeProposal/ChangeSet boundary;
- ownership enforcement;
- dependency invalidation;
- stale Evidence handling.

## Run and Provenance

Proven foundations:

- RunController;
- manifests;
- state-bound execution;
- recovery/resume;
- deterministic provenance.

## Tools and Evidence

Proven foundations:

- Tool Registry;
- ToolBroker;
- torque tool;
- typed ToolCall/ToolResult;
- deterministic Evidence;
- bounded one-tool workflow.

## Agent Boundary

Proven foundations:

- AgentGateway;
- OpenCode transport;
- strict JSON validation;
- real Luna invocation path;
- semantic tool mediation;
- Evidence-grounded follow-up reasoning.

## Constraint Loop

Proven foundations:

- structured missing-input discovery;
- deterministic ConstraintRequest identity;
- satisfaction checking;
- persistence/recovery;
- trusted constraint resolution into a new revision.

## Engineering Providers

Available foundations include:

- `py_gearworks`;
- `build123d`;
- `bd_materials`;
- `sectionproperties`;
- NumPy/SciPy numerical support.

End-to-end production integration of every provider is **not yet assumed**.

## CAD / Geometry

Proven:

- FreeCAD backend;
- typed generic CAD operations;
- rigid assembly placement;
- FCStd/STEP generation paths;
- exact intersection;
- exact distance measurement.

## Kinematics

Proven:

- single-axis generic discrete sweep;
- transient transformed assemblies;
- exact per-sample FreeCAD measurement;
- deterministic collision classification;
- domain adapter using the generic engine.

---

# 24. What Is Not Yet Proven or Still Missing

The following are the most important remaining gaps.

## 24.1. Full Independent Integration Audit

Still needed:

```text
normative contract
        ↓
actual implementation
        ↓
actual caller
        ↓
actual tool/library invocation
        ↓
actual downstream consumer
        ↓
integration/runtime proof
```

The audit must distinguish:

- implemented and connected;
- implemented but unused;
- test-only;
- placeholder/stub;
- missing;
- boundary violation.

## 24.2. Universal End-to-End Mechanical Workflow

Still not proven as one connected production path:

```text
requirements
        ↓
DesignState
        ↓
agent dispatch
        ↓
deterministic engineering tools/libraries
        ↓
proposal
        ↓
new revision
        ↓
CAD
        ↓
assembly
        ↓
kinematic verification
        ↓
engineering Evidence
```

A generic motor-driven rotary bracket is a suitable universal acceptance fixture.

It should be preferred over Yagi for system-level integration testing.

## 24.3. Provider Wiring

Need to prove actual connected call paths for:

- `py_gearworks`;
- `build123d`;
- `bd_materials`;
- `sectionproperties`.

For example:

```text
canonical requirement
        ↓
production agent/service
        ↓
ToolBroker / adapter
        ↓
real engineering library
        ↓
normalized result
        ↓
proposal or derived geometry
        ↓
verification
```

File existence and isolated unit tests are insufficient.

## 24.4. Generic Multi-Axis Kinematics

Current generic sweep is single-axis.

Still needed:

- generic joint/kinematic-chain representation;
- parent-child frame composition;
- multiple revolute joints;
- later revolute/prismatic combinations.

AZ/EL should be only one example of this generic capability.

## 24.5. Real Mechanical Synthesis

A real manufacturable mechanism still requires design synthesis for:

- motor/drive architecture;
- transmission;
- output shaft;
- bearings;
- support structure;
- brackets;
- interfaces;
- cable routing;
- service clearances;
- fasteners;
- assembly sequence.

These should be synthesized through the harness rather than simply drawn manually in FreeCAD.

## 24.6. Material Selection Loop

Material lookup exists as a foundation.

Still needed for a generic end-to-end design:

```text
part requirement
        ↓
candidate materials
        ↓
bd_materials properties
        ↓
mass / structural / thermal evaluation
        ↓
ChangeProposal
        ↓
canonical selection
```

## 24.7. Controlled Load / Structural Workflow

Still needed:

- canonical load cases;
- shaft/bearing reactions;
- bending/torsion;
- deflection;
- safety factors;
- structural acceptance criteria.

Current section properties alone are not structural approval.

## 24.8. Wind / Environmental Loads

Still future for domains that require them.

The model should eventually support generic:

- wind;
- shock;
- vibration;
- acceleration/inertia;
- cable forces;
- thermal environment.

## 24.9. FEA

Still future.

Needs:

```text
verified geometry
        ↓
mesh
        ↓
materials
        ↓
canonical loads
        ↓
solver
        ↓
stress/deformation Evidence
```

with complete provenance.

## 24.10. Dynamics / MuJoCo

Still future.

Needs a generic simulation representation derived from accepted design state.

## 24.11. Manufacturing Readiness

Still future.

Needs:

- final materials;
- tolerances;
- real purchased component interfaces;
- final fasteners;
- manufacturing features;
- assembly instructions;
- drawings;
- BOM;
- production verification.

---

# 25. Updated Universal Roadmap

The roadmap is now better described as follows.

## Phase A — Architecture Baseline — DONE

```text
M0
M1
M2
M3
M4
M5
M5.5
M6A
M6B
```

Result:

- canonical state;
- revisions;
- change control;
- dependencies;
- runs;
- tools;
- evidence;
- agent infrastructure;
- constraint discovery/resolution;
- engineering provider foundations.

## Phase B — Generic CAD / Geometry / Kinematics — DONE

```text
M7A
        ↓
generic CAD
assembly
exact collision

M7C
        ↓
transient analysis
generic discrete single-axis sweep
```

## Phase C — Reference-Domain Exercise — DONE FOR CURRENT SCOPE

```text
M7B
        ↓
reference-domain authority/layout/CAD

M7D
        ↓
thin domain adapter over generic kinematics
```

This phase demonstrates reuse.

It does not mean the full mechanical rotator is finished.

## Phase D — Documentation Hardening — COMPLETE; Integration Audit — NEXT

Tasks:

1. universal architecture documentation hardened;
2. current milestone maturity reconciled;
3. run a clean independent implementation/integration audit next;
4. identify unused or unconnected adapters/services;
5. close critical wiring gaps.

## Phase E — Universal End-to-End Acceptance — NEXT

Use a generic motor-driven rotary bracket.

Prove:

```text
Requirements
        ↓
DesignState
        ↓
Agent
        ↓
Tool / engineering provider
        ↓
Evidence
        ↓
Proposal
        ↓
ChangeSet
        ↓
new revision
        ↓
CAD part
        ↓
assembly
        ↓
kinematic analysis
        ↓
verified result
```

Do not require FEA or dynamics yet.

## Phase F — Generic Multi-Axis Mechanisms — NEXT

Add generic kinematic chains.

Then apply them to:

- pan/tilt;
- antenna rotator;
- robotic joints;
- other mechanisms.

## Phase G — Real Mechanical Design Synthesis — NEXT

Connect:

- transmission reasoning;
- gear/drive providers;
- material evaluation;
- CAD generation;
- assemblies;
- kinematics;
- clearance verification.

The objective is for the harness and agents to synthesize design variables rather than merely draw manually supplied dimensions.

## Phase H — Structural / Load Engineering — LATER

Add:

- load cases;
- shaft/bearing reactions;
- stiffness;
- strength;
- safety factors;
- wind/environmental loads.

## Phase I — FEA / Dynamics / Manufacturing — FUTURE

Add:

- FEA;
- MuJoCo/dynamics;
- continuous-motion verification;
- manufacturing package;
- multi-agent design review;
- optimization.

---

# 26. Current Reference Project: Antenna Rotator

The antenna rotator remains useful as a demanding reference domain.

Current accepted/high-level requirements include concepts such as:

- AZ rotation;
- EL rotation;
- multiple Yagi payloads;
- payload envelopes;
- adjustable carrier layout;
- collision-aware kinematics.

However:

> the reference project must not become the definition of MechCAD.

Generic core layers must remain reusable for:

- gearboxes;
- camera pan/tilt;
- robotic joints;
- rotary tables;
- linear mechanisms;
- motorized fixtures;
- other mechanical systems.

The rotator is now best used as a domain-level validation case after the universal connected workflow is proven.

---

# 27. What the System Fundamentally Must Not Do

The LLM must not:

- directly edit DesignState;
- invent authoritative engineering input;
- perform critical engineering calculations without trusted tool boundaries;
- choose trusted IDs;
- choose revision/state hashes;
- create canonical Evidence itself;
- bypass ownership;
- bypass schema validation;
- silently modify canonical CAD/design state;
- use stale Evidence as current;
- convert placeholders into final engineering decisions without an accepted proposal;
- treat a successful CAD model as proof of structural/manufacturing correctness.

---

# 28. Updated Trust Model

```text
USER / EXTERNAL AUTHORITY
        ↓
Requirements / Constraints
        ↓
Trusted Harness
        ↓
DesignState / revisions / hashes / ownership
        ↓
Agent orchestration
        ↓
LLM reasoning
        ↓
semantic requests / findings / proposals
        ↓
ToolBroker / engineering providers
        ↓
deterministic ToolResult
        ↓
Evidence
        ↓
ChangeProposal / ChangeSet
        ↓
new canonical revision
        ↓
derived CAD / analysis
        ↓
verification
```

Below the trusted harness sit deterministic engineering providers:

```text
torque calculations
gear calculations
material properties
section properties
parametric geometry
FreeCAD
future FEA
future dynamics
```

None of those providers independently owns the design.

---

# 29. Current Work in One View

## DONE

- canonical `DesignState`;
- immutable revisions/hashes;
- ChangeProposal/ChangeSet boundary;
- ownership;
- dependency invalidation;
- RunController/manifests;
- Tool Registry/ToolBroker;
- ToolCall/ToolResult;
- deterministic Evidence;
- AgentGateway;
- OpenCode/Luna structured execution foundation;
- transmission bounded reasoning;
- semantic tool mediation;
- constraint discovery;
- constraint resolution;
- engineering library adapters/foundations;
- FreeCAD backend;
- generic typed CAD operations;
- generic assembly support;
- exact collision/clearance analysis;
- transient FreeCAD measurement;
- generic discrete single-axis kinematic sweep;
- current Yagi reference-domain carrier/layout work;
- current EL reference/sweep domain integration;
- universal architecture documentation baseline.

## CURRENT STATUS

- universal documentation baseline hardened;
- M6/M7 maturity traceability reconciled;
- provider identity/version contracts documented;
- full independent audit matrix prepared;
- independent implementation/integration audit is the next quality gate.

## NEXT

- clean independent integration audit;
- close discovered wiring gaps;
- universal motor-driven rotary-bracket acceptance workflow;
- generic multi-axis kinematic chain;
- connected mechanical synthesis workflow.

## LATER / FUTURE

- structural load workflow;
- wind/environmental loads;
- FEA;
- MuJoCo/dynamics;
- continuous collision-free motion proof;
- manufacturing readiness;
- broad multi-agent engineering review;
- optimization.

---

# 30. Important Current Limitation

The project now contains many individually working foundations, but that does **not** yet prove that they all participate in one coherent production design workflow.

For example:

```text
PyGearworksAdapter exists
```

does not automatically prove:

```text
DesignState
    -> agent
    -> ToolBroker
    -> py_gearworks
    -> gear result
    -> build123d
    -> FreeCAD assembly
    -> verification
```

Likewise, a FreeCAD mechanism created directly through MCP/native primitives does not prove the intended harness architecture was exercised.

The next major quality gate is therefore **integration proof**, not simply more CAD geometry.

---

# 31. Current Status in One Sentence

**MechCAD Harness now has a hardened universal documentation baseline for accepted canonical-state, change-control, tool, Evidence, agent, constraint, CAD, transient-analysis, and discrete-kinematic foundations; the current priority is a clean independent audit of actual subsystem implementation and wiring, followed by critical wiring fixes and one domain-neutral connected mechanical workflow before structural, FEA, dynamics, and manufacturing layers.**
