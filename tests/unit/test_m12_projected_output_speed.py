from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from mechcad_harness.candidates import (
    CandidateSourceAuthority,
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisRequest,
)
from mechcad_harness.revolute_drive import (
    InputProvenanceKind,
    ProjectedSourceBoundScalar,
    RevoluteDriveEngineeringRequirements,
    SourceBoundScalar,
    StaticOutputShaftDesignLoadCase,
)
from mechcad_harness.revolute_drive.lowering import lower_projected_output_speed
from mechcad_harness.revolute_drive.service import _source_scalar_binding_defects
from tests.unit.test_canonical_scalar_projection import (
    PROJECT_ID,
    locator,
    parameter,
    source_state,
)
from mechcad_harness.engineering.scalar_projection import project_authoritative_scalar
from mechcad_harness.state import state_hash


def projection():
    state = source_state(parameter(value_rad_s=2.5))
    return project_authoritative_scalar(PROJECT_ID, state, locator(state))


def projected_requirements():
    policy_scalar = SourceBoundScalar(
        value=10.0,
        unit="N*m",
        provenance=InputProvenanceKind.POLICY_ASSUMPTION,
    )
    return RevoluteDriveEngineeringRequirements(
        required_output_speed=lower_projected_output_speed(projection()),
        design_load_case=StaticOutputShaftDesignLoadCase(
            design_torque=policy_scalar,
            transverse_force_y=policy_scalar.model_copy(update={"unit": "N", "value": 0.0}),
            transverse_force_z=policy_scalar.model_copy(update={"unit": "N", "value": 0.0}),
        ),
        trusted_source_scalar_bindings=(),
    )


def projected_request(state, references=None):
    if references is None:
        consumed = (
            CandidateSourceReference(
                path="/authoritative_parameters",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_PARAMETER,
            ),
        )
    elif not references:
        consumed = (
            CandidateSourceReference(
                path="/requirements/0",
                value_hash="pending",
                authority=CandidateSourceAuthority.CANONICAL_PARAMETER,
            ),
        )
    else:
        consumed = tuple(references)
    binding = CandidateSourceBinding(
        project_id=PROJECT_ID,
        source_revision=state.revision,
        source_state_hash=state_hash(state),
        consumed_authority=consumed,
    )
    if references is None:
        binding = binding.bound_to(state)
    return CandidateSynthesisRequest(
        source_binding=binding,
        required_joint_ids=("J-1",),
        requested_joint_ids=("J-1",),
    )


def projected_defects(requirements=None, request=None, state=None):
    state = state or source_state(parameter())
    return _source_scalar_binding_defects(
        requirements or projected_requirements(),
        request or projected_request(state),
        state,
    )


def test_lowering_constructs_one_rpm_projected_scalar_with_exact_conversion():
    result = lower_projected_output_speed(projection())

    assert result.value == 2.5 * 60.0 / (2.0 * math.pi)
    assert result.unit == "rpm"
    assert result.canonical_projection.value == 2.5
    assert result.normalization_rule_id == "m12-output-angular-speed-rad-s-to-rpm@1"
    assert result.normalized_value_hash.startswith("sha256:")
    assert result.binding_hash.startswith("sha256:")
    assert "source_path" not in result.model_dump(mode="json")
    assert "provenance" not in result.model_dump(mode="json")


@pytest.mark.parametrize(
    "changes",
    [
        {"unit": "rad/s"},
        {"normalization_rule_id": "other"},
        {"normalized_value_hash": "sha256:" + "0" * 64},
        {"binding_hash": "sha256:" + "0" * 64},
    ],
)
def test_projected_scalar_rejects_tampered_contract(changes):
    valid = lower_projected_output_speed(projection()).model_dump(mode="json")
    valid.update(changes)

    with pytest.raises(ValidationError):
        ProjectedSourceBoundScalar.model_validate(valid)


def test_projected_scalar_rejects_an_altered_rpm_value():
    valid = lower_projected_output_speed(projection()).model_dump(mode="json")
    valid["value"] += 1.0

    with pytest.raises(ValidationError, match="normalized value hash mismatch"):
        ProjectedSourceBoundScalar.model_validate(valid)


def test_lowering_rejects_non_output_speed_projection_claim():
    claim = projection().model_dump(mode="json")
    claim["authoritative_key"] = "transmission.motor_characteristics"
    claim["projection_hash"] = "sha256:" + "0" * 64

    with pytest.raises(ValidationError):
        lower_projected_output_speed(claim)


def test_projected_verifier_accepts_canonical_parameter_with_aggregate_binding_only():
    assert projected_defects() == []


def test_projected_verifier_recomputes_and_rejects_tampered_projection_claim():
    requirements = projected_requirements()
    claim = requirements.required_output_speed.canonical_projection.model_copy(
        update={"value": 9.0}
    )
    forged_scalar = requirements.required_output_speed.model_copy(
        update={"canonical_projection": claim}
    )
    forged_requirements = requirements.model_copy(
        update={"required_output_speed": forged_scalar}
    )

    defects = projected_defects(requirements=forged_requirements)
    assert defects
    assert "recomputation" in defects[0]


@pytest.mark.parametrize(
    "reference",
    [
        None,
        CandidateSourceReference(
            path="/authoritative_parameters",
            value_hash="pending",
            authority=CandidateSourceAuthority.CANONICAL_REQUIREMENT,
        ),
        CandidateSourceReference(
            path="/authoritative_parameters",
            value_hash="sha256:" + "0" * 64,
            authority=CandidateSourceAuthority.CANONICAL_PARAMETER,
        ),
    ],
)
def test_projected_verifier_rejects_missing_wrong_or_stale_aggregate_binding(reference):
    state = source_state(parameter())
    request = projected_request(state, () if reference is None else (reference,))

    defects = projected_defects(request=request, state=state)
    assert defects
    assert "authoritative_parameters" in defects[0]


def test_projected_verifier_rejects_locator_project_not_matching_request():
    state = source_state(parameter())
    requirements = projected_requirements()
    claim = requirements.required_output_speed.canonical_projection
    locator_claim = claim.source.model_copy(update={"project_id": "OTHER"})
    forged_projection = claim.model_copy(update={"source": locator_claim})
    forged_scalar = requirements.required_output_speed.model_copy(
        update={"canonical_projection": forged_projection}
    )
    forged_requirements = requirements.model_copy(
        update={"required_output_speed": forged_scalar}
    )

    defects = projected_defects(requirements=forged_requirements, state=state)
    assert defects
    assert "project" in defects[0]
