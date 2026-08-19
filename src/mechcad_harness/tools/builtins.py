from pydantic import Field, model_validator

from mechcad_harness.models.common import Model

from .models import ToolRegistration, TorqueInput


class TorqueOutput(Model):
    nominal_torque_nm: float
    design_torque_nm: float


def calc_torque(value: TorqueInput) -> TorqueOutput:
    nominal = value.force_n * value.lever_arm_m
    return TorqueOutput(nominal_torque_nm=nominal, design_torque_nm=nominal * value.safety_factor)


def torque_evidence_summary(value: TorqueOutput) -> str:
    return f"Required design torque: {value.design_torque_nm:g} N*m"


class SpurGearInput(Model):
    module_mm: float = Field(gt=0)
    teeth_pinion: int = Field(gt=0)
    teeth_gear: int = Field(gt=0)


class SpurGearOutput(Model):
    pitch_diameter_pinion_mm: float
    pitch_diameter_gear_mm: float
    center_distance_mm: float
    ratio: float


def calc_spur_gear(value: SpurGearInput) -> SpurGearOutput:
    pinion = value.module_mm * value.teeth_pinion
    gear = value.module_mm * value.teeth_gear
    return SpurGearOutput(
        pitch_diameter_pinion_mm=pinion,
        pitch_diameter_gear_mm=gear,
        center_distance_mm=(pinion + gear) / 2,
        ratio=value.teeth_gear / value.teeth_pinion,
    )


class EnvelopeInput(Model):
    part_x_mm: float = Field(gt=0)
    part_y_mm: float = Field(gt=0)
    part_z_mm: float = Field(gt=0)
    max_x_mm: float = Field(gt=0)
    max_y_mm: float = Field(gt=0)
    max_z_mm: float = Field(gt=0)


class EnvelopeOutput(Model):
    fits: bool
    clearance_x_mm: float
    clearance_y_mm: float
    clearance_z_mm: float


def check_envelope(value: EnvelopeInput) -> EnvelopeOutput:
    clearances = (value.max_x_mm - value.part_x_mm, value.max_y_mm - value.part_y_mm, value.max_z_mm - value.part_z_mm)
    return EnvelopeOutput(fits=all(clearance >= 0 for clearance in clearances), clearance_x_mm=clearances[0], clearance_y_mm=clearances[1], clearance_z_mm=clearances[2])


class CompensationInput(Model):
    nominal_mm: float
    compensation_mm: float


class CompensationOutput(Model):
    compensated_mm: float


def apply_dimension_compensation(value: CompensationInput) -> CompensationOutput:
    return CompensationOutput(compensated_mm=value.nominal_mm + value.compensation_mm)


class BuiltinTools:
    @staticmethod
    def registrations() -> list[ToolRegistration]:
        return [
            ToolRegistration(name="mechcad-calc-torque", version="1.0", input_model=TorqueInput, output_model=TorqueOutput, handler=calc_torque, evidence_nodes=("analysis.transmission.torque",), evidence_summary_handler=torque_evidence_summary),
            ToolRegistration(name="mechcad-calc-spur-gear-geometry", version="1.0", input_model=SpurGearInput, output_model=SpurGearOutput, handler=calc_spur_gear),
            ToolRegistration(name="mechcad-check-envelope", version="1.0", input_model=EnvelopeInput, output_model=EnvelopeOutput, handler=check_envelope),
            ToolRegistration(name="mechcad-apply-dimension-compensation", version="1.0", input_model=CompensationInput, output_model=CompensationOutput, handler=apply_dimension_compensation),
        ]
