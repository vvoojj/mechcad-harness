from __future__ import annotations

import pytest

from mechcad_harness.cad_assembly import (
    CadAssemblyProgram,
    CadComponentInstance,
    CadRigidTransform,
    assembly_hash,
)
from mechcad_harness.cad_program import BasePlateOperation, CadPartProgram, cad_program_hash
from mechcad_harness.candidates import (
    CandidateCadInstanceMapping,
    CandidateCadRealization,
    CandidateCollisionPairClassification,
    CandidateCollisionPairInventory,
    CandidateGeometryFidelity,
    CandidateM10Binding,
    CandidateM10BodyDisposition,
    CandidateM10ConstituentDisposition,
    CandidateM10EvaluationRequest,
    CandidateM10EvaluationScope,
    CandidateM10PairClassification,
    CandidateM10PairScopeRequirement,
    candidate_m10_scope_hash,
)
from mechcad_harness.candidates.models import (
    MechanicalConnection,
    MechanicalConnectionKind,
    PhysicalComponentInstance,
    PhysicalComponentRole,
    PhysicalMechanismRealization,
)
from mechcad_harness.kinematic_sweep import RevoluteAxis
from mechcad_harness.multi_joint_kinematics import (
    KinematicModel,
    RevoluteJointModel,
    kinematic_model_hash,
)


def _hash(value: str) -> str:
    return "sha256:" + (value * 64)[:64]


def _realization() -> CandidateCadRealization:
    names = ("motor", "driver", "shaft", "bearing", "hub", "mount", "body")
    parts = tuple(
        CadPartProgram(
            part_id=f"part-{name}",
            operations=(
                BasePlateOperation(
                    operation_id=f"base-{name}",
                    length_mm=10,
                    width_mm=10,
                    thickness_mm=2,
                ),
            ),
        )
        for name in names
    )
    mappings = tuple(
        CandidateCadInstanceMapping(
            candidate_hash="sha256:" + "a" * 64,
            physical_instance_id=name,
            cad_instance_id=f"cad-{name}",
            fidelity=CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION,
            representation_identity=cad_program_hash(parts[index]),
            geometry_definition_identities=(f"candidate:geometry:{name}",),
            placement=CadRigidTransform(x_mm=float(index * 20)),
            placement_origin={
                "authority": "deterministic_derived_relation",
                "input_identities": (f"candidate:placement:{name}",),
                "derivation": "fixture-placement@1",
                "transform": CadRigidTransform(x_mm=float(index * 20)),
            },
        )
        for index, name in enumerate(names)
    )
    assembly = CadAssemblyProgram(
        assembly_id="candidate-assembly",
        parts=parts,
        instances=tuple(
            CadComponentInstance(
                instance_id=f"cad-{name}",
                part_id=f"part-{name}",
                placement=mapping.placement,
            )
            for name, mapping in zip(names, mappings, strict=True)
        ),
    )
    return CandidateCadRealization(
        candidate_hash="sha256:" + "a" * 64,
        request_hash="sha256:" + "b" * 64,
        mappings=mappings,
        assembly=assembly,
        assembly_hash=assembly_hash(assembly),
        compiler_identity="test-compiler",
        compiler_version="1",
        provider_identity="test-provider",
    )


def _model() -> KinematicModel:
    return KinematicModel(
        model_id="m12-output-model",
        joints=(
            RevoluteJointModel(
                joint_id="output-joint",
                parent_instance_id="cad-mount",
                child_instance_id="cad-shaft",
                axis_origin_x_mm=20,
                axis_direction_z=1,
            ),
        ),
    )


