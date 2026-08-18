__all__ = [
    "ChangeConflictError",
    "ChangeEngine",
    "ChangeError",
    "ChangeOperation",
    "ChangeSetValidationError",
    "InvalidChangePathError",
    "OperationType",
    "OwnershipPolicy",
    "OwnershipViolationError",
    "StaleProposalError",
    "apply_operation",
]


def __getattr__(name: str):
    if name in {
        "ChangeConflictError",
        "ChangeError",
        "ChangeSetValidationError",
        "InvalidChangePathError",
        "OwnershipViolationError",
        "StaleProposalError",
    }:
        from . import errors
        return getattr(errors, name)
    if name in {"ChangeOperation", "OperationType"}:
        from . import operations
        return getattr(operations, name)
    if name == "OwnershipPolicy":
        from .ownership import OwnershipPolicy
        return OwnershipPolicy
    if name in {"ChangeEngine", "apply_operation"}:
        from .engine import ChangeEngine, apply_operation
        return {"ChangeEngine": ChangeEngine, "apply_operation": apply_operation}[name]
    if name == "AppliedChangeResult":
        from .engine import AppliedChangeResult
        return AppliedChangeResult
    raise AttributeError(name)

__all__.append("AppliedChangeResult")
