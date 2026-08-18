import base64
import json
import os
import socket
import hashlib
from pydantic import ValidationError
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from pydantic import Field, field_validator

from .models import AgentAdapterExecutionError, AgentAdapterExecutionOutcome, AgentAdapterIdentity, AgentAdapterProvenance, AgentInvocationRequest, AgentResponsePayload


class OpenCodeAdapterError(RuntimeError):
    pass


class OpenCodeUnavailableError(OpenCodeAdapterError):
    pass


class OpenCodeTransportError(OpenCodeAdapterError):
    pass


class OpenCodeProtocolError(OpenCodeAdapterError):
    pass


class OpenCodeStructuredOutputError(OpenCodeProtocolError):
    pass


class OpenCodeTimeoutError(OpenCodeTransportError):
    pass


class OpenCodeModelSelection:
    EXPLICIT = "explicit"
    SESSION_SELECTED = "session_selected"


class OpenCodeAdapterConfig:
    def __init__(self, *, base_url="http://127.0.0.1:4096", project_directory, username="opencode", provider_id=None, model_id=None, agent_name="build", request_timeout_seconds=60, model_selection=OpenCodeModelSelection.EXPLICIT):
        self.base_url = validate_loopback_url(base_url)
        self.project_directory = normalize_project_directory(project_directory)
        self.username = username
        self.provider_id = provider_id
        self.model_id = model_id
        self.agent_name = agent_name
        self.request_timeout_seconds = float(request_timeout_seconds)
        if model_selection not in (OpenCodeModelSelection.EXPLICIT, OpenCodeModelSelection.SESSION_SELECTED):
            raise ValueError("unsupported OpenCode model selection")
        if model_selection == OpenCodeModelSelection.EXPLICIT and (not provider_id or not model_id):
            raise ValueError("explicit model selection requires provider_id and model_id")
        self.model_selection = model_selection
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")


class OpenCodeHealth:
    def __init__(self, healthy: bool, server_version: str | None, base_url: str, message: str | None = None):
        self.healthy = healthy
        self.server_version = server_version
        self.base_url = base_url
        self.message = message


def validate_loopback_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("OpenCode base_url must be a loopback HTTP origin")
    host = parsed.hostname
    if host is None or host.lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("OpenCode base_url must target loopback")
    if parsed.port is None:
        raise ValueError("OpenCode base_url must include a port")
    return base_url.rstrip("/")


def normalize_project_directory(project_directory: str) -> str:
    normalized = project_directory.replace("\\", "/")
    if not normalized or normalized.endswith("/"):
        raise ValueError("project_directory must be an explicit directory")
    return normalized


class OpenCodeHttpTransport:
    def __init__(self, config: OpenCodeAdapterConfig, password: str):
        if not password:
            raise ValueError("OpenCode password is required")
        self.config = config
        self._auth = base64.b64encode(f"{config.username}:{password}".encode()).decode()

    def request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = Request(self.config.base_url + path, data=data, method=method, headers={"Authorization": f"Basic {self._auth}", "Content-Type": "application/json", "Accept": "application/json", "x-opencode-directory": self.config.project_directory})
        try:
            with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise OpenCodeProtocolError(f"OpenCode HTTP status {response.status}")
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise OpenCodeProtocolError("OpenCode response exceeds size limit")
                try:
                    return json.loads(raw.decode())
                except Exception as exc:
                    raise OpenCodeProtocolError("OpenCode response was not valid JSON") from exc
        except TimeoutError as exc:
            raise OpenCodeTimeoutError("OpenCode request timed out") from exc
        except socket.timeout as exc:
            raise OpenCodeTimeoutError("OpenCode request timed out") from exc
        except OpenCodeAdapterError:
            raise
        except Exception as exc:
            if getattr(exc, "code", None) == 401:
                raise OpenCodeUnavailableError("OpenCode authentication failed") from exc
            raise OpenCodeTransportError("OpenCode request failed") from exc


