# Task 1: Add Response Mode Contracts And Provenance Fields

Modify `src/mechcad_harness/agents/opencode.py` and `src/mechcad_harness/agents/models.py`; test in `tests/unit/test_opencode_adapter.py`.

Add `OpenCodeResponseMode.NATIVE_JSON_SCHEMA = "native_json_schema"` and `OpenCodeResponseMode.VALIDATED_JSON_TEXT = "validated_json_text"`.

Add `response_mode` to `OpenCodeAdapterConfig`, defaulting to `NATIVE_JSON_SCHEMA`. Reject unknown values with `ValueError("unsupported OpenCode response mode")`. Do not change native behavior, canonical models, prompts, transport, or fallback behavior.

Add normal provenance fields `response_mode: str | None = None` and `schema_hash: str | None = None` to `AgentAdapterProvenance`.

Use TDD: add tests proving native is the default, validated text is selectable only through explicit config, and invalid mode values fail. Run the tests red before implementation and green afterward. Do not commit. Preserve unrelated dirty worktree changes. Write the full implementation report to `docs/superpowers/plans/2026-08-19-m6b1-validated-json-text-task-1-report.md` and return only status, tests, and concerns.
