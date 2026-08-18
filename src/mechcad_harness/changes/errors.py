class ChangeError(Exception):
    """Base error for deterministic canonical state changes."""


class InvalidChangePathError(ChangeError):
    pass


class ChangeConflictError(ChangeError):
    pass


class StaleProposalError(ChangeError):
    pass


class OwnershipViolationError(ChangeError):
    pass


class ChangeSetValidationError(ChangeError):
    pass
