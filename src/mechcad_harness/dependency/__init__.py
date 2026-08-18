"""Dependency package reserved for later milestones."""
from .errors import (
    DependencyConfigError,
    DependencyCycleError,
    DependencyError,
    EvidenceConflictError,
    EvidenceIntegrityError,
    InvalidationError,
)
from .graph import DependencyGraph, path_matches
from .models import ChangeImpact, DependencyEdge, DependencyRule, EvidenceFreshness, InvalidationRecord

__all__ = [
    "ChangeImpact",
    "DependencyConfigError",
    "DependencyCycleError",
    "DependencyEdge",
    "DependencyError",
    "DependencyGraph",
    "DependencyRule",
    "EvidenceConflictError",
    "EvidenceFreshness",
    "EvidenceIntegrityError",
    "InvalidationError",
    "InvalidationRecord",
    "path_matches",
]


def __getattr__(name: str):
    if name == "EvidenceStore":
        from .storage import EvidenceStore
        return EvidenceStore
    raise AttributeError(name)


__all__.append("EvidenceStore")
