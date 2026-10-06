from __future__ import annotations

from hashlib import sha256

import pytest

from mechcad_harness.artifacts import ArtifactStore, ArtifactType
from mechcad_harness.cad_assembly import CadRigidTransform
from mechcad_harness.candidates.canonical_cad import (
    CanonicalCadIntegrityError,
    CanonicalPhysicalCadCompiler,
    CanonicalPhysicalCadMappingV2,
    canonical_physical_cad_mapping_hash_v2,
    semantic_canonical_placement_hash,
    validate_canonical_cad_compiler_literals,
)
from mechcad_harness.candidates.canonical_mechanism import (
    CanonicalMechanismReconstruction,
    ProjectArtifactResolver,
    TrustedSourceArtifact,
    _projection_from_mechanism,
)
from mechcad_harness.candidates.promotion import CandidatePromotionCompiler
from mechcad_harness.candidates.promotion_models import (
    CandidateCanonicalInstanceMapping,
    CandidateCanonicalInstanceMappingV3,
    CandidatePromotionPolicy,
    PromotionValueClassification,
)
from mechcad_harness.candidates.cad_realization import (
    trusted_representation_identity,
)
from mechcad_harness.models import CanonicalGeometryFidelity
from mechcad_harness.models.generated_part import generated_geometry_definition_identities
from mechcad_harness.models.physical_mechanism import CanonicalPlacementOrigin

from test_canonical_mechanism_v4 import _STEP_TEMPLATE, _mechanism_at4
from test_m13_2_generated_part_models import _shaft


def _mapping(mechanism, instance_id):
    component = next(item for item in mechanism.components if item.instance_id == instance_id)
    specification = next(
        item
        for item in mechanism.component_specifications
        if item.specification_hash == component.specification_hash
    )
    placement = next(
        (item for item in mechanism.placements if item.instance_id == instance_id), None
    )
    cad_id = f"canonical-{mechanism.id}-{instance_id}"
    transform = CadRigidTransform(
        **(
            {}
            if placement is None
            else {
                "x_mm": placement.x_mm,
                "y_mm": placement.y_mm,
                "z_mm": placement.z_mm,
                "rotation_quaternion": placement.rotation_quaternion,
            }
        )
    )
    source = specification.geometry_source
    if source is None:
        source_identity = None
        definitions = generated_geometry_definition_identities(specification.generated_part)
        representation_identity = "sha256:" + "b" * 64
    else:
        from mechcad_harness.candidates.cad_realization import SemanticSourceGeometryIdentity

        source_identity = SemanticSourceGeometryIdentity(
            content_identity=source.content_identity,
            content_identity_algorithm=source.content_identity_algorithm,
        )
        definitions = (source.content_identity,)
        representation_identity = trusted_representation_identity(
            slot=cad_id, content_identity=source.content_identity
        )
    inputs = (
        (component.component_hash,)
        if placement is None
        else tuple(
            source.content_identity
            if identity.startswith("ART-")
            else identity
            for identity in placement.input_identities
        )
    )
    return CanonicalPhysicalCadMappingV2(
        mechanism_hash=mechanism.mechanism_hash,
        physical_instance_id=instance_id,
        cad_instance_id=cad_id,
        component_hash=component.component_hash,
        specification_hash=specification.specification_hash,
        fidelity=(
            CanonicalGeometryFidelity.TRUSTED_SOURCE_GEOMETRY
            if source is not None
            else CanonicalGeometryFidelity.EXACT_GENERATED_GEOMETRY
        ),
        representation_identity=representation_identity,
        source_geometry_identity=source_identity,
        geometry_definition_identities=tuple(definitions),
        placement=transform,
        placement_id=None if placement is None else placement.placement_id,
        placement_input_identities=tuple(inputs),
        placement_relation=(
            "canonical-default-home-placement@1"
            if placement is None
            else placement.relation
        ),
    )


def _bound_mapping(mechanism, instance_id):
    mapping = _mapping(mechanism, instance_id)
    digest = canonical_physical_cad_mapping_hash_v2(mapping, mechanism)
    return mapping.model_copy(update={"mapping_hash": digest})


