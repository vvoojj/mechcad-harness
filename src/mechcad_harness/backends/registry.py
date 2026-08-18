from .errors import BackendNotFoundError, BackendRegistrationError


class BackendRegistry:
    def __init__(self, backends=()):
        self._backends = {}
        for backend in backends:
            self.register(backend)

    def register(self, backend) -> None:
        name = backend.identity.name
        if name in self._backends:
            raise BackendRegistrationError(f"backend already registered: {name}")
        self._backends[name] = backend

    def get(self, name: str):
        try:
            return self._backends[name]
        except KeyError as exc:
            raise BackendNotFoundError(f"backend not found: {name}") from exc

    def list(self):
        return tuple(self._backends[name] for name in sorted(self._backends))

    def find_by_capability(self, capability: str):
        return tuple(backend for backend in self.list() if capability in backend.identity.capabilities)
