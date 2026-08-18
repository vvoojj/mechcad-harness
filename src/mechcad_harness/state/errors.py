class StateError(Exception):
    """Base error for canonical state operations."""


class RevisionNotFoundError(StateError):
    pass


class RevisionConflictError(StateError):
    pass


class StateIntegrityError(StateError):
    pass
