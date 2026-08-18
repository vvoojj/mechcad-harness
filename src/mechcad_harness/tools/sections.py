from mechcad_harness.backends.section_properties import SectionPropertiesAdapter
from mechcad_harness.sections import CircleSectionInput, HollowCircleSectionInput, RectangleSectionInput, SectionGeometryResult, SectionWarpingResult

from .models import ToolRegistration


def section_provenance():
    return SectionPropertiesAdapter().provenance()


def calc_rectangle_section_properties(value: RectangleSectionInput):
    return SectionPropertiesAdapter().rectangle(value)


def calc_circle_section_properties(value: CircleSectionInput):
    return SectionPropertiesAdapter().circle(value)


def calc_hollow_circle_section_properties(value: HollowCircleSectionInput):
    return SectionPropertiesAdapter().hollow_circle(value)


def calc_rectangle_section_warping(value: RectangleSectionInput):
    return SectionPropertiesAdapter().rectangle_warping(value)


def calc_circle_section_warping(value: CircleSectionInput):
    return SectionPropertiesAdapter().circle_warping(value)


def calc_hollow_circle_section_warping(value: HollowCircleSectionInput):
    return SectionPropertiesAdapter().hollow_circle_warping(value)


class SectionTools:
    @staticmethod
    def registrations():
        return [
            ToolRegistration(name="mechcad-calc-rectangle-section-properties", version="1.0", input_model=RectangleSectionInput, output_model=SectionGeometryResult, handler=calc_rectangle_section_properties, provenance_handler=section_provenance, evidence_nodes=("analysis.structural",)),
            ToolRegistration(name="mechcad-calc-circle-section-properties", version="1.0", input_model=CircleSectionInput, output_model=SectionGeometryResult, handler=calc_circle_section_properties, provenance_handler=section_provenance, evidence_nodes=("analysis.structural",)),
            ToolRegistration(name="mechcad-calc-hollow-circle-section-properties", version="1.0", input_model=HollowCircleSectionInput, output_model=SectionGeometryResult, handler=calc_hollow_circle_section_properties, provenance_handler=section_provenance, evidence_nodes=("analysis.structural",)),
            ToolRegistration(name="mechcad-calc-rectangle-section-warping", version="1.0", input_model=RectangleSectionInput, output_model=SectionWarpingResult, handler=calc_rectangle_section_warping, provenance_handler=section_provenance, evidence_nodes=("analysis.structural",)),
            ToolRegistration(name="mechcad-calc-circle-section-warping", version="1.0", input_model=CircleSectionInput, output_model=SectionWarpingResult, handler=calc_circle_section_warping, provenance_handler=section_provenance, evidence_nodes=("analysis.structural",)),
            ToolRegistration(name="mechcad-calc-hollow-circle-section-warping", version="1.0", input_model=HollowCircleSectionInput, output_model=SectionWarpingResult, handler=calc_hollow_circle_section_warping, provenance_handler=section_provenance, evidence_nodes=("analysis.structural",)),
        ]
