import hashlib
from typing import Any

from mechcad_harness.core.canonical import canonical_json_bytes
from mechcad_harness.models import DesignState

# Narrowly scoped versioned state-hash contract (accepted H1-B reconciliation).
#
# ``state-hash@1`` is the frozen historical rule: the complete serialized
# ``DesignState`` with the ``joint_authority_declarations`` collection excluded.
# ``state-hash@2`` is the current runtime rule: identical to ``state-hash@1``
# except that a *non-empty* ``joint_authority_declarations`` collection is
# included.  For every state with no admitted declarations the two are
# byte-identical, so all existing revisions, stored hashes, pointers, manifests,
# replay identities and evidence are preserved without rewriting.  The exclusion
# is restricted to this one collection and is not a generic empty-field omission.
#
# Non-``DesignState`` values (for example a single resolved authority value) are
# passed through unchanged, matching the historical ``canonical_json`` contract.
_JOINT_AUTHORITY_COLLECTION = "joint_authority_declarations"


def canonical_payload(state: DesignState | Any) -> Any:
    """Return the ``state-hash@2`` payload (complete state, empty H1-B collection omitted)."""
    if not isinstance(state, DesignState):
        return state
    payload = state.model_dump(mode="json")
    if not payload.get(_JOINT_AUTHORITY_COLLECTION):
        payload.pop(_JOINT_AUTHORITY_COLLECTION, None)
    return payload


def canonical_payload_v1(state: DesignState | Any) -> Any:
    """Return the frozen ``state-hash@1`` payload (H1-B collection always excluded)."""
    if not isinstance(state, DesignState):
        return state
    payload = state.model_dump(mode="json")
    payload.pop(_JOINT_AUTHORITY_COLLECTION, None)
    return payload


def canonical_json(state: DesignState | Any) -> bytes:
    return canonical_json_bytes(canonical_payload(state))


def state_hash(state: DesignState | Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(state)).hexdigest()}"


def state_hash_v1(state: DesignState | Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(canonical_payload_v1(state))).hexdigest()}"
