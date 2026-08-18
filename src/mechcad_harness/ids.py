from enum import StrEnum
from uuid import UUID, uuid4


class IdPrefix(StrEnum):
    PROJECT = "PRJ"
    REVISION = "REV"
    RUN = "RUN"
    TASK = "TASK"
    CHANGE_PROPOSAL = "CP"
    CHANGE_SET = "CS"
    ISSUE = "ISSUE"
    EVIDENCE = "EVD"
    VALIDATION = "VAL"
    DECISION = "DEC"
    REQUIREMENT = "REQ"
    COMPONENT = "PRT"
    ASSEMBLY = "ASM"
    MATERIAL = "MAT"
    INTERFACE = "JNT"
    LOAD_CASE = "LC"


def generate_id(prefix: IdPrefix) -> str:
    if not isinstance(prefix, IdPrefix):
        raise ValueError(f"unknown ID prefix: {prefix!r}")
    return f"{prefix.value}-{uuid4()}"


def id_prefix(value: str) -> str:
    prefix, separator, suffix = value.partition("-")
    if not separator or not suffix:
        raise ValueError("ID must have a prefix and UUID suffix")
    try:
        UUID(suffix)
    except ValueError as exc:
        raise ValueError("ID suffix must be a UUID") from exc
    if prefix not in {item.value for item in IdPrefix}:
        raise ValueError(f"unknown ID prefix: {prefix!r}")
    return prefix
