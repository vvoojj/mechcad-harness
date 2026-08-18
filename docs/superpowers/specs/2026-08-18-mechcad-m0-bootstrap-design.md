# MechCAD Harness M0 Bootstrap Design

## Scope

M0 establishes a small Python 3.11+ package for the future MechCAD Harness. It
contains typed identifiers, minimal Pydantic v2 domain models, placeholder YAML
configuration, tests, and documentation. It deliberately excludes agents,
OpenCode execution, CAD, FreeCAD, FEA, scheduling, dependency execution, LLM
workflows, databases, and external services.

## Architecture

The package is organized around domain models under `src/mechcad_harness`.
`ids.py` owns readable prefixed identifier generation. Shared model behavior
such as UTC timestamps and revision/state-hash bindings lives in
`models/common.py`; concept-specific models remain in focused modules.

`DesignState` is the canonical engineering state and contains design entities
such as requirements, components, assemblies, materials, interfaces,
constraints, and load cases. Agent outputs, proposals, issues, validation, and
evidence are separate models and never become implicit state mutations.

## Model Rules

- Models use Pydantic v2 with strict-enough practical validation for required
  identifiers, non-empty names, positive revisions, and UTC-aware datetimes.
- Status-like fields use enums.
- Proposals, results, validation results, and evidence can bind to a positive
  `revision` and a non-empty `state_hash`.
- Domain models remain intentionally minimal and have no persistence or
  execution behavior.

## IDs

IDs are strings with stable human-readable prefixes and UUID4 suffixes, for
example `PRJ-<uuid>`, `REV-<uuid>`, and `TASK-<uuid>`. The centralized factory
accepts only known prefixes and supports the requested prefixes without adding
database state.

## Configuration and Verification

Each YAML file has a schema and version marker plus safe empty/default content.
Tests cover prefix formatting and uniqueness, basic model construction,
invalid values, revision/state-hash binding, and separation of canonical state
from evidence/results. The final verification is the project pytest suite and
a directory-tree inspection.
