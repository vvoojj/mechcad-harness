# M6B-1 Validated JSON Text Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `VALIDATED_JSON_TEXT` OpenCode transport mode for the Luna profile while keeping strict native JSON Schema mode as the default and never using automatic fallback.

**Architecture:** Extend `OpenCodeAdapterConfig` with an explicit response-mode value. Keep the existing session/model/provenance flow shared, but construct and extract responses through two mutually exclusive branches: native mode uses `info.structured_output`; validated-text mode omits the native `format` envelope and validates the complete ordered text parts. Record response mode and generated schema hash in normal provenance/metadata, and hash the exact final request payload including mode and prompt.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, OpenCode Desktop HTTP API, existing `AgentGateway` and `FakeAgentAdapter` contracts.

## Global Constraints

- `NATIVE_JSON_SCHEMA` remains the default response mode.
- Native mode must fail closed on `StructuredOutputError` or missing `info.structured_output`.
- Native mode must never parse ordinary text parts.
- `VALIDATED_JSON_TEXT` must omit the native `format` envelope entirely.
- `VALIDATED_JSON_TEXT` must validate the complete text with `AgentAuthoredResponsePayload.model_validate_json(text)`.
- JSON whitespace around one document is accepted; fences, prose, multiple documents, repair, extraction, regex recovery, and merging are forbidden.
- Any OpenCode `info.error` in text mode fails before text validation.
- The generated `AgentAuthoredResponsePayload.model_json_schema()` is the only prompt/schema source of truth.
- `retryCount` remains `0`; no retry experiment is added.
- `AgentAuthoredResponsePayload`, canonical models, `AgentGateway`, materialization authority, and `FakeAgentAdapter` behavior remain unchanged.
- No automatic native-to-text fallback or dynamic mode switching is allowed.
- No production commit is created.

---

### Task 1: Add Response Mode Contracts And Provenance Fields

**Files:**
- Modify: `src/mechcad_harness/agents/opencode.py:41-60,149-190`
- Modify: `src/mechcad_harness/agents/models.py:38-51`
- Test: `tests/unit/test_opencode_adapter.py`

**Interfaces:**
- Add `OpenCodeResponseMode.NATIVE_JSON_SCHEMA = "native_json_schema"`.
- Add `OpenCodeResponseMode.VALIDATED_JSON_TEXT = "validated_json_text"`.
- Add `OpenCodeAdapterConfig.response_mode`, defaulting to native mode and rejecting unknown values.
- Add normal `response_mode` and `schema_hash` fields to `AgentAdapterProvenance`.

- [ ] **Step 1: Write failing configuration and provenance tests**

Add tests proving native is the default, validated text is selectable only by explicit config, invalid values fail, and provenance can carry both mode and schema hash:

```python
def test_response_mode_defaults_to_native():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeResponseMode

    config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna")

    assert config.response_mode == OpenCodeResponseMode.NATIVE_JSON_SCHEMA


def test_validated_text_mode_requires_explicit_config():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig, OpenCodeResponseMode

    config = OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", response_mode=OpenCodeResponseMode.VALIDATED_JSON_TEXT)

    assert config.response_mode == OpenCodeResponseMode.VALIDATED_JSON_TEXT


def test_unknown_response_mode_is_rejected():
    from mechcad_harness.agents.opencode import OpenCodeAdapterConfig

    with pytest.raises(ValueError, match="unsupported OpenCode response mode"):
        OpenCodeAdapterConfig(project_directory="E:/repo/mechcad-harness", provider_id="screenpipe", model_id="gpt-5.6-luna", response_mode="fallback")
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `py -m pytest -q tests/unit/test_opencode_adapter.py -k "response_mode"`

Expected: FAIL because the response-mode namespace, config field, and provenance fields do not exist.

- [ ] **Step 3: Implement the minimal contracts**

Add the response-mode namespace and config validation alongside `OpenCodeModelSelection`:

```python
class OpenCodeResponseMode:
    NATIVE_JSON_SCHEMA = "native_json_schema"
    VALIDATED_JSON_TEXT = "validated_json_text"


