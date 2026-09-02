from enum import StrEnum


class ComponentPropertyAvailability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class ComponentPropertyAuthority(StrEnum):
    MANUFACTURER_DATASHEET = "manufacturer_datasheet"
    DISTRIBUTOR_LISTING = "distributor_listing"
    MEASURED_LOCAL = "measured_local"
    DERIVED_NORMALIZATION = "derived_normalization"
    USER_DECLARED = "user_declared"
