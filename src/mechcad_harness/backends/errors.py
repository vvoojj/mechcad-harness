class BackendError(Exception):
    pass


class BackendNotFoundError(BackendError):
    pass


class BackendRegistrationError(BackendError):
    pass


class BackendUnavailableError(BackendError):
    pass


class BackendCompatibilityError(BackendError):
    pass


class BackendProvenanceError(BackendError):
    pass
