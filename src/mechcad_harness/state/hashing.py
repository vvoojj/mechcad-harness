import hashlib
import json
from typing import Any

from mechcad_harness.models import DesignState


def canonical_payload(state: DesignState) -> dict[str, Any]:
    """Return the complete DesignState payload used for hashing, excluding no state fields."""
    return state.model_dump(mode="json")


def canonical_json(state: DesignState | dict[str, Any]) -> bytes:
    payload = canonical_payload(state) if isinstance(state, DesignState) else state
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def state_hash(state: DesignState | dict[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(state)).hexdigest()}"
