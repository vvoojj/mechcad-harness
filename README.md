# MechCAD Harness

MechCAD Harness M0 is the typed Python foundation for a future engineering
workflow system. It provides readable identifiers, minimal Pydantic v2 domain
models, placeholder YAML configuration, and tests.

## M0 Boundary

M0 deliberately excludes agents, OpenCode integration, CAD, FreeCAD, FEA,
scheduling, dependency execution, LLM workflows, databases, persistence, and
external services. The package has no execution behavior.

`DesignState` is the canonical engineering state. Proposals, results,
validation records, issues, and evidence are separate records that bind to a
revision and state hash; they do not implicitly mutate canonical state.

## Development

```text
python -m pip install -e ".[test]"
pytest -q
```

The `config/` files are schema/version-marked placeholders and intentionally
contain no runtime integration settings.

## M1 State Foundation

M1 stores canonical state under `workspace/projects/<project_id>/`. A
`DesignState` is serialized as UTF-8 JSON with sorted keys, compact separators,
and JSON-native values. That complete payload, excluding no `DesignState`
fields and excluding all external records, is hashed with SHA-256 as
`sha256:<hex digest>`.

The state flow is:

```text
DesignState
  -> canonical JSON
  -> SHA-256 state hash
  -> immutable revision snapshot
  -> lightweight current.json pointer
```

Revision snapshots are numbered monotonically from 1 and cannot be overwritten.
Loading a snapshot recomputes its hash and rejects tampering. Later agents may
propose changes, but only the harness will create new canonical revisions.

## M2 ChangeSet Foundation

M2 is the deterministic mutation boundary:

```text
ChangeProposal
  -> stale revision/hash check
  -> ownership check
  -> ChangeSet
  -> complete operation validation
  -> Pydantic DesignState validation
  -> new immutable revision
```

Proposals never mutate `DesignState` directly. Supported operations are `add`,
`replace`, and `remove` over literal JSON-Pointer-like paths. Ownership is a
deterministic policy loaded from `config/ownership.yaml`; ungoverned paths fail
closed. Failed ChangeSets do not create revisions or move `current.json`.
Detailed ownership, dependency invalidation, and orchestration are later
milestones.