class OpenCodeAdapterConfig:
    def __init__(self, *, ..., response_mode=OpenCodeResponseMode.NATIVE_JSON_SCHEMA):
        ...
        if response_mode not in (OpenCodeResponseMode.NATIVE_JSON_SCHEMA, OpenCodeResponseMode.VALIDATED_JSON_TEXT):
            raise ValueError("unsupported OpenCode response mode")
        self.response_mode = response_mode
```

Add `response_mode: str | None = None` and `schema_hash: str | None = None` to `AgentAdapterProvenance`. Do not alter canonical domain models.

- [ ] **Step 4: Run focused tests**

Run: `py -m pytest -q tests/unit/test_opencode_adapter.py -k "response_mode"`

Expected: PASS.

### Task 2: Add Red Tests For Strict Native And Validated-Text Extraction

**Files:**
- Modify: `tests/unit/test_opencode_adapter.py`

**Interfaces:**
- Tests use the existing `OpenCodeAgentAdapter.invoke()` path with monkeypatched transport.
- Native responses place authoritative data at `response["info"]["structured_output"]`.
- Validated-text responses place authoritative data only in ordered `parts` text entries.

- [ ] **Step 1: Add native fail-closed regression tests**

Add tests proving native `StructuredOutputError` fails even with valid text, native mode sends `format`, and native valid structured output ignores conflicting text. Existing native tests should be retained and expanded with an assertion that `response_mode` and `schema_hash` are normal provenance fields.

- [ ] **Step 2: Add validated-text acceptance and rejection tests**

Add tests for:

```python
def test_validated_text_accepts_one_exact_json_document(monkeypatch): ...
def test_validated_text_accepts_surrounding_json_whitespace(monkeypatch): ...
def test_validated_text_omits_native_format_and_does_not_require_structured_output(monkeypatch): ...
def test_validated_text_rejects_empty_text(monkeypatch): ...
def test_validated_text_rejects_malformed_json(monkeypatch): ...
def test_validated_text_rejects_markdown_fences(monkeypatch): ...
def test_validated_text_rejects_prose_prefix_and_suffix(monkeypatch): ...
def test_validated_text_rejects_multiple_documents(monkeypatch): ...
def test_validated_text_rejects_extra_root_fields(monkeypatch): ...
def test_validated_text_rejects_nested_canonical_constraint_request(monkeypatch): ...
def test_validated_text_accepts_plain_string_constraint_request(monkeypatch): ...
def test_validated_text_rejects_tool_parts(monkeypatch): ...
def test_validated_text_error_precedes_valid_text(monkeypatch): ...
```

Each valid fixture must contain exactly the six authored root fields. The nested constraint-request rejection fixture must use a canonical object shape rather than a string. Assertions must check failure kinds and that no raw text is persisted in provenance diagnostics.

- [ ] **Step 3: Add request hash and schema injection assertions**

Capture the outgoing message payload and assert:

```python
assert "format" not in payload
assert "OUTPUT CONTRACT" in payload["parts"][0]["text"]
assert json.dumps(AgentAuthoredResponsePayload.model_json_schema(), sort_keys=True, separators=(",", ":")) in payload["parts"][0]["text"]
assert outcome.provenance.response_mode == "validated_json_text"
assert outcome.provenance.schema_hash.startswith("sha256:")
assert outcome.provenance.request_hash != native_request_hash
```

- [ ] **Step 4: Run focused tests to verify the new tests fail for the intended reasons**

Run: `py -m pytest -q tests/unit/test_opencode_adapter.py`

Expected: existing native tests pass or expose only expected fixture updates; new validated-text tests fail because the mode and extraction branch are not implemented.

### Task 3: Implement Explicit Request Construction And Prompt Schema Injection

**Files:**
- Modify: `src/mechcad_harness/agents/opencode.py:149-190,282-303`
- Test: `tests/unit/test_opencode_adapter.py`

**Interfaces:**
- Add a mode-aware deterministic prompt method, preserving the current context and authored contract content.
- Native mode returns the current prompt semantics and includes the native format payload.
- Text mode appends the generated schema in the output contract and omits `format`.

- [ ] **Step 1: Implement schema hashing and final-prompt construction**

Compute one deterministic schema JSON representation and hash it:

```python
schema_json = json.dumps(schema, sort_keys=True, separators=(",", ":"))
schema_hash = f"sha256:{hashlib.sha256(schema_json.encode()).hexdigest()}"
prompt = self._prompt(request, response_mode=self.config.response_mode, schema_json=schema_json)
```

For validated text, include exact instructions:

```text
OUTPUT CONTRACT
Return exactly one JSON object and no other text.
The object must conform exactly to the following generated JSON Schema:
<schema_json>
No Markdown. No code fences. No extra fields.
```

Do not create a handwritten schema or add repair instructions.

- [ ] **Step 2: Implement mode-aware message payloads**

Construct the common payload with `agent`, `tools`, and one text part. Add the explicit model when configured. Only native mode adds:

```python
payload["format"] = {"type": "json_schema", "schema": schema, "retryCount": 0}
```

Validated-text mode must not contain a `format` key.

- [ ] **Step 3: Include mode and final prompt in the request hash**

Hash the canonical final message payload plus the selected mode, or equivalently ensure the canonical payload contains the mode as a deterministic request-bound field without sending a new unsupported wire field. The implementation must make mode and exact final prompt affect the hash while preserving the wire request shape.

- [ ] **Step 4: Run request-construction tests**

Run: `py -m pytest -q tests/unit/test_opencode_adapter.py -k "format or prompt or request_hash or response_mode"`

Expected: PASS.

### Task 4: Implement Mutually Exclusive Response Extraction And Metadata

**Files:**
- Modify: `src/mechcad_harness/agents/opencode.py:168-187,225-280`
- Modify: `src/mechcad_harness/agents/models.py:38-51`
- Test: `tests/unit/test_opencode_adapter.py`

**Interfaces:**
- Native extraction remains `info.structured_output` only.
- Validated-text extraction concatenates ordered `type == "text"` parts and calls `AgentAuthoredResponsePayload.model_validate_json(text)` on the complete string.
- Both modes return `AgentAdapterExecutionOutcome` with canonical authored hash metadata.

- [ ] **Step 1: Implement separate mode branches**

Branch on `self.config.response_mode` after common response metadata and tool-part checks:

```python
if self.config.response_mode == OpenCodeResponseMode.NATIVE_JSON_SCHEMA:
    authored_response = self._extract_structured_response(response)
