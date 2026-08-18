# MechCAD Harness M5.5A Backend Foundation Design

## Goal

M5.5A adds a small trusted foundation for future external engineering backend
adapters. It does not add an external engineering dependency or perform any
external calculation.

## Boundaries

The future flow remains:

```text
ToolBroker -> MechCAD Tool -> Backend Adapter -> External Library
          -> normalized MechCAD result -> ToolResult -> optional Evidence
```

M5.5A implements only identity, provenance, capability, registry, health, and
safe package metadata inspection. No `execute()` method, dynamic plugin loading,
network activity, installation, CAD, gear, materials, structural, optimization,
OpenCode, agents, or DesignState changes are included.

## Identity And Health

`BackendIdentity` describes the trusted registered adapter and expected library:

- `name`
- `adapter_version`
- `library_name`
- optional `library_version`
- optional `library_source`
- optional `library_revision`
- non-empty capability strings

`BackendHealth` describes the current runtime and never mutates identity:

- backend name
- `AVAILABLE`, `UNAVAILABLE`, `INCOMPATIBLE`, or `UNKNOWN` status
- optional detected package version
- message

Generic M5.5A inspection reports availability only. It does not invent version
constraints to manufacture `INCOMPATIBLE` results.

## Structured Provenance

`BackendProvenance` is one optional structured model containing:

- `backend_name`
- `backend_adapter_version`
- optional `library_name`
- optional `library_version`
- optional `library_source`
- optional `library_revision`

M5 ToolResult and Evidence receive only the optional
`backend_provenance: BackendProvenance | None` field. Existing records without
it remain valid. No flat duplicate backend fields are added.

## Registry

`BackendRegistry` explicitly registers trusted backend adapters. It provides
deterministic `register`, `get`, `list`, and `find_by_capability` operations.
Duplicate names fail. Registry ordering is sorted by backend name. No config can
cause arbitrary imports, and no untrusted module is loaded.

## Package Inspection

Compatibility inspection uses a fixed trusted mapping from logical library names
to distribution metadata names, for example `py_gearworks -> py_gearworks`.
It calls `importlib.metadata.version` only and never imports the target package.
Missing distributions produce deterministic `UNAVAILABLE` health. Unknown
logical names are rejected rather than interpreted as module paths.

## Persistence Boundary

Backend-specific objects are not fields in backend provenance, ToolResult,
Evidence, Run, or DesignState. Only scalar/string normalized models cross
persistence boundaries. Registration and health checks do not mutate canonical
revisions.
