# MechCAD Harness M2 ChangeSet Design

## Scope

M2 adds the deterministic mutation layer between a proposed engineering change
and a new canonical `DesignState` revision. It excludes agents, OpenCode,
dependency execution, scheduling, CAD, FEA, persistence databases, evidence
storage, invalidation, and conflict resolution.

## Data Flow

```text
ChangeProposal
  -> stale base revision/hash check
  -> operation validation
  -> ownership check
  -> in-memory ChangeSet application
  -> Pydantic DesignState validation
  -> StateManager.create_revision()
```

Only `StateManager` creates canonical revisions. Existing snapshots are read
only, and failed applications do not write a snapshot or update `current.json`.

## Operations

Operations use JSON-Pointer-like paths with `/` separators. M2 supports only
`add`, `replace`, and `remove`; path segments are literal and `~` escaping is
rejected rather than interpreted. Component, material, and other collection
items are addressed by their `id`, for example
`/components/PRT-123/name`. Add supports a missing final object field and a new
collection item at `/components/<id>`; replace and remove require an existing
target. An optional `expected` value provides compare-before-write protection.

## Ownership

Ownership rules are loaded from `config/ownership.yaml` and match exact path
segments plus a single-segment `*` wildcard. A matching rule permits only its
named actor. All paths without an explicit matching rule fail closed. A
`ConstraintRequest` remains a separate non-mutating record.

## Testing

Tests cover successful add/replace/remove operations, multi-operation atomicity,
stale proposal rejection, invalid and missing paths, ownership, Pydantic
revalidation, current-pointer preservation, revision immutability, and the
separation of evidence/results from canonical state.
