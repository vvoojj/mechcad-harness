"""Neutral canonical JSON serialization primitive (F2 remediation).

This module is a **dependency leaf**: it must import only the Python standard
library and must never import another ``mechcad_harness`` subsystem. That
invariant lets low-level packages (``models``, ``backends``, ``tools``,
``state``, ``structural``, ``candidates``) share one canonical byte contract
without inverting the ``models -> state -> models`` layering.

The contract is the accepted M0/M2 content-identity byte contract used by
``state.hashing.canonical_json``::

    json.dumps(payload, ensure_ascii=False, sort_keys=True,
               separators=(",", ":")).encode("utf-8")

The shared primitive centralizes canonical JSON *byte serialization* only. It
does not own hashing policy, artifact byte hashing, volatile-key filtering, or
the coercive ``default=str`` contract; those remain separate authorities.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_json_text(payload: Any) -> str:
    """Return the canonical JSON text for ``payload``.

    Raises ``TypeError`` for values the strict contract cannot serialize; it
    deliberately does not coerce values via ``default=str``.
    """
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_json_bytes(payload: Any) -> bytes:
    """Return the canonical UTF-8 JSON bytes for ``payload``."""
    return canonical_json_text(payload).encode("utf-8")


__all__ = ["canonical_json_bytes", "canonical_json_text"]