def resolve_opencode_config_from_environment(*, provider_id: str, model_id: str, agent_name: str = "build") -> tuple[OpenCodeAdapterConfig, str]:
    password = os.getenv("MECHCAD_OPENCODE_PASSWORD") or os.getenv("OPENCODE_SERVER_PASSWORD")
    if not password:
        raise OpenCodeUnavailableError("OpenCode password environment variable is unavailable")
    username = os.getenv("MECHCAD_OPENCODE_USERNAME") or os.getenv("OPENCODE_SERVER_USERNAME") or "opencode"
    config = OpenCodeAdapterConfig(base_url=os.getenv("MECHCAD_OPENCODE_BASE_URL") or "http://127.0.0.1:4096", project_directory=os.getenv("MECHCAD_OPENCODE_PROJECT_DIRECTORY") or "E:/repo/mechcad-harness", username=username, provider_id=provider_id, model_id=model_id, agent_name=agent_name)
    return config, password


class OpenCodeAgentAdapter:
    identity = AgentAdapterIdentity(adapter_name="opencode-http", adapter_version="0.1.0")

    def __init__(self, config: OpenCodeAdapterConfig, password: str):
        self.config = config
        self.transport = OpenCodeHttpTransport(config, password)

    def health(self) -> OpenCodeHealth:
        try:
            payload = self.transport.request("GET", "/global/health")
            if payload.get("healthy") is not True or not payload.get("version"):
                return OpenCodeHealth(False, payload.get("version"), self.config.base_url, "OpenCode health response was unhealthy")
            return OpenCodeHealth(True, payload["version"], self.config.base_url)
        except OpenCodeAdapterError as exc:
            return OpenCodeHealth(False, None, self.config.base_url, str(exc))

    def invoke(self, request: AgentInvocationRequest) -> AgentAdapterExecutionOutcome:
        session_id = message_id = request_hash = actual_provider_id = actual_model_id = None
        validation_diagnostics = None
        health = self.health()
        if not health.healthy:
            raise AgentAdapterExecutionError(health.message or "OpenCode is unavailable", provenance=self._provenance(), failure_kind="unavailable")
        session_body = {"title": "mechcad-agent-invocation", "agent": self.config.agent_name, "permission": [{"permission": "*", "pattern": "*", "action": "deny"}]}
        if self.config.model_selection == OpenCodeModelSelection.EXPLICIT:
            session_body["model"] = {"providerID": self.config.provider_id, "id": self.config.model_id}
        session = self.transport.request("POST", "/session", session_body)
        session_id = session.get("id")
        if not session_id:
            raise AgentAdapterExecutionError("OpenCode session response omitted id", provenance=self._provenance(server_version=health.server_version), failure_kind="protocol")
        schema = AgentResponsePayload.model_json_schema()
        prompt = self._prompt(request)
        message_payload = {"agent": self.config.agent_name, "tools": {}, "format": {"type": "json_schema", "schema": schema, "retryCount": 0}, "parts": [{"type": "text", "text": prompt}]}
        if self.config.model_selection == OpenCodeModelSelection.EXPLICIT:
            message_payload["model"] = {"providerID": self.config.provider_id, "modelID": self.config.model_id}
        request_hash = f"sha256:{hashlib.sha256(json.dumps(message_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}"
        response = self.transport.request("POST", f"/session/{session_id}/message", message_payload)
        info = response.get("info", {})
        message_id = info.get("id")
        actual_provider_id = info.get("providerID")
        actual_model_id = info.get("modelID")
        provenance = self._provenance(server_version=health.server_version, session_id=session_id, message_id=message_id, request_hash=request_hash, provider=actual_provider_id or self.config.provider_id, model=actual_model_id or self.config.model_id)
        if self.config.model_selection == OpenCodeModelSelection.EXPLICIT and (actual_provider_id != self.config.provider_id or actual_model_id != self.config.model_id):
            raise AgentAdapterExecutionError("OPENCODE_MODEL_MISMATCH", provenance=provenance, failure_kind="model_mismatch")
        parts = response.get("parts")
        if not isinstance(parts, list) or any(part.get("type") == "tool" for part in parts):
            raise AgentAdapterExecutionError("OpenCode response contained invalid or tool parts", provenance=provenance, failure_kind="structured_output")
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        try:
            return AgentAdapterExecutionOutcome(response=AgentResponsePayload.model_validate_json(text), provenance=provenance)
        except ValidationError as exc:
            try:
                raw = json.loads(text)
            except Exception:
                raw = None
            validation_diagnostics = {
                "top_level_keys": sorted(raw.keys()) if isinstance(raw, dict) else None,
                "status": raw.get("status") if isinstance(raw, dict) else None,
                "status_type": type(raw.get("status")).__name__ if isinstance(raw, dict) and "status" in raw else None,
                "unexpected_fields": sorted(set(raw.keys()) - set(AgentResponsePayload.model_fields)) if isinstance(raw, dict) else None,
                "missing_fields": sorted(set(AgentResponsePayload.model_fields) - set(raw.keys())) if isinstance(raw, dict) else None,
                "errors": [
                    {
                        "type": item.get("type"),
                        "loc": item.get("loc"),
                        "message": item.get("msg"),
                    }
                    for item in exc.errors(include_url=False)
                ],
            }
            raise AgentAdapterExecutionError("OpenCode structured response failed AgentResponsePayload validation", provenance=provenance.model_copy(update={"validation_diagnostics": validation_diagnostics}), failure_kind="structured_validation") from exc
        except Exception as exc:
            raise AgentAdapterExecutionError("OpenCode structured response failed AgentResponsePayload validation", provenance=provenance, failure_kind="structured_validation") from exc

    def _provenance(self, *, server_version=None, session_id=None, message_id=None, request_hash=None, provider=None, model=None, validation_diagnostics=None) -> AgentAdapterProvenance:
        return AgentAdapterProvenance(adapter_name=self.identity.adapter_name, adapter_version=self.identity.adapter_version, provider=provider or self.config.provider_id or "unknown", model=model or self.config.model_id, transport="opencode-desktop-http", server_version=server_version, configured_agent_name=self.config.agent_name, session_id=session_id, message_id=message_id, project_directory=self.config.project_directory, request_hash=request_hash, validation_diagnostics=validation_diagnostics)

    @staticmethod
    def _extract_response(response: dict) -> AgentResponsePayload:
        parts = response.get("parts")
        if not isinstance(parts, list) or any(part.get("type") == "tool" for part in parts):
            raise OpenCodeStructuredOutputError("OpenCode response contained invalid or tool parts")
        text = "".join(part.get("text", "") for part in parts if part.get("type") == "text")
        try:
            return AgentResponsePayload.model_validate_json(text)
        except Exception as exc:
            raise OpenCodeStructuredOutputError("OpenCode structured response failed AgentResponsePayload validation") from exc

    @staticmethod
    def _prompt(request: AgentInvocationRequest) -> str:
        return "\n".join((
            "You are a reasoning-only MechCAD test agent.",
            "Do not use tools, files, shell, network, or external actions.",
            "Reason only from the supplied context and do not claim missing facts.",
            f"Agent: {request.agent.agent_name}@{request.agent.agent_version}",
            f"Binding: project={request.project_id} run={request.run_id} task={request.task_id} revision={request.bound_revision} state_hash={request.bound_state_hash}",
            "INPUT CONTEXT",
            json.dumps(request.context.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
            "OUTPUT CONTRACT",
            "Return only a value conforming to the supplied native JSON Schema.",
            "The findings field is an array of plain JSON strings.",
            "Each finding is informational text only. Do not return objects inside findings.",
            "Structured canonical-impacting data belongs only in change_proposals, issues, or constraint_requests.",
            "Do not invent fields not present in the supplied JSON Schema.",
            "Do not repeat input project, run, task, revision, or state metadata unless the output schema explicitly contains those fields.",
        ))
