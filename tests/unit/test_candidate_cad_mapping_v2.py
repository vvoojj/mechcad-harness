from __future__ import annotations

from hashlib import sha256

import pytest

from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.candidates import (
    CandidateCadInstanceMappingV2,
    CandidateGeometryFidelity,
    SemanticPlacementOrigin,
    SemanticSourceGeometryIdentity,
    bind_semantic_placement_origin,
    candidate_mapping_hash_v2,
    collapse_placement_origin_inputs,
    trusted_representation_identity,
)
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_candidate_trusted_semantic_verification import (
    _at2_setup,
    _P2_GEOMETRY_SLOTS,
    _P2_STEP_VARIANTS,
)
from test_m13_2_generated_part_models import _shaft


CONTENT_A = step_content_identity_v1(_P2_STEP_VARIANTS["A"]).content_hash
CONTENT_B = step_content_identity_v1(_P2_STEP_VARIANTS["B"]).content_hash


def _raw_hash(variant="A"):
    return "sha256:" + sha256(_P2_STEP_VARIANTS[variant]).hexdigest()


def _content_by_artifact(variant="A"):
    raw_hash = _raw_hash(variant)
    mapping = {}
    for slot in _P2_GEOMETRY_SLOTS:
        mapping[f"ART-P2-{slot}-{variant}"] = CONTENT_A
        mapping[raw_hash] = CONTENT_A
    return mapping


def _trusted_mapping(candidate_hash, *, slot="motor", cad_id="cad-motor", content=CONTENT_A):
    origin = bind_semantic_placement_origin(
        "source_authority",
        (
            f"ART-P2-{slot}-A",
            _raw_hash("A"),
            f"candidate:source-authority:supplier:m12:{slot}@1",
        ),
        "fixture-placement@1",
        CadRigidTransform(x_mm=20.0),
        content_by_artifact=_content_by_artifact(),
    )
    return CandidateCadInstanceMappingV2(
        candidate_hash=candidate_hash,
        physical_instance_id=slot,
        cad_instance_id=cad_id,
        fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
        representation_identity=trusted_representation_identity(
            slot=cad_id, content_identity=content
        ),
        source_geometry_identity=SemanticSourceGeometryIdentity(
            content_identity=content,
            content_identity_algorithm="step-content-identity@1",
        ),
        geometry_definition_identities=(content,),
        placement=CadRigidTransform(x_mm=20.0),
        placement_origin=origin,
    )


def test_mapping_at2_and_origin_have_exact_declared_fields():
    assert set(CandidateCadInstanceMappingV2.model_fields) == {
        "schema_version",
        "candidate_hash",
        "physical_instance_id",
        "cad_instance_id",
        "fidelity",
        "representation_identity",
        "source_geometry_identity",
        "geometry_definition_identities",
        "placement",
        "placement_origin",
        "mapping_hash",
    }
    assert set(SemanticPlacementOrigin.model_fields) == {
        "authority",
        "input_identities",
        "derivation",
        "transform",
        "origin_hash",
    }


def test_trusted_mapping_commits_semantic_identity_and_recomputes_hash(tmp_path):
    _, _, _, _, _, _, candidate = _at2_setup(tmp_path)
    mapping = _trusted_mapping(candidate.candidate_hash)

    assert mapping.schema_version == "candidate-cad-instance-mapping@2"
    assert mapping.mapping_hash == candidate_mapping_hash_v2(mapping)
    wire = mapping.model_dump(mode="json")
    assert wire["source_geometry_identity"] == {
        "content_identity": CONTENT_A,
        "content_identity_algorithm": "step-content-identity@1",
    }
    assert wire["geometry_definition_identities"] == [CONTENT_A]
    assert "ART-P2-motor-A" not in str(wire)
    assert wire["placement_origin"]["input_identities"] == sorted(
        wire["placement_origin"]["input_identities"]
    )


def test_trusted_mapping_is_invariant_to_raw_artifact_rotation(tmp_path):
    _, _, _, _, _, _, candidate = _at2_setup(tmp_path)
    assert CONTENT_A == CONTENT_B
    first = _trusted_mapping(candidate.candidate_hash, content=CONTENT_A)
    second = _trusted_mapping(candidate.candidate_hash, content=CONTENT_B)

    assert first.mapping_hash == second.mapping_hash


def test_origin_hash_excludes_the_legacy_dump_and_normalizes_inputs():
    origin = bind_semantic_placement_origin(
        "source_authority",
        (
            "candidate:source-authority:supplier:m12:z@1",
            "ART-P2-motor-A",
            _raw_hash("A"),
        ),
        "fixture-placement@1",
        CadRigidTransform(x_mm=20.0),
        content_by_artifact=_content_by_artifact(),
    )

    assert origin.input_identities == (
        "candidate:source-authority:supplier:m12:z@1",
        CONTENT_A,
    )
    assert origin.origin_hash.startswith("sha256:")
    from mechcad_harness.state.hashing import canonical_json as _canonical_json

    legacy_tokens = (
        "candidate:source-authority:supplier:m12:z@1",
        "ART-P2-motor-A",
        _raw_hash("A"),
    )
    legacy_payload_hash = "sha256:" + sha256(
        _canonical_json(
            {
                "authority": "source_authority",
                "input_identities": list(legacy_tokens),
                "derivation": "fixture-placement@1",
                "transform": CadRigidTransform(x_mm=20.0).model_dump(mode="json"),
            }
        )
    ).hexdigest()
    assert origin.origin_hash != legacy_payload_hash


