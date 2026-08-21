# M6B-1 Explicit Validated JSON Text Transport

## Goal

Add an explicit `VALIDATED_JSON_TEXT` OpenCode response mode for the blocked
`screenpipe/gpt-5.6-luna` profile while preserving strict native structured
output as the default and without introducing automatic fallback.

## Configuration

`OpenCodeResponseMode` will expose:

- `NATIVE_JSON_SCHEMA`
- `VALIDATED_JSON_TEXT`

`OpenCodeAdapterConfig.response_mode` defaults to `NATIVE_JSON_SCHEMA`. The
mode is selected only by trusted adapter configuration before invocation. The
environment resolver continues to construct native mode unless its caller
explicitly constructs a config with validated-text mode.

## Native Mode

Native mode behavior is unchanged:

- send `format.type=json_schema` with the generated Pydantic schema;
- send `retryCount=0`;
- treat `info.structured_output` as authoritative;
- fail closed on `StructuredOutputError`;
- fail closed when structured output is missing;
- validate structured output directly with
  `AgentAuthoredResponsePayload.model_validate`;
- never parse ordinary text parts.

## Validated-Text Mode

Validated-text mode is a separate transport contract, not response fallback.
It intentionally omits the native `format` envelope entirely. The request uses
ordinary text generation with the same project, agent, tools, model selection,
session, and message representation otherwise.

The deterministic prompt builder injects the generated
`AgentAuthoredResponsePayload.model_json_schema()` in an `OUTPUT CONTRACT`
section. The generated schema is the only schema source of truth and is
serialized deterministically.

The authoritative response is the ordered concatenation of text parts. The
adapter validates the complete text using
`AgentAuthoredResponsePayload.model_validate_json(text)`. JSON whitespace around
one document is accepted by the JSON parser. Markdown fences, prose prefixes or
suffixes, multiple documents, empty text, malformed JSON, extra fields, legacy
nested canonical objects, and any other invalid whole-document input fail
closed. No extraction, repair, normalization, coercion, regex recovery, or
candidate merging is permitted.

Any OpenCode `info.error` fails before text validation, even when text happens
to be valid JSON. Tool parts remain rejected under the existing no-tools policy.

## Provenance and Hashing

Normal execution provenance/metadata records:

- selected response mode;
- generated authored schema hash;
- provider and model;
- server version;
- configured agent;
- session and message IDs;
- request hash.

The request hash covers the selected response mode and exact final prompt,
including the generated schema. The authored response hash is created only
after successful Pydantic validation and is derived from canonical validated
`AgentAuthoredResponsePayload` serialization, never raw text formatting.

No raw assistant text, credentials, or private reasoning is persisted in
failure diagnostics.

## Trusted Materialization

`AgentGateway` remains unchanged in authority and flow. It materializes a
trusted canonical `AgentResponsePayload` only after successful authored
response validation. Canonical IDs, revision/state binding, statuses, proposal
actor/base binding, and all state mutation rules remain harness-owned.
`FakeAgentAdapter` remains independent of OpenCode transport selection.

## Verification Sequence

Offline tests must cover explicit mode selection, native fail-closed behavior,
text-mode whole-document validation, error precedence, schema injection and
hashing, no repair/fallback, tool rejection, authored hashing, gateway
materialization, and fake adapter independence.

After offline verification:

1. Run one fresh `mechcad-test-agent` Luna validated-text control.
2. If it passes, run five fresh generic Luna controls.
3. If all five pass, run five fresh `mechcad-transmission` controls.
4. If all ten pass, run one real AgentGateway acceptance.

No retries, prompt repair, schema weakening, automatic mode switching, native
fallback, transmission controls, or gateway acceptance may occur before their
specified gate.

## Compatibility Rationale

OpenCode `1.18.18` with `screenpipe/gpt-5.6-luna` repeatedly returned
`StructuredOutputError` without `info.structured_output`, including with
`retryCount=2`, while ordinary text produced semantically valid authored JSON.
The explicit validated-text mode supports that profile without weakening or
renaming the native mode and must not be described as fallback.
