"""Bounded, byte-preserving STEP content identity.

The only normalization in version 1 is the timestamp in the second positional
argument of the single HEADER ``FILE_NAME`` entity.  This is deliberately a
small envelope parser, not an ISO 10303 validator.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import ConfigDict, field_validator

from mechcad_harness.models.common import Model

_MAX_INPUT_BYTES = 128 * 1024 * 1024
_MAX_HEADER_BYTES = 1 * 1024 * 1024
_MAX_PARENTHESIS_DEPTH = 32
_CANONICAL_TIMESTAMP = b"1970-01-01T00:00:00"
_TIMESTAMP_LENGTH = len(_CANONICAL_TIMESTAMP)

_ISO_STAMP = b"ISO-10303-21;"
_HEADER = b"HEADER;"
_DATA = b"DATA;"
_ENDSEC = b"ENDSEC;"
_FILE_NAME = b"FILE_NAME("


class StepContentIdentity(Model):
    """Versioned semantic identity for a STEP byte sequence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm: Literal["step-content-identity@1"]
    content_hash: str

    @field_validator("content_hash")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        prefix = "sha256:"
        digest = value[len(prefix) :] if value.startswith(prefix) else ""
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("content_hash must be a lowercase sha256 digest")
        return value


def canonical_identity_bytes_v1(original_step_bytes: bytes) -> bytes:
    """Return STEP bytes with only the accepted FILE_NAME timestamp replaced."""

    if not isinstance(original_step_bytes, bytes):
        raise TypeError("original_step_bytes must be bytes")
    if len(original_step_bytes) > _MAX_INPUT_BYTES:
        raise ValueError("STEP input exceeds the 128 MiB bound")

    scan = _scan_document(original_step_bytes)
    header_start = scan["header_start"]
    header_end = scan["header_end"]
    if header_end - header_start > _MAX_HEADER_BYTES:
        raise ValueError("STEP HEADER exceeds the 1 MiB bound")
    try:
        original_step_bytes[header_start:header_end].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("STEP HEADER must contain ASCII bytes") from exc

    iso_positions = scan["iso_positions"]
    header_positions = scan["header_positions"]
    data_positions = scan["data_positions"]
    endsec_positions = scan["endsec_positions"]
    if len(iso_positions) != 1:
        raise ValueError("STEP must contain exactly one ISO-10303-21; stamp")
    if len(header_positions) != 1 or len(data_positions) != 1:
        raise ValueError("STEP must contain exactly one HEADER and DATA section")
    if len(endsec_positions) != 2:
        raise ValueError("STEP must contain exactly two ENDSEC; markers")

    iso_start = iso_positions[0]
    header_marker = header_positions[0]
    data_marker = data_positions[0]
    header_end_marker = endsec_positions[0]
    data_end_marker = endsec_positions[1]
    if not (
        iso_start < header_marker < header_end_marker < data_marker < data_end_marker
    ):
        raise ValueError("STEP sections are missing or out of order")

    file_name_positions = [
        position
        for position in scan["file_name_positions"]
        if header_marker <= position < header_end_marker
    ]
    if len(file_name_positions) != 1:
        raise ValueError("STEP HEADER must contain exactly one FILE_NAME entity")

    timestamp_start, timestamp_end = _file_name_timestamp_bounds(
        original_step_bytes,
        file_name_positions[0],
    )
    return (
        original_step_bytes[:timestamp_start]
        + _CANONICAL_TIMESTAMP
        + original_step_bytes[timestamp_end:]
    )


def step_content_identity_v1(original_step_bytes: bytes) -> StepContentIdentity:
    """Compute the versioned semantic identity without changing raw bytes."""

    canonical_bytes = canonical_identity_bytes_v1(original_step_bytes)
    return StepContentIdentity(
        algorithm="step-content-identity@1",
        content_hash=f"sha256:{sha256(canonical_bytes).hexdigest()}",
    )


