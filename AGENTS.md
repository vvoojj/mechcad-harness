# Agent Instructions

This repository currently implements only the MechCAD Harness M0 bootstrap.

- Keep changes inside this repository.
- Preserve Python 3.11+, Pydantic v2, and UTC-aware datetime requirements.
- Keep models minimal and reject empty required strings and non-positive revisions.
- Treat `DesignState` as canonical state; proposals, results, validation, and
  evidence remain separate bindable records.
- Do not add agents, OpenCode integration, CAD, FreeCAD, FEA, scheduling,
  dependency execution, LLM workflows, databases, or external services in M0.
- Do not commit unless the user explicitly requests it.
