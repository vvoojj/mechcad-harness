class DependencyError(Exception):
    pass


class DependencyConfigError(DependencyError):
    pass


class DependencyCycleError(DependencyConfigError):
    pass


class InvalidationError(DependencyError):
    pass


class EvidenceIntegrityError(DependencyError):
    pass


class EvidenceConflictError(DependencyError):
    pass
