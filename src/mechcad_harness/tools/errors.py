class ToolErrorBase(Exception):
    pass


class ToolRegistryError(ToolErrorBase):
    pass


class ToolVersionError(ToolRegistryError):
    pass


class ToolPermissionError(ToolErrorBase):
    pass


class ToolExecutionError(ToolErrorBase):
    pass


class ToolPersistenceError(ToolErrorBase):
    pass