def test_canonical_mapping_at2_has_exact_15_fields_and_raw_free_identity():
    mechanism = _mechanism_at4()
    mapping = _bound_mapping(mechanism, "instance-parent")

    assert set(CanonicalPhysicalCadMappingV2.model_fields) == {
        "schema_version",
        "mechanism_hash",
        "physical_instance_id",
        "cad_instance_id",
        "component_hash",
        "specification_hash",
        "fidelity",
        "representation_identity",
        "source_geometry_identity",
        "geometry_definition_identities",
        "placement",
        "placement_id",
        "placement_input_identities",
        "placement_relation",
        "mapping_hash",
    }
    assert mapping.mapping_hash == canonical_physical_cad_mapping_hash_v2(
        mapping, mechanism
    )
    assert "ART-MOUNT-A" not in repr(mapping.model_dump(mode="json"))
    assert mapping.source_geometry_identity.content_identity == (
        mapping.geometry_definition_identities[0]
    )


def test_canonical_mapping_at2_is_invariant_to_raw_step_rotation():
    first_mechanism = _mechanism_at4(variant="A")
    second_mechanism = _mechanism_at4(variant="B")
    first = _bound_mapping(first_mechanism, "instance-child")
    second = _bound_mapping(second_mechanism, "instance-child")

    assert first_mechanism.mechanism_hash == second_mechanism.mechanism_hash
    assert first.placement_input_identities == second.placement_input_identities
    assert first.placement_input_identities == (
        first.source_geometry_identity.content_identity,
    )
    assert first.mapping_hash == second.mapping_hash


def test_canonical_mapping_at2_binds_mechanism_placement_semantics():
    mechanism = _mechanism_at4()
    mapping = _bound_mapping(mechanism, "instance-child")

    assert mapping.placement_id == "placement-instance-child"
    assert mapping.placement_input_identities == (
        mapping.source_geometry_identity.content_identity,
    )
    assert mapping.mapping_hash == canonical_physical_cad_mapping_hash_v2(
        mapping, mechanism
    )
    changed_placement = type(mechanism.placements[0]).model_validate(
        mechanism.placements[0].model_dump(mode="python")
        | {
            "origin": CanonicalPlacementOrigin.EXPLICIT_POLICY_ASSUMPTION,
            "placement_hash": "pending",
        }
    )
    changed_mechanism = type(mechanism).model_validate(
        mechanism.model_dump(mode="python")
        | {"placements": (changed_placement,), "mechanism_hash": "pending"}
    )
    changed_mapping = _bound_mapping(changed_mechanism, "instance-child")
    assert changed_mapping.mapping_hash != mapping.mapping_hash


def test_semantic_canonical_placement_hash_preserves_origin_and_placement():
    mechanism = _mechanism_at4()
    placement = mechanism.placements[0]
    digest = semantic_canonical_placement_hash(
        placement=placement,
        mapping_instance_id=placement.instance_id,
        geometry_identities=mechanism.component_specifications,
    )
    changed = type(placement).model_validate(
        placement.model_dump(mode="python")
        | {
            "origin": CanonicalPlacementOrigin.EXPLICIT_POLICY_ASSUMPTION,
            "placement_hash": "pending",
        }
    )
    changed_digest = semantic_canonical_placement_hash(
        placement=changed,
        mapping_instance_id=changed.instance_id,
        geometry_identities=mechanism.component_specifications,
    )

    assert digest.startswith("sha256:")
    assert digest != changed_digest


def test_canonical_placement_hash_rejects_mismatched_mapping_instance():
    mechanism = _mechanism_at4()
    placement = mechanism.placements[0]
    with pytest.raises(ValueError, match="instance"):
        semantic_canonical_placement_hash(
            placement=placement,
            mapping_instance_id="foreign-instance",
            geometry_identities=mechanism.component_specifications,
        )


def test_mapping_at2_rejects_legacy_schema_and_placement_hash_contract():
    mechanism = _mechanism_at4()
    mapping = _mapping(mechanism, "instance-parent")
    legacy_payload = mapping.model_dump(mode="json") | {
        "schema_version": "canonical-physical-cad-mapping@1",
        "placement_hash": "sha256:" + "f" * 64,
    }

    with pytest.raises(ValueError):
        CanonicalPhysicalCadMappingV2.model_validate(legacy_payload)


def test_generated_geometry_definition_identities_use_sorted_unique_output():
    generated = _shaft()
    identities = generated_geometry_definition_identities(generated)
    assert identities == tuple(sorted(set(identities)))


