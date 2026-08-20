from enum import StrEnum


class SupportedConstraintKey(StrEnum):
    OUTPUT_ANGULAR_SPEED = "transmission.output_angular_speed"
    MOTOR_CHARACTERISTICS = "transmission.motor_characteristics"
    OUTPUT_INTERFACE = "transmission.output_interface"
    PACKAGING_ENVELOPE = "transmission.packaging_envelope"
    AZIMUTH_DRIVE_MOUNT_INTERFACE = "azimuth.drive_mount_interface"
    AZIMUTH_MOUNT_PLATE_DESIGN_REQUIREMENTS = "azimuth.mount_plate_design_requirements"
    YAGI_PAYLOAD_CARRIER_REQUIREMENTS = "yagi.payload_carrier_requirements"
