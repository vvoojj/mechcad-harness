"""Neutral structural/candidate currentness status vocabulary (F3)."""

from enum import StrEnum


class Currentness(StrEnum):
    CURRENT = "current"
    STALE_RELATIVE_TO_CURRENT_STATE = "stale_relative_to_current_state"
    CURRENTNESS_UNAVAILABLE = "currentness_unavailable"


__all__ = ["Currentness"]