else:
    authored_response = self._extract_validated_text_response(response)
```

Do not call text extraction from native errors. In text mode, inspect `info.error` first and raise a dedicated typed failure before reading or validating text. Reject missing/empty text, malformed JSON, Pydantic failures, and tools without recovery.

- [ ] **Step 2: Add precise diagnostics**

Keep normal `response_mode` and `schema_hash` on successful provenance. Failure diagnostics may include only safe shape/error metadata and must distinguish native OpenCode rejection from Pydantic authored validation failure and validated-text protocol failure. Never include raw assistant text.

- [ ] **Step 3: Preserve authored hash semantics**

Calculate `authored_response_hash` only after `AgentAuthoredResponsePayload` validation and from deterministic canonical model JSON. Ensure valid JSON whitespace variations produce the same authored hash.

- [ ] **Step 4: Run focused adapter tests**

Run: `py -m pytest -q tests/unit/test_opencode_adapter.py`

Expected: all adapter tests pass, including existing native fail-closed tests.

### Task 5: Verify Gateway And Fake Adapter Boundaries

**Files:**
- Test: `tests/unit/test_agent_gateway.py`
- Test: `tests/unit/test_agents_runtime.py`
- Test: `tests/unit/test_transmission_agent.py`
- Modify only if a test needs a response-mode assertion; do not modify gateway/materialization authority.

**Interfaces:**
- `AgentGateway` consumes a successful `AgentAdapterExecutionOutcome` regardless of OpenCode response mode.
- `materialize_agent_response` remains the only authored-to-canonical conversion.
- `FakeAgentAdapter` does not instantiate or inspect OpenCode configuration.

- [ ] **Step 1: Add gateway success assertions**

Assert successful authored validation is the prerequisite for materialization, deterministic harness IDs are generated, revision/state binding remains exact, and response hashes remain present. Add a failure test proving invalid validated-text output does not call materialization.

- [ ] **Step 2: Add fake adapter independence assertion**

Instantiate `FakeAgentAdapter` without OpenCode configuration and assert it still returns its existing deterministic outcome.

- [ ] **Step 3: Run gateway/runtime tests**

Run: `py -m pytest -q tests/unit/test_agent_gateway.py tests/unit/test_agents_runtime.py tests/unit/test_transmission_agent.py`

Expected: PASS.

### Task 6: Document Explicit Mode And Compatibility Rationale

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-19-m6b1-validated-json-text-design.md`

