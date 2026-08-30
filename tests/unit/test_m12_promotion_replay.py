from __future__ import annotations

from types import SimpleNamespace

from mechcad_harness.candidates import (
    CandidateCanonicalInstanceMapping,
    CandidatePromotionCompiler,
    PromotionValueClassification,
)
from mechcad_harness.candidates.models import (
    ComponentSpecificationSnapshot,
    MechanicalConnection,
    MechanicalConnectionKind,
    PhysicalComponentInstance,
    PhysicalComponentRole,
)

from test_m12_candidate_foundation import _candidate


def _external_candidate():
    candidate, _, _ = _candidate()
    driver_spec = ComponentSpecificationSnapshot(
        component_type="spur-gear",
        source_identity="source:driver-gear",
        interfaces=("gear",),
    )
    driven_spec = ComponentSpecificationSnapshot(
        component_type="spur-gear",
        source_identity="source:driven-gear",
        interfaces=("gear", "output"),
    )
    driver = PhysicalComponentInstance(
        instance_id="driver-gear",
        specification_hash=driver_spec.specification_hash,
        role=PhysicalComponentRole.TRANSMISSION,
        interfaces=driver_spec.interfaces,
    )
    driven = PhysicalComponentInstance(
        instance_id="driven-gear",
        specification_hash=driven_spec.specification_hash,
        role=PhysicalComponentRole.TRANSMISSION,
        interfaces=driven_spec.interfaces,
    )
    realization = candidate.realization.model_copy(
        update={
            "components": (*candidate.realization.components, driver, driven),
            "connections": (
                *candidate.realization.connections,
                MechanicalConnection(
                    connection_id="gear-mesh",
                    kind=MechanicalConnectionKind.GEAR_MESH,
                    from_instance_id="driver-gear",
                    from_interface_id="gear",
                    to_instance_id="driven-gear",
                    to_interface_id="gear",
                ),
            ),
            "realization_hash": "pending",
        }
    )
    return candidate.model_copy(
        update={
            "component_specifications": (
                *candidate.component_specifications,
                driver_spec,
                driven_spec,
            ),
            "realization": realization,
            "candidate_hash": "pending",
        }
    )


def _mapping(candidate):
    return tuple(
        CandidateCanonicalInstanceMapping(
            candidate_instance_id=component.instance_id,
            canonical_instance_id=f"PM-spur:{component.instance_id}",
            canonical_path=(
                f"/physical_mechanisms/PM-spur/components/PM-spur:{component.instance_id}"
            ),
            classification=PromotionValueClassification.ACCEPTED_PHYSICAL_FACT,
            source_identity=f"candidate:physical-instance:{component.instance_id}",
        )
        for component in candidate.realization.components
    )


def test_promotion_projection_preserves_external_spur_physical_graph_without_kinematic_upgrades():
    candidate = _external_candidate()
    request = SimpleNamespace(
        candidate=candidate,
        canonical_target_mechanism_id="PM-spur",
        request_hash="sha256:" + "a" * 64,
        classifications=(),
        evaluation=SimpleNamespace(m10_scope=None, m10_binding=None),
    )

    mechanism = CandidatePromotionCompiler._compile_mechanism(
        object.__new__(CandidatePromotionCompiler), request, _mapping(candidate)
    )

    assert {
        component.instance_id.removeprefix("PM-spur:")
        for component in mechanism.components
    } == {component.instance_id for component in candidate.realization.components}
    assert {
        (connection.connection_id, connection.kind.value)
        for connection in mechanism.connections
    } == {
        (connection.connection_id, connection.kind.value)
        for connection in candidate.realization.connections
    }
    gear_meshes = tuple(
        connection
        for connection in mechanism.connections
        if connection.kind.value == "gear_mesh"
    )
    assert len(gear_meshes) == 1
    assert gear_meshes[0].from_instance_id == "PM-spur:driver-gear"
    assert gear_meshes[0].to_instance_id == "PM-spur:driven-gear"
    assert not any(
        connection.kind.value == "coupling"
        and "gear" in {connection.from_instance_id, connection.to_instance_id}
        for connection in mechanism.connections
    )
    assert mechanism.joint_bindings == ()
    assert mechanism.m10_obligations == ()
