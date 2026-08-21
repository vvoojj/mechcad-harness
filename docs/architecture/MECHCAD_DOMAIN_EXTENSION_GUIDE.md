# MechCAD Domain Extension Guide

**Maturity:** The extension boundary is a `FOUNDATION` and therefore mandatory baseline audit scope. A domain capability may be `REQUIRED_CURRENT` when its accepted contract is required by the current baseline. Broader connected domain services are `TARGET_NEXT`; structural, dynamics, manufacturing, and optimization extensions are `FUTURE` unless separately accepted.

## Extension Contract

To add an arbitrary mechanical domain:

1. Define external authority, requirements, interfaces, and constraints.
2. Define typed domain authority models.
3. Define canonical `DesignState` paths.
4. Assign owner identity and allowed proposal scope.
5. Define a domain-specific `DesignSpec`.
6. Define deterministic synthesis/evaluation services.
7. Invoke ToolBroker and engineering-library adapters as appropriate.
8. Produce structured results, issues, constraint requests, or proposals.
9. Apply accepted changes through `ChangeSet` and `ChangeEngine`.
10. Compile accepted specs into generic CAD programs.
11. Use generic CAD backends and assembly services.
12. Use generic collision, transient, kinematic, and future structural analysis.
13. Persist state-bound evidence and hashed artifacts.
14. Iterate through dependency invalidation.

## Non-Bypass Rules

Domain modules must not put domain assumptions into generic CAD primitives or generic kinematics, bypass ownership, mutate `DesignState` directly, treat temporary CAD as authority, or bypass `ChangeProposal` when canonical state must change.

## Short Examples

**Gearbox:** transmission requirements, candidate ratio, gear provider, proposal, generic gear CAD, assembly verification.

**Robotic revolute joint:** joint frame and range, typed link spec, generic `RevoluteAxis`, transient sweep, future dynamics.

**Camera pan/tilt:** two domain joints over generic frames and transforms; no requirement that core code call them AZ/EL.

**Structural mounting frame:** frame authority, section/material facts, generic part programs, future load/stress analysis.

**Antenna rotator:** payload and carrier are domain records; they reuse generic layout, CAD, collision, and kinematics. They are not the universal model.

## Reference Domain: Antenna Payload / Rotator

Current Yagi modules demonstrate a domain chain of payload authority, carrier synthesis, sliding architecture, preliminary packaging CAD, collision-layout synthesis, kinematic reference, EL reference, and EL sweep adapter over generic M7C. `YagiCollisionLayoutSpec`, `YagiKinematicReferenceModel`, `YagiELKinematicReference`, and `YagiELSweepReference` are domain-layer types.

The reference remains unresolved in important ways: collision envelopes are not RF or manufacturing dimensions; preliminary carrier packaging is not final extrusion geometry; structural verification is incomplete; physical embodiment and final joint geometry may remain unresolved; parametric values cannot be promoted silently; and discrete sweeps do not prove continuous collision-free motion.