def _binding(
    realization: CandidateCadRealization,
    *,
    driver_fixed=False,
    driver_gear_constituent_key="driver",
    constituent_key_overrides=None,
):
    constituent_key_overrides = constituent_key_overrides or {}
    disposition = {
        "motor": CandidateM10BodyDisposition.FIXED,
        "driver": CandidateM10BodyDisposition.FIXED if driver_fixed else CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED,
        "shaft": CandidateM10BodyDisposition.OUTPUT_RIGID,
        "bearing": CandidateM10BodyDisposition.FIXED,
        "hub": CandidateM10BodyDisposition.OUTPUT_RIGID,
        "mount": CandidateM10BodyDisposition.FIXED,
        "body": CandidateM10BodyDisposition.OUTPUT_RIGID,
    }
    groups = {"shaft": "output-joint", "hub": "output-joint", "body": "output-joint"}
    return CandidateM10Binding(
        candidate_hash=realization.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        model=_model(),
        output_joint_id="output-joint",
        driver_gear_constituent_key=driver_gear_constituent_key,
        output_axis=RevoluteAxis(
            origin_x_mm=120,
            origin_y_mm=0,
            origin_z_mm=0,
            direction_x=0,
            direction_y=0,
            direction_z=1,
            frame_id="joint:output-joint",
        ),
        constituent_dispositions=tuple(
            CandidateM10ConstituentDisposition(
                physical_instance_id=name,
                cad_instance_id=f"cad-{name}",
                constituent_key=constituent_key_overrides.get(name, name),
                disposition=disposition[name],
                output_transform_group=groups.get(name),
            )
            for name in disposition
        ),
    )