def test_candidate_canonical_mapping_at3_is_scalar_and_exact():
    from mechcad_harness.core.canonical import canonical_json_bytes
    from hashlib import sha256

    mapping = CandidateCanonicalInstanceMappingV3(
        candidate_instance_id="shaft",
        canonical_instance_id="PM-1:shaft",
        canonical_path="/physical_mechanisms/PM-1/components/PM-1:shaft",
        classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
        source_identity="candidate:physical-instance:shaft",
    )

    assert set(CandidateCanonicalInstanceMappingV3.model_fields) == {
        "schema_version",
        "candidate_instance_id",
        "canonical_instance_id",
        "canonical_path",
        "classification",
        "source_identity",
        "source_provenance",
        "source_value",
        "mapping_hash",
    }
    assert mapping.schema_version == "candidate-canonical-mapping@3"
    assert mapping.mapping_hash.startswith("sha256:")
    payload = mapping.model_dump(mode="json")
    actual = payload.pop("mapping_hash")
    assert actual == "sha256:" + sha256(canonical_json_bytes(payload)).hexdigest()
    assert "schema_version" not in CandidateCanonicalInstanceMapping.model_fields


def test_promotion_policy_keeps_legacy_reads_but_accepts_candidate_mapping_at3():
    legacy = CandidatePromotionPolicy()
    new_family = CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@3")

    assert legacy.mapping_schema_version == "candidate-canonical-mapping@1"
    assert new_family.mapping_schema_version == "candidate-canonical-mapping@3"


def test_candidate_promotion_mapping_admission_is_versioned_and_literal(tmp_path):
    _, _, _, _, _, _, candidate = __import__(
        "test_candidate_trusted_semantic_verification"
    )._at2_setup(tmp_path)
    compiler = object.__new__(CandidatePromotionCompiler)

    compiler._verify_policy(
        CandidatePromotionPolicy(
            mapping_schema_version="candidate-canonical-mapping@3",
            compiler_version="candidate-promotion@1",
        ),
        candidate,
    )
    with pytest.raises(ValueError, match="mapping schema"):
        compiler._verify_policy(
            CandidatePromotionPolicy(mapping_schema_version="candidate-canonical-mapping@2"),
            candidate,
        )
    with pytest.raises(ValueError, match="compiler version"):
        compiler._verify_policy(
            CandidatePromotionPolicy(
                mapping_schema_version="candidate-canonical-mapping@3",
                compiler_version="candidate-promotion@99",
            ),
            candidate,
        )


@pytest.mark.parametrize(
    ("identity", "version"),
    [
        ("canonical-physical-cad-compiler", "wrong-version"),
        ("foreign-canonical-compiler", "canonical-cad@1"),
    ],
)
def test_canonical_cad_v2_compiler_literals_fail_closed(identity, version):
    with pytest.raises(ValueError, match="compiler"):
        validate_canonical_cad_compiler_literals(identity, version)


def test_canonical_cad_v2_admission_rejects_caller_compiler_override(tmp_path):
    mechanism = _mechanism_at4()
    step_bytes = _STEP_TEMPLATE.format(timestamp="2026-09-22T12:34:56").encode()
    state_hash = "sha256:" + "a" * 64
    store = ArtifactStore(tmp_path, project_id="PRJ-CAD-V4", run_id="SOURCE")
    references = []
    for artifact_id in ("ART-MOUNT-A", "ART-SHAFT-A"):
        artifact = store.publish(
            artifact_id,
            ArtifactType.STEP,
            f"{artifact_id.lower()}.step",
            step_bytes,
            "fixture-freecad",
            "1.1.3",
            1,
            state_hash,
        )
        references.append(TrustedSourceArtifact.from_artifact(artifact))
    reconstruction = CanonicalMechanismReconstruction(
        project_id="PRJ-CAD-V4",
        revision=1,
        state_hash=state_hash,
        canonical_mechanism=mechanism,
        trusted_source_references=tuple(references),
        normalized_projection_hash=_projection_from_mechanism(mechanism).projection_hash,
    )
    resolver = ProjectArtifactResolver(
        ArtifactStore(tmp_path, project_id="PRJ-CAD-V4", run_id="LOOKUP")
    )
    compiler = CanonicalPhysicalCadCompiler(
        resolver,
        compiler_identity="caller-override",
        compiler_version="canonical-cad@1",
    )

    with pytest.raises(CanonicalCadIntegrityError, match="compiler literals"):
        compiler.realize(reconstruction)
