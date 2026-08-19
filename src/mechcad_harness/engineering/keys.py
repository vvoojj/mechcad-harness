from enum import StrEnum


class SupportedConstraintKey(StrEnum):
    OUTPUT_ANGULAR_SPEED = "transmission.output_angular_speed"
    MOTOR_CHARACTERISTICS = "transmission.motor_characteristics"
    OUTPUT_INTERFACE = "transmission.output_interface"
    PACKAGING_ENVELOPE = "transmission.packaging_envelope"
