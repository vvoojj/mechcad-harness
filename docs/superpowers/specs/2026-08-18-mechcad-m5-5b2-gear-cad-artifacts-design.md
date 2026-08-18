# M5.5B-2 Gear CAD Artifacts Design

## Scope

M5.5B-2 adds deterministic, typed STEP and STL artifacts for external spur
gears behind ToolBroker. It does not add general CAD execution, assemblies,
strength calculations, or artifact persistence to canonical state.

## Architecture

MechCAD-owned CAD inputs are validated before a trusted `PyGearworksAdapter`
creates a transient py_gearworks/build123d part. A focused CAD adapter applies an
explicit central bore, validates scalar geometry, exports STEP and STL into an
immutable scoped artifact directory, and returns only `EngineeringArtifact` and
normalized result models. `ArtifactStore` writes metadata atomically and rejects
duplicate IDs or unsafe paths. ToolBroker supplies task/revision binding and
persists ToolCall before invoking the handler.

Artifacts are derived data. ToolResult and optional Evidence contain metadata and
hashes, never bytes or third-party objects. STEP is authoritative interchange;
STL is derived mesh output. Pair generation is a narrow second operation that
creates two positioned gear artifacts and records the nominal relative transform,
not an assembly model.

## Compatibility

The optional gear profile is Python 3.13 validated on the accepted legacy host
with NumPy 2.3.5, SciPy 1.18.0, build123d 0.11.1, py_gearworks 0.0.18, and exact
revision `2fc2a13d82a9997a65f30c870498f0bb3be62318`. Core MechCAD remains
Python `>=3.11` and has no gear runtime dependency.

## Validation

Generated parts must be valid, non-empty, finite-bounded, and approximately the
requested axial width. Explicit bores must be positive, smaller than the gear's
usable diameter, and reduce volume without eliminating the solid. Published STEP
and STL files must be non-empty and have SHA-256 hashes computed from final bytes.
Repeated exports are tested for byte equality but byte determinism is reported,
not assumed as an architecture guarantee.

## Exclusions

No internal/ring gears, general CAD scripts, arbitrary output paths, GLB/OBJ/DXF/
SVG, FreeCAD, assembly persistence, gear contact mechanics, strength, FEA,
optimization, OpenCode, agents, MCP, or SQL are included.