def test_source_authority_collapse_rejects_unknown_raw_tokens():
    with pytest.raises(ValueError, match="resolve|unknown|content"):
        collapse_placement_origin_inputs(
            "source_authority",
            ("ART-unknown",),
            content_by_artifact=_content_by_artifact(),
        )


def test_generated_mapping_keeps_sorted_unique_definition_identities():
    from mechcad_harness.models.generated_part import (
        generated_geometry_definition_identities,
    )

    identities = generated_geometry_definition_identities(_shaft())
    assert tuple(sorted(set(identities))) == identities
    transform = CadRigidTransform(x_mm=5.0)
    mapping = CandidateCadInstanceMappingV2(
        candidate_hash="sha256:" + "a" * 64,
        physical_instance_id="shaft",
        cad_instance_id="cad-shaft",
        fidelity=CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
        representation_identity="sha256:" + "b" * 64,
        source_geometry_identity=None,
        geometry_definition_identities=tuple(reversed(identities)),
        placement=transform,
        placement_origin=SemanticPlacementOrigin(
            authority="deterministic_derived_relation",
            input_identities=("candidate:generated-placement:place-shaft",),
            derivation="coaxial-generated-placement@1",
            transform=transform,
        ),
    )

    assert mapping.geometry_definition_identities == identities
    assert mapping.mapping_hash == candidate_mapping_hash_v2(mapping)


def test_generated_mapping_rejects_duplicate_definition_identities():
    from mechcad_harness.models.generated_part import (
        generated_geometry_definition_identities,
    )

    identities = generated_geometry_definition_identities(_shaft())
    transform = CadRigidTransform(x_mm=5.0)
    with pytest.raises(ValueError, match="duplicate|unique"):
        CandidateCadInstanceMappingV2(
            candidate_hash="sha256:" + "a" * 64,
            physical_instance_id="shaft",
            cad_instance_id="cad-shaft",
            fidelity=CandidateGeometryFidelity.EXACT_GENERATED_GEOMETRY,
            representation_identity="sha256:" + "b" * 64,
            source_geometry_identity=None,
            geometry_definition_identities=(*identities, identities[0]),
            placement=transform,
            placement_origin=SemanticPlacementOrigin(
                authority="deterministic_derived_relation",
                input_identities=("candidate:generated-placement:place-shaft",),
                derivation="coaxial-generated-placement@1",
                transform=transform,
            ),
        )


def test_fallback_mapping_preserves_alias_key_order():
    transform = CadRigidTransform()
    identities = (
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
        "sha256:" + "3" * 64,
    )
    mapping = CandidateCadInstanceMappingV2(
        candidate_hash="sha256:" + "a" * 64,
        physical_instance_id="mount",
        cad_instance_id="cad-mount",
        fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
        representation_identity="sha256:" + "c" * 64,
        source_geometry_identity=None,
        geometry_definition_identities=identities,
        placement=transform,
        placement_origin=SemanticPlacementOrigin(
            authority="candidate_design_variable",
            input_identities=("candidate:design-variable:mount.placement.x_mm",),
            derivation="mount-frame@1",
            transform=transform,
        ),
    )

    assert mapping.geometry_definition_identities == identities
    assert mapping.source_geometry_identity is None


def test_legacy_raw_identities_do_not_verify_under_at2_semantics(tmp_path):
    _, _, _, _, _, _, candidate = _at2_setup(tmp_path)
    transform = CadRigidTransform(x_mm=20.0)
    with pytest.raises(
        ValueError, match="source_geometry_identity|semantic|trusted|valid dictionary"
    ):
        CandidateCadInstanceMappingV2(
            candidate_hash=candidate.candidate_hash,
            physical_instance_id="motor",
            cad_instance_id="cad-motor",
            fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
            representation_identity="sha256:" + "b" * 64,
            source_geometry_identity="sha256:" + "2" * 64,
            geometry_definition_identities=("ART-P2-motor-A",),
            placement=transform,
            placement_origin=SemanticPlacementOrigin(
                authority="source_authority",
                input_identities=(CONTENT_A,),
                derivation="fixture-placement@1",
                transform=transform,
            ),
        )


def test_mapping_hash_is_sensitive_to_semantic_changes(tmp_path):
    _, _, _, _, _, _, candidate = _at2_setup(tmp_path)
    baseline = _trusted_mapping(candidate.candidate_hash)
    changed = baseline.model_copy(
        update={
            "placement_origin": SemanticPlacementOrigin(
                authority="source_authority",
                input_identities=baseline.placement_origin.input_identities,
                derivation="other-rule@1",
                transform=baseline.placement,
            ),
            "mapping_hash": "pending",
        }
    )

    assert changed.mapping_hash != baseline.mapping_hash


def test_origin_subprojection_carries_no_m10_version_literal():
    origin = bind_semantic_placement_origin(
        "deterministic_derived_relation",
        ("candidate:generated-placement:place-shaft",),
        "coaxial-generated-placement@1",
        CadRigidTransform(),
        content_by_artifact={},
    )
    payload = origin.model_dump(mode="json")
    payload.pop("origin_hash")

    assert set(payload) == {"authority", "input_identities", "derivation", "transform"}
