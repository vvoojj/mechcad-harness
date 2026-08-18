from .errors import ToolVersionError
from .models import ToolRegistration


class ToolRegistry:
    def __init__(self, registrations: list[ToolRegistration]):
        self._tools = {}
        for registration in registrations:
            key = (registration.name, registration.version)
            if key in self._tools:
                raise ToolVersionError(f"duplicate tool registration: {key}")
            self._tools[key] = registration

    def resolve(self, name: str, version: str) -> ToolRegistration:
        try:
            return self._tools[(name, version)]
        except KeyError as exc:
            raise ToolVersionError(f"tool version not registered: {name}@{version}") from exc

    def registrations(self) -> tuple[ToolRegistration, ...]:
        return tuple(self._tools[key] for key in sorted(self._tools))