def _scope() -> CandidateM10EvaluationScope:
    return CandidateM10EvaluationScope(
        output_joint_semantic_key="primary-output-revolute",
        angle_interval_deg=(-45.0, 45.0),
        required_clearance_mm=1.0,
        pair_scope_requirements=(
            CandidateM10PairScopeRequirement(
                requirement_key="hub-mount-clearance",
                first_constituent_key="hub",
                second_constituent_key="mount",
                required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
            ),
            CandidateM10PairScopeRequirement(
                requirement_key="shaft-bearing-contact",
                first_constituent_key="shaft",
                second_constituent_key="bearing",
                required_classification=CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED,
            ),
            CandidateM10PairScopeRequirement(
                requirement_key="driver-internal-motion",
                first_constituent_key="driver",
                second_constituent_key="mount",
                required_classification=CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE,
                requires_home_exact_check=True,
            ),
        ),
        fidelity_requirements=(
            ("hub", CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
            ("mount", CandidateGeometryFidelity.DECLARED_BOUNDED_COLLISION_REPRESENTATION),
        ),
        required_home_check_semantics=("exact-home-nonintended-interference@1",),
        proof_service_version="m10-single-axis-continuous-proof@1",
        policy_assumptions=("unmodeled-internal-motion-is-not-continuously-certified",),
    )


def _inventory(realization, binding, scope, *, omit=(), reclassify=()):
    ids = tuple(sorted(instance.instance_id for instance in realization.assembly.instances))
    required = {
        tuple(sorted((
            f"cad-{requirement.first_constituent_key}",
            f"cad-{requirement.second_constituent_key}",
        ))): requirement
        for requirement in scope.pair_scope_requirements
    }
    classifications = []
    for index, first in enumerate(ids):
        for second in ids[index + 1 :]:
            pair = (first, second)
            requirement = required.get(pair)
            kind = (
                requirement.required_classification
                if requirement is not None
                else CandidateM10PairClassification.OTHER_EXPLICIT_OUT_OF_SCOPE
            )
            if pair in reclassify:
                kind = CandidateM10PairClassification.SAME_RIGID_GROUP_EXCLUDED
            classifications.append(
                CandidateCollisionPairClassification(
                    pair=pair,
                    classification=kind,
                    reason=None if kind is CandidateM10PairClassification.CHECK_CLEARANCE else "not required by the declared M10 engineering scope",
                    requires_home_exact_check=bool(requirement and requirement.requires_home_exact_check),
                )
            )
    classifications = tuple(
        item for item in classifications if item.pair not in set(omit)
    )
    return CandidateCollisionPairInventory.complete_for(
        realization, binding, scope, classifications
    )


def test_dispositions_are_exhaustive_and_shared_output_transforms_keep_constituents_distinct():
    realization = _realization()
    binding = _binding(realization)

    assert {entry.disposition for entry in binding.constituent_dispositions} == {
        CandidateM10BodyDisposition.FIXED,
        CandidateM10BodyDisposition.OUTPUT_RIGID,
        CandidateM10BodyDisposition.INTERNAL_MOTION_UNMODELED,
    }
    assert binding.output_rigid_cad_instance_ids == (
        "cad-body",
        "cad-hub",
        "cad-shaft",
    )
    assert len(binding.output_rigid_cad_instance_ids) == len(set(binding.output_rigid_cad_instance_ids))


def test_driver_gear_cannot_be_declared_fixed():
    with pytest.raises(ValueError, match="driver.*fixed"):
        _binding(_realization(), driver_fixed=True)


def test_driver_gear_marker_is_candidate_bound_and_unrelated_names_are_not_inferred():
    realization = _realization()
    with pytest.raises(ValueError, match="driver.*fixed"):
        _binding(
            realization,
            driver_fixed=True,
            driver_gear_constituent_key="input_gear",
            constituent_key_overrides={"driver": "input_gear"},
        )

    binding = _binding(
        realization,
        driver_gear_constituent_key=None,
        constituent_key_overrides={"motor": "driver-housing"},
    )
    assert binding.disposition_for("cad-motor").disposition is CandidateM10BodyDisposition.FIXED


@pytest.mark.parametrize("field", ("candidate_hash", "cad_realization_hash"))
def test_inventory_requires_exact_binding_realization_identity(field):
    realization = _realization()
    binding = _binding(realization)
    forged_binding = binding.model_copy(
        update={field: _hash("c" if field == "candidate_hash" else "d")}
    )

    with pytest.raises(ValueError, match="candidate|realization"):
        CandidateCollisionPairInventory.complete_for(realization, forged_binding, _scope())


def test_binding_identity_is_revalidated_against_realization():
    realization = _realization()
    binding = _binding(realization)

    forged_candidate = binding.model_copy(update={"candidate_hash": _hash("c")})
    with pytest.raises(ValueError, match="candidate"):
        forged_candidate.validate_against(realization)

    forged_realization = binding.model_copy(update={"cad_realization_hash": _hash("d")})
    with pytest.raises(ValueError, match="realization"):
        forged_realization.validate_against(realization)


def test_binding_validates_parent_local_axis_as_declared_world_axis():
    realization = _realization()
    binding = _binding(realization)

    binding.validate_against(realization)


def test_binding_rejects_world_axis_that_ignores_non_origin_parent_placement():
    realization = _realization()
    binding = _binding(realization).model_copy(
        update={
            "output_axis": RevoluteAxis(
                origin_x_mm=20,
                origin_y_mm=0,
                origin_z_mm=0,
                direction_x=0,
                direction_y=0,
                direction_z=1,
                frame_id="joint:output-joint",
            ),
            "binding_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="parent|world|axis"):
        binding.validate_against(realization)


def test_binding_rejects_a_joint_parent_missing_from_exact_cad_realization():
    realization = _realization()
    binding = _binding(realization).model_copy(
        update={
            "model": _model().model_copy(
                update={
                    "joints": (
                        _model().joints[0].model_copy(
                            update={"parent_instance_id": "cad-missing"}
                        ),
                    )
                }
            ),
            "binding_hash": "pending",
        }
    )

    with pytest.raises(ValueError, match="parent"):
        binding.validate_against(realization)


def _realization_with_stale_changed_mapping(realization):
    changed_transform = CadRigidTransform(x_mm=999.0)
    changed_origin = realization.mappings[0].placement_origin.model_copy(
        update={"transform": changed_transform, "origin_hash": "pending"}
    )
    changed_mapping = realization.mappings[0].model_copy(
        update={
            "placement": changed_transform,
            "placement_origin": changed_origin,
            "mapping_hash": "pending",
        }
    )
    return realization.model_copy(
        update={
            "mappings": (changed_mapping, *realization.mappings[1:]),
        }
    )


def test_binding_revalidates_changed_realization_content_not_only_stored_hash():
    realization = _realization()
    binding = _binding(realization)
    forged_realization = _realization_with_stale_changed_mapping(realization)

    assert forged_realization.realization_hash == realization.realization_hash
    with pytest.raises(ValueError, match="realization|placement"):
        binding.validate_against(forged_realization)


def test_inventory_revalidates_changed_realization_content_not_only_stored_hash():
    realization = _realization()
    binding = _binding(realization)
    forged_realization = _realization_with_stale_changed_mapping(realization)

    assert forged_realization.realization_hash == realization.realization_hash
    with pytest.raises(ValueError, match="realization|placement"):
        CandidateCollisionPairInventory.complete_for(forged_realization, binding, _scope())


def test_driver_gear_must_be_internal_motion_unmodeled():
    with pytest.raises(ValueError, match="driver.*internal|unmodeled"):
        _binding(_realization(), driver_gear_constituent_key="shaft")


def test_external_spur_driver_is_not_fixed_when_driver_marker_is_omitted():
    realization = _realization()
    physical = PhysicalMechanismRealization(
        components=tuple(
            PhysicalComponentInstance(
                instance_id=name,
                specification_hash="sha256:" + "e" * 64,
                role=(
                    PhysicalComponentRole.TRANSMISSION
                    if name in {"driver", "driven"}
                    else PhysicalComponentRole.MOUNT_OR_SUPPORT
                ),
                interfaces=("mesh",),
            )
            for name in ("driver", "driven", "mount")
        ),
        connections=(
            MechanicalConnection(
                connection_id="gear-mesh",
                kind=MechanicalConnectionKind.GEAR_MESH,
                from_instance_id="driver",
                from_interface_id="mesh",
                to_instance_id="driven",
                to_interface_id="mesh",
            ),
        ),
    )
    binding = _binding(
        realization,
        driver_fixed=True,
        driver_gear_constituent_key=None,
    )

    with pytest.raises(ValueError, match="driver.*fixed|motion"):
        binding.validate_against(realization, physical)


def test_external_spur_driver_marker_is_required_when_topology_is_available():
    realization = _realization()
    physical = PhysicalMechanismRealization(
        components=tuple(
            PhysicalComponentInstance(
                instance_id=name,
                specification_hash="sha256:" + "e" * 64,
                role=(
                    PhysicalComponentRole.TRANSMISSION
                    if name in {"driver", "driven"}
                    else PhysicalComponentRole.MOUNT_OR_SUPPORT
                ),
                interfaces=("mesh",),
            )
            for name in ("driver", "driven", "mount")
        ),
        connections=(
            MechanicalConnection(
                connection_id="gear-mesh",
                kind=MechanicalConnectionKind.GEAR_MESH,
                from_instance_id="driver",
                from_interface_id="mesh",
                to_instance_id="driven",
                to_interface_id="mesh",
            ),
        ),
    )
    binding = _binding(realization, driver_gear_constituent_key=None)

    with pytest.raises(ValueError, match="driver.*marker|driver.*constituent"):
        binding.validate_against(realization, physical)


def test_home_exact_check_requires_a_declared_scope_pair():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    baseline = _inventory(realization, binding, scope)
    undeclared_home_check = CandidateCollisionPairClassification(
        pair=("cad-body", "cad-driver"),
        classification=CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE,
        reason="internal motion is not continuously modeled",
        requires_home_exact_check=True,
    )
    classifications = tuple(
        undeclared_home_check if item.pair == undeclared_home_check.pair else item
        for item in baseline.classifications
    )

    with pytest.raises(ValueError, match="home.*scope|scope.*home"):
        CandidateCollisionPairInventory.complete_for(realization, binding, scope, classifications)


def test_scope_required_constituent_keys_must_exist_in_binding():
    realization = _realization()
    binding = _binding(realization)
    scope_data = _scope().model_dump(mode="python")
    scope_data["pair_scope_requirements"] = (
        CandidateM10PairScopeRequirement(
            requirement_key="missing-constituent-pair",
            first_constituent_key="missing",
            second_constituent_key="mount",
            required_classification=CandidateM10PairClassification.CHECK_CLEARANCE,
        ),
        *scope_data["pair_scope_requirements"][1:],
    )
    scope_data["scope_hash"] = "pending"
    scope = CandidateM10EvaluationScope(**scope_data)

    with pytest.raises(ValueError, match="scope.*constituent"):
        CandidateCollisionPairInventory.complete_for(realization, binding, scope)


def test_scope_hash_is_candidate_independent_but_semantic_changes_are_bound():
    first = _scope()
    second = _scope().model_copy(update={"required_clearance_mm": 2.0, "scope_hash": "pending"})

    assert candidate_m10_scope_hash(first) == first.scope_hash
    assert candidate_m10_scope_hash(first) != candidate_m10_scope_hash(second)
    assert candidate_m10_scope_hash(first) == candidate_m10_scope_hash(_scope())


def test_inventory_rejects_omitted_pairs_and_reclassification():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    with pytest.raises(ValueError, match="complete|omitted"):
        _inventory(realization, binding, scope, omit=(("cad-body", "cad-motor"),))

    with pytest.raises(ValueError, match="classification|scope"):
        _inventory(realization, binding, scope, reclassify=(("cad-hub", "cad-mount"),))


def test_unmodeled_home_check_remains_in_inventory_as_a_distinct_requirement():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    inventory = _inventory(realization, binding, scope)
    entry = next(item for item in inventory.classifications if item.pair == ("cad-driver", "cad-mount"))

    assert entry.classification is CandidateM10PairClassification.UNMODELED_MOTION_OUT_OF_SCOPE
    assert entry.requires_home_exact_check is True

    hub_mount = next(item for item in inventory.classifications if item.pair == ("cad-hub", "cad-mount"))
    shaft_bearing = next(item for item in inventory.classifications if item.pair == ("cad-bearing", "cad-shaft"))
    assert hub_mount.classification is CandidateM10PairClassification.CHECK_CLEARANCE
    assert shaft_bearing.classification is CandidateM10PairClassification.INTENDED_CONTACT_EXCLUDED
    assert hub_mount.pair in inventory.checked_pairs
    assert shaft_bearing.pair in inventory.excluded_pairs

    derived = CandidateCollisionPairInventory.complete_for(realization, binding, scope)
    assert derived.expected_pair_universe == inventory.expected_pair_universe
    assert derived.classifications == inventory.classifications


def test_request_binds_candidate_realization_binding_scope_and_complete_inventory():
    realization = _realization()
    binding = _binding(realization)
    scope = _scope()
    inventory = _inventory(realization, binding, scope)
    request = CandidateM10EvaluationRequest(
        candidate_hash=realization.candidate_hash,
        cad_realization_hash=realization.realization_hash,
        binding_hash=binding.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=kinematic_model_hash(binding.model),
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization.mappings)),
        inventory=inventory,
    )

    assert request.request_hash.startswith("sha256:")
    request.validate_against(realization, binding, scope)
    forged_binding = binding.model_copy(update={"candidate_hash": _hash("c")})
    with pytest.raises(ValueError, match="candidate"):
        request.validate_against(realization, forged_binding, scope)
    with pytest.raises(ValueError, match="scope"):
        request.validate_against(
            realization,
            binding,
            scope.model_copy(update={"required_clearance_mm": 2.0, "scope_hash": "pending"}),
        )


def test_equivalent_candidates_share_scope_but_have_distinct_requests():
    scope = _scope()
    realization_a = _realization()
    realization_b = _realization().model_copy(
        update={
            "candidate_hash": "sha256:" + "c" * 64,
            "realization_hash": "pending",
            "mappings": tuple(
                mapping.model_copy(
                    update={
                        "candidate_hash": "sha256:" + "c" * 64,
                        "mapping_hash": "pending",
                    }
                )
                for mapping in _realization().mappings
            ),
        }
    )
    # Rebuild the copied realization through validation so its derived identity is fresh.
    realization_b = CandidateCadRealization.model_validate(realization_b.model_dump(mode="python"))
    binding_a = _binding(realization_a)
    binding_b = _binding(realization_b)
    inventory_a = _inventory(realization_a, binding_a, scope)
    inventory_b = _inventory(realization_b, binding_b, scope)
    request_a = CandidateM10EvaluationRequest(
        candidate_hash=realization_a.candidate_hash,
        cad_realization_hash=realization_a.realization_hash,
        binding_hash=binding_a.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding_a.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization_a.mappings)),
        inventory=inventory_a,
    )
    request_b = CandidateM10EvaluationRequest(
        candidate_hash=realization_b.candidate_hash,
        cad_realization_hash=realization_b.realization_hash,
        binding_hash=binding_b.binding_hash,
        scope_hash=scope.scope_hash,
        model_hash=binding_b.model_hash,
        mapping_hashes=tuple(sorted(mapping.mapping_hash for mapping in realization_b.mappings)),
        inventory=inventory_b,
    )

    assert request_a.scope_hash == request_b.scope_hash
    assert request_a.request_hash != request_b.request_hash
