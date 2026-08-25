from .common import Model, NamedModel, StateBinding
from .evidence import Evidence
from .issue import Issue, IssueStatus
from .proposal import (
    ChangeProposal,
    ChangeSet,
    ConstraintRequest,
    ProposalStatus,
)
from .run import RunManifest
from .task import AgentResult, AgentTask, TaskStatus
from .validation import ValidationResult, ValidationStatus

_DESIGN_EXPORTS = {
    "Assembly",
    "Component",
    "Constraint",
    "DesignState",
    "Interface",
    "LoadCase",
    "MaterialProfile",
    "Requirement",
}

_STRUCTURAL_EXPORTS = {
    "AcceptanceMaterialAuthorityPolicy",
    "MaximumDisplacementCriterion",
    "StructuralAnalysisDefinition",
    "StructuralAnalysisKind",
    "StructuralBodyAcceleration",
    "StructuralCoordinateFrame",
    "StructuralCriterion",
    "StructuralDof",
    "StructuralFixedSupport",
    "StructuralLoad",
    "StructuralLoadCase",
    "StructuralMaterialAssignment",
    "StructuralMaterialAuthorityDecision",
    "StructuralMaterialAuthorityRejection",
    "StructuralMaterialConversionProvenance",
    "StructuralMaterialPropertyName",
    "StructuralMaterialPropertySnapshot",
    "StructuralPhysicalAssumptions",
    "StructuralPropertyAuthorityRule",
    "StructuralRegionDefinition",
    "StructuralResultField",
    "StructuralResultantForce",
    "StructuralSurfacePressure",
    "YieldSafetyFactorCriterion",
    "evaluate_material_authority_policy",
    "structural_definition_hash",
}


def __getattr__(name: str):
    if name in _DESIGN_EXPORTS:
        from . import design

        value = getattr(design, name)
    elif name in _STRUCTURAL_EXPORTS:
        from . import structural

        value = getattr(structural, name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value

__all__ = [
    "AgentResult",
    "AgentTask",
    "AcceptanceMaterialAuthorityPolicy",
    "Assembly",
    "ChangeOperation",
    "ChangeProposal",
    "ChangeSet",
    "Component",
    "Constraint",
    "ConstraintRequest",
    "DesignState",
    "Evidence",
    "Interface",
    "Issue",
    "IssueStatus",
    "LoadCase",
    "MaterialProfile",
    "MaximumDisplacementCriterion",
    "Model",
    "NamedModel",
    "ProposalStatus",
    "Requirement",
    "RunManifest",
    "StateBinding",
    "StructuralAnalysisDefinition",
    "StructuralAnalysisKind",
    "StructuralBodyAcceleration",
    "StructuralCoordinateFrame",
    "StructuralCriterion",
    "StructuralDof",
    "StructuralFixedSupport",
    "StructuralLoad",
    "StructuralLoadCase",
    "StructuralMaterialAssignment",
    "StructuralMaterialAuthorityDecision",
    "StructuralMaterialAuthorityRejection",
    "StructuralMaterialConversionProvenance",
    "StructuralMaterialPropertyName",
    "StructuralMaterialPropertySnapshot",
    "StructuralPhysicalAssumptions",
    "StructuralPropertyAuthorityRule",
    "StructuralRegionDefinition",
    "StructuralResultField",
    "StructuralResultantForce",
    "StructuralSurfacePressure",
    "TaskStatus",
    "ValidationResult",
    "ValidationStatus",
    "YieldSafetyFactorCriterion",
    "evaluate_material_authority_policy",
    "structural_definition_hash",
]
