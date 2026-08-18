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
