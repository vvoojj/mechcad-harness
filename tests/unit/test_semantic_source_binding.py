from __future__ import annotations

from hashlib import sha256

import pytest

from mechcad_harness.candidates.semantic_authority import (
    semantic_authority_value_hash,
    semantic_source_binding_hash,
)
from mechcad_harness.core.canonical import canonical_json_bytes


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
CONTENT_IDENTITY = "sha256:" + "c" * 64
STATE_HASH = "sha256:" + "d" * 64


def _raw_geometry(*, artifact_id: str, artifact_hash: str) -> dict[str, str]:
    return {
        "artifact_id": artifact_id,
        "artifact_hash": artifact_hash,
        "source_identity": "supplier:gear",
        "format": "step",
        "coordinate_system_id": "step-model-coordinates@1",
    }


def _dual_binding(raw_geometry: dict[str, str]) -> dict[tuple[object, ...], dict[str, str]]:
    key = (
        raw_geometry["artifact_id"],
        raw_geometry["artifact_hash"],
        raw_geometry["source_identity"],
        raw_geometry["format"],
        raw_geometry["coordinate_system_id"],
    )
    return {
        key: {
            "algorithm": "step-content-identity@1",
            "content_hash": CONTENT_IDENTITY,
        }
    }


def _source_binding(raw_geometry: dict[str, str]) -> dict[str, object]:
    path = "/physical_mechanisms/0/geometry_source"
    return {
        "project_id": "project-a",
        "source_revision": 17,
        "source_state_hash": STATE_HASH,
        "consumed_authority": (
            {
                "path": path,
                "value_hash": raw_geometry["artifact_hash"],
                "authority": "canonical_component_fact",
            },
        ),
    }


def _expected_hash(payload: dict[str, object]) -> str:
    return "sha256:" + sha256(canonical_json_bytes(payload)).hexdigest()


def test_raw_only_geometry_rotation_is_semantically_invariant_with_dual_binding():
    first = _raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_A)
    second = _raw_geometry(artifact_id="artifact-b", artifact_hash=HASH_B)
    path = "/physical_mechanisms/0/geometry_source"

    first_value_hash = semantic_authority_value_hash(path, first, _dual_binding(first))
    second_value_hash = semantic_authority_value_hash(path, second, _dual_binding(second))

    first_binding_hash = semantic_source_binding_hash(
        _source_binding(first), {path: first}, _dual_binding(first)
    )
    second_binding_hash = semantic_source_binding_hash(
        _source_binding(second), {path: second}, _dual_binding(second)
    )

    assert first_value_hash == second_value_hash
    assert first_binding_hash == second_binding_hash


def test_engineering_value_change_changes_semantic_authority_hash():
    path = "/requirements/torque"

    first = semantic_authority_value_hash(
        path,
        {"value": 12.0, "unit": "N*m"},
        {},
    )
    changed = semantic_authority_value_hash(
        path,
        {"value": 13.0, "unit": "N*m"},
        {},
    )

    assert first != changed


@pytest.mark.parametrize(
    "resolved_value, context",
    [
        (
            {"artifact_id": "artifact-a", "artifact_hash": HASH_A, "label": "unknown"},
            {},
        ),
        (
            {"geometry_source": _raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_A)},
            _dual_binding(_raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_A)),
        ),
        (_raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_A), {}),
        (
            _raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_A),
            _dual_binding(_raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_B)),
        ),
        (
            _raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_A),
            {"artifact-a": CONTENT_IDENTITY},
        ),
    ],
    ids=[
        "unknown-raw-bearing-shape",
        "nested-raw-bearing-shape-without-explicit-projection",
        "missing-dual-binding-context",
        "mismatched-dual-binding-context",
        "raw-only-shortcut",
    ],
)
def test_raw_bearing_values_fail_closed_without_exact_dual_binding(
    resolved_value: dict[str, object], context: dict[object, object]
):
    with pytest.raises(ValueError):
        semantic_authority_value_hash(
            "/physical_mechanisms/0/geometry_source",
            resolved_value,
            context,
        )


def test_semantic_hash_payload_excludes_raw_coordinates_and_legacy_value_hash():
    path = "/physical_mechanisms/0/geometry_source"
    raw_geometry = _raw_geometry(artifact_id="artifact-a", artifact_hash=HASH_A)
    source_binding = _source_binding(raw_geometry)
    value_hash = semantic_authority_value_hash(path, raw_geometry, _dual_binding(raw_geometry))

    expected_value_payload = {
        "path": path,
        "value": {
            "source_identity": "supplier:gear",
            "format": "step",
            "coordinate_system_id": "step-model-coordinates@1",
            "content_identity": CONTENT_IDENTITY,
            "content_identity_algorithm": "step-content-identity@1",
        },
    }
    assert value_hash == _expected_hash(expected_value_payload)

    binding_hash = semantic_source_binding_hash(
        source_binding,
        {path: raw_geometry},
        _dual_binding(raw_geometry),
    )
    expected_binding_payload = {
        "project_id": "project-a",
        "consumed_authority": [
            {
                "path": path,
                "authority": "canonical_component_fact",
                "semantic_authority_value_hash": value_hash,
            }
        ],
    }
    assert binding_hash == _expected_hash(expected_binding_payload)

    assert "source_revision" not in expected_binding_payload
    assert "source_state_hash" not in expected_binding_payload
    assert "value_hash" not in expected_binding_payload["consumed_authority"][0]


def test_semantic_geometry_projection_can_be_reused_without_raw_binding():
    path = "/physical_mechanisms/0/geometry_source"
    semantic_geometry = {
        "source_identity": "supplier:gear",
        "format": "step",
        "coordinate_system_id": "step-model-coordinates@1",
        "content_identity": CONTENT_IDENTITY,
        "content_identity_algorithm": "step-content-identity@1",
    }

    assert semantic_authority_value_hash(path, semantic_geometry, {})


@pytest.mark.parametrize(
    "value",
    [
        {"reference_hash": HASH_A},
        {"geometry_reference_hash": HASH_A},
        {"geometry_identity_hash": HASH_A},
    ],
)
def test_legacy_geometry_hash_fields_fail_closed(value):
    with pytest.raises(ValueError):
        semantic_authority_value_hash("/physical_mechanisms/0/geometry_source", value, {})
