from __future__ import annotations

import pytest

from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.candidates import (
    CandidateCadInstanceMappingV2,
    CandidateCadRealizationRequestV3,
    CandidateGeometryFidelity,
    SemanticPlacementOrigin,
    SemanticSourceGeometryIdentity,
    bind_semantic_placement_origin,
    candidate_request_hash_v3,
    semantic_placement_derivations_hash,
    trusted_representation_identity,
)
from mechcad_harness.step_content_identity import step_content_identity_v1

from test_candidate_trusted_semantic_verification import (
    _at2_setup,
    _P2_GEOMETRY_SLOTS,
    _P2_STEP_VARIANTS,
)
from test_m13_2_placement_derivations import _coaxial, _frame_derivation


CONTENT_A = step_content_identity_v1(_P2_STEP_VARIANTS["A"]).content_hash

_INSTANCE_SLOTS = (
    ("drive-motor", "motor"),
    ("output-shaft", "shaft"),
    ("bearing-a", "bearing"),
    ("bearing-b", "bearing"),
    ("output-hub", "hub"),
    ("motor-mount", "mount"),
    ("payload-body", "body"),
)


def _content_by_artifact():
    from hashlib import sha256

    raw_hash = "sha256:" + sha256(_P2_STEP_VARIANTS["A"]).hexdigest()
    mapping = {}
    for slot in _P2_GEOMETRY_SLOTS:
        mapping[f"ART-P2-{slot}-A"] = CONTENT_A
        mapping[raw_hash] = CONTENT_A
    return mapping, raw_hash


def _mapping_at2(candidate_hash, instance_id, slot, *, index=0):
    content_map, raw = _content_by_artifact()
    transform = CadRigidTransform(x_mm=float(index * 20))
    origin = bind_semantic_placement_origin(
        "source_authority",
        (
            f"ART-P2-{slot}-A",
            raw,
            f"candidate:source-authority:supplier:m12:{slot}@1",
        ),
        "fixture-placement@1",
        transform,
        content_by_artifact=content_map,
    )
    cad_id = f"cad-{instance_id}"
    return CandidateCadInstanceMappingV2(
        candidate_hash=candidate_hash,
        physical_instance_id=instance_id,
        cad_instance_id=cad_id,
        fidelity=CandidateGeometryFidelity.TRUSTED_SOURCE_GEOMETRY,
        representation_identity=trusted_representation_identity(
            slot=cad_id, content_identity=CONTENT_A
        ),
        source_geometry_identity=SemanticSourceGeometryIdentity(
            content_identity=CONTENT_A,
            content_identity_algorithm="step-content-identity@1",
        ),
        geometry_definition_identities=(CONTENT_A,),
        placement=transform,
        placement_origin=origin,
    )


def _request_at3(candidate, semantic_binding_hash, *, derivations=(), mappings=None):
    if mappings is None:
        mappings = tuple(
            _mapping_at2(candidate.candidate_hash, instance_id, slot, index=index)
            for index, (instance_id, slot) in enumerate(_INSTANCE_SLOTS)
        )
    return CandidateCadRealizationRequestV3(
        candidate_hash=candidate.candidate_hash,
        source_binding=candidate.source_binding,
        semantic_source_binding_hash=semantic_binding_hash,
        representation_policy_version="candidate-cad-policy@1",
        compiler_identity="candidate-cad-compiler",
        compiler_version="1",
        candidate_instance_ids=tuple(
            reversed([instance_id for instance_id, _ in _INSTANCE_SLOTS])
        ),
        mappings=tuple(reversed(mappings)),
        placement_derivations=derivations,
        design_variable_identities=(),
        component_interface_identities=(),
    )


def test_request_at3_has_exactly_15_declared_fields(tmp_path):
    _, _, _, _, _, _, candidate = _at2_setup(tmp_path)

    assert set(CandidateCadRealizationRequestV3.model_fields) == {
        "schema_version",
        "candidate_hash",
        "source_binding",
        "source_binding_hash",
        "semantic_source_binding_hash",
        "representation_policy_version",
        "compiler_identity",
        "compiler_version",
        "candidate_instance_ids",
        "mappings",
        "placement_derivations",
        "semantic_placement_derivations_hash",
        "design_variable_identities",
        "component_interface_identities",
        "request_hash",
    }


def test_request_at3_normalizes_order_and_recomputes_hash(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)

    assert request.schema_version == "candidate-cad-realization-request@3"
    assert request.candidate_instance_ids == tuple(
        sorted(instance_id for instance_id, _ in _INSTANCE_SLOTS)
    )
    assert (
        tuple(mapping.physical_instance_id for mapping in request.mappings)
        == request.candidate_instance_ids
    )
    assert request.semantic_placement_derivations_hash == (
        semantic_placement_derivations_hash(())
    )
    assert request.request_hash == candidate_request_hash_v3(request)
    assert "placement_derivations_hash" not in request.model_dump(mode="json")