- [ ] **Step 1: Document authority and security boundaries**

State that validated JSON text is not trusted because it is JSON; it becomes acceptable only after whole-document JSON parsing plus strict Pydantic authored validation. State that IDs, binding, statuses, actor/base fields, and state mutation remain harness-owned.

- [ ] **Step 2: Document native versus validated-text modes**

Explicitly state that native mode remains fail-closed and that validated text is a separately selected transport, never fallback. Include the observed OpenCode `1.18.18`/Luna compatibility reason and schema hash/provenance expectations.

- [ ] **Step 3: Run documentation and whitespace checks**

Run: `git diff --check`

Expected: no whitespace errors.

### Task 7: Run Required Offline Verification

**Files:**
- No additional source changes unless a failing test requires a targeted correction.

- [ ] **Step 1: Run focused tests**

Run: `py -m pytest -q tests/unit/test_opencode_adapter.py tests/unit/test_agent_gateway.py tests/unit/test_agents_runtime.py tests/unit/test_transmission_agent.py`

- [ ] **Step 2: Run full offline suite**

Run: `py -m pytest -q`

Expected: zero failures; record passed/skipped counts.

- [ ] **Step 3: Run compile check**

Run: `py -m compileall -q src tests`

Expected: exit code 0 with no output.

- [ ] **Step 4: Run whitespace check**

Run: `git diff --check`

Expected: no whitespace errors.

### Task 8: Run Gated Live Acceptance Sequence

**Files:**
- No source files modified by the probes.

**Interfaces:**
- All runs use `screenpipe/gpt-5.6-luna`, explicit model selection, `E:/repo/mechcad-harness`, no tools, fresh sessions, and config-only `VALIDATED_JSON_TEXT`.

- [ ] **Step 1: Run one fresh generic Luna one-shot**

Require exactly one complete authored JSON document with all six root fields, string findings/issues/constraint requests, and empty change proposals. Inspect structured diagnostics only; never repair text.

Expected: either a strict `PASS` or an exact structural text protocol failure. Stop on failure.

- [ ] **Step 2: Run five fresh generic Luna controls only after one-shot PASS**

Require `5/5 PASS`. Stop immediately if any run fails.

- [ ] **Step 3: Run five fresh transmission controls only after generic `5/5 PASS`**

Require `5/5 PASS`, with findings and at least one issue or constraint request, zero proposals, no tools. Stop immediately if any run fails.

- [ ] **Step 4: Run one real AgentGateway acceptance only after transmission `5/5 PASS`**

Require succeeded `AgentResult`, canonical materialization, deterministic IDs, exact revision/state binding, authored/materialized hashes, response mode and provider/session/request provenance, no tools, no Evidence, no DesignState mutation, and no M2 application.

- [ ] **Step 5: Report exact final classification**

If all gates pass, report `MECHCAD_M6B1_TRANSMISSION_REASONING_AGENT_COMPLETE`. Otherwise report the exact failed boundary and do not emit the completion marker.
