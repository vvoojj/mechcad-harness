from hashlib import sha256

import pytest

from mechcad_harness.candidates.models import (
    CandidateSourceBinding,
    CandidateSourceReference,
    CandidateSynthesisRequest,
    candidate_synthesis_request_hash_v2,
)
from mechcad_harness.core.canonical import canonical_json_bytes


STATE_A = "sha256:" + "a" * 64
STATE_B = "sha256:" + "b" * 64
VALUE_A = "sha256:" + "c" * 64
VALUE_B = "sha256:" + "d" * 64
SEMANTIC = "sha256:" + "e" * 64


def _binding(*, revision=1, state_hash=STATE_A, value_hash=VALUE_A):
    return CandidateSourceBinding(
        project_id="project-a",
        source_revision=revision,
        source_state_hash=state_hash,
        consumed_authority=(
            CandidateSourceReference(
                path="/physical_mechanisms",
                value_hash=value_hash,
                authority="canonical_component_fact",
            ),
        ),
    )


def _request(**overrides):
    values = {
        "source_binding": _binding(),
        "semantic_source_binding_hash": SEMANTIC,
        "requested_joint_ids": ("J-2", "J-1"),
        "required_joint_ids": ("J-1",),
        "out_of_scope_joint_ids": (),
        "requested_evaluation_categories": ("clearance",),
        "schema_version": "candidate-synthesis-request@2",
    }
    values.update(overrides)
    return CandidateSynthesisRequest(**values)


def test_request_wire_field_sets_are_exactly_7_for_legacy_and_8_for_v2():
    legacy = CandidateSynthesisRequest(source_binding=_binding())
    semantic = _request()

    assert set(legacy.model_dump(mode="json")) == {
        "schema_version",
        "source_binding",
        "requested_joint_ids",
        "required_joint_ids",
        "out_of_scope_joint_ids",
        "requested_evaluation_categories",
        "request_hash",
    }
    assert set(semantic.model_dump(mode="json")) == {
        "schema_version",
        "source_binding",
        "semantic_source_binding_hash",
        "requested_joint_ids",
        "required_joint_ids",
        "out_of_scope_joint_ids",
        "requested_evaluation_categories",
        "request_hash",
    }


def test_v2_request_hash_payload_is_exact_and_excludes_source_binding():
    request = _request()
    expected_payload = {
        "schema_version": "candidate-synthesis-request@2",
        "semantic_source_binding_hash": SEMANTIC,
        "requested_joint_ids": ["J-2", "J-1"],
        "required_joint_ids": ["J-1"],
        "out_of_scope_joint_ids": [],
        "requested_evaluation_categories": ["clearance"],
    }
    expected = "sha256:" + sha256(canonical_json_bytes(expected_payload)).hexdigest()

    assert candidate_synthesis_request_hash_v2(request) == expected
    assert request.request_hash == expected
    assert "source_binding" not in expected_payload


def test_legacy_request_hash_and_wire_shape_remain_unchanged():
    request = CandidateSynthesisRequest(source_binding=_binding())
    payload = request.model_dump(mode="json")
    payload.pop("request_hash")
    expected = "sha256:" + sha256(canonical_json_bytes(payload)).hexdigest()

    assert request.request_hash == expected


def test_v2_request_is_invariant_to_raw_source_binding_rotation():
    first = _request(source_binding=_binding(revision=1, state_hash=STATE_A, value_hash=VALUE_A))
    second = _request(source_binding=_binding(revision=2, state_hash=STATE_B, value_hash=VALUE_B))

    assert first.request_hash == second.request_hash


@pytest.mark.parametrize(
    "field, value",
    [
        ("semantic_source_binding_hash", "sha256:" + "f" * 64),
        ("requested_joint_ids", ("J-3", "J-1")),
        ("required_joint_ids", ()),
        ("out_of_scope_joint_ids", ("J-2",)),
        ("requested_evaluation_categories", ("kinematics",)),
    ],
)
def test_semantic_or_scope_change_changes_v2_request_hash(field, value):
    base = _request()
    changed = _request(**{field: value})

    assert base.request_hash != changed.request_hash


def test_mixed_legacy_new_request_is_rejected():
    with pytest.raises(ValueError):
        CandidateSynthesisRequest(
            schema_version="candidate-synthesis-request@1",
            source_binding=_binding(),
            semantic_source_binding_hash=SEMANTIC,
        )


def test_wrong_v2_request_hash_is_rejected():
    with pytest.raises(ValueError):
        _request(request_hash="sha256:" + "0" * 64)


def test_pending_semantic_binding_cannot_receive_a_concrete_request_hash():
    request = _request(semantic_source_binding_hash="pending", request_hash="pending")
    assert request.request_hash == "pending"
    with pytest.raises(ValueError, match="pending"):
        candidate_synthesis_request_hash_v2(request)
    with pytest.raises(ValueError, match="request hash"):
        _request(
            semantic_source_binding_hash="pending",
            request_hash="sha256:" + "1" * 64,
        )