def test_request_at3_pins_compiler_and_policy_literals(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    baseline = _request_at3(candidate, bound_request.semantic_source_binding_hash)
    with pytest.raises(ValueError, match="policy|compiler|literal"):
        CandidateCadRealizationRequestV3.model_validate(
            baseline.model_dump(mode="json")
            | {"representation_policy_version": "other-policy@9"}
        )
    with pytest.raises(ValueError, match="policy|compiler|literal"):
        CandidateCadRealizationRequestV3.model_validate(
            baseline.model_dump(mode="json") | {"compiler_identity": "other-compiler"}
        )


def _legacy_mapping_at1(candidate_hash, instance_id, *, index=0):
    from mechcad_harness.candidates import (
        CandidateCadInstanceMapping,
        CandidatePlacementOrigin,
    )

    transform = CadRigidTransform(x_mm=float(index * 20))
    return CandidateCadInstanceMapping(
        candidate_hash=candidate_hash,
        physical_instance_id=instance_id,
        cad_instance_id=f"cad-{instance_id}",
        fidelity="declared_bounded_collision_representation",
        representation_identity="sha256:" + "b" * 64,
        source_geometry_identity=None,
        geometry_definition_identities=("candidate:/mount-size",),
        placement=transform,
        placement_origin=CandidatePlacementOrigin(
            authority="candidate_design_variable",
            input_identities=("candidate:/mount-size",),
            derivation="mount-frame@1",
            transform=transform,
        ),
    )


def test_request_at3_rejects_legacy_mappings(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    legacy_mappings = tuple(
        _legacy_mapping_at1(candidate.candidate_hash, instance_id, index=index)
        for index, (instance_id, _) in enumerate(_INSTANCE_SLOTS)
    )
    with pytest.raises(ValueError, match="mapping@2|MappingV2|valid dictionary"):
        _request_at3(
            candidate,
            bound_request.semantic_source_binding_hash,
            mappings=legacy_mappings,
        )


def test_request_at3_derivation_closure_ignores_legacy_derivation_hash(tmp_path):
    from mechcad_harness.candidates import semantic_derivation_projection

    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    assert "derivation_hash" not in semantic_derivation_projection(_coaxial())
    assert "derivation_hash" not in semantic_derivation_projection(_frame_derivation())
    first = _request_at3(
        candidate,
        bound_request.semantic_source_binding_hash,
        derivations=(_coaxial(), _frame_derivation()),
    )
    second = _request_at3(
        candidate,
        bound_request.semantic_source_binding_hash,
        derivations=(_frame_derivation(), _coaxial()),
    )

    assert first.semantic_placement_derivations_hash == (
        second.semantic_placement_derivations_hash
    )
    assert first.request_hash == second.request_hash


def test_request_at3_derivation_inputs_must_match_by_input_id(tmp_path):
    from test_m13_2_placement_derivations import _rotation

    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    baseline = _frame_derivation()
    changed = _frame_derivation(rotation=_rotation(angle=45.0))
    first = _request_at3(
        candidate, bound_request.semantic_source_binding_hash, derivations=(baseline,)
    )
    second = _request_at3(
        candidate, bound_request.semantic_source_binding_hash, derivations=(changed,)
    )

    assert first.semantic_placement_derivations_hash != (
        second.semantic_placement_derivations_hash
    )


def test_request_at3_rejects_duplicate_mappings_and_derivations(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    mappings = tuple(
        _mapping_at2(candidate.candidate_hash, instance_id, slot, index=index)
        for index, (instance_id, slot) in enumerate(_INSTANCE_SLOTS)
    )
    with pytest.raises(ValueError, match="unique|duplicate|cover"):
        _request_at3(
            candidate,
            bound_request.semantic_source_binding_hash,
            mappings=(*mappings, mappings[0]),
        )
    with pytest.raises(ValueError, match="unique|duplicate"):
        _request_at3(
            candidate,
            bound_request.semantic_source_binding_hash,
            derivations=(_coaxial(), _coaxial()),
        )


def test_request_at3_identity_intersection_rules(tmp_path):
    _, _, _, _, bound_request, _, candidate = _at2_setup(tmp_path)
    request = _request_at3(candidate, bound_request.semantic_source_binding_hash)

    assert request.design_variable_identities == ()
    assert request.component_interface_identities == ()
    with pytest.raises(ValueError, match="identit"):
        CandidateCadRealizationRequestV3.model_validate(
            request.model_dump(mode="json")
            | {
                "design_variable_identities": (
                    "candidate:design-variable:undeclared",
                ),
                "request_hash": "pending",
            }
        )


def test_request_at3_pending_semantic_binding_cannot_hash(tmp_path):
    _, _, _, _, _, _, candidate = _at2_setup(tmp_path)
    pending = _request_at3(candidate, "pending")

    assert pending.semantic_source_binding_hash == "pending"
    assert pending.request_hash == "pending"
    with pytest.raises(ValueError, match="unbound|cannot have a request hash"):
        CandidateCadRealizationRequestV3.model_validate(
            pending.model_dump(mode="json") | {"request_hash": "sha256:" + "f" * 64}
        )