def _scan_document(payload: bytes) -> dict[str, object]:
    iso_positions: list[int] = []
    header_positions: list[int] = []
    data_positions: list[int] = []
    endsec_positions: list[int] = []
    file_name_positions: list[int] = []
    depth = 0
    max_depth = 0
    in_string = False
    i = 0
    length = len(payload)

    while i < length:
        byte = payload[i]
        if in_string:
            if byte == 0x27:
                if i + 1 < length and payload[i + 1] == 0x27:
                    i += 2
                    continue
                in_string = False
            i += 1
            continue

        if byte == 0x27:
            in_string = True
            i += 1
            continue
        if byte == 0x2F and i + 1 < length and payload[i + 1] == 0x2A:
            comment_end = payload.find(b"*/", i + 2)
            if comment_end < 0:
                raise ValueError("unterminated STEP comment")
            i = comment_end + 2
            continue
        if byte == 0x28:
            depth += 1
            max_depth = max(max_depth, depth)
            if max_depth > _MAX_PARENTHESIS_DEPTH:
                raise ValueError("STEP parenthesis nesting exceeds the bound")
        elif byte == 0x29:
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced STEP parentheses")

        if _token_at(payload, i, _ISO_STAMP):
            iso_positions.append(i)
        if _token_at(payload, i, _HEADER):
            header_positions.append(i)
        if _token_at(payload, i, _DATA):
            data_positions.append(i)
        if _token_at(payload, i, _ENDSEC):
            endsec_positions.append(i)
        if _token_at(payload, i, _FILE_NAME):
            file_name_positions.append(i)
        i += 1

    if in_string:
        raise ValueError("unterminated STEP string")
    if depth != 0:
        raise ValueError("unbalanced STEP parentheses")

    if len(header_positions) == 1:
        header_end = next(
            (position for position in endsec_positions if position > header_positions[0]),
            None,
        )
        if header_end is None:
            raise ValueError("STEP HEADER has no ENDSEC;")
    else:
        header_end = 0

    return {
        "iso_positions": iso_positions,
        "header_positions": header_positions,
        "data_positions": data_positions,
        "endsec_positions": endsec_positions,
        "file_name_positions": file_name_positions,
        "header_start": header_positions[0] if header_positions else 0,
        "header_end": header_end + len(_ENDSEC),
    }


def _token_at(payload: bytes, position: int, token: bytes) -> bool:
    if not payload.startswith(token, position):
        return False
    if position == 0:
        return True
    previous = payload[position - 1]
    return not (
        previous in (0x2D, 0x5F)
        or 0x30 <= previous <= 0x39
        or 0x41 <= previous <= 0x5A
        or 0x61 <= previous <= 0x7A
    )


def _file_name_timestamp_bounds(payload: bytes, start: int) -> tuple[int, int]:
    open_position = start + len(_FILE_NAME) - 1
    close_position, fields = _parse_file_name_arguments(payload, open_position)
    if len(fields) < 2:
        raise ValueError("FILE_NAME must have a second positional argument")

    field_start, field_end = fields[1]
    while field_start < field_end and payload[field_start] in b" \t\r\n":
        field_start += 1
    while field_end > field_start and payload[field_end - 1] in b" \t\r\n":
        field_end -= 1
    if field_end - field_start != _TIMESTAMP_LENGTH + 2:
        raise ValueError("FILE_NAME timestamp has an invalid length")
    if payload[field_start] != 0x27 or payload[field_end - 1] != 0x27:
        raise ValueError("FILE_NAME timestamp must be a STEP string")
    timestamp_start = field_start + 1
    timestamp_end = field_end - 1
    timestamp = payload[timestamp_start:timestamp_end]
    if not _valid_timestamp(timestamp):
        raise ValueError("FILE_NAME timestamp has an invalid grammar")
    if payload[close_position + 1 :].lstrip(b" \t\r\n")[:1] != b";":
        raise ValueError("FILE_NAME entity must terminate with a semicolon")
    return timestamp_start, timestamp_end


def _parse_file_name_arguments(payload: bytes, open_position: int) -> tuple[int, list[tuple[int, int]]]:
    depth = 1
    field_start = open_position + 1
    fields: list[tuple[int, int]] = []
    in_string = False
    i = field_start
    while i < len(payload):
        byte = payload[i]
        if in_string:
            if byte == 0x27:
                if i + 1 < len(payload) and payload[i + 1] == 0x27:
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if byte == 0x27:
            in_string = True
        elif byte == 0x2F and i + 1 < len(payload) and payload[i + 1] == 0x2A:
            comment_end = payload.find(b"*/", i + 2)
            if comment_end < 0:
                raise ValueError("unterminated FILE_NAME comment")
            i = comment_end + 2
            continue
        elif byte == 0x28:
            depth += 1
        elif byte == 0x29:
            depth -= 1
            if depth == 0:
                fields.append((field_start, i))
                return i, fields
        elif byte == 0x2C and depth == 1:
            fields.append((field_start, i))
            field_start = i + 1
        i += 1
    raise ValueError("FILE_NAME has no balanced closing parenthesis")


def _valid_timestamp(value: bytes) -> bool:
    if len(value) != 19:
        return False
    separators = {4: 0x2D, 7: 0x2D, 10: 0x54, 13: 0x3A, 16: 0x3A}
    for index, byte in enumerate(value):
        if index in separators:
            if byte != separators[index]:
                return False
        elif not 0x30 <= byte <= 0x39:
            return False
    return True


__all__ = [
    "StepContentIdentity",
    "canonical_identity_bytes_v1",
    "step_content_identity_v1",
]
